import { dashboardState } from '../../../app/state.js';
import { getCanonicalQuestionBanks, submitAssessmentAttempt } from '../../../data/platform-state.js';
import {
  ROADMAP_PRESETS,
  loadLearningRoadmapState,
  saveLearningRoadmapState,
  calculateRoadmapProgress
} from '../../../data/roadmap-data.js';


// Local UI state for filters, search, accordion, modals
let ui = {
  roadmap: null,
  activeResourceFilter: 'All',
  resourceSearchQuery: '',
  expandedMilestoneId: 'ms-assessment',
  activePlannerTab: 'Today',
  activePracticeFilter: 'All',
  actionNotification: null
};

function ensureRoadmapLoaded() {
  if (!ui.roadmap) {
    ui.roadmap = loadLearningRoadmapState();
  }
  // Check if a specific milestone was selected from Home page or external navigation
  const navMilestone = sessionStorage.getItem('talentscope-selected-milestone');
  if (navMilestone) {
    if (ui.roadmap && Array.isArray(ui.roadmap.milestones)) {
      const match = ui.roadmap.milestones.find(m => m.id === navMilestone || (m.name && m.name.toLowerCase() === navMilestone.toLowerCase()));
      ui.expandedMilestoneId = match ? match.id : navMilestone;
    } else {
      ui.expandedMilestoneId = navMilestone;
    }
    sessionStorage.removeItem('talentscope-selected-milestone');
  } else if (ui.roadmap && ui.roadmap.milestones) {
    const currentMs = ui.roadmap.milestones.find(m => m.status === 'current');
    if (currentMs && !ui.expandedMilestoneId) {
      ui.expandedMilestoneId = currentMs.id;
    }
  }
}

function persistState() {
  if (ui.roadmap) {
    ui.roadmap.progress = calculateRoadmapProgress(ui.roadmap);
    saveLearningRoadmapState(ui.roadmap);
  }
}

// ----------------------------------------------------------------------------
// HTML Renderers
// ----------------------------------------------------------------------------

function renderHeaderHTML() {
  const isCompleted = ui.roadmap?.status === 'completed';
  const isEmpty = ui.roadmap?.status === 'none' || ui.roadmap?.status === 'empty';
  const currentGoal = ui.roadmap?.goalType || 'Improve Skill';

  return `
    <header class="lp-page-heading">
      <div class="lp-heading-left">
        <span class="lp-eyebrow">
          <i data-lucide="book-open" style="width:14px; height:14px;"></i> PERSONAL LEARNING
        </span>
        <div class="lp-title-row">
          <h1 class="lp-page-title">Learning</h1>
          <span class="lp-demo-badge">
            <span class="pulse-dot"></span> Active Workspace
          </span>
        </div>
        <p class="lp-page-subtitle">
          Follow your roadmap, build your skills, track your progress, and prepare for your next goal.
        </p>
      </div>

      <div class="lp-heading-actions">
        <select class="lp-hero-simulator-select" id="lpGoalTypeSelect" title="Switch roadmap goal type">
          <option value="Improve Skill" ${currentGoal === 'Improve Skill' ? 'selected' : ''}>Goal: Improve Skill (Python Backend)</option>
          <option value="Learn Skill" ${currentGoal === 'Learn Skill' ? 'selected' : ''}>Goal: Learn Skill (Zero to Mastery)</option>
          <option value="Job Preparation" ${currentGoal === 'Job Preparation' ? 'selected' : ''}>Goal: Job Prep (AI Engineer)</option>
          <option value="Company Preparation" ${currentGoal === 'Company Preparation' ? 'selected' : ''}>Goal: Company Prep (NVIDIA Systems)</option>
        </select>

        ${!isEmpty ? `
          <button type="button" class="lp-btn-outline" id="lpSimulateCompleteBtn" title="Test 100% completion state">
            <i data-lucide="award" style="width:14px; height:14px;"></i> Simulate 100%
          </button>
          <button type="button" class="lp-btn-outline" id="lpSimulateEmptyBtn" title="Test empty / no active roadmap state">
            <i data-lucide="trash-2" style="width:14px; height:14px;"></i> Clear Roadmap
          </button>
        ` : `
          <button type="button" class="lp-btn-primary" id="lpRestoreRoadmapBtn">
            <i data-lucide="plus-circle" style="width:14px; height:14px;"></i> Activate Roadmap
          </button>
        `}
      </div>
    </header>
  `;
}

function renderEmptyStateHTML() {
  return `
    <section class="lp-empty-state-card" id="lpEmptyStateSection">
      <div class="lp-empty-icon-ring">
        <i data-lucide="compass"></i>
      </div>
      <div class="lp-empty-content">
        <span class="lp-empty-kicker">READY TO BUILD YOUR NEXT SKILL?</span>
        <h2 class="lp-empty-title">You Have No Active Roadmap</h2>
        <p class="lp-empty-desc">
          Explore a skill or career opportunity and create a personalized roadmap based on your current level, target competency, and career goal.
        </p>
      </div>
      <div class="lp-empty-actions">
        <a class="lp-btn-primary" href="#/individual/skills">
          <i data-lucide="layers-3" style="width:16px; height:16px;"></i> Explore Skills
        </a>
        <a class="lp-btn-secondary" href="#/individual/career">
          <i data-lucide="briefcase-business" style="width:16px; height:16px;"></i> Explore Career
        </a>
      </div>

      <div class="lp-preset-launch-strip">
        <span class="lp-preset-launch-title">Quick Start a Personalized Roadmap:</span>
        <button type="button" class="lp-btn-outline lp-btn-sm" data-quick-preset="Improve Skill">
          <i data-lucide="sparkles" style="width:14px; height:14px;"></i> Python Backend Advancement
        </button>
        <button type="button" class="lp-btn-outline lp-btn-sm" data-quick-preset="Job Preparation">
          <i data-lucide="cpu" style="width:14px; height:14px;"></i> AI Engineer Role Prep
        </button>
        <button type="button" class="lp-btn-outline lp-btn-sm" data-quick-preset="Company Preparation">
          <i data-lucide="building-2" style="width:14px; height:14px;"></i> NVIDIA CUDA Prep
        </button>
        <button type="button" class="lp-btn-outline lp-btn-sm" data-quick-preset="Learn Skill">
          <i data-lucide="book-marked" style="width:14px; height:14px;"></i> Python Zero to Mastery
        </button>
      </div>
    </section>
  `;
}

function renderCompletedStateHTML(roadmap) {
  return `
    <section class="lp-completed-state-card" id="lpCompletedStateSection">
      <div class="lp-completed-header">
        <div class="lp-completed-title-wrap">
          <span class="lp-completed-kicker">
            <i data-lucide="check-check" style="width:16px; height:16px;"></i> ROADMAP COMPLETED
          </span>
          <h2 class="lp-completed-title">${roadmap.title || 'Roadmap'} — 100% Verified</h2>
          <p class="lp-completed-sub">
            You have successfully satisfied all required milestones, assessments, and capstone criteria for this roadmap goal.
          </p>
        </div>
        <div class="lp-progress-huge" style="color: #4ADE80;">100%</div>
      </div>

      <div class="lp-completed-checklist">
        <div class="lp-completed-check-item">
          <i data-lucide="check-circle-2"></i> Skill Development ✓
        </div>
        <div class="lp-completed-check-item">
          <i data-lucide="check-circle-2"></i> Technical Assessment ✓
        </div>
        <div class="lp-completed-check-item">
          <i data-lucide="check-circle-2"></i> Real-world project ✓
        </div>
        <div class="lp-completed-check-item">
          <i data-lucide="check-circle-2"></i> Target Competency / Prep ✓
        </div>
      </div>

      <div class="lp-completed-actions">
        <button type="button" class="lp-btn-primary" id="lpViewResultsBtn">
          <i data-lucide="file-check" style="width:16px; height:16px;"></i> View Verification Results
        </button>
        <a class="lp-btn-secondary" href="#/individual/skills" style="background: rgba(255,255,255,0.05); color:#FFF !important; border-color: rgba(255,255,255,0.3);">
          <i data-lucide="compass" style="width:16px; height:16px;"></i> Explore Next Skill
        </a>
        <button type="button" class="lp-btn-outline" id="lpRestartRoadmapBtn" style="color:#FFF; border-color: rgba(255,255,255,0.3);">
          <i data-lucide="rotate-ccw" style="width:14px; height:14px;"></i> Reset progress
        </button>
      </div>
    </section>
  `;
}

