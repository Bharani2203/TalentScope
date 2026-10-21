const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);
export const LOCAL_FIREBASE_PROJECT_ID = 'demo-talentscope-local';

export function resolveFirebaseEmulatorConfig(location) {
  const params = new URLSearchParams(location.search || '');
  if (params.get('firebaseEmulator') !== '1') return null;

  if (!LOCAL_HOSTS.has(String(location.hostname || '').toLowerCase()) || location.protocol !== 'http:') {
    throw new Error('Firebase Emulator mode is only available on an HTTP localhost page.');
  }

  return {
    projectId: LOCAL_FIREBASE_PROJECT_ID,
    authUrl: 'http://127.0.0.1:9099',
    readinessUrl: `http://127.0.0.1:9099/emulator/v1/projects/${LOCAL_FIREBASE_PROJECT_ID}/config`
  };
}

export async function verifyFirebaseEmulator(config, fetchImpl = globalThis.fetch) {
  let response;
  try {
    response = await fetchImpl(config.readinessUrl, { method: 'GET', cache: 'no-store' });
  } catch {
    throw new Error('Firebase Auth Emulator is unavailable; production authentication was not selected.');
  }
  if (!response?.ok) {
    throw new Error('Firebase Auth Emulator readiness check failed; production authentication was not selected.');
  }
}
