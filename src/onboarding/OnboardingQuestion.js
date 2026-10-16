// ============================================================================
// TALENTSCOPE.AI — REUSABLE ONBOARDING QUESTION COMPONENT
// Follows strict UX hierarchy: 1. WHAT  2. WHY  3. OPTIONS  4. ACTIONS
// Reusable across Individual, Employee, and Company onboarding flows
// ============================================================================

import { POPULAR_SKILLS, POPULAR_ROLES, POPULAR_COMPANIES, POPULAR_INDUSTRIES } from './onboarding-data.js';

export function renderQuestionComponent(question, currentValue = {}, userType = 'individual', previousAnswers = {}) {
  const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);

  return `
    <div class="ts-question-wrapper" data-question-id="${question.id}">
      <!-- 1. WHAT & 2. WHY -->
      <header class="ts-question-header">
        <span class="ts-question-category-tag">
          <i data-lucide="sparkle"></i>
          <span>${esc(question.category)}</span>
        </span>
        <h2 class="ts-question-title">${esc(question.title)}</h2>
        <p class="ts-question-why">${esc(question.why)}</p>
      </header>

      <!-- 3. OPTIONS / INPUT BODY -->
      <div class="ts-question-body">
        ${renderInputByType(question, currentValue, userType, previousAnswers)}
      </div>
    </div>
  `;
}

