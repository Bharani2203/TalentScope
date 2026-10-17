import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  adaptCoreIntelligenceAnswerResponse,
  queryCoreIntelligenceAnswer
} from '../src/api/core-intelligence-client.js';
import { renderAnswerEvidencePanel } from '../src/components/common/IntelligenceComponents.js';
import { loadAiSession, syncHomeToAssistantSession } from '../src/data/ai-assistant-data.js';

globalThis.window = { TALENTSCOPE_API_BASE_URL: 'http://127.0.0.1:8000' };

const responseFixture = {
  request_id: 'answer-1',
  conversation_id: 'conversation-1',
  status: 'completed',
  execution_status: 'completed',
  answer: 'Python was observed in the returned source records.',
  facts: [{
    fact_id: 'fact-1',
    fact_type: 'historical_observation',
    metric_kind: 'observed',
    metric_name: 'Monthly postings',
    metric_value: 12,
    unit: 'postings',
    denominator: 40,
    period: '2026-10',
    source: 'jsearch',
    data_origin: 'real',
    series_id: 'jsearch:python:jobs:v1',
    provenance_id: 'fetch-run-1',
    readiness_state: 'ready'
  }],
  evidence: [{
    evidence_id: 'evidence-1',
    source: 'jsearch',
    signal_type: 'stored_posting',
    period: '2026-10',
    unit: 'posting',
    data_origin: 'real',
    history_type: 'platform_collected',
    series_id: 'jsearch:python:jobs:v1',
    fetch_run_id: 'fetch-run-1',
    source_url: 'https://jobs.example.test/posting/1',
    provenance_id: 'posting-1',
    description: 'Stored role record'
  }],
  limitations: ['Stored postings are not global vacancy totals.'],
  follow_up_questions: ['Which skills are listed in the postings?']
};

