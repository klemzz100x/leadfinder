"""Classification du statut web d'un business — LE CŒUR MÉTIER.

Règle fondamentale du démarchage : **un Facebook, un lien UberEats, une fiche
TripAdvisor/PagesJaunes ne comptent PAS comme un vrai site**. Ces business sont
des leads CHAUDS, pas froids.

Les 7 statuts (cf. spec) :

    NO_SITE          aucune URL connue                       -> chaud
    SOCIAL_ONLY      domaine réseau social                   -> chaud
    AGGREGATOR       domaine d'agrégateur/annuaire/livraison  -> chaud
    FREE_BUILDER     sous-domaine de constructeur gratuit     -> tiède
    REAL_SITE_POOR   vrai domaine mais audit faible           -> tiède (fixé par audit.py)
    REAL_SITE_OK     vrai domaine + audit correct             -> froid (fixé par audit.py)
    UNVERIFIED       pas de tag website -> indéterminé         -> à vérifier

À ce stade (sans audit), un vrai domaine est classé `REAL_SITE_OK` par défaut
puis pourra être rétrogradé en `REAL_SITE_POOR` par `audit.py` (Phase 1+).

Les listes de domaines sont éditables ici (et surchargables via config plus
tard) — c'est volontairement la donnée la plus sensible du métier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse


class WebStatus(str, Enum):
    NO_SITE = "NO_SITE"
    SOCIAL_ONLY = "SOCIAL_ONLY"
    AGGREGATOR = "AGGREGATOR"
    FREE_BUILDER = "FREE_BUILDER"
    REAL_SITE_POOR = "REAL_SITE_POOR"
    REAL_SITE_OK = "REAL_SITE_OK"
    UNVERIFIED = "UNVERIFIED"


# --- Listes de domaines éditables --------------------------------------------
# On matche sur le domaine "enregistrable" (eTLD+1) ET en sous-chaîne, pour
# attraper les sous-domaines (ex. "le-resto.wixsite.com").

SOCIAL_DOMAINS: set[str] = {
    "facebook.com", "fb.com", "fb.me", "m.facebook.com",
    "instagram.com", "instagr.am",
    "linktr.ee", "beacons.ai", "linktree.com",
    "tiktok.com", "x.com", "twitter.com",
    "youtube.com", "snapchat.com", "pinterest.com",
    "wa.me", "whatsapp.com",
}

AGGREGATOR_DOMAINS: set[str] = {
    # livraison
    "ubereats.com", "deliveroo.fr", "deliveroo.com", "just-eat.fr", "justeat.fr",
    # réservation resto
    "thefork.fr", "thefork.com", "lafourchette.com", "lafourchette.fr",
    "resto.fr", "opentable.com",
    # avis / annuaires
    "tripadvisor.fr", "tripadvisor.com", "yelp.fr", "yelp.com",
    "pagesjaunes.fr", "pages-jaunes.fr", "mappy.com", "petitfute.com",
    "google.com", "goo.gl", "g.page",        # fiche Google Business, pas un site
    # santé / pros
    "doctolib.fr", "maiia.com", "leboncoin.fr",
}

FREE_BUILDER_DOMAINS: set[str] = {
    "wixsite.com", "wix.com",
    "business.site",                          # Google Sites gratuit
    "godaddysites.com",
    "e-monsite.com", "emonsite.com",
    "sitew.com", "sitew.fr",
    "eatbu.com",                              # builder resto
    "jimdo.com", "jimdosite.com",
    "weebly.com",
    "wordpress.com",                          # .wordpress.com gratuit (≠ WP auto-hébergé)
    "blogspot.com", "wixstudio.com",
    "myshopify.com",                          # boutique sans domaine propre
    "page.link", "carrd.co", "strikingly.com",
}


@dataclass(slots=True)
class Classification:
    status: WebStatus
    matched_domain: Optional[str] = None     # domaine qui a déclenché le verdict
    reason: str = ""                          # explication lisible (UI/debug)


def _registrable_domain(host: str) -> str:
    """Renvoie une approximation eTLD+1 sans dépendance externe.

    Suffisant ici car nos listes ciblent des domaines connus. Pour les eTLD
    composés FR courants (.co.uk, etc.) on reste volontairement simple : le
    matching se fait aussi en sous-chaîne, donc une approximation suffit.
    """
    host = host.lower().strip().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _extract_host(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if "://" not in url:
        url = "http://" + url            # urlparse a besoin d'un schéma
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def _domain_in(host: str, domains: set[str]) -> Optional[str]:
    """Retourne le domaine matché si `host` correspond à un domaine de la liste.

    Match si égalité eTLD+1 OU si le host se termine par ".<domaine>".
    """
    reg = _registrable_domain(host)
    for d in domains:
        if reg == d or host == d or host.endswith("." + d):
            return d
    return None


def classify(website: Optional[str], *, has_website_tag: bool = True) -> Classification:
    """Classe le statut web à partir de l'URL connue.

    `has_website_tag` distingue :
      - OSM connaît un tag website -> on fait confiance (NO_SITE si vide).
      - OSM n'a aucun tag website ET on n'a pas pu vérifier -> UNVERIFIED.

    En pratique osm.py passe l'URL si présente, sinon None + has_website_tag=False.
    """
    host = _extract_host(website or "")

    if host is None:
        if has_website_tag:
            # On *sait* qu'il n'y a pas de site (ex. source fiable, champ vide).
            return Classification(WebStatus.NO_SITE, reason="Aucune URL connue")
        # OSM muet : on ne sait pas -> à vérifier (1 tap dans l'UI).
        return Classification(
            WebStatus.UNVERIFIED,
            reason="OSM ne fournit pas de site ; à vérifier manuellement",
        )

    if (d := _domain_in(host, SOCIAL_DOMAINS)) is not None:
        return Classification(WebStatus.SOCIAL_ONLY, d, f"Réseau social ({d}) ≠ vrai site")

    if (d := _domain_in(host, AGGREGATOR_DOMAINS)) is not None:
        return Classification(WebStatus.AGGREGATOR, d, f"Agrégateur/annuaire ({d}) ≠ vrai site")

    if (d := _domain_in(host, FREE_BUILDER_DOMAINS)) is not None:
        return Classification(WebStatus.FREE_BUILDER, d, f"Constructeur gratuit ({d})")

    # Vrai domaine propre. Sans audit, on l'estime OK ; audit.py peut rétrograder.
    return Classification(
        WebStatus.REAL_SITE_OK,
        _registrable_domain(host),
        "Vrai domaine (audit non encore lancé)",
    )


def is_aggregator(website: Optional[str]) -> bool:
    """Helper pour le bonus de scoring : présent sur agrégateur payant ?"""
    host = _extract_host(website or "")
    return host is not None and _domain_in(host, AGGREGATOR_DOMAINS) is not None
