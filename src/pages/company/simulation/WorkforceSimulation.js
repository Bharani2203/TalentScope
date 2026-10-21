// ============================================================================
// TALENTSCOPE.AI — COMPANY WORKFORCE SIMULATION
// What happens if the market changes? Strategic Scenario Modeling & Sensitivity Sandbox (#874FFF)
// ============================================================================

import { companyProfile, simulationScenarios } from '../../../data/company/company-data.js';
import { openCompanyModal } from '../components/CompanyModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let activeScenarioId = 'scen-ai-30';

// Parametric sandbox state
let simState = {
  demandSurge: 25,
  automationRate: 35,
  upskillInvestment: 250 // $k
};

export function renderCompanyWorkforceSimulation() {
  const p = companyProfile;
  const activeScen = simulationScenarios.find(s => s.id === activeScenarioId) || simulationScenarios[0];

  // Dynamic calculations for sensitivity sandbox
  const netDeficit = Math.max(0, Math.round(110 * (1 + simState.demandSurge / 100) - (simState.upskillInvestment / 4.8)));
  const searchFeesAvoided = Math.round(simState.upskillInvestment * 3.2);
  const netROI = Math.round(searchFeesAvoided - simState.upskillInvestment);

  return `
    <div class="company-page company-simulation">
      <aside role="note" class="cmp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">
        Prototype only. Scenario cards, workforce figures, strategies, and local calculations are illustrative examples—not HRIS data, forecasts, or outputs from a validated simulation model. No workforce simulation service is connected.
      </aside>
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="cpu" class="cmp-icon-inline"></i>
              STRATEGIC SCENARIO WORKSPACE
            </span>
            <h1>What Happens if the Market Changes?</h1>
            <p>Explore illustrative technology, regulatory, and automation scenarios. This prototype does not provide decision-grade workforce analysis.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logoInitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Illustrative prototype · no validated model</span>
              <div class="cmp-hero__context-meta">
                <span><i data-lucide="info"></i> Not connected to HRIS</span>
                <span>·</span>
                <span><i data-lucide="info"></i> No validated confidence score</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. SCENARIO SELECTOR (Section 17) -->
      <section class="cmp-section">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
          <div>
            <span class="cmp-eyebrow"><i data-lucide="sliders" class="cmp-icon-inline"></i> ILLUSTRATIVE EXAMPLE SCENARIOS</span>
            <h2 class="cmp-title">Select Strategic Scenario</h2>
            <p class="cmp-subtitle">Choose an illustrative market condition. Displayed impacts and strategy examples are not validated estimates or recommendations.</p>
          </div>
          <button type="button" class="cmp-btn-primary" id="cmpCreateScenarioBtn" style="height: 36px; padding: 0 16px;">
            <i data-lucide="plus"></i>
            <span>New Custom Scenario</span>
          </button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">
          ${simulationScenarios.map(scen => `
            <div class="cmp-card cmp-scen-selector ${scen.id === activeScenarioId ? 'is-selected' : ''}" data-scen-id="${scen.id}" style="
              cursor: pointer; transition: all 180ms ease;
              border: 2px solid ${scen.id === activeScenarioId ? 'var(--cmp-primary)' : 'var(--cmp-border)'};
              background: ${scen.id === activeScenarioId ? 'var(--cmp-light-primary)' : 'var(--cmp-surface)'};
            ">
              <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
                <span class="cmp-badge ${scen.id === activeScenarioId ? 'cmp-badge--accent' : 'cmp-badge--neutral'}">${esc(scen.badge)}</span>
                <span style="font-size: 11.5px; font-weight: 700; color: var(--cmp-deep-primary);">
                  ${scen.id === activeScenarioId ? 'Active Selection ✓' : 'Select Scenario'}
                </span>
              </div>
              <h3 style="font-size: 16px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 6px;">${esc(scen.title)}</h3>
              <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0; line-height: 1.45;">${esc(scen.trigger)}</p>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 3. SCENARIO NARRATIVE & DECISION FLOW (Section 17: CURRENT → DEMAND → GAP → OPTIONS) -->
      <section class="cmp-section">
        <div class="cmp-card" style="border-top: 4px solid var(--cmp-primary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; flex-wrap: wrap; gap: 10px;">
            <div>
              <span class="cmp-badge cmp-badge--accent" style="margin-bottom: 4px;">ILLUSTRATIVE SCENARIO: ${esc(activeScen.title)}</span>
              <h2 class="cmp-title" style="margin-top: 2px;">Workforce Impact & Options Flow</h2>
              <p class="cmp-subtitle">${esc(activeScen.trigger)}</p>
            </div>
            <button type="button" class="cmp-btn-secondary" id="cmpExportScenarioBrief">
              <i data-lucide="file-text"></i>
              <span>Export unavailable (not implemented)</span>
            </button>
          </div>

          <p role="note" class="cmp-subtitle">The figures and strategy below are illustrative demo content only; they are not calculated from company workforce data.</p>

          <!-- Scenario Comparison Cards Strip -->
          <div class="cmp-overview-grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-bottom: 20px;">
            ${activeScen.impacts.map(imp => `
              <div style="background: var(--cmp-very-light); padding: 16px; border-radius: var(--cmp-radius-md); border: 1px solid var(--cmp-border);">
                <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase;">${esc(imp.metric)}</span>
                <div style="display: flex; align-items: baseline; gap: 8px; margin: 6px 0 2px;">
                  <span style="font-size: 20px; font-weight: 850; color: var(--cmp-text-primary);">${esc(imp.projected)}</span>
                  <span class="cmp-badge cmp-badge--accent" style="font-size: 11px;">${esc(imp.delta)}</span>
                </div>
                <small style="color: var(--cmp-text-secondary); font-size: 11.5px;">Current: <strong>${esc(imp.current)}</strong></small>
              </div>
            `).join('')}
          </div>

          <!-- Recommended Workforce Options (Upskill / Redeploy / Hire) -->
          <div style="background: var(--cmp-surface); border: 1px solid var(--cmp-border); border-radius: var(--cmp-radius-md); padding: 18px;">
            <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px;">
              <div style="width: 38px; height: 38px; border-radius: 10px; background: var(--cmp-light-primary); color: var(--cmp-deep-primary); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                <i data-lucide="check-square" style="width: 18px; height: 18px;"></i>
              </div>
              <div>
                <strong style="font-size: 14.5px; color: var(--cmp-text-primary); display: block; margin-bottom: 2px;">Illustrative Strategy Example</strong>
                <p style="font-size: 13px; color: var(--cmp-text-secondary); margin: 0; line-height: 1.45;">${esc(activeScen.recommendedStrategy)}</p>
              </div>
            </div>

            <div style="display: flex; gap: 10px; flex-wrap: wrap; padding-top: 14px; border-top: 1px solid var(--cmp-border-subtle);">
              <a href="#/company/mobility" class="cmp-btn-primary" style="height: 36px; padding: 0 16px;">
                <i data-lucide="git-pull-request"></i>
                <span>Open Internal Mobility Bench</span>
              </a>
              <a href="#/company/skills" class="cmp-btn-secondary" style="height: 36px; padding: 0 14px;">
                <i data-lucide="layers"></i>
                <span>View Skill Academies</span>
              </a>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. WHAT-IF SENSITIVITY SANDBOX -->
      <section class="cmp-section">
        <div class="cmp-card">
          <div style="margin-bottom: 16px;">
            <span class="cmp-eyebrow"><i data-lucide="sliders-horizontal" class="cmp-icon-inline"></i> ILLUSTRATIVE LOCAL ARITHMETIC · NOT A MODEL</span>
            <h2 class="cmp-title">Prototype Sensitivity Sandbox</h2>
            <p class="cmp-subtitle">Adjust inputs to see illustrative arithmetic only. The sample deficit and ROI figures are not connected to company workforce data and are not validated estimates.</p>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; align-items: stretch;">
            <!-- Sliders -->
            <div style="display: flex; flex-direction: column; gap: 16px; justify-content: space-around;">
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <strong style="color: var(--cmp-text-primary);">Market Demand Surge</strong>
                  <span style="font-weight: 800; color: var(--cmp-primary);">+${simState.demandSurge}%</span>
                </div>
                <input type="range" min="10" max="60" step="5" value="${simState.demandSurge}" id="simDemandSurge" style="width: 100%; accent-color: var(--cmp-primary);" />
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--cmp-text-muted);">
                  <span>+10% (Moderate)</span>
                  <span>+60% (Hyperscale Surge)</span>
                </div>
              </div>

              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <strong style="color: var(--cmp-text-primary);">Internal AI Task Automation</strong>
                  <span style="font-weight: 800; color: var(--cmp-deep-primary);">${simState.automationRate}%</span>
                </div>
                <input type="range" min="10" max="70" step="5" value="${simState.automationRate}" id="simAutomationRate" style="width: 100%; accent-color: var(--cmp-deep-primary);" />
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--cmp-text-muted);">
                  <span>10% (Manual)</span>
                  <span>70% (Autopilot Testing)</span>
                </div>
              </div>

              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 4px;">
                  <strong style="color: var(--cmp-text-primary);">Internal Academy Upskilling Budget</strong>
                  <span style="font-weight: 800; color: var(--cmp-success);">$${simState.upskillInvestment}K</span>
                </div>
                <input type="range" min="50" max="600" step="25" value="${simState.upskillInvestment}" id="simUpskillBudget" style="width: 100%; accent-color: var(--cmp-success);" />
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--cmp-text-muted);">
                  <span>$50K</span>
                  <span>$600K (Enterprise Scaling)</span>
                </div>
              </div>
            </div>

            <!-- Output Metric Panel -->
            <div style="background: var(--cmp-very-light); border-radius: var(--cmp-radius-md); border: 1px solid var(--cmp-border); padding: 18px; display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <span class="cmp-eyebrow" style="color: var(--cmp-deep-primary);"><i data-lucide="calculator" class="cmp-icon-inline"></i> ILLUSTRATIVE CALCULATION</span>
                <h4 style="font-size: 16px; font-weight: 850; color: var(--cmp-text-primary); margin: 2px 0 12px;">Sample Arithmetic · Not an Operational Outcome</h4>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">
                  <div style="background: #FFFFFF; padding: 12px; border-radius: 8px; border: 1px solid var(--cmp-border);">
                    <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Unmet Deficit</span>
                    <div style="font-size: 20px; font-weight: 850; color: ${netDeficit > 90 ? 'var(--cmp-danger)' : 'var(--cmp-warning)'};">${netDeficit} Eng</div>
                  </div>

                  <div style="background: #FFFFFF; padding: 12px; border-radius: 8px; border: 1px solid var(--cmp-border);">
                    <span style="font-size: 11px; color: var(--cmp-text-muted); text-transform: uppercase;">Search Fees Saved</span>
                    <div style="font-size: 20px; font-weight: 850; color: var(--cmp-success);">$${searchFeesAvoided}K</div>
                  </div>
                </div>

                <div style="background: #FFFFFF; padding: 12px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px;">
                  <span style="color: var(--cmp-text-secondary);">Net Academy ROI:</span>
                  <strong style="color: var(--cmp-deep-primary); font-size: 14.5px; display: block; margin-top: 2px;">+$${netROI}K Net Financial Benefit</strong>
                </div>
              </div>

              <button type="button" class="cmp-btn-primary" id="cmpSaveParametricModelBtn" style="margin-top: 14px; width: 100%;">
                <i data-lucide="save"></i>
                <span>Save unavailable (not implemented)</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

