import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  adaptCoreIntelligenceAnswerResponse,
  adaptCoreIntelligenceResponse,
  adaptEvidenceItem,
  adaptFactItem
} from '../src/api/core-intelligence-client.js';
import { adaptSkillIntelligenceResponse } from '../src/pages/individual/skills/skills-api.js';
import { renderIntelligenceEvidencePanel } from '../src/components/common/IntelligenceEvidencePanel.js';

const metric = {
  capability: 'skill_trend',
  status: 'ready',
  metric_kind: 'observed',
  canonical_entity_id: 'python',
  series_id: 'jsearch:query-a:job-demand:python:v1',
  metric_name: 'Monthly job postings',
  metric_value: 0,
  unit: 'job_postings',
  denominator: 200,
  denominator_unit: 'sampled_postings',
  source: 'jsearch',
  signal_type: 'demand',
  period: '2026-10',
  observation_periods: ['2026-09', '2026-10'],
  latest_observed_at: '2026-10-13T10:00:00Z',
  freshness_state: 'fresh',
  source_urls: ['https://provider.example/jobs/1'],
  observation_ids: ['obs-1'],
  fetch_run_ids: ['run-1'],
  readiness_state: 'ready_for_trend',
  method_version: 'trend-v2',
  limitations: ['Sampled postings are not a global total.']
};

assert.doesNotThrow(() => {
  const html = renderIntelligenceEvidencePanel({
    data_state: 'ready',
    metric_results: [metric]
  });
  for (const expected of [
    'Monthly job postings', '0 job_postings', 'jsearch', 'demand',
    '2026-10', 'Sampled postings are not a global total.',
    'obs-1', 'run-1', 'https://provider.example/jobs/1', 'ready_for_trend'
  ]) assert.ok(html.includes(expected), `expected panel to contain ${expected}`);
  assert.ok(!html.includes('global market total'));
});

{
  const html = renderIntelligenceEvidencePanel({
    data_state: 'incomplete_history',
    metric_results: [{
      ...metric,
      status: 'unavailable',
      metric_value: 99,
      freshness_state: 'incomplete',
      reason: 'The bounded observation read was truncated.',
      limitations: ['Incomplete history.']
    }],
    readiness: { blocking_reasons: ['OBSERVATION_READ_LIMIT_REACHED'] }
  });
  assert.ok(html.includes('incomplete history'));
  assert.ok(html.includes('Unavailable'));
  assert.ok(!html.includes('99 job_postings'));
  assert.ok(html.includes('OBSERVATION_READ_LIMIT_REACHED'));
}

{
  const html = renderIntelligenceEvidencePanel({
    data_state: 'partial',
    metric_results: [{ ...metric, status: 'ready', freshness_state: 'stale' }]
  });
  assert.ok(html.includes('data-status="stale"'));
  assert.ok(html.includes('Freshness: stale'));
  assert.ok(!html.includes('0 job_postings'));
}

{
  const html = renderIntelligenceEvidencePanel({
    data_state: 'partial',
    capabilities: { forecast: { status: 'insufficient_data', reason: 'History is too short.' } },
    metric_results: [{
      ...metric,
      capability: 'forecast',
      metric_kind: 'predicted',
      metric_name: 'Forecast',
      metric_value: 42,
      status: 'ready'
    }]
  });
  assert.ok(html.includes('History is too short.'));
  assert.ok(!html.includes('42 job_postings'));
}

{
  const html = renderIntelligenceEvidencePanel({
    data_status: 'unavailable',
    forecast: { status: 'insufficient_data', reason: 'At least 24 complete periods are required.' },
    skill_health: { status: 'insufficient_data', reason: 'Not enough eligible observations.' },
    skill_half_life: { status: 'unavailable', reason: 'No declining comparable series.' }
  });
  assert.ok(html.includes('Forecast unavailable: At least 24 complete periods are required.'));
  assert.ok(html.includes('Skill Health unavailable: Not enough eligible observations.'));
  assert.ok(html.includes('Skill Half-Life unavailable: No declining comparable series.'));
  assert.ok(!html.includes('score'));
}

{
  const loading = renderIntelligenceEvidencePanel(null, { loading: true });
  const failed = renderIntelligenceEvidencePanel(null, { error: 'Request failed <script>alert(1)</script>' });
  assert.ok(loading.includes('Loading verified intelligence'));
  assert.ok(failed.includes('role="alert"'));
  assert.ok(failed.includes('&lt;script&gt;'));
  assert.ok(!failed.includes('<script>'));
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'ready',
    metric_results: [{
      ...metric,
      source: 'reference_taxonomy',
      history_type: 'static_dataset',
      metric_kind: 'observed',
      source_urls: ['https://reference.example/taxonomy', 'javascript:alert(1)']
    }]
  });
  assert.ok(html.includes('Reference dataset · not observed market demand'));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(html.includes('href="https://reference.example/taxonomy"'));
}

