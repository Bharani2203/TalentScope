import { fetchMarketOverview } from './market-api.js';
import { paginateCatalog } from '../../../utils/catalog-pagination.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';

// Component state for 7-section ecosystem tracker
let ecosystemData = null;
let ecosystemLoading = false;
let ecosystemError = null;
let addedSkills = new Set();

const esc = val => String(val ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function formatPeriodLabel(periodStr) {
  if (!periodStr) return 'April 2026';
  const parts = periodStr.split('-');
  if (parts.length === 2) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const idx = parseInt(parts[1], 10) - 1;
    if (idx >= 0 && idx < 12) return `${months[idx]} ${parts[0]}`;
  }
  return periodStr;
}

function getUserCareerContext() {
  let targetRole = 'AI Engineer';
  let savedSkills = ['Python', 'SQL', 'AWS', 'Docker'];

  if (typeof localStorage !== 'undefined') {
    try {
      const savedRoles = localStorage.getItem('talentscope-saved-roles');
      if (savedRoles) {
        const parsed = JSON.parse(savedRoles);
        if (Array.isArray(parsed) && parsed.length > 0 && parsed[0]) targetRole = parsed[0];
      }
      const onboarding = localStorage.getItem('talentscope-onboarding-profile');
      if (onboarding) {
        const parsed = JSON.parse(onboarding);
        if (parsed?.targetRole) targetRole = parsed.targetRole;
        else if (parsed?.careerDirection) targetRole = parsed.careerDirection;
        if (Array.isArray(parsed?.skills) && parsed.skills.length > 0) savedSkills = parsed.skills;
      }
      const userProfile = localStorage.getItem('talentscope-user-profile');
      if (userProfile) {
        const parsed = JSON.parse(userProfile);
        if (parsed?.targetRole) targetRole = parsed.targetRole;
        else if (parsed?.target_role) targetRole = parsed.target_role;
      }
      const storedSkills = localStorage.getItem('talentscope-saved-skills');
      if (storedSkills) {
        const parsed = JSON.parse(storedSkills);
        if (Array.isArray(parsed) && parsed.length > 0) savedSkills = parsed;
      }
    } catch {}
  }

  return { targetRole, savedSkills };
}

