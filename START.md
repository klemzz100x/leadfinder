# Démarrer LeadFinder

## Prérequis
- Python 3.10+ (`python --version`)
- Node.js 18+ (`node --version`)

## 1. Backend (FastAPI)

```bash
# Depuis le dossier leadfinder/
pip install -r requirements.txt
uvicorn backend.api:app --reload
# -> http://localhost:8000
```

## 2. Frontend (React + Vite)

```bash
# Dans un autre terminal, depuis leadfinder/frontend/
npm install
npm run dev
# -> http://localhost:5173
```

## 3. Utilisation

1. Ouvrir http://localhost:5173
2. Saisir une ville (ex : **Bordeaux**)
3. Cliquer **Scanner** — la découverte OSM peut prendre 20-60s selon la ville
4. Les leads s'affichent triés par score ; cliquer le téléphone pour appeler

## Tests

```bash
# Depuis leadfinder/
python -m pytest tests/ -v
```

## Variables d'environnement (toutes optionnelles)

Copier `.env.example` en `.env` et renseigner si souhaité.
Sans aucune clé, le projet fonctionne à 100% via OSM (0 €).
