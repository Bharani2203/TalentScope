// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE MY COMPANY
// Company overview, market signals, technology shifts, workforce trends, & feedback
// ============================================================================

import {
  employeeProfile,
  companySignals,
  companyWorkforceData
} from '../../../data/employee/employee-data.js';

let feedbackSubmitted = false;

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderEmployeeMyCompany() {
  const p = employeeProfile;
  const cw = companyWorkforceData;

  const techShifts = [
    {
      tech: 'Blackwell GPU Architecture & NVLink 5',
      status: 'Rapid Internal Scaling',
      trend: '+48%',
      impactOnRole: 'High Impact',
      summary: 'Migrating hyperscale enterprise customer clusters to 72-GPU Blackwell NVL72 racks.',
      relevantSkills: ['CUDA Kernels', 'NCCL', 'Memory Optimization', 'C++']
    },
    {
      tech: 'FP4 Quantization & TensorRT-LLM 0.12',
      status: 'Production Standard',
      trend: '+36%',
      impactOnRole: 'Direct Requirement',
      summary: 'Replacing standard FP16 inference kernels with ultra-dense FP4 matrix multiplications.',
      relevantSkills: ['TensorRT', 'Model Quantization', 'PyTorch Compilation']
    },
    {
      tech: 'Sovereign AI & Air-Gapped Microservices',
      status: 'Strategic Growth Area',
      trend: '+41%',
      impactOnRole: 'Moderate Impact',
      summary: 'Deploying NeMo microservices on isolated regional cloud networks for government clients.',
      relevantSkills: ['Docker / K8s', 'Triton Server', 'Enterprise Security']
    },
    {
      tech: 'Legacy FP32 Unoptimized Training',
      status: 'Phasing Out',
      trend: '-28%',
      impactOnRole: 'Low Impact (Deprecating)',
      summary: 'Deprecating unquantized large model checkpoints across all staging compute clusters.',
      relevantSkills: ['Automatic Mixed Precision (AMP)']
    }
  ];

  return `
    <div class="employee-page employee-company">
      <!-- 1. COMPANY HERO -->
      <section class="emp-hero">
        <div class="emp-hero__content">
          <div style="display: flex; align-items: center; gap: 20px;">
            <div class="emp-hero__company-logo" style="width: 56px; height: 56px; font-size: 22px;">
              ${esc(p.companyInitials)}
            </div>
            <div>
              <span class="emp-eyebrow"><i data-lucide="building-2"></i> INTERNAL WORKFORCE CONTEXT</span>
              <h1 style="font-size: 26px; font-weight: 850; color: var(--emp-text-primary); margin: 0 0 4px;">
                ${esc(cw.companyName)}
              </h1>
              <p style="font-size: 14px; color: var(--emp-text-secondary); margin: 0;">
                ${esc(cw.industry)} · ${esc(cw.ticker)} · ${esc(cw.primaryIndiaCampus)}
              </p>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 12px; background: rgba(255, 255, 255, 0.9); padding: 12px 18px; border-radius: 12px; border: 1px solid var(--emp-border-glass);">
            <div style="text-align: right;">
              <strong style="display: block; font-size: 13.5px; color: var(--emp-text-primary);">${esc(p.name)}</strong>
              <small style="color: var(--emp-text-secondary); font-size: 11.5px;">${esc(p.role)} · ${esc(p.level)}</small>
            </div>
            <span class="emp-badge emp-badge--success">Illustrative Employment Example</span>
          </div>
        </div>
      </section>

      <!-- 2. COMPANY OVERVIEW & DIRECTION -->
      <section class="emp-card emp-card--accent-blue">
        <div style="margin-bottom: 16px;">
          <span class="emp-eyebrow"><i data-lucide="compass"></i> STRATEGIC DIRECTION</span>
          <h2 class="emp-title">Executive Brief & Technical Focus</h2>
          <p class="emp-subtitle">Internal priorities and operational trajectory communicated by NVIDIA engineering leadership.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
          <div style="background: var(--emp-very-light); border-radius: 12px; padding: 18px; border: 1px solid var(--emp-border);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <i data-lucide="cpu" style="color: var(--emp-deep-primary); width: 18px; height: 18px;"></i>
              <strong style="font-size: 14px; color: var(--emp-text-primary);">Next-Gen Silicon Scaling</strong>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); line-height: 1.45; margin: 0;">
              Accelerating Blackwell architecture production yield and expanding multi-node NVLink interconnects for million-GPU clusters.
            </p>
          </div>

          <div style="background: var(--emp-very-light); border-radius: 12px; padding: 18px; border: 1px solid var(--emp-border);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <i data-lucide="layers" style="color: var(--emp-deep-primary); width: 18px; height: 18px;"></i>
              <strong style="font-size: 14px; color: var(--emp-text-primary);">Enterprise AI Software Stack</strong>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); line-height: 1.45; margin: 0;">
              Standardizing NeMo microservices, TensorRT-LLM, and Triton Inference Server across Fortune 500 on-prem deployments.
            </p>
          </div>

          <div style="background: var(--emp-very-light); border-radius: 12px; padding: 18px; border: 1px solid var(--emp-border);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <i data-lucide="globe" style="color: var(--emp-deep-primary); width: 18px; height: 18px;"></i>
              <strong style="font-size: 14px; color: var(--emp-text-primary);">Regional Ecosystem Expansion</strong>
            </div>
            <p style="font-size: 12.5px; color: var(--emp-text-secondary); line-height: 1.45; margin: 0;">
              Expanding the Bangalore and Pune engineering centers with dedicated sovereign AI and robotics software development pods.
            </p>
          </div>
        </div>
      </section>

      <!-- 3. INTERNAL MARKET & COMPANY SIGNALS -->
      <section class="emp-card">
        <div style="margin-bottom: 18px;">
          <span class="emp-eyebrow"><i data-lucide="activity"></i> ORGANIZATIONAL SIGNALS</span>
          <h2 class="emp-title">Internal Signals & Operational Movement</h2>
          <p class="emp-subtitle">Illustrative company developments; connected organization data is unavailable.</p>
        </div>

        <div class="emp-signals-grid">
          ${companySignals.map(sig => `
            <div class="emp-signal-item">
              <div class="emp-signal-item__top">
                <div>
                  <span class="emp-signal-item__cat">${esc(sig.category)} · ${esc(sig.timeframe)}</span>
                  <h3 class="emp-signal-item__title">${esc(sig.title)}</h3>
                </div>
                <span class="emp-badge emp-badge--success">${esc(sig.change)}</span>
              </div>
              <div class="emp-signal-item__why">
                <strong>Why it matters:</strong> ${esc(sig.whyItMatters)}
              </div>
              <div class="emp-signal-item__meta-tags">
                <span style="font-size: 11px; font-weight: 700; color: var(--emp-text-muted);">Impacted Skills:</span>
                ${sig.affectedSkills.map(sk => `<span class="emp-signal-tag emp-signal-tag--skill">${esc(sk)}</span>`).join('')}
              </div>
              <div style="font-size: 11.5px; color: var(--emp-text-muted); padding-top: 8px; border-top: 1px dashed var(--emp-border);">
                Example source: <strong>${esc(sig.evidence)}</strong>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 4. TECHNOLOGY SHIFTS CONNECTED TO YOUR SKILLS -->
      <section class="emp-card emp-card--glass">
        <div style="margin-bottom: 20px;">
          <span class="emp-eyebrow"><i data-lucide="cpu"></i> TECH STACK EVOLUTION</span>
          <h2 class="emp-title">Company Technology Shifts & Skill Impact</h2>
          <p class="emp-subtitle">How shifts in NVIDIA's architectural stack translate into personal skill requirements for your role.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
          ${techShifts.map(ts => `
            <div style="background: var(--emp-surface); border: 1px solid var(--emp-border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; gap: 14px;">
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <span class="emp-badge ${ts.trend.startsWith('+') ? 'emp-badge--success' : 'emp-badge--attention'}">${esc(ts.trend)} Adoption</span>
                  <span style="font-size: 11.5px; font-weight: 700; color: var(--emp-deep-primary);">${esc(ts.impactOnRole)}</span>
                </div>
                <h3 style="font-size: 15.5px; font-weight: 750; color: var(--emp-text-primary); margin: 0 0 6px;">${esc(ts.tech)}</h3>
                <p style="font-size: 12.5px; color: var(--emp-text-secondary); line-height: 1.45; margin: 0;">${esc(ts.summary)}</p>
              </div>

              <div>
                <div style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; margin-bottom: 6px;">Connected Skills to Master:</div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                  ${ts.relevantSkills.map(sk => `<span class="emp-signal-tag emp-signal-tag--skill">${esc(sk)}</span>`).join('')}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 5. WORKFORCE & HIRING TRENDS -->
      <section class="emp-card">
        <div style="margin-bottom: 20px;">
          <span class="emp-eyebrow"><i data-lucide="users"></i> HEADCOUNT & MOBILITY</span>
          <h2 class="emp-title">Workforce Growth & Skill Demand</h2>
          <p class="emp-subtitle">Where new teams and headcount are expanding within NVIDIA India and APAC engineering hubs.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
          ${cw.topHiringDisciplines.map(disc => `
            <div style="background: var(--emp-very-light); border: 1px solid var(--emp-border); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; justify-content: space-between; gap: 8px;">
              <div>
                <span style="font-size: 11px; font-weight: 750; color: var(--emp-deep-primary); text-transform: uppercase;">Growth Area</span>
                <h3 style="font-size: 14px; font-weight: 800; color: var(--emp-text-primary); margin: 4px 0;">${esc(disc.discipline)}</h3>
              </div>
              <div style="display: flex; align-items: baseline; justify-content: space-between; padding-top: 8px; border-top: 1px solid var(--emp-border);">
                <strong style="font-size: 20px; font-weight: 850; color: var(--emp-dark-blue);">${esc(disc.share)}</strong>
                <small style="font-size: 11.5px; font-weight: 700; color: var(--emp-text-secondary);">${esc(disc.count)}</small>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 6. STRUCTURED EMPLOYEE FEEDBACK AREA -->
      <section class="emp-card" style="background: linear-gradient(180deg, var(--emp-very-light), var(--emp-surface));">
        <div style="margin-bottom: 18px;">
          <span class="emp-eyebrow"><i data-lucide="message-square-plus"></i> WORKFORCE PULSE</span>
          <h2 class="emp-title">Internal Workforce Feedback</h2>
          <p class="emp-subtitle">Share structured insights on engineering tooling, learning resources, or role trajectory with your leadership council.</p>
        </div>

        ${feedbackSubmitted ? `
          <div style="padding: 24px; background: #E8F8F1; border: 1px solid #19B77A; border-radius: 12px; text-align: center; animation: empFadeIn 0.2s ease-out both;">
            <i data-lucide="check-circle" style="color: #0E784F; width: 32px; height: 32px; margin-bottom: 8px;"></i>
            <h4 style="font-size: 16px; font-weight: 800; color: #0E784F; margin: 0 0 4px;">Feedback Submitted to Engineering Council</h4>
            <p style="font-size: 13px; color: #0E784F; margin: 0;">Thank you, Arun. Your perspective helps shape upcoming DLI curriculum and compute cluster resource allocation.</p>
          </div>
        ` : `
          <form id="empFeedbackForm" style="display: flex; flex-direction: column; gap: 16px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
              <div>
                <label style="display: block; font-size: 11.5px; font-weight: 750; color: var(--emp-text-primary); text-transform: uppercase; margin-bottom: 6px;">Feedback Category</label>
                <select id="empFeedbackCategory" style="width: 100%; height: 42px; border-radius: 10px; border: 1px solid var(--emp-border); padding: 0 12px; background: #FFFFFF; font-size: 13px; color: var(--emp-text-primary);">
                  <option value="Role Evolution & Tech Tooling">Role Evolution & Tech Tooling</option>
                  <option value="DLI Learning & Certification Quality">DLI Learning & Certification Quality</option>
                  <option value="Internal Mobility & Project Alignment">Internal Mobility & Project Alignment</option>
                  <option value="Compute Resource Allocation (Cluster Access)">Compute Resource Allocation (Cluster Access)</option>
                </select>
              </div>

              <div>
                <label style="display: block; font-size: 11.5px; font-weight: 750; color: var(--emp-text-primary); text-transform: uppercase; margin-bottom: 6px;">Impact Scope</label>
                <select id="empFeedbackScope" style="width: 100%; height: 42px; border-radius: 10px; border: 1px solid var(--emp-border); padding: 0 12px; background: #FFFFFF; font-size: 13px; color: var(--emp-text-primary);">
                  <option value="Team / Pod Level">Team / Pod Level (Autonomous Systems)</option>
                  <option value="India Engineering Hub Level">India Engineering Hub Level (Bangalore)</option>
                  <option value="Global Organization Level">Global Organization Level</option>
                </select>
              </div>
            </div>

            <div>
              <label style="display: block; font-size: 11.5px; font-weight: 750; color: var(--emp-text-primary); text-transform: uppercase; margin-bottom: 6px;">Structured Observation / Suggestion</label>
              <textarea id="empFeedbackNotes" rows="3" placeholder="e.g. Profiling tools on Blackwell B200 nodes require updated CUDA 13 DLI lab environments for faster team onboarding..." style="width: 100%; border-radius: 10px; border: 1px solid var(--emp-border); padding: 12px; font-size: 13px; color: var(--emp-text-primary); font-family: inherit; resize: vertical;"></textarea>
            </div>

            <div style="display: flex; align-items: center; justify-content: flex-end; gap: 12px;">
              <button type="submit" class="emp-btn-primary">
                <i data-lucide="send"></i>
                <span>Submit to Engineering Council</span>
              </button>
            </div>
          </form>
        `}
      </section>
    </div>
  `;
}

export function bindEmployeeCompanyEvents(rerenderFn) {
  const form = document.querySelector('#empFeedbackForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      feedbackSubmitted = true;
      rerenderFn();
    });
  }
}
