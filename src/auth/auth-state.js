// ============================================================================
// TALENTSCOPE.AI — AUTHENTICATION & SESSION STATE MANAGEMENT
// Supports: Individual, Employee (Connected / Independent), Company Admin
// Handles: Firebase-backed sessions and local onboarding drafts
// ============================================================================

import { auth, onAuthStateChanged, signOut } from './firebase-client.js';
import { syncFirebaseUser } from './auth-api.js';
import { coalesceProfileSync } from './profile-sync-coordinator.js';
import { authTraceNow, logAuthTrace, recordAuthEvent, setAuthDiagnosticState } from './auth-trace.js';

const STORAGE_KEY_USERS = 'talentscope_users_v2';
const STORAGE_KEY_SESSION = 'talentscope_session_v2';
const STORAGE_KEY_ONBOARDING_DRAFT = 'talentscope_onboarding_draft_v2';
const STORAGE_KEY_LATEST_REPORT = 'talentscope_latest_report_v2';

function removeLegacyPasswords() {
  try {
    const users = JSON.parse(localStorage.getItem(STORAGE_KEY_USERS) || '[]');
    if (Array.isArray(users)) {
      for (const user of users) delete user.password;
      localStorage.setItem(STORAGE_KEY_USERS, JSON.stringify(users));
    }
    const session = JSON.parse(localStorage.getItem(STORAGE_KEY_SESSION) || 'null');
    if (session?.user) {
      delete session.user.password;
      localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(session));
    }
  } catch {}
}
removeLegacyPasswords();

function clientProfile(profile) {
  return {
    ...profile,
    id: profile.uid,
    name: profile.display_name || profile.email || 'TalentScope user',
    userType: profile.user_type || null,
    employeeType: profile.employee_type || null,
    companyName: profile.company_name || null,
    onboardingComplete: profile.onboarding_completed === true
  };
}

let signupFlowPending = false;
let profileSyncErrorKind = null;
const profileSyncs = new Map();

export function getProfileSyncErrorKind() {
  return profileSyncErrorKind;
}

export function setSignupFlowPending(pending) {
  signupFlowPending = Boolean(pending);
}

export async function syncCurrentFirebaseUser(firebaseUser, profile = {}) {
  if (!firebaseUser?.uid) throw new Error('A Firebase user is required to synchronize the profile.');
  const startedAt = authTraceNow();
  const { promise, coalesced } = coalesceProfileSync(profileSyncs, firebaseUser.uid, profile, async () => {
    const synced = await syncFirebaseUser(firebaseUser, profile);
    profileSyncErrorKind = null;
    const user = clientProfile(synced);
    if (user.uid !== firebaseUser.uid) throw new Error('The profile identity did not match the signed-in Firebase user.');
    setCurrentUser(user);
    return user;
  });
  if (coalesced) logAuthTrace('profile_sync_coalesced', { result: 'joined_inflight_request' });
  const user = await promise;
  logAuthTrace('profile_ready', { duration_ms: authTraceNow() - startedAt, result: 'success' });
  return user;
}

export function initializeAuthState() {
  const authStateStartedAt = authTraceNow();
  onAuthStateChanged(auth, async firebaseUser => {
    logAuthTrace('firebase_auth_state', {
      duration_ms: authTraceNow() - authStateStartedAt,
      result: firebaseUser ? 'signed_in' : 'signed_out'
    });
    if (!firebaseUser) {
      recordAuthEvent('AUTH_STATE_CHANGED', { result: 'signed_out', firebase_user: false });
      recordAuthEvent('FIREBASE_USER_MISSING');
      setAuthDiagnosticState({ firebase_user: false, email_verified: false, provider_ids: [], profile_sync: 'NOT_STARTED', profile: 'UNKNOWN', onboarding: 'UNKNOWN' });
      setCurrentUser(null);
      window.dispatchEvent(new Event('talentscope-auth-state-changed'));
      return;
    }
    const providerIds = Array.isArray(firebaseUser.providerData)
      ? firebaseUser.providerData.map(provider => provider?.providerId).filter(Boolean)
      : [];
    recordAuthEvent('AUTH_STATE_CHANGED', { result: 'signed_in', firebase_user: true, uid_present: Boolean(firebaseUser.uid), email_verified: Boolean(firebaseUser.emailVerified), provider_ids: providerIds });
    recordAuthEvent('FIREBASE_USER_AVAILABLE', { firebase_user: true, uid_present: Boolean(firebaseUser.uid), email_verified: Boolean(firebaseUser.emailVerified), provider_ids: providerIds });
    setAuthDiagnosticState({ firebase_user: true, email_verified: Boolean(firebaseUser.emailVerified), provider_ids: providerIds });
    if (signupFlowPending) {
      return;
    }
    const restoreStartedAt = authTraceNow();
    try {
      await syncCurrentFirebaseUser(firebaseUser);
      recordAuthEvent('PROFILE_STATE_READY', { profile: 'FOUND' });
      logAuthTrace('session_restore_to_profile_ready', {
        duration_ms: authTraceNow() - restoreStartedAt,
        result: 'success'
      });
    } catch (error) {
      profileSyncErrorKind = error?.kind || 'PROFILE_SYNC_FAILED';
      logAuthTrace('session_restore_to_profile_ready', {
        duration_ms: authTraceNow() - restoreStartedAt,
        result: error?.kind || 'PROFILE_SYNC_FAILED'
      });
      const existingUser = getCurrentUser();
      if (!existingUser || existingUser.uid !== firebaseUser.uid) {
        setCurrentUser(null);
      }
      setAuthDiagnosticState({ profile_sync: 'FAILED', profile: 'FAILED' });
      window.dispatchEvent(new CustomEvent('talentscope-auth-profile-sync-error', {
        detail: { kind: error?.kind || 'PROFILE_SYNC_FAILED' }
      }));
    }
    window.dispatchEvent(new Event('talentscope-auth-state-changed'));
  });
}

