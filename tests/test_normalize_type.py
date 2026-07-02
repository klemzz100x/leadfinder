"""Régression : OSM autorise des tags à valeurs composées séparées par ';'
(ex: amenity=restaurant;cafe) — avant ce correctif, une telle valeur non
présente telle quelle dans TYPE_MAP finissait stockée verbatim en
business_type ("restaurant;cafe"), échappant à tout regroupement en
catégorie côté filtre "type de client" (qui doit rester sous ~15 entrées)."""

from backend.sources.osm import _normalize_type


def test_compound_amenity_value_resolves_to_known_type():
    assert _normalize_type({"amenity": "restaurant;cafe"}) == "restaurant"


def test_compound_value_second_part_matches_if_first_unknown():
    assert _normalize_type({"amenity": "unknown_tag;cafe"}) == "cafe_bar"


def test_simple_known_value_unaffected():
    assert _normalize_type({"amenity": "restaurant"}) == "restaurant"


def test_unmapped_compound_value_falls_back_to_first_part_not_whole_string():
    assert _normalize_type({"amenity": "totally_unknown;also_unknown"}) == "totally_unknown"


def test_no_matching_key_falls_back_to_autre():
    assert _normalize_type({"some_other_key": "x"}) == "autre"
