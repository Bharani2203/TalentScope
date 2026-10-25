import { API_BASE_URL } from '../config/api.js';

export function normalizeDomainKey(rawDomain) {
  if (!rawDomain) return 'skill';
  const str = String(rawDomain).trim().toLowerCase();
  if (str === 'market' || str === 'companies' || str === 'company') return 'market';
  if (str === 'job' || str === 'jobs' || str === 'roles' || str === 'role') return 'job';
  return 'skill';
}

export function normalizeTimeRange(rawRange) {
  return normalizeAnswerTimeRange(rawRange);
}

export function normalizeAnswerTimeRange(rawRange) {
  if (!rawRange) return '30d';
  const str = String(rawRange).trim().toLowerCase();
  if (str === '7d' || str === '7 days' || str === '7day' || str === '7-day') return '7d';
  if (str === '30d' || str === '30 days' || str === '30day' || str === '30-day' || str === '1m' || str === '1 month') return '30d';
  if (str === '3m' || str === '3 months' || str === '3month' || str === '90d' || str === '90 days') return '3m';
  if (str === '6m' || str === '6 months' || str === '6month' || str === '180d' || str === '180 days') return '6m';
  if (str === '12m' || str === '12 months' || str === '1y' || str === '1 year' || str === '365d') return '12m';
  if (str === 'max' || str === 'auto' || str.includes('max available') || str === 'all') return 'max';
  if (str === 'custom' || str.startsWith('custom')) return 'custom';
  return '30d';
}

export function buildCoreIntelligenceRequest(options = {}) {
  const portalType = options.portalType || options.portal_type || 'individual';
  const intelligenceType = options.intelligenceType || options.intelligence_type || null;
  const domain = options.domain || null;
  const location = options.location || null;
  const timeRange = options.timeRange || options.range || '30d';
  const customDays = options.customDays || options.custom_days || null;
  const selectedSkills = options.selectedSkills || options.skills || [];
  const selectedRoles = options.selectedRoles || options.roles || [];
  const selectedCompanies = options.selectedCompanies || options.companies || [];
  const targetRole = options.targetRole || options.target_role || null;
  const query = options.query || null;
  const requestedAnalysis = options.requestedAnalysis || options.requested_analysis || null;
  const filters = options.filters || {};
  const contextOverride = options.contextOverride || options.context_override || {};
  const userId = options.userId || options.user_id || null;
  const companyId = options.companyId || options.company_id || null;

  const normType = normalizeDomainKey(domain || intelligenceType || 'skill');
  const normLocation = (location && location !== 'Global') ? String(location).trim() : null;
  const normRange = normalizeTimeRange(timeRange);
  const normSkills = Array.isArray(selectedSkills) ? selectedSkills.filter(Boolean) : (selectedSkills ? [selectedSkills] : []);
  const normRoles = Array.isArray(selectedRoles) ? selectedRoles.filter(Boolean) : (selectedRoles ? [selectedRoles] : []);
  const normCompanies = Array.isArray(selectedCompanies) ? selectedCompanies.filter(Boolean) : (selectedCompanies ? [selectedCompanies] : []);

  return {
    portal_type: portalType,
    intelligence_type: normType,
    domain: normType,
    user_id: userId || null,
    company_id: companyId || null,
    location: normLocation,
    time_range: normRange,
    custom_days: normRange === 'custom' && customDays ? Number(customDays) : null,
    selected_skills: normSkills,
    selected_roles: normRoles,
    selected_companies: normCompanies,
    target_role: targetRole || null,
    query: query ? String(query).trim() : null,
    requested_analysis: requestedAnalysis || null,
    filters: filters || {},
    context_override: contextOverride || {}
  };
}

export function adaptTrendItem(trend) {
  if (!trend) return null;
  const isTrendReady = Boolean(trend.is_trend_ready);
  const signalType = trend.signal_type || 'demand';

  let signalLabel = 'Job Demand';
  if (signalType === 'interest') signalLabel = 'Developer Interest';
  else if (signalType === 'adoption') signalLabel = 'Code Adoption';

  let signalBadge = `${signalLabel} (${trend.source || 'Verified'})`;

  let direction = 'Insufficient Data';
  if (isTrendReady) {
    direction = trend.trend_direction || 'Stable';
  }

  let formattedGrowth = '—';
  if (isTrendReady && trend.growth_pct != null) {
    formattedGrowth = `${trend.growth_pct > 0 ? '+' : ''}${trend.growth_pct.toFixed(1)}%`;
  }

  let formattedVelocity = '—';
  if (isTrendReady && trend.velocity != null) {
    formattedVelocity = `${trend.velocity > 0 ? '+' : ''}${trend.velocity.toFixed(2)}/mo`;
  }

  return {
    ...trend,
    canonical_skill_id: trend.canonical_skill_id || null,
    display_name: trend.display_name || trend.entity_name || null,
    is_trend_ready: isTrendReady,
    is_forecast_ready: Boolean(trend.is_forecast_ready),
    signal_type: signalType,
    signal_label: signalLabel,
    signal_badge: signalBadge,
    trend_direction: direction,
    trend_slope: isTrendReady ? (trend.trend_slope != null ? trend.trend_slope : null) : null,
    growth_pct: isTrendReady ? trend.growth_pct : null,
    velocity: isTrendReady ? trend.velocity : null,
    formatted_growth: formattedGrowth,
    formatted_velocity: formattedVelocity,
    periods_count: trend.periods_count || (trend.periods ? trend.periods.length : 0),
    data_points: Array.isArray(trend.data_points) ? trend.data_points : [],
    current_signal_value: trend.current_signal_value != null ? trend.current_signal_value : null,
    current_signal_share: trend.current_signal_share != null ? trend.current_signal_share : null,
    current_signal_period: trend.current_signal_period || null,
    limitations: Array.isArray(trend.limitations) ? trend.limitations : [],
    evidence_references: Array.isArray(trend.evidence_references) ? trend.evidence_references : [],
    explanation: trend.explanation || null
  };
}

