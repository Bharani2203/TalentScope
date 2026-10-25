import assert from 'node:assert/strict';
import {
  DOMAIN_CONFIG,
  createDefaultDomainFilterState
} from '../src/data/ai-assistant-data.js';
globalThis.localStorage = (() => {
  const values = new Map();
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
})();

const {
  getObservedFilterOptions,
  getSelectableEntities,
  validateAssistantFilterDraft,
  commitAssistantFilterDraft,
  resetAssistantFilterDraft,
  resolveCanonicalAssistantEntity,
  DOMAIN_CAPABILITY_REGISTRY,
  getDomainCapabilities,
  getAssistantComposerMode,
  resolveActiveCapabilityId,
  resolveNextJourneyStep,
  formatUnappliedFilterDisclosure,
  resolveDisplayedCapabilityId,
  shouldShowUnappliedFilterDisclosure,
  buildFollowUpRequestContext,
  renderTurnChartOrBaselineHTML,
  renderAssistantResponseDetails
} = await import('../src/pages/individual/ai-assistant/AIAssistant.js');
const {
  buildAnswerRequest,
  createIntelligenceConversation,
  fetchIntelligenceConversations,
  fetchConversationHistory,
  deleteIntelligenceConversation
} = await import('../src/api/core-intelligence-client.js');
const { readFile } = await import('node:fs/promises');

const skillTurns = [{
  facts: [
    { entity_type: 'skill', entity_name: 'Skill Alpha', canonical_entity_id: 'skill:alpha', quality_state: 'valid', data_origin: 'real', period: '2025-01', details: { country: 'Country A' } },
    { entity_type: 'skill', entity_name: 'Synthetic Skill', canonical_entity_id: 'skill:fake', data_origin: 'synthetic', period: '2010-01', details: { country: 'Unsupported Country' } },
    { entity_type: 'company', entity_name: 'Company Alpha', canonical_entity_id: 'company:alpha', period: '2025-02' }
  ]
}];
const jobTurns = [{ jobPostings: [{ company: 'Company Alpha', title: 'Role Alpha', location: 'City A', posting_date: '2025-03-01' }] }];

assert.deepEqual(DOMAIN_CONFIG.skill.scopes, ['All', 'Favourites']);
assert.deepEqual(DOMAIN_CONFIG.market.scopes, ['All', 'Favourites']);
assert.deepEqual(DOMAIN_CONFIG.job.scopes, ['All', 'Favourites']);

const skills = getObservedFilterOptions('skill', skillTurns);
assert.deepEqual(skills.entities, ['Skill Alpha']);
assert.deepEqual(skills.locations, ['Country A']);
assert.deepEqual(skills.ranges, ['Max Available'], 'synthetic coverage does not create time windows');
assert.ok(skills.ranges.includes('Max Available'));

assert.deepEqual(getSelectableEntities('skill', 'All', skills), ['Skill Alpha']);
assert.deepEqual(getSelectableEntities('skill', 'Favourites', { ...skills, favoriteSkills: ['Skill Alpha', 'Unsupported Favourite'] }), ['Skill Alpha']);
assert.deepEqual(getSelectableEntities('skill', 'Favourites', { ...skills, entities: [] }), []);
assert.equal(validateAssistantFilterDraft('skill', { scope: 'All', selectedSkills: ['Skill Alpha', 'Unknown Skill'], timeRange: 'Max Available', location: '' }, skills).valid, false);
assert.equal(validateAssistantFilterDraft('skill', { scope: 'All', selectedSkills: ['Skill Alpha'], timeRange: 'Max Available', location: '' }, skills).valid, true);
assert.equal(resolveCanonicalAssistantEntity('skill', 'Skill Alpha'), 'Skill Alpha', 'names pass only when no authenticated catalog ID is available');

const jobs = getObservedFilterOptions('job', jobTurns);
assert.deepEqual(jobs.companies, ['Company Alpha']);
assert.deepEqual(jobs.roles, ['Role Alpha']);
assert.deepEqual(jobs.locations, ['City A']);
assert.deepEqual(getSelectableEntities('job', 'All', jobs), ['Company Alpha']);

const marketTurns = [{ facts: [
  { entity_type: 'company', entity_name: 'Market Company', canonical_entity_id: 'company:market', quality_state: 'valid', data_origin: 'real' },
  { entity_type: 'technology', entity_name: 'Technology Alpha', canonical_entity_id: 'technology:alpha', quality_state: 'valid', data_origin: 'real' }
] }];
const market = getObservedFilterOptions('market', marketTurns);
assert.deepEqual(market.entities, ['Market Company', 'Technology Alpha']);
globalThis.localStorage.setItem('talentscope_fav_companies_v1', JSON.stringify(['Market Company', 'Unsupported Company']));
assert.deepEqual(getSelectableEntities('market', 'All', market), ['Market Company', 'Technology Alpha']);
assert.deepEqual(getSelectableEntities('market', 'Favourites', market), [], 'legacy browser storage is not treated as authenticated market favourites');

const committed = { filters: createDefaultDomainFilterState('job') };
const before = structuredClone(committed.filters);
const draft = { ...before, selectedCompany: 'Company Alpha', selectedRole: 'Role Alpha', location: 'City A', timeRange: 'Max Available' };
assert.deepEqual(committed.filters, before, 'draft edits remain unapplied until Apply');
assert.equal(validateAssistantFilterDraft('job', draft, jobs).valid, true);
assert.equal(validateAssistantFilterDraft('job', { ...draft, location: 'Unsupported City' }, jobs).valid, false);
commitAssistantFilterDraft(committed, 'job', draft);
assert.equal(committed.filters.selectedCompany, 'Company Alpha');
assert.equal(committed.filters.selectedRole, 'Role Alpha');
assert.equal(committed.filters.location, 'City A');
assert.equal(committed.filters.timeframe, 'Max Available');

