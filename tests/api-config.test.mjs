import assert from 'node:assert/strict';
import test from 'node:test';
import { LOCAL_TEST_API_ORIGIN, resolveApiBaseUrl } from '../src/config/api.js';

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
