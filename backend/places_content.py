"""Contenu riche pour la génération automatisée de site (photos, avis,
horaires) — étend google_places_service.py avec un FieldMask élargi, appelé
uniquement au moment de l'envoi d'un lead (pas au scan initial : coût
inutile pour des leads qui ne seront peut-être jamais envoyés).

Alternative testée et écartée : scraper Google Maps via Playwright sans
clé API. Une session anonyme reçoit une fiche réduite côté Google (horaires
du jour seul, aucun avis exploitable) — contourner cette limitation
reviendrait à contourner une détection anti-bot, refusé. L'API officielle
reste la seule voie fiable malgré son coût marginal réel (~0,025$/site,
tier "Enterprise + Atmosphere").

Photos strictement scopées au `place_id` recherché — contrairement au
carrousel Maps manuel qui mélangeait parfois des photos d'un établissement
voisin (observé plusieurs fois cette session), aucun risque de ce type ici.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .config import settings
from .google_places_service import _search_place_id, _QuotaExhausted

log = logging.getLogger("leadfinder.places_content")

_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
_CONTENT_FIELD_MASK = "photos,reviews,regularOpeningHours,editorialSummary"

_JOURS_FR = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
_ORDRE_AFFICHAGE = [1, 2, 3, 4, 5, 6, 0]  # Lundi -> Dimanche, convention des templates

MAX_PHOTOS = 4
MAX_REVIEWS = 3
MIN_REVIEW_RATING = 4


def _format_heure(h: dict[str, int]) -> str:
    return f"{h.get('hour', 0):02d}h{h.get('minute', 0):02d}"


def _format_horaires(regular_hours: Optional[dict[str, Any]]) -> list[dict[str, str]]:
    """Périodes brutes (jour 0=dimanche...6=samedi, cf. doc Places API) ->
    même format que site.config.json ({"jour": "Lundi", "heures": "..."})."""
    if not regular_hours:
        return []
    par_jour: dict[int, list[str]] = {}
    for period in regular_hours.get("periods", []):
        open_ = period.get("open")
        close = period.get("close")
        if not open_:
            continue
        jour = open_.get("day", 0)
        plage = _format_heure(open_)
        if close:
            plage += f"–{_format_heure(close)}"
        par_jour.setdefault(jour, []).append(plage)

    return [
        {"jour": _JOURS_FR[j], "heures": " / ".join(par_jour[j]) if j in par_jour else "Fermé"}
        for j in _ORDRE_AFFICHAGE
    ]


def _select_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidats = []
    for r in reviews:
        rating = r.get("rating", 0)
        if rating < MIN_REVIEW_RATING:
            continue
        # originalText (langue d'origine de l'auteur) préféré à text (parfois
        # traduit automatiquement, ex. avis français renvoyé en anglais sans
        # languageCode explicite dans la requête) — on veut le vrai texte du
        # client, pas une traduction.
        texte = (r.get("originalText") or {}).get("text") or (r.get("text") or {}).get("text")
        nom = (r.get("authorAttribution") or {}).get("displayName")
        if texte and nom:
            candidats.append({"nom": f"{nom} — avis Google", "note": rating, "texte": texte.strip()})
    candidats.sort(key=lambda a: len(a["texte"]), reverse=True)
    return candidats[:MAX_REVIEWS]


async def _download_photos(client: httpx.AsyncClient, photos: list[dict[str, Any]]) -> list[bytes]:
    out: list[bytes] = []
    for photo in photos[:MAX_PHOTOS]:
        name = photo.get("name")
        if not name:
            continue
        try:
            resp = await client.get(
                f"https://places.googleapis.com/v1/{name}/media",
                params={"key": settings.GOOGLE_PLACES_API_KEY, "maxWidthPx": 1200},
                follow_redirects=True,
                timeout=15.0,
            )
            if resp.status_code == 200:
                out.append(resp.content)
        except httpx.HTTPError as exc:
            log.warning("Téléchargement photo KO : %s", exc)
    return out


async def get_send_content(
    client: httpx.AsyncClient, name: str, address: Optional[str], city: str
) -> Optional[dict[str, Any]]:
    """Retourne {horaires, avis, photos (bytes), editorial_summary} pour un
    établissement, ou None si introuvable/quota épuisé — jamais d'exception,
    l'appelant (send_orchestrator) doit dégrader proprement sans bloquer les
    autres leads d'un envoi groupé."""
    if not settings.has_google:
        return None
    try:
        place_id = await _search_place_id(client, name, address, city)
        if place_id is None:
            return None
        resp = await client.get(
            _DETAILS_URL.format(place_id=place_id),
            headers={"X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY, "X-Goog-FieldMask": _CONTENT_FIELD_MASK},
        )
        if resp.status_code in (403, 429):
            raise _QuotaExhausted(f"HTTP {resp.status_code} sur Place Details (contenu)")
        if resp.status_code != 200:
            log.warning("Places Details (contenu) HTTP %d pour %r", resp.status_code, name)
            return None
        details = resp.json()
    except _QuotaExhausted as exc:
        log.warning("Quota Places API épuisé pour %r : %s", name, exc)
        return None
    except httpx.HTTPError as exc:
        log.warning("Places API réseau KO pour %r : %s", name, exc)
        return None

    photos = await _download_photos(client, details.get("photos", []))
    return {
        "horaires": _format_horaires(details.get("regularOpeningHours")),
        "avis": _select_reviews(details.get("reviews", [])),
        "photos": photos,
        "editorial_summary": (details.get("editorialSummary") or {}).get("text"),
    }
