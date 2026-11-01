import { API_BASE_URL } from '../config/api.js';
import {
  authTraceNow,
  AUTH_TRACE_ENABLED,
  createDiagnosticRequestId,
  diagnosticRequestSignal,
  logAuthTrace,
  recordAuthEvent,
  setAuthDiagnosticState
} from './auth-trace.js';

export class ProfileSyncError extends Error {
  constructor(kind, message, status = null) {
    super(message);
    this.name = 'ProfileSyncError';
    this.kind = kind;
    this.status = status;
  }
}

export function profileSyncErrorMessage(error) {
  if (!(error instanceof ProfileSyncError) && error?.name !== 'ProfileSyncError') {
    return 'Your account is signed in, but the profile could not be loaded. Retry profile synchronization.';
  }
  switch (error.kind) {
    case 'AUTHENTICATION_FAILED':
      return 'The backend rejected the Firebase authentication token. Sign in again.';
    case 'AUTHENTICATION_SERVICE_UNAVAILABLE':
      return 'The backend could not verify Firebase authentication. Please retry shortly.';
    case 'FIREBASE_AUTH_NETWORK_ERROR':
      return 'Firebase Authentication could not be reached, so the profile request was not sent.';
    case 'RATE_LIMITED':
      return 'The profile service rate limited this request. Please wait briefly and retry.';
    case 'EMAIL_NOT_VERIFIED':
      return 'Please verify your email before continuing.';
    case 'ACCOUNT_CONFLICT':
      return 'This account needs attention. Sign in with its existing method to continue.';
    case 'VALIDATION_ERROR':
      return 'Some account details were rejected. Review them and try again.';
    case 'NETWORK_ERROR':
      return 'Unable to connect to the local backend. Confirm it is running at the configured address and check browser network or CORS errors.';
    case 'CONNECTION_REFUSED':
      return 'The local backend refused the connection. Confirm that the existing backend process is listening on the configured address.';
    case 'TIMEOUT':
      return 'Profile synchronization timed out after 10 seconds. The login has not finished; you can retry.';
    case 'ENDPOINT_NOT_FOUND':
      return 'The backend is running, but the profile synchronization endpoint was not found.';
    case 'FIRESTORE_UNAVAILABLE':
      return 'The backend is running, but Firestore is unavailable for profile synchronization.';
    case 'BACKEND_UPSTREAM_ERROR':
      return 'The backend received an upstream error while synchronizing your profile.';
    case 'BACKEND_INTERNAL_ERROR':
      return 'The backend returned an unexpected error while synchronizing your profile.';
    case 'BACKEND_SERVICE_UNAVAILABLE':
      return 'The backend profile service is temporarily unavailable.';
    case 'MALFORMED_RESPONSE':
      return 'The backend returned an invalid profile response. Your application login has not finished.';
    default:
      return `Profile synchronization failed${error.status ? ` (HTTP ${error.status})` : ''}. Please retry.`;
  }
}

function responseErrorCode(payload) {
  const code = payload?.detail?.error_code;
  return typeof code === 'string' ? code : null;
}

