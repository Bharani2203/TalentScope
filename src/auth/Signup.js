// ============================================================================
// TALENTSCOPE.AI — SIGN UP COMPONENT
// Progressive Disclosure Flow:
// Step 1: Create Account (Email, Password, Confirm)
// Step 1.5: Firebase email verification
// Step 2: Role Selection (Individual, Employee [Connected/Independent], Company)
// Direct transition to Onboarding
// ============================================================================

import {
  auth,
  createUserWithEmailAndPassword,
  getGoogleConflictMethods,
  googleProvider,
  GoogleAuthProvider,
  linkPendingGoogleCredential,
  rememberGoogleAccountConflict,
  reload,
  sendEmailVerification,
  signInWithPopup
} from './firebase-client.js';
import {
  clearOnboardingDraft,
  saveOnboardingDraft,
  setSignupFlowPending,
  syncCurrentFirebaseUser
} from './auth-state.js';
import { profileSyncErrorMessage } from './auth-api.js';
import { authTraceNow, logAuthTrace, recordAuthEvent, setAuthDiagnosticState } from './auth-trace.js';
import { ensureAuthDiagnosticsPanel } from './auth-diagnostics-panel.js';

let signupState = {
  step: 1, // 1: credentials, 1.5: email-verify, 2: role-select
  email: '',
  userType: 'individual', // 'individual' | 'employee' | 'company'
  employeeType: 'company-connected', // 'company-connected' | 'independent'
  companyName: 'TechCorp Global',
  authStartedAt: null
};

export function renderSignupPage(container) {
  ensureAuthDiagnosticsPanel();
  const root = container || document.getElementById('mainContent') || document.getElementById('appShell') || document.body;
  renderCurrentSignupStep(root);
}

