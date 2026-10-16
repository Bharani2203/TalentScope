// ============================================================================
// TALENTSCOPE.AI — COMPANY SKILL INTELLIGENCE
// What skills do we have and need? Organizational Skill Portfolio & Academy Roadmaps (#874FFF)
// ============================================================================

import {
  companyProfile,
  companyCriticalSkillGaps,
  companyWorkforceImpact
} from '../../../data/company/company-data.js';

import { openCompanyModal } from '../components/CompanyModal.js';
import { querySkillIntelligence } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let selectedCategoryFilter = 'all';
let skillSearchQuery = '';
let companySkillsIntelligence = null;
let companySkillsLoading = false;
let companySkillsError = null;

let companySkillsRequestVersion = 0;

export async function loadCompanySkillIntelligence(rerender) {
  if (companySkillsIntelligence || companySkillsLoading) return;
  const currentVersion = ++companySkillsRequestVersion;
  companySkillsLoading = true;
  companySkillsError = null;
  const p = companyProfile;

  try {
    const res = await querySkillIntelligence({
      portal_type: 'company',
      company_id: p.id,
      company_name: p.name,
      industry: p.industry,
      workforce_headcount: p.globalHeadcount,
      skills: companyCriticalSkillGaps.map(s => s.name),
      range: '6m'
    });
    if (currentVersion !== companySkillsRequestVersion) return;
    companySkillsIntelligence = res;
    companySkillsLoading = false;
    if (typeof rerender === 'function') rerender();
  } catch (err) {
    if (currentVersion !== companySkillsRequestVersion) return;
    console.warn('[Company SkillIntelligence] Failed to load intelligence:', err);
    companySkillsLoading = false;
    companySkillsError = err.message || 'Failed to load intelligence';
    if (typeof rerender === 'function') rerender();
  }
}

