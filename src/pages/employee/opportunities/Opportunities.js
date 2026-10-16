// ============================================================================
// TALENTSCOPE.Al — EMPLOYEE OPPORTUNlTlES
// lnternal mobility for company employees & industry opportunities for independent
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
  getOpportunitiesData
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';

let activeOpportunityFilter = 'all';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeOpportunities() {
  const p = getEmployeeProfile();
  const isCompany = isCompanyEmployee();
  const opportunities = getOpportunitiesData();

  let filtered = opportunities;
  if (activeOpportunityFilter === 'high-match') {
    filtered = filtered.filter(o => o.matchScore >= 85);
  }

  return `
    <div class="employee-page">
      <!-- HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="${isCompany ? 'building-2' : 'globe'}"></i>
            ${isCompany ? 'lNTERNAL MOBlLlTY & REQUlSlTlONS' : 'STRATEGlC CAREER OPPORTUNlTlES'}
          </span>
          <h1 class="emp-hero-title">
            ${isCompany ? 'lnternal Mobility & Open Requisitions' : 'Curated lndustry & Mentorship Opportunities'}
          </h1>
          <p class="emp-hero-desc">
            ${isCompany 
              ? `Discover verified internal openings matched against your skills across <strong>${esc(p.company)}</strong> global engineering pods.`
              : `Explore high-impact positions, funded research grants, and paid mentorship opportunities matched to your verified credentials.`}
          </p>
        </div>
        <div class="emp-hero-actions">
          <div class="emp-stat-pill" style="background: var(--emp-light); border: 1px solid rgba(39, 53, 245, 0.2);">
            <strong style="color: var(--emp-primary);">${opportunities.length} Matched</strong>
            <small style="color: var(--emp-text-muted);">Active opportunities</small>
          </div>
        </div>
      </section>

      <!-- FlLTER BAR -->
      <div class="emp-card" style="padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Filter:</span>
          <button type="button" class="emp-btn-ghost ${activeOpportunityFilter === 'all' ? 'emp-btn-secondary' : ''}" data-opp-filter="all" style="height: 30px; font-size: 12px;">
            All Opportunities (${opportunities.length})
          </button>
          <button type="button" class="emp-btn-ghost ${activeOpportunityFilter === 'high-match' ? 'emp-btn-secondary' : ''}" data-opp-filter="high-match" style="height: 30px; font-size: 12px;">
            High Match (>85%)
          </button>
        </div>
        <div style="font-size: 12.5px; color: var(--emp-text-muted);">
          Matching engine powered by your <strong>illustrative skill profile</strong>
        </div>
      </div>

      <!-- OPPORTUNlTlES LlST -->
      <div style="display: flex; flex-direction: column; gap: 16px;">
        ${filtered.map(opp => `
          <div class="emp-card" style="padding: 22px; display: flex; flex-direction: column; gap: 14px; border-color: ${opp.matchScore >= 90 ? 'rgba(39, 53, 245, 0.35)' : 'var(--emp-border)'};">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
              <div>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span class="emp-badge ${opp.matchScore >= 85 ? 'emp-badge-primary' : 'emp-badge-neutral'}">
                    ${opp.matchScore}% Skill Match
                  </span>
                  <span class="emp-badge emp-badge-success">${esc(opp.status)}</span>
                  ${opp.urgency ? `<span class="emp-badge emp-badge-warning">${esc(opp.urgency)}</span>` : ''}
                </div>
                <h3 style="font-size: 18px; font-weight: 850; color: var(--emp-text-primary); margin: 8px 0 2px;">
                  ${esc(opp.title)}
                </h3>
                <div style="font-size: 13px; color: var(--emp-text-muted);">
                  ${isCompany ? `${esc(opp.team)} · ${esc(opp.department)} · Hiring Lead: ${esc(opp.hiringManager)}` : `${esc(opp.organization)} · ${esc(opp.type)}`}
                  ${opp.compensationRange ? ` · <strong style="color: var(--emp-success);">${esc(opp.compensationRange)}</strong>` : ''}
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <button type="button" class="emp-btn-primary" data-apply-opp="${esc(opp.id)}" data-opp-title="${esc(opp.title)}">
                  <i data-lucide="${isCompany ? 'send' : 'check'}"></i>
                  <span>${isCompany ? 'Express lnterest' : 'Apply with Profile'}</span>
                </button>
              </div>
            </div>

            <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0; line-height: 1.5;">
              ${esc(opp.summary)}
            </p>

            <!-- Skills Matched vs Gaps -->
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap; background: var(--emp-soft); padding: 12px 16px; border-radius: 12px; border: 1px solid var(--emp-border-subtle); font-size: 12.5px;">
              <div>
                <span style="font-weight: 750; color: var(--emp-success);"><i data-lucide="check"></i> Matched Competencies:</span>
                <span style="color: var(--emp-text-primary); margin-left: 6px;">${opp.matchedSkills.join(', ')}</span>
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
    </div>
  `;
}

export function bindEmployeeOpportunitiesEvents(rerender) {
  // Filters
  document.querySelectorAll('[data-opp-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeOpportunityFilter = btn.dataset.oppFilter;
      rerender();
    });
  });

  // Apply / Express interest button
  document.querySelectorAll('[data-apply-opp]').forEach(btn => {
    btn.addEventListener('click', () => {
      const oppTitle = btn.dataset.oppTitle;
      const isCompany = isCompanyEmployee();

      openEmployeeModal({
        title: isCompany ? `Express lnterest: ${oppTitle}` : `Apply for ${oppTitle}`,
        subtitle: isCompany 
          ? 'Your interest is shared confidentially with the hiring manager under internal mobility policy'
          : 'Your verified skill credentials and code review history will be attached',
        badge: 'lllustrative Submission',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle); font-size: 13px;">
              <strong style="color: var(--emp-text-primary);">Credentials to be shared:</strong>
              <ul style="margin: 6px 0 0; padding-left: 20px; color: var(--emp-text-secondary); line-height: 1.6;">
                <li>eerified Skill Health Score: <strong>88/100</strong> (Python & PyTorch Expert)</li>
                <li>Community Contributor Reputation: <strong>1,840 pts (Top 5%)</strong></li>
                <li>DLl GPU Kernel Optimization Track: <strong>8/12 Modules Completed</strong></li>
              </ul>
            </div>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Note to Hiring Team (Optional)
              <textarea rows="3" placeholder="Briefly highlight relevant distributed systems projects or reason for interest..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementByld('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Application submitted successfully!'); document.getElementByld('empModalCloseBtn').click();">
            <span>Submit Application</span>
          </button>
        `
      });
    });
  });
}