function renderActiveHeroHTML(roadmap) {
  const progress = roadmap.progress || 64;
  const goalType = roadmap.goalType || 'Improve Skill';
  const currentStep = roadmap.currentStep || { name: 'Assessment', detail: 'Technical Benchmark' };
  const nextStep = roadmap.nextStep || { name: 'Real-world project', detail: 'Capstone build' };
  const remainingWork = roadmap.estimatedRemainingWork || '4 milestones remaining';

  return `
    <section class="lp-hero-card lp-glass-card" id="lpActiveHeroSection" aria-label="Active Roadmap">
      <div class="lp-hero-top">
        <div class="lp-hero-identity">
          <div class="lp-hero-icon-box">
            <i data-lucide="route"></i>
          </div>
          <div class="lp-hero-info">
            <div class="lp-hero-meta-row">
              <span class="lp-pill-goal">${goalType}</span>
              <span class="lp-pill-status"><span class="pulse-dot"></span> In progress</span>
              ${roadmap.targetCompany ? `<span class="lp-pill-target"><i data-lucide="building" style="width:14px; height:14px;"></i> ${roadmap.targetCompany}</span>` : ''}
              ${roadmap.targetRole ? `<span class="lp-pill-target"><i data-lucide="briefcase" style="width:14px; height:14px;"></i> ${roadmap.targetRole}</span>` : ''}
            </div>
            <h2 class="lp-hero-title">${roadmap.title || 'Skill Roadmap'}</h2>
            <p class="lp-hero-summary">${roadmap.summary || 'Follow your structured curriculum, build capabilities and verify readiness.'}</p>
          </div>
        </div>

        <div class="lp-hero-progress-block">
          <div class="lp-progress-huge">${progress}%</div>
          <span class="lp-progress-label">Roadmap progress</span>
          <span class="lp-progress-est">${remainingWork}</span>
        </div>
      </div>

      <div class="lp-progress-track" role="progressbar" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
        <div class="lp-progress-fill" style="width: ${progress}%;"></div>
      </div>

      <div class="lp-hero-bottom">
        <div class="lp-hero-steps-preview">
          <div class="lp-step-mini-item">
            <span class="lp-step-mini-kicker">
              <i data-lucide="play" style="width:14px; height:14px; color:var(--lp-purple);"></i> CURRENT MILESTONE
            </span>
            <span class="lp-step-mini-title">${currentStep.name}</span>
          </div>

          <div class="lp-step-mini-item">
            <span class="lp-step-mini-kicker">
              <i data-lucide="arrow-right-circle" style="width:14px; height:14px;"></i> UP NEXT
            </span>
            <span class="lp-step-mini-title">${nextStep.name}</span>
          </div>
        </div>

        <div class="lp-hero-cta-group">
          <button type="button" class="lp-btn-primary" id="lpHeroContinueBtn">
            <i data-lucide="play" style="width:14px; height:14px;"></i> Continue Learning
          </button>
          <a class="lp-btn-secondary" href="#lpTimelineSection">
            <i data-lucide="list-tree" style="width:14px; height:14px;"></i> View Full Roadmap
          </a>
        </div>
      </div>
    </section>
  `;
}

function renderOverviewMetricsHTML(roadmap) {
  const milestones = roadmap.milestones || [];
  let totalTopics = 0;
  let completedTopics = 0;

  milestones.forEach(m => {
    (m.topics || []).forEach(t => {
      totalTopics++;
      if (t.status === 'completed' || t.progress === 100) completedTopics++;
    });
  });

  const streakDays = roadmap.streakDays || 7;
  const learningHours = roadmap.learningTimeHours || 12.4;

  const assessments = roadmap.assessments || [];
  let avgScore = 82;
  if (assessments.length > 0) {
    const totalScore = assessments.reduce((sum, a) => sum + (a.score || 0), 0);
    avgScore = Math.round(totalScore / assessments.length);
  }

  const projects = roadmap.projects || [];
  const completedProjects = projects.filter(p => p.status === 'completed').length;
  const totalProjects = Math.max(0, projects.length);

  return `
    <section class="lp-overview-section" aria-label="Learning Metrics">
      <div class="lp-overview-grid">
        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="percent"></i></div>
            <span class="lp-metric-sub">Target Goal</span>
          </div>
          <div class="lp-metric-value">${roadmap.progress || 64}%</div>
          <div class="lp-metric-label">Roadmap progress</div>
        </div>

        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="check-square"></i></div>
            <span class="lp-metric-sub">Curriculum</span>
          </div>
          <div class="lp-metric-value">${completedTopics || 18} / ${totalTopics || 28}</div>
          <div class="lp-metric-label">Topics Complete</div>
        </div>

        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="flame" style="color:var(--lp-attention);"></i></div>
            <span class="lp-metric-sub">Consistency</span>
          </div>
          <div class="lp-metric-value">${streakDays} days</div>
          <div class="lp-metric-label">Current Streak</div>
        </div>

        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="award"></i></div>
            <span class="lp-metric-sub">Evaluations</span>
          </div>
          <div class="lp-metric-value">${avgScore}%</div>
          <div class="lp-metric-label">Assessment Average</div>
        </div>

        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="folder-git-2"></i></div>
            <span class="lp-metric-sub">rortfolio</span>
          </div>
          <div class="lp-metric-value">${completedProjects} / ${totalProjects}</div>
          <div class="lp-metric-label">projects Complete</div>
        </div>

        <div class="lp-metric-card">
          <div class="lp-metric-top">
            <div class="lp-metric-icon"><i data-lucide="clock"></i></div>
            <span class="lp-metric-sub">Total Invested</span>
          </div>
          <div class="lp-metric-value">${learningHours}h</div>
          <div class="lp-metric-label">Learning Time</div>
        </div>
      </div>
    </section>
  `;
}

