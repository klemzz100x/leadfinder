#!/usr/bin/env node
// Déploie un site (projet Astro à builder, ou dossier statique déjà buildé)
// sur Cloudflare Pages en une commande, sans repo git, avec une URL
// prévisible (https://{slug}.pages.dev) pour l'envoyer immédiatement au
// prospect après génération.
//
// Usage :
//   node deploy.mjs <dossier-site> <nom-prospect> [--fresh] [--json]
//   node deploy.mjs --list
//   node deploy.mjs --delete <slug>
//
// Auth : variables d'environnement CLOUDFLARE_API_TOKEN et
// CLOUDFLARE_ACCOUNT_ID (jamais en dur dans le code — voir README.md).

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function requireEnv(name) {
  const v = process.env[name];
  if (!v) {
    console.error(`Variable d'environnement ${name} manquante. Voir site-web/README.md (section déploiement).`);
    process.exit(1);
  }
  return v;
}

function run(cmd, args, { capture = false } = {}) {
  const res = spawnSync(cmd, args, {
    encoding: 'utf-8',
    shell: true, // npm/npx sont des .cmd sur Windows — shell:true les résout partout
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
    env: process.env,
  });
  return res;
}

function slugify(name) {
  return name
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// Astro n'a pas d'API stable pour créer un projet Pages "s'il n'existe pas" —
// on tente la création et on interprète l'échec "already exists" comme un
// signal plutôt que de lister les projets d'abord (wrangler pages project
// list ne renvoie pas de JSON fiable). Évite aussi une course
// check-puis-create.
function ensureProject(slug) {
  const res = run('npx', ['wrangler', 'pages', 'project', 'create', slug, '--production-branch=main'], { capture: true });
  if (res.status === 0) return { created: true };
  const output = `${res.stderr || ''}${res.stdout || ''}`;
  if (/already exists/i.test(output)) return { created: false, exists: true };
  throw new Error(`Impossible de créer le projet Cloudflare Pages "${slug}" :\n${output || res.error}`);
}

function uniqueSlug(baseSlug, fresh) {
  let slug = baseSlug;
  let i = 2;
  // Sans --fresh : un projet déjà existant est réutilisé (redéploiement =
  // mise à jour du même prospect). Avec --fresh : on force un nouveau
  // projet et on suffixe en cas de collision (ex: deux prospects homonymes).
  while (true) {
    const result = ensureProject(slug);
    if (result.created || !fresh) return slug;
    slug = `${baseSlug}-${i}`;
    i++;
  }
}

// Accepte soit un dossier déjà statique (index.html à la racine), soit un
// projet Astro à installer/builder — couvre "site-web/sites-generes/{slug}"
// comme n'importe quel autre dossier de site statique.
function resolveStaticDir(inputDir) {
  const rootIndex = path.join(inputDir, 'index.html');
  if (fs.existsSync(rootIndex)) return inputDir;

  const pkgPath = path.join(inputDir, 'package.json');
  if (!fs.existsSync(pkgPath)) {
    throw new Error(`${inputDir} ne contient ni index.html ni package.json — dossier invalide.`);
  }
  if (!fs.existsSync(path.join(inputDir, 'node_modules'))) {
    console.log('Installation des dépendances…');
    const install = run('npm', ['install'], { capture: false });
    if (install.status !== 0) throw new Error("Échec de l'installation des dépendances.");
  }
  console.log('Build du site…');
  const build = run('npm', ['run', 'build'], { capture: false });
  if (build.status !== 0) throw new Error('Le build a échoué.');

  const distDir = path.join(inputDir, 'dist');
  if (!fs.existsSync(path.join(distDir, 'index.html'))) {
    throw new Error(`Build terminé mais ${distDir}/index.html introuvable.`);
  }
  return distDir;
}

function deploy(inputDir, name, { fresh = false, json = false } = {}) {
  requireEnv('CLOUDFLARE_API_TOKEN');
  requireEnv('CLOUDFLARE_ACCOUNT_ID');

  const baseSlug = slugify(name);
  if (!baseSlug) throw new Error(`Nom invalide : "${name}" ne produit aucun slug exploitable.`);

  const staticDir = resolveStaticDir(inputDir);
  const slug = uniqueSlug(baseSlug, fresh);

  console.log(`Déploiement de ${staticDir} vers le projet "${slug}"…`);
  const deployRes = run('npx', [
    'wrangler', 'pages', 'deploy', staticDir,
    `--project-name=${slug}`, '--branch=main', '--commit-dirty=true',
  ], { capture: false });
  if (deployRes.status !== 0) {
    throw new Error(`Le déploiement Cloudflare Pages a échoué (voir sortie ci-dessus).`);
  }

  const url = `https://${slug}.pages.dev`;
  const result = { slug, url, deployedAt: new Date().toISOString() };

  console.log(`\n✔ Site en ligne : ${url}`);
  if (json) console.log(JSON.stringify(result));
  return result;
}

// ── CLI ──
const args = process.argv.slice(2);

if (args[0] === '--list') {
  requireEnv('CLOUDFLARE_API_TOKEN');
  requireEnv('CLOUDFLARE_ACCOUNT_ID');
  run('npx', ['wrangler', 'pages', 'project', 'list']);
  process.exit(0);
}

if (args[0] === '--delete') {
  const slug = args[1];
  if (!slug) {
    console.error('Usage : node deploy.mjs --delete <slug>');
    process.exit(1);
  }
  requireEnv('CLOUDFLARE_API_TOKEN');
  requireEnv('CLOUDFLARE_ACCOUNT_ID');
  // Pas de --yes documenté de façon fiable : laissé interactif (stdio hérité)
  // pour que la confirmation éventuelle de wrangler reste visible.
  run('npx', ['wrangler', 'pages', 'project', 'delete', slug]);
  process.exit(0);
}

const positional = args.filter((a) => !a.startsWith('--'));
const [inputDir, name] = positional;
const fresh = args.includes('--fresh');
const json = args.includes('--json');

if (!inputDir || !name) {
  console.error('Usage : node deploy.mjs <dossier-site> <nom-prospect> [--fresh] [--json]');
  console.error('        node deploy.mjs --list');
  console.error('        node deploy.mjs --delete <slug>');
  process.exit(1);
}

try {
  deploy(inputDir, name, { fresh, json });
} catch (err) {
  console.error(err.message);
  process.exit(1);
}
