"""Persistance SQLite — upsert idempotent.

Clé primaire stable : identifiant de source (ex. "node:123456" pour OSM).
Re-scanner une ville = mise à jour propre, aucun doublon.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

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


class LeadStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or settings.SQLITE_PATH

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.execute(_CREATE_IDX_CITY)
            await db.execute(_CREATE_IDX_TEMP)
            await db.commit()
        log.info("SQLite initialisé : %s", self.db_path)

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
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT INTO leads
                    (id, name, address, phone, website, web_status, business_type,
                     score, temperature, city, lat, lng, source, first_seen, last_seen)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name          = excluded.name,
                    phone         = COALESCE(excluded.phone, leads.phone),
                    website       = COALESCE(excluded.website, leads.website),
                    web_status    = excluded.web_status,
                    score         = excluded.score,
                    temperature   = excluded.temperature,
                    last_seen     = excluded.last_seen
                """,
                params,
            )
            await db.commit()
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
            conditions.append("LOWER(city) = LOWER(?)")
            values.append(city)
        if temperature:
            conditions.append("temperature = ?")
            values.append(temperature)
        if business_type:
            conditions.append("business_type = ?")
            values.append(business_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM leads {where} ORDER BY score DESC, name ASC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, values) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_lead(self, lead_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)) as cur:
                row = await cur.fetchone()
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
            sets.append("called = ?")
            values.append(int(called))
        if outcome is not None:
            sets.append("outcome = ?")
            values.append(outcome)
        if notes is not None:
            sets.append("notes = ?")
            values.append(notes)
        if audit_json is not None:
            sets.append("audit_json = ?")
            values.append(audit_json)
        if web_status is not None:
            sets.append("web_status = ?")
            values.append(web_status)
        if not sets:
            return False
        values.append(lead_id)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", values
            )
            await db.commit()
            return cur.rowcount > 0

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
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT DISTINCT city FROM leads ORDER BY city") as cur:
                return [r[0] for r in await cur.fetchall()]

    async def distinct_types(self, city: Optional[str] = None) -> list[str]:
        if city:
            sql = "SELECT DISTINCT business_type FROM leads WHERE LOWER(city)=LOWER(?) ORDER BY business_type"
            args = (city,)
        else:
            sql = "SELECT DISTINCT business_type FROM leads ORDER BY business_type"
            args = ()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, args) as cur:
                return [r[0] for r in await cur.fetchall()]
