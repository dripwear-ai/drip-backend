import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const [surface, command = 'dev'] = process.argv.slice(2);
if (!['admin', 'seller'].includes(surface) || !['dev', 'build', 'start'].includes(command)) {
  process.stderr.write('Usage: node scripts/portal.mjs <admin|seller> <dev|build|start>\n');
  process.exit(2);
}

const root = fileURLToPath(new URL('..', import.meta.url));
const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin', 'next');
const port = surface === 'admin' ? '3001' : '3002';
const distDir = process.env.NEXT_PORTAL_DIST_DIR || `.next-${surface}`;
if (!/^\.next-[a-z0-9-]+$/.test(distDir)) {
  process.stderr.write('NEXT_PORTAL_DIST_DIR must be a project-local .next-* directory.\n');
  process.exit(2);
}
const args = [nextBin, command];
if (command === 'build') args.push('--webpack');
else args.push('--port', port, '--hostname', '127.0.0.1');
const child = spawn(process.execPath, args, {
  cwd: root,
  stdio: 'inherit',
  env: {
    ...process.env,
    DRIP_PORTAL_SURFACE: surface,
    NEXT_PORTAL_DIST_DIR: distDir,
  },
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}
child.on('exit', (code, signal) => {
  process.exit(code ?? (signal ? 130 : 1));
});
