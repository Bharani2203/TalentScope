// ============================================================================
// TALENTSCOPE.AI — LOGIN COMPONENT
// Screen: Left Storytelling Visual + Right Form Area
// Direct portal routing based on user type & company connection
// ============================================================================

import { auth, googleProvider, GoogleAuthProvider, getGoogleConflictMethods, linkPendingGoogleCredential, rememberGoogleAccountConflict, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut } from './firebase-client.js';
import { determineUserRedirect, getProfileSyncErrorKind, syncCurrentFirebaseUser } from './auth-state.js';
import { profileSyncErrorMessage } from './auth-api.js';
import { authTraceNow, logAuthTrace, recordAuthEvent, setAuthDiagnosticState } from './auth-trace.js';
import { ensureAuthDiagnosticsPanel } from './auth-diagnostics-panel.js';

export function renderLoginPage(container) {
  ensureAuthDiagnosticsPanel();
  const root = container || document.getElementById('mainContent') || document.getElementById('appShell') || document.body;

  root.innerHTML = `
    <div class="ts-auth-viewport">
      <!-- LEFT / MAIN VISUAL AREA -->
      <section class="ts-auth-visual" aria-label="TalentScope Overview">
        <div class="ts-auth-visual-top">
          <a class="ts-auth-brand" href="#/individual/home" aria-label="TalentScope.ai">
            <span class="ts-auth-brand-mark">
              <img src="assets/logo.png" alt="TalentScope Logo">
            </span>
            <span class="ts-auth-brand-name">TalentScope<span>.ai</span></span>
          </a>
        </div>

        <div class="ts-auth-visual-center">
          <div class="ts-auth-visual-headline">
            <span class="ts-auth-visual-kicker">
              <i data-lucide="sparkles"></i>
              Strategic Workforce Intelligence
            </span>
            <h1>Forecast skills. Shape your career and workforce.</h1>
            <p>Explore skill and career examples. Current market intelligence is not connected on this preview.</p>
          </div>

          <!-- Illustrative prototype signals -->
          <div class="ts-auth-signals-stack">
            <p role="note">Illustrative sample data — these values are not current provider or workforce measurements.</p>
            <div class="ts-auth-signal-card">
              <div class="ts-auth-signal-left">
                <div class="ts-auth-signal-icon is-purple">
                  <i data-lucide="brain"></i>
                </div>
                <div class="ts-auth-signal-text">
                  <strong>AI Infrastructure & GPU Systems</strong>
                  <small>Hiring acceleration +28.4% across 2,400+ tech employers</small>
                </div>
              </div>
              <span class="ts-auth-signal-badge is-positive">+28.4%</span>
            </div>

            <div class="ts-auth-signal-card">
              <div class="ts-auth-signal-left">
                <div class="ts-auth-signal-icon is-blue">
                  <i data-lucide="git-pull-request"></i>
                </div>
                <div class="ts-auth-signal-text">
                  <strong>Internal Workforce Mobility</strong>
                  <small>86% talent match rate across enterprise departments</small>
                </div>
              </div>
              <span class="ts-auth-signal-badge is-purple">86% Fit</span>
            </div>
          </div>
        </div>

        <div class="ts-auth-visual-footer">
          <i data-lucide="shield-check"></i>
          <span>Enterprise-grade encryption & calibrated workforce analytics</span>
        </div>
      </section>

      <!-- RIGHT / FORM AREA -->
      <section class="ts-auth-form-area" aria-label="Sign in to your account">
        <div class="ts-auth-card">
          <header class="ts-auth-header">
            <h2>Welcome back</h2>
            <p>Continue where you left off.</p>
          </header>

          <div id="authAlertArea"></div>

          <form class="ts-auth-form" id="loginForm" novalidate>
            <div class="ts-auth-field">
              <label for="loginEmail">Email address</label>
              <div class="ts-auth-input-wrap">
                <i data-lucide="mail" class="prefix-icon"></i>
                <input
                  type="email"
                  id="loginEmail"
                  class="ts-auth-input"
                  placeholder="name@example.com"
                  autocomplete="email"
                  required
                />
              </div>
            </div>

            <div class="ts-auth-field">
              <label for="loginPassword">
                <span>Password</span>
                <a href="#/auth/login" id="forgotPasswordLink">Forgot password?</a>
              </label>
              <div class="ts-auth-input-wrap">
                <i data-lucide="lock" class="prefix-icon"></i>
                <input
                  type="password"
                  id="loginPassword"
                  class="ts-auth-input"
                  placeholder="••••••••"
                  autocomplete="current-password"
                  required
                />
                <button type="button" class="ts-auth-toggle-pwd" id="togglePasswordBtn" aria-label="Show password">
                  <i data-lucide="eye" id="togglePwdIcon"></i>
                </button>
              </div>
            </div>

            <button type="submit" class="ts-auth-btn-primary" id="loginSubmitBtn">
              <span>Sign In</span>
              <i data-lucide="arrow-right"></i>
            </button>
          </form>

          <div class="ts-auth-divider" id="loginDivider">OR</div>

          <button type="button" class="ts-auth-btn-google" id="googleLoginBtn">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
              <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.24v3.15C3.26 21.36 7.33 24 12 24z"/>
              <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.24C.45 8.15 0 9.92 0 12s.45 3.85 1.24 5.42l4.04-3.15z"/>
              <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.24 6.58l4.04 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
            </svg>
            <span>Continue with Google</span>
          </button>

          <div class="ts-auth-footer-prompt" id="loginFooterPrompt">
            Don't have an account?
            <a href="#/signup" id="linkToSignup">Create account</a>
          </div>
        </div>
      </section>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  bindLoginEvents();
}

function bindLoginEvents() {
  const form = document.getElementById('loginForm');
  const emailInput = document.getElementById('loginEmail');
  const passwordInput = document.getElementById('loginPassword');
  const alertArea = document.getElementById('authAlertArea');
  const submitBtn = document.getElementById('loginSubmitBtn');
  const togglePwdBtn = document.getElementById('togglePasswordBtn');
  const togglePwdIcon = document.getElementById('togglePwdIcon');
  const googleBtn = document.getElementById('googleLoginBtn');
  const forgotLink = document.getElementById('forgotPasswordLink');

  // Toggle Password Visibility
  if (togglePwdBtn && passwordInput) {
    togglePwdBtn.addEventListener('click', () => {
      const isPwd = passwordInput.getAttribute('type') === 'password';
      passwordInput.setAttribute('type', isPwd ? 'text' : 'password');
      togglePwdIcon.setAttribute('data-lucide', isPwd ? 'eye-off' : 'eye');
      if (window.lucide) window.lucide.createIcons();
    });
  }

  // Firebase password-reset email
  if (forgotLink) {
    forgotLink.addEventListener('click', async (e) => {
      e.preventDefault();
      const email = emailInput.value.trim();
      if (!email) {
        showAlert('Enter your email address first.', 'error');
        emailInput.focus();
        return;
      }
      try {
        await sendPasswordResetEmail(auth, email);
        showAlert('If this account exists, Firebase has sent a password reset email.', 'success');
      } catch (error) {
        showAlert(authErrorMessage(error), 'error');
      }
    });
  }

  // Firebase Google sign-in
  if (googleBtn) {
    googleBtn.addEventListener('click', async () => {
      const originalGoogleHtml = googleBtn.innerHTML;
      googleBtn.disabled = true;
      googleBtn.innerHTML = '<span>Connecting with Google...</span>';
      clearAlert();
      const loginStarted = authTraceNow();
      const signInStarted = authTraceNow();
      let firebaseSignInSucceeded = false;
      try {
        recordAuthEvent('LOGIN_STARTED', { result: 'google' });
        recordAuthEvent('GOOGLE_SIGN_IN_STARTED');
        const credential = await signInWithPopup(auth, googleProvider);
        firebaseSignInSucceeded = true;
        recordAuthEvent('GOOGLE_SIGN_IN_SUCCESS', { duration_ms: authTraceNow() - signInStarted });
        logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'success' });
        let firebaseUser = credential.user;
        firebaseUser = await linkPendingGoogleCredential(firebaseUser);
        const user = await syncCurrentFirebaseUser(firebaseUser);
        logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: 'success' });
        showAlert('Signed in successfully. Redirecting...', 'success');
        routeAuthenticatedUser(user);
        recordAuthEvent('AUTH_FLOW_COMPLETED', { result: 'google' });
      } catch (error) {
        if (!firebaseSignInSucceeded) {
          recordAuthEvent('GOOGLE_SIGN_IN_ERROR', {
            duration_ms: authTraceNow() - signInStarted,
            category: error?.code || 'GOOGLE_SIGN_IN_FAILED',
            error_name: error?.name
          });
        }
        recordAuthEvent('AUTH_FLOW_FAILED', { category: error?.code || error?.kind || 'GOOGLE_SIGN_IN_FAILED' });
        if (error?.code) logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'failed', error_code: error.code });
        else if (error?.kind) logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: error.kind });
        if (error?.code === 'auth/popup-closed-by-user') {
          showAlert('Google sign-in was cancelled.', 'info');
        } else if (error?.code === 'auth/account-exists-with-different-credential') {
          rememberGoogleAccountConflict(error);
          const methods = await getGoogleConflictMethods(error);
          showAlert(accountConflictMessage(methods), 'error');
        } else {
          showAuthError(error);
        }
      } finally {
        googleBtn.disabled = false;
        googleBtn.innerHTML = originalGoogleHtml;
        if (window.lucide) window.lucide.createIcons();
      }
    });
  }

  // Form Submit Handler
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearAlert();

      const email = emailInput.value.trim();
      const password = passwordInput.value;

      if (!email) {
        showAlert('Please enter your email.', 'error');
        emailInput.focus();
        return;
      }

      if (!password) {
        showAlert('Please enter your password.', 'error');
        passwordInput.focus();
        return;
      }

      if (password.length < 8) {
        showAlert('Password must contain at least 8 characters.', 'error');
        passwordInput.focus();
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span>Signing in...</span>';
      const loginStarted = authTraceNow();
      const signInStarted = authTraceNow();
      let firebaseSignInSucceeded = false;
      try {
        recordAuthEvent('LOGIN_STARTED', { result: 'email_password' });
        recordAuthEvent('EMAIL_SIGN_IN_STARTED');
        const credential = await signInWithEmailAndPassword(auth, email, password);
        firebaseSignInSucceeded = true;
        recordAuthEvent('EMAIL_SIGN_IN_SUCCESS', { duration_ms: authTraceNow() - signInStarted });
        logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'success' });
        let firebaseUser = credential.user;
        firebaseUser = await linkPendingGoogleCredential(firebaseUser);
        const user = await syncCurrentFirebaseUser(firebaseUser);
        logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: 'success' });
        showAlert('Signed in successfully. Redirecting...', 'success');
        routeAuthenticatedUser(user);
        recordAuthEvent('AUTH_FLOW_COMPLETED', { result: 'email_password' });
      } catch (error) {
        if (!firebaseSignInSucceeded) {
          recordAuthEvent('EMAIL_SIGN_IN_ERROR', {
            duration_ms: authTraceNow() - signInStarted,
            category: error?.code || 'EMAIL_SIGN_IN_FAILED',
            error_name: error?.name
          });
        }
        recordAuthEvent('AUTH_FLOW_FAILED', { category: error?.code || error?.kind || 'EMAIL_SIGN_IN_FAILED' });
        if (error?.code) logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'failed', error_code: error.code });
        else if (error?.kind) logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: error.kind });
        showAuthError(error);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Sign In</span><i data-lucide="arrow-right"></i>';
        if (window.lucide) window.lucide.createIcons();
      }
    });
  }

  function showAlert(msg, type = 'error') {
    if (!alertArea) return;
    const alert = document.createElement('div');
    alert.className = `ts-auth-alert is-${type}`;
    alert.setAttribute('role', 'alert');
    const icon = document.createElement('i');
    icon.dataset.lucide = type === 'error' ? 'alert-circle' : 'check-circle-2';
    const text = document.createElement('span');
    text.textContent = msg;
    alert.append(icon, text);
    alertArea.replaceChildren(alert);
    if (window.lucide) window.lucide.createIcons();
  }

  function clearAlert() {
    if (alertArea) alertArea.innerHTML = '';
  }

  function showAuthError(error) {
    if (!error?.kind) {
      showAlert(authErrorMessage(error), 'error');
      return;
    }
    showAlert(profileSyncErrorMessage(error), 'error');
    addProfileRetryButton();
  }

  function addProfileRetryButton() {
    if (!auth.currentUser || !alertArea) return;
    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'ts-auth-btn-google';
    retryButton.textContent = 'Retry profile connection';
    retryButton.addEventListener('click', async () => {
      retryButton.disabled = true;
      try {
        const user = await syncCurrentFirebaseUser(auth.currentUser);
        window.location.hash = determineUserRedirect(user);
      } catch (error) {
        showAuthError(error);
      }
    });
    alertArea.appendChild(retryButton);
  }

  function routeAuthenticatedUser(user) {
    const startedAt = authTraceNow();
    const destination = determineUserRedirect(user);
    const onboardingRequired = !user.onboarding_completed;
    recordAuthEvent(onboardingRequired ? 'ONBOARDING_REQUIRED' : 'PORTAL_READY', {
      onboarding: onboardingRequired ? 'REQUIRED' : 'COMPLETE',
      route: destination
    });
    setAuthDiagnosticState({ onboarding: onboardingRequired ? 'REQUIRED' : 'COMPLETE' });
    window.location.hash = destination;
    recordAuthEvent('ROUTE_TRANSITION', { duration_ms: authTraceNow() - startedAt, route: destination });
    logAuthTrace('route_transition', { duration_ms: authTraceNow() - startedAt, result: 'profile_route_selected' });
  }

  const priorSyncError = getProfileSyncErrorKind();
  if (priorSyncError && auth.currentUser) {
    showAuthError({ kind: priorSyncError, name: 'ProfileSyncError' });
  }
}

function authErrorMessage(error) {
  if (error?.kind) {
    return profileSyncErrorMessage(error);
  }
  if (error?.message && error.code === undefined) return error.message;
  switch (error?.code) {
    case 'auth/invalid-credential':
    case 'auth/user-not-found':
    case 'auth/wrong-password':
      return 'Email or password is incorrect.';
    case 'auth/too-many-requests':
      return 'Too many attempts. Wait a while, then try again.';
    case 'auth/network-request-failed':
      return 'Could not reach Firebase Authentication. Check your connection.';
    case 'auth/unauthorized-domain':
      return 'This website domain is not authorized in Firebase Authentication.';
    case 'auth/popup-closed-by-user':
      return 'Google sign-in was canceled.';
    case 'auth/popup-blocked':
      return 'Your browser blocked the Google sign-in popup. Allow popups and try again.';
    case 'auth/email-already-in-use':
      return 'An account already exists for this email. Sign in with its existing method.';
    case 'auth/account-exists-with-different-credential':
      return 'This email already uses another sign-in method. Sign in with that method to connect Google.';
    case 'auth/credential-already-in-use':
    case 'auth/provider-already-linked':
      return 'This Google account is already connected to another Firebase user. Sign in to that account to continue.';
    case 'auth/email-not-verified':
      return 'Please verify your email before continuing.';
    default:
      return 'Sign-in failed. Check your details and try again.';
  }
}

function accountConflictMessage(methods) {
  const hasPassword = methods.includes('password');
  const providerHint = hasPassword
    ? ' Sign in with this email and password; Google will then be connected to that same account.'
    : ' Sign in with the method you used for this account; Google will then be connected to that same account.';
  return `This email already belongs to an account.${providerHint}`;
}
