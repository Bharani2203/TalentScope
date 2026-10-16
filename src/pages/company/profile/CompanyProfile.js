// ============================================================================
// TALENTSCOPE.AI — COMPANY PROFILE PAGE
// Comprehensive Organization Profile & Enterprise Workforce Boundary (#874FFF)
// Separates public company identity from protected internal workforce data.
// ============================================================================

import { companyProfile, companyOverviewMetrics } from '../../../data/company/company-data.js';
import { openCompanyProfileModal } from '../components/CompanyProfileModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let activeViewMode = 'public'; // 'public' | 'internal'

export function renderCompanyProfile() {
  const p = companyProfile;
  const metrics = companyOverviewMetrics;

  return `
    <div class="company-page company-profile">
      <!-- 1. EXECUTIVE HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="building" class="cmp-icon-inline"></i>
              ENTERPRISE IDENTITY &amp; GOVERNANCE
            </span>
            <div style="display: flex; align-items: center; gap: 16px; margin: 8px 0 10px; flex-wrap: wrap;">
              <div style="width: 58px; height: 58px; border-radius: 16px; background: var(--cmp-primary, #874FFF); color: #FFFFFF; font-weight: 850; font-size: 22px; display: flex; align-items: center; justify-content: center; box-shadow: 0 8px 24px rgba(135, 79, 255, 0.25);">
                ${esc(p.logoInitials)}
              </div>
              <div>
                <h1 style="margin: 0; font-size: 26px; font-weight: 850; color: var(--cmp-text-primary, #241B32); letter-spacing: -0.02em;">
                  ${esc(p.name)}
                </h1>
                <p style="margin: 4px 0 0; font-size: 13.5px; color: var(--cmp-text-secondary, #70677C);">
                  ${esc(p.industry)} · Headquarters: ${esc(p.headquarters)} · Tenant ID: <strong>${esc(p.id)}</strong>
                </p>
              </div>
            </div>
            <p style="font-size: 13px; color: var(--cmp-text-muted, #948A9F); max-width: 680px; margin: 0; line-height: 1.5;">
              Centralized organizational identity and workforce boundary. Governs public company technology momentum, verified requisitions, and protected workforce analytics.
            </p>
          </div>

          <div class="cmp-hero__context-badge" style="min-width: 260px;">
            <div class="cmp-hero__context-info">
              <span style="font-size: 11px; font-weight: 800; color: var(--cmp-text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Verification Status</span>
              <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
                <span class="cmp-badge cmp-badge--success" style="font-size: 11.5px; padding: 4px 8px;">
                  <i data-lucide="shield-check" style="width: 13px; height: 13px;"></i> Demo Enterprise Profile
                </span>
              </div>
              <div style="margin-top: 8px; font-size: 12px; color: var(--cmp-text-secondary);">
                <span><i data-lucide="users" style="width: 13px; height: 13px; vertical-align: -2px;"></i> ${p.globalHeadcount.toLocaleString()} Global Employees</span>
              </div>
            </div>
          </div>
        </div>

        <div class="cmp-hero__actions" style="margin-top: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
          <!-- View Boundary Switcher -->
          <div style="display: inline-flex; background: var(--cmp-very-light, #F8F6FC); padding: 4px; border-radius: 10px; border: 1px solid var(--cmp-border, #E6DEF7);">
            <button type="button" class="cmp-profile-view-toggle ${activeViewMode === 'public' ? 'is-active' : ''}" data-view="public" style="
              display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 8px; font-size: 12.5px; font-weight: 750; border: none; cursor: pointer; transition: all 160ms ease;
              background: ${activeViewMode === 'public' ? '#FFFFFF' : 'transparent'};
              color: ${activeViewMode === 'public' ? 'var(--cmp-deep-primary, #5B2BBF)' : 'var(--cmp-text-secondary, #70677C)'};
              box-shadow: ${activeViewMode === 'public' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none'};
            ">
              <i data-lucide="globe" style="width: 14px; height: 14px;"></i>
              <span>Public Organization Profile</span>
            </button>
            <button type="button" class="cmp-profile-view-toggle ${activeViewMode === 'internal' ? 'is-active' : ''}" data-view="internal" style="
              display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 8px; font-size: 12.5px; font-weight: 750; border: none; cursor: pointer; transition: all 160ms ease;
              background: ${activeViewMode === 'internal' ? '#FFFFFF' : 'transparent'};
              color: ${activeViewMode === 'internal' ? 'var(--cmp-deep-primary, #5B2BBF)' : 'var(--cmp-text-secondary, #70677C)'};
              box-shadow: ${activeViewMode === 'internal' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none'};
            ">
              <i data-lucide="lock" style="width: 14px; height: 14px;"></i>
              <span>Protected Workforce Boundary</span>
            </button>
          </div>

          <!-- Hero Action Buttons -->
          <div style="display: flex; align-items: center; gap: 10px;">
            <button type="button" class="cmp-btn-secondary" id="cmpExportProfileBtn" style="height: 38px;">
              <i data-lucide="download"></i>
              <span>Export Dossier</span>
            </button>
            <button type="button" class="cmp-btn-primary" id="cmpEditProfileBtn" style="height: 38px;">
              <i data-lucide="edit-3"></i>
              <span>Edit Company Profile</span>
            </button>
          </div>
        </div>
      </section>

      <!-- 2. MAIN PROFILE CONTENT AREA -->
      <section class="cmp-section" style="margin-top: 24px;">
        ${activeViewMode === 'public' ? renderPublicProfile(p) : renderInternalBoundary(p, metrics)}
      </section>
    </div>
  `;
}

