import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  adaptCoreIntelligenceAnswerResponse,
  buildCoreIntelligenceRequest,
  normalizeDomainKey,
  normalizeAnswerTimeRange
} from '../src/api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../src/components/common/IntelligenceEvidencePanel.js';
import { renderConversationAnswer } from '../src/components/common/ConversationAnswer.js';

async function runFrontendCompatibilityTests() {
  console.log('--- STARTING V2 FRONTEND COMPATIBILITY TESTS ---');

  // Load actual V2 engine response fixtures
  const rawFixtures = JSON.parse(
    await readFile(new URL('./v2_response_fixtures.json', import.meta.url), 'utf-8')
  );

  // 1. Test Query 1: What is the demand trend for Python?
  const q1Raw = rawFixtures.q1_demand_trend_python;
  assert.ok(q1Raw, 'q1 fixture must exist');
  const q1Adapted = adaptCoreIntelligenceAnswerResponse(q1Raw);
  assert.equal(q1Adapted.domain, 'skill');
  assert.equal(q1Adapted.execution_status, 'completed');
  assert.equal(q1Adapted.executed_primary_capability, 'skill_demand_trends');
  assert.ok(q1Adapted.facts.length >= 1, 'Must have at least one fact');
  assert.equal(q1Adapted.facts[0].metric_name, 'num_pushers');
  assert.equal(q1Adapted.facts[0].unit, 'pushers');
  assert.ok(q1Adapted.evidence.length >= 1, 'Must have evidence');
  const q1EvidenceHtml = renderIntelligenceEvidencePanel(q1Adapted);
  assert.ok(q1EvidenceHtml.includes('GitHub Innovation Graph'), 'Must render GitHub evidence source');
  assert.ok(q1EvidenceHtml.includes('pushers'), 'Must render pushers unit');
  const q1AnswerHtml = renderConversationAnswer(q1Adapted, text => text);
  assert.ok(q1AnswerHtml.includes('Developer adoption for Python'), 'Must render answer headline');

  // 2. Test Query 2: Which skills are relevant to a Python developer role?
  const q2Raw = rawFixtures.q2_python_developer_skills;
  const q2Adapted = adaptCoreIntelligenceAnswerResponse(q2Raw);
  assert.equal(q2Adapted.domain, 'job');
  assert.equal(q2Adapted.execution_status, 'completed');
  assert.equal(q2Adapted.executed_primary_capability, 'job_role_requirements');
  assert.ok(q2Adapted.facts.length >= 1);
  assert.equal(q2Adapted.facts[0].source, 'O*NET 28.0');
  const q2EvidenceHtml = renderIntelligenceEvidencePanel(q2Adapted);
  assert.ok(q2EvidenceHtml.includes('O*NET'), 'Must render O*NET reference evidence');

  // 3. Test Query 3: What jobs are available in India?
  const q3Raw = rawFixtures.q3_jobs_in_india;
  const q3Adapted = adaptCoreIntelligenceAnswerResponse(q3Raw);
  assert.equal(q3Adapted.domain, 'job');
  assert.equal(q3Adapted.execution_status, 'completed');
  assert.equal(q3Adapted.executed_primary_capability, 'job_verified_postings');
  assert.equal(q3Adapted.facts[0].metric_value, 0, 'Must truthfully report 0 postings without hallucination');
  assert.ok(q3Adapted.answer.includes('0 verified postings'), 'Answer must state 0 postings');
  assert.ok(q3Adapted.answer.includes('disabled by default'), 'Answer must explain disabled collector');

  // 4. Test Query 4: What skills are mentioned in this job description?
  const q4Raw = rawFixtures.q4_skills_in_job_description;
  const q4Adapted = adaptCoreIntelligenceAnswerResponse(q4Raw);
  assert.equal(q4Adapted.domain, 'job');
  assert.equal(q4Adapted.executed_primary_capability, 'job_role_requirements');
  assert.ok(q4Adapted.evidence.length >= 1);

  // 5. Test Query 5: What should I learn next for my target role?
  const q5Raw = rawFixtures.q5_what_should_i_learn_next;
  const q5Adapted = adaptCoreIntelligenceAnswerResponse(q5Raw);
  assert.equal(q5Adapted.domain, 'job');
  assert.equal(q5Adapted.executed_primary_capability, 'job_preparation_actions');
  assert.ok(q5Adapted.answer.includes('Practice Tasks'), 'Must render deterministic practice tasks');
  assert.ok(!q5Adapted.answer.includes('http'), 'Must not contain invented course URLs');

  // 6. Test Query 6: Show my historical skill signals.
  const q6Raw = rawFixtures.q6_historical_skill_signals;
  const q6Adapted = adaptCoreIntelligenceAnswerResponse(q6Raw);
  assert.equal(q6Adapted.domain, 'skill');
  assert.equal(q6Adapted.executed_primary_capability, 'skill_historical_signals');
  assert.ok(q6Adapted.facts.length >= 1);
  assert.equal(q6Adapted.facts[0].metric_name, 'historical_span');
  assert.ok(q6Adapted.answer.includes('GitHub Innovation Graph') || q6Adapted.answer.includes('quarters'));

  // 7. Verify Client Request Normalization
  const req = buildCoreIntelligenceRequest({
    domain: 'market',
    timeRange: '1 year',
    selectedSkills: ['Python', 'Docker']
  });
  assert.equal(req.domain, 'market');
  assert.equal(req.time_range, '12m');
  assert.deepEqual(req.selected_skills, ['Python', 'Docker']);

  console.log('ALL V2 FRONTEND COMPATIBILITY TESTS PASSED (7/7)!');
}

runFrontendCompatibilityTests().catch(err => {
  console.error('Frontend compatibility test failed:', err);
  process.exit(1);
});