function renderInputByType(question, val = {}, userType, previousAnswers) {
  const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);

  // A. Personal Identity Fields
  if (question.type === 'personal-identity') {
    return `
      <div class="ts-q-fields-grid">
        ${question.fields.map(f => `
          <div class="ts-auth-field ${f.name === 'name' || f.name === 'companyName' ? 'full-width' : ''}">
            <label for="qf_${f.name}">${esc(f.label)}</label>
            ${f.type === 'select' ? `
              <select id="qf_${f.name}" class="ts-auth-input" name="${f.name}">
                ${f.options.map(opt => `
                  <option value="${esc(opt)}" ${(val[f.name] || '') === opt ? 'selected' : ''}>${esc(opt)}</option>
                `).join('')}
              </select>
            ` : `
              <input
                type="text"
                id="qf_${f.name}"
                class="ts-auth-input"
                placeholder="${esc(f.placeholder || '')}"
                value="${esc(val[f.name] || '')}"
                name="${f.name}"
                ${f.required ? 'required' : ''}
              />
            `}
          </div>
        `).join('')}
      </div>
    `;
  }

  // B. Single Select
  if (question.type === 'single-select') {
    const selected = typeof val === 'string' ? val : (val.selected || '');
    return `
      <div class="ts-q-options-list" role="radiogroup">
        ${question.options.map(opt => {
          const isSelected = selected === opt.label;
          return `
            <div
              class="ts-q-option-card ${isSelected ? 'is-selected' : ''}"
              data-option-value="${esc(opt.label)}"
              role="radio"
              aria-checked="${isSelected}"
              tabindex="0"
            >
              <div class="ts-q-option-left">
                ${opt.icon ? `
                  <div class="ts-q-option-icon">
                    <i data-lucide="${opt.icon}"></i>
                  </div>
                ` : ''}
                <div class="ts-q-option-copy">
                  <strong>${esc(opt.label)}</strong>
                  ${opt.desc ? `<small>${esc(opt.desc)}</small>` : ''}
                </div>
              </div>
              <div class="ts-q-option-radio ${isSelected ? 'is-checked' : ''}">
                <i data-lucide="check"></i>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  // C. Multi-Select Cards
  if (question.type === 'multi-select') {
    const selectedList = Array.isArray(val) ? val : (val.selected || []);
    return `
      <div class="ts-q-options-list">
        ${question.options.map(opt => {
          const isSelected = selectedList.includes(opt.label);
          return `
            <div
              class="ts-q-option-card ${isSelected ? 'is-selected' : ''}"
              data-multi-value="${esc(opt.label)}"
              role="checkbox"
              aria-checked="${isSelected}"
              tabindex="0"
            >
              <div class="ts-q-option-left">
                ${opt.icon ? `
                  <div class="ts-q-option-icon">
                    <i data-lucide="${opt.icon}"></i>
                  </div>
                ` : ''}
                <div class="ts-q-option-copy">
                  <strong>${esc(opt.label)}</strong>
                  ${opt.desc ? `<small>${esc(opt.desc)}</small>` : ''}
                </div>
              </div>
              <div class="ts-q-option-check ${isSelected ? 'is-checked' : ''}">
                <i data-lucide="check"></i>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  // D. Multi-Select Pills / Chips
  if (question.type === 'multi-select-pills') {
    const selectedList = Array.isArray(val) ? val : (val.selected || []);
    return `
      <div class="ts-q-pills-container">
        ${question.options.map(opt => {
          const isSelected = selectedList.includes(opt);
          return `
            <button
              type="button"
              class="ts-q-pill-btn ${isSelected ? 'is-selected' : ''}"
              data-pill-value="${esc(opt)}"
              aria-pressed="${isSelected}"
            >
              <i data-lucide="${isSelected ? 'check' : 'plus'}"></i>
              <span>${esc(opt)}</span>
            </button>
          `;
        }).join('')}
      </div>
    `;
  }

  // E. Experience with Conditional Student Field
  if (question.type === 'experience-conditional') {
    const currentExp = val.experience || (typeof val === 'string' ? val : '');
    const isStudent = previousAnswers['current_stage'] === 'Student' || currentExp.includes('No experience');
    return `
      <div class="ts-q-options-list" role="radiogroup">
        ${question.options.map(opt => {
          const isSelected = currentExp === opt.label;
          return `
            <div
              class="ts-q-option-card ${isSelected ? 'is-selected' : ''}"
              data-option-value="${esc(opt.label)}"
              role="radio"
              aria-checked="${isSelected}"
              tabindex="0"
            >
              <div class="ts-q-option-left">
                <div class="ts-q-option-copy">
                  <strong>${esc(opt.label)}</strong>
                  <small>${esc(opt.desc)}</small>
                </div>
              </div>
              <div class="ts-q-option-radio ${isSelected ? 'is-checked' : ''}">
                <i data-lucide="check"></i>
              </div>
            </div>
          `;
        }).join('')}
      </div>

      ${isStudent ? `
        <div style="margin-top: 20px; padding: 18px 20px; background: #FAF5FF; border: 1px solid #EADBFF; border-radius: 14px;">
          <label for="qf_studyField" style="display: block; font-size: 13.5px; font-weight: 700; color: #351C66; margin-bottom: 6px;">
            ${esc(question.studyFieldPrompt || 'What is your field of study?')}
          </label>
          <input
            type="text"
            id="qf_studyField"
            class="ts-auth-input"
            placeholder="e.g. Computer Science, AI, Business, Mechanical, etc."
            value="${esc(val.studyField || '')}"
          />
        </div>
      ` : ''}
    `;
  }

  // F. Searchable Skill Selector
  if (question.type === 'skill-selector') {
    const skills = Array.isArray(val) ? val : (val.skills || []);
    return `
      <div class="ts-q-search-selector">
        <div class="ts-auth-input-wrap">
          <i data-lucide="search" class="prefix-icon"></i>
          <input
            type="text"
            id="skillSearchInput"
            class="ts-auth-input"
            placeholder="Search or type a skill (press Enter to add)..."
          />
          <button type="button" class="ts-q-add-btn" id="btnAddSearchedSkill">
            <i data-lucide="plus"></i>
            <span>Add</span>
          </button>
        </div>

        <!-- Selected Skills Badges -->
        <div class="ts-q-selected-tags-area" id="selectedSkillsArea">
          ${skills.length === 0 ? `
            <div class="ts-q-empty-tags-hint">No skills added yet. Select from popular capabilities below or type your own.</div>
          ` : skills.map(skill => `
            <span class="ts-q-skill-badge">
              <span>${esc(skill)}</span>
              <button type="button" class="remove-tag-btn" data-remove-skill="${esc(skill)}" title="Remove ${esc(skill)}">×</button>
            </span>
          `).join('')}
        </div>

        <!-- Popular Suggested Skills -->
        <div class="ts-q-suggestions-block">
          <span class="ts-q-suggestions-label">Popular capabilities:</span>
          <div class="ts-q-suggestions-list">
            ${POPULAR_SKILLS.filter(s => !skills.includes(s)).slice(0, 14).map(skill => `
              <button type="button" class="ts-q-suggest-chip" data-add-suggested-skill="${esc(skill)}">
                <i data-lucide="plus"></i>
                <span>${esc(skill)}</span>
              </button>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  // G. Skill Level Matrix
  if (question.type === 'skill-level-matrix') {
    const fallbackSkills = userType === 'individual' ? [] : ['Python', 'SQL', 'Git'];
    const rawSkills = previousAnswers['skills'] || previousAnswers['emp_skills'] || fallbackSkills;
    const skills = Array.isArray(rawSkills) ? rawSkills : (rawSkills.skills || fallbackSkills);
    const levelMap = typeof val === 'object' && !Array.isArray(val) ? val : {};

    return `
      <div class="ts-q-level-matrix">
        <p style="font-size: 13px; color: #6C6078; margin: 0 0 16px;">
          Rate your familiarity with each capability so we can adjust roadmap difficulty:
        </p>

        <div class="ts-q-matrix-rows">
          ${skills.slice(0, 8).map(skill => {
            const currentLevel = levelMap[skill] || 'Comfortable';
            return `
              <div class="ts-q-matrix-row" data-skill-row="${esc(skill)}">
                <div class="ts-q-matrix-skill-name">
                  <i data-lucide="layers"></i>
                  <strong>${esc(skill)}</strong>
                </div>
                <div class="ts-q-level-pill-group">
                  ${question.levels.map(lvl => `
                    <button
                      type="button"
                      class="ts-q-level-pill ${currentLevel === lvl.key ? 'is-active' : ''}"
                      data-level-skill="${esc(skill)}"
                      data-level-key="${lvl.key}"
                      title="${esc(lvl.desc)}"
                    >
                      <span>${lvl.label}</span>
                    </button>
                  `).join('')}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  // H. Role Selector
  if (question.type === 'role-selector') {
    const selectedRole = typeof val === 'string' ? val : (val.role || '');
    return `
      <div class="ts-q-search-selector">
        <div class="ts-auth-input-wrap">
          <i data-lucide="search" class="prefix-icon"></i>
          <input
            type="text"
            id="roleSearchInput"
            class="ts-auth-input"
            placeholder="Search target role (e.g. AI Engineer, Product Manager)..."
            value="${esc(selectedRole)}"
          />
        </div>

        <div class="ts-q-suggestions-block" style="margin-top: 16px;">
          <span class="ts-q-suggestions-label">Trending roles:</span>
          <div class="ts-q-suggestions-list">
            ${POPULAR_ROLES.map(role => `
              <button
                type="button"
                class="ts-q-suggest-chip ${selectedRole === role ? 'is-selected-role' : ''}"
                data-select-role="${esc(role)}"
              >
                <i data-lucide="${selectedRole === role ? 'check' : 'briefcase'}"></i>
                <span>${esc(role)}</span>
              </button>
            `).join('')}
          </div>
        </div>

        ${question.allowNotSure ? `
          <div style="margin-top: 16px; padding-top: 14px; border-top: 1px dashed #E2D9E8;">
            <button
              type="button"
              class="ts-q-pill-btn ${selectedRole === 'Not sure yet' ? 'is-selected' : ''}"
              data-select-role="Not sure yet"
            >
              <i data-lucide="compass"></i>
              <span>Not sure yet — help me explore options based on my skills</span>
            </button>
          </div>
        ` : ''}
      </div>
    `;
  }

  // I. Company Selector
  if (question.type === 'company-selector') {
    const companies = Array.isArray(val) ? val : (val.companies || []);
    return `
      <div class="ts-q-search-selector">
        <div class="ts-auth-input-wrap">
          <i data-lucide="building" class="prefix-icon"></i>
          <input
            type="text"
            id="companySearchInput"
            class="ts-auth-input"
            placeholder="Type company name (press Enter to add)..."
          />
          <button type="button" class="ts-q-add-btn" id="btnAddCompany">
            <i data-lucide="plus"></i>
            <span>Add</span>
          </button>
        </div>

        <div class="ts-q-selected-tags-area" id="selectedCompaniesArea">
          ${companies.length === 0 ? `
            <div class="ts-q-empty-tags-hint">No target companies added yet. Click suggested employers below or skip.</div>
          ` : companies.map(c => `
            <span class="ts-q-skill-badge" style="background:#EEF2FF; color:#2735F5; border-color:#C7D2FE;">
              <span>${esc(c)}</span>
              <button type="button" class="remove-tag-btn" data-remove-company="${esc(c)}">×</button>
            </span>
          `).join('')}
        </div>

        <div class="ts-q-suggestions-block">
          <span class="ts-q-suggestions-label">Top employers hiring in workforce tech:</span>
          <div class="ts-q-suggestions-list">
            ${POPULAR_COMPANIES.filter(c => !companies.includes(c)).map(c => `
              <button type="button" class="ts-q-suggest-chip" data-add-suggested-company="${esc(c)}">
                <i data-lucide="plus"></i>
                <span>${esc(c)}</span>
              </button>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  // J. Employee Workplace
  if (question.type === 'employee-workplace') {
    const isConnected = previousAnswers['employeeType'] === 'company-connected' || userType === 'employee';
    return `
      <div class="ts-q-fields-grid">
        ${isConnected ? `
          <div class="ts-auth-field full-width">
            <label for="qf_company">Current Company</label>
            <input type="text" id="qf_company" class="ts-auth-input" placeholder="e.g. TechCorp Global" value="${esc(val.company || previousAnswers['companyName'] || 'TechCorp Global')}" required />
          </div>
          <div class="ts-auth-field">
            <label for="qf_department">Department / Team</label>
            <input type="text" id="qf_department" class="ts-auth-input" placeholder="e.g. Platform Engineering" value="${esc(val.department || '')}" />
          </div>
        ` : `
          <div class="ts-auth-field full-width">
            <label for="qf_industry">Industry Focus</label>
            <select id="qf_industry" class="ts-auth-input">
              ${POPULAR_INDUSTRIES.map(ind => `
                <option value="${esc(ind)}" ${(val.industry || '') === ind ? 'selected' : ''}>${esc(ind)}</option>
              `).join('')}
            </select>
          </div>
        `}
        <div class="ts-auth-field">
          <label for="qf_currentRole">Current Role Title</label>
          <input type="text" id="qf_currentRole" class="ts-auth-input" placeholder="e.g. Software Engineer" value="${esc(val.currentRole || '')}" required />
        </div>
      </div>
    `;
  }

  // K. Textarea
  if (question.type === 'textarea') {
    const textVal = typeof val === 'string' ? val : (val.text || '');
    return `
      <div class="ts-auth-field">
        <textarea
          id="qf_textarea"
          class="ts-q-textarea"
          placeholder="${esc(question.placeholder || 'Type here...')}"
          rows="5"
        >${esc(textVal)}</textarea>
      </div>
    `;
  }

  return `<div class="ts-q-unsupported">Standard input</div>`;
}
