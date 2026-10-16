import { loadMySkills, loadSkillIntelligence, saveFavouriteSkillIds, saveMySkills } from './skills-api.js';
import { formatObservationPeriod, loadSkillCatalog } from '../../../api/intelligence-catalog-client.js';
import { paginateCatalog } from '../../../utils/catalog-pagination.js';
import { getSkillTrendSummary, sortCatalogByName } from '../../../utils/skill-catalog.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);

const LEVELS = ['Beginner', 'Comfortable', 'Advanced', 'Expert'];
const RANGES = [
  ['7d', '7 Days'],
  ['30d', '30 Days'],
  ['3m', '3 Months'],
  ['6m', '6 Months'],
  ['custom', 'Custom (7–184 days)']
];

let pageState = {
  skillsStatus: 'loading',
  skills: [],
  catalog: null,
  catalogStatus: 'loading',
  catalogError: '',
  catalogQuery: '',
  catalogSort: 'name',
  catalogView: 'all',
  catalogPage: 1,
  favoriteSkillIds: [],
  favoriteSaving: false,
  intelligenceStatus: 'loading',
  intelligence: null,
  profileUpdatedAt: null,
  error: '',
  location: '',
  range: '6m',
  days: 30,
  selectedSkill: '',
  consoleSkills: [],
  consoleQuery: '',
  consoleResult: '',
  consoleStatus: '',
  filtersOpen: false,
  busy: false
};
let requestId = 0;
let analysisRequestId = 0;

function skillIcon(name) {
  const normalized = name.toLowerCase();
  if (normalized.includes('python') || normalized.includes('java')) return 'code-2';
  if (normalized.includes('cloud')) return 'cloud';
  if (normalized.includes('data') || normalized.includes('machine learning')) return 'brain-circuit';
  if (normalized.includes('security')) return 'shield-check';
  if (normalized.includes('sql') || normalized.includes('database')) return 'database';
  return 'sparkles';
}

function catalogSearchMatches(item, query) {
  if (!query) return true;
  return [
    item.name,
    item.category,
    ...(Array.isArray(item.aliases) ? item.aliases : [])
  ].some(value => String(value || '').toLocaleLowerCase().includes(query));
}

function loadStatusCopy() {
  if (pageState.intelligenceStatus === 'error') {
    return 'Unable to load market intelligence. Please try again.';
  }
  if (pageState.intelligence?.data_state === 'incomplete_history'
    || pageState.intelligence?.history_complete === false) {
    return pageState.intelligence.history_completeness_reason
      || 'Observation history is incomplete; trend and forecast results are withheld.';
  }
  const status = pageState.intelligence?.data_status;
  if (status === 'pending_source_data') return 'Market trend data is not available yet.';
  if (status === 'insufficient_data') {
    return 'Not enough historical market data to calculate a reliable trend.';
  }
  if (status === 'error') {
    return pageState.intelligence.error_message || 'Unable to load market intelligence. Please try again.';
  }
  if (pageState.intelligenceStatus === 'loading') return 'Loading market intelligence...';
  return '';
}

function emptyMarketMarkup() {
  const text = loadStatusCopy();
  if (!text) return '';
  const retry = pageState.intelligenceStatus === 'error' || pageState.intelligence?.data_status === 'error';
  return `<div class="si-market-empty" role="status">
    <i data-lucide="${retry ? 'triangle-alert' : 'chart-no-axes-combined'}"></i>
    <p>${esc(text)}</p>
    ${retry ? '<button type="button" class="si-button si-button--quiet" data-action="retry">Try again</button>' : ''}
  </div>`;
}

