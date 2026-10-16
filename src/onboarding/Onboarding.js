// ============================================================================
// TALENTSCOPE.AI — ONBOARDING WORKFLOW MANAGER
// Drives question-by-question flow for Individual, Employee, and Company
// Restores drafts from localStorage, supports Back/Next/Skip, renders SVG context
// ============================================================================

import {
  INDIVIDUAL_QUESTIONS,
  EMPLOYEE_QUESTIONS,
  COMPANY_QUESTIONS
} from './onboarding-data.js';
import { renderQuestionComponent } from './OnboardingQuestion.js';
import {
  getCurrentUser,
  getOnboardingDraft,
  saveOnboardingDraft,
  clearOnboardingDraft
} from '../auth/auth-state.js';
import {
  loadIndividualOnboardingProfile,
  saveIndividualOnboardingStep,
  loadRoleOnboardingProfile,
  saveRoleOnboardingStep
} from './onboarding-api.js';

let onboardingSession = {
  userType: 'individual',
  employeeType: null,
  companyName: null,
  stepIndex: 0,
  answers: {},
  completedSteps: [],
  pendingSteps: []
};

export async function renderOnboardingPage(container) {
  const root = container || document.getElementById('mainContent') || document.getElementById('appShell') || document.body;
  root.innerHTML = '<div role="status" aria-live="polite">Loading your saved onboarding progress...</div>';
  const initResult = await initializeSession();
  if (!root.isConnected || !window.location.hash.includes('/onboarding')) return;
  renderCurrentQuestionView(root);
  if (initResult?.error) showSaveStatus(root, initResult.error, true);
}

async function initializeSession() {
  const user = getCurrentUser();
  const draft = getOnboardingDraft(user?.userType === 'individual' ? 'individual' : undefined);

  if (user?.userType === 'individual') {
    let remoteProfile;
    let loadError = null;
    try {
      remoteProfile = await loadIndividualOnboardingProfile();
    } catch (error) {
      loadError = error?.message || 'Could not load your saved onboarding profile.';
    }

    const answers = { ...(remoteProfile?.answers || {}) };
    const pendingSteps = Array.isArray(draft?.pendingSteps) ? draft.pendingSteps : [];
    if (pendingSteps.length) {
      for (const step of pendingSteps) {
        const question = INDIVIDUAL_QUESTIONS.find(item => item.stepNumber === step);
        if (question && Object.hasOwn(draft.answers || {}, question.id)) {
          answers[question.id] = draft.answers[question.id];
        }
      }
    }

    const remoteStep = remoteProfile?.onboarding?.current_step || 1;
    onboardingSession = {
      userType: 'individual',
      employeeType: null,
      companyName: null,
      stepIndex: pendingSteps.length
        ? Math.max(0, Math.min(draft.stepIndex || 0, INDIVIDUAL_QUESTIONS.length - 1))
        : Math.max(0, Math.min(remoteStep - 1, INDIVIDUAL_QUESTIONS.length - 1)),
      answers,
      completedSteps: remoteProfile?.onboarding?.completed_steps || [],
      pendingSteps
    };

    if (loadError && draft) {
      onboardingSession.answers = { ...answers, ...(draft.answers || {}) };
      onboardingSession.stepIndex = Math.max(0, Math.min(draft.stepIndex || 0, INDIVIDUAL_QUESTIONS.length - 1));
      onboardingSession.pendingSteps = Array.from(new Set([
        ...pendingSteps,
        (draft.stepIndex || 0) + 1
      ]));
    }
    saveOnboardingDraft(onboardingSession);
    return { error: loadError };
  }

  if (user?.userType === 'employee' || user?.userType === 'company') {
    const type = user.userType;
    let remote = null;
    try { remote = await loadRoleOnboardingProfile(type); } catch {}
    const answers = { ...(remote?.answers || {}), ...(draft?.answers || {}) };
    onboardingSession = {
      userType: type,
      employeeType: draft?.employeeType || user.employeeType || null,
      companyName: draft?.companyName || user.companyName || null,
      stepIndex: Math.max(0, Math.min((remote?.onboarding?.current_step || draft?.stepIndex + 1 || 1) - 1,
        (type === 'employee' ? EMPLOYEE_QUESTIONS : COMPANY_QUESTIONS).length - 1)),
      answers,
      completedSteps: remote?.onboarding?.completed_steps || draft?.completedSteps || [],
      pendingSteps: draft?.pendingSteps || []
    };
    saveOnboardingDraft(onboardingSession);
    return;
  }

  if (draft) {
    onboardingSession = {
      userType: draft.userType || user?.userType || 'individual',
      employeeType: draft.employeeType || user?.employeeType || null,
      companyName: draft.companyName || user?.companyName || null,
      stepIndex: typeof draft.stepIndex === 'number' ? draft.stepIndex : 0,
      answers: draft.answers || {},
      completedSteps: draft.completedSteps || [],
      pendingSteps: draft.pendingSteps || []
    };
  } else if (user) {
    onboardingSession = {
      userType: user.userType || 'individual',
      employeeType: user.employeeType || null,
      companyName: user.companyName || null,
      stepIndex: 0,
      answers: {
        name: user.name || '',
        companyName: user.companyName || ''
      },
      completedSteps: [],
      pendingSteps: []
    };
  } else {
    // Default fallback
    onboardingSession = {
      userType: 'individual',
      employeeType: null,
      companyName: null,
      stepIndex: 0,
      answers: {},
      completedSteps: [],
      pendingSteps: []
    };
  }
}

