// ============================================================================
// TALENTSCOPE.AI — COMPANY ADMINISTRATION & GOVERNANCE HUB
// Unified Workspace Administration: Organization, People & Access, Roles, Data Sources & Privacy
// No separate Governance page (#874FFF)
// ============================================================================

import { companyProfile } from '../../../data/company/company-data.js';
import { openCompanyModal } from '../components/CompanyModal.js';
import { openCompanyProfileModal } from '../components/CompanyProfileModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let activeAdminTab = 'organization';

const rbacUsers = [
  { id: 'USR-01', name: 'Dr. Elena Vance', role: 'Chief People Officer', access: 'Global Super Admin', department: 'Executive Leadership', status: 'Active' },
  { id: 'USR-02', name: 'Marcus Sterling', role: 'VP Workforce Planning', access: 'Strategic Modeling Admin', department: 'Global Talent Planning', status: 'Active' },
  { id: 'USR-03', name: 'Priya Sundaram', role: 'Director AI Infrastructure', access: 'Department Planning Lead', department: 'Autonomous Compute (APAC)', status: 'Active' },
  { id: 'USR-04', name: 'David Chen', role: 'Distinguished Systems Architect', access: 'Technical Guild Reviewer', department: 'Silicon Architecture', status: 'Active' }
];

const dataConnectors = [
  { id: 'src-wd', name: 'Workday HCM Enterprise', type: 'Core HRIS & Headcount', status: 'Healthy & Connected', lastSync: '14 mins ago', records: '29,600 Employees', icon: 'database' },
  { id: 'src-dli', name: 'NVIDIA Deep Learning Institute (DLI)', type: 'Skill Verification API', status: 'Illustrative demo status', lastSync: 'Demo', records: '1,840 Active Certifications', icon: 'award' },
  { id: 'src-gh', name: 'GitHub Enterprise Server', type: 'Engineering Codebase Stacks', status: 'Healthy & Connected', lastSync: '1 hour ago', records: '482 Internal Repositories', icon: 'git-branch' },
  { id: 'src-li', name: 'LinkedIn Talent Insights API', type: 'External Market Benchmarking', status: 'Daily Batch Sync', lastSync: 'Today at 04:00 AM', records: 'Market Supply Trends', icon: 'globe' }
];

const auditEvents = [
  { id: 'AUD-991', user: 'Dr. Elena Vance', action: 'Approved Q4 Internal Mobility Cohort (14 REST Devs)', timestamp: 'Today at 10:14 AM' },
  { id: 'AUD-990', user: 'Marcus Sterling', action: 'Updated APAC Sovereign AI Scenario Baseline', timestamp: 'Today at 09:30 AM' },
  { id: 'AUD-989', user: 'System Connector', action: 'Workday HCM Hourly Sync Completed (29,600 records)', timestamp: 'Today at 09:00 AM' },
  { id: 'AUD-988', user: 'Priya Sundaram', action: 'Assigned DLI Advanced Kernel Sprint to Arun Sharma', timestamp: 'Yesterday at 04:45 PM' }
];