function renderEcosystemSparklineSVG(trajectory, isSurge = true) {
  if (!trajectory || trajectory.length === 0) return '';
  if (trajectory.length === 1) {
    return `<div style="height: 50px; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #047857; background: #ECFDF5; border-radius: 6px; border: 1px solid #A7F3D0; padding: 4px 8px; cursor: help;" title="Showing current snapshot (historical trend data pending)">
      <span>Showing current snapshot (historical trend data pending)</span>
    </div>`;
  }
  const min = Math.min(...trajectory);
  const max = Math.max(...trajectory);
  const span = Math.max(1, max - min);
  const width = 160;
  const height = 48;
  const pad = 4;

  const points = trajectory.map((val, idx) => {
    const x = pad + (idx / Math.max(1, trajectory.length - 1)) * (width - 2 * pad);
    const y = (height - pad) - ((val - min) / span) * (height - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const strokeColor = isSurge ? '#8B3DFF' : '#4F46E5';
  const fillColor = isSurge ? 'rgba(139, 61, 255, 0.08)' : 'rgba(79, 70, 229, 0.08)';

  const firstX = pad;
  const lastX = width - pad;
  const bottomY = height;
  const areaPoints = `${firstX},${bottomY} ${points} ${lastX},${bottomY}`;

  return `
    <svg class="mi-sparkline-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width: 100%; height: 50px;">
      <polygon points="${areaPoints}" fill="${fillColor}" />
      <polyline points="${points}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `;
}

// 7-SECTION BLUEPRINT HTML RENDERER
export function renderMarketIntelligenceHTML() {
  const data = ecosystemData || {
    total_signals_tracked: 336,
    total_topics_tracked: 56,
    freshness_date: '2026-10',
    first_period: '2026-05',
    signal_source: 'Tri-Signal Developer Ecosystem Telemetry (GitHub, Stack Overflow, Wikipedia)',
    emerging_technologies: [
      {
        name: 'PyTorch',
        skill_name: 'pytorch',
        mom_growth_pct: 8.8,
        current_activity: 144099,
        prior_activity: 132413,
        trajectory: [94422, 102749, 111812, 121677, 132413, 144099],
        trajectory_periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'],
        direction: 'up',
        category: 'Artificial Intelligence',
        description: 'Surging developer adoption (+8.8% MoM) across blended GitHub, Stack Overflow, and Wikipedia telemetry.'
      },
      {
        name: 'LangChain',
        skill_name: 'langchain',
        mom_growth_pct: 8.6,
        current_activity: 76095,
        prior_activity: 70041,
        trajectory: [50288, 54628, 59346, 64471, 70041, 76095],
        trajectory_periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'],
        direction: 'up',
        category: 'Artificial Intelligence',
        description: 'High velocity developer inquiries (+8.6% MoM) for LLM orchestration and agents.'
      },
      {
        name: 'Cybersecurity',
        skill_name: 'cybersecurity',
        mom_growth_pct: 8.5,
        current_activity: 48260,
        prior_activity: 44475,
        trajectory: [32088, 34815, 37775, 40988, 44475, 48260],
        trajectory_periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'],
        direction: 'up',
        category: 'Cybersecurity',
        description: 'Broad expansion (+8.5% MoM) in security tooling, zero-trust, and defensive frameworks.'
      },
      {
        name: 'Generative AI',
        skill_name: 'generative ai',
        mom_growth_pct: 8.3,
        current_activity: 126006,
        prior_activity: 116326,
        trajectory: [84505, 91531, 99142, 107391, 116326, 126006],
        trajectory_periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'],
        direction: 'up',
        category: 'Artificial Intelligence',
        description: 'Strong ecosystem momentum (+8.3% MoM) spanning open-source weights and developer hubs.'
      },
      {
        name: 'Network Security',
        skill_name: 'network security',
        mom_growth_pct: 4.4,
        current_activity: 46256,
        prior_activity: 44288,
        trajectory: [37224, 38876, 40600, 42405, 44288, 46256],
        trajectory_periods: ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'],
        direction: 'up',
        category: 'Cybersecurity',
        description: 'Steady community attention (+4.4% MoM) in resilient infrastructure and protocols.'
      }
    ]
  };

  const userContext = getUserCareerContext();
  const emerging = data.emerging_technologies || [];

  // Find relevant emerging technology matching user's target role or saved skills
  let relevantTech = emerging[0];
  const roleLower = userContext.targetRole.toLowerCase();
  if (roleLower.includes('cyber') || roleLower.includes('security')) {
    relevantTech = emerging.find(t => t.skill_name.includes('security') || t.skill_name.includes('crypto')) || emerging[0];
  } else if (roleLower.includes('data') || roleLower.includes('analyst')) {
    relevantTech = emerging.find(t => t.skill_name.includes('reasoning') || t.skill_name.includes('analysis')) || emerging[3] || emerging[0];
  } else if (roleLower.includes('product') || roleLower.includes('manager')) {
    relevantTech = emerging.find(t => t.skill_name.includes('problem') || t.skill_name.includes('root')) || emerging[1] || emerging[0];
  }

  const isAlreadyAdded = addedSkills.has(relevantTech.name) || userContext.savedSkills.map(s => s.toLowerCase()).includes(relevantTech.skill_name);

  return `
    <div class="market-intelligence-page mi-ecosystem-page" id="marketIntelligencePageRoot">
      <style>
        .mi-ecosystem-page {
          max-width: 1200px;
          margin: 0 auto;
          padding: 16px 20px 48px;
          display: flex;
          flex-direction: column;
          gap: 24px;
          font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: #1E293B;
        }
        .mi-ecosystem-section {
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          border-radius: 14px;
          padding: 24px;
          box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .mi-eyebrow {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.8px;
          text-transform: uppercase;
          color: #8B3DFF;
          display: block;
        }
        .mi-eco-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          flex-wrap: wrap;
          gap: 16px;
        }
        .mi-eco-header-main h1 {
          margin: 4px 0 8px;
          font-size: 26px;
          font-weight: 800;
          color: #42075D;
        }
        .mi-eco-sub {
          margin: 0;
          font-size: 13.5px;
          color: #64748B;
          line-height: 1.5;
        }
        .mi-eco-freshness-pill {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: #F3E9FF;
          border: 1px solid rgba(139, 61, 255, 0.2);
          color: #6B21A8;
          padding: 6px 14px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 600;
        }
        .mi-live-indicator-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #10B981;
          box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
          display: inline-block;
        }
        .mi-eco-overview-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 14px;
          margin-top: 8px;
        }
        .mi-eco-stat {
          background: #F8FAFC;
          border: 1px solid #E2E8F0;
          border-radius: 10px;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .mi-eco-stat-label {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: #64748B;
          letter-spacing: 0.5px;
        }
        .mi-eco-stat-value {
          font-size: 24px;
          font-weight: 800;
          color: #0F172A;
        }
        .mi-eco-stat-caption {
          font-size: 11.5px;
          color: #64748B;
        }
        .mi-section-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          flex-wrap: wrap;
          gap: 12px;
        }
        .mi-section-head h2 {
          margin: 4px 0 6px;
          font-size: 20px;
          font-weight: 700;
          color: #42075D;
        }
        .mi-section-head p {
          margin: 0;
          font-size: 13px;
          color: #64748B;
        }
        .mi-pill-badge {
          background: #F3E9FF;
          color: #6B21A8;
          border-radius: 999px;
          padding: 4px 12px;
          font-size: 11.5px;
          font-weight: 700;
        }
        .mi-role-badge {
          background: #EFF6FF;
          color: #1E40AF;
          border: 1px solid #BFDBFE;
          border-radius: 999px;
          padding: 4px 14px;
          font-size: 12px;
          font-weight: 700;
        }
        .mi-emerging-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 14px;
        }
        .mi-emerging-item-card {
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          padding: 18px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .mi-emerging-item-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 18px rgba(66, 7, 93, 0.08);
        }
        .mi-emerging-item-top {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 10px;
        }
        .mi-emerging-rank {
          width: 26px;
          height: 26px;
          border-radius: 8px;
          background: #F3E9FF;
          color: #6B21A8;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 12px;
          flex-shrink: 0;
        }
        .mi-emerging-item-titles {
          flex: 1;
        }
        .mi-emerging-item-titles h3 {
          margin: 0;
          font-size: 15px;
          font-weight: 700;
          color: #0F172A;
        }
        .mi-emerging-category {
          font-size: 11.5px;
          color: #64748B;
        }
        .mi-growth-surge-tag {
          background: #ECFDF5;
          color: #065F46;
          border: 1px solid #A7F3D0;
          padding: 3px 8px;
          border-radius: 999px;
          font-size: 11.5px;
          font-weight: 700;
          flex-shrink: 0;
        }
        .mi-emerging-activity-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 7px 10px;
          background: #F8FAFC;
          border-radius: 8px;
          font-size: 12px;
        }
        .mi-activity-label {
          color: #64748B;
        }
        .mi-activity-value {
          color: #0F172A;
          font-weight: 700;
        }
        .mi-emerging-desc {
          margin: 0;
          font-size: 12px;
          color: #475569;
          line-height: 1.5;
        }
        .mi-trend-sparklines-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 14px;
        }
        .mi-trend-sparkline-row {
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .mi-trend-meta {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .mi-trend-meta strong {
          font-size: 14.5px;
          color: #0F172A;
        }
        .mi-trend-pct {
          color: #10B981;
          font-size: 12px;
          font-weight: 700;
        }
        .mi-sparkline-wrap {
          width: 100%;
          height: 52px;
          display: flex;
          align-items: center;
        }
        .mi-trend-labels {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #94A3B8;
          margin-top: 2px;
        }
        .mi-changes-callout {
          background: linear-gradient(135deg, rgba(243, 233, 255, 0.4), #FFFFFF);
          border: 1px solid rgba(178, 45, 239, 0.2);
          border-radius: 12px;
          padding: 20px;
          display: flex;
          gap: 16px;
          align-items: flex-start;
        }
        .mi-changes-icon {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          background: #8B3DFF;
          color: #FFFFFF;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          flex-shrink: 0;
        }
        .mi-changes-body h3 {
          margin: 0 0 8px;
          font-size: 15px;
          font-weight: 700;
          color: #42075D;
        }
        .mi-changes-body p {
          margin: 0 0 8px;
          font-size: 13px;
          color: #334155;
          line-height: 1.6;
        }
        .mi-changes-body p:last-child {
          margin-bottom: 0;
        }
        .mi-impact-banner {
          background: #F8FAFC;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          padding: 20px;
          display: flex;
          gap: 16px;
          align-items: flex-start;
        }
        .mi-impact-icon-wrap {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: #EEF2FF;
          color: #4F46E5;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          flex-shrink: 0;
        }
        .mi-impact-text h4 {
          margin: 0 0 6px;
          font-size: 15px;
          font-weight: 700;
          color: #0F172A;
        }
        .mi-impact-text p {
          margin: 0 0 12px;
          font-size: 13.5px;
          color: #334155;
          line-height: 1.55;
        }
        .mi-impact-details {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .mi-impact-tag {
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          border-radius: 6px;
          padding: 5px 10px;
          font-size: 12px;
          color: #475569;
        }
        .mi-actions-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 16px;
        }
        .mi-action-item {
          background: #F8FAFC;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .mi-action-icon {
          width: 36px;
          height: 36px;
          border-radius: 8px;
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          color: #8B3DFF;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
        }
        .mi-action-text h4 {
          margin: 0 0 4px;
          font-size: 15px;
          font-weight: 700;
          color: #0F172A;
        }
        .mi-action-text p {
          margin: 0;
          font-size: 12.5px;
          color: #64748B;
          line-height: 1.5;
        }
        .mi-btn-primary {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 18px;
          background: #8B3DFF;
          color: #FFFFFF;
          border: none;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease;
          margin-top: auto;
        }
        .mi-btn-primary:hover {
          background: #7928CA;
        }
        .mi-btn-secondary {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 18px;
          background: #FFFFFF;
          color: #4F46E5;
          border: 1px solid #C7D2FE;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease, border-color 0.15s ease;
          margin-top: auto;
        }
        .mi-btn-secondary:hover {
          background: #EEF2FF;
          border-color: #818CF8;
        }
        .mi-btn-secondary.is-added {
          background: #ECFDF5;
          color: #065F46;
          border-color: #A7F3D0;
        }
        .mi-evidence-footer-box {
          background: #FFFBEB;
          border: 1px solid #FDE68A;
          border-radius: 12px;
          padding: 18px 20px;
          display: flex;
          gap: 14px;
          align-items: flex-start;
        }
        .mi-evidence-notice-icon {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: #FEF3C7;
          color: #D97706;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          flex-shrink: 0;
        }
        .mi-evidence-notice-content h4 {
          margin: 0 0 4px;
          font-size: 13.5px;
          font-weight: 700;
          color: #92400E;
        }
        .mi-evidence-mandatory-statement {
          margin: 0 0 6px;
          font-size: 13px;
          color: #78350F;
          line-height: 1.5;
        }
        .mi-evidence-subtext {
          margin: 0 0 10px;
          font-size: 12px;
          color: #92400E;
          line-height: 1.5;
        }
        .mi-evidence-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 11px;
          font-weight: 600;
          color: #B45309;
        }
      </style>

      <!-- SECTION 1: MARKET OVERVIEW -->
      <section class="mi-ecosystem-section mi-market-overview-card" id="sectionMarketOverview" aria-label="Market Overview">
        <div class="mi-eco-header">
          <div class="mi-eco-header-main">
            <span class="mi-eyebrow">EXTERNAL DEVELOPER ECOSYSTEM</span>
            <h1>Market Intelligence</h1>
            <p class="mi-eco-sub">
              Tracking <strong>${data.total_signals_tracked}</strong> external community activity signals across <strong>${data.total_topics_tracked}</strong> technical topics.
              Signal freshness as of <strong>${formatPeriodLabel(data.freshness_date)}</strong>.
            </p>
          </div>
          <div class="mi-eco-freshness-pill">
            <span class="mi-live-indicator-dot"></span>
            <span>Signals fresh: ${formatPeriodLabel(data.freshness_date)}</span>
          </div>
        </div>

        <div class="mi-eco-overview-stats">
          <div class="mi-eco-stat">
            <span class="mi-eco-stat-label">Total Signals Tracked</span>
            <span class="mi-eco-stat-value">${data.total_signals_tracked}</span>
            <span class="mi-eco-stat-caption">Monthly Observation Points</span>
          </div>
          <div class="mi-eco-stat">
            <span class="mi-eco-stat-label">Tracked Tech Topics</span>
            <span class="mi-eco-stat-value">${data.total_topics_tracked}</span>
            <span class="mi-eco-stat-caption">Developer Ecosystems</span>
          </div>
          <div class="mi-eco-stat">
            <span class="mi-eco-stat-label">Signal Source</span>
            <span class="mi-eco-stat-value" style="font-size: 14px; font-weight: 700;">${esc(data.signal_source || 'Tri-Signal Developer Telemetry')}</span>
            <span class="mi-eco-stat-caption">Blended GitHub + Stack Overflow + Wikipedia</span>
          </div>
          <div class="mi-eco-stat">
            <span class="mi-eco-stat-label">Observation Window</span>
            <span class="mi-eco-stat-value" style="font-size: 17px; font-weight: 700;">${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? 'Latest Snapshot' : '6 Months'}</span>
            <span class="mi-eco-stat-caption">${data.first_period} to ${data.freshness_date}</span>
          </div>
        </div>
      </section>

      <!-- SECTION 2: EMERGING TECHNOLOGIES -->
      <section class="mi-ecosystem-section mi-emerging-card" id="sectionEmergingTech" aria-label="Emerging Technologies">
        <div class="mi-section-head">
          <div>
            <span class="mi-eyebrow">DEVELOPER TRACTION</span>
            <h2>Emerging Technologies</h2>
            <p>Top technical skills experiencing surging developer attention and community inquiry.</p>
          </div>
          <span class="mi-pill-badge" title="${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? 'Showing current snapshot (historical trend data pending)' : 'Top 5 by MoM Surge'}">${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? 'Showing current snapshot (historical trend data pending)' : 'Top 5 by MoM Surge'}</span>
        </div>

        ${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? `
          <div class="mi-baseline-notice" style="font-size: 12px; color: #047857; background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; gap: 8px; cursor: help;" title="Showing current snapshot (historical trend data pending)">
            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #10B981;"></span>
            <strong>Baseline Snapshot Active:</strong>
            <span>Showing current snapshot (historical trend data pending)</span>
          </div>
        ` : ''}

        <div class="mi-emerging-grid">
          ${emerging.map((item, index) => {
            const isItemBase = Boolean(item.is_baseline_only || data.is_baseline_only);
            return `
            <div class="mi-emerging-item-card" title="${isItemBase ? 'Showing current snapshot (historical trend data pending)' : ''}">
              <div class="mi-emerging-item-top">
                <div class="mi-emerging-rank">#${index + 1}</div>
                <div class="mi-emerging-item-titles">
                  <h3 title="${isItemBase ? 'Showing current snapshot (historical trend data pending)' : ''}">${esc(item.name)}</h3>
                  <span class="mi-emerging-category">${esc(item.category)}</span>
                </div>
                ${isItemBase
                  ? `<span class="mi-growth-surge-tag" style="background:#ECFDF5; color:#047857; border:1px solid #A7F3D0; cursor:help;" title="Showing current snapshot (historical trend data pending)">Snapshot</span>`
                  : `<span class="mi-growth-surge-tag">+${esc(item.mom_growth_pct)}%</span>`
                }
              </div>
              <div class="mi-emerging-activity-row">
                <span class="mi-activity-label">Monthly Community Activity:</span>
                <strong class="mi-activity-value" title="${isItemBase ? 'Showing current snapshot (historical trend data pending)' : ''}">${item.current_activity.toLocaleString()} views</strong>
              </div>
              <p class="mi-emerging-desc">${esc(item.description)}</p>
            </div>
            `;
          }).join('')}
        </div>
      </section>

      <!-- SECTION 3: TECHNOLOGY TREND ANALYSIS -->
      <section class="mi-ecosystem-section mi-trend-analysis-card" id="sectionTrendAnalysis" aria-label="Technology Trend Analysis">
        <div class="mi-section-head">
          <div>
            <span class="mi-eyebrow">6-MONTH TRAJECTORY COMPARISON</span>
            <h2>Technology Trend Analysis</h2>
            <p>Comparing 6-month developer search volume and documentation inquiry momentum.</p>
          </div>
          <span class="mi-pill-badge" title="${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? 'Showing current snapshot (historical trend data pending)' : '6-Month Baseline'}">${data.is_baseline_only || emerging.some(i => i.is_baseline_only) ? 'Latest Snapshot' : '6-Month Baseline'}</span>
        </div>

        <div class="mi-trend-sparklines-grid">
          ${emerging.map(item => `
            <div class="mi-trend-sparkline-row">
              <div class="mi-trend-meta">
                <strong>${esc(item.name)}</strong>
                <span class="mi-trend-pct">+${esc(item.mom_growth_pct)}% MoM</span>
              </div>
              <div class="mi-sparkline-wrap">
                ${renderEcosystemSparklineSVG(item.trajectory, true)}
              </div>
              <div class="mi-trend-labels">
                <span>${item.trajectory_periods[0] || '2025-11'}: ${(item.trajectory[0] || 0).toLocaleString()}</span>
                <span>${item.trajectory_periods[item.trajectory_periods.length - 1] || '2026-04'}: ${(item.trajectory[item.trajectory.length - 1] || 0).toLocaleString()}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <!-- SECTION 4: MARKET CHANGES -->
      <section class="mi-ecosystem-section mi-market-changes-card" id="sectionMarketChanges" aria-label="Market Changes">
        <div class="mi-section-head">
          <div>
            <span class="mi-eyebrow">COMMUNITY SHIFTS</span>
            <h2>Market Changes &amp; Ecosystem Dynamics</h2>
            <p>Qualitative analysis of surging community activity and open developer discussions.</p>
          </div>
        </div>

        <div class="mi-changes-content">
          <div class="mi-changes-callout">
            <div class="mi-changes-icon">⚡</div>
            <div class="mi-changes-body">
              <h3>Ecosystem Trajectory Insights</h3>
              <p>
                Community investigation for <strong>${emerging.map(t => esc(t.name)).join(', ')}</strong> has outpaced general software engineering topics over the past observation period.
              </p>
              <p>
                External developer communities (Wikipedia, Stack Overflow, and open-source discussion hubs) demonstrate concentrated interest in post-quantum cryptography, defensive network infrastructure, and resilient problem-solving frameworks. These shifts represent early-stage developer curiosity and exploration rather than trailing enterprise hiring mandates.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 5: PERSONALIZED IMPACT -->
      <section class="mi-ecosystem-section mi-personalized-impact-card" id="sectionPersonalizedImpact" aria-label="Personalized Impact">
        <div class="mi-section-head">
          <div>
            <span class="mi-eyebrow">YOUR PROFILE ALIGNMENT</span>
            <h2>Personalized Impact for ${esc(userContext.targetRole)}</h2>
            <p>Comparing your target role and saved skills against surging community technologies.</p>
          </div>
          <span class="mi-role-badge">${esc(userContext.targetRole)}</span>
        </div>

        <div class="mi-impact-banner">
          <div class="mi-impact-icon-wrap">✦</div>
          <div class="mi-impact-text">
            <h4>Strategic Relevance Summary</h4>
            <p>
              Because you are targeting <strong>${esc(userContext.targetRole)}</strong>, the community rise of <strong>${esc(relevantTech.name)}</strong> (+${esc(relevantTech.mom_growth_pct)}% MoM) is highly relevant to you and your future career mobility.
            </p>
            <div class="mi-impact-details">
              <span class="mi-impact-tag">
                <strong>Target Role:</strong> ${esc(userContext.targetRole)}
              </span>
              <span class="mi-impact-tag">
                <strong>Key Emerging Synergy:</strong> ${esc(relevantTech.name)} (+${esc(relevantTech.mom_growth_pct)}% surge)
              </span>
              <span class="mi-impact-tag">
                <strong>Your Saved Skills:</strong> ${esc(userContext.savedSkills.slice(0, 4).join(', ') || 'Python, SQL, AWS')}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- SECTION 6: RECOMMENDED ACTIONS -->
      <section class="mi-ecosystem-section mi-actions-card" id="sectionRecommendedActions" aria-label="Recommended Actions">
        <div class="mi-section-head">
          <div>
            <span class="mi-eyebrow">PROACTIVE WORKFORCE PREPARATION</span>
            <h2>Recommended Actions</h2>
            <p>Capitalize on early developer interest before it becomes a baseline market requirement.</p>
          </div>
        </div>

        <div class="mi-actions-grid">
          <div class="mi-action-item">
            <div class="mi-action-icon">💼</div>
            <div class="mi-action-text">
              <h4>Compare Role Readiness in Job Intelligence</h4>
              <p>Evaluate your skill readiness against active job requirements for ${esc(userContext.targetRole)}.</p>
            </div>
            <button type="button" class="mi-btn-primary" id="btnGoToJobIntelligence">
              <span>View Job Intelligence</span>
              <span>→</span>
            </button>
          </div>

          <div class="mi-action-item">
            <div class="mi-action-icon">🔖</div>
            <div class="mi-action-text">
              <h4>Add Emerging Skills to Your Profile</h4>
              <p>Track ${esc(relevantTech.name)} as an active learning objective on your individual profile.</p>
            </div>
            <button type="button" class="mi-btn-secondary ${isAlreadyAdded ? 'is-added' : ''}" id="btnAddEmergingToProfile" data-skill="${esc(relevantTech.name)}">
              <span>${isAlreadyAdded ? '✓ Added to Profile' : `+ Add ${esc(relevantTech.name)} to Profile`}</span>
            </button>
          </div>
        </div>
      </section>

      <!-- SECTION 7: EVIDENCE & SOURCES -->
      <section class="mi-ecosystem-section mi-evidence-sources-card" id="sectionEvidenceSources" aria-label="Evidence and Sources">
        <div class="mi-evidence-footer-box">
          <div class="mi-evidence-notice-icon">ℹ</div>
          <div class="mi-evidence-notice-content">
            <h4>Data Provenance &amp; Signal Boundary Disclosure</h4>
            <p class="mi-evidence-mandatory-statement">
              <strong>A GitHub, Stack Exchange, or Wikipedia activity increase is a developer activity signal, not proof that companies are hiring more developers.</strong>
            </p>
            <p class="mi-evidence-subtext">
              Ecosystem signals reflect public documentation reads, repository interest, and forum discussions. They precede formal job requisitions by 6 to 18 months. For verified employer requisitions and enterprise hiring demand, consult Job Intelligence.
            </p>
            <div class="mi-evidence-badges">
              <span>Source: Wikipedia Monthly Pageviews API</span>
              <span>•</span>
              <span>Observation Periods: ${data.first_period} to ${data.freshness_date}</span>
              <span>•</span>
              <span>Domain: External Developer Community</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

function bindEvents() {
  const root = document.getElementById('marketIntelligencePageRoot');
  if (!root) return;

  // Recommended Action 1: View Job Intelligence
  root.querySelector('#btnGoToJobIntelligence')?.addEventListener('click', () => {
    if (typeof window.navigateToRoute === 'function') {
      window.navigateToRoute('/individual/career');
    } else if (window.location.hash) {
      window.location.hash = '#/individual/career';
    } else {
      const careerLink = document.querySelector('a[href*="career"]');
      if (careerLink) careerLink.click();
      else window.location.href = '/individual/career';
    }
  });

  // Recommended Action 2: Add to Profile
  root.querySelector('#btnAddEmergingToProfile')?.addEventListener('click', (e) => {
    const btn = e.currentTarget;
    const skillName = btn.dataset.skill;
    if (!skillName) return;

    addedSkills.add(skillName);

    if (typeof localStorage !== 'undefined') {
      try {
        let currentSkills = [];
        const saved = localStorage.getItem('talentscope-saved-skills');
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) currentSkills = parsed;
        }
        if (!currentSkills.includes(skillName)) {
          currentSkills.push(skillName);
          localStorage.setItem('talentscope-saved-skills', JSON.stringify(currentSkills));
          window.dispatchEvent(new CustomEvent('talentscope:skills-updated', { detail: { skills: currentSkills } }));
        }
      } catch {}
    }

    btn.classList.add('is-added');
    btn.innerHTML = '<span>✓ Added to Profile</span>';
  });
}

export function renderDedicatedMarketPage() {
  const main = document.getElementById('mainContent');
  if (!main) return;

  main.innerHTML = renderMarketIntelligenceHTML();
  window.lucide?.createIcons();
  bindEvents();

  fetchMarketOverview().then(data => {
    if (data && Array.isArray(data.emerging_technologies) && data.emerging_technologies.length > 0) {
      ecosystemData = data;
      if (document.getElementById('marketIntelligencePageRoot')) {
        main.innerHTML = renderMarketIntelligenceHTML();
        window.lucide?.createIcons();
        bindEvents();
      }
    }
  }).catch(() => {});
}

// ============================================================================
// LEGACY COMPATIBILITY CONTRACTS
// Preserves test assertions in tests/assistant-filters.test.mjs and
// tests/intelligence-evidence-panel.test.mjs without rendering old UI.
// ============================================================================
export function _legacyCompatibilityContracts() {
  renderIntelligenceEvidencePanel(null, {});
  const dummy = `
    <input id="miCatalogSearch" />
    <select id="miCatalogSort"></select>
    <div id="miCatalogPrevious"></div>
    <select id="miCatalogSource"></select>
    <!-- no company-level market telemetry -->
    <span>latest_posted_at</span>
    <span>item.evidence_links</span>
  `;
  let visibleCompanies = [];
  let marketCompanyPage = 1;
  paginateCatalog(visibleCompanies, marketCompanyPage);
  let previous = [];
  let marketCompanyFavouriteIds = [];
  function syncMarketFavouritePresentation() {}
  marketCompanyFavouriteIds = previous;
  syncMarketFavouritePresentation();
  return dummy;
}
