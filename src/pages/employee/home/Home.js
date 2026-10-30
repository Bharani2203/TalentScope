// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE HOME
// High-hierarchy, action-oriented overview powered by authenticated onboarding data
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
} from '../../../data/employee/employee-data.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeSkeleton() {
  return `
    <div class="employee-page emp-skeleton-page" role="status" aria-live="polite" aria-label="Loading your employee profile">
      <div class="emp-skeleton-hero">
        <div class="emp-skeleton-shimmer" style="width: 160px; height: 18px; border-radius: 6px; margin-bottom: 14px;"></div>
        <div class="emp-skeleton-shimmer" style="width: 340px; height: 38px; border-radius: 10px; margin-bottom: 14px;"></div>
        <div class="emp-skeleton-shimmer" style="width: 65%; height: 16px; border-radius: 6px;"></div>
      </div>

      <div class="emp-skeleton-accent">
        <div class="emp-skeleton-shimmer" style="width: 100%; height: 130px; border-radius: 18px;"></div>
      </div>

      <div class="emp-grid-4">
        <div class="emp-skeleton-card">
          <div class="emp-skeleton-shimmer" style="width: 90px; height: 18px; border-radius: 6px; margin-bottom: 12px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 140px; height: 26px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 14px; border-radius: 6px;"></div>
        </div>
        <div class="emp-skeleton-card">
          <div class="emp-skeleton-shimmer" style="width: 90px; height: 18px; border-radius: 6px; margin-bottom: 12px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 140px; height: 26px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 14px; border-radius: 6px;"></div>
        </div>
        <div class="emp-skeleton-card">
          <div class="emp-skeleton-shimmer" style="width: 90px; height: 18px; border-radius: 6px; margin-bottom: 12px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 140px; height: 26px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 14px; border-radius: 6px;"></div>
        </div>
        <div class="emp-skeleton-card">
          <div class="emp-skeleton-shimmer" style="width: 90px; height: 18px; border-radius: 6px; margin-bottom: 12px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 140px; height: 26px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 14px; border-radius: 6px;"></div>
        </div>
      </div>

      <div class="emp-grid-4">
        <div class="emp-skeleton-card" style="height: 190px;">
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 16px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 100%; height: 32px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 75%; height: 32px; border-radius: 8px;"></div>
        </div>
        <div class="emp-skeleton-card" style="height: 190px;">
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 16px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 100%; height: 32px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 75%; height: 32px; border-radius: 8px;"></div>
        </div>
        <div class="emp-skeleton-card" style="height: 190px;">
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 16px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 100%; height: 32px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 75%; height: 32px; border-radius: 8px;"></div>
        </div>
        <div class="emp-skeleton-card" style="height: 190px;">
          <div class="emp-skeleton-shimmer" style="width: 110px; height: 18px; border-radius: 6px; margin-bottom: 16px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 100%; height: 32px; border-radius: 8px; margin-bottom: 8px;"></div>
          <div class="emp-skeleton-shimmer" style="width: 75%; height: 32px; border-radius: 8px;"></div>
        </div>
      </div>
    </div>
  `;
}