export function renderCompanySkillIntelligence() {
  const p = companyProfile;

  const cmpAction = companySkillsIntelligence?.action_recommendations?.[0]
    || companySkillsIntelligence?.raw?.action_recommendations?.[0];

  const filteredSkills = companyCriticalSkillGaps.filter(sk => {
    const matchesSearch = !skillSearchQuery ||
      sk.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
      sk.category.toLowerCase().includes(skillSearchQuery.toLowerCase());
    const matchesCategory = selectedCategoryFilter === 'all' ||
      (selectedCategoryFilter === 'critical' && sk.risk === 'High') ||
      (selectedCategoryFilter === 'maintain' && sk.gap === 0) ||
      (selectedCategoryFilter === sk.category);
    return matchesSearch && matchesCategory;
  });

  return `
    <div class="company-page company-skills">
      <aside role="note" class="cmp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">Illustrative company skills prototype. Coverage, health, gap and role-fit examples are sample values, not verified workforce records.</aside>
      ${companySkillsIntelligence?.answer ? `
        <div class="cmp-card" style="margin-bottom: 14px; padding: 14px 18px; background: #F8F9FD; border-left: 4px solid var(--cmp-primary, #874FFF); font-size: 13px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <div style="font-weight: 750; color: var(--cmp-primary, #874FFF); display: flex; align-items: center; gap: 6px;">
              <i data-lucide="sparkles"></i>
              <span>${esc(companySkillsIntelligence.answer.headline)}</span>
            </div>
            <span class="cmp-badge cmp-badge--primary" style="font-size: 10.5px;">${esc(companySkillsIntelligence.answer.contextual_focus || 'Enterprise Workforce Planning')}</span>
          </div>
          <p style="color: var(--cmp-text-secondary, #475467); margin: 0 0 8px 0; line-height: 1.45;">
            ${esc(companySkillsIntelligence.answer.summary)}
          </p>
          ${companySkillsIntelligence.answer.key_insights?.length ? `
            <ul style="margin: 0 0 8px 18px; padding: 0; font-size: 12px; color: var(--cmp-text-muted, #667085); line-height: 1.4;">
              ${companySkillsIntelligence.answer.key_insights.map(ki => `<li>${esc(ki)}</li>`).join('')}
            </ul>
          ` : ''}
          ${companySkillsIntelligence.answer.limitations?.length ? `
            <div style="font-size: 11px; color: var(--cmp-text-muted, #667085); border-top: 1px dashed #D0D5DD; padding-top: 6px;">
              <strong>Strategic Limitations:</strong> ${companySkillsIntelligence.answer.limitations.map(l => esc(l)).join(' ')}
            </div>
          ` : ''}
          ${renderIntelligenceEvidencePanel(companySkillsIntelligence, {
            title: 'Company skill evidence',
            loading: companySkillsLoading,
            error: companySkillsError
          })}
        </div>
      ` : ''}
      ${cmpAction ? `
        <div class="cmp-card" style="margin-bottom: 14px; padding: 14px 18px; background: #FFFFFF; border: 1px solid var(--cmp-border, #E4E7EC); border-left: 4px solid var(--cmp-primary, #874FFF); font-size: 13px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <span style="font-size: 11px; font-weight: 800; color: var(--cmp-primary, #874FFF); text-transform: uppercase;">04 — WHAT WORKFORCE ACTION TO TAKE</span>
            <span class="cmp-badge ${cmpAction.priority === 'high' ? 'cmp-badge--danger' : 'cmp-badge--neutral'}" style="font-size: 10px; font-weight: 700;">Priority: ${esc(cmpAction.priority)}</span>
          </div>
          <div style="font-size: 14px; font-weight: 750; color: var(--cmp-text-primary, #101828); margin-bottom: 4px;">
            ${esc(cmpAction.title)}
          </div>
          <p style="font-size: 12.5px; color: var(--cmp-text-secondary, #475467); margin: 0 0 8px 0; line-height: 1.45;">
            ${esc(cmpAction.recommended_action)}
          </p>
          <div style="font-size: 11.5px; color: var(--cmp-text-muted, #667085); line-height: 1.4; background: var(--cmp-very-light, #F9FAFB); padding: 8px 12px; border-radius: 6px; margin-bottom: 8px;">
            <strong>Why this action:</strong> ${esc(cmpAction.why_it_matters)}
          </div>
          ${cmpAction.limitations?.length ? `
            <div style="font-size: 11px; color: var(--cmp-text-muted, #667085);">
              <strong>Workforce Limitation:</strong> ${esc(cmpAction.limitations[0])}
            </div>
          ` : ''}
        </div>
      ` : ''}
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="layers" class="cmp-icon-inline"></i>
              ORGANIZATIONAL SKILL PORTFOLIO
            </span>
            <h1>What Skills Do We Have and Need?</h1>
            <p>Measure enterprise skill coverage against future demand, assess technical skill relevance, and plan targeted upskilling academies.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logoInitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Skill Inventory Architecture</span>
              <div class="cmp-hero__context-meta">
                <span><i data-lucide="award"></i> Certified Bench: 1,840</span>
                <span>·</span>
                <span><i data-lucide="clock"></i> Refresh Cycle: 6 Months</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. HIGH-LEVEL SKILL METRICS (Section 15) -->
      <section class="cmp-section">
        <div class="cmp-overview-grid" style="grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));">
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Average Skill Health</span>
                <div class="cmp-metric-card__icon"><i data-lucide="heart-pulse"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-success);">86%</div>
              <div class="cmp-metric-card__headline">Healthy Core Capability</div>
              <p class="cmp-metric-card__summary">Core capabilities verified across US and APAC hubs.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--success">+3.8% QoQ</span>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Critical Skill Deficit</span>
                <div class="cmp-metric-card__icon"><i data-lucide="target"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-danger);">14%</div>
              <div class="cmp-metric-card__headline">3 Urgent Priority Gaps</div>
              <p class="cmp-metric-card__summary">CUDA Kernels, NCCL, and Model Quantization.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--danger">Deficit: 14%</span>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Average Skill Half-Life</span>
                <div class="cmp-metric-card__icon"><i data-lucide="clock"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-primary);">2.4 Years</div>
              <div class="cmp-metric-card__headline">Relevance Horizon</div>
              <p class="cmp-metric-card__summary">How quickly technical skills lose industry relevance.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--neutral">6-Mo Sprint Cycle</span>
            </div>
          </div>

          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Active Academy Cohorts</span>
                <div class="cmp-metric-card__icon"><i data-lucide="graduation-cap"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-deep-primary);">142 Eng</div>
              <div class="cmp-metric-card__headline">Enrolled in Sprints</div>
              <p class="cmp-metric-card__summary">DLI Kernel Academy and Triton Microservices.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--accent">84% Completion</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 3. SKILL PORTFOLIO TABLE (Section 15: Coverage, Future Demand, Gap, Risk, Action) -->
      <section class="cmp-section">
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div>
              <span class="cmp-eyebrow"><i data-lucide="target" class="cmp-icon-inline"></i> CAPABILITY MAPPING</span>
              <h2 class="cmp-title">Enterprise Skill Coverage vs Future Demand</h2>
              <p class="cmp-subtitle">Current organizational coverage compared to projected 12-month requirements.</p>
            </div>

            <!-- Search and Filter Controls -->
            <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
              <div style="position: relative; width: 220px;">
                <i data-lucide="search" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 14px; height: 14px; color: var(--cmp-text-muted);"></i>
                <input
                  type="text"
                  id="cmpSkillSearchInput"
                  value="${esc(skillSearchQuery)}"
                  placeholder="Filter skills..."
                  style="width: 100%; height: 36px; padding: 0 12px 0 32px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; outline: none;"
                />
              </div>

              <select id="cmpSkillCategorySelect" style="height: 36px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; background: #FFF; outline: none;">
                <option value="all" ${selectedCategoryFilter === 'all' ? 'selected' : ''}>All Skills</option>
                <option value="critical" ${selectedCategoryFilter === 'critical' ? 'selected' : ''}>Critical Deficits (High Risk)</option>
                <option value="maintain" ${selectedCategoryFilter === 'maintain' ? 'selected' : ''}>Healthy Baseline</option>
              </select>
            </div>
          </div>

          <!-- Table with Controlled Spacing (Section 30) -->
          <div class="cmp-table-container">
            <table class="cmp-table" style="font-size: 13px;">
              <thead>
                <tr>
                  <th style="min-width: 180px;">Skill</th>
                  <th>Category</th>
                  <th style="min-width: 200px;">Current Coverage vs Demand</th>
                  <th>Gap</th>
                  <th>Risk</th>
                  <th>Affected Teams</th>
                  <th>Recommended Action</th>
                </tr>
              </thead>
              <tbody>
                ${filteredSkills.map(sk => {
                  const trendMatch = companySkillsIntelligence?.trends?.find(t =>
                    (t.skill_name && t.skill_name.toLowerCase() === sk.name.toLowerCase()) ||
                    (t.skill_id && t.skill_id.toLowerCase() === sk.name.toLowerCase().replace(/[^a-z0-9]/g, '_'))
                  );
                  return `
                  <tr>
                    <td>
                      <strong style="color: var(--cmp-text-primary); font-size: 13.5px; display: block;">${esc(sk.name)}</strong>
                      <small style="color: var(--cmp-text-muted);">${sk.headcountWithSkill} qualified / ${sk.headcountNeeded} needed</small>
                      ${trendMatch ? `
                        <div style="margin-top: 4px;">
                          <span class="cmp-badge ${trendMatch.is_trend_ready ? 'cmp-badge--success' : 'cmp-badge--neutral'}" style="font-size: 10px;">
                            ${trendMatch.is_trend_ready ? esc(trendMatch.trend_label) : 'Insufficient Data'} · ${esc(trendMatch.signal_badge)}
                          </span>
                        </div>
                      ` : ''}
                    </td>
                    <td>
                      <span class="cmp-badge cmp-badge--neutral">${esc(sk.category)}</span>
                    </td>
                    <td>
                      <div class="cmp-dual-bar">
                        <div class="cmp-dual-bar__labels">
                          <span>Current: <strong>${sk.currentCoverage}%</strong></span>
                          <span>Target: <strong style="color: var(--cmp-primary);">${sk.futureDemand}%</strong></span>
                        </div>
                        <div class="cmp-dual-bar__track">
                          <div class="cmp-dual-bar__target" style="width: ${sk.futureDemand}%;"></div>
                          <div class="cmp-dual-bar__current" style="width: ${sk.currentCoverage}%;"></div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <strong style="color: ${sk.gap > 20 ? 'var(--cmp-danger)' : sk.gap > 0 ? 'var(--cmp-warning)' : 'var(--cmp-success)'};">
                        ${sk.gap > 0 ? '-' + sk.gap + '%' : 'Optimal'}
                      </strong>
                    </td>
                    <td>
                      <span class="cmp-badge ${sk.risk === 'High' ? 'cmp-badge--danger' : sk.risk === 'Medium' ? 'cmp-badge--warning' : 'cmp-badge--neutral'}">
                        ${esc(sk.risk)}
                      </span>
                    </td>
                    <td style="font-size: 12.5px; color: var(--cmp-text-secondary);">
                      ${esc(sk.affectedTeams.join(', '))}
                    </td>
                    <td>
                      <button type="button" class="cmp-btn-secondary plan-skill-btn" data-skill="${esc(sk.name)}" data-action="${esc(sk.action)}" data-gap="${sk.gap}" style="height: 28px; padding: 0 10px; font-size: 11.5px;">
                        <span>${esc(sk.action)}</span>
                      </button>
                    </td>
                  </tr>
                `;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- 4. EQUAL 2-COLUMN SECTION: TASK EVOLUTION & ACADEMY SPRINTS (Section 16 & 32) -->
      <section class="cmp-section">
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; align-items: stretch;">
          
          <!-- Column 1: Task Automation & Role Impact (Section 16: Non-frightening terminology) -->
          <div class="cmp-card" style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 14px;">
              <span class="cmp-eyebrow"><i data-lucide="bot" class="cmp-icon-inline"></i> TASK EVOLUTION</span>
              <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">How Responsibilities Are Changing</h3>
              <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0;">Routine tasks become automated so engineers can focus on high-value system performance.</p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 10px; flex: 1; justify-content: space-around;">
              ${companyWorkforceImpact.aiAugmentationMatrix.slice(0, 3).map(w => `
                <div style="background: var(--cmp-very-light); padding: 12px 14px; border-radius: 8px; border: 1px solid var(--cmp-border);">
                  <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
                    <strong style="font-size: 13px; color: var(--cmp-text-primary);">${esc(w.workflow)}</strong>
                    <span class="cmp-badge cmp-badge--accent">${esc(w.automationRate)} Assisted</span>
                  </div>
                  <span style="font-size: 12px; color: var(--cmp-text-secondary); display: block; margin-bottom: 2px;">${esc(w.status)}</span>
                  <small style="font-size: 11px; font-weight: 700; color: var(--cmp-success);">Result: ${esc(w.impact)}</small>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Column 2: Active Corporate Academy Sprints -->
          <div class="cmp-card" style="display: flex; flex-direction: column;">
            <div style="margin-bottom: 14px;">
              <span class="cmp-eyebrow"><i data-lucide="graduation-cap" class="cmp-icon-inline"></i> LEARNING ROADMAPS</span>
              <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 2px;">Corporate Upskilling Academies</h3>
              <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 0;">Structured internal cohorts closing critical skill deficits before Q4 deadlines.</p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 12px; flex: 1; justify-content: space-around;">
              <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 10px; border-left: 4px solid var(--cmp-primary); border-top: 1px solid var(--cmp-border); border-right: 1px solid var(--cmp-border); border-bottom: 1px solid var(--cmp-border);">
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                  <strong style="font-size: 13.5px; color: var(--cmp-text-primary);">NVIDIA DLI Advanced CUDA & Kernel Tuning</strong>
                  <span class="cmp-badge cmp-badge--danger">Priority 1</span>
                </div>
                <p style="font-size: 12px; color: var(--cmp-text-secondary); margin: 4px 0 8px;">8-week sprint covering FP4 memory layout and multi-GPU NVLink streaming for 42 engineers.</p>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
                  <span>Enrolled: <strong>42 Engineers</strong></span>
                  <a href="#/company/mobility" class="cmp-btn-secondary" style="height: 26px; padding: 0 8px; font-size: 11px;">Inspect Cohort</a>
                </div>
              </div>

              <div style="background: var(--cmp-very-light); padding: 14px; border-radius: 10px; border-left: 4px solid var(--cmp-info); border-top: 1px solid var(--cmp-border); border-right: 1px solid var(--cmp-border); border-bottom: 1px solid var(--cmp-border);">
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                  <strong style="font-size: 13.5px; color: var(--cmp-text-primary);">Triton Microservices Reskilling Bootcamp</strong>
                  <span class="cmp-badge cmp-badge--warning">Redeployment</span>
                </div>
                <p style="font-size: 12px; color: var(--cmp-text-secondary); margin: 4px 0 8px;">4-week program preparing 14 REST developers for high-throughput containerized inference.</p>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
                  <span>Enrolled: <strong>14 Engineers (64% Done)</strong></span>
                  <a href="#/company/mobility" class="cmp-btn-secondary" style="height: 26px; padding: 0 8px; font-size: 11px;">Track Progress</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

export function bindCompanySkillsEvents(rerender) {
  const searchInput = document.querySelector('#cmpSkillSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      skillSearchQuery = e.target.value;
      rerender();
      const updated = document.querySelector('#cmpSkillSearchInput');
      if (updated) {
        updated.focus();
        updated.setSelectionRange(skillSearchQuery.length, skillSearchQuery.length);
      }
    });
  }

  document.querySelector('#cmpSkillCategorySelect')?.addEventListener('change', (e) => {
    selectedCategoryFilter = e.target.value;
    rerender();
  });

  document.querySelectorAll('.plan-skill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const skill = btn.dataset.skill;
      const action = btn.dataset.action;
      const gap = btn.dataset.gap;

      openCompanyModal({
        title: `Plan Action for ${skill}`,
        subtitle: `Recommended Strategy: ${action} (Deficit: ${gap}%)`,
        icon: 'target',
        maxWidth: '540px',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <p style="font-size: 13.5px; color: var(--cmp-text-primary); margin: 0;">
              Our workforce intelligence engine identified an immediate <strong>${gap}% gap</strong> in <strong>${esc(skill)}</strong>.
            </p>
            <div style="background: var(--cmp-light-primary); padding: 12px; border-radius: 8px; font-size: 12.5px; color: var(--cmp-deep-primary);">
              <strong>Recommended Company Action:</strong> Deploy an internal learning cohort via the NVIDIA Deep Learning Institute (DLI) to close the deficit internally and save up to $1.1M in external recruiter search fees.
            </div>
          </div>
        `,
        cancelText: 'Dismiss',
        confirmText: 'Execute in Internal Mobility',
        confirmIcon: 'git-pull-request',
        onConfirm: () => {
          window.location.hash = '#/company/mobility';
          return true;
        }
      });
    });
  });

  if (!companySkillsIntelligence && !companySkillsLoading) {
    loadCompanySkillIntelligence(rerender);
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