function renderPublicProfile(p) {
  return `
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <!-- Row 1: Illustrative Company Baseline & Infrastructure Examples -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;">
        <!-- Card 1: Enterprise Overview -->
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="cmp-card__icon"><i data-lucide="building-2"></i></span>
              <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--cmp-text-primary);">Enterprise Identity</h3>
            </div>
            <span class="cmp-badge cmp-badge--accent">Public Record</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 14px; font-size: 13px;">
            <div>
              <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase;">Legal Corporate Entity</span>
              <strong style="display: block; color: var(--cmp-text-primary); margin-top: 2px;">${esc(p.name)}</strong>
            </div>
            <div>
              <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase;">Industry Classification</span>
              <strong style="display: block; color: var(--cmp-text-primary); margin-top: 2px;">${esc(p.industry)}</strong>
            </div>
            <div>
              <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase;">Global Headquarters</span>
              <strong style="display: block; color: var(--cmp-text-primary); margin-top: 2px;">${esc(p.headquarters)}</strong>
            </div>
            <div>
              <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase;">Primary Global Hubs</span>
              <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                ${p.primaryHubs.map(hub => `
                  <span class="cmp-badge cmp-badge--subtle" style="font-size: 11.5px;">${esc(hub)}</span>
                `).join('')}
              </div>
            </div>
          </div>
        </div>

        <!-- Card 2: Strategic Tech Stack & Innovation Signals -->
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="cmp-card__icon"><i data-lucide="cpu"></i></span>
              <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--cmp-text-primary);">Core Technology Stacks</h3>
            </div>
            <span class="cmp-badge cmp-badge--success">Active Deployment</span>
          </div>

          <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0 0 14px; line-height: 1.45;">
            Illustrative production environment examples, hardware accelerators, and distributed model-serving stacks actively maintained.
          </p>

          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--cmp-very-light); border: 1px solid var(--cmp-border); border-radius: 10px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <i data-lucide="layers" style="color: var(--cmp-primary); width: 16px; height: 16px;"></i>
                <strong style="font-size: 13px; color: var(--cmp-text-primary);">Blackwell B200 &amp; DGX Cloud</strong>
              </div>
              <span class="cmp-badge cmp-badge--accent">Hardware Tier 1</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--cmp-very-light); border: 1px solid var(--cmp-border); border-radius: 10px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <i data-lucide="code-2" style="color: var(--cmp-primary); width: 16px; height: 16px;"></i>
                <strong style="font-size: 13px; color: var(--cmp-text-primary);">CUDA 12.4 &amp; TensorRT-LLM</strong>
              </div>
              <span class="cmp-badge cmp-badge--success">Core Acceleration</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--cmp-very-light); border: 1px solid var(--cmp-border); border-radius: 10px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <i data-lucide="boxes" style="color: var(--cmp-primary); width: 16px; height: 16px;"></i>
                <strong style="font-size: 13px; color: var(--cmp-text-primary);">vLLM, Megatron-LM &amp; Triton</strong>
              </div>
              <span class="cmp-badge cmp-badge--subtle">Inference Engines</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Row 2: Public Requisitions & Global Compliance Credentials -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;">
        <!-- Card 3: Public Hiring Requisitions -->
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="cmp-card__icon"><i data-lucide="briefcase"></i></span>
              <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--cmp-text-primary);">Active Talent Requisitions</h3>
            </div>
            <a href="#/company/workforce" class="cmp-btn-ghost cmp-btn-sm" style="font-size: 12px;">View Workforce</a>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div style="padding: 12px 14px; background: var(--cmp-very-light); border-radius: 10px; border: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 13.5px; color: var(--cmp-text-primary); display: block;">Senior AI Platform Engineer</strong>
                <span style="font-size: 12px; color: var(--cmp-text-secondary);">Autonomous Compute · Bangalore, India</span>
              </div>
              <span class="cmp-badge cmp-badge--accent">24 Openings</span>
            </div>
            <div style="padding: 12px 14px; background: var(--cmp-very-light); border-radius: 10px; border: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 13.5px; color: var(--cmp-text-primary); display: block;">Distributed Systems Architect</strong>
                <span style="font-size: 12px; color: var(--cmp-text-secondary);">Silicon Architecture · Santa Clara, CA</span>
              </div>
              <span class="cmp-badge cmp-badge--accent">18 Openings</span>
            </div>
            <div style="padding: 12px 14px; background: var(--cmp-very-light); border-radius: 10px; border: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 13.5px; color: var(--cmp-text-primary); display: block;">CUDA Kernel Optimization Lead</strong>
                <span style="font-size: 12px; color: var(--cmp-text-secondary);">Enterprise Software · Taipei / Remote</span>
              </div>
              <span class="cmp-badge cmp-badge--accent">12 Openings</span>
            </div>
          </div>
        </div>

        <!-- Card 4: Compliance & Institutional Certifications -->
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="cmp-card__icon"><i data-lucide="shield"></i></span>
              <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--cmp-text-primary);">Security &amp; Governance</h3>
            </div>
            <span class="cmp-badge cmp-badge--success">100% Compliant</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px; background: var(--cmp-very-light); border-radius: 10px; border: 1px solid var(--cmp-border);">
              <i data-lucide="check-circle-2" style="color: var(--cmp-success, #19B77A); width: 18px; height: 18px; margin-top: 2px; flex-shrink: 0;"></i>
              <div>
                <strong style="font-size: 13px; color: var(--cmp-text-primary); display: block;">SOC-2 Type II &amp; ISO 27001 Certified</strong>
                <p style="font-size: 12px; color: var(--cmp-text-secondary); margin: 2px 0 0;">Rigorous enterprise security and automated data isolation standards verified annually.</p>
              </div>
            </div>
            <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px; background: var(--cmp-very-light); border-radius: 10px; border: 1px solid var(--cmp-border);">
              <i data-lucide="check-circle-2" style="color: var(--cmp-success, #19B77A); width: 18px; height: 18px; margin-top: 2px; flex-shrink: 0;"></i>
              <div>
                <strong style="font-size: 13px; color: var(--cmp-text-primary); display: block;">Global Privacy (DPDP &amp; GDPR) Protected</strong>
                <p style="font-size: 12px; color: var(--cmp-text-secondary); margin: 2px 0 0;">All candidate and employee telemetry is hashed and protected by strict tenant isolation.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderInternalBoundary(p, metrics) {
  return `
    <div style="display: flex; flex-direction: column; gap: 20px;">
      <!-- Boundary Warning Banner -->
      <div style="background: rgba(135, 79, 255, 0.06); border: 1px solid var(--cmp-border-accent, #D8C7FF); border-radius: 14px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="width: 40px; height: 40px; border-radius: 10px; background: var(--cmp-light-primary, #F0E9FF); color: var(--cmp-deep-primary, #5B2BBF); display: flex; align-items: center; justify-content: center;">
            <i data-lucide="lock" style="width: 20px; height: 20px;"></i>
          </div>
          <div>
            <strong style="font-size: 14px; color: var(--cmp-text-primary, #241B32); display: block;">
              Protected Internal Workforce Boundary (RBAC Enforced)
            </strong>
            <p style="font-size: 12px; color: var(--cmp-text-secondary, #70677C); margin: 2px 0 0;">
              This intelligence is restricted to authorized Strategic Workforce Planning administrators and executive sponsors.
            </p>
          </div>
        </div>
        <span class="cmp-badge cmp-badge--accent" style="font-weight: 750;">Authorized Executive View</span>
      </div>

      <!-- Confidential Metrics Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;">
        <div class="cmp-card" style="padding: 18px;">
          <span style="font-size: 11px; font-weight: 800; color: var(--cmp-text-muted); text-transform: uppercase;">Internal Talent Pool</span>
          <div style="font-size: 26px; font-weight: 850; color: var(--cmp-text-primary); margin: 6px 0 2px;">
            ${p.globalHeadcount.toLocaleString()}
          </div>
          <span style="font-size: 12px; color: var(--cmp-text-secondary);">${p.engineeringHeadcount.toLocaleString()} in Core Engineering</span>
        </div>

        <div class="cmp-card" style="padding: 18px;">
          <span style="font-size: 11px; font-weight: 800; color: var(--cmp-text-muted); text-transform: uppercase;">Workforce Skill Health</span>
          <div style="font-size: 26px; font-weight: 850; color: var(--cmp-success, #19B77A); margin: 6px 0 2px;">
            ${metrics.workforceHealth.score}%
          </div>
          <span style="font-size: 12px; color: var(--cmp-text-secondary);">${metrics.workforceHealth.status}</span>
        </div>

        <div class="cmp-card" style="padding: 18px;">
          <span style="font-size: 11px; font-weight: 800; color: var(--cmp-text-muted); text-transform: uppercase;">Critical Skill Gap Ratio</span>
          <div style="font-size: 26px; font-weight: 850; color: var(--cmp-warning, #F59E0B); margin: 6px 0 2px;">
            ${metrics.criticalSkillGap.value}
          </div>
          <span style="font-size: 12px; color: var(--cmp-text-secondary);">${metrics.criticalSkillGap.headline}</span>
        </div>

        <div class="cmp-card" style="padding: 18px;">
          <span style="font-size: 11px; font-weight: 800; color: var(--cmp-text-muted); text-transform: uppercase;">Succession Pipeline</span>
          <div style="font-size: 26px; font-weight: 850; color: var(--cmp-primary, #874FFF); margin: 6px 0 2px;">
            74% L5+
          </div>
          <span style="font-size: 12px; color: var(--cmp-text-secondary);">Ready for immediate internal mobility</span>
        </div>
      </div>

      <!-- Confidential Organizational Allocations -->
      <div class="cmp-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="cmp-card__icon"><i data-lucide="git-pull-request"></i></span>
            <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: var(--cmp-text-primary);">Department Capability &amp; Mobility Allocations</h3>
          </div>
          <a href="#/company/mobility" class="cmp-btn-ghost cmp-btn-sm">Open Mobility Console</a>
        </div>

        <div class="cmp-table-container">
          <table class="cmp-table" style="font-size: 13px;">
            <thead>
              <tr>
                <th>Department / Unit</th>
                <th>Headcount</th>
                <th>Skill Health</th>
                <th>Mobility Readiness</th>
                <th>Critical Gap</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Autonomous Systems &amp; Compute</strong></td>
                <td>6,240</td>
                <td><span class="cmp-badge cmp-badge--success">91% Optimal</span></td>
                <td><span class="cmp-badge cmp-badge--accent">82% High</span></td>
                <td><span style="color: var(--cmp-text-muted);">FP4 Quantization</span></td>
              </tr>
              <tr>
                <td><strong>Silicon Architecture &amp; Fabrics</strong></td>
                <td>4,850</td>
                <td><span class="cmp-badge cmp-badge--success">88% Optimal</span></td>
                <td><span class="cmp-badge cmp-badge--accent">76% Medium</span></td>
                <td><span style="color: var(--cmp-text-muted);">Multi-Node NCCL</span></td>
              </tr>
              <tr>
                <td><strong>Enterprise Cloud &amp; DGX Operations</strong></td>
                <td>3,110</td>
                <td><span class="cmp-badge cmp-badge--accent">84% Adequate</span></td>
                <td><span class="cmp-badge cmp-badge--accent">68% Moderate</span></td>
                <td><span style="color: var(--cmp-text-muted);">Slurm &amp; KubeRay</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

export function bindCompanyProfileEvents(rerender) {
  // Tab switch
  document.querySelectorAll('.cmp-profile-view-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      activeViewMode = btn.dataset.view;
      if (typeof rerender === 'function') rerender();
    });
  });

  // Edit Company Profile Modal
  const editBtn = document.querySelector('#cmpEditProfileBtn');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      openCompanyProfileModal('overview', () => {
        if (typeof rerender === 'function') rerender();
      });
    });
  }

  // Export Dossier
  const exportBtn = document.querySelector('#cmpExportProfileBtn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      alert('Generating verified Organization Dossier for NVIDIA Enterprise Solutions (PDF)...');
    });
  }
}
