// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE MY GROWTH  (Learning & Progression Hub)
// Redesigned as an action-oriented dashboard with:
//   • Compact Career Context banner (replaces giant standalone cards)
//   • Skill-to-build pill badges with "Generate Roadmap" deep-links
//   • Active Learning Plans section wired to /api/v1/learning/roadmap/progress
//   • Development priorities styled with modern icon tags
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
  roleEvolutionData,
  careerPathsData,
  employeeLearningTrack
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderSkillBadges(skills, learningRoute) {
  if (!Array.isArray(skills) || !skills.length) {
    return `<span style="font-size:13px;color:var(--emp-text-muted);">No target skills recorded yet. Add skills in <a href="#/employee/skills" style="color:var(--emp-primary);">My Skills</a>.</span>`;
  }
  return skills.map(skill => {
    const encoded = encodeURIComponent(esc(skill));
    const href = `${learningRoute}?skill=${encoded}`;
    return `
      <span class="emp-growth-skill-badge" title="Generate a roadmap for ${esc(skill)}">
        <span class="emp-growth-skill-name">${esc(skill)}</span>
        <a class="emp-growth-roadmap-btn" href="${href}" aria-label="Generate roadmap for ${esc(skill)}">
          <i data-lucide="map" style="width:11px;height:11px;"></i>
          <span>Roadmap</span>
        </a>
      </span>`;
  }).join('');
}

function renderPriorityTags(priorities) {
  if (!Array.isArray(priorities) || !priorities.length) {
    return `<span style="font-size:13px;color:var(--emp-text-muted);">None recorded yet.</span>`;
  }
  const icons = ['target', 'trophy', 'zap', 'star', 'flag'];
  return priorities.map((p, i) => `
    <span class="emp-growth-priority-tag">
      <i data-lucide="${icons[i % icons.length]}" style="width:13px;height:13px;flex-shrink:0;"></i>
      ${esc(p)}
    </span>`).join('');
}

function renderPreferredHelp(items) {
  if (!Array.isArray(items) || !items.length) return '';
  return items.map(h => `<span class="emp-growth-support-tag">${esc(h)}</span>`).join('');
}

function renderActivePlanCard(plan, learningRoute = '#/employee/learning') {
  const pct = plan.progress_percent ?? 0;
  const total = plan.total_milestones ?? 0;
  const done = plan.completed_milestones ?? 0;
  const current = plan.current_milestone ?? 'Getting started…';
  const next = plan.next_milestone;
  const title = plan.title ?? 'Active Learning Plan';
  return `
    <div class="emp-growth-plan-card">
      <div class="emp-growth-plan-header">
        <div class="emp-icon-box emp-icon-box--primary" style="width:40px;height:40px;border-radius:12px;flex-shrink:0;">
          <i data-lucide="route"></i>
        </div>
        <div style="flex:1;min-width:0;">
          <div class="emp-growth-plan-title">${esc(title)}</div>
          ${plan.plan_goal ? `<div class="emp-growth-plan-goal">${esc(plan.plan_goal)}</div>` : ''}
        </div>
        <a href="${learningRoute}" class="emp-btn-primary emp-btn-sm" style="white-space:nowrap;">
          <i data-lucide="play" style="width:13px;height:13px;"></i>
          <span>Continue</span>
        </a>
      </div>

      <div class="emp-progress-bar" style="height:8px;margin:14px 0 10px;">
        <div class="emp-progress-fill" style="width:${pct}%;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <span style="font-size:12px;color:var(--emp-text-muted);">${done} of ${total} milestones complete</span>
        <span class="emp-badge emp-badge-primary" style="font-size:11px;">${pct}% done</span>
      </div>

      <div class="emp-growth-plan-milestones">
        <div class="emp-growth-ms-row emp-growth-ms-current">
          <div class="emp-growth-ms-dot emp-growth-ms-dot--active"></div>
          <div>
            <div style="font-size:11px;font-weight:700;color:var(--emp-primary);text-transform:uppercase;letter-spacing:.04em;">Current</div>
            <div style="font-size:13.5px;font-weight:650;color:var(--emp-text-primary);">${esc(current)}</div>
          </div>
        </div>
        ${next ? `
        <div class="emp-growth-ms-row" style="opacity:0.65;">
          <div class="emp-growth-ms-dot"></div>
          <div>
            <div style="font-size:11px;font-weight:700;color:var(--emp-text-muted);text-transform:uppercase;letter-spacing:.04em;">Up Next</div>
            <div style="font-size:13px;color:var(--emp-text-secondary);">${esc(next)}</div>
          </div>
        </div>` : ''}
      </div>
    </div>`;
}

