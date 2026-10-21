export const LOCAL_TEST_API_ORIGIN = 'http://127.0.0.1:8010';

export function resolveApiBaseUrl({ location, configuredApiOrigin = null, globalApiOrigin = null }) {
  const configured = configuredApiOrigin || globalApiOrigin;
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
    if (configured && String(configured).replace(/\/$/, '') !== LOCAL_TEST_API_ORIGIN) {
      throw new Error('Local Firebase Emulator mode rejected a non-isolated API override.');
    }
    return LOCAL_TEST_API_ORIGIN;
  }

  const localFrontendApiOrigin = (() => {
    if (!currentOrigin) return '';
    try {
      const pageUrl = new URL(currentOrigin);
      if (!['localhost', '127.0.0.1'].includes(pageUrl.hostname) || pageUrl.port !== '3000') return '';
      pageUrl.port = '8000';
      return pageUrl.origin;
    } catch {
      return '';
    }
  })();

  return String(configured || localFrontendApiOrigin || currentOrigin).replace(/\/$/, '');
}

const browserLocation = typeof window !== 'undefined' ? window.location : null;
const configuredOrigin = typeof window !== 'undefined' ? window.TALENTSCOPE_API_BASE_URL : null;
const globalConfiguredOrigin = typeof globalThis !== 'undefined'
  ? globalThis.TALENTSCOPE_API_BASE_URL
  : null;

export const API_BASE_URL = resolveApiBaseUrl({
  location: browserLocation,
  configuredApiOrigin: configuredOrigin,
  globalApiOrigin: globalConfiguredOrigin
});
