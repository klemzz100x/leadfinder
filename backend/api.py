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
from pydantic import BaseModel, model_validator

from .audit import audit_url
from .categories import load_categories, save_categories
from .departements import DEPARTEMENT_CENTROIDS, DEPARTEMENTS
from .pipeline import ScanSummary, scan_city, scan_departement
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
    await store.close()


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
    city: Optional[str] = None
    departements: Optional[list[str]] = None
    scanned_by: Optional[str] = None  # identité légère (Daniel/Clément), pas une vraie auth

    @model_validator(mode="after")
    def _at_least_one(self) -> "ScanRequest":
        if not (self.city and self.city.strip()) and not self.departements:
            raise ValueError("Renseignez une ville ou au moins un département")
        return self


class PatchLeadRequest(BaseModel):
    called: Optional[bool] = None
    outcome: Optional[str] = None
    notes: Optional[str] = None


class CategoryDef(BaseModel):
    types: list[str]
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    objectif_closes_mensuel: Optional[int] = None


class CategoriesRequest(BaseModel):
    categories: dict[str, CategoryDef]


class CreateListRequest(BaseModel):
    name: str


class AddLeadsRequest(BaseModel):
    lead_ids: list[str]


class PatchListLeadRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    budget_propose: Optional[float] = None
    budget_final: Optional[float] = None
    assigned_to: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/scan")
async def scan(req: ScanRequest) -> list[ScanSummary]:
    """Lance la découverte des business pour une ville, ou pour un ou plusieurs
    départements entiers, et renvoie un résumé par zone scannée.

    Si `city` est renseignée, elle prime (comportement historique inchangé) —
    les départements éventuellement sélectionnés ne servent alors qu'à filtrer
    l'affichage ensuite, pas à élargir le scan. Sans ville, chaque département
    de `departements` est scanné en entier (toutes ses communes, pas que son
    chef-lieu), séquentiellement."""
    city = (req.city or "").strip()
    if city:
        log.info("Requête de scan reçue : ville=%r (par %r)", city, req.scanned_by)
        try:
            summary = await scan_city(city, store, http_client=_http)
        except Exception:
            log.exception("Scan ville %r KO", city)
            raise
        await store.record_scan("ville", city.lower(), city, req.scanned_by, summary.total, summary.api_calls)
        return [summary]

    log.info("Requête de scan reçue : départements=%s (par %r)", req.departements, req.scanned_by)
    summaries: list[ScanSummary] = []
    for code in req.departements or []:
        log.info("Scan département %r : démarrage", code)
        try:
            summary = await scan_departement(code, store, http_client=_http)
            summaries.append(summary)
            log.info("Scan département %r : terminé — %d business, %d appels API",
                      code, summary.total, summary.api_calls)
            dept_name = DEPARTEMENTS.get(code, code)
            await store.record_scan("departement", code, dept_name, req.scanned_by, summary.total, summary.api_calls)
        except Exception:
            # Traceback complet en log (pas juste le message) : un département KO
            # ne doit jamais faire échouer les suivants du lot.
            log.exception("Scan département %r KO", code)
    log.info("Scan par lot terminé : %d/%d départements réussis", len(summaries), len(req.departements or []))
    return summaries


@app.get("/api/leads")
async def get_leads(
    city: Optional[str] = Query(None),
    temperature: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    show_equipped: bool = Query(False),
    show_closed: bool = Query(False),
    departements: Optional[list[str]] = Query(None),
) -> list[dict]:
    """Liste des leads triée par score décroissant, avec filtres optionnels."""
    return await store.get_leads(
        city=city, temperature=temperature, business_type=type,
        show_equipped=show_equipped, show_closed=show_closed,
        departements=departements,
    )


@app.get("/api/leads/meta")
async def leads_meta(city: Optional[str] = Query(None)) -> dict:
    """Villes et types distincts pour alimenter les filtres UI."""
    return {
        "cities": await store.distinct_cities(),
        "types": await store.distinct_types(city=city),
    }


@app.get("/api/departements")
async def get_departements() -> list[dict]:
    """Liste officielle complète des départements (France métropolitaine),
    indépendante des scans déjà effectués — le sélecteur de filtre doit
    proposer les 95 départements dès l'arrivée sur la page, pas seulement
    ceux déjà présents en base. Inclut la couverture de scan connue (base
    partagée entre plusieurs utilisateurs : évite un re-scan à l'aveugle
    d'un département déjà couvert par quelqu'un d'autre)."""
    coverage = await store.get_departement_coverage()
    out = []
    for code, name in sorted(DEPARTEMENTS.items()):
        cov = coverage.get(code)
        out.append({
            "code": code,
            "name": name,
            "last_scanned_at": cov["scanned_at"] if cov else None,
            "last_scanned_by": cov["scanned_by"] if cov else None,
            "last_scan_total": cov["total_found"] if cov else None,
        })
    return out


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


@app.get("/api/departements/{code}/estimate")
async def departement_estimate(code: str) -> dict:
    """Estimation gratuite (API Geo gouv.fr, pas d'appel Overpass) du volume
    d'un scan département avant de le lancer — nombre de communes et
    population cumulée, pour piloter soi-même l'ordre et le rythme de
    couverture plutôt que de tout scanner d'un coup."""
    name = DEPARTEMENTS.get(code)
    if not name:
        raise HTTPException(404, f"Département inconnu : {code!r}")
    communes: list[dict] = []
    try:
        resp = await _http.get(
            f"https://geo.api.gouv.fr/departements/{code}/communes",
            params={"fields": "nom,population"},
        )
        if resp.status_code == 200:
            communes = resp.json()
    except Exception as exc:
        log.warning("Geo API estimate KO pour %r : %s", code, exc)
    population = sum(c.get("population") or 0 for c in communes)
    return {"code": code, "name": name, "communes": len(communes), "population": population}