function renderContinueAndSmartNextHTML(roadmap) {
  const currentStep = roadmap.currentStep || {
    name: 'High-Concurrency Runtime Benchmark',
    detail: 'Technical Benchmark · 12/20 completed',
    progress: 68,
    estimatedMinutes: 35,
    description: 'Validate concurrency patterns, async exception boundaries, and async task orchestration.',
    prerequisites: 'AsyncIO Event Loop Mechanics completed'
  };

  const smartNext = roadmap.smartNextAction || {
    title: 'Review Exception Handling & Error Boundaries',
    reason: 'Recent assessment score identified Error Handling (69%) as needing reinforcement before capstone delivery.',
    badgeText: 'SMART RECOMMENDATION',
    actionLabel: 'Review Topic Now',
    actionType: 'review-topic',
    targetId: 'top-py-error-review'
  };

  const nextStep = roadmap.nextStep || {
    name: 'Real-world project: FastAPI Microservice Engine',
    detail: 'Capstone build · 2 production targets queued'
  };

  return `
    <section class="lp-current-action-layout" id="lpCurrentStepSection">
      <!-- CURRENT LEARNING TOPIC (STEP 07, 44) -->
      <div class="lp-current-step-card lp-surface-card">
        <div class="lp-step-card-header">
          <span class="lp-step-card-badge">
            <i data-lucide="play" style="width:14px; height:14px;"></i> CURRENT LEARNING FOCUS
          </span>
        </div>

        <h3 class="lp-step-card-title">${currentStep.name}</h3>
        <p class="lp-step-card-desc">${currentStep.description || 'Deepen your mastery through targeted resources, practical implementation, and benchmark testing.'}</p>

        <div class="lp-step-meta-chips">
          <span class="lp-step-chip">
            <i data-lucide="clock"></i> Est. ${currentStep.estimatedMinutes || 35} min
          </span>
          <span class="lp-step-chip">
            <i data-lucide="bar-chart-2"></i> ${currentStep.progress || 68}% complete
          </span>
          ${currentStep.prerequisites ? `
            <span class="lp-step-chip">
              <i data-lucide="shield-check"></i> prerequisite: ${currentStep.prerequisites}
            </span>
          ` : ''}
        </div>

        <div class="lp-step-actions-row">
          <button type="button" class="lp-btn-primary" id="lpActionContinueStepBtn">
            <i data-lucide="arrow-right"></i> Continue Learning
          </button>
          <button type="button" class="lp-btn-secondary" id="lpActionMarkStepDoneBtn">
            <i data-lucide="check"></i> Mark Complete
          </button>
          <a class="lp-btn-outline" href="#lpPracticeSection">
            <i data-lucide="terminal"></i> practice Now
          </a>
        </div>
      </div>

      <!-- SMART NEXT ACTION (STEP 45, 46) -->
      <div class="lp-smart-next-box lp-glass-card">
        <div class="lp-smart-badge">
          <i data-lucide="sparkles" style="width:14px; height:14px;"></i> ${smartNext.badgeText || 'NEXT BEST ACTION'}
        </div>
        <h3 class="lp-smart-title">${smartNext.title}</h3>
        <p class="lp-smart-reason">${smartNext.reason}</p>

        <div class="lp-smart-upnext">
          <span class="lp-smart-upnext-kicker">UP NEXT IN QUEUE</span>
          <span class="lp-smart-upnext-title">${nextStep.name}</span>
        </div>

        <div style="margin-top: auto;">
          <button type="button" class="lp-btn-primary" id="lpSmartActionTriggerBtn" style="width: 100%;">
            ${smartNext.actionLabel || 'Take Action'} <i data-lucide="arrow-right" style="width:14px; height:14px;"></i>
          </button>
        </div>
      </div>
    </section>
  `;
}