function getQuestionsList() {
  if (onboardingSession.userType === 'company') {
    return COMPANY_QUESTIONS;
  }
  if (onboardingSession.userType === 'employee') {
    return EMPLOYEE_QUESTIONS;
  }
  return INDIVIDUAL_QUESTIONS;
}

function renderCurrentQuestionView(root) {
  const questions = getQuestionsList();
  const maxSteps = questions.length;
  const currentIdx = Math.max(0, Math.min(onboardingSession.stepIndex, maxSteps - 1));
  onboardingSession.stepIndex = currentIdx;

  const currentQ = questions[currentIdx];
  const progressPercent = Math.round(((currentIdx + 1) / maxSteps) * 100);

  // Set Portal Accent Variable
  const accentColor = onboardingSession.userType === 'company'
    ? '#874FFF'
    : onboardingSession.userType === 'employee'
      ? '#2735F5'
      : '#B22DEF';

  const roleBadgeLabel = onboardingSession.userType === 'company'
    ? 'Company Workforce'
    : onboardingSession.userType === 'employee'
      ? (onboardingSession.employeeType === 'independent' ? 'Independent Career' : 'Employee Growth')
      : 'Individual Intelligence';

  const currentAnswer = onboardingSession.answers[currentQ.id] || {};

  root.innerHTML = `
    <div class="ts-onboarding-viewport" style="--ob-accent: ${accentColor};">
      <!-- TOP NAV -->
      <nav class="ts-ob-nav" aria-label="Onboarding Progress Navigation">
        <div class="ts-ob-nav-left">
          <button type="button" class="ts-ob-btn-back" id="obBackBtn" aria-label="Go to previous step">
            <i data-lucide="arrow-left"></i>
            <span>Back</span>
          </button>

          <a class="ts-ob-brand" href="#/individual/home" aria-label="TalentScope.ai">
            <span class="ts-ob-brand-mark">
              <img src="assets/logo.png" alt="TalentScope">
            </span>
            <span class="ts-ob-brand-name">TalentScope<span>.ai</span></span>
          </a>
        </div>

        <div class="ts-ob-progress-container">
          <span class="ts-ob-progress-text">
            Step <strong>${currentIdx + 1}</strong> of ${maxSteps} &nbsp;·&nbsp; ${currentQ.category}
          </span>
          <div class="ts-ob-progress-track" role="progressbar" aria-valuenow="${progressPercent}" aria-valuemin="0" aria-valuemax="100">
            <div class="ts-ob-progress-fill" style="width: ${progressPercent}%; background: ${accentColor};"></div>
          </div>
        </div>

        <div>
          <span class="ts-ob-role-pill is-${onboardingSession.userType}">
            <i data-lucide="${onboardingSession.userType === 'company' ? 'building-2' : onboardingSession.userType === 'employee' ? 'briefcase' : 'user'}"></i>
            <span>${roleBadgeLabel}</span>
          </span>
        </div>
      </nav>

      <!-- MAIN ONBOARDING CANVAS -->
      <main class="ts-ob-canvas">
        <!-- LEFT: QUESTION AREA -->
        <section class="ts-ob-main-col">
          <div id="questionContainer">
            ${renderQuestionComponent(currentQ, currentAnswer, onboardingSession.userType, onboardingSession.answers)}
          </div>

          <!-- BOTTOM ACTION BAR -->
          <footer class="ts-ob-actions-bar">
            <div>
              ${currentQ.allowSkip ? `
                <button type="button" class="ts-ob-skip-btn" id="obSkipBtn">
                  <span>${currentQ.skipText || 'Skip for now'}</span>
                </button>
              ` : `
                <span style="font-size: 13px; color: #8A7E98;">${currentQ.type.includes('multi') ? 'Select all that apply' : 'Select one to proceed'}</span>
              `}
            </div>

            <span id="obSaveStatus" role="status" aria-live="polite" hidden></span>
            <button type="button" class="ts-ob-continue-btn" id="obContinueBtn">
              <span>${currentIdx === maxSteps - 1 ? getFinalButtonLabel(onboardingSession.userType) : 'Continue'}</span>
              <i data-lucide="${currentIdx === maxSteps - 1 ? 'sparkles' : 'arrow-right'}"></i>
            </button>
          </footer>
        </section>

        <!-- RIGHT: CONTEXTUAL ILLUSTRATION -->
        <aside class="ts-ob-visual-col" aria-label="Visual representation">
          <div class="ts-ob-illustration-card">
            <div class="ts-ob-svg-frame">
              ${renderContextualSvg(currentQ.illustration, accentColor)}
            </div>
            <div class="ts-ob-illustration-text">
              <strong>${getIllustrationHeadline(currentQ.category)}</strong>
              <p>${getIllustrationSub(currentQ.id)}</p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  bindOnboardingEvents(root, currentQ, currentIdx, maxSteps);
}

function getFinalButtonLabel(userType) {
  if (userType === 'company') return 'Build Workforce Profile';
  if (userType === 'employee') return 'Build My Career Profile';
  return 'Build My Intelligence Profile';
}

function bindOnboardingEvents(root, currentQ, currentIdx, maxSteps) {
  const container = root.querySelector('#questionContainer');
  let currentVal = onboardingSession.answers[currentQ.id] || getDefaultValForType(currentQ.type);

  // A. Back Button
  root.querySelector('#obBackBtn')?.addEventListener('click', () => {
    if (currentIdx > 0) {
      onboardingSession.stepIndex = currentIdx - 1;
      saveOnboardingDraft(onboardingSession);
      renderCurrentQuestionView(root);
    } else {
      window.location.hash = '#/auth/signup';
    }
  });

  // B. Skip Button
  root.querySelector('#obSkipBtn')?.addEventListener('click', async () => {
    currentVal = harvestCurrentInput(container, currentQ, currentVal);
    onboardingSession.answers[currentQ.id] = currentVal;
    const saved = await persistCurrentStep(root, currentQ, currentVal);
    if (saved) advanceToNext(root, currentIdx, maxSteps);
  });

  // C. Continue Button
  root.querySelector('#obContinueBtn')?.addEventListener('click', async event => {
    const invalidInput = container.querySelector(':invalid');
    if (invalidInput) {
      invalidInput.reportValidity();
      return;
    }
    // Read input values before advancing
    currentVal = harvestCurrentInput(container, currentQ, currentVal);
    onboardingSession.answers[currentQ.id] = currentVal;
    const button = event.currentTarget;
    button.disabled = true;
    const saved = await persistCurrentStep(root, currentQ, currentVal);
    button.disabled = false;
    if (saved) advanceToNext(root, currentIdx, maxSteps);
  });

  // D. Event delegations inside question body
  // Single-Select Cards
  container.querySelectorAll('[data-option-value]').forEach(card => {
    card.addEventListener('click', () => {
      const val = card.getAttribute('data-option-value');
      currentVal = val;
      onboardingSession.answers[currentQ.id] = val;
      container.querySelectorAll('[data-option-value]').forEach(c => {
        const isTarget = c === card;
        c.classList.toggle('is-selected', isTarget);
        c.querySelector('.ts-q-option-radio')?.classList.toggle('is-checked', isTarget);
      });
    });
  });

  // Multi-Select Cards
  container.querySelectorAll('[data-multi-value]').forEach(card => {
    card.addEventListener('click', () => {
      const val = card.getAttribute('data-multi-value');
      let list = Array.isArray(currentVal) ? [...currentVal] : [];
      if (list.includes(val)) {
        list = list.filter(v => v !== val);
      } else {
        list.push(val);
      }
      currentVal = list;
      onboardingSession.answers[currentQ.id] = currentVal;
      card.classList.toggle('is-selected', list.includes(val));
      card.querySelector('.ts-q-option-check')?.classList.toggle('is-checked', list.includes(val));
    });
  });

  // Multi-Select Pills
  container.querySelectorAll('[data-pill-value]').forEach(btn => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-pill-value');
      let list = Array.isArray(currentVal) ? [...currentVal] : [];
      if (list.includes(val)) {
        list = list.filter(v => v !== val);
      } else {
        list.push(val);
      }
      currentVal = list;
      onboardingSession.answers[currentQ.id] = currentVal;
      btn.classList.toggle('is-selected', list.includes(val));
      const icon = btn.querySelector('svg') || btn.querySelector('i');
      if (icon) {
        icon.setAttribute('data-lucide', list.includes(val) ? 'check' : 'plus');
        if (window.lucide) window.lucide.createIcons();
      }
    });
  });

  // Skill Selector Logic
  const skillInput = container.querySelector('#skillSearchInput');
  const addSkillBtn = container.querySelector('#btnAddSearchedSkill');
  const selectedSkillsArea = container.querySelector('#selectedSkillsArea');

  const addSkill = (skillName) => {
    const clean = String(skillName || '').trim();
    if (!clean) return;
    let list = Array.isArray(currentVal) ? [...currentVal] : [];
    if (!list.includes(clean)) {
      list.push(clean);
      currentVal = list;
      onboardingSession.answers[currentQ.id] = list;
      renderSkillsBadges(selectedSkillsArea, list);
    }
    if (skillInput) skillInput.value = '';
  };

  if (addSkillBtn && skillInput) {
    addSkillBtn.addEventListener('click', () => addSkill(skillInput.value));
    skillInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addSkill(skillInput.value);
      }
    });
  }

  container.querySelectorAll('[data-add-suggested-skill]').forEach(btn => {
    btn.addEventListener('click', () => addSkill(btn.getAttribute('data-add-suggested-skill')));
  });

  if (selectedSkillsArea) {
    selectedSkillsArea.addEventListener('click', (e) => {
      const rm = e.target.closest('[data-remove-skill]');
      if (rm) {
        const skill = rm.getAttribute('data-remove-skill');
        let list = (Array.isArray(currentVal) ? currentVal : []).filter(s => s !== skill);
        currentVal = list;
        onboardingSession.answers[currentQ.id] = list;
        renderSkillsBadges(selectedSkillsArea, list);
      }
    });
  }

  // Skill Level Matrix Pills
  container.querySelectorAll('[data-level-skill]').forEach(pill => {
    pill.addEventListener('click', () => {
      const skill = pill.getAttribute('data-level-skill');
      const level = pill.getAttribute('data-level-key');
      if (typeof currentVal !== 'object' || Array.isArray(currentVal)) currentVal = {};
      currentVal[skill] = level;
      onboardingSession.answers[currentQ.id] = currentVal;

      const row = pill.closest('[data-skill-row]');
      row?.querySelectorAll('[data-level-skill]').forEach(p => p.classList.toggle('is-active', p === pill));
    });
  });

  // Role Selector
  container.querySelectorAll('[data-select-role]').forEach(btn => {
    btn.addEventListener('click', () => {
      const role = btn.getAttribute('data-select-role');
      currentVal = role;
      onboardingSession.answers[currentQ.id] = role;
      const roleInput = container.querySelector('#roleSearchInput');
      if (roleInput) roleInput.value = role;
      container.querySelectorAll('[data-select-role]').forEach(b => b.classList.toggle('is-selected-role', b === btn));
    });
  });

  // Company Selector
  const companyInput = container.querySelector('#companySearchInput');
  const addCompanyBtn = container.querySelector('#btnAddCompany');
  const selectedCompaniesArea = container.querySelector('#selectedCompaniesArea');

  const addCompany = (comp) => {
    const clean = String(comp || '').trim();
    if (!clean) return;
    let list = Array.isArray(currentVal) ? [...currentVal] : [];
    if (!list.includes(clean)) {
      list.push(clean);
      currentVal = list;
      onboardingSession.answers[currentQ.id] = list;
      renderCompanyBadges(selectedCompaniesArea, list);
    }
    if (companyInput) companyInput.value = '';
  };

  if (addCompanyBtn && companyInput) {
    addCompanyBtn.addEventListener('click', () => addCompany(companyInput.value));
    companyInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addCompany(companyInput.value);
      }
    });
  }

  container.querySelectorAll('[data-add-suggested-company]').forEach(btn => {
    btn.addEventListener('click', () => addCompany(btn.getAttribute('data-add-suggested-company')));
  });

  if (selectedCompaniesArea) {
    selectedCompaniesArea.addEventListener('click', (e) => {
      const rm = e.target.closest('[data-remove-company]');
      if (rm) {
        const comp = rm.getAttribute('data-remove-company');
        let list = (Array.isArray(currentVal) ? currentVal : []).filter(c => c !== comp);
        currentVal = list;
        onboardingSession.answers[currentQ.id] = list;
        renderCompanyBadges(selectedCompaniesArea, list);
      }
    });
  }
}

function harvestCurrentInput(container, question, currentVal) {
  if (question.type === 'personal-identity') {
    container.querySelectorAll('input, select').forEach(input => {
      if (input.name) {
        currentVal[input.name] = input.value.trim();
      }
    });
  } else if (question.type === 'employee-workplace') {
    const comp = container.querySelector('#qf_company')?.value.trim();
    const dept = container.querySelector('#qf_department')?.value.trim();
    const ind = container.querySelector('#qf_industry')?.value.trim();
    const role = container.querySelector('#qf_currentRole')?.value.trim();
    currentVal.company = comp || '';
    currentVal.department = dept || '';
    currentVal.industry = ind || '';
    currentVal.currentRole = role || '';
  } else if (question.type === 'textarea') {
    currentVal.text = container.querySelector('#qf_textarea')?.value.trim() || '';
  } else if (question.type === 'role-selector') {
    const inputRole = container.querySelector('#roleSearchInput')?.value.trim();
    currentVal = inputRole || '';
  } else if (question.type === 'experience-conditional') {
    const study = container.querySelector('#qf_studyField')?.value.trim();
    if (study) {
      if (typeof currentVal === 'string') currentVal = { experience: currentVal, studyField: study };
      else currentVal.studyField = study;
    } else if (currentVal && typeof currentVal === 'object') {
      delete currentVal.studyField;
    }
  } else if (question.type === 'skill-level-matrix') {
    const levels = {};
    container.querySelectorAll('[data-skill-row]').forEach(row => {
      const selectedLevel = row.querySelector('[data-level-skill].is-active');
      if (selectedLevel) {
        levels[row.getAttribute('data-skill-row')] = selectedLevel.getAttribute('data-level-key');
      }
    });
    currentVal = levels;
  }
  return currentVal;
}

async function persistCurrentStep(root, question, answer) {
  const step = question.stepNumber;
  onboardingSession.pendingSteps = Array.from(new Set([
    ...(onboardingSession.pendingSteps || []),
    step
  ]));
  saveOnboardingDraft(onboardingSession);
  showSaveStatus(root, 'Saving your answer...', false);

  try {
    const result = onboardingSession.userType === 'individual'
      ? await saveIndividualOnboardingStep(step, answer)
      : await saveRoleOnboardingStep(onboardingSession.userType, step, question.id, answer);
    onboardingSession.pendingSteps = onboardingSession.pendingSteps.filter(item => item !== step);
    onboardingSession.completedSteps = result.onboarding.completed_steps || [];
    saveOnboardingDraft(onboardingSession);
    showSaveStatus(root, 'Saved', false);
    return true;
  } catch (error) {
    showSaveStatus(root, error?.message || 'Your answer could not be saved. Please retry.', true);
    return false;
  }
}

function showSaveStatus(root, message, isError) {
  const status = root.querySelector('#obSaveStatus');
  if (!status) return;
  status.textContent = message;
  status.hidden = !message;
  status.setAttribute('aria-label', isError ? 'Save error' : 'Save status');
  status.dataset.state = isError ? 'error' : 'success';
}

function advanceToNext(root, currentIdx, maxSteps) {
  if (currentIdx < maxSteps - 1) {
    onboardingSession.stepIndex = currentIdx + 1;
    saveOnboardingDraft(onboardingSession);
    renderCurrentQuestionView(root);
  } else {
    saveOnboardingDraft(onboardingSession);
    window.location.hash = '#/onboarding/analysis';
  }
}

function getDefaultValForType(type) {
  if (type === 'multi-select' || type === 'multi-select-pills' || type === 'skill-selector' || type === 'company-selector') {
    return [];
  }
  if (type === 'skill-level-matrix' || type === 'personal-identity' || type === 'employee-workplace' || type === 'textarea') {
    return {};
  }
  return '';
}

function renderSkillsBadges(container, list) {
  if (!container) return;
  if (list.length === 0) {
    container.innerHTML = `<div class="ts-q-empty-tags-hint">No skills added yet. Select from popular capabilities below or type your own.</div>`;
    return;
  }
  container.innerHTML = list.map(skill => `
    <span class="ts-q-skill-badge">
      <span>${skill}</span>
      <button type="button" class="remove-tag-btn" data-remove-skill="${skill}">×</button>
    </span>
  `).join('');
}

function renderCompanyBadges(container, list) {
  if (!container) return;
  if (list.length === 0) {
    container.innerHTML = `<div class="ts-q-empty-tags-hint">No target companies added yet. Click suggested employers below or skip.</div>`;
    return;
  }
  container.innerHTML = list.map(comp => `
    <span class="ts-q-skill-badge" style="background:#EEF2FF; color:#2735F5; border-color:#C7D2FE;">
      <span>${comp}</span>
      <button type="button" class="remove-tag-btn" data-remove-company="${comp}">×</button>
    </span>
  `).join('');
}

// ----------------------------------------------------------------------------
// SVG CONTEXTUAL ILLUSTRATION GENERATOR
// Clean, modern, soft 3D SaaS vector graphics for each question context
// ----------------------------------------------------------------------------
function renderContextualSvg(type, accent) {
  switch (type) {
    case 'profile':
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="80" fill="${accent}" fill-opacity="0.08"/>
          <circle cx="100" cy="80" r="32" fill="${accent}" fill-opacity="0.2"/>
          <circle cx="100" cy="76" r="24" fill="${accent}"/>
          <path d="M52 152C52 125.49 73.49 104 100 104C126.51 104 148 125.49 148 152" stroke="${accent}" stroke-width="8" stroke-linecap="round"/>
          <circle cx="140" cy="56" r="8" fill="#10B981"/>
        </svg>
      `;
    case 'skills':
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="40" y="40" width="120" height="120" rx="24" fill="${accent}" fill-opacity="0.06"/>
          <circle cx="100" cy="100" r="28" fill="${accent}"/>
          <circle cx="56" cy="64" r="16" fill="${accent}" fill-opacity="0.25"/>
          <circle cx="144" cy="64" r="16" fill="#10B981" fill-opacity="0.25"/>
          <circle cx="56" cy="136" r="16" fill="#F59E0B" fill-opacity="0.25"/>
          <circle cx="144" cy="136" r="16" fill="${accent}" fill-opacity="0.25"/>
          <line x1="72" y1="76" x2="88" y2="88" stroke="${accent}" stroke-width="3" stroke-dasharray="4 4"/>
          <line x1="128" y1="76" x2="112" y2="88" stroke="${accent}" stroke-width="3" stroke-dasharray="4 4"/>
        </svg>
      `;
    case 'target':
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="76" stroke="${accent}" stroke-width="4" stroke-opacity="0.2"/>
          <circle cx="100" cy="100" r="52" stroke="${accent}" stroke-width="6" stroke-opacity="0.4"/>
          <circle cx="100" cy="100" r="28" stroke="${accent}" stroke-width="8"/>
          <circle cx="100" cy="100" r="12" fill="${accent}"/>
          <path d="M100 24V44M100 156V176M24 100H44M156 100H176" stroke="${accent}" stroke-width="4" stroke-linecap="round"/>
        </svg>
      `;
    case 'journey':
    case 'experience':
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="44" y="128" width="24" height="40" rx="6" fill="${accent}" fill-opacity="0.2"/>
          <rect x="76" y="104" width="24" height="64" rx="6" fill="${accent}" fill-opacity="0.4"/>
          <rect x="108" y="76" width="24" height="92" rx="6" fill="${accent}" fill-opacity="0.7"/>
          <rect x="140" y="44" width="24" height="124" rx="6" fill="${accent}"/>
          <path d="M44 116L92 84L124 56L156 32" stroke="#10B981" stroke-width="4" stroke-linecap="round"/>
          <circle cx="156" cy="32" r="6" fill="#10B981"/>
        </svg>
      `;
    case 'roles':
    case 'companies':
    case 'workplace':
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="52" y="70" width="44" height="90" rx="8" fill="${accent}" fill-opacity="0.18"/>
          <rect x="104" y="44" width="52" height="116" rx="10" fill="${accent}"/>
          <rect x="116" y="58" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
          <rect x="134" y="58" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
          <rect x="116" y="76" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
          <rect x="134" y="76" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
          <rect x="116" y="94" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
          <rect x="134" y="94" width="10" height="10" rx="2" fill="#FFFFFF" fill-opacity="0.8"/>
        </svg>
      `;
    default:
      return `
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="70" fill="${accent}" fill-opacity="0.12"/>
          <path d="M72 100L92 120L132 80" stroke="${accent}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      `;
  }
}

function getIllustrationHeadline(category) {
  switch (category) {
    case 'About You': return 'Personalizing Your Workspace';
    case 'Skills': return 'Calibrating Competency Baseline';
    case 'Goals': return 'Focusing Career Trajectory';
    case 'Experience': return 'Benchmarking Seniority';
    case 'Preferences': return 'Targeting Opportunities';
    case 'Organization': return 'Configuring Enterprise Scope';
    case 'Capabilities': return 'Modeling Workforce Demands';
    case 'Decisions': return 'Optimizing Operational Signals';
    default: return 'Intelligent Profile Modeling';
  }
}

function getIllustrationSub(questionId) {
  if (questionId.includes('skills')) {
    return 'Your selections directly map into our skill graph to identify strengths and bridgeable gaps.';
  }
  if (questionId.includes('role')) {
    return 'This prototype explanation uses illustrative market context; it is not a live requisition analysis.';
  }
  if (questionId.includes('cmp')) {
    return 'Tailors your company intelligence view to identify high-risk skill clusters and internal mobility.';
  }
  return 'Every answer fine-tunes your personalized analytics before generating your intelligence report.';
}
