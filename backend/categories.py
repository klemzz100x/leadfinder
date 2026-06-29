"""Configuration des catégories métier pour le groupement des leads."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("leadfinder.categories")

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Restauration": ["restaurant", "cafe_bar", "boulangerie", "alimentation"],
    "Beauté & Bien-être": ["coiffeur", "beaute", "sport"],
    "Immobilier & Juridique": ["agent_immobilier", "juridique", "comptable", "assurance"],
    "Santé": ["sante", "pharmacie"],
    "Loisirs": ["loisir_indoor", "hotellerie", "tourisme"],
    "Artisans & Commerce": ["artisan", "commerce", "autre"],
}

_CATEGORIES_FILE = Path(__file__).parent.parent / "categories.json"


def load_categories() -> dict[str, list[str]]:
    """Charge les catégories depuis categories.json ou retourne DEFAULT_CATEGORIES."""
    if _CATEGORIES_FILE.exists():
        try:
            with _CATEGORIES_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            log.warning("Erreur lecture categories.json : %s", exc)
    return dict(DEFAULT_CATEGORIES)


def save_categories(categories: dict[str, list[str]]) -> None:
    """Sauvegarde les catégories dans categories.json."""
    with _CATEGORIES_FILE.open("w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
