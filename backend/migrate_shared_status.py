"""Migration ponctuelle : rend le statut d'un lead (et ce qui en découle —
budget_propose, budget_final, closed_at) partagé entre toutes les listes,
au lieu d'être dupliqué par ligne `list_leads` (cf. prompt "statut de lead
partagé entre listes"). Avant cette migration, un même établissement présent
dans 2 listes pouvait afficher 2 statuts différents selon la liste consultée.

Règle de réconciliation quand un même lead a des statuts différents selon la
liste : le statut le plus avancé dans le pipeline gagne (même ordre que
celui déjà utilisé côté lecture dans store.py, cf. `_STATUS_PRIORITY`) —
facture_payee > closing > devis_relance/devis_envoye > pas_interesse/
injoignable > repondeur/rappel > a_contacter. À priorité égale, la ligne la
plus récemment mise à jour gagne.

IMPORTANT — à faire AVANT `--apply` sur la base de production :
  1. Sauvegarder la base : `pg_dump $DATABASE_URL > backup_pre_migration.sql`
     (ou créer un branch Neon depuis le dashboard neon.tech).
  2. Lancer `--dry-run` (défaut) et relire l'échantillon de conflits affiché.
  3. Idéalement, rejouer `--dry-run`/`--apply` une première fois sur une
     copie/branche de la base avant de toucher la production.

Usage (depuis leadfinder/) :
    python -m backend.migrate_shared_status              # dry-run (défaut)
    python -m backend.migrate_shared_status --dry-run
    python -m backend.migrate_shared_status --apply       # écrit pour de vrai
"""

from __future__ import annotations

import argparse
import asyncio

import asyncpg

from .config import settings
from .store import _STATUS_PRIORITY_SQL_CASE

_WINNERS_CTE = f"""
    SELECT DISTINCT ON (lead_id) lead_id, status, budget_propose, budget_final,
           closed_at, updated_at
    FROM list_leads
    ORDER BY lead_id, {_STATUS_PRIORITY_SQL_CASE} DESC, updated_at DESC
"""


async def _report(conn: asyncpg.Connection) -> None:
    total = await conn.fetchval("SELECT COUNT(DISTINCT lead_id) FROM list_leads")
    conflicts = await conn.fetch(
        "SELECT lead_id FROM list_leads GROUP BY lead_id HAVING COUNT(DISTINCT status) > 1"
    )
    print(f"Leads présents dans au moins une liste : {total}")
    print(f"Leads avec un statut différent selon la liste (conflits réels) : {len(conflicts)}")

    if not conflicts:
        return

    sample_ids = [r["lead_id"] for r in conflicts[:15]]
    detail = await conn.fetch(
        """
        SELECT ll.lead_id, l.name, pl.name AS list_name, ll.status, ll.updated_at
        FROM list_leads ll
        JOIN leads l ON l.id = ll.lead_id
        JOIN prospect_lists pl ON pl.id = ll.list_id
        WHERE ll.lead_id = ANY($1)
        ORDER BY ll.lead_id, ll.updated_at DESC
        """,
        sample_ids,
    )
    winner_rows = await conn.fetch(
        f"SELECT lead_id, status FROM ({_WINNERS_CTE}) w WHERE w.lead_id = ANY($1)", sample_ids
    )
    winners = {r["lead_id"]: r["status"] for r in winner_rows}

    print(f"\nÉchantillon ({len(sample_ids)} premiers conflits, sur {len(conflicts)}) :")
    by_lead: dict[str, list[asyncpg.Record]] = {}
    for r in detail:
        by_lead.setdefault(r["lead_id"], []).append(r)
    for lead_id, rows in by_lead.items():
        name = rows[0]["name"]
        winner = winners.get(lead_id, "?")
        print(f"  - {name} ({lead_id})")
        for r in rows:
            marker = " <- retenu" if r["status"] == winner else ""
            print(f"      liste {r['list_name']!r} : {r['status']}{marker}")


async def _apply(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        result = await conn.execute(
            f"""
            UPDATE leads AS l SET
                status = w.status,
                budget_propose = w.budget_propose,
                budget_final = w.budget_final,
                closed_at = w.closed_at,
                status_updated_at = w.updated_at
            FROM ({_WINNERS_CTE}) AS w
            WHERE l.id = w.lead_id
            """
        )
    print(f"Migration appliquée : {result}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Écrit réellement (sinon dry-run par défaut).")
    args = parser.parse_args()

    if not settings.DATABASE_URL:
        raise SystemExit("DATABASE_URL manquant (.env) — connexion base requise.")

    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    try:
        await _report(conn)
        if args.apply:
            print("\n--apply demandé : écriture dans leads.status/budget_propose/budget_final/closed_at…")
            await _apply(conn)
        else:
            print("\nDry-run (aucune écriture). Relancer avec --apply pour appliquer, après relecture du rapport ci-dessus.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
