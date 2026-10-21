import assert from 'node:assert/strict';
import test from 'node:test';

import { buildCoreIntelligenceRequest } from '../src/api/core-intelligence-client.js';
import {
  bindCompanySimulationEvents,
  renderCompanyWorkforceSimulation
} from '../src/pages/company/simulation/WorkforceSimulation.js';

const forbiddenDemoIdentity = ['ORG', 'NV', '2026'].join('-');

test('workforce simulation is explicitly illustrative and does not claim unsupported persistence', () => {
  const html = renderCompanyWorkforceSimulation();

  assert.match(html, /Prototype only/);
  assert.match(html, /not HRIS data, forecasts, or outputs from a validated simulation model/i);
  assert.match(html, /Not connected to HRIS/);
  assert.match(html, /No validated confidence score/);
  assert.doesNotMatch(html, /Grounded in HRIS Data|Confidence: 94%|REAL-TIME COMPUTED MODEL/);
  assert.match(html, /Export unavailable \(not implemented\)/);
  assert.match(html, /Save unavailable \(not implemented\)/);
});

test('simulation export and save actions do not report success', () => {
  const handlers = new Map();
  const messages = [];
  const priorWindow = globalThis.window;
  const priorDocument = globalThis.document;
  const priorAlert = globalThis.alert;

  globalThis.window = { lucide: null };
  globalThis.document = {
    querySelectorAll: () => [],
    querySelector: selector => ({
      addEventListener: (_event, handler) => handlers.set(selector, handler)
    })
  };
  globalThis.alert = message => messages.push(message);

  try {
    bindCompanySimulationEvents(() => {});
    handlers.get('#cmpExportScenarioBrief')();
    handlers.get('#cmpSaveParametricModelBtn')();
  } finally {
    if (priorWindow === undefined) delete globalThis.window;
    else globalThis.window = priorWindow;
    if (priorDocument === undefined) delete globalThis.document;
    else globalThis.document = priorDocument;
    if (priorAlert === undefined) delete globalThis.alert;
    else globalThis.alert = priorAlert;
  }

  assert.deepEqual(messages, [
    'Export is not implemented. No brief was created or saved.',
    'Saving is not implemented. No model was saved.'
  ]);
});

test('company API requests use authenticated tenant resolution instead of the demo identity', async () => {
  const market = await import('../src/pages/company/market/MarketIntelligence.js?offline-authorized');
  const skills = await import('../src/pages/company/skills/SkillIntelligence.js?offline-authorized');
  const requests = [];
  const urls = [];
  const priorWindow = globalThis.window;
  const priorFetch = globalThis.fetch;
  const priorDocument = globalThis.document;

  globalThis.window = { talentscopeGetAuthToken: async () => 'offline-test-token' };
  globalThis.fetch = async (url, options) => {
    urls.push(url);
    requests.push(JSON.parse(options.body));
    return {
      ok: true,
      status: 200,
      json: async () => ({ status: 'insufficient_data', execution_status: 'insufficient_data', planned_primary_capability: 'market_snapshot', answer: 'No verified data is available.' })
    };
  };

  try {
    await market.loadCompanyMarketData(() => {});
    await skills.loadCompanySkillIntelligence(() => {});
  } finally {
    if (priorWindow === undefined) delete globalThis.window;
    else globalThis.window = priorWindow;
    if (priorFetch === undefined) delete globalThis.fetch;
    else globalThis.fetch = priorFetch;
  }

  assert.equal(requests.length, 2);
  assert.match(urls[0], /\/api\/v1\/intelligence\/answer$/);
  assert.match(urls[1], /\/api\/v1\/intelligence\/core$/);
  assert.equal(requests[0].domain, 'market');
  assert.equal(requests[0].capability_id, 'market_snapshot');
  for (const request of requests) {
    assert.equal(request.portal_type, 'company');
    if (Object.hasOwn(request, 'company_id')) assert.equal(request.company_id, null);
    if (Object.hasOwn(request, 'context_override')) assert.deepEqual(request.context_override, {});
    assert.equal(JSON.stringify(request).includes(forbiddenDemoIdentity), false);
    assert.equal(JSON.stringify(request).includes('NVIDIA Enterprise Solutions'), false);
    assert.equal(request.user_id ?? null, null);
  }

  assert.match(market.renderCompanyMarketIntelligence(), /insufficient data/i);
  assert.doesNotMatch(market.renderCompanyMarketIntelligence(), /\+24\.5%|company technology intelligence|nvidia software moat/i);
  assert.match(skills.renderCompanySkillIntelligence(), /insufficient data/);

  const authorizedPayload = buildCoreIntelligenceRequest(market.buildCompanyMarketRequest());
  assert.equal(authorizedPayload.portal_type, 'company');
  assert.equal(authorizedPayload.company_id, null);
});

