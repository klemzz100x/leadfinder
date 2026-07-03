"""Régression : GET /api/leads/{lead_id:path} (ajouté pour le générateur de
sites vitrine) est un attrape-tout — s'il était enregistré avant les routes
GET /api/leads/... plus spécifiques (meta, geo), il les masquerait (FastAPI
matche dans l'ordre d'enregistrement). Les méthodes du store sont mockées
pour que chaque handler réussisse proprement (sans DB réelle) et reste
distinguable par son contenu de réponse — sinon les deux échoueraient de la
même façon (pool absent) et le test ne détecterait pas un mauvais routage."""

from fastapi.testclient import TestClient

from backend import api as api_module


def test_leads_geo_route_not_shadowed_by_lead_id_catchall(monkeypatch):
    async def fake_get_leads_in_bounds(**kwargs):
        return [{"marker": "geo-endpoint-hit"}]

    async def fake_get_lead(lead_id):
        return None  # simule "introuvable" si jamais get_lead était atteint à tort

    monkeypatch.setattr(api_module.store, "get_leads_in_bounds", fake_get_leads_in_bounds)
    monkeypatch.setattr(api_module.store, "get_lead", fake_get_lead)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads/geo", params={"south": 0, "west": 0, "north": 1, "east": 1})

    assert resp.status_code == 200
    # Pas d'égalité exacte : /api/leads/geo enrichit chaque lead avec
    # devis_suggere (backend/pricing.py) avant de le renvoyer, seul le
    # marqueur importe ici pour prouver que le bon handler a été atteint.
    body = resp.json()
    assert len(body) == 1
    assert body[0]["marker"] == "geo-endpoint-hit"


def test_leads_meta_route_not_shadowed_by_lead_id_catchall(monkeypatch):
    async def fake_distinct_cities():
        return ["VilleTest"]

    # "restaurant" est un business_type brut connu, groupé sous la catégorie
    # "Restauration" (categories.py) ; "type_totalement_inconnu" ne
    # correspond à aucune catégorie et doit retomber sur "Autres" — le
    # filtre "type de client" ne doit jamais réafficher des valeurs brutes.
    async def fake_distinct_types(city=None):
        return ["restaurant", "type_totalement_inconnu"]

    async def fake_get_lead(lead_id):
        return None

    monkeypatch.setattr(api_module.store, "distinct_cities", fake_distinct_cities)
    monkeypatch.setattr(api_module.store, "distinct_types", fake_distinct_types)
    monkeypatch.setattr(api_module.store, "get_lead", fake_get_lead)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads/meta")

    assert resp.status_code == 200
    assert resp.json() == {"cities": ["VilleTest"], "types": ["Autres", "Restauration"]}


def test_get_lead_by_id_still_reachable(monkeypatch):
    async def fake_get_lead(lead_id):
        assert lead_id == "node:123456"
        return {"id": "node:123456", "name": "Business Test"}

    monkeypatch.setattr(api_module.store, "get_lead", fake_get_lead)

    client = TestClient(api_module.app)
    resp = client.get("/api/leads/node:123456")

    assert resp.status_code == 200
    assert resp.json()["name"] == "Business Test"


def test_get_rappels_returns_store_data(monkeypatch):
    async def fake_get_rappels():
        return [{"id": "node:1", "name": "Salon Test", "list_id": "abc", "list_name": "Liste Test"}]

    monkeypatch.setattr(api_module.store, "get_rappels", fake_get_rappels)

    client = TestClient(api_module.app)
    resp = client.get("/api/rappels")

    assert resp.status_code == 200
    assert resp.json() == [{"id": "node:1", "name": "Salon Test", "list_id": "abc", "list_name": "Liste Test"}]
