import { API_BASE_URL } from '../config/api.js';

const hostname = typeof window === 'undefined' ? '' : window.location.hostname;
export const AUTH_PROFILE_SYNC_TIMEOUT_MS = 10_000;
export const AUTH_TRACE_ENABLED =
  ['localhost', '127.0.0.1'].includes(hostname) && window.TALENTSCOPE_AUTH_DIAGNOSTICS !== false;

const MAX_EVENTS = 300;
let diagnosticCounter = 0;
const events = [];
const state = {
  firebase_user: false,
  email_verified: false,
  provider_ids: [],
  id_token: 'NOT_REQUESTED',
  profile_sync: 'NOT_STARTED',
  profile: 'UNKNOWN',
  onboarding: 'UNKNOWN'
};
const inFlightRequests = new Set();
const SAFE_FIELDS = new Set([
  'duration_ms', 'elapsed_ms', 'token_ms', 'fetch_ms', 'response_parse_ms', 'total_ms',
  'status', 'result', 'category', 'error_code', 'error_name', 'error_message',
  'request_id', 'backend_request_id', 'url', 'method', 'content_type', 'body_bytes', 'origin', 'api_base_url',
  'firebase_user', 'uid_present', 'email_verified', 'provider_ids', 'profile_sync',
  'profile', 'onboarding', 'route', 'profile_status'
]);

export function authTraceNow() {
  return globalThis.performance?.now?.() ?? Date.now();
}

function safeText(value, max = 240) {
  if (typeof value !== 'string') return undefined;
  return value
    .replace(/Bearer\s+\S+/gi, 'Bearer <redacted>')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email-redacted>')
    .replace(/-----BEGIN[^-]+PRIVATE KEY-----[\s\S]*?-----END[^-]+PRIVATE KEY-----/gi, '<private-key-redacted>')
    .replace(/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g, '<token-redacted>')
    .slice(0, max);
}

function safeUrl(value) {
  try {
    const url = new URL(value, window.location.href);
    return `${url.origin}${url.pathname}`;
  } catch {
    return undefined;
  }
}

function safeValue(key, value) {
  if (['duration_ms', 'elapsed_ms', 'token_ms', 'fetch_ms', 'response_parse_ms', 'total_ms', 'status', 'body_bytes'].includes(key)) {
    return typeof value === 'number' && Number.isFinite(value) ? Math.round(value * 100) / 100 : undefined;
  }
  if (['firebase_user', 'uid_present', 'email_verified'].includes(key)) return typeof value === 'boolean' ? value : undefined;
  if (key === 'provider_ids') {
    return Array.isArray(value) ? value.filter(item => typeof item === 'string' && /^[a-z0-9._-]{1,40}$/i.test(item)).slice(0, 8) : undefined;
  }
  if (key === 'url') return safeUrl(value);
  if (key === 'api_base_url') return safeUrl(value);
  if (key === 'origin') {
    try { return new URL(value).origin; } catch { return undefined; }
  }
  if (key === 'method') return ['GET', 'POST', 'PUT', 'OPTIONS'].includes(value) ? value : undefined;
  if (key === 'route') return typeof value === 'string' && /^#\/[a-z0-9/_-]{0,80}$/i.test(value) ? value : undefined;
  if (key === 'content_type') return safeText(value, 100);
  if (key === 'backend_request_id') return safeText(value, 64);
  if (key === 'error_message') return safeText(value);
  if (typeof value === 'string' && /^[a-z0-9_./:-]{1,100}$/i.test(value)) return value;
  return undefined;
}

export function setAuthDiagnosticState(patch) {
  if (!AUTH_TRACE_ENABLED || !patch || typeof patch !== 'object') return;
  for (const key of ['firebase_user', 'email_verified', 'id_token', 'profile_sync', 'profile', 'onboarding']) {
    if (typeof patch[key] === 'boolean' || typeof patch[key] === 'string') state[key] = patch[key];
  }
  if (Array.isArray(patch.provider_ids)) state.provider_ids = safeValue('provider_ids', patch.provider_ids) || [];
  window.dispatchEvent(new CustomEvent('talentscope-auth-diagnostic-update'));
}

export function getAuthDiagnosticSnapshot() {
  return {
    frontend_origin: window.location.origin,
    api_base_url: API_BASE_URL,
    ...state,
    events: events.slice()
  };
}

export function clearAuthDiagnosticEvents() {
  if (!AUTH_TRACE_ENABLED) return;
  events.length = 0;
  inFlightRequests.clear();
  window.dispatchEvent(new CustomEvent('talentscope-auth-diagnostic-clear'));
}

export function recordAuthEvent(event, fields = {}) {
  if (!AUTH_TRACE_ENABLED) return;
  const details = {};
  for (const [key, value] of Object.entries(fields)) {
    if (!SAFE_FIELDS.has(key)) continue;
    const sanitized = safeValue(key, value);
    if (sanitized !== undefined) details[key] = sanitized;
  }
  const entry = {
    timestamp: new Date().toISOString(),
    event: String(event).replace(/[^A-Z0-9_]/gi, '_').toUpperCase().slice(0, 64),
    ...details
  };
  if (entry.event === 'PROFILE_SYNC_REQUEST_SENT' && entry.request_id) {
    if (inFlightRequests.size > 0 && !inFlightRequests.has(entry.request_id)) {
      events.push({ timestamp: entry.timestamp, event: 'DUPLICATE_PROFILE_SYNC', request_id: entry.request_id, result: 'overlapping_request' });
    }
    inFlightRequests.add(entry.request_id);
  }
  if (['PROFILE_SYNC_RESPONSE_RECEIVED', 'PROFILE_SYNC_HTTP_ERROR', 'PROFILE_SYNC_NETWORK_ERROR', 'PROFILE_SYNC_TIMEOUT', 'PROFILE_SYNC_PARSE_ERROR'].includes(entry.event) && entry.request_id) {
    inFlightRequests.delete(entry.request_id);
  }
  events.push(entry);
  if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS);
  console.info('AUTH_DIAGNOSTIC', JSON.stringify(entry));
  window.dispatchEvent(new CustomEvent('talentscope-auth-diagnostic-event', { detail: entry }));
}

export function logAuthTrace(stage, fields = {}) {
  recordAuthEvent(stage, fields);
}

export function logAuthDuration(stage, startedAt, fields = {}) {
  recordAuthEvent(stage, { ...fields, duration_ms: authTraceNow() - startedAt });
}

export function createDiagnosticRequestId() {
  const uuid = globalThis.crypto?.randomUUID?.();
  const suffix = uuid || `${Date.now().toString(36)}_${(++diagnosticCounter).toString(36)}`;
  return `authreq_${suffix.replace(/[^a-z0-9_-]/gi, '').slice(0, 48)}`;
}

export function diagnosticRequestSignal() {
  if (!AUTH_TRACE_ENABLED || typeof globalThis.AbortSignal?.timeout !== 'function') return undefined;
  return globalThis.AbortSignal.timeout(AUTH_PROFILE_SYNC_TIMEOUT_MS);
}
