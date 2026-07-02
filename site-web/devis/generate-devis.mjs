#!/usr/bin/env node
// Génère un devis PDF par client à partir de template.html, fidèle à la
// maquette fournie (site-web/../Template_devis). Émetteur fixe (moi),
// informations client à renseigner par entreprise.
//
// Usage : node generate-devis.mjs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
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

// Statut SIRET vérifié auprès de annuaire-entreprises.data.gouv.fr (source
// officielle) le jour de la génération — voir note dans le rapport de
// conversation. Pour les 2 sociétés dont l'établissement trouvé apparaît
// fermé/radié, le champ SIRET reste un placeholder explicite à compléter
// après vérification sur place plutôt que d'inventer un numéro.
const CLIENTS = [
  {
    numero: 'DEVIS #01',
    fichier: 'devis-miss-yan.pdf',
    nom: 'Miss Yan',
    siret: '820 780 492 00022',
    adresse: '58 Rue Faugères, 33130 Bègles',
  },
  {
    numero: 'DEVIS #02',
    fichier: 'devis-lile-o-beaute.pdf',
    nom: "L'Ile O Beauté",
    siret: 'à compléter — statut SIRET à vérifier sur place',
    adresse: '20 Rue Jean Mermoz, 33185 Le Haillan',
  },
  {
    numero: 'DEVIS #03',
    fichier: 'devis-plaisance-coiffure.pdf',
    nom: 'Plaisance Coiffure',
    siret: 'à compléter — statut SIRET à vérifier sur place',
    adresse: '34 Rue Alfred Dejean, 33120 Arcachon',
  },
];

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

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const template = fs.readFileSync(path.join(__dirname, 'template.html'), 'utf-8');

  const browser = await chromium.launch();
  const page = await browser.newPage();

  for (const client of CLIENTS) {
    const html = buildHtml(template, client);
    await page.setContent(html, { waitUntil: 'networkidle' });
    const outPath = path.join(OUT_DIR, client.fichier);
    await page.pdf({ path: outPath, format: 'A4', printBackground: true });
    console.log(`✔ ${client.numero} — ${client.nom} → site-web/devis/generes/${client.fichier}`);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
