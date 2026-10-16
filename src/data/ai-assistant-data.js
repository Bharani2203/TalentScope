// ============================================
// TalentScope.ai — Grounded AI Assistant Domain & Filter Configuration
// Zero Mock / Zero Fabricated Production Data
// ============================================

export const AI_STORAGE_KEY_PREFIX = 'ts_ai_session_v4';
export const AI_SAVED_KEY_PREFIX = 'ts_ai_saved_insights_v4';

export const DOMAIN_CONFIG = {
  skill: {
    id: 'skill',
    homeKey: 'skills',
    label: 'Skill Intelligence',
    shortLabel: 'Skill Intelligence',
    icon: 'brain-circuit',
    title: 'Skill Intelligence',
    subtitle: 'Analyze skill health, empirical demand slopes, half-life readiness, and O*NET occupational baselines.',
    description: 'Analyze skill health, empirical demand slopes, half-life readiness, and O*NET occupational baselines.',
    placeholder: 'Ask about skill demand, skill health, or future relevance...',
    scopes: ['All', 'Favourites'],
    defaultScope: 'All',
    focusLabel: 'Focus Skill',
    focusType: 'skill',
    prompts: [
      'Why is Python demand changing?',
      'Which of my skills are gaining relevance?',
      'What skills are adjacent to Python?'
    ],
    suggestedQuestions: [
      'Why is Python demand changing?',
      'Which of my skills are gaining relevance?',
      'What skills are adjacent to Python?'
    ]
  },
  market: {
    id: 'market',
    homeKey: 'companies',
    label: 'Market Intelligence',
    shortLabel: 'Market Intelligence',
    icon: 'building-2',
    title: 'Market Intelligence',
    subtitle: 'Track labor-market signal series, company technology adoption, and verified observation provenance.',
    description: 'Track labor-market signal series, company technology adoption, and verified observation provenance.',
    placeholder: 'Ask about company technology adoption, hiring signals, or market changes...',
    scopes: ['All', 'Favourites'],
    defaultScope: 'All',
    focusLabel: 'Focus Company / Tech',
    focusType: 'company_or_tech',
    prompts: [
      'Which companies are increasing technology adoption?',
      'What hiring signals are changing?',
      'Which companies are relevant to my interests?'
    ],
    suggestedQuestions: [
      'Which companies are increasing technology adoption?',
      'What hiring signals are changing?',
      'Which companies are relevant to my interests?'
    ]
  },
  job: {
    id: 'job',
    homeKey: 'roles',
    label: 'Job Intelligence',
    shortLabel: 'Job Intelligence',
    icon: 'briefcase',
    title: 'Job Intelligence',
    subtitle: 'Inspect stored job postings, required skills, occupational classifications, and role opportunities.',
    description: 'Inspect stored job postings, required skills, occupational classifications, and role opportunities.',
    placeholder: 'Ask about job demand, required skills, or role opportunities at a company...',
    scopes: ['All', 'Favourites'],
    defaultScope: 'All',
    focusLabel: 'Role / Posting Filter',
    focusType: 'role',
    prompts: [
      'What skills do current postings require?',
      'Which companies have relevant openings?',
      'How do job requirements compare across companies?'
    ],
    suggestedQuestions: [
      'What skills do current postings require?',
      'Which companies have relevant openings?',
      'How do job requirements compare across companies?'
    ]
  }
};

export function createDefaultDomainFilterState(domainKey = 'skill') {
  const norm = domainKey === 'market' || domainKey === 'companies'
    ? 'market'
    : (domainKey === 'job' || domainKey === 'roles' ? 'job' : 'skill');
  const cfg = DOMAIN_CONFIG[norm] || DOMAIN_CONFIG.skill;
  return {
    domain: norm,
    scope: cfg.defaultScope,
    location: '',
    timeRange: 'Max Available',
    timeframe: 'Max Available',
    selectedSkill: '',
    selectedSkills: [],
    selectedCompany: '',
    selectedRole: '',
    focusSkill: '',
    focusCompany: '',
    role: ''
  };
}

export const defaultAiContext = {
  domain: 'skill',
  scope: 'All Skills',
  location: '',
  timeframe: 'Max Available',
  timeRange: 'Max Available',
  role: '',
  skill: '',
  company: '',
  userProfile: null
};

export const aiContextOptions = {
  domains: [
    { id: 'skill', label: 'Skill Intelligence' },
    { id: 'market', label: 'Market Intelligence' },
    { id: 'job', label: 'Job Intelligence' }
  ],
  scopesByDomain: {
    skill: ['All', 'Favourites'],
    market: ['All', 'Favourites'],
    job: ['All', 'Favourites']
  },
  locations: ['Global'],
  timeframes: ['Max Available'],
  roles: [],
  skills: [],
  companies: [],
  unsupportedFilters: [
    {
      id: 'salary_band',
      label: 'Salary Band',
      reason: 'Compensation percentiles are not available in normalized market observation series.'
    },
    {
      id: 'remote_mode',
      label: 'Remote / Hybrid',
      reason: 'Workplace modality is not indexed across historical aggregate series.'
    },
    {
      id: 'visa_sponsorship',
      label: 'Visa Sponsorship',
      reason: 'Visa sponsorship metadata is not available in stored provider observations.'
    }
  ]
};

