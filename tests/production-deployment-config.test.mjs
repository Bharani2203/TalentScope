import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

test('Production Deployment Configuration & Environment Guard Suite', async (t) => {
  await t.test('1. Frontend firebase-client.js guards connectAuthEmulator with process.env.NODE_ENV === "development"', () => {
    const filePath = path.join(process.cwd(), 'src', 'auth', 'firebase-client.js');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(
      content.includes("process.env.NODE_ENV === 'development'"),
      'firebase-client.js must include process.env.NODE_ENV === "development" guard'
    );
    assert.ok(
      content.includes('connectAuthEmulator'),
      'firebase-client.js must reference connectAuthEmulator'
    );
    assert.ok(
      content.includes("'skill-demand-forecasting'"),
      'firebase-client.js must default to production live Firebase project ID'
    );
  });

  await t.test('2. Frontend src/config/firebase.js guards all emulator connections', () => {
    const filePath = path.join(process.cwd(), 'src', 'config', 'firebase.js');
    assert.ok(fs.existsSync(filePath), 'src/config/firebase.js must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(
      content.includes("process.env.NODE_ENV === 'development'"),
      'src/config/firebase.js must guard emulator connections with NODE_ENV development check'
    );
    assert.ok(content.includes('connectAuthEmulator'), 'Must guard connectAuthEmulator');
    assert.ok(content.includes('connectFirestoreEmulator'), 'Must guard connectFirestoreEmulator');
    assert.ok(content.includes('connectFunctionsEmulator'), 'Must guard connectFunctionsEmulator');
    assert.ok(
      content.includes("'skill-demand-forecasting'"),
      'src/config/firebase.js must target live project skill-demand-forecasting'
    );
  });

  await t.test('3. Backend app/core/database.py dynamically reads DATABASE_URL', () => {
    const filePath = path.join(process.cwd(), 'backend', 'app', 'core', 'database.py');
    assert.ok(fs.existsSync(filePath), 'database.py must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('DATABASE_URL'), 'Must read DATABASE_URL environment variable');
    assert.ok(content.includes('POSTGRES_URL'), 'Must support POSTGRES_URL fallback');
    assert.ok(content.includes('get_pg_config'), 'Must export dynamic get_pg_config');
    assert.ok(content.includes('get_database_url'), 'Must export get_database_url');
    assert.ok(content.includes('PG_CONFIG'), 'Must export dynamic PG_CONFIG proxy');
  });

  await t.test('4. Backend firebase.py supports FIREBASE_SERVICE_ACCOUNT_BASE64 and raw JSON', () => {
    const filePath = path.join(process.cwd(), 'backend', 'app', 'core', 'firebase.py');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(
      content.includes('FIREBASE_SERVICE_ACCOUNT_BASE64'),
      'firebase.py must support FIREBASE_SERVICE_ACCOUNT_BASE64'
    );
    assert.ok(
      content.includes('FIREBASE_SERVICE_ACCOUNT_JSON'),
      'firebase.py must support FIREBASE_SERVICE_ACCOUNT_JSON'
    );
  });

  await t.test('5. production.env.example explicitly warns against emulator flags and documents DATABASE_URL', () => {
    const filePath = path.join(process.cwd(), 'backend', 'production.env.example');
    assert.ok(fs.existsSync(filePath), 'production.env.example must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(
      content.includes('FIRESTORE_EMULATOR_HOST'),
      'production.env.example must mention FIRESTORE_EMULATOR_HOST'
    );
    assert.ok(
      content.includes('FIREBASE_AUTH_EMULATOR_HOST'),
      'production.env.example must mention FIREBASE_AUTH_EMULATOR_HOST'
    );
    assert.ok(
      content.includes('DATABASE_URL'),
      'production.env.example must configure DATABASE_URL for hosted Postgres'
    );
    assert.ok(
      content.includes('FIREBASE_SERVICE_ACCOUNT_BASE64'),
      'production.env.example must document Base64 service account credentials'
    );
  });

  await t.test('6. Live backend API health check succeeds', async () => {
    const res = await fetch('http://127.0.0.1:8000/api/v1/health');
    assert.equal(res.status, 200, 'Health endpoint should return 200 OK');
    const data = await res.json();
    assert.ok(data.status === 'ok' || data.status === 'healthy', 'Backend should report healthy status');
  });

  await t.test('7. sync_local_to_live_firestore.py contains quota safety guards and terminal confirmation', () => {
    const scriptPath = path.join(process.cwd(), 'backend', 'scripts', 'sync_local_to_live_firestore.py');
    assert.ok(fs.existsSync(scriptPath), 'sync_local_to_live_firestore.py must exist in backend/scripts/');
    const content = fs.readFileSync(scriptPath, 'utf-8');

    assert.ok(
      content.includes('450'),
      'Migration script must use chunked batch limit of 450 items'
    );
    assert.ok(
      content.includes('2.5'),
      'Migration script must pause 2.5s between batch commits'
    );
    assert.ok(
      content.includes("WARNING: You are about to write local data to the LIVE production Firestore. Type 'YES' to continue:"),
      'Migration script must require strict interactive terminal confirmation'
    );
    assert.ok(
      content.includes('FIRESTORE_EMULATOR_HOST'),
      'Migration script must explicitly remove emulator environment variables'
    );
    assert.ok(
      content.includes('Successfully migrated') && content.includes('Sleeping'),
      'Migration script must output telemetry on batch commit'
    );
  });
});

