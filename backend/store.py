"""Persistance PostgreSQL (Neon) — upsert idempotent.

Clé primaire stable : identifiant de source (ex. "node:123456" pour OSM).
Re-scanner une ville = mise à jour propre, aucun doublon.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from .config import settings

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


def _affected(status: str) -> int:
    """Extrait le nombre de lignes affectées d'un status asyncpg (ex. 'UPDATE 1')."""
    parts = status.split()
    return int(parts[-1]) if parts else 0


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
        log.info("PostgreSQL initialisé")

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
            )
            for r in rows
        ]
        await self.pool.executemany(
            """
            INSERT INTO leads
                (id, name, address, phone, website, web_status, business_type,
                 score, temperature, city, lat, lng, source, first_seen, last_seen)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (id) DO UPDATE SET
                name          = EXCLUDED.name,
                phone         = COALESCE(EXCLUDED.phone, leads.phone),
                website       = COALESCE(EXCLUDED.website, leads.website),
                web_status    = EXCLUDED.web_status,
                score         = EXCLUDED.score,
                temperature   = EXCLUDED.temperature,
                last_seen     = EXCLUDED.last_seen
            """,
            params,
        )
        return len(rows)

    async def get_leads(
        self,
        city: Optional[str] = None,
        temperature: Optional[str] = None,
        business_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        values: list[Any] = []
        if city:
            values.append(city)
            conditions.append(f"LOWER(city) = LOWER(${len(values)})")
        if temperature:
            values.append(temperature)
            conditions.append(f"temperature = ${len(values)}")
        if business_type:
            values.append(business_type)
            conditions.append(f"business_type = ${len(values)}")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM leads {where} ORDER BY score DESC, name ASC"

        rows = await self.pool.fetch(sql, *values)
        return [dict(r) for r in rows]

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

    async def get_lists(self) -> list[dict[str, Any]]:
        rows = await self.pool.fetch("""
            SELECT pl.id, pl.name, pl.created_at, pl.updated_at,
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

    async def add_leads_to_list(self, list_id: str, lead_ids: list[str]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        await self.pool.executemany(
            """
            INSERT INTO list_leads (list_id, lead_id, status, added_at, updated_at)
            VALUES ($1,$2,'a_contacter',$3,$4)
            ON CONFLICT (list_id, lead_id) DO NOTHING
            """,
            [(list_id, lid, now, now) for lid in lead_ids],
        )
        await self.pool.execute("UPDATE prospect_lists SET updated_at = $1 WHERE id = $2", now, list_id)
        return len(lead_ids)

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
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        sets: list[str] = ["updated_at = $1"]
        values: list[Any] = [now]

        if status is not None:
            values.append(status)
            sets.append(f"status = ${len(values)}")
            if status in _CLOSED_STATUSES:
                values.append(now)
                sets.append(f"closed_at = COALESCE(closed_at, ${len(values)})")
            else:
                sets.append("closed_at = NULL")
        if notes is not None:
            values.append(notes)
            sets.append(f"notes = ${len(values)}")

        values.extend([list_id, lead_id])
        sql = (
            f"UPDATE list_leads SET {', '.join(sets)} "
            f"WHERE list_id = ${len(values) - 1} AND lead_id = ${len(values)}"
        )
        db_status = await self.pool.execute(sql, *values)
        updated = _affected(db_status) > 0
        if updated:
            await self.pool.execute("UPDATE prospect_lists SET updated_at = $1 WHERE id = $2", now, list_id)
        return updated

    async def get_list_leads(self, list_id: str) -> list[dict[str, Any]]:
        rows = await self.pool.fetch("""
            SELECT l.*, ll.status AS list_status, ll.notes AS list_notes,
                   ll.added_at, ll.updated_at AS ll_updated_at, ll.closed_at
            FROM list_leads ll
            JOIN leads l ON l.id = ll.lead_id
            WHERE ll.list_id = $1
            ORDER BY ll.added_at ASC
        """, list_id)
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
