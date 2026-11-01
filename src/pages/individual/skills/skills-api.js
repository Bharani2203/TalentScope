import { API_BASE_URL } from '../../../config/api.js';

// Always resolve to the backend server (defaulting to http://127.0.0.1:8000 when frontend dev server ports are encountered)
const BACKEND_API_BASE_URL = (() => {
  if (typeof API_BASE_URL === 'string' && API_BASE_URL && !API_BASE_URL.match(/:3000|:5173|:5000/)) {
    return API_BASE_URL.replace(/\/$/, '');
  }
  return 'http://127.0.0.1:8000';
})();

/**
 * Executes a promise with a timeout guarantee and optional fallback value.
 */
export function withTimeout(promise, ms = 5000, fallback = undefined) {
  let timerId;
  const timeoutPromise = new Promise((resolve, reject) => {
    timerId = setTimeout(() => {
      if (fallback !== undefined) {
        resolve(typeof fallback === 'function' ? fallback() : fallback);
      } else {
        reject(new Error(`Operation timed out after ${ms}ms`));
      }
    }, ms);
  });
  return Promise.race([promise, timeoutPromise]).finally(() => clearTimeout(timerId));
}

async function authenticatedRequest(path, options = {}) {
  let idToken = null;
  try {
    const { auth } = await import('../../../auth/firebase-client.js');
    let firebaseUser = auth?.currentUser;
    if (!firebaseUser && typeof auth?.onAuthStateChanged === 'function') {
      firebaseUser = await withTimeout(new Promise(resolve => {
        const unsubscribe = auth.onAuthStateChanged(u => {
          unsubscribe();
          resolve(u);
        });
      }), 2000, null);
    }
    if (firebaseUser && typeof firebaseUser.getIdToken === 'function') {
      idToken = await withTimeout(firebaseUser.getIdToken(), 3000, null);
    }
  } catch (err) {
    console.warn('Could not acquire Firebase auth token for skills:', err);
  }

  if (!idToken) {
    throw new Error('Your sign-in session expired. Sign in again to load your skills.');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  let response;
  try {
    response = await fetch(`${BACKEND_API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${idToken}`,
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers
      }
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Skill service request timed out. Please try again.');
    }
    throw new Error('Could not reach the skill service. Please try again.');
  } finally {
    clearTimeout(timeoutId);
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
  const supportedRanges = new Set(['current', '7d', '30d', '3m', '6m', 'custom']);
  if (!supportedRanges.has(range)) throw new Error('Choose a supported historical window.');
  if (range === 'custom' && (!Number.isInteger(days) || days < 7 || days > 184)) {
    throw new Error('Custom history must be between 7 and 184 days.');
  }
  if (range !== 'custom' && days !== undefined) throw new Error('Custom days are only valid with the custom window.');
  const effectiveRange = range === 'current' ? '6m' : range;
  const params = new URLSearchParams({ range: effectiveRange });
  if (range === 'custom' && Number.isInteger(days)) params.set('days', String(days));
  if (location) params.set('location', location);
  if (skill) params.set('skill', skill);

  const raw = await authenticatedRequest(`/api/v1/skills/intelligence?${params}`);
  return adaptSkillIntelligenceResponse(raw, skill);
}

export async function loadSkillTrends({ sortBy = 'frequency', limit = 5 } = {}) {
  const params = new URLSearchParams({ sort_by: sortBy, limit: String(limit) });
  const urls = [
    `${BACKEND_API_BASE_URL}/api/v1/skills/top-trending?${params}`,
    `${BACKEND_API_BASE_URL}/api/v1/skills/trends/overall?${params}`,
    `${BACKEND_API_BASE_URL}/api/skill-intelligence/trends?${params}`,
    `${BACKEND_API_BASE_URL}/api/v1/skill-intelligence/trends?${params}`,
    `http://127.0.0.1:8000/api/skill-intelligence/trends?${params}`,
    `http://127.0.0.1:8000/api/v1/skill-intelligence/trends?${params}`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data;
        }
      }
    } catch {
      // try next backend target
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return [];
}


export async function fetchAdvancedSkillMetrics({ limit = 5, skills, skill } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (skills) params.set('skills', skills);
  if (skill) params.set('skill', skill);
  const urls = [
    `${BACKEND_API_BASE_URL}/api/skill-intelligence/advanced-metrics?${params}`,
    `${BACKEND_API_BASE_URL}/api/v1/skill-intelligence/advanced-metrics?${params}`,
    `http://127.0.0.1:8000/api/skill-intelligence/advanced-metrics?${params}`,
    `http://127.0.0.1:8000/api/v1/skill-intelligence/advanced-metrics?${params}`,
    `${BACKEND_API_BASE_URL}/api/v1/skills/analytics?${params}`,
    `http://127.0.0.1:8000/api/v1/skills/analytics?${params}`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data;
        }
        if (data && !Array.isArray(data) && (data.health || data.skill)) {
          return [data];
        }
      }
    } catch {
      // try next backend target
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return [];
}

export async function fetchCareerPillars() {
  const urls = [
    `${BACKEND_API_BASE_URL}/api/skill-intelligence/pillars`,
    `${BACKEND_API_BASE_URL}/api/v1/skill-intelligence/pillars`,
    `http://127.0.0.1:8000/api/skill-intelligence/pillars`,
    `http://127.0.0.1:8000/api/v1/skill-intelligence/pillars`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data;
        }
      }
    } catch {
      // try next backend target
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return [];
}

export async function fetchPillarSkillTrends(pillarSlug, sortBy = 'composite') {
  const query = `?pillar=${encodeURIComponent(pillarSlug)}&sort_by=${encodeURIComponent(sortBy)}`;
  const urls = [
    `${BACKEND_API_BASE_URL}/api/skill-intelligence/trends${query}`,
    `${BACKEND_API_BASE_URL}/api/v1/skill-intelligence/trends${query}`,
    `http://127.0.0.1:8000/api/skill-intelligence/trends${query}`,
    `http://127.0.0.1:8000/api/v1/skill-intelligence/trends${query}`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data;
        }
      }
    } catch {
      // try next backend target
    } finally {
      clearTimeout(timeoutId);
    }
  }

  return [];
}
