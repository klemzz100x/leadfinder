"""Orchestration du pipeline de scan — par ville ou par département entier.

Étapes (factorisées dans `_discover_classify_store`, partagées par les deux
modes de scan) :
  1. Découverte via OSMSource (Nominatim + Overpass).
  2. Classification du statut web (classify.py).
  3. Scoring + température (score.py).
  4. Upsert batch en base (store.py).
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
from .departements import DEPARTEMENTS, postcode_to_departement
from .google_places_service import verify_batch
from .score import compute_score
from .sources.osm import OSMSource
from .store import LeadStore

log = logging.getLogger("leadfinder.pipeline")

_WEBSITE_KEYS = ("website", "contact:website", "url")

# Plafond de vérifications Google Places par scan — borne le coût (~2 appels
# API par lead : Text Search + Place Details). Partagé entre toutes les villes
# touchées par un scan (une seule pour scan_city, potentiellement plusieurs
# pour scan_departement) — pas de multiplication par ville.
_GMAPS_BATCH_LIMIT = 50


class ScanSummary(BaseModel):
    city: str
    total: int
    by_temperature: dict[str, int]
    by_status: dict[str, int]
    api_calls: int
    gmaps_checked: int = 0
    duration_seconds: float


async def _discover_classify_store(
    query: str,
    store: LeadStore,
    *,
    featuretype: Optional[str],
    fallback_city: str,
) -> tuple[list[dict], Counter, Counter, int]:
    """Découvre, classe, score et stocke les business trouvés pour `query`
    (nom de ville ou de département envoyé à Nominatim). Chaque ligne utilise
    la ville OSM réelle (`addr:city`) si connue, sinon `fallback_city` — pour
    un scan département, ça garantit que chaque lead garde sa vraie commune
    plutôt que le nom du département répété partout."""
    source = OSMSource()
    try:
        businesses = await source.discover(query, featuretype=featuretype)
    finally:
        await source.aclose()

    log.info("Scan %r : %d business découverts", query, len(businesses))

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
                "city": biz.city or fallback_city,
                "lat": biz.lat,
                "lng": biz.lng,
                "source": biz.source,
            }
        )
        temp_counts[sr.temperature.value] += 1
        status_counts[clf.status.value] += 1

    await store.batch_upsert(rows)
    return rows, temp_counts, status_counts, source.call_count


async def scan_city(city: str, store: LeadStore, http_client: Optional[httpx.AsyncClient] = None) -> ScanSummary:
    t0 = time.monotonic()
    rows, temp_counts, status_counts, api_calls = await _discover_classify_store(
        city, store, featuretype="city", fallback_city=city
    )

    gmaps_checked = 0
    if settings.has_google and http_client is not None and rows:
        cities = sorted({r["city"] for r in rows})
        gmaps_checked = await _verify_gmaps_signals(cities, store, http_client)

    return ScanSummary(
        city=city,
        total=len(rows),
        by_temperature=dict(temp_counts),
        by_status=dict(status_counts),
        api_calls=api_calls,
        gmaps_checked=gmaps_checked,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


async def scan_departement(
    dept_code: str, store: LeadStore, http_client: Optional[httpx.AsyncClient] = None
) -> ScanSummary:
    """Scanne un département entier — toutes les communes qu'il contient, pas
    seulement son chef-lieu. Nominatim résout le nom du département vers sa
    limite administrative complète (bbox couvrant tout le département,
    vérifié en amont), et `_fetch_bbox_recursive` subdivise déjà la zone si
    elle est trop dense pour Overpass — aucune découpe manuelle nécessaire."""
    t0 = time.monotonic()
    dept_name = DEPARTEMENTS.get(dept_code)
    if not dept_name:
        log.warning("Département inconnu : %r", dept_code)
        return ScanSummary(
            city=dept_code, total=0, by_temperature={}, by_status={},
            api_calls=0, gmaps_checked=0, duration_seconds=round(time.monotonic() - t0, 2),
        )

    query = f"{dept_name}, France"
    rows, temp_counts, status_counts, api_calls = await _discover_classify_store(
        query, store, featuretype=None, fallback_city=dept_name
    )

    gmaps_checked = 0
    if settings.has_google and http_client is not None and rows:
        cities = sorted({r["city"] for r in rows})
        gmaps_checked = await _verify_gmaps_signals(cities, store, http_client)

    return ScanSummary(
        city=f"{dept_name} ({dept_code})",
        total=len(rows),
        by_temperature=dict(temp_counts),
        by_status=dict(status_counts),
        api_calls=api_calls,
        gmaps_checked=gmaps_checked,
        duration_seconds=round(time.monotonic() - t0, 2),
    )


async def _verify_gmaps_signals(cities: list[str], store: LeadStore, client: httpx.AsyncClient) -> int:
    """Second passage Google Places : uniquement sur les leads sans site OSM,
    parmi les villes concernées par ce scan.

    Résout les statuts UNVERIFIED en NO_SITE quand Google confirme l'absence
    de site (recalcul via compute_score existant — pas de score parallèle).
    Les leads "déjà équipés" (gmaps_website rempli) et fermés définitivement
    ne changent pas de température : ils sont exclus du pipeline actif via
    LeadStore._ACTIVE_PIPELINE_WHERE, pas via une rétrogradation de score.
    """
    candidates = await store.get_leads_needing_gmaps_check(cities, limit=_GMAPS_BATCH_LIMIT)
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
            gmaps_rating=r.get("gmaps_rating"),
            gmaps_user_ratings_total=r.get("gmaps_user_ratings_total"),
        )

    return len(results)
