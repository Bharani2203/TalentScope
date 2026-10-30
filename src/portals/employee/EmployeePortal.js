// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE PORTAL DISPATCHER
// Master portal controller for Employee Workforce Intelligence & Growth routes
// ============================================================================

import { renderEmployeeHome, bindEmployeeHomeEvents, renderEmployeeSkeleton } from '../../pages/employee/home/Home.js';
import { renderEmployeeMySkills, bindEmployeeSkillsEvents } from '../../pages/employee/skills/MySkills.js';
import { renderEmployeeMyGrowth, bindEmployeeGrowthEvents } from '../../pages/employee/growth/MyGrowth.js';
import { renderEmployeeCommunity, bindEmployeeCommunityEvents } from '../../pages/employee/community/Community.js';
import { renderEmployeeOpportunities, bindEmployeeOpportunitiesEvents } from '../../pages/employee/opportunities/Opportunities.js';
import { renderEmployeeProfile, bindEmployeeProfileEvents } from '../../pages/employee/profile/Profile.js';
import { employeeRoutes, isEmployeeRouteCurrent, resolveEmployeeRoute } from './navigation.js';
import { renderEmployeeCompanyConnection, bindEmployeeCompanyConnection } from '../../pages/employee/company/CompanyConnection.js';
import {
  clearEmployeeOnboardingProfile,
  getEmployeeProfile,
  isCompanyEmployee,
  setEmployeeOnboardingProfile,
  toggleEmployeeType
} from '../../data/employee/employee-data.js';
import { getCurrentUser } from '../../auth/auth-state.js';
import { loadRoleOnboardingProfile } from '../../onboarding/onboarding-api.js';
import {
  getCompanyInvitations,
  acceptCompanyInvitation,
  rejectCompanyInvitation,
  getCanonicalBookings
} from '../../data/platform-state.js';

let employeeStateListenerBound = false;
let authStateListenerBound = false;
let profileLoadUid = null;
let profileLoadState = 'idle';
let profileLoadError = null;
let profileLoadGeneration = 0;

