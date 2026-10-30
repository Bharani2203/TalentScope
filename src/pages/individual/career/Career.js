import { dashboardState, dedicatedJobState, intelligenceExplorerState, roadmapState } from '../../../app/state.js';
import { queryJobIntelligence } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { fetchLiveJobRoles, fetchRoleGapAnalysis, fetchRoleSignalMix } from './career-api.js';
import { sendSupervisorMessage, streamSupervisorMessage, buildUserContext } from '../../../services/supervisor-api.js';
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

export const ROLE_TO_PILLAR = {
  'ai engineer': 'Artificial Intelligence and Machine Learning',
  'machine learning engineer': 'Artificial Intelligence and Machine Learning',
  'data scientist': 'Data Analysis and Data Science',
  'data engineer': 'Data Analysis and Data Science',
  'data & business analyst': 'Data Analysis and Data Science',
  'data analyst': 'Data Analysis and Data Science',
  'cloud solutions architect': 'Cloud Computing and DevOps',
  'cloud architect': 'Cloud Computing and DevOps',
  'devops & mlops lead': 'Cloud Computing and DevOps',
  'devops lead': 'Cloud Computing and DevOps',
  'backend developer': 'Software Engineering and Full-Stack Development',
  'backend engineer': 'Software Engineering and Full-Stack Development',
  'frontend engineer': 'Software Engineering and Full-Stack Development',
  'frontend developer': 'Software Engineering and Full-Stack Development',
  'full stack engineer': 'Software Engineering and Full-Stack Development',
  'full stack developer': 'Software Engineering and Full-Stack Development',
  'cybersecurity specialist': 'Cybersecurity',
  'ai product manager': 'Project Management and Stakeholder Coordination'
};

export function getUserOnboardingRoles() {
  const roles = new Set();
  if (Array.isArray(dashboardState?.savedRoles) && dashboardState.savedRoles.length > 0) {
    dashboardState.savedRoles.forEach(r => r && roles.add(r));
  }
  if (Array.isArray(dedicatedJobState?.savedRoles) && dedicatedJobState.savedRoles.length > 0) {
    dedicatedJobState.savedRoles.forEach(r => r && roles.add(r));
  }
  try {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('talentscope-saved-roles');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) parsed.forEach(r => r && roles.add(r));
      }
      const profile = localStorage.getItem('talentscope-onboarding-profile');
      if (profile) {
        const parsed = JSON.parse(profile);
        if (parsed?.targetRole) roles.add(parsed.targetRole);
        if (parsed?.careerDirection) roles.add(parsed.careerDirection);
        if (Array.isArray(parsed?.targetRoles)) parsed.targetRoles.forEach(r => r && roles.add(r));
        if (parsed?.answers?.target_role) roles.add(parsed.answers.target_role);
        if (Array.isArray(parsed?.answers?.cmp_important_roles)) {
          parsed.answers.cmp_important_roles.forEach(r => r && roles.add(r));
        }
      }
      const userProfile = localStorage.getItem('talentscope-user-profile');
      if (userProfile) {
        const parsed = JSON.parse(userProfile);
        if (parsed?.targetRole) roles.add(parsed.targetRole);
        if (parsed?.target_role) roles.add(parsed.target_role);
      }
    }
  } catch {}

  return Array.from(roles);
}

export function getFavoriteRoles() {
  const favs = new Set();
  if (Array.isArray(dashboardState?.favoriteRoles) && dashboardState.favoriteRoles.length > 0) {
    dashboardState.favoriteRoles.forEach(r => r && favs.add(r));
  }
  if (Array.isArray(dedicatedJobState?.favoriteRoles) && dedicatedJobState.favoriteRoles.length > 0) {
    dedicatedJobState.favoriteRoles.forEach(r => r && favs.add(r));
  }
  try {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('talentscope-favorite-roles');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) parsed.forEach(r => r && favs.add(r));
      }
    }
  } catch {}

  return Array.from(favs);
}

function getRoleSkillNames(r) {
  const skills = new Set();
  if (Array.isArray(r.requiredSkills)) {
    r.requiredSkills.forEach(s => skills.add((typeof s === 'string' ? s : s.name || '').toLowerCase().trim()));
  }
  if (Array.isArray(r.evolution?.current)) {
    r.evolution.current.forEach(s => skills.add(String(s).toLowerCase().trim()));
  }
  if (Array.isArray(r.evolution?.emerging)) {
    r.evolution.emerging.forEach(s => skills.add(String(s).toLowerCase().trim()));
  }
  return skills;
}

function calculateRoleSkillOverlap(role, userSkills) {
  if (!userSkills || !Array.isArray(userSkills) || userSkills.length === 0) return 0;
  const roleSkills = getRoleSkillNames(role);
  let matches = 0;
  for (const s of userSkills) {
    const sLower = String(s).toLowerCase().trim();
    if (!sLower) continue;
    for (const rs of roleSkills) {
      if (rs === sLower || rs.includes(sLower) || sLower.includes(rs)) {
        matches++;
        break;
      }
    }
  }
  return matches;
}

function getRolesGroupedByPillar() {
  const allRoles = (ui.liveRoles && ui.liveRoles.length > 0) ? ui.liveRoles : dedicatedJobRoles;
  const groups = {};
  allRoles.forEach(role => {
    const pillar = role.pillarCategory || role.pillar_category || ROLE_TO_PILLAR[(role.name || '').toLowerCase().trim()] || 'Software Engineering and Full-Stack Development';
    if (!groups[pillar]) {
      groups[pillar] = [];
    }
    if (!groups[pillar].some(existing => existing.name.toLowerCase() === role.name.toLowerCase())) {
      groups[pillar].push(role);
    }
  });
  return groups;
}


// Component UI State
let ui = {
  activeTab: 'my_roles',
  collection: dedicatedJobState?.roleScope || 'My Roles',
  activeRole: (getUserOnboardingRoles()[0] || dedicatedJobState?.selectedRole || dashboardState?.selectedRole || 'AI Engineer'),
  userOnboardingRoles: getUserOnboardingRoles(),
  favoriteRoles: getFavoriteRoles(),
  activeInvestigationTab: dedicatedJobState?.selectedTab || 'Overview',
  searchQuery: '',
  filterOpen: false,
  addModalOpen: false,
  evidenceModalData: null,
  isAnalyzing: false,
  hasAnalyzed: true,
  jobApiResponse: null,
  jobApiError: '',
  roleAssociationResponse: null,
  roleAssociationError: '',
  queryText: '',
  location: dashboardState?.market || 'Bangalore',
  timeRange: dashboardState?.timeRange || '30D',
  categoryFilter: 'All Categories',
  typeFilter: 'All Types',
  selectedCompanyContext: dedicatedJobState?.selectedCompanyContext || ['NVIDIA', 'Microsoft'],
  selectedSignalId: null,
  liveRoles: [],
  liveRolesLoading: false,
  liveRolesLoaded: false,
  liveRolesError: '',
  gapAnalysis: null,
  gapAnalysisLoading: false,
  gapAnalysisRole: null,
  gapAnalysisError: '',
  consoleMessages: [],
  consoleStreaming: false
};

export function getUserSkills() {
  const stateSkills = dashboardState?.savedSkills || [];
  if (Array.isArray(stateSkills) && stateSkills.length > 0) return stateSkills;

  try {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('talentscope-saved-skills');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
      const profile = localStorage.getItem('talentscope-onboarding-profile');
      if (profile) {
        const parsed = JSON.parse(profile);
        if (Array.isArray(parsed?.skills) && parsed.skills.length > 0) return parsed.skills;
      }
    }
  } catch {}

  return ['Python', 'SQL', 'Git'];
}