export function bindCompanySimulationEvents(rerender) {
  // Scenario Card selection
  document.querySelectorAll('.cmp-scen-selector').forEach(card => {
    card.addEventListener('click', () => {
      activeScenarioId = card.dataset.scenId;
      rerender();
    });
  });

  // Sliders
  document.querySelector('#simDemandSurge')?.addEventListener('input', (e) => {
    simState.demandSurge = parseInt(e.target.value, 10);
    rerender();
  });

  document.querySelector('#simAutomationRate')?.addEventListener('input', (e) => {
    simState.automationRate = parseInt(e.target.value, 10);
    rerender();
  });

  document.querySelector('#simUpskillBudget')?.addEventListener('input', (e) => {
    simState.upskillInvestment = parseInt(e.target.value, 10);
    rerender();
  });

  // Export memo
  document.querySelector('#cmpExportScenarioBrief')?.addEventListener('click', () => {
    alert('Export is not implemented. No brief was created or saved.');
  });

  // Save model
  document.querySelector('#cmpSaveParametricModelBtn')?.addEventListener('click', () => {
    alert('Saving is not implemented. No model was saved.');
  });

  // Create Custom Scenario Modal
  document.querySelector('#cmpCreateScenarioBtn')?.addEventListener('click', () => {
    openCompanyModal({
      title: 'Create Custom What-If Scenario',
      subtitle: 'Define market trigger, time horizon, and target affected teams.',
      icon: 'sliders',
      maxWidth: '560px',
      contentHtml: `
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div>
            <label style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Scenario Title *</label>
            <input type="text" id="newScenTitle" placeholder="e.g. Autonomous Driving Pod Doubling" style="width: 100%; height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px;" />
          </div>
          <div>
            <label style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Market Trigger Description *</label>
            <textarea id="newScenTrigger" placeholder="What market, product, or regulatory shift drives this scenario?" style="width: 100%; height: 70px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; resize: vertical;"></textarea>
          </div>
          <div>
            <label style="font-size: 12px; font-weight: 700; color: var(--cmp-text-primary); display: block; margin-bottom: 4px;">Primary Affected Pod</label>
            <select id="newScenTeam" style="width: 100%; height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; background: #FFF;">
              <option value="Autonomous Compute">Autonomous Compute</option>
              <option value="Hyperscale Inference Services">Hyperscale Inference Services</option>
              <option value="NeMo Cloud Platform">NeMo Cloud Platform</option>
            </select>
          </div>
        </div>
      `,
      cancelText: 'Cancel',
      confirmText: 'Add Illustrative Scenario',
      confirmIcon: 'cpu',
      onConfirm: () => {
        const title = document.querySelector('#newScenTitle')?.value.trim();
        const trigger = document.querySelector('#newScenTrigger')?.value.trim();
        if (!title || !trigger) {
          alert('Please provide a scenario title and trigger description.');
          return false;
        }

        const newId = `scen-custom-${Date.now().toString().slice(-4)}`;
        simulationScenarios.unshift({
          id: newId,
          title,
          badge: 'Illustrative Scenario · No Model',
          trigger,
          impacts: [],
          recommendedStrategy: 'No validated model is available to estimate workforce impact or recommend a strategy.'
        });

        activeScenarioId = newId;
        rerender();
        alert(`Illustrative scenario "${title}" was added for this session. No workforce estimate was generated or saved.`);
        return true;
      }
    });
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
