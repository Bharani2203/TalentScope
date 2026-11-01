export const PRODUCTION_API_ORIGIN = 'https://talentscope-im0q.onrender.com';
export const LOCAL_TEST_API_ORIGIN = 'http://127.0.0.1:8010';
export const LOCAL_DEV_API_ORIGIN = 'http://127.0.0.1:8000';

/**
 * Normalizes an API origin or base URL by stripping trailing slashes and
 * ensuring any accidental trailing /api/v1 is removed so routes that append
 * /api/v1 never produce double /api/v1/api/v1.
 */
export function normalizeApiOrigin(url) {
  if (!url || typeof url !== 'string') return '';
  return url.trim().replace(/\/api\/v1\/?$/i, '').replace(/\/+$/, '');
}

/**
 * Safely reads the configured API base URL from Vite or Node environment variables.
 */
export function readEnvApiOrigin() {
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env) {
      const val = import.meta.env.VITE_API_BASE_URL ||
        import.meta.env.VITE_API_URL ||
        import.meta.env.REACT_APP_API_BASE_URL ||
        import.meta.env.REACT_APP_API_URL;
      if (val) return val;
    }
  } catch {}
  try {
    if (typeof process !== 'undefined' && process.env) {
      const val = process.env.VITE_API_BASE_URL ||
        process.env.VITE_API_URL ||
        process.env.REACT_APP_API_BASE_URL ||
        process.env.REACT_APP_API_URL ||
        process.env.API_BASE_URL;
      if (val) return val;
    }
  } catch {}
  return null;
}

export function resolveApiBaseUrl({ location, configuredApiOrigin = null, globalApiOrigin = null }) {
  const configured = normalizeApiOrigin(configuredApiOrigin || globalApiOrigin);
  const currentOrigin = location && /^https?:\/\//i.test(location.origin || '')
    ? location.origin
    : '';
  const emulatorMode = new URLSearchParams(location?.search || '').get('firebaseEmulator') === '1';

  if (emulatorMode) {
    let parsed;
    try {
      parsed = new URL(currentOrigin);
    } catch {
      throw new Error('Local Firebase Emulator mode requires an HTTP loopback frontend.');
    }
    if (
      parsed.protocol !== 'http:' ||
      !['localhost', '127.0.0.1'].includes(parsed.hostname)
    ) {
      throw new Error('Local Firebase Emulator mode requires an HTTP loopback frontend.');
    }
    if (configured && configured !== LOCAL_TEST_API_ORIGIN) {
      throw new Error('Local Firebase Emulator mode rejected a non-isolated API override.');
    }
    return LOCAL_TEST_API_ORIGIN;
  }

  // If explicitly configured, use it (normalized without trailing /api/v1)
  if (configured) {
    return configured;
  }

  let hostname = '';
  let protocol = 'http:';
  if (location) {
    if (location.hostname) {
      hostname = location.hostname;
      protocol = location.protocol || 'http:';
    } else if (currentOrigin) {
      try {
        const u = new URL(currentOrigin);
        hostname = u.hostname;
        protocol = u.protocol;
      } catch {}
    }
  }

  // Local development: preserve loopback hostname ('localhost' -> port 8000, '127.0.0.1' -> port 8000)
  if (['localhost', '127.0.0.1'].includes(hostname)) {
    return `${protocol}//${hostname}:8000`;
  }

  // Preserve test domains in mock environments
  if (hostname && (hostname.endsWith('.example') || hostname.endsWith('.test'))) {
    return currentOrigin;
  }

  // Production fallback for deployed frontends (e.g. talent-scope-ten.vercel.app, talentscope.ai)
  return PRODUCTION_API_ORIGIN;
}

const browserLocation = typeof window !== 'undefined' ? window.location : null;
const configuredOrigin = (typeof window !== 'undefined' && window.TALENTSCOPE_API_BASE_URL)
  ? window.TALENTSCOPE_API_BASE_URL
  : (typeof globalThis !== 'undefined' && globalThis.TALENTSCOPE_API_BASE_URL)
    ? globalThis.TALENTSCOPE_API_BASE_URL
    : readEnvApiOrigin();

export const API_BASE_URL = resolveApiBaseUrl({
  location: browserLocation,
  configuredApiOrigin: configuredOrigin
});

export const API_V1_BASE_URL = `${API_BASE_URL}/api/v1`;

/**
 * Helper to build an absolute endpoint URL cleanly without double slashes or duplicated /api/v1.
 */
export function resolveApiUrl(path = '') {
  const p = String(path).trim();
  const leading = p.startsWith('/') ? p : `/${p}`;
  if (leading.startsWith('/api/v1/')) {
    return `${API_BASE_URL}${leading}`;
  }
  if (leading.startsWith('/api/')) {
    return `${API_BASE_URL}${leading}`;
  }
  return `${API_BASE_URL}/api/v1${leading}`;
}
