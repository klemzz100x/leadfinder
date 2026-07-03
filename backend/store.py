"""Persistance PostgreSQL (Neon) — upsert idempotent.

Clé primaire stable : identifiant de source (ex. "node:123456" pour OSM).
Re-scanner une ville = mise à jour propre, aucun doublon.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg

from .categories import load_categories, types_to_category
from .config import settings
from .departements import postcode_to_departement

_POSTCODE_RE = re.compile(r"\b(\d{5})\b")

log = logging.getLogger("leadfinder.store")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS leads (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    address         TEXT,
    phone           TEXT,
    website         TEXT,
    web_status      TEXT NOT NULL,
    business_type   TEXT NOT NULL,
    score           REAL NOT NULL DEFAULT 0,
    temperature     TEXT NOT NULL,
    audit_json      TEXT,
    called          INTEGER NOT NULL DEFAULT 0,
    outcome         TEXT,
    notes           TEXT,
    city            TEXT NOT NULL,
    lat             REAL NOT NULL,
    lng             REAL NOT NULL,
    source          TEXT NOT NULL DEFAULT 'osm',
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL
)
"""

_CREATE_IDX_CITY = "CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city)"
_CREATE_IDX_TEMP = "CREATE INDEX IF NOT EXISTS idx_leads_temp ON leads(temperature)"

# ── Phase 1 : signal Google Places (vérification statut + site existant) ──────
_ALTER_STATEMENTS = [
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_status TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_website TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_url TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_checked_at TEXT",
    # ── Phase 2 : filtre département ───────────────────────────────────────
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS postcode TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS departement TEXT",
    "CREATE INDEX IF NOT EXISTS idx_leads_dept ON leads(departement)",
    # ── Phase 3 : budgets de closing (dashboard) ────────────────────────────
    # NB : budget_propose/budget_final sur list_leads sont désormais mortes
    # (plus lues ni écrites, cf. Phase 5 ci-dessous) — conservées comme filet
    # de sécurité, suppression dans un nettoyage ultérieur séparé.
    "ALTER TABLE list_leads ADD COLUMN IF NOT EXISTS budget_propose REAL",
    "ALTER TABLE list_leads ADD COLUMN IF NOT EXISTS budget_final REAL",
    # ── Usage partagé (Daniel/Clément) : visibilité, pas séparation des données ──
    "ALTER TABLE list_leads ADD COLUMN IF NOT EXISTS assigned_to TEXT",
    # ── Assignation + priorité au niveau de la liste elle-même (pas seulement
    # par lead) : qui suit cette liste, et son urgence relative ──
    "ALTER TABLE prospect_lists ADD COLUMN IF NOT EXISTS assigned_to TEXT",
    "ALTER TABLE prospect_lists ADD COLUMN IF NOT EXISTS priorite TEXT",
    # ── Phase 5 : statut partagé entre listes ────────────────────────────────
    # Le statut d'un établissement (et ce qui en découle : devis, closing)
    # est une propriété du LEAD, pas de sa relation à telle ou telle liste —
    # sinon un même établissement présent dans 2 listes peut afficher 2
    # statuts différents, avec le risque concret de le rappeler deux fois.
    # `list_leads.status/budget_propose/budget_final/closed_at` restent en
    # base (filet de sécurité) mais ne sont plus lues/écrites après migration
    # (cf. backend/migrate_shared_status.py) — la source de vérité est ici.
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'a_contacter'",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS budget_propose REAL",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS budget_final REAL",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS closed_at TEXT",
    # Horodatage du dernier changement de statut — sert de tri pour la
    # todo-list des rappels (remplace list_leads.updated_at, qui ne bouge
    # plus au changement de statut désormais stocké sur `leads`).
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS status_updated_at TEXT",
    "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
    # ── Phase 6 : date d'envoi réelle du devis ──────────────────────────────
    # Le statut 'devis_envoye' est en pratique utilisé comme "en cours de
    # préparation", pas "réellement envoyé" — plutôt que de changer ce
    # fonctionnement déjà pris en main, on ajoute une coche indépendante avec
    # sa date, pour pouvoir relancer sur la base d'un vrai envoi (cf.
    # get_devis_a_relancer). NULL = pas (encore) coché envoyé.
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS devis_envoye_le TEXT",
    "CREATE INDEX IF NOT EXISTS idx_leads_devis_envoye_le ON leads(devis_envoye_le)",
    # ── Phase 7 : signaux Google Places pour le prix de devis suggéré ───────
    # Récupérés au même appel Place Details que gmaps_status/website (même
    # tier de facturation "Enterprise" que websiteUri, donc coût marginal
    # nul — cf. backend/pricing.py pour l'utilisation).
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_rating REAL",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS gmaps_user_ratings_total INTEGER",
]

# Historique des scans (ville ou département) — évite qu'un scan déjà fait
# par une personne soit relancé sans le savoir par l'autre (base partagée,
# mais aucune visibilité sur "qui a scanné quoi et quand" jusqu'ici).
_CREATE_SCAN_HISTORY = """
CREATE TABLE IF NOT EXISTS scan_history (
    id          TEXT PRIMARY KEY,
    area_type   TEXT NOT NULL,   -- 'ville' | 'departement'
    area_code   TEXT NOT NULL,   -- code département, ou nom de ville normalisé
    area_name   TEXT NOT NULL,
    scanned_by  TEXT,
    scanned_at  TEXT NOT NULL,
    total_found INTEGER NOT NULL DEFAULT 0,
    api_calls   INTEGER NOT NULL DEFAULT 0
)
"""
_CREATE_IDX_SCAN_HISTORY = (
    "CREATE INDEX IF NOT EXISTS idx_scan_history_area ON scan_history(area_type, area_code)"
)