{
  const previousFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    requests.push({ url, body });
    return new Response(JSON.stringify({
      ...responseFixture,
      portal_type: body.portal_type,
      user_message: body.message
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    for (const portalType of ['individual', 'employee', 'company']) {
      const result = await queryCoreIntelligenceAnswer({
        message: 'Show available evidence',
        portalType,
        companyId: portalType === 'company' ? 'authorized-tenant' : null,
        conversationId: 'conversation-1'
      });
      assert.equal(result.portal_type, portalType);
      assert.equal(result.conversation_id, 'conversation-1');
      assert.equal(result.facts[0].metric_kind, 'observed');
      assert.equal(result.facts[0].denominator, 40);
    }
    assert.equal(requests.length, 3);
    assert.ok(requests.every(({ url }) => url.endsWith('/api/v1/intelligence/answer')));
    assert.equal(requests[2].body.company_id, 'authorized-tenant');
    assert.equal(requests[2].body.observations.length, 0);
    assert.equal(requests[0].body.conversation_id, 'conversation-1');
  } finally {
    globalThis.fetch = previousFetch;
  }
}

{
  const response = adaptCoreIntelligenceAnswerResponse(responseFixture);
  assert.equal(response.answer_origin, 'deterministic');
  const html = renderAnswerEvidencePanel(response.facts, response.evidence);
  for (const expected of [
    '12 postings', 'Observed measurement', 'jsearch', 'Denominator: 40', '2026-10',
    'fetch-run-1', 'posting-1', 'https://jobs.example.test/posting/1'
  ]) {
    assert.ok(html.includes(expected), `expected answer evidence panel to include ${expected}`);
  }
  assert.ok(html.includes('rel="noopener noreferrer"'));
  assert.ok(!html.includes('javascript:'));
}

{
  const html = renderAnswerEvidencePanel(
    [{ ...responseFixture.facts[0], details: { employee_id: 'private-person-id' } }],
    responseFixture.evidence,
    { status: 'completed', executionStatus: 'blocked' }
  );
  assert.equal(html, '', 'blocked responses do not render attached facts, evidence, or identifiers');
}

{
  const html = renderAnswerEvidencePanel([{
    fact_type: 'trend_analysis',
    entity_name: 'Python',
    metric_name: 'trend_direction',
    metric_value: 'Increasing',
    unit: 'job_postings per month',
    period: '2026-07_to_2026-10',
    source: 'jsearch',
    data_origin: 'real',
    history_type: 'platform_collected',
    denominator: 1000,
    calculation_version: 'trend-v2',
    details: {
      signal_type: 'demand',
      provider: 'jsearch',
      start_period: '2026-07',
      end_period: '2026-10',
      freshness_state: 'fresh',
      history_complete: true
    }
  }], [{
    evidence_id: 'trend-evidence',
    source: 'jsearch',
    signal_type: 'demand',
    period: '2026-07_to_2026-10',
    unit: 'job_postings per month',
    data_origin: 'real',
    history_type: 'platform_collected',
    series_id: 'jsearch:python:demand:v1',
    supporting_observation_ids: ['obs-1'],
    supporting_fetch_run_ids: ['run-1'],
    supporting_source_urls: ['https://provider.example/obs-1'],
    freshness_state: 'fresh',
    description: 'Comparable job-posting demand series'
  }]);
  assert.ok(html.includes('Observed skill trend · Python'));
  assert.ok(html.includes('Increasing Job-posting demand'));
  assert.ok(html.includes('Freshness: fresh'));
  assert.ok(html.includes('History completeness: complete within the requested range'));
  assert.ok(html.includes('Collection runs: run-1'));
  assert.ok(html.includes('Observation records: obs-1'));
  assert.ok(html.includes('href="https://provider.example/obs-1"'));
  assert.ok(!html.includes('trend_direction'));
}

{
  const previousStorage = globalThis.localStorage;
  const values = new Map();
  globalThis.localStorage = {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key)
  };

  try {
    syncHomeToAssistantSession('home-assistant-test-user', 'skills', {
      conversationId: 'conversation-1',
      messages: [
        {
          id: 'home-turn-1',
          query: 'Show available evidence',
          status: 'completed',
          answer: responseFixture.answer,
          apiResponse: responseFixture,
          evidenceItems: responseFixture.evidence,
          contextualFollowUps: responseFixture.follow_up_questions
        },
        {
          id: 'home-turn-error',
          query: 'Retry this question',
          status: 'error',
          answer: 'The answer service could not be reached.'
        }
      ]
    });
    const history = loadAiSession('home-assistant-test-user').domains.skill.history;
    assert.equal(history[0].userQuestion, 'Show available evidence');
    assert.equal(history[0].answer, responseFixture.answer);
    assert.equal(history[0].conversation_id, 'conversation-1');
    assert.equal(history[0].facts[0].fact_id, 'fact-1');
    assert.equal(history[0].evidence[0].source_url, responseFixture.evidence[0].source_url);
    assert.deepEqual(history[0].follow_up_questions, responseFixture.follow_up_questions);
    assert.equal(history[1].status, 'error');
    assert.equal(history[1].answer, 'The answer service could not be reached.');
  } finally {
    if (previousStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previousStorage;
  }
}

{
  const facts = [{
    fact_type: 'stored_job_postings',
    metric_name: 'Stored postings',
    metric_value: 1,
    unit: 'postings',
    details: {
      postings: [{
        title: 'Platform Engineer',
        source_url: 'https://jobs.example.test/platform-engineer',
        required_skills: ['Python', 'Kubernetes']
      }]
    }
  }];
  const present = renderAnswerEvidencePanel(facts, []);
  assert.ok(present.includes('Skills listed in stored job postings'));
  assert.ok(present.includes('Python, Kubernetes'));
  assert.ok(present.includes('https://jobs.example.test/platform-engineer'));

  facts[0].details.postings[0].required_skills = [];
  const absent = renderAnswerEvidencePanel(facts, []);
  assert.ok(absent.includes('No structured required-skill list was recorded'));
  assert.ok(!absent.includes('Python'));
}

{
  const reference = renderAnswerEvidencePanel([{
    fact_type: 'skill_overview',
    metric_name: 'Taxonomy category',
    metric_value: 'Programming language',
    source: 'reference_taxonomy',
    data_origin: 'reference',
    history_type: 'static_dataset'
  }], [{
    source: 'reference_taxonomy',
    signal_type: 'taxonomy_definition',
    source_url: 'javascript:alert(1)'
  }]);
  assert.ok(reference.includes('Reference'));
  assert.ok(!reference.includes('href="javascript:'));

  const unavailable = renderAnswerEvidencePanel([{
    fact_type: 'trend_analysis',
    metric_name: 'Trend',
    metric_value: null,
    unit: 'percent'
  }], []);
  assert.ok(unavailable.includes('Unavailable'));
  assert.ok(!unavailable.includes('0 percent'));
}

{
  for (const status of ['completed', 'partial', 'unavailable', 'insufficient_data', 'unsupported', 'blocked', 'failed']) {
    const adapted = adaptCoreIntelligenceAnswerResponse({
      status,
      execution_status: status,
      answer: `Response state: ${status}`,
      facts: [],
      evidence: [],
      limitations: ['No verified metric is available.']
    });
    assert.equal(adapted.status, status);
    assert.equal(adapted.execution_status, status);
    assert.equal(adapted.facts.length, 0);
    assert.equal(adapted.limitations[0], 'No verified metric is available.');
  }
}

{
  const previousFetch = globalThis.fetch;
  let attempts = 0;
  globalThis.fetch = async () => {
    attempts += 1;
    if (attempts === 1) throw new TypeError('offline');
    return new Response(JSON.stringify(responseFixture), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  };

  try {
    await assert.rejects(
      queryCoreIntelligenceAnswer({ message: 'Retry me', portalType: 'employee' }),
      error => error.name === 'CoreIntelligenceNetworkError'
    );
    const retried = await queryCoreIntelligenceAnswer({
      message: 'Retry me',
      portalType: 'employee',
      conversationId: 'conversation-1'
    });
    assert.equal(attempts, 2);
    assert.equal(retried.answer, responseFixture.answer);
  } finally {
    globalThis.fetch = previousFetch;
  }
}

{
  const [home, individual, employee, company] = await Promise.all([
    readFile(new URL('../src/app/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/pages/individual/ai-assistant/AIAssistant.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/pages/employee/ai-assistant/AIAssistant.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/pages/company/ai-assistant/AIAssistant.js', import.meta.url), 'utf8')
  ]);

  assert.ok(home.includes('queryIntelligenceAnswer({'));
  assert.ok(home.includes('conversation_id: activeConvId'));
  assert.ok(home.includes('console-retry-answer-btn'));
  assert.ok(home.includes('apiResponse: response'));
  assert.ok(home.includes('Could not preserve failed Home turn'));
  assert.ok(home.includes("const showFocusEntities = popupScope !== 'All Skills' && popupScope !== 'All Companies';"));
  assert.ok(home.includes('${showFocusEntities ? `'));
  assert.ok(!home.includes('Platform Verified Store & O*NET 30.2'));
  for (const page of [individual, employee, company]) {
    assert.ok(page.includes('queryCoreIntelligenceAnswer({'));
  }
  assert.ok(individual.includes('conversationId: domState.conversation_id'));
  assert.ok(employee.includes('conversationId: activeConversationId'));
  assert.ok(company.includes('conversationId: activeConversationId'));
  assert.ok(individual.includes('source_url'));
  assert.ok(individual.includes('p.required_skills'));
  assert.ok(employee.includes('renderAnswerEvidencePanel('));
  assert.ok(company.includes('renderAnswerEvidencePanel('));
  assert.ok(employee.includes('if (isAnalyzing || !query) return;'));
  assert.ok(company.includes('if (isCopilotAnalyzing || !query) return;'));
  assert.ok(company.includes('getCurrentUser()'));
  assert.ok(!company.includes("companyProfile.id || 'nvidia'"));
  assert.ok(individual.includes('ai-retry-turn'));
  assert.ok(employee.includes('emp-chat-retry-btn'));
  assert.ok(company.includes('cmp-copilot-retry-btn'));
}

console.log('ANSWER ENGINE FRONTEND TESTS: 8/8 PASSED');