function renderLoadingPlanCard() {
  return `
    <div class="emp-growth-plan-card" id="growthActivePlanContainer">
      <div style="display:flex;align-items:center;gap:12px;padding:12px 0;">
        <div class="emp-skeleton-shimmer" style="width:40px;height:40px;border-radius:12px;flex-shrink:0;"></div>
        <div style="flex:1;">
          <div class="emp-skeleton-shimmer" style="width:60%;height:16px;border-radius:6px;margin-bottom:8px;"></div>
          <div class="emp-skeleton-shimmer" style="width:40%;height:12px;border-radius:5px;"></div>
        </div>
      </div>
      <div class="emp-skeleton-shimmer" style="width:100%;height:8px;border-radius:4px;margin:14px 0 10px;"></div>
      <div class="emp-skeleton-shimmer" style="width:50%;height:12px;border-radius:4px;"></div>
    </div>`;
}

function renderEmptyPlanCard(learningRoute) {
  return `
    <div class="emp-growth-plan-card emp-growth-plan-card--empty" id="growthActivePlanContainer">
      <div class="emp-icon-box emp-icon-box--primary" style="width:44px;height:44px;border-radius:14px;margin:0 auto 14px;">
        <i data-lucide="map" style="width:22px;height:22px;"></i>
      </div>
      <h3 style="font-size:16px;font-weight:800;color:var(--emp-text-primary);text-align:center;margin:0 0 8px;">No Active Learning Plan</h3>
      <p style="font-size:13px;color:var(--emp-text-secondary);text-align:center;margin:0 0 18px;line-height:1.55;">
        Build a personalised roadmap from your target skills below — or explore the full Learning workspace.
      </p>
      <a href="${learningRoute}" class="emp-btn-primary" style="display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;">
        <i data-lucide="sparkles" style="width:14px;height:14px;"></i>
        <span>Create Your First Plan</span>
      </a>
    </div>`;
}

// ─── Main render: profile loaded ──────────────────────────────────────────────

