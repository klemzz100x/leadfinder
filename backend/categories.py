"""Configuration des catégories métier pour le groupement des leads.

Chaque catégorie porte, en plus de la liste de `business_type` regroupés,
un budget cible par deal (`budget_min`/`budget_max`) et un objectif de
nombre de closes mensuel optionnel (`objectif_closes_mensuel`), tous deux
éditables depuis l'UI (CategoryEditor.jsx) — jamais en dur dans le code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("leadfinder.categories")

DEFAULT_CATEGORIES: dict[str, dict[str, Any]] = {
    "Restauration": {
        "types": ["restaurant", "cafe_bar", "boulangerie", "alimentation"],
        "budget_min": 1000, "budget_max": 1000, "objectif_closes_mensuel": None,
    },
    "Restauration rapide": {
        "types": ["fast_food"],
        "budget_min": 500, "budget_max": 500, "objectif_closes_mensuel": None,
    },
    "Beauté & Bien-être": {
        "types": ["coiffeur", "beaute", "sport"],
        "budget_min": 500, "budget_max": 750, "objectif_closes_mensuel": None,
    },
    "Immobilier & Juridique": {
        "types": ["agent_immobilier", "juridique", "comptable", "assurance"],
        "budget_min": 500, "budget_max": 750, "objectif_closes_mensuel": None,
    },
    "Santé": {
        "types": ["sante", "pharmacie"],
        "budget_min": None, "budget_max": None, "objectif_closes_mensuel": None,
    },
    "Loisirs": {
        "types": ["loisir_indoor", "hotellerie", "tourisme"],
        "budget_min": None, "budget_max": None, "objectif_closes_mensuel": None,
    },
    "Artisans & Commerce": {
        "types": ["artisan", "commerce", "autre"],
        "budget_min": None, "budget_max": None, "objectif_closes_mensuel": None,
    },
}

_CATEGORIES_FILE = Path(__file__).parent.parent / "categories.json"


def _normalize(entry: Any) -> dict[str, Any]:
    """Rétro-compatibilité : une entrée peut être une simple liste (ancien format
    Phase 0) ou déjà le nouveau dict {types, budget_min, budget_max, objectif_closes_mensuel}."""
    if isinstance(entry, list):
        return {"types": entry, "budget_min": None, "budget_max": None, "objectif_closes_mensuel": None}
    return {
        "types": entry.get("types", []),
        "budget_min": entry.get("budget_min"),
        "budget_max": entry.get("budget_max"),
        "objectif_closes_mensuel": entry.get("objectif_closes_mensuel"),
    }


def load_categories() -> dict[str, dict[str, Any]]:
    """Charge les catégories depuis categories.json ou retourne DEFAULT_CATEGORIES."""
    if _CATEGORIES_FILE.exists():
        try:
            with _CATEGORIES_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {name: _normalize(entry) for name, entry in data.items()}
        except Exception as exc:
            log.warning("Erreur lecture categories.json : %s", exc)
    return {name: dict(entry) for name, entry in DEFAULT_CATEGORIES.items()}


def save_categories(categories: dict[str, Any]) -> None:
    """Sauvegarde les catégories dans categories.json."""
    normalized = {name: _normalize(entry) for name, entry in categories.items()}
    with _CATEGORIES_FILE.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def types_to_category(categories: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Mapping inverse business_type -> nom de catégorie (pour l'agrégation dashboard/stats)."""
    out: dict[str, str] = {}
    for name, entry in categories.items():
        for t in entry.get("types", []):
            out[t] = name
    return out