const skillFilterState = { filters: createDefaultDomainFilterState('skill') };
commitAssistantFilterDraft(skillFilterState, 'skill', {
  ...skillFilterState.filters,
  scope: 'Favourites',
  selectedSkills: ['Skill Alpha'],
  selectedSkill: 'Skill Alpha',
  timeRange: 'Max Available'
});
assert.deepEqual(skillFilterState.filters.selectedSkills, ['Skill Alpha']);

const reset = resetAssistantFilterDraft('job', jobs.ranges);
assert.equal(reset.scope, 'All');
assert.equal(reset.selectedCompany, '');
assert.equal(reset.selectedRole, '');
assert.equal(reset.timeRange, 'Max Available');
assert.equal(committed.filters.selectedCompany, 'Company Alpha', 'Reset only changes the draft until Apply');

const request = buildAnswerRequest({
  message: 'Show hiring evidence', domain: 'job', location: committed.filters.location,
  timeRange: 'Max Available', targetRole: committed.filters.selectedRole,
  selectedCompanies: [committed.filters.selectedCompany],
  filters: { scope: committed.filters.scope, location: committed.filters.location, requested_time_window: committed.filters.timeRange }
});
assert.equal(request.location, 'City A');
assert.equal(request.target_role, 'Role Alpha');
assert.deepEqual(request.selected_companies, ['Company Alpha']);
assert.equal(request.filters.requested_time_window, 'Max Available');
const regenerateRequest = buildAnswerRequest({
  message: 'Show hiring evidence', domain: 'job', conversationId: 'conv-1',
  clientMessageId: 'message-1', regenerate: true
});
assert.equal(regenerateRequest.regenerate, true);
assert.equal(regenerateRequest.client_message_id, 'message-1');
assert.equal(regenerateRequest.conversation_id, 'conv-1');
const focusedTrendRequest = buildAnswerRequest({
  message: 'ui/ux trend',
  domain: 'skill',
  capabilityId: 'skill_future_relevance_score'
});
assert.equal(focusedTrendRequest.capability_id, 'skill_future_relevance_score', 'focused Skill Future Relevance Score selection reaches the backend as its canonical capability ID');

