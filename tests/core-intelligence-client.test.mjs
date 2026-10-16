import assert from 'node:assert/strict';
// Setup browser globals for test environment
globalThis.window = {
  TALENTSCOPE_API_BASE_URL: 'http://127.0.0.1:8000',
  // Test-only authenticated client boundary; production still reads Firebase directly.
  talentscopeGetAuthToken: async () => 'mock-firebase-id-token'
};

const {
  normalizeTimeRange,
  buildCoreIntelligenceRequest,
  adaptTrendItem,
  adaptCoreIntelligenceResponse,
  sendCoreIntelligenceRequest,
  queryCoreIntelligence,
  querySkillIntelligence,
  queryMarketIntelligence,
  queryJobIntelligence,
  adaptActionRecommendation,
  adaptActionRecommendationResponse,
  queryActionRecommendations,
  buildAnswerRequest,
  adaptFactItem,
  adaptEvidenceItem,
  adaptCoreIntelligenceAnswerResponse,
  queryCoreIntelligenceAnswer,
  queryCoreIntelligencePlan,
  resolveEntity,
  getCapabilityCatalog,
  evaluateCapabilities,
  getAuthIdToken
} = await import('../src/api/core-intelligence-client.js');
const { loadSkillCatalog, loadMarketCatalog, formatObservationPeriod } =
  await import('../src/api/intelligence-catalog-client.js');

{
  const configuredOrigin = window.TALENTSCOPE_API_BASE_URL;
  const configuredLocation = window.location;
  delete window.TALENTSCOPE_API_BASE_URL;
  window.location = { origin: 'http://localhost:3000' };
  const { API_BASE_URL: localApiOrigin } = await import('../src/config/api.js?local-api');
  assert.equal(localApiOrigin, 'http://localhost:8000', 'local frontend uses its documented FastAPI development port');
  window.location = { origin: 'http://127.0.0.1:3000' };
  const { API_BASE_URL: loopbackApiOrigin } = await import('../src/config/api.js?loopback-api');
  assert.equal(loopbackApiOrigin, 'http://127.0.0.1:8000', 'loopback frontend preserves its hostname when selecting the local API');
  window.location = { origin: 'https://assistant.talentscope.example' };
  const { API_BASE_URL } = await import('../src/config/api.js?same-origin');
  assert.equal(API_BASE_URL, 'https://assistant.talentscope.example');
  window.TALENTSCOPE_API_BASE_URL = configuredOrigin;
  window.location = configuredLocation;
}

const registeredTests = [];
function test(name, run) {
  registeredTests.push({ name, run });
}

test('normalizeTimeRange maps raw frontend ranges to standard keys', () => {
  assert.equal(normalizeTimeRange('7 Days'), '7d');
  assert.equal(normalizeTimeRange('30 Days'), '30d');
  assert.equal(normalizeTimeRange('3 Months'), '3m');
  assert.equal(normalizeTimeRange('6 Months'), '6m');
  assert.equal(normalizeTimeRange('6M'), '6m');
  assert.equal(normalizeTimeRange('custom'), 'custom');
  assert.equal(normalizeTimeRange(null), '30d');
});

test('Node callers without an explicit token do not import the browser Firebase SDK', async () => {
  const previousWindow = globalThis.window;
  try {
    globalThis.window = undefined;
    assert.equal(await getAuthIdToken(), null);
  } finally {
    globalThis.window = previousWindow;
  }
});

test('observation periods display as friendly month labels without changing canonical semantics', () => {
  assert.equal(formatObservationPeriod('2026-10'), 'Oct 2026');
  assert.equal(formatObservationPeriod('10-2026'), 'Oct 2026');
  assert.equal(formatObservationPeriod('2026-13'), '2026-13');
});

test('buildCoreIntelligenceRequest normalizes parameters and filters Global location', () => {
  const req = buildCoreIntelligenceRequest({
    portalType: 'employee',
    intelligenceType: 'market',
    location: 'Global',
    timeRange: '6 Months',
    selectedSkills: ['python', 'c_sharp'],
    selectedCompanies: ['Microsoft'],
    query: 'How is Python trending in cloud?'
  });

  assert.equal(req.portal_type, 'employee');
  assert.equal(req.intelligence_type, 'market');
  assert.equal(req.location, null); // Global mapped to null
  assert.equal(req.time_range, '6m');
  assert.deepEqual(req.selected_skills, ['python', 'c_sharp']);
  assert.deepEqual(req.selected_companies, ['Microsoft']);
  assert.equal(req.query, 'How is Python trending in cloud?');
});

