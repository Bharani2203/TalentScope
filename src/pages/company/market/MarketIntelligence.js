// ============================================================================
// TALENTSCOPE.AI — COMPANY MARKET & TECHNOLOGY INTELLIGENCE
// What is changing outside the company, tech momentum & competitor workforce vectors (#874FFF)
// ============================================================================

import { companyProfile } from '../../../data/company/company-data.js';
import { openCompanyModal } from '../components/CompanyModal.js';
import { queryMarketIntelligence } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let companyMarketData = null;
let companyMarketLoading = false;
let companyMarketError = null;

let companyMarketRequestVersion = 0;

export async function loadCompanyMarketData(rerender) {
  if (companyMarketData || companyMarketLoading) return;
  const currentVersion = ++companyMarketRequestVersion;
  companyMarketLoading = true;
  companyMarketError = null;
  const p = companyProfile;

  try {
    const res = await queryMarketIntelligence({
      portal_type: 'company',
      company_id: p.id,
      company_name: p.name,
      industry: p.industry,
      workforce_headcount: p.globalHeadcount,
      range: '6m'
    });
    if (currentVersion !== companyMarketRequestVersion) return;
    companyMarketData = res;
    companyMarketLoading = false;
    if (typeof rerender === 'function') rerender();
  } catch (err) {
    if (currentVersion !== companyMarketRequestVersion) return;
    console.warn('[Company MarketIntelligence] Failed to load market intelligence:', err);
    companyMarketLoading = false;
    companyMarketError = err.message || 'Failed to load market intelligence';
    if (typeof rerender === 'function') rerender();
  }
}

const marketTrends = [
  {
    title: 'AI Compute & Cluster Infrastructure Demand',
    change: '+24.5%',
    whyItMatters: 'Enterprise clients shifting from general cloud compute to dedicated GPU cluster infrastructure.',
    affectedAreas: ['AI Platform', 'Cloud Infrastructure', 'Autonomous Pods'],
    actionLabel: 'Explore Skills',
    actionRoute: '#/company/skills'
  },
  {
    title: 'Sovereign AI Data Residency Mandates',
    change: '+41.0%',
    whyItMatters: 'Public sector contracts require localized model fine-tuning with zero offshore data egress.',
    affectedAreas: ['Public Sector Solutions', 'Security Architecture'],
    actionLabel: 'Review Hiring',
    actionRoute: '#/company/workforce'
  },
  {
    title: 'Low-Bitwidth Model Quantization (FP4 / FP8)',
    change: '+38.2%',
    whyItMatters: 'Extreme memory efficiency needed to cut cost-per-token in hyperscale customer deployments.',
    affectedAreas: ['Hyperscale Inference', 'Compiler Lab'],
    actionLabel: 'Simulate Moat',
    actionRoute: '#/company/simulation'
  },
  {
    title: 'Standardized LLM Serving Microservices',
    change: '+19.8%',
    whyItMatters: 'Deprecating legacy REST endpoints in favor of containerized Triton gRPC serving pipelines.',
    affectedAreas: ['Core Platform API', 'Inference Services'],
    actionLabel: 'Inspect Mobility',
    actionRoute: '#/company/mobility'
  }
];

const companyTechnologies = [
  {
    name: 'CUDA & Kernel Optimization',
    marketDemand: '↑ 28%',
    companyUsage: 'High (Core Moat)',
    teams: 'Autonomous Compute, Inference',
    impact: 'Critical Advantage',
    action: 'Upskill Bench'
  },
  {
    name: 'TensorRT-LLM',
    marketDemand: '↑ 35%',
    companyUsage: 'High (Scaling)',
    teams: 'Inference Services, Edge',
    impact: 'High Product Value',
    action: 'Expand Usage'
  },
  {
    name: 'Triton Inference Server',
    marketDemand: '↑ 22%',
    companyUsage: 'Medium-High',
    teams: 'Core Platform API, Cloud',
    impact: 'Redeployment Driver',
    action: 'Redeploy Devs'
  },
  {
    name: 'Multi-Node NCCL & InfiniBand',
    marketDemand: '↑ 31%',
    companyUsage: 'High (1024+ GPU Clusters)',
    teams: 'Cloud Infrastructure, NeMo',
    impact: 'Hardware Moat',
    action: 'Hire Specialists'
  },
  {
    name: 'FP4 / FP8 Quantization',
    marketDemand: '↑ 44%',
    companyUsage: 'Emerging (Blackwell Rollout)',
    teams: 'Hyperscale Inference',
    impact: 'Urgent Gap (27%)',
    action: 'Certify Cohort'
  }
];

