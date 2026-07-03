"""Prix de devis suggéré (backend/pricing.py) : vérifie que le score reste
toujours DANS la fourchette budget_min/budget_max de la catégorie du lead
(jamais en dehors, quel que soit le signal), et que l'absence de données
Google (jamais vérifié) ne pénalise pas un lead par rapport à un score neutre."""

from backend.pricing import suggest_price


def test_price_stays_within_category_range_best_case():
    # "coiffeur" -> Beauté & Bien-être, 500-750€. Meilleur cas possible :
    # note et volume d'avis au maximum.
    result = suggest_price("coiffeur", gmaps_rating=5.0, gmaps_user_ratings_total=500)
    assert 500 <= result.prix <= 750
    assert result.prix > 700  # score élevé -> proche du haut de la fourchette


def test_price_stays_within_category_range_worst_case():
    # Pire cas : note basse, aucun avis (vérifié, vraiment 0).
    result = suggest_price("coiffeur", gmaps_rating=1.0, gmaps_user_ratings_total=0)
    assert 500 <= result.prix <= 750
    assert result.prix < 600  # score faible -> proche du bas de la fourchette


def test_price_never_leaves_high_budget_category_range():
    # "restaurant" -> Restauration, 850-1150€ (élargi ±15% autour de l'ancien
    # prix fixe 1000€) — jamais sous 850 ni au-dessus de 1150.
    for rating, reviews in [(None, None), (5.0, 1000), (1.0, 0), (3.5, 40)]:
        result = suggest_price("restaurant", gmaps_rating=rating, gmaps_user_ratings_total=reviews)
        assert 850 <= result.prix <= 1150


def test_missing_google_data_is_neutral_not_penalizing():
    # Jamais vérifié côté Google (rating/avis = None) -> score neutre sur ces
    # deux composantes, pas un score plancher comme si l'établissement avait
    # une mauvaise note ou aucun avis.
    unverified = suggest_price("coiffeur", gmaps_rating=None, gmaps_user_ratings_total=None)
    zero_reviews = suggest_price("coiffeur", gmaps_rating=1.0, gmaps_user_ratings_total=0)
    assert unverified.prix > zero_reviews.prix


def test_unknown_category_falls_back_to_generic_range_not_invented_amount():
    result = suggest_price("type_totalement_inconnu", gmaps_rating=4.5, gmaps_user_ratings_total=50)
    assert 500 <= result.prix <= 750


def test_justification_mentions_review_count_when_available():
    result = suggest_price("coiffeur", gmaps_rating=4.6, gmaps_user_ratings_total=45)
    assert "45 avis" in result.justification
    assert "4.6" in result.justification
