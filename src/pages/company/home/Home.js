// ============================================================================
// TALENTSCOPE.AI — COMPANY HOME
// Executive Workforce Intelligence Console (#874FFF)
// "How is our workforce doing and what changed?"
// Concise, decision-oriented, minimal text, clear hierarchy
// ============================================================================

import {
  companyProfile,
  companyOverviewMetrics,
  companyStrategicSignals,
  companyCriticalSkillGaps,
  companyWorkforceImpact,
  companyRecommendedActions
} from '../../../data/company/company-data.js';

import { openCompanyProfileModal } from '../components/CompanyProfileModal.js';
import { openCompanyModal } from '../components/CompanyModal.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

export function renderCompanyHome() {
  const p = companyProfile;
  const m = companyOverviewMetrics;
  const completion = p.completionPercentage || 82;

  return `
    <div class="company-page company-home">
      <aside role="note" class="cmp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">Illustrative company dashboard preview. Workforce, skill, market and recommendation figures shown here are sample data, not verified company records or live intelligence.</aside>
      <!-- 1. COMPANY HEADER (Section 7) -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="shield-alert" class="cmp-icon-inline"></i>
              COMPANY WORKFORCE INTELLIGENCE
            </span>
            <h1>Build the workforce your future needs.</h1>
            <p>Understand market changes, workforce health, skill gaps, and emerging role risks in one decision-oriented workspace.</p>
          </div>

          <div class="cmp-hero__context-badge" style="min-width: 320px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
              <div class="cmp-hero__company-logo" title="${esc(p.name)}">
                ${esc(p.logoInitials)}
              </div>
              <div class="cmp-hero__context-info" style="flex: 1;">
                <strong>${esc(p.name)}</strong>
                <span>${esc(p.industry)}</span>
                <div class="cmp-hero__context-meta" style="margin-top: 2px;">
                  <span><i data-lucide="map-pin"></i> ${esc(p.headquarters)}</span>
                  <span>·</span>
                  <span><i data-lucide="users"></i> ${(p.globalHeadcount).toLocaleString()}</span>
                </div>
              </div>
            </div>

            <!-- Profile Progress & Button -->
            <div style="padding-top: 10px; border-top: 1px solid var(--cmp-border, #E6DEF7); display: flex; align-items: center; justify-content: space-between; gap: 12px;">
              <div>
                <div style="font-size: 11.5px; font-weight: 700; color: var(--cmp-text-muted); margin-bottom: 3px;">
                  Company Profile · <strong style="color: var(--cmp-primary);">${completion}% Complete</strong>
                </div>
                <div class="cmp-meter-track" style="width: 120px; height: 5px;">
                  <div class="cmp-meter-fill cmp-meter-fill--accent" style="width: ${completion}%;"></div>
                </div>
              </div>
              <button type="button" class="cmp-btn-secondary" id="cmpHeaderProfileBtn" style="height: 32px; padding: 0 12px; font-size: 12px;">
                <i data-lucide="edit-3"></i>
                <span>${completion < 100 ? 'Complete Profile' : 'Edit Profile'}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. WORKFORCE INTELLIGENCE OVERVIEW (Section 7: 5 Compact Metric Cards) -->
      <section class="cmp-section">
        <div style="margin-bottom: 14px;">
          <span class="cmp-eyebrow"><i data-lucide="layout-grid" class="cmp-icon-inline"></i> WORKFORCE STATUS</span>
          <h2 class="cmp-title">Workforce Intelligence Overview</h2>
          <p class="cmp-subtitle">Illustrative workforce indicators for preview; connected company data is not available yet.</p>
        </div>

        <div class="cmp-overview-grid" style="grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));">
          <!-- Card 1: Workforce Health -->
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Workforce Health</span>
                <div class="cmp-metric-card__icon"><i data-lucide="heart-pulse"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-success);">
                ${m.workforceHealth.score} <span style="font-size: 14px; font-weight: 600; color: var(--cmp-text-muted);">/ 100</span>
              </div>
              <div class="cmp-metric-card__headline">${esc(m.workforceHealth.status)}</div>
              <p class="cmp-metric-card__summary">Core capabilities meet current pipeline commitments across key pods.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--success"><i data-lucide="trending-up"></i> ${esc(m.workforceHealth.change)}</span>
              <a href="#/company/workforce" class="cmp-metric-card__link">
                <span>View Workforce</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>

          <!-- Card 2: Skill Gap -->
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Skill Gap</span>
                <div class="cmp-metric-card__icon"><i data-lucide="target"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-warning);">
                ${esc(m.criticalSkillGap.value)}
              </div>
              <div class="cmp-metric-card__headline">${esc(m.criticalSkillGap.headline)}</div>
              <p class="cmp-metric-card__summary">3 teams have urgent need in CUDA, NCCL, and model quantization.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--warning">Deficit: 14%</span>
              <a href="#/company/skills" class="cmp-metric-card__link">
                <span>View Skills</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>

          <!-- Card 3: Role Change -->
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Role Change</span>
                <div class="cmp-metric-card__icon"><i data-lucide="git-branch"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-deep-primary);">
                ${esc(m.roleEvolutionRisk.level)}
              </div>
              <div class="cmp-metric-card__headline">${esc(m.roleEvolutionRisk.headline)}</div>
              <p class="cmp-metric-card__summary">AI and backend REST developers shifting to containerized microservices.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--neutral">34% Tasks Evolving</span>
              <a href="#/company/workforce" class="cmp-metric-card__link">
                <span>Inspect Roles</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>

          <!-- Card 4: Hiring Demand -->
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">Hiring Demand</span>
                <div class="cmp-metric-card__icon"><i data-lucide="user-plus"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-primary);">
                ${esc(m.hiringDemand.value)}
              </div>
              <div class="cmp-metric-card__headline">${esc(m.hiringDemand.headline)}</div>
              <p class="cmp-metric-card__summary">Expansion velocity focused on Autonomous Compute and Edge Hubs.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--accent">+18.4% QoQ</span>
              <a href="#/company/market" class="cmp-metric-card__link">
                <span>Hiring Trends</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>

          <!-- Card 5: AI Impact -->
          <div class="cmp-metric-card">
            <div>
              <div class="cmp-metric-card__header">
                <span class="cmp-metric-card__label">AI Impact</span>
                <div class="cmp-metric-card__icon"><i data-lucide="sparkles"></i></div>
              </div>
              <div class="cmp-metric-card__value" style="color: var(--cmp-deep-primary);">
                ${esc(m.aiImpactIndex.level)}
              </div>
              <div class="cmp-metric-card__headline">${esc(m.aiImpactIndex.headline)}</div>
              <p class="cmp-metric-card__summary">Automated testing and profiling accelerating engineering velocity +22%.</p>
            </div>
            <div class="cmp-metric-card__footer">
              <span class="cmp-badge cmp-badge--neutral">+28% Velocity</span>
              <a href="#/company/simulation" class="cmp-metric-card__link">
                <span>Simulate Impact</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>
        </div>
      </section>

      <!-- 3. WHAT CHANGED? (Section 7: 5 Meaningful Scannable Changes) -->
      <section class="cmp-section">
        <div style="margin-bottom: 14px;">
          <span class="cmp-eyebrow"><i data-lucide="radio" class="cmp-icon-inline"></i> STRATEGIC PULSE</span>
          <h2 class="cmp-title">What Changed?</h2>
          <p class="cmp-subtitle">Market events, technology shifts, and hiring expansion triggers impacting our workforce.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
          ${companyStrategicSignals.slice(0, 4).map(sig => `
            <div class="cmp-card" style="display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                  <span class="cmp-badge cmp-badge--neutral">${esc(sig.category)}</span>
                  <span class="cmp-badge cmp-badge--success"><i data-lucide="trending-up"></i> ${esc(sig.change)}</span>
                </div>
                <h3 style="font-size: 15px; font-weight: 800; color: var(--cmp-text-primary); margin: 0 0 6px;">${esc(sig.title)}</h3>
                
                <div style="margin-bottom: 10px;">
                  <span style="font-size: 11px; font-weight: 700; color: var(--cmp-text-muted); text-transform: uppercase; display: block;">Why it matters:</span>
                  <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 2px 0 0; line-height: 1.45;">${esc(sig.whyItMatters)}</p>
                </div>

                <div style="font-size: 12px; color: var(--cmp-text-muted); margin-bottom: 6px;">
                  <strong>Affected:</strong> <span style="color: var(--cmp-text-primary); font-weight: 600;">${sig.affectedTeams.length} teams (${esc(sig.affectedTeams.slice(0, 2).join(', '))})</span>
                </div>
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 12px; border-top: 1px solid var(--cmp-border-subtle); margin-top: 10px;">
                <span style="font-size: 11.5px; font-weight: 700; color: var(--cmp-text-muted);">${esc(sig.metric)}</span>
                <a href="${esc(sig.actionRoute)}" class="cmp-btn-secondary" style="height: 30px; padding: 0 12px; font-size: 12px;">
                  <span>${esc(sig.actionLabel)}</span>
                  <i data-lucide="arrow-right"></i>
                </a>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 4. EQUAL 2-COLUMN SECTION: CRITICAL SKILL GAPS & ROLE EVOLUTION -->
      <section class="cmp-section">
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; align-items: stretch;">
          
          <!-- Column 1: Critical Skill Gaps (Section 7) -->
          <div class="cmp-card" style="display: flex; flex-direction: column;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
              <div>
                <span class="cmp-eyebrow"><i data-lucide="target" class="cmp-icon-inline"></i> SKILL DEFICIT AUDIT</span>
                <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0;">Critical Skill Gaps</h3>
                <span style="font-size: 12px; color: var(--cmp-text-secondary);">Highest priority capabilities needed for upcoming deliverables.</span>
              </div>
              <a href="#/company/skills" class="cmp-btn-ghost" style="font-size: 12px; padding: 0 8px;">
                <span>View All Skills</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>

            <!-- Compact Skill Table -->
            <div class="cmp-table-container" style="flex: 1; border: 1px solid var(--cmp-border-subtle); border-radius: 10px;">
              <table class="cmp-table" style="font-size: 12.5px;">
                <thead>
                  <tr>
                    <th>Skill</th>
                    <th>Coverage / Target</th>
                    <th>Gap</th>
                    <th>Risk</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${companyCriticalSkillGaps.slice(0, 5).map(sk => `
                    <tr>
                      <td>
                        <strong style="color: var(--cmp-text-primary); font-size: 13px; display: block;">${esc(sk.name)}</strong>
                        <small style="color: var(--cmp-text-muted);">${sk.affectedTeams[0] || 'Core Pod'}</small>
                      </td>
                      <td>
                        <div class="cmp-dual-bar" style="max-width: 140px;">
                          <div class="cmp-dual-bar__labels" style="font-size: 11px;">
                            <span>${sk.currentCoverage}%</span>
                            <span style="color: var(--cmp-primary);">${sk.futureDemand}%</span>
                          </div>
                          <div class="cmp-dual-bar__track" style="height: 5px;">
                            <div class="cmp-dual-bar__target" style="width: ${sk.futureDemand}%;"></div>
                            <div class="cmp-dual-bar__current" style="width: ${sk.currentCoverage}%;"></div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <strong style="color: ${sk.gap > 20 ? 'var(--cmp-danger)' : sk.gap > 10 ? 'var(--cmp-warning)' : 'var(--cmp-success)'};">
                          ${sk.gap > 0 ? '-' + sk.gap + '%' : '0%'}
                        </strong>
                      </td>
                      <td>
                        <span class="cmp-badge ${sk.risk === 'High' ? 'cmp-badge--danger' : sk.risk === 'Medium' ? 'cmp-badge--warning' : 'cmp-badge--neutral'}" style="font-size: 10.5px;">
                          ${esc(sk.risk)}
                        </span>
                      </td>
                      <td>
                        <a href="#/company/skills" class="cmp-btn-secondary" style="height: 26px; padding: 0 8px; font-size: 11px;">
                          ${esc(sk.action)}
                        </a>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>

          <!-- Column 2: Role Evolution (Section 7 & 16) -->
          <div class="cmp-card" style="display: flex; flex-direction: column;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
              <div>
                <span class="cmp-eyebrow"><i data-lucide="trending-up" class="cmp-icon-inline"></i> ROLE EVOLUTION</span>
                <h3 style="font-size: 17px; font-weight: 850; color: var(--cmp-text-primary); margin: 0;">How Roles Are Changing</h3>
                <span style="font-size: 12px; color: var(--cmp-text-secondary);">Current responsibilities transitioning to emerging responsibilities.</span>
              </div>
              <a href="#/company/workforce" class="cmp-btn-ghost" style="font-size: 12px; padding: 0 8px;">
                <span>View Roles</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>

            <!-- Role Evolution Cards -->
            <div style="display: flex; flex-direction: column; gap: 10px; flex: 1; justify-content: space-around;">
              <div style="background: var(--cmp-very-light); padding: 12px 14px; border-radius: 10px; border: 1px solid var(--cmp-border);">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
                  <strong style="color: var(--cmp-text-primary); font-size: 13.5px;">AI Engineer (L4) → Senior AI Platform Lead</strong>
                  <span class="cmp-badge cmp-badge--accent">Growing Role</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                  <div>
                    <span style="color: var(--cmp-text-muted); font-weight: 700; text-transform: uppercase; font-size: 10.5px;">Current Tasks:</span>
                    <ul style="margin: 4px 0 0; padding-left: 14px; color: var(--cmp-text-secondary);">
                      <li>Model fine-tuning</li>
                      <li>PyTorch evaluation scripts</li>
                    </ul>
                  </div>
                  <div>
                    <span style="color: var(--cmp-deep-primary); font-weight: 700; text-transform: uppercase; font-size: 10.5px;">Emerging Tasks:</span>
                    <ul style="margin: 4px 0 0; padding-left: 14px; color: var(--cmp-text-primary);">
                      <li>Low-latency CUDA memory tuning</li>
                      <li>Distributed 128+ GPU cluster orchestration</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div style="background: var(--cmp-very-light); padding: 12px 14px; border-radius: 10px; border: 1px solid var(--cmp-border);">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
                  <strong style="color: var(--cmp-text-primary); font-size: 13.5px;">Backend REST Developer → Triton Microservices Engineer</strong>
                  <span class="cmp-badge cmp-badge--warning">Redeployment</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                  <div>
                    <span style="color: var(--cmp-text-muted); font-weight: 700; text-transform: uppercase; font-size: 10.5px;">Current Tasks:</span>
                    <ul style="margin: 4px 0 0; padding-left: 14px; color: var(--cmp-text-secondary);">
                      <li>REST API endpoints (monolith)</li>
                      <li>Standard relational SQL queries</li>
                    </ul>
                  </div>
                  <div>
                    <span style="color: var(--cmp-deep-primary); font-weight: 700; text-transform: uppercase; font-size: 10.5px;">Emerging Tasks:</span>
                    <ul style="margin: 4px 0 0; padding-left: 14px; color: var(--cmp-text-primary);">
                      <li>Containerized Triton model serving</li>
                      <li>High-throughput gRPC streaming</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 5. RECOMMENDED ACTIONS (Section 7: Prioritized Decisions) -->
      <section class="cmp-section">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
          <div>
            <span class="cmp-eyebrow"><i data-lucide="check-square" class="cmp-icon-inline"></i> COMPANY DECISION OPTIONS</span>
            <h2 class="cmp-title">Recommended Actions</h2>
            <p class="cmp-subtitle">Prioritized interventions answering: What should the company do next to close capability deficits?</p>
          </div>
          <div style="display: flex; gap: 8px;">
            <a href="#/company/mobility" class="cmp-btn-secondary" style="height: 36px; padding: 0 14px;">
              <i data-lucide="git-pull-request"></i>
              <span>Internal Mobility</span>
            </a>
            <a href="#/company/simulation" class="cmp-btn-primary" style="height: 36px; padding: 0 16px;">
              <i data-lucide="sliders"></i>
              <span>Simulate Options</span>
            </a>
          </div>
        </div>

        <div class="cmp-actions-grid" style="grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));">
          ${companyRecommendedActions.slice(0, 4).map(act => `
            <div class="cmp-action-card" style="display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div class="cmp-action-card__top" style="margin-bottom: 8px;">
                  <span class="cmp-action-type-pill cmp-action-type-pill--${act.type.toLowerCase()}">${esc(act.type)}</span>
                  <span class="cmp-badge ${act.priority === 'High' ? 'cmp-badge--danger' : 'cmp-badge--neutral'}" style="font-size: 10.5px;">
                    ${esc(act.priority)} Priority
                  </span>
                </div>
                <h4 class="cmp-action-card__title" style="font-size: 14.5px; margin: 0 0 6px;">${esc(act.title)}</h4>
                
                <div style="font-size: 12px; margin-bottom: 6px;">
                  <strong style="color: var(--cmp-text-muted); text-transform: uppercase; font-size: 10.5px; display: block;">Why:</strong>
                  <span style="color: var(--cmp-text-secondary); line-height: 1.4;">${esc(act.reason)}</span>
                </div>

                <div style="background: var(--cmp-very-light); padding: 8px 10px; border-radius: 6px; font-size: 11.5px; margin-bottom: 8px; border: 1px solid var(--cmp-border-subtle);">
                  <strong style="color: var(--cmp-deep-primary);">Impact:</strong>
                  <span style="color: var(--cmp-text-secondary);">${esc(act.impact)}</span>
                </div>
              </div>

              <div style="padding-top: 10px; border-top: 1px solid var(--cmp-border-subtle); display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                <span style="font-size: 11px; color: var(--cmp-text-muted); font-weight: 600;">${act.type === 'UPSKILL' ? '42 Engineers' : act.type === 'REDEPLOY' ? '14 Engineers' : act.type === 'HIRE' ? '6 Requisitions' : 'Continuous'}</span>
                <button type="button" class="cmp-btn-primary review-action-btn" data-act-id="${esc(act.id)}" data-route="${esc(act.route)}" style="height: 30px; padding: 0 12px; font-size: 11.5px;">
                  <span>Review Action</span>
                  <i data-lucide="arrow-right"></i>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </section>
    </div>
  `;
}

export function bindCompanyHomeEvents(rerender) {
  // Company Profile Modal Launch
  document.querySelector('#cmpHeaderProfileBtn')?.addEventListener('click', () => {
    openCompanyProfileModal('overview', () => {
      rerender();
    });
  });

  // Action Buttons
  document.querySelectorAll('.review-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const actId = btn.dataset.actId;
      const route = btn.dataset.route;
      const action = companyRecommendedActions.find(a => a.id === actId);
      if (!action) {
        if (route) window.location.hash = route;
        return;
      }

      openCompanyModal({
        title: `Strategic Intervention: ${action.title}`,
        subtitle: `${action.type} · ${action.priority} Priority`,
        icon: 'check-square',
        maxWidth: '560px',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <div>
              <strong style="font-size: 12.5px; color: var(--cmp-text-muted); text-transform: uppercase;">Strategic Driver (Why):</strong>
              <p style="margin: 4px 0 0; font-size: 13.5px; color: var(--cmp-text-primary);">${esc(action.reason)}</p>
            </div>
            <div style="background: var(--cmp-light-primary); padding: 12px; border-radius: 8px; border-left: 3px solid var(--cmp-primary);">
              <strong style="color: var(--cmp-deep-primary); font-size: 12.5px;">Projected Organizational Impact:</strong>
              <p style="margin: 4px 0 0; font-size: 13px; color: var(--cmp-text-primary);">${esc(action.impact)}</p>
            </div>
            <div style="background: var(--cmp-very-light); padding: 12px; border-radius: 8px; border: 1px solid var(--cmp-border);">
              <strong style="color: var(--cmp-text-muted); font-size: 11.5px; text-transform: uppercase;">Cost / Benefit Ratio:</strong>
              <p style="margin: 4px 0 0; font-size: 12.5px; color: var(--cmp-text-secondary);">${esc(action.costBenefit)}</p>
            </div>
          </div>
        `,
        cancelText: 'Dismiss',
        confirmText: 'Execute in Workspace',
        confirmIcon: 'arrow-right',
        onConfirm: () => {
          if (route) window.location.hash = route;
          return true;
        }
      });
    });
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
