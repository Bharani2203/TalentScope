import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

async function roadmapRequest(path, { method = 'GET', body, token, signal } = {}) {
  const idToken = await getAuthIdToken(token);
  if (!idToken) {
    const error = new Error('Sign in to access your learning roadmap.');
    error.kind = 'auth';
    error.status = 401;
    throw error;
  }
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/learning/roadmap${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${idToken}`,
        ...(body ? { 'Content-Type': 'application/json' } : {})
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
      ...(signal ? { signal } : {})
    });
  } catch {
    const error = new Error('Could not reach the learning roadmap service. Check your connection and retry.');
    error.kind = 'network';
    throw error;
  }
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const detailValue = data?.detail;
    const detail = typeof detailValue === 'string' ? detailValue
      : typeof detailValue?.message === 'string' ? detailValue.message
        : response.status === 503 ? 'The learning service is temporarily unavailable. Your plan details are still here; retry in a moment.'
          : `Learning roadmap request failed (${response.status}).`;
    const error = new Error(detail);
    error.kind = response.status === 401 || response.status === 403 ? 'auth'
      : response.status === 422 ? 'profile' : 'http';
    error.status = response.status;
    throw error;
  }
  return data;
}

export function loadPersonalizedRoadmap(options = {}) {
  return roadmapRequest('', options);
}

export function loadRoadmapProgress(options = {}) {
  return roadmapRequest('/progress', options);
}

export function searchRoadmapOptions(kind, query = '', options = {}) {
  if (!['skill', 'role'].includes(kind)) throw new TypeError('kind must be skill or role.');
  const params = new URLSearchParams({ kind, query: String(query || '') });
  return roadmapRequest(`/options?${params.toString()}`, options);
}

export function previewLearningPlan(config, options = {}) {
  return roadmapRequest('/preview', { ...options, method: 'POST', body: config });
}

export function updateLearningPlanDraft(draftId, edits, options = {}) {
  if (!draftId) throw new TypeError('draftId is required.');
  return roadmapRequest(`/drafts/${encodeURIComponent(draftId)}`, { ...options, method: 'PATCH', body: edits });
}

export function approveLearningPlan(draftId, options = {}) {
  if (!draftId) throw new TypeError('draftId is required.');
  return roadmapRequest(`/drafts/${encodeURIComponent(draftId)}/approve`, { ...options, method: 'POST' });
}

export function discardLearningPlanDraft(draftId, options = {}) {
  if (!draftId) throw new TypeError('draftId is required.');
  return roadmapRequest(`/drafts/${encodeURIComponent(draftId)}`, { ...options, method: 'DELETE' });
}

export function updateRoadmapMilestone(milestoneId, status, options = {}) {
  if (!milestoneId) throw new TypeError('milestoneId is required.');
  if (!['not_started', 'in_progress', 'completed'].includes(status)) throw new TypeError('Invalid milestone status.');
  return roadmapRequest(`/milestones/${encodeURIComponent(milestoneId)}`, {
    ...options, method: 'PATCH', body: { status }
  });
}

export function deletePersonalizedRoadmap(options = {}) {
  return roadmapRequest('', { ...options, method: 'DELETE' });
}