export function renderEmployeeRoute(route) {
  const main = document.querySelector('#mainContent');
  if (!main) return;

  if (!authStateListenerBound) {
    window.addEventListener('talentscope-auth-state-changed', () => {
      const uid = getCurrentUser()?.uid || null;
      if (uid !== profileLoadUid) {
        profileLoadGeneration += 1;
        profileLoadUid = null;
        profileLoadState = 'idle';
        profileLoadError = null;
        clearEmployeeOnboardingProfile();
      }
    });
    authStateListenerBound = true;
  }

  const user = getCurrentUser();
  if (!user?.uid || user.userType !== 'employee') {
    profileLoadGeneration += 1;
    profileLoadUid = null;
    profileLoadState = 'idle';
    clearEmployeeOnboardingProfile();
    main.innerHTML = '<div role="alert" class="emp-card">Your employee session is unavailable. Sign in again to continue.</div>';
    return;
  }

  if (profileLoadUid !== user.uid || profileLoadState === 'idle') {
    profileLoadUid = user.uid;
    profileLoadState = 'loading';
    profileLoadError = null;
    clearEmployeeOnboardingProfile();
    main.innerHTML = renderEmployeeSkeleton();
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
    loadEmployeeProfile(user.uid);
    return;
  }

  if (profileLoadState === 'loading') {
    main.innerHTML = renderEmployeeSkeleton();
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
    return;
  }

  if (profileLoadState === 'error') {
    main.innerHTML = `
      <section class="emp-card" role="alert">
        <h1>Profile unavailable</h1>
        <p>${escapeHtml(profileLoadError || 'Your employee profile could not be loaded.')}</p>
        <button type="button" class="emp-btn-primary" id="retryEmployeeProfile">Retry</button>
      </section>
    `;
    main.querySelector('#retryEmployeeProfile')?.addEventListener('click', () => {
      profileLoadState = 'idle';
      renderEmployeeRoute(window.location.hash.slice(1).split('?')[0] || '/employee/home');
    });
    return;
  }

  const resolvedRoute = resolveEmployeeRoute(route);

  const page = employeeRoutes[resolvedRoute] || employeeRoutes['/employee/home'];
  document.title = `TalentScope.ai — ${page.title}`;

  const p = getEmployeeProfile();
  const isCompany = p.profileLoaded ? p.companyVerified === true : isCompanyEmployee();

  const assistantBtn = document.querySelector('.button--assistant');
  if (assistantBtn) {
    assistantBtn.style.display = 'none';
  }

  const topbarContext = document.querySelector('#topbarContext');
  if (topbarContext) {
    topbarContext.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-weight: 750; color: var(--emp-primary); font-size: 13.5px;">${page.eyebrow}</span>
        <span class="portal-badge" style="background: var(--emp-light); color: var(--emp-primary); border-color: rgba(39, 53, 245, 0.2);">
          <i data-lucide="shield"></i> Employee Portal
        </span>
        <span class="emp-badge ${isCompany ? 'emp-badge-success' : 'emp-badge-primary'}" style="font-size: 11px;">
          Employee-provided profile
        </span>
      </div>
    `;
  }

  function loadEmployeeProfile(uid) {
    const generation = ++profileLoadGeneration;
    loadRoleOnboardingProfile('employee').then(profile => {
      if (generation !== profileLoadGeneration || profileLoadUid !== uid) return;
      setEmployeeOnboardingProfile(uid, profile);
      profileLoadState = 'loaded';
      const currentUser = getCurrentUser();
      if (currentUser?.uid === uid) {
        renderEmployeeRoute(window.location.hash.slice(1).split('?')[0] || '/employee/home');
      }
    }).catch(error => {
      if (generation !== profileLoadGeneration || profileLoadUid !== uid) return;
      profileLoadError = error?.message || 'Your employee profile could not be loaded.';
      profileLoadState = 'error';
      renderEmployeeRoute(window.location.hash.slice(1).split('?')[0] || '/employee/home');
    });
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  const rerender = () => {
    const activeRoute = window.location.hash.slice(1).split('?')[0] || '/employee/home';
    if (isEmployeeRouteCurrent(resolvedRoute, activeRoute)) renderEmployeeRoute(activeRoute);
  };

  // Dispatch appropriate page
  if (resolvedRoute === '/employee/home') {
    main.innerHTML = renderEmployeeHome();
    bindEmployeeHomeEvents(rerender);
  } else if (resolvedRoute === '/employee/skills') {
    main.innerHTML = renderEmployeeMySkills();
    bindEmployeeSkillsEvents(rerender);
  } else if (resolvedRoute === '/employee/company') {
    main.innerHTML = renderEmployeeCompanyConnection();
    bindEmployeeCompanyConnection(rerender);
  } else if (resolvedRoute === '/employee/growth') {
    main.innerHTML = renderEmployeeMyGrowth();
    bindEmployeeGrowthEvents(rerender);
  } else if (resolvedRoute === '/employee/learning') {
    import('../../pages/employee/learning/EmployeeLearning.js').then(mod => {
      if (typeof mod.renderEmployeeLearningPage === 'function') {
        mod.renderEmployeeLearningPage();
      }
    }).catch(err => {
      console.error('Failed to load employee learning workspace:', err);
      main.innerHTML = '<div role="alert" class="emp-card">The learning workspace could not be loaded. Please try again.</div>';
    });
  } else if (resolvedRoute === '/employee/community') {
    main.innerHTML = renderEmployeeCommunity();
    bindEmployeeCommunityEvents(rerender);
  } else if (resolvedRoute === '/employee/opportunities') {
    main.innerHTML = renderEmployeeOpportunities();
    bindEmployeeOpportunitiesEvents(rerender);
  } else if (resolvedRoute === '/employee/profile') {
    main.innerHTML = renderEmployeeProfile();
    bindEmployeeProfileEvents(rerender);

  } else if (resolvedRoute === '/employee/notifications') {
    main.innerHTML = renderEmployeeNotifications();
    bindEmployeeNotificationsEvents(rerender);
  } else if (resolvedRoute === '/employee/settings') {
    main.innerHTML = renderEmployeeSettings();
    bindEmployeeSettingsEvents(rerender);
  } else {
    main.innerHTML = renderEmployeeHome();
    bindEmployeeHomeEvents(rerender);
  }

  // Bind state changed listener once
  if (!employeeStateListenerBound) {
    window.addEventListener('talentscope:employee-state-changed', () => {
      renderEmployeeRoute(window.location.hash.slice(1) || '/employee/home');
    });
    employeeStateListenerBound = true;
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function renderEmployeeNotifications() {
  const isCompany = isCompanyEmployee();
  const pendingInvs = [];
  const bookings = getCanonicalBookings() || [];

  return `
    <div class="employee-page">
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="bell"></i> NOTIFICATIONS & ALERTS</span>
          <h1 class="emp-hero-title">Employee Notifications</h1>
          <p class="emp-hero-desc">Assessment results, mentee bookings, requisition matches, and organizational invitations.</p>
        </div>
      </section>

      <div class="emp-card" style="display: flex; flex-direction: column; gap: 14px;">
        <div role="note" style="padding:12px;border:1px solid var(--emp-border-subtle);border-radius:10px">Company invitations are not actionable from local demo records. Open <a href="#/employee/company">Company Connection</a> for server-backed membership requests.</div>
        ${pendingInvs.map(inv => `
          <div style="display: flex; align-items: flex-start; gap: 14px; padding: 18px; background: rgba(39, 53, 245, 0.05); border-radius: 12px; border: 1.5px solid rgba(39, 53, 245, 0.3);">
            <div class="emp-icon-box" style="background: #2735F5; color: #FFF; width: 42px; height: 42px; border-radius: 10px; display: grid; place-items: center; flex-shrink: 0;">
              <i data-lucide="building-2"></i>
            </div>
            <div style="flex: 1;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px;">
                <strong style="font-size: 15px; color: var(--emp-text-primary);">Company Membership Invitation: ${inv.companyName}</strong>
                <span class="emp-badge emp-badge-warning" style="font-size: 11px;">Action Required</span>
              </div>
              <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 6px 0 12px; line-height: 1.5;">
                ${inv.companyName} has invited you to join their verified workforce as <strong>${inv.role}</strong> in <strong>${inv.team}</strong>. Connecting unlocks internal mobility, team benchmarks, and Blackwell GPU infrastructure signals.
              </p>
              <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <button type="button" class="emp-btn-primary emp-accept-inv-btn" data-inv-id="${inv.id}" style="padding: 7px 16px; font-size: 12.5px;">
                  <i data-lucide="check-circle-2"></i>
                  <span>Accept Invitation & Connect</span>
                </button>
                <button type="button" class="emp-btn-ghost emp-reject-inv-btn" data-inv-id="${inv.id}" style="padding: 7px 14px; font-size: 12.5px;">
                  <span>Decline</span>
                </button>
              </div>
            </div>
          </div>
        `).join('')}

        <!-- RECENT BOOKINGS NOTIFICATION -->
        ${bookings.slice(0, 1).map(b => `
          <div style="display: flex; align-items: flex-start; gap: 14px; padding: 16px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
            <div class="emp-icon-box" style="background: var(--emp-primary); color: #FFF;">
              <i data-lucide="video"></i>
            </div>
            <div style="flex: 1;">
              <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <strong style="font-size: 14px; color: var(--emp-text-primary);">Mock Interview Session Scheduled</strong>
                <small style="color: var(--emp-text-muted); font-size: 11.5px;">${b.date} · ${b.time}</small>
              </div>
              <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 4px 0 0;">
                ${b.menteeName} (${b.menteeRole || 'Learner'}) booked your slot on "${b.focus}".
              </p>
            </div>
          </div>
        `).join('')}

        <div style="display: flex; align-items: flex-start; gap: 14px; padding: 16px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
          <div class="emp-icon-box">
            <i data-lucide="file-check"></i>
          </div>
          <div style="flex: 1;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
              <strong style="font-size: 14px; color: var(--emp-text-primary);">Question Bank Milestone Reached</strong>
              <small style="color: var(--emp-text-muted); font-size: 11.5px;">Yesterday</small>
            </div>
            <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 4px 0 0;">
              Your "Python Asynchronous Pipelines" question bank reached 128 verified attempts with 78% average pass rate (+25 Rep Points).
            </p>
          </div>
        </div>

        ${isCompany ? `
          <div style="display: flex; align-items: flex-start; gap: 14px; padding: 16px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
            <div class="emp-icon-box">
              <i data-lucide="briefcase"></i>
            </div>
            <div style="flex: 1;">
              <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <strong style="font-size: 14px; color: var(--emp-text-primary);">New Internal Requisition in Hyperscale Acceleration</strong>
                <small style="color: var(--emp-text-muted); font-size: 11.5px;">2 days ago</small>
              </div>
              <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 4px 0 0;">
                Senior AI Platform Engineer opening matches 84% of your verified skill profile.
              </p>
            </div>
          </div>
        ` : `
          <div style="display: flex; align-items: flex-start; gap: 14px; padding: 16px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
            <div class="emp-icon-box">
              <i data-lucide="award"></i>
            </div>
            <div style="flex: 1;">
              <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <strong style="font-size: 14px; color: var(--emp-text-primary);">New Mentorship Invitation Received</strong>
                <small style="color: var(--emp-text-muted); font-size: 11.5px;">2 days ago</small>
              </div>
              <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 4px 0 0;">
                Global AI Fellowship Guild invited you to become a Lead Reviewer in Distributed Systems.
              </p>
            </div>
          </div>
        `}
      </div>
    </div>
  `;
}

function bindEmployeeNotificationsEvents(rerender) {
  document.querySelectorAll('.emp-accept-inv-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      return; // Local mock invitation IDs are not valid backend invitation tokens.
      const invId = btn.getAttribute('data-inv-id');
      rerender();
      alert('✓ Company invitation accepted! You are now connected to NVIDIA Enterprise Solutions.');
    });
  });

  document.querySelectorAll('.emp-reject-inv-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const invId = btn.getAttribute('data-inv-id');
      rerender();
    });
  });
}


function renderEmployeeSettings() {
  const isCompany = isCompanyEmployee();
  return `
    <div class="employee-page">
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="settings-2"></i> PREFERENCES & CONFIGURATION</span>
          <h1 class="emp-hero-title">Employee Settings</h1>
          <p class="emp-hero-desc">Manage your employee operating mode, internal mobility privacy, and notifications.</p>
        </div>
      </section>

      <div class="emp-card" style="display: flex; flex-direction: column; gap: 24px; padding: 28px;">
        <!-- Dual State Toggle -->
        <div>
          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 6px;">
            Dual Employee Operating Mode
          </h3>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 14px;">
            Connection membership is controlled by the backend. Local demo state does not establish company membership.
          </p>
          <div style="display: flex; align-items: center; gap: 16px; background: var(--emp-soft); padding: 16px; border-radius: 14px; border: 1px solid var(--emp-border-subtle);">
            <div style="flex: 1;">
              <div style="font-weight: 750; font-size: 14px; color: var(--emp-text-primary);">
                Current connection state: <span style="color: var(--emp-primary);">Check Company Connection</span>
              </div>
              <div style="font-size: 12px; color: var(--emp-text-muted); margin-top: 2px;">
                ${isCompany ? 'Displays company pod alignment, internal promotion readiness, and Blackwell signals.' : 'Eliminates all company-dependent data; displays market career benchmarks and open opportunities.'}
              </div>
            </div>
            <a class="emp-btn-primary" href="#/employee/company">Manage verified connection</a>
          </div>
        </div>

        <!-- Privacy & Visibility -->
        <div style="padding-top: 20px; border-top: 1px solid var(--emp-border-subtle);">
          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 4px;">
            Confidential Mobility & Skill Sharing
          </h3>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 12px;">
            Control whether internal hiring teams or community organizers can discover your verified skills.
          </p>
          <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
            <input type="checkbox" checked style="width: 18px; height: 18px; accent-color: var(--emp-primary);" />
            <span style="font-size: 13.5px; font-weight: 650; color: var(--emp-text-primary);">
              Enable confidential skill discovery & internal matching
            </span>
          </label>
        </div>

        <!-- Portal Navigation Shortcut -->
        <div style="padding-top: 20px; border-top: 1px solid var(--emp-border-subtle);">
          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 4px;">
            Switch Portal Experience
          </h3>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 14px;">
            Switch seamlessly to the Individual Portal or Company Portal.
          </p>
          <div style="display: flex; gap: 12px; flex-wrap: wrap;">
            <a href="#/individual/home" class="emp-btn-secondary">
              <i data-lucide="user"></i>
              <span>Switch to Individual Portal</span>
            </a>
            <a href="#/company/home" class="emp-btn-ghost">
              <i data-lucide="building-2"></i>
              <span>Switch to Company Portal</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindEmployeeSettingsEvents(rerender) {
}