export function adaptActionRecommendation(rec) {
  if (!rec) return null;
  return {
    action_id: rec.action_id || 'act_unknown',
    action_type: rec.action_type || 'monitor_market_signal',
    title: rec.title || 'Recommended Action',
    summary: rec.summary || '',
    why_it_matters: rec.why_it_matters || '',
    recommended_action: rec.recommended_action || '',
    priority: rec.priority || 'medium',
    target_type: rec.target_type || 'skill',
    target_id: rec.target_id || '',
    portal: rec.portal || 'individual',
    readiness_status: rec.readiness_status || 'insufficient_data',
    evidence_references: Array.isArray(rec.evidence_references) ? rec.evidence_references : [],
    limitations: Array.isArray(rec.limitations) ? rec.limitations : [],
    roadmap_eligible: Boolean(rec.roadmap_eligible),
    calculation_version: rec.calculation_version || 'g2.5-production-v1'
  };
}

export function adaptActionRecommendationResponse(raw) {
  if (!raw) {
    return {
      data_status: 'insufficient_data',
      recommendations: [],
      contextual_focus: 'Personal Skill Relevance & Learning Roadmap',
      limitations: ['No recommendations available.'],
      evidence_summary: {},
      calculation_version: 'g2.5-production-v1'
    };
  }
  const rawRecs = Array.isArray(raw.recommendations) ? raw.recommendations : [];
  return {
    data_status: raw.data_status || 'available',
    recommendations: rawRecs.map(adaptActionRecommendation).filter(Boolean),
    contextual_focus: raw.contextual_focus || 'Personal Skill Relevance & Learning Roadmap',
    limitations: Array.isArray(raw.limitations) ? raw.limitations : [],
    evidence_summary: raw.evidence_summary || {},
    calculation_version: raw.calculation_version || 'g2.5-production-v1'
  };
}