test('company authorization failures stay visible without exposing backend details', async () => {
  const market = await import('../src/pages/company/market/MarketIntelligence.js?offline-forbidden');
  const skills = await import('../src/pages/company/skills/SkillIntelligence.js?offline-forbidden');
  const priorWindow = globalThis.window;
  const priorFetch = globalThis.fetch;
  const priorWarn = console.warn;

  globalThis.window = { talentscopeGetAuthToken: async () => 'offline-test-token' };
  globalThis.fetch = async () => ({
    ok: false,
    status: 403,
    json: async () => ({ detail: 'private company record must not reach the UI' })
  });
  console.warn = () => {};

  try {
    await market.loadCompanyMarketData(() => {});
    await skills.loadCompanySkillIntelligence(() => {});
  } finally {
    if (priorWindow === undefined) delete globalThis.window;
    else globalThis.window = priorWindow;
    if (priorFetch === undefined) delete globalThis.fetch;
    else globalThis.fetch = priorFetch;
    console.warn = priorWarn;
  }

  const marketHtml = market.renderCompanyMarketIntelligence();
  const skillsHtml = skills.renderCompanySkillIntelligence();
  assert.match(marketHtml, /Company access could not be verified/);
  assert.match(marketHtml, /no market result was loaded/);
  assert.match(skillsHtml, /Company access could not be verified/);
  assert.match(skillsHtml, /no company-specific API result was loaded/);
  for (const html of [marketHtml, skillsHtml]) {
    assert.doesNotMatch(html, /private company record must not reach the UI/);
  }
});

test('market workbench routes selected features through authenticated answer and renders backend response', async () => {
  const market = await import('../src/pages/company/market/MarketIntelligence.js?market-workbench-offline');
  const requests = [];
  const urls = [];
  const priorWindow = globalThis.window;
  const priorFetch = globalThis.fetch;
  const priorDocument = globalThis.document;
  let resolveFetch;
  globalThis.window = { talentscopeGetAuthToken: async () => 'offline-test-token', lucide: null };
  globalThis.fetch = (url, options) => {
    urls.push(url);
    requests.push({ body: JSON.parse(options.body), headers: options.headers });
    return new Promise(resolve => { resolveFetch = resolve; });
  };

  try {
    const request = market.buildMarketAnswerRequest({
      feature: 'market_trend',
      message: 'Is Python hiring demand increasing?',
      location: 'India'
    });
    assert.deepEqual(request, {
      message: 'Is Python hiring demand increasing?',
      market_feature: 'market_trend',
      portal_type: 'company',
      domain: 'market',
      capability_id: 'trend_velocity_analysis',
      location: 'India',
      time_range: 'max_available',
      conversation_id: null
    });

    const pending = market.submitMarketQuestion(request);
    assert.match(market.renderCompanyMarketIntelligence(), /Checking the selected market evidence/);
    await new Promise(resolve => setImmediate(resolve));
    assert.match(urls[0], /\/api\/v1\/intelligence\/answer$/);
    assert.equal(requests[0].headers.Authorization, 'Bearer offline-test-token');
    assert.equal(requests[0].body.capability_id, 'trend_velocity_analysis');

    resolveFetch({
      ok: true,
      status: 200,
      json: async () => ({
        portal_type: 'company',
        domain: 'market',
        intent: 'analyze_trend',
        status: 'insufficient_data',
        execution_status: 'insufficient_data',
        planned_primary_capability: 'trend_velocity_analysis',
        executed_primary_capability: 'trend_velocity_analysis',
        answer: 'No eligible hiring series is available for India.',
        facts: [{
          fact_id: 'readiness-1', fact_type: 'analysis_readiness', entity_name: 'Python',
          metric_name: 'trend_readiness', metric_value: 'insufficient_data', unit: 'status',
          source: 'configured_market_observation_store', data_origin: 'unavailable',
          readiness_state: 'insufficient_data', details: { reason: 'No eligible observations.' }
        }],
        evidence: [],
        limitations: ['At least four consecutive monthly periods are required.'],
        follow_up_questions: ['Which source should be checked?'],
        conversation_id: 'offline-market-conversation'
      })
    });
    const response = await pending;
    assert.equal(response.execution_status, 'insufficient_data');

    const html = market.renderCompanyMarketIntelligence();
    assert.match(html, /No eligible hiring series is available for India/);
    assert.match(html, /insufficient data/i);
    assert.match(html, /four consecutive monthly periods/);
    assert.match(html, /Evidence and provenance/);
    assert.match(html, /Which source should be checked/);
    assert.doesNotMatch(html, /trend_readiness|\+24\.5%|NVIDIA|companyUsage/);

    const nextRequest = market.buildMarketAnswerRequest({ feature: 'market_trend', message: 'Which source should be checked?' });
    assert.equal(nextRequest.conversation_id, 'offline-market-conversation');

    const listeners = new Map();
    const controls = {
      '#marketFeature': { value: 'hiring_signals', addEventListener: (name, handler) => listeners.set('feature', handler) },
      '#marketQuestionForm': { addEventListener: (name, handler) => listeners.set('submit', handler) },
      '#marketQuestion': { value: '', addEventListener() {} },
      '#marketLocation': { value: '', addEventListener() {} },
      '#marketNewConversation': { addEventListener() {} }
    };
    globalThis.document = {
      querySelector: selector => controls[selector] || null,
      querySelectorAll: () => []
    };
    market.bindCompanyMarketEvents(() => {});
    listeners.get('feature')();
    const hiringRequest = market.buildMarketAnswerRequest({ feature: 'hiring_signals' });
    assert.equal(hiringRequest.domain, 'job');
    assert.equal(hiringRequest.capability_id, 'job_posting_search');
    assert.equal(hiringRequest.conversation_id, null, 'switching domains starts a separately owned conversation');
  } finally {
    if (priorWindow === undefined) delete globalThis.window;
    else globalThis.window = priorWindow;
    if (priorFetch === undefined) delete globalThis.fetch;
    else globalThis.fetch = priorFetch;
    if (priorDocument === undefined) delete globalThis.document;
    else globalThis.document = priorDocument;
  }
});