function renderProfileGrowthHub(p) {
  const learningRoute = '#/employee/learning';
  const desiredSkills = Array.isArray(p.desiredSkills) ? p.desiredSkills : [];
  const growthPriorities = Array.isArray(p.growthPriorities) ? p.growthPriorities : [];
  const preferredHelp = Array.isArray(p.preferredHelp) ? p.preferredHelp : [];
  const targetRole = esc(p.targetRole || 'Not set yet');
  const currentRole = esc(p.role || 'Not provided');
  const weeklyTime = esc(p.weeklyLearningTime || 'Not set yet');

  return `
    <div class="employee-page">
      <!-- HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="trending-up"></i> LEARNING &amp; PROGRESSION HUB</span>
          <h1 class="emp-hero-title">My Growth</h1>
          <p class="emp-hero-desc">Your personalised learning roadmaps, development priorities, and career progression tracker.</p>
        </div>
        <div class="emp-hero-actions">
          <a href="${learningRoute}" class="emp-btn-primary">
            <i data-lucide="sparkles"></i>
            <span>Open Learning Workspace</span>
          </a>
          <a href="#/employee/skills" class="emp-btn-secondary">
            <i data-lucide="layers-3"></i>
            <span>My Skills</span>
          </a>
        </div>
      </section>

      <!-- CAREER CONTEXT BANNER -->
      <section class="emp-growth-context-banner">
        <div class="emp-growth-context-item">
          <span class="emp-growth-context-label"><i data-lucide="compass" style="width:13px;height:13px;"></i> Career Direction</span>
          <span class="emp-growth-context-value">${targetRole}</span>
          <span class="emp-growth-context-sub">from <strong>${currentRole}</strong></span>
        </div>
        <div class="emp-growth-context-divider"></div>
        <div class="emp-growth-context-item">
          <span class="emp-growth-context-label"><i data-lucide="clock" style="width:13px;height:13px;"></i> Weekly Availability</span>
          <span class="emp-growth-context-value">${weeklyTime}</span>
          <span class="emp-growth-context-sub">self-reported learning time</span>
        </div>
        ${preferredHelp.length ? `
        <div class="emp-growth-context-divider"></div>
        <div class="emp-growth-context-item" style="flex:2;min-width:0;">
          <span class="emp-growth-context-label"><i data-lucide="life-buoy" style="width:13px;height:13px;"></i> Preferred Support</span>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;">${renderPreferredHelp(preferredHelp)}</div>
        </div>` : ''}
      </section>

      <!-- 2-COLUMN HUB LAYOUT -->
      <div class="emp-growth-hub-layout">

        <!-- LEFT: Active Learning Plans -->
        <section class="emp-growth-panel">
          <div class="emp-growth-panel-header">
            <div>
              <span class="emp-eyebrow" style="font-size:11px;"><i data-lucide="route"></i> ACTIVE LEARNING PLANS</span>
              <h2 style="font-size:17px;font-weight:850;color:var(--emp-text-primary);margin:4px 0 0;">Current Curriculum</h2>
            </div>
            <a href="${learningRoute}" class="emp-btn-secondary emp-btn-sm">
              <i data-lucide="external-link" style="width:13px;height:13px;"></i>
              <span>Full Workspace</span>
            </a>
          </div>
          <!-- Plan card injected async -->
          <div id="growthActivePlanContainer">
            ${renderLoadingPlanCard()}
          </div>
        </section>

        <!-- RIGHT: Goals & Skills -->
        <div class="emp-growth-sidebar">

          <!-- Development Priorities -->
          <section class="emp-card emp-growth-card-section">
            <div class="emp-growth-section-head">
              <span class="emp-growth-section-icon emp-icon-box" style="background:#EEF1FF;width:32px;height:32px;border-radius:10px;">
                <i data-lucide="target" style="width:15px;height:15px;color:var(--emp-primary);"></i>
              </span>
              <div>
                <span style="font-size:11px;font-weight:700;color:var(--emp-text-muted);text-transform:uppercase;letter-spacing:.06em;">Focus Areas</span>
                <h3 style="font-size:15px;font-weight:800;color:var(--emp-text-primary);margin:2px 0 0;">Development Priorities</h3>
              </div>
            </div>
            <div class="emp-growth-priority-tags">
              ${renderPriorityTags(growthPriorities)}
            </div>
          </section>

          <!-- Skills to Build -->
          <section class="emp-card emp-growth-card-section">
            <div class="emp-growth-section-head">
              <span class="emp-growth-section-icon emp-icon-box" style="background:#E7F9F2;width:32px;height:32px;border-radius:10px;">
                <i data-lucide="book-open-check" style="width:15px;height:15px;color:var(--emp-success);"></i>
              </span>
              <div>
                <span style="font-size:11px;font-weight:700;color:var(--emp-text-muted);text-transform:uppercase;letter-spacing:.06em;">Actionable</span>
                <h3 style="font-size:15px;font-weight:800;color:var(--emp-text-primary);margin:2px 0 0;">Skills to Build</h3>
              </div>
            </div>
            <p style="font-size:12.5px;color:var(--emp-text-muted);margin:0 0 12px;line-height:1.5;">
              Click <strong>Roadmap</strong> on any skill to open the Learning Workspace with that skill pre-loaded.
            </p>
            <div class="emp-growth-skill-badges">
              ${renderSkillBadges(desiredSkills, learningRoute)}
            </div>
          </section>

        </div>
      </div>
    </div>
  `;
}

// ─── Main render: fallback (no profile loaded) ────────────────────────────────

