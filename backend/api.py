"""API FastAPI — endpoints Phase 0.

Lancer :  uvicorn backend.api:app --reload   (depuis leadfinder/)
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .audit import audit_url
from .categories import load_categories, save_categories
from .pipeline import ScanSummary, scan_city
from .sources.osm import USER_AGENT
from .store import LeadStore

log = logging.getLogger("leadfinder.api")

store = LeadStore()
_http: httpx.AsyncClient  # initialisé dans lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _http = httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(8.0),
    )
    await store.init()
    yield
    await _http.aclose()


app = FastAPI(title="LeadFinder", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ── Modèles de requête ─────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    city: str


class PatchLeadRequest(BaseModel):
    called: Optional[bool] = None
    outcome: Optional[str] = None
    notes: Optional[str] = None


class CategoriesRequest(BaseModel):
    categories: dict[str, list[str]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/scan", response_model=ScanSummary)
async def scan(req: ScanRequest) -> ScanSummary:
    """Lance la découverte des business pour une ville et renvoie le résumé."""
    city = req.city.strip()
    if not city:
        raise HTTPException(400, "Paramètre 'city' vide")
    return await scan_city(city, store)


@app.get("/api/leads")
async def get_leads(
    city: Optional[str] = Query(None),
    temperature: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
) -> list[dict]:
    """Liste des leads triée par score décroissant, avec filtres optionnels."""
    return await store.get_leads(city=city, temperature=temperature, business_type=type)


@app.get("/api/leads/meta")
async def leads_meta(city: Optional[str] = Query(None)) -> dict:
    """Villes et types distincts pour alimenter les filtres UI."""
    return {
        "cities": await store.distinct_cities(),
        "types": await store.distinct_types(city=city),
    }


@app.post("/api/leads/{lead_id:path}/audit")
async def audit_lead(lead_id: str) -> dict:
    """Lance l'audit d'un site (complet en Phase 1 ; stub en Phase 0)."""
    lead = await store.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, f"Lead {lead_id!r} introuvable")
    if not lead.get("website"):
        raise HTTPException(400, "Ce lead n'a pas de site connu à auditer")

    result = await audit_url(lead["website"])
    audit_json = json.dumps(
        {
            "url": result.url,
            "weak_points": result.weak_points,
            "score_perf": result.score_perf,
            "is_https": result.is_https,
            "is_responsive": result.is_responsive,
            "response_ms": result.response_ms,
            "cms_detected": result.cms_detected,
            "error": result.error,
        }
    )
    await store.update_lead(lead_id, audit_json=audit_json)
    return json.loads(audit_json)


@app.patch("/api/leads/{lead_id:path}")
async def patch_lead(lead_id: str, data: PatchLeadRequest) -> dict:
    """Mise à jour du suivi appel (appelé / résultat / notes)."""
    updated = await store.update_lead(
        lead_id,
        called=data.called,
        outcome=data.outcome,
        notes=data.notes,
    )
    if not updated:
        raise HTTPException(404, f"Lead {lead_id!r} introuvable")
    return {"ok": True}


@app.get("/api/export")
async def export_csv(city: Optional[str] = Query(None)) -> StreamingResponse:
    """Export CSV de tous les leads (ou d'une ville)."""
    csv_content = await store.export_csv(city=city)
    filename = f"leads_{city or 'all'}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/cities/suggest")
async def suggest_cities(q: str = Query(..., min_length=2)) -> list[dict]:
    """Suggestions de villes françaises — API Geo gouv.fr (gratuit, sans compte, sans rate-limit).

    Retourne les communes françaises triées par population décroissante.
    """
    try:
        resp = await _http.get(
            "https://geo.api.gouv.fr/communes",
            params={
                "nom": q,
                "fields": "nom,departement,population",
                "boost": "population",
                "limit": 8,
                "type": "commune-actuelle",
            },
        )
        if resp.status_code != 200:
            return []
        results = resp.json()
    except Exception as exc:
        log.warning("Geo API suggest KO : %s", exc)
        return []

    out: list[dict] = []
    for r in results:
        name = r.get("nom", "").strip()
        if not name:
            continue
        dept = r.get("departement", {})
        detail = f"{dept.get('nom', '')} ({dept.get('code', '')})" if dept else ""
        out.append({"name": name, "detail": detail, "place_id": None})
    return out


@app.get("/api/categories")
async def get_categories() -> dict[str, list[str]]:
    """Retourne les catégories métier actuelles."""
    return load_categories()


@app.put("/api/categories")
async def put_categories(req: CategoriesRequest) -> dict:
    """Sauvegarde les catégories métier dans categories.json."""
    save_categories(req.categories)
    return {"ok": True}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ── Serving du frontend React (si le build existe) ────────────────────────────
# En local : le frontend est servi par Vite (npm run dev) sur le port 5173.
# En production (Render) : FastAPI sert le build Vite directement.

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Assets compilés (JS, CSS) servis directement sous /assets/
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Catch-all : renvoie index.html pour toute route non-API (SPA routing)."""
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
