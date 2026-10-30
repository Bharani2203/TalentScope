// ============================================================================
// TALENTSCOPE.AI — INTERNAL MOBILITY & JOBS CLIENT
// Fetch live company requisitions and calculate dynamic skill matches
// ============================================================================

import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

export async function loadCompanyInternalJobs({ companyName, companyId, token, signal } = {}) {
  const idToken = await getAuthIdToken(token);
  const params = new URLSearchParams();
  if (companyName) params.set('company_name', companyName);
  if (companyId) params.set('company_id', companyId);

  const url = `${API_BASE_URL}/api/v1/jobs/internal${params.toString() ? '?' + params.toString() : ''}`;
  const headers = {
    Accept: 'application/json'
  };
  if (idToken) {
    headers.Authorization = `Bearer ${idToken}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method: 'GET',
      headers,
      signal
    });
  } catch (err) {
    const error = new Error('Could not reach the jobs service. Check your connection and retry.');
    error.kind = 'network';
    throw error;
  }

  if (!response.ok) {
    const error = new Error(`Failed to load company requisitions (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export function calculateSkillMatch(userSkills = [], requiredSkills = []) {
  const normalizedUser = (Array.isArray(userSkills) ? userSkills : [])
    .map(s => String(s || '').trim().toLowerCase())
    .filter(Boolean);

  const reqList = (Array.isArray(requiredSkills) ? requiredSkills : [])
    .map(s => String(s || '').trim())
    .filter(Boolean);

  if (!reqList.length) {
    return {
      matchScore: 80,
      matchedSkills: (Array.isArray(userSkills) ? userSkills : []).slice(0, 3),
      gaps: []
    };
  }

  const matched = [];
  const gaps = [];

  for (const req of reqList) {
    const rLower = req.toLowerCase();
    const hasMatch = normalizedUser.some(u => 
      u === rLower || rLower.includes(u) || u.includes(rLower)
    );
    if (hasMatch) {
      matched.push(req);
    } else {
      gaps.push(req);
    }
  }

  const matchScore = Math.max(10, Math.min(100, Math.round((matched.length / reqList.length) * 100)));

  return {
    matchScore,
    matchedSkills: matched,
    gaps
  };
}

