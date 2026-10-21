import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {}
};
const { renderRoleAssociationComparison } = await import('../src/pages/individual/career/Career.js');

const summary = {
  fact_type: 'learning_recommendation_summary',
  details: {
    profile_skill_source: 'authenticated_individual_profile',
    role_associated_skill_overlap: {
      score_pct: 50,
      matched_count: 1,
      resolved_mapping_count: 2
    },
    matched_associated_skills: [{ skill: '<Python>', profile_evidence: 'authenticated_individual_profile' }],
    missing_associated_skills: [{ skill: 'SQL', meaning: 'not a qualification gap' }],
    unresolved_requirements: [{ label: 'Unmapped tool', reason: 'no canonical skill mapping is available' }],
    level_gaps: { status: 'unavailable', reason: 'Required levels are not provided.' }
  }
};

const declaredMarkup = renderRoleAssociationComparison({ facts: [summary] });
assert.ok(declaredMarkup.includes('Matched declared profile skills'));
assert.ok(declaredMarkup.includes('&lt;Python&gt;'));
assert.ok(declaredMarkup.includes('not role fit, required qualifications, or employability'));
assert.ok(declaredMarkup.includes('Unmapped tool'));
assert.ok(declaredMarkup.includes('Proficiency gaps:</strong> unavailable'));

const requestMarkup = renderRoleAssociationComparison({
  facts: [{ ...summary, details: { ...summary.details, profile_skill_source: 'request_supplied_skills' } }]
});
assert.ok(requestMarkup.includes('Matched request-supplied skills'));

assert.equal(renderRoleAssociationComparison({ status: 'insufficient_data', facts: [] }), '');
assert.equal(renderRoleAssociationComparison(null), '');

const source = await readFile(new URL('../src/pages/individual/career/Career.js', import.meta.url), 'utf8');
assert.ok(source.includes('queryJobIntelligence({'));
assert.ok(source.includes('queryCoreIntelligenceAnswer({'));
assert.ok(source.includes('renderRoleAssociationComparison(ui.roleAssociationResponse)'));
assert.ok(source.includes('Market intelligence could not be loaded. Please try again.'));
assert.ok(source.includes('Role-associated skill comparison is unavailable. Please try again.'));
assert.ok(!source.includes('ui.jobApiResponse)}'));

console.log('CAREER INTELLIGENCE TESTS: 1 passed');
