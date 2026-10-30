// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE OPPORTUNITIES
// Internal mobility for company employees & industry opportunities for independent
// Powered dynamically by verified company requisitions and real-time skill matching
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
  externalOpportunitiesData
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';
import { loadCompanyInternalJobs, calculateSkillMatch } from '../../../api/jobs-client.js';

let activeOpportunityFilter = 'all';

let opportunitiesState = {
  status: 'idle', // 'idle' | 'loading' | 'loaded' | 'error'
  companyKey: null,
  companyJobs: [],
  error: null
};

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function resetOpportunitiesState() {
  opportunitiesState = {
    status: 'idle',
    companyKey: null,
    companyJobs: [],
    error: null
  };
  activeOpportunityFilter = 'all';
}

export function setOpportunitiesStateForTest(state) {
  opportunitiesState = { ...opportunitiesState, ...state };
}

export function renderEmployeeOpportunities() {
  const p = getEmployeeProfile();
  const companyName = (p.company || '').trim();
  const isCompany = isCompanyEmployee() || Boolean(companyName);

  let opportunities = [];
  const isLoading = isCompany && companyName && opportunitiesState.status === 'loading';

  if (isCompany) {
    if (opportunitiesState.status === 'loaded' && opportunitiesState.companyKey === companyName) {
      opportunities = opportunitiesState.companyJobs;
    } else {
      opportunities = [];
    }
  } else {
    opportunities = externalOpportunitiesData.map(opp => {
      const match = calculateSkillMatch(p.skills, opp.requiredSkills || []);
      return {
        ...opp,
        matchScore: opp.matchScore ?? match.matchScore,
        matchedSkills: opp.matchedSkills || match.matchedSkills,
        gaps: opp.gaps || match.gaps
      };
    });
  }

  let filtered = opportunities;
  if (activeOpportunityFilter === 'high-match') {
    filtered = filtered.filter(o => o.matchScore >= 85);
  }

  const totalCount = opportunities.length;

  return `
    <div class="employee-page">
      <!-- HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="${isCompany ? 'building-2' : 'globe'}"></i>
            ${isCompany ? 'INTERNAL MOBILITY & REQUISITIONS' : 'STRATEGIC CAREER OPPORTUNITIES'}
          </span>
          <h1 class="emp-hero-title">
            ${isCompany ? 'Internal Mobility & Open Requisitions' : 'Curated Industry & Mentorship Opportunities'}
          </h1>
          <p class="emp-hero-desc">
            ${isCompany 
              ? `Discover verified internal openings matched against your skills across <strong>${esc(companyName || 'your company')}</strong> global engineering pods.`
              : `Explore high-impact positions, funded research grants, and paid mentorship opportunities matched to your verified credentials.`}
          </p>
        </div>
        <div class="emp-hero-actions">
          <div class="emp-stat-pill" style="background: var(--emp-light); border: 1px solid rgba(39, 53, 245, 0.2);">
            <strong style="color: var(--emp-primary);">${isLoading ? '…' : `${totalCount} Matched`}</strong>
            <small style="color: var(--emp-text-muted);">Active opportunities</small>
          </div>
        </div>
      </section>

      <!-- FILTER BAR -->
      <div class="emp-card" style="padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Filter:</span>
          <button type="button" class="emp-btn-ghost ${activeOpportunityFilter === 'all' ? 'emp-btn-secondary' : ''}" data-opp-filter="all" style="height: 30px; font-size: 12px;">
            All Opportunities (${isLoading ? '…' : totalCount})
          </button>
          <button type="button" class="emp-btn-ghost ${activeOpportunityFilter === 'high-match' ? 'emp-btn-secondary' : ''}" data-opp-filter="high-match" style="height: 30px; font-size: 12px;">
            High Match (>85%)
          </button>
        </div>
        <div style="font-size: 12.5px; color: var(--emp-text-muted);">
          Matching engine powered by your <strong>verified profile skills</strong>
        </div>
      </div>

      <!-- OPPORTUNITIES LIST / CONTENT -->
      <div id="opportunitiesContainer">
        ${isLoading ? `
          <div style="display: flex; flex-direction: column; gap: 16px;">
            <div class="emp-card" style="padding: 24px;">
              <div class="emp-skeleton-shimmer" style="width: 140px; height: 18px; border-radius: 6px; margin-bottom: 12px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 260px; height: 22px; border-radius: 8px; margin-bottom: 8px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 180px; height: 14px; border-radius: 6px; margin-bottom: 16px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 100%; height: 38px; border-radius: 8px; background: var(--emp-border-subtle);"></div>
            </div>
            <div class="emp-card" style="padding: 24px;">
              <div class="emp-skeleton-shimmer" style="width: 140px; height: 18px; border-radius: 6px; margin-bottom: 12px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 260px; height: 22px; border-radius: 8px; margin-bottom: 8px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 180px; height: 14px; border-radius: 6px; margin-bottom: 16px; background: var(--emp-border-subtle);"></div>
              <div class="emp-skeleton-shimmer" style="width: 100%; height: 38px; border-radius: 8px; background: var(--emp-border-subtle);"></div>
            </div>
          </div>
        ` : isCompany && !companyName ? `
          <div class="emp-card" style="padding: 48px 24px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;">
            <div class="emp-icon-box emp-icon-box--primary" style="width: 52px; height: 52px; border-radius: 16px;">
              <i data-lucide="building-2" style="width: 24px; height: 24px;"></i>
            </div>
            <h3 style="font-size: 17px; font-weight: 800; color: var(--emp-text-primary); margin: 0;">
              Connect Your Company to Access Internal Mobility
            </h3>
            <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; max-width: 440px; line-height: 1.5;">
              Verify your employer to unlock confidential internal requisitions, direct hiring lead routing, and promotion readiness pipelines.
            </p>
            <a href="#/employee/company" class="emp-btn-primary" style="margin-top: 8px; text-decoration: none;">
              <i data-lucide="building-2"></i>
              <span>Company Connection</span>
            </a>
          </div>
        ` : totalCount === 0 ? `
          <div class="emp-card" style="padding: 48px 24px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;">
            <div class="emp-icon-box emp-icon-box--primary" style="width: 52px; height: 52px; border-radius: 16px;">
              <i data-lucide="briefcase" style="width: 24px; height: 24px;"></i>
            </div>
            <h3 style="font-size: 17px; font-weight: 800; color: var(--emp-text-primary); margin: 0;">
              No open internal requisitions at the moment
            </h3>
            <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; max-width: 420px; line-height: 1.5;">
              No open internal requisitions at the moment. Keep building your skills! We will notify you as soon as new internal mobility requisitions match your profile at <strong>${esc(companyName || 'your company')}</strong>.
            </p>
            <a href="#/employee/skills" class="emp-btn-secondary" style="margin-top: 8px; text-decoration: none;">
              <i data-lucide="layers-3"></i>
              <span>Explore &amp; Update Skills</span>
            </a>
          </div>
        ` : filtered.length === 0 ? `
          <div class="emp-card" style="padding: 36px 20px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;">
            <h4 style="font-size: 15px; font-weight: 750; color: var(--emp-text-primary); margin: 0;">
              No requisitions matching filter criteria
            </h4>
            <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
              Try viewing all opportunities to see roles with emerging skill alignment.
            </p>
            <button type="button" class="emp-btn-secondary emp-btn-sm" data-opp-filter="all" style="margin-top: 6px;">
              View All Opportunities (${totalCount})
            </button>
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 16px;">
            ${filtered.map(opp => `
              <div class="emp-card" style="padding: 22px; display: flex; flex-direction: column; gap: 14px; border-color: ${opp.matchScore >= 90 ? 'rgba(39, 53, 245, 0.35)' : 'var(--emp-border)'};">
                <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
                  <div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                      <span class="emp-badge ${opp.matchScore >= 85 ? 'emp-badge-primary' : 'emp-badge-neutral'}">
                        ${opp.matchScore}% Skill Match
                      </span>
                      <span class="emp-badge emp-badge-success">${esc(opp.status || 'Open Internal Requisition')}</span>
                      ${opp.urgency ? `<span class="emp-badge emp-badge-warning">${esc(opp.urgency)}</span>` : ''}
                    </div>
                    <h3 style="font-size: 18px; font-weight: 850; color: var(--emp-text-primary); margin: 8px 0 2px;">
                      ${esc(opp.title)}
                    </h3>
                    <div style="font-size: 13px; color: var(--emp-text-muted);">
                      ${isCompany 
                        ? `${esc(opp.team || 'Engineering')} · ${esc(opp.department || 'Technology')} · Hiring Lead: ${esc(opp.hiringManager || 'Internal Talent Acquisition')}` 
                        : `${esc(opp.organization || opp.company_name || 'Partner Org')} · ${esc(opp.type || 'Opportunity')}`}
                      ${opp.location ? ` · <span style="color: var(--emp-text-secondary);">${esc(opp.location)}</span>` : ''}
                      ${opp.compensationRange ? ` · <strong style="color: var(--emp-success);">${esc(opp.compensationRange)}</strong>` : ''}
                    </div>
                  </div>
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <button type="button" class="emp-btn-primary" data-apply-opp="${esc(opp.id)}" data-opp-title="${esc(opp.title)}">
                      <i data-lucide="${isCompany ? 'send' : 'check'}"></i>
                      <span>${isCompany ? 'Express Interest' : 'Apply with Profile'}</span>
                    </button>
                  </div>
                </div>

                <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; line-height: 1.5;">
                  ${esc(opp.summary || opp.description || '')}
                </p>

                <!-- Skills Matched vs Gaps -->
                <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; background: var(--emp-soft); padding: 12px 16px; border-radius: 12px; border: 1px solid var(--emp-border-subtle); font-size: 12.5px;">
                  <div>
                    <span style="font-weight: 750; color: var(--emp-success);"><i data-lucide="check"></i> Matched Competencies:</span>
                    <span style="color: var(--emp-text-primary); margin-left: 6px;">${opp.matchedSkills && opp.matchedSkills.length ? opp.matchedSkills.join(', ') : 'Building initial alignment'}</span>
                  </div>
                  ${opp.gaps && opp.gaps.length ? `
                    <div style="border-left: 1px solid var(--emp-border); padding-left: 14px;">
                      <span style="font-weight: 750; color: var(--emp-attention);"><i data-lucide="alert-circle"></i> Growth Areas:</span>
                      <span style="color: var(--emp-text-secondary); margin-left: 6px;">${opp.gaps.join(', ')}</span>
                    </div>
                  ` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        `}
      </div>
    </div>
  `;
}

export function bindEmployeeOpportunitiesEvents(rerender) {
  const p = getEmployeeProfile();
  const companyName = (p.company || '').trim();
  const isCompany = isCompanyEmployee() || Boolean(companyName);

  // Trigger dynamic data fetch for company employees
  if (isCompany && companyName && (opportunitiesState.status === 'idle' || opportunitiesState.companyKey !== companyName)) {
    opportunitiesState.status = 'loading';
    opportunitiesState.companyKey = companyName;

    loadCompanyInternalJobs({ companyName })
      .then(res => {
        const rawJobs = Array.isArray(res?.jobs) ? res.jobs : [];
        const userSkills = p.skills || [];

        opportunitiesState.companyJobs = rawJobs.map(job => {
          const skillAnalysis = calculateSkillMatch(userSkills, job.required_skills || job.requiredSkills || []);
          return {
            id: job.id,
            title: job.title,
            team: job.team || 'Engineering & Product Pod',
            department: job.department || 'Technology',
            hiringManager: job.hiring_manager || job.hiringManager || 'Internal Talent Acquisition',
            location: job.location || 'Hybrid',
            status: job.status || 'Open Internal Requisition',
            urgency: job.urgency || null,
            summary: job.summary || job.description || `Internal role opportunity at ${companyName}.`,
            requiredSkills: job.required_skills || job.requiredSkills || [],
            matchedSkills: skillAnalysis.matchedSkills,
            gaps: skillAnalysis.gaps,
            matchScore: skillAnalysis.matchScore,
            compensationRange: job.compensation_range || job.compensationRange || null,
          };
        });
        opportunitiesState.status = 'loaded';
        if (typeof rerender === 'function') {
          rerender();
        }
      })
      .catch(err => {
        console.warn('Could not load company internal requisitions:', err);
        opportunitiesState.status = 'error';
        opportunitiesState.companyJobs = [];
        if (typeof rerender === 'function') {
          rerender();
        }
      });
  }

  // Filters
  document.querySelectorAll('[data-opp-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeOpportunityFilter = btn.dataset.oppFilter;
      if (typeof rerender === 'function') {
        rerender();
      }
    });
  });

  // Apply / Express interest button
  document.querySelectorAll('[data-apply-opp]').forEach(btn => {
    btn.addEventListener('click', () => {
      const oppTitle = btn.dataset.oppTitle;

      openEmployeeModal({
        title: isCompany ? `Express Interest: ${oppTitle}` : `Apply for ${oppTitle}`,
        subtitle: isCompany 
          ? 'Your interest is shared confidentially with the hiring manager under internal mobility policy'
          : 'Your verified skill credentials and code review history will be attached',
        badge: 'Internal Submission',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle); font-size: 13px;">
              <strong style="color: var(--emp-text-primary);">Credentials to be shared:</strong>
              <ul style="margin: 6px 0 0; padding-left: 20px; color: var(--emp-text-secondary); line-height: 1.6;">
                <li>Verified Employee: <strong>${esc(p.name || 'Current Employee')}</strong> (${esc(p.role || 'Staff')})</li>
                <li>Current Capabilities: <strong>${esc((p.skills || []).join(', ') || 'Saved skills')}</strong></li>
                <li>Career Progression Target: <strong>${esc(p.targetRole || 'Growth Goal')}</strong></li>
              </ul>
            </div>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Note to Hiring Team (Optional)
              <textarea rows="3" placeholder="Briefly highlight relevant experience or reason for interest..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Interest expressed successfully! The hiring manager has been notified.'); document.getElementById('empModalCloseBtn').click();">
            <span>Submit Interest</span>
          </button>
        `
      });
    });
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
