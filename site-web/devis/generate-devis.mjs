#!/usr/bin/env node
// Génère un devis PDF pour un client à partir de template.html, fidèle à la
// maquette fournie (../../../Template_devis). Émetteur fixe (moi),
// informations client passées en paramètres. Numéro de devis auto-incrémenté
// à partir des fichiers déjà générés dans generes/.
//
// Usage :
//   node generate-devis.mjs --name "Miss Yan" --address "58 Rue Faugères, 33130 Bègles" --siret "820 780 492 00022"
//   node generate-devis.mjs --name "..." --address "..."   (sans --siret : placeholder explicite "à compléter")

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(__dirname, 'generes');

const EMETTEUR = {
  nom: 'Clément Garnero Nguyen',
  siren: '935352153',
  email: 'clem.garnero753@gmail.com',
  adresse: '11 chemin des chaüs, Cestas',
};

const LIGNES = [
  { description: "Conception et développement d'un site internet professionnel", prix: '600 €' },
  { description: 'Maintenance', prix: '100 €/an' },
];

const TERMES = 'Acompte de 25% à la signature, solde de 75% sous 30 jours après livraison';
const DATE = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });

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
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// Cherche le plus grand numéro "devis-NN-" déjà généré dans generes/ pour
// enchaîner sans collision, quel que soit le client précédent.
function nextDevisNumber() {
  if (!fs.existsSync(OUT_DIR)) return 1;
  const existing = fs.readdirSync(OUT_DIR)
    .map((f) => f.match(/^devis-(\d+)-/))
    .filter(Boolean)
    .map((m) => parseInt(m[1], 10));
  return existing.length > 0 ? Math.max(...existing) + 1 : 1;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function buildHtml(template, client) {
  // LIGNES est le seul champ qui contient volontairement du HTML (les <tr>,
  // déjà échappés valeur par valeur) — tous les autres champs sont du texte
  // brut à échapper avant insertion.
  const lignesHtml = LIGNES.map(
    (l) => `<tr><td>${escapeHtml(l.description)}</td><td class="price">${escapeHtml(l.prix)}</td></tr>`
  ).join('\n');

  const textFields = {
    NUMERO: client.numero,
    DATE,
    VALIDITE: '1 mois',
    EMETTEUR_NOM: EMETTEUR.nom,
    EMETTEUR_SIREN: EMETTEUR.siren,
    EMETTEUR_EMAIL: EMETTEUR.email,
    EMETTEUR_ADRESSE: EMETTEUR.adresse,
    CLIENT_NOM: client.nom,
    CLIENT_SIRET_LABEL: `Numéro Siret : ${client.siret}`,
    CLIENT_ADRESSE: client.adresse,
    SOUS_TOTAL: '700 €',
    TOTAL: '700 €',
    TERMES,
  };

  let html = template;
  for (const [key, value] of Object.entries(textFields)) {
    html = html.replaceAll(`{{${key}}}`, escapeHtml(value));
  }
  html = html.replaceAll('{{LIGNES}}', lignesHtml);
  return html;
}

export async function generateDevis({ name, address, siret }) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const template = fs.readFileSync(path.join(__dirname, 'template.html'), 'utf-8');

  const num = nextDevisNumber();
  const numeroLabel = `DEVIS #${String(num).padStart(2, '0')}`;
  const slug = slugify(name);
  const fichier = `devis-${String(num).padStart(2, '0')}-${slug}.pdf`;

  const client = {
    numero: numeroLabel,
    nom: name,
    siret: siret || 'à compléter — statut SIRET à vérifier sur place',
    adresse: address,
  };

  const html = buildHtml(template, client);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle' });
  const outPath = path.join(OUT_DIR, fichier);
  await page.pdf({ path: outPath, format: 'A4', printBackground: true });
  await browser.close();

  console.log(`✔ ${numeroLabel} — ${name} → site-web/devis/generes/${fichier}`);
  return { numero: numeroLabel, fichier: outPath };
}

// ── CLI ──
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = parseArgs(process.argv.slice(2));
  if (!args.name || !args.address) {
    console.error('Usage : node generate-devis.mjs --name "Nom entreprise" --address "Adresse complète" [--siret "..."]');
    process.exit(1);
  }
  generateDevis({ name: args.name, address: args.address, siret: args.siret }).catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
