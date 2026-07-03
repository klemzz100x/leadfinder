"""Prix de devis suggéré par lead, à partir de signaux d'activité réels —
pas seulement la catégorie générique.

    score = 0.45 × note Google (normalisée /5)
          + 0.30 × volume d'avis Google (normalisé, échelle log, plafonné ~200 avis)
          + 0.25 × valeur du secteur (BUSINESS_VALUE, déjà utilisée pour la
                   température des leads — cf. score.py, même raisonnement
                   "artisanat/hôtellerie > commerce générique" réutilisé tel quel)

    prix = budget_min_catégorie + score × (budget_max_catégorie − budget_min_catégorie)

Chaque catégorie a son propre écart budget_min/budget_max (cf.
categories.py — plus aucune catégorie à min == max ou None/None depuis la
Phase 7) : le score positionne le prix DANS l'écart propre à son secteur,
il ne le fait jamais sortir de la fourchette 500-750€ vs 850-1150€ etc.
définie par la catégorie.

Note/avis absents (jamais vérifié côté Google) -> composante neutre (0.5),
pour ne pas pénaliser un lead par manque de donnée plutôt que par signal
réellement défavorable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .categories import load_categories, types_to_category
from .score import BUSINESS_VALUE, DEFAULT_VALUE

W_RATING = 0.45
W_REVIEWS = 0.30
W_SECTOR = 0.25

# Au-delà de ce nombre d'avis, le signal "volume" est considéré maximal —
# un établissement à 2000 avis ne doit pas écraser un établissement à 200.
REVIEWS_CAP = 200


@dataclass(slots=True)
class PriceSuggestion:
    prix: int
    justification: str
    breakdown: dict[str, float]


def _normalize_rating(rating: Optional[float]) -> float:
    if rating is None:
        return 0.5
    return max(0.0, min(1.0, rating / 5.0))


def _normalize_reviews(count: Optional[int]) -> float:
    if not count:
        return 0.5 if count is None else 0.0  # None = jamais vérifié (neutre) ; 0 = vérifié et vraiment aucun avis
    return max(0.0, min(1.0, math.log10(count + 1) / math.log10(REVIEWS_CAP + 1)))


def suggest_price(
    business_type: str,
    gmaps_rating: Optional[float],
    gmaps_user_ratings_total: Optional[int],
) -> PriceSuggestion:
    categories = load_categories()
    type_to_cat = types_to_category(categories)
    cat_name = type_to_cat.get(business_type, "Autre")
    cat = categories.get(cat_name, {})

    budget_min = cat.get("budget_min")
    budget_max = cat.get("budget_max")
    if budget_min is None or budget_max is None:
        # Catégorie "Autre" (hors table) ou non configurée -> fourchette
        # générique, jamais un montant inventé hors de toute base.
        budget_min, budget_max = 500, 750

    rating_n = _normalize_rating(gmaps_rating)
    reviews_n = _normalize_reviews(gmaps_user_ratings_total)
    sector_n = BUSINESS_VALUE.get(business_type, DEFAULT_VALUE)

    score = W_RATING * rating_n + W_REVIEWS * reviews_n + W_SECTOR * sector_n
    prix = round(budget_min + score * (budget_max - budget_min))

    justification = _build_justification(gmaps_rating, gmaps_user_ratings_total, sector_n)

    return PriceSuggestion(
        prix=prix,
        justification=justification,
        breakdown={
            "score": round(score, 3),
            "rating_normalise": round(rating_n, 3),
            "avis_normalise": round(reviews_n, 3),
            "secteur_normalise": round(sector_n, 3),
            "budget_min": budget_min,
            "budget_max": budget_max,
        },
    )


def _build_justification(rating: Optional[float], reviews: Optional[int], sector_n: float) -> str:
    parts: list[str] = []
    if rating is not None and reviews is not None:
        if rating >= 4.3 and reviews >= 30:
            parts.append("bonne notoriété locale")
        elif rating and rating < 3.5:
            parts.append("réputation à surveiller")
        parts.append(f"{reviews} avis")
        parts.append(f"note {rating:g}")
    else:
        parts.append("avis Google non vérifiés")
    if sector_n >= 0.8:
        parts.append("secteur à fort pouvoir d'achat")
    elif sector_n <= 0.45:
        parts.append("secteur à budget plus serré")
    return ", ".join(parts)
