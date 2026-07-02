"""Adapter OpenStreetMap — source par défaut, 100 % gratuite, sans compte.

Deux services publics OSM sont utilisés :
  - **Nominatim** : résout une ville → bbox + zone administrative (1 appel/ville).
  - **Overpass API** : récupère tous les business lucratifs de la zone.

Règles de bon citoyen (sinon bannissement IP) :
  - `User-Agent` identifiable obligatoire.
  - Nominatim : 1 requête/seconde max.
  - Overpass : requêtes lourdes → on découpe la bbox en sous-cellules si le
    serveur renvoie une réponse tronquée / timeout, et on espace les appels.
  - Retry exponentiel sur 429/504.

Aucune clé n'est requise. Le compteur `call_count` trace chaque appel réseau
pour la garantie "0 €".
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from .base import BusinessSource, RawBusiness

log = logging.getLogger("leadfinder.osm")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",  # miroir de secours
]

# User-Agent identifiable, exigé par les ToS Nominatim/Overpass.
USER_AGENT = "LeadFinder/0.1 (local prospecting tool; contact: clem.garnero753@gmail.com)"

# --- Quels tags OSM considérer comme "business privé à but lucratif" ---------
# On vise large mais on exclut le non-lucratif (écoles, mairies, lieux de culte).
# Clé OSM -> soit True (toutes les valeurs), soit un set de valeurs autorisées.
LUCRATIVE_FILTERS: dict[str, Any] = {
    "shop": True,                       # tous commerces
    "craft": True,                      # artisans
    "office": True,                     # dont office=estate_agent (agents immo), lawyer, etc.
    "healthcare": True,                 # praticiens privés
    "amenity": {
        "restaurant", "cafe", "bar", "pub", "fast_food", "food_court",
        "pharmacy", "dentist", "doctors", "clinic", "veterinary",
        "fuel", "car_wash", "car_rental", "driving_school", "bank",
        "nightclub", "ice_cream", "cinema", "spa", "marketplace",
    },
    "leisure": {
        "fitness_centre", "sports_centre", "escape_game", "amusement_arcade",
        "bowling_alley", "dance", "trampoline_park", "laser_tag", "hackerspace",
    },
    "tourism": {"hotel", "guest_house", "motel", "hostel", "apartment", "chalet"},
}

# Mapping OSM -> type interne normalisé (utilisé par score.py / l'UI).
# On garde une granularité utile au démarchage, pas le détail OSM complet.
TYPE_MAP: dict[tuple[str, str], str] = {
    ("amenity", "restaurant"): "restaurant",
    ("amenity", "fast_food"): "fast_food",
    ("amenity", "cafe"): "cafe_bar",
    ("amenity", "bar"): "cafe_bar",
    ("amenity", "pub"): "cafe_bar",
    ("amenity", "pharmacy"): "pharmacie",
    ("amenity", "dentist"): "sante",
    ("amenity", "doctors"): "sante",
    ("amenity", "clinic"): "sante",
    ("amenity", "veterinary"): "sante",
    ("office", "estate_agent"): "agent_immobilier",
    ("office", "lawyer"): "juridique",
    ("office", "notary"): "juridique",
    ("office", "accountant"): "comptable",
    ("office", "insurance"): "assurance",
    ("shop", "hairdresser"): "coiffeur",
    ("shop", "beauty"): "beaute",
    ("shop", "bakery"): "boulangerie",
    ("shop", "butcher"): "alimentation",
    ("leisure", "escape_game"): "loisir_indoor",
    ("leisure", "laser_tag"): "loisir_indoor",
    ("leisure", "amusement_arcade"): "loisir_indoor",
    ("leisure", "bowling_alley"): "loisir_indoor",
    ("leisure", "fitness_centre"): "sport",
    ("leisure", "sports_centre"): "sport",
    ("tourism", "hotel"): "hotellerie",
}


def _normalize_type(tags: dict[str, str]) -> str:
    """Type interne à partir des tags. Fallback : 'craft:xxx' / 'shop:xxx' / 'autre'."""
    for key in ("amenity", "office", "shop", "leisure", "tourism", "craft", "healthcare"):
        val = tags.get(key)
        if not val:
            continue
        mapped = TYPE_MAP.get((key, val))
        if mapped:
            return mapped
        if key == "craft":
            return "artisan"
        if key == "shop":
            return "commerce"
        if key == "healthcare":
            return "sante"
        return val
    return "autre"


def _is_lucrative(tags: dict[str, str]) -> bool:
    for key, allowed in LUCRATIVE_FILTERS.items():
        val = tags.get(key)
        if val is None:
            continue
        if allowed is True or (isinstance(allowed, set) and val in allowed):
            return True
    return False


def _build_address(tags: dict[str, str]) -> Optional[str]:
    parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:city", ""),
    ]
    addr = " ".join(p for p in parts if p).strip()
    return addr or None


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """Construit une requête Overpass QL pour une bbox (south, west, north, east).

    On interroge nodes + ways + relations pour chaque famille de tags lucratifs,
    `out center` pour récupérer un point même pour les ways/relations.
    """
    s, w, n, e = bbox
    b = f"({s},{w},{n},{e})"
    clauses: list[str] = []
    for key, allowed in LUCRATIVE_FILTERS.items():
        if allowed is True:
            for elem in ("node", "way", "relation"):
                clauses.append(f'{elem}["{key}"]{b};')
        else:
            regex = "|".join(sorted(allowed))
            for elem in ("node", "way", "relation"):
                clauses.append(f'{elem}["{key}"~"^({regex})$"]{b};')
    body = "\n  ".join(clauses)
    return f"[out:json][timeout:25];\n(\n  {body}\n);\nout center tags;"


class OSMSource(BusinessSource):
    name = "osm"

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(120.0),
        )
        self._owns_client = client is None
        self._calls = 0
        # Verrou + horodatage pour garantir 1 req/s côté Nominatim.
        self._last_nominatim = 0.0
        self._nominatim_lock = asyncio.Lock()

    @property
    def call_count(self) -> int:
        return self._calls

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # -- Étape 1 : requête -> zone -------------------------------------------
    async def _resolve_city(
        self, query: str, featuretype: Optional[str] = "city"
    ) -> Optional[tuple[float, float, float, float]]:
        """Renvoie la bbox (south, west, north, east) résolue par Nominatim, ou None.

        `featuretype="city"` restreint aux villes (recherche par ville, comportement
        historique). `featuretype=None` laisse Nominatim résoudre librement — utilisé
        pour un département, où le meilleur résultat est la limite administrative
        entière (vérifié : `"Gironde, France"` résout bien vers un `boundingbox`
        couvrant tout le département, pas seulement son chef-lieu)."""
        async with self._nominatim_lock:
            # respecter 1 req/s
            now = asyncio.get_event_loop().time()
            wait = 1.0 - (now - self._last_nominatim)
            if wait > 0:
                await asyncio.sleep(wait)
            params = {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 0,
            }
            if featuretype:
                params["featuretype"] = featuretype
            self._calls += 1
            resp = await self._request_with_retry("GET", NOMINATIM_URL, params=params)
            self._last_nominatim = asyncio.get_event_loop().time()
        if resp is None:
            return None
        data = resp.json()
        if not data:
            log.warning("Nominatim n'a pas résolu: %r", query)
            return None
        bb = data[0].get("boundingbox")  # [south, north, west, east] (strings)
        if not bb or len(bb) != 4:
            return None
        south, north, west, east = (float(x) for x in bb)
        log.info("%r -> bbox S=%.4f W=%.4f N=%.4f E=%.4f", query, south, west, north, east)
        return (south, west, north, east)

    # -- Étape 2 : zone -> business ----------------------------------------
    async def discover(self, city: str, featuretype: Optional[str] = "city") -> list[RawBusiness]:
        bbox = await self._resolve_city(city, featuretype=featuretype)
        if bbox is None:
            return []

        elements = await self._fetch_bbox_recursive(bbox, depth=0)

        # Dédoublonnage par id stable osm_type:osm_id.
        seen: dict[str, RawBusiness] = {}
        for el in elements:
            biz = self._element_to_business(el)
            if biz is None:
                continue
            seen.setdefault(biz.id, biz)

        results = list(seen.values())
        log.info(
            "%r : %d business uniques (%d éléments bruts, %d appels réseau)",
            city, len(results), len(elements), self._calls,
        )
        return results

    async def _fetch_bbox_recursive(
        self, bbox: tuple[float, float, float, float], depth: int, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        """Récupère les éléments d'une bbox ; découpe en 4 sous-cellules si la
        réponse est tronquée (trop volumineuse) OU si Overpass échoue/timeout
        sur cette zone — une bbox de département entier est un cas classique
        de requête trop lourde pour passer en un seul appel (confirmé en
        conditions réelles : 504 Gateway Timeout sur une zone de la taille de
        l'Ain). Une bbox 4x plus petite est une requête plus légère, donc plus
        susceptible de passer même si le serveur est chargé."""
        query = _overpass_query(bbox)
        resp = await self._overpass_call(query)

        if resp is None:
            if depth < max_depth:
                log.warning("Overpass KO sur bbox %s (depth=%d) -> subdivision", bbox, depth)
                return await self._split_and_fetch(bbox, depth, max_depth)
            log.warning("Overpass KO sur bbox %s -> abandon (profondeur max atteinte)", bbox)
            return []

        elements = resp.get("elements", [])
        # Heuristique de saturation : Overpass tronque vers ~la limite mémoire.
        # Si on est proche d'un palier suspect et qu'on peut encore subdiviser,
        # on découpe pour ne rien rater sur les grosses villes.
        if len(elements) >= 8000 and depth < max_depth:
            log.info("bbox %s saturée (%d éléments) -> subdivision", bbox, len(elements))
            return await self._split_and_fetch(bbox, depth, max_depth)
        return elements

    async def _split_and_fetch(
        self, bbox: tuple[float, float, float, float], depth: int, max_depth: int
    ) -> list[dict[str, Any]]:
        s, w, n, e = bbox
        mid_lat = (s + n) / 2
        mid_lng = (w + e) / 2
        quadrants = [
            (s, w, mid_lat, mid_lng),
            (s, mid_lng, mid_lat, e),
            (mid_lat, w, n, mid_lng),
            (mid_lat, mid_lng, n, e),
        ]
        out: list[dict[str, Any]] = []
        for q in quadrants:
            out.extend(await self._fetch_bbox_recursive(q, depth + 1, max_depth))
        return out

    def _element_to_business(self, el: dict[str, Any]) -> Optional[RawBusiness]:
        tags: dict[str, str] = el.get("tags") or {}
        if not _is_lucrative(tags):
            return None
        name = tags.get("name")
        if not name:
            return None  # sans nom, inexploitable pour du démarchage

        # Coordonnées : node -> lat/lon ; way/relation -> center.
        if "lat" in el and "lon" in el:
            lat, lng = float(el["lat"]), float(el["lon"])
        elif "center" in el:
            lat, lng = float(el["center"]["lat"]), float(el["center"]["lon"])
        else:
            return None

        osm_type = el.get("type", "node")
        osm_id = el.get("id")
        stable_id = f"{osm_type}:{osm_id}"

        website = (
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("url")
        )
        phone = tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile")

        return RawBusiness(
            id=stable_id,
            name=name,
            lat=lat,
            lng=lng,
            business_type=_normalize_type(tags),
            source=self.name,
            phone=phone,
            website=website,
            address=_build_address(tags),
            postcode=tags.get("addr:postcode"),
            city=tags.get("addr:city"),
            opening_hours=tags.get("opening_hours"),
            raw_tags=tags,
        )

    # -- Couche réseau bas niveau ------------------------------------------
    async def _overpass_call(self, query: str) -> Optional[dict[str, Any]]:
        """Appelle Overpass avec bascule sur miroir + retry."""
        for url in OVERPASS_URLS:
            self._calls += 1
            resp = await self._request_with_retry("POST", url, data={"data": query}, max_retries=2)
            if resp is not None:
                try:
                    return resp.json()
                except Exception:  # réponse non-JSON (HTML d'erreur)
                    log.warning("Réponse Overpass non-JSON depuis %s", url)
                    continue
        return None

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        max_retries: int = 4,
    ) -> Optional[httpx.Response]:
        delay = 2.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = await self._client.request(method, url, params=params, data=data)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                log.warning("Réseau KO (%s) tentative %d/%d: %s", url, attempt, max_retries, exc)
                resp = None
            else:
                if resp.status_code == 200:
                    return resp
                if resp.status_code in (429, 503, 504):
                    log.warning(
                        "Rate-limit/serveur (%s) %d, retry dans %.0fs", url, resp.status_code, delay
                    )
                else:
                    log.error("HTTP %d sur %s", resp.status_code, url)
                    return None
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2  # backoff exponentiel
        return None
