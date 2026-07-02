"""Vérification Google Places — statut d'activité + site web existant.

Second passage, appelé uniquement sur les leads sans site trouvé côté OSM
(limite le coût — cf. pipeline.py). Utilise l'API Places (New) : Text Search
puis Place Details, avec un FieldMask restreint à chaque appel pour rester
sur le SKU le moins cher.

Aucune clé -> le service est inactif (cf. `settings.has_google`).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .config import settings

log = logging.getLogger("leadfinder.google_places")

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

_STATUS_MAP = {
    "OPERATIONAL": "operational",
    "CLOSED_TEMPORARILY": "closed_temporarily",
    "CLOSED_PERMANENTLY": "closed_permanently",
}


class _QuotaExhausted(Exception):
    """Levée sur 403/429 pour abandonner proprement le reste du batch."""


async def _search_place_id(client: httpx.AsyncClient, name: str, address: Optional[str], city: str) -> Optional[str]:
    query = ", ".join(p for p in (name, address or city) if p)
    resp = await client.post(
        _SEARCH_URL,
        json={"textQuery": query},
        headers={
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": "places.id",
        },
    )
    if resp.status_code in (403, 429):
        raise _QuotaExhausted(f"HTTP {resp.status_code} sur Text Search")
    if resp.status_code != 200:
        log.warning("Places Text Search HTTP %d pour %r", resp.status_code, query)
        return None
    places = resp.json().get("places") or []
    return places[0]["id"] if places else None


async def _get_place_details(client: httpx.AsyncClient, place_id: str) -> Optional[dict[str, Any]]:
    resp = await client.get(
        _DETAILS_URL.format(place_id=place_id),
        headers={
            "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": "businessStatus,websiteUri,googleMapsUri",
        },
    )
    if resp.status_code in (403, 429):
        raise _QuotaExhausted(f"HTTP {resp.status_code} sur Place Details")
    if resp.status_code != 200:
        log.warning("Places Details HTTP %d pour %s", resp.status_code, place_id)
        return None
    return resp.json()


async def verify_batch(candidates: list[dict[str, Any]], client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
    """Vérifie un lot de leads via Google Places.

    `candidates` : liste de dicts {id, name, address, city}.
    Retourne {lead_id: {gmaps_status, gmaps_website, gmaps_url}}. Un lead absent
    du résultat signifie un échec (le cache 30j côté store évitera une boucle de
    re-tentative immédiate, il sera retenté au prochain scan de la ville).
    """
    if not settings.has_google or not candidates:
        return {}

    # "unchecked" = tentative faite mais aucune correspondance Google trouvée ;
    # on l'enregistre quand même (cache 30j) pour ne pas re-tenter en boucle un
    # lead introuvable sur Google (mismatch de nom, etc.).
    not_found = {"gmaps_status": "unchecked", "gmaps_website": None, "gmaps_url": None}

    out: dict[str, dict[str, Any]] = {}
    try:
        for c in candidates:
            place_id = await _search_place_id(client, c["name"], c.get("address"), c["city"])
            if place_id is None:
                out[c["id"]] = not_found
                continue
            details = await _get_place_details(client, place_id)
            if details is None:
                out[c["id"]] = not_found
                continue
            out[c["id"]] = {
                "gmaps_status": _STATUS_MAP.get(details.get("businessStatus"), "unchecked"),
                "gmaps_website": details.get("websiteUri"),
                "gmaps_url": details.get("googleMapsUri"),
            }
    except _QuotaExhausted as exc:
        log.warning("Places API quota/permission KO, arrêt du batch (%d/%d déjà vérifiés): %s",
                    len(out), len(candidates), exc)
    except httpx.HTTPError as exc:
        log.warning("Places API réseau KO, arrêt du batch (%d/%d déjà vérifiés): %s",
                    len(out), len(candidates), exc)

    return out
