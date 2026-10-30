import { API_BASE_URL } from '../../../config/api.js';
import { fetchPillarSkillTrends } from '../skills/skills-api.js';

// Resolve to backend API host (defaulting to http://127.0.0.1:8000 for local development)
const BACKEND_API_BASE_URL = (() => {
  if (typeof API_BASE_URL === 'string' && API_BASE_URL && !API_BASE_URL.match(/:3000|:5173|:5000/)) {
    return API_BASE_URL.replace(/\/$/, '');
  }
  return 'http://127.0.0.1:8000';
})();

export { fetchPillarSkillTrends };

export async function fetchMarketOverview() {
  const urls = [
    `${BACKEND_API_BASE_URL}/api/market-intelligence/overview`,
    `${BACKEND_API_BASE_URL}/api/market-intelligence/ecosystem`,
    `http://127.0.0.1:8000/api/market-intelligence/overview`,
    `http://127.0.0.1:8000/api/market-intelligence/ecosystem`,
    `${BACKEND_API_BASE_URL}/api/v1/market-intelligence/overview`,
    `http://127.0.0.1:8000/api/v1/market-intelligence/overview`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        headers: { Accept: 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && typeof data === 'object' && Array.isArray(data.emerging_technologies)) {
          return data;
        }
      }
    } catch {
      // try next target
    }
  }

  // Fallback data if backend is momentarily unreachable
  return {
    total_signals_tracked: 330,
    total_topics_tracked: 53,
    freshness_date: '2026-04',
    first_period: '2025-11',
    signal_source: 'Wikipedia Developer Community Signals',
    emerging_technologies: [
      {
        name: 'Cryptography',
        skill_name: 'cryptography',
        mom_growth_pct: 1322.0,
        current_activity: 548224,
        prior_activity: 38553,
        trajectory: [42259, 45967, 36552, 37210, 38553, 548224],
        trajectory_periods: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'],
        direction: 'up',
        category: 'Cybersecurity',
        description: 'Surging community interest (+1322.0% MoM) with 548,224 monthly Wikipedia pageviews.'
      },
      {
        name: 'Problem Solving',
        skill_name: 'problem solving',
        mom_growth_pct: 692.2,
        current_activity: 146659,
        prior_activity: 18512,
        trajectory: [23075, 24483, 26538, 18475, 18512, 146659],
        trajectory_periods: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'],
        direction: 'up',
        category: 'Core Engineering Competency',
        description: 'Surging community interest (+692.2% MoM) with 146,659 monthly Wikipedia pageviews.'
      },
      {
        name: 'Network Security',
        skill_name: 'network security',
        mom_growth_pct: 227.9,
        current_activity: 20191,
        prior_activity: 6157,
        trajectory: [5388, 5332, 6501, 7073, 6157, 20191],
        trajectory_periods: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'],
        direction: 'up',
        category: 'Cybersecurity',
        description: 'Surging community interest (+227.9% MoM) with 20,191 monthly Wikipedia pageviews.'
      },
      {
        name: 'Root Cause Analysis',
        skill_name: 'root cause analysis',
        mom_growth_pct: 81.0,
        current_activity: 12508,
        prior_activity: 6912,
        trajectory: [6025, 3608, 4646, 5462, 6912, 12508],
        trajectory_periods: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'],
        direction: 'up',
        category: 'Systems Engineering',
        description: 'Surging community interest (+81.0% MoM) with 12,508 monthly Wikipedia pageviews.'
      },
      {
        name: 'Logical Reasoning',
        skill_name: 'logical reasoning',
        mom_growth_pct: 31.2,
        current_activity: 15107,
        prior_activity: 11511,
        trajectory: [21660, 11587, 11398, 10487, 11511, 15107],
        trajectory_periods: ['2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04'],
        direction: 'up',
        category: 'Analytical Foundations',
        description: 'Surging community interest (+31.2% MoM) with 15,107 monthly Wikipedia pageviews.'
      }
    ]
  };
}