export function renderCompanyAdministration() {
  const p = companyProfile;

  return `
    <div class="company-page company-admin">
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="shield-check" class="cmp-icon-inline"></i>
              ENTERPRISE ADMINISTRATION
            </span>
            <h1>Enterprise Workspace Administration</h1>
            <p>Manage company entity profile, people access, skill architecture, connected HRIS pipelines, and data privacy guardrails.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logoInitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Tenant ID: ${esc(p.id)}</span>
              <div class="cmp-hero__context-meta">
                <span><i data-lucide="lock"></i> SOC-2 Type II Certified</span>
                <span>·</span>
                <span><i data-lucide="shield-check"></i> DPDP & GDPR Compliant</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. ADMIN SUB-TABS NAVIGATION (Section 5 & 22) -->
      <section class="cmp-section">
        <div class="cmp-card" style="padding-bottom: 24px;">
          <!-- Tabs Bar -->
          <div style="display: flex; gap: 6px; overflow-x: auto; padding-bottom: 8px; border-bottom: 1px solid var(--cmp-border); margin-bottom: 20px;">
            ${[
              { id: 'organization', label: 'Organization', icon: 'building' },
              { id: 'people', label: 'People & Access', icon: 'users' },
              { id: 'roles', label: 'Roles & Permissions', icon: 'key' },
              { id: 'skills', label: 'Skill Architecture', icon: 'layers' },
              { id: 'sources', label: 'Data Sources', icon: 'database' },
              { id: 'ai', label: 'AI & Models', icon: 'sparkles' },
              { id: 'privacy', label: 'Privacy & Ethics', icon: 'lock' },
              { id: 'audit', label: 'Audit Log', icon: 'clipboard-list' }
            ].map(t => `
              <button type="button" class="cmp-admin-tab-btn ${t.id === activeAdminTab ? 'is-active' : ''}" data-admin-tab="${t.id}" style="
                display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 700; border: none; cursor: pointer; transition: all 180ms ease;
                background: ${t.id === activeAdminTab ? 'var(--cmp-light-primary)' : 'transparent'};
                color: ${t.id === activeAdminTab ? 'var(--cmp-deep-primary)' : 'var(--cmp-text-secondary)'};
              ">
                <i data-lucide="${t.icon}" style="width: 14px; height: 14px;"></i>
                <span>${t.label}</span>
              </button>
            `).join('')}
          </div>

          <!-- Active Admin Tab Content -->
          <div id="cmpAdminTabContentArea">
            ${renderActiveAdminTab(activeAdminTab, p)}
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderActiveAdminTab(tab, p) {
  if (tab === 'organization') {
    return `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
          <div>
            <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Organization Profile & Entity Configuration</h3>
            <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0;">The foundational entity profile powering all company intelligence.</p>
          </div>
          <button type="button" class="cmp-btn-primary" id="cmpLaunchProfileModalBtn" style="height: 36px; padding: 0 16px;">
            <i data-lucide="edit-3"></i>
            <span>Edit Full Profile Setup</span>
          </button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px;">
          <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 8px; border: 1px solid var(--cmp-border);">
            <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Organization Legal Name</span>
            <div style="font-size: 15px; font-weight: 800; color: var(--cmp-text-primary); margin-top: 3px;">${esc(p.name)}</div>
          </div>
          <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 8px; border: 1px solid var(--cmp-border);">
            <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Industry Classification</span>
            <div style="font-size: 15px; font-weight: 800; color: var(--cmp-text-primary); margin-top: 3px;">${esc(p.industry)}</div>
          </div>
          <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 8px; border: 1px solid var(--cmp-border);">
            <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Global Headcount Baseline</span>
            <div style="font-size: 15px; font-weight: 800; color: var(--cmp-primary); margin-top: 3px;">${(p.globalHeadcount).toLocaleString()} Active Records</div>
          </div>
          <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 8px; border: 1px solid var(--cmp-border);">
            <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Executive People Sponsor</span>
            <div style="font-size: 15px; font-weight: 800; color: var(--cmp-text-primary); margin-top: 3px;">${esc(p.chiefPeopleOfficer)}</div>
          </div>
        </div>
      </div>
    `;
  }

  if (tab === 'people') {
    return `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
          <div>
            <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Authorized Leadership & Administrative Access</h3>
            <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0;">Users granted access to strategic workforce planning and scenario modeling.</p>
          </div>
          <button type="button" class="cmp-btn-secondary" id="cmpAssignAdminBtn" style="height: 36px; padding: 0 14px;">
            <i data-lucide="user-plus"></i>
            <span>Add Administrator</span>
          </button>
        </div>

        <div class="cmp-table-container">
          <table class="cmp-table" style="font-size: 13px;">
            <thead>
              <tr>
                <th>User / Leader</th>
                <th>Role</th>
                <th>Privilege Level</th>
                <th>Department Scope</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${rbacUsers.map(u => `
                <tr>
                  <td>
                    <strong>${esc(u.name)}</strong>
                    <small style="color: var(--cmp-text-muted); display: block;">${esc(u.id)}</small>
                  </td>
                  <td>${esc(u.role)}</td>
                  <td><span class="cmp-badge cmp-badge--accent">${esc(u.access)}</span></td>
                  <td>${esc(u.department)}</td>
                  <td><span class="cmp-badge cmp-badge--success">${esc(u.status)}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  if (tab === 'sources') {
    return `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
          <div>
            <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Connected Data Pipelines & HRIS Connectors</h3>
            <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0;">Automated enterprise sync pipelines feeding live headcount and skills data.</p>
          </div>
          <button type="button" class="cmp-btn-primary" id="cmpSyncAllBtn" style="height: 36px; padding: 0 16px;">
            <i data-lucide="refresh-cw"></i>
            <span>Sync All Pipelines Now</span>
          </button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
          ${dataConnectors.map(c => `
            <div style="background: var(--cmp-very-light); padding: 14px; border-radius: var(--cmp-radius-md); border: 1px solid var(--cmp-border); display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                  <span class="cmp-badge cmp-badge--success">${esc(c.status)}</span>
                  <span style="font-size: 11px; color: var(--cmp-text-muted);">Sync: ${esc(c.lastSync)}</span>
                </div>
                <h4 style="font-size: 14.5px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">${esc(c.name)}</h4>
                <span style="font-size: 12px; color: var(--cmp-text-secondary); display: block; margin-bottom: 6px;">${esc(c.type)}</span>
                <div style="font-size: 12px; color: var(--cmp-text-muted);">
                  Payload: <strong style="color: var(--cmp-text-primary);">${esc(c.records)}</strong>
                </div>
              </div>
              <div style="padding-top: 10px; border-top: 1px solid var(--cmp-border); margin-top: 10px; text-align: right;">
                <button type="button" class="cmp-btn-ghost test-connector-btn" data-conn="${esc(c.name)}" style="font-size: 11.5px; padding: 0 8px;">Test Connection</button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  if (tab === 'privacy') {
    return `
      <div>
        <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Talent Privacy & Compliance Guardrails</h3>
        <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0 0 16px;">Rules governing employee confidentiality during internal mobility and scenario modeling.</p>

        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--cmp-very-light); border-radius: 8px; border: 1px solid var(--cmp-border);">
            <div>
              <strong style="font-size: 13.5px; color: var(--cmp-text-primary); display: block;">Confidential Internal Mobility Protection</strong>
              <span style="font-size: 12px; color: var(--cmp-text-secondary);">Direct managers are not notified when employees explore internal vacancies until formal candidate nomination.</span>
            </div>
            <input type="checkbox" checked style="width: 18px; height: 18px; accent-color: var(--cmp-primary);" />
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--cmp-very-light); border-radius: 8px; border: 1px solid var(--cmp-border);">
            <div>
              <strong style="font-size: 13.5px; color: var(--cmp-text-primary); display: block;">Anonymized Scenario Aggregation</strong>
              <span style="font-size: 12px; color: var(--cmp-text-secondary);">Executive exports aggregate headcount counts without exposing employee personal IDs.</span>
            </div>
            <input type="checkbox" checked style="width: 18px; height: 18px; accent-color: var(--cmp-primary);" />
          </div>
        </div>
      </div>
    `;
  }

  if (tab === 'audit') {
    return `
      <div>
        <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Enterprise Audit Trail</h3>
        <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0 0 14px;">Immutable event log of administrative actions, cohort updates, and data sync events.</p>

        <div class="cmp-table-container">
          <table class="cmp-table" style="font-size: 12.5px;">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Author / Trigger</th>
                <th>Action Details</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              ${auditEvents.map(ev => `
                <tr>
                  <td><span style="font-weight: 700; color: var(--cmp-primary);">${esc(ev.id)}</span></td>
                  <td><strong>${esc(ev.user)}</strong></td>
                  <td>${esc(ev.action)}</td>
                  <td><small style="color: var(--cmp-text-muted);">${esc(ev.timestamp)}</small></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Fallback for roles, skills, ai tabs
  return `
    <div style="padding: 16px; background: var(--cmp-very-light); border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; color: var(--cmp-text-secondary);">
      <strong style="color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Configured & Synced</strong>
      This configuration area is calibrated for NVIDIA Enterprise Solutions. All parameters are active and monitored.
    </div>
  `;
}

export function bindCompanyAdminEvents(rerender) {
  // Tab click
  document.querySelectorAll('.cmp-admin-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeAdminTab = btn.dataset.adminTab;
      rerender();
    });
  });

  // Launch Company Profile modal
  document.querySelector('#cmpLaunchProfileModalBtn')?.addEventListener('click', () => {
    openCompanyProfileModal('overview', () => {
      rerender();
    });
  });

  // Sync Pipelines
  document.querySelector('#cmpSyncAllBtn')?.addEventListener('click', () => {
    alert('Full enterprise sync triggered across Workday, DLI, GitHub, and LinkedIn APIs. 29,600 employee records verified.');
  });

  // Test connector
  document.querySelectorAll('.test-connector-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      alert(`Connection to ${btn.dataset.conn} verified! Latency: 38ms.`);
    });
  });

  // Add admin
  document.querySelector('#cmpAssignAdminBtn')?.addEventListener('click', () => {
    alert('Admin invite link generated for NVIDIA Leadership SSO.');
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
