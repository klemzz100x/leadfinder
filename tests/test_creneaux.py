"""Créneaux d'appel indicatifs par famille : vérifie le mapping business_type
-> créneau, et surtout qu'un business_type non couvert par aucune famille
(ex: 'sante', 'autre') ne reçoit jamais de créneau par défaut inventé —
consigne explicite du prompt (champ vide plutôt qu'une valeur arbitraire)."""

from backend.creneaux import DEFAULT_FAMILLES, types_to_creneau


def test_known_type_resolves_to_its_famille_creneau():
    mapping = types_to_creneau(DEFAULT_FAMILLES)
    assert mapping["restaurant"] == "15h–18h"
    assert mapping["coiffeur"] == "9h30–11h"
    assert mapping["agent_immobilier"] == "10h–12h ou 14h–17h"


def test_unmapped_type_has_no_creneau():
    mapping = types_to_creneau(DEFAULT_FAMILLES)
    assert "sante" not in mapping
    assert "pharmacie" not in mapping
    assert "autre" not in mapping


def test_famille_with_empty_types_contributes_nothing():
    # "Services aux particuliers" et "Automobile" ont une liste `types` vide
    # par défaut (aucun business_type OSM connu n'y correspond encore) —
    # ne doivent jamais faire planter le mapping ni y injecter de clé factice.
    mapping = types_to_creneau(DEFAULT_FAMILLES)
    assert all(v for v in mapping.values())
