import assert from 'node:assert/strict';

globalThis.localStorage = (() => {
  const values = new Map();
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
})();

const {
  DOMAIN_CAPABILITY_REGISTRY,
  getDomainCapabilities,
  capabilitySuggestedQuestions,
  resolveActiveCapabilityId
} = await import('../src/pages/individual/ai-assistant/AIAssistant.js');

const EXPECTED_SEVEN_FEATURES = {
  skill: [
    {
      id: 'skill_future_relevance_score',
      title: 'Skill Future Relevance Score',
      category: 'Skill Relevance',
      desc: "Assess a skill's potential future relevance using available historical and technology-adoption signals."
    },
    {
      id: 'skill_change_alert',
      title: 'Skill Change Alert',
      category: 'Skill Alerts',
      desc: 'Identify supported increases, decreases, or stable patterns in comparable skill signals.'
    },
    {
      id: 'adaptive_skill_roadmap',
      title: 'Adaptive Skill Roadmap',
      category: 'Skill Pathways',
      desc: 'Recommend an ordered learning plan based on current skills, a target role, and available skill relationships.'
    }
  ],
  market: [
    {
      id: 'technology_adoption_shift_detector',
      title: 'Technology Adoption Shift Detector',
      category: 'Market Shifts',
      desc: 'Compare supported technology-adoption signals over comparable periods and identify meaningful changes.'
    },
    {
      id: 'technology_impact_explorer',
      title: 'Technology Impact Explorer',
      category: 'Market Impact',
      desc: 'Explore supported relationships between technologies, skills, and occupations.'
    }
  ],
  job: [
    {
      id: 'skill_based_job_match',
      title: 'Skill-Based Job Match',
      category: 'Job Matching',
      desc: "Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps."
    },
    {
      id: 'career_transition_opportunity',
      title: 'Career Transition Opportunity',
      category: 'Career Pathways',
      desc: 'Identify possible related target roles and the skills that may be needed for a transition.'
    }
  ]
};

// 1. Total feature count in frontend registry
const allFrontendCards = [
  ...DOMAIN_CAPABILITY_REGISTRY.skill,
  ...DOMAIN_CAPABILITY_REGISTRY.market,
  ...DOMAIN_CAPABILITY_REGISTRY.job
];
assert.equal(allFrontendCards.length, 7, 'Frontend registry contains exactly 7 feature cards');

// 2. Domain breakdown: Skill 3, Market 2, Job 2
assert.equal(DOMAIN_CAPABILITY_REGISTRY.skill.length, 3, 'Skill domain has exactly 3 approved features');
assert.equal(DOMAIN_CAPABILITY_REGISTRY.market.length, 2, 'Market domain has exactly 2 approved features');
assert.equal(DOMAIN_CAPABILITY_REGISTRY.job.length, 2, 'Job domain has exactly 2 approved features');

// 3. Unique IDs across all domains
const allIds = allFrontendCards.map(c => c.id);
assert.equal(new Set(allIds).size, 7, 'All 7 feature IDs are unique');

// 4. Verification of IDs and metadata per domain
for (const [domain, expectedList] of Object.entries(EXPECTED_SEVEN_FEATURES)) {
  const actualList = DOMAIN_CAPABILITY_REGISTRY[domain];
  assert.equal(actualList.length, expectedList.length);
  for (let i = 0; i < expectedList.length; i++) {
    const expected = expectedList[i];
    const actual = actualList[i];
    assert.equal(actual.id, expected.id, `Feature ${expected.id} matches expected ID`);
    assert.equal(actual.title, expected.title, `Feature ${expected.id} matches expected title`);
    assert.equal(actual.category, expected.category, `Feature ${expected.id} matches expected category`);
    assert.equal(actual.desc, expected.desc, `Feature ${expected.id} matches expected description`);
    assert.deepEqual(actual.supportedDomains, [domain], `Feature ${expected.id} is scoped to ${domain}`);
    assert.ok(actual.cardTagline && actual.cardTagline.length > 10, `${actual.id} has valid cardTagline`);
    assert.ok(actual.defaultPrompt && actual.defaultPrompt.includes('{entity}'), `${actual.id} has entity placeholder in defaultPrompt`);
    assert.ok(actual.icon && actual.icon.length > 0, `${actual.id} has an icon`);
    assert.ok(actual.color && actual.color.startsWith('#'), `${actual.id} has a hex color`);
    assert.ok(actual.motif && actual.motif.includes('<svg'), `${actual.id} has an SVG motif`);
    assert.ok(actual.explainer && actual.explainer.whatItDoes, `${actual.id} has explainer.whatItDoes`);
    assert.ok(actual.explainer.inputsNeeded, `${actual.id} has explainer.inputsNeeded`);
    assert.ok(actual.explainer.outputProduced, `${actual.id} has explainer.outputProduced`);
    assert.ok(actual.explainer.limitations, `${actual.id} has explainer.limitations`);
  }
}

// 5. Verification of no obsolete features
const obsoleteIds = [
  'trend_velocity_analysis',
  'historical_signal_retrieval',
  'skill_gap_role_fit',
  'evidence_provenance_retrieval',
  'skill_technology_reference',
  'market_snapshot',
  'job_posting_search',
  'occupation_software_skills',
  'related_occupations',
  'role_preparation_actions',
  'skill_health_analysis',
  'action_recommendations'
];
for (const obsoleteId of obsoleteIds) {
  assert.ok(!allIds.includes(obsoleteId), `Obsolete feature ID '${obsoleteId}' must not be present in active registry`);
}

// 6. Capability Suggested Questions mapping
for (const card of allFrontendCards) {
  const questions = capabilitySuggestedQuestions[card.id];
  assert.ok(Array.isArray(questions), `${card.id} has suggested questions defined`);
  assert.ok(questions.length >= 3, `${card.id} has at least 3 suggested questions`);
  for (const q of questions) {
    assert.ok(typeof q === 'string' && q.length > 10, `${card.id} question is non-empty string`);
  }
}

// 7. Backend Catalog filtering with getDomainCapabilities
const mockBackendCatalog = {
  capabilities: allFrontendCards.map(c => ({
    capability_id: c.id,
    name: c.title,
    global_status: 'available',
    handler: 'app.intelligence_v2.pending_phase2',
    supported_domains: c.supportedDomains
  }))
};

assert.equal(getDomainCapabilities('skill', mockBackendCatalog).length, 3, 'getDomainCapabilities returns 3 for skill');
assert.equal(getDomainCapabilities('market', mockBackendCatalog).length, 2, 'getDomainCapabilities returns 2 for market');
assert.equal(getDomainCapabilities('job', mockBackendCatalog).length, 2, 'getDomainCapabilities returns 2 for job');

// 8. Active capability resolution
const resolved = resolveActiveCapabilityId({
  executed_primary_capability: 'adaptive_skill_roadmap',
  planned_primary_capability: 'skill_future_relevance_score',
  capabilities_used: ['adaptive_skill_roadmap']
}, 'skill', mockBackendCatalog);
assert.equal(resolved, 'adaptive_skill_roadmap', 'resolveActiveCapabilityId resolves active capability');

console.log('PHASE 1 FEATURE REGISTRY MIGRATION TESTS PASSED: All 7 features, domains (Skill 3, Market 2, Job 2), unique IDs, and metadata verified.');
