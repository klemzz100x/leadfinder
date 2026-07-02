#!/usr/bin/env node
// Génère un site client à partir d'un template : copie templates/{template}/
// vers sites-generes/{slug}/, puis injecte les infos déjà connues (nom,
// adresse, téléphone, lien Google Maps) dans src/data/site.config.json. Le
// reste (photos, avis, tarifs) reste en placeholder pour remplissage manuel.
//
// Usage :
//   node generate.mjs --template vitrine-beaute --name "Bar à Ongles Bordeaux"
//   node generate.mjs --template reservation --lead-id "node:123456" --api-url http://localhost:8000

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = path.join(__dirname, 'templates');
const OUTPUT_DIR = path.join(__dirname, 'sites-generes');
const SKIP_ENTRIES = new Set(['node_modules', 'dist', '.astro']);

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2);
      const next = argv[i + 1];
      const value = next !== undefined && !next.startsWith('--') ? argv[++i] : true;
      args[key] = value;
    }
  }
  return args;
}

function slugify(name) {
  return name
    .normalize('NFD').replace(/[̀-ͯ]/g, '') // retire les accents
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (SKIP_ENTRIES.has(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

async function fetchLeadInfo(apiUrl, leadId) {
  const url = `${apiUrl.replace(/\/$/, '')}/api/leads/${encodeURIComponent(leadId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Impossible de récupérer le lead ${leadId} depuis ${url} (HTTP ${res.status})`);
  return res.json();
}

function buildReadme({ slug, template, calLinkNote }) {
  return `# ${slug}

Site généré depuis le template \`${template}\` du système de génération LeadFinder.

## Personnalisation restante

Ouvrez \`src/data/site.config.json\` et remplacez les champs encore marqués
"à remplacer" (photos dans \`public/images/\`, avis clients, tarifs, réseaux
sociaux...). Le nom/adresse/téléphone/lien Maps ont déjà été injectés
automatiquement si disponibles.
${calLinkNote}

## Déploiement rapide (Vercel)

\`\`\`bash
npm install
npx vercel --prod
\`\`\`

Ou connectez ce dossier à un nouveau projet depuis le dashboard Vercel.

## Développement local

\`\`\`bash
npm install
npm run dev
\`\`\`
`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const template = args.template;

  if (!template) {
    console.error('Paramètre --template requis. Templates disponibles :', fs.readdirSync(TEMPLATES_DIR).join(', '));
    process.exit(1);
  }
  if (!fs.existsSync(path.join(TEMPLATES_DIR, template))) {
    console.error(`Template inconnu : "${template}". Templates disponibles :`, fs.readdirSync(TEMPLATES_DIR).join(', '));
    process.exit(1);
  }

  let name = args.name;
  let address = args.address;
  let phone = args.phone;
  let gmapsUrl = args['gmaps-url'];
  let website = args.website;

  if (args['lead-id']) {
    const apiUrl = args['api-url'] || 'http://localhost:8000';
    console.log(`Récupération du lead ${args['lead-id']} depuis ${apiUrl}…`);
    const lead = await fetchLeadInfo(apiUrl, args['lead-id']);
    name = name || lead.name;
    address = address || lead.address;
    phone = phone || lead.phone;
    gmapsUrl = gmapsUrl || lead.gmaps_url;
    website = website || lead.website;
  }

  if (!name) {
    console.error("Paramètre --name requis (nom de l'entreprise), ou --lead-id pour le récupérer automatiquement.");
    process.exit(1);
  }

  const slug = slugify(name);
  const destDir = path.join(OUTPUT_DIR, slug);
  if (fs.existsSync(destDir)) {
    console.error(`Le dossier sites-generes/${slug} existe déjà — supprimez-le ou choisissez un autre nom avant de régénérer.`);
    process.exit(1);
  }

  console.log(`Génération de "${name}" (${slug}) à partir du template "${template}"…`);
  copyDir(path.join(TEMPLATES_DIR, template), destDir);

  const configPath = path.join(destDir, 'src', 'data', 'site.config.json');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  config.nom = name;
  if (address) config.adresse = address;
  if (phone) config.telephone = phone;
  if (website) config.siteWebActuel = website;
  if (gmapsUrl) {
    config.googleMapsUrl = gmapsUrl;
  } else if (address) {
    config.googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${name}, ${address}`)}`;
  }
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');

  const calLinkNote = template === 'reservation'
    ? "\n\nCe template utilise Cal.com pour la réservation : remplacez `reservation.calLink` dans `site.config.json` par votre propre lien Cal.com (compte à créer sur cal.com), sinon un widget de démonstration reste affiché."
    : '';
  fs.writeFileSync(path.join(destDir, 'README.md'), buildReadme({ slug, template, calLinkNote }));

  console.log(`✔ Site généré : site-web/sites-generes/${slug}/`);
  console.log(`  Prochaine étape : cd site-web/sites-generes/${slug} && npm install && npm run dev`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
