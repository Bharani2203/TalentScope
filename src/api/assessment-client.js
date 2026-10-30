import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

async function requestAssessment(path, { method = 'GET', body, token, signal } = {}) {
  const idToken = await getAuthIdToken(token);
  if (!idToken) {
    const error = new Error('Sign in to use skill assessments.');
    error.kind = 'auth';
    error.status = 401;
    throw error;
  }
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/learning/assessments${path}`, {
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
    const error = new Error('Could not reach the assessment service. Check your connection and retry.');
    error.kind = 'network';
    throw error;
  }
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : `Assessment request failed (${response.status}).`;
    const error = new Error(detail);
    error.kind = response.status === 401 || response.status === 403 ? 'auth'
      : response.status === 409 ? 'unavailable' : 'http';
    error.status = response.status;
    throw error;
  }
  return data;
}

export function loadAvailableAssessments(options = {}) {
  const query = new URLSearchParams();
  if (options.skillId) query.set('skill_id', options.skillId);
  return requestAssessment(`${query.size ? `?${query}` : ''}`, options);
}

export function startSkillAssessment(skillId, { questionCount = 10, ...options } = {}) {
  if (!skillId) throw new TypeError('skillId is required.');
  const query = new URLSearchParams({ question_count: String(questionCount) });
  return requestAssessment(`/${encodeURIComponent(skillId)}/attempts?${query}`, { ...options, method: 'POST' });
}

export function submitSkillAssessment(attemptId, answers, options = {}) {
  if (!attemptId) throw new TypeError('attemptId is required.');
  return requestAssessment(`/attempts/${encodeURIComponent(attemptId)}/submit`, {
    ...options, method: 'POST', body: { answers: Object.fromEntries(
      Object.entries(answers || {}).map(([questionId, answer]) => [questionId, { answer }])
    ) }
  });
}

export function loadAssessmentHistory(options = {}) {
  const limit = Math.min(50, Math.max(1, Number(options.limit) || 20));
  return requestAssessment(`/attempts?limit=${limit}`, options);
}

export function checkAssessmentRestriction(options = {}) {
  return requestAssessment('/security/restriction-status', options);
}

export function recordAssessmentStrike(attemptId, eventType, options = {}) {
  return requestAssessment('/security/strikes', {
    ...options,
    method: 'POST',
    body: { attempt_id: attemptId, event_type: eventType }
  });
}