function trendChartMarkup(trends) {
  const usableTrends = trends.filter(item =>
    item.is_trend_ready && Array.isArray(item.series) && item.series.length > 1
  );
  if (!usableTrends.length) {
    return '<div class="si-market-empty" role="status"><p>Market data is marked available, but no trend series were returned.</p></div>';
  }

  const values = usableTrends.flatMap(item => item.series.map(point => point.value));
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const width = 600;
  const height = 180;
  const periodKeys = [...new Set(usableTrends.flatMap(item => item.series.map(point => point.period)))]
    .sort();
  const lineMarkup = usableTrends.map((item, index) => {
    const points = item.series.map(point => {
      const x = 24 + periodKeys.indexOf(point.period) / Math.max(1, periodKeys.length - 1) * (width - 48);
      const y = height - 16 - ((point.value - minimum) / span) * (height - 32);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return `<polyline class="si-data-trend si-data-trend--${index % 5}" points="${points}"></polyline>`;
  }).join('');
  const periods = periodKeys.map(period => `<span>${esc(period)}</span>`).join('');

  return `<div class="si-data-chart" role="img" aria-label="Market demand trend values supplied by the intelligence service">
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      ${lineMarkup}
    </svg>
    <div class="si-data-chart-periods">${periods}</div>
    <p>Market demand / momentum · values supplied by the intelligence service</p>
  </div>`;
}

function trendingSkillsMarkup() {
  const items = (pageState.intelligence?.personal_top_skills || []).filter(item => item.is_trend_ready);
  if (pageState.intelligence?.data_status !== 'available') return emptyMarketMarkup();
  if (!items.length) {
    return '<div class="si-market-empty" role="status"><p>No ranked market skills are available.</p></div>';
  }
  return `<ol class="si-trending-list">${items.slice(0, 5).map((item, index) => `
    <li class="si-trending-row">
      <span class="si-trending-rank">${String(index + 1).padStart(2, '0')}</span>
      <span><strong>${esc(item.skill)}</strong>${item.category ? `<small>${esc(item.category)}</small>` : ''}</span>
      <span>${item.trend ? esc(item.trend) : '—'}</span>
      <span>${item.growth_pct == null ? '—' : `${esc(item.growth_pct)}%`}</span>
    </li>
  `).join('')}</ol>`;
}

function skillRowsMarkup() {
  if (pageState.skillsStatus === 'loading') {
    return '<div class="si-empty" role="status"><p>Loading your saved skills...</p></div>';
  }
  if (pageState.skillsStatus === 'error') {
    return `<div class="si-empty" role="alert"><p>${esc(pageState.error)}</p>
      <button type="button" class="si-button si-button--quiet" data-action="retry">Try again</button></div>`;
  }
  if (!pageState.skills.length) {
    return '<div class="si-empty" role="status"><i data-lucide="inbox"></i><p>No skills have been selected yet.</p><a href="#si-add-skill-name">Add skills to your profile</a></div>';
  }
  return pageState.skills.map(item => `
    <div class="si-skill-row-wrap">
      <button type="button" class="si-skill-row ${item.name === pageState.selectedSkill ? 'is-active' : ''}"
        data-skill="${esc(item.name)}" aria-pressed="${item.name === pageState.selectedSkill}">
        <span class="si-skill-icon"><i data-lucide="${skillIcon(item.name)}"></i></span>
        <span class="si-row-name"><strong>${esc(item.name)}</strong><small>Onboarding profile</small></span>
        <span class="si-row-trend">${esc(item.level || 'Level not set')}</span>
        <span class="si-row-level" aria-hidden="true"></span>
      </button>
      <button type="button" class="si-row-unfavorite" data-action="remove-skill" data-skill="${esc(item.name)}"
        aria-label="Remove ${esc(item.name)} from My Skills"><i data-lucide="trash-2"></i></button>
    </div>
  `).join('');
}

function catalogOverviewMarkup() {
  const catalog = pageState.catalog;
  const skills = Array.isArray(catalog?.skills) ? catalog.skills : [];
  const query = pageState.catalogQuery.trim().toLocaleLowerCase();
  const queryMatches = skills.filter(item => catalogSearchMatches(item, query));
  const observed = queryMatches.filter(item => item.status === 'observed');
  const referenceOnly = queryMatches.filter(item => item.status === 'reference_only');
  const profileEntries = catalog?.my_skills || [];
  const profileFor = item => profileEntries.find(profile => {
    const name = String(profile.name || '').trim().toLocaleLowerCase();
    return name === item.name.toLocaleLowerCase() || (item.aliases || []).some(alias => String(alias).toLocaleLowerCase() === name);
  });
  const mySkillIds = new Set(skills.filter(item => profileFor(item)).map(item => item.skill_id));
  const viewRows = pageState.catalogView === 'favorites'
    ? queryMatches.filter(item => pageState.favoriteSkillIds.includes(item.skill_id))
    : pageState.catalogView === 'trend_ready' ? queryMatches.filter(item => item.analysis_readiness?.trend_ready || item.trend_available)
    : pageState.catalogView === 'reference' ? referenceOnly
    : pageState.catalogView === 'my_skills' ? queryMatches.filter(item => mySkillIds.has(item.skill_id))
    : pageState.catalogView === 'observed' ? observed : queryMatches;
  const rows = sortCatalogByName(viewRows);
  const page = paginateCatalog(rows, pageState.catalogPage);
  pageState.catalogPage = page.page;
  if (pageState.catalogStatus === 'loading') return '<section class="si-catalog" role="status"><p>Loading supported skills and observed signals?</p></section>';
  if (pageState.catalogStatus === 'error') return `<section class="si-catalog" role="alert"><p>${esc(pageState.catalogError)}</p></section>`;
  const rowMarkup = page.items.map(item => {
    const profileSkill = profileFor(item);
    const github = item.developer_activity || [];
    const summary = getSkillTrendSummary(item);
    const latest = item.latest || github.map(series => series.latest).filter(Boolean).sort((a, b) => String(b.period).localeCompare(String(a.period)))[0];
    const analysis = item.analysis_readiness || {};
    const health = analysis.skill_health || {};
    const halfLife = analysis.half_life || {};
    const forecast = analysis.forecast || {};
    const isFavourite = pageState.favoriteSkillIds.includes(item.skill_id);
    const source = `${summary.source || item.latest?.source || (item.status === 'reference_only' ? 'Reference only' : 'Observed')}${item.provider_data_state === 'stale' ? ' · stale' : ''}`;
    const period = summary.period || latest?.period || '';
    const directionIcons = {
      Rising: 'trending-up',
      Falling: 'trending-down',
      Stable: 'minus',
      Mixed: 'arrow-left-right',
      Unavailable: 'circle-help'
    };
    const directionClass = summary.direction.toLowerCase();
    const trendLabel = item.status === 'reference_only' && !github.length && !item.trend_available
      ? 'Reference only'
      : summary.direction;
    const trendDetail = summary.latestChange == null
      ? ''
      : `<small>Latest period: ${summary.latestChange > 0 ? '+' : ''}${esc(summary.latestChange)} ${esc(summary.unit || '')}</small>`;
    const velocityEvidence = summary.velocity == null
      ? `${esc(analysis.velocity?.status || 'insufficient_history')} · ${esc(analysis.velocity?.reason || 'No eligible rate.')}`
      : `${esc(summary.velocityMetric || analysis.velocity?.unit || 'Rate of change')}: ${esc(summary.velocity)}`;
    const githubEvidence = github.map(series => `<li><strong>${esc(series.label)}</strong>: ${esc(series.metric)} · ${esc(series.period_grain)} (${esc(series.unit)}) · India · local SQLite · latest ${esc(series.latest?.period || '—')}: ${esc(series.latest?.value ?? 'unavailable')} ${esc(series.unit)} · full-window ${esc(series.trend_direction)} · periods ${esc(series.dataset_period_range || 'unavailable')}${series.velocity_per_quarter == null ? '' : ` · ${esc(series.velocity_metric)}: ${esc(series.velocity_per_quarter)}`}${series.period_over_period_change == null ? '' : ` · latest comparable-period change ${series.period_over_period_change > 0 ? '+' : ''}${esc(series.period_over_period_change)}`}${series.trend_unavailable_reason ? ` · ${esc(series.trend_unavailable_reason)}` : ''}${series.stale_reason ? ` · ${esc(series.stale_reason)}` : ''}</li>`).join('');
    const evidence = `<details class="si-catalog-evidence"><summary>Evidence</summary><div>${item.latest ? `<p>${esc(item.latest.source)} · ${esc(item.latest.signal_label || item.latest.signal_type)} · ${esc(item.latest.metric)} · ${esc(item.latest.unit)} · ${esc(item.latest.period)}${item.latest.denominator == null ? '' : ` · denominator ${esc(item.latest.denominator)}`}</p>` : ''}${githubEvidence ? `<ul>${githubEvidence}</ul>` : ''}<p>Trend: ${esc(analysis.trend?.reason || summary.unavailableReason || (summary.direction === 'Unavailable' ? 'No eligible time series.' : `Full-window ${summary.direction.toLowerCase()} trend.`))}</p><p>Velocity: ${velocityEvidence}</p><p>Period-over-period change: ${esc(analysis.period_over_period_change?.status || 'insufficient_history')} · ${esc(analysis.period_over_period_change?.reason || 'No comparable complete periods.')}</p><p>Skill Health: ${esc(health.category || 'insufficient_data')} · ${esc(health.reason || 'No eligible evidence.')}</p><p>Half-Life: ${halfLife.eligible ? 'eligible' : 'not eligible'} · ${esc(halfLife.reason || 'No valid eligible half-life series.')}</p><p>Forecast: ${forecast.eligible ? `eligible · ${esc(forecast.target || '')} · ${esc(forecast.period || '')}` : `not eligible · ${esc(forecast.reason || 'No eligible forecast series.')}`}</p><p>Canonical ID: ${esc(item.skill_id)}${profileSkill?.level ? ` · My Skills proficiency: ${esc(profileSkill.level)}` : ''}${item.reference_sources?.length ? ` · Reference: ${esc(item.reference_sources.join(', '))}` : ''}</p></div></details>`;
    return `<tr><td class="si-catalog-skill"><strong title="${esc(item.name)}">${esc(item.name)}</strong>${pageState.catalogView === 'my_skills' && profileSkill?.level ? `<small>${esc(profileSkill.level)}</small>` : ''}${evidence}</td><td class="si-catalog-source" title="${esc(source)}">${esc(source)}</td><td title="${esc(period)}">${esc(period || '—')}</td><td><span class="si-catalog-trend si-catalog-trend--${directionClass}" aria-label="${esc(trendLabel)}"><i data-lucide="${directionIcons[summary.direction]}"></i><span>${esc(trendLabel)}</span></span>${trendDetail}</td><td><button type="button" class="si-catalog-star ${isFavourite ? 'is-favourite' : ''}" data-action="toggle-favourite" data-skill-id="${esc(item.skill_id)}" aria-pressed="${isFavourite}" aria-label="${isFavourite ? 'Remove' : 'Add'} ${esc(item.name)} ${isFavourite ? 'from' : 'to'} favourites" ${pageState.favoriteSaving ? 'disabled' : ''}><i data-lucide="star"></i></button></td></tr>`;
  }).join('');
  return `<section class="si-catalog" aria-labelledby="si-catalog-title">
    <header><div><span class="si-kicker">SUPPORTED DATA CATALOG</span><h2 id="si-catalog-title">${pageState.catalogView === 'favorites' ? 'Favourite skills' : pageState.catalogView === 'my_skills' ? 'My profile skills' : pageState.catalogView === 'trend_ready' ? 'Trend-ready skills' : pageState.catalogView === 'reference' ? 'Reference skills' : pageState.catalogView === 'observed' ? 'Observed skill signals' : 'All supported skills'}</h2><p>Local taxonomy references are separate from dated market observations. GitHub Innovation Graph values describe developer activity, not job demand, and remain quarterly.</p></div></header>
    ${pageState.catalogError ? `<p class="si-catalog-error" role="alert">${esc(pageState.catalogError)}</p>` : ''}
    <div class="si-catalog-metrics"><div><strong>${catalog?.counts?.total_unique ?? skills.length}</strong><span>Unique skills</span></div><div><strong>${catalog?.counts?.observed ?? observed.length}</strong><span>Observed</span></div><div><strong>${catalog?.counts?.reference_only ?? skills.length - observed.length}</strong><span>Reference only</span></div><div><strong>${catalog?.counts?.trend_ready ?? catalog?.counts?.with_historical_market_trend ?? catalog?.counts?.historical_trends ?? 0}</strong><span>Trend ready</span></div><div><strong>${catalog?.counts?.with_local_quarterly_developer_history ?? 0}</strong><span>With local GitHub history</span></div></div>
    <div class="si-catalog-controls"><label>Catalog view<select data-catalog-view><option value="all" ${pageState.catalogView === 'all' ? 'selected' : ''}>All supported skills</option><option value="observed" ${pageState.catalogView === 'observed' ? 'selected' : ''}>Observed skills</option><option value="trend_ready" ${pageState.catalogView === 'trend_ready' ? 'selected' : ''}>Trend-ready skills</option><option value="reference" ${pageState.catalogView === 'reference' ? 'selected' : ''}>Reference only (${catalog?.counts?.reference_only ?? referenceOnly.length})</option><option value="favorites" ${pageState.catalogView === 'favorites' ? 'selected' : ''}>Favourites (${pageState.favoriteSkillIds.length})</option><option value="my_skills" ${pageState.catalogView === 'my_skills' ? 'selected' : ''}>My Skills (${(catalog?.my_skills || []).length})</option></select></label><label>Search supported skills<input type="search" data-catalog-search value="${esc(pageState.catalogQuery)}" placeholder="Find by skill, alias, or category" /></label><span class="si-catalog-sort-note">Sorted A–Z by canonical skill name</span></div>
    ${page.items.length ? `<div class="si-catalog-table-wrap"><table class="si-catalog-table"><thead><tr><th>Skill</th><th>Source</th><th>Latest period</th><th>Trend</th><th scope="col" title="Save this skill to your favourites">Favourite</th></tr></thead><tbody>${rowMarkup}</tbody></table></div><div class="si-catalog-pagination" aria-label="Skill catalog pagination"><span>${page.start}–${page.end} of ${page.total}</span><div><button type="button" data-catalog-page="previous" ${page.page <= 1 ? 'disabled' : ''}>Previous</button><span>Page ${page.page} of ${page.pageCount}</span><button type="button" data-catalog-page="next" ${page.page >= page.pageCount ? 'disabled' : ''}>Next</button></div></div>` : `<p class="si-catalog-empty">${pageState.catalogView === 'favorites' ? 'You have no favourite skills yet.' : pageState.catalogView === 'my_skills' ? 'No profile skills are saved yet. Add skills to your profile below.' : pageState.catalogView === 'reference' ? 'No reference-only skills match this search.' : 'No skills match this search.'}</p>`}
    <p class="si-catalog-foot">Firestore observation coverage: ${esc(catalog?.coverage?.first_period || 'unavailable')} ? ${esc(catalog?.coverage?.latest_period || 'unavailable')}. Local O*NET/ESCO taxonomies and GitHub developer activity are not Firestore market observations.</p>
  </section>`;
}
function consoleQuestions(skill) {
  if (!skill) return [];
  return [
    `Why is ${skill} demand changing?`,
    `Where is ${skill} demand growing?`,
    `How relevant is ${skill} to my career?`,
    `Which companies are using ${skill}?`,
    `What skills are adjacent to ${skill}?`,
    'What should I learn next?'
  ];
}

function skillConsoleMarkup() {
  const selectedSkills = pageState.skills.filter(skill =>
    pageState.consoleSkills.includes(skill.name)
  );
  const activeSkill = selectedSkills.find(skill => skill.name === pageState.selectedSkill)
    || selectedSkills[0];
  const questionList = consoleQuestions(activeSkill?.name);

  return `<section class="si-console" aria-labelledby="si-console-title">
    <header>
      <div>
        <span class="si-kicker">SKILL INTELLIGENCE CONSOLE</span>
        <h2 id="si-console-title">What do you want to understand about a skill?</h2>
        <p>Explore demand, relevance, health and evidence in one intelligence workspace.</p>
      </div>
      <button class="si-filter-trigger" type="button" data-action="toggle-filters"
        aria-expanded="${pageState.filtersOpen}">
        <i data-lucide="sliders-horizontal"></i> Filters
      </button>
      ${pageState.filtersOpen ? `<form class="si-filter-pop" data-form="console-filters">
        <div class="si-filter-head">
          <div><small>INTELLIGENCE FILTERS</small><strong>Choose your context</strong></div>
          <button class="si-icon-button" type="button" data-action="close-filters" aria-label="Close filters">
            <i data-lucide="x"></i>
          </button>
        </div>
        <div class="si-filter-body">
          <label>Location
            <input name="location" value="${esc(pageState.location)}" maxlength="160" placeholder="Use profile location">
          </label>
          <label>Time range
            <select name="range">${RANGES.map(([value, label]) =>
              `<option value="${value}" ${value === pageState.range ? 'selected' : ''}>${label}</option>`
            ).join('')}</select>
          </label>
          ${pageState.range === 'custom' ? `<label>Custom days<input name="days" type="number" min="7" max="184" step="1" required value="${pageState.days}"></label>` : ''}
          ${pageState.skills.length ? `<fieldset class="si-console-skill-options">
            <legend>Skills in this console</legend>
            ${pageState.skills.map(skill => `<label>
              <input type="checkbox" name="consoleSkill" value="${esc(skill.name)}"
                ${pageState.consoleSkills.includes(skill.name) ? 'checked' : ''}>
              <span>${esc(skill.name)}</span>
            </label>`).join('')}
          </fieldset>` : '<p>No saved skills to select.</p>'}
        </div>
        <footer><button class="si-button si-button--primary" type="submit">Apply filters</button></footer>
      </form>` : ''}
    </header>
    <div class="si-quick-context">
      <span class="si-quick-label">Selected skills</span>
      ${selectedSkills.length ? selectedSkills.map(skill => `<span class="si-quick-chip ${skill.name === activeSkill?.name ? 'is-active' : ''}">
        <button type="button" data-action="select-console-skill" data-skill="${esc(skill.name)}"
          aria-pressed="${skill.name === activeSkill?.name}">
          <i data-lucide="${skillIcon(skill.name)}"></i>${esc(skill.name)}
        </button>
        <button class="si-quick-remove" type="button" data-action="remove-console-skill"
          data-skill="${esc(skill.name)}" aria-label="Remove ${esc(skill.name)} from this console">×</button>
      </span>`).join('') : `<span class="si-console-empty" role="status">${
        pageState.skillsStatus === 'loading'
          ? 'Loading your saved skills...'
          : pageState.skillsStatus === 'error'
            ? esc(pageState.error)
            : 'No skills have been selected yet.'
      }</span>`}
    </div>
    <form class="si-console-composer" data-form="analysis">
      <div class="si-query-wrap">
        <i data-lucide="search"></i>
        <input name="question" value="${esc(pageState.consoleQuery)}"
          placeholder="${activeSkill ? `Ask anything about ${esc(activeSkill.name)}...` : 'Select a saved skill to begin...'}"
          autocomplete="off" ${!selectedSkills.length || pageState.skillsStatus !== 'loaded' ? 'disabled' : ''}>
        <button class="si-analyze-button" type="submit"
          ${pageState.intelligenceStatus === 'loading' || !selectedSkills.length || pageState.skillsStatus !== 'loaded' ? 'disabled' : ''}>
          <i data-lucide="sparkles"></i> Analyze skill
        </button>
      </div>
      <div class="si-suggestions">
        <span>Questions</span>
        ${questionList.map(question => `<button type="button" data-action="use-console-question"
          data-question="${esc(question)}">${esc(question)}</button>`).join('')}
      </div>
    </form>
    ${pageState.consoleResult ? `<div class="si-console-result" role="${pageState.consoleStatus === 'error' ? 'alert' : 'status'}">
      ${esc(pageState.consoleResult)}
    </div>` : ''}
  </section>`;
}

function renderPage() {
  const main = document.getElementById('mainContent');
  const route = window.location.hash.slice(1).split('?')[0];
  if (!main || !route.startsWith('/individual/skills')) return;

  const currentLocation = pageState.location || pageState.intelligence?.filters?.location || '';
  const selectedSkill = pageState.skills.find(item => item.name === pageState.selectedSkill);
  const currentMarketStatus = loadStatusCopy();
  main.innerHTML = `
    <div class="skill-intelligence-page" aria-labelledby="si-page-title">
      <header class="si-page-heading">
        <div>
          <span class="si-kicker">SKILL FORECAST TELEMETRY</span>
          <h1 id="si-page-title">Skill Intelligence</h1>
          <p>Market demand trends and momentum across your saved skills.</p>
        </div>
        <form class="si-page-filters" data-form="filters">
          <label>Location
            <input name="location" value="${esc(currentLocation)}" placeholder="Use profile location" maxlength="160">
          </label>
          <label>Time range
            <select name="range">${RANGES.map(([value, label]) =>
              `<option value="${value}" ${value === pageState.range ? 'selected' : ''}>${label}</option>`
            ).join('')}</select>
          </label>
          ${pageState.range === 'custom' ? `<label>Custom days<input name="days" type="number" min="7" max="184" step="1" required value="${pageState.days}"></label>` : ''}
          <button class="si-button si-button--primary" type="submit" ${pageState.busy ? 'disabled' : ''}>Apply</button>
        </form>
      </header>

      ${catalogOverviewMarkup()}

      ${skillConsoleMarkup()}

      <section class="si-workspace" aria-label="My skills and market intelligence">
        <section class="si-collection">
          <header class="si-section-heading">
            <div><span class="si-kicker">MY SKILLS</span><h2>Your saved profile skills</h2></div>
            <span class="si-profile-updated">${pageState.profileUpdatedAt
              ? `Updated ${esc(new Date(pageState.profileUpdatedAt).toLocaleDateString())}`
              : ''}</span>
          </header>
          <div class="si-skill-list" aria-live="polite">${skillRowsMarkup()}</div>
          <form class="si-add-skill-form" data-form="add-skill">
            <label for="si-add-skill-name">Add a skill to your profile</label>
            <div>
              <input id="si-add-skill-name" name="name" maxlength="160" required placeholder="Enter a skill name">
              <select name="level" aria-label="Skill level">
                <option value="">Level not set</option>
                ${LEVELS.map(level => `<option value="${level}">${level}</option>`).join('')}
              </select>
              <button class="si-button si-button--primary" type="submit" ${pageState.busy ? 'disabled' : ''}>Add skill</button>
            </div>
          </form>
          ${pageState.busy ? '<p class="si-save-status" role="status">Saving your profile skills...</p>' : ''}
        </section>

        <aside class="si-monitor">
          <div class="si-monitor-head">
            <div>
              <span class="si-kicker">MARKET TREND</span>
              <h3>${esc(selectedSkill?.name || 'Skill Intelligence')}</h3>
              <span class="si-monitor-meta">${selectedSkill
                ? `Your proficiency: ${esc(selectedSkill.level || 'Not set')}`
                : 'Market intelligence for your selected skills'}</span>
            </div>
          </div>
          <div class="si-market-panels">
            ${pageState.intelligence?.answer ? `
              <div class="si-card" style="background: var(--surface-subtle, #F8FAFC); border: 1px solid var(--border-subtle, #E2E8F0); border-radius: 8px; padding: 12px; margin-bottom: 12px; font-size: 12.5px;">
                <div style="font-weight: 700; color: var(--primary, #2563EB); margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
                  <span>${esc(pageState.intelligence.answer.headline)}</span>
                  <span style="font-size: 10px; padding: 2px 6px; background: #EEF2FF; border-radius: 4px; color: #4F46E5;">${esc(pageState.intelligence.answer.contextual_focus || 'Personal Learning')}</span>
                </div>
                <p style="margin: 0 0 6px 0; color: var(--text-secondary, #475569); line-height: 1.4;">${esc(pageState.intelligence.answer.summary)}</p>
                ${pageState.intelligence.answer.key_insights?.length ? `
                  <ul style="margin: 0 0 6px 16px; padding: 0; font-size: 11.5px; color: var(--text-muted, #64748B); line-height: 1.4;">
                    ${pageState.intelligence.answer.key_insights.map(ki => `<li>${esc(ki)}</li>`).join('')}
                  </ul>
                ` : ''}
                ${pageState.intelligence.answer.limitations?.length ? `
                  <div style="font-size: 11px; color: var(--text-muted, #64748B); border-top: 1px dashed #CBD5E1; padding-top: 4px; margin-top: 4px;">
                    <strong>Limitations:</strong> ${pageState.intelligence.answer.limitations.map(l => esc(l)).join(' ')}
                  </div>
                ` : ''}
              </div>
            ` : ''}
                  ${renderIntelligenceEvidencePanel(pageState.intelligenceStatus === 'loading' ? null : pageState.intelligence, {
                    title: 'Skill intelligence evidence',
                    loading: pageState.intelligenceStatus === 'loading',
                    error: pageState.intelligenceStatus === 'error' ? pageState.error : null
                  })}
                  <section aria-labelledby="si-trend-title">
              <h4 id="si-trend-title">Overall Top 5 Skill Trends</h4>
              <p>Comparative momentum trajectory</p>
              ${pageState.intelligenceStatus === 'loading' ? '<div class="si-market-empty" role="status"><p>Loading skill intelligence...</p></div>' : ''}
              ${pageState.intelligence?.data_status === 'available'
                        ? trendChartMarkup(pageState.intelligence.personal_top_skills || [])
                : pageState.intelligenceStatus === 'loading' ? '' : emptyMarketMarkup()}
            </section>
            <section aria-labelledby="si-trending-title">
              <h4 id="si-trending-title">Top 5 Trending Skills</h4>
              <p>Ranked by available market momentum</p>
              ${trendingSkillsMarkup()}
            </section>
          </div>
          ${currentMarketStatus && pageState.skills.length
            ? `<p class="si-monitor-note" role="status">${esc(currentMarketStatus)}</p>` : ''}
        </aside>
      </section>
    </div>
  `;

  window.lucide?.createIcons();
  bindPageEvents(main);
}

function renderError(error) {
  pageState.skillsStatus = 'error';
  pageState.intelligenceStatus = 'error';
  pageState.error = error.message || 'Unable to load market intelligence. Please try again.';
  renderPage();
}

async function refreshData({ location = pageState.location, range = pageState.range, days = pageState.days } = {}) {
  const currentRequest = ++requestId;
  pageState.location = location;
  pageState.range = range;
  pageState.days = days;
  pageState.skillsStatus = 'loading';
  pageState.intelligenceStatus = 'loading';
  pageState.error = '';
  renderPage();

  try {
    const skillsResponse = await loadMySkills();
    if (currentRequest !== requestId) return;

    pageState.skills = Array.isArray(skillsResponse.skills) ? skillsResponse.skills : [];
    pageState.profileUpdatedAt = skillsResponse.profile_updated_at || null;
    pageState.skillsStatus = 'loaded';
    if (!pageState.skills.some(item => item.name === pageState.selectedSkill)) {
      pageState.selectedSkill = pageState.skills[0]?.name || '';
    }
    const savedNames = pageState.skills.map(item => item.name);
    pageState.consoleSkills = pageState.consoleSkills.filter(name => savedNames.includes(name));
    if (!pageState.consoleSkills.length) pageState.consoleSkills = [...savedNames];
    if (!pageState.consoleSkills.includes(pageState.selectedSkill)) {
      pageState.selectedSkill = pageState.consoleSkills[0] || '';
    }
    const intelligence = await loadSkillIntelligence({
      location: location || undefined,
      range,
      days: range === 'custom' ? days : undefined,
      skill: pageState.selectedSkill || undefined
    });
    if (currentRequest !== requestId) return;
    pageState.intelligence = intelligence;
    pageState.location = location || intelligence.filters?.location || '';
    pageState.intelligenceStatus = 'loaded';
    pageState.consoleResult = '';
    pageState.consoleStatus = '';
    renderPage();
  } catch (error) {
    if (currentRequest !== requestId) return;
    renderError(error);
  }
}

async function persistSkills(skills) {
  pageState.busy = true;
  renderPage();
  try {
    const result = await saveMySkills(skills);
    pageState.skills = result.skills;
    pageState.consoleSkills = result.skills.map(skill => skill.name);
    pageState.profileUpdatedAt = result.profile_updated_at || null;
    pageState.skillsStatus = 'loaded';
    pageState.busy = false;
    window.dispatchEvent(new Event('talentscope:skills-updated'));
    await refreshData();
  } catch (error) {
    pageState.busy = false;
    pageState.error = error.message || 'Your skills could not be saved. Please try again.';
    pageState.skillsStatus = 'error';
    renderPage();
  }
}

function bindPageEvents(root) {
  if (!root.dataset.skillPageEventsBound) {
    root.dataset.skillPageEventsBound = 'true';
    root.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button) return;
      if (button.dataset.action === 'toggle-filters') {
        pageState.filtersOpen = !pageState.filtersOpen;
        renderPage();
        return;
      }
      if (button.dataset.action === 'close-filters') {
        pageState.filtersOpen = false;
        renderPage();
        return;
      }
      if (button.dataset.action === 'select-console-skill') {
        pageState.selectedSkill = button.dataset.skill;
        pageState.consoleResult = '';
        renderPage();
        return;
      }
      if (button.dataset.action === 'remove-console-skill') {
        pageState.consoleSkills = pageState.consoleSkills.filter(name => name !== button.dataset.skill);
        if (pageState.selectedSkill === button.dataset.skill) {
          pageState.selectedSkill = pageState.consoleSkills[0] || '';
        }
        pageState.consoleResult = '';
        renderPage();
        return;
      }
      if (button.dataset.action === 'use-console-question') {
        pageState.consoleQuery = button.dataset.question || '';
        renderPage();
        root.querySelector('[name="question"]')?.focus();
        return;
      }
      if (button.dataset.action === 'retry') {
        refreshData({ location: pageState.location, range: pageState.range });
        return;
      }
      if (button.dataset.action === 'toggle-favourite') {
        if (pageState.favoriteSaving) return;
        const skillId = button.dataset.skillId;
        const previousIds = pageState.favoriteSkillIds;
        const next = pageState.favoriteSkillIds.includes(skillId)
          ? pageState.favoriteSkillIds.filter(id => id !== skillId)
          : [...pageState.favoriteSkillIds, skillId];
        pageState.favoriteSkillIds = next;
        pageState.favoriteSaving = true;
        renderPage();
        saveFavouriteSkillIds(next).then(result => {
          pageState.favoriteSkillIds = result.skill_ids || [];
          pageState.catalogError = '';
          window.dispatchEvent(new CustomEvent('talentscope:favourites-updated', {
            detail: { domain: 'skill', skill_ids: pageState.favoriteSkillIds }
          }));
        }).catch(error => {
          pageState.favoriteSkillIds = previousIds;
          pageState.catalogError = error.message || 'Your favourite could not be saved.';
        }).finally(() => {
          pageState.favoriteSaving = false;
          renderPage();
        });
        return;
      }
      if (button.dataset.catalogPage) {
        pageState.catalogPage += button.dataset.catalogPage === 'next' ? 1 : -1;
        renderPage();
        return;
      }
      if (button.dataset.action === 'remove-skill') {
        const target = button.dataset.skill;
        persistSkills(pageState.skills.filter(item => item.name !== target));
        if (target === pageState.selectedSkill) {
          pageState.selectedSkill = pageState.skills.find(item => item.name !== target)?.name || '';
        }
        return;
      }
      if (button.dataset.skill) {
        pageState.selectedSkill = button.dataset.skill;
        refreshData({ location: pageState.location, range: pageState.range });
      }
    });
    root.addEventListener('change', event => {
      if (event.target.matches('[data-catalog-sort]')) {
        pageState.catalogSort = event.target.value;
        pageState.catalogPage = 1;
        renderPage();
      }
      if (event.target.matches('[data-catalog-view]')) {
        pageState.catalogView = event.target.value;
        pageState.catalogPage = 1;
        renderPage();
      }
      if (event.target.matches('select[name="range"]')) {
        pageState.range = event.target.value;
        renderPage();
      }
    });
    root.addEventListener('input', event => {
      if (event.target.matches('[data-catalog-search]')) {
        pageState.catalogQuery = event.target.value;
        pageState.catalogPage = 1;
        renderPage();
        const search = root.querySelector('[data-catalog-search]');
        search?.focus();
        if (search) search.setSelectionRange(search.value.length, search.value.length);
      }
    });
  }

  root.querySelector('[data-form="filters"]')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    refreshData({
      location: String(form.get('location') || '').trim(),
      range: String(form.get('range') || '6m'),
      days: form.has('days') ? Number(form.get('days')) : pageState.days
    });
  });

  root.querySelector('[data-form="console-filters"]')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    pageState.consoleSkills = form.getAll('consoleSkill').map(String);
    if (!pageState.consoleSkills.includes(pageState.selectedSkill)) {
      pageState.selectedSkill = pageState.consoleSkills[0] || '';
    }
    pageState.filtersOpen = false;
    refreshData({
      location: String(form.get('location') || '').trim(),
      range: String(form.get('range') || '6m'),
      days: form.has('days') ? Number(form.get('days')) : pageState.days
    });
  });

  root.querySelector('[data-form="analysis"]')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const question = String(form.get('question') || '').trim();
    const skill = pageState.selectedSkill;
    if (!question || !skill) return;

    const currentAnalysisRequest = ++analysisRequestId;
    pageState.consoleQuery = question;
    pageState.consoleResult = 'Checking available market intelligence...';
    pageState.consoleStatus = 'loading';
    renderPage();
    try {
      const intelligence = await loadSkillIntelligence({
        location: pageState.location || undefined,
        range: pageState.range,
        skill
      });
      if (currentAnalysisRequest !== analysisRequestId) return;
      pageState.intelligence = intelligence;
      pageState.intelligenceStatus = 'loaded';
      pageState.consoleStatus = intelligence.data_status === 'error' ? 'error' : 'loaded';
      const selected = intelligence.selected_skill;
      pageState.consoleResult = intelligence.data_status === 'insufficient_data'
        ? `Not enough historical market data to calculate a reliable trend for ${skill}.`
        : intelligence.data_status === 'available'
          ? (['Growing', 'Increasing', 'Rising', 'Stable', 'Declining'].includes(selected?.trend))
            ? (intelligence.explanations?.[0]?.body || `${skill} ${selected?.signal_type === 'interest' ? 'developer interest' : selected?.signal_type === 'adoption' ? 'code adoption' : 'job demand'} is ${selected.trend.toLowerCase()}${selected.growth_pct == null ? '' : ` (${selected.growth_pct > 0 ? '+' : ''}${selected.growth_pct}% over observed periods)`}. Based on verified ${intelligence.sources_used.join(' and ') || 'stored market'} data (G1.8 quality gates applied).`)
            : `There is not enough historical market data to calculate a reliable trend for ${skill}.`
          : intelligence.data_status === 'error'
            ? intelligence.error_message || 'Unable to load market intelligence. Please try again.'
            : `Market trend data is not available yet for ${skill}. Your question is ready, but a market data source must be connected before it can be answered.`;
      renderPage();
    } catch (error) {
      if (currentAnalysisRequest !== analysisRequestId) return;
      pageState.consoleStatus = 'error';
      pageState.consoleResult = error.message || 'Unable to load market intelligence. Please try again.';
      renderPage();
    }
  });

  root.querySelector('[data-form="add-skill"]')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get('name') || '').trim();
    const level = String(form.get('level') || '');
    if (!name || pageState.skills.some(item => item.name.toLowerCase() === name.toLowerCase())) return;
    persistSkills([...pageState.skills, { name, level: level || null }]);
  });
}

export function renderDedicatedSkillsPage() {
  const main = document.getElementById('mainContent');
  if (!main) return;

  pageState = {
    ...pageState,
    skillsStatus: 'loading',
    intelligenceStatus: 'loading',
    skills: [],
    intelligence: null,
    error: '',
    location: '',
    range: '6m',
    selectedSkill: '',
    consoleSkills: [],
    consoleQuery: '',
    consoleResult: '',
    consoleStatus: '',
    filtersOpen: false,
    busy: false
  };
  renderPage();
  loadSkillCatalog().then(catalog => {
    if (window.location.hash.slice(1).split('?')[0].startsWith('/individual/skills')) {
      pageState.catalog = catalog;
      pageState.favoriteSkillIds = Array.isArray(catalog.favorite_skill_ids) ? catalog.favorite_skill_ids : [];
      pageState.catalogStatus = 'loaded';
      renderPage();
    }
  }).catch(error => {
    pageState.catalogStatus = 'error';
    pageState.catalogError = error.message || 'The skill catalog could not be loaded.';
    if (window.location.hash.slice(1).split('?')[0].startsWith('/individual/skills')) renderPage();
  });
  refreshData({ location: '', range: '6m' });
}
