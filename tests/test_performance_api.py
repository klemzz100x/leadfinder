"""GET /api/performance (onglet Performance, VS Clément/Daniel) et le passage
de l'identité de l'auteur (`by`) sur PATCH /api/lists/{list_id}/leads/{lead_id}
— nécessaire pour attribuer un appel/devis à la bonne personne dans
`lead_events` (cf. store.patch_list_lead)."""

from fastapi.testclient import TestClient

from backend import api as api_module


def test_performance_endpoint_forwards_period(monkeypatch):
    captured = {}

    async def fake_get_performance(period):
        captured["period"] = period
        return {"period": period, "users": {}}

    monkeypatch.setattr(api_module.store, "get_performance", fake_get_performance)

    client = TestClient(api_module.app)
    resp = client.get("/api/performance", params={"period": "week"})

    assert resp.status_code == 200
    assert captured["period"] == "week"
    assert resp.json() == {"period": "week", "users": {}}


def test_performance_endpoint_defaults_to_day(monkeypatch):
    captured = {}

    async def fake_get_performance(period):
        captured["period"] = period
        return {"period": period, "users": {}}

    monkeypatch.setattr(api_module.store, "get_performance", fake_get_performance)

    client = TestClient(api_module.app)
    resp = client.get("/api/performance")

    assert resp.status_code == 200
    assert captured["period"] == "day"


def test_performance_endpoint_rejects_unknown_period(monkeypatch):
    client = TestClient(api_module.app)
    resp = client.get("/api/performance", params={"period": "year"})
    assert resp.status_code == 422


def test_patch_list_lead_forwards_actor_identity(monkeypatch):
    captured = {}

    async def fake_patch_list_lead(list_id, lead_id, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(api_module.store, "patch_list_lead", fake_patch_list_lead)

    client = TestClient(api_module.app)
    resp = client.patch(
        "/api/lists/list-1/leads/lead-1",
        json={"status": "devis_envoye", "by": "Clément"},
    )

    assert resp.status_code == 200
    assert captured["status"] == "devis_envoye"
    assert captured["by"] == "Clément"