test('adaptTrendItem enforces honest trend and readiness boundaries', () => {
  // Case 1: Insufficient data series (e.g. 1 period JSearch demand)
  const singlePeriodDemand = {
    entity_id: 'python',
    entity_name: 'Python',
    entity_type: 'skill',
    signal_type: 'demand',
    source: 'jsearch',
    is_trend_ready: false,
    trend_direction: 'Insufficient Data',
    velocity: null,
    growth_pct: null,
    periods: ['2026-10']
  };
  const adapted1 = adaptTrendItem(singlePeriodDemand);
  assert.equal(adapted1.is_trend_ready, false);
  assert.equal(adapted1.is_forecast_ready, false);
  assert.equal(adapted1.trend_direction, 'Insufficient Data');
  assert.equal(adapted1.formatted_growth, '—');
  assert.equal(adapted1.formatted_velocity, '—');
  assert.equal(adapted1.signal_label, 'Job Demand');

  // Case 2: Multi-period interest series (e.g. Stack Exchange 5 periods)
  const multiPeriodInterest = {
    entity_id: 'c_sharp',
    entity_name: 'C#',
    entity_type: 'skill',
    signal_type: 'interest',
    source: 'stack_exchange',
    is_trend_ready: true,
    trend_direction: 'Increasing',
    velocity: 0.08,
    growth_pct: 12.5,
    periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09']
  };
  const adapted2 = adaptTrendItem(multiPeriodInterest);
  assert.equal(adapted2.is_trend_ready, true);
  assert.equal(adapted2.is_forecast_ready, false); // Forecast strictly false
  assert.equal(adapted2.trend_direction, 'Increasing');
  assert.equal(adapted2.formatted_growth, '+12.5%');
  assert.equal(adapted2.formatted_velocity, '+0.08/mo');
  assert.equal(adapted2.signal_label, 'Developer Interest');
  assert.match(adapted2.signal_badge, /Developer Interest/);

  // Case 3: G2.3 enriched trend item
  const enrichedTrend = {
    entity_id: 'python',
    entity_name: 'Python',
    canonical_skill_id: 'python',
    display_name: 'Python',
    entity_type: 'skill',
    signal_type: 'interest',
    source: 'stack_exchange',
    is_trend_ready: true,
    trend_direction: 'Rising',
    trend_slope: 0.045,
    growth_pct: 15.2,
    velocity: 0.045,
    periods: ['2026-05', '2026-06', '2026-07', '2026-08'],
    limitations: ['Forecasting model inactive (is_forecast_ready = false)'],
    evidence_references: ['obs-1', 'obs-2'],
    explanation: 'Statistically verified rising trajectory'
  };
  const adapted3 = adaptTrendItem(enrichedTrend);
  assert.equal(adapted3.canonical_skill_id, 'python');
  assert.equal(adapted3.display_name, 'Python');
  assert.equal(adapted3.trend_slope, 0.045);
  assert.deepEqual(adapted3.limitations, ['Forecasting model inactive (is_forecast_ready = false)']);
  assert.deepEqual(adapted3.evidence_references, ['obs-1', 'obs-2']);
  assert.equal(adapted3.explanation, 'Statistically verified rising trajectory');
});

