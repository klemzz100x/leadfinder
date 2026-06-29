"""Orchestration du pipeline de scan d'une ville.

Étapes :
  1. Découverte via OSMSource (Nominatim + Overpass).
  2. Classification du statut web (classify.py).
  3. Scoring + température (score.py).
  4. Upsert batch en SQLite (store.py).
  5. Renvoi du résumé avec compteur d'appels API.
"""

from __future__ import annotations

import logging
import time
from collections import Counter

from pydantic import BaseModel

from .classify import classify
from .score import compute_score
from .sources.osm import OSMSource
from .store import LeadStore

log = logging.getLogger("leadfinder.pipeline")

_WEBSITE_KEYS = ("website", "contact:website", "url")


class ScanSummary(BaseModel):
    city: str
    total: int
    by_temperature: dict[str, int]
    by_status: dict[str, int]
    api_calls: int
    duration_seconds: float


async def scan_city(city: str, store: LeadStore) -> ScanSummary:
    t0 = time.monotonic()
    source = OSMSource()

    try:
        businesses = await source.discover(city)
    finally:
        await source.aclose()

    log.info("Scan %r : %d business découverts en %.1fs", city, len(businesses), time.monotonic() - t0)

    rows: list[dict] = []
    temp_counts: Counter = Counter()
    status_counts: Counter = Counter()

    for biz in businesses:
        # Détermine si OSM avait un tag website (même vide) ou pas du tout.
        has_website_info = any(k in biz.raw_tags for k in _WEBSITE_KEYS)

        clf = classify(biz.website, has_website_tag=has_website_info)
        sr = compute_score(clf.status, biz.business_type, biz.website)

        rows.append(
            {
                "id": biz.id,
                "name": biz.name,
                "address": biz.address,
                "phone": biz.phone,
                "website": biz.website,
                "web_status": clf.status.value,
                "business_type": biz.business_type,
                "score": sr.score,
                "temperature": sr.temperature.value,
                "city": city,
                "lat": biz.lat,
                "lng": biz.lng,
                "source": biz.source,
            }
        )
        temp_counts[sr.temperature.value] += 1
        status_counts[clf.status.value] += 1

    await store.batch_upsert(rows)

    return ScanSummary(
        city=city,
        total=len(businesses),
        by_temperature=dict(temp_counts),
        by_status=dict(status_counts),
        api_calls=source.call_count,
        duration_seconds=round(time.monotonic() - t0, 2),
    )
