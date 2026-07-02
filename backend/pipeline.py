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
from typing import Optional

import httpx
from pydantic import BaseModel

from .classify import WebStatus, classify
from .config import settings
from .departements import postcode_to_departement
from .google_places_service import verify_batch
from .score import compute_score
from .sources.osm import OSMSource
from .store import LeadStore

log = logging.getLogger("leadfinder.pipeline")

_WEBSITE_KEYS = ("website", "contact:website", "url")

# Plafond de vérifications Google Places par scan — borne le coût (~2 appels
# API par lead : Text Search + Place Details).
_GMAPS_BATCH_LIMIT = 50


class ScanSummary(BaseModel):
    city: str
    total: int
    by_temperature: dict[str, int]
    by_status: dict[str, int]
    api_calls: int
    gmaps_checked: int = 0
    duration_seconds: float


async def scan_city(city: str, store: LeadStore, http_client: Optional[httpx.AsyncClient] = None) -> ScanSummary:
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
                "postcode": biz.postcode,
                "departement": postcode_to_departement(biz.postcode),
                "city": city,
                "lat": biz.lat,
                "lng": biz.lng,
                "source": biz.source,
            }
        )
        temp_counts[sr.temperature.value] += 1
        status_counts[clf.status.value] += 1

    await store.batch_upsert(rows)

    gmaps_checked = 0
    if settings.has_google and http_client is not None:
        gmaps_checked = await _verify_gmaps_signals(city, store, http_client)

    return ScanSummary(
        city=city,
        total=len(businesses),
        by_temperature=dict(temp_counts),
        by_status=dict(status_counts),
        api_calls=source.call_count,
        gmaps_checked=gmaps_checked,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


async def _verify_gmaps_signals(city: str, store: LeadStore, client: httpx.AsyncClient) -> int:
    """Second passage Google Places : uniquement sur les leads sans site OSM.

    Résout les statuts UNVERIFIED en NO_SITE quand Google confirme l'absence
    de site (recalcul via compute_score existant — pas de score parallèle).
    Les leads "déjà équipés" (gmaps_website rempli) et fermés définitivement
    ne changent pas de température : ils sont exclus du pipeline actif via
    LeadStore._ACTIVE_PIPELINE_WHERE, pas via une rétrogradation de score.
    """
    candidates = await store.get_leads_needing_gmaps_check(city, limit=_GMAPS_BATCH_LIMIT)
    if not candidates:
        return 0

    results = await verify_batch(candidates, client)
    by_id = {c["id"]: c for c in candidates}

    for lead_id, r in results.items():
        candidate = by_id[lead_id]
        web_status = None
        temperature = None
        score = None

        if (
            not r.get("gmaps_website")
            and r["gmaps_status"] != "unchecked"
            and candidate["web_status"] == WebStatus.UNVERIFIED.value
        ):
            clf = classify(None, has_website_tag=True)  # -> NO_SITE, plancher CHAUD garanti
            sr = compute_score(clf.status, candidate["business_type"], None)
            web_status, temperature, score = clf.status.value, sr.temperature.value, sr.score

        await store.update_gmaps(
            lead_id,
            gmaps_status=r["gmaps_status"],
            gmaps_website=r.get("gmaps_website"),
            gmaps_url=r.get("gmaps_url"),
            web_status=web_status,
            temperature=temperature,
            score=score,
        )

    return len(results)
