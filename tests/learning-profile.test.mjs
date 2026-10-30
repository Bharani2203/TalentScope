import assert from 'node:assert/strict';

const localStorageValues = new Map();
globalThis.localStorage = {
  getItem: key => localStorageValues.get(key) ?? null,
  setItem: (key, value) => localStorageValues.set(key, String(value)),
  removeItem: key => localStorageValues.delete(key),
  clear: () => localStorageValues.clear()
};
globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  talentscopeGetAuthToken: async () => 'firebase-test-token'
};
globalThis.document = {};

const { loadIndividualOnboardingProfile, OnboardingApiError } = await import('../src/onboarding/onboarding-api.js');
const { normalizeLearningProfile, loadLearningProfileContext } = await import('../src/pages/individual/learning/learning-profile.js');
const { renderLearningWorkspaceHTML, renderLearningProfileContext } = await import('../src/pages/individual/learning/Learning.js');

const catalog = { skills: [
  { skill_id: 'python', name: 'Python', aliases: ['py'] },
  { skill_id: 'javascript', name: 'JavaScript', aliases: ['js'] }
] };

const completeProfileResponse = {
  display_name: 'Taylor Learner',
  onboarding: { completed: false, current_step: 8, completed_steps: [1, 2, 3, 4, 5, 6, 7] },
  profile: {
    basic_profile: { name: 'Taylor', city: 'Chennai', country: 'India' },
    experience: { experience: '1–2 years', studyField: 'Computer Science' },
    skills: { selected_skills: ['Python', 'Py', 'My Handmade Tool'], skill_levels: { Python: 'Comfortable', 'My Handmade Tool': 'Beginner' } },
    career: { career_goals: ['Get my first job'], target_roles: ['Backend Developer'] },
    interests: ['Software Development'],
    learning_preferences: ['Hands-on practice', 'Videos'],
    work_preferences: { learning_time: '2–5 hours', work_preference: 'Remote' }
  },
  answers: {}
};

// Authenticated loading uses the existing profile endpoint and current Firebase token.
{
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json(completeProfileResponse);
  };
  try {
    const response = await loadIndividualOnboardingProfile();
    assert.equal(response.profile.basic_profile.name, 'Taylor');
    assert.match(request.url, /\/api\/v1\/onboarding\/individual\/profile$/);
    assert.equal(request.options.headers.Authorization, 'Bearer firebase-test-token');
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// Canonical skills normalize exactly; unsupported manual names remain intact.
{
  const context = normalizeLearningProfile(completeProfileResponse, catalog);
  assert.deepEqual(context.skills.map(skill => [skill.skill_id, skill.name]), [
    ['python', 'Python'],
    [null, 'My Handmade Tool']
  ]);
  assert.equal(context.skills[0].self_reported_level, 'Comfortable');
  assert.equal(context.skills[0].level_source, 'self_reported');
  assert.equal(context.skills[0].assessment_level, null);
  assert.equal(context.skills[0].assessment_status, 'not_assessed');
  assert.equal(context.skills[1].self_reported_level, 'Beginner');
  assert.equal(context.target_role, 'Backend Developer');
  assert.deepEqual(context.career_goals, ['Get my first job']);
  assert.deepEqual(context.interests, ['Software Development']);
  assert.deepEqual(context.learning_preferences, ['Hands-on practice', 'Videos']);
  assert.equal(context.experience, '1–2 years');
  assert.equal(context.location, 'Chennai, India');
  assert.equal(context.weekly_learning_time, '2–5 hours');
  assert.equal(context.onboarding.completed, false);
}

// Empty or partial profiles remain safe, and registry/network failure preserves skill names.
{
  const empty = normalizeLearningProfile({ profile: {}, answers: {}, onboarding: {} }, { skills: [] });
  assert.deepEqual(empty.skills, []);
  assert.deepEqual(empty.career_goals, []);
  assert.equal(empty.target_role, null);
  assert.equal(empty.skill_registry_available, false);

  const context = await loadLearningProfileContext({
    loadProfile: async () => completeProfileResponse,
    loadCatalog: async () => { throw new Error('catalog unavailable'); }
  });
  assert.equal(context.skills[0].mapping_status, 'unverified');
  assert.equal(context.skills[0].name, 'Python');
  assert.equal(context.skill_registry_available, false);
}

// Authentication and transport failures are typed for a recoverable Learning Page state.
{
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'unauthorized' }), { status: 401 });
    await assert.rejects(loadIndividualOnboardingProfile(), error => (
      error instanceof OnboardingApiError && error.status === 401 && error.kind === 'AUTHENTICATION_FAILED'
    ));
    globalThis.fetch = async () => { throw new TypeError('offline'); };
    await assert.rejects(loadIndividualOnboardingProfile(), error => (
      error instanceof OnboardingApiError && error.kind === 'NETWORK_ERROR'
    ));
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// Profile rendering labels self-reporting and never presents the old demo roadmap or scores.
{
  const context = normalizeLearningProfile(completeProfileResponse, catalog);
  const markup = renderLearningProfileContext(context, 'loaded');
  assert.match(markup, /Self-reported: Comfortable/);
  assert.match(markup, /Assessment: unknown/);
  const evidenceMarkup = renderLearningProfileContext(context, 'loaded', null, {
    milestones: [{ skill_id: 'python', assessment_evidence: { status: 'available_provisional' } }]
  }, 'loaded');
  assert.match(evidenceMarkup, /Assessment: provisional evidence/);
  assert.match(markup, /My Handmade Tool/);

  const workspace = renderLearningWorkspaceHTML();
  assert.match(workspace, /Loading saved profile/);
  assert.doesNotMatch(workspace, /Python Advanced Technical Benchmark|AI Engineer Role Prep|82%|85th percentile/);
  assert.match(renderLearningProfileContext(null, 'error', { status: 401 }), /sign-in session could not be verified/);
  assert.match(renderLearningProfileContext(null, 'error', { kind: 'NETWORK_ERROR' }), /could not be loaded/);
}

console.log('LEARNING PROFILE INTEGRATION TESTS: 5 passed');
