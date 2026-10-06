// Local fixture only; production uses a managed PostgreSQL DATABASE_URL.
// PGlite cannot prove concurrent production row-lock behaviour.
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { open, rm, mkdir } from 'node:fs/promises';
const [command, ...args] = process.argv.slice(2);
if (!command) throw new Error('Usage: node tools/pg-run.mjs COMMAND [ARGS...]');
const directory = resolve(process.env.TEST_DB_DIR || 'data/pg');
await mkdir(resolve(directory, '..'), { recursive: true });
// Opening two PGlite processes on one directory can overwrite each other's state.
const lockPath = `${directory}.lock`;
let lock;
try {
  lock = await open(lockPath, 'wx');
  await lock.writeFile(String(process.pid));
} catch (error) {
  if (error.code === 'EEXIST') throw new Error(`Fixture is already in use: ${lockPath}. After a crash, verify no fixture process is running before removing this lock.`);
  throw error;
}
let database, server, child;
let status = 1;
try {
  database = await PGlite.create(directory);
  server = new PGLiteSocketServer({ db: database, host: '127.0.0.1', port: 5544 });
  await server.start();
  child = spawn(command, args, {
    stdio: 'inherit',
    env: { ...process.env, DATABASE_URL: 'postgresql+psycopg://postgres:postgres@127.0.0.1:5544/postgres' },
  });
  process.on('SIGTERM', () => child.kill('SIGTERM'));
  process.on('SIGINT', () => child.kill('SIGINT'));
  status = await new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('exit', code => resolve(code ?? 1));
  });
} finally {
  if (server) await server.stop();
  // Socket stop schedules asynchronous detach callbacks. Drain them before closing WASM.
  await new Promise(resolve => setImmediate(resolve));
  if (database) {
    await database.exec('SELECT 1');
    await new Promise(resolve => setImmediate(resolve));
    await database.syncToFs();
    await database.close();
  }
  await lock.close();
  await rm(lockPath);
}
process.exit(status);
