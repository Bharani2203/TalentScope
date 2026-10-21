import { getApp, getApps, initializeApp } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js';
import {
  createUserWithEmailAndPassword,
  connectAuthEmulator,
  getAuth,
  GoogleAuthProvider,
  fetchSignInMethodsForEmail,
  linkWithCredential,
  onAuthStateChanged,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut
} from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';
import {
  resolveFirebaseEmulatorConfig,
  verifyFirebaseEmulator
} from './firebase-emulator-config.js';

const emulatorConfig = resolveFirebaseEmulatorConfig(window.location);
if (emulatorConfig) await verifyFirebaseEmulator(emulatorConfig);

const firebaseConfig = emulatorConfig ? {
  apiKey: 'local-emulator-only',
  authDomain: `${emulatorConfig.projectId}.firebaseapp.com`,
  projectId: emulatorConfig.projectId,
  messagingSenderId: '000000000000',
  appId: '1:000000000000:web:local-emulator'
} : window.TALENTSCOPE_FIREBASE_CONFIG || {
  apiKey: 'AIzaSyD5h3VUZkFevzyFfh9DO6TBK8nfTkCoQqA',
  authDomain: 'skill-demand-forecasting.firebaseapp.com',
  projectId: 'skill-demand-forecasting',
  messagingSenderId: '83023493920',
  appId: '1:83023493920:web:f9f0fe3a01b891fa46b545'
};

const firebaseApp = getApps().length ? getApp() : initializeApp(firebaseConfig);
if (emulatorConfig && firebaseApp.options.projectId !== emulatorConfig.projectId) {
  throw new Error('Firebase Emulator mode rejected an already initialized non-emulator project.');
}
export const auth = getAuth(firebaseApp);
if (emulatorConfig) {
  connectAuthEmulator(auth, emulatorConfig.authUrl, { disableWarnings: true });
}
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

// Keep an account-conflict credential in memory only. It is consumed after the
// user signs in with the account's existing provider; it is never persisted.
let pendingGoogleCredential = null;

export function rememberGoogleAccountConflict(error) {
  if (error?.code !== 'auth/account-exists-with-different-credential') return false;
  pendingGoogleCredential = GoogleAuthProvider.credentialFromError(error) || null;
  return Boolean(pendingGoogleCredential);
}

export function hasPendingGoogleCredential() {
  return Boolean(pendingGoogleCredential);
}

export async function getGoogleConflictMethods(error) {
  const email = error?.customData?.email;
  if (typeof email !== 'string' || !email) return [];
  try {
    return await fetchSignInMethodsForEmail(auth, email);
  } catch {
    return [];
  }
}

export async function linkPendingGoogleCredential(user) {
  if (!pendingGoogleCredential) return user;
  if (!user) throw new Error('Sign in with the account’s existing method to connect Google.');
  const credential = pendingGoogleCredential;
  const linked = await linkWithCredential(user, credential);
  pendingGoogleCredential = null;
  return linked.user;
}

export {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  fetchSignInMethodsForEmail,
  onAuthStateChanged,
  linkWithCredential,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut
};