export function getDynamicSignalMix(role) {
  if (!role) return jobMarketSignalMix;
  if (Array.isArray(role.signalMix) && role.signalMix.length === 4) {
    return role.signalMix;
  }
  if (Array.isArray(role.signal_mix) && role.signal_mix.length === 4) {
    return role.signal_mix;
  }

  const openCount = Number(role.totalRoles || role.openRoles || 4500);
  const compCount = Array.isArray(role.companiesHiring) && role.companiesHiring.length
    ? role.companiesHiring.length * 90
    : (Array.isArray(role.topEmployers) && role.topEmployers.length ? role.topEmployers.length * 90 : 320);
  const momentum = Number(role.growthPercentage ?? role.growthMomentum ?? role.change ?? 15.0);

  const rawOpen = Math.max(15, Math.min(60, 40 * Math.sqrt(openCount / 9800)));
  const rawComp = Math.max(12, Math.min(45, 25 * Math.sqrt(compCount / 670)));
  const rawMom = Math.max(8, Math.min(40, 20 + Math.min(20, Math.max(-10, momentum * 0.25))));
  const rawRed = momentum < 0 ? Math.min(30, 10 + Math.abs(momentum) * 0.4) : Math.max(5, 10 - Math.min(5, momentum * 0.15));

  const totalRaw = rawOpen + rawComp + rawMom + rawRed;
  let pOpen = Math.round((rawOpen / totalRaw) * 100);
  let pComp = Math.round((rawComp / totalRaw) * 100);
  let pMom = Math.round((rawMom / totalRaw) * 100);
  let pRed = Math.round((rawRed / totalRaw) * 100);

  const diff = 100 - (pOpen + pComp + pMom + pRed);
  pOpen += diff;

  const topComps = (role.companiesHiring || role.topEmployers || []).map(c => c.name).filter(Boolean);

  return [
    {
      id: 'open_roles',
      key: 'open_role_activity',
      label: 'Open Role Activity',
      percent: pOpen,
      color: '#B22DEF',
      count: `${openCount.toLocaleString()} Active Postings`,
      change: 'Live Demand',
      detail: `Live requisition demand streams tracked across verified employers for ${role.name || 'this role'}.`,
      topRoles: [role.name || 'AI Engineer'],
      topHubs: ['Bengaluru', 'Hyderabad', 'Pune']
    },
    {
      id: 'hiring_companies',
      key: 'hiring_company_activity',
      label: 'Hiring Company Activity',
      percent: pComp,
      color: '#06B6D4',
      count: `${compCount} Employers Hiring`,
      change: 'Active Hiring',
      detail: `Enterprise employers actively hiring ${role.name || 'this role'} talent across observation windows.`,
      topCompanies: topComps.length ? topComps : ['Enterprise Technology Leaders'],
      topHubs: ['Bengaluru', 'Remote', 'Pune']
    },
    {
      id: 'role_momentum',
      key: 'role_demand_momentum',
      label: 'Role Demand Momentum',
      percent: pMom,
      color: '#19B77A',
      count: `${momentum >= 0 ? '+' : ''}${momentum.toFixed(1)}% Velocity`,
      change: momentum >= 0 ? 'Rising Momentum' : 'Steady Velocity',
      detail: `Posting velocity telemetry indicates ${momentum >= 0 ? 'positive expansion' : 'stabilization'} for ${role.name || 'this role'}.`,
      fastGrowing: [role.name || 'AI Engineer']
    },
    {
      id: 'reduction_signal',
      key: 'workforce_reduction_signal',
      label: 'Workforce Reduction Signal',
      percent: pRed,
      color: '#F59E0B',
      count: `${pRed > 12 ? 'Elevated' : 'Low'} Contraction (${pRed}%)`,
      change: pRed > 10 ? 'Shift' : 'Minimal Shift',
      detail: `Contraction telemetry indicates ${pRed > 12 ? 'elevated realignment' : 'low contraction and stable retention'} for ${role.name || 'this role'}.`,
      impacted: pRed > 10 ? ['Legacy Support'] : ['None']
    }
  ];
}

export function smoothHistorySeries(rawHistory, currentDemandScore) {
  if (!Array.isArray(rawHistory) || rawHistory.length === 0) {
    const base = currentDemandScore || 85;
    return [Math.max(45, base - 18), Math.max(48, base - 14), Math.max(52, base - 10), Math.max(58, base - 6), Math.max(65, base - 3), Math.max(70, base - 1), base];
  }

  let cleaned = [...rawHistory];

  for (let i = 0; i < cleaned.length; i++) {
    const v = cleaned[i];
    if (v === null || v === undefined || isNaN(v) || typeof v !== 'number' || v <= 10) {
      cleaned[i] = null;
    }
  }

  for (let i = 0; i < cleaned.length; i++) {
    if (cleaned[i] === null) {
      let prev = 50;
      for (let p = i - 1; p >= 0; p--) {
        if (cleaned[p] !== null) { prev = cleaned[p]; break; }
      }
      let next = prev;
      let nextIdx = i;
      for (let n = i + 1; n < cleaned.length; n++) {
        if (cleaned[n] !== null) { next = cleaned[n]; nextIdx = n; break; }
      }
      cleaned[i] = nextIdx > i ? Math.round(prev + (next - prev) / (nextIdx - i + 1)) : prev;
    }
  }

  while (cleaned.length < 7) {
    cleaned.unshift(cleaned[0] || 50);
  }
  if (cleaned.length > 7) {
    cleaned = cleaned.slice(-7);
  }

  if (currentDemandScore && typeof currentDemandScore === 'number') {
    cleaned[cleaned.length - 1] = currentDemandScore;
  }

  for (let i = 1; i < cleaned.length; i++) {
    if (cleaned[i] < cleaned[i - 1] * 0.6) {
      cleaned[i] = Math.round((cleaned[i - 1] * 2 + cleaned[i]) / 3);
    }
  }

  return cleaned;
}

function getSelectedRoleData() {
  const roleName = ui.activeRole || dedicatedJobState?.selectedRole || dashboardState?.selectedRole || 'AI Engineer';
  const base = getRoleJobDetails(roleName, ui.location, ui.timeRange, ui.selectedCompanyContext);

  if (ui.liveRoles && ui.liveRoles.length > 0) {
    const live = ui.liveRoles.find(
      r => (r.name && r.name.toLowerCase() === (roleName || '').toLowerCase().trim()) ||
           (r.id && r.id.toLowerCase() === (roleName || '').toLowerCase().trim())
    );
    if (live) {
      return {
        ...base,
        ...live,
        openRoles: live.openRoles || live.totalRoles || base.openRoles,
        totalRoles: live.totalRoles || live.openRoles || base.totalRoles,
        change: live.change ?? live.growthMomentum ?? base.change,
        growthPercentage: live.growthPercentage ?? live.growthMomentum ?? base.growthPercentage,
        growthMomentum: live.growthMomentum ?? base.growthMomentum,
        demandScore: live.demandScore || base.demandScore,
        history: live.history && live.history.length > 0 ? live.history : base.history,
        companiesHiring: (live.companiesHiring && live.companiesHiring.length > 0)
          ? live.companiesHiring
          : (live.topEmployers && live.topEmployers.length > 0 ? live.topEmployers : base.companiesHiring),
        topEmployers: (live.topEmployers && live.topEmployers.length > 0)
          ? live.topEmployers
          : (live.companiesHiring && live.companiesHiring.length > 0 ? live.companiesHiring : base.companiesHiring),
        pillarCategory: live.pillarCategory || live.pillar_category || ROLE_TO_PILLAR[(live.name || '').toLowerCase().trim()] || base.pillarCategory,
        status: live.status || base.status,
        signalMix: live.signalMix || live.signal_mix || getDynamicSignalMix(live),
        signal_mix: live.signal_mix || live.signalMix || getDynamicSignalMix(live),
        signalBreakdown: live.signalBreakdown || live.signal_breakdown
      };
    }
  }

  return {
    ...base,
    signalMix: getDynamicSignalMix(base),
    signal_mix: getDynamicSignalMix(base)
  };
}

export function renderRoleAssociationComparison(response) {
  const summary = (response?.facts || []).find(
    fact => fact.fact_type === 'learning_recommendation_summary'
  );
  if (!summary) return '';
  const details = summary.details || {};
  const overlap = details.role_associated_skill_overlap || {};
  const profileSkillLabel = details.profile_skill_source === 'authenticated_individual_profile'
    ? 'declared profile skills'
    : details.profile_skill_source === 'request_supplied_skills'
      ? 'request-supplied skills'
      : 'compared skills';
  const list = items => Array.isArray(items) && items.length
    ? `<ul>${items.map(item => `<li>${esc(item.skill || item.label || 'Unresolved mapping')}${item.profile_evidence ? ` <small>(${esc(item.profile_evidence.replaceAll('_', ' '))})</small>` : ''}</li>`).join('')}</ul>`
    : '<p>None reported.</p>';
  const overlapText = overlap.score_pct == null
    ? 'Unavailable: a comparable skill list or resolved mappings were insufficient.'
    : `${esc(overlap.score_pct)}% overlap across ${esc(overlap.matched_count)} of ${esc(overlap.resolved_mapping_count)} resolved occupation-associated mappings.`;
  return `<section class="ji-role-fit-summary" aria-label="Role-associated skill comparison">
    <h3>Role-associated skill comparison</h3>
    <p>${overlapText} This measures overlap with O*NET technology associations, not role fit, required qualifications, or employability.</p>
    <div><strong>Matched ${esc(profileSkillLabel)}</strong>${list(details.matched_associated_skills)}</div>
    <div><strong>Unmatched associated skills</strong>${list(details.missing_associated_skills)}</div>
    <div><strong>Unresolved role mappings</strong>${list(details.unresolved_requirements)}</div>
    <p><strong>Proficiency gaps:</strong> unavailable. ${esc(details.level_gaps?.reason || 'Required proficiency levels are not provided by this reference mapping.')}</p>
  </section>`;
}

