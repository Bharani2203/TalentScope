import { API_BASE_URL } from '../../../config/api.js';

async function authenticatedRequest(path, options = {}) {
  const { auth } = await import('../../../auth/firebase-client.js');
  const firebaseUser = auth.currentUser;
  if (!firebaseUser) throw new Error('Your sign-in session expired. Sign in again to load your skills.');

  const idToken = await firebaseUser.getIdToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${idToken}`,
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers
      }
    });
  } catch {
    throw new Error('Could not reach the skill service. Please try again.');
  }

  if (response.status === 401 || response.status === 403) {
    throw new Error('Your sign-in session could not be verified. Sign in again to load your skills.');
  }
  if (!response.ok) {
    throw new Error(response.status === 503
      ? 'Your skills are temporarily unavailable. Please try again.'
      : 'The skill service could not complete your request.');
  }
  return response.json();
}

export function loadMySkills() {
  return authenticatedRequest('/api/v1/skills/my');
}

export function saveMySkills(skills) {
  return authenticatedRequest('/api/v1/skills/my', {
    method: 'PUT',
    body: JSON.stringify({ skills })
  });
}

export function saveFavouriteSkillIds(skill_ids) {
  return authenticatedRequest('/api/v1/skills/favourites', {
    method: 'PUT',
    body: JSON.stringify({ skill_ids })
  });
}

export function adaptSkillIntelligenceResponse(raw, skill) {
  const trendCollections = [
    raw.historical_trends,
    raw.market_top_skills,
    raw.skill_trends,
    raw.production_trends
  ];
  const trends = trendCollections.find(items => Array.isArray(items) && items.length) || [];
  const historyIncomplete = raw.history_complete === false || raw.data_state === 'incomplete_history';
  const signals = Array.isArray(raw.current_signals) ? raw.current_signals : [];
  const sources = [...new Set([
    ...(Array.isArray(raw.sources_used) ? raw.sources_used : []),
    ...signals.map(s => s.source),
    ...trends.map(t => t.source)
  ])].filter(Boolean);

  const mapTrend = trend => {
    const sourceTrendReady = typeof trend.is_trend_ready === 'boolean'
      ? trend.is_trend_ready
      : ['ready_for_trend', 'ready_for_forecast', 'fresh', 'ready'].includes(trend.readiness_state)
        || ['Growing', 'Stable', 'Declining'].includes(trend.trend);
    return {
      ...trend,
      skill: trend.entity_name || trend.skill || trend.canonical_name,
      category: trend.entity_type || trend.category,
      trend: sourceTrendReady && !historyIncomplete
        ? (trend.trend_direction || trend.trend || 'Stable')
        : 'Insufficient Data',
      growth_pct: sourceTrendReady && !historyIncomplete ? trend.growth_pct : null,
      velocity: sourceTrendReady && !historyIncomplete ? trend.velocity : null,
      is_trend_ready: Boolean(sourceTrendReady && !historyIncomplete),
      signal_type: trend.signal_type || 'demand',
      series: (Array.isArray(trend.data_points)
        ? trend.data_points
        : Array.isArray(trend.series) ? trend.series : [])
        .filter(dp => dp && dp.value != null && Number.isFinite(Number(dp.value)))
        .map(dp => ({ ...dp, period: dp.period, value: Number(dp.value) }))
    };
  };
  const mappedSkills = trends.map(mapTrend);
  const personalTrends = Array.isArray(raw.personal_top_skills)
    ? raw.personal_top_skills.map(mapTrend)
    : mappedSkills;

  const normSkill = skill ? skill.toLowerCase().trim() : '';
  const rawSelectedSkill = raw.selected_skill;
  const selectedSkillName = rawSelectedSkill?.skill || rawSelectedSkill?.entity_name;
  const selectedTrend = mappedSkills.find(s => (
    s.skill && s.skill.toLowerCase() === (selectedSkillName || normSkill).toLowerCase().trim()
  )) || personalTrends.find(s => s.skill && s.skill.toLowerCase() === normSkill)
    || mappedSkills[0]
    || (rawSelectedSkill ? mapTrend(rawSelectedSkill) : null);

  return {
    ...raw,
    data_status: raw.data_status || 'insufficient_data',
    data_state: historyIncomplete ? 'incomplete_history' : raw.data_state || (mappedSkills.some(s => s.is_trend_ready) ? 'ready' : 'insufficient_data'),
    sources_used: sources,
    personal_top_skills: personalTrends,
    market_top_skills: mappedSkills,
    selected_skill: selectedTrend,
    is_forecast_ready: Boolean(raw.forecast && raw.forecast.status === 'ready')
  };
}

export async function loadSkillIntelligence({ location, range = '6m', days, skill } = {}) {
  const supportedRanges = new Set(['7d', '30d', '3m', '6m', 'custom']);
  if (!supportedRanges.has(range)) throw new Error('Choose a supported historical window.');
  if (range === 'custom' && (!Number.isInteger(days) || days < 7 || days > 184)) {
    throw new Error('Custom history must be between 7 and 184 days.');
  }
  if (range !== 'custom' && days !== undefined) throw new Error('Custom days are only valid with the custom window.');
  const params = new URLSearchParams({ range });
  if (range === 'custom' && Number.isInteger(days)) params.set('days', String(days));
  if (location) params.set('location', location);
  if (skill) params.set('skill', skill);

  const raw = await authenticatedRequest(`/api/v1/skills/intelligence?${params}`);
  return adaptSkillIntelligenceResponse(raw, skill);
}