export function adaptCoreIntelligenceResponse(raw) {
  if (!raw) {
    return {
      data_status: 'error',
      data_state: 'error',
      data_origin: 'unavailable',
      history_type: 'unavailable',
      intelligence_type: 'skill',
      portal_type: 'individual',
      summary: {},
      answer: null,
      current_signals: [],
      historical_trends: [],
      key_changes: [],
      explanations: [],
      recommendations: [],
      action_recommendations: [],
      next_actions: [],
      readiness: { total_series_assessed: 0, ready_for_trend_count: 0, ready_for_forecast_count: 0, blocked_count: 0, blocking_reasons: [] },
      blocking_reasons: ['No response received from intelligence engine.']
    };
  }

  const rawTrends = Array.isArray(raw.historical_trends) ? raw.historical_trends : [];
  const historyIncomplete = raw.history_complete === false
    || raw.evidence?.history_complete === false
    || raw.data_state === 'incomplete_history';
  const adaptedTrends = rawTrends.map(trend => adaptTrendItem(historyIncomplete
    ? { ...trend, is_trend_ready: false, is_forecast_ready: false }
    : trend));
  const trendReadyCount = adaptedTrends.filter(t => t.is_trend_ready).length;
  const rawActionRecs = Array.isArray(raw.action_recommendations) ? raw.action_recommendations : [];
  const readiness = raw.readiness || {
    total_series_assessed: adaptedTrends.length,
    ready_for_trend_count: trendReadyCount,
    ready_for_forecast_count: raw.forecast && raw.forecast.status === 'ready' ? 1 : 0,
    blocked_count: Math.max(0, adaptedTrends.length - trendReadyCount),
    blocking_reasons: raw.blocking_reasons || []
  };
  const safeReadiness = historyIncomplete ? {
    ...readiness,
    ready_for_trend_count: 0,
    ready_for_forecast_count: 0,
    blocked_count: Math.max(1, readiness.blocked_count || 0),
    blocking_reasons: [...new Set([
      ...(Array.isArray(readiness.blocking_reasons) ? readiness.blocking_reasons : []),
      'OBSERVATION_HISTORY_INCOMPLETE'
    ])]
  } : readiness;
  const metricResults = Array.isArray(raw.metric_results) ? raw.metric_results.map(metric =>
    historyIncomplete && metric.metric_kind !== 'observed' && ['ready', 'partial'].includes(metric.status)
      ? {
          ...metric,
          status: 'unavailable',
          metric_value: null,
          reason: 'The observation history is incomplete; this derived result is withheld.'
        }
      : metric
  ) : [];
  const withholdResult = (result, valueFields = []) => {
    if (!historyIncomplete || !result || !['ready', 'partial'].includes(result.status)) return result || null;
    return {
      ...result,
      status: 'unavailable',
      reason: 'The observation history is incomplete.',
      ...Object.fromEntries(valueFields.map(field => [field, null]))
    };
  };
  const forecast = historyIncomplete && ['ready', 'partial'].includes(raw.forecast?.status)
    ? { ...raw.forecast, status: 'unavailable', value: null, reason: 'The observation history is incomplete.' }
    : raw.forecast || null;
  const capabilities = { ...(raw.capabilities || {}) };
  if (historyIncomplete) {
    for (const capabilityName of ['forecast', 'skill_health', 'skill_half_life']) {
      const capability = capabilities[capabilityName];
      if (['ready', 'partial'].includes(capability?.status)) {
        capabilities[capabilityName] = {
          ...capability,
          status: 'unavailable',
          reason: 'The observation history is incomplete.',
          payload: withholdResult(capability.payload, [
            'value', 'score', 'health_score', 'half_life_months'
          ])
        };
      }
    }
  }

  return {
    ...raw,
    status: historyIncomplete ? 'incomplete_history' : raw.status || raw.data_state || (trendReadyCount > 0 ? 'ready' : 'insufficient_data'),
    intelligence_type: raw.intelligence_type || 'skill',
    portal_type: raw.portal_type || 'individual',
    data_status: raw.data_status || 'insufficient_data',
    data_state: historyIncomplete ? 'incomplete_history' : raw.data_state || (trendReadyCount > 0 ? 'ready' : 'insufficient_data'),
    data_origin: raw.data_origin || 'unavailable',
    history_type: raw.history_type || 'unavailable',
    answer: raw.answer || null,
    historical_trends: adaptedTrends,
    is_trend_ready: trendReadyCount > 0,
    is_forecast_ready: !historyIncomplete && Boolean(raw.forecast && raw.forecast.status === 'ready'),
    current_signals: Array.isArray(raw.current_signals) ? raw.current_signals : [],
    key_changes: Array.isArray(raw.key_changes) ? raw.key_changes : [],
    explanations: Array.isArray(raw.explanations) ? raw.explanations : [],
    recommendations: Array.isArray(raw.recommendations) ? raw.recommendations : [],
    action_recommendations: rawActionRecs.map(adaptActionRecommendation).filter(Boolean),
    next_actions: Array.isArray(raw.next_actions) ? raw.next_actions : [],
    applied_filters: raw.applied_filters || {},
    unapplied_filters: Array.isArray(raw.unapplied_filters) ? raw.unapplied_filters : [],
    capabilities,
    metric_results: metricResults,
    skill_health: withholdResult(raw.skill_health, ['score', 'health_score']),
    skill_half_life: withholdResult(raw.skill_half_life, ['half_life_months']),
    forecast,
    ai_disruption: raw.ai_disruption || null,
    market_rankings: Array.isArray(raw.market_rankings) ? raw.market_rankings : [],
    workforce_impact: raw.workforce_impact || null,
    confidence_breakdown: raw.confidence_breakdown || null,
    freshness: raw.freshness || {},
    source_coverage: raw.source_coverage || {},
    follow_up_suggestions: Array.isArray(raw.follow_up_suggestions) ? raw.follow_up_suggestions.slice(0, 2) : [],
    readiness: safeReadiness,
    blocking_reasons: Array.isArray(raw.blocking_reasons) ? raw.blocking_reasons : []
  };
}