export const suggestedQuestions = [
  ...DOMAIN_CONFIG.skill.suggestedQuestions.map((label, idx) => ({
    id: `sq_skill_${idx}`,
    label,
    domain: 'skill',
    icon: 'brain-circuit'
  })),
  ...DOMAIN_CONFIG.market.suggestedQuestions.map((label, idx) => ({
    id: `sq_market_${idx}`,
    label,
    domain: 'market',
    icon: 'building-2'
  })),
  ...DOMAIN_CONFIG.job.suggestedQuestions.map((label, idx) => ({
    id: `sq_job_${idx}`,
    label,
    domain: 'job',
    icon: 'briefcase'
  }))
];

// Explicitly empty: no fabricated or demonstration scenarios are permitted in production UI paths.
export const intelligenceScenarios = [];

function resolveUserStorageKey(prefix, userId = null) {
  let uid = userId;
  if (!uid && typeof window !== 'undefined') {
    uid = window.__talentscopeCurrentUid || null;
  }
  const cleanUid = uid ? String(uid).trim() : 'guest';
  return `${prefix}_${cleanUid}`;
}

export function createInitialMultiDomainSession() {
  return {
    activeDomain: 'skill',
    context: { ...defaultAiContext },
    domains: {
      skill: {
        conversation_id: null,
        history: [],
        draftQuestion: '',
        filters: createDefaultDomainFilterState('skill')
      },
      market: {
        conversation_id: null,
        history: [],
        draftQuestion: '',
        filters: createDefaultDomainFilterState('market')
      },
      job: {
        conversation_id: null,
        history: [],
        draftQuestion: '',
        filters: createDefaultDomainFilterState('job')
      }
    }
  };
}

export function loadAiSession(userId = null) {
  const initial = createInitialMultiDomainSession();
  try {
    const key = resolveUserStorageKey(AI_STORAGE_KEY_PREFIX, userId);
    const raw = localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        const activeDomain = ['skill', 'market', 'job'].includes(parsed.activeDomain)
          ? parsed.activeDomain
          : 'skill';
        const domains = {
          skill: {
            ...initial.domains.skill,
            ...(parsed.domains?.skill || {}),
            filters: {
              ...createDefaultDomainFilterState('skill'),
              ...(parsed.domains?.skill?.filters || {})
            },
            history: Array.isArray(parsed.domains?.skill?.history) ? parsed.domains.skill.history : []
          },
          market: {
            ...initial.domains.market,
            ...(parsed.domains?.market || {}),
            filters: {
              ...createDefaultDomainFilterState('market'),
              ...(parsed.domains?.market?.filters || {})
            },
            history: Array.isArray(parsed.domains?.market?.history) ? parsed.domains.market.history : []
          },
          job: {
            ...initial.domains.job,
            ...(parsed.domains?.job || {}),
            filters: {
              ...createDefaultDomainFilterState('job'),
              ...(parsed.domains?.job?.filters || {})
            },
            history: Array.isArray(parsed.domains?.job?.history) ? parsed.domains.job.history : []
          }
        };
        return {
          activeDomain,
          context: {
            ...defaultAiContext,
            ...(parsed.context || {}),
            domain: activeDomain
          },
          domains
        };
      }
    }
  } catch (e) {
    console.warn('Could not load AI session from storage:', e);
  }
  return initial;
}

export function saveAiSession(sessionData, userId = null) {
  try {
    const key = resolveUserStorageKey(AI_STORAGE_KEY_PREFIX, userId);
    localStorage.setItem(key, JSON.stringify(sessionData));
  } catch (e) {
    console.warn('Could not save AI session to storage:', e);
  }
}

