import assert from 'node:assert/strict';
import test from 'node:test';
import {
  LOCAL_TEST_API_ORIGIN,
  PRODUCTION_API_ORIGIN,
  normalizeApiOrigin,
  resolveApiBaseUrl,
  resolveApiUrl
} from '../src/config/api.js';

const localPage = {
  origin: 'http://127.0.0.1:3000',
  hostname: '127.0.0.1',
  protocol: 'http:',
  search: '?firebaseEmulator=1'
};

test('emulator browser configuration selects only the isolated backend port', () => {
  assert.equal(resolveApiBaseUrl({ location: localPage }), LOCAL_TEST_API_ORIGIN);
  assert.notEqual(LOCAL_TEST_API_ORIGIN, 'http://127.0.0.1:8000');
});

test('emulator mode rejects production hosts and non-isolated API overrides', () => {
  assert.throws(() => resolveApiBaseUrl({
    location: { ...localPage, origin: 'https://talentscope.example', hostname: 'talentscope.example', protocol: 'https:' }
  }), /HTTP loopback/);
  assert.throws(() => resolveApiBaseUrl({
    location: localPage,
    configuredApiOrigin: 'https://api.example'
  }), /non-isolated API override/);
});

test('normal frontend development and explicit API configuration remain unchanged', () => {
  assert.equal(resolveApiBaseUrl({
    location: { ...localPage, search: '' }
  }), 'http://127.0.0.1:8000');
  assert.equal(resolveApiBaseUrl({
    location: { ...localPage, search: '' },
    configuredApiOrigin: 'https://api.example'
  }), 'https://api.example');
});

test('production deployment on Vercel automatically falls back to live Render API', () => {
  const vercelPage = {
    origin: 'https://talent-scope-ten.vercel.app',
    hostname: 'talent-scope-ten.vercel.app',
    protocol: 'https:',
    search: ''
  };
  assert.equal(resolveApiBaseUrl({ location: vercelPage }), PRODUCTION_API_ORIGIN);
  assert.equal(PRODUCTION_API_ORIGIN, 'https://talentscope-im0q.onrender.com');
});

test('normalizeApiOrigin strips trailing slashes and /api/v1 so endpoints never duplicate /api/v1/api/v1', () => {
  assert.equal(normalizeApiOrigin('https://talentscope-im0q.onrender.com/api/v1'), 'https://talentscope-im0q.onrender.com');
  assert.equal(normalizeApiOrigin('https://talentscope-im0q.onrender.com/api/v1/'), 'https://talentscope-im0q.onrender.com');
  assert.equal(normalizeApiOrigin('https://talentscope-im0q.onrender.com/'), 'https://talentscope-im0q.onrender.com');
  assert.equal(normalizeApiOrigin('http://127.0.0.1:8000/api/v1'), 'http://127.0.0.1:8000');

  const resolved = resolveApiBaseUrl({
    location: { ...localPage, search: '' },
    configuredApiOrigin: 'https://talentscope-im0q.onrender.com/api/v1/'
  });
  assert.equal(resolved, 'https://talentscope-im0q.onrender.com');
});

test('resolveApiUrl cleanly constructs paths without duplicating /api/v1 or missing slashes', () => {
  const urlWithV1 = resolveApiUrl('/api/v1/auth/sync');
  assert.match(urlWithV1, /\/api\/v1\/auth\/sync$/);
  assert.doesNotMatch(urlWithV1, /\/api\/v1\/api\/v1/);

  const urlWithoutV1 = resolveApiUrl('/auth/sync');
  assert.match(urlWithoutV1, /\/api\/v1\/auth\/sync$/);

  const urlAssistant = resolveApiUrl('/api/assistant/chat');
  assert.match(urlAssistant, /\/api\/assistant\/chat$/);
  assert.doesNotMatch(urlAssistant, /\/api\/v1\/api\/assistant/);
});