export async function getAuthIdToken(explicitToken = null) {
  if (explicitToken) return explicitToken;
  try {
    if (typeof window !== 'undefined' && typeof window.talentscopeGetAuthToken === 'function') {
      const hooked = await window.talentscopeGetAuthToken();
      if (hooked) return hooked;
    }
    // Firebase's browser SDK is not loadable by Node's default ESM loader.
    // Explicit tokens and the test hook above remain available to non-browser callers.
    if (typeof window === 'undefined' || typeof document === 'undefined') return null;
    const { auth } = await import('../auth/firebase-client.js');
    if (!auth) return null;

    let user = auth.currentUser;
    if (!user) {
      if (typeof auth.authStateReady === 'function') {
        await auth.authStateReady();
        user = auth.currentUser;
      } else {
        user = await new Promise(resolve => {
          const unsubscribe = auth.onAuthStateChanged(u => {
            unsubscribe();
            resolve(u);
          });
          setTimeout(() => resolve(auth.currentUser || null), 2000);
        });
      }
    }

    if (user && typeof user.getIdToken === 'function') {
      return await user.getIdToken();
    }
  } catch (err) {
    console.warn('Could not acquire Firebase auth token:', err);
  }
  return null;
}

export async function sendCoreIntelligenceRequest(path, options = {}) {
  const token = await getAuthIdToken(options.token);
  if (!token) {
    const authError = new Error('Your sign-in session could not be verified for core intelligence. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = 401;
    throw authError;
  }

  const headers = {
    Accept: 'application/json',
    Authorization: `Bearer ${token}`,
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach the core intelligence service. Please check your network or sign-in.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified for core intelligence. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok) {
    let errorDetail = null;
    try {
      const errJson = await response.json();
      errorDetail = typeof errJson?.detail === 'string' ? errJson.detail : errJson?.detail?.message;
    } catch {}
    const httpError = new Error(errorDetail || (response.status === 503
      ? 'The core intelligence service is temporarily unavailable.'
      : `Intelligence query failed (${response.status}).`));
    httpError.name = 'CoreIntelligenceHttpError';
    httpError.status = response.status;
    throw httpError;
  }

  const rawJson = await response.json();
  return adaptCoreIntelligenceResponse(rawJson);
}

export function queryCoreIntelligence(requestData, options = {}) {
  const payload = buildCoreIntelligenceRequest(requestData);
  return sendCoreIntelligenceRequest('/api/v1/intelligence/core', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options
  });
}

export function querySkillIntelligence(params = {}, options = {}) {
  return queryCoreIntelligence({
    ...params,
    intelligenceType: 'skill'
  }, options);
}

export function queryMarketIntelligence(params = {}, options = {}) {
  return queryCoreIntelligence({
    ...params,
    intelligenceType: 'market'
  }, options);
}

export function queryJobIntelligence(params = {}, options = {}) {
  return queryCoreIntelligence({
    ...params,
    intelligenceType: 'job'
  }, options);
}

