import { dashboardState, dedicatedJobState, intelligenceExplorerState, roadmapState } from '../../../app/state.js';
import { queryJobIntelligence } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import {
  dedicatedJobRoles,
  jobMarketSignalMix,
  getRolesForScope,
  getRoleJobDetails,
  searchRoles
} from '../../../data/job-data.js';

// Configuration Constants
const LOCATIONS = ['Global', 'India', 'Tamil Nadu', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Remote'];
const RANGES = ['7 Days', '30 Days', '3 Months', '6 Months'];
const CATEGORIES = ['All Categories', 'AI / ML', 'Engineering', 'Data', 'Cloud & DevOps', 'Security', 'Product'];
const EMPLOYMENT_TYPES = ['All Types', 'Full-time', 'Contract', 'Hybrid', 'Remote'];

const TABS = ['Overview', 'Demand Change', 'Role Intelligence', 'Company Hiring', 'Skill Requirements', 'Evidence', 'AI Insight'];
const TAB_ICONS = {
  Overview: 'layout-dashboard',
  'Demand Change': 'chart-no-axes-combined',
  'Role Intelligence': 'layers',
  'Company Hiring': 'building-2',
  'Skill Requirements': 'cpu',
  Evidence: 'file-search',
  'AI Insight': 'sparkles'
};

const esc = val => String(val ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

const clamp = (val, min, max) => Math.min(max, Math.max(min, val));

// Component UI State
let ui = {
  collection: dedicatedJobState?.roleScope || 'My Roles',
  activeTab: dedicatedJobState?.selectedTab || 'Overview',
  searchQuery: '',
  filterOpen: false,
  addModalOpen: false,
  evidenceModalData: null,
  isAnalyzing: false,
  analysisStep: 0,
  hasAnalyzed: true,
  queryText: '',
  location: dashboardState?.market || 'Bangalore',
  timeRange: dashboardState?.timeRange || '30D',
  categoryFilter: 'All Categories',
  typeFilter: 'All Types',
  selectedCompanyContext: dedicatedJobState?.selectedCompanyContext || ['NVIDIA', 'Microsoft'],
  selectedSignalId: null,
  simTick: 0
};

let simTimer = null;

function getSelectedRoleData() {
  const roleName = dedicatedJobState?.selectedRole || dashboardState?.selectedRole || 'AI Engineer';
  return getRoleJobDetails(roleName, ui.location, ui.timeRange, ui.selectedCompanyContext);
}

function getVisibleRoles() {
  let list = getRolesForScope(
    ui.collection,
    dashboardState?.favoriteRoles || [],
    dashboardState?.savedRoles || []
  );

  // Category filter
  if (ui.categoryFilter && ui.categoryFilter !== 'All Categories') {
    list = list.filter(r => r.category === ui.categoryFilter);
  }

  // Search filter
  if (ui.searchQuery) {
    const q = ui.searchQuery.toLowerCase().trim();
    list = list.filter(r =>
      r.name.toLowerCase().includes(q) ||
      r.category.toLowerCase().includes(q) ||
      (r.evolution?.current && r.evolution.current.some(s => s.toLowerCase().includes(q))) ||
      (r.requiredSkills && r.requiredSkills.some(s => s.name.toLowerCase().includes(q)))
    );
  }

  return list;
}

function sparklineSVG(history = [48, 56, 64, 72, 80, 85, 91], isDown = false) {
  const min = Math.min(...history);
  const max = Math.max(...history);
  const span = Math.max(1, max - min);
  const points = history.map((val, idx) => {
    const x = (idx / Math.max(1, history.length - 1) * 72).toFixed(1);
    const y = (26 - (val - min) / span * 22).toFixed(1);
    return `${x},${y}`;
  }).join(' ');

  return `
    <svg class="ji-sparkline-svg ${isDown ? 'is-down' : ''}" viewBox="0 0 72 28" preserveAspectRatio="none">
      <polyline points="${points}" />
    </svg>
  `;
}

function renderMainTrendChart(role) {
  const history = role.history || [48, 56, 64, 72, 80, 85, 91];
  const projection = role.projection || [93, 96, 99];
  const allPoints = [...history, ...projection];

  const width = 640;
  const height = 190;
  const padX = 24;
  const padY = 24;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const minVal = Math.min(30, ...allPoints);
  const maxVal = Math.max(100, ...allPoints);
  const span = Math.max(1, maxVal - minVal);

  const getX = (idx, total) => (padX + (idx / (total - 1)) * plotW).toFixed(1);
  const getY = (val) => (padY + plotH - ((val - minVal) / span) * plotH).toFixed(1);

  // History path
  const histCoords = history.map((val, idx) => ({
    x: getX(idx, allPoints.length),
    y: getY(val),
    val
  }));

  const histPathD = histCoords.reduce((acc, pt, idx) =>
    idx === 0 ? `M ${pt.x},${pt.y}` : `${acc} L ${pt.x},${pt.y}`, ''
  );

  const histAreaD = `${histPathD} L ${histCoords[histCoords.length - 1].x},${padY + plotH} L ${histCoords[0].x},${padY + plotH} Z`;

  // Projection path (dashed)
  const lastHist = histCoords[histCoords.length - 1];
  const projCoords = projection.map((val, idx) => ({
    x: getX(history.length + idx, allPoints.length),
    y: getY(val),
    val
  }));
  const fullProjCoords = [lastHist, ...projCoords];
  const projPathD = fullProjCoords.reduce((acc, pt, idx) =>
    idx === 0 ? `M ${pt.x},${pt.y}` : `${acc} L ${pt.x},${pt.y}`, ''
  );

  const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct (Now)', 'Nov', 'Dec', 'Jan'];

  return `
    <div class="ji-chart-container">
      <svg class="ji-main-chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="jiChartGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#B22DEF" stop-opacity="0.32" />
            <stop offset="65%" stop-color="#8B3DFF" stop-opacity="0.10" />
            <stop offset="100%" stop-color="#8B3DFF" stop-opacity="0.0" />
          </linearGradient>
        </defs>

        <!-- Horizontal Gridlines -->
        <line x1="${padX}" y1="${padY}" x2="${width - padX}" y2="${padY}" class="ji-chart-gridline" />
        <line x1="${padX}" y1="${padY + plotH * 0.5}" x2="${width - padX}" y2="${padY + plotH * 0.5}" class="ji-chart-gridline" />
        <line x1="${padX}" y1="${padY + plotH}" x2="${width - padX}" y2="${padY + plotH}" class="ji-chart-gridline" />

        <!-- Area fill for historical data -->
        <path d="${histAreaD}" fill="url(#jiChartGrad)" />

        <!-- Historical Trend Line -->
        <path d="${histPathD}" fill="none" stroke="#B22DEF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />

        <!-- Forecast Projection Line -->
        <path d="${projPathD}" fill="none" stroke="#B22DEF" stroke-width="2.2" stroke-dasharray="4,4" stroke-opacity="0.75" />

        <!-- Data Point Dots (Historical) -->
        ${histCoords.map((pt, idx) => `
          <g class="ji-chart-point-group" tabindex="0" role="button" aria-label="${months[idx] || ''}: Demand Score ${pt.val}">
            <circle cx="${pt.x}" cy="${pt.y}" r="4" class="ji-chart-point" />
            <title>${months[idx] || 'Month'}: Demand Score ${pt.val}/100</title>
          </g>
        `).join('')}

        <!-- Projection Points -->
        ${projCoords.map((pt, idx) => `
          <g class="ji-chart-point-group ji-point-projected" tabindex="0" role="button" aria-label="Forecast ${months[history.length + idx] || ''}: ${pt.val}">
            <circle cx="${pt.x}" cy="${pt.y}" r="3.5" class="ji-chart-point is-projected" />
            <title>Forecast: ${months[history.length + idx] || 'Forecast'}: Score ${pt.val}/100</title>
          </g>
        `).join('')}
      </svg>

      <!-- Time Axis Labels -->
      <div class="ji-chart-axis-labels">
        <span>6M Ago</span>
        <span>3M Ago</span>
        <span class="is-current">Current Demand (${role.demandScore}/100)</span>
        <span class="is-forecast">Forecast (+${((role.growthPercentage || 18.4) * 0.6).toFixed(1)}%)</span>
      </div>
    </div>
  `;
}

// ============================================================================
// HTML TEMPLATE RENDERERS
// ============================================================================

function renderJobIntelligenceHTML() {
  const role = getSelectedRoleData();
  const visibleRoles = getVisibleRoles();
  const allRolesCount = dedicatedJobRoles.length;
  const favCount = (dashboardState?.favoriteRoles || []).length;
  const myCount = dedicatedJobRoles.filter(r => r.isMyRole || (dashboardState?.savedRoles || []).includes(r.name)).length;

  return `
    <div class="job-intelligence-page" id="jobIntelligenceWorkspace">
      <!-- Page Heading -->
      <header class="ji-page-heading">
        <div>
          <span class="ji-eyebrow">
            <i data-lucide="briefcase-business"></i>
            INDIVIDUAL INTELLIGENCE
          </span>
          <h1>Job Intelligence</h1>
          <p>Explore role momentum, track company hiring signals, analyze required skills, and discover targeted career opportunities.</p>
        </div>
        <div class="ji-page-heading-actions">
          <div class="ji-demo-badge" title="Job market intelligence baseline">
            <span class="ji-live-dot"></span>
            <span>Job intelligence baseline</span>
          </div>
        </div>
      </header>

      <!-- 50/50 Workspace Grid: Left = Role Collection, Right = Illustrative Job Trend -->
      <div class="ji-workspace-grid">
        <!-- LEFT COLUMN: ROLE COLLECTION -->
        <section class="ji-card ji-col-roles" aria-label="Job Role Collection">
          <div class="ji-card-header">
            <div>
              <h2>Job Roles</h2>
              <p>Explore tracked roles, demand scores, and growth momentum</p>
            </div>
            <button type="button" class="ji-btn-secondary" id="btnOpenAddRoleModal" aria-label="Add role to tracking list">
              <i data-lucide="plus"></i>
              <span>Add Role</span>
            </button>
          </div>

          <!-- Collection Segment Control -->
          <div class="ji-collection-tabs" role="tablist" aria-label="Role Scope">
            <button type="button" class="ji-collection-tab ${ui.collection === 'My Roles' ? 'is-active' : ''}" data-collection="My Roles" role="tab" aria-selected="${ui.collection === 'My Roles'}">
              <span>My Roles</span>
              <span class="ji-filter-count-badge">${myCount}</span>
            </button>
            <button type="button" class="ji-collection-tab ${ui.collection === 'Favorite Roles' ? 'is-active' : ''}" data-collection="Favorite Roles" role="tab" aria-selected="${ui.collection === 'Favorite Roles'}">
              <span>Favorite Roles</span>
              <span class="ji-filter-count-badge">${favCount}</span>
            </button>
            <button type="button" class="ji-collection-tab ${ui.collection === 'All Roles' ? 'is-active' : ''}" data-collection="All Roles" role="tab" aria-selected="${ui.collection === 'All Roles'}">
              <span>All Roles</span>
              <span class="ji-filter-count-badge">${allRolesCount}</span>
            </button>
          </div>

          <!-- Search & Filter Controls -->
          <div class="ji-collection-controls">
            <div class="ji-search-wrap">
              <i data-lucide="search"></i>
              <input
                type="text"
                class="ji-search-input"
                id="jiRoleSearchInput"
                placeholder="Search roles, categories, or skills..."
                value="${esc(ui.searchQuery)}"
                aria-label="Search roles"
              />
              ${ui.searchQuery ? `
                <button type="button" class="ji-search-clear" id="jiClearSearchBtn" aria-label="Clear search">
                  <i data-lucide="x"></i>
                </button>
              ` : ''}
            </div>
            <div class="ji-filter-anchor">
              <button
                type="button"
                class="ji-filter-trigger ${ui.filterOpen ? 'is-open' : ''} ${(ui.location !== 'Bangalore' || ui.timeRange !== '30D' || ui.categoryFilter !== 'All Categories') ? 'has-badge' : ''}"
                id="jiFilterTriggerBtn"
                aria-expanded="${ui.filterOpen}"
                aria-haspopup="dialog"
              >
                <i data-lucide="sliders-horizontal"></i>
                <span>Filters</span>
                ${(ui.location !== 'Bangalore' || ui.timeRange !== '30D' || ui.categoryFilter !== 'All Categories') ? `<span class="ji-filter-active-dot"></span>` : ''}
              </button>

              ${renderFilterPopoverHTML()}
            </div>
          </div>

          <!-- Roles List -->
          <div class="ji-role-list" role="listbox" aria-label="Tracked Roles">
            ${visibleRoles.length === 0 ? `
              <div class="ji-empty-state">
                <i data-lucide="search-x"></i>
                <p>No roles found matching "${esc(ui.searchQuery)}"</p>
                <button type="button" class="ji-btn-secondary" id="btnResetFiltersAndSearch">
                  <span>Reset Search & Filters</span>
                </button>
              </div>
            ` : visibleRoles.map(r => {
              const isSelected = r.name.toLowerCase() === role.name.toLowerCase();
              const isFav = (dashboardState?.favoriteRoles || []).includes(r.name);
              const isDown = r.direction === 'down';

              return `
                <div
                  class="ji-role-row ${isSelected ? 'is-active' : ''}"
                  data-role="${esc(r.name)}"
                  tabindex="0"
                  role="option"
                  aria-selected="${isSelected}"
                >
                  <div class="ji-role-icon">
                    <i data-lucide="${esc(r.icon || 'briefcase')}"></i>
                  </div>
                  <div class="ji-role-meta">
                    <strong>${esc(r.name)}</strong>
                    <small>${esc(r.category)} • ${Number(r.openRoles || 0).toLocaleString()} roles</small>
                  </div>
                  <div class="ji-role-spark">
                    ${sparklineSVG(r.history, isDown)}
                  </div>
                  <div class="ji-role-stats">
                    <div class="ji-trend-pill ${isDown ? 'is-down' : 'is-up'}">
                      <i data-lucide="${isDown ? 'trending-down' : 'trending-up'}"></i>
                      <span>${r.change > 0 ? '+' : ''}${r.change}%</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    class="ji-fav-btn ${isFav ? 'is-fav' : ''}"
                    data-action="toggle-fav"
                    data-role="${esc(r.name)}"
                    aria-label="${isFav ? 'Remove from favorites' : 'Add to favorites'}"
                    title="${isFav ? 'Remove from favorites' : 'Add to favorites'}"
                  >
                    <i data-lucide="star"></i>
                  </button>
                </div>
              `;
            }).join('')}
          </div>
        </section>

        <!-- RIGHT COLUMN: DEMO JOB TREND -->
        <section class="ji-card ji-col-trend" aria-label="Job Intelligence Trend">
          <div class="ji-trend-header-details">
            <div class="ji-trend-hero-role">
              <div class="ji-role-icon">
                <i data-lucide="${esc(role.icon || 'briefcase')}"></i>
              </div>
              <div class="ji-trend-hero-meta">
                <span class="ji-eyebrow" style="font-size: 10px;">DEMO JOB TREND</span>
                <h3>${esc(role.name)}</h3>
                <span>${esc(role.category)} • <i data-lucide="map-pin" style="width: 12px; height: 12px; display: inline-block; vertical-align: middle;"></i> ${esc(ui.location)} • ${esc(ui.timeRange)} • <strong style="color: var(--ji-purple);">${esc(role.status)}</strong></span>
              </div>
            </div>
            <div class="ji-trend-hero-metric">
              <div class="ji-trend-hero-val">${role.demandScore}</div>
              <div class="ji-trend-hero-label">Demand Score</div>
            </div>
          </div>

          <!-- Interactive Trend SVG Chart -->
          <div class="ji-chart-section">
            ${renderMainTrendChart(role)}
          </div>

          <!-- Normalized Job Market Signal Mix (Step 16) -->
          <div class="ji-signal-mix-section">
            <div class="ji-signal-mix-header">
              <strong>JOB MARKET SIGNAL MIX</strong>
              <small>Normalized signal taxonomy across verified demand streams</small>
            </div>
            <div class="ji-signal-mix-bar" role="group" aria-label="Job signal distribution">
              ${jobMarketSignalMix.map(sig => `
                <div
                  class="ji-mix-segment"
                  style="width: ${sig.percent}%; background-color: ${sig.color};"
                  title="${esc(sig.label)}: ${sig.percent}%"
                  data-action="select-signal"
                  data-signal-id="${esc(sig.id)}"
                ></div>
              `).join('')}
            </div>
            <div class="ji-signal-mix-pills">
              ${jobMarketSignalMix.map(sig => {
                const isSelected = ui.selectedSignalId === sig.id;
                return `
                  <button
                    type="button"
                    class="ji-mix-pill ${isSelected ? 'is-active' : ''}"
                    data-action="select-signal"
                    data-signal-id="${esc(sig.id)}"
                    aria-label="${esc(sig.label)}: ${sig.percent}%. Click to view details."
                  >
                    <span style="display: flex; align-items: center; gap: 6px;">
                      <span class="ji-mix-pill-dot" style="background-color: ${sig.color};"></span>
                      <strong>${esc(sig.label)}</strong>
                    </span>
                    <span style="font-weight: 700; color: var(--ji-purple); font-size: 11px;">${sig.percent}%</span>
                  </button>
                `;
              }).join('')}
            </div>

            <!-- Signal Detail Popover/Drawer when clicked -->
            ${ui.selectedSignalId ? renderSelectedSignalDetailHTML() : ''}
          </div>

          <!-- Company Hiring Signals (Step 19: Direct links to Market Intelligence) -->
          <div class="ji-companies-section">
            <div class="ji-companies-section-title">
              <span>Top Hiring Employers for ${esc(role.name)}</span>
              <a href="#/individual/market-insights" class="ji-see-all-link" style="color: var(--ji-purple); font-size: 11px; text-decoration: none; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;">
                <span>ALL COMPANIES</span>
                <i data-lucide="arrow-up-right" style="width: 13px; height: 13px;"></i>
              </a>
            </div>
            <div class="ji-companies-hiring-stack" style="display: flex; flex-direction: column; gap: 8px;">
              ${(role.companiesHiring || []).slice(0, 3).map(comp => `
                <div
                  class="ji-company-hiring-row"
                  data-action="navigate-company"
                  data-company="${esc(comp.name)}"
                  tabindex="0"
                  role="button"
                  aria-label="Investigate ${esc(comp.name)} hiring in Market Intelligence"
                >
                  <div class="ji-comp-monogram" style="background: ${comp.brandColor || '#B22DEF'}">
                    ${esc(comp.logoInitials || comp.name.substring(0, 2))}
                  </div>
                  <div class="ji-comp-info">
                    <strong>${esc(comp.name)}</strong>
                    <small>${comp.openCount ? `${comp.openCount} open roles` : 'Active hiring'} • ${esc(comp.location || 'Multiple hubs')}</small>
                  </div>
                  <div class="ji-trend-pill is-up" style="font-size: 11px;">
                    <i data-lucide="trending-up"></i>
                    <span>${esc(comp.signalText)}</span>
                  </div>
                  <button type="button" class="ji-btn-subtle" style="padding: 4px 10px; font-size: 11px;" aria-label="View ${esc(comp.name)} in Market Intelligence">
                    <span>Investigate</span>
                    <i data-lucide="arrow-right" style="width: 12px; height: 12px;"></i>
                  </button>
                </div>
              `).join('')}
            </div>
          </div>
        </section>
      </div>

      <!-- SECTION 3: JOB INTELLIGENCE CONSOLE -->
      <section class="ji-console-card" aria-label="Job Intelligence Console">
        <div class="ji-console-header">
          <span class="ji-eyebrow">
            <i data-lucide="sparkles"></i>
            DYNAMIC ANALYSIS ENGINE
          </span>
          <h2>Job Intelligence Console</h2>
          <p>Query role demand momentum, evaluate hiring companies, inspect skill requirements, and benchmark career alignment.</p>
        </div>

        <!-- Role & Company Context Chips (Step 22) -->
        <div class="ji-context-chips-wrap">
          <span class="ji-context-label">Role Focus:</span>
          <div class="ji-context-chip is-active">
            <i data-lucide="${esc(role.icon || 'bot')}" style="width: 14px; height: 14px;"></i>
            <span>${esc(role.name)}</span>
          </div>

          <span class="ji-context-label" style="margin-left: 8px;">Company Context:</span>
          ${['NVIDIA', 'Microsoft', 'Google', 'Amazon', 'OpenAI'].map(compName => {
            const isChipActive = ui.selectedCompanyContext.includes(compName);
            return `
              <button
                type="button"
                class="ji-context-chip ${isChipActive ? 'is-active' : ''}"
                data-action="toggle-company-context"
                data-company="${esc(compName)}"
                aria-pressed="${isChipActive}"
              >
                <span>${esc(compName)}</span>
                ${isChipActive ? `<i data-lucide="check" style="width: 13px; height: 13px;"></i>` : `<i data-lucide="plus" style="width: 13px; height: 13px;"></i>`}
              </button>
            `;
          }).join('')}
        </div>

        <!-- Dynamic Suggested Questions (Step 24) -->
        <div class="ji-suggested-questions">
          ${getSuggestedQuestionsForRole(role.name).map(q => `
            <button
              type="button"
              class="ji-question-pill"
              data-action="select-question"
              data-query="${esc(q)}"
            >
              <i data-lucide="help-circle"></i>
              <span>${esc(q)}</span>
            </button>
          `).join('')}
        </div>

        <!-- Query Input Bar -->
        <div class="ji-query-bar">
          <div class="ji-query-input-wrap">
            <i data-lucide="sparkles"></i>
            <input
              type="text"
              class="ji-query-input"
              id="jiConsoleQueryInput"
              placeholder="Ask about role growth, compensation, required skills, or hiring velocity..."
              value="${esc(ui.queryText)}"
              aria-label="Ask about job trends"
            />
          </div>
          <button
            type="button"
            class="ji-btn-primary"
            id="btnRunJobAnalysis"
            ${ui.isAnalyzing ? 'disabled' : ''}
            aria-label="Analyze job trend"
          >
            <i data-lucide="${ui.isAnalyzing ? 'loader-2' : 'sparkles'}" class="${ui.isAnalyzing ? 'is-spinning' : ''}"></i>
            <span>${ui.isAnalyzing ? 'Analyzing...' : 'Analyze Job Trend'}</span>
          </button>
        </div>

        <!-- 3-Stage Scanning Animation State (Step 26) -->
        ${ui.isAnalyzing ? `
          <div class="ji-analysis-state" aria-live="polite">
            <div class="ji-analysis-orb">
              <i data-lucide="sparkles"></i>
            </div>
            <strong>${getScanningStageText(ui.analysisStep, role.name)}</strong>
            <small>Correlating regional requisitions, employer signals, and skill graph trajectories...</small>
            <div class="ji-analysis-progress-bar">
              <div class="ji-analysis-progress-fill"></div>
            </div>
          </div>
        ` : ''}
      </section>

      <!-- SECTION 4: INTELLIGENCE RESULT (Step 27: 7 Investigation Tabs) -->
      ${ui.hasAnalyzed && !ui.isAnalyzing ? `
        <section class="ji-result-card" id="jiResultSection" aria-label="Job Intelligence Findings">
          <div class="ji-result-header">
            <div class="ji-result-profile">
              <div class="ji-result-icon">
                <i data-lucide="${esc(role.icon || 'bot')}"></i>
              </div>
              <div class="ji-result-info">
                <h3>${esc(role.name)} — Strategic Job Intelligence</h3>
                <div class="ji-result-meta-tags">
                  <span class="ji-result-tag"><i data-lucide="tag"></i>${esc(role.category)}</span>
                  <span class="ji-result-tag"><i data-lucide="map-pin"></i>${esc(ui.location)}</span>
                  <span class="ji-result-tag"><i data-lucide="clock"></i>${esc(ui.timeRange)}</span>
                  <span class="ji-result-tag is-badge"><i data-lucide="briefcase"></i>${esc(role.experienceLevel || 'Mid to Senior')}</span>
                </div>
              </div>
            </div>
            <div class="ji-result-actions">
              <button
                type="button"
                class="ji-btn-secondary"
                id="btnSaveRoleResult"
                aria-label="Bookmark this role"
              >
                <i data-lucide="${(dashboardState?.savedRoles || []).includes(role.name) ? 'bookmark-check' : 'bookmark'}"></i>
                <span>${(dashboardState?.savedRoles || []).includes(role.name) ? 'Saved Role' : 'Save Role'}</span>
              </button>
            </div>
          </div>

          <!-- 7 Tabs Navigation Bar -->
          <nav class="ji-tabs-bar" role="tablist" aria-label="Investigation Tabs">
            ${TABS.map(tab => {
              const isActive = ui.activeTab === tab;
              const iconName = TAB_ICONS[tab] || 'layout';
              return `
                <button
                  type="button"
                  class="ji-tab-btn ${isActive ? 'is-active' : ''}"
                  data-tab="${esc(tab)}"
                  role="tab"
                  aria-selected="${isActive}"
                >
                  <i data-lucide="${esc(iconName)}"></i>
                  <span>${esc(tab)}</span>
                </button>
              `;
            }).join('')}
          </nav>
          ${renderIntelligenceEvidencePanel(ui.jobApiResponse, {
            title: 'Job intelligence evidence',
            loading: ui.isAnalyzing,
            error: ui.jobApiError
          })}
          <p class="intel-evidence-panel__message" role="note">
            This role dashboard also contains illustrative baseline values. Only metrics shown with structured evidence above are API-backed.
          </p>

          <!-- Tab Panels Content -->
          <div class="ji-panel-content">
            ${renderTabPanelContent(ui.activeTab, role)}
          </div>
        </section>
      ` : ''}

      <!-- Modals (Add Role & Evidence Viewer) -->
      ${ui.addModalOpen ? renderAddRoleModalHTML() : ''}
      ${ui.evidenceModalData ? renderEvidenceModalHTML() : ''}
    </div>
  `;
}

// ============================================================================
// TAB PANELS IMPLEMENTATION
// ============================================================================

function renderTabPanelContent(tab, role) {
  switch (tab) {
    case 'Overview':
      return renderOverviewTabHTML(role);
    case 'Demand Change':
      return renderDemandChangeTabHTML(role);
    case 'Role Intelligence':
      return renderRoleIntelligenceTabHTML(role);
    case 'Company Hiring':
      return renderCompanyHiringTabHTML(role);
    case 'Skill Requirements':
      return renderSkillRequirementsTabHTML(role);
    case 'Evidence':
      return renderEvidenceTabHTML(role);
    case 'AI Insight':
      return renderAIInsightTabHTML(role);
    default:
      return renderOverviewTabHTML(role);
  }
}

// 1. OVERVIEW TAB
function renderOverviewTabHTML(role) {
  const af = role.alignmentFactors || {
    skillAlignment: 'High (Python, Machine Learning match 82%)',
    roleDemand: 'Accelerating (+18.4% growth)',
    experienceFit: 'Strong (Mid to Senior range matches current career baseline)',
    locationFit: 'Optimal (Bangalore is top national hiring hub)',
    skillGaps: 'CUDA Systems, Low-level GPU optimization'
  };

  return `
    <div class="ji-tab-pane">
      <!-- 4 Key Metrics Cards -->
      <div class="ji-overview-metrics-grid">
        <div class="ji-metric-quad-card">
          <span class="ji-metric-quad-label">Active Requisitions</span>
          <div class="ji-metric-quad-value">${role.openRoles ? Number(role.openRoles).toLocaleString() : 'Baseline'}</div>
          <span class="ji-metric-quad-sub">${role.growthPercentage != null ? `+${role.growthPercentage}% vs previous period` : 'Taxonomy Baseline'}</span>
        </div>
        <div class="ji-metric-quad-card">
          <span class="ji-metric-quad-label">Hiring Employers</span>
          <div class="ji-metric-quad-value">${role.hiringCompaniesCount != null ? role.hiringCompaniesCount : 'Curated'}</div>
          <span class="ji-metric-quad-sub">Across enterprise & scale-up tiers</span>
        </div>
        <div class="ji-metric-quad-card">
          <span class="ji-metric-quad-label">Target Compensation</span>
          <div class="ji-metric-quad-value" style="font-size: 20px; line-height: 1.2;">${esc(role.averageComp || '₹28L - ₹55L / yr')}</div>
          <span class="ji-metric-quad-sub">Top quartile for specialized talent</span>
        </div>
        <div class="ji-metric-quad-card">
          <span class="ji-metric-quad-label">Demand Score</span>
          <div class="ji-metric-quad-value" style="color: var(--ji-purple);">${role.demandScore}/100</div>
          <span class="ji-metric-quad-sub">Ranked #${role.demandScore > 85 ? '1' : '3'} in ${esc(role.category)}</span>
        </div>
      </div>

      <!-- Transparent Profile Alignment Breakdown (Step 29, 50) -->
      <div class="ji-alignment-section">
        <div class="ji-alignment-header">
          <div>
            <strong>Transparent Profile Alignment Breakdown</strong>
            <small style="display: block; color: var(--ji-muted); margin-top: 2px;">
              How this role's market signals intersect with your authenticated skills and trajectory
            </small>
          </div>
          <span class="ji-status-badge is-known">84% Match Index</span>
        </div>
        <div class="ji-alignment-grid">
          <div class="ji-alignment-item">
            <span class="ji-alignment-label">Skill Alignment</span>
            <span class="ji-alignment-val">${esc(af.skillAlignment)}</span>
          </div>
          <div class="ji-alignment-item">
            <span class="ji-alignment-label">Market Demand</span>
            <span class="ji-alignment-val">${esc(af.roleDemand)}</span>
          </div>
          <div class="ji-alignment-item">
            <span class="ji-alignment-label">Experience Fit</span>
            <span class="ji-alignment-val">${esc(af.experienceFit)}</span>
          </div>
          <div class="ji-alignment-item">
            <span class="ji-alignment-label">Location Fit</span>
            <span class="ji-alignment-val">${esc(af.locationFit)}</span>
          </div>
          <div class="ji-alignment-item" style="grid-column: span 2;">
            <span class="ji-alignment-label">Identified Skill Gaps</span>
            <span class="ji-alignment-val" style="color: var(--ji-negative); font-weight: 700;">${esc(af.skillGaps)}</span>
          </div>
        </div>
      </div>

      <!-- Overview Summary & Core Responsibilities -->
      <div class="ji-demand-history-grid">
        <div class="ji-demand-box">
          <strong>Role Definition & Market Mandate</strong>
          <p>${esc(role.overview)}</p>
          <div style="margin-top: 10px;">
            <small style="color: var(--ji-muted); font-weight: 700; text-transform: uppercase;">Adjacent Roles:</small>
            <div style="display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap;">
              ${(role.adjacentRoles || ['Machine Learning Engineer', 'Backend Developer']).map(adj => `
                <button type="button" class="ji-evolution-pill" data-action="switch-role" data-role="${esc(adj)}">
                  ${esc(adj)}
                </button>
              `).join('')}
            </div>
          </div>
        </div>
        <div class="ji-demand-box">
          <strong>Key Responsibilities in Current Postings</strong>
          <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: var(--ji-ink); display: flex; flex-direction: column; gap: 6px;">
            ${(role.responsibilities || [
              'Architect production AI/ML services with guaranteed latency SLAs.',
              'Implement scalable model serving infrastructure across GPU clusters.',
              'Fine-tune foundation models and optimize context retrieval architectures.',
              'Integrate automated telemetry and data lineage pipelines.'
            ]).map(resp => `<li>${esc(resp)}</li>`).join('')}
          </ul>
        </div>
      </div>
    </div>
  `;
}

// 2. DEMAND CHANGE TAB
function renderDemandChangeTabHTML(role) {
  const history = role.history || [48, 56, 64, 72, 80, 85, 91];
  const delta30D = (history[history.length - 1] - history[history.length - 2]).toFixed(1);
  const delta3M = (history[history.length - 1] - history[Math.max(0, history.length - 4)]).toFixed(1);

  return `
    <div class="ji-tab-pane">
      <div class="ji-demand-history-grid">
        <div class="ji-demand-box">
          <span class="ji-evolution-col-title">Historical Momentum Drivers</span>
          <p>
            Requisition volume for <strong>${esc(role.name)}</strong> in <strong>${esc(ui.location)}</strong> has shown consistent upward velocity over the past 6 months (+${role.growthPercentage || 18.4}% overall).
          </p>
          <div style="display: flex; gap: 16px; margin-top: 12px;">
            <div style="padding: 10px 14px; background: #FFFFFF; border-radius: 8px; border: 1px solid var(--ji-border); flex: 1;">
              <small style="color: var(--ji-muted); display: block;">30-Day Change</small>
              <strong style="color: var(--ji-positive); font-size: 18px;">+${delta30D}%</strong>
            </div>
            <div style="padding: 10px 14px; background: #FFFFFF; border-radius: 8px; border: 1px solid var(--ji-border); flex: 1;">
              <small style="color: var(--ji-muted); display: block;">3-Month Velocity</small>
              <strong style="color: var(--ji-positive); font-size: 18px;">+${delta3M}%</strong>
            </div>
          </div>
        </div>
        <div class="ji-demand-box">
          <span class="ji-evolution-col-title">Forward Forecasting Status</span>
          <p>
            Forward-looking projections are held offline until multi-period longitudinal evidence thresholds are satisfied. Current intelligence operates strictly on verified empirical observations and taxonomy cross-references.
          </p>
          <div style="padding: 12px; background: #FFFFFF; border-radius: 8px; border: 1px solid var(--ji-border); margin-top: 8px;">
            <strong style="display: block; font-size: 12.5px; color: var(--ji-deep);">Forecast Policy (G2.6/G2.7)</strong>
            <span style="font-size: 12px; color: var(--ji-muted);">Speculative forecasting disabled • Evidence-grounded observations only</span>
          </div>
        </div>
      </div>

      <!-- Signals Breakdown Table -->
      <div class="ji-card" style="padding: 20px; margin-top: 16px;">
        <h4 style="margin: 0 0 12px; font-size: 14px; color: var(--ji-deep);">Component Telemetry Streams</h4>
        <div class="ji-signal-legend-grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
          ${jobMarketSignalMix.map(s => `
            <div class="ji-signal-legend-item" style="cursor: default;">
              <span class="ji-signal-color-dot" style="background-color: ${s.color};"></span>
              <div class="ji-signal-legend-text">
                <strong>${esc(s.label)} (${s.percent}%)</strong>
                <span>${esc(s.detail)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// 3. ROLE INTELLIGENCE TAB (Step 34, 35)
function renderRoleIntelligenceTabHTML(role) {
  const evo = role.evolution || {
    current: ['Python', 'Machine Learning', 'SQL', 'FastAPI'],
    emerging: ['Generative AI', 'CUDA', 'Cloud Computing', 'MLOps'],
    future: ['Autonomous Multi-Agent Orchestration', 'On-Device Quantization', 'Kernel Compilation (Triton)']
  };

  const prog = role.careerProgression || [
    { step: 'Current Profile', title: 'AI/ML Professional', match: 'Aligned (Python, ML)' },
    { step: 'Target Role', title: 'Senior AI Engineer', match: 'Next Target (Bridge CUDA/Infra)' },
    { step: 'Advanced Track', title: 'Lead AI Systems Architect', match: 'Strategic Leadership' }
  ];

  return `
    <div class="ji-tab-pane">
      <!-- Role Evolution Stack -->
      <div class="ji-evolution-card">
        <span class="ji-eyebrow">
          <i data-lucide="layers"></i>
          SKILL GRAPH EVOLUTION
        </span>
        <h4 style="margin: 6px 0 4px; font-size: 16px; color: var(--ji-deep);">Technological Evolution for ${esc(role.name)}</h4>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0 0 16px;">
          How technological requisitions for this role have shifted from foundational skills to modern frontiers.
        </p>

        <div class="ji-evolution-grid">
          <div class="ji-evolution-col">
            <span class="ji-evolution-col-title">Foundational Baseline</span>
            <small style="color: var(--ji-muted); font-size: 11px;">Expected in 95%+ of postings</small>
            ${evo.current.map(skill => `
              <div class="ji-evolution-pill" data-action="navigate-skill" data-skill="${esc(skill)}" style="cursor: pointer;" title="Explore ${esc(skill)} in Skill Intelligence">
                <span>${esc(skill)}</span>
                <i data-lucide="arrow-up-right" style="width: 12px; height: 12px; margin-left: auto;"></i>
              </div>
            `).join('')}
          </div>

          <div class="ji-evolution-col" style="border-color: rgba(178, 45, 239, 0.3); background: rgba(243, 233, 255, 0.2);">
            <span class="ji-evolution-col-title" style="color: var(--ji-purple);">Active Growth Vector</span>
            <small style="color: var(--ji-muted); font-size: 11px;">Differentiating high-comp requisitions</small>
            ${evo.emerging.map(skill => `
              <div class="ji-evolution-pill" data-action="navigate-skill" data-skill="${esc(skill)}" style="cursor: pointer; background: #FFFFFF; border: 1px solid var(--ji-border-glass);" title="Explore ${esc(skill)} in Skill Intelligence">
                <span style="font-weight: 700; color: var(--ji-purple);">${esc(skill)}</span>
                <i data-lucide="arrow-up-right" style="width: 12px; height: 12px; margin-left: auto; color: var(--ji-purple);"></i>
              </div>
            `).join('')}
          </div>

          <div class="ji-evolution-col">
            <span class="ji-evolution-col-title">Emerging Frontiers</span>
            <small style="color: var(--ji-muted); font-size: 11px;">12-24 month horizon specialization</small>
            ${evo.future.map(skill => `
              <div class="ji-evolution-pill">
                <span>${esc(skill)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>

      <!-- Career Progression Pathway -->
      <div class="ji-card" style="padding: 24px; margin-top: 20px;">
        <span class="ji-eyebrow">
          <i data-lucide="git-commit"></i>
          CAREER PROGRESSION PATHWAY
        </span>
        <h4 style="margin: 6px 0 16px; font-size: 16px; color: var(--ji-deep);">Strategic Role Trajectory</h4>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
          ${prog.map((p, idx) => `
            <div style="padding: 16px; background: var(--ji-wash); border: 1px solid var(--ji-border); border-radius: 12px; position: relative;">
              <span style="font-size: 11px; font-weight: 750; text-transform: uppercase; color: var(--ji-purple); letter-spacing: 0.05em;">
                Step 0${idx + 1}: ${esc(p.step)}
              </span>
              <strong style="display: block; font-size: 15px; color: var(--ji-deep); margin: 6px 0 4px;">${esc(p.title)}</strong>
              <small style="font-size: 12px; color: var(--ji-muted);">${esc(p.match)}</small>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// 4. COMPANY HIRING TAB (Step 36, 37)
function renderCompanyHiringTabHTML(role) {
  const comps = role.companiesHiring || [];
  const jobs = role.jobOpportunities || [];

  return `
    <div class="ji-tab-pane">
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 4px; font-size: 16px; color: var(--ji-deep);">Enterprise Hiring Velocity</h4>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0;">
          Top employers actively expanding their engineering roster for <strong>${esc(role.name)}</strong> in <strong>${esc(ui.location)}</strong>.
        </p>
      </div>

      <!-- Companies Grid -->
      <div class="ji-companies-hiring-grid">
        ${comps.map(c => `
          <div class="ji-employer-card">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div class="ji-comp-monogram" style="background: ${c.brandColor || '#B22DEF'};">
                  ${esc(c.logoInitials || c.name.substring(0, 2))}
                </div>
                <div>
                  <strong style="font-size: 14px; color: var(--ji-deep); display: block;">${esc(c.name)}</strong>
                  <small style="color: var(--ji-muted); font-size: 11.5px;">${esc(c.location)}</small>
                </div>
              </div>
              <span class="ji-trend-pill is-up">${esc(c.signalText)}</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--ji-border); padding-top: 10px; margin-top: 4px;">
              <span style="font-size: 12px; color: var(--ji-muted);">
                ${c.openCount ? `<strong>${c.openCount}+</strong> open roles` : `<strong>Verified</strong> employer`}
              </span>
              <button
                type="button"
                class="ji-btn-secondary"
                style="padding: 6px 12px; font-size: 12px;"
                data-action="navigate-company"
                data-company="${esc(c.name)}"
                aria-label="Explore ${esc(c.name)} in Market Intelligence"
              >
                <span>Explore in Market</span>
                <i data-lucide="arrow-up-right"></i>
              </button>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Curated Job Requisitions List (Step 37) -->
      <div style="margin-top: 28px;">
        <h4 style="margin: 0 0 12px; font-size: 15px; color: var(--ji-deep);">Curated Requisition Signals</h4>
        <div class="ji-opportunities-list">
          ${jobs.map(job => `
            <div class="ji-job-row">
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <strong style="font-size: 14px; color: var(--ji-deep);">${esc(job.role)}</strong>
                  <span class="ji-status-badge is-known">${esc(job.signal)}</span>
                </div>
                <div style="display: flex; gap: 12px; font-size: 12px; color: var(--ji-muted); margin-top: 4px;">
                  <span><strong>${esc(job.company)}</strong></span>
                  <span>•</span>
                  <span>${esc(job.location)}</span>
                  <span>•</span>
                  <span>${esc(job.type)}</span>
                  <span>•</span>
                  <span>Posted ${esc(job.posted)}</span>
                </div>
                <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
                  ${(job.reqSkills || []).map(sk => `
                    <span class="ji-evolution-pill" style="font-size: 11px;">${esc(sk)}</span>
                  `).join('')}
                </div>
              </div>
              <button
                type="button"
                class="ji-btn-primary"
                data-action="navigate-company"
                data-company="${esc(job.company)}"
                aria-label="View ${esc(job.company)} details in Market Intelligence"
              >
                <span>View Company</span>
                <i data-lucide="arrow-right"></i>
              </button>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// 5. SKILL REQUIREMENTS TAB (Step 38, 39, 40, 41)
function renderSkillRequirementsTabHTML(role) {
  const skills = role.requiredSkills || [];

  return `
    <div class="ji-tab-pane">
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 4px; font-size: 16px; color: var(--ji-deep);">Required Skills Breakdown & Profile Alignment</h4>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0;">
          Skills demanded by current requisitions for <strong>${esc(role.name)}</strong>. Click any skill to investigate deeply in Skill Intelligence.
        </p>
      </div>

      <div class="ji-skills-req-grid">
        ${skills.map(sk => {
          const isGap = sk.status === 'Gap';
          const isDeveloping = sk.status === 'Developing';
          const statusClass = isGap ? 'is-gap' : isDeveloping ? 'is-developing' : 'is-known';

          return `
            <div class="ji-skill-req-card">
              <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;">
                <div>
                  <strong style="font-size: 15px; color: var(--ji-deep);">${esc(sk.name)}</strong>
                  <div style="display: flex; gap: 6px; margin-top: 4px;">
                    <span class="ji-status-badge ${statusClass}">${esc(sk.status)}</span>
                    <span class="ji-evolution-pill" style="font-size: 10.5px;">${esc(sk.importance)}</span>
                  </div>
                </div>
                <span style="font-size: 12px; font-weight: 700; color: var(--ji-positive);">${esc(sk.trend)}</span>
              </div>

              <p style="font-size: 12.5px; color: var(--ji-muted); margin: 6px 0; line-height: 1.45; flex: 1;">
                ${esc(sk.notes)}
              </p>

              <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--ji-border); padding-top: 10px; margin-top: auto;">
                <span style="font-size: 11.5px; color: var(--ji-muted);">${esc(sk.level)}</span>
                <button
                  type="button"
                  class="ji-btn-secondary"
                  style="padding: 5px 10px; font-size: 11.5px;"
                  data-action="navigate-skill"
                  data-skill="${esc(sk.name)}"
                  aria-label="Investigate ${esc(sk.name)} in Skill Intelligence"
                >
                  <span>Skill Intel</span>
                  <i data-lucide="arrow-up-right"></i>
                </button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  `;
}

// 6. EVIDENCE TAB
function renderEvidenceTabHTML(role) {
  const evList = role.evidence || [];

  return `
    <div class="ji-tab-pane">
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 4px; font-size: 16px; color: var(--ji-deep);">Requisition Examples & Research</h4>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0;">
          All telemetry insights for <strong>${esc(role.name)}</strong> are corroborated by authoritative workforce publications and raw requisition feeds.
        </p>
      </div>

      <div class="ji-evidence-list">
        ${evList.map((item, idx) => `
          <div class="ji-evidence-row">
            <div style="flex: 1; min-width: 0;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <strong style="font-size: 14.5px; color: var(--ji-deep);">${esc(item.source)}</strong>
                <span class="ji-evidence-badge">${esc(item.type)}</span>
                <span style="font-size: 12px; color: var(--ji-muted);">• ${esc(item.date)}</span>
              </div>
              <p style="margin: 6px 0 4px; font-size: 13px; font-weight: 600; color: var(--ji-purple);">
                "${esc(item.signal)}"
              </p>
              <p style="margin: 0; font-size: 12.5px; color: var(--ji-muted);">
                ${esc(item.supports)}
              </p>
            </div>
            <button
              type="button"
              class="ji-btn-secondary"
              data-action="view-evidence"
              data-evidence-index="${idx}"
              aria-label="View citation details"
            >
              <i data-lucide="file-text"></i>
              <span>View Citation</span>
            </button>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// 7. AI INSIGHT TAB (Step 42, 43, 44, 45, 54, 55, 56)
function renderAIInsightTabHTML(role) {
  const insight = role.aiInsight || {
    whatChanged: `Requisitions for ${role.name} increased +${role.growthPercentage || 18.4}%, driven by enterprise modernization.`,
    whyItMatters: 'Organizations are operationalizing generative models into production environments with strict reliability requirements.',
    whatItMeans: 'Your core background provides strong candidacy; bridging identified hardware systems gaps unlocks premium opportunities.',
    whatYouShouldDo: 'Prioritize low-latency GPU acceleration and containerized deployment, then connect directly with hiring teams.',
    recommendations: [
      { type: 'Skill Focus', title: 'Bridge CUDA and GPU Acceleration Gap', desc: 'Appears as a recurring requirement across 480+ AI infrastructure roles.', skill: 'CUDA', primaryAction: 'Build Roadmap' },
      { type: 'Target Employer', title: 'Explore NVIDIA Engineering Openings', desc: 'Illustrative example of engineering opportunities in Bangalore; current requisition data is not connected.', company: 'NVIDIA', primaryAction: 'Explore in Market' },
      { type: 'Role Opportunity', title: 'Prepare for AI Infrastructure Engineer Requisitions', desc: 'Review benchmark assessment and role requirements.', role: 'AI Infrastructure Engineer', primaryAction: 'View Role Details' }
    ]
  };

  return `
    <div class="ji-tab-pane">
      <!-- 4 Structured Insight Boxes -->
      <div class="ji-insight-quad-grid">
        <div class="ji-insight-box">
          <span class="ji-insight-box-title">What Changed?</span>
          <p>${esc(insight.whatChanged)}</p>
        </div>
        <div class="ji-insight-box">
          <span class="ji-insight-box-title">Why It Matters?</span>
          <p>${esc(insight.whyItMatters)}</p>
        </div>
        <div class="ji-insight-box">
          <span class="ji-insight-box-title">What It Means for You?</span>
          <p>${esc(insight.whatItMeans)}</p>
        </div>
        <div class="ji-insight-box">
          <span class="ji-insight-box-title">What You Should Do?</span>
          <p>${esc(insight.whatYouShouldDo)}</p>
        </div>
      </div>

      <!-- Actionable Next Steps & Connected Pathways -->
      <div class="ji-recommendations-section">
        <span class="ji-eyebrow">
          <i data-lucide="check-circle-2"></i>
          RECOMMENDED STRATEGIC ACTIONS
        </span>
        <h4 style="margin: 4px 0 12px; font-size: 16px; color: var(--ji-deep);">Targeted Career Initiatives</h4>

        <div class="ji-recommendations-list">
          ${(insight.recommendations || []).map(rec => `
            <div class="ji-recommendation-item">
              <div style="flex: 1; min-width: 0;">
                <span class="ji-evolution-pill" style="font-size: 10.5px; margin-bottom: 4px; display: inline-block;">
                  ${esc(rec.type)}
                </span>
                <strong style="display: block; font-size: 14.5px; color: var(--ji-deep);">${esc(rec.title)}</strong>
                <p style="margin: 4px 0 0; font-size: 12.5px; color: var(--ji-muted);">${esc(rec.desc)}</p>
              </div>

              <div>
                ${rec.skill ? `
                  <button
                    type="button"
                    class="ji-btn-primary"
                    data-action="trigger-roadmap-builder"
                    data-skill="${esc(rec.skill)}"
                    aria-label="Build roadmap for ${esc(rec.skill)}"
                  >
                    <i data-lucide="map"></i>
                    <span>Build Roadmap</span>
                  </button>
                ` : rec.company ? `
                  <button
                    type="button"
                    class="ji-btn-secondary"
                    data-action="navigate-company"
                    data-company="${esc(rec.company)}"
                    aria-label="Investigate ${esc(rec.company)} in Market Intelligence"
                  >
                    <i data-lucide="building-2"></i>
                    <span>Explore in Market</span>
                  </button>
                ` : `
                  <button
                    type="button"
                    class="ji-btn-secondary"
                    data-action="switch-role"
                    data-role="${esc(rec.role || role.name)}"
                  >
                    <span>View Role</span>
                    <i data-lucide="arrow-right"></i>
                  </button>
                `}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

// ============================================================================
// MODALS & POPOVERS
// ============================================================================

function renderFilterPopoverHTML() {
  if (!ui.filterOpen) return '';

  return `
    <div class="ji-popover-scrim" id="jiFilterScrim"></div>
    <div class="ji-filter-popover" role="dialog" aria-modal="true" aria-label="Job Intelligence Filters">
      <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--ji-border); padding-bottom: 10px;">
        <strong style="font-size: 15px; color: var(--ji-deep);">Job Intelligence Filters</strong>
        <button type="button" class="ji-chip-remove" id="btnCloseFilterPopover" aria-label="Close filters">
          <i data-lucide="x"></i>
        </button>
      </div>

      <!-- Location Filter -->
      <div class="ji-filter-group">
        <label for="jiFilterLocation" style="display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: var(--ji-muted); margin-bottom: 6px;">
          Location Scope
        </label>
        <select class="ji-select" id="jiFilterLocation">
          ${LOCATIONS.map(loc => `
            <option value="${esc(loc)}" ${ui.location === loc ? 'selected' : ''}>${esc(loc)}</option>
          `).join('')}
        </select>
      </div>

      <!-- Time Range Filter -->
      <div class="ji-filter-group">
        <label for="jiFilterTimeRange" style="display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: var(--ji-muted); margin-bottom: 6px;">
          Time Horizon
        </label>
        <select class="ji-select" id="jiFilterTimeRange">
          ${RANGES.map(rng => `
            <option value="${esc(rng)}" ${ui.timeRange === rng ? 'selected' : ''}>${esc(rng)}</option>
          `).join('')}
        </select>
      </div>

      <!-- Role Category Filter -->
      <div class="ji-filter-group">
        <label for="jiFilterCategory" style="display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: var(--ji-muted); margin-bottom: 6px;">
          Role Category
        </label>
        <select class="ji-select" id="jiFilterCategory">
          ${CATEGORIES.map(cat => `
            <option value="${esc(cat)}" ${ui.categoryFilter === cat ? 'selected' : ''}>${esc(cat)}</option>
          `).join('')}
        </select>
      </div>

      <!-- Employment Type Filter -->
      <div class="ji-filter-group">
        <label for="jiFilterType" style="display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: var(--ji-muted); margin-bottom: 6px;">
          Employment Type
        </label>
        <select class="ji-select" id="jiFilterType">
          ${EMPLOYMENT_TYPES.map(typ => `
            <option value="${esc(typ)}" ${ui.typeFilter === typ ? 'selected' : ''}>${esc(typ)}</option>
          `).join('')}
        </select>
      </div>

      <div style="display: flex; gap: 10px; margin-top: 8px;">
        <button type="button" class="ji-btn-secondary" id="btnResetFilters" style="flex: 1;">
          <span>Reset</span>
        </button>
        <button type="button" class="ji-btn-primary" id="btnApplyFilters" style="flex: 1;">
          <span>Apply Filters</span>
        </button>
      </div>
    </div>
  `;
}

function renderSelectedSignalDetailHTML() {
  const sig = jobMarketSignalMix.find(s => s.id === ui.selectedSignalId);
  if (!sig) return '';

  return `
    <div class="ji-signal-detail-card" style="margin-top: 14px; padding: 14px; background: #FFFFFF; border: 1px solid var(--ji-border); border-radius: 10px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <strong style="color: ${sig.color}; font-size: 13.5px;">${esc(sig.label)} (${sig.percent}%)</strong>
        <button type="button" class="ji-chip-remove" data-action="close-signal-detail" aria-label="Close detail">
          <i data-lucide="x"></i>
        </button>
      </div>
      <p style="margin: 0; font-size: 12.5px; color: var(--ji-ink);">${esc(sig.detail)}</p>
      ${sig.topRoles ? `
        <div style="margin-top: 8px; font-size: 11.5px; color: var(--ji-muted);">
          <strong>Concentrated Roles:</strong> ${sig.topRoles.join(', ')}
        </div>
      ` : ''}
      ${sig.topCompanies ? `
        <div style="margin-top: 8px; font-size: 11.5px; color: var(--ji-muted);">
          <strong>Active Employers:</strong> ${sig.topCompanies.join(', ')}
        </div>
      ` : ''}
    </div>
  `;
}

function renderAddRoleModalHTML() {
  const currentRoleNames = dedicatedJobRoles.map(r => r.name);
  const untrackedSuggestions = [
    'AI Infrastructure Engineer',
    'MLOps Engineer',
    'Applied AI Scientist',
    'Distributed Systems Architect',
    'Quantum Computing Researcher'
  ].filter(name => !currentRoleNames.includes(name));

  return `
    <div class="ji-modal-backdrop" id="jiAddRoleBackdrop">
      <div class="ji-modal-window" role="dialog" aria-modal="true" aria-label="Add Role to Tracked Collection">
        <div class="ji-modal-header">
          <h3>Track New Role</h3>
          <button type="button" class="ji-modal-close" id="btnCloseAddRoleModal" aria-label="Close modal">
            <i data-lucide="x"></i>
          </button>
        </div>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0 0 16px;">
          Add a role to your monitored portfolio to track hiring velocity, salary benchmarks, and skill graphs.
        </p>

        <div style="margin-bottom: 16px;">
          <label for="jiNewRoleInput" style="display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: var(--ji-muted); margin-bottom: 6px;">
            Role Title
          </label>
          <input
            type="text"
            id="jiNewRoleInput"
            class="ji-query-input"
            style="height: 40px; padding: 0 12px;"
            placeholder="e.g. MLOps Engineer"
          />
        </div>

        <div style="margin-bottom: 20px;">
          <small style="color: var(--ji-muted); font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 8px;">
            Suggested Next-Gen Roles
          </small>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            ${untrackedSuggestions.map(sug => `
              <button type="button" class="ji-evolution-pill" data-action="select-suggested-new-role" data-role="${esc(sug)}">
                <i data-lucide="plus" style="width: 12px; height: 12px;"></i>
                <span>${esc(sug)}</span>
              </button>
            `).join('')}
          </div>
        </div>

        <div style="display: flex; gap: 10px; justify-content: flex-end;">
          <button type="button" class="ji-btn-secondary" id="btnCancelAddRole">Cancel</button>
          <button type="button" class="ji-btn-primary" id="btnConfirmAddRole">Track Role</button>
        </div>
      </div>
    </div>
  `;
}

function renderEvidenceModalHTML() {
  const ev = ui.evidenceModalData;
  if (!ev) return '';

  return `
    <div class="ji-modal-backdrop" id="jiEvidenceModalBackdrop">
      <div class="ji-modal-window" role="dialog" aria-modal="true" aria-label="Evidence Citation Details">
        <div class="ji-modal-header">
          <span class="ji-evidence-badge">${esc(ev.type)}</span>
          <button type="button" class="ji-modal-close" id="btnCloseEvidenceModal" aria-label="Close citation">
            <i data-lucide="x"></i>
          </button>
        </div>
        <h3 style="margin: 0 0 6px; font-size: 18px; color: var(--ji-deep);">${esc(ev.source)}</h3>
        <span style="font-size: 12px; color: var(--ji-muted); display: block; margin-bottom: 16px;">
          Published: ${esc(ev.date)} • Methodology: Core Intelligence market collection
        </span>

        <div style="padding: 16px; background: var(--ji-wash); border-radius: 10px; border: 1px solid var(--ji-border); margin-bottom: 16px;">
          <strong style="color: var(--ji-purple); font-size: 14px; display: block; margin-bottom: 6px;">
            Key Finding
          </strong>
          <p style="margin: 0; font-size: 13.5px; color: var(--ji-ink); line-height: 1.5;">
            "${esc(ev.signal)}"
          </p>
        </div>

        <p style="font-size: 13px; color: var(--ji-muted); line-height: 1.5; margin: 0 0 20px;">
          <strong>Corroboration:</strong> ${esc(ev.supports)}
        </p>

        <div style="display: flex; justify-content: flex-end;">
          <button type="button" class="ji-btn-primary" id="btnDismissEvidence">Close Citation</button>
        </div>
      </div>
    </div>
  `;
}

// ============================================================================
// DYNAMIC HELPER FUNCTIONS
// ============================================================================

function getSuggestedQuestionsForRole(roleName) {
  switch (roleName) {
    case 'AI Engineer':
      return [
        'What skills bridge the gap to Senior AI Engineer?',
        'Which companies are accelerating AI Engineer hiring in Bangalore?',
        'How does AI Engineer demand compare over the last 3 months?',
        'What compensation range is commanded by CUDA specialists?'
      ];
    case 'Machine Learning Engineer':
      return [
        'How does ML Engineer hiring compare between Bangalore and Hyderabad?',
        'What are the critical MLOps requirements across enterprise postings?',
        'What is the salary benchmark for PyTorch and distributed training experts?'
      ];
    case 'Cloud Solutions Architect':
      return [
        'Which cloud certifications command the highest role momentum?',
        'Which tier-1 enterprises are hiring cloud architects right now?',
        'What adjacent skills transition fastest into Cloud Infrastructure?'
      ];
    default:
      return [
        `What are the fastest-growing skills required for ${roleName}?`,
        `Which top employers have open requisitions for ${roleName}?`,
        `What is the projected 6-month demand trajectory for ${roleName}?`
      ];
  }
}

function getScanningStageText(step, roleName) {
  switch (step) {
    case 0:
      return 'Scanning 42,000+ active requisitions...';
    case 1:
      return `Correlating employer hiring velocity and skill requirements for ${roleName}...`;
    case 2:
      return 'Synthesizing career progression pathways and recommendations...';
    default:
      return 'Finalizing intelligence assessment...';
  }
}

// ============================================================================
// EVENT HANDLERS & NAVIGATION INTERACTION
// ============================================================================

function bindEvents() {
  const root = document.getElementById('jobIntelligenceWorkspace');
  if (!root) return;

  // 1. Role Scope Tabs
  root.querySelectorAll('.ji-collection-tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const coll = e.currentTarget.dataset.collection;
      if (coll) {
        ui.collection = coll;
        if (dedicatedJobState) dedicatedJobState.roleScope = coll;
        rerender();
      }
    });
  });

  // 2. Role Search
  const searchInput = root.querySelector('#jiRoleSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      ui.searchQuery = e.target.value;
      rerender({ preserveFocus: 'jiRoleSearchInput' });
    });
  }

  root.querySelector('#jiClearSearchBtn')?.addEventListener('click', () => {
    ui.searchQuery = '';
    rerender({ preserveFocus: 'jiRoleSearchInput' });
  });

  // 3. Filter Popover Toggles
  const filterBtn = root.querySelector('#jiFilterTriggerBtn');
  if (filterBtn) {
    filterBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      ui.filterOpen = !ui.filterOpen;
      rerender();
    });
  }

  const scrim = root.querySelector('#jiFilterScrim');
  const closeFilterBtn = root.querySelector('#btnCloseFilterPopover');
  [scrim, closeFilterBtn].forEach(el => {
    el?.addEventListener('click', () => {
      ui.filterOpen = false;
      rerender();
    });
  });

  // Filter Apply / Reset
  root.querySelector('#btnApplyFilters')?.addEventListener('click', () => {
    const loc = root.querySelector('#jiFilterLocation')?.value;
    const rng = root.querySelector('#jiFilterTimeRange')?.value;
    const cat = root.querySelector('#jiFilterCategory')?.value;
    const typ = root.querySelector('#jiFilterType')?.value;

    if (loc) ui.location = loc;
    if (rng) ui.timeRange = rng;
    if (cat) ui.categoryFilter = cat;
    if (typ) ui.typeFilter = typ;

    ui.filterOpen = false;
    rerender();
  });

  root.querySelector('#btnResetFilters')?.addEventListener('click', () => {
    ui.location = 'Bangalore';
    ui.timeRange = '30D';
    ui.categoryFilter = 'All Categories';
    ui.typeFilter = 'All Types';
    ui.filterOpen = false;
    rerender();
  });

  root.querySelector('#btnResetFiltersAndSearch')?.addEventListener('click', () => {
    ui.searchQuery = '';
    ui.categoryFilter = 'All Categories';
    ui.location = 'Bangalore';
    rerender();
  });

  // 4. Role Selection
  root.querySelectorAll('.ji-role-row').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('[data-action="toggle-fav"]')) return;
      const roleName = item.dataset.role;
      if (roleName) selectRole(roleName);
    });

    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const roleName = item.dataset.role;
        if (roleName) selectRole(roleName);
      }
    });
  });

  // 5. Favorite Toggle
  root.querySelectorAll('[data-action="toggle-fav"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const roleName = btn.dataset.role;
      if (roleName) toggleFavoriteRole(roleName);
    });
  });

  // 6. Signal Mix Item Click
  root.querySelectorAll('[data-action="select-signal"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const sigId = e.currentTarget.dataset.signalId;
      ui.selectedSignalId = ui.selectedSignalId === sigId ? null : sigId;
      rerender();
    });
  });

  root.querySelector('[data-action="close-signal-detail"]')?.addEventListener('click', () => {
    ui.selectedSignalId = null;
    rerender();
  });

  // 7. Navigation into Market Intelligence (Companies)
  root.querySelectorAll('[data-action="navigate-company"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const compName = e.currentTarget.dataset.company;
      if (compName) {
        dashboardState.selectedCompany = compName;
        window.location.hash = '/individual/market-insights';
      }
    });
  });

  // 8. Navigation into Skill Intelligence (Skills)
  root.querySelectorAll('[data-action="navigate-skill"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const skillName = e.currentTarget.dataset.skill;
      if (skillName) {
        dashboardState.selectedSkill = skillName;
        window.location.hash = '/individual/skills';
      }
    });
  });

  // 9. Company Context Chips Toggle
  root.querySelectorAll('[data-action="toggle-company-context"]').forEach(chip => {
    chip.addEventListener('click', (e) => {
      const comp = e.currentTarget.dataset.company;
      if (!comp) return;
      if (ui.selectedCompanyContext.includes(comp)) {
        ui.selectedCompanyContext = ui.selectedCompanyContext.filter(c => c !== comp);
      } else {
        ui.selectedCompanyContext.push(comp);
      }
      if (dedicatedJobState) dedicatedJobState.selectedCompanyContext = ui.selectedCompanyContext;
      rerender();
    });
  });

  // 10. Suggested Questions Click
  root.querySelectorAll('[data-action="select-question"]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      const query = e.currentTarget.dataset.query;
      if (query) {
        ui.queryText = query;
        rerender({ preserveFocus: 'jiConsoleQueryInput' });
        runAnalysis();
      }
    });
  });

  // 11. Console Query Input Enter Key
  const consoleInput = root.querySelector('#jiConsoleQueryInput');
  if (consoleInput) {
    consoleInput.addEventListener('input', (e) => {
      ui.queryText = e.target.value;
    });
    consoleInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        runAnalysis();
      }
    });
  }

  // 12. Run Analysis Button
  root.querySelector('#btnRunJobAnalysis')?.addEventListener('click', () => {
    runAnalysis();
  });

  // 13. Tabs Switch
  root.querySelectorAll('.ji-tab-btn').forEach(tabBtn => {
    tabBtn.addEventListener('click', (e) => {
      const targetTab = e.currentTarget.dataset.tab;
      if (targetTab) {
        ui.activeTab = targetTab;
        if (dedicatedJobState) dedicatedJobState.selectedTab = targetTab;
        rerender();
      }
    });
  });

  // 14. Switch Role (Adjacent Roles or Next Steps)
  root.querySelectorAll('[data-action="switch-role"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const r = e.currentTarget.dataset.role;
      if (r) selectRole(r);
    });
  });

  // 15. Trigger Roadmap Builder (Steps 41, 54, 55, 56)
  root.querySelectorAll('[data-action="trigger-roadmap-builder"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const skill = e.currentTarget.dataset.skill || 'CUDA';
      triggerRoadmapPreview(skill);
    });
  });

  // 16. Save Role Result
  root.querySelector('#btnSaveRoleResult')?.addEventListener('click', () => {
    const role = getSelectedRoleData();
    toggleSaveRole(role.name);
  });

  // 17. Evidence View Modal
  root.querySelectorAll('[data-action="view-evidence"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = Number(e.currentTarget.dataset.evidenceIndex);
      const role = getSelectedRoleData();
      if (role.evidence && role.evidence[idx]) {
        ui.evidenceModalData = role.evidence[idx];
        rerender();
      }
    });
  });

  const closeEvidenceBtn = root.querySelector('#btnCloseEvidenceModal');
  const dismissEvidenceBtn = root.querySelector('#btnDismissEvidence');
  const evidenceBackdrop = root.querySelector('#jiEvidenceModalBackdrop');
  [closeEvidenceBtn, dismissEvidenceBtn, evidenceBackdrop].forEach(el => {
    el?.addEventListener('click', (e) => {
      if (e.target === el) {
        ui.evidenceModalData = null;
        rerender();
      }
    });
  });

  // 18. Add Role Modal
  root.querySelector('#btnOpenAddRoleModal')?.addEventListener('click', () => {
    ui.addModalOpen = true;
    rerender();
  });

  const closeAddRoleBtn = root.querySelector('#btnCloseAddRoleModal');
  const cancelAddRoleBtn = root.querySelector('#btnCancelAddRole');
  const addRoleBackdrop = root.querySelector('#jiAddRoleBackdrop');
  [closeAddRoleBtn, cancelAddRoleBtn, addRoleBackdrop].forEach(el => {
    el?.addEventListener('click', (e) => {
      if (e.target === el) {
        ui.addModalOpen = false;
        rerender();
      }
    });
  });

  root.querySelectorAll('[data-action="select-suggested-new-role"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const name = e.currentTarget.dataset.role;
      const input = root.querySelector('#jiNewRoleInput');
      if (input && name) input.value = name;
    });
  });

  root.querySelector('#btnConfirmAddRole')?.addEventListener('click', () => {
    const input = root.querySelector('#jiNewRoleInput');
    const newName = input ? input.value.trim() : '';
    if (newName) {
      if (!dedicatedJobRoles.some(r => r.name.toLowerCase() === newName.toLowerCase())) {
        dedicatedJobRoles.push({
          id: newName.toLowerCase().replace(/\s+/g, '-'),
          name: newName,
          category: 'AI / ML',
          icon: 'briefcase',
          demandScore: 78,
          growthPercentage: 14.2,
          change: 14.2,
          direction: 'up',
          status: 'Emerging',
          openRoles: 3200,
          hiringCompaniesCount: 210,
          isFavorite: false,
          isMyRole: true,
          experienceLevel: 'Mid',
          averageComp: '₹22L - ₹42L / yr',
          locations: [ui.location, 'Remote'],
          history: [40, 48, 55, 62, 70, 74, 78],
          projection: [80, 83, 86],
          overview: `Specialized role in ${newName} focusing on scalable architecture and enterprise deployment.`,
          responsibilities: [
            `Design and maintain systems for ${newName}.`,
            'Partner with cross-functional teams to integrate services.'
          ],
          evolution: {
            current: ['Python', 'Cloud Computing'],
            emerging: ['Machine Learning', 'Containerization'],
            future: ['Autonomous Pipelines']
          },
          careerProgression: [
            { step: 'Current Profile', title: 'Software Engineer', match: 'Baseline' },
            { step: 'Target Role', title: newName, match: 'Primary Focus' }
          ],
          alignmentFactors: {
            skillAlignment: 'Moderate (Baseline engineering skills align)',
            roleDemand: 'Developing (+14.2% acceleration)',
            experienceFit: 'Strong',
            locationFit: 'Optimal',
            skillGaps: 'Specialized tooling'
          },
          companiesHiring: [
            { name: 'NVIDIA', logoInitials: 'NV', signalText: '+28% Active Hiring', change: 28, dir: 'up', openCount: 120, location: ui.location },
            { name: 'Microsoft', logoInitials: 'MS', signalText: '+15% Active Hiring', change: 15, dir: 'up', openCount: 140, location: ui.location }
          ],
          jobOpportunities: [
            { id: 'job-new-1', company: 'NVIDIA', role: newName, location: ui.location, type: 'Full-time', reqSkills: ['Python', 'Cloud'], posted: '1 day ago', signal: 'New' }
          ],
          requiredSkills: [
            { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Intermediate', notes: 'Core execution layer.' },
            { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Developing', level: 'Intermediate', notes: 'Deployment infra.' }
          ],
          evidence: [
            { source: 'Global Tech Hiring Index (GTHI)', type: 'Workforce Report', date: 'Sep 2026', verified: true, signal: `Emerging requisition volume for ${newName}`, supports: 'Market adoption underway.' }
          ],
          aiInsight: {
            whatChanged: `Demand for ${newName} expanded into the monitored index.`,
            whyItMatters: 'Specialized domain acceleration offers candidate leverage.',
            whatItMeans: 'Skill alignment is achievable within an accelerated horizon.',
            whatYouShouldDo: 'Map immediate learning roadmaps to cover core competencies.',
            recommendations: [
              { type: 'Role Focus', title: `Prepare for ${newName} Requisitions`, desc: 'Explore requirement landscape.', role: newName, primaryAction: 'View Role Details' }
            ]
          }
        });
      }
      selectRole(newName);
      ui.addModalOpen = false;
      rerender();
    }
  });
}

function selectRole(roleName) {
  if (dedicatedJobState) dedicatedJobState.selectedRole = roleName;
  if (dashboardState) dashboardState.selectedRole = roleName;
  rerender();
}

function toggleFavoriteRole(roleName) {
  let favs = [...(dashboardState?.favoriteRoles || [])];
  if (favs.includes(roleName)) {
    favs = favs.filter(r => r !== roleName);
  } else {
    favs.push(roleName);
  }
  dashboardState.favoriteRoles = favs;
  if (dedicatedJobState) dedicatedJobState.favoriteRoles = favs;
  localStorage.setItem('talentscope-favorite-roles', JSON.stringify(favs));
  rerender();
}

function toggleSaveRole(roleName) {
  let saved = [...(dashboardState?.savedRoles || [])];
  if (saved.includes(roleName)) {
    saved = saved.filter(r => r !== roleName);
  } else {
    saved.push(roleName);
  }
  dashboardState.savedRoles = saved;
  if (dedicatedJobState) dedicatedJobState.savedRoles = saved;
  localStorage.setItem('talentscope-saved-roles', JSON.stringify(saved));
  rerender();
}

function triggerRoadmapPreview(skillName) {
  if (dashboardState) dashboardState.selectedSkill = skillName;
  if (roadmapState) roadmapState.skill = skillName;
  if (intelligenceExplorerState) intelligenceExplorerState.isRoadmapPreviewing = true;
  window.location.hash = '/individual/home';
}

async function runAnalysis() {
  ui.isAnalyzing = true;
  ui.jobApiResponse = null;
  ui.jobApiError = null;
  ui.analysisStep = 0;
  rerender();

  const stepInterval = setInterval(() => {
    ui.analysisStep = Math.min(ui.analysisStep + 1, 2);
    rerender();
  }, 450);

  const roleName = dedicatedJobState?.selectedRole || dashboardState?.selectedRole || 'AI Engineer';
  try {
    const res = await queryJobIntelligence({
      portalType: 'individual',
      location: ui.location === 'Global' ? undefined : ui.location,
      timeRange: ({ '7 Days': '7d', '30 Days': '30d', '3 Months': '3m', '6 Months': '6m' })[ui.timeRange] || '30d',
      selectedRoles: [roleName],
      targetRole: roleName,
      query: ui.queryText || undefined
    });
    ui.jobApiResponse = res;
    ui.jobApiError = null;
  } catch (err) {
    ui.jobApiError = err.message || 'Job intelligence could not be loaded.';
  } finally {
    clearInterval(stepInterval);
    ui.isAnalyzing = false;
    ui.hasAnalyzed = true;
    rerender();
    document.querySelector('#jiResultSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function rerender(options = {}) {
  const main = document.getElementById('mainContent');
  if (!main) return;
  main.innerHTML = renderJobIntelligenceHTML();
  window.lucide?.createIcons();
  bindEvents();

  if (options.preserveFocus) {
    const el = document.getElementById(options.preserveFocus);
    if (el) {
      el.focus();
      if (typeof el.selectionStart === 'number') {
        el.selectionStart = el.selectionEnd = el.value.length;
      }
    }
  }
}

function tickSimulation() {
  ui.simTick++;
  const role = getSelectedRoleData();
  if (role && role.history) {
    const drift = Math.sin(ui.simTick * 0.8) * 0.35;
    const lastIdx = role.history.length - 1;
    role.history[lastIdx] = clamp(Math.round(role.history[lastIdx] + drift), 50, 99);
  }
  const badge = document.querySelector('.job-intelligence-page .ji-demo-badge');
  if (badge) {
    badge.classList.add('is-pulsing');
    setTimeout(() => badge.classList.remove('is-pulsing'), 600);
  }
}

// ============================================================================
// EXPORT ENTRY POINTS
// ============================================================================

export function renderDedicatedJobPage() {
  if (simTimer) clearInterval(simTimer);
  const main = document.getElementById('mainContent');
  if (!main) return;
  main.innerHTML = renderJobIntelligenceHTML();
  window.lucide?.createIcons();
  bindEvents();
  simTimer = window.setInterval(tickSimulation, 4200);
}

// Retain alias for existing imports / router references
export function renderCareerPage() {
  return renderDedicatedJobPage();
}
