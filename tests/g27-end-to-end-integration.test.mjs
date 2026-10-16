import assert from 'node:assert/strict';
import {
  buildAnswerRequest,
  adaptCoreIntelligenceAnswerResponse,
  queryCoreIntelligenceAnswer,
  resolveEntity,
  getCapabilityCatalog,
  evaluateCapabilities
} from '../src/api/core-intelligence-client.js';
import {
  renderCapabilityStatusBadge,
  renderStructuredFactsGrid,
  renderEvidenceDrawer,
  renderLimitationsNotice,
  renderFollowUpChips,
  renderIntelligenceErrorNotice,
  STATUS_CONFIG
} from '../src/components/common/IntelligenceComponents.js';

// Setup browser globals for test environment
globalThis.window = {
  TALENTSCOPE_API_BASE_URL: 'http://127.0.0.1:8000'
};

const registeredTests = [];
function test(name, run) {
  registeredTests.push({ name, run });
}

// ----------------------------------------------------------------------------
// 1. Cross-Portal Contract Consistency
// ----------------------------------------------------------------------------

test('Portal requests enforce correct portal_type and context fields', () => {
  // Individual Portal query
  const indReq = buildAnswerRequest({
    message: 'What are the top skills for Cloud Architect?',
    portalType: 'individual',
    targetRole: 'Cloud Architect',
    selectedSkills: ['AWS', 'Kubernetes'],
    location: 'Bangalore'
  });
  assert.equal(indReq.portal_type, 'individual');
  assert.equal(indReq.target_role, 'Cloud Architect');
  assert.deepEqual(indReq.selected_skills, ['AWS', 'Kubernetes']);
  assert.equal(indReq.location, 'Bangalore');

  // Employee Portal query
  const empReq = buildAnswerRequest({
    message: 'How do I bridge my CUDA skill gap?',
    portalType: 'employee',
    targetRole: 'Principal AI Engineer',
    selectedSkills: ['Python', 'Machine Learning'],
    location: 'Bangalore'
  });
  assert.equal(empReq.portal_type, 'employee');
  assert.equal(empReq.target_role, 'Principal AI Engineer');
  assert.deepEqual(empReq.selected_skills, ['Python', 'Machine Learning']);

  // Company Portal query
  const compReq = buildAnswerRequest({
    message: 'Which teams have the largest skill gaps?',
    portalType: 'company',
    companyId: 'nvidia',
    location: 'Bangalore'
  });
  assert.equal(compReq.portal_type, 'company');
  assert.equal(compReq.company_id, 'nvidia');
});

// ----------------------------------------------------------------------------
// 2. Multi-turn Session & Anaphora Flow
// ----------------------------------------------------------------------------

