"""Régression : un scan département (grosse bbox) qui timeout sur Overpass
doit se rabattre sur une subdivision en sous-cellules plutôt que d'abandonner
toute la zone — reproduit un 504 Gateway Timeout observé en production sur
un scan département (l'Ain)."""

import pytest

from backend.sources.osm import OSMSource


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
