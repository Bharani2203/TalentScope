// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE PROFILE
// Verified credentials, role progression, mentor reputation, and portfolio
// Interactive profile management with complete Save & Sync functionality (#2735F5)
// ============================================================================

import {
  getEmployeeProfile,
  updateEmployeeProfile,
  isCompanyEmployee,
  employeeSkillsData,
  employeeLearningTrack
} from '../../../data/employee/employee-data.js';
import { updatePlatformUser } from '../../../data/platform-state.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeProfile() {
  const p = getEmployeeProfile();
  const isCompany = isCompanyEmployee();
  const skills = employeeSkillsData;
  const learn = employeeLearningTrack;

  return `
    <div class="employee-page">
      <!-- Profile Header Hero -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <div style="display: flex; align-items: center; gap: 20px; flex-wrap: wrap;">
            <div style="width: 72px; height: 72px; border-radius: 20px; background: var(--emp-primary); color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 850; box-shadow: 0 8px 24px rgba(39, 53, 245, 0.25);">
              ${esc(p.initials)}
            </div>
            <div>
              <span class="emp-eyebrow">
                <i data-lucide="${isCompany ? 'shield-check' : 'user-check'}"></i>
                ${isCompany ? 'VERIFIED INTERNAL EMPLOYEE' : 'INDEPENDENT PROFESSIONAL'}
              </span>
              <h1 class="emp-hero-title">${esc(p.name)}</h1>
              <p class="emp-hero-desc">
                ${isCompany 
                  ? `${esc(p.role)} · ${esc(p.department)} · <strong>${esc(p.company)}</strong>`
                  : `${esc(p.role)} · Distributed Systems & AI Infrastructure Track`}
              </p>
              <div style="display: flex; align-items: center; gap: 10px; margin-top: 6px; font-size: 12px; color: var(--emp-text-muted); flex-wrap: wrap;">
                <span>ID: <strong>${esc(p.id)}</strong></span>
                <span>·</span>
                <span>${esc(p.location || p.hub)}</span>
                <span>·</span>
                <span class="emp-badge emp-badge-success">${esc(p.status)}</span>
                <span>·</span>
                <span class="emp-badge emp-badge-primary">${p.reputationPoints.toLocaleString()} Rep Points</span>
              </div>
            </div>
          </div>
        </div>
        <div class="emp-hero-actions" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
          <button type="button" class="emp-btn-secondary" id="btnExportProfile">
            <i data-lucide="download"></i>
            <span>Export Profile Preview</span>
          </button>
          <button type="button" class="emp-btn-primary" id="btnEditEmployeeProfile">
            <i data-lucide="edit-3"></i>
            <span>Edit Profile</span>
          </button>
        </div>
      </section>

      <!-- 2-Column Profile Layout -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: start;">
        
        <!-- LEFT COLUMN: Employment Context & Achievements -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <!-- Context Information -->
          <div class="emp-card">
            <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 16px;">
              ${isCompany ? 'Employment & Pod Context' : 'Professional Profile Context'}
            </h3>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; font-size: 13px;">
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">
                  ${isCompany ? 'Reporting Manager' : 'Career Focus'}
                </span>
                <strong style="display: block; color: var(--emp-text-primary); margin-top: 2px;">
                  ${isCompany ? esc(p.manager) : 'Distributed Model Serving'}
                </strong>
              </div>
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Technical Advisor</span>
                <strong style="display: block; color: var(--emp-primary); margin-top: 2px;">${esc(p.mentor)}</strong>
              </div>
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Campus / Location</span>
                <strong style="display: block; color: var(--emp-text-primary); margin-top: 2px;">${esc(p.hub || p.location)}</strong>
              </div>
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Experience</span>
                <strong style="display: block; color: var(--emp-text-primary); margin-top: 2px;">${esc(p.experience)}</strong>
              </div>
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Target Designation</span>
                <strong style="display: block; color: var(--emp-primary); margin-top: 2px;">${esc(p.targetRole)}</strong>
              </div>
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Latest Evaluation</span>
                <strong style="display: block; color: var(--emp-success); margin-top: 2px;">${esc(p.lastAppraisal)}</strong>
              </div>
            </div>

            ${p.careerGoal ? `
              <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--emp-border-subtle);">
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Strategic Career Focus</span>
                <p style="font-size: 13px; color: var(--emp-text-secondary); margin: 4px 0 0; line-height: 1.5;">${esc(p.careerGoal)}</p>
              </div>
            ` : ''}
          </div>

          <!-- Verified Key Achievements -->
          <div class="emp-card">
            <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 14px;">
              Technical Achievements & Recognition
            </h3>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <div style="display: flex; align-items: flex-start; gap: 12px; padding: 14px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
                <i data-lucide="trophy" style="color: var(--emp-attention); width: 20px; height: 20px; margin-top: 2px; flex-shrink: 0;"></i>
                <div>
                  <strong style="font-size: 13.5px; color: var(--emp-text-primary); display: block;">
                    APAC Engineering Spotlight Award (2026)
                  </strong>
                  <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 2px 0 0; line-height: 1.45;">
                    Recognized for 3.2x latency improvement on enterprise customer multi-modal inference pipeline using TensorRT.
                  </p>
                </div>
              </div>

              <div style="display: flex; align-items: flex-start; gap: 12px; padding: 14px; background: var(--emp-soft); border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
                <i data-lucide="award" style="color: var(--emp-primary); width: 20px; height: 20px; margin-top: 2px; flex-shrink: 0;"></i>
                <div>
                  <strong style="font-size: 13.5px; color: var(--emp-text-primary); display: block;">
                    Master Question Author Badge
                  </strong>
                  <p style="font-size: 12.5px; color: var(--emp-text-secondary); margin: 2px 0 0; line-height: 1.45;">
                    Authored 16 verified assessment questions with 128 successful candidate evaluations.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT COLUMN: Verified Skills & Learning Credentials -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <!-- Verified Skills Snapshot -->
          <div class="emp-card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
              <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0;">
                Illustrative Skill Portfolio
              </h3>
              <a href="#/employee/skills" class="emp-btn-ghost emp-btn-sm">Inspect Skills</a>
            </div>

            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${skills.map(sk => `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 10px;">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="${esc(sk.icon)}" style="color: var(--emp-primary); width: 16px; height: 16px;"></i>
                    <strong style="font-size: 13px; color: var(--emp-text-primary);">${esc(sk.name)}</strong>
                  </div>
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 11.5px; color: var(--emp-text-muted);">${esc(sk.proficiency)}</span>
                    <span class="emp-badge ${sk.status === 'Strong' ? 'emp-badge-success' : 'emp-badge-warning'}">
                      ${sk.status === 'Strong' ? 'Verified' : 'Target Gap'}
                    </span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- DLI Certifications & Active Progress -->
          <div class="emp-card">
            <h3 style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin: 0 0 14px;">
              Credentials & Active Labs
            </h3>

            <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px;">
              ${learn.earnedCredentials.map(c => `
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; background: #FFFFFF; border-radius: 10px; border: 1px solid var(--emp-border);">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <i data-lucide="shield-check" style="color: var(--emp-success); width: 16px; height: 16px;"></i>
                    <span style="font-size: 12.5px; font-weight: 700; color: var(--emp-text-primary);">${esc(c.title)}</span>
                  </div>
                  <span style="font-size: 11.5px; color: var(--emp-text-muted);">${esc(c.date)}</span>
                </div>
              `).join('')}
            </div>

            <!-- Active learning track -->
            <div style="background: var(--emp-soft); padding: 12px 14px; border-radius: 12px; border: 1px solid var(--emp-border-subtle);">
              <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 750; margin-bottom: 6px;">
                <span style="color: var(--emp-text-primary);">In Progress: ${esc(learn.activeTrack)}</span>
                <span style="color: var(--emp-primary);">${learn.progressPercent}%</span>
              </div>
              <div class="emp-progress-bar">
                <div class="emp-progress-fill" style="width: ${learn.progressPercent}%;"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function openEmployeeEditModal(rerender) {
  const p = getEmployeeProfile();
  const isCompany = isCompanyEmployee();

  const modalContainer = document.createElement('div');
  modalContainer.className = 'emp-modal-overlay portal-modal-scrim';
  modalContainer.id = 'editEmployeeProfileModal';

  modalContainer.innerHTML = `
    <div class="emp-modal-dialog portal-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="editEmpModalTitle" style="max-width: 620px;">
      <div class="portal-modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid var(--emp-border);">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div style="width: 36px; height: 36px; border-radius: 10px; background: var(--emp-light); color: var(--emp-primary); display: flex; align-items: center; justify-content: center;">
            <i data-lucide="user-cog" style="width: 18px; height: 18px;"></i>
          </div>
          <div>
            <h3 id="editEmpModalTitle" style="margin: 0; font-size: 16px; font-weight: 800; color: var(--emp-text-primary);">Edit Employee Profile</h3>
            <span style="font-size: 12px; color: var(--emp-text-muted);">${isCompany ? 'Illustrative Internal Record' : 'Independent Professional Record'}</span>
          </div>
        </div>
        <button type="button" class="portal-modal-close-btn" id="empModalCloseBtn" style="background: none; border: none; cursor: pointer; color: var(--emp-text-muted); padding: 6px; border-radius: 6px;">
          <i data-lucide="x" style="width: 18px; height: 18px;"></i>
        </button>
      </div>

      <div class="portal-modal-body" style="padding: 24px; max-height: 70vh; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Full Name</label>
            <input type="text" id="inputEmpName" value="${esc(p.name)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Current Role</label>
            <input type="text" id="inputEmpRole" value="${esc(p.role)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Department / Track</label>
            <input type="text" id="inputEmpDept" value="${esc(p.department)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Target Designation</label>
            <input type="text" id="inputEmpTargetRole" value="${esc(p.targetRole)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Campus / Hub Location</label>
            <input type="text" id="inputEmpLocation" value="${esc(p.hub || p.location)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Total Experience</label>
            <input type="text" id="inputEmpExperience" value="${esc(p.experience)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Technical Advisor / Mentor</label>
            <input type="text" id="inputEmpMentor" value="${esc(p.mentor)}" class="emp-input" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); box-sizing: border-box;" />
          </div>
          <div>
            <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Mentorship Status</label>
            <select id="inputEmpMentorStatus" style="width: 100%; height: 38px; border-radius: 8px; border: 1px solid var(--emp-border); padding: 0 12px; font-size: 13.5px; color: var(--emp-text-primary); background: #FFFFFF; box-sizing: border-box;">
              <option value="Active Technical Mentor" ${p.mentorStatus === 'Active Technical Mentor' ? 'selected' : ''}>Active Technical Mentor</option>
              <option value="Available for Advisory" ${p.mentorStatus === 'Available for Advisory' ? 'selected' : ''}>Available for Advisory</option>
              <option value="Focusing on Learning Track" ${p.mentorStatus === 'Focusing on Learning Track' ? 'selected' : ''}>Focusing on Learning Track</option>
            </select>
          </div>
        </div>

        <div>
          <label style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; display: block; margin-bottom: 6px;">Strategic Career Focus / Bio</label>
          <textarea id="inputEmpGoal" rows="3" style="width: 100%; border-radius: 8px; border: 1px solid var(--emp-border); padding: 10px 12px; font-size: 13.5px; color: var(--emp-text-primary); font-family: inherit; line-height: 1.45; box-sizing: border-box;">${esc(p.careerGoal || '')}</textarea>
        </div>
      </div>

      <div class="portal-modal-footer" style="padding: 16px 24px; border-top: 1px solid var(--emp-border); display: flex; justify-content: flex-end; gap: 10px; background: var(--emp-soft);">
        <button type="button" class="emp-btn-secondary" id="empModalCancelBtn" style="height: 38px;">Cancel</button>
        <button type="button" class="emp-btn-primary" id="empModalSaveBtn" style="height: 38px;">Save Changes</button>
      </div>
    </div>
  `;

  document.body.appendChild(modalContainer);
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  const close = () => {
    window.removeEventListener('keydown', handleKeyDown);
    modalContainer.remove();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') close();
  };
  window.addEventListener('keydown', handleKeyDown);

  modalContainer.addEventListener('click', (e) => {
    if (e.target === modalContainer) close();
  });

  document.getElementById('empModalCloseBtn')?.addEventListener('click', close);
  document.getElementById('empModalCancelBtn')?.addEventListener('click', close);

  document.getElementById('empModalSaveBtn')?.addEventListener('click', () => {
    const newName = document.getElementById('inputEmpName')?.value?.trim();
    const newRole = document.getElementById('inputEmpRole')?.value?.trim();
    const newDept = document.getElementById('inputEmpDept')?.value?.trim();
    const newTargetRole = document.getElementById('inputEmpTargetRole')?.value?.trim();
    const newLoc = document.getElementById('inputEmpLocation')?.value?.trim();
    const newExp = document.getElementById('inputEmpExperience')?.value?.trim();
    const newMentor = document.getElementById('inputEmpMentor')?.value?.trim();
    const newMentorStatus = document.getElementById('inputEmpMentorStatus')?.value;
    const newGoal = document.getElementById('inputEmpGoal')?.value?.trim();

    const updates = {};
    if (newName) {
      updates.name = newName;
      updates.shortName = newName.split(' ')[0] || newName;
      updates.initials = newName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    }
    if (newRole) updates.role = newRole;
    if (newDept) updates.department = newDept;
    if (newTargetRole) updates.targetRole = newTargetRole;
    if (newLoc) {
      updates.location = newLoc;
      updates.hub = newLoc;
    }
    if (newExp) updates.experience = newExp;
    if (newMentor) updates.mentor = newMentor;
    if (newMentorStatus) updates.mentorStatus = newMentorStatus;
    if (newGoal !== undefined) updates.careerGoal = newGoal;

    updateEmployeeProfile(updates);
    if (updates.name || updates.role) {
      updatePlatformUser({
        name: updates.name || p.name,
        role: updates.role || p.role
      });
    }

    close();
    if (typeof rerender === 'function') {
      rerender();
    }
    showToast('Employee profile updated successfully!');
  });
}

function showToast(message) {
  const existing = document.querySelector('.emp-toast-banner');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'emp-toast-banner';
  toast.style.cssText = `
    position: fixed;
    bottom: 28px;
    right: 28px;
    background: #1823A8;
    color: #FFFFFF;
    padding: 12px 20px;
    border-radius: 12px;
    font-size: 13.5px;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    border-left: 4px solid #2735F5;
    z-index: 999999;
    animation: empSlideUp 240ms cubic-bezier(0.16, 1, 0.3, 1);
  `;
  toast.innerHTML = `<i data-lucide="check-circle" style="color: #61C2FF; width: 18px; height: 18px;"></i> <span>${message}</span>`;
  document.body.appendChild(toast);
  if (window.lucide) window.lucide.createIcons();

  setTimeout(() => {
    toast.remove();
  }, 3200);
}

export function bindEmployeeProfileEvents(rerender) {
  const exportBtn = document.querySelector('#btnExportProfile');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      alert('Generating verified PDF credentials dossier for ' + getEmployeeProfile().name + '...');
    });
  }

  const editBtn = document.querySelector('#btnEditEmployeeProfile');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      openEmployeeEditModal(rerender);
    });
  }
}
