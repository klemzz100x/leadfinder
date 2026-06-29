"""Tests unitaires pour classify.py — les 7 statuts + cas limites."""

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.classify import classify, WebStatus


# ── Cas centraux ──────────────────────────────────────────────────────────────

def test_no_site_when_tag_present():
    c = classify(None, has_website_tag=True)
    assert c.status == WebStatus.NO_SITE

def test_unverified_when_no_tag():
    c = classify(None, has_website_tag=False)
    assert c.status == WebStatus.UNVERIFIED

def test_empty_string_with_tag_is_no_site():
    c = classify("", has_website_tag=True)
    assert c.status == WebStatus.NO_SITE

def test_empty_string_without_tag_is_unverified():
    c = classify("", has_website_tag=False)
    assert c.status == WebStatus.UNVERIFIED


# ── SOCIAL_ONLY ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.facebook.com/mon-resto",
    "https://m.facebook.com/page/123",
    "http://instagram.com/coiffeur.dupont",
    "https://www.instagram.com/salon_de_beaute/",
    "https://linktr.ee/le-bistrot",
    "https://beacons.ai/artisan",
    "https://www.tiktok.com/@shop",
])
def test_social_only(url):
    c = classify(url)
    assert c.status == WebStatus.SOCIAL_ONLY, f"Attendu SOCIAL_ONLY pour {url}, obtenu {c.status}"


# ── AGGREGATOR ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.ubereats.com/fr/store/le-resto",
    "https://deliveroo.fr/menu/bordeaux/restaurant-x",
    "https://www.just-eat.fr/restaurant/xxx",
    "https://www.thefork.fr/restaurant/xxx",
    "https://www.lafourchette.com/restaurant/yyy",
    "https://www.tripadvisor.fr/Restaurant_Review-g123",
    "https://www.pagesjaunes.fr/pros/xxx",
    "https://doctolib.fr/medecin/paris/nom",
])
def test_aggregator(url):
    c = classify(url)
    assert c.status == WebStatus.AGGREGATOR, f"Attendu AGGREGATOR pour {url}, obtenu {c.status}"


# ── FREE_BUILDER ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://le-resto.wixsite.com/restaurant",
    "https://coiffeur-dupont.business.site",
    "https://mon-salon.e-monsite.com",
    "https://resto.godaddysites.com",
    "http://artisan.eatbu.com",
    "https://plombier.jimdo.com",
    "https://yoga.sitew.com",
    "https://boulangerie.wordpress.com",
])
def test_free_builder(url):
    c = classify(url)
    assert c.status == WebStatus.FREE_BUILDER, f"Attendu FREE_BUILDER pour {url}, obtenu {c.status}"


# ── REAL_SITE_OK ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.restaurant-le-bistrot.fr",
    "https://cabinet-dupont-avocat.com",
    "http://hotel-des-arenes.fr",
    "https://plombier-martin-bordeaux.fr",
    "cabinet-dupont.fr",            # sans schéma -> quand même parsé comme vrai domaine
])
def test_real_site_ok(url):
    c = classify(url)
    assert c.status == WebStatus.REAL_SITE_OK, f"Attendu REAL_SITE_OK pour {url}, obtenu {c.status}"


# ── Sous-domaines ─────────────────────────────────────────────────────────────

def test_facebook_subdomain_is_social():
    c = classify("https://fr-fr.facebook.com/pagename")
    assert c.status == WebStatus.SOCIAL_ONLY

def test_wixsite_subdomain_is_free_builder():
    c = classify("https://my-cafe.wixsite.com/home")
    assert c.status == WebStatus.FREE_BUILDER


# ── Informations sur le match ─────────────────────────────────────────────────

def test_matched_domain_populated():
    c = classify("https://facebook.com/test")
    assert c.matched_domain is not None
    assert "facebook" in c.matched_domain

def test_reason_populated():
    c = classify(None, has_website_tag=False)
    assert len(c.reason) > 0
