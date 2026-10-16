// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE HOME
// High-hierarchy, action-oriented overview with dynamic dual-state support
// ============================================================================

import {
  getEmployeeProfile,
  getEmployeeOverviewMetrics,
  isCompanyEmployee,
  toggleEmployeeType,
  companySignals,
  employeeSkillsData,
  questionBanksData,
  mockInterviewsData
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeHome() {
  const p = getEmployeeProfile();
  const metrics = getEmployeeOverviewMetrics();
  const isCompany = isCompanyEmployee();

  const primaryContextCard = `
    <div class="emp-card">
      <div class="emp-card-header">
        <div>
          <span class="emp-badge emp-badge-primary">${isCompany ? 'Company Context' : 'Market Context'}</span>
          <h3 class="emp-card-title" style="margin-top: 6px;">${esc(metrics.primaryContext.title)}</h3>
          <p class="emp-card-subtitle">${esc(metrics.primaryContext.headline)}</p>
        </div>
        <div class="emp-icon-box">
          <i data-lucide="${isCompany ? 'building-2' : 'globe'}"></i>
        </div>
      </div>
      <div class="emp-card-metric emp-card-metric--highlight">${esc(metrics.primaryContext.value)}</div>
      <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 16px; line-height: 1.45;">
        ${esc(metrics.primaryContext.summary)}
      </p>
      <div style="margin-top: auto; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--emp-border-subtle); padding-top: 14px;">
        <span class="emp-badge emp-badge-success"><i data-lucide="info"></i> Illustrative signal examples</span>
        <a href="#${metrics.primaryContext.route}" class="emp-btn-secondary emp-btn-sm">
          <span>${esc(metrics.primaryContext.actionLabel)}</span>
          <i data-lucide="arrow-right"></i>
        </a>
      </div>
    </div>
  `;

  const skillHealthCard = `
    <div class="emp-card">
      <div class="emp-card-header">
        <div>
          <span class="emp-badge emp-badge-success">Health Score</span>
          <h3 class="emp-card-title" style="margin-top: 6px;">${esc(metrics.skillHealth.title)}</h3>
          <p class="emp-card-subtitle">${esc(metrics.skillHealth.headline)}</p>
        </div>
        <div class="emp-icon-box emp-icon-box--success">
          <i data-lucide="activity"></i>
        </div>
      </div>
      <div class="emp-card-metric" style="color: var(--emp-success);">
        ${metrics.skillHealth.score} <span style="font-size: 14px; font-weight: 600; color: var(--emp-text-muted);">/ 100</span>
      </div>
      <div class="emp-progress-bar" style="margin-bottom: 12px;">
        <div class="emp-progress-fill emp-progress-fill--success" style="width: ${metrics.skillHealth.score}%;"></div>
      </div>
      <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 16px; line-height: 1.45;">
        ${esc(metrics.skillHealth.summary)}
      </p>
      <div style="margin-top: auto; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--emp-border-subtle); padding-top: 14px;">
        <span style="font-size: 12px; font-weight: 650; color: var(--emp-success);">${esc(metrics.skillHealth.trend)}</span>
        <a href="#/employee/skills" class="emp-btn-secondary emp-btn-sm">
          <span>Explore Skills</span>
          <i data-lucide="arrow-right"></i>
        </a>
      </div>
    </div>
  `;

  const readinessCard = `
    <div class="emp-card">
      <div class="emp-card-header">
        <div>
          <span class="emp-badge emp-badge-primary">${isCompany ? 'L5 Target' : 'Staff Target'}</span>
          <h3 class="emp-card-title" style="margin-top: 6px;">${esc(metrics.roleEvolution.title)}</h3>
          <p class="emp-card-subtitle">${esc(metrics.roleEvolution.headline)}</p>
        </div>
        <div class="emp-icon-box">
          <i data-lucide="trending-up"></i>
        </div>
      </div>
      <div class="emp-card-metric" style="color: var(--emp-primary);">
        ${metrics.roleEvolution.score}%
      </div>
      <div class="emp-progress-bar" style="margin-bottom: 12px;">
        <div class="emp-progress-fill" style="width: ${metrics.roleEvolution.score}%;"></div>
      </div>
      <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 16px; line-height: 1.45;">
        ${esc(metrics.roleEvolution.summary)}
      </p>
      <div style="margin-top: auto; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--emp-border-subtle); padding-top: 14px;">
        <span class="emp-badge emp-badge-neutral">${esc(metrics.roleEvolution.evolutionState)}</span>
        <a href="#/employee/growth" class="emp-btn-secondary emp-btn-sm">
          <span>View Growth</span>
          <i data-lucide="arrow-right"></i>
        </a>
      </div>
    </div>
  `;

  const nextActionCard = `
    <div class="emp-card" style="border-color: rgba(39, 53, 245, 0.28); background: linear-gradient(180deg, #FFFFFF 0%, #F5F7FF 100%);">
      <div class="emp-card-header">
        <div>
          <span class="emp-badge emp-badge-warning">Priority Action</span>
          <h3 class="emp-card-title" style="margin-top: 6px;">${esc(metrics.nextAction.title)}</h3>
          <p class="emp-card-subtitle">${esc(metrics.nextAction.primarySkill)}</p>
        </div>
        <div class="emp-icon-box emp-icon-box--warning">
          <i data-lucide="zap"></i>
        </div>
      </div>
      <div style="font-size: 16px; font-weight: 750; color: var(--emp-text-primary); margin: 6px 0 4px;">
        ${esc(metrics.nextAction.headline)}
      </div>
      <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 0 0 16px; line-height: 1.45;">
        ${esc(metrics.nextAction.summary)}
      </p>
      <div style="margin-top: auto; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid rgba(39, 53, 245, 0.12); padding-top: 14px;">
        <span style="font-size: 11.5px; color: var(--emp-text-muted);"><i data-lucide="clock"></i> ${esc(metrics.nextAction.eta)}</span>
        <button type="button" class="emp-btn-primary emp-btn-sm" id="btnHomeStartAction">
          <span>Start Action</span>
          <i data-lucide="arrow-right"></i>
        </button>
      </div>
    </div>
  `;

  // Signals to display based on state
  const signalsToRender = isCompany ? companySignals.slice(0, 3) : [
    {
      title: 'Decentralized High-Throughput Inference Architecture',
      change: '+38.5%',
      timeframe: 'Industry Shift',
      summary: 'Organizations are decoupling model training from low-latency edge inference clusters using Triton and vLLM.',
      whyItMatters: 'Requires proficiency in dynamic batching, paged attention, and asynchronous IPC streaming.',
      indicator: 'positive'
    },
    {
      title: 'GPU Kernel Optimization Demand across AI Startups',
      change: '+29.0%',
      timeframe: 'Ongoing Q3',
      summary: 'High demand for engineers capable of writing custom CUDA and Triton kernels for specialized attention layers.',
      whyItMatters: 'Direct match for your targeted Lead / Staff ML Infrastructure career progression.',
      indicator: 'positive'
    },
    {
      title: 'Standardization on Open Weights Foundation Models',
      change: '+45.2%',
      timeframe: 'Last 3 Months',
      summary: 'Enterprise adoption shifting toward self-hosted open foundation models with strict telemetry auditing.',
      whyItMatters: 'Positions your skills in quantization and evaluation benchmarks as high-value capabilities.',
      indicator: 'positive'
    }
  ];

  return `
    <div class="employee-page">
      <aside role="note" class="emp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">Employee portal preview: profile, skill, market and connection-mode examples on this page are illustrative local data. Backend membership status is authoritative in Company connection; the preview toggle does not change membership.</aside>
      <!-- DUAL-STATE BANNER & MODE TOGGLE -->
      <div class="emp-state-banner">
        <div class="emp-state-info">
          <span class="emp-state-pill ${isCompany ? 'emp-state-pill--company' : 'emp-state-pill--independent'}">
            <i data-lucide="${isCompany ? 'building-2' : 'user-check'}"></i>
            ${isCompany ? 'Company-Invited Employee · NVIDIA' : 'Independent Professional · Open Market'}
          </span>
          <span class="emp-state-meta">
            ${isCompany 
              ? `Connected to <strong>NVIDIA APAC</strong> · Manager: <strong>Priya Sundaram</strong>`
              : `Self-directed growth track · <strong>No company dependency</strong> · Open workforce`}
          </span>
        </div>
        <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnToggleEmployeeState" title="Switch employee profile state for demonstration">
          <i data-lucide="repeat"></i>
          <span>Switch to ${isCompany ? 'Independent Mode' : 'Company Mode'}</span>
        </button>
      </div>

      <!-- EMPLOYEE HERO SECTION -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="sparkles"></i>
            ${isCompany ? 'ENTERPRISE WORKFORCE & GROWTH CONSOLE' : 'INDEPENDENT CAREER & SKILLS CONSOLE'}
          </span>
          <h1 class="emp-hero-title">Good morning, ${esc(p.shortName)}</h1>
          <p class="emp-hero-desc">
            ${isCompany 
              ? `You are on track for <strong>${esc(p.targetRole)}</strong> in the ${esc(p.department)}. 2 of 3 milestones for Q3 promotion readiness are verified.`
              : `Your profile matches <strong>85%</strong> of market requisitions for <strong>${esc(p.targetRole)}</strong>. Deepen CUDA kernel profiling to bridge the final gap.`}
          </p>
        </div>
        <div class="emp-hero-actions">
          <a href="#/employee/growth" class="emp-btn-primary">
            <i data-lucide="trending-up"></i>
            <span>${isCompany ? 'View Promotion Readiness' : 'Explore Career Track'}</span>
          </a>
          <button type="button" class="emp-btn-ghost" id="btnQuickSkillAssess">
            <i data-lucide="check-circle-2"></i>
            <span>Verify Skill Evidence</span>
          </button>
        </div>
      </section>

      <!-- 4 PROGRESS OVERVIEW CARDS -->
      <section class="emp-grid-4">
        ${primaryContextCard}
        ${skillHealthCard}
        ${readinessCard}
        ${nextActionCard}
      </section>

      <!-- WHAT CHANGED? (Scannable, High-Contrast Intelligence) -->
      <section class="emp-card" style="padding: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="zap"></i> RECENT DEVELOPMENTS</span>
            <h2 style="font-size: 18px; font-weight: 800; color: var(--emp-text-primary); margin: 4px 0 0;">
              ${isCompany ? 'What Changed in My Company & Role?' : 'What Changed in the Technology Market?'}
            </h2>
          </div>
          <a href="#/employee/growth" class="emp-btn-ghost emp-btn-sm">
            <span>View All Shifts</span>
            <i data-lucide="arrow-right"></i>
          </a>
        </div>

        <div class="emp-grid-3">
          ${signalsToRender.map(sig => `
            <div style="background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 14px; padding: 18px; display: flex; flex-direction: column; gap: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="emp-badge emp-badge-primary">${esc(sig.timeframe)}</span>
                <strong style="color: var(--emp-success); font-size: 14px;">${esc(sig.change)}</strong>
              </div>
              <h4 style="font-size: 14.5px; font-weight: 750; color: var(--emp-text-primary); margin: 4px 0 0; line-height: 1.35;">
                ${esc(sig.title)}
              </h4>
              <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0; line-height: 1.45;">
                ${esc(sig.summary)}
              </p>
              <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid rgba(39, 53, 245, 0.08); font-size: 11.5px; color: var(--emp-primary); font-weight: 650;">
                <i data-lucide="arrow-right-circle"></i> Impact: ${esc(sig.whyItMatters)}
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- SKILL-TO-CONTRIBUTION PLATFORM (Mentorship, Question Banks & Reputation) -->
      <section class="emp-card" style="padding: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="award"></i> SKILL-TO-CONTRIBUTION PLATFORM</span>
            <h2 style="font-size: 18px; font-weight: 800; color: var(--emp-text-primary); margin: 4px 0 0;">
              Turn Verified Skills Into Knowledge & Reputation
            </h2>
            <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 2px 0 0;">
              Your expert proficiency in Python and PyTorch qualifies you to create assessments and mentor engineers.
            </p>
          </div>
          <a href="#/employee/community" class="emp-btn-primary emp-btn-sm">
            <span>Open Community Hub</span>
            <i data-lucide="arrow-right"></i>
          </a>
        </div>

        <!-- Reputation Banner -->
        <div class="emp-reputation-banner">
          <div style="display: flex; align-items: center; gap: 16px;">
            <div style="width: 52px; height: 52px; border-radius: 14px; background: rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 24px;">
              <i data-lucide="trophy"></i>
            </div>
            <div>
              <div style="font-size: 20px; font-weight: 850;">${p.reputationPoints.toLocaleString()} Reputation Points</div>
              <div style="font-size: 13px; opacity: 0.9;">Top 5% Technical Contributor · ${p.mentorStatus}</div>
            </div>
          </div>
          <div style="display: flex; gap: 14px; flex-wrap: wrap;">
            <div class="emp-stat-pill">
              <strong>${questionBanksData.filter(q => q.createdByMe).length} Banks</strong>
              <small>Authored by you</small>
            </div>
            <div class="emp-stat-pill">
              <strong>${mockInterviewsData.availableSlots.length} Slots</strong>
              <small>Mock interviews open</small>
            </div>
            <div class="emp-stat-pill">
              <strong>142</strong>
              <small>Learners assisted</small>
            </div>
            <div class="emp-stat-pill">
              <strong>4.9 / 5.0</strong>
              <small>Mentor rating</small>
            </div>
          </div>
        </div>

        <!-- Contribution Quick Actions -->
        <div class="emp-grid-3" style="margin-top: 18px;">
          <div class="emp-qb-card">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="emp-icon-box"><i data-lucide="file-question"></i></div>
              <div>
                <strong style="font-size: 14px; color: var(--emp-text-primary);">Question Bank Engine</strong>
                <div style="font-size: 12px; color: var(--emp-text-muted);">Python & PyTorch quizzes</div>
              </div>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">
              Your "Python Async Pipelines" assessment has 128 attempts with a 78% average score.
            </p>
            <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnHomeNewQuestion" style="margin-top: auto;">
              <i data-lucide="plus"></i>
              <span>Create New Question</span>
            </button>
          </div>

          <div class="emp-qb-card">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="emp-icon-box"><i data-lucide="video"></i></div>
              <div>
                <strong style="font-size: 14px; color: var(--emp-text-primary);">Mock Interview Hosting</strong>
                <div style="font-size: 12px; color: var(--emp-text-muted);">45 min technical sessions</div>
              </div>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">
              Offer practical mock interviews for junior peers preparing for L4 systems evaluations.
            </p>
            <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnHomeAddMockSlot" style="margin-top: auto;">
              <i data-lucide="calendar-plus"></i>
              <span>Add Interview Slot</span>
            </button>
          </div>

          <div class="emp-qb-card">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="emp-icon-box"><i data-lucide="users"></i></div>
              <div>
                <strong style="font-size: 14px; color: var(--emp-text-primary);">Peer Mentorship</strong>
                <div style="font-size: 12px; color: var(--emp-text-muted);">${p.menteesCount} active mentees</div>
              </div>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">
              1 session scheduled today at 4:30 PM with Kavita Nair (PyTorch DDP Profiling).
            </p>
            <a href="#/employee/community" class="emp-btn-secondary emp-btn-sm" style="margin-top: auto;">
              <i data-lucide="external-link"></i>
              <span>Manage Mentorship</span>
            </a>
          </div>
        </div>
      </section>
    </div>
  `;
}

export function bindEmployeeHomeEvents() {
  // 1. Dual-state toggle button
  const toggleBtn = document.querySelector('#btnToggleEmployeeState');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      toggleEmployeeType();
      // Re-trigger navigation & page render
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
  }

  // 2. Quick action modal
  const startActionBtn = document.querySelector('#btnHomeStartAction');
  if (startActionBtn) {
    startActionBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Start Learning Action: CUDA & NCCL Optimization',
        subtitle: 'Accelerated Deep Learning & Low-Latency GPU Kernel Profiling',
        badge: 'Recommended Growth Step',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <p>This module bridges your final gap toward <strong>Senior AI Platform Engineer (L5)</strong>.</p>
            <div style="background: var(--emp-soft); padding: 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <div style="font-weight: 700; color: var(--emp-text-primary); margin-bottom: 6px;">Curriculum Highlights:</div>
              <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: var(--emp-text-secondary); line-height: 1.6;">
                <li>Warp Divergence & Shared Memory Bank Conflicts</li>
                <li>NCCL All-Reduce Interconnect Optimization across NVLink</li>
                <li>FP4 / FP8 Precision Serving with TensorRT-LLM</li>
              </ul>
            </div>
            <div style="font-size: 13px; color: var(--emp-text-muted);">
              Estimated time: 3 weeks (self-paced, 4 hrs/week). Verified milestone badge issued upon passing practical kernel lab.
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <a href="#/employee/growth" class="emp-btn-primary" onclick="document.getElementById('empModalCloseBtn').click()">
            <i data-lucide="book-open"></i>
            <span>Launch Learning Path</span>
          </a>
        `
      });
    });
  }

  // 3. Quick skill verification modal
  const quickAssessBtn = document.querySelector('#btnQuickSkillAssess');
  if (quickAssessBtn) {
    quickAssessBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Verify Skill Capability & Evidence',
        subtitle: 'Submit code repositories, PRs, or take an automated technical assessment',
        badge: 'Verification Engine',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 16px;">
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; font-weight: 650; color: var(--emp-text-primary);">
              Select Capability to Verify
              <select style="padding: 10px 14px; border: 1px solid var(--emp-border); border-radius: 10px; font-size: 13.5px; background: #FFF;">
                <option>CUDA & GPU Optimization (Current Gap: 62%)</option>
                <option>Distributed Systems & NCCL (Current Gap: 54%)</option>
                <option>TensorRT Model Deployment (Current Fit: 86%)</option>
              </select>
            </label>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <div style="border: 1px solid var(--emp-border); border-radius: 12px; padding: 14px; cursor: pointer; background: var(--emp-soft);">
                <strong style="display: block; font-size: 13.5px; color: var(--emp-primary);">Take 20-min Quiz</strong>
                <small style="color: var(--emp-text-secondary); font-size: 12px;">Automated code challenge created by technical guild architects.</small>
              </div>
              <div style="border: 1px solid var(--emp-border); border-radius: 12px; padding: 14px; cursor: pointer; background: #FFF;">
                <strong style="display: block; font-size: 13.5px; color: var(--emp-text-primary);">Link GitHub / Internal PR</strong>
                <small style="color: var(--emp-text-secondary); font-size: 12px;">AI analyzes PR complexity, test coverage, and latency benchmarks.</small>
              </div>
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Close</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Verification test started. Directing to sandbox environment...'); document.getElementById('empModalCloseBtn').click();">
            <span>Start Verification</span>
          </button>
        `
      });
    });
  }

  // 4. Create new question modal
  const newQuestionBtn = document.querySelector('#btnHomeNewQuestion');
  if (newQuestionBtn) {
    newQuestionBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Create Assessment Question',
        subtitle: 'Contribute a question to the community question bank to earn reputation points',
        badge: '+25 Reputation Points',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Target Skill
              <select style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;">
                <option>Python & Async Systems</option>
                <option>PyTorch Deep Learning & DDP</option>
                <option>TensorRT & Model Deployment</option>
              </select>
            </label>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Question Title / Scenario
              <input type="text" placeholder="e.g. Profiling Memory Leaks in Shared IPC Ring Buffers" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
            </label>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Problem Details & Code Snippet
              <textarea rows="4" placeholder="Describe the debugging challenge or architecture trade-off..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Question submitted successfully to guild peer review!'); document.getElementById('empModalCloseBtn').click();">
            <span>Submit to Question Bank</span>
          </button>
        `
      });
    });
  }

  // 5. Add mock slot modal
  const addMockSlotBtn = document.querySelector('#btnHomeAddMockSlot');
  if (addMockSlotBtn) {
    addMockSlotBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Open Mock Technical Interview Slot',
        subtitle: 'Make yourself available to conduct a peer technical mock interview',
        badge: 'Peer Coaching',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Interview Focus Area
              <select style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;">
                <option>Distributed ML Architecture & Inference</option>
                <option>Python Concurrency & Async Optimization</option>
                <option>PyTorch Dynamic Graph Profiling</option>
              </select>
            </label>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
                Date
                <input type="date" value="2026-09-30" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
              </label>
              <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
                Time Slot
                <input type="text" value="5:00 PM — 5:45 PM IST" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
              </label>
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Mock interview slot published to guild calendar!'); document.getElementById('empModalCloseBtn').click();">
            <span>Publish Slot</span>
          </button>
        `
      });
    });
  }
}
