import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { renderStructuredIntelligenceDetails } from '../src/components/common/IntelligenceResultDetails.js';

const gap = {
  fact_type: 'personalized_skill_gap',
  entity_name: 'Data Analyst',
  canonical_entity_id: 'esco:occupation:123',
  metric_value: 0.5,
  denominator: 4,
  details: {
    taxonomy: 'esco',
    coverage_numerator: 2,
    coverage_percent: 50,
    reference_count: 4,
    matched: [{ label: 'SQL', taxonomy_id: 'esco:sql', match_method: 'official_alias_match' }],
    missing: [
      { label: 'Data Analysis', taxonomy_id: 'esco:analysis', classification: 'essential' },
      { label: 'Excel', taxonomy_id: 'esco:excel', classification: 'optional' }
    ],
    unmatched_user: [{ original_text: '<Mystery Tool>' }],
    coverage_formula: 'distinct matched / distinct applicable references',
    interpretation: 'Reference-skill coverage only; not job readiness.',
    learning_roadmap: {
      progress_persistence: 'not_configured',
      limitations: ['No duration is inferred.'],
      steps: [{
        priority: 1,
        priority_group: 'essential',
        target_skill: 'Data Analysis',
        why_relevant: 'Essential reference skill.',
        suggested_task: 'Analyze a small dataset.',
        tangible_outcome: 'A reproducible analysis note.',
        self_check_criterion: 'Check the result on a sample.',
        progress_state: 'not_started',
        proficiency_verified: false
      }]
    }
  }
};

{
  const html = renderStructuredIntelligenceDetails({ facts: [gap], intent: 'analyze_skill_gap' });
  for (const value of [
    'Data Analyst', 'esco', 'esco:occupation:123', '50%', '2 of 4', 'Matched skills',
    'SQL', 'Essential reference gaps', 'Data Analysis', 'Optional reference gaps', 'Excel',
    '&lt;Mystery Tool&gt;', 'not job readiness', 'Step 1', 'Practice task:', 'Expected outcome:',
    'Self-check:', 'not verified', 'not configured', 'No duration is inferred.'
  ]) assert.ok(html.includes(value), `expected skill-gap and roadmap rendering to include ${value}`);
  assert.ok(!html.includes('<Mystery Tool>'));
  assert.ok(!html.includes('Verified course'));
  assert.match(html, /<table class="ts-intel-comparison-table"[\s\S]*<th scope="col">Matched skills<\/th>[\s\S]*<th scope="col">Reference gaps<\/th>/);
}

{
  const html = renderStructuredIntelligenceDetails({ facts: [{
    fact_type: 'canonical_reference',
    entity_name: 'Python',
    canonical_entity_id: 'skill:esco:python',
    source: 'ref_esco_skills',
    history_type: 'reference_taxonomy',
    provenance_id: 'http://example.test/skill/python',
    details: { taxonomy: 'ESCO', source_version: '1.2.1', description: 'A verified ESCO definition.' }
  }] });
  for (const value of ['Reference entries', 'Python', 'ref_esco_skills', 'skill:esco:python', 'ESCO', '1.2.1', 'A verified ESCO definition.', 'http://example.test/skill/python']) {
    assert.ok(html.includes(value));
  }
}

{
  const html = renderStructuredIntelligenceDetails({
    intent: 'retrieve_history',
    facts: [{
      fact_type: 'historical_observation', entity_name: 'Python', metric_name: 'language_pushers',
      metric_value: 66832, unit: 'unique developers per quarter', period: '2020-Q1',
      source: 'github_innovation_graph', data_origin: 'real', history_type: 'backfill',
      series_id: 'github_innovation_graph:language_pushers:python:IN:python',
      details: { signal_type: 'adoption', frequency: 'quarterly', geography: 'IN' }
    }]
  });
  for (const value of ['Historical Skill Signals', '2020-Q1', 'github_innovation_graph', 'adoption',
    '66832', 'unique developers per quarter', 'quarterly', 'IN', 'backfill', 'real',
    'missing periods are not interpolated']) assert.ok(html.includes(value));
}

{
  const html = renderStructuredIntelligenceDetails({ facts: [{
    fact_type: 'occupation_skill_association', entity_name: 'Data analysis',
    canonical_entity_id: 'skill:esco:http://data.europa.eu/esco/skill/example',
    metric_name: 'relation_type', metric_value: 'essential', source: 'ref_esco_occupation_skill_relations',
    history_type: 'reference_taxonomy', provenance_id: 'occupation-uri|skill-uri|essential',
    details: { occupation_uri: 'occupation-uri', skill_uri: 'skill-uri', source_version: 'v1.2.1' }
  }] });
  for (const value of ['Data analysis', 'essential', 'occupation-uri', 'skill-uri', 'occupation-uri|skill-uri|essential']) {
    assert.ok(html.includes(value));
  }
}

{
  const html = renderStructuredIntelligenceDetails({ facts: [{
    fact_type: 'trend_analysis', entity_name: 'JavaScript', metric_value: 'Increasing',
    unit: 'quarterly developer pushers', source: 'github', signal_type: 'adoption',
    period: '2025-Q4_to_2026-Q1', details: { signal_type: 'adoption', geography: 'India', change_pct: 12.5 }
  }] });
  for (const value of ['Developer adoption/activity', 'quarterly developer pushers', 'India', '2025-Q4 to 2026-Q1', '12.5%', 'not hiring demand']) {
    assert.ok(html.includes(value));
  }
}