# Prédicat du pipeline actif : exclut les leads déjà équipés (site trouvé côté
# Google) et les établissements fermés définitivement. Réutilisé par les stats
# département (Phase 4).
_ACTIVE_PIPELINE_WHERE = "(gmaps_website IS NULL) AND (gmaps_status IS DISTINCT FROM 'closed_permanently')"

_CREATE_PROSPECT_LISTS = """
CREATE TABLE IF NOT EXISTS prospect_lists (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""

_CREATE_LIST_LEADS = """
CREATE TABLE IF NOT EXISTS list_leads (
    list_id    TEXT NOT NULL,
    lead_id    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'a_contacter',
    notes      TEXT,
    added_at   TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at  TEXT,
    PRIMARY KEY (list_id, lead_id)
)
"""

_CLOSED_STATUSES = {'closing', 'facture_payee'}

# Ordre de priorité "statut le plus avancé gagne" — utilisé pour la migration
# (réconciliation d'un même lead ayant eu des statuts différents selon la
# liste, sous l'ancien modèle par-liste) et, avant migration, pour trier les
# lignes candidates dans le SQL de lecture (LATERAL JOIN). Une seule source
# de vérité pour cet ordre, dupliqué 3x auparavant.
_STATUS_PRIORITY: dict[str, int] = {
    'facture_payee': 6,
    'closing': 5,
    'devis_relance': 4,
    'devis_envoye': 4,
    'pas_interesse': 2,
    'injoignable': 2,
    'repondeur': 1,
    'rappel': 1,
}

_STATUS_PRIORITY_SQL_CASE = "CASE status " + " ".join(
    f"WHEN '{status}' THEN {prio}" for status, prio in _STATUS_PRIORITY.items()
) + " ELSE 0 END"

_CREATE_LEAD_EVENTS = """
CREATE TABLE IF NOT EXISTS lead_events (
    id          TEXT PRIMARY KEY,
    lead_id     TEXT NOT NULL,
    list_id     TEXT,
    actor       TEXT,
    event_type  TEXT NOT NULL,   -- 'appel' | 'devis'
    from_status TEXT,
    to_status   TEXT NOT NULL,
    created_at  TEXT NOT NULL
)
"""
_CREATE_IDX_LEAD_EVENTS_ACTOR = (
    "CREATE INDEX IF NOT EXISTS idx_lead_events_actor ON lead_events(actor, created_at)"
)
_CREATE_IDX_LEAD_EVENTS_TYPE = (
    "CREATE INDEX IF NOT EXISTS idx_lead_events_type ON lead_events(event_type, created_at)"
)


def _affected(status: str) -> int:
    """Extrait le nombre de lignes affectées d'un status asyncpg (ex. 'UPDATE 1')."""
    parts = status.split()
    return int(parts[-1]) if parts else 0


def _compute_streak(closing_days: set[str]) -> int:
    """Nombre de jours consécutifs (jusqu'à aujourd'hui ou hier) avec >=1 closing."""
    if not closing_days:
        return 0
    day = date.today()
    if day.isoformat() not in closing_days:
        day -= timedelta(days=1)
    streak = 0
    while day.isoformat() in closing_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


