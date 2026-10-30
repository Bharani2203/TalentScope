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
import { cleanConversationAnswer, renderConversationAnswer, renderConversationNextAction } from '../src/components/common/ConversationAnswer.js';

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
  measured_signal_type: 'demand',
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

  {
    const escapedMarkdown = value => `<p>${String(value).replace(/[&<>]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[char])}</p>`;
    const html = renderConversationAnswer({
      status: 'completed',
      execution_status: 'completed',
      answer_origin: 'gemini'
    }, escapedMarkdown, {
      answer: 'Python is relevant to the role.\n\nforecast_readiness: ready\nskill_health_component_readiness: unknown\n### Evidence Highlights\nObserved details\nSources:\n{\n"taxonomy_category": "synthetic"\n}',
      explanation: 'This is based on the selected role requirements.'
    });
    assert.ok(html.includes('AI explanation of evidence'));
    assert.ok(html.includes('Python is relevant to the role.'));
    assert.ok(html.includes('What this means'));
    assert.ok(renderConversationNextAction('Review the cited skill mapping.', escapedMarkdown).includes('Next step'));
    for (const internal of ['forecast_readiness', 'skill_health_component_readiness', 'Evidence Highlights', 'Observed details', 'taxonomy_category', '{']) {
      assert.ok(!html.includes(internal));
    }
  }

  {
    const unavailable = renderConversationAnswer({
      intent: 'general_explanation',
      status: 'unavailable',
      execution_status: 'unsupported',
      answer_origin: 'deterministic'
    }, value => `<p>${value}</p>`, { answer: 'No explanation was returned.' });
    assert.ok(unavailable.includes('General explanation unavailable'));
    assert.ok(!unavailable.includes('Platform-generated answer'));
    const reference = renderConversationAnswer({
      intent: 'lookup_skill_reference',
      status: 'insufficient_data',
      execution_status: 'insufficient_data'
    }, value => `<p>${value}</p>`, { answer: 'No reference record was found.' });
    assert.ok(reference.includes('Reference information unavailable'));
    assert.ok(!reference.includes('Not enough data'));
    const clarification = renderConversationAnswer({
      intent: 'lookup_skill_reference',
      status: 'requires_clarification',
      execution_status: 'requires_clarification'
    }, value => `<p>${value}</p>`, { answer: 'Which ESCO skill did you mean?' });
    assert.ok(clarification.includes('Which ESCO skill did you mean?'));
    const error = renderConversationAnswer({
      intent: 'lookup_skill_reference', status: 'error', execution_status: 'failed'
    }, value => `<p>${value}</p>`, { answer: 'Reference lookup failed. Reference: req-test.' });
    assert.ok(error.includes('Reference lookup failed. Reference: req-test.'));
  }

  {
    const html = renderConversationAnswer({
      status: 'completed',
      execution_status: 'unsupported'
    }, value => `<p>${value}</p>`, {
      answer: 'Workforce projections are not available.'
    });
    assert.ok(html.includes('Not supported'));
    assert.ok(html.includes('no estimate or projection was produced'));
    assert.ok(html.includes('Workforce projections are not available.'));
  }

  {
    const html = renderIntelligenceEvidencePanel({
      status: 'completed',
      execution_status: 'blocked',
      metric_results: [{ ...metric, metric_value: 15, status: 'ready' }],
      facts: [{
        metric_name: 'Employee skill coverage',
        metric_value: 12,
        quality_state: 'valid',
        details: { employee_ids: ['private-employee-id'] }
      }]
    }, { compact: true });
    assert.ok(!html.includes('15 job_postings'));
    assert.ok(!html.includes('12'));
    assert.ok(!html.includes('private-employee-id'));
    assert.ok(html.includes('Unavailable'));
  }
  for (const expected of [
    'Monthly job postings', '0 job postings', 'jsearch', 'demand',
    '2026-10', 'Sampled postings are not a global total.',
    'obs-1', 'run-1', 'https://provider.example/jobs/1', 'ready_for_trend'
  ]) assert.ok(html.includes(expected), `expected panel to contain ${expected}`);
  assert.ok(!html.includes('global market total'));

