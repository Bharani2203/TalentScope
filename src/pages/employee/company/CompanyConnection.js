// ============================================================================
// TALENTSCOPE.AI — COMPANY CONNECTION & HR FEEDBACK HUB
// Verified company membership, HR upskill directives, project assignments & feedback
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee
} from '../../../data/employee/employee-data.js';
import { loadRoleOnboardingProfile } from '../../../onboarding/onboarding-api.js';
import {
  acceptCompanyInvitation,
  declineCompanyInvitation,
  requestCompanyConnection,
  searchCompanies,
  setEmployeeIndependent
} from '../../../data/company-relationships-api.js';
import { loadCompanyMessages } from '../../../api/company-messages-client.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);

let connectionState = {
  status: 'idle', // 'idle' | 'loading' | 'loaded' | 'error'
  employmentState: null, // 'connected' | 'requesting' | 'independent' | null
  companyName: '',
  companyId: '',
  messages: [],
  error: null
};

export function resetConnectionState() {
  connectionState = {
    status: 'idle',
    employmentState: null,
    companyName: '',
    companyId: '',
    messages: [],
    error: null
  };
}

export function setConnectionStateForTest(patch = {}) {
  connectionState = { ...connectionState, ...patch };
}

export function getConnectionState() {
  return connectionState;
}

