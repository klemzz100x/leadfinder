"""Régression : un scan département (grosse bbox) qui timeout sur Overpass
doit se rabattre sur une subdivision en sous-cellules plutôt que d'abandonner
toute la zone — reproduit un 504 Gateway Timeout observé en production sur
un scan département (l'Ain)."""

import time

import pytest

from backend.sources.osm import OSMSource, OVERPASS_MIN_INTERVAL


@pytest.mark.asyncio
async def test_fetch_bbox_recursive_subdivides_on_overpass_failure():
    source = OSMSource()
    calls: list[str] = []

    async def fake_overpass_call(query):
        calls.append(query)
        if len(calls) == 1:
            # Bbox pleine : timeout/échec Overpass (ex. 504).
            return None
        # Les 4 sous-cellules réussissent, chacune avec un élément distinct.
        return {"elements": [{"type": "node", "id": len(calls), "tags": {"name": f"biz{len(calls)}"}}]}

    source._overpass_call = fake_overpass_call
    try:
        elements = await source._fetch_bbox_recursive((0.0, 0.0, 1.0, 1.0), depth=0, max_depth=3)
    finally:
        await source.aclose()

    assert len(calls) == 5  # 1 échec initial + 4 sous-cellules
    assert len(elements) == 4


@pytest.mark.asyncio
async def test_fetch_bbox_recursive_gives_up_at_max_depth():
    """Si Overpass échoue systématiquement, on abandonne à la profondeur max
    plutôt que de subdiviser indéfiniment."""
    source = OSMSource()
    calls: list[str] = []

    async def always_fail(query):
        calls.append(query)
        return None

    source._overpass_call = always_fail
    try:
        elements = await source._fetch_bbox_recursive((0.0, 0.0, 1.0, 1.0), depth=0, max_depth=2)
    finally:
        await source.aclose()

    assert elements == []
    # 1 (depth 0) + 4 (depth 1) + 16 (depth 2, max atteint) = 21 tentatives, bornées.
    assert len(calls) == 1 + 4 + 16


@pytest.mark.asyncio
async def test_fetch_bbox_recursive_still_splits_on_truncated_response():
    """Non-régression : le cas historique (réponse valide mais tronquée,
    >=8000 éléments) continue de déclencher une subdivision."""
    source = OSMSource()
    calls: list[str] = []

    async def fake_overpass_call(query):
        calls.append(query)
        if len(calls) == 1:
            return {"elements": [{"type": "node", "id": i, "tags": {}} for i in range(8000)]}
        return {"elements": [{"type": "node", "id": 100 + len(calls), "tags": {}}]}

    source._overpass_call = fake_overpass_call
    try:
        elements = await source._fetch_bbox_recursive((0.0, 0.0, 1.0, 1.0), depth=0, max_depth=3)
    finally:
        await source.aclose()

    assert len(calls) == 5
    assert len(elements) == 4


@pytest.mark.asyncio
async def test_overpass_call_paced_between_consecutive_calls():
    """Régression : observé en prod, des appels Overpass rapprochés (bbox
    pleine + sous-cellules) se faisaient rate-limiter (429) faute de cadence
    minimale — Nominatim était throttlé à 1 req/s mais pas Overpass."""
    source = OSMSource()

    async def fake_request_with_retry(method, url, **kwargs):
        class FakeResp:
            status_code = 200
            def json(self):
                return {"elements": []}
        return FakeResp()

    source._request_with_retry = fake_request_with_retry
    try:
        t0 = time.monotonic()
        await source._overpass_call("query1")
        await source._overpass_call("query2")
        elapsed = time.monotonic() - t0
    finally:
        await source.aclose()

    assert elapsed >= OVERPASS_MIN_INTERVAL - 0.05


@pytest.mark.asyncio
async def test_overpass_call_uses_patient_retry_budget():
    """Un 429 mérite un backoff plus patient (4 tentatives) qu'un abandon
    rapide — le budget de retry ne doit pas être réduit à 2 sur Overpass."""
    source = OSMSource()
    captured = {}

    async def fake_request_with_retry(method, url, **kwargs):
        captured["max_retries"] = kwargs.get("max_retries")
        return None

    source._request_with_retry = fake_request_with_retry
    try:
        await source._overpass_call("query")
    finally:
        await source.aclose()

    assert captured["max_retries"] == 4