// Standard Pre-Seeded Accounts for Testing & Instant Login
const DEFAULT_SEEDED_USERS = [
  {
    id: 'user_alex',
    email: 'alex@example.com',
    name: 'Alex Mercer',
    userType: 'individual',
    employeeType: null,
    companyId: null,
    companyName: null,
    department: null,
    avatar: 'assets/avatar.png',
    ageGroup: '22–25',
    location: { country: 'India', region: 'Karnataka', city: 'Bangalore' },
    currentStage: 'Student',
    education: 'Computer Science & AI',
    experience: 'Less than 1 year',
    skills: ['Python', 'Machine Learning', 'SQL', 'Git'],
    skillLevels: { 'Python': 'Comfortable', 'Machine Learning': 'Beginner', 'SQL': 'Comfortable', 'Git': 'Comfortable' },
    careerGoals: ['Get my first job', 'Build AI skills'],
    targetRoles: ['AI Engineer', 'Machine Learning Specialist'],
    interests: ['Artificial Intelligence', 'Software Development', 'Data'],
    learningPreferences: ['Hands-on practice', 'Projects'],
    weeklyLearningTime: '5–10 hours',
    workPreference: 'Remote',
    favoriteCompanies: ['Google', 'NVIDIA', 'Microsoft'],
    onboardingComplete: true,
    createdAt: '2026-01-15T09:00:00Z'
  },
  {
    id: 'user_sarah',
    email: 'sarah@techcorp.com',
    name: 'Sarah Jenkins',
    userType: 'employee',
    employeeType: 'company-connected',
    companyId: 'techcorp-1',
    companyName: 'TechCorp Global',
    department: 'Platform Engineering',
    currentRole: 'Software Engineer',
    industry: 'Enterprise Cloud & AI',
    avatar: 'assets/avatar.png',
    location: { country: 'United States', region: 'California', city: 'San Francisco' },
    experience: '3–5 years',
    skills: ['Python', 'Kubernetes', 'Distributed Systems', 'Docker', 'Go'],
    skillLevels: { 'Python': 'Advanced', 'Kubernetes': 'Comfortable', 'Distributed Systems': 'Beginner', 'Docker': 'Advanced', 'Go': 'Comfortable' },
    careerGoals: ['Move to a senior role', 'Improve my technical skills'],
    targetRoles: ['Senior AI Platform Engineer', 'Staff Infrastructure Engineer'],
    desiredSkills: ['CUDA & GPU Optimization', 'NCCL', 'TensorRT'],
    interests: ['AI Infrastructure', 'Cloud Architecture'],
    learningPreferences: ['Hands-on practice', 'Projects'],
    weeklyLearningTime: '2–5 hours',
    internalGrowthGoals: ['Prepare for promotion', 'Understand where my role is going'],
    onboardingComplete: true,
    createdAt: '2026-02-01T10:30:00Z'
  },
  {
    id: 'user_david',
    email: 'david@dev.io',
    name: 'David Chen',
    userType: 'employee',
    employeeType: 'independent',
    companyId: null,
    companyName: null,
    department: null,
    currentRole: 'Full Stack Developer',
    industry: 'Fintech & Web3',
    avatar: 'assets/avatar.png',
    location: { country: 'Germany', region: 'Berlin', city: 'Berlin' },
    experience: '1–2 years',
    skills: ['JavaScript', 'TypeScript', 'React', 'Node.js', 'PostgreSQL'],
    skillLevels: { 'JavaScript': 'Advanced', 'TypeScript': 'Comfortable', 'React': 'Advanced', 'Node.js': 'Comfortable', 'PostgreSQL': 'Comfortable' },
    careerGoals: ['Explore opportunities', 'Improve my skills'],
    targetRoles: ['Senior Full Stack Engineer', 'Backend Architect'],
    desiredSkills: ['Microservices', 'System Design', 'Rust'],
    interests: ['Fintech', 'Software Architecture'],
    learningPreferences: ['Projects', 'Videos'],
    weeklyLearningTime: '5–10 hours',
    internalGrowthGoals: [],
    onboardingComplete: true,
    createdAt: '2026-03-10T14:15:00Z'
  },
  {
    id: 'user_elena',
    email: 'admin@novatech.com',
    name: 'Elena Rostova',
    userType: 'company',
    employeeType: null,
    companyId: 'novatech-global',
    companyName: 'NovaTech Solutions',
    industry: 'Artificial Intelligence & Enterprise Software',
    avatar: 'assets/avatar.png',
    location: { country: 'United States', region: 'Washington', city: 'Seattle' },
    workforceSize: '501–1,000',
    description: 'Enterprise AI infrastructure and intelligent automation platform serving Fortune 500 organizations.',
    businessAreas: ['Technology', 'Engineering', 'Operations', 'Research'],
    criticalSkills: ['Python', 'PyTorch', 'Kubernetes', 'Distributed Computing', 'MLOps'],
    futureSkills: ['Agentic AI', 'CUDA Optimization', 'LLM Fine-tuning', 'Vector Databases'],
    workforceGoals: ['Build future skills', 'Understand workforce gaps', 'Plan future workforce'],
    workforceChallenges: ['Finding the right skills', 'Keeping employee skills current', 'Preparing employees for AI'],
    importantRoles: ['AI Engineer', 'MLOps Architect', 'Cloud Systems Lead'],
    workforceDecisions: ['Workforce planning', 'Upskilling', 'Hiring'],
    platformGoals: ['Understand the market', 'Understand our workforce', 'Find skill gaps'],
    onboardingComplete: true,
    createdAt: '2026-01-20T11:00:00Z'
  }
];

