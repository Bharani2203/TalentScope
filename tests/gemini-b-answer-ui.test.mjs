import assert from 'node:assert/strict';
import { adaptCoreIntelligenceAnswerResponse } from '../src/api/core-intelligence-client.js';
import { renderConversationAnswer } from '../src/components/common/ConversationAnswer.js';
import { renderStructuredIntelligenceDetails } from '../src/components/common/IntelligenceResultDetails.js';
import { renderIntelligenceEvidencePanel } from '../src/components/common/IntelligenceEvidencePanel.js';

const raw = {
  request_id: 'test-guidance',
  user_message: 'What should I learn?',
  portal_type: 'individual',
  domain: 'skill',
  intent: 'skill_demand_trends',
  plan_status: 'ready_to_execute',
  execution_status: 'completed',
  status: 'ready',
  answer: 'Learn the core concepts, then practice with a small project.',
  answer_origin: 'gemini',
  answer_title: 'Skill guidance',
  answer_type: 'recommendations',
  source_mode: 'ai_general_guidance',
  evidence: [],
  facts: [],
  visualization: null,
  next_actions: ['Choose a small project.']
};

const adapted = adaptCoreIntelligenceAnswerResponse(raw);
assert.equal(adapted.source_mode, 'ai_general_guidance');
assert.equal(adapted.answer_type, 'recommendations');
assert.deepEqual(adapted.next_actions, ['Choose a small project.']);

const html = renderConversationAnswer(adapted, value => value);
assert.match(html, /Skill guidance/);
assert.match(html, /General AI guidance/);
assert.match(html, /Choose a small project/);
assert.doesNotMatch(html, /AI explanation of evidence/);
assert.equal(renderStructuredIntelligenceDetails(adapted), '');
assert.equal(renderIntelligenceEvidencePanel(adapted), '');

for (const answerType of ['explanation', 'comparison', 'roadmap']) {
  const formatted = adaptCoreIntelligenceAnswerResponse({ ...raw, answer_type: answerType });
  assert.equal(formatted.answer_type, answerType);
  assert.ok(renderConversationAnswer(formatted, value => value).includes('Skill guidance'));
}

const withEvidence = adaptCoreIntelligenceAnswerResponse({
  ...raw,
  source_mode: 'platform_data',
  answer_origin: 'deterministic',
  evidence: [{
    evidence_id: 'fixture:source:one', source: 'Local test fixture', signal_type: 'reference_taxonomy',
    data_origin: 'real', source_url: 'https://example.org/reference', description: 'Test-only evidence.'
  }],
  metric_results: [{ metric_name: 'reference_entry', metric_value: 1, unit: 'record', source: 'Local test fixture', status: 'observed' }]
});
assert.match(renderIntelligenceEvidencePanel(withEvidence), /Local test fixture/);

const insufficient = adaptCoreIntelligenceAnswerResponse({
  ...raw, status: 'insufficient_data', execution_status: 'insufficient_data',
  answer: 'No verified platform result is available.'
});
assert.match(renderConversationAnswer(insufficient, value => value), /Not enough verified evidence/);
assert.equal(renderStructuredIntelligenceDetails(insufficient), '');

console.log('Gemini B answer UI contract passed.');