test('adaptCoreIntelligenceResponse guarantees is_forecast_ready is false and preserves answer', () => {
  const mockResponse = {
    intelligence_type: 'skill',
    portal_type: 'individual',
    data_status: 'available',
    data_state: 'ready',
    data_origin: 'real',
    history_type: 'platform_collected',
    answer: {
      headline: 'Python Demonstrates Verified Momentum',
      summary: 'Longitudinal analysis confirms Python is rising.',
      domain: 'skill',
      portal: 'individual',
      confidence: 0.95,
      readiness_status: 'ready_for_trend',
      key_insights: ['Insight 1'],
      evidence_citations: ['Citation 1'],
      limitations: ['Forecasting model inactive'],
      contextual_focus: 'Personal Skill Relevance'
    },
    historical_trends: [
      {
        entity_id: 'python',
        entity_name: 'Python',
        signal_type: 'interest',
        source: 'stack_exchange',
        is_trend_ready: true,
        trend_direction: 'Increasing',
        growth_pct: 10.0,
        velocity: 0.05
      }
    ],
    readiness: {
      total_series_assessed: 1,
      ready_for_trend_count: 1,
      ready_for_forecast_count: 0,
      blocked_count: 0,
      blocking_reasons: []
    }
  };

  const adapted = adaptCoreIntelligenceResponse(mockResponse);
  assert.equal(adapted.is_trend_ready, true);
  assert.equal(adapted.is_forecast_ready, false);
  assert.equal(adapted.readiness.ready_for_forecast_count, 0);
  assert.equal(adapted.historical_trends[0].is_forecast_ready, false);
  assert.ok(adapted.answer, 'Answer object should be present');
  assert.equal(adapted.answer.headline, 'Python Demonstrates Verified Momentum');
  assert.equal(adapted.answer.readiness_status, 'ready_for_trend');
});