const competitorSignals = [
  {
    competitor: 'AMD Instinct MI300X',
    vector: 'Aggressive recruiting for CUDA-to-HIP migration engineers and open-source Triton contributors.',
    ourMoat: 'Proprietary CUDA cuDNN/TensorRT optimization delivers 1.8x throughput advantage on Blackwell pods.',
    action: 'Deepen proprietary kernel optimizations in autonomous pods.'
  },
  {
    competitor: 'Cerebras CS-3 Cloud',
    vector: 'Marketing low token latency for real-time speech synthesis to capture mid-market AI accounts.',
    ourMoat: 'TensorRT-LLM enterprise ecosystem ubiquity and standard Kubernetes Triton integrations.',
    action: 'Upskill inference services team on speculative decoding.'
  },
  {
    competitor: 'Microsoft Azure Maia 100',
    vector: 'First-party workload substitution in OpenAI inference clusters to cut hardware capex.',
    ourMoat: 'Co-development of DGX Cloud; full-stack software lock-in across enterprise private datacenters.',
    action: 'Coordinate DGX Cloud engineering pods with Azure cloud teams.'
  }
];

export function renderCompanyMarketIntelligence() {
  const p = companyProfile;

  return `
    <div class="company-page company-market">
      <aside role="note" class="cmp-card" style="margin-bottom:14px;border-color:#D6C79A;background:#FFF9E8;color:#574817">Illustrative market intelligence prototype. Example company, technology and hiring values are not verified market data.</aside>
      ${companyMarketData?.answer ? `
        <div class="cmp-card" style="margin-bottom: 14px; padding: 14px 18px; background: #F8F9FD; border-left: 4px solid var(--cmp-primary, #874FFF); font-size: 13px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <div style="font-weight: 750; color: var(--cmp-primary, #874FFF); display: flex; align-items: center; gap: 6px;">
              <i data-lucide="sparkles"></i>
              <span>${esc(companyMarketData.answer.headline)}</span>
            </div>
            <span class="cmp-badge cmp-badge--primary" style="font-size: 10.5px;">${esc(companyMarketData.answer.contextual_focus || 'Market Ecosystem Intelligence')}</span>
          </div>
          <p style="color: var(--cmp-text-secondary, #475467); margin: 0 0 8px 0; line-height: 1.45;">
            ${esc(companyMarketData.answer.summary)}
          </p>
          ${companyMarketData.answer.key_insights?.length ? `
            <ul style="margin: 0 0 8px 18px; padding: 0; font-size: 12px; color: var(--cmp-text-muted, #667085); line-height: 1.4;">
              ${companyMarketData.answer.key_insights.map(ki => `<li>${esc(ki)}</li>`).join('')}
            </ul>
          ` : ''}
          ${companyMarketData.answer.limitations?.length ? `
            <div style="font-size: 11px; color: var(--cmp-text-muted, #667085); border-top: 1px dashed #D0D5DD; padding-top: 6px;">
              <strong>Data Boundary:</strong> ${companyMarketData.answer.limitations.map(l => esc(l)).join(' ')}
            </div>
          ` : ''}
          ${renderIntelligenceEvidencePanel(companyMarketData, {
            title: 'Company market evidence',
            loading: companyMarketLoading,
            error: companyMarketError
          })}
        </div>
      ` : ''}
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="globe" class="cmp-icon-inline"></i>
              EXTERNAL MARKET INTELLIGENCE
            </span>
            <h1>External Market to Enterprise Talent Impact</h1>
            <p>Understand what is changing outside the company, connect global shifts to talent needs, and safeguard NVIDIA's technology moat.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logoInitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Market Impact Intelligence</span>
              <div class="cmp-hero__context-meta">
                <span><i data-lucide="shield-check"></i> Software Moat: 88%</span>
                <span>·</span>
                <span><i data-lucide="trending-up"></i> External Demand: +24%</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. MARKET & INDUSTRY TRENDS (Section 13: What changed, Why it matters, How it affects us) -->
      <section class="cmp-section">
        <div style="margin-bottom: 14px;">
          <span class="cmp-eyebrow"><i data-lucide="trending-up" class="cmp-icon-inline"></i> EXTERNAL FORCES</span>
          <h2 class="cmp-title">What is Changing in Our Industry?</h2>
          <p class="cmp-subtitle">Major external movements and their direct implications on company engineering teams.</p>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;">
          ${marketTrends.map(t => `
            <div class="cmp-card" style="display: flex; flex-direction: column; justify-content: space-between;">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                  <span class="cmp-badge cmp-badge--accent">${esc(t.change)} Demand Growth</span>
                </div>
                <h3 style="font-size: 15.5px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 8px;">${esc(t.title)}</h3>
                
                <div style="margin-bottom: 10px;">
                  <strong style="font-size: 11px; text-transform: uppercase; color: var(--cmp-text-muted); display: block;">Why it matters:</strong>
                  <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 2px 0 0; line-height: 1.45;">${esc(t.whyItMatters)}</p>
                </div>

                <div style="font-size: 12px; color: var(--cmp-text-muted); margin-bottom: 10px;">
                  <strong>Affected Areas:</strong> <span style="color: var(--cmp-text-primary); font-weight: 600;">${t.affectedAreas.join(', ')}</span>
                </div>
              </div>

              <div style="padding-top: 12px; border-top: 1px solid var(--cmp-border-subtle); display: flex; justify-content: flex-end;">
                <a href="${esc(t.actionRoute)}" class="cmp-btn-secondary" style="height: 30px; padding: 0 12px; font-size: 12px;">
                  <span>${esc(t.actionLabel)}</span>
                  <i data-lucide="arrow-right"></i>
                </a>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- 3. COMPANY TECHNOLOGY INTELLIGENCE (Section 14: Technologies, Demand, Usage, Impact) -->
      <section class="cmp-section">
        <div class="cmp-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
            <div>
              <span class="cmp-eyebrow"><i data-lucide="cpu" class="cmp-icon-inline"></i> TECHNOLOGY RADAR</span>
              <h2 class="cmp-title">Company Technology Intelligence</h2>
              <p class="cmp-subtitle">Current and emerging technologies, market momentum, internal usage, and team impact.</p>
            </div>
            <a href="#/company/skills" class="cmp-btn-primary" style="height: 36px; padding: 0 14px;">
              <i data-lucide="layers"></i>
              <span>Map to Skill Portfolio</span>
            </a>
          </div>

          <!-- Technology Table (Section 30 Spacing) -->
          <div class="cmp-table-container">
            <table class="cmp-table" style="font-size: 13px;">
              <thead>
                <tr>
                  <th>Technology</th>
                  <th>Market Demand</th>
                  <th>Company Usage</th>
                  <th>Relevant Teams</th>
                  <th>Organizational Impact</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${companyTechnologies.map(tech => {
                  const trendMatch = companyMarketData?.trends?.find(t =>
                    (t.skill_name && tech.name.toLowerCase().includes(t.skill_name.toLowerCase())) ||
                    (t.skill_id && tech.name.toLowerCase().includes(t.skill_id.toLowerCase()))
                  );
                  return `
                  <tr>
                    <td>
                      <strong style="color: var(--cmp-text-primary); font-size: 13.5px;">${esc(tech.name)}</strong>
                    </td>
                    <td>
                      <span class="cmp-badge ${trendMatch && !trendMatch.is_trend_ready ? 'cmp-badge--neutral' : 'cmp-badge--success'}" style="font-weight: 800;">
                        ${trendMatch ? (trendMatch.is_trend_ready ? esc(trendMatch.trend_label) : 'Insufficient Data') : esc(tech.marketDemand)}
                      </span>
                      ${trendMatch?.signal_badge ? `<div style="font-size: 10px; color: var(--cmp-text-muted); margin-top: 2px;">${esc(trendMatch.signal_badge)}</div>` : ''}
                    </td>
                    <td>
                      <span style="font-weight: 600; color: var(--cmp-text-primary);">${esc(tech.companyUsage)}</span>
                    </td>
                    <td>
                      <span style="font-size: 12.5px; color: var(--cmp-text-secondary);">${esc(tech.teams)}</span>
                    </td>
                    <td>
                      <span class="cmp-badge ${tech.impact.includes('Critical') ? 'cmp-badge--danger' : tech.impact.includes('Redeployment') ? 'cmp-badge--warning' : 'cmp-badge--accent'}">
                        ${esc(tech.impact)}
                      </span>
                    </td>
                    <td>
                      <button type="button" class="cmp-btn-secondary inspect-tech-btn" data-tech="${esc(tech.name)}" style="height: 28px; padding: 0 10px; font-size: 11.5px;">
                        <span>${esc(tech.action)}</span>
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

      <!-- 4. COMPETITOR WORKFORCE SIGNALS & MOAT DEFENSE -->
      <section class="cmp-section">
        <div class="cmp-card">
          <div style="margin-bottom: 14px;">
            <span class="cmp-eyebrow"><i data-lucide="crosshair" class="cmp-icon-inline"></i> COMPETITOR SIGNALS</span>
            <h2 class="cmp-title">Competitor Moves & Talent Defense</h2>
            <p class="cmp-subtitle">Track competitor talent acquisition vectors, architectural vulnerabilities, and recommended workforce countermeasures.</p>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
            ${competitorSignals.map(c => `
              <div style="background: var(--cmp-very-light); padding: 16px; border-radius: var(--cmp-radius-md); border: 1px solid var(--cmp-border); display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                  <h4 style="font-size: 15px; font-weight: 850; color: var(--cmp-text-primary); margin: 0 0 6px;">${esc(c.competitor)}</h4>
                  
                  <div style="margin-bottom: 8px;">
                    <strong style="font-size: 11px; text-transform: uppercase; color: var(--cmp-danger); display: flex; align-items: center; gap: 4px;">
                      <i data-lucide="user-minus" style="width: 12px; height: 12px;"></i> Talent Poaching Vector:
                    </strong>
                    <p style="font-size: 12.5px; color: var(--cmp-text-secondary); margin: 2px 0 0; line-height: 1.4;">${esc(c.vector)}</p>
                  </div>

                  <div style="margin-bottom: 10px;">
                    <strong style="font-size: 11px; text-transform: uppercase; color: var(--cmp-success); display: flex; align-items: center; gap: 4px;">
                      <i data-lucide="shield-check" style="width: 12px; height: 12px;"></i> NVIDIA Software Moat:
                    </strong>
                    <p style="font-size: 12.5px; color: var(--cmp-text-primary); margin: 2px 0 0; line-height: 1.4;">${esc(c.ourMoat)}</p>
                  </div>
                </div>

                <div style="background: var(--cmp-surface); padding: 10px 12px; border-radius: 8px; border: 1px solid var(--cmp-border-subtle); font-size: 12px; color: var(--cmp-dark); display: flex; align-items: center; gap: 8px;">
                  <i data-lucide="check" style="color: var(--cmp-primary); width: 14px; height: 14px; flex-shrink: 0;"></i>
                  <span><strong>Countermeasure:</strong> ${esc(c.action)}</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </section>
    </div>
  `;
}

export function bindCompanyMarketEvents(rerender) {
  if (!companyMarketData && !companyMarketLoading) {
    loadCompanyMarketData(rerender);
  }

  document.querySelectorAll('.inspect-tech-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const techName = btn.dataset.tech;
      openCompanyModal({
        title: `Technology Strategy: ${techName}`,
        subtitle: 'Enterprise Adoption & Talent Readiness',
        icon: 'cpu',
        maxWidth: '520px',
        contentHtml: `
          <p style="font-size: 13.5px; color: var(--cmp-text-primary); margin: 0 0 12px;">
            To support ongoing <strong>${esc(techName)}</strong> initiatives, our workforce planning engine recommends accelerating internal training through the NVIDIA Deep Learning Institute (DLI) to protect software delivery margins.
          </p>
          <div style="background: var(--cmp-light-primary); padding: 12px; border-radius: 8px; font-size: 12.5px; color: var(--cmp-deep-primary);">
            <strong>Recommended Step:</strong> Review active skill coverage in Skill Intelligence or simulate a +25% market adoption surge in Workforce Simulation.
          </div>
        `,
        cancelText: 'Close',
        confirmText: 'Go to Skill Intelligence',
        confirmIcon: 'arrow-right',
        onConfirm: () => {
          window.location.hash = '#/company/skills';
          return true;
        }
      });
    });
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