function renderRoadmapTimelineHTML(roadmap) {
  const milestones = roadmap.milestones || [];

  return `
    <section class="lp-timeline-section" id="lpTimelineSection" aria-label="Roadmap Execution Area">
      <div class="lp-section-header">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">ROADMAP EXECUTION</span>
          <h2 class="lp-section-title">
            <i data-lucide="route" style="color:var(--lp-purple); width:20px; height:20px;"></i>
            Structured Milestone Timeline
          </h2>
          <p class="lp-section-desc">Click any milestone to inspect individual topics, complete learning units, and track verification.</p>
        </div>
      </div>

      <div class="lp-timeline-container">
        ${milestones.map((m, index) => {
          const isOpen = ui.expandedMilestoneId === m.id || (Boolean(ui.expandedMilestoneId && m.name) && String(ui.expandedMilestoneId).toLowerCase() === String(m.name).toLowerCase());
          const statusClass = m.status || 'upcoming';
          const topics = m.topics || [];

          return `
            <div class="lp-milestone-accordion ${isOpen ? 'is-open' : ''} is-${statusClass}" data-milestone-id="${m.id}">
              <div class="lp-milestone-header" data-toggle-milestone="${m.id}" role="button" aria-expanded="${isOpen}">
                <div class="lp-milestone-left">
                  <div class="lp-milestone-icon-indicator ${statusClass}">
                    ${statusClass === 'completed' ? '<i data-lucide="check" style="width:16px; height:16px;"></i>' : (statusClass === 'current' ? '<i data-lucide="play" style="width:14px; height:14px;"></i>' : (index + 1))}
                  </div>
                  <div class="lp-milestone-title-col">
                    <h3 class="lp-milestone-name">${m.name}</h3>
                    <p class="lp-milestone-desc">${m.description || m.label}</p>
                  </div>
                </div>

                <div class="lp-milestone-right">
                  <span class="lp-milestone-progress-pill ${statusClass}">
                    ${statusClass === 'completed' ? 'Completed 100%' : (statusClass === 'current' ? `${m.progress || 68}% In progress` : 'Upcoming')}
                  </span>
                  <i data-lucide="chevron-down" class="lp-accordion-caret" style="width:18px; height:18px;"></i>
                </div>
              </div>

              ${isOpen ? `
                <div class="lp-milestone-body">
                  <div class="lp-topics-list">
                    ${topics.map(t => {
                      const isDone = t.status === 'completed' || t.progress === 100;
                      const isNeedsReview = t.status === 'needs-review';
                      const isCurrent = t.status === 'in-progress';

                      return `
                        <div class="lp-topic-row" id="topic-row-${t.id}">
                          <div class="lp-topic-left">
                            <button type="button" class="lp-topic-checkbox ${isDone ? 'completed' : (isNeedsReview ? 'needs-review' : (isCurrent ? 'current' : ''))}"
                                    data-toggle-topic="${t.id}" title="Toggle topic status">
                              ${isDone ? '<i data-lucide="check" style="width:14px; height:14px;"></i>' : (isNeedsReview ? '<i data-lucide="alert-circle" style="width:14px; height:14px;"></i>' : '')}
                            </button>
                            <div class="lp-topic-title-wrap">
                              <h4 class="lp-topic-title">${t.title}</h4>
                            </div>
                          </div>

                          <div class="lp-topic-right">
                            <span class="lp-step-chip" style="font-size:11px;">
                              <i data-lucide="clock" style="width:14px; height:14px;"></i> ${t.estimatedMinutes || 40} min
                            </span>
                            <span class="lp-topic-status-tag ${t.status || 'not-started'}">
                              ${isDone ? 'Completed' : (isNeedsReview ? 'Needs Review' : (isCurrent ? 'In progress' : 'Upcoming'))}
                            </span>
                          </div>
                        </div>
                      `;
                    }).join('')}
                  </div>
                </div>
              ` : ''}
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function renderResourcesHTML(roadmap) {
  const resources = roadmap.resources || [];
  const filters = ['All', 'Documentation', 'Articles', 'Videos', 'practice', 'Saved', 'Completed'];

  let filtered = resources;
  if (ui.activeResourceFilter !== 'All') {
    const f = ui.activeResourceFilter.toLowerCase();
    if (f === 'saved') {
      filtered = filtered.filter(r => r.saved);
    } else if (f === 'completed') {
      filtered = filtered.filter(r => r.status === 'completed');
    } else if (f === 'documentation') {
      filtered = filtered.filter(r => r.type === 'documentation');
    } else if (f === 'articles') {
      filtered = filtered.filter(r => r.type === 'article');
    } else if (f === 'videos') {
      filtered = filtered.filter(r => r.type === 'video');
    } else if (f === 'practice') {
      filtered = filtered.filter(r => r.type === 'practice');
    }
  }

  if (ui.resourceSearchQuery) {
    const q = ui.resourceSearchQuery.toLowerCase();
    filtered = filtered.filter(r =>
      r.title.toLowerCase().includes(q) ||
      (r.source && r.source.toLowerCase().includes(q)) ||
      (r.topicTitle && r.topicTitle.toLowerCase().includes(q))
    );
  }

  const iconMap = {
    documentation: 'file-text',
    article: 'newspaper',
    video: 'video',
    tutorial: 'graduation-cap',
    practice: 'terminal',
    project: 'folder-git-2'
  };

  return `
    <section class="lp-resources-section" id="lpResourcesSection" aria-label="Learning Resources">
      <div class="lp-section-header">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">CURATED MATERIALS</span>
          <h2 class="lp-section-title">
            <i data-lucide="library" style="color:var(--lp-purple); width:20px; height:20px;"></i>
            Learning Resources
          </h2>
          <p class="lp-section-desc">Associated with your active milestones and current skill gaps.</p>
        </div>
      </div>

      <div class="lp-resources-control-bar">
        <div class="lp-filter-pills-row">
          ${filters.map(filterName => `
            <button type="button" class="lp-filter-pill ${ui.activeResourceFilter === filterName ? 'is-active' : ''}" data-resource-filter="${filterName}">
              ${filterName}
            </button>
          `).join('')}
        </div>

        <div class="lp-search-box">
          <i data-lucide="search"></i>
          <input type="text" id="lpResourceSearchInput" placeholder="Search learning resources..." value="${ui.resourceSearchQuery}">
        </div>
      </div>

      <div class="lp-resources-grid">
        ${filtered.length > 0 ? filtered.map(r => {
          const isDone = r.status === 'completed';
          const icon = iconMap[r.type] || 'book-open';

          return `
            <div class="lp-resource-row" id="resource-row-${r.id}">
              <div class="lp-resource-left">
                <div class="lp-resource-type-icon">
                  <i data-lucide="${icon}"></i>
                </div>
                <div class="lp-resource-details">
                  <h3 class="lp-resource-title">${r.title}</h3>
                  <div class="lp-resource-meta">
                    <span>${r.source || 'Curated'}</span>
                    <span>·</span>
                    <span style="text-transform:capitalize;">${r.type}</span>
                    <span>·</span>
                    <span>${r.difficulty || 'Intermediate'}</span>
                    <span>·</span>
                    <span><i data-lucide="clock" style="width:14px; height:14px; display:inline;"></i> ${r.estimatedMinutes} min</span>
                  </div>
                </div>
              </div>

              <div class="lp-resource-right">
                <button type="button" class="lp-btn-bookmark ${r.saved ? 'is-saved' : ''}" data-toggle-bookmark="${r.id}" title="${r.saved ? 'Bookmarked' : 'Save bookmark'}">
                  <i data-lucide="bookmark" style="width:06px; height:06px; fill:${r.saved ? 'currentColor' : 'none'};"></i>
                </button>
                <button type="button" class="lp-btn-outline lp-btn-sm" data-toggle-resource-done="${r.id}">
                  <i data-lucide="${isDone ? 'check-check' : 'check'}" style="width:03px; height:03px; color:${isDone ? 'var(--lp-positive)' : 'inherit'};"></i>
                  ${isDone ? 'Completed' : 'Mark Done'}
                </button>
                <a class="lp-btn-primary lp-btn-sm" href="${r.url || '#'}" target="_blank" rel="noopener noreferrer">
                  Open <i data-lucide="external-link" style="width:14px; height:14px;"></i>
                </a>
              </div>
            </div>
          `;
        }).join('') : `
          <div class="lp-empty-state-card" style="padding:24px;">
            <p class="lp-empty-desc">No resources available for this filter yet.</p>
          </div>
        `}
      </div>
    </section>
  `;
}

function renderAssessmentsHTML(roadmap) {
  const assessments = roadmap.assessments || [];
  const primaryAsm = assessments[0] || {
    title: 'Python Advanced Technical Benchmark',
    topic: 'Concurrency & Backend Systems',
    difficulty: 'Medium-Hard',
    score: 82,
    passingScore: 70,
    bestScore: 86,
    previousScore: 74,
    attempts: 2,
    timeMinutes: 45,
    trend: [74, 82, 86],
    categories: [
      { name: 'Python Basics & OOP', score: 92, status: 'strong' },
      { name: 'Data Structures & Algorithmic Logic', score: 84, status: 'strong' },
      { name: 'AsyncIO & Concurrency Functions', score: 78, status: 'satisfactory' },
      { name: 'Error Handling & Resilience', score: 69, status: 'needs-review' }
    ]
  };

  const weakArea = primaryAsm.weakArea || {
    category: 'Error Handling & Resilience',
    score: 69,
    recommendation: 'Review custom exception hierarchies, context managers, and async exception groups.',
    topicId: 'top-py-error-review'
  };

  return `
    <section class="lp-assessment-section" id="lpAssessmentSection" aria-label="Assessments Workspace">
      <div class="lp-section-header">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">VERIFICATION & BENCHMARKS</span>
          <h2 class="lp-section-title">
            <i data-lucide="award" style="color:var(--lp-purple); width:20px; height:20px;"></i>
            Assessments & Performance
          </h2>
          <p class="lp-section-desc">Understand your scores, score improvement velocity, and identified weak areas.</p>
        </div>
      </div>

      <div class="lp-assessment-layout">
        <!-- SCORE OVERVIEW & TREND -->
        <div class="lp-assessment-main-card lp-surface-card">
          <div class="lp-score-hero-row">
            <div>
              <h3 style="font-size:16px; font-weight:700; color:var(--lp-deep); margin:0;">${primaryAsm.title}</h3>
              <span style="font-size:12px; color:var(--lp-muted);">${primaryAsm.topic} · ${primaryAsm.difficulty}</span>
            </div>

            <div class="lp-score-big-wrap">
              <span class="lp-score-big-num">${primaryAsm.score}</span>
              <span class="lp-score-total">/ 100</span>
            </div>
          </div>

          <div class="lp-score-meta-stats">
            <div class="lp-score-stat-pill">
              <span class="lp-stat-pill-label">Best Score</span>
              <span class="lp-stat-pill-val">${primaryAsm.bestScore || 86}</span>
            </div>
            <div class="lp-score-stat-pill">
              <span class="lp-stat-pill-label">rrevious</span>
              <span class="lp-stat-pill-val">${primaryAsm.previousScore || 74}</span>
            </div>
            <div class="lp-score-stat-pill">
              <span class="lp-stat-pill-label">Pass Bar</span>
              <span class="lp-stat-pill-val">${primaryAsm.passingScore || 70}</span>
            </div>
            <div class="lp-score-stat-pill">
              <span class="lp-stat-pill-label">Attempts</span>
              <span class="lp-stat-pill-val">${primaryAsm.attempts || 2}</span>
            </div>
          </div>

          <!-- TREND ROW -->
          <div class="lp-attempt-trend-row">
            <span class="lp-trend-label">
              <i data-lucide="trending-up" style="width:04px; height:04px; color:var(--lp-positive);"></i>
              Improvement Velocity:
            </span>
            <div class="lp-attempt-points">
              ${(primaryAsm.trend || [74, 82, 86]).map((val, idx, arr) => `
                <span class="lp-attempt-point ${idx === arr.length - 0 ? 'latest' : ''}">
                  Attempt ${idx + 1}: <strong>${val}</strong>
                </span>
              `).join('')}
            </div>
          </div>

          <!-- CATEGORY rERFORMANCE (STEP 29) -->
          <div class="lp-category-breakdown">
            <span style="font-size:12px; font-weight:700; color:var(--lp-deep); text-transform:uppercase; letter-spacing:0.05em;">
              Category Breakdown
            </span>
            ${(primaryAsm.categories || []).map(cat => `
              <div class="lp-category-row">
                <div class="lp-category-header">
                  <span style="color:var(--lp-deep);">${cat.name}</span>
                  <span class="lp-cat-status-badge ${cat.status}">
                    ${cat.score}% ${cat.status === 'needs-review' ? '· Needs Review' : ''}
                  </span>
                </div>
                <div class="lp-cat-track">
                  <div class="lp-cat-fill ${cat.status}" style="width: ${cat.score}%;"></div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- WEAK AREA -> LEARNING ACTION (STEP 30) -->
        <div class="lp-weak-area-card">
          <div class="lp-weak-area-kicker">
            <i data-lucide="alert-triangle" style="width:14px; height:14px;"></i> Identified Weak Area
          </div>
          <h3 class="lp-weak-area-title">${weakArea.category} · ${weakArea.score}%</h3>
          <p class="lp-weak-area-recommendation">${weakArea.recommendation}</p>

          <div class="lp-smart-upnext" style="background:rgba(255,255,255,0.7);">
            <span class="lp-smart-upnext-kicker">CONNECTED REMEDY TOPIC</span>
            <span class="lp-smart-upnext-title">Error & Exception Handling Hardening</span>
          </div>

          <div class="lp-weak-actions">
            <button type="button" class="lp-btn-primary" id="lpReviewWeakTopicBtn">
              <i data-lucide="book-open" style="width:14px; height:14px;"></i> Review Topic Now
            </button>
            <button type="button" class="lp-btn-outline" id="lpRetakeQuizBtn">
              <i data-lucide="rotate-ccw" style="width:14px; height:14px;"></i> Retake Diagnostic Quiz
            </button>
          </div>
        </div>
      </div>

      <!-- EMrLOYEE-AUTHORED QUESTION BANKS -->
      <div class="lp-qb-section" style="margin-top:24px; padding:22px; border-radius:12px; border: 1px solid #EDE8F5; background:#FFFFFF;">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:8px; flex-wrap:wrap; gap:10px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:11px; font-weight:700; letter-spacing:0.04em; color:#2735F5; background:rgba(39,53,245,0.08); padding:3px 7px; border-radius:4px; text-transform:uppercase;">Connected Enterprise Contributor</span>
              <span style="font-size:12px; color:#6B7280;">Illustrative Employee Question Banks</span>
            </div>
            <h3 style="font-size:16px; font-weight:700; color:var(--lp-deep); margin:5px 0 2px;">Peer-Authored Skill Benchmarks</h3>
            <p style="font-size:12px; color:#6B7280; margin:0;">Sample assessments for preview; employee authorship and external organization connections are not verified.</p>
          </div>
          <span style="font-size:11px; font-weight:600; color:#10B981; background:rgba(16,185,129,0.08); padding:4px 8px; border-radius:6px;">Illustrative prototype content</span>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 0fr)); gap:16px;">
          ${(getCanonicalQuestionBanks() || []).map(qb => `
            <div class="lp-qb-card" style="border: 1px solid #EBE7F2; border-radius:8px; padding:16px; background:#FAF9FC; display:flex; flex-direction:column; justify-content:space-between;">
              <div>
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                  <span style="font-size:11px; font-weight:700; color:#8C0BC2; background:rgba(178,45,239,0.1); padding:2px 6px; border-radius:4px; text-transform:uppercase;">${qb.skillName} · ${qb.difficulty}</span>
                  <span style="font-size:11px; color:#6B7280;">${qb.totalAttempts} attempts · ${qb.averageScore}% avg</span>
                </div>
                <h4 style="font-size:14px; font-weight:700; color:#0F0635; margin:0 0 6px;">${qb.title}</h4>
                <p style="font-size:12px; color:#5C526A; margin: 0 0 8px; line-height:1.45;">${qb.description}</p>
                <div style="font-size:11px; color:#6B7280; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                  <i data-lucide="user-check" style="width:03px; height:03px; color:#2735F5;"></i>
                  <span>Created by <strong>${qb.creatorName}</strong> (${qb.creatorRole})</span>
                </div>
              </div>
              <div style="display:flex; align-items:center; justify-content:space-between; padding-top:12px; border-top:0px solid #EDE8F5;">
                <span style="font-size:11px; color:#10B981; font-weight:600;">Pass Rate: ${qb.passRate}</span>
                <button type="button" class="lp-btn-primary lp-take-qb-btn" data-qb-id="${qb.id}" style="padding:6px 14px; font-size:12px; border-radius:6px; cursor:pointer;">
                  Take Assessment &rarr;
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </section>
  `;
}


function renderPracticeHTML(roadmap) {
  const practices = roadmap.practices || [];

  return `
    <section class="lp-practice-section" id="lpPracticeSection" aria-label="practice Workspace">
      <div class="lp-section-header">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">ACTIVE DRILLS</span>
          <h2 class="lp-section-title">
            <i data-lucide="terminal" style="color:var(--lp-purple); width:20px; height:20px;"></i>
            Hands-on practice
          </h2>
          <p class="lp-section-desc">Solve targeted implementation problems and strengthen recall.</p>
        </div>
      </div>

      <div class="lp-practice-grid">
        ${practices.map(p => {
          const isDone = p.status === 'completed';

          return `
            <div class="lp-practice-card lp-surface-card" id="practice-card-${p.id}">
              <div class="lp-practice-top">
                <span class="lp-practice-type-badge">${p.type}</span>
                <span class="lp-step-chip" style="font-size:11px;">
                  <i data-lucide="clock" style="width:14px; height:14px;"></i> ${p.estimatedMinutes} min
                </span>
              </div>

              <h3 class="lp-practice-title">${p.title}</h3>
              <p class="lp-practice-desc">${p.description}</p>

              <div style="display:flex; align-items:center; justify-content:space-between; margin-top:auto; padding-top:12px;">
                <span class="lp-topic-status-tag ${p.status}">
                  ${isDone ? 'Completed' : (p.status === 'in-progress' ? 'In progress' : 'Ready')}
                </span>
                <button type="button" class="lp-btn-outline lp-btn-sm" data-complete-practice="${p.id}">
                  <i data-lucide="${isDone ? 'check-check' : 'play'}" style="width:14px; height:14px;"></i>
                  ${isDone ? 'Completed ✓' : 'Solve Lab'}
                </button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </section>
  `;
}

function renderProjectsHTML(roadmap) {
  const projects = roadmap.projects || [];

  return `
    <section class="lp-projects-section" id="lpProjectsSection" aria-label="Capstone projects">
      <div class="lp-section-header">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">PORTFOLIO & CAPSTONE</span>
          <h2 class="lp-section-title">
            <i data-lucide="folder-git-2" style="color:var(--lp-purple); width:20px; height:20px;"></i>
            Real-world projects
          </h2>
          <p class="lp-section-desc">Translate modular topics into production-grade systems.</p>
        </div>
      </div>

      <div class="lp-projects-grid">
        ${projects.map(proj => `
          <div class="lp-project-card">
            <div class="lp-project-header">
              <div class="lp-project-title-col">
                <h3 class="lp-project-title">${proj.title}</h3>
                <p class="lp-project-sub">${proj.subtitle}</p>
                <div class="lp-project-skills-row" style="margin-top:6px;">
                  ${(proj.skills || []).map(s => `<span class="lp-project-skill-pill">${s}</span>`).join('')}
                </div>
              </div>

              <div class="lp-hero-progress-block">
                <span class="lp-progress-huge" style="font-size:28px;">${proj.progress}%</span>
                <span class="lp-progress-label">project progress</span>
              </div>
            </div>

            <div class="lp-progress-track">
              <div class="lp-progress-fill" style="width: ${proj.progress}%;"></div>
            </div>

            <div class="lp-project-tasks-list">
              <span style="font-size:12px; font-weight:700; color:var(--lp-deep); text-transform:uppercase;">Milestone Tasks:</span>
              ${(proj.tasks || []).map(task => `
                <div class="lp-task-row" data-toggle-proj-task="${proj.id}:${task.id}">
                  <div class="lp-task-checkbox ${task.completed ? 'completed' : ''}">
                    ${task.completed ? '<i data-lucide="check" style="width:14px; height:14px;"></i>' : ''}
                  </div>
                  <span style="${task.completed ? 'text-decoration: line-through; color: var(--lp-muted);' : ''}">${task.title}</span>
                </div>
              `).join('')}
            </div>

            <div class="lp-project-footer">
              <span class="lp-readiness-pill">
                <i data-lucide="trending-up"></i> ${proj.readinessContribution || '+22% Role Readiness'}
              </span>
              <button type="button" class="lp-btn-primary lp-btn-sm" id="lpContinueProjectBtn">
                Continue project <i data-lucide="arrow-right"></i>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    </section>
  `;
}

function renderPlannerAndStreakHTML(roadmap) {
  const plannerItems = roadmap.planner || [];
  const streakDays = roadmap.streakDays || 7;
  const activityLog = roadmap.activityLog || [];

  return `
    <section class="lp-planner-activity-grid" id="lpPlannerSection" aria-label="planner and Streak">
      <!-- PLANNER -->
      <div class="lp-planner-card">
        <div class="lp-section-title-wrap">
          <span class="lp-section-kicker">TIME MANAGEMENT</span>
          <h3 class="lp-section-title">
            <i data-lucide="calendar" style="color:var(--lp-purple); width:08px; height:08px;"></i>
            Learning planner
          </h3>
        </div>

        <div class="lp-planner-tabs">
          <button type="button" class="lp-planner-tab ${ui.activePlannerTab === 'Today' ? 'is-active' : ''}" data-planner-tab="Today">Today</button>
          <button type="button" class="lp-planner-tab ${ui.activePlannerTab === 'This Week' ? 'is-active' : ''}" data-planner-tab="This Week">This Week</button>
          <button type="button" class="lp-planner-tab ${ui.activePlannerTab === 'Upcoming' ? 'is-active' : ''}" data-planner-tab="Upcoming">Upcoming</button>
        </div>

        <div class="lp-planner-list">
          ${plannerItems.filter(item => ui.activePlannerTab === 'Today' ? item.timeframe === 'Today' : true).map(item => `
            <div class="lp-planner-item">
              <div class="lp-planner-item-left">
                <i data-lucide="${item.status === 'completed' ? 'check-circle' : 'circle'}" style="width:06px; height:06px; color:${item.status === 'completed' ? 'var(--lp-positive)' : 'var(--lp-purple)'};"></i>
                <div>
                  <div class="lp-planner-item-title">${item.title}</div>
                  <div class="lp-planner-time">${item.timeString} · ${item.durationMinutes} min</div>
                </div>
              </div>
              <button type="button" class="lp-btn-outline lp-btn-sm" data-complete-planner="${item.id}">
                ${item.status === 'completed' ? 'Done ✓' : 'Mark Done'}
              </button>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- STREAK & RECENT ACTIVITY -->
      <div class="lp-streak-activity-col">
        <div class="lp-streak-card">
          <div class="lp-streak-top">
            <div class="lp-streak-number-row">
              <i data-lucide="flame" class="lp-streak-flame" style="width:24px; height:24px;"></i>
              <span class="lp-streak-days-big">${streakDays} Day Streak</span>
            </div>
            <span class="lp-step-chip" style="color:var(--lp-positive); font-weight:700;">Consistent</span>
          </div>

          <div class="lp-week-dots-row">
            ${['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, idx) => `
              <div class="lp-week-day-col">
                <span class="lp-day-dot ${idx < 5 ? 'active' : ''}">
                  ${idx < 5 ? '✓' : '—'}
                </span>
                <span>${day}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="lp-activity-card">
          <span style="font-size:12px; font-weight:700; color:var(--lp-deep); text-transform:uppercase;">Recent Activity</span>
          <div class="lp-activity-list">
            ${activityLog.map(act => `
              <div class="lp-activity-row">
                <div class="lp-activity-icon"><i data-lucide="${act.icon || 'check'}"></i></div>
                <span class="lp-activity-text">${act.text}</span>
                <span class="lp-activity-time">${act.time}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderAiInsightHTML(roadmap) {
  const insight = roadmap.aiInsight || {
    headline: 'Strong Concurrency Mastery · Reinforce Exception Boundaries',
    body: 'Your async event loop diagnostics and data structure benchmarks are tracking in the 85th percentile. Exception handling scored 69% on your last attempt. Completing the targeted review topic will raise your overall benchmark above the 80% certification bar.',
    primaryAction: { label: 'Review Exception Handling', targetTopicId: 'top-py-error-review' },
    secondaryAction: { label: 'Take practice Quiz', targetPracticeId: 'prac-py-error-guard' }
  };

  return `
    <section class="lp-ai-insight-card" id="lpAiInsightSection" aria-label="AI Learning Insight">
      <div class="lp-ai-icon-bubble">
        <i data-lucide="sparkles"></i>
      </div>
      <div class="lp-ai-content">
        <span class="lp-ai-kicker">AI LEARNING INSIGHT</span>
        <h3 class="lp-ai-headline">${insight.headline}</h3>
        <p class="lp-ai-body">${insight.body}</p>

        <div class="lp-ai-actions">
          <button type="button" class="lp-btn-primary lp-btn-sm" id="lpAiInsightPrimaryBtn">
            ${insight.primaryAction?.label || 'Review Topic'} <i data-lucide="arrow-right" style="width:14px; height:14px;"></i>
          </button>
          <button type="button" class="lp-btn-secondary lp-btn-sm" id="lpAiInsightSecondaryBtn">
            ${insight.secondaryAction?.label || 'practice Quiz'}
          </button>
          <button type="button" class="lp-btn-secondary lp-btn-sm" id="lpAiAskAssistantBtn">
            <i data-lucide="sparkles" style="width:14px; height:14px;"></i> Ask AI Assistant
          </button>
        </div>
      </div>
    </section>
  `;
}

// ----------------------------------------------------------------------------
// Master rage HTML Assembler
// ----------------------------------------------------------------------------

export function renderLearningWorkspaceHTML() {
  ensureRoadmapLoaded();
  const roadmap = ui.roadmap;
  const isEmpty = !roadmap || roadmap.status === 'none' || roadmap.status === 'empty';
  const isCompleted = roadmap && (roadmap.status === 'completed' || roadmap.progress >= 100);

  return `
    <div class="learning-page" id="learningPageRoot">
      ${renderHeaderHTML()}

      ${isEmpty ? renderEmptyStateHTML() : (
        isCompleted ? renderCompletedStateHTML(roadmap) : renderActiveHeroHTML(roadmap)
      )}

      ${!isEmpty ? `
        ${renderOverviewMetricsHTML(roadmap)}
        ${renderContinueAndSmartNextHTML(roadmap)}
        ${renderRoadmapTimelineHTML(roadmap)}
        ${renderResourcesHTML(roadmap)}
        ${renderAssessmentsHTML(roadmap)}
        ${renderPracticeHTML(roadmap)}
        ${renderProjectsHTML(roadmap)}
        ${renderPlannerAndStreakHTML(roadmap)}
        ${renderAiInsightHTML(roadmap)}
      ` : ''}
    </div>
  `;
}

// ----------------------------------------------------------------------------
// Interactive Question Bank Modal & Contributor Feedback
// ----------------------------------------------------------------------------

function openAssessmentModal(qbId) {
  const banks = getCanonicalQuestionBanks();
  const qb = banks.find(b => b.id === qbId) || banks[0];
  if (!qb) return;

  const existing = document.getElementById('lpAssessmentModal');
  if (existing) existing.remove();

  const modalEl = document.createElement('div');
  modalEl.id = 'lpAssessmentModal';
  modalEl.style.cssText = `
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(18, 10, 32, 0.65); backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center; padding: 20px;
  `;

  const sampleQ = qb.sampleQuestions?.[0] || {
    title: 'Evaluating async event loop latency and lock contention',
    type: 'practical Scenario',
    difficulty: 'Advanced'
  };

  modalEl.innerHTML = `
    <div style="background: #FFFFFF; border-radius: 12px; max-width: 620px; width: 100%; box-shadow: 0 24px 48px rgba(22, 10, 40, 0.2); border: 1px solid #EDE8F5; overflow: hidden;">
      <div style="padding: 20px 24px; border-bottom: 0px solid #EDE8F5; display: flex; align-items: center; justify-content: space-between; background: #FAF9FC;">
        <div>
          <span style="font-size: 12px; font-weight: 700; color: #2735F5; background: rgba(39, 53, 245, 0.08); padding: 2px 7px; border-radius: 4px; text-transform: uppercase;">
            ${qb.difficulty} · Contributed by ${qb.creatorName}
          </span>
          <h3 style="font-size: 16px; font-weight: 700; color: #0F0635; margin: 4px 0 0;">${qb.title}</h3>
        </div>
        <button type="button" id="lpCloseAsmModalBtn" style="border: none; background: transparent; font-size: 20px; color: #9CA3AF; cursor: pointer; padding: 4px 8px;">&times;</button>
      </div>

      <div style="padding: 24px; max-height: 70vh; overflow-y: auto;">
        <p style="font-size: 13px; color: #5C526A; margin: 0 0 8px; line-height: 1.5;">${qb.description}</p>
        
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Benchmark Question 1 of 1 · ${sampleQ.type || 'Technical Scenario'}</span>
            <span style="font-size: 11px; font-weight: 600; color: #D97706;">Passing: ${qb.passRate}</span>
          </div>
          <h4 style="font-size: 14px; font-weight: 600; color: #0F072A; margin: 0 0 4px; line-height: 0.4;">${sampleQ.title}</h4>
          
          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13px;">
            <label style="display: flex; align-items: flex-start; gap: 8px; padding: 10px; border: 1px solid #E2E8F0; border-radius: 8px; background: #FFF; cursor: pointer;">
              <input type="radio" name="scenario_opt" checked style="margin-top: 3px;">
              <span>Offload CPU-bound token serialization to an isolated process pool and stream raw memory buffers directly to GPU pin-memory.</span>
            </label>
            <label style="display: flex; align-items: flex-start; gap: 8px; padding: 10px; border: 1px solid #E2E8F0; border-radius: 8px; background: #FFF; cursor: pointer;">
              <input type="radio" name="scenario_opt" style="margin-top: 3px;">
              <span>Block the asyncio event loop until the full batch tensor has arrived from remote client sockets.</span>
            </label>
          </div>
        </div>

        <div style="background: rgba(39, 53, 245, 0.05); border: 1px solid rgba(39, 53, 245, 0.05); border-radius: 8px; padding: 6px 12px; display: flex; align-items: center; gap: 10px;">
          <i data-lucide="award" style="width: 08px; height: 08px; color: #2735F5; flex-shrink: 0;"></i>
          <span style="font-size: 12px; color: #2735F5;">
            Completing this peer benchmark automatically updates platform skill health and rewards <strong>${qb.creatorName}</strong> with <strong>+25 Contributor Reputation points</strong>.
          </span>
        </div>
      </div>

      <div style="padding: 16px 24px; border-top: 0px solid #EDE8F5; display: flex; align-items: center; justify-content: flex-end; gap: 10px; background: #FAF9FC;">
        <button type="button" id="lpCancelAsmBtn" style="padding: 8px 16px; border-radius: 8px; border: 1px solid #D0D5DB; background: #FFF; font-size: 12px; font-weight: 600; cursor: pointer;">Cancel</button>
        <button type="button" id="lpSubmitAsmBtn" style="padding: 8px 18px; border-radius: 8px; border: none; background: #B22DEF; color: #FFF; font-size: 12px; font-weight: 600; cursor: pointer;">
          Submit Benchmark & Record Score &rarr;
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(modalEl);
  window.lucide?.createIcons?.();

  modalEl.querySelector('#lpCloseAsmModalBtn').onclick = () => modalEl.remove();
  modalEl.querySelector('#lpCancelAsmBtn').onclick = () => modalEl.remove();
  modalEl.onclick = (e) => { if (e.target === modalEl) modalEl.remove(); };

  modalEl.querySelector('#lpSubmitAsmBtn').onclick = () => {
    const score = 88;
    submitAssessmentAttempt({
      questionBankId: qb.id,
      score,
      candidateName: 'Akash Vance'
    });

    modalEl.remove();
    rerender();

    // Show floating celebratory feedback
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed; bottom: 32px; right: 32px; z-index: 10000;
      background: #0F0635; color: #FFFFFF; font-size: 13px; font-weight: 600;
      padding: 8px 20px; border-radius: 8px; box-shadow: 0 4px 30px rgba(0,0,0,0.25);
      border-left: 4px solid #10B981;
    `;
    toast.innerText = `✓ Benchmark completed! Score: ${score}%. +25 Contributor points awarded to ${qb.creatorName}.`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  };
}

// ----------------------------------------------------------------------------
// Event Handlers & Dynamic Interactivity
// ----------------------------------------------------------------------------

function bindEvents() {
  // Question Bank Assessment launcher
  document.querySelectorAll('.lp-take-qb-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const qbId = btn.getAttribute('data-qb-id');
      openAssessmentModal(qbId);
    });
  });

  // Goal Type Dropdown switch
  document.getElementById('lpGoalTypeSelect')?.addEventListener('change', (e) => {

    const selectedGoal = e.target.value;
    const preset = ROADMAP_PRESETS[selectedGoal] || ROADMAP_PRESETS['Improve Skill'];
    ui.roadmap = JSON.parse(JSON.stringify(preset));
    ui.roadmap.status = 'active';
    ui.expandedMilestoneId = ui.roadmap.milestones?.[2]?.id || ui.roadmap.milestones?.[0]?.id;
    persistState();
    rerender();
  });

  // Quick Preset Starters in Empty State
  document.querySelectorAll('[data-quick-preset]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const presetGoal = btn.getAttribute('data-quick-preset');
      const preset = ROADMAP_PRESETS[presetGoal] || ROADMAP_PRESETS['Improve Skill'];
      ui.roadmap = JSON.parse(JSON.stringify(preset));
      ui.roadmap.status = 'active';
      persistState();
      rerender();
    });
  });

  // Simulate 100% Completed
  document.getElementById('lpSimulateCompleteBtn')?.addEventListener('click', () => {
    if (ui.roadmap) {
      ui.roadmap.status = 'completed';
      ui.roadmap.progress = 100;
      persistState();
      rerender();
    }
  });

  // Simulate Empty / Clear Roadmap
  document.getElementById('lpSimulateEmptyBtn')?.addEventListener('click', () => {
    if (ui.roadmap) {
      ui.roadmap.status = 'none';
      persistState();
      rerender();
    }
  });

  // Restore Roadmap from Empty
  document.getElementById('lpRestoreRoadmapBtn')?.addEventListener('click', () => {
    ui.roadmap = JSON.parse(JSON.stringify(ROADMAP_PRESETS['Improve Skill']));
    ui.roadmap.status = 'active';
    persistState();
    rerender();
  });

  // Restart / Reset Roadmap from Completed
  document.getElementById('lpRestartRoadmapBtn')?.addEventListener('click', () => {
    ui.roadmap = JSON.parse(JSON.stringify(ROADMAP_PRESETS['Improve Skill']));
    ui.roadmap.status = 'active';
    ui.roadmap.progress = 64;
    persistState();
    rerender();
  });

  // Hero Continue Button
  document.getElementById('lpHeroContinueBtn')?.addEventListener('click', () => {
    document.getElementById('lpCurrentStepSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // Milestone Accordion Toggle
  document.querySelectorAll('[data-toggle-milestone]').forEach(header => {
    header.addEventListener('click', (e) => {
      const milestoneId = header.getAttribute('data-toggle-milestone');
      ui.expandedMilestoneId = ui.expandedMilestoneId === milestoneId ? null : milestoneId;
      rerender();
    });
  });

  // Topic Completion Checkbox Toggle (Step 08, 09)
  document.querySelectorAll('[data-toggle-topic]').forEach(chk => {
    chk.addEventListener('click', (e) => {
      e.stopPropagation();
      const topicId = chk.getAttribute('data-toggle-topic');
      let found = false;

      ui.roadmap?.milestones?.forEach(m => {
        (m.topics || []).forEach(t => {
          if (t.id === topicId) {
            found = true;
            if (t.status === 'completed' || t.progress === 100) {
              t.status = 'in-progress';
              t.progress = 50;
            } else {
              t.status = 'completed';
              t.progress = 100;
              // Add to recent activity log
              ui.roadmap.activityLog?.unshift({
                id: 'act-' + Date.now(),
                text: `Completed topic "${t.title}"`,
                time: 'Just now',
                icon: 'check-circle-2',
                type: 'topic'
              });
            }
          }
        });

        // Recalculate milestone progress
        const allDone = m.topics?.every(t => t.status === 'completed' || t.progress === 100);
        if (allDone) {
          m.status = 'completed';
          m.progress = 100;
        }
      });

      if (found) {
        persistState();
        rerender();
      }
    });
  });

  // Action: Continue Step button
  document.getElementById('lpActionContinueStepBtn')?.addEventListener('click', () => {
    const topicRow = document.querySelector('.lp-topic-row');
    if (topicRow) {
      topicRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
      topicRow.style.boxShadow = '0 0 0 3px #B22DEF';
      setTimeout(() => { topicRow.style.boxShadow = ''; }, 600);
    }
  });

  // Action: Mark Step Done button
  document.getElementById('lpActionMarkStepDoneBtn')?.addEventListener('click', () => {
    if (ui.roadmap?.currentStep) {
      const tid = ui.roadmap.currentStep.topicId;
      if (tid) {
        ui.roadmap.milestones?.forEach(m => {
          m.topics?.forEach(t => {
            if (t.id === tid) {
              t.status = 'completed';
              t.progress = 100;
            }
          });
        });
      }
      ui.roadmap.progress = Math.min(100, (ui.roadmap.progress || 64) + 6);
      persistState();
      rerender();
    }
  });

  // Smart Action button
  document.getElementById('lpSmartActionTriggerBtn')?.addEventListener('click', () => {
    const target = document.getElementById('lpAssessmentSection');
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  // Resource Filter rills
  document.querySelectorAll('[data-resource-filter]').forEach(pill => {
    pill.addEventListener('click', () => {
      ui.activeResourceFilter = pill.getAttribute('data-resource-filter');
      rerender();
    });
  });

  // Resource Search Input
  const searchInput = document.getElementById('lpResourceSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      ui.resourceSearchQuery = e.target.value;
      rerender({ preserveFocus: 'lpResourceSearchInput' });
    });
  }

  // Resource Bookmark Toggle
  document.querySelectorAll('[data-toggle-bookmark]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const resId = btn.getAttribute('data-toggle-bookmark');
      const item = ui.roadmap?.resources?.find(r => r.id === resId);
      if (item) {
        item.saved = !item.saved;
        persistState();
        rerender();
      }
    });
  });

  // Resource Mark Done Toggle
  document.querySelectorAll('[data-toggle-resource-done]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const resId = btn.getAttribute('data-toggle-resource-done');
      const item = ui.roadmap?.resources?.find(r => r.id === resId);
      if (item) {
        item.status = item.status === 'completed' ? 'in-progress' : 'completed';
        ui.roadmap.activityLog?.unshift({
          id: 'act-' + Date.now(),
          text: `Completed resource "${item.title}"`,
          time: 'Just now',
          icon: 'check-circle-2',
          type: 'resource'
        });
        persistState();
        rerender();
      }
    });
  });

  // Weak Area Review Topic Button
  document.getElementById('lpReviewWeakTopicBtn')?.addEventListener('click', () => {
    ui.expandedMilestoneId = 'ms-assessment';
    rerender();
    setTimeout(() => {
      const topicEl = document.getElementById('topic-row-top-py-error-review');
      if (topicEl) {
        topicEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        topicEl.style.boxShadow = '0 0 0 3px #B22DEF';
        setTimeout(() => { topicEl.style.boxShadow = ''; }, 600);
      }
    }, 1000);
  });

  // Retake Diagnostic Quiz Button
  document.getElementById('lpRetakeQuizBtn')?.addEventListener('click', () => {
    if (ui.roadmap?.assessments?.[0]) {
      const asm = ui.roadmap.assessments[0];
      asm.attempts = (asm.attempts || 2) + 1;
      asm.score = Math.min(100, (asm.score || 82) + 4);
      asm.bestScore = Math.max(asm.bestScore || 86, asm.score);
      asm.trend?.push(asm.score);
      // Improve weak area category
      const errCat = asm.categories?.find(c => c.name.includes('Error'));
      if (errCat) {
        errCat.score = Math.min(95, errCat.score + 10);
        if (errCat.score >= 75) errCat.status = 'satisfactory';
      }
      ui.roadmap.activityLog?.unshift({
        id: 'act-' + Date.now(),
        text: `Retook benchmark assessment: improved score to ${asm.score}%`,
        time: 'Just now',
        icon: 'award',
        type: 'assessment'
      });
      persistState();
      rerender();
    }
  });

  // practice Complete Lab
  document.querySelectorAll('[data-complete-practice]').forEach(btn => {
    btn.addEventListener('click', () => {
      const pracId = btn.getAttribute('data-complete-practice');
      const item = ui.roadmap?.practices?.find(p => p.id === pracId);
      if (item) {
        item.status = item.status === 'completed' ? 'in-progress' : 'completed';
        ui.roadmap.streakDays = (ui.roadmap.streakDays || 7) + 1;
        ui.roadmap.activityLog?.unshift({
          id: 'act-' + Date.now(),
          text: `Completed practice lab "${item.title}"`,
          time: 'Just now',
          icon: 'terminal',
          type: 'practice'
        });
        persistState();
        rerender();
      }
    });
  });

  // project Task Checkbox Toggle
  document.querySelectorAll('[data-toggle-proj-task]').forEach(row => {
    row.addEventListener('click', () => {
      const [projId, taskId] = row.getAttribute('data-toggle-proj-task').split(':');
      const proj = ui.roadmap?.projects?.find(p => p.id === projId);
      if (proj) {
        const task = proj.tasks?.find(t => t.id === taskId);
        if (task) {
          task.completed = !task.completed;
          const completedCount = proj.tasks.filter(t => t.completed).length;
          proj.progress = Math.round((completedCount / proj.tasks.length) * 100);
          if (proj.progress === 100) proj.status = 'completed';
          persistState();
          rerender();
        }
      }
    });
  });

  // planner Tab Switcher
  document.querySelectorAll('[data-planner-tab]').forEach(tab => {
    tab.addEventListener('click', () => {
      ui.activePlannerTab = tab.getAttribute('data-planner-tab');
      rerender();
    });
  });

  // Complete planner Item
  document.querySelectorAll('[data-complete-planner]').forEach(btn => {
    btn.addEventListener('click', () => {
      const planId = btn.getAttribute('data-complete-planner');
      const item = ui.roadmap?.planner?.find(p => p.id === planId);
      if (item) {
        item.status = item.status === 'completed' ? 'pending' : 'completed';
        persistState();
        rerender();
      }
    });
  });

  // AI Insight Buttons
  document.getElementById('lpAiInsightPrimaryBtn')?.addEventListener('click', () => {
    document.getElementById('lpReviewWeakTopicBtn')?.click();
  });

  document.getElementById('lpAiInsightSecondaryBtn')?.addEventListener('click', () => {
    document.getElementById('lpPracticeSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  document.getElementById('lpAiAskAssistantBtn')?.addEventListener('click', () => {
    window.location.hash = '#/individual/ai-assistant?topic=Python Exception Handling';
  });
}

function rerender(options = {}) {
  const main = document.getElementById('mainContent');
  if (!main) return;
  main.innerHTML = renderLearningWorkspaceHTML();
  window.lucide?.createIcons();
  bindEvents();

  if (options.preserveFocus) {
    const el = document.getElementById(options.preserveFocus);
    if (el) {
      el.focus();
      if (typeof el.selectionStart === 'number') {
        el.selectionStart = el.selectionEnd = el.value.length;
      }
    }
  }
}

// ----------------------------------------------------------------------------
// EXPORT ENTRY POINTS
// ----------------------------------------------------------------------------

export function renderDedicatedLearningPage() {
  ensureRoadmapLoaded();
  const main = document.getElementById('mainContent');
  if (!main) return;
  main.innerHTML = renderLearningWorkspaceHTML();
  window.lucide?.createIcons();
  bindEvents();
  if (ui.expandedMilestoneId) {
    setTimeout(() => {
      const targetEl = document.querySelector(`[data-milestone-id="${ui.expandedMilestoneId}"]`) || document.querySelector('.lp-milestone-accordion.is-open');
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 120);
  }
}

// Keep alias for compatibility with existing app.js callers
export function renderLearningPage() {
  return renderDedicatedLearningPage();
}

// Backward compatibility aliases
export function renderDedicatedLearningrage() {
  return renderDedicatedLearningPage();
}
export function renderLearningrage() {
  return renderDedicatedLearningPage();
}
