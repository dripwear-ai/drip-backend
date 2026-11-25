import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Copy only Git-visible source. Never copy .env, node_modules, virtualenvs or generated outputs.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pnpmCli = process.env.npm_execpath;
if (!pnpmCli || !/pnpm/i.test(pnpmCli)) throw new Error('Run this with pnpm verify:clean');
const env = { ...process.env, CI: '1', EXPO_NO_TELEMETRY: '1', NEXT_TELEMETRY_DISABLED: '1',
  DRIP_ENV_FILE: '', ENVIRONMENT: 'test', PYTHONPATH: '',
  UV_CACHE_DIR: path.join(root, '.cache', 'uv'),
  npm_config_store_dir: path.join(root, '.pnpm-store'),
  npm_config_cache: path.join(root, '.cache', 'npm'),
  EXPO_HOME: path.join(root, '.cache', 'expo'),
  GIT_CONFIG_GLOBAL: process.platform === 'win32' ? 'NUL' : '/dev/null',
  GIT_CONFIG_NOSYSTEM: '1', GIT_OPTIONAL_LOCKS: '0' };
for (const key of ['VIRTUAL_ENV', 'UV_PROJECT_ENVIRONMENT', 'DATABASE_URL', 'REDIS_URL',
  'DRIP_TEST_DATABASE_URL', 'DRIP_TEST_REDIS_URL', 'SECRET_KEY', 'DEBUG']) delete env[key];
const listing = spawnSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'],
  { cwd: root, env, encoding: 'utf8' });
if (listing.status !== 0) throw new Error(listing.stderr);
mkdirSync(path.join(root, '.verification'), { recursive: true });
const snapshot = mkdtempSync(path.join(root, '.verification', 'clean-'));
const excluded = /(^|[/\\])(node_modules|dist|\.next|\.expo|\.venv|\.git|\.cache|\.verification|__pycache__)([/\\]|$)/;
const generatedDeclarations = new Set(['apps/web/next-env.d.ts', 'apps/mobile/expo-env.d.ts']);
let files = 0;
const sourceFiles = [];
for (const name of listing.stdout.split('\0').filter(Boolean)) {
  if (excluded.test(name) || generatedDeclarations.has(name) || name.endsWith('.tsbuildinfo') || /^\.env(?!\.example$)/.test(path.basename(name))) continue;
  const source = path.join(root, name);
  if (!existsSync(source)) continue;
  if (!lstatSync(source).isFile()) throw new Error(`Refusing non-regular source: ${name}`);
  const target = path.resolve(snapshot, name);
  if (!target.startsWith(snapshot + path.sep)) throw new Error('Unsafe source path');
  mkdirSync(path.dirname(target), { recursive: true });
  copyFileSync(source, target); files++;
  sourceFiles.push(name);
}
const generatedPaths = ['node_modules', '.venv', '.env', 'apps/api/.venv', 'apps/api/.env',
  'apps/web/node_modules', 'apps/web/.next', 'apps/mobile/node_modules', 'apps/mobile/.expo',
  'apps/mobile/dist', 'packages/shared-types/node_modules', 'packages/shared-types/dist',
  ...generatedDeclarations];
if (generatedPaths.some(name => existsSync(path.join(snapshot, name)))) {
  throw new Error('Clean source preflight found a generated artifact or local environment file');
}
const results = { snapshot, files, sourceFiles,
  source: 'Current Git-visible working tree, without generated artifacts or local environment files',
  preflight: { status: 'PASS', absentBeforeInstallation: generatedPaths }, checks: [] };
const hash = p => createHash('sha256').update(readFileSync(path.join(snapshot, p))).digest('hex');
const locks = ['pnpm-lock.yaml', 'apps/api/uv.lock'];
const before = locks.map(hash);
const checks = [
  ['Frozen JS install', process.execPath, [pnpmCli, 'install', '--frozen-lockfile']],
  ['Locked Python sync', 'uv', ['sync', '--project', 'apps/api', '--locked', '--python', '3.14.7', '--extra', 'dev']],
  ...['build:shared', 'type-check', 'test', 'lint', 'type-check:api', 'build', 'check:mobile', 'export:mobile', 'verify:static']
    .map(name => [name, process.execPath, [pnpmCli, name]]),
];
let installFailed = false;
for (const [name, executable, args] of checks) {
  if (installFailed) { results.checks.push({ name, status: 'BLOCKED', reason: 'Installation failed' }); continue; }
  console.log(`\n>>> ${name}`);
  const run = spawnSync(executable, args, { cwd: snapshot, env, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
  const output = (run.stdout || '') + (run.stderr || '') + (run.error ? String(run.error) : '');
  console.log(output);
  const log = `${results.checks.length + 1}-${name.replaceAll(':', '-')}.log`;
  writeFileSync(path.join(snapshot, log), output);
  const status = run.error?.code === 'ENOENT' ? 'BLOCKED' : run.status === 0 ? 'PASS' : 'FAIL';
  results.checks.push({ name, command: [executable, ...args], status, exitCode: run.status, log });
  if (run.status !== 0 && (name === 'Frozen JS install' || name === 'Locked Python sync')) installFailed = true;
  writeFileSync(path.join(snapshot, 'verification-results.json'), JSON.stringify(results, null, 2));
}
const unchanged = locks.every((p, i) => hash(p) === before[i]);
results.checks.push({ name: 'Lockfiles unchanged', status: unchanged ? 'PASS' : 'FAIL' });
results.checks.push({ name: 'Docker/live migrations and native device tests', status: 'NOT RUN', reason: 'Run the separate documented service/device checks' });
writeFileSync(path.join(snapshot, 'verification-results.json'), JSON.stringify(results, null, 2));
console.log(`Results: ${snapshot}`);
console.log('This verifies the listed software checks only; Gate B acceptance remains pending.');
process.exitCode = results.checks.some(c => ['FAIL', 'BLOCKED'].includes(c.status)) ? 1 : 0;
