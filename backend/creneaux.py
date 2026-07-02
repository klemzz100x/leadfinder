"""Créneaux d'appel indicatifs par famille de secteur.

Même logique que categories.py (table budgets par catégorie) : chaque
famille porte une liste de `business_type` regroupés et un créneau horaire
indicatif ("meilleur moment pour appeler"), éditable depuis le dashboard
(CreneauxEditor.jsx) — jamais en dur dans le code une fois modifié.

Une famille de secteur est un regroupement différent (granularité, noms) des
catégories de categories.py (qui portent des budgets cibles) : les deux
tables coexistent, chacune pour son usage propre.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("leadfinder.creneaux")

DEFAULT_FAMILLES: dict[str, dict[str, Any]] = {
    "Restauration / CHR": {
        "types": ["restaurant", "fast_food", "cafe_bar", "boulangerie", "alimentation"],
        "creneau": "15h–18h",
    },
    "Beauté & bien-être": {
        "types": ["coiffeur", "beaute", "sport"],
        "creneau": "9h30–11h",
    },
    "Artisanat / BTP": {
        "types": ["artisan"],
        "creneau": "7h–8h30 ou 12h–13h30",
    },
    "Commerce de proximité": {
        "types": ["commerce"],
        "creneau": "10h30–12h",
    },
    "Hôtellerie & tourisme": {
        "types": ["hotellerie", "tourisme"],
        "creneau": "10h–12h",
    },
    "Services B2B / professions": {
        "types": ["juridique", "comptable", "assurance"],
        "creneau": "9h–10h30",
    },
    "Services aux particuliers": {
        "types": [],
        "creneau": "10h–11h30",
    },
    "Immobilier": {
        "types": ["agent_immobilier"],
        "creneau": "10h–12h ou 14h–17h",
    },
    "Automobile": {
        "types": [],
        "creneau": "8h–9h ou 12h–13h30",
    },
}

_CRENEAUX_FILE = Path(__file__).parent.parent / "creneaux.json"


def _normalize(entry: Any) -> dict[str, Any]:
    return {
        "types": entry.get("types", []),
        "creneau": entry.get("creneau") or "",
    }


def load_familles() -> dict[str, dict[str, Any]]:
    """Charge les familles depuis creneaux.json ou retourne DEFAULT_FAMILLES."""
    if _CRENEAUX_FILE.exists():
        try:
            with _CRENEAUX_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {name: _normalize(entry) for name, entry in data.items()}
        except Exception as exc:
            log.warning("Erreur lecture creneaux.json : %s", exc)
    return {name: dict(entry) for name, entry in DEFAULT_FAMILLES.items()}


def save_familles(familles: dict[str, Any]) -> None:
    """Sauvegarde les familles dans creneaux.json."""
    normalized = {name: _normalize(entry) for name, entry in familles.items()}
    with _CRENEAUX_FILE.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def types_to_creneau(familles: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Mapping inverse business_type -> créneau indicatif de sa famille.

    Un business_type non couvert par aucune famille n'apparaît pas dans le
    mapping — le créneau reste vide côté affichage plutôt que d'inventer une
    valeur par défaut arbitraire (cf. consigne)."""
    out: dict[str, str] = {}
    for entry in familles.values():
        creneau = entry.get("creneau") or ""
        if not creneau:
            continue
        for t in entry.get("types", []):
            out[t] = creneau
    return out