const previousFetch = globalThis.fetch;
const conversationUrls = [];
const conversationRequests = [];
globalThis.fetch = async (url, options = {}) => {
  conversationUrls.push(String(url));
  conversationRequests.push({ url: String(url), options });
  return new Response(JSON.stringify({ conversation_id: 'conv-1' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
};
try {
  await fetchIntelligenceConversations({ limit: 100, domain: 'skill', portalType: 'individual' });
  await fetchConversationHistory('conv-1', { domain: 'skill', portalType: 'individual' });
  await deleteIntelligenceConversation('conv-1', { domain: 'skill', portalType: 'individual' });
  await createIntelligenceConversation({
    portalType: 'individual',
    domain: 'skill',
    title: 'New skill session',
    filters: { scope: 'All' }
  });
} finally {
  globalThis.fetch = previousFetch;
}
assert.equal(conversationUrls.length, 4);
assert.ok(conversationUrls.slice(0, 3).every(url => url.includes('domain=skill') && url.includes('portal_type=individual')));
assert.equal(conversationRequests[3].options.method, 'POST');
assert.deepEqual(JSON.parse(conversationRequests[3].options.body), {
  portalType: 'individual',
  domain: 'skill',
  title: 'New skill session',
  filters: { scope: 'All' }
});

const assistantSource = await readFile(new URL('../src/pages/individual/ai-assistant/AIAssistant.js', import.meta.url), 'utf8');
const conversationAnswerSource = await readFile(new URL('../src/components/common/ConversationAnswer.js', import.meta.url), 'utf8');
const assistantCss = await readFile(new URL('../src/pages/individual/ai-assistant/ai-assistant.css', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../src/app/app.js', import.meta.url), 'utf8');
assert.equal((assistantSource.match(/id="btnOpenFilters"/g) || []).length, 1, 'there is one Filters trigger');
assert.match(assistantSource, /document\.body\.appendChild\(filterPanel\)/, 'popover escapes clipping ancestors');
assert.match(assistantSource, /event\.key === 'Escape'/, 'Escape closes the filter panel');
assert.match(assistantSource, /pointerdown', filterPopoverDismissHandler, true/, 'outside pointer dismisses the panel');
assert.match(assistantSource, /fetchIntelligenceConversations\(\{ limit: 100, domain, portalType: 'individual' \}\)/, 'history queries stay within the active domain and portal');
assert.match(assistantSource, /fetchConversationHistory\(convId, \{ domain: getActiveDomainKey\(\), portalType: 'individual' \}\)/, 'restored conversations are checked against their active domain and portal');
assert.match(assistantSource, /deleteIntelligenceConversation\(convId, \{ domain: getActiveDomainKey\(\), portalType: 'individual' \}\)/, 'deletes are checked against their active domain and portal');
assert.match(assistantSource, /window\.addEventListener\('hashchange'/, 'leaving Assistant closes temporary menus and invalidates in-flight requests');
assert.match(assistantCss, /body:has\(\.ai-ref-workspace-page\) \.sidebar \{ display: flex !important; \}/, 'Assistant preserves the portal sidebar');
assert.doesNotMatch(assistantCss, /body:has\(\.ai-ref-workspace-page\) \.sidebar,[\s\S]{0,100}?display: none !important/, 'Assistant does not hide portal navigation');
assert.match(assistantCss, /\.ai-history-drawer,\s*\.ai-history-drawer\.is-open \{[\s\S]*?right: 12px;[\s\S]*?width: min\(380px/, 'history opens as a compact right-side drawer');
assert.match(assistantCss, /font-family: 'DM Sans'/, 'Assistant controls and content share the portal font');
assert.match(assistantCss, /assistant-loading-shimmer/, 'loading feedback uses the shared subtle shimmer treatment');
assert.match(assistantCss, /@media \(prefers-reduced-motion: reduce\)/, 'decorative motion respects reduced-motion preferences');
assert.match(appSource, /\{ label: 'AI Assistant', icon: 'sparkles', route: '\/individual\/ai-assistant' \}/, 'the portal sidebar keeps the Assistant route available');
assert.match(assistantSource, /data-action="regenerate_answer"/, 'answers expose a regeneration action');
assert.match(assistantSource, /replaceTurnId: turn\.id/, 'regeneration replaces the original local turn');
assert.match(assistantSource, /ai-ref-feature-card--\$\{featureIndex \+ 1\}/, 'feature cards use distinct visual treatments');
assert.match(assistantSource, /capabilityId: selectedCapabilityId/, 'focused capability is included in the answer request');
assert.match(assistantSource, /reasonCodes\.includes\('INTELLIGENCE_SOURCE_UNAVAILABLE'\)[\s\S]*'data_source_unavailable'/, 'provider outages render as data-source failures rather than unsupported capabilities');
assert.match(assistantSource, /\['error', 'failed', 'data_source_unavailable'\]\.includes\(statusKey\)[\s\S]*Retry this question/, 'provider outages offer a retry for the original question');
assert.match(assistantSource, /\['unsupported', 'requires_clarification'\]\.includes\(turn\.execution_status\)/, 'unsupported and clarification outcomes retain their distinct backend statuses');
assert.match(assistantSource, /data-open-explainer/, 'discovery cards open a preview without attaching a capability');
assert.match(assistantSource, /available_ranges[\s\S]*Max Available/, 'time choices are based on catalogue coverage with a Max Available fallback');
assert.doesNotMatch(assistantSource, /scope === 'My Skills'/, 'My scope is not used by the assistant');
assert.doesNotMatch(assistantSource, /selectedSkillsPayload|selectedCompaniesPayload/, 'the composer no longer carries hidden selected-entity request state');
assert.match(assistantSource, /function buildSupportedInsightChips\(turn, activeDomain\)[\s\S]*turn\.facts/, 'suggested insight questions use the current turn evidence');
assert.doesNotMatch(assistantSource.slice(assistantSource.indexOf('function buildSupportedInsightChips'), assistantSource.indexOf('function renderTurnHTML')), /domState\.filters/, 'suggestions do not reuse stale filter selections');
const createConversationSource = assistantSource.slice(assistantSource.indexOf('createIntelligenceConversation({'), assistantSource.indexOf('});', assistantSource.indexOf('createIntelligenceConversation({')));
assert.doesNotMatch(createConversationSource, /filters\s*:/, 'new conversations do not persist hidden filter state');
assert.doesNotMatch(assistantSource, /focusSkill\s*\?/, 'default skill queries do not reference an undefined legacy variable');

const skillPage = await readFile(new URL('../src/pages/individual/skills/SkillIntelligence.js', import.meta.url), 'utf8');
assert.match(skillPage, /Reference only/, 'reference skills are visibly kept separate');
assert.match(skillPage, /Sorted A–Z by canonical skill name/, 'skill catalog documents its canonical-name sort order');
assert.match(skillPage, /sortCatalogByName\(viewRows\)/, 'skill catalog sorts all filtered rows before pagination');
assert.match(skillPage, /: summary\.direction;/, 'skills without a valid trend retain the explicit unavailable direction');
assert.match(skillPage, /analysis\.trend\?\.reason \|\| summary\.unavailableReason/, 'the evidence details preserve the unavailable reason');
assert.match(skillPage, /data-action="toggle-favourite"/, 'catalog rows expose persistent favourites');
assert.match(skillPage, /saveFavouriteSkillIds\(next\)/, 'favourite changes persist through the authenticated API');
assert.match(skillPage, /catalogView === 'favorites'/, 'the catalogue Favourites view is backed by saved favourite IDs');
assert.match(skillPage, /scope="col" title="Save this skill to your favourites">Favourite/, 'observed table has a dedicated accessible Favourite column');
assert.match(skillPage, /talentscope:favourites-updated/, 'favourite changes notify other intelligence entry points');
assert.match(skillPage, /pageState\.favoriteSkillIds = next;\s+pageState\.favoriteSaving = true;\s+renderPage\(\)/, 'favourite star updates optimistically and prevents overlapping writes');
assert.match(skillPage, /pageState\.favoriteSkillIds = previousIds/, 'failed favourite writes roll back the optimistic star');

const marketPage = await readFile(new URL('../src/pages/individual/market/MarketIntelligence.js', import.meta.url), 'utf8');
assert.match(marketPage, /id="miCatalogSearch"/, 'market catalog supports entity search');
assert.match(marketPage, /id="miCatalogSort"/, 'market catalog supports sorting');
assert.match(marketPage, /paginateCatalog\(visibleCompanies, marketCompanyPage\)/, 'employers paginate after full-catalog search and sorting');
assert.match(marketPage, /miCatalogPrevious/, 'employer catalog exposes pagination controls');
assert.match(marketPage, /miCatalogSource/, 'employer catalog filters by stored source');
assert.match(marketPage, /no company-level market telemetry/i, 'posting evidence is not represented as company telemetry');
assert.match(marketPage, /latest_posted_at/, 'company rows show real stored posting dates when available');
assert.match(marketPage, /item\.evidence_links/, 'company rows link to genuine stored posting evidence');
assert.match(marketPage, /marketCompanyFavouriteIds = previous;\s+syncMarketFavouritePresentation\(\)/, 'failed company favourite writes restore saved state and refresh presentation');

const homeSource = await readFile(new URL('../src/app/app.js', import.meta.url), 'utf8');
assert.match(homeSource, /__talentscopeCommittedIntelligenceFilters/, 'Home reads and commits the shared domain filter contract');
assert.match(assistantSource, /__talentscopeCommittedIntelligenceFilters/, 'Assistant reads and commits the same domain filter contract');

// Domain-specific capabilities use IDs registered by the backend answer engine.
assert.ok(DOMAIN_CAPABILITY_REGISTRY, 'DOMAIN_CAPABILITY_REGISTRY is defined and exported');
const catalogRecords = new Map();
for (const capabilities of Object.values(DOMAIN_CAPABILITY_REGISTRY)) {
  assert.equal(new Set(capabilities.map(capability => capability.id)).size, capabilities.length, 'domain capability IDs are unique');
  for (const capability of capabilities) {
    assert.ok(capability.capabilityId === capability.id, `${capability.id} uses its canonical backend ID`);
    const record = catalogRecords.get(capability.id) || {
      capability_id: capability.id,
      global_status: 'available',
      handler: 'registered',
      supported_domains: []
    };
    record.supported_domains.push(...capability.supportedDomains);
    catalogRecords.set(capability.id, record);
  }
}
const backendCatalog = { capabilities: [...catalogRecords.values()] };
assert.equal(getDomainCapabilities('skill').length, 0, 'capabilities are not advertised before the authenticated backend catalog loads');
assert.equal(getDomainCapabilities('skill', backendCatalog).length, 3, 'Skill presentation is filtered by backend registrations to exactly 3 features');
assert.equal(getDomainCapabilities('market', backendCatalog).length, 2, 'Market presentation uses backend-supported operations with exactly 2 features');
assert.equal(getDomainCapabilities('job', backendCatalog).length, 2, 'Job presentation uses backend-supported operations with exactly 2 features');
assert.equal(resolveActiveCapabilityId({
  executed_primary_capability: 'skill_change_alert',
  planned_primary_capability: 'skill_future_relevance_score',
  capabilities_used: ['skill_change_alert'],
  planned_capabilities: ['skill_future_relevance_score']
}, 'skill', backendCatalog), 'skill_change_alert', 'executed route takes precedence over the selected-feature hint');
assert.equal(resolveActiveCapabilityId({
  capabilities_used: [],
  planned_capabilities: ['skill_change_alert']
}, 'skill', backendCatalog), 'skill_change_alert', 'planned route updates the active feature even while asking for missing context');
assert.equal(resolveActiveCapabilityId({
  capabilities_used: [],
  planned_capabilities: []
}, 'skill', backendCatalog), null, 'unmatched requests do not activate or attribute a capability');
const skillCapabilities = getDomainCapabilities('skill', backendCatalog);
const marketCapabilities = getDomainCapabilities('market', backendCatalog);
const jobCapabilities = getDomainCapabilities('job', backendCatalog);
for (const capability of [...skillCapabilities, ...marketCapabilities, ...jobCapabilities]) {
  assert.ok(capability.suggestedQuestions.length >= 3, `${capability.id} has contextual optional suggestions`);
  assert.ok(capability.suggestedQuestions.every(question => typeof question === 'string' && question.length > 0));
}
assert.deepEqual(skillCapabilities.map(capability => capability.id), [
  'skill_future_relevance_score',
  'skill_change_alert',
  'adaptive_skill_roadmap'
], 'Skill suggestions are attached only to the 3 approved Skill capabilities');
assert.deepEqual(marketCapabilities.map(capability => capability.id), [
  'technology_adoption_shift_detector',
  'technology_impact_explorer'
], 'Market suggestions are attached only to the 2 approved Market capabilities');
assert.deepEqual(jobCapabilities.map(capability => capability.id), [
  'skill_based_job_match',
  'career_transition_opportunity'
], 'Job suggestions are attached only to the 2 approved Job capabilities');
const sfrCapability = skillCapabilities.find(capability => capability.id === 'skill_future_relevance_score');
const scaCapability = skillCapabilities.find(capability => capability.id === 'skill_change_alert');
const asrCapability = skillCapabilities.find(capability => capability.id === 'adaptive_skill_roadmap');
const tasdCapability = marketCapabilities.find(capability => capability.id === 'technology_adoption_shift_detector');
const tieCapability = marketCapabilities.find(capability => capability.id === 'technology_impact_explorer');
const sbjmCapability = jobCapabilities.find(capability => capability.id === 'skill_based_job_match');
const ctoCapability = jobCapabilities.find(capability => capability.id === 'career_transition_opportunity');
assert.equal(sfrCapability.title, 'Skill Future Relevance Score');
assert.equal(sfrCapability.category, 'Skill Relevance');
assert.match(sfrCapability.defaultPrompt, /future relevance score/i);
assert.match(sfrCapability.explainer.limitations, /bounded by observable data/i);
assert.equal(scaCapability.title, 'Skill Change Alert');
assert.equal(scaCapability.category, 'Skill Alerts');
assert.match(scaCapability.defaultPrompt, /change alerts/i);
assert.equal(asrCapability.title, 'Adaptive Skill Roadmap');
assert.equal(asrCapability.category, 'Skill Pathways');
assert.match(asrCapability.defaultPrompt, /adaptive skill roadmap/i);
assert.equal(tasdCapability.title, 'Technology Adoption Shift Detector');
assert.equal(tasdCapability.category, 'Market Shifts');
assert.match(tasdCapability.explainer.limitations, /developer activity is not conflated with employer demand/i);
assert.equal(tieCapability.title, 'Technology Impact Explorer');
assert.equal(tieCapability.category, 'Market Impact');
assert.equal(sbjmCapability.title, 'Skill-Based Job Match');
assert.equal(sbjmCapability.category, 'Job Matching');
assert.match(sbjmCapability.explainer.limitations, /verified job postings/i);
assert.equal(ctoCapability.title, 'Career Transition Opportunity');
assert.equal(ctoCapability.category, 'Career Pathways');
assert.match(ctoCapability.explainer.limitations, /O\*NET\/ESCO/i);
assert.equal(shouldShowUnappliedFilterDisclosure({
  intent: 'lookup_skill_reference',
  planned_capabilities: ['skill_technology_reference'],
  unapplied_filters: [{ filter: 'salary_band' }]
}), false, 'irrelevant filters do not dominate a taxonomy answer');
assert.equal(shouldShowUnappliedFilterDisclosure({
  intent: 'search_jobs',
  planned_capabilities: ['job_posting_search'],
  unapplied_filters: [{ filter: 'salary_band' }]
}), true, 'posting filter limitations remain visible');
assert.equal(
  resolveDisplayedCapabilityId({ capabilities_used: ['trend_velocity_analysis'] }),
  'trend_velocity_analysis',
  'automatically classified answers are attributed to the capability actually executed'
);
assert.equal(
  resolveDisplayedCapabilityId({
    capabilityId: 'skill_health_analysis',
    capabilities_used: [],
    planned_capabilities: ['skill_technology_reference']
  }),
  'skill_technology_reference',
  'the active feature follows the routed capability even when its data gate is not ready'
);
assert.equal(
  resolveDisplayedCapabilityId({ capabilityId: 'skill_technology_reference', capabilities_used: ['trend_velocity_analysis'] }),
  'trend_velocity_analysis',
  'execution attribution takes precedence when it differs from the requested capability'
);
assert.equal(
  resolveDisplayedCapabilityId({ capabilityId: 'trend_velocity_analysis', capabilities_used: [] }),
  null,
  'unexecuted capability requests do not claim an executed feature'
);
assert.equal(resolveDisplayedCapabilityId({
  capabilityId: 'market_snapshot',
  status: 'insufficient_data',
  capabilities_used: []
}), null, 'insufficient-data responses do not claim a capability was executed');
const priorTurnContext = {
  domain: 'skill',
  capabilityId: 'trend_velocity_analysis',
  capability_id: 'trend_velocity_analysis',
  timeRange: '6m',
  selectedSkills: ['Python'],
  filters: {
    domain: 'skill',
    selected_feature: 'trend_velocity_analysis',
    selected_skills: ['Python'],
    requested_time_window: '6m'
  }
};
const followUpContext = buildFollowUpRequestContext(priorTurnContext);
assert.equal('capabilityId' in followUpContext, false, 'follow-up questions are routed from their own intent');
assert.equal('capability_id' in followUpContext, false, 'snake-case capability IDs are also cleared');
assert.equal('filters' in followUpContext, false, 'follow-ups do not carry legacy hidden filters');
assert.equal(followUpContext.timeRange, 'max', 'follow-ups use the full available history');
assert.equal('selectedSkills' in followUpContext, false, 'follow-ups rely on conversation context rather than hidden entity selections');
const technicalDisclosure = formatUnappliedFilterDisclosure({
  filter: 'selected_feature',
  reason: 'CAPABILITY_NOT_SUPPORTED_IN_DOMAIN'
});
assert.match(technicalDisclosure, /not supported for this request/i);
assert.doesNotMatch(technicalDisclosure, /selected_feature|CAPABILITY_NOT_SUPPORTED_IN_DOMAIN/);
const salaryDisclosure = formatUnappliedFilterDisclosure({
  filter: 'salary_band',
  reason: "Filter 'salary_band' is not supported by current normalized market series."
});
assert.match(salaryDisclosure, /Salary range/i);
assert.match(salaryDisclosure, /stored market data/i);
assert.equal(getAssistantComposerMode({}), 'normal', 'empty composer state is normal chat');
assert.equal(getAssistantComposerMode({ selectedFeature: 'skill_health' }), 'feature', 'a single capability activates feature mode');
assert.equal(getAssistantComposerMode({ selectedFeature: 'skill_health', guidedJourney: { id: 'guided' } }), 'guided', 'guided mode has precedence over an incidental current-step capability');
const unavailableCatalog = {
  capabilities: backendCatalog.capabilities.map(record => record.capability_id === 'trend_velocity_analysis'
    ? { ...record, global_status: 'building' }
    : record)
};
assert.ok(!getDomainCapabilities('skill', unavailableCatalog).some(capability => capability.id === 'trend_velocity_analysis'));
const wrongDomainCatalog = {
  capabilities: backendCatalog.capabilities.map(record => record.capability_id === 'market_snapshot'
    ? { ...record, supported_domains: ['skill'] }
    : record)
};
assert.ok(!getDomainCapabilities('market', wrongDomainCatalog).some(capability => capability.id === 'market_snapshot'));
assert.ok(!getDomainCapabilities('skill', backendCatalog).some(capability => ['skill_half_life', 'ai_disruption', 'forecast'].includes(capability.id)));
assert.ok(!getDomainCapabilities('market', backendCatalog).some(capability => ['hiring_velocity', 'tech_benchmarks', 'regional_concentration'].includes(capability.id)));

// Verify Explainer metadata integrity
for (const [domKey, caps] of Object.entries(DOMAIN_CAPABILITY_REGISTRY)) {
  for (const cap of caps) {
    assert.ok(cap.id, `Capability in ${domKey} must have an id`);
    assert.ok(cap.title, `Capability ${cap.id} must have a title`);
    assert.ok(cap.category, `Capability ${cap.id} must have a category`);
    assert.ok(cap.desc, `Capability ${cap.id} must have a desc`);
    assert.ok(cap.cardTagline, `Capability ${cap.id} must define a concise discovery-card tagline`);
    assert.ok(cap.explainer?.whatItDoes, `Capability ${cap.id} must define whatItDoes`);
    assert.ok(cap.explainer?.inputsNeeded, `Capability ${cap.id} must define inputsNeeded`);
    assert.ok(cap.explainer?.outputProduced, `Capability ${cap.id} must define outputProduced`);
    assert.ok(cap.explainer?.limitations, `Capability ${cap.id} must define limitations`);
  }
}

// Capability cards on Landing View are Explainers Only (never feature selectors or auto-senders)
assert.match(assistantSource, /data-open-explainer="\$\{escapeHTML\(feat\.id\)\}"/, 'Landing cards trigger explainer modal');
assert.match(assistantSource, /activeExplainerCapability\s*=\s*caps\.find/, 'Explainer card click activates the explainer modal');
assert.match(assistantSource, /id="btnCloseCapabilityExplainer"/, 'Explainer modal provides a close action');
assert.match(assistantSource, /id="aiExplainerBackdrop"/, 'Explainer modal provides backdrop dismissal');

// Features Button inside Composer is the ONLY place capabilities are selected
assert.match(assistantSource, /class="ai-feature-selector-list"/, 'Features popover provides a single-column list of capabilities');
assert.match(assistantSource, /data-select-feature-id=/, 'Popover items allow capability selection');
assert.match(assistantSource, /domState\.selectedFeature\s*=\s*featId/, 'Selecting a capability sets domState.selectedFeature');
assert.match(assistantSource, /class="ai-composer-feature-chip-banner(?:\s|")/, 'Composer renders a removable chip banner when a feature is selected');
assert.match(assistantSource, /id="btnRemoveActiveFeature"/, 'Composer provides active feature chip removal button');
assert.match(assistantSource, /<span>Features<\/span>/, 'compact feature picker has a short title');
assert.match(assistantSource, /event\.key === 'ArrowDown'/, 'feature picker supports arrow-key navigation');
assert.match(assistantSource, /data-open-explainer/, 'discovery card selection stays separate from composer capability attachment');
assert.match(assistantSource, /id="btnRemoveGuidedJourney"/, 'guided mode chip provides an explicit exit action');
assert.match(assistantSource, /placeholder="\$\{escapeHTML\(isGuidedMode[\s\S]*Ask your question to begin a guided analysis/, 'guided mode gives the composer an explicit question placeholder');
assert.match(assistantSource, /requestRecommendedCapability\(query, domain, domState\)/, 'guided mode plans its first capability from the submitted question');
assert.match(assistantSource, /No specialized capability matched\. Sending your question through normal chat\./, 'guided mode falls back to normal chat when no specialized operation applies');
assert.match(assistantSource, /guidedJourney = null;\s*domState\.selectedFeature = null;/, 'leaving guided mode clears its current capability');
assert.match(assistantSource, /await executeAiQuery\(query, \{ selectedFeatureId \}\);\s*\}/, 'submitting preserves the selected capability mode for conversation follow-ups');
assert.match(assistantSource, /guidedJourneyId: savedJourney\?\.completedCapabilityIds\?\.includes\(capabilityId\)/, 'restored completed guided steps retain a locally persisted journey when available');
assert.match(assistantSource, /usedCapability \?/, 'conversation responses identify the capability that produced them');
assert.doesNotMatch(assistantSource, /ai-res-unapplied-banner/, 'the individual assistant no longer renders legacy hidden-filter disclosures');
const executeQuerySource = assistantSource.slice(assistantSource.indexOf('async function executeAiQuery'));
assert.match(executeQuerySource, /timeRange: 'max'/, 'individual assistant requests use the maximum supported historical window');
assert.match(executeQuerySource, /domain: null/, 'user messages do not force a Skill, Market, or Job domain');
assert.match(executeQuerySource, /planResult = await queryCoreIntelligencePlan\(\{[\s\S]*?message: question,[\s\S]*?portalType: 'individual'/, 'each user message gets a domain-unset plan before the answer request');
assert.match(executeQuerySource, /understood: typeof planResult\?\.understood === 'string'/, 'the turn retains the exact understood sentence from its plan');
assert.doesNotMatch(executeQuerySource, /scope_empty|selectedSkillsPayload|selectedCompaniesPayload|filters:\s*\{/, 'invisible legacy filters and scope state are not sent to the answer endpoint');
assert.doesNotMatch(assistantSource, /escapeHTML\(u\.filter\).*escapeHTML\(u\.reason\)/, 'raw filter identifiers and backend diagnostics are not rendered directly');
assert.doesNotMatch(assistantSource, /data-ai-domain=/, 'the Assistant has no Skill, Market, or Job domain controls');
assert.match(assistantSource, /const created = await createIntelligenceConversation\(/, 'New chat creates a backend-issued conversation');
assert.match(assistantSource, /domState\.history = \[\];[\s\S]*?domState\.draftQuestion = '';/, 'New chat clears the local transcript and composer draft');
assert.match(conversationAnswerSource, /label: 'Could not complete'/, 'failed requests have an explicit non-success label');
assert.match(conversationAnswerSource, /role="\$\{\['blocked', 'error', 'failed'\]/, 'access and execution failures use an alert');

const responseDetails = renderAssistantResponseDetails({
  understood: 'You want to search stored job postings.',
  status: 'insufficient_data',
  enough_data: false,
  limitations: ['No matching postings were found.'],
  degraded: true,
  degraded_reason: 'internal_provider_timeout',
  intent: 'search_jobs',
  sources: [
    { type: 'stored posting', label: 'Stored role', source_url: 'https://jobs.example/role/1' },
    { type: 'external', label: 'Unsecured source', source_url: 'http://jobs.example/role/2' }
  ],
  evidence: [{ signal_type: 'job_demand', description: 'Stored evidence', source_url: 'https://evidence.example/item/3' }],
  facts: [{ fact_type: 'stored_job_postings', details: { scanned_count: 22, matched_count: 0, city: 'Kolkata' } }],
  clarification: 'Would you like to narrow the request?'
});
assert.match(responseDetails, /Understood:<\/strong> You want to search stored job postings\./);
assert.match(responseDetails, /Limited data/);
assert.match(responseDetails, /No matching postings were found\./);
assert.match(responseDetails, /Gemini unavailable, showing deterministic answer/);
assert.doesNotMatch(responseDetails, /internal_provider_timeout/);
assert.match(responseDetails, /scanned 22, matched 0, city Kolkata/);
assert.match(responseDetails, /live search is off/);
assert.match(responseDetails, /Would you like to narrow the request\?/);
assert.match(responseDetails, /data-assistant-follow-up="skills"/);
assert.match(responseDetails, /data-assistant-follow-up="jobs"/);
assert.match(responseDetails, /data-assistant-follow-up="market signals"/);
assert.equal((responseDetails.match(/<a href=/g) || []).length, 2, 'only stored HTTPS source_url values render as links');
assert.doesNotMatch(responseDetails, /href="http:\/\/jobs\.example/);

const demoResponseDetails = renderAssistantResponseDetails({
  status: 'insufficient_data',
  evidence: [{ signal_type: 'skill_adoption', description: 'Sample observation', data_origin: 'demo' }]
});
assert.match(demoResponseDetails, /DEMO SAMPLE — illustrative data only; not live market evidence\./);
assert.doesNotMatch(responseDetails, /DEMO SAMPLE/);

const realTrendChart = renderTurnChartOrBaselineHTML({}, {
  readiness_state: 'ready',
  data_origin: 'real',
  period: '2024-01_to_2024-04',
  details: { series: [{ period: '2024-01', value: 0.2 }, { period: '2024-04', value: 0.4 }], provider: 'jsearch', signal_type: 'demand', metric: 'normalized_share', value_unit: 'share' }
}, [], []);
const insecurePostingLink = renderTurnChartOrBaselineHTML({}, null, [], [{
  title: 'Stored role',
  source_url: 'http://jobs.example/role/1'
}]);
assert.doesNotMatch(insecurePostingLink, /href="http:\/\/jobs\.example/);
assert.match(insecurePostingLink, /http:\/\/jobs\.example\/role\/1/);
assert.ok(realTrendChart.includes('2024-01') && realTrendChart.includes('2024-04'));
assert.ok(realTrendChart.includes('jsearch') && realTrendChart.includes('normalized_share') && realTrendChart.includes('share'));
assert.ok(!renderTurnChartOrBaselineHTML({}, { period: 'window', details: { observation_count: 4 } }, [], []).includes('<svg'), 'no chart is drawn unless actual series points are returned');
assert.equal(renderTurnChartOrBaselineHTML({}, {
  readiness_state: 'insufficient_data', data_origin: 'real',
  details: { series: [{ period: '2024-01', value: 0.2 }, { period: '2024-04', value: 0.4 }] }
}, [], []), '', 'an unready trend cannot produce a measured chart');
assert.equal(renderTurnChartOrBaselineHTML({}, {
  readiness_state: 'ready', data_origin: 'benchmark',
  details: { series: [{ period: '2024-01', value: 0.2 }, { period: '2024-04', value: 0.4 }] }
}, [], []), '', 'benchmark data cannot be presented as a real measured chart');

// Conversational AI Turn Flow & Actions
assert.match(assistantSource, /class="ai-user-turn-wrapper"/, 'User turn is right-aligned in conversation stream');
assert.match(assistantSource, /class="ai-assistant-turn-card ai-conv-card-modern"/, 'Assistant turn uses modern card layout');
assert.match(assistantSource, /renderConversationAnswer\(turn, formatMarkdown/, 'Assistant turn uses the shared natural-language answer renderer');
assert.match(assistantSource, /data-action="copy_answer"/, 'Turn footer includes copy answer button');
assert.match(assistantSource, /data-feedback="up"/, 'Turn footer includes thumbs-up feedback');
assert.match(assistantSource, /data-feedback="down"/, 'Turn footer includes thumbs-down feedback');
assert.match(assistantSource, /data-feedback="up" data-turn-index="\$\{index\}"/, 'Feedback actions are bound to their assistant turn');
assert.match(assistantSource, /requestContext: buildFollowUpRequestContext\(turn\?\.requestContext\)/, 'follow-ups preserve context without pinning the previous capability');
assert.match(assistantSource, /writeText\(cleanConversationAnswer/, 'copy actions omit hidden internal fields');

// Guided Intelligence Journey & backend-driven recommendation checks
assert.match(assistantSource, /queryCoreIntelligencePlan\(/, 'recommendations are planned by the authenticated backend engine');
assert.match(assistantSource, /plan\.selected_capabilities/, 'recommendation uses the planner-selected capability');
assert.match(assistantSource, /readiness\.can_execute/, 'unready capabilities are not silently attached');
assert.match(assistantSource, /data-feature-prompt/, 'suggestion chips use the assistant composer prompt attribute');
assert.match(assistantSource, /input\.value = prompt;\s+domState\.draftQuestion = prompt;/, 'suggestion clicks populate the regular composer draft');
assert.match(assistantSource, /domState\.selectedFeature = activeCapability\.id;/, 'automatic capability routing updates the active feature');
assert.match(assistantSource, /planned_capabilities/, 'clarification and readiness responses can identify the planned feature without claiming execution');
assert.match(assistantSource, /capabilityId: routedCapabilityId/, 'turn context is attributed to the capability actually executed');
assert.match(assistantSource, /capabilities_used[\s\S]*getDomainCapabilities\(dom\)/, 'active feature follows backend execution attribution');

// Guided journeys suggest only a registered, uncompleted next operation.
const journey = {
  id: 'journey-test',
  originalQuestion: 'What is the future relevance score for Python?',
  completedCapabilityIds: ['skill_future_relevance_score'],
  currentCapabilityId: 'skill_future_relevance_score',
  remainingCapabilityIds: ['skill_change_alert', 'adaptive_skill_roadmap'],
  readinessEvaluated: true,
  readinessCapabilityId: 'skill_change_alert',
  nextCapabilityReady: true
};
const initialTurn = {
  userQuestion: 'What is the future relevance score for Python?',
  status: 'ready',
  selectedFeature: 'skill_future_relevance_score',
  capabilityId: 'skill_future_relevance_score',
  guidedJourneyId: journey.id,
  capabilities_used: ['skill_future_relevance_score']
};
const step1 = resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], journey, backendCatalog);
assert.ok(step1 && !step1.isComplete, 'Next step after skill_future_relevance_score should be provided');
assert.equal(step1.nextCapability.id, 'skill_change_alert');
assert.equal(resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], {
  ...journey,
  readinessEvaluated: false
}, backendCatalog), null, 'journey does not suggest a step before readiness is checked');
assert.ok(resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], {
  ...journey,
  nextCapabilityReady: false
}, backendCatalog)?.isComplete, 'journey does not suggest a capability that fails readiness');
const skippedStep = resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], {
  ...journey,
  skippedCapabilityIds: ['skill_change_alert'],
  readinessCapabilityId: 'adaptive_skill_roadmap'
}, backendCatalog);
assert.equal(skippedStep?.nextCapability.id, 'adaptive_skill_roadmap', 'journey advances past an unready step without repeating it');
assert.equal(resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], null, backendCatalog), null, 'normal chat has no automatic guided step');

const completeJourney = { ...journey, completedCapabilityIds: [...journey.completedCapabilityIds, 'skill_change_alert'], remainingCapabilityIds: [] };
const completedStep = resolveNextJourneyStep(initialTurn, 'skill', [initialTurn], completeJourney, backendCatalog);
assert.ok(completedStep?.isComplete, 'journey does not repeat steps after the eligible sequence is exhausted');

// UI Structure & Brand System Tests
assert.match(assistantSource, /class="ai-hero-brand-mark"><i data-lucide="sparkles"><\/i><\/span>/, 'Hero orbit reuses the established TalentScope AI sparkle identity');
assert.doesNotMatch(assistantSource, /Verified Telemetry<\/span>/, 'conversation headers do not claim telemetry when no freshness date is returned');
assert.match(assistantSource, /id="btnStartGuidedJourney" aria-label="Start Guided Intelligence Journey"/, 'guided analysis is a clearly named persistent composer control');
assert.match(assistantSource, /id="btnRecommendAnalysis"/, 'Composer includes Recommend My Analysis quick action');
assert.match(assistantSource, /id="btnStartGuidedJourney"/, 'guided journey has an explicit optional start action');
assert.match(assistantSource, /getCapabilityCatalog\(\)/, 'supported capability availability is loaded from the authenticated backend registry');
assert.match(assistantSource, /class="ai-conv-journey-card"/, 'Conversational turn footer renders Guided Journey next-step card');
assert.match(assistantSource, /if \(!hist \|\| hist\.conversation_id !== convId\)/, 'a missing history response does not masquerade as a successful restore');
assert.match(assistantSource, /domState\.history = Array\.isArray\(hist\.turns\) \? hist\.turns\.map/, 'restoring an empty chat clears the previous chat transcript');
assert.match(assistantSource, /isHistoryModalOpen = false;\s*historyLoading = false;/, 'restoring history closes the modal and ends its loading state');
assert.match(assistantSource, /if \(isCreatingConversation\) return;/, 'duplicate new-chat requests are prevented');
assert.match(assistantSource, /if \(!created\?\.conversation_id\) throw new Error/, 'new chat requires a backend-issued conversation ID');
assert.match(assistantSource, /assistantRootClickContainer\.removeEventListener\('click', assistantRootClickHandler\)/, 'rerenders replace rather than accumulate page-level click handlers');
assert.match(assistantSource, /class="ai-history-open-btn"[^>]*data-restore-conv=/, 'history entries can be restored with keyboard-accessible buttons');
assert.match(assistantCss, /\.ai-history-open-btn:focus-visible/, 'history entry controls have visible keyboard focus');
assert.match(assistantCss, /\.ai-feature-cards-grid\s*\{\s*display:\s*grid;\s*grid-template-columns:\s*repeat\(6, minmax\(0, 1fr\)\)/, 'desktop discovery uses six compact columns');
assert.match(assistantCss, /\.ai-feature-count-4\s*\{\s*grid-template-columns:\s*repeat\(4, minmax\(0, 1fr\)\)/, 'four supported cards share one centered row');
assert.match(assistantCss, /\.ai-feature-count-5\s*\{\s*grid-template-columns:\s*repeat\(5, minmax\(0, 1fr\)\)/, 'five supported cards share one centered row');
assert.match(assistantCss, /\.ai-feature-card\s*\{[^}]*min-height:\s*72px/s, 'discovery cards use compact desktop heights');
assert.match(assistantCss, /\.ai-feature-content\s*\{[^}]*min-width:\s*0/s, 'card text can shrink and wrap within its grid track');
assert.match(assistantCss, /\.ai-feature-chip-remove-btn\s*\{[^}]*width:\s*32px/s, 'selected-mode remove control has a usable 32px target');
assert.match(assistantCss, /\.ai-composer-feature-chip-banner--feature \.ai-feature-chip-pill\s*\{[^}]*var\(--feature-accent\)/s, 'focused composer accent is driven by the selected capability color');
assert.match(assistantCss, /\.ai-composer-feature-chip-banner--guided \.ai-feature-chip-pill\s*\{[^}]*#f5edff/s, 'guided composer has a distinct violet treatment');
assert.match(assistantCss, /\.ai-conv-mode-pill\.is-feature\s*\{[^}]*var\(--feature-accent\)/s, 'conversation mode accent follows the selected capability');
assert.equal((assistantSource.match(/id="btnStartGuidedJourney"/g) || []).length, 1, 'guided-mode trigger appears once inside the composer');
assert.match(assistantCss, /\.ai-conv-service-error\s*\{/, 'service failures have a dedicated, non-answer visual state');

// Privacy & Error Message Hygiene
assert.doesNotMatch(assistantSource, /Could not reach the Core Intelligence service at \$\{API_BASE_URL\}/, 'Assistant error messages never leak backend service URLs');

console.log('INTELLIGENCE CATALOG AND FILTER TESTS: domain options, supported entities, Apply/Cancel/Reset, provenance, measured sorting, search, and popover accessibility passed');
console.log('AI ASSISTANT REDESIGN TESTS: canonical capabilities, explainer previews, focused request routing, optional guided journey, and conversational actions passed');
