import assert from 'node:assert/strict';

const registeredTests = [];
function test(name, run) {
  registeredTests.push({ name, run });
}

globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  TALENTSCOPE_API_BASE_URL: 'http://127.0.0.1:8000',
  TALENTSCOPE_AUTH_DIAGNOSTICS: true,
  dispatchEvent: () => true
};
globalThis.CustomEvent ||= class CustomEvent { constructor(type, init = {}) { this.type = type; this.detail = init.detail; } };

const { syncFirebaseUser, ProfileSyncError } = await import('../src/auth/auth-api.js');
const { coalesceProfileSync } = await import('../src/auth/profile-sync-coordinator.js');
const {
  AUTH_PROFILE_SYNC_TIMEOUT_MS,
  diagnosticRequestSignal,
  getAuthDiagnosticSnapshot,
  logAuthTrace
} = await import('../src/auth/auth-trace.js');
const traceOutput = [];
const originalConsoleInfo = console.info;
console.info = (...args) => traceOutput.push(args.join(' '));

function user() {
  return { uid: 'uid-test', getIdToken: async () => 'test-token-value' };
}

test('profile sync sends one authenticated request and accepts only matching UID', async () => {
  const previousFetch = globalThis.fetch;
  let requestCount = 0;
  globalThis.fetch = async (url, options) => {
    requestCount += 1;
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/auth/sync');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.Authorization, 'Bearer test-token-value');
    assert.match(options.headers['X-Auth-Diagnostic-Id'], /^authreq_[a-z0-9_-]+$/i);
    assert.equal(options.signal instanceof AbortSignal, true);
    assert.equal(options.signal.aborted, false);
    return Response.json({ authenticated: true, user: { uid: 'uid-test', onboarding_completed: false } });
  };
  try {
    const profile = await syncFirebaseUser(user());
    assert.equal(profile.uid, 'uid-test');
    assert.equal(requestCount, 1);
    const snapshot = getAuthDiagnosticSnapshot();
    assert.ok(snapshot.events.some(event => event.event === 'PROFILE_SYNC_REQUEST_SENT' && event.request_id));
    assert.ok(snapshot.events.some(event => event.event === 'PROFILE_SYNC_SUCCESS'));
    assert.doesNotMatch(JSON.stringify(snapshot), /test-token-value|Bearer|email-redacted/);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('profile sync classifies network rejection, connection refusal, and timeout', async () => {
  const previousFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
    await assert.rejects(syncFirebaseUser(user()), error => error instanceof ProfileSyncError && error.kind === 'NETWORK_ERROR');
    assert.ok(getAuthDiagnosticSnapshot().events.some(event => event.event === 'PROFILE_SYNC_NETWORK_ERROR' && event.error_name === 'TypeError'));
    const refused = new TypeError('connect ECONNREFUSED');
    refused.cause = { code: 'ECONNREFUSED' };
    globalThis.fetch = async () => { throw refused; };
    await assert.rejects(syncFirebaseUser(user()), error => error instanceof ProfileSyncError && error.kind === 'CONNECTION_REFUSED');
    globalThis.fetch = async () => { throw new DOMException('The operation timed out.', 'TimeoutError'); };
    await assert.rejects(syncFirebaseUser(user()), error => error instanceof ProfileSyncError && error.kind === 'TIMEOUT');
    assert.ok(getAuthDiagnosticSnapshot().events.some(event => event.event === 'PROFILE_SYNC_TIMEOUT'));
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('profile sync distinguishes protected API and backend status failures', async () => {
  const previousFetch = globalThis.fetch;
  const cases = [
    [401, null, 'AUTHENTICATION_FAILED'],
    [403, null, 'EMAIL_NOT_VERIFIED'],
    [404, null, 'ENDPOINT_NOT_FOUND'],
    [422, null, 'VALIDATION_ERROR'],
    [429, null, 'RATE_LIMITED'],
    [500, null, 'BACKEND_INTERNAL_ERROR'],
    [502, null, 'BACKEND_UPSTREAM_ERROR'],
    [503, { detail: { error_code: 'firestore_unavailable' } }, 'FIRESTORE_UNAVAILABLE'],
    [503, { detail: { error_code: 'auth_verification_unavailable' } }, 'AUTHENTICATION_SERVICE_UNAVAILABLE']
  ];
  try {
    for (const [status, body, kind] of cases) {
      globalThis.fetch = async () => new Response(JSON.stringify(body || {}), {
        status,
        headers: { 'Content-Type': 'application/json' }
      });
      await assert.rejects(syncFirebaseUser(user()), error => error instanceof ProfileSyncError && error.kind === kind);
    }
    assert.ok(getAuthDiagnosticSnapshot().events.some(event => event.event === 'PROFILE_SYNC_HTTP_ERROR' && event.status === 401));
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('same UID and profile concurrent syncs share one operation and clear after completion', async () => {
  const inFlight = new Map();
  let complete;
  let calls = 0;
  const operation = () => {
    calls += 1;
    return new Promise(resolve => { complete = resolve; });
  };
  const first = coalesceProfileSync(inFlight, 'same-uid', {}, operation);
  const second = coalesceProfileSync(inFlight, 'same-uid', {}, operation);
  assert.equal(first.coalesced, false);
  assert.equal(second.coalesced, true);
  assert.equal(first.promise, second.promise);
  await Promise.resolve();
  assert.equal(calls, 1);
  complete({ uid: 'same-uid' });
  await Promise.all([first.promise, second.promise]);
  assert.equal(inFlight.size, 0);
});

test('development diagnostics carry timing but filter token-like values', async () => {
  assert.equal(AUTH_PROFILE_SYNC_TIMEOUT_MS, 10_000);
  assert.equal(diagnosticRequestSignal() instanceof AbortSignal, true);
  logAuthTrace('security_filter_test', {
    duration_ms: 1,
    id_token: 'must-not-appear',
    authorization: 'must-not-appear',
    email: 'private@example.test',
    error_message: 'Failed to fetch: bearer private-token'
  });
  const emitted = traceOutput.join('\n');
  assert.match(emitted, /AUTH_DIAGNOSTIC/);
  assert.doesNotMatch(emitted, /test-token-value|must-not-appear|private@example\.test|private-token|authorization":|id_token":/i);
});

let passed = 0;
for (const { name, run } of registeredTests) {
  await run();
  passed += 1;
  console.log(`PASS ${name}`);
}
console.log(`AUTH TESTS PASSED=${passed} FAILED=0`);
console.info = originalConsoleInfo;
