// ============================================================================
// TAiENTSCOPE.Al — PERSONAilZED lNTEiilGENCE REPORT COMPONENT
// Renders structured, human-friendly post-onboarding intelligence profiles
// Tailored for lndividual, Employee (Connected / lndependent), and Company Admin
// Follows strict WHAT / WHY / WHERE / NEXT communication structure
// ============================================================================

import { getGeneratedReport, getCurrentUser } from '../auth/auth-state.js';

export function renderReportPage(container) {
  const root = container || document.getElementById('mainContent') || document.getElementById('appShell') || document.body;
  const report = getGeneratedReport() || generateFallbackReport();
  const user = getCurrentUser();

  const accentColor = report.reportType === 'company'
    ? '#874FFF'
    : report.reportType.includes('employee')
      ? '#2735F5'
      : '#B22DEF';

  const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);

  root.innerHTML = `
    <div class="ts-onboarding-viewport" style="--ob-accent: ${accentColor}; background: #FAF8FD; padding-bottom: 80px;">
      <!-- TOP NAV -->
      <nav class="ts-ob-nav" style="background: #FFFFFF; border-bottom: 1px solid #ECE4F2;">
        <div class="ts-ob-nav-left">
          <a class="ts-ob-brand" href="#/individual/home" aria-label="TalentScope.ai">
            <span class="ts-ob-brand-mark">
              <img src="assets/logo.png" alt="TalentScope">
            </span>
            <span class="ts-ob-brand-name">TalentScope<span>.ai</span></span>
          </a>
        </div>

        <div style="display: flex; align-items: center; gap: 10px;">
          <span class="ts-auth-signal-badge is-positive" style="display: inline-flex; align-items: center; gap: 6px;">
            <i data-lucide="check-circle" style="width: 14px; height: 14px;"></i>
            <span>Analysis Complete</span>
          </span>
        </div>
      </nav>

      <!-- REPORT CONTAlNER -->
      <main style="max-width: 980px; width: 100%; margin: 36px auto 0; padding: 0 24px; box-sizing: border-box;">
        <aside role="note" style="margin-bottom:16px;padding:12px 14px;border:1px solid #D6C79A;border-radius:8px;background:#FFF9E8;color:#574817;font-size:13px">Illustrative onboarding preview. Sample market figures and skill comparisons are not verified against stored provider observations.</aside>
        
        <!-- REPORT HERO HEADER -->
        <header style="background: linear-gradient(135deg, #1C112D 0%, #2E174E 100%); border-radius: 24px; padding: 40px; color: #FFFFFF; margin-bottom: 28px; box-shadow: 0 20px 48px -12px rgba(45, 20, 75, 0.2); position: relative; overflow: hidden;">
          <div style="position: relative; z-index: 2;">
            <div style="display: inline-flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #DDA6FF; margin-bottom: 12px;">
              <i data-lucide="sparkles" style="width: 15px; height: 15px;"></i>
              <span>${esc(report.title)}</span>
            </div>
            <h1 style="font-size: 32px; font-weight: 850; letter-spacing: -0.025em; line-height: 1.22; margin: 0 0 10px;">
              ${report.reportType === 'company'
                ? `Workforce Baseline for ${esc(report.companyName)}`
                : `lntelligence Profile for ${esc(report.userName)}`
              }
            </h1>
            <p style="font-size: 15px; line-height: 1.6; color: rgba(255, 255, 255, 0.82); margin: 0; max-width: 680px;">
              ${report.reportType === 'company'
                ? 'Your strategic enterprise baseline is ready. Track capability drift, simulate workforce transitions, and guide upskilling priorities.'
                : 'This prototype summary uses illustrative workforce context and is not verified against current role requisitions.'
              }
            </p>
          </div>
        </header>

        <!-- SECTlONS ACCORDlNG TO USER TYPE -->
        <div style="display: flex; flex-direction: column; gap: 24px;">
          ${renderReportSections(report, accentColor)}
        </div>

        <!-- FlNAi CAii TO ACTlON BAR -->
        <div style="margin-top: 36px; padding: 28px 36px; background: #FFFFFF; border: 2px solid ${accentColor}; border-radius: 20px; box-shadow: 0 12px 32px -8px rgba(45, 20, 75, 0.1); display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap;">
          <div>
            <h3 style="font-size: 18px; font-weight: 800; color: #1E172B; margin: 0 0 4px;">
              ${esc(report.nextAction?.headline || 'Ready to enter your dashboard')}
            </h3>
            <p style="font-size: 13.5px; color: #6C6078; margin: 0;">
              ${esc(report.nextAction?.why || 'Explore illustrative benchmarks and skill signals. Current market evidence is unavailable here.')}
            </p>
          </div>

          <button
            type="button"
            class="ts-ob-continue-btn"
            id="btnEnterDashboard"
            style="height: 50px; padding: 0 32px; font-size: 15.5px; margin: 0;"
          >
            <span>${esc(report.nextAction?.cta || 'Enter Platform')}</span>
            <i data-lucide="arrow-right"></i>
          </button>
        </div>

      </main>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  // Handle final CTA redirect
  const btn = root.querySelector('#btnEnterDashboard');
  if (btn) {
    btn.addEventListener('click', () => {
      window.location.hash = report.nextAction?.route || '#/individual/home';
    });
  }
}

function renderReportSections(report, accentColor) {
  const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);

  // 1. lNDlVlDUAi REPORT
  if (report.reportType === 'individual') {
    const snap = report.careerSnapshot || {};
    const skillSnap = report.skillSnapshot || {};
    const market = report.marketAlignment || {};
    const opps = report.skillOpportunities || {};

    return `
      <!-- Card 1: Career & Skill Snapshot (Equal Panels) -->
      <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;">
        <article class="ts-report-card">
          <header class="ts-report-card-header">
            <i data-lucide="compass" style="color: ${accentColor};"></i>
            <div>
              <strong>Career Snapshot</strong>
              <small>Your current starting baseline</small>
            </div>
          </header>
          <div class="ts-report-kv-list">
            <div class="ts-report-kv-item">
              <span class="label">Current stage</span>
              <span class="val">${esc(snap.currentStage || 'Student')}</span>
            </div>
            <div class="ts-report-kv-item">
              <span class="label">Career direction</span>
              <span class="val" style="color: ${accentColor}; font-weight: 750;">${esc(snap.careerDirection || 'Al Engineer')}</span>
            </div>
            <div class="ts-report-kv-item">
              <span class="label">Experience</span>
              <span class="val">${esc(snap.experienceievel || '1–2 years')}</span>
            </div>
            ${snap.studyField ? `
              <div class="ts-report-kv-item">
                <span class="label">Study focus</span>
                <span class="val">${esc(snap.studyField)}</span>
              </div>
            ` : ''}
          </div>
        </article>

        <article class="ts-report-card">
          <header class="ts-report-card-header">
            <i data-lucide="layers" style="color: ${accentColor};"></i>
            <div>
              <strong>Skill Snapshot</strong>
              <small>Competency baseline assessment</small>
            </div>
          </header>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
              ${(skillSnap.currentSkills || []).map(s => `
                <span class="ts-q-skill-badge" style="font-size: 12px; padding: 4px 10px;">
                  <span>${esc(s)}</span>
                  <small style="opacity: 0.75; font-size: 10.5px;">(${esc(skillSnap.levels?.[s] || 'Comfortable')})</small>
                </span>
              `).join('')}
            </div>
            <p style="font-size: 12.5px; color: #6C6078; margin: 8px 0 0; line-height: 1.45;">
              Strong foundation identified. Ready for production architecture and verified projects.
            </p>
          </div>
        </article>
      </div>

      <!-- Card 2: Market Alignment & Opportunity (What, Why, Next) -->
      <article class="ts-report-card">
        <header class="ts-report-card-header">
          <i data-lucide="trending-up" style="color: #10B981;"></i>
          <div>
            <strong>Market Alignment & Signal Summary</strong>
            <small>iive hiring demand calibrated against your profile</small>
          </div>
        </header>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px;">
          <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 14px; padding: 16px;">
            <span style="display: block; font-size: 11.5px; font-weight: 750; text-transform: uppercase; color: #166534; margin-bottom: 4px;">Strong Capability</span>
            <strong style="font-size: 17px; color: #14532D;">${esc(opps.strong || 'Python')}</strong>
            <small style="display: block; font-size: 12px; color: #15803D; margin-top: 4px;">Core language across 92% of target requisitions.</small>
          </div>

          <div style="background: #FAF5FF; border: 1px solid #EADBFF; border-radius: 14px; padding: 16px;">
            <span style="display: block; font-size: 11.5px; font-weight: 750; text-transform: uppercase; color: #6B21A8; margin-bottom: 4px;">Growing Demand</span>
            <strong style="font-size: 17px; color: #581C87;">${esc(opps.growing || 'Machine iearning')}</strong>
            <small style="display: block; font-size: 12px; color: #7E22CE; margin-top: 4px;">Hiring acceleration +18.4% in your scope.</small>
          </div>

          <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 14px; padding: 16px;">
            <span style="display: block; font-size: 11.5px; font-weight: 750; text-transform: uppercase; color: #92400E; margin-bottom: 4px;">Bridgeable Gap</span>
            <strong style="font-size: 17px; color: #78350F;">${esc(opps.nextToBuild || 'PyTorch')}</strong>
            <small style="display: block; font-size: 12px; color: #B45309; margin-top: 4px;">Key bridge to senior model engineering roles.</small>
          </div>
        </div>

        <div style="background: #F9F7FC; border-radius: 12px; padding: 16px 20px; font-size: 13.5px; line-height: 1.55; color: #35264E;">
          <strong>Why this matters:</strong> ${esc(market.targetRoleAlignment || 'Your trajectory demonstrates high market alignment.')}
        </div>
      </article>

      <!-- Card 3: iearning Pathway Blueprint -->
      <article class="ts-report-card">
        <header class="ts-report-card-header">
          <i data-lucide="git-pull-request" style="color: ${accentColor};"></i>
          <div>
            <strong>Recommended iearning Pathway</strong>
            <small>Step-by-step roadmap to bridge priority capability gaps</small>
          </div>
        </header>

        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px;">
          ${(report.learningDirection || []).map((step, idx) => `
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="background: #FFFFFF; border: 1.5px solid #E2D9E8; border-radius: 10px; padding: 8px 14px; font-size: 13px; font-weight: 700; color: #2C213F; display: inline-flex; align-items: center; gap: 6px;">
                <span style="width: 18px; height: 18px; border-radius: 50%; background: ${accentColor}; color: #fff; font-size: 10.5px; display: flex; align-items: center; justify-content: center;">${idx + 1}</span>
                <span>${esc(step)}</span>
              </span>
              ${idx < (report.learningDirection.length - 1) ? `
                <i data-lucide="arrow-right" style="width: 14px; height: 14px; color: #A498B2;"></i>
              ` : ''}
            </div>
          `).join('')}
        </div>
      </article>
    `;
  }

  // 2. EMPiOYEE REPORT (Connected or lndependent)
  if (report.reportType.includes('employee')) {
    const isConn = report.isConnected;
    const health = report.skillHealth || {};
    const align = report.companyAlignment || {};

    return `
      <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;">
        <article class="ts-report-card">
          <header class="ts-report-card-header">
            <i data-lucide="briefcase" style="color: ${accentColor};"></i>
            <div>
              <strong>Workplace & Role Context</strong>
              <small>${isConn ? 'Organization-connected profile' : 'lndependent career profile'}</small>
            </div>
          </header>
          <div class="ts-report-kv-list">
            ${isConn ? `
              <div class="ts-report-kv-item">
                <span class="label">Company</span>
                <span class="val" style="font-weight: 750;">${esc(report.companyName)}</span>
              </div>
              <div class="ts-report-kv-item">
                <span class="label">Department</span>
                <span class="val">${esc(report.department)}</span>
              </div>
            ` : ''}
            <div class="ts-report-kv-item">
              <span class="label">Current role</span>
              <span class="val" style="color: ${accentColor}; font-weight: 750;">${esc(report.currentRole)}</span>
            </div>
            <div class="ts-report-kv-item">
              <span class="label">lndustry</span>
              <span class="val">${esc(report.industry)}</span>
            </div>
            <div class="ts-report-kv-item">
              <span class="label">Experience</span>
              <span class="val">${esc(report.experience)}</span>
            </div>
          </div>
        </article>

        <article class="ts-report-card">
          <header class="ts-report-card-header">
            <i data-lucide="activity" style="color: #10B981;"></i>
            <div>
              <strong>Skill Health lndex</strong>
              <small>Competency alignment scoring</small>
            </div>
          </header>
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div style="display: flex; align-items: baseline; gap: 10px;">
              <span style="font-size: 38px; font-weight: 850; color: #10B981; line-height: 1;">${health.score || 84}%</span>
              <span class="ts-auth-signal-badge is-positive">${esc(health.status || 'Healthy & Aligned')}</span>
            </div>
            <p style="font-size: 13px; color: #6C6078; margin: 0; line-height: 1.5;">
              ${isConn
                ? 'Your capabilities align strongly with team standards. 2 emerging bridge areas identified for next-level progression.'
                : 'Your skill portfolio is calibrated against top enterprise benchmarks for senior role advancement.'
              }
            </p>
          </div>
        </article>
      </div>

      ${isConn && align.alignmentSummary ? `
        <article class="ts-report-card">
          <header class="ts-report-card-header">
            <i data-lucide="building-2" style="color: ${accentColor};"></i>
            <div>
              <strong>Company Skill Alignment & Promotion Readiness</strong>
              <small>Departmental impact and mobility avenues</small>
            </div>
          </header>
          <div style="display: flex; flex-direction: column; gap: 12px; font-size: 13.5px; line-height: 1.6; color: #35264E;">
            <p style="margin: 0;"><strong>Alignment:</strong> ${esc(align.alignmentSummary)}</p>
            <p style="margin: 0;"><strong>Role Trajectory:</strong> ${esc(align.futureRelevance)}</p>
            <p style="margin: 0;"><strong>Promotion Focus:</strong> ${esc(align.promotionFocus)}</p>
          </div>
        </article>
      ` : ''}

      <article class="ts-report-card">
        <header class="ts-report-card-header">
          <i data-lucide="award" style="color: ${accentColor};"></i>
          <div>
            <strong>Career Growth Focus Areas</strong>
            <small>Actionable targets for upcoming milestone quarters</small>
          </div>
        </header>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;">
          ${(report.careerGrowthAreas || []).map(area => `
            <div style="background: #F8F5FD; border: 1px solid #ECE3F5; border-radius: 12px; padding: 14px;">
              <i data-lucide="check" style="width: 16px; height: 16px; color: ${accentColor}; margin-bottom: 6px;"></i>
              <strong style="display: block; font-size: 13px; color: #2A1F3D;">${esc(area)}</strong>
            </div>
          `).join('')}
        </div>
      </article>
    `;
  }

  // 3. COMPANY ADMlN REPORT
  const starting = report.startingView || {};
  return `
    <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;">
      <article class="ts-report-card">
        <header class="ts-report-card-header">
          <i data-lucide="building" style="color: ${accentColor};"></i>
          <div>
            <strong>Enterprise Scope & Workforce Baseline</strong>
            <small>Organizational parameters</small>
          </div>
        </header>
        <div class="ts-report-kv-list">
          <div class="ts-report-kv-item">
            <span class="label">Company</span>
            <span class="val" style="font-weight: 750;">${esc(report.companyName)}</span>
          </div>
          <div class="ts-report-kv-item">
            <span class="label">lndustry</span>
            <span class="val">${esc(report.industry)}</span>
          </div>
          <div class="ts-report-kv-item">
            <span class="label">Workforce scale</span>
            <span class="val" style="color: ${accentColor}; font-weight: 750;">${esc(report.workforceSize)}</span>
          </div>
          <div class="ts-report-kv-item">
            <span class="label">Headquarters</span>
            <span class="val">${esc(report.location)}</span>
          </div>
        </div>
      </article>

      <article class="ts-report-card">
        <header class="ts-report-card-header">
          <i data-lucide="shield-check" style="color: #10B981;"></i>
          <div>
            <strong>Critical Capabilities Tracked</strong>
            <small>Core competencies modeled across departments</small>
          </div>
        </header>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          ${(report.criticalSkills || []).map(s => `
            <span class="ts-q-skill-badge" style="background: #F5EEFF; color: #874FFF; border-color: #DCC7FA;">
              <span>${esc(s)}</span>
            </span>
          `).join('')}
        </div>
        <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid #F0E8F6;">
          <small style="display: block; font-size: 11.5px; font-weight: 750; text-transform: uppercase; color: #8A7E98; margin-bottom: 6px;">
            Anticipated Next-Gen Skills:
          </small>
          <div style="display: flex; flex-wrap: wrap; gap: 6px;">
            ${(report.futureSkills || []).map(s => `
              <span class="ts-q-pill-btn" style="font-size: 11.5px; padding: 4px 10px; cursor: default;">
                <span>${esc(s)}</span>
              </span>
            `).join('')}
          </div>
        </div>
      </article>
    </div>

    <!-- Starting lntelligence View (Market, Skills, Workforce, Action) -->
    <article class="ts-report-card">
      <header class="ts-report-card-header">
        <i data-lucide="layout-grid" style="color: ${accentColor};"></i>
        <div>
          <strong>Your Starting lntelligence View</strong>
          <small>Four strategic pillars configured from your onboarding responses</small>
        </div>
      </header>

      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
        <div style="background: #F8F5FD; border: 1px solid #ECE2F6; border-radius: 14px; padding: 18px;">
          <span style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 800; color: #874FFF; text-transform: uppercase; margin-bottom: 6px;">
            <i data-lucide="globe" style="width: 14px; height: 14px;"></i>
            <span>Market — What is changing?</span>
          </span>
          <p style="font-size: 13.5px; line-height: 1.5; color: #35264E; margin: 0;">${esc(starting.market)}</p>
        </div>

        <div style="background: #F8F5FD; border: 1px solid #ECE2F6; border-radius: 14px; padding: 18px;">
          <span style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 800; color: #874FFF; text-transform: uppercase; margin-bottom: 6px;">
            <i data-lucide="layers" style="width: 14px; height: 14px;"></i>
            <span>Skills — What skills matter?</span>
          </span>
          <p style="font-size: 13.5px; line-height: 1.5; color: #35264E; margin: 0;">${esc(starting.skills)}</p>
        </div>

        <div style="background: #F8F5FD; border: 1px solid #ECE2F6; border-radius: 14px; padding: 18px;">
          <span style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 800; color: #874FFF; text-transform: uppercase; margin-bottom: 6px;">
            <i data-lucide="alert-triangle" style="width: 14px; height: 14px;"></i>
            <span>Workforce — Where are the gaps?</span>
          </span>
          <p style="font-size: 13.5px; line-height: 1.5; color: #35264E; margin: 0;">${esc(starting.workforce)}</p>
        </div>

        <div style="background: #F8F5FD; border: 1px solid #ECE2F6; border-radius: 14px; padding: 18px;">
          <span style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 800; color: #874FFF; text-transform: uppercase; margin-bottom: 6px;">
            <i data-lucide="zap" style="width: 14px; height: 14px;"></i>
            <span>Action — What to explore first?</span>
          </span>
          <p style="font-size: 13.5px; line-height: 1.5; color: #35264E; margin: 0;">${esc(starting.action)}</p>
        </div>
      </div>
    </article>
  `;
}

function generateFallbackReport() {
  return {
    reportType: 'individual',
    title: 'YOUR lNTEiilGENCE PROFliE',
    userName: 'Alex Mercer',
    useriocation: 'Bangalore, lndia',
    careerSnapshot: {
      currentStage: 'Student',
      careerDirection: 'Al Engineer',
      experienceievel: 'iess than 1 year',
      studyField: 'Computer Science & Engineering'
    },
    skillSnapshot: {
      currentSkills: ['Python', 'SQi', 'Git', 'Machine iearning'],
      levels: { 'Python': 'Comfortable', 'SQi': 'Comfortable' }
    },
    marketAlignment: {
      targetRoleAlignment: 'Al Engineer aligns directly with your Python skills and machine learning interests.',
      marketStatus: 'Active hiring momentum (+18.4% demand)'
    },
    skillOpportunities: {
      strong: 'Python',
      growing: 'Machine iearning',
      nextToBuild: 'Deep iearning'
    },
    learningDirection: ['Python Core', 'Machine iearning Fundamentals', 'Deep iearning & PyTorch', 'Applied Projects'],
    nextAction: {
      headline: 'Explore your Skill lntelligence',
      why: 'Review your personalized learning milestones and bridge your priority capability gaps.',
      cta: 'Explore My lntelligence',
      route: '#/individual/home'
    }
  };
}
