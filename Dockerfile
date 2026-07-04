FROM python:3.11-slim

# Node.js 20 LTS pour builder le frontend
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dépendances Python ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Build frontend ---
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# --- site-web (génération de sites + devis, Phase 8) ---
# wrangler (déploiement Cloudflare Pages) et playwright (rendu PDF des
# devis) partagent le même package.json à la racine de site-web/.
COPY site-web/package*.json ./site-web/
RUN cd site-web && npm ci
# --with-deps installe aussi les libs système nécessaires à Chromium
# (nécessite root, déjà le cas dans cette image) — ajoute plusieurs
# centaines de Mo à l'image, cf. plan pour le compromis assumé.
RUN cd site-web && npx playwright install --with-deps chromium
COPY site-web/generate.mjs site-web/deploy.mjs ./site-web/
COPY site-web/templates/ ./site-web/templates/
COPY site-web/devis/ ./site-web/devis/

# --- Backend ---
COPY backend/ ./backend/
COPY .env.example .env.example

# DATABASE_URL (Postgres Neon) est injecté via les variables d'environnement Render.
#
# ATTENTION — limite connue : le système de fichiers de Render (tier gratuit)
# est éphémère (repart de zéro à chaque redéploiement/redémarrage). Deux
# conséquences pour la Phase 8 :
#   1. La numérotation des devis (site-web/devis/generate-devis.mjs, calculée
#      en scannant les fichiers déjà générés) peut se réinitialiser après un
#      redémarrage et entrer en collision avec un numéro déjà envoyé à un
#      vrai client. Pas dangereux (juste un numéro de référence, pas un ID
#      légal), mais pas propre — à corriger plus tard en stockant le dernier
#      numéro utilisé dans Postgres plutôt qu'en scannant le disque local.
#   2. La vérification "ce site existe-t-il déjà ?" dans send_orchestrator.py
#      (qui protège un site généré/personnalisé à la main d'un écrasement)
#      se base sur ce même disque éphémère — après un redémarrage, elle ne
#      détecterait plus un site pourtant déjà déployé sur Cloudflare Pages.
#      Sans conséquence pour un envoi ponctuel supervisé (le workflow prévu
#      pour l'instant), à surveiller si le volume d'envois augmente.

EXPOSE 8000
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
