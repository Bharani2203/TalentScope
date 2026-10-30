import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

globalThis.localStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {}
};
const { renderRoleAssociationComparison, getUserOnboardingRoles, getFavoriteRoles, ROLE_TO_PILLAR, getDynamicSignalMix, smoothHistorySeries } = await import('../src/pages/individual/career/Career.js');

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
assert.ok(source.includes('sendSupervisorMessage(ui.consoleMessages'));
assert.ok(source.includes('renderRoleAssociationComparison(ui.roleAssociationResponse)'));
assert.ok(source.includes('Market intelligence could not be loaded. Please try again.'));
assert.ok(!source.includes('ui.jobApiResponse)}'));

// Onboarding sync & interactive tabs verification
assert.ok(typeof getUserOnboardingRoles === 'function');
assert.ok(Array.isArray(getUserOnboardingRoles()));
assert.ok(typeof getFavoriteRoles === 'function');
assert.ok(Array.isArray(getFavoriteRoles()));
assert.equal(ROLE_TO_PILLAR['ai engineer'], 'Artificial Intelligence and Machine Learning');
assert.equal(ROLE_TO_PILLAR['backend developer'], 'Software Engineering and Full-Stack Development');
assert.equal(ROLE_TO_PILLAR['cloud solutions architect'], 'Cloud Computing and DevOps');
assert.ok(source.includes('data-tab="my_roles"'));
assert.ok(source.includes('data-tab="favorite_roles"'));
assert.ok(source.includes('data-tab="all_roles"'));
assert.ok(source.includes('data-action="add-role-from-pillar"'));
assert.ok(source.includes('addRoleAndActivate('));
assert.ok(source.includes('getRolesGroupedByPillar('));

// Dynamic tab counts & clean empty states verification
assert.ok(source.includes('${myCount}'));
assert.ok(source.includes('${favCount}'));
assert.ok(source.includes('${liveRolesCount}'));
assert.ok(source.includes("No roles selected. Click '+ Add Role' to start tracking."));
assert.ok(source.includes("No favorites yet. Click the star icon on a role to save it here."));
assert.ok(source.includes('renderRoleListEmptyStateHTML()'));

// Skill Gap Role Selector dropdown verification
assert.ok(source.includes('class="ji-gap-role-selector"'));
assert.ok(source.includes("root.querySelectorAll('.ji-gap-role-selector')"));

// Dynamic signal mix verification
assert.ok(typeof getDynamicSignalMix === 'function');
const dsSignals = getDynamicSignalMix({ name: 'Data Scientist', totalRoles: 4618, growthPercentage: 46.7, companiesHiring: [{}, {}, {}] });
assert.equal(dsSignals.length, 4);
const dsSum = dsSignals.reduce((acc, s) => acc + s.percent, 0);
assert.equal(dsSum, 100);

const aiSignals = getDynamicSignalMix({ name: 'AI Engineer', totalRoles: 13018, growthPercentage: 11.9, companiesHiring: [{}, {}, {}] });
assert.equal(aiSignals.length, 4);
const aiSum = aiSignals.reduce((acc, s) => acc + s.percent, 0);
assert.equal(aiSum, 100);

// Verify signals are role-dependent and not static
assert.notEqual(dsSignals[0].percent, aiSignals[0].percent);

// Historical trend smoothing verification
assert.ok(typeof smoothHistorySeries === 'function');
const smoothed = smoothHistorySeries([70, 75, 0, 80, 82, 30, 88], 88);
assert.equal(smoothed.length, 7);
assert.equal(smoothed[6], 88); // Last point matches current demand
assert.ok(smoothed[2] > 60); // 0 point interpolated, no plunge
assert.ok(smoothed[5] > 50); // intermediate drop smoothed

// Hero role selector and axis labels verification
assert.ok(source.includes('class="ji-hero-role-select"'));
assert.ok(source.includes('class="ji-chart-axis-labels"'));
assert.ok(source.includes('fetchRoleSignalMix'));

console.log('CAREER INTELLIGENCE TESTS: 1 passed');