{
  const html = renderStructuredIntelligenceDetails({
    intent: 'search_jobs',
    facts: [
      { fact_type: 'stored_job_postings', metric_value: 2, source: 'firestore_jobs', details: { postings: [
        { title: 'Analyst', company: 'Example Co', location: 'Chennai', source: 'adzuna', source_url: 'https://jobs.example/1', posting_date: '2026-10-01' }
      ] } },
      { fact_type: 'stored_posting_skill', entity_name: 'SQL', canonical_entity_id: 'skill:sql', metric_value: 1, denominator: 2 },
      { fact_type: 'stored_posting_skill', entity_name: 'Microsoft Excel', canonical_entity_id: null, metric_value: 1, denominator: 2, details: { mapping_status: 'onet_exact' } },
      { fact_type: 'stored_posting_skill', entity_name: '<tool text>', canonical_entity_id: null, metric_value: 1, denominator: 2, details: { mapping_status: 'unmatched' } },
      { fact_type: 'stored_posting_skill', entity_name: 'Potential ambiguous skill', canonical_entity_id: null, metric_value: 1, denominator: 2, details: { mapping_status: 'ambiguous' } }
    ]
  });
  for (const value of ['<strong>2</strong> retrieved postings', 'firestore_jobs', 'Matched skills in retrieved sample', 'SQL', 'Microsoft Excel', 'Unmatched skill text', '&lt;tool text&gt;', 'Ambiguous skill mappings', 'Potential ambiguous skill', 'Analyst', 'Example Co', 'https://jobs.example/1']) {
    assert.ok(html.includes(value));
  }
  assert.ok(!html.includes('<tool text>'));
}

{
  const empty = renderStructuredIntelligenceDetails({ intent: 'search_jobs', facts: [{
    fact_type: 'stored_job_postings', metric_value: 0, source: 'firestore_jobs', details: { postings: [] }
  }] });
  assert.ok(empty.includes('No stored postings matched'));
  assert.ok(empty.includes('insufficient data'));
  assert.equal(renderStructuredIntelligenceDetails({ execution_status: 'failed', facts: [gap] }), '');
  assert.equal(renderStructuredIntelligenceDetails({ intent: 'general_explanation', facts: [] }), '');
}

{
  const html = renderStructuredIntelligenceDetails({
    facts: [{
      fact_type: 'action_recommendation', entity_name: 'Data analysis', metric_value: 'Data analysis',
      source: 'ref_esco_occupation_skill_relations', history_type: 'reference_taxonomy',
      provenance_id: 'esco-skill-uri', evidence_reference: 'esco-evidence-1',
      details: {
        taxonomy: 'esco', classification: 'essential',
        recommendation_basis: 'general_essential_esco_role_relationships_no_personal_gap_assessed',
        reason: 'ESCO lists this as essential for Data Analyst.',
        next_action: 'Choose a small task using Data analysis.', proficiency_verified: false
      }
    }],
    evidence: [{ evidence_id: 'esco-evidence-1', source: 'ref_esco_occupation_skill_relations', provenance_id: 'esco-skill-uri' }],
    limitations: ['No verified course catalogue is configured.', 'This is not a personalized skill gap.']
  });
  for (const value of [
    'Action Recommendation', 'Data analysis', 'essential ESCO relationship',
    'ESCO lists this as essential', 'Suggested practice:', 'not a personalized skill gap',
    'Evidence: ref_esco_occupation_skill_relations', 'esco-skill-uri', 'Proficiency verified: no'
  ]) assert.ok(html.includes(value), `expected action recommendation rendering to include ${value}`);
  assert.ok(!html.includes('Reference entries'));
}

{
  const facts = Array.from({ length: 7 }, (_, index) => ({
    fact_type: 'action_recommendation',
    entity_name: `Suggestion ${index + 1}`,
    details: { reason: `Reason ${index + 1}`, next_action: `Practice ${index + 1}` }
  }));
  const html = renderStructuredIntelligenceDetails({ facts });
  assert.ok(html.includes('Suggestion 1') && html.includes('Reason 1'));
  assert.ok(html.includes('Suggestion 5') && html.includes('Reason 5'));
  assert.ok(!html.includes('Suggestion 6') && !html.includes('Suggestion 7'));
}

{
  const html = renderStructuredIntelligenceDetails({
    facts: [{
      fact_type: 'learning_recommendation_readiness', metric_value: 'UNRESOLVED_USER_SKILL',
      details: { message: 'The supplied skill label is unresolved: <unknown>.' }
    }], evidence: []
  });
  assert.ok(html.includes('The supplied skill label is unresolved: &lt;unknown&gt;.'));
  assert.ok(!html.includes('Action Recommendation</h3><ol'));
}

const assistantSource = await readFile(new URL('../src/pages/individual/ai-assistant/AIAssistant.js', import.meta.url), 'utf8');
assert.ok(assistantSource.includes('renderStructuredIntelligenceDetails(turn)'));
assert.ok(assistantSource.includes('queryCoreIntelligenceAnswer({'));
console.log('INTELLIGENCE RESULT DETAILS TESTS: passed');
