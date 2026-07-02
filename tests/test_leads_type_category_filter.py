"""GET /api/leads?type=... reçoit désormais un nom de catégorie (le filtre
"type de client" ne doit jamais dépasser une quinzaine d'entrées, cf.
/api/leads/meta qui groupe les dizaines de business_type bruts en quelques
catégories). Vérifie que l'endpoint résout correctement une catégorie connue,
le cas spécial "Autres" (pas une vraie clé de categories.json, mais "tout ce
qui n'est couvert par aucune catégorie"), et le repli en valeur brute pour
compat descendante (ancien lien/favori)."""

from fastapi.testclient import TestClient

from backend import api as api_module


def test_leads_filtered_by_known_category_resolves_to_its_types(monkeypatch):
    captured = {}

    async def fake_get_leads(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(api_module.store, "get_leads", fake_get_leads)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads", params={"type": "Restauration"})

    assert resp.status_code == 200
    assert captured["business_types"] == ["restaurant", "cafe_bar", "boulangerie", "alimentation"]
    assert captured["business_type"] is None
    assert captured["exclude_business_types"] is None


def test_leads_filtered_by_autres_excludes_all_known_category_types(monkeypatch):
    captured = {}

    async def fake_get_leads(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(api_module.store, "get_leads", fake_get_leads)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads", params={"type": "Autres"})

    assert resp.status_code == 200
    assert captured["business_types"] is None
    assert captured["business_type"] is None
    # "restaurant" (catégorie Restauration) fait partie des types connus à exclure.
    assert "restaurant" in captured["exclude_business_types"]
    assert "fast_food" in captured["exclude_business_types"]


def test_leads_filtered_by_unknown_raw_value_falls_back_to_exact_match(monkeypatch):
    captured = {}

    async def fake_get_leads(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(api_module.store, "get_leads", fake_get_leads)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads", params={"type": "un_ancien_lien_favori"})

    assert resp.status_code == 200
    assert captured["business_type"] == "un_ancien_lien_favori"
    assert captured["business_types"] is None
    assert captured["exclude_business_types"] is None