export async function queryActionRecommendations(requestData, options = {}) {
  const payload = buildCoreIntelligenceRequest(requestData);
  const token = await getAuthIdToken(options.token);
  if (!token) {
    const authError = new Error('Your sign-in session could not be verified for action recommendations. Please sign in again.');
    authError.name = 'ActionIntelligenceAuthError';
    authError.status = 401;
    throw authError;
  }
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/actions`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach the action intelligence service. Please check your network or sign-in.');
    networkError.name = 'ActionIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified for action recommendations. Please sign in again.');
    authError.name = 'ActionIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok) {
    let errorDetail = null;
    try {
      const errJson = await response.json();
      errorDetail = typeof errJson?.detail === 'string' ? errJson.detail : errJson?.detail?.message;
    } catch {}
    const httpError = new Error(errorDetail || `Action recommendations query failed (${response.status}).`);
    httpError.name = 'ActionIntelligenceHttpError';
    httpError.status = response.status;
    throw httpError;
  }

  const rawJson = await response.json();
  return adaptActionRecommendationResponse(rawJson);
}

export function buildAnswerRequest(options = {}) {
  const message = options.message || options.query || '';
  const portalType = options.portalType || options.portal_type || 'individual';
  const domain = options.domain ? normalizeDomainKey(options.domain) : null;
  const capabilityId = options.capabilityId || options.capability_id || null;
  const location = (options.location && options.location !== 'Global') ? String(options.location).trim() : null;
  const timeRange = normalizeAnswerTimeRange(options.timeRange || options.time_range || options.range || '30d');
  const targetRole = options.targetRole || options.target_role || null;
  const rawSkills = options.selectedSkills ?? options.selected_skills ?? options.skills;
  const rawCompanies = options.selectedCompanies ?? options.selected_companies ?? options.companies;
  const rawRoles = options.selectedRoles ?? options.selected_roles ?? options.roles;
  const selectedSkills = Array.isArray(rawSkills) ? rawSkills.filter(Boolean) : (rawSkills ? [rawSkills] : []);
  const selectedCompanies = Array.isArray(rawCompanies) ? rawCompanies.filter(Boolean) : (rawCompanies ? [rawCompanies] : []);
  const selectedRoles = Array.isArray(rawRoles) ? rawRoles.filter(Boolean) : (rawRoles ? [rawRoles] : []);
  const companyId = options.companyId || options.company_id || null;
  const conversationId = options.conversationId || options.conversation_id || null;
  const clientMessageId = options.clientMessageId || options.client_message_id || null;
  const regenerate = Boolean(options.regenerate);
  const filters = options.filters ? { ...options.filters } : {};
  if (domain && !filters.domain) {
    filters.domain = domain;
  }
  const clearContext = Boolean(options.clearContext || options.clear_context);
  const observations = Array.isArray(options.observations) ? options.observations : [];
  const contextOverride = options.contextOverride || options.context_override || {};

  return {
    message: String(message).trim(),
    portal_type: portalType,
    domain,
    capability_id: capabilityId,
    location,
    time_range: timeRange,
    target_role: targetRole,
    selected_skills: selectedSkills,
    selected_roles: selectedRoles,
    selected_companies: selectedCompanies,
    company_id: companyId,
    conversation_id: conversationId,
    client_message_id: clientMessageId,
    regenerate,
    filters,
    clear_context: clearContext,
    observations,
    context_override: contextOverride
  };
}

export function adaptFactItem(fact) {
  if (!fact) return null;
  return {
    fact_id: fact.fact_id || null,
    fact_type: fact.fact_type || 'metric',
    entity_name: fact.entity_name || null,
    canonical_entity_id: fact.canonical_entity_id || null,
    entity_type: fact.entity_type || null,
    metric_name: fact.metric_name || '',
    metric_value: fact.metric_value != null ? fact.metric_value : null,
    metric_kind: fact.metric_kind || null,
    unit: fact.unit || null,
    denominator: fact.denominator != null ? fact.denominator : null,
    denominator_unit: fact.denominator_unit || null,
    signal_type: fact.signal_type || null,
    period: fact.period || fact.observation_period || null,
    observation_period: fact.observation_period || fact.period || null,
    timestamp: fact.timestamp || fact.observed_at || null,
    source: fact.source || null,
    data_origin: fact.data_origin || 'unavailable',
    history_type: fact.history_type || null,
    series_id: fact.series_id || null,
    panel_version: fact.panel_version || null,
    quality_state: fact.quality_state || 'unknown',
    readiness_state: fact.readiness_state || null,
    freshness_state: fact.freshness_state || null,
    freshness: fact.freshness && typeof fact.freshness === 'object' ? fact.freshness : null,
    calculation_version: fact.calculation_version || null,
    provenance_id: fact.provenance_id || null,
    evidence_reference: fact.evidence_reference || null,
    details: fact.details && typeof fact.details === 'object' ? fact.details : {}
  };
}

export function adaptEvidenceItem(ev) {
  if (!ev) return null;
  return {
    evidence_id: ev.evidence_id || 'ev_unknown',
    source: ev.source || null,
    signal_type: ev.signal_type || 'unknown',
    measured_signal_type: ev.measured_signal_type || null,
    period: ev.period || null,
    unit: ev.unit || null,
    data_origin: ev.data_origin || 'unavailable',
    history_type: ev.history_type || null,
    series_id: ev.series_id || null,
    fetch_run_id: ev.fetch_run_id || null,
    supporting_fetch_run_ids: Array.isArray(ev.supporting_fetch_run_ids) ? ev.supporting_fetch_run_ids : [],
    source_url: ev.source_url || null,
    provenance_id: ev.provenance_id || null,
    supporting_observation_ids: Array.isArray(ev.supporting_observation_ids) ? ev.supporting_observation_ids : [],
    supporting_source_urls: Array.isArray(ev.supporting_source_urls) ? ev.supporting_source_urls : [],
    freshness_state: ev.freshness_state || null,
    quality: ev.quality || 'unknown',
    confidence: ev.confidence != null ? ev.confidence : null,
    description: ev.description || ''
  };
}

export function adaptCoreIntelligenceAnswerResponse(raw) {
  if (!raw) {
    return {
      request_id: 'ans_err',
      user_message: '',
      portal_type: 'individual',
      domain: null,
      selected_entities: [],
      conversation_id: null,
      client_message_id: null,
      status: 'error',
      resolved_entity: null,
      intent: 'unknown',
      plan_status: 'blocked',
      execution_status: 'failed',
      answer: 'No response received from intelligence service.',
      answer_origin: 'deterministic',
      answer_title: null,
      answer_type: 'other',
      source_mode: 'platform_data',
      visualization: null,
      next_actions: [],
      facts: [],
      evidence: [],
      metric_results: [],
      planned_primary_capability: null,
      executed_primary_capability: null,
      dependency_capabilities: [],
      planned_capabilities: [],
      capabilities_used: [],
      capabilities: {},
      applied_filters: {},
      unapplied_filters: [],
      confidence: null,
      freshness: {},
      history_type: 'none',
      source_coverage: {},
      limitations: ['Service response was empty.'],
      reason_codes: ['EMPTY_SERVICE_RESPONSE'],
      follow_up_questions: [],
      follow_up_suggestions: [],
      evaluated_at: new Date().toISOString()
    };
  }

  const rawFacts = Array.isArray(raw.facts) ? raw.facts : [];
  const rawEvidence = Array.isArray(raw.evidence) ? raw.evidence : [];
  const followUps = Array.isArray(raw.follow_up_questions) ? raw.follow_up_questions : [];
  const followUpSuggestions = Array.isArray(raw.follow_up_suggestions) && raw.follow_up_suggestions.length
    ? raw.follow_up_suggestions.slice(0, 2)
    : followUps.slice(0, 2);

  return {
    request_id: raw.request_id || `ans_${Date.now()}`,
    user_message: raw.user_message || '',
    portal_type: raw.portal_type || 'individual',
    domain: raw.domain || raw.applied_filters?.domain || null,
    selected_entities: Array.isArray(raw.selected_entities) ? raw.selected_entities : [],
    conversation_id: raw.conversation_id || null,
    client_message_id: raw.client_message_id || null,
    status: raw.status || raw.execution_status || 'unavailable',
    resolved_entity: raw.resolved_entity || null,
    intent: raw.intent || 'unknown',
    plan_status: raw.plan_status || 'planned',
    execution_status: raw.execution_status || 'unavailable',
    answer: raw.answer || '',
    answer_origin: raw.answer_origin === 'gemini' ? 'gemini' : 'deterministic',
    answer_title: typeof raw.answer_title === 'string' ? raw.answer_title : null,
    answer_type: ['explanation', 'comparison', 'recommendations', 'roadmap', 'other'].includes(raw.answer_type) ? raw.answer_type : 'other',
    source_mode: ['platform_data', 'ai_general_guidance', 'mixed'].includes(raw.source_mode)
      ? raw.source_mode
      : (raw.answer_origin === 'gemini' ? 'mixed' : 'platform_data'),
    visualization: raw.visualization && typeof raw.visualization === 'object' ? raw.visualization : null,
    next_actions: Array.isArray(raw.next_actions) ? raw.next_actions.slice(0, 5) : [],
    facts: rawFacts.map(adaptFactItem).filter(Boolean),
    evidence: rawEvidence.map(adaptEvidenceItem).filter(Boolean),
    sources: Array.isArray(raw.sources)
      ? raw.sources.filter(source => source && typeof source === 'object').map(source => ({
        type: typeof source.type === 'string' ? source.type : (typeof source.source_type === 'string' ? source.source_type : null),
        label: typeof source.label === 'string' ? source.label : (typeof source.title === 'string' ? source.title : null),
        source_url: typeof source.source_url === 'string' ? source.source_url : null
      }))
      : [],
    enough_data: typeof raw.enough_data === 'boolean' ? raw.enough_data : null,
    degraded: raw.degraded === true,
    degraded_reason: typeof raw.degraded_reason === 'string' ? raw.degraded_reason : null,
    metric_results: Array.isArray(raw.metric_results) ? raw.metric_results : [],
    planned_primary_capability: typeof raw.planned_primary_capability === 'string' ? raw.planned_primary_capability : null,
    executed_primary_capability: typeof raw.executed_primary_capability === 'string' ? raw.executed_primary_capability : null,
    dependency_capabilities: Array.isArray(raw.dependency_capabilities) ? raw.dependency_capabilities : [],
    planned_capabilities: Array.isArray(raw.planned_capabilities) ? raw.planned_capabilities : [],
    capabilities_used: Array.isArray(raw.capabilities_used) ? raw.capabilities_used : [],
    capabilities: raw.capabilities || {},
    applied_filters: raw.applied_filters || {},
    unapplied_filters: Array.isArray(raw.unapplied_filters) ? raw.unapplied_filters : [],
    confidence: raw.confidence || null,
    freshness: raw.freshness || {},
    history_type: raw.history_type || 'none',
    source_coverage: raw.source_coverage || {},
    limitations: Array.isArray(raw.limitations) ? raw.limitations : [],
    reason_codes: Array.isArray(raw.reason_codes) ? raw.reason_codes : [],
    follow_up_questions: followUps,
    follow_up_suggestions: followUpSuggestions,
    evaluated_at: raw.evaluated_at || new Date().toISOString()
  };
}

export async function queryGuestIntelligenceAnswer(requestData, options = {}) {
  const payload = buildAnswerRequest(requestData);
  payload.conversation_id = null;
  payload.company_id = null;
  payload.user_id = null;

  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/guest/answer`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach the guest intelligence answer service. Please check your network connection.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 403) {
    const authReqError = new Error('This capability requires an authenticated account. Please sign in to access personalized profile and workforce insights.');
    authReqError.name = 'CoreIntelligenceAuthRequiredError';
    authReqError.status = 403;
    throw authReqError;
  }

  if (!response.ok) {
    let errorDetail = null;
    try {
      const errJson = await response.json();
      errorDetail = typeof errJson?.detail === 'string' ? errJson.detail : null;
    } catch {}
    const httpError = new Error(errorDetail || `Guest intelligence query failed (${response.status}).`);
    httpError.name = 'CoreIntelligenceHttpError';
    httpError.status = response.status;
    throw httpError;
  }

  const rawJson = await response.json();
  return adaptCoreIntelligenceAnswerResponse(rawJson);
}

