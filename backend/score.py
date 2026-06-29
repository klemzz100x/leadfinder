"""Scoring d'un lead et attribution d'une température (chaud / tiède / froid).

    score = poids_statut × valeur_business × besoin_visibilité × bonus

Principe des deux niveaux :
  - Le STATUT web qualifie le lead (plancher de température garanti par statut).
  - Le SCORE trie les leads dans la liste (il peut élever la température au-dessus
    du plancher, mais JAMAIS la faire descendre en-dessous).

Cela garantit que FREE_BUILDER (ex. coiffeur sur Wixsite) reste toujours ≥ tiède
même si son score brut est faible, car le pitch "upgrade" est toujours valide.

Toutes les tables sont éditables ici — calibrer après les premiers scans réels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .classify import WebStatus, is_aggregator


class Temperature(str, Enum):
    CHAUD = "chaud"
    TIEDE = "tiede"
    FROID = "froid"
    A_VERIFIER = "a_verifier"


# Ordre de priorité croissante (A_VERIFIER est hors-classement).
_TEMP_RANK: dict[Temperature, int] = {
    Temperature.FROID: 0,
    Temperature.TIEDE: 1,
    Temperature.CHAUD: 2,
}

# --- Tables de pondération ---------------------------------------------------

STATUS_WEIGHT: dict[WebStatus, float] = {
    WebStatus.NO_SITE: 1.0,
    WebStatus.SOCIAL_ONLY: 1.0,
    WebStatus.AGGREGATOR: 1.0,
    WebStatus.FREE_BUILDER: 0.7,
    WebStatus.REAL_SITE_POOR: 0.5,
    WebStatus.REAL_SITE_OK: 0.0,
    WebStatus.UNVERIFIED: 0.6,
}

# Plancher de température garanti par statut.
# Quelle que soit la valeur/visibilité du business, il ne descend jamais sous ce seuil.
STATUS_TEMP_FLOOR: dict[WebStatus, Temperature] = {
    WebStatus.NO_SITE: Temperature.CHAUD,
    WebStatus.SOCIAL_ONLY: Temperature.CHAUD,
    WebStatus.AGGREGATOR: Temperature.CHAUD,
    WebStatus.FREE_BUILDER: Temperature.TIEDE,   # pitch "upgrade" toujours valide
    WebStatus.REAL_SITE_POOR: Temperature.TIEDE,
    WebStatus.REAL_SITE_OK: Temperature.FROID,
    WebStatus.UNVERIFIED: Temperature.A_VERIFIER,
}

# Valeur d'un client / panier moyen estimé (échelle 0→1).
BUSINESS_VALUE: dict[str, float] = {
    "agent_immobilier": 1.0,
    "juridique": 1.0,
    "comptable": 0.9,
    "assurance": 0.8,
    "sante": 0.8,
    "hotellerie": 0.8,
    "loisir_indoor": 0.7,
    "restaurant": 0.6,
    "sport": 0.6,
    "beaute": 0.6,
    "cafe_bar": 0.5,
    "coiffeur": 0.5,
    "boulangerie": 0.5,
    "pharmacie": 0.5,
    "commerce": 0.5,
    "artisan": 0.6,
    "alimentation": 0.45,
    "autre": 0.4,
}

# Besoin de visibilité web (à quel point le métier vit de sa présence en ligne).
VISIBILITY_NEED: dict[str, float] = {
    "agent_immobilier": 1.0,
    "loisir_indoor": 1.0,
    "hotellerie": 1.0,
    "restaurant": 0.9,
    "sport": 0.85,
    "artisan": 0.85,
    "beaute": 0.8,
    "juridique": 0.7,
    "coiffeur": 0.7,
    "cafe_bar": 0.7,
    "commerce": 0.7,
    "sante": 0.6,
    "comptable": 0.6,
    "assurance": 0.6,
    "alimentation": 0.55,
    "boulangerie": 0.5,
    "pharmacie": 0.4,
    "autre": 0.5,
}

DEFAULT_VALUE = 0.4
DEFAULT_VISIBILITY = 0.5

# Présent sur agrégateur payant => dépense déjà en acquisition => plus solvable.
AGGREGATOR_BONUS = 1.2

# Seuils de température basés sur le score brut. Calibrer après premiers scans.
THRESHOLD_CHAUD = 0.6
THRESHOLD_TIEDE = 0.3


@dataclass(slots=True)
class ScoreResult:
    score: float
    temperature: Temperature
    breakdown: dict[str, float]


def compute_score(
    web_status: WebStatus,
    business_type: str,
    website: str | None = None,
) -> ScoreResult:
    status_w = STATUS_WEIGHT.get(web_status, 0.0)
    value_w = BUSINESS_VALUE.get(business_type, DEFAULT_VALUE)
    visibility_w = VISIBILITY_NEED.get(business_type, DEFAULT_VISIBILITY)
    bonus = AGGREGATOR_BONUS if is_aggregator(website) else 1.0

    score = round(status_w * value_w * visibility_w * bonus, 4)
    temperature = _resolve_temperature(web_status, score)

    return ScoreResult(
        score=score,
        temperature=temperature,
        breakdown={
            "status_weight": status_w,
            "business_value": value_w,
            "visibility_need": visibility_w,
            "aggregator_bonus": bonus,
        },
    )


def _resolve_temperature(web_status: WebStatus, score: float) -> Temperature:
    if web_status == WebStatus.UNVERIFIED:
        return Temperature.A_VERIFIER

    floor = STATUS_TEMP_FLOOR.get(web_status, Temperature.FROID)
    if floor == Temperature.A_VERIFIER:
        return Temperature.A_VERIFIER

    if score >= THRESHOLD_CHAUD:
        score_temp = Temperature.CHAUD
    elif score >= THRESHOLD_TIEDE:
        score_temp = Temperature.TIEDE
    else:
        score_temp = Temperature.FROID

    # Prendre le max entre le plancher du statut et la température du score.
    return max(floor, score_temp, key=lambda t: _TEMP_RANK[t])