class LeadStore:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or settings.DATABASE_URL
        self.pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5)
        async with self.pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE)
            await conn.execute(_CREATE_IDX_CITY)
            await conn.execute(_CREATE_IDX_TEMP)
            await conn.execute(_CREATE_PROSPECT_LISTS)
            await conn.execute(_CREATE_LIST_LEADS)
            await conn.execute(_CREATE_SCAN_HISTORY)
            await conn.execute(_CREATE_IDX_SCAN_HISTORY)
            await conn.execute(_CREATE_LEAD_EVENTS)
            await conn.execute(_CREATE_IDX_LEAD_EVENTS_ACTOR)
            await conn.execute(_CREATE_IDX_LEAD_EVENTS_TYPE)
            for stmt in _ALTER_STATEMENTS:
                await conn.execute(stmt)
        await self.backfill_postcodes()
        log.info("PostgreSQL initialisé")

    async def backfill_postcodes(self) -> int:
        """Extrait le code postal (regex) depuis `address` pour les leads existants
        qui n'ont pas encore `postcode` renseigné (scans antérieurs à la Phase 2).

        Idempotent : ne retouche que les lignes `postcode IS NULL`, donc coût nul
        après le premier démarrage. Les nouveaux scans stockent directement le CP
        extrait du tag OSM `addr:postcode` (plus fiable) via `batch_upsert`.
        """
        rows = await self.pool.fetch(
            "SELECT id, address FROM leads WHERE postcode IS NULL AND address IS NOT NULL"
        )
        updates = []
        for r in rows:
            m = _POSTCODE_RE.search(r["address"] or "")
            if not m:
                continue
            postcode = m.group(1)
            dept = postcode_to_departement(postcode)
            updates.append((postcode, dept, r["id"]))
        if updates:
            await self.pool.executemany(
                "UPDATE leads SET postcode = $1, departement = $2 WHERE id = $3", updates
            )
            log.info("Backfill code postal : %d/%d leads mis à jour", len(updates), len(rows))
        return len(updates)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def batch_upsert(self, rows: list[dict[str, Any]]) -> int:
        """Upsert batch de leads. Retourne le nombre de lignes affectées."""
        if not rows:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        params = [
            (
                r["id"], r["name"], r.get("address"), r.get("phone"), r.get("website"),
                r["web_status"], r["business_type"], r["score"], r["temperature"],
                r["city"], r["lat"], r["lng"], r.get("source", "osm"), now, now,
                r.get("postcode"), r.get("departement"),
            )
            for r in rows
        ]
        await self.pool.executemany(
            """
            INSERT INTO leads
                (id, name, address, phone, website, web_status, business_type,
                 score, temperature, city, lat, lng, source, first_seen, last_seen,
                 postcode, departement)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            ON CONFLICT (id) DO UPDATE SET
                name          = EXCLUDED.name,
                phone         = COALESCE(EXCLUDED.phone, leads.phone),
                website       = COALESCE(EXCLUDED.website, leads.website),
                web_status    = EXCLUDED.web_status,
                score         = EXCLUDED.score,
                temperature   = EXCLUDED.temperature,
                last_seen     = EXCLUDED.last_seen,
                postcode      = COALESCE(EXCLUDED.postcode, leads.postcode),
                departement   = COALESCE(EXCLUDED.departement, leads.departement)
            """,
            params,
        )
        return len(rows)

    async def get_leads(
        self,
        city: Optional[str] = None,
        temperature: Optional[str] = None,
        business_type: Optional[str] = None,
        business_types: Optional[list[str]] = None,
        exclude_business_types: Optional[list[str]] = None,
        show_equipped: bool = False,
        show_closed: bool = False,
        departements: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        values: list[Any] = []
        if city:
            values.append(city)
            conditions.append(f"LOWER(l.city) = LOWER(${len(values)})")
        if temperature:
            values.append(temperature)
            conditions.append(f"l.temperature = ${len(values)}")
        # `business_types` (catégorie résolue en plusieurs types bruts) prime
        # sur `business_type` (valeur brute unique, conservé pour compat) si
        # les deux sont fournis.
        if business_types:
            values.append(business_types)
            conditions.append(f"l.business_type = ANY(${len(values)})")
        elif business_type:
            values.append(business_type)
            conditions.append(f"l.business_type = ${len(values)}")
        # Catégorie "Autres" (filtre) : tout business_type non couvert par une
        # catégorie connue plutôt qu'une recherche exacte sur "Autres" (qui ne
        # correspondrait à aucun lead réel).
        if exclude_business_types:
            values.append(exclude_business_types)
            conditions.append(f"NOT (l.business_type = ANY(${len(values)}))")
        if departements:
            values.append(departements)
            conditions.append(f"l.departement = ANY(${len(values)})")
        if not show_equipped:
            conditions.append("l.gmaps_website IS NULL")
        if not show_closed:
            conditions.append("l.gmaps_status IS DISTINCT FROM 'closed_permanently'")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        # `contact_status` : statut du lead lui-même (propriété partagée entre
        # toutes les listes qui le contiennent, cf. Phase 5) — sert à afficher
        # "déjà appelé" côté Recherche pour ne pas relancer un contact déjà
        # fait, même en dehors de la vue carte.
        sql = f"""
            SELECT l.*, NULLIF(l.status, 'a_contacter') AS contact_status
            FROM leads l
            {where}
            ORDER BY l.score DESC, l.name ASC
        """

        rows = await self.pool.fetch(sql, *values)
        return [dict(r) for r in rows]

    # ── Historique des scans (visibilité partagée entre utilisateurs) ──────────

    async def record_scan(
        self, area_type: str, area_code: str, area_name: str,
        scanned_by: Optional[str], total_found: int, api_calls: int,
    ) -> None:
        await self.pool.execute(
            """
            INSERT INTO scan_history (id, area_type, area_code, area_name, scanned_by, scanned_at, total_found, api_calls)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            str(uuid.uuid4()), area_type, area_code, area_name, scanned_by,
            datetime.now(timezone.utc).isoformat(), total_found, api_calls,
        )

    async def get_departement_coverage(self) -> dict[str, dict[str, Any]]:
        """Dernier scan connu par département — {code: {scanned_at, scanned_by,
        total_found}}. Sert à afficher "déjà scanné le [date] par [qui]" avant
        de relancer un scan déjà fait par l'autre utilisateur de la base
        partagée."""
        rows = await self.pool.fetch(
            """
            SELECT DISTINCT ON (area_code) area_code, scanned_at, scanned_by, total_found
            FROM scan_history
            WHERE area_type = 'departement'
            ORDER BY area_code, scanned_at DESC
            """
        )
        return {
            r["area_code"]: {
                "scanned_at": r["scanned_at"],
                "scanned_by": r["scanned_by"],
                "total_found": r["total_found"],
            }
            for r in rows
        }

    async def stats_by_ville(
        self,
        business_types: Optional[list[str]] = None,
        departement_codes: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Nombre de leads chauds (et total actif) par ville, agrégé côté serveur.

        S'appuie directement sur `city`/`lat`/`lng` de chaque lead scanné (peu
        importe si le scan a été lancé par ville ou par département) : toute
        ville scannée apparaît automatiquement. `departement_codes` permet de
        restreindre l'affichage carte à une sélection de départements, sans
        dépendre de l'historique des recherches par ville. Mêmes exclusions
        que le pipeline actif (déjà équipés / fermés définitivement, villes
        sans lead chaud)."""
        rows = await self.pool.fetch(
            f"""
            SELECT city AS name, departement,
                   AVG(lat) AS lat, AVG(lng) AS lng,
                   COUNT(*) FILTER (WHERE temperature = 'chaud') AS chauds,
                   COUNT(*) AS total
            FROM leads
            WHERE {_ACTIVE_PIPELINE_WHERE}
              AND ($1::text[] IS NULL OR business_type = ANY($1))
              AND ($2::text[] IS NULL OR departement = ANY($2))
            GROUP BY city, departement
            HAVING COUNT(*) FILTER (WHERE temperature = 'chaud') > 0
            """,
            business_types, departement_codes,
        )
        return [dict(r) for r in rows]

    async def get_leads_in_bounds(
        self,
        south: float, west: float, north: float, east: float,
        business_types: Optional[list[str]] = None,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        """Leads chauds précis dans un viewport carte (Phase 5, niveau 2 du drill-down).

        Toujours borné au rectangle visible + LIMIT : jamais tous les leads de
        France chargés en mémoire, uniquement ce qui est affiché à l'écran.

        `contact_status` : statut du lead lui-même (propriété partagée entre
        toutes les listes qui le contiennent, cf. Phase 5) — NULL n'existe
        plus (défaut 'a_contacter'), traité côté frontend comme "pas encore
        contacté". Sert au code couleur des marqueurs précis côté carte (le
        niveau macro/bulles reste sur la seule densité de leads chauds,
        inchangé)."""
        rows = await self.pool.fetch(
            f"""
            SELECT l.id, l.name, l.address, l.phone, l.website, l.web_status, l.business_type,
                   l.score, l.temperature, l.gmaps_status, l.gmaps_website, l.gmaps_url,
                   l.gmaps_rating, l.gmaps_user_ratings_total,
                   l.city, l.lat, l.lng, NULLIF(l.status, 'a_contacter') AS contact_status
            FROM leads l
            WHERE l.temperature = 'chaud' AND {_ACTIVE_PIPELINE_WHERE}
              AND l.lat BETWEEN $1 AND $2 AND l.lng BETWEEN $3 AND $4
              AND ($5::text[] IS NULL OR l.business_type = ANY($5))
            ORDER BY l.score DESC
            LIMIT $6
            """,
            south, north, west, east, business_types, limit,
        )
        return [dict(r) for r in rows]

    async def stats_by_departement(self, business_types: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Nombre de leads chauds (et total actif) par département, agrégé côté
        serveur pour rester correct au-delà du scan courant en mémoire. Exclut
        les leads hors pipeline actif (déjà équipés / fermés définitivement, cf.
        _ACTIVE_PIPELINE_WHERE) et les départements sans lead chaud."""
        rows = await self.pool.fetch(
            f"""
            SELECT departement,
                   COUNT(*) FILTER (WHERE temperature = 'chaud') AS chauds,
                   COUNT(*) AS total
            FROM leads
            WHERE departement IS NOT NULL AND {_ACTIVE_PIPELINE_WHERE}
              AND ($1::text[] IS NULL OR business_type = ANY($1))
            GROUP BY departement
            HAVING COUNT(*) FILTER (WHERE temperature = 'chaud') > 0
            """,
            business_types,
        )
        return [dict(r) for r in rows]

    # ── Vérification Google Places ─────────────────────────────────────────────

    async def get_leads_needing_gmaps_check(self, cities: list[str], limit: int = 50) -> list[dict[str, Any]]:
        """Leads sans site OSM, jamais vérifiés côté Google ou vérifiés il y a >30j,
        parmi les villes données (une seule pour un scan ville, potentiellement
        plusieurs pour un scan département — `limit` reste un plafond global,
        pas par ville)."""
        if not cities:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = await self.pool.fetch(
            """
            SELECT id, name, address, city, business_type, web_status FROM leads
            WHERE city = ANY($1)
              AND website IS NULL
              AND (gmaps_checked_at IS NULL OR gmaps_checked_at < $2)
            ORDER BY score DESC
            LIMIT $3
            """,
            cities, cutoff, limit,
        )
        return [dict(r) for r in rows]

    async def update_gmaps(
        self,
        lead_id: str,
        gmaps_status: str,
        gmaps_website: Optional[str],
        gmaps_url: Optional[str],
        web_status: Optional[str] = None,
        temperature: Optional[str] = None,
        score: Optional[float] = None,
        gmaps_rating: Optional[float] = None,
        gmaps_user_ratings_total: Optional[int] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sets = [
            "gmaps_status = $1", "gmaps_website = $2", "gmaps_url = $3", "gmaps_checked_at = $4",
        ]
        values: list[Any] = [gmaps_status, gmaps_website, gmaps_url, now]
        if web_status is not None:
            values.append(web_status)
            sets.append(f"web_status = ${len(values)}")
        if temperature is not None:
            values.append(temperature)
            sets.append(f"temperature = ${len(values)}")
        if score is not None:
            values.append(score)
            sets.append(f"score = ${len(values)}")
        if gmaps_rating is not None:
            values.append(gmaps_rating)
            sets.append(f"gmaps_rating = ${len(values)}")
        if gmaps_user_ratings_total is not None:
            values.append(gmaps_user_ratings_total)
            sets.append(f"gmaps_user_ratings_total = ${len(values)}")
        values.append(lead_id)
        await self.pool.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ${len(values)}", *values)

    async def get_lead(self, lead_id: str) -> Optional[dict[str, Any]]:
        row = await self.pool.fetchrow("SELECT * FROM leads WHERE id = $1", lead_id)
        return dict(row) if row else None

    async def update_lead(
        self,
        lead_id: str,
        called: Optional[bool] = None,
        outcome: Optional[str] = None,
        notes: Optional[str] = None,
        audit_json: Optional[str] = None,
        web_status: Optional[str] = None,
    ) -> bool:
        sets: list[str] = []
        values: list[Any] = []
        if called is not None:
            values.append(int(called))
            sets.append(f"called = ${len(values)}")
        if outcome is not None:
            values.append(outcome)
            sets.append(f"outcome = ${len(values)}")
        if notes is not None:
            values.append(notes)
            sets.append(f"notes = ${len(values)}")
        if audit_json is not None:
            values.append(audit_json)
            sets.append(f"audit_json = ${len(values)}")
        if web_status is not None:
            values.append(web_status)
            sets.append(f"web_status = ${len(values)}")
        if not sets:
            return False
        values.append(lead_id)
        status = await self.pool.execute(
            f"UPDATE leads SET {', '.join(sets)} WHERE id = ${len(values)}", *values
        )
        return _affected(status) > 0

    async def export_csv(self, city: Optional[str] = None) -> str:
        leads = await self.get_leads(city=city)
        columns = [
            "id", "name", "business_type", "web_status", "temperature", "score",
            "phone", "website", "address", "city", "called", "outcome", "notes",
            "lat", "lng", "first_seen", "last_seen",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(leads)
        return buf.getvalue()

    async def distinct_cities(self) -> list[str]:
        rows = await self.pool.fetch("SELECT DISTINCT city FROM leads ORDER BY city")
        return [r["city"] for r in rows]

    async def distinct_types(self, city: Optional[str] = None) -> list[str]:
        if city:
            sql = "SELECT DISTINCT business_type FROM leads WHERE LOWER(city)=LOWER($1) ORDER BY business_type"
            rows = await self.pool.fetch(sql, city)
        else:
            sql = "SELECT DISTINCT business_type FROM leads ORDER BY business_type"
            rows = await self.pool.fetch(sql)
        return [r["business_type"] for r in rows]

    # ── Listes de prospection ──────────────────────────────────────────────────

    async def create_list(self, name: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        list_id = str(uuid.uuid4())
        await self.pool.execute(
            "INSERT INTO prospect_lists (id, name, created_at, updated_at) VALUES ($1,$2,$3,$4)",
            list_id, name, now, now,
        )
        return {"id": list_id, "name": name, "created_at": now, "updated_at": now, "lead_count": 0}

    async def patch_list(
        self,
        list_id: str,
        name: Optional[str] = None,
        assigned_to: Optional[str] = None,
        priorite: Optional[str] = None,
    ) -> bool:
        """Renomme la liste et/ou l'attribue à un utilisateur et/ou lui donne
        un niveau de priorité — attribution/priorité au niveau de la LISTE
        (qui la suit, son urgence globale), distinct de `assigned_to` par
        lead déjà existant sur list_leads."""
        now = datetime.now(timezone.utc).isoformat()
        sets: list[str] = ["updated_at = $1"]
        values: list[Any] = [now]

        if name is not None:
            values.append(name)
            sets.append(f"name = ${len(values)}")
        if assigned_to is not None:
            values.append(assigned_to or None)
            sets.append(f"assigned_to = ${len(values)}")
        if priorite is not None:
            values.append(priorite or None)
            sets.append(f"priorite = ${len(values)}")

        values.append(list_id)
        query = f"UPDATE prospect_lists SET {', '.join(sets)} WHERE id = ${len(values)}"
        status = await self.pool.execute(query, *values)
        return _affected(status) > 0

    async def get_lists(self) -> list[dict[str, Any]]:
        rows = await self.pool.fetch("""
            SELECT pl.id, pl.name, pl.created_at, pl.updated_at,
                   pl.assigned_to, pl.priorite,
                   COUNT(ll.lead_id) as lead_count
            FROM prospect_lists pl
            LEFT JOIN list_leads ll ON ll.list_id = pl.id
            GROUP BY pl.id
            ORDER BY pl.created_at DESC
        """)
        return [dict(r) for r in rows]

    async def delete_list(self, list_id: str) -> bool:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM list_leads WHERE list_id = $1", list_id)
                status = await conn.execute("DELETE FROM prospect_lists WHERE id = $1", list_id)
        return _affected(status) > 0

    async def add_leads_to_list(self, list_id: str, lead_ids: list[str]) -> dict[str, Any]:
        """Ajoute des leads à une liste, en écartant les doublons "flous" —
        même (nom, adresse) normalisés déjà présents dans CETTE liste sous un
        `lead_id` technique différent (doublon OSM node/way, ou lead
        redécouvert par un scan département). L'unicité exacte par `lead_id`
        est déjà garantie par la clé primaire (list_id, lead_id).

        Retourne {"added": n, "skipped": [lead_id, ...]}."""
        if not lead_ids:
            return {"added": 0, "skipped": []}

        now = datetime.now(timezone.utc).isoformat()

        existing = await self.pool.fetch(
            """
            SELECT LOWER(TRIM(l.name)) AS norm_name, LOWER(TRIM(COALESCE(l.address, ''))) AS norm_address
            FROM list_leads ll JOIN leads l ON l.id = ll.lead_id
            WHERE ll.list_id = $1
            """,
            list_id,
        )
        seen_keys = {(r["norm_name"], r["norm_address"]) for r in existing}

        candidates = await self.pool.fetch(
            "SELECT id, LOWER(TRIM(name)) AS norm_name, LOWER(TRIM(COALESCE(address, ''))) AS norm_address "
            "FROM leads WHERE id = ANY($1)",
            lead_ids,
        )
        key_by_id = {r["id"]: (r["norm_name"], r["norm_address"]) for r in candidates}

        to_insert: list[str] = []
        skipped: list[str] = []
        for lid in lead_ids:
            key = key_by_id.get(lid)
            if key is None or key in seen_keys:
                skipped.append(lid)
                continue
            seen_keys.add(key)
            to_insert.append(lid)

        if to_insert:
            await self.pool.executemany(
                """
                INSERT INTO list_leads (list_id, lead_id, status, added_at, updated_at)
                VALUES ($1,$2,'a_contacter',$3,$4)
                ON CONFLICT (list_id, lead_id) DO NOTHING
                """,
                [(list_id, lid, now, now) for lid in to_insert],
            )
            await self.pool.execute("UPDATE prospect_lists SET updated_at = $1 WHERE id = $2", now, list_id)

        return {"added": len(to_insert), "skipped": skipped}

    async def remove_lead_from_list(self, list_id: str, lead_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        status = await self.pool.execute(
            "DELETE FROM list_leads WHERE list_id = $1 AND lead_id = $2", list_id, lead_id
        )
        removed = _affected(status) > 0
        if removed:
            await self.pool.execute("UPDATE prospect_lists SET updated_at = $1 WHERE id = $2", now, list_id)
        return removed

    async def patch_list_lead(
        self,
        list_id: str,
        lead_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        budget_propose: Optional[float] = None,
        budget_final: Optional[float] = None,
        assigned_to: Optional[str] = None,
        by: Optional[str] = None,
        devis_envoye: Optional[bool] = None,
    ) -> bool:
        """`status`/`budget_propose`/`budget_final`/`closed_at`/
        `devis_envoye_le` sont des propriétés du LEAD (partagées entre
        toutes les listes qui le contiennent, cf. Phase 5) -> écrites sur
        `leads`. `notes`/`assigned_to` restent propres à CETTE liste ->
        écrites sur `list_leads`. `by` (identité de l'auteur) sert
        uniquement à tracer l'événement dans `lead_events` (onglet
        Performance) quand le statut change réellement.

        `devis_envoye` (Phase 6) est une coche indépendante du statut
        pipeline (`status` reste utilisé comme "en cours de préparation"
        dans l'usage actuel, pas touché) : True -> horodate maintenant
        (chaque coche/re-coche vaut "envoyé maintenant", y compris une
        relance) ; False -> efface la date (retire de la todo-list de
        relance)."""
        now = datetime.now(timezone.utc).isoformat()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    "SELECT 1 FROM list_leads WHERE list_id = $1 AND lead_id = $2", list_id, lead_id
                )
                if not exists:
                    return False

                list_sets: list[str] = ["updated_at = $1"]
                list_values: list[Any] = [now]
                if notes is not None:
                    list_values.append(notes)
                    list_sets.append(f"notes = ${len(list_values)}")
                if assigned_to is not None:
                    # Chaîne vide = "non assigné" explicite (distinct de "ne pas modifier").
                    list_values.append(assigned_to or None)
                    list_sets.append(f"assigned_to = ${len(list_values)}")
                if len(list_sets) > 1:
                    list_values.extend([list_id, lead_id])
                    await conn.execute(
                        f"UPDATE list_leads SET {', '.join(list_sets)} "
                        f"WHERE list_id = ${len(list_values) - 1} AND lead_id = ${len(list_values)}",
                        *list_values,
                    )

                if status is not None or budget_propose is not None or budget_final is not None or devis_envoye is not None:
                    old_status = (
                        await conn.fetchval("SELECT status FROM leads WHERE id = $1", lead_id)
                        if status is not None else None
                    )

                    lead_sets: list[str] = []
                    lead_values: list[Any] = []
                    if status is not None:
                        lead_values.append(status)
                        lead_sets.append(f"status = ${len(lead_values)}")
                        lead_values.append(now)
                        lead_sets.append(f"status_updated_at = ${len(lead_values)}")
                        if status in _CLOSED_STATUSES:
                            lead_values.append(now)
                            lead_sets.append(f"closed_at = COALESCE(closed_at, ${len(lead_values)})")
                        else:
                            lead_sets.append("closed_at = NULL")
                    if budget_propose is not None:
                        lead_values.append(budget_propose)
                        lead_sets.append(f"budget_propose = ${len(lead_values)}")
                    if budget_final is not None:
                        lead_values.append(budget_final)
                        lead_sets.append(f"budget_final = ${len(lead_values)}")
                    if devis_envoye is not None:
                        if devis_envoye:
                            lead_values.append(now)
                            lead_sets.append(f"devis_envoye_le = ${len(lead_values)}")
                        else:
                            lead_sets.append("devis_envoye_le = NULL")

                    lead_values.append(lead_id)
                    await conn.execute(
                        f"UPDATE leads SET {', '.join(lead_sets)} WHERE id = ${len(lead_values)}", *lead_values
                    )

                    # "Un appel" = un changement de statut effectif (pas de log
                    # d'appel dédié) ; "un devis" = entrée dans devis_envoye.
                    if status is not None and status != old_status:
                        await conn.execute(
                            """
                            INSERT INTO lead_events (id, lead_id, list_id, actor, event_type, from_status, to_status, created_at)
                            VALUES ($1,$2,$3,$4,'appel',$5,$6,$7)
                            """,
                            str(uuid.uuid4()), lead_id, list_id, by, old_status, status, now,
                        )
                        if status == 'devis_envoye':
                            await conn.execute(
                                """
                                INSERT INTO lead_events (id, lead_id, list_id, actor, event_type, from_status, to_status, created_at)
                                VALUES ($1,$2,$3,$4,'devis',$5,$6,$7)
                                """,
                                str(uuid.uuid4()), lead_id, list_id, by, old_status, status, now,
                            )

                await conn.execute("UPDATE prospect_lists SET updated_at = $1 WHERE id = $2", now, list_id)

        return True

    async def get_list_leads(self, list_id: str) -> list[dict[str, Any]]:
        # `status`/`budget_propose`/`budget_final`/`closed_at` viennent tous
        # de `l.*` désormais (propriétés du lead, partagées entre listes,
        # cf. Phase 5) — `list_status` reste le nom de clé attendu côté
        # frontend, juste réalimenté depuis `l.status` au lieu de `ll.status`.
        rows = await self.pool.fetch("""
            SELECT l.*, l.status AS list_status, ll.notes AS list_notes,
                   ll.added_at, ll.updated_at AS ll_updated_at, ll.assigned_to
            FROM list_leads ll
            JOIN leads l ON l.id = ll.lead_id
            WHERE ll.list_id = $1
            ORDER BY ll.added_at ASC
        """, list_id)
        return [dict(r) for r in rows]

    async def get_rappels(self) -> list[dict[str, Any]]:
        """Tous les leads tagués 'rappel' (statut partagé, cf. Phase 5),
        toutes listes confondues — sert de todo-list des rappels à faire,
        indépendamment de la liste/ville/département. Un même lead présent
        dans plusieurs listes apparaît une fois par liste (contexte de suivi
        propre à chaque liste : notes, assignation)."""
        rows = await self.pool.fetch("""
            SELECT l.id, l.name, l.phone, l.address, l.city, l.business_type,
                   ll.list_id, pl.name AS list_name, ll.notes AS list_notes,
                   ll.assigned_to, l.status_updated_at AS updated_at
            FROM list_leads ll
            JOIN leads l ON l.id = ll.lead_id
            JOIN prospect_lists pl ON pl.id = ll.list_id
            WHERE l.status = 'rappel'
            ORDER BY l.status_updated_at ASC
        """)
        return [dict(r) for r in rows]

    async def get_devis_a_relancer(self) -> list[dict[str, Any]]:
        """Tous les leads dont le devis a été coché "envoyé" (date renseignée,
        cf. Phase 6 — indépendant du statut pipeline), toutes listes
        confondues, triés par date d'envoi la plus ancienne en premier (la
        relance la plus urgente). Même logique de duplication par liste que
        get_rappels (contexte de suivi propre à chaque liste)."""
        rows = await self.pool.fetch("""
            SELECT l.id, l.name, l.phone, l.address, l.city, l.business_type,
                   l.status, l.budget_propose, l.devis_envoye_le,
                   ll.list_id, pl.name AS list_name, ll.notes AS list_notes, ll.assigned_to
            FROM list_leads ll
            JOIN leads l ON l.id = ll.lead_id
            JOIN prospect_lists pl ON pl.id = ll.list_id
            WHERE l.devis_envoye_le IS NOT NULL
            ORDER BY l.devis_envoye_le ASC
        """)
        return [dict(r) for r in rows]

    async def get_list_stats(self, list_id: str) -> dict[str, Any]:
        leads = await self.get_list_leads(list_id)
        if not leads:
            return {"total": 0, "by_status": {}, "taux_contact": 0.0,
                    "taux_devis": 0.0, "taux_closing": 0.0, "closings_par_jour": []}

        by_status = Counter(l["list_status"] for l in leads)
        total = len(leads)

        _DEVIS_PLUS = {'devis_envoye', 'devis_relance', 'closing', 'facture_payee'}
        _NOT_CONTACTED = {'a_contacter', 'repondeur', 'injoignable'}

        contacted = total - sum(by_status.get(s, 0) for s in _NOT_CONTACTED)
        devis = sum(by_status.get(s, 0) for s in _DEVIS_PLUS)
        closed = sum(by_status.get(s, 0) for s in _CLOSED_STATUSES)

        taux_contact = round(contacted / total * 100, 1) if total else 0.0
        taux_devis = round(devis / contacted * 100, 1) if contacted else 0.0
        taux_closing = round(closed / total * 100, 1) if total else 0.0

        day_counts: dict[str, int] = defaultdict(int)
        for lead in leads:
            if lead["list_status"] in _CLOSED_STATUSES and lead.get("closed_at"):
                day_counts[lead["closed_at"][:10]] += 1

        return {
            "total": total,
            "by_status": dict(by_status),
            "taux_contact": taux_contact,
            "taux_devis": taux_devis,
            "taux_closing": taux_closing,
            "closings_par_jour": [{"date": d, "count": c} for d, c in sorted(day_counts.items())],
        }

    # ── Dashboard commercial (tous les prospect_lists confondus) ────────────────

    async def get_pipeline_funnel(self) -> dict[str, Any]:
        """Vue d'ensemble du pipeline, un lead compté une seule fois (statut
        étant désormais une propriété du lead lui-même, cf. Phase 5) :
        combien de leads ont été appelés (tout statut sauf 'a_contacter'),
        quelle part a reçu un devis, et le CA potentiel si 100% des devis
        déjà envoyés étaient signés (montant final si déjà closé, sinon
        montant proposé) — mise en avant demandée en tête du dashboard.

        Lit directement `leads` (plus besoin de `list_leads`) : seuls les
        leads ajoutés à au moins une liste peuvent avoir un statut différent
        du défaut 'a_contacter', donc on peut se limiter à ceux-là (filtre
        `status != 'a_contacter'`) sans changer le résultat — évite de
        parcourir la totalité des leads scannés (potentiellement bien plus
        nombreux que ceux réellement travaillés)."""
        rows = await self.pool.fetch(
            "SELECT status, budget_propose, budget_final FROM leads WHERE status != 'a_contacter'"
        )

        _DEVIS_OU_PLUS = {'devis_envoye', 'devis_relance', 'closing', 'facture_payee'}
        total_appeles = sum(1 for r in rows if r["status"] != 'a_contacter')
        devis_envoyes = sum(1 for r in rows if r["status"] in _DEVIS_OU_PLUS)
        ca_potentiel = sum(
            (r["budget_final"] if r["status"] in _CLOSED_STATUSES else r["budget_propose"]) or 0.0
            for r in rows if r["status"] in _DEVIS_OU_PLUS
        )
        taux_devis = round(devis_envoyes / total_appeles * 100, 1) if total_appeles else 0.0

        return {
            "total_appeles": total_appeles,
            "devis_envoyes": devis_envoyes,
            "taux_devis": taux_devis,
            "ca_potentiel": round(ca_potentiel, 2),
        }

    async def get_dashboard_stats(self, month: Optional[str] = None) -> dict[str, Any]:
        """Agrégation gamifiée tous-listes : closes/CA du mois par catégorie,
        classement, streak de jours consécutifs avec au moins un closing.
        """
        target_month = month or date.today().isoformat()[:7]

        rows = await self.pool.fetch("""
            SELECT status, budget_final, closed_at, business_type
            FROM leads
            WHERE status = ANY($1) AND closed_at IS NOT NULL
        """, list(_CLOSED_STATUSES))

        categories = load_categories()
        type_to_cat = types_to_category(categories)

        by_category: dict[str, dict[str, Any]] = {
            name: {"closes": 0, "ca_reel": 0.0} for name in categories
        }
        closing_days: set[str] = set()
        closes_mois = 0
        ca_reel_mois = 0.0

        for r in rows:
            day = r["closed_at"][:10]
            closing_days.add(day)
            if day[:7] != target_month:
                continue
            cat = type_to_cat.get(r["business_type"], "Autre")
            by_category.setdefault(cat, {"closes": 0, "ca_reel": 0.0})
            by_category[cat]["closes"] += 1
            montant = r["budget_final"] or 0.0
            by_category[cat]["ca_reel"] += montant
            closes_mois += 1
            ca_reel_mois += montant

        categories_out = []
        for name, entry in categories.items():
            agg = by_category.get(name, {"closes": 0, "ca_reel": 0.0})
            objectif_closes = entry.get("objectif_closes_mensuel")
            budget_ref = entry.get("budget_max") or entry.get("budget_min")
            objectif_ca = (objectif_closes * budget_ref) if (objectif_closes and budget_ref) else None
            categories_out.append({
                "name": name,
                "closes": agg["closes"],
                "ca_reel": round(agg["ca_reel"], 2),
                "budget_min": entry.get("budget_min"),
                "budget_max": entry.get("budget_max"),
                "objectif_closes_mensuel": objectif_closes,
                "objectif_ca": objectif_ca,
            })
        # Business_type non rattaché à une catégorie configurée -> bucket "Autre"
        # (n'apparaît que s'il contient effectivement des closings, pour ne pas
        # polluer le dashboard avec une carte vide).
        if by_category.get("Autre", {}).get("closes", 0) > 0:
            categories_out.append({
                "name": "Autre",
                "closes": by_category["Autre"]["closes"],
                "ca_reel": round(by_category["Autre"]["ca_reel"], 2),
                "budget_min": None, "budget_max": None,
                "objectif_closes_mensuel": None, "objectif_ca": None,
            })
        categories_out.sort(key=lambda c: c["ca_reel"], reverse=True)
        categorie_top = categories_out[0]["name"] if categories_out and categories_out[0]["ca_reel"] > 0 else None
        funnel = await self.get_pipeline_funnel()

        return {
            "month": target_month,
            "closes_ce_mois": closes_mois,
            "ca_reel_mois": round(ca_reel_mois, 2),
            "streak_jours": _compute_streak(closing_days),
            "categorie_top": categorie_top,
            "categories": categories_out,
            **funnel,
        }

    # ── Onglet Performance (VS Clément/Daniel) ───────────────────────────────

    async def get_performance(self, period: str = "day") -> dict[str, Any]:
        """Agrège `lead_events` par auteur : appels passés et devis envoyés
        (compteur du jour + cumulé sur `period`), et le CA potentiel de ces
        devis (budget_max ou budget_min de la catégorie du business_type du
        lead, cf. categories.py — jamais un montant fixe unique). Aucune
        liste d'utilisateurs codée en dur : seuls les acteurs ayant au moins
        un événement apparaissent, le frontend complète à 0 pour Clément/
        Daniel si absents.

        Inclut aussi une tendance quotidienne (7 derniers jours, tous types
        d'événements confondus) par acteur pour le petit graphique optionnel.
        """
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        if period == "week":
            period_start = (today_start - timedelta(days=today_start.weekday()))
        elif period == "month":
            period_start = today_start.replace(day=1)
        else:
            period_start = today_start

        trend_start = today_start - timedelta(days=6)
        query_start = min(period_start, trend_start).isoformat()
        today_start_iso = today_start.isoformat()
        period_start_iso = period_start.isoformat()

        rows = await self.pool.fetch(
            """
            SELECT e.actor, e.event_type, e.created_at, l.business_type
            FROM lead_events e
            JOIN leads l ON l.id = e.lead_id
            WHERE e.created_at >= $1
            """,
            query_start,
        )

        categories = load_categories()
        type_to_cat = types_to_category(categories)

        def _budget_ref(business_type: Optional[str]) -> float:
            cat = type_to_cat.get(business_type, "Autre")
            entry = categories.get(cat, {})
            return (entry.get("budget_max") or entry.get("budget_min") or 0.0)

        users: dict[str, dict[str, Any]] = {}
        trend: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for r in rows:
            actor = r["actor"] or "Non attribué"
            u = users.setdefault(actor, {
                "appels_jour": 0, "appels_periode": 0,
                "devis_jour": 0, "devis_periode": 0,
                "ca_potentiel": 0.0,
            })
            is_today = r["created_at"] >= today_start_iso
            is_period = r["created_at"] >= period_start_iso

            if r["created_at"] >= trend_start.isoformat():
                trend[actor][r["created_at"][:10]] += 1

            if r["event_type"] == "appel":
                if is_period:
                    u["appels_periode"] += 1
                if is_today:
                    u["appels_jour"] += 1
            elif r["event_type"] == "devis":
                if is_period:
                    u["devis_periode"] += 1
                    u["ca_potentiel"] = round(u["ca_potentiel"] + _budget_ref(r["business_type"]), 2)
                if is_today:
                    u["devis_jour"] += 1

        for actor, u in users.items():
            u["trend"] = [
                {"date": d, "count": trend[actor].get(d, 0)}
                for d in (
                    (trend_start + timedelta(days=i)).date().isoformat() for i in range(7)
                )
            ]

        return {"period": period, "users": users}