test('sendCoreIntelligenceRequest attaches Bearer token and parses response', async () => {
  const previousFetch = globalThis.fetch;
  let receivedUrl = null;
  let receivedHeaders = null;
  let receivedBody = null;

  globalThis.fetch = async (url, opts) => {
    receivedUrl = url;
    receivedHeaders = opts.headers;
    receivedBody = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      intelligence_type: 'skill',
      portal_type: 'individual',
      data_status: 'available',
      data_state: 'ready',
      historical_trends: []
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await sendCoreIntelligenceRequest('/api/v1/intelligence/core', {
      method: 'POST',
      body: JSON.stringify({ portal_type: 'individual', intelligence_type: 'skill' }),
      token: 'mock-firebase-id-token'
    });

    assert.equal(receivedUrl, 'http://127.0.0.1:8000/api/v1/intelligence/core');
    assert.equal(receivedHeaders.Authorization, 'Bearer mock-firebase-id-token');
    assert.equal(receivedBody.portal_type, 'individual');
    assert.equal(res.data_status, 'available');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('catalog clients use authenticated shared intelligence catalog endpoints', async () => {
  const previousFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url, options) => {
    urls.push(url);
    assert.equal(options.headers.Authorization, 'Bearer mock-firebase-id-token');
    return new Response(JSON.stringify({ skills: [], market: {} }), { status: 200 });
  };
  try {
    await loadSkillCatalog();
    await loadMarketCatalog();
    assert.deepEqual(urls, [
      'http://127.0.0.1:8000/api/v1/intelligence/catalog/skills',
      'http://127.0.0.1:8000/api/v1/intelligence/catalog/market'
    ]);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('sendCoreIntelligenceRequest properly raises auth and network errors', async () => {
  const previousFetch = globalThis.fetch;
  const previousTokenProvider = globalThis.window.talentscopeGetAuthToken;
  try {
    // Keep this transport test independent of loading Firebase's browser SDK in Node.
    globalThis.window.talentscopeGetAuthToken = async () => 'mock-firebase-id-token';
    // 401 error
    globalThis.fetch = async () => new Response('Unauthorized', { status: 401 });
    await assert.rejects(
      sendCoreIntelligenceRequest('/api/v1/intelligence/core'),
      err => err.name === 'CoreIntelligenceAuthError' && err.status === 401
    );

    // Network error
    globalThis.fetch = async () => { throw new TypeError('Network connection refused'); };
    await assert.rejects(
      sendCoreIntelligenceRequest('/api/v1/intelligence/core'),
      err => err.name === 'CoreIntelligenceNetworkError'
    );
  } finally {
    globalThis.fetch = previousFetch;
    globalThis.window.talentscopeGetAuthToken = previousTokenProvider;
  }
});

test('buildCoreIntelligenceRequest normalizes roles, companies, and skills lists', () => {
  const req = buildCoreIntelligenceRequest({
    portalType: 'company',
    domain: 'job',
    selectedRoles: ['ai_engineer', 'cloud_architect'],
    selectedCompanies: ['NVIDIA', 'Microsoft'],
    selectedSkills: ['CUDA', 'Python'],
    location: 'Bangalore',
    timeRange: '3 Months'
  });

  assert.equal(req.portal_type, 'company');
  assert.equal(req.domain, 'job');
  assert.deepEqual(req.selected_roles, ['ai_engineer', 'cloud_architect']);
  assert.deepEqual(req.selected_companies, ['NVIDIA', 'Microsoft']);
  assert.deepEqual(req.selected_skills, ['CUDA', 'Python']);
  assert.equal(req.location, 'Bangalore');
  assert.equal(req.time_range, '3m');
});

test('stale request protection discards out-of-order resolved responses', async () => {
  let activeVersion = 0;
  let finalDisplayedSkill = null;

  async function mockFetchSkill(skillName, delayMs) {
    const requestVersion = ++activeVersion;
    await new Promise(resolve => setTimeout(resolve, delayMs));
    if (requestVersion !== activeVersion) {
      // Stale response correctly discarded
      return;
    }
    finalDisplayedSkill = skillName;
  }

  // Request 1 starts for Python with 50ms delay
  const p1 = mockFetchSkill('Python', 50);
  // Request 2 starts for CUDA with 10ms delay (finishes earlier)
  const p2 = mockFetchSkill('CUDA', 10);

  await Promise.all([p1, p2]);

  // Request 2 (CUDA) must be the final displayed skill, request 1 (Python) discarded because it finished second but had older version!
  assert.equal(finalDisplayedSkill, 'CUDA');
});

test('adaptActionRecommendation and adaptActionRecommendationResponse normalize action structure', () => {
  const raw = {
    data_status: 'available',
    contextual_focus: 'Personal Skill Relevance & Learning Roadmap',
    limitations: ['Empirical market observation.'],
    evidence_summary: { observations_count: 5 },
    recommendations: [
      {
        action_id: 'act_individual_python_strengthen_skill',
        action_type: 'strengthen_skill',
        title: 'Strengthen Python Proficiency',
        summary: 'Multi-period market signals confirm sustained positive demand momentum.',
        why_it_matters: 'Recommended because the validated Python series contains 5 consecutive observations.',
        recommended_action: 'Strengthen Python proficiency and update learning roadmap.',
        priority: 'high',
        target_type: 'skill',
        target_id: 'python',
        portal: 'individual',
        readiness_status: 'ready_for_trend',
        evidence_references: ['obs-1', 'obs-2'],
        limitations: ['Empirical market observation.'],
        roadmap_eligible: true,
        calculation_version: 'g2.5-production-v1'
      }
    ]
  };

  const adapted = adaptActionRecommendationResponse(raw);
  assert.equal(adapted.data_status, 'available');
  assert.equal(adapted.contextual_focus, 'Personal Skill Relevance & Learning Roadmap');
  assert.equal(adapted.recommendations.length, 1);
  const rec = adapted.recommendations[0];
  assert.equal(rec.action_id, 'act_individual_python_strengthen_skill');
  assert.equal(rec.action_type, 'strengthen_skill');
  assert.equal(rec.priority, 'high');
  assert.equal(rec.roadmap_eligible, true);
  assert.deepEqual(rec.evidence_references, ['obs-1', 'obs-2']);
});

test('adaptCoreIntelligenceResponse properly adapts action_recommendations', () => {
  const raw = {
    intelligence_type: 'skill',
    portal_type: 'individual',
    data_status: 'available',
    action_recommendations: [
      {
        action_id: 'act_1',
        action_type: 'review_skill',
        title: 'Review Python',
        why_it_matters: 'Declining trend',
        recommended_action: 'Review skill relevance',
        priority: 'high',
        target_type: 'skill',
        target_id: 'python',
        portal: 'individual',
        readiness_status: 'ready_for_trend',
        roadmap_eligible: true
      }
    ]
  };

  const adapted = adaptCoreIntelligenceResponse(raw);
  assert.equal(adapted.action_recommendations.length, 1);
  assert.equal(adapted.action_recommendations[0].action_id, 'act_1');
  assert.equal(adapted.action_recommendations[0].action_type, 'review_skill');
  assert.equal(adapted.action_recommendations[0].priority, 'high');
  assert.equal(adapted.action_recommendations[0].roadmap_eligible, true);
});

test('buildAnswerRequest normalizes message, portal_type, skills, and time_range', () => {
  const req = buildAnswerRequest({
    message: 'What skills are required for AI Engineer?',
    portalType: 'employee',
    location: 'Bangalore',
    timeRange: '6 Months',
    targetRole: 'AI Engineer',
    skills: ['Python', 'CUDA'],
    selectedRoles: ['AI Engineer'],
    companyId: 'nvidia',
    capabilityId: 'occupation_software_skills'
  });

  assert.equal(req.message, 'What skills are required for AI Engineer?');
  assert.equal(req.portal_type, 'employee');
  assert.equal(req.location, 'Bangalore');
  assert.equal(req.time_range, '6m');
  assert.equal(req.target_role, 'AI Engineer');
  assert.deepEqual(req.selected_skills, ['Python', 'CUDA']);
  assert.deepEqual(req.selected_roles, ['AI Engineer']);
  assert.equal(req.company_id, 'nvidia');
  assert.equal(req.capability_id, 'occupation_software_skills');
});

test('buildAnswerRequest preserves Home snake_case selections and normalizes the supported 12-month window', () => {
  const req = buildAnswerRequest({
    message: 'What does my role need?',
    portal_type: 'individual',
    domain: 'skill',
    time_range: '12 Months',
    selected_skills: ['skill:python'],
    selected_roles: ['occupation:software_developer'],
    selected_companies: ['employer:acme'],
    filters: { domain: 'skill', requested_time_window: '12 Months' }
  });

  assert.equal(req.time_range, '12m');
  assert.deepEqual(req.selected_skills, ['skill:python']);
  assert.deepEqual(req.selected_roles, ['occupation:software_developer']);
  assert.deepEqual(req.selected_companies, ['employer:acme']);
});

test('answer client surfaces FastAPI validation locations and messages for 422 responses', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    detail: [{
      type: 'value_error',
      loc: ['body', 'filters', 'requested_time_window'],
      msg: 'time_range must be 7d, 30d, 3m, 6m, 1y, or max.'
    }]
  }), { status: 422, headers: { 'Content-Type': 'application/json' } });

  try {
    await assert.rejects(
      queryCoreIntelligenceAnswer({ message: 'Check this' }),
      error => error.name === 'CoreIntelligenceHttpError'
        && error.status === 422
        && error.message === 'filters.requested_time_window: time_range must be 7d, 30d, 3m, 6m, 1y, or max.'
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('adaptFactItem and adaptEvidenceItem preserve verifiable provenance and quality', () => {
  const fact = adaptFactItem({
    fact_id: 'fact_1',
    metric_name: 'Software Skills Count',
    metric_value: 31821,
    source: 'O*NET 29.0',
    data_origin: 'real',
    quality_state: 'valid',
    signal_type: 'reference',
    observation_period: '2025-01',
    denominator: 100,
    denominator_unit: 'records',
    freshness_state: 'current'
  });
  assert.equal(fact.fact_id, 'fact_1');
  assert.equal(fact.metric_name, 'Software Skills Count');
  assert.equal(fact.metric_value, 31821);
  assert.equal(fact.source, 'O*NET 29.0');
  assert.equal(fact.data_origin, 'real');
  assert.equal(fact.signal_type, 'reference');
  assert.equal(fact.period, '2025-01');
  assert.equal(fact.denominator, 100);
  assert.equal(fact.denominator_unit, 'records');
  assert.equal(fact.freshness_state, 'current');

  const ev = adaptEvidenceItem({
    evidence_id: 'ev_1',
    source: 'GitHub Topic Adoption',
    signal_type: 'adoption',
    quality: 'valid',
    data_origin: 'real',
    description: '82,591 topics ingested'
  });
  assert.equal(ev.evidence_id, 'ev_1');
  assert.equal(ev.source, 'GitHub Topic Adoption');
  assert.equal(ev.signal_type, 'adoption');
  assert.equal(ev.data_origin, 'real');
});

test('adaptCoreIntelligenceAnswerResponse adapts all 6 execution statuses correctly', () => {
  const statuses = ['completed', 'requires_clarification', 'insufficient_data', 'blocked', 'unsupported', 'failed'];
  for (const st of statuses) {
    const resp = adaptCoreIntelligenceAnswerResponse({
      request_id: `ans_${st}`,
      user_message: 'Test message',
      portal_type: 'individual',
      intent: 'skill_lookup',
      plan_status: st === 'completed' ? 'executable' : st,
      execution_status: st,
      answer: `Answer for ${st}`,
      facts: [{ fact_type: 'count', metric_name: 'm1', metric_value: 10, source: 'src' }],
      evidence: [{ evidence_id: 'ev_1', source: 'src', signal_type: 'ref', description: 'desc' }],
      limitations: ['Limitation 1'],
      reason_codes: [`REASON_${st.toUpperCase()}`],
      follow_up_questions: ['Follow up 1']
    });

    assert.equal(resp.execution_status, st);
    assert.equal(resp.facts.length, 1);
    assert.equal(resp.evidence.length, 1);
    assert.equal(resp.limitations.length, 1);
    assert.equal(resp.reason_codes[0], `REASON_${st.toUpperCase()}`);
    assert.equal(resp.follow_up_questions[0], 'Follow up 1');
  }
});

test('queryCoreIntelligenceAnswer sends POST /api/v1/intelligence/answer with Bearer token', async () => {
  const previousFetch = globalThis.fetch;
  let receivedUrl = null;
  let receivedHeaders = null;
  let receivedBody = null;

  globalThis.fetch = async (url, opts) => {
    receivedUrl = url;
    receivedHeaders = opts.headers;
    receivedBody = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      request_id: 'ans_123',
      user_message: 'Why is Python in demand?',
      portal_type: 'individual',
      intent: 'skill_technology_reference',
      plan_status: 'executable',
      execution_status: 'completed',
      answer: 'Python is foundational.',
      facts: [],
      evidence: [],
      limitations: [],
      reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY'],
      follow_up_questions: []
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await queryCoreIntelligenceAnswer({
      message: 'Why is Python in demand?',
      portalType: 'individual'
    }, { token: 'mock-token' });

    assert.equal(receivedUrl, 'http://127.0.0.1:8000/api/v1/intelligence/answer');
    assert.equal(receivedHeaders.Authorization, 'Bearer mock-token');
    assert.equal(receivedBody.message, 'Why is Python in demand?');
    assert.equal(res.execution_status, 'completed');
    assert.equal(res.answer, 'Python is foundational.');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('queryCoreIntelligenceAnswer handles 401/403 auth errors and network errors', async () => {
  const previousFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('Unauthorized', { status: 401 });
    await assert.rejects(
      queryCoreIntelligenceAnswer({ message: 'query' }),
      err => err.name === 'CoreIntelligenceAuthError' && err.status === 401
    );

    globalThis.fetch = async () => { throw new TypeError('Network connection refused'); };
    await assert.rejects(
      queryCoreIntelligenceAnswer({ message: 'query' }),
      err => err.name === 'CoreIntelligenceNetworkError'
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('queryCoreIntelligencePlan uses authenticated planner endpoint and preserves domain context', async () => {
  const previousFetch = globalThis.fetch;
  let requestUrl = '';
  let requestBody = null;
  let requestHeaders = null;
  globalThis.fetch = async (url, options) => {
    requestUrl = String(url);
    requestBody = JSON.parse(options.body);
    requestHeaders = options.headers;
    return new Response(JSON.stringify({
      selected_capabilities: ['market_snapshot'],
      readiness_results: [{ capability_id: 'market_snapshot', can_execute: true }]
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  try {
    const plan = await queryCoreIntelligencePlan({
      message: 'What current signals exist for Python?',
      domain: 'market',
      portalType: 'individual',
      conversationId: 'conversation-market'
    }, { token: 'mock-firebase-id-token' });
    assert.equal(requestUrl, 'http://127.0.0.1:8000/api/v1/intelligence/plan');
    assert.equal(requestHeaders.Authorization.startsWith('Bearer '), true);
    assert.equal(requestBody.domain, 'market');
    assert.equal(requestBody.portal_type, 'individual');
    assert.equal(requestBody.conversation_id, 'conversation-market');
    assert.deepEqual(plan.selected_capabilities, ['market_snapshot']);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('buildAnswerRequest preserves conversationId and clearContext flags', () => {
  const req1 = buildAnswerRequest({
    message: 'What about its trends?',
    conversationId: 'conv_abc123',
    clearContext: false
  });
  assert.equal(req1.conversation_id, 'conv_abc123');
  assert.equal(req1.clear_context, false);

  const req2 = buildAnswerRequest({
    message: 'Reset my session',
    clearContext: true
  });
  assert.equal(req2.clear_context, true);
  assert.equal(req2.conversation_id, null);
});

test('adaptCoreIntelligenceAnswerResponse preserves conversation_id', () => {
  const resp = adaptCoreIntelligenceAnswerResponse({
    request_id: 'ans_123',
    conversation_id: 'conv_session_999',
    user_message: 'Tell me about Docker',
    portal_type: 'individual',
    execution_status: 'completed',
    answer: 'Docker is a containerization platform.',
    facts: [],
    evidence: [],
    limitations: [],
    reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY'],
    follow_up_questions: []
  });
  assert.equal(resp.conversation_id, 'conv_session_999');
  assert.equal(resp.execution_status, 'completed');
});

test('resolveEntity sends POST /api/v1/intelligence/entities/resolve', async () => {
  const previousFetch = globalThis.fetch;
  let receivedUrl = null;
  let receivedBody = null;

  globalThis.fetch = async (url, opts) => {
    receivedUrl = url;
    receivedBody = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      query: 'PyTorch',
      entity_type: 'skill',
      canonical_id: 'pytorch',
      canonical_name: 'PyTorch',
      confidence: 1.0,
      match_type: 'exact'
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await resolveEntity('PyTorch', { entityType: 'skill' });
    assert.equal(receivedUrl, 'http://127.0.0.1:8000/api/v1/intelligence/entities/resolve');
    assert.equal(receivedBody.name, 'PyTorch');
    assert.equal(receivedBody.entity_type, 'skill');
    assert.equal(res.canonical_id, 'pytorch');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('getCapabilityCatalog sends GET /api/v1/intelligence/capabilities', async () => {
  const previousFetch = globalThis.fetch;
  let receivedUrl = null;

  globalThis.fetch = async (url) => {
    receivedUrl = url;
    return new Response(JSON.stringify({
      total_capabilities: 6,
      capabilities: [
        { capability_id: 'cap_skill_overview', status: 'operational' }
      ]
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await getCapabilityCatalog({ portalType: 'individual' });
    assert.equal(receivedUrl, 'http://127.0.0.1:8000/api/v1/intelligence/capabilities?portal_type=individual');
    assert.equal(res.total_capabilities, 6);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('evaluateCapabilities sends POST /api/v1/intelligence/capabilities/evaluate', async () => {
  const previousFetch = globalThis.fetch;
  let receivedUrl = null;
  let receivedBody = null;

  globalThis.fetch = async (url, opts) => {
    receivedUrl = url;
    receivedBody = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      matched_capabilities: ['cap_skill_overview'],
      primary_capability_id: 'cap_skill_overview',
      evaluation_status: 'supported'
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await evaluateCapabilities({
      query: 'Tell me about Python',
      portal_type: 'employee'
    });
    assert.equal(receivedUrl, 'http://127.0.0.1:8000/api/v1/intelligence/capabilities/evaluate');
    assert.equal(receivedBody.query, 'Tell me about Python');
    assert.equal(res.evaluation_status, 'supported');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

// Run registered tests
let passed = 0;
for (const t of registeredTests) {
  try {
    await t.run();
    console.log(`PASS ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`FAIL ${t.name}`);
    console.error(err);
    process.exitCode = 1;
  }
}
console.log(`CORE INTELLIGENCE CLIENT TESTS: ${passed}/${registeredTests.length} PASSED`);