function renderFallbackGrowthPage() {
  const isCompany = isCompanyEmployee();
  const evo = roleEvolutionData;
  const path = careerPathsData[0];
  const learning = employeeLearningTrack;
  const p = getEmployeeProfile();
  const learningRoute = '#/employee/learning';

  return `
    <div class="employee-page">
      <!-- HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="${isCompany ? 'trending-up' : 'compass'}"></i>
            ${isCompany ? 'PROMOTION READINESS &amp; COMPANY ALIGNMENT' : 'CAREER ADVANCEMENT &amp; MARKET POSITIONING'}
          </span>
          <h1 class="emp-hero-title">
            ${isCompany
              ? `Growth Pathway to ${esc(p.targetRole)} (${esc(p.targetLevel)})`
              : `Career Pathway: ${esc(p.targetRole)}`}
          </h1>
          <p class="emp-hero-desc">
            ${isCompany
              ? `Tracking internal promotion milestones and role evolution at <strong>${esc(p.company)}</strong>.`
              : `Benchmarking your capabilities against global standards for <strong>${esc(p.targetRole)}</strong>.`}
          </p>
        </div>
        <div class="emp-hero-actions">
          <button type="button" class="emp-btn-primary" id="btnSubmitMilestone">
            <i data-lucide="check-circle-2"></i>
            <span>${isCompany ? 'Submit Milestone Review' : 'Log Capability Proof'}</span>
          </button>
          <a href="#/employee/opportunities" class="emp-btn-secondary">
            <i data-lucide="briefcase"></i>
            <span>${isCompany ? 'Matched Internal Roles' : 'View Opportunities'}</span>
          </a>
        </div>
      </section>

      <!-- TOP 4 METRICS -->
      <div class="emp-grid-4">
        <div class="emp-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-primary">${isCompany ? 'Promotion Readiness' : 'Market Readiness'}</span>
              <h4 class="emp-card-title" style="margin-top: 6px;">Target Role Fit</h4>
            </div>
            <div class="emp-icon-box"><i data-lucide="award"></i></div>
          </div>
          <div class="emp-card-metric" style="color: var(--emp-primary);">${path.readinessScore}%</div>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
            ${isCompany ? '2 of 3 milestones verified for L5 elevation horizon.' : 'Matches 85% of market benchmarks for Lead ML Infra roles.'}
          </p>
        </div>

        <div class="emp-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-success">Trajectory</span>
              <h4 class="emp-card-title" style="margin-top: 6px;">Role Evolution</h4>
            </div>
            <div class="emp-icon-box emp-icon-box--success"><i data-lucide="git-pull-request"></i></div>
          </div>
          <div class="emp-card-metric" style="color: var(--emp-success); font-size: 22px; margin-top: 8px;">
            ${esc(evo.trajectoryState)}
          </div>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
            Shifting from standalone modeling to low-latency cluster inference.
          </p>
        </div>

        <div class="emp-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-warning">Capability Gaps</span>
              <h4 class="emp-card-title" style="margin-top: 6px;">Priority Actions</h4>
            </div>
            <div class="emp-icon-box emp-icon-box--warning"><i data-lucide="alert-circle"></i></div>
          </div>
          <div class="emp-card-metric" style="color: var(--emp-attention);">2 Focus Areas</div>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
            CUDA Kernel optimization &amp; NCCL cluster interconnect tuning.
          </p>
        </div>

        <div class="emp-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-primary">Active Learning</span>
              <h4 class="emp-card-title" style="margin-top: 6px;">Learning Track</h4>
            </div>
            <div class="emp-icon-box"><i data-lucide="book-open"></i></div>
          </div>
          <div class="emp-card-metric" style="color: var(--emp-primary);">${learning.progressPercent}%</div>
          <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0;">
            ${learning.completedModules} of ${learning.totalModules} modules completed in DLI track.
          </p>
        </div>
      </div>

      <!-- PROMOTION & MILESTONES ROADMAP -->
      <section class="emp-card" style="padding: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="calendar"></i> READINESS HORIZON</span>
            <h2 style="font-size: 18px; font-weight: 850; color: var(--emp-text-primary); margin: 4px 0 0;">
              ${isCompany ? `Milestone Progress toward ${esc(path.nextStage)}` : `Career Milestones for ${esc(p.targetRole)}`}
            </h2>
            <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 2px 0 0;">
              ${esc(path.timeframe)} · Target Scope: ${esc(path.growthExpectation)}
            </p>
          </div>
          <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnMilestoneCriteria">
            <i data-lucide="file-text"></i>
            <span>View Promotion Criteria</span>
          </button>
        </div>

        <div style="display: flex; flex-direction: column; gap: 12px;">
          ${path.keyMilestones.map((m, idx) => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 14px; gap: 16px; flex-wrap: wrap;">
              <div style="display: flex; align-items: center; gap: 14px;">
                <div style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; ${m.status === 'Completed' ? 'background: var(--emp-success-light); color: var(--emp-success); border: 1.5px solid var(--emp-success);' : 'background: #EEF1FF; color: var(--emp-primary); border: 1.5px solid var(--emp-primary);'}">
                  ${m.status === 'Completed' ? '✓' : idx + 1}
                </div>
                <div>
                  <div style="font-weight: 750; font-size: 14px; color: var(--emp-text-primary);">${esc(m.name)}</div>
                  <div style="font-size: 12px; color: var(--emp-text-muted);">Target Deadline: ${esc(m.deadline)}</div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                <span class="emp-badge ${m.status === 'Completed' ? 'emp-badge-success' : 'emp-badge-warning'}">
                  ${esc(m.status)}
                </span>
                ${m.status !== 'Completed' ? `
                  <button type="button" class="emp-btn-primary emp-btn-sm" onclick="alert('Milestone submission modal opened.');">
                    <span>Submit Proof</span>
                  </button>
                ` : `
                  <span style="font-size: 12px; color: var(--emp-success); font-weight: 650;"><i data-lucide="check-check"></i> Verified</span>
                `}
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- ROLE RESPONSIBILITIES: CURRENT VS TARGET -->
      <section class="emp-grid-2">
        <div class="emp-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-neutral">Current Level (${esc(p.level)})</span>
              <h3 class="emp-card-title" style="margin-top: 6px;">Current Role Scope</h3>
              <p class="emp-card-subtitle">Autonomous Systems &amp; Inference Pipeline Delivery</p>
            </div>
            <div class="emp-icon-box"><i data-lucide="check"></i></div>
          </div>
          <ul style="margin: 0; padding-left: 20px; font-size: 13.5px; color: var(--emp-text-secondary); line-height: 1.7; display: flex; flex-direction: column; gap: 8px;">
            ${evo.currentResponsibilities.map(r => `<li>${esc(r)}</li>`).join('')}
          </ul>
        </div>

        <div class="emp-card" style="border-color: rgba(39, 53, 245, 0.28); background: linear-gradient(180deg, #FFFFFF 0%, #F5F7FF 100%);">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-primary">Target Level (${esc(p.targetLevel || 'L5')})</span>
              <h3 class="emp-card-title" style="margin-top: 6px;">Emerging Senior Scope</h3>
              <p class="emp-card-subtitle">Distributed GPU Architecture &amp; Resilient Serving</p>
            </div>
            <div class="emp-icon-box"><i data-lucide="sparkles"></i></div>
          </div>
          <ul style="margin: 0; padding-left: 20px; font-size: 13.5px; color: var(--emp-text-primary); line-height: 1.7; display: flex; flex-direction: column; gap: 8px;">
            ${evo.emergingResponsibilities.map(r => `<li><strong>${esc(r)}</strong></li>`).join('')}
          </ul>
        </div>
      </section>

      <!-- ACTIVE LEARNING LAB -->
      <section class="emp-card" style="padding: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="book-marked"></i> GUIDED CAPABILITY LAB</span>
            <h2 style="font-size: 18px; font-weight: 850; color: var(--emp-text-primary); margin: 4px 0 0;">
              ${esc(learning.activeTrack)}
            </h2>
            <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 2px 0 0;">
              ${esc(learning.provider)} · ${esc(learning.estimatedTimeLeft)}
            </p>
          </div>
          <button type="button" class="emp-btn-primary" id="btnResumeLab">
            <i data-lucide="play"></i>
            <span>Resume Module 9</span>
          </button>
        </div>

        <div class="emp-progress-bar" style="height: 10px; margin-bottom: 16px;">
          <div class="emp-progress-fill" style="width: ${learning.progressPercent}%;"></div>
        </div>

        <div style="background: var(--emp-soft); padding: 16px; border-radius: 14px; border: 1px solid var(--emp-border-subtle); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
          <div>
            <div style="font-size: 12px; font-weight: 750; color: var(--emp-primary); text-transform: uppercase;">Next Up:</div>
            <div style="font-size: 14.5px; font-weight: 750; color: var(--emp-text-primary); margin-top: 2px;">
              ${esc(learning.nextModule)}
            </div>
            <div style="font-size: 12.5px; color: var(--emp-text-muted); margin-top: 2px;">
              Pass this module to earn the <strong>${esc(learning.certificationBadge)}</strong>.
            </div>
          </div>
          <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnLaunchLabSandbox">
            <i data-lucide="terminal"></i>
            <span>Launch GPU Sandbox</span>
          </button>
        </div>
      </section>
    </div>
  `;
}

