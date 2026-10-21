import assert from 'node:assert/strict';
import test from 'node:test';
import {
  LOCAL_FIREBASE_PROJECT_ID,
  resolveFirebaseEmulatorConfig,
  verifyFirebaseEmulator
} from '../src/auth/firebase-emulator-config.js';

const localLocation = { hostname: 'localhost', protocol: 'http:', search: '?firebaseEmulator=1' };

test('Firebase emulator mode is disabled by default', () => {
  assert.equal(resolveFirebaseEmulatorConfig({ ...localLocation, search: '' }), null);
});

test('explicit local mode selects only the fixed demo project and loopback Auth emulator', () => {
  assert.deepEqual(resolveFirebaseEmulatorConfig(localLocation), {
    projectId: LOCAL_FIREBASE_PROJECT_ID,
    authUrl: 'http://127.0.0.1:9099',
    readinessUrl: 'http://127.0.0.1:9099/emulator/v1/projects/demo-talentscope-local/config'
  });
});

test('emulator mode rejects production hosts and HTTPS production origins', () => {
  assert.throws(() => resolveFirebaseEmulatorConfig({ ...localLocation, hostname: 'app.example.com' }), /localhost/);
  assert.throws(() => resolveFirebaseEmulatorConfig({ ...localLocation, protocol: 'https:' }), /localhost/);
});

test('unavailable or unhealthy Auth emulator fails closed', async () => {
  const config = resolveFirebaseEmulatorConfig(localLocation);
  await assert.rejects(verifyFirebaseEmulator(config, async () => { throw new Error('offline'); }), /production authentication was not selected/);
  await assert.rejects(verifyFirebaseEmulator(config, async () => ({ ok: false })), /readiness check failed/);
  await verifyFirebaseEmulator(config, async () => ({ ok: true }));
});
