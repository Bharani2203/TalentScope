import { API_BASE_URL } from '../config/api.js';

async function authenticatedRequest(path, options = {}) {
  const isWrite = Boolean(options.method);
  const { auth } = await import('../auth/firebase-client.js');
  const firebaseUser = auth.currentUser;
  if (!firebaseUser) {
    throw new Error(`Your sign-in session expired. Sign in again to ${isWrite ? 'save onboarding' : 'load your profile'}.`);
  }

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
    throw new Error(isWrite
      ? 'Could not reach the onboarding service. Your local draft is preserved; retry when connected.'
      : 'Could not reach the onboarding service to load your saved profile. Retry when connected.');
  }

  if (response.status === 401) {
    const { logoutUser } = await import('../auth/auth-state.js');
    await logoutUser();
    throw new Error('Your sign-in session expired. Sign in again to continue.');
  }
  if (response.status === 403) {
    throw new Error(`Your sign-in session could not be verified. Sign in again to ${isWrite ? 'save onboarding' : 'load your profile'}.`);
  }
  if (!response.ok) {
    const detail = response.status === 422
      ? isWrite ? 'This answer is not valid. Review it and try again.' : 'Your saved profile could not be validated.'
      : response.status === 409
        ? 'Complete the earlier onboarding step before continuing.'
        : isWrite
          ? 'The answer could not be saved. Your local draft is preserved; please retry.'
          : 'Your saved profile could not be loaded. Please retry.';
    throw new Error(detail);
  }
  return response.json();
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