{
  const adoption = renderIntelligenceEvidencePanel({
    status: 'completed',
    execution_status: 'completed',
    evidence: [{
      evidence_id: 'github:record-1',
      source: 'ref_github_topic_adoption',
      signal_type: 'developer_adoption_observation',
      measured_signal_type: 'adoption',
      period: '2025-Q4',
      unit: 'unique developers per quarter',
      data_origin: 'real',
      history_type: 'backfill',
      series_id: 'github_innovation_graph:topic_pushers:IN:python',
      location: 'IN',
      scope: 'country',
      provenance_id: 'record-1',
      description: 'GitHub Innovation Graph topic pushers in IN; developer activity, not hiring demand.'
    }]
  }, { compact: true });
  for (const value of [
    'ref_github_topic_adoption', 'Developer adoption/activity', '2025-Q4',
    'unique developers per quarter', 'real', 'backfill',
    'github_innovation_graph:topic_pushers:IN:python', 'IN', 'record-1',
    'not hiring demand'
  ]) assert.ok(adoption.includes(value), `expected rendered adoption evidence to include ${value}`);
}
});

{
  const escoUri = 'http://data.europa.eu/esco/skill/example-uri';
  const evidenceId = 'ev_esco_skill_example';
  const adapted = adaptCoreIntelligenceAnswerResponse({
    request_id: 'ans_esco_frontend',
    user_message: 'Find an ESCO skill',
    portal_type: 'individual',
    intent: 'lookup_skill_reference',
    plan_status: 'ready_to_execute',
    execution_status: 'completed',
    status: 'ready',
    answer: 'ESCO v1.2.1 reference entry.',
    facts: [{
      fact_type: 'canonical_reference',
      entity_name: 'Example skill',
      canonical_entity_id: `skill:esco:${escoUri}`,
      metric_name: 'taxonomy_category',
      metric_value: 'knowledge',
      source: 'ref_esco_skills',
      history_type: 'reference_taxonomy',
      quality_state: 'valid',
      provenance_id: escoUri,
      evidence_reference: evidenceId,
      details: { esco_uri: escoUri, source_version: 'v1.2.1' }
    }],
    evidence: [{
      evidence_id: evidenceId,
      source: 'ref_esco_skills',
      signal_type: 'taxonomy_lookup',
      provenance_id: escoUri,
      description: 'ESCO v1.2.1 skill taxonomy entry: Example skill.'
    }],
    limitations: [
      'ESCO taxonomy does not prove individual qualifications.',
      'ESCO taxonomy is not current hiring demand.'
    ]
  });
  assert.equal(adapted.facts[0].details.esco_uri, escoUri);
  assert.equal(adapted.facts[0].details.source_version, 'v1.2.1');
  assert.equal(adapted.facts[0].evidence_reference, evidenceId);
  assert.equal(adapted.evidence[0].provenance_id, escoUri);
  const html = renderIntelligenceEvidencePanel(adapted, { compact: true });
  assert.ok(html.includes('ref_esco_skills'));
  assert.ok(html.includes(evidenceId));
  assert.ok(html.includes(escoUri));
  assert.ok(html.includes('ESCO taxonomy does not prove individual qualifications.'));
  assert.ok(html.includes('ESCO taxonomy is not current hiring demand.'));
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'ready',
    facts: [{
      fact_type: 'trend_analysis',
      metric_name: 'trend_direction',
      metric_value: 'Increasing',
      unit: 'job_postings per month',
      period: '2026-07_to_2026-10',
      source: 'jsearch',
      data_origin: 'real',
      history_type: 'platform_collected',
      quality_state: 'valid',
      readiness_state: 'ready',
      calculation_version: 'trend-velocity-theil-sen-v2',
      details: {
        provider: 'jsearch',
        signal_type: 'demand',
        start_period: '2026-07',
        end_period: '2026-10',
        freshness_state: 'fresh',
        history_complete: true,
        observation_ids: ['obs-1'],
        fetch_run_ids: ['run-1'],
        source_urls: ['https://provider.example/obs-1']
      }
    }]
  }, { compact: true });
  const visibleSummary = html.split('<details')[0];
  assert.ok(visibleSummary.includes('Observed skill trend'));
  assert.ok(visibleSummary.includes('Increasing · Job-posting demand'));
  assert.ok(!visibleSummary.includes('trend_direction'));
  assert.ok(html.includes('Freshness: fresh'));
  assert.ok(html.includes('History completeness: complete within the requested range'));
  assert.ok(html.includes('Observation obs-1'));
  assert.ok(html.includes('Fetch run run-1'));
  assert.ok(html.includes('href="https://provider.example/obs-1"'));
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'ready',
    facts: [{
      fact_type: 'trend_analysis',
      metric_name: 'trend_direction',
      metric_value: 'Increasing',
      source: 'github',
      quality_state: 'valid',
      details: {
        provider: 'github',
        signal_type: 'adoption',
        freshness_state: 'unknown'
      }
    }]
  }, { compact: true });
  assert.ok(html.includes('Developer adoption/activity'));
  assert.ok(!html.includes('Job-posting demand'));
}

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
      source_urls: ['https://reference.example/taxonomy', 'javascript:alert(1)', 'https://', 'https://user:pass@reference.example/private']
    }]
  });
  assert.ok(html.includes('Reference dataset · not observed market demand'));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(!html.includes('href="https:///'));
  assert.ok(!html.includes('user:pass@'));
  assert.ok(html.includes('href="https://reference.example/taxonomy"'));
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'ready',
    metric_results: [metric],
    facts: [{
      metric_name: 'Monthly job postings',
      metric_value: 0,
      unit: 'job_postings',
      period: '2026-10',
      source: 'jsearch',
      series_id: 'jsearch:query-a:job-demand:python:v1',
      quality_state: 'valid',
      metric_kind: 'observed',
      signal_type: 'demand',
      provenance_id: 'fact-provenance'
    }],
    evidence: [{
      evidence_id: 'evidence-1',
      source: 'jsearch',
      signal_type: 'job_demand',
      period: '2026-10',
      source_url: 'https://provider.example/jobs/1',
      description: 'A stored posting record'
    }]
  }, { title: 'Evidence snapshot', compact: true });
  const visibleSummary = html.split('<details')[0];
  assert.ok(visibleSummary.includes('Evidence snapshot'));
  assert.ok(visibleSummary.includes('Job postings'));
  assert.ok(visibleSummary.includes('0 job postings'));
  assert.ok(visibleSummary.includes('Job-posting demand'));
  assert.ok(!visibleSummary.includes('jsearch'));
  assert.ok(!visibleSummary.includes('fact-provenance'));
  assert.ok(html.includes('<details class="intel-evidence-details">'));
  assert.ok(!html.includes('<details open'));
  assert.ok(html.includes('Source: jsearch'));
  assert.ok(html.includes('fact-provenance'));
  assert.ok(html.includes('href="https://provider.example/jobs/1"'));
  const referenceHtml = renderIntelligenceEvidencePanel({
    metric_results: [{
      ...metric,
      metric_kind: 'observed',
      source: 'reference_graph',
      history_type: 'static_dataset',
      signal_type: 'adoption'
    }]
  }, { compact: true });
  assert.ok(referenceHtml.includes('Reference material · not job-market demand'));
  assert.ok(!html.includes('href="javascript:'));
  assert.equal((html.match(/class="intel-evidence-highlight"/g) || []).length, 1);
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'partial',
    metric_results: [{
      ...metric,
      status: 'unavailable',
      metric_value: 0,
      freshness_state: 'stale'
    }],
    facts: [{
      metric_name: 'Trend direction',
      metric_value: 'up',
      quality_state: 'valid',
      freshness_state: 'incomplete'
    }],
    limitations: ['The latest observation is stale.']
  }, { compact: true });
  const visibleSummary = html.split('<details')[0];
  assert.ok(!visibleSummary.includes('0 job postings'));
  assert.ok(!visibleSummary.includes('>up<'));
  assert.ok(visibleSummary.includes('No current, usable metric values are available.'));
  assert.ok(html.includes('The latest observation is stale.'));
  assert.ok(html.includes('Unavailable'));
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
  const skill = adaptSkillIntelligenceResponse({
    data_status: 'available',
    data_state: 'ready',
    sources_used: ['jsearch'],
    personal_top_skills: [{
      skill: 'Python',
      trend: 'Growing',
      readiness_state: 'ready_for_trend',
      source: 'jsearch',
      series: [
        { period: '2026-07', value: 0.1 },
        { period: '2026-08', value: 0.12 },
        { period: '2026-09', value: 0.14 },
        { period: '2026-10', value: 0.16 }
      ]
    }],
    market_top_skills: [{
      skill: 'Python',
      trend: 'Growing',
      growth_pct: 60,
      readiness_state: 'ready_for_trend',
      source: 'jsearch',
      series: [
        { period: '2026-07', value: 0.1 },
        { period: '2026-08', value: 0.12 },
        { period: '2026-09', value: 0.14 },
        { period: '2026-10', value: 0.16 }
      ]
    }],
    selected_skill: {
      skill: 'Python',
      trend: 'Growing',
      source: 'jsearch',
      series: [
        { period: '2026-07', value: 0.1 },
        { period: '2026-08', value: 0.12 },
        { period: '2026-09', value: 0.14 },
        { period: '2026-10', value: 0.16 }
      ]
    }
  }, 'Python');

  assert.deepEqual(skill.sources_used, ['jsearch']);
  assert.equal(skill.market_top_skills[0].is_trend_ready, true);
  assert.equal(skill.personal_top_skills[0].series.length, 4);
  assert.equal(skill.selected_skill.skill, 'Python');
  assert.equal(skill.selected_skill.trend, 'Growing');

  const noPersonalTrends = adaptSkillIntelligenceResponse({
    data_status: 'available',
    personal_top_skills: [],
    market_top_skills: skill.market_top_skills
  });
  assert.deepEqual(noPersonalTrends.personal_top_skills, []);
  assert.equal(noPersonalTrends.market_top_skills.length, 1);
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
  const individualAssistant = await readFile(new URL(pagePaths[3], import.meta.url), 'utf8');
  assert.ok(individualAssistant.includes("{ title: 'Evidence snapshot', compact: true }"));
  assert.ok(!individualAssistant.includes('Evidence Highlights'));
  assert.ok(!individualAssistant.includes('Verified Grounded'));
  assert.ok(individualAssistant.includes("showToast('Thanks for letting us know.')"));
  assert.ok(individualAssistant.includes('data-action="copy_answer"'));
  assert.ok(individualAssistant.includes('data-feedback="up"'));
  assert.ok(individualAssistant.includes('executeAiQuery(fu'));
  assert.ok(individualAssistant.includes('requestContext: turn.requestContext'));
  const careerPage = await readFile(new URL(pagePaths[2], import.meta.url), 'utf8');
  assert.ok(careerPage.includes('Illustrative prototype only:'));
  assert.ok(careerPage.includes('title="Illustrative prototype; not live job-market data"'));
  assert.ok(careerPage.includes('This prototype does not include verified citations.'));
  assert.ok(careerPage.includes('Sample fixture only; not verified, API-backed, or externally sourced.'));
  assert.ok(careerPage.includes('Waiting for the job-intelligence API response...'));
  assert.ok(!careerPage.includes('Methodology: Core Intelligence market collection'));
  assert.ok(!careerPage.includes('42,000+ active requisitions'));
  assert.ok(!careerPage.includes('analysisStep'));
  assert.ok(!careerPage.includes('getScanningStageText'));
  assert.ok(!careerPage.includes('tickSimulation'));
  const assistantStyles = await readFile(new URL('../src/pages/individual/ai-assistant/ai-assistant.css', import.meta.url), 'utf8');
  assert.ok(assistantStyles.includes('max-width: 1200px;'));
  const employeeAssistant = await readFile(new URL(pagePaths[4], import.meta.url), 'utf8');
  assert.ok(!employeeAssistant.includes('verified empirical platform intelligence'));
  assert.ok(!employeeAssistant.includes('NVIDIA APAC L4'));
  const companyAssistant = await readFile(new URL(pagePaths[5], import.meta.url), 'utf8');
  assert.ok(!companyAssistant.includes('29,600 employee records'));
  assert.ok(!companyAssistant.includes('Simulated Prototype Intelligence Feed'));
  assert.ok(!companyAssistant.includes('Workday and DLI benchmarks'));
  for (const assistantPath of [pagePaths[4], pagePaths[5]]) {
    const source = await readFile(new URL(assistantPath, import.meta.url), 'utf8');
    assert.ok(source.includes('data-copy-assistant-answer'), `${assistantPath} should provide answer copying`);
    assert.ok(source.includes('data-assistant-feedback'), `${assistantPath} should provide message feedback`);
    assert.ok(source.includes('data-message-index'), `${assistantPath} actions should target a specific message`);
    assert.ok(source.includes('cleanConversationAnswer'), `${assistantPath} should omit hidden fields from copied answers`);
  }
}

{
  const html = renderIntelligenceEvidencePanel({
    status: 'ready',
    metric_results: [
      { source: 'adzuna', entity_name: 'AI', metric_value: 3 },
      { source: 'jsearch', entity_name: 'AI', metric_value: 2 },
      { source: 'jsearch', entity_name: 'Backend', metric_value: 4 },
      { source: 'jsearch', entity_name: 'Python', metric_value: 10 }
    ]
  }, {
    title: 'Skill intelligence evidence',
    skill: 'Python'
  });

  assert.ok(html.includes('Top Associated Role'), 'should render Top Associated Role title');
  assert.ok(html.includes('AI'), 'should identify top role AI');
  assert.ok(html.includes('Top Role: <strong>AI</strong>'), 'should display Top Role: AI');
  assert.ok(html.includes('Total Demand: <strong>5</strong>'), 'should aggregate total demand to 5');
  assert.ok(html.includes('intel-evidence-single-box'), 'should render single box container');
  assert.ok(!html.includes('intel-evidence-grid'), 'should not render evidence grid');
  assert.ok(html.includes('Aggregated across 2 sources (Adzuna, JSearch)'), 'should report aggregated sources');
}

console.log('INTELLIGENCE EVIDENCE PANEL TESTS: 15 passed');

