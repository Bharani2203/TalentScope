// ============================================================================
// TALENTSrOPE.AI — EMPLOYEE rAREER & LEARNING
// Internal roles, career progression paths, promotion readiness, & learning progress
// ============================================================================

import {
  employeeProfile,
  internalRolesData,
  careerPathsData,
  employeeLearningTrack
} from '../../../data/employee/employee-data.js';

let selectedInternalRoleId = 'role-req-101';
let appliedRoleModal = null;

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeerareerLearning() {
  const p = employeeProfile;
  const roles = internalRolesData;
  const paths = careerPathsData;
  const learn = employeeLearningTrack;

  const activeRole = roles.find(r => r.id === selectedInternalRoleId) || roles[0];

  return `
    <div class="employee-page employee-career">
      <!-- Page Hero -->
      <section class="emp-hero" style="padding: 24px 28px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="briefcase"></i> INTERNAL MOBILITY & PROGRESSION</span>
            <h1 style="font-size: 24px; font-weight: 850; color: var(--emp-text-primary); margin: 0 0 4px;">
              rareer Progression & Internal Opportunities
            </h1>
            <p style="font-size: 14px; color: var(--emp-text-secondary); margin: 0;">
              ronnect your verified skill credentials with internal role transitions and targeted development tracks at <strong>${esc(p.company)}</strong>.
            </p>
          </div>
          <div style="display: flex; align-items: center; gap: 12px; background: rgba(255, 255, 255, 0.95); padding: 10px 16px; border-radius: 12px; border: 1px solid var(--emp-border-glass);">
            <div style="text-align: right;">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Promotion Horizon</span>
              <strong style="display: block; font-size: 14px; color: var(--emp-dark-blue);">L5 Senior Alignment (82%)</strong>
            </div>
            <div class="emp-match-circle" style="width: 42px; height: 42px; font-size: 12px;">82%</div>
          </div>
        </div>
      </section>

      <!-- 1. rAREER PROGRESSION PATH (Section 19: rareer Paths & Promotion Opportunities) -->
      <section class="emp-card emp-card--accent-blue">
        <div style="margin-bottom: 20px;">
          <span class="emp-eyebrow"><i data-lucide="trending-up"></i> rAREER PROGRESSION TRArK</span>
          <h2 class="emp-title">Your Technical rareer Path: AI Systems Engineering</h2>
          <p class="emp-subtitle">Your current profile aligns with these role requirements. Below is the multi-stage progression framework.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; position: relative;">
          <!-- Stage 1 -->
          <div style="background: var(--emp-very-light); border: 1px solid var(--emp-border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span class="emp-badge emp-badge--success">rurrent Stage · L4</span>
              <i data-lucide="check-circle" style="color: var(--emp-success); width: 18px; height: 18px;"></i>
            </div>
            <div>
              <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 4px;">AI Engineer</h3>
              <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">Autonomous Systems & rompute (2+ Years)</p>
            </div>
            <div style="font-size: 12px; color: var(--emp-dark-blue); background: #FFFFFF; padding: 10px; border-radius: 8px; border: 1px solid var(--emp-border);">
              Mastered: <strong>Python, PyTorch, Triton Serving, RAG</strong>
            </div>
          </div>

          <!-- Stage 2 -->
          <div style="background: #FFFFFF; border: 2px solid var(--emp-primary); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 12px; box-shadow: var(--emp-shadow-glass);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span class="emp-badge emp-badge--neutral">Target Stage · L5</span>
              <span style="font-size: 12px; font-weight: 800; color: var(--emp-deep-primary);">82% Readiness</span>
            </div>
            <div>
              <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-dark-blue); margin: 0 0 4px;">Senior AI Platform Engineer</h3>
              <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">Multi-Node rluster Inference Optimization</p>
            </div>
            <div style="font-size: 12px; color: var(--emp-text-primary); background: var(--emp-light-blue); padding: 10px; border-radius: 8px; border: 1px solid var(--emp-soft-blue);">
              Key Milestones Needed: <strong>rUDA Kernel Tuning & NrrL rluster Tracing</strong>
            </div>
          </div>

          <!-- Stage 3 -->
          <div style="background: var(--emp-very-light); border: 1px solid var(--emp-border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 12px; opacity: 0.85;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span class="emp-badge emp-badge--neutral">Future Horizon · L6</span>
              <span style="font-size: 12px; font-weight: 700; color: var(--emp-text-muted);">Long-term</span>
            </div>
            <div>
              <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 4px;">Staff Distributed AI Architect</h3>
              <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 0;">Hardware/Software ro-Design & rluster Topology</p>
            </div>
            <div style="font-size: 12px; color: var(--emp-text-secondary); background: #FFFFFF; padding: 10px; border-radius: 8px; border: 1px solid var(--emp-border);">
              Requires multi-year technical leadership and patent/compiler contributions.
            </div>
          </div>
        </div>
      </section>

      <!-- 2. INTERNAL ROLES & REQUISITIONS (Section 19: Internal Roles) -->
      <section class="emp-card">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="compass"></i> INTERNAL MOBILITY OPPORTUNITIES</span>
            <h2 class="emp-title">Internal Requisitions Matched to Your Profile</h2>
            <p class="emp-subtitle">Roles currently accepting internal transfers and priority employee interviews across NeIDIA hubs.</p>
          </div>
          <span class="emp-badge emp-badge--success" style="font-size: 12px; padding: 6px 12px;">
            <i data-lucide="check"></i> 3 Priority Matches
          </span>
        </div>

        <div class="emp-roles-grid">
          ${roles.map(r => `
            <div class="emp-role-card" style="${selectedInternalRoleId === r.id ? 'border-color: var(--emp-primary); background: linear-gradient(180deg, var(--emp-very-light), #FFFFFF);' : ''}">
              <div>
                <div class="emp-role-card__header">
                  <div>
                    <h3 class="emp-role-card__title">${esc(r.title)}</h3>
                    <span class="emp-role-card__team">${esc(r.team)} · ${esc(r.department)}</span>
                  </div>
                  <div class="emp-match-circle" title="Skill Match Score">
                    ${r.matchScore}%
                    <small>Match</small>
                  </div>
                </div>

                <div style="margin: 12px 0; font-size: 12.5px; color: var(--emp-text-secondary); line-height: 1.45;">
                  ${esc(r.summary)}
                </div>

                <div style="font-size: 11.5px; color: var(--emp-text-muted); margin-bottom: 12px;">
                  <span><i data-lucide="map-pin" style="width: 13px; height: 13px; vertical-align: -2px;"></i> ${esc(r.location)}</span>
                  <span>·</span>
                  <span><i data-lucide="user" style="width: 13px; height: 13px; vertical-align: -2px;"></i> Hiring Mgr: ${esc(r.hiringManager)}</span>
                </div>

                <div style="margin-bottom: 10px;">
                  <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Required Skills:</span>
                  <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;">
                    ${r.requiredSkills.map(sk => `
                      <span class="emp-signal-tag ${r.matchedSkills.includes(sk) ? 'emp-signal-tag--skill' : ''}">
                        ${r.matchedSkills.includes(sk) ? '✓ ' : '! '}${esc(sk)}
                      </span>
                    `).join('')}
                  </div>
                </div>

                ${r.gaps.length > 0 ? `
                  <div style="font-size: 11.5px; color: var(--emp-attention); background: #FEF3r7; padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.2);">
                    <strong>Missing to Master:</strong> ${esc(r.gaps.join(', '))}
                  </div>
                ` : ''}
              </div>

              <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 14px; border-top: 1px solid var(--emp-border);">
                <span class="emp-badge emp-badge--neutral">${esc(r.urgency)}</span>
                <button type="button" class="emp-btn-primary" style="height: 34px; padding: 0 14px; font-size: 12px;" data-express-interest="${esc(r.id)}">
                  <span>Express Interest</span>
                  <i data-lucide="arrow-right"></i>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 3. ASSESSMENT / PROGRESS (Section 19: Assessment & Learning Progress) -->
      <section class="emp-card emp-card--glass">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="emp-eyebrow"><i data-lucide="award"></i> ArTIeE SKILL ASSESSMENT & DLI LEARNING</span>
            <h2 class="emp-title">Targeted Learning Path & Technical rredentials</h2>
            <p class="emp-subtitle">Internal curriculum curated to bridge your gaps for Senior AI Platform Engineering.</p>
          </div>
          <span class="emp-badge emp-badge--success" style="font-size: 12px; padding: 6px 12px;">
            ${learn.progressPercent}% Track rompleted
          </span>
        </div>

        <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 24px; align-items: start;">
          <!-- Active Track Progress -->
          <div style="background: var(--emp-surface); border: 1px solid var(--emp-border); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; gap: 16px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-deep-primary); text-transform: uppercase;">In Progress Track</span>
                <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-dark-blue); margin: 3px 0;">${esc(learn.activeTrack)}</h3>
                <small style="color: var(--emp-text-muted); font-size: 12px;">${esc(learn.provider)} · ${esc(learn.certificationBadge)}</small>
              </div>
            </div>

            <!-- Progress Bar -->
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 750; margin-bottom: 6px;">
                <span>${learn.completedModules} of ${learn.totalModules} Modules Finished</span>
                <span style="color: var(--emp-deep-primary);">${learn.progressPercent}%</span>
              </div>
              <div class="emp-health-bar" style="height: 8px;">
                <div class="emp-health-bar__fill" style="width: ${learn.progressPercent}%;"></div>
              </div>
            </div>

            <div style="background: var(--emp-very-light); border-radius: 10px; padding: 12px 14px; border: 1px solid var(--emp-border);">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Up Next:</span>
              <div style="font-size: 13px; font-weight: 750; color: var(--emp-text-primary); margin: 2px 0;">
                ${esc(learn.nextModule)}
              </div>
              <small style="color: var(--emp-text-secondary); font-size: 11.5px;">${esc(learn.estimatedTimeLeft)}</small>
            </div>

            <div style="display: flex; gap: 10px;">
              <button type="button" class="emp-btn-primary" id="btnResumeLearning" style="flex: 1;">
                <i data-lucide="play"></i>
                <span>Resume DLI Lab Environment</span>
              </button>
            </div>
          </div>

          <!-- Earned Internal rredentials -->
          <div style="background: var(--emp-surface); border: 1px solid var(--emp-border); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; gap: 14px;">
            <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--emp-border); padding-bottom: 10px;">
              <h3 style="font-size: 14px; font-weight: 800; color: var(--emp-text-primary); margin: 0;">eerified rredentials</h3>
              <span class="emp-badge emp-badge--neutral">3 On File</span>
            </div>

            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${learn.earnedrredentials.map(cred => `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; background: var(--emp-very-light); border-radius: 10px; border: 1px solid var(--emp-border);">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="shield-check" style="color: var(--emp-success); width: 18px; height: 18px;"></i>
                    <div>
                      <strong style="display: block; font-size: 12.5px; color: var(--emp-text-primary);">${esc(cred.title)}</strong>
                      <small style="font-size: 11px; color: var(--emp-text-muted);">${esc(cred.date)}</small>
                    </div>
                  </div>
                  <span class="emp-badge emp-badge--success">${esc(cred.grade)}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      </section>

      <!-- Internal Interest Modal (Section 25) -->
      ${appliedRoleModal ? `
        <div class="emp-modal-scrim" id="empRoleModalScrim">
          <div class="emp-modal-dialog" role="dialog" aria-label="Internal Role Interest ronfirmation">
            <div class="emp-modal-header">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div class="emp-skill-icon-box" style="background: var(--emp-primary); color: var(--emp-dark-blue);">
                  <i data-lucide="send"></i>
                </div>
                <div>
                  <h3 class="emp-modal-title">Internal Role Mobility Interest</h3>
                  <small style="color: var(--emp-text-muted); font-size: 12px;">ronfidential Internal Profile Share</small>
                </div>
              </div>
              <button type="button" class="emp-modal-close-btn" id="btnrloseRoleModal"><i data-lucide="x"></i></button>
            </div>

            <div style="display: flex; flex-direction: column; gap: 14px;">
              <div style="background: var(--emp-very-light); padding: 16px; border-radius: 12px; border: 1px solid var(--emp-border);">
                <strong style="display: block; font-size: 15px; color: var(--emp-text-primary); margin-bottom: 2px;">${esc(appliedRoleModal.title)}</strong>
                <span style="font-size: 12.5px; color: var(--emp-text-secondary);">${esc(appliedRoleModal.team)} · ${esc(appliedRoleModal.department)}</span>
                <div style="display: flex; gap: 8px; margin-top: 10px;">
                  <span class="emp-badge emp-badge--neutral">Manager: ${esc(appliedRoleModal.hiringManager)}</span>
                  <span class="emp-badge emp-badge--success">${appliedRoleModal.matchScore}% Profile Match</span>
                </div>
              </div>

              <p style="font-size: 13px; color: var(--emp-text-secondary); line-height: 1.5; margin: 0;">
                Expressing interest directly notifies the hiring manager and connects your verified credentials and DLI learning progress. Your current manager will only be notified if an interview loop is scheduled.
              </p>

              <div>
                <label style="display: block; font-size: 11.5px; font-weight: 750; color: var(--emp-text-primary); text-transform: uppercase; margin-bottom: 6px;">Note to Hiring Manager (Optional)</label>
                <textarea rows="3" placeholder="Highlight relevant cluster optimization projects, DLI labs completed, or interest in the team..." style="width: 100%; border-radius: 10px; border: 1px solid var(--emp-border); padding: 10px; font-size: 13px; font-family: inherit; resize: vertical;"></textarea>
              </div>

              <div style="display: flex; justify-content: flex-end; gap: 10px; padding-top: 10px; border-top: 1px solid var(--emp-border);">
                <button type="button" class="emp-btn-secondary" id="btnrancelRoleModal">rancel</button>
                <button type="button" class="emp-btn-primary" id="btnronfirmRoleInterest">
                  <i data-lucide="check"></i>
                  <span>Submit Interest</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

export function bindEmployeerareerEvents(rerenderFn) {
  const container = document.querySelector('.employee-career');
  if (!container) return;

  container.querySelectorAll('[data-express-interest]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const roleId = btn.dataset.expressInterest;
      appliedRoleModal = internalRolesData.find(r => r.id === roleId) || internalRolesData[0];
      rerenderFn();
    });
  });

  const closeBtn = container.querySelector('#btnrloseRoleModal');
  const cancelBtn = container.querySelector('#btnrancelRoleModal');
  const scrim = container.querySelector('#empRoleModalScrim');

  [closeBtn, cancelBtn, scrim].forEach(el => {
    el?.addEventListener('click', (e) => {
      if (e.target === scrim || el === closeBtn || el === cancelBtn) {
        appliedRoleModal = null;
        rerenderFn();
      }
    });
  });

  const confirmBtn = container.querySelector('#btnronfirmRoleInterest');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      alert(`Interest submitted for ${appliedRoleModal.title}! The hiring team has received your profile.`);
      appliedRoleModal = null;
      rerenderFn();
    });
  }

  const resumeBtn = container.querySelector('#btnResumeLearning');
  if (resumeBtn) {
    resumeBtn.addEventListener('click', () => {
      alert('Launching NeIDIA DLI Interactive GPU eirtual Lab (Blackwell Node rluster)...');
    });
  }
}
