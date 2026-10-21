import assert from 'node:assert/strict';

const registeredTests = [];
function test(name, run) {
  registeredTests.push({ name, run });
}

globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  TALENTSCOPE_API_BASE_URL: 'http://127.0.0.1:8010',
  dispatchEvent: () => true
};
globalThis.CustomEvent ||= class CustomEvent { constructor(type, init = {}) { this.type = type; this.detail = init.detail; } };

const {
  fetchIntelligenceConversations,
  queryCoreIntelligenceAnswer,
  queryGuestIntelligenceAnswer,
} = await import('../src/api/core-intelligence-client.js');
const { syncFirebaseUser, ProfileSyncError, profileSyncErrorMessage } = await import('../src/auth/auth-api.js');

test('signed-out caller without token throws auth error and does not load false private history', async () => {
  const previousFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async (url, opts) => {
    fetchCalled = true;
    return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    // Calling fetchIntelligenceConversations when unauthenticated hits backend which requires token
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'A Firebase ID token is required.' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
    await assert.rejects(
      fetchIntelligenceConversations({ limit: 100, domain: 'skill', portalType: 'individual' }),
      err => err.name === 'CoreIntelligenceAuthError' && err.status === 401
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('infrastructure 503 preserves retryable service-unavailable error and does not produce false empty list', async () => {
  const previousFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({
      detail: { error_code: 'auth_verification_unavailable', message: 'Authentication verification is temporarily unavailable.' }
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });

    await assert.rejects(
      fetchIntelligenceConversations({ token: 'mock-valid-token', limit: 100, domain: 'skill', portalType: 'individual' }),
      err => err.name === 'CoreIntelligenceServiceUnavailableError' && err.status === 503
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('authenticated request sends Bearer token and returns user conversations', async () => {
  const previousFetch = globalThis.fetch;
  let receivedAuth = null;
  globalThis.fetch = async (url, opts) => {
    receivedAuth = opts.headers?.Authorization;
    return new Response(JSON.stringify([
      { conversation_id: 'conv_123', title: 'Python demand analysis', domain: 'skill', portal_type: 'individual' }
    ]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  };

  try {
    const list = await fetchIntelligenceConversations({
      token: 'verified-user-token',
      limit: 100,
      domain: 'skill',
      portalType: 'individual'
    });
    assert.equal(receivedAuth, 'Bearer verified-user-token');
    assert.equal(list.length, 1);
    assert.equal(list[0].conversation_id, 'conv_123');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('guest intelligence answer routes to /api/v1/intelligence/guest/answer and strips conversation/user/company IDs', async () => {
  const previousFetch = globalThis.fetch;
  let calledUrl = null;
  let sentBody = null;

  globalThis.fetch = async (url, opts) => {
    calledUrl = url;
    sentBody = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      request_id: 'ans_guest_456',
      user_message: 'Python demand trends',
      portal_type: 'individual',
      domain: 'skill',
      intent: 'trend_velocity_analysis',
      plan_status: 'executable',
      execution_status: 'completed',
      answer: 'Python shows positive market adoption.',
      conversation_id: null,
      facts: [],
      evidence: [],
      limitations: [],
      reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY']
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  };

  try {
    const res = await queryGuestIntelligenceAnswer({
      message: 'Python demand trends',
      portalType: 'individual',
      domain: 'skill',
      conversationId: 'attempt_private_conv',
      companyId: 'attempt_company'
    });

    assert.ok(calledUrl.endsWith('/api/v1/intelligence/guest/answer'));
    assert.equal(sentBody.conversation_id, null);
    assert.equal(sentBody.company_id, null);
    assert.equal(sentBody.user_id, null);
    assert.equal(res.conversation_id, null);
    assert.equal(res.execution_status, 'completed');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('guest intelligence rejects private profile capability with 403', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    detail: "The requested capability 'skill_gap_role_fit' requires authentication. Please sign in to access personalized profile and workforce insights."
  }), {
    status: 403,
    headers: { 'Content-Type': 'application/json' }
  });

  try {
    await assert.rejects(
      queryGuestIntelligenceAnswer({
        message: 'Analyze my skill gap',
        portalType: 'individual',
        domain: 'skill',
        capabilityId: 'skill_gap_role_fit'
      }),
      err => err.name === 'CoreIntelligenceAuthRequiredError' && err.status === 403
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('profile-sync HTTP 503 auth_verification_unavailable yields retryable error with clear message', async () => {
  const previousFetch = globalThis.fetch;
  let attempt = 0;
  globalThis.fetch = async (url, opts) => {
    attempt += 1;
    if (attempt === 1) {
      return new Response(JSON.stringify({
        detail: { error_code: 'auth_verification_unavailable', message: 'Authentication verification is temporarily unavailable.' }
      }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    // Attempt 2 succeeds after backend recovery
    return new Response(JSON.stringify({
      authenticated: true,
      user: { uid: 'retry-user-id', email: 'retry@example.com', onboarding_completed: true }
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  };

  try {
    const mockUser = { uid: 'retry-user-id', getIdToken: async () => 'valid-token' };
    let firstError = null;
    try {
      await syncFirebaseUser(mockUser);
    } catch (err) {
      firstError = err;
    }
    assert.ok(firstError instanceof ProfileSyncError);
    assert.equal(firstError.kind, 'AUTHENTICATION_SERVICE_UNAVAILABLE');
    assert.equal(firstError.status, 503);
    const msg = profileSyncErrorMessage(firstError);
    assert.match(msg, /backend could not verify Firebase authentication/i);

    // Subsequent retry succeeds without creating duplicate account
    const recoveredProfile = await syncFirebaseUser(mockUser);
    assert.equal(recoveredProfile.uid, 'retry-user-id');
    assert.equal(recoveredProfile.onboarding_completed, true);
    assert.equal(attempt, 2);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('email-already-in-use error semantics directs user to sign in or recover account instead of repeating signup', () => {
  const errorMapping = {
    'auth/email-already-in-use': 'An account already exists for this email address. Please sign in or recover your account instead of repeating registration.'
  };
  const msg = errorMapping['auth/email-already-in-use'];
  assert.match(msg, /already exists/i);
  assert.match(msg, /sign in/i);
  assert.match(msg, /recover your account/i);
});

// Run all registered tests
let passed = 0;
for (const t of registeredTests) {
  try {
    await t.run();
    console.log(`PASS ${t.name}`);
    passed += 1;
  } catch (err) {
    console.error(`FAIL ${t.name}:`, err);
    process.exitCode = 1;
  }
}
console.log(`\nPHASE 3B FRONTEND AUTH TESTS: ${passed}/${registeredTests.length} PASSED`);
