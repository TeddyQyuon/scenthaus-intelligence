// Local test fixture only: PGlite's PostgreSQL wire protocol, without Docker.
// Production uses a managed PostgreSQL DATABASE_URL. This is not a concurrency proof.
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
const database = await PGlite.create(resolve(process.env.TEST_DB_DIR || 'data/pg'));
const server = new PGLiteSocketServer({ db: database, host: '127.0.0.1', port: 5544 });
await server.start();
const [command, ...args] = process.argv.slice(2);
if (!command) throw new Error('Usage: node tools/pg-run.mjs COMMAND [ARGS...]');
const child = spawn(command, args, {
  stdio: 'inherit',
  env: { ...process.env, DATABASE_URL: 'postgresql+psycopg://postgres:postgres@127.0.0.1:5544/postgres' },
});
process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));
child.on('exit', async (code) => {
  await server.stop();
  await database.close();
  process.exit(code ?? 1);
});