function renderCurrentSignupStep(root) {
  root.innerHTML = `
    <div class="ts-auth-viewport">
      <!-- LEFT VISUAL AREA -->
      <section class="ts-auth-visual" aria-label="TalentScope Vision">
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
              <i data-lucide="compass"></i>
              Future-Ready Workforce Platform
            </span>
            <h1>Intelligence designed around your actual trajectory.</h1>
            <p>Whether you're developing high-demand skills as an individual, advancing within your organization, or planning enterprise workforce capabilities.</p>
          </div>

          <!-- Feature Highlights Stack -->
          <div class="ts-auth-signals-stack">
            <div class="ts-auth-signal-card">
              <div class="ts-auth-signal-left">
                <div class="ts-auth-signal-icon is-purple">
                  <i data-lucide="layers-3"></i>
                </div>
                <div class="ts-auth-signal-text">
                  <strong>Personalized Skill Graphs</strong>
                  <small>Illustrative competency mapping preview; current job data is not connected.</small>
                </div>
              </div>
              <span class="ts-auth-signal-badge is-positive">Active</span>
            </div>

            <div class="ts-auth-signal-card">
              <div class="ts-auth-signal-left">
                <div class="ts-auth-signal-icon is-blue">
                  <i data-lucide="building-2"></i>
                </div>
                <div class="ts-auth-signal-text">
                  <strong>Connected Workforce Ecosystem</strong>
                  <small>Bridges personal career growth directly with company capability planning</small>
                </div>
              </div>
              <span class="ts-auth-signal-badge is-purple">Demo</span>
            </div>
          </div>
        </div>

        <div class="ts-auth-visual-footer">
          <i data-lucide="lock"></i>
          <span>Secure, role-tailored intelligence profile generation</span>
        </div>
      </section>

      <!-- RIGHT FORM AREA -->
      <section class="ts-auth-form-area" aria-label="Sign up for TalentScope">
        <div class="ts-auth-card ${signupState.step === 2 ? 'ts-usertype-container' : ''}">
          ${getStepContentHtml()}
        </div>
      </section>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  bindStepEvents(root);
}

function getStepContentHtml() {
  if (signupState.step === 1) {
    // Step 1: Account Credentials
    return `
      <header class="ts-auth-header">
        <h2>Create your account</h2>
        <p>Let's get you set up for a more personalized experience.</p>
      </header>

      <div id="authAlertArea"></div>

      <button type="button" class="ts-auth-btn-google" id="googleSignupBtn">
        <svg viewBox="0 0 24 24" width="18" height="18">
          <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
          <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.24v3.15C3.26 21.36 7.33 24 12 24z"/>
          <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.24C.45 8.15 0 9.92 0 12s.45 3.85 1.24 5.42l4.04-3.15z"/>
          <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.24 6.58l4.04 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
        </svg>
        <span>Continue with Google</span>
      </button>

      <div class="ts-auth-divider">OR</div>

      <form class="ts-auth-form" id="signupForm" novalidate>
        <div class="ts-auth-field">
          <label for="signupEmail">Work or personal email</label>
          <div class="ts-auth-input-wrap">
            <i data-lucide="mail" class="prefix-icon"></i>
            <input
              type="email"
              id="signupEmail"
              class="ts-auth-input"
              placeholder="name@example.com"
              value="${signupState.email}"
              required
            />
          </div>
        </div>

        <div class="ts-auth-field">
          <label for="signupPassword">Password</label>
          <div class="ts-auth-input-wrap">
            <i data-lucide="lock" class="prefix-icon"></i>
            <input
              type="password"
              id="signupPassword"
              class="ts-auth-input"
              placeholder="At least 8 characters"
              required
            />
            <button type="button" class="ts-auth-toggle-pwd" id="togglePwdBtn" aria-label="Show password">
              <i data-lucide="eye" id="togglePwdIcon"></i>
            </button>
          </div>
        </div>

        <div class="ts-auth-field">
          <label for="signupConfirmPassword">Confirm password</label>
          <div class="ts-auth-input-wrap">
            <i data-lucide="shield-check" class="prefix-icon"></i>
            <input
              type="password"
              id="signupConfirmPassword"
              class="ts-auth-input"
              placeholder="Re-enter your password"
              required
            />
          </div>
        </div>

        <button type="submit" class="ts-auth-btn-primary" id="step1SubmitBtn">
          <span>Continue</span>
          <i data-lucide="arrow-right"></i>
        </button>
      </form>

      <div class="ts-auth-footer-prompt">
        Already have an account?
        <a href="#/login">Sign in</a>
      </div>
    `;
  }

  if (signupState.step === 1.5) {
    // Step 1.5: Email Verification
    return `
      <header class="ts-auth-header">
        <div style="width: 48px; height: 48px; border-radius: 14px; background: #F3EEFF; color: #874FFF; display: flex; align-items: center; justify-content: center; margin-bottom: 16px;">
          <i data-lucide="mail-check" style="width: 24px; height: 24px;"></i>
        </div>
        <h2>Verify your email</h2>
        <p>Firebase email verification is required for <strong>${signupState.email || 'your email'}</strong>. Check your inbox, then return here to continue.</p>
      </header>

      <div id="authAlertArea"></div>

      <form class="ts-auth-form" id="verifyForm">
        <div class="ts-auth-field">
          <span>Open the verification link in your inbox, then return here and continue.</span>
        </div>

        <button type="submit" class="ts-auth-btn-primary" id="verifySubmitBtn">
          <span>I've verified my email</span>
          <i data-lucide="check"></i>
        </button>

        <button type="button" class="ts-auth-btn-google" id="resendVerificationBtn" style="margin-top: 8px;">
          <i data-lucide="rotate-cw"></i>
          <span>Resend verification email</span>
        </button>
      </form>
    `;
  }

  // Step 2: "How will you use the platform?"
  return `
    <header class="ts-auth-header">
      <h2>How will you use the platform?</h2>
      <p>Choose the experience tailored to your workforce and career goals.</p>
    </header>

    <div id="authAlertArea"></div>

    <div class="ts-usertype-grid" role="radiogroup" aria-label="Select user type">
      <!-- 1. INDIVIDUAL -->
      <article
        class="ts-usertype-card ${signupState.userType === 'individual' ? 'is-selected' : ''}"
        data-type="individual"
        role="radio"
        aria-checked="${signupState.userType === 'individual'}"
        tabindex="0"
      >
        <span class="ts-usertype-check" aria-hidden="true">
          <i data-lucide="check"></i>
        </span>
        <div class="ts-usertype-icon is-individual">
          <i data-lucide="user-round" style="width: 28px; height: 28px;"></i>
        </div>
        <h3 class="ts-usertype-title">Individual</h3>
        <p class="ts-usertype-desc">Build skills, map market opportunities, and prepare for your future career.</p>
        <span class="ts-usertype-arrow">Select Individual <i data-lucide="arrow-right"></i></span>
      </article>

      <!-- 2. EMPLOYEE -->
      <article
        class="ts-usertype-card ${signupState.userType === 'employee' ? 'is-selected' : ''}"
        data-type="employee"
        role="radio"
        aria-checked="${signupState.userType === 'employee'}"
        tabindex="0"
      >
        <span class="ts-usertype-check" aria-hidden="true">
          <i data-lucide="check"></i>
        </span>
        <div class="ts-usertype-icon is-employee">
          <i data-lucide="briefcase" style="width: 28px; height: 28px;"></i>
        </div>
        <h3 class="ts-usertype-title">Employee</h3>
        <p class="ts-usertype-desc">Grow your skills, explore internal mobility, and advance your career at or beyond your company.</p>
        <span class="ts-usertype-arrow">Select Employee <i data-lucide="arrow-right"></i></span>
      </article>

      <!-- 3. COMPANY -->
      <article
        class="ts-usertype-card ${signupState.userType === 'company' ? 'is-selected' : ''}"
        data-type="company"
        role="radio"
        aria-checked="${signupState.userType === 'company'}"
        tabindex="0"
      >
        <span class="ts-usertype-check" aria-hidden="true">
          <i data-lucide="check"></i>
        </span>
        <div class="ts-usertype-icon is-company">
          <i data-lucide="building-2" style="width: 28px; height: 28px;"></i>
        </div>
        <h3 class="ts-usertype-title">Company Admin</h3>
        <p class="ts-usertype-desc">Build, plan, reskill, and forecast the workforce capabilities your enterprise needs next.</p>
        <span class="ts-usertype-arrow">Select Company <i data-lucide="arrow-right"></i></span>
      </article>
    </div>

    <!-- Conditional Employee Connection Sub-Step -->
    ${signupState.userType === 'employee' ? `
      <div class="ts-emp-connection-box" id="empConnectionBox">
        <strong style="display: block; font-size: 15px; color: #1E172B; margin-bottom: 4px;">
          Are you currently connected to a company?
        </strong>
        <p style="font-size: 13px; color: #6C6078; margin: 0 0 12px;">
          Choose whether to link your profile to an employer or advance independently.
        </p>

        <div class="ts-emp-connection-options">
          <button
            type="button"
            class="ts-emp-connection-btn ${signupState.employeeType === 'company-connected' ? 'is-active' : ''}"
            id="btnConnectedEmployee"
          >
            <strong>Yes, I work at a company</strong>
            <small>I want to understand and improve my career within my organization.</small>
          </button>

          <button
            type="button"
            class="ts-emp-connection-btn ${signupState.employeeType === 'independent' ? 'is-active' : ''}"
            id="btnIndependentEmployee"
          >
            <strong>Not yet</strong>
            <small>I want to build and manage my career independently.</small>
          </button>
        </div>

        ${signupState.employeeType === 'company-connected' ? `
          <div style="margin-top: 18px; padding-top: 16px; border-top: 1px solid #E4DAEC;">
            <label style="display: block; font-size: 13px; font-weight: 700; color: #2A1F3B; margin-bottom: 6px;">
              Which company do you work for?
            </label>
            <div class="ts-auth-input-wrap">
              <i data-lucide="building" class="prefix-icon"></i>
              <input
                type="text"
                id="employeeCompanyInput"
                class="ts-auth-input"
                placeholder="Search or enter company name (e.g. TechCorp Global)"
                value="${signupState.companyName}"
              />
            </div>
            <div style="margin-top: 10px; display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #15803D; background: #F0FDF4; padding: 8px 12px; border-radius: 8px;">
              <i data-lucide="check-circle" style="width: 16px; height: 16px;"></i>
              <span>Company workspace detected: <strong>TechCorp Global</strong></span>
            </div>
          </div>
        ` : ''}
      </div>
    ` : ''}

    <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 32px; gap: 16px;">
      <button type="button" class="ts-auth-btn-google" id="btnBackToCreds" style="width: auto; padding: 0 20px;">
        <i data-lucide="arrow-left"></i>
        <span>Back</span>
      </button>

      <button type="button" class="ts-auth-btn-primary" id="btnFinalSignupContinue" style="flex: 1; max-width: 320px; margin: 0;">
        <span>Continue to Onboarding</span>
        <i data-lucide="arrow-right"></i>
      </button>
    </div>
  `;
}

function bindStepEvents(root) {
  // STEP 1 Events
  if (signupState.step === 1) {
    const form = document.getElementById('signupForm');
    const emailInput = document.getElementById('signupEmail');
    const pwdInput = document.getElementById('signupPassword');
    const confirmPwdInput = document.getElementById('signupConfirmPassword');
    const toggleBtn = document.getElementById('togglePwdBtn');
    const toggleIcon = document.getElementById('togglePwdIcon');
    const googleBtn = document.getElementById('googleSignupBtn');

    if (toggleBtn && pwdInput) {
      toggleBtn.addEventListener('click', () => {
        const isPwd = pwdInput.getAttribute('type') === 'password';
        pwdInput.setAttribute('type', isPwd ? 'text' : 'password');
        toggleIcon.setAttribute('data-lucide', isPwd ? 'eye-off' : 'eye');
        if (window.lucide) window.lucide.createIcons();
      });
    }

    if (googleBtn) {
      googleBtn.addEventListener('click', async () => {
        setSignupFlowPending(true);
        const originalGoogleHtml = googleBtn.innerHTML;
        googleBtn.disabled = true;
        googleBtn.innerHTML = '<span>Connecting with Google...</span>';
        clearAlert();
        const loginStarted = authTraceNow();
        signupState.authStartedAt = loginStarted;
        const signInStarted = authTraceNow();
        let firebaseSignInSucceeded = false;
        try {
          recordAuthEvent('LOGIN_STARTED', { result: 'google_signup' });
          recordAuthEvent('GOOGLE_SIGN_IN_STARTED');
          const credential = await signInWithPopup(auth, googleProvider);
          firebaseSignInSucceeded = true;
          recordAuthEvent('GOOGLE_SIGN_IN_SUCCESS', { duration_ms: authTraceNow() - signInStarted });
          logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'success' });
          let firebaseUser = credential.user;
          firebaseUser = await linkPendingGoogleCredential(firebaseUser);
          await syncCurrentFirebaseUser(firebaseUser);
          logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: 'success' });
          recordAuthEvent('AUTH_FLOW_COMPLETED', { result: 'google_signup' });
          signupState.email = firebaseUser.email || '';
          signupState.step = 2;
          renderCurrentSignupStep(root);
        } catch (error) {
          setSignupFlowPending(false);
          if (!firebaseSignInSucceeded) recordAuthEvent('GOOGLE_SIGN_IN_ERROR', { duration_ms: authTraceNow() - signInStarted, category: error?.code || 'GOOGLE_SIGN_IN_FAILED', error_name: error?.name });
          recordAuthEvent('AUTH_FLOW_FAILED', { category: error?.code || error?.kind || 'GOOGLE_SIGN_IN_FAILED' });
          if (error?.code) logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - signInStarted, result: 'failed', error_code: error.code });
          else if (error?.kind) logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - loginStarted, result: error.kind });
          if (error?.code === 'auth/popup-closed-by-user') {
            showAlert('Google sign-up was cancelled.', 'info');
          } else if (error?.code === 'auth/account-exists-with-different-credential') {
            rememberGoogleAccountConflict(error);
            const methods = await getGoogleConflictMethods(error);
            showAlert(accountConflictMessage(methods), 'error');
          } else {
            showAlert(authErrorMessage(error), 'error');
          }
        } finally {
          googleBtn.disabled = false;
          googleBtn.innerHTML = originalGoogleHtml;
          if (window.lucide) window.lucide.createIcons();
        }
      });
    }

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAlert();

        const email = emailInput.value.trim();
        const pwd = pwdInput.value;
        const confirmPwd = confirmPwdInput.value;

        if (!email || !email.includes('@')) {
          showAlert('Please enter a valid email address.', 'error');
          emailInput.focus();
          return;
        }

        if (!pwd || pwd.length < 8) {
          showAlert('Password must contain at least 8 characters.', 'error');
          pwdInput.focus();
          return;
        }

        if (pwd !== confirmPwd) {
          showAlert('Passwords do not match. Please re-check.', 'error');
          confirmPwdInput.focus();
          return;
        }

        signupState.email = email;
        setSignupFlowPending(true);
        signupState.authStartedAt = authTraceNow();
        const accountStarted = authTraceNow();
        const submitButton = document.getElementById('step1SubmitBtn');
        submitButton.disabled = true;
        let firebaseUser;
        try {
          recordAuthEvent('EMAIL_SIGNUP_STARTED');
          const credential = await createUserWithEmailAndPassword(auth, email, pwd);
          firebaseUser = credential.user;
          recordAuthEvent('EMAIL_SIGNUP_SUCCESS', { duration_ms: authTraceNow() - accountStarted });
          setAuthDiagnosticState({ firebase_user: true, email_verified: Boolean(firebaseUser.emailVerified), profile_sync: 'NOT_STARTED' });
          logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - accountStarted, result: 'success' });
          signupState.email = firebaseUser.email || email;
          signupState.step = 2;
          renderCurrentSignupStep(root);
        } catch (error) {
          recordAuthEvent('EMAIL_SIGNUP_ERROR', { duration_ms: authTraceNow() - accountStarted, category: error?.code || 'SIGNUP_FAILED', error_name: error?.name });
          recordAuthEvent('AUTH_FLOW_FAILED', { category: error?.code || 'SIGNUP_FAILED' });
          logAuthTrace('firebase_sign_in', { duration_ms: authTraceNow() - accountStarted, result: 'failed', error_code: error?.code || 'signup_failed' });
          setSignupFlowPending(false);
          submitButton.disabled = false;
          if (error?.code === 'auth/email-already-in-use') {
            showEmailAlreadyInUseAlert();
          } else {
            showAlert(authErrorMessage(error), 'error');
          }
        }
      });
    }
  }

  // STEP 1.5 Verification Events
  if (signupState.step === 1.5) {
    const verifyForm = document.getElementById('verifyForm');
    const resendBtn = document.getElementById('resendVerificationBtn');

    if (resendBtn) {
      resendBtn.addEventListener('click', async () => {
        try {
          if (!auth.currentUser) throw new Error('Sign-up session expired. Please create your account again.');
          await sendEmailVerification(auth.currentUser);
          showAlert('Firebase sent another verification link.', 'success');
        } catch (error) {
          showAlert(authErrorMessage(error), 'error');
        }
      });
    }

    if (verifyForm) {
      verifyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const verificationStarted = authTraceNow();
        const firebaseUser = auth.currentUser;
        if (!firebaseUser) {
          showAlert('Your sign-up session expired. Please create your account again.', 'error');
          return;
        }
        try {
          await reload(firebaseUser);
          const refreshedUser = auth.currentUser || firebaseUser;
          recordAuthEvent('VERIFICATION_REFRESHED', { result: refreshedUser.emailVerified ? 'verified' : 'unverified' });
          setAuthDiagnosticState({ email_verified: Boolean(refreshedUser.emailVerified) });
          if (!refreshedUser.emailVerified) {
            recordAuthEvent('VERIFICATION_REQUIRED', { result: 'still_unverified' });
            logAuthTrace('verification_return_to_profile_ready', { duration_ms: authTraceNow() - verificationStarted, result: 'still_unverified' });
            showAlert('Open the Firebase verification link before continuing.', 'error');
            return;
          }
          await syncCurrentFirebaseUser(refreshedUser);
          recordAuthEvent('AUTH_FLOW_COMPLETED', { result: 'email_signup_verified' });
          logAuthTrace('verification_return_to_profile_ready', { duration_ms: authTraceNow() - verificationStarted, result: 'success' });
          showAlert('Email verified successfully!', 'success');
          signupState.step = 2;
          renderCurrentSignupStep(root);
        } catch (error) {
          recordAuthEvent('AUTH_FLOW_FAILED', { category: error?.code || error?.kind || 'VERIFICATION_OR_PROFILE_SYNC_FAILED' });
          if (error?.kind) logAuthTrace('verification_return_to_profile_ready', { duration_ms: authTraceNow() - verificationStarted, result: error.kind });
          showAlert(authErrorMessage(error), 'error');
        }
      });
    }
  }

  // STEP 2 Role Selection Events
  if (signupState.step === 2) {
    document.querySelectorAll('.ts-usertype-card').forEach(card => {
      card.addEventListener('click', () => {
        const type = card.getAttribute('data-type');
        if (signupState.userType !== type) {
          clearOnboardingDraft();
        }
        signupState.userType = type;
        renderCurrentSignupStep(root);
      });

      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });

    const btnConnected = document.getElementById('btnConnectedEmployee');
    const btnIndependent = document.getElementById('btnIndependentEmployee');
    const companyInput = document.getElementById('employeeCompanyInput');

    if (btnConnected) {
      btnConnected.addEventListener('click', () => {
        signupState.employeeType = 'company-connected';
        renderCurrentSignupStep(root);
      });
    }

    if (btnIndependent) {
      btnIndependent.addEventListener('click', () => {
        signupState.employeeType = 'independent';
        renderCurrentSignupStep(root);
      });
    }

    if (companyInput) {
      companyInput.addEventListener('input', (e) => {
        signupState.companyName = e.target.value.trim();
      });
    }

    const btnBack = document.getElementById('btnBackToCreds');
    if (btnBack) {
      btnBack.addEventListener('click', () => {
        signupState.step = 1;
        renderCurrentSignupStep(root);
      });
    }

    const btnContinue = document.getElementById('btnFinalSignupContinue');
    if (btnContinue) {
      btnContinue.addEventListener('click', async () => {
        if (!auth.currentUser) {
          showAlert('Your Firebase sign-up session expired. Please sign in again.', 'error');
          return;
        }
        btnContinue.disabled = true;
        try {
          if (typeof auth.currentUser?.getIdToken === 'function') {
            await auth.currentUser.getIdToken(true);
          }
          const employee = signupState.userType === 'employee';
          await syncCurrentFirebaseUser(auth.currentUser, {
            user_type: signupState.userType,
            employee_type: employee ? signupState.employeeType : null,
            company_name: employee && signupState.employeeType === 'company-connected'
              ? signupState.companyName
              : null
          });
          if (signupState.authStartedAt !== null) {
            logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - signupState.authStartedAt, result: 'success' });
          }
          setSignupFlowPending(false);
          clearOnboardingDraft();
          saveOnboardingDraft({
            userType: signupState.userType,
            employeeType: signupState.employeeType,
            companyName: signupState.companyName,
            stepIndex: 0,
            answers: {},
            completedSteps: [],
            pendingSteps: []
          });
          const routeStarted = authTraceNow();
          window.location.hash = '#/onboarding';
          recordAuthEvent('ONBOARDING_REQUIRED', { onboarding: 'REQUIRED', route: '#/onboarding' });
          setAuthDiagnosticState({ onboarding: 'REQUIRED' });
          recordAuthEvent('ROUTE_TRANSITION', { duration_ms: authTraceNow() - routeStarted, route: '#/onboarding' });
          logAuthTrace('route_transition', { duration_ms: authTraceNow() - routeStarted, result: 'onboarding' });
        } catch (error) {
          if (error?.kind && signupState.authStartedAt !== null) {
            logAuthTrace('login_to_profile_ready', { duration_ms: authTraceNow() - signupState.authStartedAt, result: error.kind });
          }
          showAlert(authErrorMessage(error), 'error');
          addStep3ProfileRetryButton();
        } finally {
          btnContinue.disabled = false;
        }
      });
    }
  }

  function addStep3ProfileRetryButton() {
    const alertArea = document.getElementById('authAlertArea');
    if (!auth.currentUser || !alertArea) return;
    const retryBtn = document.createElement('button');
    retryBtn.type = 'button';
    retryBtn.className = 'ts-auth-btn-google';
    retryBtn.style.marginTop = '8px';
    retryBtn.textContent = 'Retry profile synchronization';
    retryBtn.addEventListener('click', async () => {
      retryBtn.disabled = true;
      retryBtn.textContent = 'Retrying synchronization...';
      try {
        if (typeof auth.currentUser?.getIdToken === 'function') {
          await auth.currentUser.getIdToken(true);
        }
        const employee = signupState.userType === 'employee';
        await syncCurrentFirebaseUser(auth.currentUser, {
          user_type: signupState.userType,
          employee_type: employee ? signupState.employeeType : null,
          company_name: employee && signupState.employeeType === 'company-connected'
            ? signupState.companyName
            : null
        });
        setSignupFlowPending(false);
        clearOnboardingDraft();
        saveOnboardingDraft({
          userType: signupState.userType,
          employeeType: signupState.employeeType,
          companyName: signupState.companyName,
          stepIndex: 0,
          answers: {},
          completedSteps: [],
          pendingSteps: []
        });
        window.location.hash = '#/onboarding';
      } catch (err) {
        showAlert(authErrorMessage(err), 'error');
        addStep3ProfileRetryButton();
      }
    });
    alertArea.appendChild(retryBtn);
  }

  function showAlert(msg, type = 'error') {
    const alertArea = document.getElementById('authAlertArea');
    if (!alertArea) return;
    const iconName = type === 'error' ? 'alert-circle' : (type === 'info' ? 'info' : 'check-circle-2');
    alertArea.innerHTML = `
      <div class="ts-auth-alert is-${type}" role="alert">
        <i data-lucide="${iconName}"></i>
        <span>${msg}</span>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
  }

  function showEmailAlreadyInUseAlert() {
    const alertArea = document.getElementById('authAlertArea');
    if (!alertArea) return;
    alertArea.innerHTML = `
      <div class="ts-auth-alert is-error" role="alert" style="display:flex; flex-direction:column; gap:10px; align-items:flex-start;">
        <div style="display:flex; align-items:center; gap:8px;">
          <i data-lucide="alert-circle"></i>
          <span>An account already exists for this email address. Please sign in or recover your account instead of repeating registration.</span>
        </div>
        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:4px;">
          <a href="#/login" class="ts-auth-btn-primary" style="display:inline-flex; align-items:center; justify-content:center; text-decoration:none; padding:8px 16px; font-size:13px; width:auto;">
            <span>Sign In to Existing Account</span>
            <i data-lucide="arrow-right" style="margin-left:6px;"></i>
          </a>
          <a href="#/login" style="font-size:13px; color:var(--ts-accent, #6366f1); text-decoration:underline;">
            Recover Account
          </a>
        </div>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
  }

  function clearAlert() {
    const alertArea = document.getElementById('authAlertArea');
    if (alertArea) alertArea.innerHTML = '';
  }
}

export function authErrorMessage(error) {
  if (error?.kind) {
    return profileSyncErrorMessage(error);
  }
  if (error?.message && error.code === undefined) return error.message;
  switch (error?.code) {
    case 'auth/email-already-in-use':
      return 'An account already exists for this email. Sign in instead.';
    case 'auth/weak-password':
      return 'Choose a stronger password and try again.';
    case 'auth/invalid-email':
      return 'Enter a valid email address.';
    case 'auth/too-many-requests':
      return 'Too many attempts. Wait a while, then try again.';
    case 'auth/network-request-failed':
      return 'Could not reach Firebase Authentication. Check your connection.';
    case 'auth/unauthorized-domain':
      return 'This website domain is not authorized in Firebase Authentication.';
    case 'auth/popup-closed-by-user':
      return 'Google sign-up was canceled.';
    case 'auth/popup-blocked':
      return 'Your browser blocked the Google sign-in popup. Allow popups and try again.';
    case 'auth/account-exists-with-different-credential':
      return 'This email already uses another sign-in method. Sign in with it on the Login page to connect Google.';
    case 'auth/credential-already-in-use':
    case 'auth/provider-already-linked':
      return 'This Google account is already connected to another Firebase user. Sign in to that account to continue.';
    default:
      return 'Firebase sign-up could not be completed. Please try again.';
  }
}

function accountConflictMessage(methods) {
  const hasPassword = methods.includes('password');
  return hasPassword
    ? 'This email already belongs to an account. Sign in with this email and password on the Login page; Google will then be connected to that same account.'
    : 'This email already belongs to an account. Sign in with its existing method on the Login page; Google will then be connected to that same account.';
}
