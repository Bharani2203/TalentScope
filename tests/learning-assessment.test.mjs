import assert from 'node:assert/strict';

globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  talentscopeGetAuthToken: async () => 'verified-firebase-token'
};
globalThis.document = {};
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };

const { loadAssessmentHistory, loadAvailableAssessments, startSkillAssessment, submitSkillAssessment } = await import('../src/api/assessment-client.js');
const originalFetch = globalThis.fetch;
try {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ assessments: [] });
  };
  assert.deepEqual(await loadAvailableAssessments(), { assessments: [] });
  assert.match(request.url, /\/api\/v1\/learning\/assessments$/);
  assert.equal(request.options.headers.Authorization, 'Bearer verified-firebase-token');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ attempts: [], count: 0 });
  };
  assert.deepEqual(await loadAssessmentHistory(), { attempts: [], count: 0 });
  assert.match(request.url, /\/api\/v1\/learning\/assessments\/attempts\?limit=20$/);

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ attempt_id: 'attempt-id', questions: [] });
  };
  await startSkillAssessment('python', { questionCount: 4 });
  assert.match(request.url, /\/python\/attempts\?question_count=4$/);
  assert.equal(request.options.method, 'POST');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ status: 'completed' });
  };
  await submitSkillAssessment('attempt-id', { q1: 'b' });
  assert.match(request.url, /\/attempts\/attempt-id\/submit$/);
  assert.deepEqual(JSON.parse(request.options.body), { answers: { q1: { answer: 'b' } } });

  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Sign-in required' }), { status: 401 });
  await assert.rejects(loadAvailableAssessments(), error => error.kind === 'auth' && error.status === 401);

  const { renderLearningWorkspaceHTML, renderLearningAssessment, renderAssessmentHistory } = await import('../src/pages/individual/learning/Learning.js');
  const page = renderLearningWorkspaceHTML();
  assert.match(page, /Entrance skill assessment/);
  assert.match(page, /Loading available assessments/);
  assert.doesNotMatch(page, /88%|Benchmark completed|Python Backend Advancement/);
  const unavailable = renderLearningAssessment({ assessmentStatus: 'loaded', assessments: [] });
  assert.match(unavailable, /Assessments are not available yet/);
  assert.match(unavailable, /awaiting review/);
  assert.match(unavailable, /initial roadmap is ready/);
  const errorState = renderLearningAssessment({ assessmentStatus: 'error', assessmentError: 'Session expired' });
  assert.match(errorState, /Session expired/);
  const history = renderAssessmentHistory({ assessmentHistoryStatus: 'loaded', assessmentHistory: [
    { skill_id: 'python', status: 'completed', score: 3, max_score: 4, percentage: 75, completed_at: '2026-10-01T00:00:00Z' },
    { skill_id: 'javascript', status: 'in_progress', started_at: '2026-10-02T00:00:00Z' }
  ] });
  assert.match(history, /Provisional result: 3 \/ 4 \(75%\)/);
  assert.match(history, /Assessment pending/);
  const retained = renderAssessmentHistory({ assessmentHistoryStatus: 'error', assessmentHistoryError: 'offline', assessmentHistory: [
    { skill_id: 'python', status: 'completed', score: 3, max_score: 4, percentage: 75 }
  ] });
  assert.match(retained, /Previously loaded results are retained/);
  assert.match(retained, /Provisional result: 3 \/ 4 \(75%\)/);
} finally {
  globalThis.fetch = originalFetch;
}

console.log('LEARNING ASSESSMENT FRONTEND TESTS: 5 passed');