test('Multi-turn conversation flow tracks conversation_id and maintains continuity', async () => {
  const previousFetch = globalThis.fetch;
  const calls = [];

  globalThis.fetch = async (url, opts) => {
    const body = JSON.parse(opts.body);
    calls.push({ url, body });

    // Turn 1: Initial query returns conversation_id
    if (!body.conversation_id) {
      return new Response(JSON.stringify({
        request_id: 'ans_turn1',
        conversation_id: 'conv_session_1001',
        user_message: body.message,
        portal_type: body.portal_type,
        intent: 'skill_technology_reference',
        plan_status: 'executable',
        execution_status: 'completed',
        answer: 'Python is a high-level programming language.',
        facts: [
          {
            fact_id: 'f_1',
            fact_type: 'skill_overview',
            metric_name: 'Canonical Name',
            metric_value: 'Python',
            unit: null,
            source: 'Lightcast Open Taxonomy',
            data_origin: 'real',
            quality_state: 'valid'
          }
        ],
        evidence: [
          {
            evidence_id: 'ev_1',
            source: 'Lightcast Open Taxonomy',
            signal_type: 'taxonomy_definition',
            quality: 'valid',
            description: 'Canonical skill python'
          }
        ],
        limitations: [],
        reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY'],
        follow_up_questions: ['What tools are associated with Python?']
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    // Turn 2: Follow-up query with conversation_id
    return new Response(JSON.stringify({
      request_id: 'ans_turn2',
      conversation_id: body.conversation_id,
      user_message: body.message,
      portal_type: body.portal_type,
      intent: 'skill_technology_reference',
      plan_status: 'executable',
      execution_status: 'completed',
      answer: 'Key tools associated with Python include Django, FastAPI, and PyTorch.',
      facts: [],
      evidence: [],
      limitations: [],
      reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY'],
      follow_up_questions: []
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    // Turn 1
    const res1 = await queryCoreIntelligenceAnswer({
      message: 'Tell me about Python',
      portalType: 'individual'
    });
    assert.equal(res1.conversation_id, 'conv_session_1001');
    assert.equal(res1.execution_status, 'completed');
    assert.equal(calls[0].body.conversation_id, null);

    // Turn 2: uses res1.conversation_id
    const res2 = await queryCoreIntelligenceAnswer({
      message: 'What tools are associated with it?',
      portalType: 'individual',
      conversationId: res1.conversation_id
    });
    assert.equal(res2.conversation_id, 'conv_session_1001');
    assert.equal(calls[1].body.conversation_id, 'conv_session_1001');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

// ----------------------------------------------------------------------------
// 3. Explicit Context Clearing
// ----------------------------------------------------------------------------

test('Explicit session reset sends clear_context=true and resets conversation flow', async () => {
  const previousFetch = globalThis.fetch;
  let clearCallReceived = null;

  globalThis.fetch = async (url, opts) => {
    clearCallReceived = JSON.parse(opts.body);
    return new Response(JSON.stringify({
      request_id: 'ans_reset',
      conversation_id: 'conv_session_1002',
      user_message: 'clear context',
      portal_type: 'company',
      intent: 'general_assistance',
      plan_status: 'executable',
      execution_status: 'completed',
      answer: 'Session reset.',
      facts: [],
      evidence: [],
      limitations: [],
      reason_codes: ['CONTEXT_CLEARED'],
      follow_up_questions: []
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  try {
    const res = await queryCoreIntelligenceAnswer({
      message: 'clear context',
      portalType: 'company',
      companyId: 'nvidia',
      conversationId: 'conv_session_1001',
      clearContext: true
    });

    assert.equal(clearCallReceived.clear_context, true);
    assert.equal(clearCallReceived.conversation_id, 'conv_session_1001');
    assert.equal(clearCallReceived.company_id, 'nvidia');
    assert.equal(res.execution_status, 'completed');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

// ----------------------------------------------------------------------------
// 4. Honest Execution Status Disclosures
// ----------------------------------------------------------------------------

test('Execution status disclosures correctly propagate across all 6 runtime statuses', () => {
  const testCases = [
    {
      status: 'completed',
      reason: 'EXECUTION_COMPLETED_SUCCESSFULLY',
      expectFact: true,
      expectLimitation: false
    },
    {
      status: 'requires_clarification',
      reason: 'MISSING_TARGET_ENTITY',
      expectFact: false,
      expectLimitation: true
    },
    {
      status: 'insufficient_data',
      reason: 'INSUFFICIENT_HISTORICAL_PERIODS',
      expectFact: false,
      expectLimitation: true
    },
    {
      status: 'unsupported',
      reason: 'UNSUPPORTED_FORECASTING_CAPABILITY',
      expectFact: false,
      expectLimitation: true
    },
    {
      status: 'blocked',
      reason: 'UNAUTHORIZED_CROSS_COMPANY_ACCESS',
      expectFact: false,
      expectLimitation: true
    },
    {
      status: 'failed',
      reason: 'PIPELINE_EXECUTION_FAILURE',
      expectFact: false,
      expectLimitation: true
    }
  ];

  for (const tc of testCases) {
    const adapted = adaptCoreIntelligenceAnswerResponse({
      request_id: `req_${tc.status}`,
      conversation_id: 'conv_1',
      user_message: 'Query',
      portal_type: 'employee',
      plan_status: tc.status,
      execution_status: tc.status,
      answer: `Response for ${tc.status}`,
      facts: tc.expectFact ? [{ fact_id: 'f1', metric_name: 'M', metric_value: 10, source: 'S' }] : [],
      evidence: tc.expectFact ? [{ evidence_id: 'e1', source: 'S', signal_type: 'T', description: 'D' }] : [],
      limitations: tc.expectLimitation ? [`Limitation for ${tc.status}`] : [],
      reason_codes: [tc.reason],
      follow_up_questions: []
    });

    assert.equal(adapted.execution_status, tc.status);
    assert.equal(adapted.reason_codes[0], tc.reason);
    if (tc.expectFact) {
      assert.ok(adapted.facts.length > 0);
      assert.ok(adapted.evidence.length > 0);
    }
    if (tc.expectLimitation) {
      assert.ok(adapted.limitations.length > 0);
    }
  }
});

// ----------------------------------------------------------------------------
// 5. Security & Multi-tenant Isolation Error Handling
// ----------------------------------------------------------------------------

test('Portal error handling classifies 401/403 as blocked and network as failed', async () => {
  const previousFetch = globalThis.fetch;

  try {
    // 403 Forbidden - Tenant violation or unauthorized portal
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Cross-tenant access forbidden' }), { status: 403 });

    await assert.rejects(
      queryCoreIntelligenceAnswer({
        message: 'Show Google workforce secrets',
        portalType: 'company',
        companyId: 'google'
      }),
      err => {
        assert.equal(err.name, 'CoreIntelligenceAuthError');
        assert.equal(err.status, 403);
        return true;
      }
    );

    // Network connection drop
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };

    await assert.rejects(
      queryCoreIntelligenceAnswer({
        message: 'Any query',
        portalType: 'individual'
      }),
      err => {
        assert.equal(err.name, 'CoreIntelligenceNetworkError');
        return true;
      }
    );
  } finally {
    globalThis.fetch = previousFetch;
  }
});

// ----------------------------------------------------------------------------
// 6. Capability Registry & Entity Resolution Integration
// ----------------------------------------------------------------------------

test('Capability catalog and entity resolution endpoints integrate properly', async () => {
  const previousFetch = globalThis.fetch;

  globalThis.fetch = async (url, opts) => {
    if (url.includes('/entities/resolve')) {
      const body = JSON.parse(opts.body);
      return new Response(JSON.stringify({
        name: body.name,
        status: 'resolved',
        entity: {
          entity_id: 'cuda',
          entity_type: 'skill',
          canonical_name: 'CUDA',
          aliases: ['CUDA C++', 'CUDA Architecture'],
          category: 'Parallel Computing',
          source: 'Lightcast Open Taxonomy',
          source_record_id: 'KS120P660144T263Q234',
          status: 'active',
          metadata: {}
        },
        candidates: [],
        match_method: 'exact',
        confidence: 1.0,
        source_provenance: { source: 'lightcast' }
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    if (url.includes('/capabilities/evaluate')) {
      const body = JSON.parse(opts.body);
      return new Response(JSON.stringify({
        query: body.query,
        portal_type: body.portal_type,
        matched_capabilities: ['cap_skill_overview'],
        primary_capability_id: 'cap_skill_overview',
        evaluation_status: 'supported',
        readiness_status: 'ready',
        evaluations: [
          {
            capability_id: 'cap_skill_overview',
            is_supported: true,
            is_ready: true,
            missing_requirements: []
          }
        ]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    if (url.includes('/capabilities')) {
      return new Response(JSON.stringify({
        total_capabilities: 6,
        capabilities: [
          {
            capability_id: 'cap_skill_overview',
            name: 'Skill Technology Overview',
            status: 'operational',
            supported_portals: ['individual', 'employee', 'company']
          }
        ]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    return new Response('Not Found', { status: 404 });
  };

  try {
    const entRes = await resolveEntity('CUDA', { entityType: 'skill' });
    assert.equal(entRes.status, 'resolved');
    assert.equal(entRes.entity.canonical_name, 'CUDA');

    const evalRes = await evaluateCapabilities({
      query: 'What is CUDA?',
      portal_type: 'individual'
    });
    assert.equal(evalRes.evaluation_status, 'supported');
    assert.equal(evalRes.primary_capability_id, 'cap_skill_overview');

    const catRes = await getCapabilityCatalog({ portalType: 'individual' });
    assert.equal(catRes.total_capabilities, 6);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

// ----------------------------------------------------------------------------
// 7. Shared IntelligenceComponents Rendering
// ----------------------------------------------------------------------------

test('Shared IntelligenceComponents render all 6 statuses and structures faithfully', () => {
  // A. Status badges for all 6 statuses
  const statuses = ['completed', 'requires_clarification', 'insufficient_data', 'unsupported', 'blocked', 'failed'];
  for (const st of statuses) {
    const html = renderCapabilityStatusBadge(st, ['TEST_REASON_CODE']);
    assert.ok(html.includes(`ts-status-badge--${st}`));
    assert.ok(html.includes(STATUS_CONFIG[st].label));
    assert.ok(html.includes('TEST_REASON_CODE'));
  }

  // B. Facts Grid
  assert.equal(renderStructuredFactsGrid([]), '');
  assert.equal(renderStructuredFactsGrid(null), '');
  const factsHtml = renderStructuredFactsGrid([
    {
      metric_name: 'Demand Index',
      metric_value: 84.5,
      unit: '%',
      source: 'Lightcast Open Taxonomy',
      quality_state: 'valid'
    }
  ], { title: 'Verified Metrics', primaryColor: '#059669' });
  assert.ok(factsHtml.includes('Verified Metrics (1)'));
  assert.ok(factsHtml.includes('Demand Index'));
  assert.ok(factsHtml.includes('84.5'));
  assert.ok(factsHtml.includes('%'));
  assert.ok(factsHtml.includes('Lightcast Open Taxonomy'));
  assert.ok(factsHtml.includes('valid'));

  // C. Evidence Drawer
  assert.equal(renderEvidenceDrawer([]), '');
  assert.equal(renderEvidenceDrawer(null), '');
  const evHtml = renderEvidenceDrawer([
    {
      evidence_id: 'ev_onet_42',
      source: 'ref_onet_technology_skills',
      signal_type: 'onet_technology',
      period: '2026-Q1',
      description: 'Software Developer technology mapping',
      data_origin: 'real',
      quality: 'valid'
    }
  ], 1);
  assert.ok(evHtml.includes('Grounding Citations & Artifacts (1)'));
  assert.ok(evHtml.includes('evidenceList_1'));
  assert.ok(evHtml.includes('ref_onet_technology_skills'));
  assert.ok(evHtml.includes('onet_technology · 2026-Q1'));
  assert.ok(evHtml.includes('real'));
  assert.ok(evHtml.includes('ev_onet_42'));

  // D. Limitations Notice
  assert.equal(renderLimitationsNotice([]), '');
  const unsuppLim = renderLimitationsNotice(['Forecasting is disabled in G2.6/G2.7'], 'unsupported');
  assert.ok(unsuppLim.includes('Capability Boundary:'));
  assert.ok(unsuppLim.includes('Forecasting is disabled in G2.6/G2.7'));

  const insuffLim = renderLimitationsNotice(['Zero historical periods available'], 'insufficient_data');
  assert.ok(insuffLim.includes('Analytical Limitations & Scope:'));
  assert.ok(insuffLim.includes('Zero historical periods available'));

  // E. Follow-Up Chips
  assert.equal(renderFollowUpChips([]), '');
  const chipsHtml = renderFollowUpChips(['What are related skills?', 'Show citations'], 'data-query');
  assert.ok(chipsHtml.includes('data-query="What are related skills?"'));
  assert.ok(chipsHtml.includes('data-query="Show citations"'));

  // F. Error Notices (Auth, Company Tenant, Network)
  const compAuthErr = renderIntelligenceErrorNotice({
    error: { name: 'CoreIntelligenceAuthError', status: 403, message: 'Cross-tenant access forbidden' },
    portalType: 'company'
  });
  assert.ok(compAuthErr.includes('Access Restricted: Enterprise Multi-Tenant Boundary'));
  assert.ok(compAuthErr.includes('Cross-company access is strictly prohibited'));

  const netErr = renderIntelligenceErrorNotice({
    error: { name: 'CoreIntelligenceNetworkError', message: 'Failed to fetch' },
    portalType: 'individual'
  });
  assert.ok(netErr.includes('Service Unavailable'));
  assert.ok(!netErr.includes('127.0.0.1:8000'));
});

// ----------------------------------------------------------------------------
// 8. End-to-End Review Demo Scenario Response Compatibility
// ----------------------------------------------------------------------------

test('Core Intelligence Review demonstration responses adapt without loss or mutation', () => {
  // Scenario 2: Software Skills Crosswalk
  const crosswalkResp = adaptCoreIntelligenceAnswerResponse({
    request_id: 'demo_scen_2',
    conversation_id: 'conv_s2',
    user_message: 'What software tools does a Software Developer use?',
    portal_type: 'individual',
    plan_status: 'executable',
    execution_status: 'completed',
    answer: 'Software Developers routinely use Python, Git, Docker, and SQL.',
    facts: [
      { fact_id: 'f_tool_1', metric_name: 'Hot Technology', metric_value: 'Python', source: 'ref_onet_technology_skills', quality_state: 'valid' },
      { fact_id: 'f_tool_2', metric_name: 'Hot Technology', metric_value: 'Git', source: 'ref_onet_technology_skills', quality_state: 'valid' }
    ],
    evidence: [
      { evidence_id: 'ev_onet_1', source: 'ref_onet_technology_skills', signal_type: 'onet_technology', data_origin: 'real', quality: 'valid', description: 'O*NET 28.0 technology skill' }
    ],
    limitations: [],
    reason_codes: ['EXECUTION_COMPLETED_SUCCESSFULLY'],
    follow_up_questions: ['What are related occupations?']
  });
  assert.equal(crosswalkResp.execution_status, 'completed');
  assert.equal(crosswalkResp.facts.length, 2);
  assert.equal(crosswalkResp.evidence[0].data_origin, 'real');

  // Scenario 5A: Insufficient Data on Trend
  const insuffResp = adaptCoreIntelligenceAnswerResponse({
    request_id: 'demo_scen_5a',
    conversation_id: 'conv_s5',
    user_message: "Show Python's historical market demand trend",
    portal_type: 'individual',
    plan_status: 'insufficient_data',
    execution_status: 'insufficient_data',
    answer: 'Insufficient empirical observations in local store to compute trend.',
    facts: [],
    evidence: [],
    limitations: ['Zero observations available in market_observations table.'],
    reason_codes: ['INSUFFICIENT_OBSERVATION_DATA'],
    follow_up_questions: []
  });
  assert.equal(insuffResp.execution_status, 'insufficient_data');
  assert.equal(insuffResp.limitations.length, 1);
  assert.equal(insuffResp.reason_codes[0], 'INSUFFICIENT_OBSERVATION_DATA');

  // Scenario 8: Unsupported Forecasting
  const unsuppResp = adaptCoreIntelligenceAnswerResponse({
    request_id: 'demo_scen_8',
    conversation_id: 'conv_s8',
    user_message: 'Forecast future demand for Python over the next 2 years',
    portal_type: 'individual',
    plan_status: 'unsupported',
    execution_status: 'unsupported',
    answer: 'Forecasting is not supported in G2.6/G2.7.',
    facts: [],
    evidence: [],
    limitations: ['Predictive time-series forecasting is inactive in G2.6/G2.7.'],
    reason_codes: ['CAPABILITY_UNSUPPORTED_IN_G2_6'],
    follow_up_questions: []
  });
  assert.equal(unsuppResp.execution_status, 'unsupported');
  assert.equal(unsuppResp.limitations[0], 'Predictive time-series forecasting is inactive in G2.6/G2.7.');
});

// ----------------------------------------------------------------------------
// 9. HTML Escaping & Sanitization
// ----------------------------------------------------------------------------

test('Intelligence UI components safely escape malicious HTML inputs', () => {
  const badScript = '<script>alert("pwned")</script>';
  const badImg = '<img src=x onerror=alert(1)>';

  const badgeHtml = renderCapabilityStatusBadge('completed', [badScript]);
  assert.ok(!badgeHtml.includes('<script>'));
  assert.ok(badgeHtml.includes('&lt;script&gt;'));

  const factsHtml = renderStructuredFactsGrid([
    { metric_name: badScript, metric_value: badImg, source: '<b>bold</b>' }
  ]);
  assert.ok(!factsHtml.includes('<script>'));
  assert.ok(!factsHtml.includes('<img'));
  assert.ok(!factsHtml.includes('<b>'));

  const evHtml = renderEvidenceDrawer([
    { source: badScript, description: badImg }
  ]);
  assert.ok(!evHtml.includes('<script>'));
  assert.ok(!evHtml.includes('<img'));

  const limHtml = renderLimitationsNotice([badScript]);
  assert.ok(!limHtml.includes('<script>'));
});

// Run all tests
let passed = 0;
for (const t of registeredTests) {
  try {
    await t.run();
    console.log(`PASS: ${t.name}`);
    passed++;
  } catch (err) {
    console.error(`FAIL: ${t.name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

console.log(`\nG2.7 END-TO-END INTEGRATION TESTS: ${passed}/${registeredTests.length} PASSED`);