test('market workbench feature choices map only to existing market capabilities', async () => {
  const market = await import('../src/pages/company/market/MarketIntelligence.js?market-feature-map-offline');
  const expected = {
    market_snapshot: 'market_snapshot',
    hiring_signals: 'job_posting_search',
    historical_signals: 'historical_signal_retrieval',
    market_trend: 'trend_velocity_analysis',
    evidence_sources: 'evidence_provenance_retrieval'
  };
  for (const [feature, capability] of Object.entries(expected)) {
    assert.equal(market.buildMarketAnswerRequest({ feature }).capability_id, capability);
  }
  assert.equal(market.buildMarketAnswerRequest({ feature: 'hiring_signals' }).domain, 'job');
  const html = market.renderCompanyMarketIntelligence();
  assert.match(html, /id="marketFeature"/);
  assert.match(html, /id="marketQuestionForm"/);
  assert.match(html, /Market Snapshot/);
  assert.match(html, /Evidence and Sources/);
  assert.doesNotMatch(html, /\+24\.5%|\+41\.0%|Illustrative market intelligence prototype/);
});

test('market workbench displays clarification and safe general-error states', async () => {
  const market = await import('../src/pages/company/market/MarketIntelligence.js?market-statuses-offline');
  const priorWindow = globalThis.window;
  const priorFetch = globalThis.fetch;
  globalThis.window = { talentscopeGetAuthToken: async () => 'offline-test-token', lucide: null };
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      status: 'insufficient_data',
      execution_status: 'requires_clarification',
      intent: 'unsupported_or_unclear',
      planned_primary_capability: 'evidence_provenance_retrieval',
      executed_primary_capability: null,
      answer: 'Which skill and source do you want evidence for?',
      follow_up_questions: ['Show evidence for Python from GitHub.'],
      facts: [], evidence: [], limitations: []
    })
  });

  try {
    await market.submitMarketQuestion(market.buildMarketAnswerRequest({ feature: 'evidence_sources' }));
    const clarificationHtml = market.renderCompanyMarketIntelligence();
    assert.match(clarificationHtml, /More detail needed/);
    assert.match(clarificationHtml, /Show evidence for Python from GitHub/);
    assert.doesNotMatch(clarificationHtml, /verified result was returned/);

    globalThis.fetch = async () => { throw new Error('private transport details'); };
    await market.submitMarketQuestion(market.buildMarketAnswerRequest({ feature: 'evidence_sources' }));
    const errorHtml = market.renderCompanyMarketIntelligence();
    assert.match(errorHtml, /Market intelligence could not be loaded/);
    assert.doesNotMatch(errorHtml, /private transport details/);
  } finally {
    if (priorWindow === undefined) delete globalThis.window;
    else globalThis.window = priorWindow;
    if (priorFetch === undefined) delete globalThis.fetch;
    else globalThis.fetch = priorFetch;
  }
});