function renderIncompleteProfileHome() {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return `
    <div class="employee-page">
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="sparkles"></i> WELCOME TO TALENTSCOPE</span>
          <h1 class="emp-hero-title">${greeting}</h1>
          <p class="emp-hero-desc">Complete your employee profile to unlock personalized skill intelligence, promotion pathways, and market alignment metrics.</p>
        </div>
        <div class="emp-hero-actions">
          <a href="#/onboarding/employee" class="emp-btn-primary"><i data-lucide="arrow-right"></i><span>Complete Profile</span></a>
        </div>
      </section>

      <section class="emp-card emp-empty-state-card" style="text-align: center; padding: 48px 24px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <div class="emp-icon-box emp-icon-box--primary" style="width: 56px; height: 56px; border-radius: 16px; margin-bottom: 16px;">
          <i data-lucide="user-plus" style="width: 28px; height: 28px;"></i>
        </div>
        <h2 class="emp-card-title" style="font-size: 20px; font-weight: 800; margin-bottom: 8px;">No Onboarding Profile Found</h2>
        <p style="color: var(--emp-text-secondary); max-width: 500px; font-size: 14px; line-height: 1.5; margin: 0 0 24px;">
          Your employee onboarding answers have not been completed yet. Share your organization, role, and current skills to unlock your customized growth console.
        </p>
        <div style="display: flex; gap: 12px; align-items: center; justify-content: center; flex-wrap: wrap;">
          <a href="#/onboarding/employee" class="emp-btn-primary">
            <i data-lucide="sparkles"></i>
            <span>Start Onboarding</span>
          </a>
          <button type="button" class="emp-btn-secondary" id="btnRefreshEmployeeProfile">
            <i data-lucide="refresh-cw"></i>
            <span>Refresh Status</span>
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderEmployeeOnboardingHome(profile) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const name = profile.shortName ? `, ${esc(profile.shortName)}` : '';
  const currentSkills = Array.isArray(profile.skills) ? profile.skills : [];
  const targetSkills = Array.isArray(profile.desiredSkills) ? profile.desiredSkills : [];
  const growthPriorities = Array.isArray(profile.growthPriorities) ? profile.growthPriorities : [];
  const preferredHelp = Array.isArray(profile.preferredHelp) ? profile.preferredHelp : [];

  const company = profile.company || 'Workplace not provided';
  const role = profile.role || 'Role details not provided';
  const department = profile.department || '';
  const experience = profile.experience || 'Not provided yet';
  const weeklyLearningTime = profile.weeklyLearningTime || 'Not provided yet';
  const targetRole = profile.targetRole || 'Not provided yet';
  const careerGoal = profile.careerGoal || '';
  const location = [profile.city, profile.country].filter(Boolean).join(', ');
  const primaryMilestone = preferredHelp.length && preferredHelp[0] ? preferredHelp[0] : (targetRole !== 'Not provided yet' ? targetRole : 'Skill Development');

  return `
    <div class="employee-page">
      <!-- 1. PROFILE HEADER / HERO -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="sparkles"></i> TALENTSCOPE WORKFORCE INTELLIGENCE</span>
          <h1 class="emp-hero-title">${greeting}${name}</h1>
          
          <div class="emp-hero-meta-row">
            <span class="emp-hero-pill emp-hero-pill--role">
              <i data-lucide="briefcase"></i>
              <span>${esc(role)}</span>
            </span>
            <span class="emp-hero-pill emp-hero-pill--company">
              <i data-lucide="building-2"></i>
              <span>${esc(company)}</span>
            </span>
            ${department ? `
              <span class="emp-hero-pill emp-hero-pill--dept">
                <i data-lucide="users"></i>
                <span>${esc(department)}</span>
              </span>
            ` : ''}
            ${location ? `
              <span class="emp-hero-pill emp-hero-pill--location">
                <i data-lucide="map-pin"></i>
                <span>${esc(location)}</span>
              </span>
            ` : ''}
          </div>

          <p class="emp-hero-desc">Your portal reflects the answers you provided during onboarding. Company and skill details are self-reported unless separately verified.</p>
        </div>
        <div class="emp-hero-actions">
          <a href="#/employee/skills" class="emp-btn-primary">
            <i data-lucide="layers-3"></i>
            <span>Review My Skills</span>
          </a>
          <a href="#/employee/growth" class="emp-btn-secondary">
            <i data-lucide="trending-up"></i>
            <span>Continue Learning</span>
          </a>
        </div>
      </section>

      <!-- 2. CAREER DIRECTION STANDOUT ACCENT CARD -->
      <section class="emp-accent-card emp-career-accent">
        <div class="emp-career-accent-header">
          <div class="emp-career-accent-title-group">
            <span class="emp-badge emp-badge-primary"><i data-lucide="compass"></i> Targeted Career Direction</span>
            <h2 class="emp-accent-title">Career Trajectory & Growth Pathway</h2>
          </div>
          <span class="emp-badge emp-badge-accent-soft"><i data-lucide="sparkles"></i> Self-Directed Pathway</span>
        </div>

        <div class="emp-career-flow">
          <div class="emp-flow-node emp-flow-node--current">
            <div class="emp-flow-icon"><i data-lucide="user-check"></i></div>
            <div class="emp-flow-content">
              <span class="emp-flow-label">Current Role</span>
              <strong class="emp-flow-value">${esc(role)}</strong>
              <span class="emp-flow-sub">${esc(company)}</span>
            </div>
          </div>

          <div class="emp-flow-connector">
            <div class="emp-flow-line"></div>
            <div class="emp-flow-badge"><i data-lucide="arrow-right"></i></div>
          </div>

          <div class="emp-flow-node emp-flow-node--target">
            <div class="emp-flow-icon emp-flow-icon--target"><i data-lucide="target"></i></div>
            <div class="emp-flow-content">
              <span class="emp-flow-label">Target Milestone</span>
              <strong class="emp-flow-value emp-flow-value--target">${esc(targetRole)}</strong>
              <span class="emp-flow-sub">${esc(careerGoal || 'Stated career advancement direction')}</span>
            </div>
          </div>
        </div>

        <div class="emp-career-accent-footer">
          <div class="emp-career-hint">
            <i data-lucide="info"></i>
            <span>Your stated direction guides skill gap analysis and recommended learning milestones.</span>
          </div>
          <a href="#/employee/growth" class="emp-btn-secondary emp-btn-sm">
            <span>Explore Career Track</span>
            <i data-lucide="arrow-right"></i>
          </a>
        </div>
      </section>

      <!-- 3. METRIC CARDS WITH RELEVANT ICONS -->
      <section class="emp-grid-4">
        <article class="emp-card emp-metric-card">
          <div class="emp-metric-header">
            <span class="emp-badge emp-badge-primary">Workplace</span>
            <div class="emp-icon-box emp-icon-box--primary"><i data-lucide="building-2"></i></div>
          </div>
          <div class="emp-metric-body">
            <h2 class="emp-metric-val">${esc(company)}</h2>
            <p class="emp-metric-sub">${esc(department || role)}</p>
            ${location ? `<p class="emp-metric-meta"><i data-lucide="map-pin"></i> ${esc(location)}</p>` : ''}
          </div>
        </article>

        <article class="emp-card emp-metric-card">
          <div class="emp-metric-header">
            <span class="emp-badge emp-badge-primary">Field Experience</span>
            <div class="emp-icon-box emp-icon-box--primary"><i data-lucide="briefcase"></i></div>
          </div>
          <div class="emp-metric-body">
            <h2 class="emp-metric-val">${esc(experience)}</h2>
            <p class="emp-metric-sub">Based on your onboarding response</p>
            <p class="emp-metric-meta"><i data-lucide="award"></i> Industry experience tenure</p>
          </div>
        </article>

        <article class="emp-card emp-metric-card">
          <div class="emp-metric-header">
            <span class="emp-badge emp-badge-primary">Weekly Learning Time</span>
            <div class="emp-icon-box emp-icon-box--primary"><i data-lucide="clock"></i></div>
          </div>
          <div class="emp-metric-body">
            <h2 class="emp-metric-val">${esc(weeklyLearningTime)}</h2>
            <p class="emp-metric-sub">Committed learning availability</p>
            <p class="emp-metric-meta"><i data-lucide="calendar"></i> Self-paced schedule</p>
          </div>
        </article>

        <article class="emp-card emp-metric-card">
          <div class="emp-metric-header">
            <span class="emp-badge emp-badge-success">Primary Milestone</span>
            <div class="emp-icon-box emp-icon-box--success"><i data-lucide="flag"></i></div>
          </div>
          <div class="emp-metric-body">
            <h2 class="emp-metric-val">${esc(primaryMilestone)}</h2>
            <p class="emp-metric-sub">Selected onboarding milestone</p>
            <p class="emp-metric-meta"><i data-lucide="target"></i> Focus priority</p>
          </div>
        </article>
      </section>

      <!-- 4. SKILLS & DEVELOPMENT VISUALS -->
      <section class="emp-grid-4">
        <article class="emp-card emp-skills-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-primary"><i data-lucide="check-circle-2"></i> Current Stack</span>
              <h2 class="emp-card-title" style="margin-top: 6px;">Skills you use</h2>
              <p class="emp-card-subtitle">Active technical capabilities</p>
            </div>
            <div class="emp-icon-box emp-icon-box--primary"><i data-lucide="code-2"></i></div>
          </div>
          <div class="emp-tags-wrapper">
            ${currentSkills.length ? currentSkills.map(skill => {
              const level = profile.skillLevels?.[skill];
              return `
                <span class="emp-tag emp-tag--current">
                  <i data-lucide="check"></i>
                  <span class="emp-tag-text">${esc(skill)}</span>
                  ${level ? `<span class="emp-tag-confidence">${esc(level)}</span>` : ''}
                </span>
              `;
            }).join('') : '<span class="emp-empty-tag">No skills added yet</span>'}
          </div>
        </article>

        <article class="emp-card emp-skills-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-warning"><i data-lucide="trending-up"></i> Target Stack</span>
              <h2 class="emp-card-title" style="margin-top: 6px;">Skills you want to build</h2>
              <p class="emp-card-subtitle">Desired growth competencies</p>
            </div>
            <div class="emp-icon-box emp-icon-box--warning"><i data-lucide="sparkles"></i></div>
          </div>
          <div class="emp-tags-wrapper">
            ${targetSkills.length ? targetSkills.map(skill => `
              <span class="emp-tag emp-tag--target">
                <i data-lucide="plus"></i>
                <span class="emp-tag-text">${esc(skill)}</span>
              </span>
            `).join('') : '<span class="emp-empty-tag">No target skills added yet</span>'}
          </div>
        </article>

        <article class="emp-card emp-skills-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-neutral"><i data-lucide="compass"></i> Development</span>
              <h2 class="emp-card-title" style="margin-top: 6px;">Areas to improve</h2>
              <p class="emp-card-subtitle">Growth priorities</p>
            </div>
            <div class="emp-icon-box"><i data-lucide="arrow-up-right"></i></div>
          </div>
          <div class="emp-tags-wrapper">
            ${growthPriorities.length ? growthPriorities.map(area => `
              <span class="emp-tag emp-tag--growth">
                <i data-lucide="circle-dot"></i>
                <span class="emp-tag-text">${esc(area)}</span>
              </span>
            `).join('') : '<span class="emp-empty-tag">Not provided yet</span>'}
          </div>
        </article>

        <article class="emp-card emp-skills-card">
          <div class="emp-card-header">
            <div>
              <span class="emp-badge emp-badge-success"><i data-lucide="help-circle"></i> Support</span>
              <h2 class="emp-card-title" style="margin-top: 6px;">Where you want help</h2>
              <p class="emp-card-subtitle">Mentorship & learning aids</p>
            </div>
            <div class="emp-icon-box emp-icon-box--success"><i data-lucide="heart-handshake"></i></div>
          </div>
          <div class="emp-tags-wrapper">
            ${preferredHelp.length ? preferredHelp.map(item => `
              <span class="emp-tag emp-tag--support">
                <i data-lucide="check"></i>
                <span class="emp-tag-text">${esc(item)}</span>
              </span>
            `).join('') : '<span class="emp-empty-tag">Not provided yet</span>'}
          </div>
        </article>
      </section>
    </div>
  `;
}

export function renderEmployeeHome() {
  const p = getEmployeeProfile();
  if (p.profileLoaded) return renderEmployeeOnboardingHome(p);
  return renderIncompleteProfileHome();
}

export function bindEmployeeHomeEvents(rerender) {
  const refreshBtn = document.querySelector('#btnRefreshEmployeeProfile');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (typeof rerender === 'function') {
        rerender();
      } else {
        window.dispatchEvent(new CustomEvent('talentscope-auth-state-changed'));
      }
    });
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
