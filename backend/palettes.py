"""Palette de couleurs par secteur, formalisant les choix faits à la main sur
les 18 premiers sites générés cette session (fleuriste = vert/rose, fromagerie
= ambre/brun, librairie = bordeaux/or, auto = rouge/ardoise...).

Clé par `business_type` (pas par catégorie de `categories.py`, trop large :
"Artisans & Commerce" regroupe aussi bien un fleuriste qu'un garage auto, qui
n'ont visuellement rien à voir — la granularité `business_type` est le
meilleur compromis déterministe sans réintroduire un jugement créatif par
établissement individuel).

Chaque palette remplace les 3 nuances du thème par défaut des templates
(`rose-400`/`rose-600`/`rose-700`, visibles dans les fichiers .astro sous
`src/components/`) — même mécanique que les commandes `sed` passées à la main
ce tour-ci, formalisée en une fonction réutilisable.

Limite assumée : à l'intérieur d'un même `business_type` générique (ex.
"commerce"), impossible de distinguer un fleuriste d'une librairie sans
jugement humain ou appel LLM — non fait ici par choix (cf. plan), la palette
"commerce" reste un compromis volontairement neutre.
"""

from __future__ import annotations

import re
from pathlib import Path

_DEFAULT_TOKENS = {"rose-400": "rose-400", "rose-600": "rose-600", "rose-700": "rose-700"}

# {business_type: {token_actuel: token_cible}}
PALETTES: dict[str, dict[str, str]] = {
    # Restauration — chaleureux, ambré (cf. Chez Delphine, fromagerie)
    "restaurant": {"rose-400": "amber-500", "rose-600": "amber-700", "rose-700": "stone-900"},
    "cafe_bar": {"rose-400": "amber-500", "rose-600": "amber-700", "rose-700": "stone-900"},
    "boulangerie": {"rose-400": "amber-500", "rose-600": "amber-700", "rose-700": "stone-900"},
    "alimentation": {"rose-400": "amber-500", "rose-600": "amber-700", "rose-700": "stone-900"},
    "fast_food": {"rose-400": "orange-400", "rose-600": "orange-600", "rose-700": "orange-800"},
    # Beauté & Bien-être — thème natif des templates, aucun remplacement
    "coiffeur": dict(_DEFAULT_TOKENS),
    "beaute": dict(_DEFAULT_TOKENS),
    "sport": dict(_DEFAULT_TOKENS),
    # Immobilier & Juridique — sobre, confiance
    "agent_immobilier": {"rose-400": "indigo-400", "rose-600": "indigo-600", "rose-700": "indigo-900"},
    "juridique": {"rose-400": "indigo-400", "rose-600": "indigo-600", "rose-700": "indigo-900"},
    "comptable": {"rose-400": "indigo-400", "rose-600": "indigo-600", "rose-700": "indigo-900"},
    "assurance": {"rose-400": "indigo-400", "rose-600": "indigo-600", "rose-700": "indigo-900"},
    # Santé — apaisant
    "sante": {"rose-400": "teal-400", "rose-600": "teal-600", "rose-700": "teal-800"},
    "pharmacie": {"rose-400": "teal-400", "rose-600": "teal-600", "rose-700": "teal-800"},
    # Loisirs — évasion, bleu ciel/océan
    "loisir_indoor": {"rose-400": "sky-400", "rose-600": "sky-600", "rose-700": "sky-800"},
    "hotellerie": {"rose-400": "sky-400", "rose-600": "sky-600", "rose-700": "sky-800"},
    "tourisme": {"rose-400": "sky-400", "rose-600": "sky-600", "rose-700": "sky-800"},
    # Artisans — cf. Degrif Auto (garage), ton "atelier"
    "artisan": {"rose-400": "red-500", "rose-600": "red-700", "rose-700": "slate-900"},
    # Commerce générique — cf. Librairie Folies d'Encre, compromis neutre
    "commerce": {"rose-400": "emerald-400", "rose-600": "emerald-700", "rose-700": "emerald-900"},
    "autre": dict(_DEFAULT_TOKENS),
}

_ASTRO_TOKEN_RE = re.compile(r"\brose-(400|600|700)\b")


def get_palette(business_type: str) -> dict[str, str]:
    return PALETTES.get(business_type, dict(_DEFAULT_TOKENS))


def apply_palette(site_dir: Path, business_type: str) -> None:
    """Remplace les tokens Tailwind rose-400/600/700 dans tous les .astro de
    src/components/ par la palette du secteur — no-op si palette = défaut."""
    palette = get_palette(business_type)
    if palette == _DEFAULT_TOKENS:
        return

    components_dir = site_dir / "src" / "components"
    if not components_dir.is_dir():
        return

    for astro_file in components_dir.glob("*.astro"):
        text = astro_file.read_text(encoding="utf-8")
        new_text = _ASTRO_TOKEN_RE.sub(lambda m: palette[f"rose-{m.group(1)}"], text)
        if new_text != text:
            astro_file.write_text(new_text, encoding="utf-8")
