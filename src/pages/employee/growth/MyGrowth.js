// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE MY GROWTH
// Unified role evolution, promotion readiness & career pathway platform
// Dynamically adapts to Company-Invited Employee vs Independent Employee
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
  roleEvolutionData,
  careerPathsData,
  companySignals,
  employeeLearningTrack
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeMyGrowth() {
  const p = getEmployeeProfile();
  if (p.profileLoaded) {
    const list = values => Array.isArray(values) && values.length
      ? values.map(value => `<li>${esc(value)}</li>`).join('')
      : '<li>Not provided yet</li>';
    return `
      <div class="employee-page">
        <section class="emp-hero">
          <div class="emp-hero-content">
            <span class="emp-eyebrow"><i data-lucide="trending-up"></i> YOUR CAREER AND LEARNING CONTEXT</span>
            <h1 class="emp-hero-title">My Growth</h1>
            <p class="emp-hero-desc">This view uses your stated goals and available learning time. It does not imply verified promotion criteria or company-specific recommendations.</p>
          </div>
          <div class="emp-hero-actions"><a href="#/employee/skills" class="emp-btn-secondary">Review current skills</a></div>
        </section>
        <section class="emp-grid-4">
          <article class="emp-card"><span class="emp-badge emp-badge-primary">Career direction · self-reported</span><h2 class="emp-card-title">${esc(p.targetRole || 'Not provided yet')}</h2><p>Current role: ${esc(p.role || 'Not provided')}</p></article>
          <article class="emp-card"><span class="emp-badge emp-badge-primary">Weekly availability</span><h2 class="emp-card-title">${esc(p.weeklyLearningTime || 'Not provided yet')}</h2><p>Based on your onboarding response</p></article>
        </section>
        <section class="emp-grid-4">
          <article class="emp-card"><h2 class="emp-card-title">Development priorities</h2><ul>${list(p.growthPriorities)}</ul></article>
          <article class="emp-card"><h2 class="emp-card-title">Skills you want to build</h2><ul>${list(p.desiredSkills)}</ul></article>
          <article class="emp-card"><h2 class="emp-card-title">Preferred support</h2><ul>${list(p.preferredHelp)}</ul></article>
        </section>
      </div>
    `;
  }
  const isCompany = isCompanyEmployee();
  const evo = roleEvolutionData;
  const path = careerPathsData[0];
  const learning = employeeLearningTrack;

  return `
    <div class="employee-page">
      <!-- HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="${isCompany ? 'trending-up' : 'compass'}"></i>
            ${isCompany ? 'PROMOTION READINESS & COMPANY ALIGNMENT' : 'CAREER ADVANCEMENT & MARKET POSITIONING'}
          </span>
          <h1 class="emp-hero-title">
            ${isCompany ? `Growth Pathway to ${esc(p.targetRole)} (${esc(p.targetLevel)})` : `Career Pathway: ${esc(p.targetRole)}`}
          </h1>
          <p class="emp-hero-desc">
            ${isCompany 
              ? `Tracking internal promotion milestones, role evolution, and Blackwell architecture alignment at <strong>${esc(p.company)}</strong>.`
              : `Benchmarking your capabilities against global standards for <strong>${esc(p.targetRole)}</strong> in high-throughput distributed systems.`}
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
            CUDA Kernel optimization & NCCL cluster interconnect tuning.
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

        <!-- Milestones list -->
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
              <p class="emp-card-subtitle">Autonomous Systems & Inference Pipeline Delivery</p>
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
              <p class="emp-card-subtitle">Distributed GPU Architecture & Resilient Serving</p>
            </div>
            <div class="emp-icon-box"><i data-lucide="sparkles"></i></div>
          </div>
          <ul style="margin: 0; padding-left: 20px; font-size: 13.5px; color: var(--emp-text-primary); line-height: 1.7; display: flex; flex-direction: column; gap: 8px;">
            ${evo.emergingResponsibilities.map(r => `<li><strong>${esc(r)}</strong></li>`).join('')}
          </ul>
        </div>
      </section>

      <!-- ACTIVE LEARNING LAB (DLI TRACK) -->
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

export function bindEmployeeGrowthEvents(rerender) {
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
              Architectural Summary & Latency Reduction Metrics
              <textarea rows="3" placeholder="Explain the warp optimization, speedup achieved, and interconnect impact..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Milestone submitted for Director & Architecture Guild signoff!'); document.getElementById('empModalCloseBtn').click();">
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
              <strong style="color: var(--emp-text-primary); font-size: 14px;">1. System Impact & Scale</strong>
              <p style="margin: 4px 0 0;">Demonstrated ownership of high-throughput inference serving across 64+ node GPU clusters with 99.99% latency SLA adherence.</p>
            </div>
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <strong style="color: var(--emp-text-primary); font-size: 14px;">2. Low-Level Acceleration</strong>
              <p style="margin: 4px 0 0;">Ability to profile and optimize custom CUDA kernels, memory coalescing, and quantized FP4/FP8 compute pipelines.</p>
            </div>
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <strong style="color: var(--emp-text-primary); font-size: 14px;">3. Guild Leadership & Mentorship</strong>
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