export function renderEmployeeCompanyConnection() {
  const p = getEmployeeProfile();
  const profileConnected = Boolean(p.companyVerified || p.employmentState === 'connected' || (isCompanyEmployee() && p.company));
  
  const isConnected = connectionState.employmentState === 'connected' || 
    (connectionState.employmentState === null && profileConnected);
  
  const isRequesting = connectionState.employmentState === 'requesting' || 
    (!isConnected && p.employmentState === 'requesting');

  const companyName = connectionState.companyName || p.company || 'Connected Company';

  let hasInvitation = false;
  try {
    hasInvitation = Boolean(sessionStorage.getItem('talentscope_pending_company_invitation'));
  } catch {}

  // --------------------------------------------------------------------------
  // 1. CONNECTED STATE: COMPANY FEEDBACK & COMMUNICATIONS HUB
  // --------------------------------------------------------------------------
  if (isConnected) {
    const messages = connectionState.messages || [];
    const isLoading = connectionState.status === 'loading';

    return `
      <div class="employee-page">
        <!-- ACTIVE COMPANY HERO HEADER -->
        <section class="emp-hero">
          <div class="emp-hero-content">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap;">
              <span class="emp-eyebrow" style="margin: 0;">
                <i data-lucide="building-2"></i>
                COMPANY CONNECTION &amp; FEEDBACK HUB
              </span>
              <span id="employeeConnectionStatus" class="emp-badge emp-badge-success" style="font-size: 11.5px; padding: 4px 10px; display: inline-flex; align-items: center; gap: 6px;">
                <i data-lucide="check-circle-2"></i> Verified Member
              </span>
            </div>
            <h1 class="emp-hero-title">
              ${escapeHtml(companyName)}
            </h1>
            <p class="emp-hero-desc">
              Direct communication, skill directives, and project allocation stream from <strong>${escapeHtml(companyName)}</strong> HR and Engineering Leadership.
            </p>
          </div>
          <div class="emp-hero-actions">
            <div class="emp-stat-pill" style="background: var(--emp-light); border: 1px solid rgba(39, 53, 245, 0.2);">
              <strong style="color: var(--emp-primary);">${isLoading ? '…' : `${messages.length} Active`}</strong>
              <small style="color: var(--emp-text-muted);">Company Communications</small>
            </div>
          </div>
        </section>

        <!-- HR COMMUNICATIONS & FEEDBACK DASHBOARD -->
        <section class="emp-card" style="padding: 24px; display: flex; flex-direction: column; gap: 20px;">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--emp-border-subtle); padding-bottom: 14px;">
            <div>
              <h2 style="font-size: 17px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 4px;">
                Management Communications &amp; Directives
              </h2>
              <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
                Actionable feedback, upskill requests, and mission assignments issued for your profile.
              </p>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="emp-badge emp-badge-primary" style="font-size: 11px;">Live Synchronization</span>
            </div>
          </div>

          <!-- FEEDBACK CARDS GRID -->
          <div id="companyFeedbackContainer">
            ${isLoading ? `
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
                <div class="emp-card" style="padding: 20px;">
                  <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 12px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 220px; height: 20px; border-radius: 6px; margin-bottom: 10px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 100%; height: 40px; border-radius: 6px; margin-bottom: 14px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 130px; height: 32px; border-radius: 8px; background: var(--emp-border-subtle);"></div>
                </div>
                <div class="emp-card" style="padding: 20px;">
                  <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 12px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 220px; height: 20px; border-radius: 6px; margin-bottom: 10px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 100%; height: 40px; border-radius: 6px; margin-bottom: 14px; background: var(--emp-border-subtle);"></div>
                  <div class="emp-skeleton-shimmer" style="width: 130px; height: 32px; border-radius: 8px; background: var(--emp-border-subtle);"></div>
                </div>
              </div>
            ` : messages.length === 0 ? `
              <div style="text-align: center; padding: 36px 16px; display: flex; flex-direction: column; align-items: center; gap: 12px;">
                <div class="emp-icon-box emp-icon-box--primary" style="width: 48px; height: 48px; border-radius: 14px;">
                  <i data-lucide="inbox" style="width: 22px; height: 22px;"></i>
                </div>
                <h4 style="font-size: 15px; font-weight: 750; color: var(--emp-text-primary); margin: 0;">
                  No direct communications at this time
                </h4>
                <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0; max-width: 400px; line-height: 1.5;">
                  Your connection with <strong>${escapeHtml(companyName)}</strong> is verified. Upskill directives and project allocations from HR will appear here.
                </p>
              </div>
            ` : `
              <div class="company-feedback-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px;">
                ${messages.map(msg => {
                  if (msg.type === 'upskill_request') {
                    const skill = msg.skill_name || 'Distributed Systems';
                    return `
                      <article class="emp-card company-message-card company-message--upskill" style="padding: 22px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px; border-color: rgba(39, 53, 245, 0.35); background: linear-gradient(180deg, #ffffff 0%, rgba(39, 53, 245, 0.02) 100%);">
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                            <span class="emp-badge emp-badge-primary" style="font-size: 11px;">
                              <i data-lucide="sparkles"></i> Upskill Request
                            </span>
                            <span style="font-size: 12px; color: var(--emp-text-muted);">
                              ${escapeHtml(msg.date || 'Active')}
                            </span>
                          </div>
                          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 2px 0 0;">
                            ${escapeHtml(msg.title || `HR requested you upskill in ${skill}`)}
                          </h3>
                          <div style="font-size: 12px; color: var(--emp-text-muted);">
                            Issued by: <strong>${escapeHtml(msg.sender || 'HR Operations')}</strong>
                            ${msg.target_date ? ` · Target: <strong>${escapeHtml(msg.target_date)}</strong>` : ''}
                          </div>
                          <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; line-height: 1.5;">
                            ${escapeHtml(msg.message || `HR requested you upskill in ${skill}.`)}
                          </p>
                          ${msg.details ? `
                            <div style="background: var(--emp-soft); padding: 10px 12px; border-radius: 8px; font-size: 12.5px; color: var(--emp-text-secondary); border: 1px solid var(--emp-border-subtle);">
                              ${escapeHtml(msg.details)}
                            </div>
                          ` : ''}
                        </div>
                        <div style="margin-top: 6px; padding-top: 12px; border-top: 1px solid var(--emp-border-subtle); display: flex; align-items: center; justify-content: space-between;">
                          <span style="font-size: 12px; font-weight: 700; color: var(--emp-primary);">
                            Skill: ${escapeHtml(skill)}
                          </span>
                          <a href="#/employee/learning?skill=${encodeURIComponent(skill)}" class="emp-btn-primary" style="text-decoration: none; height: 32px; font-size: 12.5px; display: inline-flex; align-items: center; gap: 6px;">
                            <i data-lucide="play-circle"></i>
                            <span>Start Learning</span>
                          </a>
                        </div>
                      </article>
                    `;
                  } else if (msg.type === 'project_assignment') {
                    return `
                      <article class="emp-card company-message-card company-message--project" style="padding: 22px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px; border-color: rgba(16, 185, 129, 0.35); background: linear-gradient(180deg, #ffffff 0%, rgba(16, 185, 129, 0.02) 100%);">
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                            <span class="emp-badge emp-badge-success" style="font-size: 11px;">
                              <i data-lucide="briefcase"></i> Project Assignment
                            </span>
                            <span style="font-size: 12px; color: var(--emp-text-muted);">
                              ${escapeHtml(msg.date || 'Scheduled')}
                            </span>
                          </div>
                          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 2px 0 0;">
                            ${escapeHtml(msg.title || `You have been assigned to Project ${msg.project_name || 'Initiative'}`)}
                          </h3>
                          <div style="font-size: 12px; color: var(--emp-text-muted);">
                            Pod Lead: <strong>${escapeHtml(msg.sender || 'Engineering Management')}</strong>
                          </div>
                          <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; line-height: 1.5;">
                            ${escapeHtml(msg.message || `You have been assigned to Project ${msg.project_name || 'Initiative'}.`)}
                          </p>
                          <div style="background: var(--emp-soft); padding: 12px 14px; border-radius: 10px; font-size: 12.5px; border: 1px solid var(--emp-border-subtle); display: flex; flex-direction: column; gap: 6px;">
                            ${msg.project_name ? `<div><span style="color: var(--emp-text-muted);">Project:</span> <strong>${escapeHtml(msg.project_name)}</strong></div>` : ''}
                            ${msg.project_role ? `<div><span style="color: var(--emp-text-muted);">Assigned Role:</span> <strong>${escapeHtml(msg.project_role)}</strong></div>` : ''}
                            ${msg.team ? `<div><span style="color: var(--emp-text-muted);">Pod / Team:</span> <strong>${escapeHtml(msg.team)}</strong></div>` : ''}
                            ${msg.start_date ? `<div><span style="color: var(--emp-text-muted);">Start Date:</span> <strong style="color: var(--emp-success);">${escapeHtml(msg.start_date)}</strong></div>` : ''}
                            ${msg.details ? `<div style="margin-top: 4px; color: var(--emp-text-secondary); line-height: 1.4;">${escapeHtml(msg.details)}</div>` : ''}
                          </div>
                        </div>
                        <div style="margin-top: 6px; padding-top: 12px; border-top: 1px solid var(--emp-border-subtle); display: flex; align-items: center; justify-content: flex-end;">
                          <a href="#/employee/opportunities" class="emp-btn-secondary" style="text-decoration: none; height: 32px; font-size: 12.5px; display: inline-flex; align-items: center; gap: 6px;">
                            <i data-lucide="layers"></i>
                            <span>View Pod Requisitions</span>
                          </a>
                        </div>
                      </article>
                    `;
                  } else {
                    return `
                      <article class="emp-card company-message-card company-message--feedback" style="padding: 22px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px;">
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                            <span class="emp-badge emp-badge-neutral" style="font-size: 11px;">
                              <i data-lucide="message-square"></i> General HR Feedback
                            </span>
                            <span style="font-size: 12px; color: var(--emp-text-muted);">
                              ${escapeHtml(msg.date || 'Recent')}
                            </span>
                          </div>
                          <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 2px 0 0;">
                            ${escapeHtml(msg.title || 'Management Review & Progress Note')}
                          </h3>
                          <div style="font-size: 12px; color: var(--emp-text-muted);">
                            From: <strong>${escapeHtml(msg.sender || 'Director of Engineering')}</strong>
                            ${msg.sentiment ? ` · <span class="emp-badge emp-badge-success" style="font-size: 10.5px; padding: 2px 6px;">${escapeHtml(msg.sentiment)}</span>` : ''}
                          </div>
                          <div style="background: var(--emp-soft); padding: 14px 16px; border-radius: 10px; border: 1px solid var(--emp-border-subtle); font-size: 13.5px; color: var(--emp-text-primary); line-height: 1.6; font-style: italic;">
                            “${escapeHtml(msg.message)}”
                          </div>
                        </div>
                        <div style="margin-top: 6px; padding-top: 12px; border-top: 1px solid var(--emp-border-subtle); font-size: 12px; color: var(--emp-text-muted); display: flex; align-items: center; gap: 6px;">
                          <i data-lucide="check" style="width: 14px; height: 14px; color: var(--emp-success);"></i>
                          <span>Acknowledged in verified employee record</span>
                        </div>
                      </article>
                    `;
                  }
                }).join('')}
              </div>
            `}
          </div>

          <!-- CONNECTION SETTINGS & ACTIONS FOOTER -->
          <div style="padding-top: 16px; border-top: 1px solid var(--emp-border-subtle); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
            <div style="font-size: 12.5px; color: var(--emp-text-muted);">
              Verified membership connected to <strong>${escapeHtml(companyName)}</strong>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <a href="#/employee/skills" class="emp-btn-secondary" style="text-decoration: none; height: 32px; font-size: 12px;">
                <i data-lucide="layers-3"></i>
                <span>Explore Skills</span>
              </a>
              <button id="setIndependentButton" class="emp-btn-ghost" type="button" style="height: 32px; font-size: 12px; color: var(--emp-text-muted);">
                <i data-lucide="unlink"></i>
                <span>Disconnect</span>
              </button>
            </div>
          </div>
        </section>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // 2. INDEPENDENT OR PENDING REVIEW STATE
  // --------------------------------------------------------------------------
  return `
    <div class="employee-page">
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="building-2"></i>
            COMPANY CONNECTION
          </span>
          <h1 class="emp-hero-title">Company Connection</h1>
          <p class="emp-hero-desc">
            ${isRequesting 
              ? 'Your connection request has been transmitted and is pending verification.' 
              : 'Connect your employee profile with your verified organization to unlock internal mobility and HR directives.'}
          </p>
        </div>
      </section>

      <section class="emp-card" style="padding: 24px; display: flex; flex-direction: column; gap: 18px;">
        <!-- PENDING STATUS NOTICE -->
        ${isRequesting ? `
          <div class="emp-card" role="alert" style="border-left: 4px solid var(--emp-attention, #f59e0b); padding: 16px 20px; background: rgba(245, 158, 11, 0.06); display: flex; align-items: center; gap: 12px;">
            <i data-lucide="clock" style="color: var(--emp-attention, #f59e0b); width: 22px; height: 22px; flex-shrink: 0;"></i>
            <div>
              <strong style="color: var(--emp-text-primary); font-size: 14px;">Connection Request Pending Review</strong>
              <p style="margin: 4px 0 0; font-size: 13px; color: var(--emp-text-secondary); line-height: 1.4;">
                Your connection request is pending company review. Once an HR administrator approves your profile, this hub will activate with company communications.
              </p>
            </div>
          </div>
        ` : ''}

        <div id="employeeConnectionStatus" role="status" style="font-size: 13px; color: var(--emp-text-secondary);">
          ${isRequesting 
            ? 'Your connection request is pending company review.' 
            : 'You are independent. You can request a connection or continue independently.'}
        </div>

        ${hasInvitation ? `
          <div class="emp-card" role="group" aria-label="Company invitation" style="padding: 18px; border: 1px solid rgba(39, 53, 245, 0.2); background: var(--emp-soft);">
            <p style="margin: 0 0 12px; font-size: 13.5px; color: var(--emp-text-primary);">
              A company invitation token was preserved during sign-in. Verify your email and choose whether to accept it.
            </p>
            <div style="display: flex; gap: 10px;">
              <button id="acceptBackendInvitation" class="emp-btn-primary" type="button">Accept invitation</button>
              <button id="declineBackendInvitation" class="emp-btn-ghost" type="button">Decline invitation</button>
            </div>
          </div>
        ` : ''}

        <!-- FIND A COMPANY SEARCH FORM -->
        <form id="companySearchForm" style="display: flex; flex-direction: column; gap: 8px;">
          <label for="companySearchInput" style="font-weight: 750; font-size: 14px; color: var(--emp-text-primary);">
            Find a company
          </label>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <input 
              id="companySearchInput" 
              name="query" 
              minlength="2" 
              maxlength="120" 
              required 
              autocomplete="organization" 
              placeholder="Enter company name" 
              style="flex: 1; min-width: 220px; padding: 10px 14px; border: 1px solid var(--emp-border); border-radius: 10px; font-size: 13.5px;"
            >
            <button class="emp-btn-primary" type="submit">Search</button>
          </div>
        </form>

        <div id="companySearchResults" aria-live="polite"></div>

        <div style="padding-top: 12px; border-top: 1px solid var(--emp-border-subtle); display: flex; justify-content: flex-start;">
          <button id="setIndependentButton" class="emp-btn-ghost" type="button">
            Continue independently
          </button>
        </div>
      </section>
    </div>
  `;
}

export function bindEmployeeCompanyConnection(rerender) {
  const status = document.querySelector('#employeeConnectionStatus');
  const results = document.querySelector('#companySearchResults');
  const form = document.querySelector('#companySearchForm');
  const independent = document.querySelector('#setIndependentButton');

  const showError = error => {
    if (status) {
      status.textContent = error.message || 'The request could not be completed.';
    }
  };

  const p = getEmployeeProfile();

  // Load server profile state
  loadRoleOnboardingProfile('employee')
    .then(result => {
      const profile = result.profile || {};
      const state = profile.employment_state || (profile.company_id ? 'connected' : 'independent');
      const company = profile.employer_name_claim || p.company || '';

      connectionState.employmentState = state;
      connectionState.companyName = company;
      connectionState.companyId = profile.company_id || '';

      if (state === 'connected') {
        if (connectionState.status === 'idle') {
          connectionState.status = 'loading';
          loadCompanyMessages({
            companyName: company,
            companyId: connectionState.companyId
          })
            .then(msgRes => {
              connectionState.status = 'loaded';
              connectionState.messages = Array.isArray(msgRes?.messages) ? msgRes.messages : [];
              if (typeof rerender === 'function') {
                rerender();
              }
            })
            .catch(err => {
              console.warn('Could not load company messages:', err);
              connectionState.status = 'error';
              if (typeof rerender === 'function') {
                rerender();
              }
            });
        }
      } else if (status) {
        status.textContent = state === 'requesting'
          ? 'Your connection request is pending company review.'
          : 'You are independent. You can request a connection or continue independently.';
      }
    })
    .catch(showError);

  // If already connected from profile/state, load messages if idle
  const profileConnected = Boolean(p.companyVerified || p.employmentState === 'connected' || (isCompanyEmployee() && p.company));
  if ((profileConnected || connectionState.employmentState === 'connected') && connectionState.status === 'idle') {
    connectionState.status = 'loading';
    loadCompanyMessages({
      companyName: connectionState.companyName || p.company,
      companyId: connectionState.companyId
    })
      .then(msgRes => {
        connectionState.status = 'loaded';
        connectionState.messages = Array.isArray(msgRes?.messages) ? msgRes.messages : [];
        if (typeof rerender === 'function') {
          rerender();
        }
      })
      .catch(err => {
        console.warn('Could not load company messages:', err);
        connectionState.status = 'error';
        if (typeof rerender === 'function') {
          rerender();
        }
      });
  }

  // Handle invitation accept/decline
  const invitationToken = (() => {
    try {
      return sessionStorage.getItem('talentscope_pending_company_invitation');
    } catch {
      return null;
    }
  })();

  const settleInvitation = async accept => {
    const button = document.querySelector(accept ? '#acceptBackendInvitation' : '#declineBackendInvitation');
    if (!invitationToken || !button) return;
    button.disabled = true;
    try {
      const result = accept
        ? await acceptCompanyInvitation(invitationToken)
        : await declineCompanyInvitation(invitationToken);
      try {
        sessionStorage.removeItem('talentscope_pending_company_invitation');
      } catch {}
      
      if (accept) {
        connectionState.employmentState = 'connected';
        connectionState.companyName = result.company_name || p.company || 'Verified Company';
        connectionState.companyId = result.company_id || '';
        connectionState.status = 'idle';
        if (typeof rerender === 'function') {
          rerender();
        }
      } else {
        connectionState.employmentState = 'independent';
        if (status) {
          status.textContent = 'Invitation declined. You remain independent.';
        }
        button.closest('[role="group"]')?.remove();
      }
    } catch (error) {
      showError(error);
      button.disabled = false;
    }
  };

  document.querySelector('#acceptBackendInvitation')?.addEventListener('click', () => settleInvitation(true));
  document.querySelector('#declineBackendInvitation')?.addEventListener('click', () => settleInvitation(false));

  // Search form submit
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!results) return;
    results.textContent = 'Searching verified company profiles…';
    try {
      const companies = await searchCompanies(new FormData(form).get('query').trim());
      if (!companies.length) {
        results.textContent = 'No matching verified companies were found.';
        return;
      }
      results.innerHTML = companies.map(company => `
        <article class="emp-card" style="margin-top: 10px; padding: 14px;">
          <strong>${escapeHtml(company.company_name || 'Company')}</strong>
          <p style="margin: 4px 0 10px; font-size: 13px; color: var(--emp-text-secondary);">${escapeHtml(company.industry || 'Industry unavailable')}</p>
          <button type="button" class="emp-btn-primary emp-btn-sm" data-company-id="${escapeHtml(company.company_id)}">Request connection</button>
        </article>
      `).join('');

      results.querySelectorAll('[data-company-id]').forEach(button => {
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const result = await requestCompanyConnection(button.dataset.companyId);
            if (result.status === 'connected') {
              connectionState.employmentState = 'connected';
              connectionState.companyId = button.dataset.companyId;
              connectionState.status = 'idle';
              if (typeof rerender === 'function') {
                rerender();
              }
            } else {
              connectionState.employmentState = 'requesting';
              if (status) {
                status.textContent = 'Your request is pending company review.';
              }
              results.replaceChildren();
              if (typeof rerender === 'function') {
                rerender();
              }
            }
          } catch (error) {
            button.disabled = false;
            showError(error);
          }
        });
      });
    } catch (error) {
      results.textContent = error.message;
    }
  });

  // Continue independently / Disconnect button
  independent?.addEventListener('click', async () => {
    independent.disabled = true;
    try {
      await setEmployeeIndependent();
      connectionState.employmentState = 'independent';
      connectionState.messages = [];
      connectionState.status = 'idle';
      if (typeof rerender === 'function') {
        rerender();
      } else if (status) {
        status.textContent = 'Your server profile is set to independent.';
        results?.replaceChildren();
      }
    } catch (error) {
      showError(error);
      independent.disabled = false;
    }
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