export async function syncFirebaseUser(firebaseUser, profile = {}) {
  const totalStarted = authTraceNow();
  if (!firebaseUser) {
    recordAuthEvent('FIREBASE_USER_MISSING');
    throw new ProfileSyncError('AUTHENTICATION_FAILED', 'A Firebase user is required.');
  }
  const providerIds = Array.isArray(firebaseUser.providerData)
    ? firebaseUser.providerData.map(provider => provider?.providerId).filter(Boolean)
    : [];
  recordAuthEvent('FIREBASE_USER_AVAILABLE', {
    firebase_user: true,
    uid_present: Boolean(firebaseUser.uid),
    email_verified: Boolean(firebaseUser.emailVerified),
    provider_ids: providerIds
  });
  recordAuthEvent('PROFILE_SYNC_STARTED', { api_base_url: API_BASE_URL, result: 'started' });
  setAuthDiagnosticState({
    firebase_user: true,
    email_verified: Boolean(firebaseUser.emailVerified),
    provider_ids: providerIds,
    profile_sync: 'RUNNING'
  });

  let idToken;
  const tokenStarted = authTraceNow();
  recordAuthEvent('ID_TOKEN_STARTED');
  try {
    idToken = await firebaseUser.getIdToken(true);
    recordAuthEvent('ID_TOKEN_SUCCESS', { elapsed_ms: authTraceNow() - tokenStarted });
    setAuthDiagnosticState({ id_token: 'AVAILABLE' });
    logAuthTrace('firebase_id_token', {
      token_ms: authTraceNow() - tokenStarted,
      result: 'success'
    });
  } catch (error) {
    recordAuthEvent('ID_TOKEN_ERROR', {
      elapsed_ms: authTraceNow() - tokenStarted,
      category: error?.code || 'TOKEN_ERROR',
      error_name: error?.name
    });
    setAuthDiagnosticState({ id_token: 'FAILED', profile_sync: 'FAILED' });
    const kind = error?.code === 'auth/network-request-failed'
      ? 'FIREBASE_AUTH_NETWORK_ERROR'
      : 'AUTHENTICATION_FAILED';
    logAuthTrace('firebase_id_token', {
      token_ms: authTraceNow() - tokenStarted,
      result: 'failed',
      error_code: error?.code || 'token_error'
    });
    logAuthTrace('profile_sync_total', { total_ms: authTraceNow() - totalStarted, result: kind });
    throw new ProfileSyncError(kind, 'Firebase could not provide a current ID token.');
  }

  let response;
  const fetchStarted = authTraceNow();
  const requestId = createDiagnosticRequestId();
  const requestUrl = `${API_BASE_URL}/api/v1/auth/sync`;
  recordAuthEvent('PROFILE_SYNC_REQUEST_CREATED', {
    request_id: requestId,
    url: requestUrl,
    method: 'POST'
  });
  try {
    recordAuthEvent('PROFILE_SYNC_REQUEST_SENT', {
      request_id: requestId,
      url: requestUrl,
      method: 'POST'
    });
    response = await fetch(requestUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${idToken}`,
        'Content-Type': 'application/json',
        ...(AUTH_TRACE_ENABLED ? { 'X-Auth-Diagnostic-Id': requestId } : {})
      },
      body: JSON.stringify(profile),
      signal: diagnosticRequestSignal()
    });
  } catch (error) {
    const elapsedMs = authTraceNow() - fetchStarted;
    const networkCode = error?.cause?.code || error?.code;
    const kind = error?.name === 'TimeoutError' || error?.name === 'AbortError'
      ? 'TIMEOUT'
      : ['ECONNREFUSED', 'ERR_CONNECTION_REFUSED'].includes(networkCode)
        ? 'CONNECTION_REFUSED'
        : 'NETWORK_ERROR';
    const eventName = kind === 'TIMEOUT' ? 'PROFILE_SYNC_TIMEOUT' : 'PROFILE_SYNC_NETWORK_ERROR';
    recordAuthEvent(eventName, {
      request_id: requestId,
      url: requestUrl,
      method: 'POST',
      elapsed_ms: elapsedMs,
      category: kind,
      error_name: error?.name,
      error_message: error?.message
    });
    setAuthDiagnosticState({ profile_sync: 'FAILED', profile: 'FAILED' });
    logAuthTrace('profile_sync_fetch', {
      request_id: requestId,
      fetch_ms: elapsedMs,
      result: kind,
      error_code: kind === 'TIMEOUT' ? 'timeout_10s' : networkCode || 'fetch_rejected',
      error_name: error?.name,
      error_message: error?.message,
      url: requestUrl,
      method: 'POST'
    });
    logAuthTrace('profile_sync_total', { total_ms: authTraceNow() - totalStarted, result: kind });
    throw new ProfileSyncError(kind, 'The authenticated profile request did not complete.');
  } finally {
    idToken = null;
  }

  const fetchMs = authTraceNow() - fetchStarted;
  const responseDetails = {
    request_id: requestId,
    url: requestUrl,
    method: 'POST',
    status: response.status,
    elapsed_ms: fetchMs,
    content_type: response.headers.get('content-type') || undefined,
    body_bytes: Number(response.headers.get('content-length')) || undefined,
    backend_request_id: response.headers.get('x-auth-diagnostic-id') || 'not_returned'
  };
  recordAuthEvent('PROFILE_SYNC_RESPONSE_RECEIVED', responseDetails);
  if (!response.ok) {
    let errorPayload = null;
    const parseStarted = authTraceNow();
    try { errorPayload = await response.json(); } catch {}
    const errorCode = responseErrorCode(errorPayload);
    recordAuthEvent('PROFILE_SYNC_HTTP_ERROR', {
      ...responseDetails,
      category: errorCode || `HTTP_${response.status}`
    });
    setAuthDiagnosticState({ profile_sync: 'FAILED', profile: 'FAILED' });
    let kind;
    if (response.status === 401) kind = 'AUTHENTICATION_FAILED';
    else if (response.status === 403) kind = 'EMAIL_NOT_VERIFIED';
    else if (response.status === 404) kind = 'ENDPOINT_NOT_FOUND';
    else if (response.status === 409) kind = 'ACCOUNT_CONFLICT';
    else if (response.status === 422) kind = 'VALIDATION_ERROR';
    else if (response.status === 429) kind = 'RATE_LIMITED';
    else if (response.status === 500) kind = 'BACKEND_INTERNAL_ERROR';
    else if (response.status === 502) kind = 'BACKEND_UPSTREAM_ERROR';
    else if (response.status === 503 && errorCode === 'auth_verification_unavailable') kind = 'AUTHENTICATION_SERVICE_UNAVAILABLE';
    else if (response.status === 503 && errorCode === 'firestore_unavailable') kind = 'FIRESTORE_UNAVAILABLE';
    else if (response.status === 503) kind = 'BACKEND_SERVICE_UNAVAILABLE';
    else kind = 'BACKEND_HTTP_ERROR';
    logAuthTrace('profile_sync_fetch', {
      fetch_ms: fetchMs,
      response_parse_ms: authTraceNow() - parseStarted,
      status: response.status,
      result: kind
    });
    logAuthTrace('profile_sync_total', { total_ms: authTraceNow() - totalStarted, status: response.status, result: kind });
    throw new ProfileSyncError(kind, 'The profile service rejected the request.', response.status);
  }

  let result;
  const parseStarted = authTraceNow();
  try {
    result = await response.json();
  } catch {
    recordAuthEvent('PROFILE_SYNC_PARSE_ERROR', { ...responseDetails, category: 'INVALID_JSON' });
    setAuthDiagnosticState({ profile_sync: 'FAILED', profile: 'FAILED' });
    logAuthTrace('profile_sync_fetch', {
      fetch_ms: fetchMs,
      response_parse_ms: authTraceNow() - parseStarted,
      status: response.status,
      result: 'malformed_response'
    });
    logAuthTrace('profile_sync_total', {
      token_ms: fetchStarted - tokenStarted,
      fetch_ms: fetchMs,
      response_parse_ms: authTraceNow() - parseStarted,
      total_ms: authTraceNow() - totalStarted,
      status: response.status,
      result: 'malformed_response'
    });
    throw new ProfileSyncError('MALFORMED_RESPONSE', 'The profile service returned an invalid response.', response.status);
  }
  const parseMs = authTraceNow() - parseStarted;
  if (!result?.authenticated || result.user?.uid !== firebaseUser.uid) {
    recordAuthEvent('PROFILE_SYNC_PARSE_ERROR', { ...responseDetails, category: 'IDENTITY_MISMATCH' });
    setAuthDiagnosticState({ profile_sync: 'FAILED', profile: 'FAILED' });
    logAuthTrace('profile_sync_fetch', {
      fetch_ms: fetchMs,
      response_parse_ms: parseMs,
      status: response.status,
      result: 'identity_mismatch'
    });
    logAuthTrace('profile_sync_total', {
      token_ms: fetchStarted - tokenStarted,
      fetch_ms: fetchMs,
      response_parse_ms: parseMs,
      total_ms: authTraceNow() - totalStarted,
      status: response.status,
      result: 'identity_mismatch'
    });
    throw new ProfileSyncError('MALFORMED_RESPONSE', 'The profile service returned an unexpected identity.', response.status);
  }
  const profileStatus = response.headers.get('x-auth-profile-status') || 'FOUND';
  recordAuthEvent('PROFILE_SYNC_SUCCESS', { ...responseDetails, result: 'success', profile_status: profileStatus });
  setAuthDiagnosticState({ profile_sync: 'SUCCESS', profile: profileStatus.toUpperCase() });
  logAuthTrace('profile_sync_fetch', {
    fetch_ms: fetchMs,
    response_parse_ms: parseMs,
    status: response.status,
    result: 'success'
  });
  logAuthTrace('profile_sync_total', {
    token_ms: fetchStarted - tokenStarted,
    fetch_ms: fetchMs,
    response_parse_ms: parseMs,
    total_ms: authTraceNow() - totalStarted,
    status: response.status,
    result: 'profile_ready'
  });
  return result.user;
}
