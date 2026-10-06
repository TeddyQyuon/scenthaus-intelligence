import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
test('a second fixture writer is rejected before opening the database', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'scenthaus-lock-'));
  const database = join(dir, 'pg');
  await writeFile(`${database}.lock`, 'first-owner');
  try {
    const result = spawnSync(process.execPath, [resolve('tools/pg-run.mjs'), process.execPath, '-e', 'throw Error("must not run")'], {
      env: { ...process.env, TEST_DB_DIR: database }, encoding: 'utf8',
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Fixture is already in use/);
    assert.equal(await readFile(`${database}.lock`, 'utf8'), 'first-owner');
  } finally { await rm(dir, { recursive: true }); }
});