export function syncHomeToAssistantSession(userId, domainMode, payload = {}) {
  const normDom = domainMode === 'companies' || domainMode === 'market'
    ? 'market'
    : (domainMode === 'roles' || domainMode === 'job' ? 'job' : 'skill');
  const session = loadAiSession(userId);
  session.activeDomain = normDom;
  const domState = session.domains[normDom] || {
    conversation_id: null,
    history: [],
    draftQuestion: '',
    filters: createDefaultDomainFilterState(normDom)
  };
  if (payload.conversationId !== undefined) {
    domState.conversation_id = payload.conversationId;
  }
  if (payload.filters && typeof payload.filters === 'object') {
    domState.filters = {
      ...domState.filters,
      ...payload.filters
    };
  }
  if (payload.scope) {
    domState.filters.scope = payload.scope === 'All' && normDom !== 'skill' ? 'All Companies' : payload.scope;
  }
  if (payload.location) {
    domState.filters.location = payload.location;
  }
  if (payload.timeRange) {
    domState.filters.timeRange = payload.timeRange;
    domState.filters.timeframe = payload.timeRange;
  }
  if (payload.entity) {
    if (normDom === 'skill') {
      domState.filters.selectedSkill = payload.entity;
      domState.filters.focusSkill = payload.entity;
    } else if (normDom === 'market') {
      domState.filters.selectedCompany = payload.entity;
      domState.filters.focusCompany = payload.entity;
    } else {
      domState.filters.selectedRole = payload.entity;
      domState.filters.role = payload.entity;
    }
  }
  if (Array.isArray(payload.turns) && payload.turns.length) {
    domState.history = payload.turns;
  } else if (Array.isArray(payload.messages) && payload.messages.length) {
    domState.history = payload.messages.map(m => ({
      id: m.id || `turn_${Date.now()}`,
      conversation_id: payload.conversationId || null,
      client_message_id: m.apiResponse?.client_message_id || null,
      userQuestion: m.query || m.userQuestion || '',
      query: m.query || '',
      timestamp: m.timestamp || '',
      domain: normDom,
      domainIcon: normDom === 'market' ? 'building-2' : normDom === 'job' ? 'briefcase' : 'brain-circuit',
      badgeClass: 'badge-skill-market',
      status: m.apiResponse?.status || m.status || m.executionStatus || 'unavailable',
      execution_status: m.apiResponse?.execution_status || m.executionStatus || m.status || 'unavailable',
      plan_status: m.apiResponse?.plan_status || null,
      intent: m.apiResponse?.intent || null,
      answer: m.apiResponse?.answer || m.answer || m.resultData?.whatChangedBody || '',
      facts: m.apiResponse?.facts || m.facts || [],
      metric_results: m.apiResponse?.metric_results || m.metric_results || [],
      evidence: m.apiResponse?.evidence || m.evidenceItems || m.evidence || [],
      limitations: m.apiResponse?.limitations || m.limitationsItems || m.limitations || [],
      reason_codes: m.apiResponse?.reason_codes || m.reason_codes || [],
      capabilities_used: m.apiResponse?.capabilities_used || m.capabilities_used || [],
      unapplied_filters: m.apiResponse?.unapplied_filters || m.unappliedFilters || [],
      follow_up_questions: m.apiResponse?.follow_up_questions || m.contextualFollowUps || m.follow_up_questions || [],
      follow_up_suggestions: m.apiResponse?.follow_up_suggestions || m.contextualFollowUps || m.follow_up_suggestions || [],
      followUps: m.apiResponse?.follow_up_suggestions || m.contextualFollowUps || m.follow_up_questions || [],
      jobPostings: m.jobPostings || [],
      capabilities: m.apiResponse?.capabilities || m.capabilities || {},
      confidence: m.apiResponse?.confidence || m.confidence || null,
      freshness: m.apiResponse?.freshness || m.freshness || {},
      contextSnapshot: {
        domain: normDom,
        scope: m.scope || domState.filters.scope,
        location: m.location || domState.filters.location,
        timeframe: m.timeRange || domState.filters.timeRange,
        skill: normDom === 'skill' ? (m.entity || domState.filters.selectedSkill || '') : (domState.filters.selectedSkill || ''),
        company: normDom !== 'skill' ? (m.entity || domState.filters.selectedCompany || '') : (domState.filters.selectedCompany || ''),
        role: normDom === 'job' ? (m.entity || domState.filters.selectedRole || '') : (domState.filters.selectedRole || '')
      },
      response: m.apiResponse || null
    }));
  }
  session.domains[normDom] = domState;
  session.context = {
    ...(session.context || {}),
    domain: normDom,
    scope: domState.filters.scope,
    location: domState.filters.location,
    timeframe: domState.filters.timeRange || domState.filters.timeframe,
    skill: domState.filters.selectedSkill || '',
    company: domState.filters.selectedCompany || '',
    role: domState.filters.selectedRole || ''
  };
  saveAiSession(session, userId);
}

export function loadSavedInsights(userId = null) {
  try {
    const key = resolveUserStorageKey(AI_SAVED_KEY_PREFIX, userId);
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

export function saveInsight(insightItem, userId = null) {
  try {
    const current = loadSavedInsights(userId);
    const exists = current.some(item => item.id === insightItem.id);
    if (!exists) {
      current.unshift({
        ...insightItem,
        savedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
      const key = resolveUserStorageKey(AI_SAVED_KEY_PREFIX, userId);
      localStorage.setItem(key, JSON.stringify(current.slice(0, 30)));
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}

export function synthesizeIntelligenceResponse() {
  return null;
}