function getVisibleRoles() {
  const liveRoles = (ui.liveRoles && ui.liveRoles.length > 0)
    ? ui.liveRoles
    : (ui.liveRolesLoaded ? [] : dedicatedJobRoles);

  let list = liveRoles.map(liveRole => ({
    ...liveRole,
    openRoles: liveRole.openRoles || liveRole.totalRoles || 0,
    totalRoles: liveRole.totalRoles || liveRole.openRoles || 0,
    change: liveRole.change ?? liveRole.growthMomentum ?? 0,
    growthPercentage: liveRole.growthPercentage ?? liveRole.growthMomentum ?? 0,
    growthMomentum: liveRole.growthMomentum ?? 0,
    demandScore: liveRole.demandScore || 70,
    history: liveRole.history && liveRole.history.length > 0 ? liveRole.history : [45, 50, 55, 60, 65, 70, 75],
    companiesHiring: (liveRole.companiesHiring && liveRole.companiesHiring.length > 0)
      ? liveRole.companiesHiring
      : (liveRole.topEmployers || []),
    topEmployers: (liveRole.topEmployers && liveRole.topEmployers.length > 0)
      ? liveRole.topEmployers
      : (liveRole.companiesHiring || []),
    pillarCategory: liveRole.pillarCategory || liveRole.pillar_category || ROLE_TO_PILLAR[(liveRole.name || '').toLowerCase().trim()] || 'Software Engineering and Full-Stack Development'
  }));

  const isMyRolesTab = ui.activeTab === 'my_roles' || ui.collection === 'My Roles';
  const isFavRolesTab = ui.activeTab === 'favorite_roles' || ui.collection === 'Favorite Roles';
  const isAllRolesTab = ui.activeTab === 'all_roles' || ui.collection === 'All Roles';

  if (isFavRolesTab) {
    const favs = (ui.favoriteRoles || []).map(f => (f || '').toLowerCase().trim()).filter(Boolean);
    list = list.filter(r => {
      const rName = (r.name || '').toLowerCase().trim();
      const rId = (r.id || '').toLowerCase().trim();
      return favs.some(f => f === rName || f === rId);
    });
  } else if (isMyRolesTab) {
    const saved = (ui.userOnboardingRoles || []).map(s => (s || '').toLowerCase().trim()).filter(Boolean);
    list = list.filter(r => {
      const rName = (r.name || '').toLowerCase().trim();
      const rId = (r.id || '').toLowerCase().trim();
      return saved.some(s => s === rName || s === rId || rName.includes(s) || s.includes(rName));
    });
  } else if (isAllRolesTab) {
    const userSkills = getUserSkills();
    list.sort((a, b) => {
      const overlapA = calculateRoleSkillOverlap(a, userSkills);
      const overlapB = calculateRoleSkillOverlap(b, userSkills);
      if (overlapB !== overlapA) {
        return overlapB - overlapA;
      }
      return (b.demandScore || 0) - (a.demandScore || 0);
    });
  }

  // Category filter
  if (ui.categoryFilter && ui.categoryFilter !== 'All Categories') {
    list = list.filter(r => r.category === ui.categoryFilter);
  }

  // Search filter
  if (ui.searchQuery) {
    const q = ui.searchQuery.toLowerCase().trim();
    list = list.filter(r =>
      r.name.toLowerCase().includes(q) ||
      (r.category && r.category.toLowerCase().includes(q)) ||
      (r.pillarCategory && r.pillarCategory.toLowerCase().includes(q)) ||
      (r.evolution?.current && r.evolution.current.some(s => s.toLowerCase().includes(q))) ||
      (r.requiredSkills && r.requiredSkills.some(s => (s.name || s).toLowerCase().includes(q)))
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
  const rawHistory = role.history || [48, 56, 64, 72, 80, 85, 91];
  const history = smoothHistorySeries(rawHistory, role.demandScore);
  const lastHistVal = history[history.length - 1];
  const growthRate = ((role.growthPercentage || 12.0) / 100);
  const defaultProj = [
    Math.min(99, Math.round(lastHistVal * (1 + growthRate * 0.25))),
    Math.min(99, Math.round(lastHistVal * (1 + growthRate * 0.55))),
    Math.min(99, Math.round(lastHistVal * (1 + growthRate * 0.85)))
  ];
  const projection = (role.projection && role.projection.length === 3) ? role.projection : defaultProj;
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

function renderSkillGapSectionHTML(role) {
  const gapData = ui.gapAnalysis;
  const isLoading = ui.gapAnalysisLoading && (!gapData || ui.gapAnalysisRole !== role.name);
  const availableRoles = (ui.liveRoles && ui.liveRoles.length > 0)
    ? ui.liveRoles
    : dedicatedJobRoles;

  if (isLoading) {
    return `
      <section class="ji-skill-gap-card" id="jiSkillGapSection" aria-label="Skill Gap Analysis & Readiness">
        <div class="ji-gap-card-header">
          <div class="ji-gap-header-title-block">
            <span class="ji-eyebrow">
              <i data-lucide="compass"></i>
              ROLE-TO-SKILL GAP ANALYSIS
            </span>
            <h2>Skill Gap Analysis & Readiness</h2>
            <div class="ji-gap-subtitle-wrap">
              <span>Evaluating live market requirements for</span>
              <select class="ji-gap-role-selector" aria-label="Target Role for Skill Gap Analysis">
                ${availableRoles.map(r => `
                  <option value="${esc(r.name)}" ${r.name.toLowerCase().trim() === role.name.toLowerCase().trim() ? 'selected' : ''}>
                    ${esc(r.name)}
                  </option>
                `).join('')}
              </select>
              <span>...</span>
            </div>
          </div>
        </div>
        <div style="padding: 32px 16px; text-align: center; color: var(--ji-muted); font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 10px;">
          <i data-lucide="loader-2" class="is-spinning" style="width: 18px; height: 18px; color: var(--ji-purple);"></i>
          <span>Computing skill readiness against PostgreSQL market observations...</span>
        </div>
      </section>
    `;
  }

  const score = gapData?.readinessScore ?? 0;
  const matched = gapData?.matchedSkills || [];
  const missing = gapData?.missingSkills || [];

  let statusBadgeColor = '#15803D';
  let statusBadgeBg = '#DCFCE7';
  let statusBadgeBorder = '#86EFAC';
  let statusLabel = 'Market Ready';

  if (score < 40) {
    statusBadgeColor = '#7E22CE';
    statusBadgeBg = '#F3E8FF';
    statusBadgeBorder = '#D8B4FE';
    statusLabel = 'Emerging Fit';
  } else if (score < 70) {
    statusBadgeColor = '#B45309';
    statusBadgeBg = '#FEF3C7';
    statusBadgeBorder = '#FDE68A';
    statusLabel = 'Moderate Gap';
  }

  return `
    <section class="ji-skill-gap-card" id="jiSkillGapSection" aria-label="Skill Gap Analysis & Readiness">
      <!-- Section Header with Title & Readiness Summary -->
      <div class="ji-gap-card-header">
        <div class="ji-gap-header-title-block">
          <span class="ji-eyebrow">
            <i data-lucide="compass"></i>
            ROLE-TO-SKILL GAP ANALYSIS
          </span>
          <h2>Skill Gap Analysis & Readiness</h2>
          <div class="ji-gap-subtitle-wrap">
            <span>Comparing your declared profile skills against top 10 market-demanded skills for</span>
            <select class="ji-gap-role-selector" id="jiGapRoleSelector" aria-label="Target Role for Skill Gap Analysis">
              ${availableRoles.map(r => `
                <option value="${esc(r.name)}" ${r.name.toLowerCase().trim() === role.name.toLowerCase().trim() ? 'selected' : ''}>
                  ${esc(r.name)}
                </option>
              `).join('')}
            </select>
            <span>in India.</span>
          </div>
        </div>
        <div class="ji-gap-header-score-summary">
          <div class="ji-gap-score-badge-wrap">
            <span class="ji-gap-status-pill" style="background: ${statusBadgeBg}; color: ${statusBadgeColor}; border: 1px solid ${statusBadgeBorder};">
              ${statusLabel}
            </span>
            <span class="ji-gap-big-score">${score}%</span>
          </div>
          <div class="ji-gap-score-subtext">
            <span><strong>${matched.length}</strong> Matched</span>
            <span class="ji-gap-dot-divider">•</span>
            <span><strong>${missing.length}</strong> High-Demand Gaps</span>
          </div>
        </div>
      </div>

      <!-- Readiness Score Progress Bar -->
      <div class="ji-gap-progress-track" role="progressbar" aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="100" aria-label="Role Readiness Score: ${score}%">
        <div class="ji-gap-progress-fill" style="width: ${score}%;"></div>
      </div>

      <!-- Dual Columns Grid: Matched Skills vs High-Demand Gaps -->
      <div class="ji-gap-columns-grid">
        <!-- Matched Skills Column -->
        <div class="ji-gap-column is-matched">
          <div class="ji-gap-col-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <i data-lucide="check-circle-2" style="width: 16px; height: 16px; color: #16A34A;"></i>
              <strong>Matched Skills (${matched.length})</strong>
            </div>
            <small>Verified in your profile</small>
          </div>
          <div class="ji-gap-skills-list">
            ${matched.length === 0 ? `
              <div class="ji-gap-empty-text">No declared skills match this role's top requirements yet.</div>
            ` : matched.map(m => `
              <div class="ji-gap-skill-pill is-verified" title="Matched from your profile skills">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <i data-lucide="check" style="width: 14px; height: 14px; color: #16A34A; stroke-width: 3;"></i>
                  <span class="ji-gap-skill-name">${esc(m.skill || m.name)}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span class="ji-gap-freq-tag">${Number(m.demandFrequency || m.frequency || m.demand_frequency || 0).toLocaleString()} postings</span>
                  <span class="ji-gap-verified-badge">Verified</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Missing Skills Column -->
        <div class="ji-gap-column is-missing">
          <div class="ji-gap-col-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <i data-lucide="alert-circle" style="width: 16px; height: 16px; color: #D97706;"></i>
              <strong>High-Demand Gaps (${missing.length})</strong>
            </div>
            <small>Top employer requirements</small>
          </div>
          <div class="ji-gap-skills-list">
            ${missing.length === 0 ? `
              <div class="ji-gap-empty-text" style="color: #15803D;">Outstanding! You cover all top 10 demanded skills.</div>
            ` : missing.map(ms => `
              <div class="ji-gap-skill-pill is-gap" title="High-demand skill required for this role">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span class="ji-gap-dot"></span>
                  <span class="ji-gap-skill-name">${esc(ms.skill || ms.name)}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span class="ji-gap-freq-tag">${Number(ms.demandFrequency || ms.frequency || ms.demand_frequency || 0).toLocaleString()} postings</span>
                  <button
                    type="button"
                    class="ji-btn-gap-upskill"
                    data-action="upskill-gap"
                    data-skill="${esc(ms.skill || ms.name)}"
                    aria-label="Upskill ${esc(ms.skill || ms.name)} via Learning Roadmap"
                  >
                    <i data-lucide="sparkles" style="width: 12px; height: 12px;"></i>
                    <span>Upskill</span>
                  </button>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    </section>
  `;
}

// ============================================================================
// HTML TEMPLATE RENDERERS
// ============================================================================

function renderRoleListEmptyStateHTML() {
  const isMyRolesTab = ui.activeTab === 'my_roles' || ui.collection === 'My Roles';
  const isFavRolesTab = ui.activeTab === 'favorite_roles' || ui.collection === 'Favorite Roles';

  if (ui.searchQuery) {
    return `
      <div class="ji-empty-state" style="padding: 36px 16px; text-align: center; color: var(--ji-muted);">
        <i data-lucide="search-x" style="width: 32px; height: 32px; margin: 0 auto 12px; color: var(--ji-muted); display: block;"></i>
        <p style="margin: 0 0 12px; font-size: 13px;">No roles found matching "${esc(ui.searchQuery)}"</p>
        <button type="button" class="ji-btn-secondary" id="btnResetFiltersAndSearch" style="margin: 0 auto;">
          <span>Reset Search & Filters</span>
        </button>
      </div>
    `;
  }

  if (isMyRolesTab) {
    return `
      <div class="ji-empty-state ji-empty-state-my-roles" style="padding: 36px 16px; text-align: center;">
        <div style="width: 44px; height: 44px; border-radius: 12px; background: #F3E8FF; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px;">
          <i data-lucide="briefcase" style="width: 22px; height: 22px; color: #8B3DFF;"></i>
        </div>
        <p style="margin: 0 0 14px; font-size: 13.5px; font-weight: 500; color: #475569;">
          No roles selected. Click '+ Add Role' to start tracking.
        </p>
        <button type="button" class="ji-btn-primary" data-action="open-add-role-modal" style="margin: 0 auto; display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; font-size: 12px;">
          <i data-lucide="plus" style="width: 14px; height: 14px;"></i>
          <span>+ Add Role</span>
        </button>
      </div>
    `;
  }

  if (isFavRolesTab) {
    return `
      <div class="ji-empty-state ji-empty-state-favorites" style="padding: 36px 16px; text-align: center;">
        <div style="width: 44px; height: 44px; border-radius: 12px; background: #FEF3C7; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px;">
          <i data-lucide="star" style="width: 22px; height: 22px; color: #D97706;"></i>
        </div>
        <p style="margin: 0; font-size: 13.5px; font-weight: 500; color: #475569;">
          No favorites yet. Click the star icon on a role to save it here.
        </p>
      </div>
    `;
  }

  return `
    <div class="ji-empty-state" style="padding: 36px 16px; text-align: center;">
      <i data-lucide="inbox" style="width: 32px; height: 32px; margin: 0 auto 12px; color: #94A3B8; display: block;"></i>
      <p style="margin: 0; font-size: 13.5px; color: #64748B;">No roles available.</p>
    </div>
  `;
}

function formatMarkdownToHTML(markdown) {
  if (!markdown) return '';
  let html = esc(markdown);

  // Markdown tables
  const tableRegex = /((?:^|\n)\|[^\n]+\|\r?\n\|[-: |]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g;
  html = html.replace(tableRegex, (match) => {
    const lines = match.trim().split(/\r?\n/);
    if (lines.length < 3) return match;
    const headerCells = lines[0].split('|').slice(1, -1).map(c => `<th style="padding: 8px 12px; border: 1px solid #E2E8F0; background: #F8FAFC; font-weight: 600; text-align: left; color: #1E293B;">${c.trim()}</th>`).join('');
    const thead = `<thead><tr>${headerCells}</tr></thead>`;
    const bodyRows = lines.slice(2).map((row, idx) => {
      const cells = row.split('|').slice(1, -1).map(c => `<td style="padding: 8px 12px; border: 1px solid #E2E8F0; color: #334155;">${c.trim()}</td>`).join('');
      const bg = idx % 2 === 0 ? '#FFFFFF' : '#F8FAFC';
      return `<tr style="background: ${bg};">${cells}</tr>`;
    }).join('');
    return `\n\n<div class="ji-table-wrap" style="overflow-x: auto; margin: 10px 0; border-radius: 6px; border: 1px solid #E2E8F0;"><table class="ji-markdown-table" style="width: 100%; border-collapse: collapse; font-size: 13px;">${thead}<tbody>${bodyRows}</tbody></table></div>\n\n`;
  });

  // Markdown links: [text](url) -> Clickable hyperlinks
  html = html.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/)[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #8B3DFF; text-decoration: underline; font-weight: 500;">$1</a>');

  html = html.replace(/^### (.*$)/gim, '<h4 class="ji-chat-h4">$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3 class="ji-chat-h3">$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2 class="ji-chat-h2">$1</h2>');
  html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/gim, '<code style="background: #F1F5F9; padding: 2px 5px; border-radius: 4px; font-size: 12px; font-family: monospace;">$1</code>');
  html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/gim, '<ul class="ji-chat-ul">$1</ul>');
  html = html.replace(/\n{2,}/g, '</p><p>');
  html = html.replace(/\n/g, '<br/>');
  html = html.replace(/<p[^>]*>\s*(<div class="ji-table-wrap"[\s\S]*?<\/div>)\s*<\/p>/g, '$1');
  html = html.replace(/<p[^>]*>\s*(<h[2-4][^>]*>.*?<\/h[2-4]>)\s*<\/p>/g, '$1');
  html = html.replace(/<p[^>]*>\s*(<ul[\s\S]*?<\/ul>)\s*<\/p>/g, '$1');
  return `<p>${html}</p>`;
}

function renderSupervisorEvidence(evidencePayloads) {
  if (!Array.isArray(evidencePayloads) || !evidencePayloads.length) return '';

  return evidencePayloads.map(ev => {
    if (!ev || typeof ev !== 'object') return '';
    const tool = ev.tool || '';

    // Live Jobs Evidence
    if (tool === 'fetch_live_job_openings' && Array.isArray(ev.jobs) && ev.jobs.length) {
      return `
        <div class="ji-evidence-block">
          <div class="ji-evidence-title" style="font-weight: 700; font-size: 12px; color: #1E293B; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
            <i data-lucide="briefcase" style="width: 14px; height: 14px; color: #8B3DFF;"></i>
            <span>Verified Live Openings (${ev.jobs.length})</span>
          </div>
          <div class="ji-evidence-job-grid">
            ${ev.jobs.map(job => `
              <div class="ji-evidence-job-card">
                <div class="ji-evidence-job-header">
                  <span class="ji-evidence-job-role">${esc(job.job_title || job.normalized_role || 'Job Posting')}</span>
                  <span class="ji-evidence-job-source">${esc(job.source_provider || 'Verified')}</span>
                </div>
                <div class="ji-evidence-job-meta">
                  <span class="ji-evidence-job-company"><i data-lucide="building" style="width: 12px; height: 12px;"></i> ${esc(job.company_name || 'Hiring Employer')}</span>
                  <span class="ji-evidence-job-location"><i data-lucide="map-pin" style="width: 12px; height: 12px;"></i> ${esc(job.location_city || 'India')}</span>
                </div>
                ${Array.isArray(job.required_skills) && job.required_skills.length ? `
                  <div class="ji-evidence-job-skills">
                    ${job.required_skills.slice(0, 5).map(s => `<span class="ji-job-skill-tag">${esc(s)}</span>`).join('')}
                  </div>
                ` : ''}
                ${job.apply_url ? `
                  <div class="ji-evidence-job-action">
                    <a href="${esc(job.apply_url)}" target="_blank" rel="noopener noreferrer" class="ji-job-apply-link">
                      <span>Apply Now</span>
                      <i data-lucide="external-link" style="width: 12px; height: 12px;"></i>
                    </a>
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // Skill Gap Evidence
    if (tool === 'analyze_skill_gap') {
      const matched = Array.isArray(ev.matched_skills) ? ev.matched_skills : [];
      const missing = Array.isArray(ev.missing_skills) ? ev.missing_skills : [];
      const score = ev.readiness_score ?? ev.readinessScore ?? 0;
      return `
        <div class="ji-evidence-block" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; margin-top: 6px;">
          <div class="ji-evidence-title" style="font-weight: 700; font-size: 12px; color: #1E293B; display: flex; align-items: center; gap: 6px;">
            <i data-lucide="target" style="width: 14px; height: 14px; color: #8B3DFF;"></i>
            <span>Skill Readiness Assessment: ${score}% match</span>
          </div>
          <div style="font-size: 12px; margin-top: 6px; color: #475569;">
            ${matched.length ? `<div><strong>Matched:</strong> ${matched.map(s => esc(s)).join(', ')}</div>` : ''}
            ${missing.length ? `<div style="margin-top: 4px;"><strong>Target Gaps:</strong> ${missing.map(s => esc(s)).join(', ')}</div>` : ''}
          </div>
        </div>
      `;
    }

    // Historical Demand Evidence
    if (tool === 'analyze_historical_job_demand') {
      return `
        <div class="ji-evidence-block" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; margin-top: 6px;">
          <div class="ji-evidence-title" style="font-weight: 700; font-size: 12px; color: #1E293B; display: flex; align-items: center; gap: 6px;">
            <i data-lucide="trending-up" style="width: 14px; height: 14px; color: #8B3DFF;"></i>
            <span>Historical Job Demand: ${ev.posting_count || 0} tracked postings (${ev.growth_pct >= 0 ? '+' : ''}${ev.growth_pct || 0}% MoM)</span>
          </div>
          ${Array.isArray(ev.top_employers) && ev.top_employers.length ? `
            <div style="font-size: 11.5px; color: #64748B; margin-top: 4px;">
              Top employers: ${ev.top_employers.map(e => esc(e.company_name || e)).slice(0, 5).join(', ')}
            </div>
          ` : ''}
        </div>
      `;
    }

    // Market Ecosystem Evidence
    if (tool === 'analyze_market_ecosystem') {
      const surging = Array.isArray(ev.surging_technologies) ? ev.surging_technologies : [];
      return `
        <div class="ji-evidence-block" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; margin-top: 6px;">
          <div class="ji-evidence-title" style="font-weight: 700; font-size: 12px; color: #1E293B; display: flex; align-items: center; gap: 6px;">
            <i data-lucide="activity" style="width: 14px; height: 14px; color: #8B3DFF;"></i>
            <span>Market Ecosystem: ${ev.total_signals_tracked || 0} external developer signals</span>
          </div>
          ${surging.length ? `
            <div style="font-size: 11.5px; color: #64748B; margin-top: 4px;">
              Surging skills: ${surging.map(s => `${esc(s.name || s.skill_name)} (${s.growth_pct >= 0 ? '+' : ''}${s.growth_pct || 0}%)`).join(', ')}
            </div>
          ` : ''}
        </div>
      `;
    }

    return '';
  }).join('');
}

function renderConsoleMessageHTML(msg, index) {
  if (msg.role === 'user') {
    return `
      <div class="ji-chat-msg ji-chat-msg--user" data-turn="${index}">
        <div class="ji-chat-bubble ji-chat-bubble--user">
          <span class="ji-chat-user-label">You</span>
          <p>${esc(msg.content)}</p>
        </div>
      </div>
    `;
  }

  return `
    <div class="ji-chat-msg ji-chat-msg--assistant" data-turn="${index}">
      <div class="ji-chat-bubble ji-chat-bubble--assistant">
        <div class="ji-chat-asst-header">
          <span class="ji-chat-asst-badge">
            <i data-lucide="sparkles"></i>
            Supervisor Agent
          </span>
          ${msg.provenance ? `<span class="ji-chat-provenance">${esc(msg.provenance)}</span>` : ''}
        </div>
        ${Array.isArray(msg.tools) && msg.tools.length ? `
          <div class="ji-chat-tools-invoked">
            ${msg.tools.map(tool => `
              <span class="ji-tool-pill"><i data-lucide="zap" style="width: 11px; height: 11px;"></i> ${esc(tool)}</span>
            `).join('')}
          </div>
        ` : ''}
        <div class="ji-chat-content">
          ${formatMarkdownToHTML(msg.content)}
        </div>
        ${Array.isArray(msg.evidence) && msg.evidence.length ? `
          <div class="ji-chat-evidence-container">
            ${renderSupervisorEvidence(msg.evidence)}
          </div>
        ` : ''}
        ${Array.isArray(msg.followups) && msg.followups.length ? `
          <div class="ji-chat-followups">
            <span class="ji-followup-label">Suggested follow-ups:</span>
            <div class="ji-followup-chips">
              ${msg.followups.map(chip => `
                <button type="button" class="ji-followup-chip" data-action="ask-followup" data-query="${esc(chip)}">
                  <i data-lucide="arrow-right-circle" style="width: 12px; height: 12px;"></i>
                  <span>${esc(chip)}</span>
                </button>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderJobIntelligenceHTML() {
  const role = getSelectedRoleData();
  const visibleRoles = getVisibleRoles();
  const liveRoles = (ui.liveRoles && ui.liveRoles.length > 0)
    ? ui.liveRoles
    : (ui.liveRolesLoaded ? [] : dedicatedJobRoles);
  const userSaved = (ui.userOnboardingRoles || []).map(s => (s || '').toLowerCase().trim()).filter(Boolean);
  const userFavs = (ui.favoriteRoles || []).map(f => (f || '').toLowerCase().trim()).filter(Boolean);

  const myRoles = liveRoles.filter(r => {
    const rName = (r.name || '').toLowerCase().trim();
    const rId = (r.id || '').toLowerCase().trim();
    return userSaved.some(s => s === rName || s === rId || rName.includes(s) || s.includes(rName));
  });

  const favoriteRoles = liveRoles.filter(r => {
    const rName = (r.name || '').toLowerCase().trim();
    const rId = (r.id || '').toLowerCase().trim();
    return userFavs.some(f => f === rName || f === rId);
  });

  const myCount = myRoles.length;
  const favCount = favoriteRoles.length;
  const liveRolesCount = liveRoles.length;

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
          ${(ui.liveRolesLoaded && ui.liveRoles.length > 0) ? `
            <p>Live market intelligence: role demand momentum, posting counts, and top hiring employers powered by PostgreSQL telemetry.</p>
          ` : `
            <p>Illustrative prototype only: role scores, trends, hiring counts, employers, requisitions, skills, compensation, and citations below are not live or validated. API-backed results appear separately when available.</p>
          `}
        </div>
        <div class="ji-page-heading-actions">
          ${(ui.liveRolesLoaded && ui.liveRoles.length > 0) ? `
            <div class="ji-live-badge" style="background:#DCFCE7; color:#15803D; border:1px solid #86EFAC; border-radius:12px; padding:3px 10px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:5px;" title="Live PostgreSQL telemetry and market demand metrics">
              <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#16A34A;"></span>
              <span>Live PostgreSQL Telemetry</span>
            </div>
          ` : `
            <div class="ji-demo-badge" title="Illustrative prototype; not live job-market data">
              <span>Illustrative prototype</span>
            </div>
          `}
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
            <button type="button" class="ji-collection-tab ${(ui.activeTab === 'my_roles' || ui.collection === 'My Roles') ? 'is-active' : ''}" data-collection="My Roles" data-tab="my_roles" role="tab" aria-selected="${ui.activeTab === 'my_roles' || ui.collection === 'My Roles'}">
              <span>My Roles</span>
              <span class="ji-filter-count-badge">${myCount}</span>
            </button>
            <button type="button" class="ji-collection-tab ${(ui.activeTab === 'favorite_roles' || ui.collection === 'Favorite Roles') ? 'is-active' : ''}" data-collection="Favorite Roles" data-tab="favorite_roles" role="tab" aria-selected="${ui.activeTab === 'favorite_roles' || ui.collection === 'Favorite Roles'}">
              <span>Favorite Roles</span>
              <span class="ji-filter-count-badge">${favCount}</span>
            </button>
            <button type="button" class="ji-collection-tab ${(ui.activeTab === 'all_roles' || ui.collection === 'All Roles') ? 'is-active' : ''}" data-collection="All Roles" data-tab="all_roles" role="tab" aria-selected="${ui.activeTab === 'all_roles' || ui.collection === 'All Roles'}">
              <span>All Roles</span>
              <span class="ji-filter-count-badge">${liveRolesCount}</span>
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
            ${visibleRoles.length === 0 ? renderRoleListEmptyStateHTML() : visibleRoles.map(r => {
              const isSelected = r.name.toLowerCase().trim() === (role.name || '').toLowerCase().trim();
              const isFav = (ui.favoriteRoles || dashboardState?.favoriteRoles || []).some(f => (f || '').toLowerCase().trim() === r.name.toLowerCase().trim());
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
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 2px;">
                  <span class="ji-eyebrow" style="font-size: 10px;">VERIFIED JOB TREND</span>
                  <select class="ji-hero-role-select" id="jiHeroRoleSelect" aria-label="Target Role Selector">
                    ${((ui.liveRoles && ui.liveRoles.length > 0) ? ui.liveRoles : dedicatedJobRoles).map(r => `
                      <option value="${esc(r.name)}" ${r.name.toLowerCase().trim() === (role.name || '').toLowerCase().trim() ? 'selected' : ''}>
                        ${esc(r.name)}
                      </option>
                    `).join('')}
                  </select>
                </div>
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
              ${(role.signalMix || getDynamicSignalMix(role)).map(sig => `
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
              ${(role.signalMix || getDynamicSignalMix(role)).map(sig => {
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
              ${(role.companiesHiring || role.topEmployers || []).slice(0, 3).map(comp => `
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
                    <span>${esc(comp.signalText || `${comp.openCount || 0} Open Postings`)}</span>
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

      <!-- STANDALONE FULL-WIDTH SKILL GAP ANALYSIS & READINESS SECTION -->
      ${renderSkillGapSectionHTML(role)}

      <!-- SECTION 3: STRATEGIC JOB INTELLIGENCE (7 Investigation Tabs) -->
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
                <i data-lucide="${(ui.userOnboardingRoles || dashboardState?.savedRoles || []).includes(role.name) ? 'bookmark-check' : 'bookmark'}"></i>
                <span>${(ui.userOnboardingRoles || dashboardState?.savedRoles || []).includes(role.name) ? 'Saved Role' : 'Save Role'}</span>
              </button>
            </div>
          </div>

          <!-- 7 Tabs Navigation Bar -->
          <nav class="ji-tabs-bar" role="tablist" aria-label="Investigation Tabs">
            ${TABS.map(tab => {
              const isActive = (ui.activeInvestigationTab || 'Overview') === tab;
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
          ${renderRoleAssociationComparison(ui.roleAssociationResponse)}
          ${ui.roleAssociationError ? `<p class="intel-evidence-panel__message" role="status">${esc(ui.roleAssociationError)}</p>` : ''}
          <p class="intel-evidence-panel__message" role="note">
            This role dashboard also contains illustrative baseline values. Only metrics shown with structured evidence above are API-backed.
          </p>

          <!-- Tab Panels Content -->
          <div class="ji-panel-content">
            ${renderTabPanelContent(ui.activeInvestigationTab || 'Overview', role)}
          </div>
        </section>
      ` : ''}

      <!-- SECTION 4: JOB INTELLIGENCE CONSOLE (AI Assistant Box at the very bottom) -->
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
        <!-- Multi-turn Conversation Thread -->
        <div class="ji-conversation-thread" id="jiConversationThread" aria-live="polite">
          ${(ui.consoleMessages || []).map((msg, index) => renderConsoleMessageHTML(msg, index)).join('')}
          ${ui.isAnalyzing ? `
            <div class="ji-chat-msg ji-chat-msg--assistant ji-chat-msg--loading">
              <div class="ji-chat-bubble ji-chat-bubble--assistant">
                <div class="ji-chat-asst-header">
                  <span class="ji-chat-asst-badge"><i data-lucide="sparkles" class="is-spinning"></i> Supervisor Agent</span>
                  <span class="ji-chat-provenance">Synthesizing live connectors & telemetry...</span>
                </div>
                <p style="margin: 4px 0; color: #64748B; font-size: 13px;">
                  Executing cross-provider job queries and skill readiness analysis...
                </p>
              </div>
            </div>
          ` : ''}
        </div>
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

        <!-- API request state -->
        ${ui.isAnalyzing ? `
          <div class="ji-analysis-state" aria-live="polite">
            <div class="ji-analysis-orb">
              <i data-lucide="sparkles"></i>
            </div>
            <strong>Waiting for the job-intelligence API response...</strong>
            <small>Results and evidence will be shown only if returned by the API.</small>
          </div>
        ` : ''}
      </section>

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
          ${(role.signalMix || getDynamicSignalMix(role)).map(s => `
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
  return `
    <div class="ji-tab-pane">
      <div style="margin-bottom: 20px;">
        <h4 style="margin: 0 0 4px; font-size: 16px; color: var(--ji-deep);">Evidence for ${esc(role.name)}</h4>
        <p style="color: var(--ji-muted); font-size: 13px; margin: 0;">
          This prototype does not include verified citations. API-backed evidence, when returned, appears in the Job intelligence evidence panel above.
        </p>
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
  const role = getSelectedRoleData();
  const currentMix = (role.signalMix && role.signalMix.length === 4) ? role.signalMix : getDynamicSignalMix(role);
  const sig = currentMix.find(s => s.id === ui.selectedSignalId) || currentMix[0];
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
  const groupedPillars = getRolesGroupedByPillar();
  const currentSaved = (ui.userOnboardingRoles || []).map(r => r.toLowerCase().trim());

  return `
    <div class="ji-modal-backdrop" id="jiAddRoleBackdrop">
      <div class="ji-modal-window" role="dialog" aria-modal="true" aria-label="Add Role to Tracked Collection" style="max-width: 680px; max-height: 85vh; display: flex; flex-direction: column;">
        <div class="ji-modal-header" style="flex-shrink: 0;">
          <div>
            <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #0F172A;">Track New Role</h3>
            <p style="color: #64748B; font-size: 13px; margin: 4px 0 0;">
              Select from roles grouped by Career Pillar, or add a custom role to your tracked portfolio.
            </p>
          </div>
          <button type="button" class="ji-modal-close" id="btnCloseAddRoleModal" aria-label="Close modal">
            <i data-lucide="x"></i>
          </button>
        </div>

        <div style="flex: 1; overflow-y: auto; padding: 16px 0; margin: 12px 0;">
          <div style="margin-bottom: 20px;">
            <label for="jiNewRoleInput" style="display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748B; margin-bottom: 6px; letter-spacing: 0.05em;">
              Enter Custom Role
            </label>
            <div style="display: flex; gap: 8px;">
              <input
                type="text"
                id="jiNewRoleInput"
                class="ji-query-input"
                style="height: 40px; padding: 0 12px; flex: 1; border: 1px solid #CBD5E1; border-radius: 8px;"
                placeholder="e.g. AI Infrastructure Engineer"
              />
              <button type="button" class="ji-btn-primary" id="btnConfirmAddRole" style="white-space: nowrap;">Track Role</button>
            </div>
          </div>

          <div class="ji-pillars-role-grouping" style="display: flex; flex-direction: column; gap: 14px;">
            <small style="color: #64748B; font-weight: 700; text-transform: uppercase; display: block; font-size: 11px; letter-spacing: 0.05em;">
              Available Roles by Career Pillar
            </small>
            ${Object.entries(groupedPillars).map(([pillarName, roles]) => `
              <div class="ji-pillar-group-card" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 12px 14px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                  <h4 style="margin: 0; font-size: 13px; font-weight: 700; color: #0F172A; display: flex; align-items: center; gap: 6px;">
                    <i data-lucide="layers" style="width: 14px; height: 14px; color: #8B3DFF;"></i>
                    ${esc(pillarName)}
                  </h4>
                  <span style="font-size: 11px; color: #64748B; font-weight: 600;">${roles.length} role${roles.length === 1 ? '' : 's'}</span>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  ${roles.map(r => {
                    const isTracked = currentSaved.includes(r.name.toLowerCase().trim());
                    return `
                      <button
                        type="button"
                        class="ji-evolution-pill ${isTracked ? 'is-tracked' : ''}"
                        data-action="add-role-from-pillar"
                        data-role="${esc(r.name)}"
                        style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; border-radius: 6px; border: 1px solid ${isTracked ? '#93C5FD' : '#E2E8F0'}; background: ${isTracked ? '#EFF6FF' : '#FFFFFF'}; color: ${isTracked ? '#1D4ED8' : '#334155'}; font-weight: 500;"
                        title="${isTracked ? 'Already in My Roles (Click to activate)' : 'Add to My Roles'}"
                      >
                        <i data-lucide="${isTracked ? 'check' : 'plus'}" style="width: 12px; height: 12px; color: ${isTracked ? '#1D4ED8' : '#8B3DFF'};"></i>
                        <span>${esc(r.name)}</span>
                        ${isTracked ? '<span style="font-size: 10px; background: #DBEAFE; color: #1E40AF; padding: 1px 5px; border-radius: 10px; font-weight: 600;">Tracked</span>' : ''}
                      </button>
                    `;
                  }).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <div style="display: flex; gap: 10px; justify-content: flex-end; padding-top: 12px; border-top: 1px solid #E2E8F0; flex-shrink: 0;">
          <button type="button" class="ji-btn-secondary" id="btnCancelAddRole">Cancel</button>
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
      <div class="ji-modal-window" role="dialog" aria-modal="true" aria-label="Illustrative Sample Details">
        <div class="ji-modal-header">
          <span class="ji-evidence-badge">Illustrative sample</span>
          <button type="button" class="ji-modal-close" id="btnCloseEvidenceModal" aria-label="Close citation">
            <i data-lucide="x"></i>
          </button>
        </div>
        <h3 style="margin: 0 0 6px; font-size: 18px; color: var(--ji-deep);">${esc(ev.source)}</h3>
        <span style="font-size: 12px; color: var(--ji-muted); display: block; margin-bottom: 16px;">
          Sample fixture only; not verified, API-backed, or externally sourced.
        </span>

        <div style="padding: 16px; background: var(--ji-wash); border-radius: 10px; border: 1px solid var(--ji-border); margin-bottom: 16px;">
          <strong style="color: var(--ji-purple); font-size: 14px; display: block; margin-bottom: 6px;">
            Illustrative example
          </strong>
          <p style="margin: 0; font-size: 13.5px; color: var(--ji-ink); line-height: 1.5;">
            "${esc(ev.signal)}"
          </p>
        </div>

        <p style="font-size: 13px; color: var(--ji-muted); line-height: 1.5; margin: 0 0 20px;">
          <strong>Sample context (not corroboration):</strong> ${esc(ev.supports)}
        </p>

        <div style="display: flex; justify-content: flex-end;">
          <button type="button" class="ji-btn-primary" id="btnDismissEvidence">Close</button>
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

// ============================================================================
// EVENT HANDLERS & NAVIGATION INTERACTION
// ============================================================================

function bindEvents() {
  const root = document.getElementById('jobIntelligenceWorkspace');
  if (!root) return;

  // 1. Role Scope Tabs
  root.querySelectorAll('.ji-collection-tab').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tab = e.currentTarget.dataset.tab;
      const coll = e.currentTarget.dataset.collection;
      ui.activeTab = tab || (coll === 'Favorite Roles' ? 'favorite_roles' : coll === 'All Roles' ? 'all_roles' : 'my_roles');
      ui.collection = coll || (tab === 'favorite_roles' ? 'Favorite Roles' : tab === 'all_roles' ? 'All Roles' : 'My Roles');
      if (dedicatedJobState) dedicatedJobState.roleScope = ui.collection;
      rerender();
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

  // 7b. Upskill Gap Button Click
  root.querySelectorAll('[data-action="upskill-gap"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const skillName = btn.dataset.skill;
      if (skillName) {
        triggerRoadmapPreview(skillName);
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


  // 12b. Supervisor Followup Chips Click
  root.querySelectorAll('[data-action="ask-followup"]').forEach(chip => {
    chip.addEventListener('click', (e) => {
      const query = e.currentTarget.dataset.query;
      if (query) {
        ui.queryText = query;
        runAnalysis(query);
      }
    });
  });
    runAnalysis();
  });

  // 13. Tabs Switch
  root.querySelectorAll('.ji-tab-btn').forEach(tabBtn => {
    tabBtn.addEventListener('click', (e) => {
      const targetTab = e.currentTarget.dataset.tab;
      if (targetTab) {
        ui.activeInvestigationTab = targetTab;
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
  root.querySelectorAll('[data-action="open-add-role-modal"]').forEach(btn => {
    btn.addEventListener('click', () => {
      ui.addModalOpen = true;
      rerender();
    });
  });
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

  root.querySelectorAll('[data-action="add-role-from-pillar"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const r = e.currentTarget.dataset.role;
      if (r) addRoleAndActivate(r);
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
          pillarCategory: 'Artificial Intelligence and Machine Learning',
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
          locations: [ui.location, 'Remote'],
          history: [40, 48, 55, 62, 70, 74, 78],
          projection: [80, 83, 86],
          companiesHiring: [
            { name: 'NVIDIA', logoInitials: 'NV', signalText: '+28% Active Hiring', change: 28, dir: 'up', openCount: 120, location: ui.location },
            { name: 'Microsoft', logoInitials: 'MS', signalText: '+15% Active Hiring', change: 15, dir: 'up', openCount: 140, location: ui.location }
          ]
        });
      }
      addRoleAndActivate(newName);
    }
  });
  // 19. Skill Gap Role Selector Dropdown & Hero Role Selector
  root.querySelectorAll('.ji-gap-role-selector').forEach(selectEl => {
    selectEl.addEventListener('change', (e) => {
      const newRoleName = e.target.value;
      if (newRoleName) {
        selectRole(newRoleName);
      }
    });
  });

  root.querySelectorAll('.ji-hero-role-select').forEach(selectEl => {
    selectEl.addEventListener('change', (e) => {
      const newRoleName = e.target.value;
      if (newRoleName) {
        selectRole(newRoleName);
      }
    });
  });
}

async function selectRole(roleName) {
  if (!roleName) return;
  ui.activeRole = roleName;
  if (dedicatedJobState) dedicatedJobState.selectedRole = roleName;
  if (dashboardState) dashboardState.selectedRole = roleName;
  loadGapAnalysis(roleName);
  rerender();

  try {
    const res = await fetchRoleSignalMix(roleName);
    if (res && Array.isArray(res.signalMix)) {
      if (ui.liveRoles && ui.liveRoles.length > 0) {
        const live = ui.liveRoles.find(
          r => (r.name && r.name.toLowerCase() === roleName.toLowerCase().trim()) ||
               (r.id && r.id.toLowerCase() === roleName.toLowerCase().trim())
        );
        if (live) {
          live.signalMix = res.signalMix;
          live.signalBreakdown = res.signalBreakdown;
        }
      }
      rerender();
    }
  } catch (err) {
    console.warn('Failed to fetch fresh signal mix for role:', roleName, err);
  }
}

function addRoleAndActivate(roleName) {
  if (!roleName) return;
  let currentRoles = [...(ui.userOnboardingRoles || [])];
  if (!currentRoles.some(r => r.toLowerCase().trim() === roleName.toLowerCase().trim())) {
    currentRoles.push(roleName);
    ui.userOnboardingRoles = currentRoles;
    if (dashboardState) dashboardState.savedRoles = currentRoles;
    if (dedicatedJobState) dedicatedJobState.savedRoles = currentRoles;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('talentscope-saved-roles', JSON.stringify(currentRoles));
      }
    } catch {}
  }

  ui.activeTab = 'my_roles';
  ui.collection = 'My Roles';
  if (dedicatedJobState) dedicatedJobState.roleScope = 'My Roles';

  selectRole(roleName);
  ui.addModalOpen = false;
  rerender();
}

function toggleFavoriteRole(roleName) {
  let favs = [...(ui.favoriteRoles || [])];
  if (favs.includes(roleName)) {
    favs = favs.filter(r => r !== roleName);
  } else {
    favs.push(roleName);
  }
  ui.favoriteRoles = favs;
  if (dashboardState) dashboardState.favoriteRoles = favs;
  if (dedicatedJobState) dedicatedJobState.favoriteRoles = favs;
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('talentscope-favorite-roles', JSON.stringify(favs));
    }
  } catch {}
  rerender();
}

function toggleSaveRole(roleName) {
  let saved = [...(ui.userOnboardingRoles || [])];
  if (saved.includes(roleName)) {
    saved = saved.filter(r => r !== roleName);
  } else {
    saved.push(roleName);
  }
  ui.userOnboardingRoles = saved;
  if (dashboardState) dashboardState.savedRoles = saved;
  if (dedicatedJobState) dedicatedJobState.savedRoles = saved;
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('talentscope-saved-roles', JSON.stringify(saved));
    }
  } catch {}
  rerender();
}

function triggerRoadmapPreview(skillName) {
  if (dashboardState) dashboardState.selectedSkill = skillName;
  if (roadmapState) roadmapState.skill = skillName;
  if (intelligenceExplorerState) intelligenceExplorerState.isRoadmapPreviewing = true;
  window.location.hash = '/individual/home';
}

async function runAnalysis(explicitQuery = null) {
  const query = explicitQuery !== null ? explicitQuery : (ui.queryText || '');
  const roleName = ui.activeRole || dedicatedJobState?.selectedRole || dashboardState?.selectedRole || 'AI Engineer';
  const promptText = query.trim() || `What is the hiring demand, skill requirements, and live openings for ${roleName}?`;

  ui.consoleMessages.push({
    role: 'user',
    content: promptText
  });
  ui.queryText = '';
  ui.isAnalyzing = true;
  ui.jobApiResponse = null;
  ui.jobApiError = null;
  ui.roleAssociationResponse = null;
  ui.roleAssociationError = null;
  rerender();

  try {
    const timeRange = ({ '7 Days': '7d', '30 Days': '30d', '3 Months': '3m', '6 Months': '6m' })[ui.timeRange] || '30d';
    const userContext = buildUserContext({
      target_role: roleName,
      current_view: roleName,
      user_skills: getUserSkills(),
      location: ui.location === 'Global' ? 'India' : (ui.location || 'India')
    });

    const [supervisorResult, marketResult] = await Promise.allSettled([
      sendSupervisorMessage(ui.consoleMessages, userContext),
      queryJobIntelligence({
        portalType: 'individual',
        location: ui.location === 'Global' ? undefined : ui.location,
        timeRange,
        selectedRoles: [roleName],
        targetRole: roleName,
        query: promptText || undefined
      })
    ]);

    if (supervisorResult.status === 'fulfilled' && supervisorResult.value) {
      const resp = supervisorResult.value;
      ui.consoleMessages.push({
        role: 'assistant',
        content: resp.answer || 'Analysis complete.',
        tools: resp.tools_invoked || [],
        evidence: resp.evidence_payloads || [],
        followups: resp.suggested_followups || [],
        provenance: resp.provenance_summary || ''
      });
    } else {
      ui.consoleMessages.push({
        role: 'assistant',
        content: 'Unable to connect to the Supervisor Agent. Please ensure the backend server is running.',
        tools: [],
        evidence: [],
        followups: ['Try again', 'Show available roles'],
        provenance: 'Local fallback'
      });
    }

    if (marketResult.status === 'fulfilled') {
      ui.jobApiResponse = marketResult.value;
      ui.jobApiError = '';
    } else {
      ui.jobApiError = 'Market intelligence could not be loaded. Please try again.';
    }
    ui.roleAssociationResponse = null;
    ui.roleAssociationError = '';
  } finally {
    ui.isAnalyzing = false;
    ui.hasAnalyzed = true;
    rerender();
    const thread = document.getElementById('jiConversationThread');
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
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

// ============================================================================
// EXPORT ENTRY POINTS
// ============================================================================

function loadLiveRoles() {
  if (ui.liveRolesLoading) return;
  ui.liveRolesLoading = true;
  fetchLiveJobRoles()
    .then(roles => {
      ui.liveRolesLoading = false;
      if (Array.isArray(roles) && roles.length > 0) {
        ui.liveRoles = roles;
        ui.liveRolesLoaded = true;

        if (ui.userOnboardingRoles && ui.userOnboardingRoles.length > 0) {
          const firstTarget = ui.userOnboardingRoles[0];
          const matched = roles.find(r =>
            (r.name && r.name.toLowerCase() === firstTarget.toLowerCase().trim()) ||
            (r.id && r.id.toLowerCase() === firstTarget.toLowerCase().trim())
          );
          if (matched) {
            ui.activeRole = matched.name;
          } else {
            ui.activeRole = firstTarget;
          }
        } else if (!ui.activeRole && roles.length > 0) {
          ui.activeRole = roles[0].name;
        }

        if (dashboardState) dashboardState.selectedRole = ui.activeRole;
        if (dedicatedJobState) dedicatedJobState.selectedRole = ui.activeRole;
        loadGapAnalysis(ui.activeRole);

        if (typeof document !== 'undefined' && document.getElementById('jobIntelligenceWorkspace')) {
          rerender();
        }
      }
    })
    .catch(err => {
      console.warn('Failed to load live job roles:', err);
      ui.liveRolesLoading = false;
      ui.liveRolesError = 'Failed to load live roles';
    });
}

function loadGapAnalysis(roleName) {
  if (!roleName) return;
  const userSkills = getUserSkills();
  ui.gapAnalysisLoading = true;
  ui.gapAnalysisRole = roleName;
  ui.gapAnalysisError = '';

  fetchRoleGapAnalysis(roleName, userSkills)
    .then(data => {
      if (ui.gapAnalysisRole === roleName) {
        ui.gapAnalysis = data;
        ui.gapAnalysisLoading = false;
        if (typeof document !== 'undefined' && document.getElementById('jobIntelligenceWorkspace')) {
          rerender();
        }
      }
    })
    .catch(err => {
      console.warn('Failed to load gap analysis:', err);
      ui.gapAnalysisLoading = false;
      ui.gapAnalysisError = 'Gap analysis temporarily unavailable';
    });
}

export function renderDedicatedJobPage() {
  const main = document.getElementById('mainContent');
  if (!main) return;

  if (!ui.userOnboardingRoles || ui.userOnboardingRoles.length === 0) {
    ui.userOnboardingRoles = getUserOnboardingRoles();
  }
  if (!ui.favoriteRoles || ui.favoriteRoles.length === 0) {
    ui.favoriteRoles = getFavoriteRoles();
  }
  if (!ui.activeRole && ui.userOnboardingRoles.length > 0) {
    ui.activeRole = ui.userOnboardingRoles[0];
  }

  main.innerHTML = renderJobIntelligenceHTML();
  window.lucide?.createIcons();
  bindEvents();

  if (!ui.liveRolesLoaded && !ui.liveRolesLoading) {
    loadLiveRoles();
  }

  const role = getSelectedRoleData();
  if (role && (!ui.gapAnalysis || ui.gapAnalysisRole !== role.name) && !ui.gapAnalysisLoading) {
    loadGapAnalysis(role.name);
  }
}

// Retain alias for existing imports / router references
export function renderCareerPage() {
  return renderDedicatedJobPage();
}
