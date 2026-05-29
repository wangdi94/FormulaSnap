#!/usr/bin/env node
/**
 * Sync version from package.json to Cargo.toml and tauri.conf.json.
 * 
 * Usage: node scripts/sync-version.js
 * 
 * Reads version from package.json and writes it to:
 * - src-tauri/Cargo.toml (version = "x.y.z")
 * - src-tauri/tauri.conf.json ("version": "x.y.z")
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

// Read version from package.json
const pkgPath = resolve(root, 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
const version = pkg.version;

if (!version || !/^\d+\.\d+\.\d+/.test(version)) {
  console.error(`Invalid version in package.json: "${version}"`);
  process.exit(1);
}

// Update Cargo.toml
const cargoPath = resolve(root, 'src-tauri/Cargo.toml');
let cargo = readFileSync(cargoPath, 'utf8');
cargo = cargo.replace(
  /^(version\s*=\s*")[^"]*(")/m,
  `$1${version}$2`
);
writeFileSync(cargoPath, cargo);

// Update tauri.conf.json
const tauriPath = resolve(root, 'src-tauri/tauri.conf.json');
const tauri = JSON.parse(readFileSync(tauriPath, 'utf8'));
tauri.version = version;
writeFileSync(tauriPath, JSON.stringify(tauri, null, 2) + '\n');

console.log(`Version synced to ${version} across package.json, Cargo.toml, tauri.conf.json`);
