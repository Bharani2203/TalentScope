import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from '../api/core-intelligence-client.js';

export class OnboardingApiError extends Error {
  constructor(kind, message, status = null) {
    super(message);
    this.name = 'OnboardingApiError';
    this.kind = kind;
    this.status = status;
  }
}

async function authenticatedRequest(path, options = {}) {
  let idToken;
  try {
    idToken = await getAuthIdToken();
  } catch {
    throw new OnboardingApiError('AUTHENTICATION_FAILED', 'Your sign-in session could not be verified. Sign in again.', 401);
  }
  if (!idToken) {
    throw new OnboardingApiError('AUTHENTICATION_REQUIRED', 'Your sign-in session expired. Sign in again.', 401);
  }
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
  } catch (err) {
    console.error(`[ONBOARDING_API_NETWORK_ERROR] fetch failed for ${API_BASE_URL}${path}:`, err);
    throw new OnboardingApiError('NETWORK_ERROR', 'Could not reach the onboarding service. Please retry when connected.');
  }

  if (response.status === 401 || response.status === 403) {
    throw new OnboardingApiError('AUTHENTICATION_FAILED', 'Your sign-in session could not be verified. Sign in again.', response.status);
  }
  if (!response.ok) {
    const detail = response.status === 422
      ? 'This answer is not valid. Review it and try again.'
      : response.status === 409
        ? 'Complete the earlier onboarding step before continuing.'
        : 'The onboarding profile could not be loaded or saved. Please retry.';
    throw new OnboardingApiError('REQUEST_FAILED', detail, response.status);
  }
  try {
    return await response.json();
  } catch {
    throw new OnboardingApiError('MALFORMED_RESPONSE', 'The onboarding service returned an invalid response.', response.status);
  }
}

export async function loadIndividualOnboardingProfile() {
  return authenticatedRequest('/api/v1/onboarding/individual/profile');
}

export async function saveIndividualOnboardingStep(stepNumber, answer) {
  return authenticatedRequest(`/api/v1/onboarding/individual/step/${stepNumber}`, {
    method: 'PUT',
    body: JSON.stringify({ answer })
  });
}

export async function loadRoleOnboardingProfile(userType) {
  return authenticatedRequest(`/api/v1/onboarding/${encodeURIComponent(userType)}/profile`);
}

export async function saveRoleOnboardingStep(userType, stepNumber, questionId, answer) {
  return authenticatedRequest(`/api/v1/onboarding/${encodeURIComponent(userType)}/step/${stepNumber}`, {
    method: 'PUT',
    body: JSON.stringify({ question_id: questionId, answer })
  });
}