export function getAllUsers() {
  try {
    const users = JSON.parse(localStorage.getItem(STORAGE_KEY_USERS) || '[]');
    return Array.isArray(users) ? users : [];
  } catch {
    return [];
  }
}

export function saveUser(user) {
  const currentUser = getCurrentUser();
  if (!currentUser || (user.uid && user.uid !== currentUser.uid)) return;
  setCurrentUser({ ...currentUser, ...user, uid: currentUser.uid, id: currentUser.uid });
}

export function getCurrentUser() {
  try {
    const session = localStorage.getItem(STORAGE_KEY_SESSION);
    if (!session) return null;
    const parsed = JSON.parse(session);
    return parsed?.authSource === 'firebase' && parsed.user?.uid === parsed.userId
      ? parsed.user
      : null;
  } catch {
    return null;
  }
}

export function setCurrentUser(user) {
  if (!user?.uid) {
    localStorage.removeItem(STORAGE_KEY_SESSION);
    return;
  }
  const {
    password,
    idToken,
    accessToken,
    otp,
    verificationCode,
    ...safeUser
  } = user;
  localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify({
    authSource: 'firebase',
    userId: user.uid,
    user: safeUser,
    timestamp: new Date().toISOString()
  }));
}

export async function logoutUser() {
  try {
    await signOut(auth);
  } finally {
    setCurrentUser(null);
  }
  clearOnboardingDraft();
}

export function determineUserRedirect(user) {
  if (!user) return '#/auth/login';

  // Incomplete onboarding -> return to onboarding
  if (!user.onboardingComplete) {
    return '#/onboarding';
  }

  // Completed onboarding -> redirect to user's assigned portal
  if (user.userType === 'company') {
    return '#/company/home';
  } else if (user.userType === 'employee') {
    return '#/employee/home';
  } else {
    return '#/individual/home';
  }
}

// Onboarding Draft Management
export function getOnboardingDraft(userType) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_ONBOARDING_DRAFT);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (userType && parsed.userType !== userType) return null;
    return parsed;
  } catch (e) {
    return null;
  }
}

export function saveOnboardingDraft(data) {
  try {
    localStorage.setItem(STORAGE_KEY_ONBOARDING_DRAFT, JSON.stringify({
      ...data,
      savedAt: new Date().toISOString()
    }));
  } catch (e) {}
}

export function clearOnboardingDraft() {
  localStorage.removeItem(STORAGE_KEY_ONBOARDING_DRAFT);
}

// Report Storage
export function saveGeneratedReport(report) {
  try {
    localStorage.setItem(STORAGE_KEY_LATEST_REPORT, JSON.stringify(report));
  } catch (e) {}
}

export function getGeneratedReport() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_LATEST_REPORT);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}