export async function queryCoreIntelligenceAnswer(requestData, options = {}) {
  if (options.guest) {
    return queryGuestIntelligenceAnswer(requestData, options);
  }
  const payload = buildAnswerRequest(requestData);
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/answer`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach the core intelligence answer service. Please check your network connection.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified for intelligence answers. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok) {
    let errorDetail = null;
    try {
      const errJson = await response.json();
      const detail = errJson?.detail;
      if (typeof detail === 'string') {
        errorDetail = detail;
      } else if (typeof detail?.message === 'string') {
        errorDetail = detail.message;
      } else if (Array.isArray(detail)) {
        errorDetail = detail.map(item => {
          const location = Array.isArray(item?.loc)
            ? item.loc.filter(part => part !== 'body').join('.')
            : '';
          const message = typeof item?.msg === 'string' ? item.msg : 'Invalid request value';
          return location ? `${location}: ${message}` : message;
        }).join('; ');
      }
    } catch {}
    const fallback = response.status === 422
      ? 'The answer request contains an invalid value. Check the message and selected filters, then try again.'
      : `Intelligence answer query failed (${response.status}).`;
    const httpError = new Error(errorDetail || fallback);
    httpError.name = 'CoreIntelligenceHttpError';
    httpError.status = response.status;
    throw httpError;
  }

  const rawJson = await response.json();
  return adaptCoreIntelligenceAnswerResponse(rawJson);
}

export async function queryCoreIntelligencePlan(requestData, options = {}) {
  const payload = buildAnswerRequest(requestData);
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/plan`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach the core intelligence plan service. Please check your network connection.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified for intelligence planning. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok) {
    let errorDetail = null;
    try {
      const errJson = await response.json();
      errorDetail = typeof errJson?.detail === 'string' ? errJson.detail : errJson?.detail?.message;
    } catch {}
    const httpError = new Error(errorDetail || `Intelligence plan query failed (${response.status}).`);
    httpError.name = 'CoreIntelligenceHttpError';
    httpError.status = response.status;
    throw httpError;
  }

  return response.json();
}

