"""Recherche de SIRET via l'API publique du gouvernement (gratuite, sans
clé) — recherche-entreprises.api.gouv.fr.

Reproduit la méthode utilisée à la main tout au long de cette session :
chercher par nom + ville, ne retenir un résultat que si son établissement est
**actif** (le piège du SIRET fermé rencontré plusieurs fois — cf. Fleurtez,
où l'ancien enregistrement était fermé depuis 2019 alors que le commerce
tournait toujours), et vérifier que le code postal correspond pour éviter de
retenir un homonyme dans une autre ville. Jamais de SIRET inventé : `None` si
rien de fiable, le générateur de devis garde son comportement actuel
("à compléter — statut SIRET à vérifier sur place").
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

log = logging.getLogger("leadfinder.siret_lookup")

_SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"
_POSTCODE_RE = re.compile(r"\b(\d{5})\b")


async def find_siret(client: httpx.AsyncClient, name: str, address: str) -> Optional[str]:
    postcode_match = _POSTCODE_RE.search(address or "")
    postcode = postcode_match.group(1) if postcode_match else None

    try:
        resp = await client.get(_SEARCH_URL, params={"q": name, "limite": 5}, timeout=10.0)
    except httpx.HTTPError as exc:
        log.warning("Recherche SIRET KO pour %r : %s", name, exc)
        return None
    if resp.status_code != 200:
        log.warning("Recherche SIRET HTTP %d pour %r", resp.status_code, name)
        return None

    results = resp.json().get("results") or []
    for result in results:
        siege = result.get("siege") or {}
        if siege.get("etat_administratif") != "A":
            continue
        if postcode and siege.get("code_postal") != postcode:
            continue
        siret = siege.get("siret")
        if siret:
            return siret
    return None
