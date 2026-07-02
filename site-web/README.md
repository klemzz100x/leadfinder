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
npx vercel --prod # déploiement
```

Puis ouvrir `src/data/site.config.json` et remplacer les placeholders
restants (photos dans `public/images/`, avis, tarifs...). Pour le template
`reservation`, remplacer `reservation.calLink` par le vrai lien Cal.com du
client (sinon un widget de démonstration reste affiché, avec un message
d'erreur Cal.com explicite si le lien n'existe pas).

## Ajouter un nouveau secteur (fast-food, restaurant avec menu, etc.)

Créer un nouveau dossier dans `templates/` avec la même structure
(`src/data/site.config.json` avec au minimum `nom`/`adresse`/`telephone`/
`googleMapsUrl`, mêmes noms de champs) — `generate.mjs` fonctionne sans
modification sur tout nouveau template respectant cette convention.