export async function resolveEntity(name, options = {}) {
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  const payload = {
    name: String(name || '').trim(),
    ...(options.entityType || options.entity_type ? { entity_type: options.entityType || options.entity_type } : {}),
    ...(options.context ? { context: options.context } : {})
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/entities/resolve`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach entity resolution service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Session unverified for entity resolution.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok) {
    throw new Error(`Entity resolution failed (${response.status}).`);
  }

  return await response.json();
}

export async function getCapabilityCatalog(options = {}) {
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  let targetUrl = `${API_BASE_URL}/api/v1/intelligence/capabilities`;
  const portal = options.portalType || options.portal_type;
  if (portal) {
    targetUrl += `?portal_type=${encodeURIComponent(portal)}`;
  }

  let response;
  try {
    response = await fetch(targetUrl, {
      method: 'GET',
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach capability registry service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (!response.ok) {
    throw new Error(`Capability catalog query failed (${response.status}).`);
  }

  return await response.json();
}

export async function evaluateCapabilities(requestData, options = {}) {
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/capabilities/evaluate`, {
      method: 'POST',
      body: JSON.stringify(requestData),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach capability evaluation service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (!response.ok) {
    throw new Error(`Capability evaluation query failed (${response.status}).`);
  }

  return await response.json();
}

export const queryIntelligenceAnswer = queryCoreIntelligenceAnswer;

export async function fetchIntelligenceConversations(options = {}) {
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  const limit = options.limit || 20;
  const query = new URLSearchParams({ limit: String(limit) });
  if (options.domain) query.set('domain', normalizeDomainKey(options.domain));
  if (options.portalType || options.portal_type) query.set('portal_type', String(options.portalType || options.portal_type));
  const targetUrl = `${API_BASE_URL}/api/v1/intelligence/conversations?${query.toString()}`;

  let response;
  try {
    response = await fetch(targetUrl, {
      method: 'GET',
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach conversation history service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (response.status === 503) {
    const serviceError = new Error('Authentication service is temporarily unavailable. Please retry shortly.');
    serviceError.name = 'CoreIntelligenceServiceUnavailableError';
    serviceError.status = 503;
    throw serviceError;
  }

  if (!response.ok) {
    throw new Error(`Failed to list conversations (${response.status}).`);
  }

  return await response.json();
}

export async function fetchConversationHistory(conversationId, options = {}) {
  if (!conversationId) return null;
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  const query = new URLSearchParams();
  if (options.domain) query.set('domain', normalizeDomainKey(options.domain));
  if (options.portalType || options.portal_type) query.set('portal_type', String(options.portalType || options.portal_type));
  const queryString = query.toString();
  const targetUrl = `${API_BASE_URL}/api/v1/intelligence/conversations/${encodeURIComponent(conversationId)}${queryString ? `?${queryString}` : ''}`;

  let response;
  try {
    response = await fetch(targetUrl, {
      method: 'GET',
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach conversation history service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch conversation (${response.status}).`);
  }

  return await response.json();
}

export async function deleteIntelligenceConversation(conversationId, options = {}) {
  if (!conversationId) return { status: 'deleted' };
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  const query = new URLSearchParams();
  if (options.domain) query.set('domain', normalizeDomainKey(options.domain));
  if (options.portalType || options.portal_type) query.set('portal_type', String(options.portalType || options.portal_type));
  const queryString = query.toString();
  const targetUrl = `${API_BASE_URL}/api/v1/intelligence/conversations/${encodeURIComponent(conversationId)}${queryString ? `?${queryString}` : ''}`;

  let response;
  try {
    response = await fetch(targetUrl, {
      method: 'DELETE',
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach conversation service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (response.status === 401 || response.status === 403) {
    const authError = new Error('Your sign-in session could not be verified. Please sign in again.');
    authError.name = 'CoreIntelligenceAuthError';
    authError.status = response.status;
    throw authError;
  }

  if (!response.ok && response.status !== 404) {
    throw new Error(`Failed to delete conversation (${response.status}).`);
  }

  return response.ok ? await response.json() : { status: 'deleted', conversation_id: conversationId };
}

export async function fetchMarketJobs(params = {}, options = {}) {
  const rawQuery = (params.query || params.role || 'engineer').trim();
  const query = rawQuery.length >= 2 ? rawQuery : 'Software';
  const country = params.country ? String(params.country).trim().slice(0, 2) : null;
  const qParams = new URLSearchParams({ query });
  if (country && /^[A-Za-z]{2}$/.test(country)) {
    qParams.set('country', country.toLowerCase());
  }

  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/market/jobs?${qParams.toString()}`, {
      method: 'GET',
      headers,
      ...options
    });
    if (!res.ok) {
      return { status: 'empty', jobs: [], count: 0, query };
    }
    const data = await res.json();
    return {
      status: data.status || (data.jobs && data.jobs.length ? 'available' : 'empty'),
      query: data.query || query,
      country: data.country || country,
      jobs: Array.isArray(data.jobs) ? data.jobs : [],
      count: typeof data.count === 'number' ? data.count : (data.jobs ? data.jobs.length : 0),
      fetched_at: data.fetched_at || null,
      source: data.source || 'stored'
    };
  } catch (err) {
    return { status: 'unavailable', jobs: [], count: 0, query, error: err.message };
  }
}

export const fetchActionRecommendations = queryActionRecommendations;

export async function createIntelligenceConversation(payload = {}, options = {}) {
  const token = await getAuthIdToken(options.token);
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/conversations`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
      ...options,
      headers
    });
  } catch (err) {
    const networkError = new Error('Could not reach conversation creation service.');
    networkError.name = 'CoreIntelligenceNetworkError';
    throw networkError;
  }

  if (!response.ok) {
    throw new Error(`Failed to create conversation (${response.status}).`);
  }

  return await response.json();
}

export function isClientGeneratedConversationId(conversationId, portalType = 'individual', domain = 'skill') {
  const normDomain = normalizeDomainKey(domain);
  return typeof conversationId === 'string'
    && conversationId.startsWith(`conv_${portalType}_${normDomain}_`);
}

export function getActiveConversationId(portalType = 'individual', domain = 'skill', userId = null) {
  const normDomain = normalizeDomainKey(domain);
  const userScope = userId ? String(userId).trim() : 'default';
  try {
    const key = `talentscope_active_conv_${userScope}_${portalType}_${normDomain}`;
    const cid = sessionStorage.getItem(key) || localStorage.getItem(key) || null;
    if (isClientGeneratedConversationId(cid, portalType, normDomain)) {
      sessionStorage.removeItem(key);
      localStorage.removeItem(key);
      return null;
    }
    return cid;
  } catch {
    return null;
  }
}

export function setActiveConversationId(conversationId, portalType = 'individual', domain = 'skill', userId = null) {
  const normDomain = normalizeDomainKey(domain);
  const userScope = userId ? String(userId).trim() : 'default';
  try {
    const key = `talentscope_active_conv_${userScope}_${portalType}_${normDomain}`;
    if (conversationId) {
      sessionStorage.setItem(key, conversationId);
      localStorage.setItem(key, conversationId);
    } else {
      sessionStorage.removeItem(key);
      localStorage.removeItem(key);
    }
  } catch {}
}
