import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

async function fetchLearningResources(path, options = {}) {
  const token = await getAuthIdToken(options.token);
  if (!token) throw new Error('Sign in to load learning resources.');
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || 'GET',
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, ...options.headers },
      ...(options.body ? { body: options.body } : {}),
      signal: options.signal
    });
  } catch {
    throw new Error('Could not reach the learning resource service.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('Your sign-in session could not be verified. Please sign in again.');
  }
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) {
    const error = new Error(typeof data?.detail === 'string' ? data.detail : `Learning resource query failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export function loadLearningResources({ skillId, topicId, resourceType, limit = 20 } = {}, options = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (skillId) query.set('skill_id', String(skillId));
  if (topicId) query.set('topic_id', String(topicId));
  if (resourceType) query.set('resource_type', String(resourceType));
  return fetchLearningResources(`/api/v1/learning/resources?${query.toString()}`, options);
}

export function loadLearningResourcesForSkill(skillId, options = {}) {
  if (!skillId) throw new TypeError('skillId is required.');
  const query = new URLSearchParams({ limit: String(options.limit ?? 20) });
  return fetchLearningResources(
    `/api/v1/learning/resources/by-skill/${encodeURIComponent(skillId)}?${query.toString()}`,
    options
  );
}

export function loadLearningVideos({ skillId, topicId, limit = 8 } = {}, options = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (skillId) query.set('skill_id', String(skillId));
  if (topicId) query.set('topic_id', String(topicId));
  return fetchLearningResources(`/api/v1/learning/videos?${query.toString()}`, options);
}

export function loadLearningActivityProgress(options = {}) {
  return fetchLearningResources('/api/v1/learning/progress', options);
}

export function updateLearningActivityProgress(activityId, status, options = {}) {
  if (!activityId) throw new TypeError('activityId is required.');
  if (!['not_started', 'in_progress', 'completed'].includes(status)) throw new TypeError('Invalid learning activity status.');
  return fetchLearningResources(`/api/v1/learning/progress/${encodeURIComponent(activityId)}`, {
    ...options,
    method: 'PUT',
    body: JSON.stringify({ status }),
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
}

export function loadLearningCurriculum(options = {}) {
  return fetchLearningResources('/api/v1/learning/curriculum', options);
}

export function recordLearningChapterEvent(chapterId, event, options = {}) {
  if (!chapterId) throw new TypeError('chapterId is required.');
  return fetchLearningResources(`/api/v1/learning/chapters/${encodeURIComponent(chapterId)}/events`, {
    ...options,
    method: 'POST',
    body: JSON.stringify(event),
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
}

export function runCompilerCode({ language, sourceCode, code, stdin }, options = {}) {
  const actualCode = sourceCode ?? code;
  if (!language || !actualCode) throw new TypeError('language and sourceCode are required.');
  return fetchLearningResources('/api/v1/learning/compiler/run', {
    ...options,
    method: 'POST',
    body: JSON.stringify({ language, source_code: actualCode, stdin: stdin || null }),
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
}

export function evaluateCodingAssessment({ questionId, question_id, language, sourceCode, code, attemptId, attempt_id }, options = {}) {
  const actualQId = questionId ?? question_id;
  const actualCode = sourceCode ?? code;
  const actualAttemptId = attemptId ?? attempt_id ?? null;
  if (!actualQId || !actualCode) throw new TypeError('questionId and sourceCode are required.');
  const payload = {
    question_id: actualQId,
    language: language || 'python',
    source_code: actualCode,
  };
  if (actualAttemptId) {
    payload.attempt_id = actualAttemptId;
  }
  return fetchLearningResources('/api/v1/learning/compiler/evaluate', {
    ...options,
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json', ...options.headers }
  });
}

