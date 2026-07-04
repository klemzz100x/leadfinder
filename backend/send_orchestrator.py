"""Chaîne bout-en-bout par lead : génération du site, devis, email — appelée
par POST /api/leads/send. Chaque lead est traité indépendamment ; un échec
sur l'un n'interrompt jamais les autres (résultat détaillé par lead, jamais
d'exception qui remonterait jusqu'à l'endpoint).

Reprend et enchaîne les modules déjà construits et testés individuellement :
places_content (photos/avis/horaires), palettes, site_copy (LLM), siret_lookup,
pricing (déjà existant), email_service — plus les scripts Node existants
(generate.mjs, deploy.mjs, devis/generate-devis.mjs) via subprocess.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from . import email_service, palettes, pricing, siret_lookup, site_copy
from .categories import load_categories, types_to_category
from .config import settings
from .places_content import get_send_content
from .store import LeadStore

log = logging.getLogger("leadfinder.send_orchestrator")

_BACKEND_DIR = Path(__file__).parent
_SITE_WEB_DIR = _BACKEND_DIR.parent / "site-web"
_SITES_DIR = _SITE_WEB_DIR / "sites-generes"
_INTERNAL_API_URL = "http://localhost:8000"

# Un seul secteur bénéficie du template réservation aujourd'hui (prise de
# RDV en ligne pertinente) ; tout le reste utilise le template généraliste —
# mapping arbitraire assumé vu qu'il n'existe que 2 templates (cf. plan).
_RESERVATION_CATEGORY = "Beauté & Bien-être"

# Résultat de génération (site déployé + devis) mis en cache par lead_id.
# Sert le flux aperçu -> confirmation de la modale d'envoi (SendPreviewModal) :
# les deux clics appellent process_lead pour les mêmes lead_ids (preview=True
# puis preview=False) ; sans ce cache, le 2e appel relance tout le pipeline et
# échoue systématiquement car generate.mjs refuse un dossier déjà existant
# (créé par le 1er appel). Le cache évite de refaire génération/build/déploiement
# coûteux : la confirmation ne fait plus que composer/envoyer l'email.
_generated_cache: dict[str, dict[str, Any]] = {}


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")


@dataclass(slots=True)
class SendResult:
    lead_id: str
    name: str
    ok: bool
    error: Optional[str] = None
    site_url: Optional[str] = None
    devis_numero: Optional[str] = None
    email: Optional[dict[str, Any]] = None


async def _run(cmd: list[str], cwd: Path, extra_env: Optional[dict[str, str]] = None) -> tuple[int, str, str]:
    import os
    import sys

    # npm est un script .cmd sur Windows, pas un exécutable direct —
    # create_subprocess_exec ne le résout pas sans l'extension explicite
    # (même contrainte documentée dans deploy.mjs côté Node, shell:true).
    # node.exe n'a pas ce problème (exécutable natif), inchangé.
    if sys.platform == "win32" and cmd and cmd[0] == "npm":
        cmd = ["npm.cmd", *cmd[1:]]

    env = {**os.environ, **(extra_env or {})}
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def _last_json_line(stdout: str) -> Optional[dict[str, Any]]:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


async def process_lead(lead_id: str, preview: bool, store: LeadStore, client: httpx.AsyncClient) -> SendResult:
    lead = await store.get_lead(lead_id)
    if not lead:
        return SendResult(lead_id, "?", ok=False, error="Lead introuvable")

    name = lead["name"]
    if not lead.get("email_client"):
        return SendResult(lead_id, name, ok=False, error="Aucun email client renseigné pour ce lead")

    address = lead.get("address") or ""
    city = lead.get("city") or ""
    business_type = lead.get("business_type") or "autre"

    categories = load_categories()
    category = types_to_category(categories).get(business_type, "Artisans & Commerce")
    template = "reservation" if category == _RESERVATION_CATEGORY else "vitrine-beaute"

    slug = _slugify(name)
    site_dir = _SITES_DIR / slug

    cached = _generated_cache.get(lead_id)
    if cached and cached["slug"] == slug:
        email_result = email_service.send_or_preview(
            to=lead["email_client"], nom_etablissement=name, site_url=cached["site_url"],
            devis_path=cached["devis_path"], devis_numero=cached["devis_numero"], preview=preview,
        )
        if email_result.sent:
            await store.mark_devis_envoye(lead_id)
            _generated_cache.pop(lead_id, None)
        return SendResult(
            lead_id, name, ok=True, site_url=cached["site_url"], devis_numero=cached["devis_numero"],
            email=asdict(email_result),
        )

    if site_dir.exists():
        return SendResult(
            lead_id, name, ok=False,
            error=f"Le site \"{slug}\" existe déjà (généré manuellement ou lors d'un envoi précédent) "
                  "— supprimez le dossier ou traitez ce lead à la main avant de renvoyer.",
        )

    # 1. Contenu riche (Google Places) — jamais bloquant si indisponible.
    content = await get_send_content(client, name, address, city) or {}
    photos: list[bytes] = content.get("photos", [])
    avis: list[dict[str, Any]] = content.get("avis", [])

    # 2. Prix suggéré (module existant, réutilisé tel quel).
    price = pricing.suggest_price(business_type, lead.get("gmaps_rating"), lead.get("gmaps_user_ratings_total"))

    # 3. Texte du site (LLM, jamais bloquant — repli générique intégré).
    copy = await site_copy.generate_copy(client, name, category, city, avis, content.get("editorial_summary"))

    # 4. SIRET (API gouvernementale, jamais bloquant — reste "à compléter" si rien de fiable).
    siret = await siret_lookup.find_siret(client, name, address)

    # 5. Génération du squelette (nom/adresse/tél/Maps déjà pré-remplis via --lead-id).
    rc, out, err = await _run(
        ["node", "generate.mjs", "--template", template, "--lead-id", lead_id, "--api-url", _INTERNAL_API_URL],
        cwd=_SITE_WEB_DIR,
    )
    if rc != 0:
        return SendResult(lead_id, name, ok=False, error=f"Échec génération du site : {err.strip() or out.strip()}")

    try:
        # 6. Photos.
        images_dir = site_dir / "public" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        photo_paths = []
        for i, photo_bytes in enumerate(photos, start=1):
            (images_dir / f"photo-{i}.jpg").write_bytes(photo_bytes)
            photo_paths.append(f"/images/photo-{i}.jpg")

        # 7. Palette par secteur.
        palettes.apply_palette(site_dir, business_type)

        # 8. Contenu riche dans site.config.json.
        config_path = site_dir / "src" / "data" / "site.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["accroche"] = copy.accroche
        config["description"] = copy.description
        config["garanties"] = copy.garanties
        config["prestations"] = [
            {"nom": p["nom"], "prix": "Sur devis", "duree": p["duree"]} for p in copy.prestations
        ]
        if content.get("horaires"):
            config["horaires"] = content["horaires"]
        if avis:
            config["avis"] = avis
            if lead.get("gmaps_rating"):
                config["avisGlobal"] = {
                    "note": lead["gmaps_rating"], "nombre": lead.get("gmaps_user_ratings_total") or 0,
                    "source": "Google",
                }
        if lead.get("page_facebook"):
            config["reseauxSociaux"]["facebook"] = lead["page_facebook"]
        if photo_paths:
            config["heroImage"] = photo_paths[0]
            config["galerie"] = [
                {"src": p, "alt": name} for p in photo_paths[1:]
            ] or config["galerie"]
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        # 9. Build.
        rc, out, err = await _run(["npm", "install"], cwd=site_dir)
        if rc != 0:
            return SendResult(lead_id, name, ok=False, error=f"npm install KO : {err.strip()[-500:]}")
        rc, out, err = await _run(["npm", "run", "build"], cwd=site_dir)
        if rc != 0:
            return SendResult(lead_id, name, ok=False, error=f"Build KO : {err.strip()[-500:]}")

        # 10. Déploiement Cloudflare Pages.
        cf_env = {
            "CLOUDFLARE_API_TOKEN": settings.CLOUDFLARE_API_TOKEN,
            "CLOUDFLARE_ACCOUNT_ID": settings.CLOUDFLARE_ACCOUNT_ID,
        }
        rc, out, err = await _run(
            ["node", "deploy.mjs", f"sites-generes/{slug}", name, "--json"], cwd=_SITE_WEB_DIR, extra_env=cf_env,
        )
        deploy_result = _last_json_line(out)
        if rc != 0 or not deploy_result:
            return SendResult(lead_id, name, ok=False, error=f"Déploiement KO : {err.strip()[-500:] or out.strip()[-500:]}")
        site_url = deploy_result["url"]

        # 11. Devis.
        devis_args = ["node", "devis/generate-devis.mjs", "--name", name, "--address", address,
                       "--total", str(price.prix), "--json"]
        if siret:
            devis_args += ["--siret", siret]
        rc, out, err = await _run(devis_args, cwd=_SITE_WEB_DIR)
        devis_result = _last_json_line(out)
        if rc != 0 or not devis_result:
            return SendResult(lead_id, name, ok=False, error=f"Devis KO : {err.strip()[-500:] or out.strip()[-500:]}")

        devis_path = Path(devis_result["fichier"])
        _generated_cache[lead_id] = {
            "slug": slug, "site_url": site_url, "devis_path": devis_path, "devis_numero": devis_result["numero"],
        }

        # 12. Email (aperçu ou envoi réel selon `preview`).
        email_result = email_service.send_or_preview(
            to=lead["email_client"], nom_etablissement=name, site_url=site_url,
            devis_path=devis_path, devis_numero=devis_result["numero"], preview=preview,
        )
        if email_result.sent:
            await store.mark_devis_envoye(lead_id)
            _generated_cache.pop(lead_id, None)

        return SendResult(
            lead_id, name, ok=True, site_url=site_url, devis_numero=devis_result["numero"],
            email=asdict(email_result),
        )
    except Exception as exc:  # noqa: BLE001 — un lead en échec ne doit jamais interrompre le lot
        log.exception("Échec inattendu pour le lead %r (%s)", name, lead_id)
        return SendResult(lead_id, name, ok=False, error=f"Erreur inattendue : {exc}")


async def process_batch(lead_ids: list[str], preview: bool, store: LeadStore) -> list[SendResult]:
    results = []
    async with httpx.AsyncClient() as client:
        for lead_id in lead_ids:
            results.append(await process_lead(lead_id, preview, store, client))
    return results
