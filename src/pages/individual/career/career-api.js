import { API_BASE_URL } from '../../../config/api.js';

// Resolve to backend API host (defaulting to http://127.0.0.1:8000 for local development)
const BACKEND_API_BASE_URL = (() => {
  if (typeof API_BASE_URL === 'string' && API_BASE_URL && !API_BASE_URL.match(/:3000|:5173|:5000/)) {
    return API_BASE_URL.replace(/\/$/, '');
  }
  return 'http://127.0.0.1:8000';
})();

export async function fetchLiveJobRoles() {
  const urls = [
    `${BACKEND_API_BASE_URL}/api/career-intelligence/roles`,
    `${BACKEND_API_BASE_URL}/api/v1/career-intelligence/roles`,
    `http://127.0.0.1:8000/api/career-intelligence/roles`,
    `http://127.0.0.1:8000/api/v1/career-intelligence/roles`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data;
        }
      }
    } catch {
      // try next target
    }
  }

  return [];
}

export async function fetchRoleGapAnalysis(targetRole, userSkills = []) {
  const payload = {
    target_role: targetRole,
    user_skills: userSkills
  };

  const urls = [
    `${BACKEND_API_BASE_URL}/api/career-intelligence/analyze-gap`,
    `${BACKEND_API_BASE_URL}/api/v1/career-intelligence/analyze-gap`,
    `http://127.0.0.1:8000/api/career-intelligence/analyze-gap`,
    `http://127.0.0.1:8000/api/v1/career-intelligence/analyze-gap`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        if (data && (typeof data.readiness_score === 'number' || typeof data.readinessScore === 'number')) {
          return {
            targetRole: data.targetRole || data.target_role || targetRole,
            readinessScore: data.readinessScore ?? data.readiness_score ?? 0,
            matchedSkills: data.matchedSkills || data.matched_skills || [],
            missingSkills: data.missingSkills || data.missing_skills || [],
            totalTopSkills: data.totalTopSkills ?? data.total_top_skills ?? 10,
            matchedCount: data.matchedCount ?? data.matched_count ?? 0,
            missingCount: data.missingCount ?? data.missing_count ?? 0
          };
        }
      }
    } catch {
      // try next target
    }
  }

  return {
    targetRole,
    readinessScore: 0,
    matchedSkills: [],
    missingSkills: [],
    totalTopSkills: 10,
    matchedCount: 0,
    missingCount: 10
  };
}

export async function fetchRoleSignalMix(roleName) {
  if (!roleName) return null;
  const target = encodeURIComponent(roleName.trim());
  const urls = [
    `${BACKEND_API_BASE_URL}/api/career-intelligence/signal-mix?role=${target}`,
    `${BACKEND_API_BASE_URL}/api/v1/career-intelligence/signal-mix?role=${target}`,
    `${BACKEND_API_BASE_URL}/api/career-intelligence/roles/${target}/signal-mix`,
    `http://127.0.0.1:8000/api/career-intelligence/signal-mix?role=${target}`,
    `http://127.0.0.1:8000/api/v1/career-intelligence/signal-mix?role=${target}`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.signal_mix || data.signalMix)) {
          return {
            role: data.role || roleName,
            signalMix: data.signalMix || data.signal_mix,
            signalBreakdown: data.signalBreakdown || data.signal_breakdown || {},
            total: data.total || 100
          };
        }
      }
    } catch {}
  }
  return null;
}


