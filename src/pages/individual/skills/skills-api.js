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
  const trends = Array.isArray(raw.historical_trends) ? raw.historical_trends : [];
  const historyIncomplete = raw.history_complete === false || raw.data_state === 'incomplete_history';
  const signals = Array.isArray(raw.current_signals) ? raw.current_signals : [];
  const sources = [...new Set([
    ...signals.map(s => s.source),
    ...trends.map(t => t.source)
  ])].filter(Boolean);

  const mappedSkills = trends.map(t => ({
    ...t,
    skill: t.entity_name,
    category: t.entity_type,
    trend: t.is_trend_ready && !historyIncomplete ? (t.trend_direction || 'Stable') : 'Insufficient Data',
    growth_pct: t.is_trend_ready && !historyIncomplete ? t.growth_pct : null,
    velocity: t.is_trend_ready && !historyIncomplete ? t.velocity : null,
    is_trend_ready: Boolean(t.is_trend_ready && !historyIncomplete),
    signal_type: t.signal_type,
    series: Array.isArray(t.data_points) ? t.data_points
      .filter(dp => dp && dp.value != null && Number.isFinite(Number(dp.value)))
      .map(dp => ({ ...dp, period: dp.period, value: Number(dp.value) })) : []
  }));

  const normSkill = skill ? skill.toLowerCase().trim() : '';
  const selectedTrend = mappedSkills.find(s => s.skill.toLowerCase() === normSkill) || mappedSkills[0] || null;

  return {
    ...raw,
    data_status: raw.data_status || 'insufficient_data',
    data_state: historyIncomplete ? 'incomplete_history' : raw.data_state || (mappedSkills.some(s => s.is_trend_ready) ? 'ready' : 'insufficient_data'),
    sources_used: sources,
    personal_top_skills: mappedSkills,
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