{
  const skill = adaptSkillIntelligenceResponse({
    data_status: 'available',
    forecast: { status: 'ready' },
    sources_used: [],
    current_signals: [{ source: 'jsearch' }],
    historical_trends: [{
      entity_name: 'Python',
      canonical_skill_id: 'python',
      is_trend_ready: true,
      data_points: [
        { period: '2026-09', value: null },
        { period: '2026-10', value: 0 }
      ]
    }]
  }, 'Python');
  assert.deepEqual(skill.sources_used, ['jsearch']);
  assert.equal(skill.is_forecast_ready, true);
  assert.deepEqual(skill.selected_skill.series.map(item => item.value), [0]);
  assert.equal(skill.selected_skill.canonical_skill_id, 'python');
}

{
  const response = adaptCoreIntelligenceResponse({
    intelligence_type: 'market',
    metric_results: [metric],
    historical_trends: [{ entity_name: 'Python', is_forecast_ready: true }]
  });
  assert.deepEqual(response.metric_results, [metric]);
  assert.equal(response.historical_trends[0].is_forecast_ready, true);
  assert.equal(adaptCoreIntelligenceResponse({}).data_origin, 'unavailable');
  assert.equal(adaptCoreIntelligenceResponse({}).history_type, 'unavailable');

  const answer = adaptCoreIntelligenceAnswerResponse({ metric_results: [metric] });
  assert.deepEqual(answer.metric_results, [metric]);
  const incompleteFact = adaptFactItem({ metric_name: 'Count', metric_value: 4 });
  assert.equal(incompleteFact.source, null);
  assert.equal(incompleteFact.data_origin, 'unavailable');
  assert.equal(incompleteFact.quality_state, 'unknown');
  const incompleteEvidence = adaptEvidenceItem({});
  assert.equal(incompleteEvidence.source, null);
  assert.equal(incompleteEvidence.data_origin, 'unavailable');
  assert.equal(adaptCoreIntelligenceAnswerResponse({ answer: 'Text without execution status.' }).status, 'unavailable');
}

{
  const response = adaptCoreIntelligenceResponse({
    data_state: 'ready',
    history_complete: false,
    historical_trends: [{ entity_name: 'Python', is_trend_ready: true, growth_pct: 20 }],
    forecast: { status: 'ready', value: 99 },
    skill_health: { status: 'ready', score: 80 },
    skill_half_life: { status: 'ready', half_life_months: 12 },
    readiness: { ready_for_trend_count: 1, ready_for_forecast_count: 1, blocked_count: 0, blocking_reasons: [] },
    metric_results: [{
      ...metric,
      capability: 'forecast',
      metric_kind: 'predicted',
      status: 'ready',
      metric_value: 99
    }]
  });
  assert.equal(response.data_state, 'incomplete_history');
  assert.equal(response.historical_trends[0].is_trend_ready, false);
  assert.equal(response.is_forecast_ready, false);
  assert.equal(response.forecast.status, 'unavailable');
  assert.equal(response.skill_health.score, null);
  assert.equal(response.skill_half_life.half_life_months, null);
  assert.equal(response.metric_results[0].metric_value, null);
  assert.equal(response.readiness.ready_for_trend_count, 0);
  assert.ok(response.readiness.blocking_reasons.includes('OBSERVATION_HISTORY_INCOMPLETE'));
}

{
  const pagePaths = [
    '../src/pages/individual/skills/SkillIntelligence.js',
    '../src/pages/individual/market/MarketIntelligence.js',
    '../src/pages/individual/career/Career.js',
    '../src/pages/individual/ai-assistant/AIAssistant.js',
    '../src/pages/employee/ai-assistant/AIAssistant.js',
    '../src/pages/company/ai-assistant/AIAssistant.js',
    '../src/pages/company/market/MarketIntelligence.js',
    '../src/pages/company/skills/SkillIntelligence.js'
  ];
  for (const path of pagePaths) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8');
    assert.ok(source.includes('renderIntelligenceEvidencePanel'), `${path} should render structured intelligence evidence`);
  }
  const companyAssistant = await readFile(new URL(pagePaths[5], import.meta.url), 'utf8');
  assert.ok(!companyAssistant.includes('29,600 employee records'));
  assert.ok(!companyAssistant.includes('Simulated Prototype Intelligence Feed'));
}

console.log('INTELLIGENCE EVIDENCE PANEL TESTS: 11 passed');