@app.get("/api/lists")
async def get_lists() -> list[dict]:
    return await store.get_lists()


@app.post("/api/lists")
async def create_list(req: CreateListRequest) -> dict:
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Nom de liste vide")
    return await store.create_list(name)


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str) -> dict:
    if not await store.delete_list(list_id):
        raise HTTPException(404, f"Liste {list_id!r} introuvable")
    return {"ok": True}


@app.get("/api/lists/{list_id}/stats")
async def get_list_stats(list_id: str) -> dict:
    return await store.get_list_stats(list_id)


@app.get("/api/lists/{list_id}/leads")
async def get_list_leads(list_id: str) -> list[dict]:
    return await store.get_list_leads(list_id)


@app.post("/api/lists/{list_id}/leads")
async def add_leads_to_list(list_id: str, req: AddLeadsRequest) -> dict:
    """Ajoute des leads à une liste. Les doublons (même nom+adresse déjà dans
    cette liste, id technique différent) sont écartés et renvoyés dans `skipped`."""
    result = await store.add_leads_to_list(list_id, req.lead_ids)
    return {"ok": True, "added": result["added"], "skipped": result["skipped"]}


@app.delete("/api/lists/{list_id}/leads/{lead_id:path}")
async def remove_lead_from_list(list_id: str, lead_id: str) -> dict:
    if not await store.remove_lead_from_list(list_id, lead_id):
        raise HTTPException(404, "Lead non trouvé dans cette liste")
    return {"ok": True}


@app.patch("/api/lists/{list_id}/leads/{lead_id:path}")
async def patch_list_lead(list_id: str, lead_id: str, data: PatchListLeadRequest) -> dict:
    updated = await store.patch_list_lead(
        list_id, lead_id, status=data.status, notes=data.notes,
        budget_propose=data.budget_propose, budget_final=data.budget_final,
        assigned_to=data.assigned_to,
    )
    if not updated:
        raise HTTPException(404, "Lead non trouvé dans cette liste")
    return {"ok": True}


@app.get("/api/dashboard")
async def get_dashboard(month: Optional[str] = Query(None, description="YYYY-MM, défaut mois courant")) -> dict:
    """Dashboard commercial agrégé (tous les prospect_lists confondus) : closes du
    mois, CA réel vs objectif par catégorie, classement, streak."""
    return await store.get_dashboard_stats(month=month)


@app.get("/api/categories")
async def get_categories() -> dict[str, dict]:
    """Retourne les catégories métier actuelles (types + budget cible éditable)."""
    return load_categories()


@app.put("/api/categories")
async def put_categories(req: CategoriesRequest) -> dict:
    """Sauvegarde les catégories métier dans categories.json."""
    save_categories({name: c.model_dump() for name, c in req.categories.items()})
    return {"ok": True}


@app.get("/api/stats/departements")
async def stats_departements(activite: Optional[str] = Query(None)) -> list[dict]:
    """Concentration de leads chauds par département, pour une catégorie d'activité
    donnée (nom de catégorie tel que défini dans categories.json). Sans `activite`,
    agrège tous les business_type confondus."""
    business_types: Optional[list[str]] = None
    if activite:
        cat = load_categories().get(activite)
        business_types = cat["types"] if cat else []

    rows = await store.stats_by_departement(business_types=business_types)
    out = []
    for r in rows:
        code = r["departement"]
        centroid = DEPARTEMENT_CENTROIDS.get(code)
        if not centroid:
            continue
        out.append({
            "code": code,
            "name": DEPARTEMENTS.get(code, code),
            "lat": centroid[0],
            "lng": centroid[1],
            "chauds": r["chauds"],
            "total": r["total"],
        })
    out.sort(key=lambda d: d["chauds"], reverse=True)
    return out


@app.get("/api/stats/villes")
async def stats_villes(
    activite: Optional[str] = Query(None),
    departements: Optional[list[str]] = Query(None),
) -> list[dict]:
    """Concentration de leads chauds par ville (niveau 1 du drill-down carte).
    Sans `activite`, agrège tous les business_type confondus. `departements`
    restreint l'affichage à une sélection de départements, indépendamment de
    l'historique des recherches par ville (un scan département alimente les
    mêmes données, cf. /api/scan)."""
    business_types: Optional[list[str]] = None
    if activite:
        cat = load_categories().get(activite)
        business_types = cat["types"] if cat else []
    rows = await store.stats_by_ville(business_types=business_types, departement_codes=departements)
    rows.sort(key=lambda r: r["chauds"], reverse=True)
    return rows


@app.get("/api/leads/geo")
async def leads_geo(
    south: float = Query(...), west: float = Query(...),
    north: float = Query(...), east: float = Query(...),
    activite: Optional[str] = Query(None),
    limit: int = Query(300, le=500),
) -> list[dict]:
    """Leads chauds précis dans un viewport carte (niveau 2 du drill-down),
    bornés au rectangle visible pour ne jamais charger tous les leads de France."""
    business_types: Optional[list[str]] = None
    if activite:
        cat = load_categories().get(activite)
        business_types = cat["types"] if cat else []
    return await store.get_leads_in_bounds(
        south=south, west=west, north=north, east=east,
        business_types=business_types, limit=limit,
    )


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
