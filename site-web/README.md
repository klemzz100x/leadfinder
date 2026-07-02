# Système de templates de sites web (livraison rapide clients closés)

Génère un site vitrine prêt à déployer pour un lead closé, en quelques minutes.

## Stack

**Astro + Tailwind CSS**, pas Next.js — les sites générés sont très majoritairement
statiques (texte/photos/avis) ; Astro ne ships quasiment aucun JS par défaut,
ce qui donne des sites plus légers/rapides par client généré qu'une appli
Next.js complète, tout en gardant la possibilité d'îlots interactifs ciblés
(widget de réservation) sans le poids de React partout. Déploiement Vercel
tout aussi instantané dans les deux cas.

## Structure

```
site-web/
  templates/          gabarits sources, jamais modifiés directement pour un client
    vitrine-beaute/    site vitrine simple (institut, coiffeur, bar à ongles...)
    reservation/       vitrine + réservation Cal.com + biens immobiliers (activable)
  sites-generes/       un dossier par client livré (généré, pas versionné — cf. .gitignore)
  generate.mjs         script de génération
```

Chaque template est un projet Astro **complet et indépendant** (pas un
package partagé) : un site généré doit rester copiable et déployable tel
quel, sans dépendance vers `templates/`.

## Contenu personnalisable : `src/data/site.config.json`

Astro utilise `{expression}` pour l'interpolation dans les fichiers `.astro`
(comme JSX) — un token `{{MUSTACHE}}` casserait la compilation. Tout le
contenu injectable (nom, adresse, téléphone, accroche, avis, tarifs,
galerie, horaires, réseaux sociaux) vit donc dans un unique fichier JSON par
site, importé nativement par les composants. Les placeholders restants sont
des valeurs explicites du type `"Avis client type — à remplacer"` — jamais
de faux contenu qui pourrait passer inaperçu en ligne.

## Générer un site

```bash
cd site-web

# Depuis des infos saisies à la main
node generate.mjs --template vitrine-beaute --name "Bar à Ongles Bordeaux" \
  --address "12 Rue de la Paix, 33000 Bordeaux" --phone "0556000000"

# Ou connecté au pipeline lead gen existant (backend démarré, GET /api/leads/{id})
node generate.mjs --template reservation --lead-id "node:123456" --api-url http://localhost:8000
```

Le script :
1. Slugifie le nom de l'entreprise (`Bar à Ongles Bordeaux` → `bar-a-ongles-bordeaux`).
2. Copie `templates/{template}/` → `sites-generes/{slug}/`.
3. Injecte les champs connus (nom, adresse, téléphone, lien Google Maps) dans
   `site.config.json` — le reste (photos, avis, tarifs) reste en placeholder.
4. Génère un `README.md` dans le dossier généré avec les instructions de
   déploiement Vercel.

## Après génération

```bash
cd sites-generes/{slug}
npm install
npm run dev      # aperçu local
```

Puis ouvrir `src/data/site.config.json` et remplacer les placeholders
restants (photos dans `public/images/`, avis, tarifs...). Pour le template
`reservation`, remplacer `reservation.calLink` par le vrai lien Cal.com du
client (sinon un widget de démonstration reste affiché, avec un message
d'erreur Cal.com explicite si le lien n'existe pas).

Une fois le contenu prêt, déployer avec `deploy.mjs` (voir section suivante)
pour obtenir une URL de preview à envoyer au prospect.

## Déploiement automatisé (`site-web/deploy.mjs`)

### Pourquoi Cloudflare Pages plutôt que Vercel

Les deux options envisagées ont un tier gratuit et un CLI de déploiement
direct sans repo git. Le point qui tranche pour ce cas d'usage précis
(démarchage à froid, sites de preview pour des prospects, donc usage
**commercial**) :

- **Vercel Hobby (gratuit)** interdit explicitement l'usage commercial dans
  ses CGU — toute mise en ligne "for the purpose of financial gain" doit
  passer sur le plan Pro (20 $/mois **par utilisateur**), sous peine de
  suspension de projet sans préavis. Techniquement hors périmètre pour un
  outil de prospection commerciale sur le tier gratuit.
- **Cloudflare Pages (gratuit)** autorise l'usage commercial sur son tier
  gratuit, sans limite de bande passante/requêtes. La seule vraie limite :
  un plafond souple de **100 projets par compte**, avec demande
  d'augmentation possible auprès de Cloudflare si besoin. Comme la plupart
  des previews envoyées à des prospects ne se transforment pas en client
  signé, il faut prévoir un nettoyage régulier des projets inutilisés (voir
  `--delete` ci-dessous) plutôt que de tout accumuler indéfiniment.

**→ Cloudflare Pages retenu**, via le CLI `wrangler` (déploiement direct
d'un dossier, pas de repo git nécessaire), avec une URL prévisible du type
`https://{slug}.pages.dev`.

### Installation & configuration

```bash
npm install -g wrangler   # ou laisser deploy.mjs utiliser npx (aucune install globale requise)
```

Créer un token API Cloudflare (dashboard Cloudflare → My Profile → API
Tokens → "Edit Cloudflare Workers" ou un token custom avec la permission
`Cloudflare Pages: Edit`), puis exporter :

```bash
export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ACCOUNT_ID="..."   # visible dans le dashboard Cloudflare, colonne de droite
```

Jamais en dur dans le code — uniquement via ces variables d'environnement.

### Utilisation

```bash
cd site-web

# Build + déploiement en une commande (prend un projet Astro OU un dossier déjà buildé)
node deploy.mjs sites-generes/miss-yan "Miss Yan"

# Sortie JSON en plus du texte (pour brancher sur un CRM)
node deploy.mjs sites-generes/miss-yan "Miss Yan" --json

# Forcer un nouveau projet même si le slug existe déjà (sinon : réutilisation = mise à jour)
node deploy.mjs sites-generes/miss-yan "Miss Yan" --fresh

# Lister les projets déployés
node deploy.mjs --list

# Supprimer un projet (prospect qui n'a pas donné suite, ex. après 30 jours)
node deploy.mjs --delete miss-yan
```

Le script : installe les dépendances et build si un projet Astro est passé
en entrée (détecté par l'absence d'`index.html` à la racine du dossier) ;
crée le projet Cloudflare Pages s'il n'existe pas encore ; déploie
directement en production (pas de preview intermédiaire à valider) ; imprime
l'URL finale (`https://{slug}.pages.dev`) et, avec `--json`, une ligne JSON
`{slug, url, deployedAt}` exploitable par un script tiers.

### Coût réel à l'échelle (50–100 sites de preview/mois)

**0 €/mois.** Le tier gratuit Cloudflare Pages n'a ni limite de bande
passante ni de requêtes, et 50–100 sites/mois reste très en dessous du
plafond de 100 projets simultanés — à condition de supprimer les previews
des prospects qui ne signent pas au bout de quelques semaines plutôt que de
les laisser s'accumuler indéfiniment (sans quoi le plafond de 100 projets
serait atteint en 1 à 2 mois). Domaine personnalisé également gratuit sur ce
tier le jour où un prospect signe — pas besoin de changer de plan.

## Ajouter un nouveau secteur (fast-food, restaurant avec menu, etc.)

Créer un nouveau dossier dans `templates/` avec la même structure
(`src/data/site.config.json` avec au minimum `nom`/`adresse`/`telephone`/
`googleMapsUrl`, mêmes noms de champs) — `generate.mjs` fonctionne sans
modification sur tout nouveau template respectant cette convention.
