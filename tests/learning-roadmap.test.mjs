import assert from 'node:assert/strict';

const values = new Map([
  ['talentscope-learning-roadmap-v1', JSON.stringify({ title: 'Older browser roadmap', progress: 42 })],
  ['talentscope-roadmap-state-v1', JSON.stringify({ title: 'Older browser roadmap', progress: 42 })]
]);
let writes = 0;
globalThis.localStorage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => { writes += 1; values.set(key, String(value)); },
  removeItem: key => { writes += 1; values.delete(key); }
};
globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.window = {
  location: { hostname: 'localhost', origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
  talentscopeGetAuthToken: async () => 'firebase-roadmap-token'
};
globalThis.document = {};

const { loadPersonalizedRoadmap, deletePersonalizedRoadmap, previewLearningPlan, approveLearningPlan, discardLearningPlanDraft, updateLearningPlanDraft, updateRoadmapMilestone, searchRoadmapOptions } = await import('../src/api/roadmap-client.js');
const { renderLearningWorkspaceHTML, renderPersonalizedRoadmap, renderLearningAssessment, renderRoadmapWizardModal, renderDeleteRoadmapModal } = await import('../src/pages/individual/learning/Learning.js');
const originalFetch = globalThis.fetch;
try {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ roadmap: null, created: false });
  };
  assert.deepEqual(await loadPersonalizedRoadmap(), { roadmap: null, created: false });
  assert.match(request.url, /\/api\/v1\/learning\/roadmap$/);
  assert.equal(request.options.headers.Authorization, 'Bearer firebase-roadmap-token');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ roadmap: { roadmap_id: 'r1' }, created: true });
  };
  await previewLearningPlan({ plan_type: 'skill', skills: [{ name: 'Python' }], target_duration_days: 30 });
  assert.equal(request.options.method, 'POST');
  assert.match(request.url, /\/roadmap\/preview$/);
  assert.deepEqual(JSON.parse(request.options.body), { plan_type: 'skill', skills: [{ name: 'Python' }], target_duration_days: 30 });

  await approveLearningPlan('draft-1');
  assert.equal(request.options.method, 'POST');
  assert.match(request.url, /\/roadmap\/drafts\/draft-1\/approve$/);

  await discardLearningPlanDraft('draft-2');
  assert.equal(request.options.method, 'DELETE');
  assert.match(request.url, /\/roadmap\/drafts\/draft-2$/);

  await updateLearningPlanDraft('draft-3', { target_duration_days: 30, weekly_learning_time: '2-4 hours', starting_level: 'advanced', stages: [] });
  assert.equal(request.options.method, 'PATCH');
  assert.match(request.url, /\/roadmap\/drafts\/draft-3$/);
  assert.deepEqual(JSON.parse(request.options.body), { target_duration_days: 30, weekly_learning_time: '2-4 hours', starting_level: 'advanced', stages: [] });

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ roadmap: { roadmap_id: 'r1' } });
  };
  await updateRoadmapMilestone('m1', 'completed');
  assert.equal(request.options.method, 'PATCH');
  assert.deepEqual(JSON.parse(request.options.body), { status: 'completed' });

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return new Response(null, { status: 204 });
  };
  await deletePersonalizedRoadmap();
  assert.equal(request.options.method, 'DELETE');
  assert.match(request.url, /\/api\/v1\/learning\/roadmap$/);
  assert.equal(request.options.headers.Authorization, 'Bearer firebase-roadmap-token');

  globalThis.fetch = async (url, options) => {
    request = { url: String(url), options };
    return Response.json({ roles: ['Software Developer'] });
  };
  assert.deepEqual(await searchRoadmapOptions('role', 'software'), { roles: ['Software Developer'] });
  assert.match(request.url, /\/roadmap\/options\?kind=role&query=software/);

  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'expired' }), { status: 401 });
  await assert.rejects(loadPersonalizedRoadmap(), error => error.kind === 'auth');
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: {
    error_code: 'auth_verification_unavailable', message: 'Authentication verification is temporarily unavailable.'
  } }), { status: 503 });
  await assert.rejects(loadPersonalizedRoadmap(), error => error.status === 503 && /Authentication verification is temporarily unavailable/.test(error.message));

  const empty = renderPersonalizedRoadmap({ roadmapStatus: 'loaded', personalizedRoadmap: null, profileContext: { skills: [], target_role: null } });
  assert.equal(empty, '');
  const error = renderPersonalizedRoadmap({ roadmapStatus: 'error', roadmapError: 'Firestore unavailable' });
  assert.match(error, /Firestore unavailable/);
  const loading = renderPersonalizedRoadmap({ roadmapStatus: 'loading' });
  assert.match(loading, /role="status"/);
  const assessmentUnavailable = renderLearningAssessment({ assessmentStatus: 'loaded', assessments: [] });
  assert.match(assessmentUnavailable, /awaiting review/);
  assert.match(assessmentUnavailable, /initial roadmap is ready/);
  const perSkillEvidence = renderPersonalizedRoadmap({
    roadmapStatus: 'loaded',
    personalizedRoadmap: {
      roadmap_id: 'r1', title: 'Initial plan', summary: 'Based on your profile.', completed_count: 0,
      relationship_note: 'Role associations are context only.', assessment_evidence_status: 'not_available',
      milestones: [{
        milestone_id: 'm1', title: 'Practice Python', skill_name: 'Python', skill_id: 'python',
        explanation: 'Try a small task.', completion_criterion: 'Check your result.',
        effort: { basis: 'Gemini suggested estimate.', estimated_minutes: 45 }, assessment_evidence: { status: 'not_available' },
        resources: [], status: 'not_started'
      }]
    }
  });
  assert.match(perSkillEvidence, /Assessment: Not assessed yet/);
  assert.match(perSkillEvidence, /45 min suggested estimate/);
  assert.match(perSkillEvidence, /id="lpDeleteRoadmapBtn"/);
  assert.match(perSkillEvidence, /data-lucide="trash-2"/);
  assert.match(perSkillEvidence, /Delete Plan/);

  const modalHtml = renderDeleteRoadmapModal({
    confirmingDeleteRoadmap: true,
    personalizedRoadmap: { title: 'Python plan' }
  });
  assert.match(modalHtml, /role="alertdialog"/);
  assert.match(modalHtml, /Delete "Python plan"\?/);
  assert.match(modalHtml, /id="lpConfirmDeleteRoadmapBtn"/);
  assert.match(modalHtml, /id="lpCancelDeleteRoadmapBtn"/);

  const unknownEvidence = renderPersonalizedRoadmap({
    roadmapStatus: 'loaded',
    personalizedRoadmap: {
      roadmap_id: 'r2', title: 'Initial plan', summary: 'Based on your profile.', completed_count: 0,
      relationship_note: 'Role associations are context only.', assessment_evidence_status: 'unknown',
      milestones: [{
        milestone_id: 'm2', title: 'Practice Python', skill_name: 'Python', skill_id: 'python',
        explanation: 'Try a small task.', completion_criterion: 'Check your result.',
        effort: { basis: 'No estimate.' }, assessment_evidence: { status: 'unknown' },
        resources: [], status: 'not_started'
      }]
    }
  });
  assert.match(unknownEvidence, /Assessment history could not be checked/);
  assert.match(unknownEvidence, /Assessment evidence unknown/);

  const { MINIMUM_ROADMAP_ASSESSMENT_SCORE } = await import('../src/pages/individual/learning/Learning.js');
  assert.equal(MINIMUM_ROADMAP_ASSESSMENT_SCORE, 70);

  const initialPage = renderLearningWorkspaceHTML();
  assert.match(initialPage, /YOUR STARTING POINT/);
  assert.match(initialPage, /YOUR GOAL/);
  assert.match(initialPage, /MY LEARNING/);
  assert.match(initialPage, /PROGRESS/);
  assert.match(initialPage, /Create Roadmap/);
  assert.doesNotMatch(initialPage, /role="tablist"/);
  assert.doesNotMatch(initialPage, /42%|Older browser roadmap|82%|Benchmark completed/);
  assert.equal(writes, 0);
  assert.equal(JSON.parse(values.get('talentscope-learning-roadmap-v1')).progress, 42);

  const choiceStep = renderRoadmapWizardModal({ planStep: 1, planForm: { plan_type: 'skill' }, planBusy: false });
  assert.match(choiceStep, /role="dialog"/);
  assert.match(choiceStep, /aria-modal="true"/);
  assert.match(choiceStep, /Learn a Skill/);
  assert.match(choiceStep, /Prepare for a Job/);
  assert.doesNotMatch(choiceStep, /Combine a Skill and Role/);
  assert.doesNotMatch(choiceStep, /Combine both|Step 1 of 4/);
  const roleStep = renderRoadmapWizardModal({
    planStep: 2, planForm: { plan_type: 'role', target_role: 'Designer', target_duration_days: 60 },
    profileContext: { skills: [{ name: 'CSS', self_reported_level: 'Beginner', assessment_status: 'not_assessed' }] }
  });
  assert.match(roleStep, /Target job role/);
  assert.match(roleStep, /value="Designer"/);
  assert.match(roleStep, /Target duration in days/);
  assert.match(roleStep, />Back</);
  assert.match(roleStep, />Create preview</);
  assert.doesNotMatch(roleStep, />Cancel</);
  assert.doesNotMatch(roleStep.match(/<button[^>]*id="lpNextPlan"[^>]*>/)?.[0] || '', /disabled/);
  const retryStep = renderRoadmapWizardModal({
    planStep: 2, planWizardError: 'The service could not be reached. Retry.',
    planForm: { plan_type: 'skill', skill_name: 'C', target_duration_days: 60 }
  });
  assert.match(retryStep, /role="alert"[^>]*>The service could not be reached\. Retry\./);
  assert.match(retryStep, />Retry preview</);
  assert.match(retryStep, /value="C"/);
  assert.match(retryStep, /value="60"/);
  const skillStep = renderRoadmapWizardModal({ planStep: 2, planForm: { plan_type: 'skill', skill_name: 'Python', target_duration_days: 30, preferences: ['Practice'] }, profileContext: { skill_catalog: [{ name: 'Python' }] } });
  assert.match(skillStep, /Skill to learn/);
  assert.match(skillStep, /<option value="Python">/);
  assert.match(skillStep, /value="30"/);
  assert.match(skillStep, /name="learning_preferences" value="Practice" checked/);
  const notSureStep = renderRoadmapWizardModal({ planStep: 2, planForm: { plan_type: 'skill', skill_name: 'Python', starting_level: 'not sure' } });
  assert.match(notSureStep, /<option value="not sure" selected>Not sure/);
  const previewStep = renderRoadmapWizardModal({
    planStep: 3, planForm: { plan_type: 'skill', skill_name: 'Python', target_duration_days: 30 }, planDraft: { roadmap: {
      title: 'Python plan', summary: 'Reference-based plan.', plan_type: 'skill',
      plan_goal: null, target_duration_days: 30,
      target_role: null, profile_context: { weekly_learning_time: null }, milestones: [{
        title: 'Practice Python', skill_name: 'Python', skill_source: 'user_selected',
        assessment_evidence: { status: 'not_available' }, explanation: 'Build a small script.',
        completion_criterion: 'Run the script and inspect output.', resources: [{
          title: 'Official Python docs', url: 'https://docs.python.org/3/', verification_status: 'verified_official', provenance: 'Python Software Foundation'
        }]
      }]
    } }, assessments: []
  });
  assert.match(previewStep, /30 days|30-day/);
  assert.match(previewStep, /Official Python docs/);
  assert.match(previewStep, /Accept Roadmap/);
  assert.doesNotMatch(previewStep, /Edit roadmap/);
  assert.doesNotMatch(previewStep, /Edit setup/);
  assert.match(previewStep, /Learning outcomes/);
  assert.match(previewStep, /Starting level/);
  assert.doesNotMatch(previewStep, /Stage 1TitleLearning outcomesPractice taskRemove stage/);
  assert.doesNotMatch(previewStep, /Save changes/);

  // Dedicated lesson workspace verification
  const lessonPage = renderLearningWorkspaceHTML({
    activeLessonId: 'm1',
    personalizedRoadmap: {
      roadmap_id: 'r1', title: 'Python plan',
      milestones: [{
        milestone_id: 'm1', title: 'Practice Python', skill_name: 'Python',
        explanation: 'Build a small script.', resources: [{ title: 'Docs', url: 'https://docs.python.org' }]
      }]
    }
  });
  assert.match(lessonPage, /lp-dedicated-lesson-workspace/);
  assert.match(lessonPage, /Practice Python/);
  assert.match(lessonPage, /Back to Roadmap/);
} finally {
  globalThis.fetch = originalFetch;
}

console.log('LEARNING ROADMAP FRONTEND TESTS: 10 passed');