// ─── Public API ────────────────────────────────────────────────────────────────

export function renderEmployeeMyGrowth() {
  const p = getEmployeeProfile();
  if (p.profileLoaded) {
    return renderProfileGrowthHub(p);
  }
  return renderFallbackGrowthPage();
}

export function bindEmployeeGrowthEvents(rerender) {
  // ── Profile-loaded path: async-fetch active learning plan ──
  const planContainer = document.getElementById('growthActivePlanContainer');
  if (planContainer) {
    const p = getEmployeeProfile();
    const learningRoute = '#/employee/learning';
    // Fetch progress from backend
    import('../../../api/roadmap-client.js').then(({ loadRoadmapProgress }) => {
      return loadRoadmapProgress();
    }).then(plan => {
      if (!document.getElementById('growthActivePlanContainer')) return;
      if (plan && plan.has_roadmap) {
        document.getElementById('growthActivePlanContainer').outerHTML = renderActivePlanCard(plan, learningRoute);
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      } else {
        document.getElementById('growthActivePlanContainer').outerHTML = renderEmptyPlanCard(learningRoute);
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }
    }).catch(() => {
      const el = document.getElementById('growthActivePlanContainer');
      if (el) {
        el.outerHTML = renderEmptyPlanCard(learningRoute);
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }
    });

    // Skill Roadmap deep-link clicks handled natively via href — no JS binding needed.
    return; // profile-loaded path exits here
  }

  // ── Fallback (mock) path ──

  // Submit milestone modal
  const submitBtn = document.querySelector('#btnSubmitMilestone');
  if (submitBtn) {
    submitBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Submit Promotion Milestone Proof',
        subtitle: 'Upload PR benchmark logs, architecture memos, or assessment completion',
        badge: 'L5 Evaluation',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Milestone to Verify
              <select style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;">
                <option>CUDA Kernel Certification (L5 Standard)</option>
                <option>Lead Multi-GPU Benchmarking Project (Completed)</option>
                <option>Internal Architecture Review Approval</option>
              </select>
            </label>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Evidence Link / Git Commit
              <input type="text" placeholder="https://internal-git.nvidia.com/pull/48291" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
            </label>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Architectural Summary &amp; Latency Reduction Metrics
              <textarea rows="3" placeholder="Explain the warp optimization, speedup achieved, and interconnect impact..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Milestone submitted for Director &amp; Architecture Guild signoff!'); document.getElementById('empModalCloseBtn').click();">
            <span>Submit for Review</span>
          </button>
        `
      });
    });
  }

  // View promotion criteria modal
  const criteriaBtn = document.querySelector('#btnMilestoneCriteria');
  if (criteriaBtn) {
    criteriaBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'L5 Senior AI Platform Engineer Criteria',
        subtitle: 'Official engineering evaluation rubric for technical elevation',
        badge: 'Competency Rubric',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px; font-size: 13.5px; color: var(--emp-text-secondary);">
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <strong style="color: var(--emp-text-primary); font-size: 14px;">1. System Impact &amp; Scale</strong>
              <p style="margin: 4px 0 0;">Demonstrated ownership of high-throughput inference serving across 64+ node GPU clusters with 99.99% latency SLA adherence.</p>
            </div>
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <strong style="color: var(--emp-text-primary); font-size: 14px;">2. Low-Level Acceleration</strong>
              <p style="margin: 4px 0 0;">Ability to profile and optimize custom CUDA kernels, memory coalescing, and quantized FP4/FP8 compute pipelines.</p>
            </div>
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <strong style="color: var(--emp-text-primary); font-size: 14px;">3. Guild Leadership &amp; Mentorship</strong>
              <p style="margin: 4px 0 0;">Active contribution to internal question banks, mock technical interview evaluations, and direct mentorship of at least 3 junior engineers.</p>
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-primary" onclick="document.getElementById('empModalCloseBtn').click()">
            <span>Understood</span>
          </button>
        `
      });
    });
  }

  // Resume lab
  const resumeBtn = document.querySelector('#btnResumeLab');
  if (resumeBtn) {
    resumeBtn.addEventListener('click', () => {
      alert('Launching NVIDIA DLI Enterprise Module 9: Cooperative Groups & WMMA Matrix Multiply...');
    });
  }

  // Sandbox launcher
  const sandboxBtn = document.querySelector('#btnLaunchLabSandbox');
  if (sandboxBtn) {
    sandboxBtn.addEventListener('click', () => {
      alert('Provisioning Blackwell B200 interactive profiling notebook session...');
    });
  }
}
