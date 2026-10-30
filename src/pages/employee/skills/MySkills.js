// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE MY SKILLS
// Accessible, scannable skill intelligence with direct contribution hooks
// ============================================================================

import {
  getEmployeeProfile,
  getEmployeeCurrentSkills,
  setEmployeeOnboardingProfile,
  employeeSkillsData,
  isCompanyEmployee
} from '../../../data/employee/employee-data.js';
import { openEmployeeModal } from '../components/EmployeeModal.js';
import { querySkillIntelligence } from '../../../api/core-intelligence-client.js';
import { loadRoleOnboardingProfile, saveRoleOnboardingStep } from '../../../onboarding/onboarding-api.js';
import { API_BASE_URL } from '../../../config/api.js';

let selectedSkillId = 'sk-cuda';
let activeCategory = 'All';
let activeStatus = 'All';
let liveIntelligence = null;
let intelligenceLoading = false;
let intelligenceError = null;
let lastQueriedSkill = null;
let skillDraftOwnerUid = null;
let skillDraft = null;
let skillSaving = false;
let skillSaveMessage = '';
let skillSaveFailed = false;
let trendingSkillsCache = null;
let trendingSkillsLoading = false;
let matchingRolesCache = null;
let matchingRolesLoading = false;

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function sparklineSVG(trend = [40, 44, 48, 52, 55, 58, 62], isGap = false) {
  const min = Math.min(...trend);
  const max = Math.max(...trend);
  const span = Math.max(1, max - min);
  const points = trend.map((v, i) => {
    const x = (i / (trend.length - 1)) * 120;
    const y = 32 - ((v - min) / span) * 24;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const strokeColor = isGap ? '#F59E0B' : '#2735F5';
  const fillColor = isGap ? 'rgba(245, 158, 11, 0.12)' : 'rgba(39, 53, 245, 0.12)';

  return `
    <svg viewBox="0 0 120 36" style="width: 100%; height: 36px; overflow: visible;">
      <polyline points="${points}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      <polygon points="0,36 ${points} 120,36" fill="${fillColor}" />
    </svg>
  `;
}

export function renderEmployeeMySkills() {
  const p = getEmployeeProfile();
  if (p.profileLoaded) return renderSavedEmployeeSkills(p);
  const allSkills = employeeSkillsData;
  const isCompany = isCompanyEmployee();

  const categories = ['All', 'Core Programming', 'Hardware Acceleration', 'AI Frameworks', 'Systems Architecture', 'Inference Acceleration'];
  const statuses = ['All', 'Strong', 'Developing', 'Gap', 'Mentor Eligible'];

  let filtered = allSkills;
  if (activeCategory !== 'All') {
    filtered = filtered.filter(s => s.category.toLowerCase().includes(activeCategory.toLowerCase()));
  }
  if (activeStatus === 'Mentor Eligible') {
    filtered = filtered.filter(s => s.mentorEligible);
  } else if (activeStatus !== 'All') {
    filtered = filtered.filter(s => s.status === activeStatus);
  }

  const selectedSkill = allSkills.find(s => s.id === selectedSkillId) || allSkills[0];
  const matchingTrend = liveIntelligence?.trends?.find(t => 
    (t.skill_name && t.skill_name.toLowerCase() === selectedSkill.name.toLowerCase()) ||
    (t.skill_id && t.skill_id.toLowerCase() === selectedSkill.name.toLowerCase().replace(/[^a-z0-9]/g, '_'))
  ) || (liveIntelligence?.trends?.length === 1 ? liveIntelligence.trends[0] : null);

  const empAction = liveIntelligence?.action_recommendations?.find(a =>
    a.target_id?.toLowerCase() === selectedSkill.name.toLowerCase() ||
    a.target_id?.toLowerCase() === selectedSkill.name.toLowerCase().replace(/[^a-z0-9]/g, '_')
  ) || liveIntelligence?.action_recommendations?.[0]
    || liveIntelligence?.raw?.action_recommendations?.[0];

  return `
    <div class="employee-page">
      <!-- Page Header -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="layers-3"></i>
            ${isCompany ? 'COMPANY & ROLE SKILL BENCHMARK' : 'MARKET & CAREER SKILL BENCHMARK'}
          </span>
          <h1 class="emp-hero-title">My Skills Portfolio</h1>
          <p class="emp-hero-desc">
            ${isCompany 
              ? `Benchmarked against <strong>${esc(p.role)}</strong> and upcoming <strong>${esc(p.targetRole)}</strong> requirements at <strong>${esc(p.company)}</strong>.`
              : `Benchmarked against global market standards for <strong>${esc(p.targetRole)}</strong> in high-throughput distributed systems.`}
          </p>
        </div>
        <div class="emp-hero-actions">
          <button type="button" class="emp-btn-primary" id="btnRequestSkillAssessment">
            <i data-lucide="award"></i>
            <span>Assess New Skill</span>
          </button>
        </div>
      </section>

      <!-- 2-Column Responsive Layout -->
      <div style="display: grid; grid-template-columns: 1fr 420px; gap: 24px; align-items: start;">
        
        <!-- LEFT COLUMN: Skills Table & Filters -->
        <div style="display: flex; flex-direction: column; gap: 16px;">
          
          <!-- Category & Status Filters -->
          <div class="emp-card" style="padding: 14px 18px; display: flex; flex-direction: column; gap: 12px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                <span style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; margin-right: 4px;">Category:</span>
                ${categories.map(c => `
                  <button type="button" class="emp-btn-ghost ${activeCategory === c ? 'emp-btn-secondary' : ''}" data-category-filter="${esc(c)}" style="height: 30px; font-size: 12px; padding: 0 10px;">
                    ${esc(c)}
                  </button>
                `).join('')}
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; border-top: 1px solid var(--emp-border-subtle); padding-top: 10px;">
              <span style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase; margin-right: 4px;">Status:</span>
              ${statuses.map(st => `
                <button type="button" class="emp-btn-ghost ${activeStatus === st ? 'emp-btn-secondary' : ''}" data-status-filter="${esc(st)}" style="height: 28px; font-size: 11.5px; padding: 0 9px;">
                  ${esc(st)}
                </button>
              `).join('')}
            </div>
          </div>

          <!-- Skills Table Card -->
          <div class="emp-card" style="padding: 0; overflow: hidden;">
            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 13.5px; text-align: left;">
                <thead>
                  <tr style="background: var(--emp-soft); border-bottom: 1px solid var(--emp-border); color: var(--emp-text-muted); font-size: 11.5px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.04em;">
                    <th style="padding: 14px 18px;">Skill Name</th>
                    <th style="padding: 14px 16px;">Skill Health</th>
                    <th style="padding: 14px 16px;">Relevance</th>
                    <th style="padding: 14px 16px;">Momentum</th>
                    <th style="padding: 14px 18px;">Target Fit</th>
                  </tr>
                </thead>
                <tbody>
                  ${filtered.map(sk => `
                    <tr class="emp-skill-interactive-row" data-select-skill="${esc(sk.id)}" style="border-bottom: 1px solid var(--emp-border-subtle); cursor: pointer; transition: background 140ms ease; ${selectedSkillId === sk.id ? 'background: #EEF1FF;' : ''}">
                      <td style="padding: 14px 18px;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                          <div class="emp-icon-box" style="${selectedSkillId === sk.id ? 'background: var(--emp-primary); color: #FFF;' : ''}">
                            <i data-lucide="${esc(sk.icon)}"></i>
                          </div>
                          <div>
                            <div style="font-weight: 750; color: var(--emp-text-primary); font-size: 14px;">${esc(sk.name)}</div>
                            <div style="font-size: 12px; color: var(--emp-text-muted);">${esc(sk.proficiency)} · ${esc(sk.category)}</div>
                          </div>
                        </div>
                      </td>
                      <td style="padding: 14px 16px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                          <div class="emp-progress-bar" style="width: 72px;">
                            <div class="emp-progress-fill ${sk.status === 'Gap' ? 'emp-progress-fill--warning' : 'emp-progress-fill--success'}" style="width: ${sk.healthScore}%;"></div>
                          </div>
                          <span style="font-weight: 750; font-size: 12px; color: var(--emp-text-primary);">${sk.healthScore}%</span>
                        </div>
                      </td>
                      <td style="padding: 14px 16px;">
                        <span style="font-weight: 700; color: var(--emp-text-primary);">${sk.relevance}%</span>
                      </td>
                      <td style="padding: 14px 16px;">
                        <span style="font-weight: 700; color: var(--emp-success);">${esc(sk.momentum)}</span>
                      </td>
                      <td style="padding: 14px 18px;">
                        <span class="emp-badge ${sk.status === 'Strong' ? 'emp-badge-success' : 'emp-badge-warning'}">
                          ${sk.status === 'Strong' ? '✓ Aligned' : '! Priority Gap'}
                        </span>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- RIGHT COLUMN: Deep Dive Detail & Contribution Hooks -->
        <div class="emp-card" style="position: sticky; top: 96px; display: flex; flex-direction: column; gap: 18px; border-color: rgba(39, 53, 245, 0.2);">
          
          <!-- Detail Header -->
          <div style="display: flex; align-items: flex-start; justify-content: space-between; border-bottom: 1px solid var(--emp-border-subtle); padding-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div class="emp-icon-box" style="width: 42px; height: 42px; background: var(--emp-primary); color: #FFFFFF;">
                <i data-lucide="${esc(selectedSkill.icon)}" style="width: 20px; height: 20px;"></i>
              </div>
              <div>
                <span class="emp-eyebrow">SKILL DETAIL</span>
                <h3 style="font-size: 18px; font-weight: 850; color: var(--emp-text-primary); margin: 0;">${esc(selectedSkill.name)}</h3>
                <small style="color: var(--emp-text-muted); font-size: 12px;">${esc(selectedSkill.category)}</small>
              </div>
            </div>
            <span class="emp-badge ${selectedSkill.status === 'Strong' ? 'emp-badge-success' : 'emp-badge-warning'}">
              ${esc(selectedSkill.status)}
            </span>
          </div>

          <!-- Description -->
          <p style="font-size: 13px; color: var(--emp-text-secondary); line-height: 1.5; margin: 0;">
            ${esc(selectedSkill.description)}
          </p>

          <!-- 4 Stats in 2x2 Grid -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div style="background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 12px; padding: 12px;">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Health Score</span>
              <div style="font-size: 20px; font-weight: 850; color: var(--emp-primary); margin-top: 2px;">
                ${selectedSkill.healthScore} <small style="font-size: 11px; font-weight: 600; color: var(--emp-text-muted);">/ 100</small>
              </div>
            </div>
            <div style="background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 12px; padding: 12px;">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Relevance</span>
              <div style="font-size: 20px; font-weight: 850; color: var(--emp-text-primary); margin-top: 2px;">
                ${selectedSkill.relevance}%
              </div>
            </div>
            <div style="background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 12px; padding: 12px;">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Half-Life</span>
              <div style="font-size: 16px; font-weight: 800; color: var(--emp-text-primary); margin-top: 4px;">
                ${esc(selectedSkill.halfLife)}
              </div>
            </div>
            <div style="background: var(--emp-soft); border: 1px solid var(--emp-border-subtle); border-radius: 12px; padding: 12px;">
              <span style="font-size: 11px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Momentum</span>
              <div style="font-size: 15px; font-weight: 800; color: ${matchingTrend && !matchingTrend.is_trend_ready ? 'var(--emp-text-muted)' : 'var(--emp-success)'}; margin-top: 4px;">
                ${matchingTrend
                  ? (matchingTrend.is_trend_ready ? esc(matchingTrend.trend_label) : 'Insufficient Data')
                  : esc(selectedSkill.momentum)}
              </div>
              ${matchingTrend?.signal_badge ? `<div style="font-size: 10px; color: var(--emp-text-muted); margin-top: 2px;">${esc(matchingTrend.signal_badge)}</div>` : ''}
            </div>
          </div>

          <!-- Trend Chart -->
          <div style="background: #FFFFFF; border: 1px solid var(--emp-border); border-radius: 12px; padding: 14px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
              <span style="font-size: 11.5px; font-weight: 750; color: var(--emp-text-muted); text-transform: uppercase;">Momentum Trend</span>
              <span style="font-size: 12px; font-weight: 700; color: ${matchingTrend && matchingTrend.is_trend_ready ? 'var(--emp-success)' : 'var(--emp-text-muted)'};">
                ${matchingTrend ? (matchingTrend.is_trend_ready ? esc(matchingTrend.trend_label) : 'Insufficient Data') : esc(selectedSkill.momentum)}
              </span>
            </div>
            ${matchingTrend && matchingTrend.is_trend_ready && matchingTrend.historical_series?.length > 1
              ? sparklineSVG(matchingTrend.historical_series.map(pt => pt.value || 0), false)
              : matchingTrend
                ? `<div style="padding: 10px; background: var(--emp-soft); border-radius: 8px; font-size: 11.5px; color: var(--emp-text-secondary); line-height: 1.4;">
                     <strong>Single Observed Period (${matchingTrend.consecutive_periods || 1} period)</strong><br>
                     Multi-period trend requires consecutive historical periods. Forecast ready: <code>false</code>.
                   </div>`
                : sparklineSVG(selectedSkill.trend, selectedSkill.status === 'Gap')
            }
          </div>

          <!-- Evidence & Alignment -->
          <div style="background: var(--emp-soft); border-radius: 12px; padding: 14px; font-size: 12.5px; line-height: 1.45; border: 1px solid var(--emp-border-subtle);">
            <div style="font-weight: 750; color: var(--emp-primary); margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
              <span style="display: flex; align-items: center; gap: 6px;">
                <i data-lucide="shield-check"></i>
                Target Requirement Alignment
              </span>
              ${liveIntelligence?.raw?.answer?.contextual_focus ? `
                <span class="emp-badge emp-badge-primary" style="font-size: 10px;">${esc(liveIntelligence.raw.answer.contextual_focus)}</span>
              ` : ''}
            </div>
            <div style="color: var(--emp-text-secondary);">
              ${esc(selectedSkill.roleRequirement)} · ${esc(selectedSkill.gap)}
            </div>
            ${liveIntelligence?.raw?.answer ? `
              <div style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--emp-border-subtle);">
                <div style="font-weight: 750; color: var(--emp-text-primary); font-size: 12.5px; margin-bottom: 2px;">
                  ${esc(liveIntelligence.raw.answer.headline)}
                </div>
                <div style="color: var(--emp-text-secondary); font-size: 12px; line-height: 1.4;">
                  ${esc(liveIntelligence.raw.answer.summary)}
                </div>
                ${liveIntelligence.raw.answer.key_insights?.length ? `
                  <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 11px; color: var(--emp-text-muted);">
                    ${liveIntelligence.raw.answer.key_insights.map(ki => `<li>${esc(ki)}</li>`).join('')}
                  </ul>
                ` : ''}
                ${liveIntelligence.raw.answer.limitations?.length ? `
                  <div style="font-size: 10.5px; color: var(--emp-text-muted); margin-top: 4px;">
                    <strong>Limitations:</strong> ${liveIntelligence.raw.answer.limitations.map(l => esc(l)).join(' ')}
                  </div>
                ` : ''}
              </div>
            ` : ''}
            <div style="font-size: 11px; color: var(--emp-text-muted); margin-top: 6px;">
              Evidence: <strong>${liveIntelligence?.raw?.calculation_record_id ? `Core Intelligence (#${liveIntelligence.raw.calculation_record_id.slice(-8)})` : esc(selectedSkill.evidenceBadge || selectedSkill.verifiedDate)}</strong>
              ${liveIntelligence?.sources_used?.length ? ` · Sources: ${liveIntelligence.sources_used.join(', ')}` : ''}
            </div>
          </div>

          <!-- G2.5 Recommended Action Block -->
          ${empAction ? `
            <div style="background: #FFFFFF; border: 1px solid var(--emp-border); border-left: 4px solid var(--emp-primary); border-radius: 12px; padding: 14px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 800; color: var(--emp-primary); text-transform: uppercase;">04 — RECOMMENDED NEXT ACTION</span>
                <span class="emp-badge ${empAction.priority === 'high' ? 'emp-badge-warning' : 'emp-badge-primary'}" style="font-size: 10px; font-weight: 700;">Priority: ${esc(empAction.priority)}</span>
              </div>
              <div style="font-size: 13.5px; font-weight: 750; color: var(--emp-text-primary); margin-bottom: 4px;">
                ${esc(empAction.title)}
              </div>
              <p style="font-size: 12px; color: var(--emp-text-secondary); line-height: 1.45; margin: 0 0 8px 0;">
                ${esc(empAction.recommended_action)}
              </p>
              <div style="font-size: 11.5px; color: var(--emp-text-muted); line-height: 1.4; background: var(--emp-soft); padding: 8px 10px; border-radius: 6px; margin-bottom: 8px;">
                <strong>Why this action:</strong> ${esc(empAction.why_it_matters)}
              </div>
              ${empAction.limitations?.length ? `
                <div style="font-size: 10.5px; color: var(--emp-text-muted);">
                  <strong>Limitation:</strong> ${esc(empAction.limitations[0])}
                </div>
              ` : ''}
            </div>
          ` : ''}

          <!-- Action Box: Dual Path (If Gap: Learn & Assess. If Strong: Contribute & Mentor) -->
          <div style="border-top: 1px solid var(--emp-border-subtle); padding-top: 14px; display: flex; flex-direction: column; gap: 10px;">
            ${selectedSkill.mentorEligible ? `
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span class="emp-badge emp-badge-primary"><i data-lucide="award"></i> Mentor Eligible</span>
                <span style="font-size: 12px; color: var(--emp-text-muted);">${selectedSkill.questionsAuthoredCount || 0} questions authored</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button type="button" class="emp-btn-primary emp-btn-sm" id="btnSkillCreateQuestion" data-skill="${esc(selectedSkill.name)}">
                  <i data-lucide="file-question"></i>
                  <span>Add Question</span>
                </button>
                <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnSkillHostMock" data-skill="${esc(selectedSkill.name)}">
                  <i data-lucide="video"></i>
                  <span>Host Mock</span>
                </button>
              </div>
            ` : `
              <div style="display: flex; align-items: center; justify-content: space-between;">
                <span class="emp-badge emp-badge-warning"><i data-lucide="target"></i> Focus Area</span>
                <span style="font-size: 12px; color: var(--emp-text-muted);">Required for Target Role</span>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <a href="#/employee/growth" class="emp-btn-primary emp-btn-sm">
                  <i data-lucide="book-open"></i>
                  <span>Start Lab</span>
                </a>
                <button type="button" class="emp-btn-secondary emp-btn-sm" id="btnSkillRunAssessment" data-skill="${esc(selectedSkill.name)}">
                  <i data-lucide="award"></i>
                  <span>Take Quiz</span>
                </button>
              </div>
            `}
          </div>

        </div>
      </div>
    </div>
  `;
}

function renderTrendingSkillsWidget(trendingList, loading) {
  if (loading) {
    return `
      <div class="emp-widget-skeleton">
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px;"></div>
      </div>
    `;
  }
  if (!trendingList || !trendingList.length) {
    return `
      <div class="emp-widget-skeleton">
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 54px; border-radius: 12px;"></div>
      </div>
    `;
  }
  return `
    <div class="emp-trending-skills-list">
      ${trendingList.slice(0, 4).map(item => {
        const title = esc(item.skill_name || item.skill || 'Trending Skill');
        const growth = item.growth_pct != null
          ? `${item.growth_pct > 0 ? '+' : ''}${Math.round(item.growth_pct * 10) / 10}%`
          : (item.trend || '+18.4%');
        const score = item.composite_score ? Math.round(item.composite_score) : 85;
        return `
          <div class="emp-trending-skill-card">
            <div class="emp-trending-skill-info">
              <strong class="emp-trending-skill-name">${title}</strong>
              <div class="emp-trending-skill-meta">
                <span class="emp-badge emp-badge-success" style="font-size: 10.5px; padding: 2px 7px;">
                  <i data-lucide="trending-up"></i> ${esc(growth)}
                </span>
                <span class="emp-trending-score">Score: <strong>${score}/100</strong></span>
              </div>
            </div>
            <button type="button" class="emp-btn-ghost emp-btn-sm" data-add-trending-skill="${title}" title="Add ${title} to your skills">
              <i data-lucide="plus"></i>
              <span>Add</span>
            </button>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderMatchingRolesWidget(rolesList, loading) {
  if (loading) {
    return `
      <div class="emp-widget-skeleton">
        <div class="emp-skeleton-shimmer" style="height: 96px; border-radius: 14px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 96px; border-radius: 14px;"></div>
      </div>
    `;
  }
  if (!rolesList || !rolesList.length) {
    return `
      <div class="emp-widget-skeleton">
        <div class="emp-skeleton-shimmer" style="height: 96px; border-radius: 14px; margin-bottom: 10px;"></div>
        <div class="emp-skeleton-shimmer" style="height: 96px; border-radius: 14px;"></div>
      </div>
    `;
  }
  return `
    <div class="emp-matching-roles-list">
      ${rolesList.slice(0, 3).map(role => {
        const title = esc(role.title || role.name || 'Job Role');
        const demand = role.demand_score || 88;
        const matchPct = role.match_percentage || 80;
        const matched = Array.isArray(role.matched_skills) ? role.matched_skills : [];
        const route = role.roadmap_route || `#/employee/growth?role=${encodeURIComponent(role.id || title)}`;

        return `
          <div class="emp-matching-role-card">
            <div class="emp-role-card-top">
              <div class="emp-role-title-group">
                <strong class="emp-role-card-title">${title}</strong>
                <span class="emp-role-match-pill"><i data-lucide="check-check"></i> ${matchPct}% Match</span>
              </div>
              <span class="emp-role-demand-badge">Demand: <strong>${demand}/100</strong></span>
            </div>

            ${matched.length ? `
              <div class="emp-role-matched-skills">
                <span class="emp-role-matched-label">Matched:</span>
                ${matched.slice(0, 3).map(m => `<span class="emp-role-skill-pill">${esc(m)}</span>`).join('')}
              </div>
            ` : ''}

            <div class="emp-role-card-actions">
              <a href="${route}" class="emp-btn-primary emp-btn-sm" style="flex: 1; text-align: center;">
                <i data-lucide="map"></i>
                <span>View Roadmap</span>
              </a>
              <a href="#/individual/career" class="emp-btn-ghost emp-btn-sm" title="Explore role in Career Intelligence">
                <span>Explore Role</span>
                <i data-lucide="arrow-right"></i>
              </a>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

async function fetchTrendingSkillsApi() {
  if (trendingSkillsCache && trendingSkillsCache.length) return trendingSkillsCache;
  trendingSkillsLoading = true;
  const urls = [
    `${API_BASE_URL}/api/v1/skills/top-trending?limit=4`,
    `${API_BASE_URL}/api/skills/top-trending?limit=4`,
    `http://127.0.0.1:8000/api/v1/skills/top-trending?limit=4`
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          trendingSkillsCache = data;
          trendingSkillsLoading = false;
          return data;
        }
      }
    } catch {
      // try next
    }
  }
  trendingSkillsLoading = false;
  return [];
}

async function fetchMatchingRolesApi(skills = []) {
  if (matchingRolesCache && matchingRolesCache.length) return matchingRolesCache;
  matchingRolesLoading = true;
  const payload = {
    skills: skills.map(s => typeof s === 'string' ? s : s.name),
    limit: 4
  };
  const urls = [
    `${API_BASE_URL}/api/v1/career/recommendations`,
    `${API_BASE_URL}/api/v1/career-intelligence/recommendations`,
    `http://127.0.0.1:8000/api/v1/career/recommendations`,
    `http://127.0.0.1:8000/api/v1/career-intelligence/recommendations`
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          matchingRolesCache = data;
          matchingRolesLoading = false;
          return data;
        }
      }
    } catch {
      // try next
    }
  }
  matchingRolesLoading = false;
  return [];
}

function renderSavedEmployeeSkills(profile) {
  if (skillDraftOwnerUid !== profile.id) {
    skillDraftOwnerUid = profile.id;
    skillDraft = null;
    skillSaving = false;
    skillSaveMessage = '';
    skillSaveFailed = false;
    trendingSkillsCache = null;
    matchingRolesCache = null;
  }
  const rawSkills = skillDraft?.skills || getEmployeeCurrentSkills();
  const confidence = skillDraft?.confidence || Object.fromEntries(
    getEmployeeCurrentSkills().filter(skill => skill.confidence).map(skill => [skill.name, skill.confidence])
  );
  const normalizedSkills = rawSkills.map(s => {
    if (typeof s === 'string') return { name: s, confidence: confidence[s] || '' };
    return { name: s.name, confidence: confidence[s.name] || s.confidence || '' };
  });

  const levels = ['', 'Beginner', 'Comfortable', 'Advanced', 'Expert'];

  return `
    <div class="employee-page emp-skills-hub-page">
      <!-- 1. Header / Hero -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow"><i data-lucide="sparkles"></i> CAREER & SKILLS INTELLIGENCE HUB</span>
          <h1 class="emp-hero-title">My Skills & Career Alignment</h1>
          <p class="emp-hero-desc">Manage your self-reported competencies, discover surging market trends, and explore live career opportunities aligned with your capabilities.</p>
        </div>
        <div class="emp-hero-actions">
          <a href="#/employee/profile" class="emp-btn-ghost"><i data-lucide="user"></i><span>View Profile</span></a>
          <a href="#/employee/growth" class="emp-btn-secondary"><i data-lucide="trending-up"></i><span>Growth Console</span></a>
        </div>
      </section>

      <!-- 2. Responsive 2-Column Grid -->
      <div class="emp-skills-layout">
        <!-- Main Column: My Skills -->
        <div class="emp-skills-main-column">
          <section class="emp-card emp-my-skills-card" aria-labelledby="employee-skills-heading">
            <div class="emp-card-header" style="margin-bottom: 16px;">
              <div>
                <span class="emp-badge emp-badge-primary"><i data-lucide="layers-3"></i> Verified & Stated Competencies</span>
                <h2 class="emp-card-title" id="employee-skills-heading" style="margin-top: 6px; font-size: 19px;">Skills you use at work</h2>
                <p class="emp-card-subtitle">Self-reported skill confidence ratings guide role-fit matching and personalized roadmaps.</p>
              </div>
              <span class="emp-badge emp-badge-neutral">${normalizedSkills.length} skills declared</span>
            </div>

            <!-- Modern Action Bar -->
            <div class="emp-skills-action-bar">
              <div class="emp-skill-add-group">
                <div class="emp-skill-input-box">
                  <i data-lucide="plus" class="emp-input-icon"></i>
                  <label for="employeeSkillInput" class="emp-sr-only">Add a skill</label>
                  <input id="employeeSkillInput" class="emp-skill-text-input" type="text" placeholder="Add a skill (e.g., Docker, GraphQL, Kubernetes)..." maxlength="120" autocomplete="off" />
                </div>
                <button type="button" class="emp-btn-secondary" id="addEmployeeSkill">
                  <i data-lucide="plus"></i>
                  <span>Add skill</span>
                </button>
              </div>
              <button type="button" class="emp-btn-primary" id="saveEmployeeSkills" ${skillSaving ? 'disabled' : ''}>
                <i data-lucide="${skillSaving ? 'loader-2' : 'save'}"></i>
                <span>${skillSaving ? 'Saving…' : 'Save skills'}</span>
              </button>
            </div>

            <p id="employeeSkillsSaveStatus" class="emp-save-status ${skillSaveFailed ? 'emp-save-status--error' : ''}" role="${skillSaveFailed ? 'alert' : 'status'}" aria-live="polite">${esc(skillSaveMessage)}</p>

            <!-- Upgraded Skills Grid / Cards -->
            ${normalizedSkills.length ? `
              <div class="emp-skills-cards-grid">
                ${normalizedSkills.map(skill => {
                  const currentConf = confidence[skill.name] || skill.confidence || '';
                  const levelMeta = {
                    'Expert': { pct: 100, class: 'emp-conf--expert', color: '#7C3AED' },
                    'Advanced': { pct: 80, class: 'emp-conf--advanced', color: '#10B981' },
                    'Comfortable': { pct: 55, class: 'emp-conf--comfortable', color: '#2735F5' },
                    'Beginner': { pct: 30, class: 'emp-conf--beginner', color: '#F59E0B' },
                    '': { pct: 10, class: 'emp-conf--unrated', color: '#9CA3AF' }
                  }[currentConf] || { pct: 10, class: 'emp-conf--unrated', color: '#9CA3AF' };

                  return `
                    <div class="emp-skill-item-card">
                      <div class="emp-skill-item-top">
                        <div class="emp-skill-name-group">
                          <div class="emp-skill-icon-badge"><i data-lucide="code-2"></i></div>
                          <strong class="emp-skill-name">${esc(skill.name)}</strong>
                        </div>
                        <button type="button" class="emp-skill-del-btn" data-remove-employee-skill="${esc(skill.name)}" aria-label="Remove ${esc(skill.name)}" title="Remove ${esc(skill.name)}">
                          <i data-lucide="trash-2"></i>
                        </button>
                      </div>

                      <div class="emp-skill-confidence-section">
                        <div class="emp-confidence-header">
                          <span class="emp-confidence-caption">Self-reported confidence:</span>
                          <strong class="emp-confidence-label ${levelMeta.class}">${esc(currentConf || 'Not rated')}</strong>
                        </div>

                        <div class="emp-progress-bar" style="height: 6px; margin: 6px 0 10px;">
                          <div class="emp-progress-fill" style="width: ${levelMeta.pct}%; background: ${levelMeta.color};"></div>
                        </div>

                        <div class="emp-confidence-pills-row" data-skill="${esc(skill.name)}">
                          ${['Beginner', 'Comfortable', 'Advanced', 'Expert'].map(level => {
                            const isActive = currentConf === level;
                            return `
                              <button type="button" 
                                class="emp-conf-pill ${isActive ? `is-active emp-conf-pill--${level.toLowerCase()}` : ''}" 
                                data-set-skill-confidence="${esc(skill.name)}" 
                                data-confidence-level="${esc(level)}">
                                ${esc(level)}
                              </button>
                            `;
                          }).join('')}
                        </div>

                        <label class="emp-sr-only" for="select-conf-${esc(skill.name)}">Self-reported confidence for ${esc(skill.name)}</label>
                        <select id="select-conf-${esc(skill.name)}" data-skill-confidence="${esc(skill.name)}" class="emp-sr-only">
                          ${levels.map(level => `<option value="${esc(level)}" ${currentConf === level ? 'selected' : ''}>${esc(level || 'Not rated')}</option>`).join('')}
                        </select>
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            ` : '<p role="status" class="emp-empty-status">No skills have been added yet. Add the skills you currently use at work.</p>'}
          </section>
        </div>

        <!-- Sidebar Column: Intelligence Widgets -->
        <div class="emp-skills-sidebar-column">
          <!-- Widget 1: Trending Market Skills -->
          <section class="emp-card emp-widget-card" id="trendingSkillsWidget">
            <div class="emp-card-header" style="margin-bottom: 14px;">
              <div>
                <span class="emp-badge emp-badge-primary"><i data-lucide="trending-up"></i> Market Telemetry</span>
                <h3 class="emp-card-title" style="margin-top: 4px; font-size: 16px;">Trending Skills to Build</h3>
                <p class="emp-card-subtitle">Tri-Signal high-momentum market demands</p>
              </div>
              <span class="emp-badge emp-badge-success" style="font-size: 10.5px;">Live</span>
            </div>

            <div id="trendingSkillsList">
              ${renderTrendingSkillsWidget(trendingSkillsCache, trendingSkillsLoading)}
            </div>
          </section>

          <!-- Widget 2: Roles Matching Your Skills -->
          <section class="emp-card emp-widget-card" id="matchingRolesWidget">
            <div class="emp-card-header" style="margin-bottom: 14px;">
              <div>
                <span class="emp-badge emp-badge-warning"><i data-lucide="briefcase"></i> Role Alignment</span>
                <h3 class="emp-card-title" style="margin-top: 4px; font-size: 16px;">Roles Matching Your Skills</h3>
                <p class="emp-card-subtitle">Active opportunities matched to your profile</p>
              </div>
              <span class="emp-badge emp-badge-neutral" style="font-size: 10.5px;">AI Match</span>
            </div>

            <div id="matchingRolesList">
              ${renderMatchingRolesWidget(matchingRolesCache, matchingRolesLoading)}
            </div>
          </section>
        </div>
      </div>
    </div>
  `;
}

let employeeSkillRequestVersion = 0;

export async function loadEmployeeSkillIntelligence(rerender) {
  const currentVersion = ++employeeSkillRequestVersion;
  const p = getEmployeeProfile();
  const isCompany = isCompanyEmployee();
  const selectedSkill = employeeSkillsData.find(s => s.id === selectedSkillId) || employeeSkillsData[0];
  const querySkill = selectedSkill ? selectedSkill.name : 'Python';

  if (lastQueriedSkill === querySkill && liveIntelligence) {
    return;
  }

  intelligenceLoading = true;
  intelligenceError = null;
  lastQueriedSkill = querySkill;

  try {
    const res = await querySkillIntelligence({
      portal_type: 'employee',
      user_id: p.id,
      company_id: isCompany ? (p.companyInitials || p.company) : null,
      company_name: isCompany ? p.company : null,
      current_role: p.role,
      target_role: p.targetRole,
      is_connected: isCompany,
      skills: [querySkill],
      range: '6m'
    });
    if (currentVersion !== employeeSkillRequestVersion) return;
    liveIntelligence = res;
    intelligenceLoading = false;
    if (typeof rerender === 'function') rerender();
  } catch (err) {
    if (currentVersion !== employeeSkillRequestVersion) return;
    console.warn('[Employee MySkills] Failed to fetch skill intelligence:', err);
    intelligenceLoading = false;
    intelligenceError = err.message || 'Failed to fetch skill intelligence';
    if (typeof rerender === 'function') rerender();
  }
}

export function bindEmployeeSkillsEvents(rerender) {
  const profile = getEmployeeProfile();
  if (profile.profileLoaded) {
    bindSavedEmployeeSkillsEvents(profile, rerender);
    return;
  }
  // Row selection
  document.querySelectorAll('[data-select-skill]').forEach(row => {
    row.addEventListener('click', () => {
      selectedSkillId = row.dataset.selectSkill;
      lastQueriedSkill = null;
      rerender();
      loadEmployeeSkillIntelligence(rerender);
    });
  });

  // Initial intelligence fetch
  if (!liveIntelligence && !intelligenceLoading) {
    loadEmployeeSkillIntelligence(rerender);
  }

  function bindSavedEmployeeSkillsEvents(profile, rerender) {
    const ensureDraft = () => {
      if (!skillDraft) {
        const current = getEmployeeCurrentSkills();
        skillDraft = {
          skills: current.map(skill => (typeof skill === 'string' ? skill : skill.name)),
          confidence: Object.fromEntries(
            current.filter(skill => (typeof skill === 'object' ? skill.confidence : ''))
                   .map(skill => [typeof skill === 'string' ? skill : skill.name, typeof skill === 'object' ? skill.confidence : ''])
          )
        };
      }
      return skillDraft;
    };

    document.querySelector('#addEmployeeSkill')?.addEventListener('click', () => {
      const input = document.querySelector('#employeeSkillInput');
      const name = input?.value.trim();
      if (!name) return;
      const draft = ensureDraft();
      if (!draft.skills.some(s => s.toLowerCase() === name.toLowerCase())) {
        draft.skills.push(name);
        draft.confidence[name] = 'Beginner';
      }
      if (input) input.value = '';
      rerender();
    });

    document.querySelector('#employeeSkillInput')?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        document.querySelector('#addEmployeeSkill')?.click();
      }
    });

    document.querySelectorAll('[data-remove-employee-skill]').forEach(button => {
      button.addEventListener('click', () => {
        const draft = ensureDraft();
        const name = button.dataset.removeEmployeeSkill;
        draft.skills = draft.skills.filter(skill => skill !== name);
        delete draft.confidence[name];
        rerender();
      });
    });

    // Handle interactive confidence pill badges
    document.querySelectorAll('[data-set-skill-confidence]').forEach(button => {
      button.addEventListener('click', () => {
        const draft = ensureDraft();
        const skill = button.dataset.setSkillConfidence;
        const level = button.dataset.confidenceLevel;
        if (draft.confidence[skill] === level) {
          delete draft.confidence[skill];
        } else {
          draft.confidence[skill] = level;
        }
        rerender();
      });
    });

    // Handle native select changes (for accessibility & tests)
    document.querySelectorAll('[data-skill-confidence]').forEach(select => {
      select.addEventListener('change', () => {
        const draft = ensureDraft();
        const skill = select.dataset.skillConfidence;
        if (select.value) draft.confidence[skill] = select.value;
        else delete draft.confidence[skill];
        rerender();
      });
    });

    document.querySelector('#saveEmployeeSkills')?.addEventListener('click', async event => {
      if (skillSaving) return;
      skillSaving = true;
      const button = event.currentTarget;
      button.disabled = true;
      const status = document.querySelector('#employeeSkillsSaveStatus');
      skillSaveMessage = 'Saving your skills…';
      skillSaveFailed = false;
      if (status) status.textContent = skillSaveMessage;
      const draft = ensureDraft();
      try {
        await saveRoleOnboardingStep('employee', 4, 'emp_skills', draft.skills);
        const confidenceToSave = Object.fromEntries(
          Object.entries(draft.confidence).filter(([skill]) => draft.skills.includes(skill))
        );
        await saveRoleOnboardingStep('employee', 5, 'emp_skill_confidence', confidenceToSave);
        const updatedProfile = await loadRoleOnboardingProfile('employee');
        setEmployeeOnboardingProfile(profile.id, updatedProfile);
        skillDraft = null;
        skillSaveMessage = 'Your skills have been saved.';
      } catch (error) {
        try {
          const latestProfile = await loadRoleOnboardingProfile('employee');
          setEmployeeOnboardingProfile(profile.id, latestProfile);
        } catch {
          skillSaveMessage = 'Your skills could not be saved, and the latest server profile could not be reloaded.';
        }
        if (skillSaveMessage === 'Saving your skills…') {
          skillSaveMessage = error?.message || 'Your skills could not be saved. Please retry.';
        }
        skillSaveFailed = true;
      } finally {
        skillSaving = false;
        rerender();
      }
    });

    // Async Fetch Trending Skills Widget
    fetchTrendingSkillsApi().then(data => {
      const container = document.querySelector('#trendingSkillsList');
      if (container && data && data.length) {
        container.innerHTML = renderTrendingSkillsWidget(data, false);
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
        container.querySelectorAll('[data-add-trending-skill]').forEach(btn => {
          btn.addEventListener('click', () => {
            const skillName = btn.dataset.addTrendingSkill;
            const draft = ensureDraft();
            if (!draft.skills.some(s => s.toLowerCase() === skillName.toLowerCase())) {
              draft.skills.push(skillName);
              draft.confidence[skillName] = 'Beginner';
              rerender();
            }
          });
        });
      }
    }).catch(() => {});

    // Async Fetch Roles Matching Skills Widget
    const currentSkills = (skillDraft?.skills || getEmployeeCurrentSkills()).map(s => typeof s === 'string' ? s : s.name);
    fetchMatchingRolesApi(currentSkills).then(roles => {
      const container = document.querySelector('#matchingRolesList');
      if (container && roles && roles.length) {
        container.innerHTML = renderMatchingRolesWidget(roles, false);
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      }
    }).catch(() => {});

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  }

  // Category filters
  document.querySelectorAll('[data-category-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeCategory = btn.dataset.categoryFilter;
      rerender();
    });
  });

  // Status filters
  document.querySelectorAll('[data-status-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeStatus = btn.dataset.statusFilter;
      rerender();
    });
  });

  // Request Skill Assessment Modal
  const requestAssessBtn = document.querySelector('#btnRequestSkillAssessment');
  if (requestAssessBtn) {
    requestAssessBtn.addEventListener('click', () => {
      openEmployeeModal({
        title: 'Request Technical Assessment',
        subtitle: 'Validate your competencies to update your health score and unlock mentor eligibility',
        badge: 'Assessment Gateway',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <p>Select which skill category you wish to benchmark against current standards:</p>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <label style="display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; cursor: pointer;">
                <input type="radio" name="skillToAssess" checked style="accent-color: var(--emp-primary);" />
                <div>
                  <strong>CUDA & GPU Optimization</strong>
                  <div style="font-size: 12px; color: var(--emp-text-muted);">20 questions · 35 mins · Kernel memory profiling</div>
                </div>
              </label>
              <label style="display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; cursor: pointer;">
                <input type="radio" name="skillToAssess" style="accent-color: var(--emp-primary);" />
                <div>
                  <strong>Distributed Systems & NCCL</strong>
                  <div style="font-size: 12px; color: var(--emp-text-muted);">15 questions · 30 mins · Interconnect latency & ring reduce</div>
                </div>
              </label>
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Assessment initiated! Opening testing console...'); document.getElementById('empModalCloseBtn').click();">
            <span>Begin Assessment</span>
          </button>
        `
      });
    });
  }

  // Direct action button: Add Question
  const createQBtn = document.querySelector('#btnSkillCreateQuestion');
  if (createQBtn) {
    createQBtn.addEventListener('click', () => {
      const skillName = createQBtn.dataset.skill;
      openEmployeeModal({
        title: `Contribute to ${skillName} Question Bank`,
        subtitle: 'Help peer engineers benchmark their capabilities and earn contributor reputation',
        badge: '+25 Rep Points',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Scenario / Question Concept
              <input type="text" placeholder="e.g. Asynchronous Ring Buffers in high-load inference" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
            </label>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Explanation / Solution Standard
              <textarea rows="3" placeholder="Provide test cases or expected architectural approach..." style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px; resize: vertical;"></textarea>
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Question submitted to Question Bank!'); document.getElementById('empModalCloseBtn').click();">
            <span>Publish Question</span>
          </button>
        `
      });
    });
  }

  // Direct action button: Host Mock
  const hostMockBtn = document.querySelector('#btnSkillHostMock');
  if (hostMockBtn) {
    hostMockBtn.addEventListener('click', () => {
      const skillName = hostMockBtn.dataset.skill;
      openEmployeeModal({
        title: `Host Mock Technical Interview: ${skillName}`,
        subtitle: 'Provide a 45-min peer mock interview slot',
        badge: 'Peer Coaching',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0;">
              Your rating in ${skillName} is <strong>4.9 / 5.0</strong>. Junior engineers frequently request practical architecture reviews.
            </p>
            <label style="display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 650;">
              Session Date
              <input type="date" value="2026-10-02" style="padding: 10px; border: 1px solid var(--emp-border); border-radius: 10px;" />
            </label>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Cancel</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Mock interview slot added to community board!'); document.getElementById('empModalCloseBtn').click();">
            <span>Publish Slot</span>
          </button>
        `
      });
    });
  }

  // Direct action button: Take Quiz
  const runAssessBtn = document.querySelector('#btnSkillRunAssessment');
  if (runAssessBtn) {
    runAssessBtn.addEventListener('click', () => {
      const skillName = runAssessBtn.dataset.skill;
      openEmployeeModal({
        title: `Take ${skillName} Practice Quiz`,
        subtitle: '10 quick questions designed by internal systems architects',
        badge: 'Skill Gap Closer',
        contentHtml: `
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <p style="font-size: 13.5px; color: var(--emp-text-secondary); margin: 0;">
              Score 75% or above to boost your verified skill health score and reduce role evolution gap.
            </p>
            <div style="background: var(--emp-soft); padding: 12px; border-radius: 10px; border: 1px solid var(--emp-border-subtle); font-size: 13px;">
              ⏱ <strong>Duration:</strong> 15 minutes<br>
              🎯 <strong>Format:</strong> Code snippet debugging & multiple-choice
            </div>
          </div>
        `,
        footerHtml: `
          <button type="button" class="emp-btn-ghost" onclick="document.getElementById('empModalCloseBtn').click()">Close</button>
          <button type="button" class="emp-btn-primary" onclick="alert('Starting practice quiz in sandbox...'); document.getElementById('empModalCloseBtn').click();">
            <span>Start Practice Quiz</span>
          </button>
        `
      });
    });
  }
}
