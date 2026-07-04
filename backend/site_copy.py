"""Rédaction du texte d'un site généré (accroche, description, garanties,
prestations) via l'API Claude — la seule étape du flux d'envoi automatisé qui
demande un vrai jugement rédactionnel (cf. plan : tout le reste — photos,
avis, palette, SIRET, prix — est déterministe).

Ne génère JAMAIS `responsable.histoire` : ce champ concerne une personne
réelle et identifiable, et rien dans les données disponibles (avis Google,
fiche établissement) ne permet de savoir de façon fiable qui dirige
l'établissement — inventer une biographie serait fabriquer un fait sur une
vraie personne, pas de la rédaction marketing défendable comme le reste. Ce
champ reste vide, à remplir à la main si souhaité (comme pour les 18 premiers
sites de cette session).

Repli sur un texte générique minimal (jamais un échec bloquant) si l'appel
échoue ou renvoie un JSON invalide — un seul lead en échec ne doit jamais
interrompre l'envoi groupé des autres.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .config import settings

log = logging.getLogger("leadfinder.site_copy")

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"  # texte court et structuré : pas besoin d'un modèle plus cher

_SCHEMA_HINT = """Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), de cette forme exacte :
{
  "accroche": "une phrase courte et concrète qui donne envie de venir",
  "description": "2-3 phrases présentant vraiment l'activité et ce qui la distingue",
  "garanties": [
    {"icone": "un seul emoji", "titre": "titre court", "texte": "texte court"},
    {"icone": "un seul emoji", "titre": "titre court", "texte": "texte court"},
    {"icone": "un seul emoji", "titre": "titre court", "texte": "texte court"},
    {"icone": "un seul emoji", "titre": "titre court", "texte": "texte court"}
  ],
  "prestations": [
    {"nom": "nom du service/produit", "duree": "précision courte (ou catégorie de produit)"},
    {"nom": "nom du service/produit", "duree": "précision courte (ou catégorie de produit)"},
    {"nom": "nom du service/produit", "duree": "précision courte (ou catégorie de produit)"},
    {"nom": "nom du service/produit", "duree": "précision courte (ou catégorie de produit)"}
  ]
}"""


@dataclass(slots=True)
class SiteCopy:
    accroche: str
    description: str
    garanties: list[dict[str, str]]
    prestations: list[dict[str, str]]
    fallback: bool = field(default=False)


def _fallback_copy(name: str, category: str, city: str) -> SiteCopy:
    return SiteCopy(
        accroche=f"{name} — {category} à {city}",
        description=(
            f"{name} vous accueille à {city}. Contactez l'établissement pour en savoir plus "
            "sur les prestations proposées."
        ),
        garanties=[
            {"icone": "✨", "titre": "Qualité", "texte": "Un savoir-faire reconnu localement"},
            {"icone": "🤝", "titre": "Accueil", "texte": "Une équipe à votre écoute"},
            {"icone": "📍", "titre": city, "texte": "Facile d'accès"},
            {"icone": "☎️", "titre": "Contact", "texte": "Renseignements par téléphone"},
        ],
        prestations=[
            {"nom": "Sur devis", "duree": "Nous consulter"},
            {"nom": "Sur devis", "duree": "Nous consulter"},
            {"nom": "Sur devis", "duree": "Nous consulter"},
            {"nom": "Sur devis", "duree": "Nous consulter"},
        ],
        fallback=True,
    )


def _build_prompt(
    name: str, category: str, city: str, avis: list[dict[str, Any]], editorial_summary: Optional[str]
) -> str:
    faits = [f"Nom : {name}", f"Secteur : {category}", f"Ville : {city}"]
    if editorial_summary:
        faits.append(f"Description Google : {editorial_summary}")
    if avis:
        faits.append("Avis clients réels (pour le ton, ne pas citer directement) :")
        for a in avis:
            faits.append(f'- {a["note"]}/5 : "{a["texte"][:200]}"')

    return (
        "Tu rédiges le contenu d'un site vitrine pour un petit commerce/artisan/professionnel français, "
        "à partir des faits ci-dessous. Ton naturel, concret, sans superlatifs vides ni tournures "
        "génériques de template (\"une expérience unique\", \"votre satisfaction est notre priorité\"...). "
        "Ne mentionne aucune personne par son nom (ne pas inventer qui dirige l'établissement).\n\n"
        + "\n".join(faits)
        + "\n\n"
        + _SCHEMA_HINT
    )


def _parse_response(text: str) -> Optional[dict[str, Any]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    required = {"accroche", "description", "garanties", "prestations"}
    if not required.issubset(data.keys()):
        return None
    if len(data["garanties"]) != 4 or len(data["prestations"]) != 4:
        return None
    return data


async def generate_copy(
    client: httpx.AsyncClient,
    name: str,
    category: str,
    city: str,
    avis: list[dict[str, Any]],
    editorial_summary: Optional[str] = None,
) -> SiteCopy:
    if not settings.has_anthropic:
        return _fallback_copy(name, category, city)

    prompt = _build_prompt(name, category, city, avis, editorial_summary)
    try:
        resp = await client.post(
            _API_URL,
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _MODEL,
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        if resp.status_code != 200:
            log.warning("Claude API HTTP %d pour %r", resp.status_code, name)
            return _fallback_copy(name, category, city)
        text = resp.json()["content"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        log.warning("Claude API KO pour %r : %s", name, exc)
        return _fallback_copy(name, category, city)

    data = _parse_response(text)
    if data is None:
        log.warning("Réponse Claude non exploitable pour %r, repli générique", name)
        return _fallback_copy(name, category, city)

    return SiteCopy(
        accroche=data["accroche"],
        description=data["description"],
        garanties=data["garanties"],
        prestations=data["prestations"],
    )
