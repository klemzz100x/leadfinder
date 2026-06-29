"""Tests unitaires pour score.py — scoring + température + plancher de statut."""

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.classify import WebStatus
from backend.score import compute_score, Temperature, THRESHOLD_CHAUD, THRESHOLD_TIEDE


# ── Températures attendues par statut ─────────────────────────────────────────

def test_no_site_is_chaud():
    r = compute_score(WebStatus.NO_SITE, "restaurant")
    assert r.temperature == Temperature.CHAUD

def test_social_only_is_chaud():
    r = compute_score(WebStatus.SOCIAL_ONLY, "coiffeur")
    assert r.temperature == Temperature.CHAUD

def test_aggregator_is_chaud():
    r = compute_score(WebStatus.AGGREGATOR, "boulangerie")
    assert r.temperature == Temperature.CHAUD

def test_unverified_is_a_verifier():
    r = compute_score(WebStatus.UNVERIFIED, "artisan")
    assert r.temperature == Temperature.A_VERIFIER

def test_real_site_ok_is_froid():
    r = compute_score(WebStatus.REAL_SITE_OK, "restaurant")
    assert r.temperature == Temperature.FROID
    assert r.score == 0.0


# ── Plancher de température : FREE_BUILDER jamais en dessous de tiède ─────────

@pytest.mark.parametrize("business_type", [
    "coiffeur", "boulangerie", "alimentation", "autre",
])
def test_free_builder_floor_tiede(business_type):
    r = compute_score(WebStatus.FREE_BUILDER, business_type)
    assert r.temperature in (Temperature.TIEDE, Temperature.CHAUD), (
        f"FREE_BUILDER/{business_type} ne doit jamais être froid, obtenu {r.temperature}"
    )


# ── Cas à haute valeur ────────────────────────────────────────────────────────

def test_no_site_agent_immo_top_score():
    r = compute_score(WebStatus.NO_SITE, "agent_immobilier")
    assert r.score == 1.0
    assert r.temperature == Temperature.CHAUD

def test_no_site_loisir_indoor_chaud():
    r = compute_score(WebStatus.NO_SITE, "loisir_indoor")
    assert r.temperature == Temperature.CHAUD
    assert r.score >= THRESHOLD_CHAUD


# ── Bonus agrégateur ──────────────────────────────────────────────────────────

def test_aggregator_bonus_applied():
    r_with = compute_score(WebStatus.AGGREGATOR, "restaurant", "https://ubereats.com/x")
    r_without = compute_score(WebStatus.AGGREGATOR, "restaurant", None)
    assert r_with.score > r_without.score

def test_aggregator_bonus_breakdown():
    r = compute_score(WebStatus.AGGREGATOR, "restaurant", "https://ubereats.com/x")
    assert r.breakdown["aggregator_bonus"] == 1.2

def test_no_bonus_for_real_site():
    r = compute_score(WebStatus.REAL_SITE_OK, "restaurant", "https://mon-site.fr")
    assert r.breakdown["aggregator_bonus"] == 1.0


# ── Ordre de score cohérent ───────────────────────────────────────────────────

def test_no_site_beats_free_builder_same_type():
    r_no = compute_score(WebStatus.NO_SITE, "restaurant")
    r_free = compute_score(WebStatus.FREE_BUILDER, "restaurant")
    assert r_no.score > r_free.score

def test_free_builder_beats_real_site_ok_same_type():
    r_free = compute_score(WebStatus.FREE_BUILDER, "restaurant")
    r_ok = compute_score(WebStatus.REAL_SITE_OK, "restaurant")
    assert r_free.score > r_ok.score


# ── Breakdown complet ─────────────────────────────────────────────────────────

def test_breakdown_keys_present():
    r = compute_score(WebStatus.NO_SITE, "restaurant")
    assert set(r.breakdown) == {"status_weight", "business_value", "visibility_need", "aggregator_bonus"}

def test_breakdown_product_matches_score():
    r = compute_score(WebStatus.FREE_BUILDER, "artisan")
    expected = round(
        r.breakdown["status_weight"]
        * r.breakdown["business_value"]
        * r.breakdown["visibility_need"]
        * r.breakdown["aggregator_bonus"],
        4,
    )
    assert r.score == expected
