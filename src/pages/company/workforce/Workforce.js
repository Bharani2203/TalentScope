// ============================================================================
// TALENTSCOPE.Al — COMPANY WORKFORCE MANAGEMENT
// Workforce Overview, Team Allocations, Employee Directory, lnvitation & Growth Analysis
// "Understand the people and capabilities inside the company" (#874FFF)
// ============================================================================

import {
  companyProfile,
  companyTeams,
  companyEmployees
} from '../../../data/company/company-data.js';

import { openCompanyModal } from '../components/CompanyModal.js';
import { createCompanyInvitation, loadCompanyInvitations } from '../../../data/company-relationships-api.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let employeeSearchQuery = '';
let selectedTeamFilter = 'all';
let selectedReadinessFilter = 'all';

export function renderCompanyWorkforce() {
  const p = companyProfile;

  // Filter employees
  const filteredEmployees = companyEmployees.filter(emp => {
    const matchesSearch = !employeeSearchQuery ||
      emp.name.toLowerCase().includes(employeeSearchQuery.toLowerCase()) ||
      emp.role.toLowerCase().includes(employeeSearchQuery.toLowerCase()) ||
      emp.team.toLowerCase().includes(employeeSearchQuery.toLowerCase()) ||
      emp.keySkills.some(s => s.toLowerCase().includes(employeeSearchQuery.toLowerCase()));
    
    const matchesTeam = selectedTeamFilter === 'all' || emp.team === selectedTeamFilter;
    const matchesReadiness = selectedReadinessFilter === 'all' ||
      (selectedReadinessFilter === 'ready' && emp.targetRoleFit >= 75) ||
      (selectedReadinessFilter === 'upskilling' && emp.targetRoleFit < 75);

    return matchesSearch && matchesTeam && matchesReadiness;
  });

  return `
    <div class="company-page company-workforce">
      <aside role="note" class="cmp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">Workforce directory, headcount, employee skills and fit metrics below are illustrative prototype data. Employee invitation links are created and persisted by the authenticated backend.</aside>
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="users" class="cmp-icon-inline"></i>
              ORGANlZATlONAL WORKFORCE
            </span>
            <h1>Workforce Capability & People Directory</h1>
            <p>Understand the people and technical capabilities inside NelDlA Enterprise Solutions, monitor team skill health, and foster internal growth.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logolnitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Headcount Architecture</span>
              <div class="cmp-hero__context-meta">
                <span><i data-lucide="users"></i> ${(p.globalHeadcount).toLocaleString()} Total</span>
                <span>·</span>
                <span><i data-lucide="cpu"></i> ${(p.engineeringHeadcount).toLocaleString()} Eng</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. WORKFORCE OeERelEW (Section 9) -->
      <section class="cmp-section">
        <div class="cmp-overview-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Total Workforce</span>
                <div class="cmp-metric-card__icon"><i data-lucide="users"></i></div>
              </div>
              <div class="cmp-metric-card__value">${(p.globalHeadcount).toLocaleString()}</div>
              <div class="cmp-metric-card__headline">Global Organization</div>
              <p class="cmp-metric-card__summary">4,850 in APAC Engineering Centers.</p>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Engineering Units</span>
                <div class="cmp-metric-card__icon"><i data-lucide="layers"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-primary);">${companyTeams.length} Teams</div>
              <div class="cmp-metric-card__headline">Core Delivery Pods</div>
              <p class="cmp-metric-card__summary">Autonomous, lnference, NeMo, Silicon.</p>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Active Requisitions</span>
                <div class="cmp-metric-card__icon"><i data-lucide="briefcase"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-deep-primary);">82 Open</div>
              <div class="cmp-metric-card__headline">Growth Demand</div>
              <p class="cmp-metric-card__summary">31.4% targeted for internal placement.</p>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Average Skill Health</span>
                <div class="cmp-metric-card__icon"><i data-lucide="heart-pulse"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-success);">86%</div>
              <div class="cmp-metric-card__headline">Stable Capability</div>
              <p class="cmp-metric-card__summary">Core technical skills verified via DLl.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 3. TEAM elEW (Section 9: Engineering, Data & Al, Cloud & Platform, Silicon) -->
      <section class="cmp-section">
        <div style="margin-bottom: 14px;">
          <span class="cmp-eyebrow"><i data-lucide="layers" class="cmp-icon-inline"></i> TEAM CAPABlLlTY</span>
          <h2 class="cmp-title">Engineering Teams & Delivery Pods</h2>
          <p class="cmp-subtitle">Headcount, skill health, open requisitions, and priority gaps by team.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
          ${companyTeams.map(t => `
            <div class="cmp-card" style="display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                  <span class="cmp-badge ${t.skillHealth >= 88 ? 'cmp-badge--success' : 'cmp-badge--warning'}">
                    Skill Health: ${t.skillHealth}%
                  </span>
                  <span style="font-size: 11px; font-weight: 700; color: var(--cmp-text-muted);">${esc(t.budgetStatus)}</span>
                </div>
                <h3 style="font-size: 16px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">${esc(t.name)}</h3>
                <span style="font-size: 12px; color: var(--cmp-text-secondary); display: block; margin-bottom: 12px;">Lead: <strong>${esc(t.lead)}</strong> · ${t.headcount} Engineers</span>

                <div style="background: var(--cmp-very-light); padding: 10px; border-radius: 8px; border: 1px solid var(--cmp-border); margin-bottom: 10px; font-size: 12px;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: var(--cmp-text-muted);">Open Requisitions:</span>
                    <strong style="color: var(--cmp-primary);">${t.openRoles} openings</strong>
                  </div>
                  <div>
                    <span style="color: var(--cmp-text-muted); display: block; margin-bottom: 2px;">Critical Skill Needs:</span>
                    <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                      ${t.criticalGaps.map(g => `<span class="cmp-badge cmp-badge--neutral" style="font-size: 10.5px;">${esc(g)}</span>`).join('')}
                    </div>
                  </div>
                </div>
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid var(--cmp-border-subtle); margin-top: 4px;">
                <button type="button" class="cmp-btn-ghost filter-team-quick-btn" data-team="${esc(t.name)}" style="font-size: 11.5px; padding: 0 8px;">
                  <span>Filter Directory</span>
                  <i data-lucide="filter"></i>
                </button>
                <a href="#/company/mobility" class="cmp-btn-secondary" style="height: 28px; padding: 0 10px; font-size: 11px;">
                  <span>Mobility Matches</span>
                </a>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 4. EMPLOYEE DlRECTORY & lNelTATlON FLOW (Sections 9, 10, 11) -->
      <section class="cmp-section" id="employeeDirectorySection">
        <div class="cmp-card">
          <!-- Top Controls -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 14px;">
            <div>
              <span class="cmp-eyebrow"><i data-lucide="user-check" class="cmp-icon-inline"></i> EMPLOYEE DlRECTORY</span>
              <h2 class="cmp-title">People & Capabilities Directory</h2>
              <p class="cmp-subtitle">Search employees, explore skill health, review internal role readiness, and invite team members.</p>
            </div>

            <!-- Action Buttons: lnvite Employee -->
            <button type="button" class="cmp-btn-primary" id="cmplnviteEmployeeBtn">
              <i data-lucide="user-plus"></i>
              <span>lnvite Employee</span>
            </button>
          </div>

          <!-- Search and Filter Bar -->
          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; background: var(--cmp-very-light); padding: 12px; border-radius: var(--cmp-radius-md); border: 1px solid var(--cmp-border);">
            <div style="position: relative; flex: 1; min-width: 220px;">
              <i data-lucide="search" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 14px; height: 14px; color: var(--cmp-text-muted);"></i>
              <input
                type="text"
                id="cmpEmpSearchlnput"
                value="${esc(employeeSearchQuery)}"
                placeholder="Search by name, role, skill, or team..."
                style="width: 100%; height: 36px; padding: 0 12px 0 32px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; outline: none; background: #FFFFFF;"
              />
            </div>

            <select id="cmpEmpTeamFilter" style="height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; background: #FFFFFF; outline: none;">
              <option value="all" ${selectedTeamFilter === 'all' ? 'selected' : ''}>All Teams</option>
              <option value="Autonomous Compute" ${selectedTeamFilter === 'Autonomous Compute' ? 'selected' : ''}>Autonomous Compute</option>
              <option value="Cloud lnfrastructure" ${selectedTeamFilter === 'Cloud lnfrastructure' ? 'selected' : ''}>Cloud lnfrastructure</option>
              <option value="lnference Services" ${selectedTeamFilter === 'lnference Services' ? 'selected' : ''}>lnference Services</option>
              <option value="Core Silicon Architecture" ${selectedTeamFilter === 'Core Silicon Architecture' ? 'selected' : ''}>Core Silicon</option>
              <option value="Core Platform APl" ${selectedTeamFilter === 'Core Platform APl' ? 'selected' : ''}>Core Platform APl</option>
            </select>

            <select id="cmpEmpReadinessFilter" style="height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; background: #FFFFFF; outline: none;">
              <option value="all" ${selectedReadinessFilter === 'all' ? 'selected' : ''}>All Readiness</option>
              <option value="ready" ${selectedReadinessFilter === 'ready' ? 'selected' : ''}>Ready for Next Role (≥75%)</option>
              <option value="upskilling" ${selectedReadinessFilter === 'upskilling' ? 'selected' : ''}>Upskilling ln Progress (&lt;75%)</option>
            </select>

            <button type="button" id="cmpResetEmpFilters" class="cmp-btn-ghost" style="height: 36px; font-size: 12px; padding: 0 10px;">
              <i data-lucide="rotate-ccw"></i>
              <span>Reset</span>
            </button>
          </div>

          <!-- Employee Table with Controlled Spacing (Section 30) -->
          <div class="cmp-table-container">
            <table class="cmp-table" style="font-size: 13px;">
              <thead>
                <tr>
                  <th style="min-width: 200px;">Employee</th>
                  <th>Current Role & Team</th>
                  <th>Skill Health</th>
                  <th>Core Strengths</th>
                  <th style="min-width: 180px;">Role Progression Fit</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${filteredEmployees.length === 0 ? `
                  <tr>
                    <td colspan="6" style="text-align: center; padding: 36px; color: var(--cmp-text-muted);">
                      No employees match your filter criteria.
                    </td>
                  </tr>
                ` : filteredEmployees.map(emp => `
                  <tr>
                    <td>
                      <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="width: 34px; height: 34px; border-radius: 50%; background: var(--cmp-light-primary); color: var(--cmp-deep-primary); font-weight: 800; font-size: 12px; display: flex; align-items: center; justify-content: center; border: 1px solid var(--cmp-border-accent);">
                          ${esc(emp.initials)}
                        </div>
                        <div>
                          <strong style="color: var(--cmp-text-primary); font-size: 13.5px; display: block;">${esc(emp.name)}</strong>
                          <span style="font-size: 11px; color: var(--cmp-text-muted);">${esc(emp.id)} · ${esc(emp.location)}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <strong style="color: var(--cmp-text-primary); display: block;">${esc(emp.role)}</strong>
                      <small style="color: var(--cmp-text-secondary);">${esc(emp.team)}</small>
                    </td>
                    <td>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <strong style="color: ${emp.skillHealth >= 85 ? 'var(--cmp-success)' : 'var(--cmp-warning)'};">${emp.skillHealth}%</strong>
                        <div class="cmp-meter-track" style="width: 50px; height: 5px;">
                          <div class="cmp-meter-fill cmp-meter-fill--accent" style="width: ${emp.skillHealth}%;"></div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style="display: flex; gap: 4px; flex-wrap: wrap; max-width: 200px;">
                        ${emp.keySkills.slice(0, 3).map(sk => `<span class="cmp-badge cmp-badge--neutral" style="font-size: 10.5px;">${esc(sk)}</span>`).join('')}
                      </div>
                    </td>
                    <td>
                      <div>
                        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
                          <span style="color: var(--cmp-text-primary); font-weight: 600;">${esc(emp.targetRole)}</span>
                          <strong style="color: var(--cmp-primary);">${emp.targetRoleFit}%</strong>
                        </div>
                        <div class="cmp-meter-track" style="height: 4px;">
                          <div class="cmp-meter-fill cmp-meter-fill--accent" style="width: ${emp.targetRoleFit}%;"></div>
                        </div>
                        <small style="font-size: 10.5px; color: var(--cmp-danger);">Gap: ${esc(emp.priorityGap)}</small>
                      </div>
                    </td>
                    <td>
                      <button type="button" class="cmp-btn-secondary inspect-emp-btn" data-emp-id="${esc(emp.id)}" style="height: 28px; padding: 0 10px; font-size: 11.5px;">
                        <i data-lucide="user"></i>
                        <span>eiew</span>
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>

          <!-- Pending lnvitations Accordion/Strip (Section 10) -->
          <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div style="font-size: 12.5px; color: var(--cmp-text-secondary);">
              <strong>Invitation status:</strong> Invitations are stored by the verified company service.
            </div>
            <button type="button" class="cmp-btn-ghost" id="cmpeiewlnvitationsBtn" style="font-size:12px;padding:0 8px">View sent invitations</button>
          </div>

        </div>
      </section>
    </div>
  `;
}

export function bindCompanyWorkforceEvents(rerender) {
  // Quick Filter Team button
  document.querySelectorAll('.filter-team-quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const team = btn.dataset.team;
      selectedTeamFilter = team;
      rerender();
      document.querySelector('#employeeDirectorySection')?.scrolllntoeiew({ behavior: 'smooth' });
    });
  });

  // Search input
  const searchlnput = document.querySelector('#cmpEmpSearchlnput');
  if (searchlnput) {
    searchlnput.addEventListener('input', (e) => {
      employeeSearchQuery = e.target.value;
      rerender();
      const updated = document.querySelector('#cmpEmpSearchlnput');
      if (updated) {
        updated.focus();
        updated.setSelectionRange(employeeSearchQuery.length, employeeSearchQuery.length);
      }
    });
  }

  // Team Filter
  document.querySelector('#cmpEmpTeamFilter')?.addEventListener('change', (e) => {
    selectedTeamFilter = e.target.value;
    rerender();
  });

  // Readiness Filter
  document.querySelector('#cmpEmpReadinessFilter')?.addEventListener('change', (e) => {
    selectedReadinessFilter = e.target.value;
    rerender();
  });

  // Reset Filters
  document.querySelector('#cmpResetEmpFilters')?.addEventListener('click', () => {
    employeeSearchQuery = '';
    selectedTeamFilter = 'all';
    selectedReadinessFilter = 'all';
    rerender();
  });

  // lNelTE EMPLOYEE MODAL (Section 10)
  document.querySelector('#cmplnviteEmployeeBtn')?.addEventListener('click', () => {
    openCompanyModal({
      title: 'Invite employee',
      subtitle: 'Create a seven-day invitation link for an employee email. TalentScope will not send email.',
      icon: 'user-plus',
      maxWidth: '540px',
      contentHtml: `
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div>
            <label for="invEmpEmail" style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Employee email *</label>
            <input type="email" id="invEmpEmail" required maxlength="254" autocomplete="email" placeholder="employee@company.com" style="width: 100%; height: 38px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px;" />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label for="invEmpTeam" style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Team (optional)</label>
              <select id="invEmpTeam" style="width: 100%; height: 38px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; background: #FFF;">
                <option value="Autonomous Compute">Autonomous Compute</option>
                <option value="Hyperscale lnference Services">Hyperscale lnference Services</option>
                <option value="NeMo Cloud & LLM Platform">NeMo Cloud Platform</option>
                <option value="Core Silicon Architecture">Core Silicon</option>
              </select>
            </div>
            <div>
              <label for="invEmpRole" style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Role (optional)</label>
              <input type="text" id="invEmpRole" placeholder="e.g. Al Engineer (L4)" style="width: 100%; height: 38px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px;" />
            </div>
          </div>
          <p id="inviteEmployeeStatus" role="status" aria-live="polite"></p>
        </div>
      `,
      cancelText: 'Cancel',
      confirmText: 'Create invitation link',
      confirmIcon: 'link',
      onConfirm: async () => {
        const emailInput = document.querySelector('#invEmpEmail');
        const email = emailInput?.value.trim();
        const status = document.querySelector('#inviteEmployeeStatus');
        const confirm = document.querySelector('#cmpModalConfirmBtn');
        if (!email) { status.textContent = 'Enter an employee email address.'; emailInput?.focus(); return false; }
        if (!emailInput.checkValidity()) { status.textContent = 'Enter a valid email address.'; emailInput?.focus(); return false; }
        if (confirm) confirm.disabled = true;
        status.textContent = 'Creating the invitation…';
        try {
          const result = await createCompanyInvitation({
            email,
            team: document.querySelector('#invEmpTeam')?.value || null,
            role: document.querySelector('#invEmpRole')?.value.trim() || null
          });
          const inviteUrl = `${window.location.origin}${window.location.pathname}#/login?invitation=${encodeURIComponent(result.token)}`;
          const body = document.querySelector('#cmpGlobalModalContainer .cmp-modal-body');
          if (body) body.innerHTML = `<p role="status">Invitation created and stored by the backend for <strong>${esc(email)}</strong>. No email was sent. This link expires ${esc(new Date(result.expires_at).toLocaleString())}.</p><label for="createdInvitationLink">Invitation link</label><input id="createdInvitationLink" readonly value="${esc(inviteUrl)}" style="width:100%;padding:10px;border:1px solid var(--cmp-border);border-radius:8px"><button type="button" id="copyCreatedInvitationLink" class="cmp-btn-secondary" style="margin-top:10px">Copy invitation link</button>`;
          document.querySelector('#copyCreatedInvitationLink')?.addEventListener('click', async () => {
            const currentStatus = document.querySelector('#cmpGlobalModalContainer [role="status"]');
            try { await navigator.clipboard.writeText(inviteUrl); if (currentStatus) currentStatus.textContent = 'Invitation link copied.'; }
            catch { document.querySelector('#createdInvitationLink')?.select(); if (currentStatus) currentStatus.textContent = 'Select and copy the invitation link.'; }
          });
          if (confirm) { confirm.disabled = true; confirm.querySelector('span').textContent = 'Created'; }
          rerender();
        } catch (error) {
          status.textContent = error.message || 'The invitation could not be created.';
          if (confirm) confirm.disabled = false;
        }
        return false;
      }
    });
  });

  document.querySelector('#cmpeiewlnvitationsBtn')?.addEventListener('click', async () => {
    openCompanyModal({
      title: 'Sent employee invitations',
      subtitle: 'Persisted invitations for the authenticated company. Invitation tokens are never shown here.',
      icon: 'mail',
      maxWidth: '720px',
      contentHtml: '<p role="status">Loading invitations from the verified company account…</p>',
      cancelText: 'Close',
      hideFooter: true
    });
    const body = document.querySelector('#cmpGlobalModalContainer .cmp-modal-body');
    try {
      const invitations = await loadCompanyInvitations();
      if (!body?.isConnected) return;
      body.innerHTML = invitations.length ? `
        <div class="cmp-table-container"><table class="cmp-table"><thead><tr><th>Email</th><th>Role / team</th><th>Status</th><th>Created</th><th>Expires</th></tr></thead>
        <tbody>${invitations.map(invitation => {
          const displayStatus = invitation.expired ? 'Expired' : invitation.status === 'invited' ? 'Pending' : invitation.status || 'Unavailable';
          const date = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Unavailable';
          return `<tr><td>${esc(invitation.intended_email || 'Unavailable')}</td><td>${esc(invitation.role || '—')}<br><small>${esc(invitation.team || '—')}</small></td><td>${esc(displayStatus)}</td><td>${esc(date(invitation.created_at))}</td><td>${esc(date(invitation.expires_at))}</td></tr>`;
        }).join('')}</tbody></table></div>` : '<p role="status">No persisted invitations were found for this company.</p>';
    } catch (error) {
      if (body?.isConnected) body.innerHTML = `<p role="alert">${esc(error.message || 'Invitations could not be loaded.')}</p>`;
    }
  });

  // EMPLOYEE PROFlLE / ANALYSlS MODAL (Section 11)
  document.querySelectorAll('.inspect-emp-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const empld = btn.dataset.empld;
      const emp = companyEmployees.find(e => e.id === empld);
      if (!emp) return;

      openCompanyModal({
        title: `Employee Growth Analysis: ${emp.name}`,
        subtitle: `${emp.id} · ${emp.role} (${emp.level}) · ${emp.team}`,
        icon: 'user',
        maxWidth: '640px',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <!-- Narrative flow: CURRENT ROLE → CURRENT SKlLLS → SKlLL GAP → POTENTlAL FUTURE ROLE → RECOMMENDED DEeELOPMENT -->
            <div style="background: var(--cmp-very-light); padding: 12px 16px; border-radius: 10px; border: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <span style="font-size: 11px; font-weight: 700; color: var(--cmp-text-muted); text-transform: uppercase;">Current Role</span>
                <strong style="font-size: 14px; color: var(--cmp-text-primary); display: block;">${esc(emp.role)} (${esc(emp.level)})</strong>
                <small style="color: var(--cmp-text-secondary);">${esc(emp.team)} · ${esc(emp.location)}</small>
              </div>
              <div style="text-align: right;">
                <span style="font-size: 11px; font-weight: 700; color: var(--cmp-text-muted); text-transform: uppercase;">Technical Skill Health</span>
                <div style="font-size: 18px; font-weight: 850; color: ${emp.skillHealth >= 85 ? 'var(--cmp-success)' : 'var(--cmp-warning)'};">
                  ${emp.skillHealth} / 100
                </div>
              </div>
            </div>

            <!-- Current Skills -->
            <div>
              <span style="font-size: 11.5px; font-weight: 700; color: var(--cmp-text-muted); text-transform: uppercase; display: block; margin-bottom: 4px;">eerified Current Strengths:</span>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                ${emp.keySkills.map(sk => `<span class="cmp-badge cmp-badge--neutral" style="font-size: 12px; padding: 4px 10px;">${esc(sk)}</span>`).join('')}
              </div>
            </div>

            <!-- Skill Gap & Target Role Progression -->
            <div style="background: var(--cmp-surface); border: 1px solid var(--cmp-border); border-radius: 10px; padding: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
                <div>
                  <span style="font-size: 11px; font-weight: 700; color: var(--cmp-deep-primary); text-transform: uppercase;">Potential Future Role</span>
                  <strong style="font-size: 14.5px; color: var(--cmp-text-primary); display: block;">${esc(emp.targetRole)}</strong>
                </div>
                <span class="cmp-badge cmp-badge--success" style="font-size: 12px; font-weight: 800;">${emp.targetRoleFit}% Readiness</span>
              </div>

              <div class="cmp-meter-track" style="height: 6px; margin: 8px 0;">
                <div class="cmp-meter-fill cmp-meter-fill--accent" style="width: ${emp.targetRoleFit}%;"></div>
              </div>

              <div style="font-size: 12px; color: var(--cmp-danger); margin-top: 4px;">
                <strong>Primary Development Gap:</strong> ${esc(emp.priorityGap)}
              </div>
            </div>

            <!-- Recommended Development Plan -->
            <div style="background: var(--cmp-light-primary); padding: 12px 14px; border-radius: 8px; border-left: 3px solid var(--cmp-primary); font-size: 12.5px; color: var(--cmp-dark);">
              <strong>Recommended Growth Path:</strong> Enroll ${esc(emp.name)} into the NelDlA DLl Advanced Kernel Academy sprint to resolve ${esc(emp.priorityGap)} gap for internal L5 promotion consideration.
            </div>
          </div>
        `,
        cancelText: 'Dismiss',
        confirmText: 'Open in Mobility Studio',
        confirmlcon: 'git-pull-request',
        onConfirm: () => {
          window.location.hash = '#/company/mobility';
          return true;
        }
      });
    });
  });

  if (window.lucide && typeof window.lucide.createlcons === 'function') {
    window.lucide.createlcons();
  }
}
