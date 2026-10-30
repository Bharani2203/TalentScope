/**
 * Firebase Client Configuration & Emulator Guard.
 *
 * In production builds (NODE_ENV !== 'development'), strictly connects to the live
 * Google Firebase backend using production API credentials.
 * Connects to local emulators ONLY when running in development mode on localhost.
 */

import { initializeApp, getApps, getApp } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js';
import { getAuth, connectAuthEmulator } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';
import { getFirestore, connectFirestoreEmulator } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js';

// Safe environment shim across browser and build bundlers
if (typeof process === 'undefined') {
  const isLocalhost = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location?.hostname);
  globalThis.process = { env: { NODE_ENV: isLocalhost ? 'development' : 'production' } };
}

export const firebaseConfig = window.TALENTSCOPE_FIREBASE_CONFIG || {
  apiKey: 'AIzaSyD5h3VUZkFevzyFfh9DO6TBK8nfTkCoQqA',
  authDomain: 'skill-demand-forecasting.firebaseapp.com',
  projectId: 'skill-demand-forecasting',
  messagingSenderId: '83023493920',
  appId: '1:83023493920:web:f9f0fe3a01b891fa46b545'
};

const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// STRICT GUARD: Connect emulators only during local development
if (process.env.NODE_ENV === 'development') {
  const isLocalhost = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location?.hostname);
  const useEmulator = isLocalhost && new URLSearchParams(window.location?.search || '').get('firebaseEmulator') === '1';

  if (useEmulator) {
    if (typeof connectAuthEmulator === 'function') {
      connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
    }
    if (typeof connectFirestoreEmulator === 'function') {
      connectFirestoreEmulator(db, '127.0.0.1', 8080);
    }
    // Reserved for cloud functions emulator if enabled
    if (typeof connectFunctionsEmulator === 'function') {
      connectFunctionsEmulator(auth, '127.0.0.1', 5001);
    }
  }
}

export { app, auth, db };
export default app;

