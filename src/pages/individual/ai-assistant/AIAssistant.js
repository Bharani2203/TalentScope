// AIAssistant.js — Dedicated Workforce Intelligence AI Application
// Grounded Three-Domain Intelligence Assistant: Skill Intelligence, Market Intelligence, Job Intelligence

import {
  DOMAIN_CONFIG,
  aiContextOptions,
  createDefaultDomainFilterState,
  loadAiSession,
  saveAiSession,
  loadSavedInsights,
  saveInsight
} from '../../../data/ai-assistant-data.js';

import { dashboardState, userProfileState } from '../../../app/state.js';
import { resolveAssistantUserId } from '../../../auth/assistant-user-identity.js';
import { loadSkillCatalog, loadMarketCatalog } from '../../../api/intelligence-catalog-client.js';
import {
  queryCoreIntelligenceAnswer,
  fetchIntelligenceConversations,
  fetchConversationHistory,
  deleteIntelligenceConversation,
  createIntelligenceConversation,
  getActiveConversationId,
  isClientGeneratedConversationId,
  setActiveConversationId,
  getCapabilityCatalog,
  queryCoreIntelligencePlan,
  evaluateCapabilities
} from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { renderStructuredIntelligenceDetails } from '../../../components/common/IntelligenceResultDetails.js';
import { cleanConversationAnswer, renderConversationAnswer } from '../../../components/common/ConversationAnswer.js';
import { API_BASE_URL } from '../../../config/api.js';

function formatMarkdown(content) {
  if (!content) return '';
  const escaped = escapeHTML(content);

  // Convert markdown tables
  const tableRegex = /((?:^|\n)\|[^\n]+\|\r?\n\|[-: |]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g;
  const withTables = escaped.replace(tableRegex, (match) => {
    const lines = match.trim().split(/\r?\n/);
    if (lines.length < 3) return match;
    const headerCells = lines[0].split('|').slice(1, -1).map(c => `<th>${c.trim()}</th>`).join('');
    const thead = `<thead><tr>${headerCells}</tr></thead>`;
    const bodyRows = lines.slice(2).map(row => {
      const cells = row.split('|').slice(1, -1).map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');
    const tbody = `<tbody>${bodyRows}</tbody>`;
    return `<div class="ai-table-container" style="overflow-x:auto;margin:12px 0;"><table class="ai-markdown-table" style="width:100%;border-collapse:collapse;font-size:13px;">${thead}${tbody}</table></div>`;
  });

  return withTables
    .replace(/^### (.*$)/gim, '<h4 class="ai-md-h4">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 class="ai-md-h3">$1</h3>')
    .replace(/^# (.*$)/gim, '<h2 class="ai-md-h2">$1</h2>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*-\s+(.*$)/gim, '<li class="ai-md-li">$1</li>')
    .replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ai-md-li-num">$2</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

// Page-level active state
let activeSession = null;
let currentAiState = 'idle'; // 'idle' | 'typing' | 'analyzing' | 'thinking' | 'ready'
let currentToastTimer = null;
let conversationsList = [];
let historySearchQuery = '';
let activeRequestCounter = 0;
let planningRequestCounter = 0;
let capabilityPlanning = false;
let isFilterPopoverOpen = false;
let activeExplainerCapability = null; // Currently viewed capability in explainer modal
let draftFilterState = null; // Uncommitted filter state while popover is open
let isHistoryModalOpen = false;
let isHistoryDrawerOpen = false; // Backward compatibility
let isProfileMenuOpen = false;
let isCreatingConversation = false;
let historyLoadError = '';
let historyLoading = false;
let assistantRootClickContainer = null;
let assistantRootClickHandler = null;
let filterPopoverDismissHandler = null;
let skillCatalog = null;
let marketCatalog = null;
let capabilityCatalog = null;
let capabilityCatalogLoadError = false;
let catalogLoadPromise = null;
let filterPopoverKeyHandler = null;
if (typeof window !== 'undefined' && !window.__talentscopeAssistantRouteCleanup) {
  window.__talentscopeAssistantRouteCleanup = true;
  window.addEventListener('hashchange', () => {
    if (window.location.hash.split('?')[0] === '#/individual/ai-assistant') return;
    activeRequestCounter += 1;
    planningRequestCounter += 1;
    capabilityPlanning = false;
    isHistoryModalOpen = false;
    isHistoryDrawerOpen = false;
    isProfileMenuOpen = false;
    isFilterPopoverOpen = false;
    activeExplainerCapability = null;
    draftFilterState = null;
    historyLoading = false;
    removeFilterPopoverPortal();
    if (assistantRootClickContainer && assistantRootClickHandler) {
      assistantRootClickContainer.removeEventListener('click', assistantRootClickHandler);
      assistantRootClickContainer = null;
      assistantRootClickHandler = null;
    }
  });
}
if (typeof window !== 'undefined' && !window.__talentscopeFavouriteCatalogListener) {
  window.__talentscopeFavouriteCatalogListener = true;
  window.addEventListener('talentscope:favourites-updated', () => {
    catalogLoadPromise = null;
    if (window.location.hash.split('?')[0].endsWith('/individual/ai-assistant')) renderDedicatedAIAssistantPage();
  });
}

function removeFilterPopoverPortal() {
  document.getElementById('aiUnifiedFilterPanel')?.remove();
  if (filterPopoverDismissHandler) document.removeEventListener('pointerdown', filterPopoverDismissHandler, true);
  if (filterPopoverKeyHandler) document.removeEventListener('keydown', filterPopoverKeyHandler, true);
  filterPopoverDismissHandler = null;
  filterPopoverKeyHandler = null;
}

function resolveCurrentUserId() {
  return resolveAssistantUserId();
}

// ----------------------------------------------------------------------------
// Domain Capability Registry (Source of Truth for All 3 Domains)
// ----------------------------------------------------------------------------
export const DOMAIN_CAPABILITY_REGISTRY = {
  skill: [
    {
      id: 'skill_future_relevance_score',
      capabilityId: 'skill_future_relevance_score',
      title: 'Skill Future Relevance Score',
      category: 'Skill Relevance',
      desc: "Assess a skill's potential future relevance using available historical and technology-adoption signals.",
      cardTagline: "Assess a skill's potential future relevance using available signals.",
      promptHint: 'Ask about future relevance, demand trajectory, or adoption signals',
      defaultPrompt: 'What is the future relevance score for {entity}?',
      icon: 'trending-up',
      color: '#8B5CF6',
      supportedDomains: ['skill'],
      suggestedQuestions: [
        'What is the future relevance score for Python?',
        'How do historical and adoption signals project future relevance for React?',
        'What evidence supports the future relevance score for Kubernetes?'
      ],
      explainer: {
        whatItDoes: "Assess a skill's potential future relevance using available historical and technology-adoption signals.",
        inputsNeeded: 'Skill name; optional time period and target role.',
        outputProduced: 'Potential future relevance evaluation based on observable historical and adoption signals.',
        limitations: 'Predictions are strictly bounded by observable data and historical adoption signals; does not guarantee employment outcomes.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="sfrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#8B5CF6" />
              <stop offset="50%" stop-color="#6366F1" />
              <stop offset="100%" stop-color="#3B82F6" />
            </linearGradient>
            <linearGradient id="sfrSparkGrad" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#10B981" />
              <stop offset="100%" stop-color="#38BDF8" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#sfrGrad)" fill-opacity="0.14" />
          <path d="M11 31 L18 24 L24 28 L33 15" stroke="url(#sfrGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M27 15 H33 V21" stroke="url(#sfrGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="33" cy="15" r="3" fill="url(#sfrSparkGrad)" />
        </svg>
      `,
      followUpCapabilityIds: ['skill_change_alert', 'adaptive_skill_roadmap']
    },
    {
      id: 'skill_change_alert',
      capabilityId: 'skill_change_alert',
      title: 'Skill Change Alert',
      category: 'Skill Alerts',
      desc: 'Identify supported increases, decreases, or stable patterns in comparable skill signals.',
      cardTagline: 'Identify increases, decreases, or stable patterns in skill signals.',
      promptHint: 'Ask about momentum changes, inflection points, or emerging patterns',
      defaultPrompt: 'Are there any change alerts for {entity}?',
      icon: 'alert-circle',
      color: '#EC4899',
      supportedDomains: ['skill'],
      suggestedQuestions: [
        'Are there any change alerts for Python in recent periods?',
        'Identify shift patterns or momentum changes for TypeScript.',
        'What signal changes are detected for Cloud Computing?'
      ],
      explainer: {
        whatItDoes: 'Identify supported increases, decreases, or stable patterns in comparable skill signals.',
        inputsNeeded: 'Skill name; comparison period when needed.',
        outputProduced: 'Change alert status, direction shifts, and momentum patterns.',
        limitations: 'Requires comparable historical periods without synthetic interpolation.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="scaGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#FF3366" />
              <stop offset="50%" stop-color="#EC4899" />
              <stop offset="100%" stop-color="#8B5CF6" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#scaGrad)" fill-opacity="0.14" />
          <circle cx="22" cy="22" r="12" stroke="url(#scaGrad)" stroke-width="2" stroke-dasharray="3 2" />
          <path d="M22 14 V24" stroke="url(#scaGrad)" stroke-width="2.2" stroke-linecap="round" />
          <circle cx="22" cy="28" r="1.6" fill="#EC4899" />
        </svg>
      `,
      followUpCapabilityIds: ['skill_future_relevance_score', 'adaptive_skill_roadmap']
    },
    {
      id: 'adaptive_skill_roadmap',
      capabilityId: 'adaptive_skill_roadmap',
      title: 'Adaptive Skill Roadmap',
      category: 'Skill Pathways',
      desc: 'Recommend an ordered learning plan based on current skills, a target role, and available skill relationships.',
      cardTagline: 'Recommend an ordered learning plan for a target role.',
      promptHint: 'Ask about milestone learning paths, target roles, or skill bridges',
      defaultPrompt: 'What is the adaptive skill roadmap for {entity}?',
      icon: 'map',
      color: '#06B6D4',
      supportedDomains: ['skill'],
      suggestedQuestions: [
        'Create an adaptive skill roadmap for a Backend Developer role.',
        'What ordered learning plan transitions from Python to Machine Learning Engineer?',
        'Recommend a milestone learning path for DevOps Engineer.'
      ],
      explainer: {
        whatItDoes: 'Recommend an ordered learning plan based on current skills, a target role, and available skill relationships.',
        inputsNeeded: 'Target role; current skills when available.',
        outputProduced: 'Ordered milestone roadmap, prerequisite dependencies, and skill groupings.',
        limitations: 'Based on standardized occupational taxonomy and reference curricula, not guaranteed placement.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="asrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#06B6D4" />
              <stop offset="50%" stop-color="#3B82F6" />
              <stop offset="100%" stop-color="#10B981" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#asrGrad)" fill-opacity="0.14" />
          <path d="M12 32 C12 25, 22 25, 22 18 C22 11, 32 11, 32 18" stroke="url(#asrGrad)" stroke-width="2.2" stroke-linecap="round" fill="none" />
          <circle cx="12" cy="32" r="3" fill="#06B6D4" />
          <circle cx="22" cy="20" r="3" fill="#3B82F6" />
          <circle cx="32" cy="18" r="3.5" fill="#10B981" />
        </svg>
      `,
      followUpCapabilityIds: ['skill_future_relevance_score', 'skill_change_alert']
    }
  ],
  market: [
    {
      id: 'technology_adoption_shift_detector',
      capabilityId: 'technology_adoption_shift_detector',
      title: 'Technology Adoption Shift Detector',
      category: 'Market Shifts',
      desc: 'Compare supported technology-adoption signals over comparable periods and identify meaningful changes.',
      cardTagline: 'Compare technology-adoption signals over comparable periods.',
      promptHint: 'Ask about technology adoption shifts, developer traction, or public interest',
      defaultPrompt: 'What adoption shifts are detected for {entity}?',
      icon: 'activity',
      color: '#3B82F6',
      supportedDomains: ['market'],
      suggestedQuestions: [
        'Detect technology adoption shifts between React and Vue.',
        'Compare quarterly developer adoption signals for Rust versus Go.',
        'What adoption trajectory shifts are observed for Docker over comparable periods?'
      ],
      explainer: {
        whatItDoes: 'Compare supported technology-adoption signals over comparable periods and identify meaningful changes.',
        inputsNeeded: 'One or more technologies; comparison period when needed.',
        outputProduced: 'Adoption shift direction, comparative velocity, and multi-source signals.',
        limitations: 'Preserves each source\'s native metric and provenance; developer activity is not conflated with employer demand.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="tasdGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#3B82F6" />
              <stop offset="50%" stop-color="#06B6D4" />
              <stop offset="100%" stop-color="#8B5CF6" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#tasdGrad)" fill-opacity="0.14" />
          <path d="M11 28 L17 18 L24 24 L33 13" stroke="url(#tasdGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M11 33 H33" stroke="url(#tasdGrad)" stroke-width="1.5" stroke-opacity="0.4" stroke-linecap="round" />
          <circle cx="24" cy="24" r="2.5" fill="#3B82F6" />
          <circle cx="33" cy="13" r="3" fill="#06B6D4" />
        </svg>
      `,
      followUpCapabilityIds: ['technology_impact_explorer']
    },
    {
      id: 'technology_impact_explorer',
      capabilityId: 'technology_impact_explorer',
      title: 'Technology Impact Explorer',
      category: 'Market Impact',
      desc: 'Explore supported relationships between technologies, skills, and occupations.',
      cardTagline: 'Explore relationships between technologies, skills, and occupations.',
      promptHint: 'Ask about occupational exposure, technology impacts, or skill crosswalks',
      defaultPrompt: 'What is the technology impact of {entity} across roles and occupations?',
      icon: 'compass',
      color: '#10B981',
      supportedDomains: ['market'],
      suggestedQuestions: [
        'Explore the occupational impact of Generative AI.',
        'Which job roles and software skills are most affected by Kubernetes?',
        'How does Cloud Computing impact Data Engineering occupations?'
      ],
      explainer: {
        whatItDoes: 'Explore supported relationships between technologies, skills, and occupations.',
        inputsNeeded: 'Technology or skill; optional target occupation.',
        outputProduced: 'Crosswalk of impacted roles, related software skills, and occupational dependencies.',
        limitations: 'Reflects structured taxonomy mappings between technologies and occupations without speculative projection.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="tieGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#10B981" />
              <stop offset="50%" stop-color="#38BDF8" />
              <stop offset="100%" stop-color="#6366F1" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#tieGrad)" fill-opacity="0.14" />
          <circle cx="22" cy="22" r="11" stroke="url(#tieGrad)" stroke-width="1.8" />
          <polygon points="22,14 25,22 22,20 19,22" fill="#10B981" />
          <polygon points="22,30 25,22 22,24 19,22" fill="#38BDF8" />
          <circle cx="22" cy="22" r="2" fill="#FFFFFF" />
        </svg>
      `,
      followUpCapabilityIds: ['technology_adoption_shift_detector']
    }
  ],
  job: [
    {
      id: 'skill_based_job_match',
      capabilityId: 'skill_based_job_match',
      title: 'Skill-Based Job Match',
      category: 'Job Matching',
      desc: "Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps.",
      cardTagline: "Compare your skills with requirements in retrieved job postings.",
      promptHint: 'Ask about matching postings, required software skills, or skill gap analysis',
      defaultPrompt: 'How do my skills match job postings for {entity}?',
      icon: 'briefcase',
      color: '#F59E0B',
      supportedDomains: ['job'],
      suggestedQuestions: [
        'Match my skills against verified Software Engineer job postings.',
        'Which job postings match a skill profile of Python and SQL?',
        'Explain the skill gaps between my profile and Senior Data Scientist postings.'
      ],
      explainer: {
        whatItDoes: "Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps.",
        inputsNeeded: 'Current skills or profile; optional target role and location.',
        outputProduced: 'Matched job postings, requirement coverage, and specific skill gaps.',
        limitations: 'Matches against retrieved and verified job postings; not an exhaustive index of all market vacancies.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="sbjmGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#F59E0B" />
              <stop offset="50%" stop-color="#EC4899" />
              <stop offset="100%" stop-color="#8B5CF6" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#sbjmGrad)" fill-opacity="0.14" />
          <rect x="12" y="16" width="20" height="15" rx="3" stroke="url(#sbjmGrad)" stroke-width="2" />
          <path d="M17 16 V13 C17 11.5, 18.5 10.5, 20 10.5 H24 C25.5 10.5, 27 11.5, 27 13 V16" stroke="url(#sbjmGrad)" stroke-width="1.8" stroke-linecap="round" />
          <circle cx="22" cy="23.5" r="2" fill="#F59E0B" />
        </svg>
      `,
      followUpCapabilityIds: ['career_transition_opportunity']
    },
    {
      id: 'career_transition_opportunity',
      capabilityId: 'career_transition_opportunity',
      title: 'Career Transition Opportunity',
      category: 'Career Pathways',
      desc: 'Identify possible related target roles and the skills that may be needed for a transition.',
      cardTagline: 'Identify related target roles and transition skills.',
      promptHint: 'Ask about lateral moves, transition pathways, or role bridges',
      defaultPrompt: 'What career transition opportunities exist from {entity}?',
      icon: 'shuffle',
      color: '#6366F1',
      supportedDomains: ['job'],
      suggestedQuestions: [
        'What career transition opportunities exist from QA Engineer to DevOps?',
        'Identify related occupations and skill bridges for Data Analyst.',
        'Explore viable transition pathways from Frontend Developer to Full Stack Engineer.'
      ],
      explainer: {
        whatItDoes: 'Identify possible related target roles and the skills that may be needed for a transition.',
        inputsNeeded: 'Current or target role; current skills when available.',
        outputProduced: 'Viable target roles, shared work activities, and transition skill requirements.',
        limitations: 'Identifies transition opportunities based on shared occupational tasks and skills in O*NET/ESCO baselines.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="ctoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#6366F1" />
              <stop offset="50%" stop-color="#8B5CF6" />
              <stop offset="100%" stop-color="#EC4899" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#ctoGrad)" fill-opacity="0.14" />
          <path d="M12 16 H24 L29 22 L24 28 H12" stroke="url(#ctoGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M27 16 L32 22 L27 28" stroke="url(#ctoGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      `,
      followUpCapabilityIds: ['skill_based_job_match']
    }
  ]
};

export const capabilitySuggestedQuestions = {
  skill_future_relevance_score: [
    'What is the future relevance score for Python?',
    'How do historical and adoption signals project future relevance for React?',
    'What evidence supports the future relevance score for Kubernetes?'
  ],
  skill_change_alert: [
    'Are there any change alerts for Python in recent periods?',
    'Identify shift patterns or momentum changes for TypeScript.',
    'What signal changes are detected for Cloud Computing?'
  ],
  adaptive_skill_roadmap: [
    'Create an adaptive skill roadmap for a Backend Developer role.',
    'What ordered learning plan transitions from Python to Machine Learning Engineer?',
    'Recommend a milestone learning path for DevOps Engineer.'
  ],
  technology_adoption_shift_detector: [
    'Detect technology adoption shifts between React and Vue.',
    'Compare quarterly developer adoption signals for Rust versus Go.',
    'What adoption trajectory shifts are observed for Docker over comparable periods?'
  ],
  technology_impact_explorer: [
    'Explore the occupational impact of Generative AI.',
    'Which job roles and software skills are most affected by Kubernetes?',
    'How does Cloud Computing impact Data Engineering occupations?'
  ],
  skill_based_job_match: [
    'Match my skills against verified Software Engineer job postings.',
    'Which job postings match a skill profile of Python and SQL?',
    'Explain the skill gaps between my profile and Senior Data Scientist postings.'
  ],
  career_transition_opportunity: [
    'What career transition opportunities exist from QA Engineer to DevOps?',
    'Identify related occupations and skill bridges for Data Analyst.',
    'Explore viable transition pathways from Frontend Developer to Full Stack Engineer.'
  ]
};

export function resolveActiveCapabilityId(response, domain, catalog = capabilityCatalog) {
  const capabilities = getDomainCapabilities(domain, catalog);
  const capabilityIds = [
    response?.executed_primary_capability,
    response?.planned_primary_capability,
    ...(Array.isArray(response?.capabilities_used) ? response.capabilities_used : []),
    ...(Array.isArray(response?.planned_capabilities) ? response.planned_capabilities : [])
  ].filter(capabilityId => typeof capabilityId === 'string');
  return capabilityIds
    .map(capabilityId => capabilities.find(capability => capability.id === capabilityId))
    .find(Boolean)?.id || null;
}

export function getDomainCapabilities(domain, catalog = capabilityCatalog) {
  const domKey = ['skill', 'market', 'job'].includes(domain) ? domain : 'skill';
  const presentations = DOMAIN_CAPABILITY_REGISTRY[domKey] || DOMAIN_CAPABILITY_REGISTRY.skill;
  const registered = new Map(
    (Array.isArray(catalog?.capabilities) ? catalog.capabilities : [])
      .filter(capability => ['available', 'partial'].includes(capability.global_status) && capability.handler)
      .map(capability => [capability.capability_id, capability])
  );
  return presentations
    .filter(capability => {
      const record = registered.get(capability.id);
      return record?.supported_domains?.includes(domKey);
    })
    .map(capability => ({
      ...capability,
      supportedDomains: registered.get(capability.id).supported_domains
    }));
}

export function getAssistantComposerMode(domainState) {
  if (domainState?.guidedJourney) return 'guided';
  if (domainState?.selectedFeature) return 'feature';
  return 'normal';
}

async function requestRecommendedCapability(question, domain, domState) {
  const plan = await queryCoreIntelligencePlan({
    message: question,
    portalType: 'individual',
    timeRange: 'max',
    conversationId: domState.conversation_id || undefined,
  });
  const capabilities = getDomainCapabilities(domain);
  const selectedIds = Array.isArray(plan.selected_capabilities) ? plan.selected_capabilities : [];
  const capability = selectedIds
    .map(id => capabilities.find(item => item.id === id))
    .find(Boolean);
  if (!capability) {
    return {
      capability: null,
      reason: plan.intent_explanation || 'No executable capability matched this question in the selected domain.'
    };
  }
  const readiness = (plan.readiness_results || []).find(result => result.capability_id === capability.id);
  if (readiness && !readiness.can_execute) {
    return {
      capability: null,
      reason: readiness.explanation || `The ${capability.title} prerequisites are not currently met.`
    };
  }
  return {
    capability,
    reason: plan.intent_explanation || `The intelligence planner selected ${capability.title} for this question.`
  };
}

function extractEntityCandidate(question) {
  if (!question) return '';
  const q = String(question).trim();
  const forMatch = q.match(/(?:for|about|in|on)\s+([A-Za-z0-9#+.\s]{2,25})(?:\?|$|\.)/i);
  if (forMatch && forMatch[1]) return forMatch[1].trim();
  const words = q.split(/\s+/).filter(w => w.length > 2 && !['what', 'how', 'when', 'where', 'show', 'tell', 'explain', 'which'].includes(w.toLowerCase()));
  return words.slice(0, 2).join(' ') || '';
}

function collectJourneyCapabilityIds(firstCapabilityId, capabilities) {
  const byId = new Map(capabilities.map(capability => [capability.id, capability]));
  const visited = new Set([firstCapabilityId]);
  const pending = [...(byId.get(firstCapabilityId)?.followUpCapabilityIds || [])];
  while (pending.length) {
    const nextId = pending.shift();
    if (visited.has(nextId) || !byId.has(nextId)) continue;
    visited.add(nextId);
    pending.push(...(byId.get(nextId)?.followUpCapabilityIds || []));
  }
  visited.delete(firstCapabilityId);
  return [...visited];
}

function findNextJourneyCandidate(turn, domainKey, history, journey, catalog) {
  if (!journey?.id) return null;
  if (!turn || turn.guidedJourneyId !== journey.id) {
    return null;
  }
  if (!['ready', 'partial'].includes(turn.status)) return null;
  const dom = ['skill', 'market', 'job'].includes(domainKey) ? domainKey : 'skill';
  const allCaps = getDomainCapabilities(dom, catalog);

  const completedIds = new Set(journey.completedCapabilityIds || []);
  (journey.skippedCapabilityIds || []).forEach(id => completedIds.add(id));
  (history || []).forEach(t => {
    if (t.guidedJourneyId !== journey.id) return;
    const feat = t.capabilityId || t.requestContext?.capabilityId || t.requestContext?.filters?.selected_feature || t.selectedFeature;
    if (feat) completedIds.add(feat);
    if (Array.isArray(t.capabilities_used)) {
      t.capabilities_used.forEach(c => completedIds.add(c));
    }
  });

  const currentFeat = turn.capabilityId || turn.requestContext?.capabilityId || turn.requestContext?.filters?.selected_feature || turn.selectedFeature || null;
  if (currentFeat) completedIds.add(currentFeat);
  if (!Array.isArray(turn.capabilities_used) || !turn.capabilities_used.includes(currentFeat)) {
    return null;
  }
  const currentCapability = allCaps.find(capability => capability.id === currentFeat);
  const remainingIds = new Set(journey.remainingCapabilityIds || []);
  const capabilitiesById = new Map(allCaps.map(capability => [capability.id, capability]));
  const visitedIds = new Set();
  const pendingIds = [...(currentCapability?.followUpCapabilityIds || [])];
  let nextCapId = null;
  while (pendingIds.length) {
    const candidateId = pendingIds.shift();
    if (visitedIds.has(candidateId)) continue;
    visitedIds.add(candidateId);
    const candidate = capabilitiesById.get(candidateId);
    if (!candidate) continue;
    if (completedIds.has(candidateId) || !remainingIds.has(candidateId)) {
      pendingIds.push(...(candidate.followUpCapabilityIds || []));
      continue;
    }
    nextCapId = candidateId;
    break;
  }

  if (!nextCapId) {
    return { isComplete: true, completionReason: journey.completionReason || 'No additional relevant capability is available for this journey.' };
  }

  const nextCap = allCaps.find(c => c.id === nextCapId);
  if (!nextCap) return null;

  const originalQuestion = journey.originalQuestion || turn.userQuestion;
  const entity = originalQuestion ? (extractEntityCandidate(originalQuestion) || 'this area') : 'this area';
  const prompt = nextCap.defaultPrompt.replace('{entity}', entity);

  return {
    isComplete: false,
    nextCapability: nextCap,
    reason: `Continue with ${nextCap.title} using the evidence and context from this step.`,
    prompt
  };
}

export function resolveNextJourneyStep(turn, domainKey, history = [], journey = null, catalog = capabilityCatalog) {
  if (!Array.isArray(catalog?.capabilities)) return null;
  if (journey?.isEvaluatingNext) return { isEvaluating: true };
  if (journey?.readinessError) return { isUnavailable: true, reason: journey.readinessError };
  const candidate = findNextJourneyCandidate(turn, domainKey, history, journey, catalog);
  if (!candidate || candidate.isComplete) return candidate;
  if (!journey.readinessEvaluated) return null;
  if (journey.readinessCapabilityId !== candidate.nextCapability.id || journey.nextCapabilityReady !== true) {
    return {
      isComplete: true,
      completionReason: journey.completionReason || 'No further step is ready with the currently available evidence.'
    };
  }
  return candidate;
}

async function evaluateGuidedJourneyNextStep(turn, domain, userId, journeyId) {
  const domState = getActiveDomainSession(domain);
  const journey = domState.guidedJourney;
  if (!journey || journey.id !== journeyId || userId !== resolveCurrentUserId()) return;
  const requestContext = turn.requestContext || {};
  const entityFact = (turn.facts || []).find(fact =>
    fact.canonical_entity_id && fact.entity_name && fact.quality_state === 'valid'
  );
  const originalQuestion = journey.originalQuestion || turn.userQuestion || '';
  const entityName = entityFact?.entity_name
    || extractEntityCandidate(originalQuestion);
  if (!entityName) {
    journey.isEvaluatingNext = false;
    journey.isComplete = true;
    journey.currentCapabilityId = null;
    domState.selectedFeature = null;
    journey.readinessError = 'The next step cannot be checked because this answer has no resolved entity to evaluate.';
    saveAiSession(activeSession, userId);
    if (getActiveDomainKey() === domain) renderDedicatedAIAssistantPage();
    return;
  }

  const entityType = entityFact?.entity_type
    || (domain === 'skill' ? 'skill' : domain === 'job' ? 'occupation' : 'technology');
  const maxChecks = getDomainCapabilities(domain).length;
  for (let check = 0; check < maxChecks; check += 1) {
    if (userId !== resolveCurrentUserId()) return;
    const currentJourney = getActiveDomainSession(domain).guidedJourney;
    if (!currentJourney || currentJourney.id !== journeyId) return;
    const candidate = findNextJourneyCandidate(turn, domain, domState.history, currentJourney, capabilityCatalog);
    if (!candidate || candidate.isComplete) {
      currentJourney.isEvaluatingNext = false;
      currentJourney.isComplete = true;
      currentJourney.currentCapabilityId = null;
      domState.selectedFeature = null;
      currentJourney.readinessEvaluated = true;
      currentJourney.readinessCapabilityId = null;
      currentJourney.nextCapabilityReady = false;
      currentJourney.completionReason = candidate?.completionReason
        || 'No further supported capability is relevant to the question and available evidence.';
      saveAiSession(activeSession, userId);
      if (getActiveDomainKey() === domain) renderDedicatedAIAssistantPage();
      return;
    }

    try {
      const evaluated = await evaluateCapabilities({
        capability_id: candidate.nextCapability.id,
        entity_name: entityName,
        entity_type: entityType,
        portal_type: 'individual',
        time_range: requestContext.timeRange || 'max'
      });
      const readiness = (evaluated.results || []).find(result => result.capability_id === candidate.nextCapability.id);
      const latestJourney = getActiveDomainSession(domain).guidedJourney;
      if (!latestJourney || latestJourney.id !== journeyId || userId !== resolveCurrentUserId()) return;
      if (readiness?.can_execute) {
        latestJourney.isEvaluatingNext = false;
        latestJourney.readinessEvaluated = true;
        latestJourney.readinessCapabilityId = candidate.nextCapability.id;
        latestJourney.nextCapabilityReady = true;
        latestJourney.readinessError = '';
        latestJourney.completionReason = '';
        saveAiSession(activeSession, userId);
        if (getActiveDomainKey() === domain) renderDedicatedAIAssistantPage();
        return;
      }
      latestJourney.skippedCapabilityIds ||= [];
      if (!latestJourney.skippedCapabilityIds.includes(candidate.nextCapability.id)) {
        latestJourney.skippedCapabilityIds.push(candidate.nextCapability.id);
      }
      latestJourney.completionReason = readiness?.explanation
        || `The ${candidate.nextCapability.title} prerequisites are not currently met.`;
    } catch (error) {
      const latestJourney = getActiveDomainSession(domain).guidedJourney;
      if (!latestJourney || latestJourney.id !== journeyId || userId !== resolveCurrentUserId()) return;
      latestJourney.isEvaluatingNext = false;
      latestJourney.isComplete = true;
      latestJourney.currentCapabilityId = null;
      domState.selectedFeature = null;
      latestJourney.readinessError = error?.message || 'The next capability readiness could not be verified.';
      saveAiSession(activeSession, userId);
      if (getActiveDomainKey() === domain) renderDedicatedAIAssistantPage();
      return;
    }
  }

  const latestJourney = getActiveDomainSession(domain).guidedJourney;
  if (!latestJourney || latestJourney.id !== journeyId || userId !== resolveCurrentUserId()) return;
  latestJourney.isEvaluatingNext = false;
  latestJourney.isComplete = true;
  latestJourney.currentCapabilityId = null;
  domState.selectedFeature = null;
  latestJourney.readinessEvaluated = true;
  latestJourney.readinessCapabilityId = null;
  latestJourney.nextCapabilityReady = false;
  saveAiSession(activeSession, userId);
  if (getActiveDomainKey() === domain) renderDedicatedAIAssistantPage();
}

function getActiveDomainKey() {
  const dom = activeSession?.activeDomain || activeSession?.context?.domain || 'skill';
  return ['skill', 'market', 'job'].includes(dom) ? dom : 'skill';
}

function getActiveDomainSession(domainKey = null) {
  // Keep this accessor safe from initSession(): initSession itself needs the
  // active domain state, so calling it here creates an infinite recursion.
  const uid = resolveCurrentUserId();
  if (!activeSession || activeSession._uid !== uid) {
    activeSession = loadAiSession(uid);
    activeSession._uid = uid;
  }
  const dom = domainKey || getActiveDomainKey();
  if (!activeSession.domains) {
    activeSession.domains = {};
  }
  if (!activeSession.domains[dom]) {
    activeSession.domains[dom] = {
      conversation_id: getActiveConversationId('individual', dom, resolveCurrentUserId()) || null,
      filters: createDefaultDomainFilterState(dom),
      draftQuestion: '',
      selectedFeature: null,
      guidedJourney: null,
      history: []
    };
  }
  if (!activeSession.domains[dom].filters) {
    activeSession.domains[dom].filters = createDefaultDomainFilterState(dom);
  }
  if (activeSession.domains[dom].selectedFeature === undefined) {
    activeSession.domains[dom].selectedFeature = null;
  }
  if (activeSession.domains[dom].guidedJourney === undefined) {
    activeSession.domains[dom].guidedJourney = null;
  }
  if (!Array.isArray(activeSession.domains[dom].history)) {
    activeSession.domains[dom].history = [];
  }
  return activeSession.domains[dom];
}

function normalizeDomainScope(domainKey, rawScope) {
  const cfg = DOMAIN_CONFIG[domainKey] || DOMAIN_CONFIG.skill;
  const allowed = cfg.scopes || ['All', 'Favourites'];
  const mapped = rawScope === 'Favourite Skills' || rawScope === 'Favourite Companies' || rawScope === 'Favorite Skills' || rawScope === 'Favorite Companies'
    ? 'Favourites'
    : ['All', 'All Skills', 'All Companies', 'My Skills'].includes(rawScope)
      ? 'All'
      : rawScope;
  return allowed.includes(mapped) ? mapped : allowed[0];
}

export function resolveCanonicalAssistantEntity(domain, name) {
  if (!name) return '';
  if (domain === 'skill') {
    const item = skillCatalog?.skills?.find(row =>
      row.name === name || (row.aliases || []).includes(name)
    );
    return item?.skill_id || name;
  }
  const technologies = marketCatalog?.technologies || [];
  const companies = marketCatalog?.companies_with_job_evidence || [];
  const registered = marketCatalog?.registered_company;
  if (domain === 'market') {
    return technologies.find(row => row.name === name)?.skill_id
      || companies.find(row => row.name === name)?.entity_id
      || (registered?.name === name ? registered.entity_id : '')
      || name;
  }
  return companies.find(row => row.name === name)?.entity_id || name;
}

function getCommittedFilterSnapshot(domainKey = null) {
  const dom = domainKey || getActiveDomainKey();
  const domState = getActiveDomainSession(dom);
  const f = domState.filters || createDefaultDomainFilterState(dom);
  const shared = typeof window !== 'undefined' ? window.__talentscopeCommittedIntelligenceFilters?.[dom] : null;
  if (shared) {
    f.scope = normalizeDomainScope(dom, shared.scope);
    f.location = shared.location || '';
    f.timeRange = shared.timeRange || 'Max Available';
    f.timeframe = f.timeRange;
    f.selectedSkill = dom === 'skill' ? shared.entity || '' : '';
    f.selectedSkills = dom === 'skill' && Array.isArray(shared.entities)
      ? shared.entities
      : (f.selectedSkill ? [f.selectedSkill] : []);
    f.selectedCompany = dom === 'market' ? shared.entity || '' : '';
    f.selectedRole = dom === 'job' ? shared.entity || '' : '';
  }
  const scope = normalizeDomainScope(dom, f.scope);
  const selectedSkills = Array.isArray(f.selectedSkills) && f.selectedSkills.length
    ? [...new Set(f.selectedSkills.filter(Boolean))]
    : (f.selectedSkill ? [f.selectedSkill] : []);
  return {
    scope,
    selectedSkill: selectedSkills[0] || f.selectedSkill || '',
    selectedSkills,
    selectedCompany: f.selectedCompany || '',
    selectedRole: f.selectedRole || '',
    location: f.location || '',
    timeRange: f.timeRange || 'Max Available'
  };
}

function syncLegacySessionPointers() {
  if (!activeSession) return;
  const dom = getActiveDomainKey();
  const domState = getActiveDomainSession(dom);
  activeSession.activeDomain = dom;
  activeSession.conversation_id = domState.conversation_id || null;
  activeSession.history = domState.history;
  activeSession.context = {
    ...(activeSession.context || {}),
    domain: dom,
    scope: domState.filters.scope,
    location: domState.filters.location,
    timeframe: domState.filters.timeRange,
    skill: domState.filters.selectedSkill || '',
    company: domState.filters.selectedCompany || '',
    role: domState.filters.selectedRole || ''
  };
}

function initSession() {
  const uid = resolveCurrentUserId();
  if (!activeSession || activeSession._uid !== uid) {
    activeSession = loadAiSession(uid);
    activeSession._uid = uid;
  }
  const dom = getActiveDomainKey();
  const domState = getActiveDomainSession(dom);
  const storedConvId = getActiveConversationId('individual', dom, uid);
  if (storedConvId && !domState.conversation_id) {
    domState.conversation_id = storedConvId;
  }
  syncLegacySessionPointers();
}

function switchAssistantDomain(newDomain) {
  if (!['skill', 'market', 'job'].includes(newDomain)) return;
  initSession();
  const prevDomain = getActiveDomainKey();
  const prevDomState = getActiveDomainSession(prevDomain);
  const inputEl = document.getElementById('aiComposerInput');
  if (inputEl) {
    prevDomState.draftQuestion = inputEl.value;
  }
  prevDomState.pendingQuestion = '';
  activeRequestCounter += 1;
  planningRequestCounter += 1;
  capabilityPlanning = false;
  currentAiState = 'idle';
  activeExplainerCapability = null;
  if (newDomain !== prevDomain) {
    const nextState = getActiveDomainSession(newDomain);
    if (nextState.filters.domain !== newDomain) nextState.filters = createDefaultDomainFilterState(newDomain);
    nextState.selectedFeature = null;
    nextState.guidedJourney = null;
    nextState.selectionReason = '';
  }
  activeSession.activeDomain = newDomain;
  if (!activeSession.context) activeSession.context = {};
  activeSession.context.domain = newDomain;
  isFilterPopoverOpen = false;
  isProfileMenuOpen = false;
  draftFilterState = null;
  syncLegacySessionPointers();
  saveAiSession(activeSession, resolveCurrentUserId());
}

function resolveFreshnessInfo(domState) {
  const history = Array.isArray(domState?.history) ? domState.history : [];
  for (let i = history.length - 1; i >= 0; i--) {
    const ts = history[i]?.freshness?.latest_observed_at;
    if (ts) {
      return {
        isLive: true,
        dateStr: String(ts).slice(0, 10),
        label: `Data updated · ${String(ts).slice(0, 10)}`
      };
    }
  }
  const homeTs = dashboardState?.homeSkillIntel?.freshness?.latest_observed_at
    || dashboardState?.homeJobIntel?.freshness?.latest_observed_at
    || null;
  if (homeTs) {
    return {
      isLive: true,
      dateStr: String(homeTs).slice(0, 10),
      label: `Data updated · ${String(homeTs).slice(0, 10)}`
    };
  }
  return {
    isLive: false,
    dateStr: null,
    label: 'Freshness unavailable'
  };
}

function groupConversationsByDate(items, searchStr = '') {
  const groups = { Today: [], Yesterday: [], 'Previous 7 Days': [], Older: [] };
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 7 * 86400000;
  const q = (searchStr || '').trim().toLowerCase();

  (items || []).forEach(item => {
    const title = item.title || item.active_entity || 'Intelligence Session';
    if (q && !title.toLowerCase().includes(q) && !(item.active_entity || '').toLowerCase().includes(q)) {
      return;
    }
    const ts = new Date(item.updated_at || item.created_at || Date.now()).getTime();
    if (ts >= todayStart) groups.Today.push(item);
    else if (ts >= yesterdayStart) groups.Yesterday.push(item);
    else if (ts >= weekStart) groups['Previous 7 Days'].push(item);
    else groups.Older.push(item);
  });
  return groups;
}

async function refreshConversationSidebar() {
  if (!isHistoryModalOpen && !isHistoryDrawerOpen) return;
  const currentUid = resolveCurrentUserId();
  if (currentUid === 'anonymous') {
    historyLoading = false;
    historyLoadError = '';
    conversationsList = [];
    const sidebarBody = document.getElementById('aiHistoryGroupedList');
    if (sidebarBody) {
      sidebarBody.innerHTML = renderGroupedHistoryItemsHTML();
      attachSidebarItemListeners(document.getElementById('mainContent'));
      if (window.lucide) window.lucide.createIcons();
    }
    return;
  }

  historyLoading = true;
  try {
    const domain = getActiveDomainKey();
    const list = await fetchIntelligenceConversations({ limit: 100, domain, portalType: 'individual' });
    if ((!isHistoryModalOpen && !isHistoryDrawerOpen) || domain !== getActiveDomainKey()) return;
    if (Array.isArray(list)) {
      conversationsList = list.filter(item => (item.domain || 'skill') === domain && (item.portal_type || 'individual') === 'individual');
      historyLoadError = '';
      historyLoading = false;
      const sidebarBody = document.getElementById('aiHistoryGroupedList');
      if (sidebarBody) {
        sidebarBody.innerHTML = renderGroupedHistoryItemsHTML();
        attachSidebarItemListeners(document.getElementById('mainContent'));
        if (window.lucide) window.lucide.createIcons();
      }
    }
  } catch (error) {
    historyLoading = false;
    if (error?.status === 401 || error?.name === 'CoreIntelligenceAuthError') {
      historyLoadError = 'Your session has expired. Please sign in again to view your conversation history.';
    } else if (error?.status === 503 || error?.name === 'CoreIntelligenceServiceUnavailableError') {
      historyLoadError = 'Authentication service is temporarily unavailable. Please retry shortly.';
    } else {
      historyLoadError = error?.message || 'Conversation history is temporarily unavailable.';
    }
    conversationsList = [];
    const sidebarBody = document.getElementById('aiHistoryGroupedList');
    if (sidebarBody) sidebarBody.innerHTML = renderGroupedHistoryItemsHTML();
  }
}

function renderGroupedHistoryItemsHTML() {
  const dom = getActiveDomainKey();
  const domCfg = DOMAIN_CONFIG[dom] || DOMAIN_CONFIG.skill;
  const currentUid = resolveCurrentUserId();
  if (currentUid === 'anonymous') {
    return `
      <div class="ai-history-empty-state">
        <i data-lucide="log-in" class="ai-history-empty-icon"></i>
        <strong class="ai-history-empty-title">Sign in for conversation history</strong>
        <span class="ai-history-empty-sub">Sign in to save, resume, and manage your private ${escapeHTML(domCfg.label)} sessions across visits.</span>
      </div>
    `;
  }
  if (historyLoading) {
    return `<div class="ai-history-empty-state" role="status"><i data-lucide="loader-2" class="ai-history-empty-icon ai-spin"></i><span>Loading ${escapeHTML(domCfg.shortLabel)} history…</span></div>`;
  }
  if (historyLoadError) {
    return `<div class="ai-history-empty-state" role="alert">
      <i data-lucide="wifi-off" class="ai-history-empty-icon"></i>
      <strong class="ai-history-empty-title">History could not be loaded</strong>
      <span class="ai-history-empty-sub">${escapeHTML(historyLoadError)}</span>
      <button type="button" class="ai-modal-new-btn" id="btnRetryAssistantHistory" style="margin-top:8px;">Try again</button>
    </div>`;
  }
  const domainItems = (conversationsList || []).filter(item =>
    (item.domain || 'skill') === dom && (item.portal_type || 'individual') === 'individual'
  );
  if (domainItems.length === 0) {
    return `
      <div class="ai-history-empty-state">
        <i data-lucide="message-square-dashed" class="ai-history-empty-icon"></i>
        <strong class="ai-history-empty-title">No ${escapeHTML(domCfg.shortLabel)} conversations yet</strong>
        <span class="ai-history-empty-sub">Submit a question in ${escapeHTML(domCfg.label)} to automatically save and resume your session here.</span>
      </div>
    `;
  }

  const groups = groupConversationsByDate(domainItems, historySearchQuery);
  const domState = getActiveDomainSession(dom);
  const activeId = domState?.conversation_id;
  const entries = Object.entries(groups).filter(([, arr]) => arr.length > 0);
  if (!entries.length) {
    return `
      <div class="ai-history-empty-state">
        <i data-lucide="search-x" class="ai-history-empty-icon"></i>
        <strong class="ai-history-empty-title">No matching conversations</strong>
        <span class="ai-history-empty-sub">No sessions match "${escapeHTML(historySearchQuery)}". Try a different keyword.</span>
      </div>
    `;
  }
  return entries.map(([label, arr]) => `
    <div class="ai-history-group">
      <div class="ai-history-group-label">${escapeHTML(label)}</div>
      ${arr.map(item => `
        <div class="ai-history-card-item ${item.conversation_id === activeId ? 'is-active' : ''}" role="group" aria-label="Conversation: ${escapeHTML(item.title || item.active_entity || 'Conversation')}">
          <button type="button" class="ai-history-open-btn" data-restore-conv="${escapeHTML(item.conversation_id)}" aria-current="${item.conversation_id === activeId ? 'true' : 'false'}">
            <span class="ai-history-item-left">
              <span class="ai-history-item-title">${escapeHTML(item.title || item.active_entity || 'Conversation')}</span>
              <span class="ai-history-item-meta">${escapeHTML(item.updated_at ? new Date(item.updated_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : domCfg.shortLabel)} · ${item.turn_count || 0} turn${item.turn_count === 1 ? '' : 's'}</span>
            </span>
          </button>
          <button type="button" class="ai-history-delete-btn" data-delete-conv="${escapeHTML(item.conversation_id)}" title="Delete conversation" aria-label="Delete conversation">
            <i data-lucide="trash-2" style="width:13px; height:13px;"></i>
          </button>
        </div>
      `).join('')}
    </div>
  `).join('');
}

// ----------------------------------------------------------------------------
// Render Main Page
// ----------------------------------------------------------------------------
export function renderDedicatedAIAssistantPage() {
  const container = document.getElementById('mainContent');
  if (!container) return;
  if (!catalogLoadPromise) {
    catalogLoadPromise = Promise.all([
      loadSkillCatalog().catch(() => null),
      loadMarketCatalog().catch(() => null),
      getCapabilityCatalog().catch(() => null)
    ]).then(([skills, market, capabilities]) => {
      skillCatalog = skills;
      marketCatalog = market;
      capabilityCatalog = Array.isArray(capabilities?.capabilities) ? capabilities : null;
      capabilityCatalogLoadError = capabilityCatalog === null;
      if (window.location.hash.split('?')[0].endsWith('/individual/ai-assistant')) renderDedicatedAIAssistantPage();
    });
  }
  removeFilterPopoverPortal();

  // Reload session from storage only if not already initialized for this user
  const uid = resolveCurrentUserId();
  if (!activeSession || activeSession._uid !== uid) {
    activeSession = loadAiSession(uid);
    activeSession._uid = uid;
  }
  initSession();
  refreshConversationSidebar();

  // Check URL query parameters for contextual entry
  const hash = window.location.hash || '';
  if (hash.includes('?')) {
    const queryParams = new URLSearchParams(hash.split('?')[1]);
    const incomingTopic = queryParams.get('topic');
    const incomingSkill = queryParams.get('skill');
    const incomingRole = queryParams.get('role');
    const incomingQuery = queryParams.get('q');

    const domState = getActiveDomainSession();
    if (incomingTopic) {
      domState.filters.selectedSkill = incomingTopic;
    } else if (incomingSkill) {
      domState.filters.selectedSkill = incomingSkill;
    }
    if (incomingRole) {
      domState.filters.selectedRole = incomingRole;
    }
    syncLegacySessionPointers();
    saveAiSession(activeSession, resolveCurrentUserId());

    if (incomingQuery && domState.history.length === 0) {
      executeAiQuery(incomingQuery);
      return;
    }
  }

  container.innerHTML = generatePageHTML();
  attachEventListeners(container);

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  const stream = container.querySelector('#aiConversationStream');
  if (stream) {
    requestAnimationFrame(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    });
  }
}

export function renderAIAssistantPage() {
  return renderDedicatedAIAssistantPage();
}

function renderScopeDropdownHTML(domain, currentScope, scopes) {
  return `
    <div class="ai-ref-filter-dropdown" id="scopeDropdownMenu" role="menu">
      <div class="ai-ref-dropdown-title">Scope (${domain === 'skill' ? 'Skills' : domain === 'market' ? 'Companies' : 'Roles'})</div>
      ${scopes.map(sc => `
        <button type="button" class="ai-ref-dropdown-item ${sc === currentScope ? 'is-selected' : ''}" data-select-scope="${escapeHTML(sc)}" role="menuitem">
          <i data-lucide="${sc === currentScope ? 'check' : 'layers'}" class="ai-ref-dropdown-icon"></i>
          <span class="ai-ref-dropdown-text">${escapeHTML(sc)}</span>
        </button>
      `).join('')}
    </div>
  `;
}

function renderLocationDropdownHTML(currentLocation, locations) {
  const options = locations.length ? locations : ['Global'];
  return `
    <div class="ai-ref-filter-dropdown" id="locationDropdownMenu" role="menu">
      <div class="ai-ref-dropdown-title">Location</div>
      ${options.map(loc => `
        <button type="button" class="ai-ref-dropdown-item ${loc === currentLocation ? 'is-selected' : ''}" data-select-location="${escapeHTML(loc)}" role="menuitem">
          <i data-lucide="${loc === currentLocation ? 'check' : 'map-pin'}" class="ai-ref-dropdown-icon"></i>
          <span class="ai-ref-dropdown-text">${escapeHTML(loc)}</span>
        </button>
      `).join('')}
    </div>
  `;
}

function renderTimeRangeDropdownHTML(currentTimeRange, ranges) {
  const options = ranges.length ? ranges : ['Max Available'];
  return `
    <div class="ai-ref-filter-dropdown" id="timerangeDropdownMenu" role="menu">
      <div class="ai-ref-dropdown-title">Time Range</div>
      ${options.map(tr => `
        <button type="button" class="ai-ref-dropdown-item ${tr === currentTimeRange ? 'is-selected' : ''}" data-select-timerange="${escapeHTML(tr)}" role="menuitem">
          <i data-lucide="${tr === currentTimeRange ? 'check' : 'calendar'}" class="ai-ref-dropdown-icon"></i>
          <span class="ai-ref-dropdown-text">${escapeHTML(tr)}</span>
        </button>
      `).join('')}
    </div>
  `;
}

export function getObservedFilterOptions(domain, turns) {
  const entities = new Set();
  const companies = new Set();
  const roles = new Set();
  const locations = new Set();
  (turns || []).forEach(turn => {
    (turn.facts || []).forEach(fact => {
      const factType = String(fact.entity_type || '').toLowerCase();
      const supported = fact.canonical_entity_id && fact.entity_name
        && fact.quality_state === 'valid'
        && fact.data_origin === 'real';
      const relevant = domain === 'skill' ? factType === 'skill'
        : domain === 'market' ? ['company', 'technology', 'tech'].includes(factType)
          : false;
      if (supported && relevant) {
        entities.add(fact.entity_name);
        if (domain === 'market' && factType === 'company') companies.add(fact.entity_name);
        const details = fact.details || {};
        [details.location, details.city, details.country, details.region].filter(Boolean).forEach(value => locations.add(String(value)));
      }
    });
    (turn.jobPostings || []).forEach(posting => {
      if (domain === 'job') {
        if (posting.company) { entities.add(String(posting.company)); companies.add(String(posting.company)); }
        if (posting.title || posting.role) roles.add(String(posting.title || posting.role));
        if (posting.location) locations.add(String(posting.location));
      }
    });
    (turn.evidence || []).forEach(item => {
      const details = item.details || {};
      [details.location, details.city, details.country, details.region].filter(Boolean).forEach(value => locations.add(String(value)));
    });
  });

  // Catalog options are sourced from authenticated API catalogs; turn evidence is
  // retained to support conversation-local locations and job roles.
  if (domain === 'skill' && Array.isArray(skillCatalog?.skills)) {
    skillCatalog.skills.forEach(item => { if (item?.name) entities.add(item.name); });
    (skillCatalog.locations || []).forEach(value => locations.add(String(value)));
  } else if (domain === 'market' && Array.isArray(marketCatalog?.technologies)) {
    marketCatalog.technologies.forEach(item => { if (item?.name) entities.add(item.name); });
    (marketCatalog.companies_with_job_evidence || []).forEach(item => { if (item?.name) entities.add(item.name); });
    if (marketCatalog.registered_company?.name) entities.add(marketCatalog.registered_company.name);
    (marketCatalog.locations || []).forEach(value => locations.add(String(value)));
  } else if (domain === 'job' && Array.isArray(marketCatalog?.companies_with_job_evidence)) {
    marketCatalog.companies_with_job_evidence.forEach(item => {
      if (item?.name) { entities.add(item.name); companies.add(item.name); }
    });
    (marketCatalog.job_locations_in_sample || []).forEach(value => locations.add(String(value)));
    (marketCatalog.roles_in_sample || []).forEach(value => roles.add(String(value)));
  }

  // Reuse intelligence records already loaded by the Home console when available.
  const homeIntel = domain === 'skill' ? dashboardState?.homeSkillIntel
    : domain === 'market' ? dashboardState?.homeMarketIntel : dashboardState?.homeJobIntel;
  const homeRecords = Array.isArray(homeIntel?.records) ? homeIntel.records : (Array.isArray(homeIntel?.items) ? homeIntel.items : []);
  homeRecords.forEach(record => {
    const name = record?.entity_name || record?.skill || record?.company || record?.company_name;
    const type = String(record?.entity_type || record?.type || '').toLowerCase();
    if (domain === 'job') {
      const company = record.company || record.company_name;
      const role = record.role || record.title || record.job_title;
      if (company) { companies.add(String(company)); entities.add(String(company)); }
      if (role) roles.add(String(role));
    } else if (name && (!type || type === domain || (domain === 'market' && ['company', 'technology', 'tech'].includes(type)) || (domain === 'skill' && type === 'skill'))) {
      entities.add(String(name));
      if (domain === 'market' && type === 'company') companies.add(String(name));
    }
    [record.location, record.city, record.country].filter(Boolean).forEach(value => locations.add(String(value)));
  });

  const catalogRanges = domain === 'skill' ? skillCatalog?.available_ranges
    : domain === 'market' ? marketCatalog?.available_ranges
      : domain === 'job' ? marketCatalog?.job_available_ranges : null;
  const ranges = [...new Set((Array.isArray(catalogRanges) ? catalogRanges : [])
    .map(value => value === '30d' ? '30 Days' : value === '3m' ? '3 Months' : value === '6m' ? '6 Months' : value))];
  if (!ranges.includes('Max Available')) ranges.push('Max Available');
  const favoriteIds = new Set(marketCatalog?.favorite_entity_ids || []);
  const favoriteMarketEntities = [];
  (marketCatalog?.technologies || []).filter(item => favoriteIds.has(item.skill_id)).forEach(item => favoriteMarketEntities.push(item.name));
  (marketCatalog?.companies_with_job_evidence || []).filter(item => favoriteIds.has(item.entity_id)).forEach(item => favoriteMarketEntities.push(item.name));
  if (marketCatalog?.registered_company && favoriteIds.has(marketCatalog.registered_company.entity_id)) favoriteMarketEntities.push(marketCatalog.registered_company.name);
  const favoriteJobCompanies = (marketCatalog?.companies_with_job_evidence || []).filter(item => favoriteIds.has(item.entity_id)).map(item => item.name);
  return {
    entities: [...entities].sort((a, b) => a.localeCompare(b)),
    companies: [...companies].sort((a, b) => a.localeCompare(b)),
    favoriteMarketEntities: [...new Set(favoriteMarketEntities)].sort((a, b) => a.localeCompare(b)),
    favoriteCompanies: favoriteJobCompanies,
    roles: [...roles].sort((a, b) => a.localeCompare(b)),
    favoriteSkills: (skillCatalog?.favorite_skill_ids || []).map(id => skillCatalog.skills?.find(item => item.skill_id === id)?.name).filter(Boolean),
    locations: [...locations].sort((a, b) => a.localeCompare(b)),
    ranges
  };
}

export function getSelectableEntities(domain, scope, observed) {
  const supported = new Set(observed.entities || []);
  if (domain === 'skill') {
    const candidates = scope === 'Favourites' ? (observed.favoriteSkills || []) : [...supported];
    return [...new Set(candidates)].filter(name => supported.has(name)).sort((a, b) => a.localeCompare(b));
  }
  if (domain === 'market') {
    const candidates = scope === 'Favourites' ? (observed.favoriteMarketEntities || []) : [...supported];
    return [...new Set(candidates)].filter(name => supported.has(name)).sort((a, b) => a.localeCompare(b));
  }
  const jobCompanies = new Set(observed.companies || observed.entities || []);
  const candidates = scope === 'Favourites' ? (observed.favoriteCompanies || []) : [...jobCompanies];
  return [...new Set(candidates)].filter(name => jobCompanies.has(name)).sort((a, b) => a.localeCompare(b));
}

function filterEntityOptionLabel(domain, name) {
  if (domain === 'skill') {
    const entity = skillCatalog?.skills?.find(item => item.name === name);
    return entity?.status === 'reference_only' ? `${name} · Reference only — no trend data` : name;
  }
  return name;
}

export function validateAssistantFilterDraft(domain, draft, options) {
  const entity = draft.selectedSkill || draft.selectedCompany || '';
  const selectedSkills = Array.isArray(draft.selectedSkills) && draft.selectedSkills.length
    ? draft.selectedSkills
    : (entity ? [entity] : []);
  const validEntities = getSelectableEntities(domain, draft.scope, options);
  const entityValid = domain === 'skill'
    ? selectedSkills.every(value => validEntities.includes(value))
    : (!entity || validEntities.includes(entity));
  return {
    valid: entityValid
      && (!draft.selectedRole || (options.roles || []).includes(draft.selectedRole))
      && options.ranges.includes(draft.timeRange)
      && (!draft.location || options.locations.includes(draft.location)),
    entityValid,
    roleValid: !draft.selectedRole || (options.roles || []).includes(draft.selectedRole),
    locationValid: !draft.location || options.locations.includes(draft.location),
    timeRangeValid: options.ranges.includes(draft.timeRange)
  };
}

export function commitAssistantFilterDraft(domainState, domain, draft) {
  const selectedSkills = Array.isArray(draft.selectedSkills) ? [...new Set(draft.selectedSkills.filter(Boolean))] : [];
  domainState.filters = {
    ...domainState.filters,
    ...draft,
    domain,
    timeframe: draft.timeRange,
    selectedSkills,
    selectedSkill: domain === 'skill' ? (selectedSkills[0] || '') : draft.selectedSkill,
    focusSkill: domain === 'skill' ? (selectedSkills[0] || '') : draft.selectedSkill,
    focusCompany: draft.selectedCompany,
    role: draft.selectedRole
  };
  if (typeof window !== 'undefined') {
    window.__talentscopeCommittedIntelligenceFilters = window.__talentscopeCommittedIntelligenceFilters || {};
    window.__talentscopeCommittedIntelligenceFilters[domain] = {
      domain,
      scope: domainState.filters.scope,
      entity: domain === 'skill' ? domainState.filters.selectedSkill : domain === 'market' ? domainState.filters.selectedCompany : domainState.filters.selectedRole,
      entities: domain === 'skill' ? selectedSkills : [],
      location: domainState.filters.location || '',
      timeRange: domainState.filters.timeRange || 'Max Available'
    };
  }
  return domainState.filters;
}

export function resetAssistantFilterDraft(domain, availableRanges = ['Max Available']) {
  const defaults = createDefaultDomainFilterState(domain);
  const timeRange = availableRanges.includes('Max Available') ? 'Max Available' : (availableRanges[0] || 'Max Available');
  return { ...defaults, timeRange, timeframe: timeRange };
}

function parseObservedLocations(locations) {
  const parsed = [];
  (locations || []).forEach(loc => {
    if (!loc) return;
    const str = String(loc).trim();
    const parts = str.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length === 1) {
      parsed.push({ raw: str, city: '', state: '', country: parts[0] });
    } else if (parts.length === 2) {
      parsed.push({ raw: str, city: parts[0], state: '', country: parts[1] });
    } else if (parts.length >= 3) {
      parsed.push({ raw: str, city: parts[0], state: parts[1], country: parts[parts.length - 1] });
    }
  });
  return parsed;
}

function getLocationHierarchy(locations) {
  const parsed = parseObservedLocations(locations);
  const countries = [...new Set(parsed.map(p => p.country).filter(Boolean))].sort((a, b) => a.localeCompare(b));

  const getStates = (country) => {
    if (!country) return [];
    return [...new Set(parsed.filter(p => p.country.toLowerCase() === country.toLowerCase() && p.state).map(p => p.state))].sort((a, b) => a.localeCompare(b));
  };

  const getCities = (country, state) => {
    return [...new Set(parsed.filter(p => {
      const matchCountry = !country || p.country.toLowerCase() === country.toLowerCase();
      const matchState = !state || p.state.toLowerCase() === state.toLowerCase();
      return matchCountry && matchState && p.city;
    }).map(p => p.city))].sort((a, b) => a.localeCompare(b));
  };

  return { countries, getStates, getCities, parsed };
}

function renderLocationCascadeFields(draft, observedOptions) {
  const hierarchy = getLocationHierarchy(observedOptions.locations);
  if (!observedOptions.locations || !observedOptions.locations.length) {
    return `
      <div class="ai-filter-field">
        <label class="ai-filter-label">Location</label>
        <small class="ai-filter-help-text">Location filtering is unavailable until supported regional telemetry is exposed.</small>
      </div>
    `;
  }

  // Auto-sync country/state/city from draft.location if not set
  if (!draft.country && draft.location) {
    const matched = hierarchy.parsed.find(p => p.raw.toLowerCase() === draft.location.toLowerCase());
    if (matched) {
      draft.country = matched.country;
      draft.state = matched.state;
      draft.city = matched.city;
    }
  }

  const states = hierarchy.getStates(draft.country);
  const cities = hierarchy.getCities(draft.country, draft.state);

  return `
    <div class="ai-filter-field">
      <div class="ai-filter-label-row">
        <label class="ai-filter-label">3. Location Hierarchy</label>
        ${draft.location ? `<span class="ai-filter-location-active-tag">${escapeHTML(draft.location)}</span>` : ''}
      </div>
      <div class="ai-location-cascade-group">
        <div class="ai-location-row">
          <div class="ai-location-select-wrap">
            <span class="ai-location-select-hint"><i data-lucide="globe"></i> Country</span>
            <select class="ai-filter-select" data-draft-filter="country" aria-label="Country">
              <option value="">✦ All Countries</option>
              ${hierarchy.countries.map(c => `<option value="${escapeHTML(c)}" ${c === draft.country ? 'selected' : ''}>${escapeHTML(c)}</option>`).join('')}
            </select>
          </div>
          ${states.length > 0 ? `
            <div class="ai-location-select-wrap">
              <span class="ai-location-select-hint"><i data-lucide="map"></i> State / Region</span>
              <select class="ai-filter-select" data-draft-filter="state" aria-label="State or Region">
                <option value="">✦ All States / Regions</option>
                ${states.map(s => `<option value="${escapeHTML(s)}" ${s === draft.state ? 'selected' : ''}>${escapeHTML(s)}</option>`).join('')}
              </select>
            </div>
          ` : ''}
          ${cities.length > 0 ? `
            <div class="ai-location-select-wrap">
              <span class="ai-location-select-hint"><i data-lucide="map-pin"></i> City</span>
              <select class="ai-filter-select" data-draft-filter="city" aria-label="City">
                <option value="">✦ All Cities</option>
                ${cities.map(ct => `<option value="${escapeHTML(ct)}" ${ct === draft.city ? 'selected' : ''}>${escapeHTML(ct)}</option>`).join('')}
              </select>
            </div>
          ` : ''}
        </div>
        <small class="ai-filter-help-text">
          ${draft.location ? `Filtering by: <strong>${escapeHTML(draft.location)}</strong>` : 'Filtering across all observed telemetry locations.'}
        </small>
      </div>
    </div>
  `;
}

function renderEntityFilterFieldHTML(domain, domainConfig, draft, entities, options) {
  if (domain === 'job') {
    const isAll = draft.scope === 'All';
    return `
      <div class="ai-filter-field">
        <div class="ai-filter-label-row">
          <label class="ai-filter-label" for="aiFilterCompany">Focus company</label>
          <span class="ai-filter-scope-badge ${isAll ? 'ai-filter-scope-badge--all' : 'ai-filter-scope-badge--fav'}">
            ${isAll ? 'All Companies' : `Favourites (${entities.length})`}
          </span>
        </div>
        <select class="ai-filter-select" id="aiFilterCompany" data-draft-filter="company" aria-label="Focus company">
          <option value="">${isAll ? 'All supported companies' : `All saved favourite companies (${entities.length})`}</option>
          ${entities.map(name => `<option value="${escapeHTML(name)}" ${name === draft.selectedCompany ? 'selected' : ''}>${escapeHTML(name)}</option>`).join('')}
        </select>
        <small class="ai-filter-help-text" id="aiFilterCompanyHelp">
          ${entities.length
            ? (draft.selectedCompany ? `Focused on: <strong>${escapeHTML(draft.selectedCompany)}</strong>` : (isAll ? 'Querying across all supported employers in indexed postings.' : `Querying across all ${entities.length} saved favourite companies.`))
            : (draft.scope === 'Favourites' ? 'No saved favourite companies found in job data.' : 'No companies are present in available job postings.')}
        </small>
      </div>
      <div class="ai-filter-field">
        <div class="ai-filter-label-row">
          <label class="ai-filter-label" for="aiFilterRole">Focus role</label>
        </div>
        <select class="ai-filter-select" id="aiFilterRole" data-draft-filter="role" aria-label="Focus role">
          <option value="">All supported roles</option>
          ${options.roles.map(name => `<option value="${escapeHTML(name)}" ${name === draft.selectedRole ? 'selected' : ''}>${escapeHTML(name)}</option>`).join('')}
        </select>
        <small class="ai-filter-help-text" id="aiFilterRoleHelp">
          ${draft.selectedRole ? `Focused on role: <strong>${escapeHTML(draft.selectedRole)}</strong>` : 'Querying across all indexed role titles.'}
        </small>
      </div>`;
  }
  if (domain === 'skill') {
    const isAll = draft.scope === 'All';
    const currentSelected = draft.selectedSkill || (draft.selectedSkills && draft.selectedSkills[0]) || '';
    const favCount = entities.length;
    const selectedCount = draft.selectedSkills?.length || (draft.selectedSkill ? 1 : 0);
    return `
      <div class="ai-filter-field">
        <div class="ai-filter-label-row">
          <label class="ai-filter-label" for="aiFilterFocusSkill">Focus skills</label>
          <span class="ai-filter-scope-badge ${isAll ? 'ai-filter-scope-badge--all' : 'ai-filter-scope-badge--fav'}">
            ${isAll ? 'All supported skills' : (favCount > 0 ? (selectedCount ? `${selectedCount} of ${favCount} selected` : `0 of ${favCount} selected`) : 'No Favourites')}
          </span>
        </div>
        <select class="ai-filter-select" id="aiFilterFocusSkill" data-draft-filter="entity" aria-label="Focus skills">
          ${isAll ? `
            <option value="" ${!currentSelected ? 'selected' : ''}>All supported skills</option>
            ${entities.map(name => `<option value="${escapeHTML(name)}" ${name === currentSelected ? 'selected' : ''}>${escapeHTML(filterEntityOptionLabel(domain, name))}</option>`).join('')}
          ` : `
            ${favCount > 0 ? `
              <option value="" ${!currentSelected ? 'selected' : ''}>All saved favourite skills (${favCount})</option>
              ${entities.map(name => `<option value="${escapeHTML(name)}" ${name === currentSelected ? 'selected' : ''}>${escapeHTML(filterEntityOptionLabel(domain, name))}</option>`).join('')}
            ` : `
              <option value="" disabled selected>No saved favourite skills</option>
            `}
          `}
        </select>
        <small class="ai-filter-help-text" id="aiFilterFocusHelp">
          ${isAll
            ? (currentSelected ? `Focused on: <strong>${escapeHTML(currentSelected)}</strong>` : 'Querying across all supported skills in the catalog without restriction.')
            : (favCount > 0
                ? (currentSelected ? `Focused on favourite: <strong>${escapeHTML(currentSelected)}</strong>` : `Querying across all ${favCount} saved favourite skills.`)
                : `No favourite skills saved yet. You can star skills in the <a href="#/individual/skills" style="color:var(--domain-accent, #B22DEF); text-decoration:underline;">Skill Intelligence Catalog</a>.`)}
        </small>
      </div>`;
  }
  const isMarketAll = draft.scope === 'All';
  const selectedMarket = draft.selectedCompany || '';
  return `
    <div class="ai-filter-field">
      <div class="ai-filter-label-row">
        <label class="ai-filter-label" for="aiFilterMarketEntity">Focus company</label>
        <span class="ai-filter-scope-badge ${isMarketAll ? 'ai-filter-scope-badge--all' : 'ai-filter-scope-badge--fav'}">
          ${isMarketAll ? 'All Companies' : `Favourites (${entities.length})`}
        </span>
      </div>
      <select class="ai-filter-select" id="aiFilterMarketEntity" data-draft-filter="entity" aria-label="${escapeHTML(domainConfig.focusLabel)}">
        <option value="" ${!selectedMarket ? 'selected' : ''}>${isMarketAll ? 'All supported companies' : `All saved favourite companies (${entities.length})`}</option>
        ${entities.map(name => `<option value="${escapeHTML(name)}" ${name === selectedMarket ? 'selected' : ''}>${escapeHTML(filterEntityOptionLabel(domain, name))}</option>`).join('')}
      </select>
      <small class="ai-filter-help-text" id="aiFilterMarketHelp">
        ${entities.length
          ? (selectedMarket ? `Focused on: <strong>${escapeHTML(selectedMarket)}</strong>` : (isMarketAll ? 'Querying across all indexed market entities.' : `Querying across all ${entities.length} saved favourite companies.`))
          : (draft.scope === 'Favourites' ? 'No saved favourite companies found in market catalogue.' : 'No compatible entities available.')}
      </small>
    </div>`;
}

// ----------------------------------------------------------------------------
// HTML Generation (Exact Reference Image 2 Composition in TalentScope Brand Colors)
// ----------------------------------------------------------------------------
function generatePageHTML() {
  const activeDomain = getActiveDomainKey();
  const domState = getActiveDomainSession(activeDomain);
  let committed = getCommittedFilterSnapshot(activeDomain);
  const isBusy = currentAiState === 'analyzing' || currentAiState === 'thinking';
  const freshness = resolveFreshnessInfo(domState);
  const currentDomainCfg = DOMAIN_CONFIG[activeDomain] || DOMAIN_CONFIG.skill;
  const allowedScopes = currentDomainCfg.scopes || (activeDomain === 'skill' ? ['All Skills', 'My Skills', 'Favourites'] : ['All Companies', 'Favourites']);
  const observedOptions = getObservedFilterOptions(activeDomain, domState.history);
  const supportedEntities = getSelectableEntities(activeDomain, committed.scope, observedOptions);
  const committedEntityKey = activeDomain === 'skill' ? 'selectedSkill' : 'selectedCompany';
  if (domState.filters[committedEntityKey] && !supportedEntities.includes(domState.filters[committedEntityKey])) domState.filters[committedEntityKey] = '';
  if (domState.filters.location && !observedOptions.locations.includes(domState.filters.location)) domState.filters.location = '';
  if (!observedOptions.ranges.includes(domState.filters.timeRange)) domState.filters.timeRange = observedOptions.ranges.at(-1) || 'Max Available';
  domState.filters.timeframe = domState.filters.timeRange;
  committed = getCommittedFilterSnapshot(activeDomain);
  const draft = draftFilterState || committed;
  const selectableEntities = getSelectableEntities(activeDomain, draft.scope, observedOptions);

  // Ensure committed scope is valid
  domState.filters.scope = committed.scope;

  const turns = Array.isArray(domState.history) ? domState.history : [];
  const reversedTurns = [...turns].map((t, idx) => ({ turn: t, originalIndex: idx })).reverse();
  const selectedEntityLabel = activeDomain === 'skill' && committed.selectedSkills.length > 1
    ? `${committed.selectedSkills.length} skills selected`
    : committed.selectedSkill || committed.selectedCompany || committed.selectedRole || 'All supported entities';
  const hasConversation = turns.length > 0 || Boolean(domState.pendingQuestion) || isBusy;
  const profileName = userProfileState?.name || 'Your account';
  const profileInitial = profileName.trim().split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase() || 'U';

  // Capabilities for active domain (Requirement 7)
  const capabilities = getDomainCapabilities(activeDomain);
  if ((capabilityCatalog || capabilityCatalogLoadError) && domState.selectedFeature && !capabilities.some(capability => capability.id === domState.selectedFeature)) {
    domState.selectedFeature = null;
    domState.selectionReason = '';
    saveAiSession(activeSession, resolveCurrentUserId());
  }
  const activeFeatureId = domState.selectedFeature || null;
  const activeFeature = activeFeatureId ? capabilities.find(c => c.id === activeFeatureId) : null;
  const isGuidedMode = getAssistantComposerMode(domState) === 'guided';

  // Modern Search/Composer Box (Modeled on Reference Images 2 & 4)
  const renderComposerHTML = (isBottomDock = false) => `
    <div class="ai-composer-wrapper ${isBottomDock ? 'is-bottom-dock' : ''}">
      <div class="ai-composer-card ${isBusy ? 'is-busy' : ''} ${activeFeature && !isGuidedMode ? 'has-feature-mode' : ''}" ${activeFeature && !isGuidedMode ? `style="--feature-accent:${escapeHTML(activeFeature.color)};"` : ''}>
        <!-- Top Meta Bar Inside Composer -->
        <div class="ai-composer-meta-row">
          <div class="ai-composer-meta-left">
            <div class="ai-composer-engine-badge">
              <span class="ai-composer-gem-icon">
                <svg viewBox="0 0 20 20" fill="none" class="ai-gem-sparkle-svg">
                  <defs>
                    <linearGradient id="compGemGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#38BDF8" />
                      <stop offset="50%" stop-color="#B22DEF" />
                      <stop offset="100%" stop-color="#8B3DFF" />
                    </linearGradient>
                  </defs>
                  <path d="M10 2L12 7.5L17.5 10L12 12.5L10 18L8 12.5L2.5 10L8 7.5L10 2Z" fill="url(#compGemGrad)" />
                  <circle cx="10" cy="10" r="1.5" fill="#FFFFFF" />
                </svg>
              </span>
              <span class="ai-composer-engine-title">Intelligence Assistant</span>
              <span class="ai-composer-engine-version">v2.7</span>
            </div>
          </div>
          <div class="ai-composer-meta-right">
            <span class="ai-composer-powered">Powered by TalentScope.ai</span>
          </div>
        </div>

        ${isGuidedMode ? `
          <div class="ai-composer-feature-chip-banner ai-composer-feature-chip-banner--guided" aria-label="Guided Intelligence Journey active">
            <div class="ai-feature-chip-pill">
              <span class="ai-feature-chip-icon-wrap"><i data-lucide="route" class="ai-feature-chip-icon"></i></span>
              <strong class="ai-feature-chip-title">Guided Intelligence</strong>
              <span class="ai-feature-chip-badge">Journey mode</span>
              ${activeFeature ? `<span class="ai-feature-chip-badge">Next: ${escapeHTML(activeFeature.title)}</span>` : ''}
              <button type="button" class="ai-feature-chip-remove-btn" id="btnRemoveGuidedJourney" title="Exit guided mode" aria-label="Exit Guided Intelligence Journey">
                <i data-lucide="x"></i>
              </button>
            </div>
            <small class="ai-feature-chip-hint">${activeFeature
              ? escapeHTML(domState.selectionReason || `The planner selected ${activeFeature.title} for this step.`)
              : domState.guidedJourney.isComplete
                ? 'This journey is complete. Your next question will use normal chat.'
                : 'The planner will choose the first supported analysis after you submit your question.'}</small>
          </div>
        ` : activeFeature ? `
          <!-- Active Selected Capability Removable Chip (Requirement 6) -->
          <div class="ai-composer-feature-chip-banner ai-composer-feature-chip-banner--feature" style="--feature-accent:${escapeHTML(activeFeature.color)};" aria-label="Attached capability">
            <div class="ai-feature-chip-pill">
              <span class="ai-feature-chip-icon-wrap">
                <i data-lucide="${activeFeature.icon}" class="ai-feature-chip-icon"></i>
              </span>
              <strong class="ai-feature-chip-title">${escapeHTML(activeFeature.title)}</strong>
              <span class="ai-feature-chip-badge">Focused mode</span>
              <button type="button" class="ai-feature-chip-remove-btn" id="btnRemoveActiveFeature" title="Remove capability" aria-label="Remove capability ${escapeHTML(activeFeature.title)}">
                <i data-lucide="x"></i>
              </button>
            </div>
            <small class="ai-feature-chip-hint">${escapeHTML(domState.selectionReason || activeFeature.desc)}</small>
          </div>
        ` : ''}

          ${activeFeature && !isGuidedMode && activeFeature.suggestedQuestions?.length ? `
            <div class="ai-feature-suggested-questions" aria-label="Suggested questions for ${escapeHTML(activeFeature.title)}">
              <span class="ai-feature-suggestions-label">Try asking</span>
              ${activeFeature.suggestedQuestions.slice(0, 3).map(prompt => `
                <button type="button" class="ai-suggested-chip" data-feature-prompt="${escapeHTML(prompt)}" ${isBusy ? 'disabled' : ''}>
                  <i data-lucide="corner-down-right" class="ai-suggested-chip-icon"></i>
                  <span>${escapeHTML(prompt)}</span>
                </button>
              `).join('')}
            </div>
          ` : ''}

          <form class="ai-composer-form-inner" id="aiComposerForm">
          <div class="ai-composer-input-row">
            <textarea
              type="text"
              class="ai-composer-input"
              id="aiComposerInput"
              rows="2"
              placeholder="${escapeHTML(isGuidedMode
                ? domState.guidedJourney.isComplete
                  ? currentDomainCfg.placeholder
                  : 'Ask your question to begin a guided analysis…'
                : activeFeature
                  ? (activeFeature.promptHint || activeFeature.desc)
                  : currentDomainCfg.placeholder)}"
              autocomplete="off"
              aria-label="Ask a question in ${escapeHTML(currentDomainCfg.label)}"
              ${isBusy || capabilityPlanning ? 'disabled' : ''}
            >${escapeHTML(domState.draftQuestion || '')}</textarea>
            <button
              type="button"
              class="ai-composer-clear-btn"
              id="btnComposerClear"
              title="Clear question"
              aria-label="Clear question"
              style="display:${domState.draftQuestion && !isBusy && !capabilityPlanning ? 'inline-flex' : 'none'};"
            >
              <i data-lucide="x"></i>
            </button>
          </div>

          <!-- Bottom Actions Inside Composer -->
          <div class="ai-composer-bottom-bar">
            <div class="ai-composer-actions-left">
              <button
                type="button"
                class="ai-composer-plus-btn ${isFilterPopoverOpen ? 'is-open' : ''} ${activeFeature || isGuidedMode ? 'is-hidden' : ''}"
                id="btnOpenFilters"
                aria-expanded="${isFilterPopoverOpen}"
                aria-haspopup="dialog"
                aria-controls="aiUnifiedFilterPanel"
                title="Select Capabilities & Features"
                ${!capabilityCatalog || !capabilities.length || capabilityPlanning ? 'disabled' : ''}
                style="${activeFeature || isGuidedMode ? 'display: none !important;' : ''}"
              >
                <i data-lucide="plus"></i>
                <span>Features</span>
              </button>
              ${activeFeature && !isGuidedMode ? `
                <button type="button" class="ai-composer-change-cap-btn" id="btnChangeActiveFeature" title="Change to a different capability">
                  <i data-lucide="refresh-cw"></i>
                  <span>Change Feature</span>
                </button>
              ` : ''}
              ${!activeFeature && !isGuidedMode ? `
                <button type="button" class="ai-composer-guided-btn" id="btnStartGuidedJourney" aria-label="Start Guided Intelligence Journey" title="The planner will choose the first supported capability and recommend evidence-based next steps" ${isBusy || capabilityPlanning || !capabilityCatalog ? 'disabled' : ''}>
                  <i data-lucide="route"></i>
                  <span>Guided Intelligence</span>
                </button>
              ` : ''}
            </div>
            <div class="ai-composer-actions-right">
              <button type="submit" class="ai-composer-send-btn" id="btnComposerSend" ${isBusy ? 'disabled aria-busy="true"' : ''}>
                ${isBusy
                  ? `<i data-lucide="loader-2" class="ai-spin"></i><span>Analyzing...</span>`
                  : `<span>Send</span><i data-lucide="arrow-right"></i>`}
              </button>
            </div>
          </div>
        </form>
      </div>

      ${!isBottomDock && !activeFeature && !isGuidedMode ? `
        <!-- Two Suggested Questions & Auto-Recommend Action Outside Composer (Sections 7 & 8) -->
        <div class="ai-suggested-prompts-row" aria-label="Suggested questions and actions">
          <button type="button" class="ai-recommend-action-chip" id="btnRecommendAnalysis" title="Ask the intelligence planner to select a supported analysis" ${isBusy || capabilityPlanning || !capabilityCatalog ? 'disabled' : ''}>
            <i data-lucide="sparkles"></i>
            <span><strong>${capabilityPlanning ? 'Planning analysis…' : 'Recommend My Analysis'}</strong></span>
          </button>
          ${(currentDomainCfg.suggestedQuestions || []).slice(0, 2).map(prompt => `
            <button type="button" class="ai-suggested-chip" data-prompt="${escapeHTML(prompt)}" ${isBusy ? 'disabled' : ''}>
              <i data-lucide="corner-down-right" class="ai-suggested-chip-icon"></i>
              <span>${escapeHTML(prompt)}</span>
            </button>
          `).join('')}
        </div>
      ` : ''}
    </div>
  `;

  return `
    <div class="ai-assistant-page ai-ref-workspace-page ${hasConversation ? 'has-conversation' : 'is-landing'}" data-active-domain="${escapeHTML(activeDomain)}">
      <!-- 1. Full-Width Workspace Header Spanning Container -->
      <header class="ai-floating-header" role="banner">
        <div class="ai-header-left">
          <div class="ai-header-brand-mark" aria-hidden="true">
            <i data-lucide="sparkles"></i>
          </div>
          <div class="ai-header-brand-text">
            <span class="ai-header-title">TalentScope.ai</span>
            <span class="ai-header-subtitle">Workforce intelligence for your next decision</span>
          </div>
        </div>

        <div class="ai-header-right">
          <button type="button" class="ai-header-new-chat" id="btnNewAiConversation">
            <i data-lucide="plus"></i><span>New chat</span>
          </button>
          <span class="ai-freshness-pill" id="aiStateIndicator" title="Latest verified backend observation date">
            <span class="ai-freshness-dot ${isBusy ? 'is-busy' : freshness.isLive ? 'is-live' : ''}"></span>
            <span id="aiStateText">${escapeHTML(currentAiState === 'idle' ? freshness.label : getStateLabel(currentAiState))}</span>
          </span>

          <button type="button" class="ai-avatar-btn" id="btnAssistantProfile" aria-label="Open ${escapeHTML(profileName)} menu" aria-haspopup="menu" aria-expanded="${isProfileMenuOpen}" title="${escapeHTML(profileName)}">
            <span>${escapeHTML(profileInitial)}</span>
          </button>

          ${isProfileMenuOpen ? `
            <div class="ai-profile-popover" id="aiAssistantProfileMenu" role="menu" aria-label="Assistant options">
              <div class="ai-profile-popover-header">
                <div class="ai-profile-name">${escapeHTML(profileName)}</div>
                <div class="ai-profile-role">Intelligence Workspace</div>
              </div>
              <button type="button" role="menuitem" class="ai-profile-menu-item" id="btnToggleHistoryModal">
                <i data-lucide="history"></i><span>History</span>
              </button>
            </div>
          ` : ''}
        </div>
      </header>

      <!-- 2. Centered Conversation History Modal -->
      ${(isHistoryModalOpen || isHistoryDrawerOpen) ? `
        <div class="ai-modal-backdrop" id="aiHistoryBackdrop">
          <div class="ai-history-modal" id="aiHistorySidebar" role="dialog" aria-modal="true" aria-labelledby="aiHistoryTitle">
            <div class="ai-modal-header">
              <div class="ai-modal-header-left">
                <div class="ai-modal-icon-badge"><i data-lucide="history"></i></div>
                <h2 id="aiHistoryTitle" class="ai-modal-title">${escapeHTML(currentDomainCfg.label)} History</h2>
              </div>
              <div class="ai-modal-header-right">
                <button type="button" class="ai-modal-new-btn" id="btnSidebarNewChat" title="Start a new chat">
                  <i data-lucide="plus"></i><span>New Chat</span>
                </button>
                <button type="button" class="ai-modal-close-btn" id="btnCloseHistoryModal" aria-label="Close history modal">
                  <i data-lucide="x"></i>
                </button>
              </div>
            </div>

            <div class="ai-modal-search-bar">
              <i data-lucide="search"></i>
              <input
                type="search"
                id="aiHistorySearchInput"
                class="ai-modal-search-input"
                value="${escapeHTML(historySearchQuery)}"
                placeholder="Search ${escapeHTML(currentDomainCfg.label.toLowerCase())} conversations..."
                aria-label="Search conversations"
              />
            </div>

            <div id="aiHistoryGroupedList" class="ai-modal-body-list">
              ${renderGroupedHistoryItemsHTML()}
            </div>

            <div class="ai-modal-footer">
              <button type="button" class="ai-modal-footer-reset" id="btnClearAiSession">
                <i data-lucide="rotate-ccw"></i><span>Reset ${escapeHTML(currentDomainCfg.label)} Session</span>
              </button>
              <button type="button" class="ai-modal-footer-close" id="btnCloseHistoryModalBottom">Close</button>
            </div>
          </div>
        </div>
      ` : ''}

      ${hasConversation ? `
        <!-- CONVERSATION VIEW: Distraction-free conversational interface (Requirement 10) -->
        <main class="ai-conversation-view">
          <section class="ai-conversation-stream" id="aiConversationStream" aria-live="polite">
            ${capabilityCatalogLoadError ? `
              <div class="ai-capability-empty-state" role="alert">
                Supported capabilities could not be loaded.
                <button type="button" id="btnRetryCapabilityCatalog">Retry</button>
              </div>
            ` : ''}
            ${turns.map((turn, index) => renderTurnHTML(turn, index, index === turns.length - 1, activeDomain)).join('')}

            ${domState.pendingQuestion ? `
              <div class="ai-user-turn-wrapper">
                <div class="ai-user-message-bubble">
                  <div class="ai-user-message-header">
                    <span class="ai-user-badge"><i data-lucide="user"></i> You</span>
                    <span class="ai-user-time">Just now</span>
                  </div>
                  <div class="ai-user-message-text">${escapeHTML(domState.pendingQuestion)}</div>
                </div>
              </div>
            ` : ''}

            ${isBusy ? `
              <div class="ai-analyzing-card" role="status">
                <div class="ai-analyzing-orb"></div>
                <div class="ai-analyzing-text">
                  <strong class="ai-analyzing-title">Analyzing with ${escapeHTML(currentDomainCfg.label)}...</strong>
                  <span class="ai-analyzing-desc">Retrieving verified evidence telemetry and evaluating domain readiness.</span>
                </div>
              </div>
            ` : ''}
          </section>

          <!-- Sticky Bottom Composer Dock (Contained within main area, never overlaps sidebar) -->
          <footer class="ai-bottom-composer-dock">
            ${renderComposerHTML(true)}
          </footer>
        </main>
      ` : `
        <!-- LANDING VIEW: Order: 1. Header, 2. Welcome (Badge + Branded Emblem + Title + Tagline), 3. Capability Cards ABOVE Composer, 4. Composer Box, 5. Suggested Chips, 6. Footer -->
        <main class="ai-workspace-landing">
          <!-- 2. Welcome Section with Badge, 3D Iridescent Crystal Orb Animation, Title & Tagline -->
          <section class="ai-welcome-section" aria-label="Welcome">
            <div class="ai-welcome-badge">
              <i data-lucide="sparkles"></i>
              <span>TalentScope.ai</span>
            </div>

            <!-- Premium TalentScope AI Logo Orbital Stage (Section 3) -->
            <div class="ai-hero-visual-stage" aria-hidden="true">
              <div class="ai-hero-logo-nexus">
                <div class="ai-hero-aura-glow"></div>
                <div class="ai-hero-pulse-wave ai-hero-pulse-1"></div>
                <div class="ai-hero-pulse-wave ai-hero-pulse-2"></div>
                <div class="ai-hero-orbit-ring ai-hero-ring-1">
                  <span class="ai-orbit-particle ai-particle-1"></span>
                </div>
                <div class="ai-hero-orbit-ring ai-hero-ring-2">
                  <span class="ai-orbit-particle ai-particle-2"></span>
                </div>
                <div class="ai-hero-orbit-ring ai-hero-ring-3">
                  <span class="ai-orbit-particle ai-particle-3"></span>
                </div>
                <div class="ai-hero-logo-emblem">
                  <span class="ai-hero-brand-mark"><i data-lucide="sparkles"></i></span>
                </div>
              </div>
            </div>

            <h1 class="ai-welcome-title">Understand change. <span class="ai-welcome-gradient">Decide what comes next.</span></h1>
            <p class="ai-welcome-desc">Explore evidence-backed skill, market, and job intelligence.</p>
          </section>

          <!-- 3. Capability Discovery Cards or Focused Analysis Banner (Sections 5 & 6) -->
          ${!domState.selectedFeature && !isGuidedMode ? `
            <section class="ai-feature-nav-section" aria-label="Explore intelligence capabilities">
              ${capabilityCatalog ? (capabilities.length ? `
                <div class="ai-feature-cards-grid ai-feature-count-${capabilities.length}">
                  ${capabilities.map((feat, featureIndex) => `
                    <button
                      type="button"
                      class="ai-feature-card ai-feature-card--${featureIndex + 1} ai-ref-feature-card--${featureIndex + 1}"
                      data-open-explainer="${escapeHTML(feat.id)}"
                      aria-haspopup="dialog"
                      title="Capability overview: ${escapeHTML(feat.title)}"
                      ${isBusy ? 'disabled' : ''}
                    >
                      <div class="ai-feature-motif-box" style="color:${feat.color}; background:${feat.color}15;">
                        <i data-lucide="${escapeHTML(feat.icon)}"></i>
                      </div>
                      <div class="ai-feature-content">
                        <h3 class="ai-feature-title">${escapeHTML(feat.title)}</h3>
                        <p class="ai-feature-desc">${escapeHTML(feat.cardTagline || feat.desc)}</p>
                      </div>
                    </button>
                  `).join('')}
                </div>
              ` : '<p class="ai-capability-empty-state">No executable capabilities are currently registered for this domain.</p>')
                : capabilityCatalogLoadError
                  ? '<div class="ai-capability-empty-state" role="alert">Supported capabilities could not be loaded. <button type="button" id="btnRetryCapabilityCatalog">Retry</button></div>'
                  : '<p class="ai-capability-empty-state" role="status">Loading supported capabilities…</p>'}
            </section>
          ` : ''}

          <!-- 4. Search Composer Box & Suggested Chips -->
          ${renderComposerHTML(false)}

          <!-- In-flight progress banner if submitted from landing -->
          ${isBusy ? `
            <div style="max-width:1140px; margin:0 auto 24px; padding:0 20px;">
              <div class="ai-analyzing-card" role="status">
                <div class="ai-analyzing-orb"></div>
                <div class="ai-analyzing-text">
                  <strong class="ai-analyzing-title">Analyzing with ${escapeHTML(currentDomainCfg.label)}...</strong>
                  <span class="ai-analyzing-desc">Checking evidence telemetry and computing grounded response.</span>
                </div>
              </div>
            </div>
          ` : ''}

          <!-- 5. Minimal Footer Pinned to Bottom -->
          <footer class="ai-landing-footer">
            <span><strong>TALENTSCOPE.AI</strong> / Smarter Insights. Better Decisions.</span>
          </footer>
        </main>
      `}

      <!-- Compact Features Popover Panel (Opened via Features Button in Composer, Requirement 6) -->
      ${isFilterPopoverOpen ? `
        <section class="ai-filter-popover-portal" id="aiUnifiedFilterPanel" role="dialog" aria-labelledby="aiFilterTitle" aria-modal="false">
          <div class="ai-filter-panel-header">
            <h3 class="ai-filter-panel-title" id="aiFilterTitle">
              <i data-lucide="sparkles"></i>
              <span>Choose a feature</span>
            </h3>
            <div class="ai-filter-header-actions">
              <button type="button" class="ai-filter-close-btn" data-filter-action="cancel" aria-label="Close" id="btnCloseFeaturePopover">
                <i data-lucide="x"></i>
              </button>
            </div>
          </div>

          <!-- Vertical Single-Column List: 1 feature per row (Requirement 6) -->
          ${capabilities.length ? `<div class="ai-feature-selector-list" role="listbox" aria-label="Available capabilities">
            ${capabilities.map((feat, featureIndex) => {
              const isSelected = domState.selectedFeature === feat.id;
              return `
                <button
                  type="button"
                  class="ai-feature-selector-item ${isSelected ? 'is-selected' : ''} ai-ref-feature-card--${featureIndex + 1}"
                  data-select-feature-id="${escapeHTML(feat.id)}"
                  role="option"
                  aria-selected="${isSelected}"
                >
                  <div class="ai-feat-item-icon" style="color:${feat.color}; background:${feat.color}15;">
                    <i data-lucide="${feat.icon}"></i>
                  </div>
                  <div class="ai-feat-item-info">
                    <strong class="ai-feat-item-name">${escapeHTML(feat.title)}</strong>
                  </div>
                  <div class="ai-feat-item-check" aria-hidden="true">
                    ${isSelected ? '<i data-lucide="check"></i>' : ''}
                  </div>
                </button>
              `;
            }).join('')}
          </div>` : `
            <div class="ai-capability-empty-state" role="${capabilityCatalogLoadError ? 'alert' : 'status'}">
              ${capabilityCatalogLoadError
                ? 'Supported capabilities could not be loaded.'
                : 'Loading supported capabilities…'}
              ${capabilityCatalogLoadError ? '<button type="button" id="btnRetryCapabilityCatalog">Retry</button>' : ''}
            </div>
          `}

        </section>
      ` : ''}

      <!-- Capability Explainer Modal (Opened via Capability Card Click, Requirement 5) -->
      ${activeExplainerCapability ? `
        <div class="ai-modal-backdrop" id="aiExplainerBackdrop">
          <div class="ai-capability-explainer-card" role="dialog" aria-modal="true" aria-labelledby="aiExplainerTitle">
            <div class="ai-explainer-header">
              <div class="ai-explainer-header-left">
                <div class="ai-explainer-icon-box" style="color:${activeExplainerCapability.color}; background:${activeExplainerCapability.color}18;">
                  <i data-lucide="${activeExplainerCapability.icon}"></i>
                </div>
                <div>
                  <h2 id="aiExplainerTitle" class="ai-explainer-title">${escapeHTML(activeExplainerCapability.title)}</h2>
                </div>
              </div>
              <button type="button" class="ai-modal-close-btn" id="btnCloseCapabilityExplainer" aria-label="Close capability explainer">
                <i data-lucide="x"></i>
              </button>
            </div>

            <div class="ai-explainer-body">
              <div class="ai-explainer-concept-card">
                <div class="ai-explainer-concept-visual" style="color:${activeExplainerCapability.color}; background:${activeExplainerCapability.color}15;">
                  <i data-lucide="${escapeHTML(activeExplainerCapability.icon)}"></i>
                </div>
                <p class="ai-explainer-concept-desc">${escapeHTML(activeExplainerCapability.desc)}</p>
              </div>
              <div class="ai-explainer-example">
                <span>Try asking</span>
                <p>&ldquo;${escapeHTML(activeExplainerCapability.defaultPrompt.replace('{entity}', activeDomain === 'skill' ? 'Python' : (activeDomain === 'market' ? 'NVIDIA' : 'Software Engineers')))}&rdquo;</p>
              </div>
            </div>

            <div class="ai-explainer-footer">
              <span class="ai-explainer-footer-note">Preview only · Choose it from Features to use it.</span>
              <button type="button" class="ai-explainer-close-cta" id="btnCloseCapabilityExplainerBottom">Close</button>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

// ----------------------------------------------------------------------------
// Render Concise 6-Part Evidence-Based Result Card + Additional Insights
// ----------------------------------------------------------------------------
export function renderTurnChartOrBaselineHTML(turn, trendFact, facts, jobPostings) {
  if (jobPostings.length > 0) {
    return `
      <div class="ai-res-part ai-res-part--trend">
        <div class="ai-res-part-label">
          <i data-lucide="briefcase"></i>
          <span>3. Verified Job Postings (${jobPostings.length} Deduplicated)</span>
        </div>
        <div class="ai-res-postings-grid">
          ${jobPostings.slice(0, 6).map(p => `
            <div class="ai-res-posting-card">
              <div class="ai-res-posting-card__top">
                ${p.title ? `<strong>${escapeHTML(p.title)}</strong>` : ''}
                ${p.company ? `<span class="ai-res-posting-company">${escapeHTML(p.company)}</span>` : ''}
              </div>
              <div class="ai-res-posting-card__meta">
                ${p.location ? `<span><i data-lucide="map-pin"></i> ${escapeHTML(p.location)}</span>` : ''}
                ${p.posting_date ? `<span>· ${escapeHTML(String(p.posting_date).slice(0, 10))}</span>` : ''}
                ${p.skill ? `<span>· ${escapeHTML(p.skill)}</span>` : ''}
              </div>
              ${Array.isArray(p.required_skills) && p.required_skills.length
                ? `<div class="ai-res-posting-skills"><strong>Skills recorded:</strong> ${p.required_skills.map(escapeHTML).join(', ')}</div>`
                : '<div class="ai-res-posting-skills">No structured required-skill list was recorded.</div>'}
              ${safeStoredSourceUrl(p.source_url) ? `
                <a href="${escapeHTML(safeStoredSourceUrl(p.source_url))}" target="_blank" rel="noopener noreferrer" class="ai-res-posting-link">
                  View Source (${escapeHTML(p.source || 'Verified')}) ↗
                </a>
              ` : (p.source_url || p.source ? `<span class="ai-res-posting-source">Source: ${escapeHTML(p.source_url || p.source)}</span>` : '')}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Do not turn a series into a measured chart unless the backend explicitly
  // marked it ready and sourced it from real observations.
  if (trendFact && (
    (trendFact.readiness_state || trendFact.details?.readiness_status) !== 'ready'
    || trendFact.data_origin !== 'real'
  )) return '';

  const series = Array.isArray(trendFact?.details?.series) ? trendFact.details.series : [];
  const validSeries = series.filter(point => {
    const value = point.value ?? point.metric_value;
    return value !== null && value !== undefined && Number.isFinite(Number(value));
  });
  const obsCount = Number(trendFact?.details?.observation_count ?? series.length ?? 0);

  if (series.length >= 2 && validSeries.length === series.length) {
    const vals = validSeries.map(pt => Number(pt.value ?? pt.metric_value));
    const maxV = Math.max(...vals, 1);
    const minV = Math.min(...vals, 0);
    const span = Math.max(maxV - minV, 1);
    const coords = vals.map((v, idx) => {
      const x = 28 + (idx / Math.max(1, vals.length - 1)) * 424;
      const y = 96 - ((v - minV) / span) * 68;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const isUp = vals[vals.length - 1] >= vals[0];
    const stroke = isUp ? '#10B981' : '#EF4444';

    return `
      <div class="ai-res-part ai-res-part--trend">
        <div class="ai-res-part-label">
          <i data-lucide="trending-up"></i>
          <span>3. Observed Trend (${validSeries.length} Verified Periods · ${escapeHTML(String(trendFact?.period || 'Historical Window'))})</span>
        </div>
        <p class="ai-res-chart-context">${escapeHTML([trendFact?.details?.provider, trendFact?.details?.signal_type, trendFact?.details?.metric, trendFact?.details?.value_unit].filter(Boolean).join(' · '))}</p>
        <div class="ai-res-mini-chart-box">
          <svg viewBox="0 0 480 116" class="ai-res-trend-svg" role="img" aria-label="Observed multi-period trend from ${escapeHTML([trendFact?.details?.provider, trendFact?.details?.metric, trendFact?.details?.value_unit].filter(Boolean).join(', '))}">
            <line x1="28" y1="28" x2="452" y2="28" stroke="#EFE6F7" stroke-width="1" stroke-dasharray="3 3" />
            <line x1="28" y1="62" x2="452" y2="62" stroke="#EFE6F7" stroke-width="1" stroke-dasharray="3 3" />
            <line x1="28" y1="96" x2="452" y2="96" stroke="#E2D4F0" stroke-width="1" />
            <polyline points="${coords}" fill="none" stroke="${stroke}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
            ${vals.map((v, idx) => {
              const x = 28 + (idx / Math.max(1, vals.length - 1)) * 424;
              const y = 96 - ((v - minV) / span) * 68;
              return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${stroke}" stroke="#FFFFFF" stroke-width="1.5" />`;
            }).join('')}
          </svg>
          <div class="ai-res-chart-axis">
            <span>${escapeHTML(String(validSeries[0]?.period || 'Start'))}</span>
            <span>${escapeHTML(String(validSeries[validSeries.length - 1]?.period || 'Latest'))}</span>
          </div>
        </div>
      </div>
    `;
  }

  if (trendFact?.details && obsCount >= 2) {
    return `
      <div class="ai-res-part ai-res-part--trend">
        <div class="ai-res-part-label">
          <i data-lucide="trending-up"></i>
          <span>3. Observed Trend (${escapeHTML(String(trendFact.period || 'Multi-Period Window'))})</span>
        </div>
        <div class="ai-res-telemetry-strip">
          <div class="ai-res-telemetry-cell">
            <span>Direction</span>
            <strong>${escapeHTML(String(trendFact.metric_value || 'Observed'))}</strong>
          </div>
          <div class="ai-res-telemetry-cell">
            <span>Theil-Sen Slope</span>
            <strong>${trendFact.details.slope_per_period != null ? `${trendFact.details.slope_per_period > 0 ? '+' : ''}${trendFact.details.slope_per_period}/period` : 'N/A'}</strong>
          </div>
          <div class="ai-res-telemetry-cell">
            <span>Window Change</span>
            <strong>${trendFact.details.whole_window_pct_change != null ? `${trendFact.details.whole_window_pct_change > 0 ? '+' : ''}${trendFact.details.whole_window_pct_change}%` : 'N/A'}</strong>
          </div>
          <div class="ai-res-telemetry-cell">
            <span>Latest MoM</span>
            <strong>${trendFact.details.latest_mom_pct_change != null ? `${trendFact.details.latest_mom_pct_change > 0 ? '+' : ''}${trendFact.details.latest_mom_pct_change}%` : 'N/A'}</strong>
          </div>
        </div>
      </div>
    `;
  }

  // Honest Single-Period Baseline Card when <2 historical points exist
  const primaryFact = facts[0] || null;
  return `
    <div class="ai-res-part ai-res-part--trend">
      <div class="ai-res-part-label">
        <i data-lucide="activity"></i>
        <span>3. Trend & Baseline Status</span>
      </div>
      <div class="ai-res-single-baseline-card">
        <div class="ai-res-single-baseline-card__badge">
          <i data-lucide="info"></i>
          <span>Single-Period Baseline (Requires ≥2 periods for trend curve)</span>
        </div>
        <p>
          ${primaryFact
            ? `Recorded baseline for <strong>${escapeHTML(primaryFact.metric_name)}</strong>: <strong>${escapeHTML(String(primaryFact.metric_value))}${primaryFact.unit ? ` ${escapeHTML(primaryFact.unit)}` : ''}</strong> (${escapeHTML(primaryFact.source || 'Verified Store')}${primaryFact.period ? ` · ${escapeHTML(primaryFact.period)}` : ''}). Multi-period directional trend lines are withheld until ≥2 compatible historical snapshots are verified.`
            : 'Insufficient multi-period historical points to plot a directional trend curve. Zero synthetic trend lines are fabricated.'}
        </p>
      </div>
    </div>
  `;
}

function buildSupportedInsightChips(turn, activeDomain) {
  const relevantEntityTypes = activeDomain === 'skill'
    ? new Set(['skill', 'technology'])
    : activeDomain === 'market'
      ? new Set(['company', 'skill', 'technology'])
      : new Set(['occupation', 'role']);
  const entity = (turn.facts || []).find(fact =>
    fact.entity_name && fact.quality_state === 'valid' && relevantEntityTypes.has(fact.entity_type)
  )?.entity_name || extractEntityCandidate(turn.userQuestion || '');

  const caps = turn.capabilities || {};
  const sh = caps.skill_health?.payload;
  const hl = caps.skill_half_life?.payload;
  const fc = caps.forecast?.payload;

  const chips = [];
  if (activeDomain === 'skill') {
    chips.push({
      label: `Skill Health${sh?.health_category ? ` (${sh.health_category})` : ''}`,
      icon: 'heart-pulse',
      prompt: `What is the current skill health and ecosystem vitality for ${entity}?`
    });
    chips.push({
      label: `Skill Half-Life${hl?.half_life_months != null ? ` (${hl.half_life_months}m)` : ''}`,
      icon: 'hourglass',
      prompt: `What is the adaptive skill half-life and freshness decay rate for ${entity}?`
    });
    chips.push({
      label: `Future Skill Relevance${fc?.status === 'ready' ? ' (Ready)' : ''}`,
      icon: 'sparkles',
      prompt: `What is the future skill relevance and forecasted demand trajectory for ${entity}?`
    });
    chips.push({
      label: 'Adjacent Skills & Skill Gaps',
      icon: 'git-branch',
      prompt: `What skills are adjacent to ${entity} and what skill gaps should I close?`
    });
    chips.push({
      label: 'Recommended Actions',
      icon: 'compass',
      prompt: `What concrete learning and career actions do you recommend for ${entity}?`
    });
  } else if (activeDomain === 'market') {
    chips.push({
      label: 'Market-to-Person Impact',
      icon: 'user-check',
      prompt: `How do current market and technology adoption signals at ${entity} impact my skill profile?`
    });
    chips.push({
      label: 'Technology Adoption Signals',
      icon: 'cpu',
      prompt: `Which technologies show the strongest adoption signals across ${entity} and the market?`
    });
    chips.push({
      label: 'Hiring Momentum',
      icon: 'trending-up',
      prompt: `What hiring momentum and demand signals are observed for ${entity}?`
    });
    chips.push({
      label: 'Recommended Actions',
      icon: 'compass',
      prompt: `What actions should I take based on current market intelligence for ${entity}?`
    });
  } else {
    chips.push({
      label: 'Adjacent Skills & Role Gaps',
      icon: 'git-branch',
      prompt: `What core and adjacent skills are required for ${entity} postings compared to my profile?`
    });
    chips.push({
      label: 'Company Hiring Activity',
      icon: 'building-2',
      prompt: `Which companies have active verified job postings for ${entity}?`
    });
    chips.push({
      label: 'Market-to-Person Impact',
      icon: 'user-check',
      prompt: `How do current job requirements for ${entity} align with my skills?`
    });
    chips.push({
      label: 'Recommended Actions',
      icon: 'compass',
      prompt: `What career preparation actions do you recommend to target ${entity} roles?`
    });
  }
  const question = String(turn.userQuestion || '').toLocaleLowerCase();
  const duplicateChecks = [
    [/health/, /skill health|ecosystem health/],
    [/half.?life|freshness decay/, /half.?life|freshness decay/],
    [/future|forecast|predict/, /future relevance|forecast|prediction|trajectory/],
    [/action|recommend|learn next|what should i learn/, /recommend|action|learn/],
    [/workforce|person|company impact|disruption/, /market.to.person|impact|workforce/],
    [/adjacent skill|skill gap/, /adjacent skills|skill gaps/],
    [/hiring|job posting/, /hiring|company hiring/]
  ];
  return chips.filter(chip => !duplicateChecks.some(([asked, labels]) =>
    asked.test(question) && labels.test(chip.label)
  )).slice(0, 3);
}

function describeFactKind(fact) {
  if (fact.data_origin === 'demo') return 'Demo data';
  if (['reference', 'static_dataset'].includes(fact.data_origin)
    || fact.history_type === 'static_dataset'
    || String(fact.source || '').toLowerCase().startsWith('reference')) return 'Reference';
  if (fact.metric_kind) return fact.metric_kind;
  if (/forecast|prediction/i.test(fact.fact_type || '')) return 'Predicted';
  if (/readiness/i.test(fact.fact_type || '')) return 'Readiness';
  if (/trend|health|half.life|analysis/i.test(fact.fact_type || '')) return 'Derived';
  return 'Evidence-backed fact';
}

const unappliedFilterLabels = {
  salary_band: 'Salary range',
  seniority_level: 'Seniority level',
  remote_mode: 'Work arrangement',
  visa_sponsorship: 'Visa sponsorship',
  selected_companies: 'Company selection',
  selected_company: 'Company selection',
  scope: 'Data scope',
  selected_skill: 'Skill selection',
  selected_skills: 'Skill selection',
  selected_role: 'Role selection',
  country: 'Country selection'
};

export function formatUnappliedFilterDisclosure(filter) {
  const field = typeof filter?.filter === 'string' ? filter.filter : '';
  const reason = typeof filter?.reason === 'string' ? filter.reason.toLowerCase() : '';
  const label = unappliedFilterLabels[field] || 'Selected option';

  if (reason.includes('market observation source contains technology signals')) {
    return `${label} could not be applied because this market data contains technology signals, not company-specific market data.`;
  }
  if (field === 'scope') {
    return 'The selected data scope is not available for this domain. Choose one of the scopes offered in the filters.';
  }
  if (field === 'selected_skill') {
    return reason.includes('not a supported entity filter')
      ? 'Skill selection is not available in this intelligence domain.'
      : 'The selected skill does not match the committed skill selection.';
  }
  if (field === 'selected_role') {
    return reason.includes('not a supported entity filter')
      ? 'Role selection is not available in this intelligence domain.'
      : 'The selected role does not match the committed role selection.';
  }
  if (field === 'selected_company') {
    return 'The selected company does not match the committed company selection.';
  }
  if (field === 'country') {
    return 'Country selection is only available when searching stored job postings.';
  }
  if (['salary_band', 'seniority_level', 'remote_mode', 'visa_sponsorship'].includes(field)) {
    return `${label} cannot be applied because this information is not consistently available in the stored market data.`;
  }

  return `${label} could not be applied because it is not supported for this request.`;
}

export function resolveDisplayedCapabilityId(turn) {
  const usedCapabilities = Array.isArray(turn?.capabilities_used)
    ? turn.capabilities_used.filter(capabilityId => typeof capabilityId === 'string')
    : [];
  const plannedCapabilities = Array.isArray(turn?.planned_capabilities)
    ? turn.planned_capabilities.filter(capabilityId => typeof capabilityId === 'string')
    : [];
  const requestedCapability = turn?.capabilityId
    || turn?.requestContext?.capabilityId
    || turn?.requestContext?.filters?.selected_feature;
  if (turn?.executed_primary_capability && usedCapabilities.includes(turn.executed_primary_capability)) {
    return turn.executed_primary_capability;
  }
  if (turn?.planned_primary_capability && plannedCapabilities.includes(turn.planned_primary_capability)) {
    return turn.planned_primary_capability;
  }
  if (requestedCapability && usedCapabilities.includes(requestedCapability)) {
    return requestedCapability;
  }
  return usedCapabilities[0] || plannedCapabilities[0] || null;
}

function safeStoredSourceUrl(value) {
  if (typeof value !== 'string' || !value.startsWith('https://')) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function renderAssistantResponseDetails(turn) {
  const status = String(turn?.status || turn?.execution_status || '').toLowerCase();
  const limitations = Array.isArray(turn?.limitations) ? turn.limitations.filter(item => typeof item === 'string' && item.trim()) : [];
  const showLimitedData = ['partial', 'insufficient_data'].includes(status) || turn?.enough_data === false;
  const hasDemoOrigin = [
    ...(Array.isArray(turn?.sources) ? turn.sources : []),
    ...(Array.isArray(turn?.evidence) ? turn.evidence : []),
    ...(Array.isArray(turn?.facts) ? turn.facts : [])
  ].some(item => item?.data_origin === 'demo');
  const evidence = [
    ...(Array.isArray(turn?.sources) ? turn.sources : []),
    ...(Array.isArray(turn?.evidence) ? turn.evidence : [])
  ].map(item => {
    const type = item?.type || item?.signal_type || item?.measured_signal_type;
    const label = item?.label || item?.title || item?.description || item?.source;
    const sourceUrl = typeof item?.source_url === 'string' ? item.source_url : '';
    if (!type && !label && !sourceUrl) return '';
    const safeUrl = safeStoredSourceUrl(sourceUrl);
    return {
      source: label || sourceUrl,
      signal_type: type,
      source_url: safeUrl,
      data_origin: item?.data_origin
    };
  }).filter(Boolean);
  const jobCapabilityIds = [
    ...(Array.isArray(turn?.capabilities_used) ? turn.capabilities_used : []),
    ...(Array.isArray(turn?.planned_capabilities) ? turn.planned_capabilities : [])
  ];
  const jobFact = (Array.isArray(turn?.facts) ? turn.facts : [])
    .find(fact => fact?.fact_type === 'stored_job_postings');
  const jobDetails = jobFact?.details || {};
  const isJobSearch = turn?.intent === 'search_jobs'
    || jobCapabilityIds.some(id => ['job_verified_postings', 'job_posting_search'].includes(id))
    || Boolean(jobFact);
  const hasJobCounts = Number.isFinite(jobDetails.scanned_count)
    && Number.isFinite(jobDetails.matched_count)
    && typeof jobDetails.city === 'string';
  const clarification = typeof turn?.clarification === 'string' && turn.clarification.trim()
    ? turn.clarification
    : (Array.isArray(turn?.clarification_questions) ? turn.clarification_questions[0] : '');

  return `
    ${hasDemoOrigin ? '<p class="ai-demo-sample-banner" role="note">DEMO SAMPLE — illustrative data only; not live market evidence.</p>' : ''}
    ${turn?.understood ? `<p class="ai-understood-line"><strong>Understood:</strong> ${escapeHTML(turn.understood)}</p>` : ''}
    ${showLimitedData ? `<section class="ai-limited-data" aria-label="Limited data"><strong>Limited data</strong>${limitations.length ? `<ul>${limitations.map(item => `<li>${escapeHTML(item)}</li>`).join('')}</ul>` : ''}</section>` : ''}
    ${turn?.degraded === true ? '<p class="ai-degraded-banner" role="status">Gemini unavailable, showing deterministic answer</p>' : ''}
    ${evidence.length ? renderIntelligenceEvidencePanel({
      status: turn.status,
      evidence
    }, { title: 'Evidence snapshot', compact: true }) : ''}
    ${isJobSearch ? `<p class="ai-job-search-disclosure">${hasJobCounts ? `scanned ${jobDetails.scanned_count}, matched ${jobDetails.matched_count}, city ${escapeHTML(jobDetails.city)}` : ''}${hasJobCounts ? '<br>' : ''}live search is off</p>` : ''}
    ${clarification ? `<section class="ai-clarification" aria-label="Clarification"><p>${escapeHTML(clarification)}</p><div role="group" aria-label="Choose a follow-up">${['skills', 'jobs', 'market signals'].map(topic => `<button type="button" data-assistant-follow-up="${topic}">${topic}</button>`).join('')}</div></section>` : ''}
  `;
}

export function shouldShowUnappliedFilterDisclosure(turn) {
  const intent = String(turn?.intent || '').toLowerCase();
  const capabilityIds = [
    ...(Array.isArray(turn?.capabilities_used) ? turn.capabilities_used : []),
    ...(Array.isArray(turn?.planned_capabilities) ? turn.planned_capabilities : [])
  ];
  if (['general_explanation', 'explain_concept', 'lookup_skill_reference'].includes(intent)
      || capabilityIds.includes('skill_technology_reference')) return false;
  return capabilityIds.some(id => [
    'trend_velocity_analysis', 'skill_health_analysis', 'skill_half_life_analysis',
    'skill_forecasting_half_life', 'job_posting_search', 'market_snapshot',
    'historical_signal_retrieval', 'company_intelligence'
  ].includes(id));
}

export function buildFollowUpRequestContext(requestContext) {
  if (!requestContext || typeof requestContext !== 'object') return undefined;
  return {
    domain: requestContext.domain || null,
    timeRange: 'max'
  };
}

function renderTurnHTML(turn, index, isLatest = false, activeDomain = 'skill') {
  const statusLabels = {
    completed: { label: 'Answer ready', badge: 'cmp-badge--success', icon: 'check-circle-2' },
    ready: { label: 'Answer ready', badge: 'cmp-badge--success', icon: 'check-circle-2' },
    partial: { label: 'Partial Coverage', badge: 'cmp-badge--warning', icon: 'alert-circle' },
    requires_clarification: { label: 'Clarification Required', badge: 'cmp-badge--warning', icon: 'help-circle' },
    insufficient_data: { label: 'Insufficient Observation Data', badge: 'cmp-badge--neutral', icon: 'database' },
    unavailable: { label: 'Capability Unavailable', badge: 'cmp-badge--neutral', icon: 'ban' },
    data_source_unavailable: { label: 'Data Source Unavailable', badge: 'cmp-badge--warning', icon: 'database-zap' },
    unsupported: { label: 'Capability Unsupported', badge: 'cmp-badge--neutral', icon: 'ban' },
    blocked: { label: 'Access Restricted', badge: 'cmp-badge--danger', icon: 'lock' },
    error: { label: 'Service Error', badge: 'cmp-badge--danger', icon: 'alert-triangle' },
    failed: { label: 'Query Failed', badge: 'cmp-badge--danger', icon: 'alert-triangle' }
  };
  const reasonCodes = Array.isArray(turn.reason_codes) ? turn.reason_codes : [];
  const statusKey = reasonCodes.includes('INTELLIGENCE_SOURCE_UNAVAILABLE')
    ? 'data_source_unavailable'
    : ['unsupported', 'requires_clarification'].includes(turn.execution_status)
      ? turn.execution_status
      : turn.status || turn.execution_status;
  const intentStatusLabels = {
    general_explanation: { unavailable: 'General Explanation Unavailable', insufficient_data: 'General Explanation Unavailable' },
    explain_concept: { unavailable: 'Reference Information Unavailable', insufficient_data: 'Reference Information Unavailable' },
    lookup_skill_reference: { unavailable: 'Reference Information Unavailable', insufficient_data: 'Reference Information Unavailable' },
    analyze_trend: { insufficient_data: 'Trend Not Calculated', data_source_unavailable: 'Trend Source Unavailable' },
    search_jobs: { insufficient_data: 'No Verified Postings Retrieved', data_source_unavailable: 'Posting Source Unavailable' }
  };
  const baseStatusInfo = statusKey ? (statusLabels[statusKey] || { label: 'Status unavailable', badge: 'cmp-badge--neutral', icon: 'circle-help' }) : null;
  const statusInfo = baseStatusInfo && intentStatusLabels[turn.intent]?.[statusKey]
    ? { ...baseStatusInfo, label: intentStatusLabels[turn.intent][statusKey] }
    : baseStatusInfo;
  const isServiceError = ['error', 'failed', 'blocked', 'data_source_unavailable'].includes(statusKey)
    || ['error', 'failed', 'blocked'].includes(turn.execution_status);
  const domState = getActiveDomainSession(activeDomain);
  const usedCapabilityId = resolveDisplayedCapabilityId(turn);
  const usedCapability = (DOMAIN_CAPABILITY_REGISTRY[turn.domainKey || activeDomain] || [])
    .find(capability => capability.id === usedCapabilityId);
  const freshness = turn.freshness || {};
  const previousFollowUps = new Set(domState.history
    .slice(0, index)
    .flatMap(previous => previous.follow_up_suggestions || previous.follow_up_questions || previous.followUps || [])
    .map(suggestion => String(suggestion).trim().toLocaleLowerCase()));
  const followUps = turn.guidedJourneyId
    ? []
    : (turn.follow_up_suggestions || turn.follow_up_questions || turn.followUps || [])
      .filter(suggestion => !previousFollowUps.has(String(suggestion).trim().toLocaleLowerCase()))
      .slice(0, 1);

  const allFacts = Array.isArray(turn.facts) ? turn.facts : [];
  const facts = allFacts.filter(f =>
    f.metric_value != null
    && f.quality_state === 'valid'
  );
  const trendFact = facts.find(f => f.fact_type === 'trend_analysis');
  const postingsFact = facts.find(f => f.fact_type === 'stored_job_postings');
  const jobPostings = Array.isArray(turn.jobPostings) && turn.jobPostings.length
    ? turn.jobPostings
    : (Array.isArray(postingsFact?.details?.postings) ? postingsFact.details.postings : []);

  // 4. Contextual explanation (only when explicitly provided)
  const caps = turn.capabilities || {};
  const sh = caps.skill_health?.payload;
  const hl = caps.skill_half_life?.payload;
  let whyItMattersText = '';
  if (sh?.explanation) {
    whyItMattersText = sh.explanation;
  } else if (hl?.explanation) {
    whyItMattersText = hl.explanation;
  }

  const evidenceList = Array.isArray(turn.evidence) ? turn.evidence : [];
  const metricResults = Array.isArray(turn.metric_results) ? turn.metric_results : [];
  const hasChartOrPostings = jobPostings.length > 0 || Boolean(trendFact && (trendFact.details?.series?.length >= 2 || trendFact.details?.observation_count >= 2));
  const journeyStep = isLatest
    ? resolveNextJourneyStep(turn, activeDomain, domState.history, domState.guidedJourney)
    : null;

  return `
    <div class="ai-turn-item ${isLatest ? 'is-latest-turn' : ''}" data-turn-id="${escapeHTML(turn.id || String(index))}">
      <!-- User Question Bubble (Right-Aligned, Requirement 10) -->
      <div class="ai-user-turn-wrapper">
        <div class="ai-user-message-bubble">
          <div class="ai-user-message-header">
            <span class="ai-user-badge"><i data-lucide="user"></i> You</span>
            <span class="ai-user-time">${escapeHTML(turn.timestamp || 'Just now')}</span>
          </div>
          <div class="ai-user-message-text">${escapeHTML(turn.userQuestion)}</div>
        </div>
      </div>

      <!-- Assistant Conversational Response Card (Left-Aligned, Requirement 10) -->
      <article class="ai-assistant-turn-card ai-conv-card-modern">
        <!-- Assistant Top Identity Bar -->
        <div class="ai-conv-assistant-header">
          <div class="ai-conv-brand-wrap">
            <div class="ai-conv-avatar">
              <i data-lucide="${turn.domainIcon || 'sparkles'}"></i>
            </div>
            <div class="ai-conv-brand-info">
              <strong class="ai-conv-brand-name">TalentScope.ai</strong>
              <span class="ai-conv-domain-tag">${escapeHTML(turn.domain || 'CORE INTELLIGENCE')}</span>
            </div>
          </div>
          <div class="ai-conv-header-right">
            ${usedCapability ? `
              <span class="ai-conv-mode-pill ${turn.guidedJourneyId ? 'is-guided' : 'is-feature'}"
                ${turn.guidedJourneyId ? '' : `style="--feature-accent:${escapeHTML(usedCapability.color)};"`}>
                <i data-lucide="${turn.guidedJourneyId ? 'route' : usedCapability.icon}"></i>
                <span>${turn.guidedJourneyId ? 'Guided · ' : ''}${escapeHTML(usedCapability.title)}</span>
              </span>
            ` : ''}
            ${statusInfo ? `
              <span class="ai-conv-status-pill ${statusInfo.badge === 'cmp-badge--success' ? 'is-success' : 'is-neutral'}">
                <i data-lucide="${statusInfo.icon}"></i>
                <span>${statusInfo.label}</span>
              </span>
            ` : ''}
            ${freshness?.latest_observed_at ? `
              <span class="ai-conv-time-tag" title="Latest observed data date">
                <i data-lucide="clock"></i>
                <span>${escapeHTML(String(freshness.latest_observed_at).slice(0, 10))}</span>
              </span>
            ` : ''}
          </div>
        </div>

        <!-- Flowing Conversational Body (Natural AI Answer First, Requirement 10) -->
        <div class="ai-conv-body">
          ${renderAssistantResponseDetails(turn)}
          <!-- Main Markdown Response -->
          ${renderConversationAnswer(turn, formatMarkdown, {
            answer: turn.answer || turn.finding || (isServiceError ? 'The intelligence service did not return an answer.' : ''),
            explanation: whyItMattersText
          })}

          ${renderStructuredIntelligenceDetails(turn)}

          ${['error', 'failed', 'data_source_unavailable'].includes(statusKey) && turn.userQuestion ? `
            <div class="ai-conv-error-retry">
              <button type="button" class="ai-retry-turn" data-retry-turn-id="${escapeHTML(turn.id || '')}" data-retry-question="${escapeHTML(turn.userQuestion)}">
                <i data-lucide="refresh-cw"></i> Retry this question
              </button>
            </div>
          ` : ''}

          <!-- Trend Chart or Verified Postings (Rendered only when relevant data exists) -->
          ${hasChartOrPostings ? renderTurnChartOrBaselineHTML(turn, trendFact, facts, jobPostings) : ''}

        </div>

        <!-- Conversational Turn Footer (Copy, Regenerate & Feedback) -->
        <div class="ai-conv-footer-bar">
          <div class="ai-conv-actions-left">
            <button type="button" class="ai-turn-action-btn" data-action="copy_answer" data-turn-index="${index}" aria-label="Copy answer">
              <i data-lucide="copy" aria-hidden="true"></i><span>Copy answer</span>
            </button>
            <button type="button" class="ai-turn-action-btn" data-action="regenerate_answer" data-turn-index="${index}" ${turn.clientMessageId ? '' : 'disabled title="This saved turn cannot be regenerated because its idempotency key is unavailable."'}>
              <i data-lucide="refresh-cw" aria-hidden="true"></i><span>Regenerate response</span>
            </button>
            <button type="button" class="ai-conv-feedback-btn ${turn.feedback === 'up' ? 'is-active' : ''}" data-feedback="up" data-turn-index="${index}" aria-pressed="${turn.feedback === 'up'}" title="Good response" aria-label="Good response">
              <i data-lucide="thumbs-up"></i>
            </button>
            <button type="button" class="ai-conv-feedback-btn ${turn.feedback === 'down' ? 'is-active' : ''}" data-feedback="down" data-turn-index="${index}" aria-pressed="${turn.feedback === 'down'}" title="Bad response" aria-label="Bad response">
              <i data-lucide="thumbs-down"></i>
            </button>
          </div>

          ${followUps.length > 0 ? `
            <div class="ai-conv-followup-chips" aria-label="Contextual follow-up suggestions">
              ${followUps.map(fu => `
                <button type="button" class="ai-conv-fu-chip" data-followup="${escapeHTML(fu)}" data-turn-index="${index}">
                  <i data-lucide="corner-down-right"></i>
                  <span>${escapeHTML(fu)}</span>
                </button>
              `).join('')}
            </div>
          ` : ''}
        </div>

        ${isLatest && journeyStep ? `
          <div class="ai-conv-journey-section">
            ${journeyStep.isComplete ? `
              <div class="ai-journey-complete-card">
                <div class="ai-journey-complete-icon"><i data-lucide="check-circle-2"></i></div>
                <div class="ai-journey-complete-content">
                  <strong class="ai-journey-complete-title">No Further Ready Step</strong>
                  <p class="ai-journey-complete-desc">${escapeHTML(journeyStep.completionReason || 'No additional relevant capability is ready with the available evidence. Ask a normal follow-up question to continue.')}</p>
                </div>
              </div>
                  ` : journeyStep.isUnavailable ? `
                    <div class="ai-journey-complete-card" role="status">
                      <div class="ai-journey-complete-icon"><i data-lucide="alert-circle"></i></div>
                      <div class="ai-journey-complete-content">
                        <strong class="ai-journey-complete-title">Next Step Not Verified</strong>
                        <p class="ai-journey-complete-desc">${escapeHTML(journeyStep.reason)} You can still ask a normal follow-up question.</p>
                      </div>
                    </div>
                  ` : journeyStep.isEvaluating ? `
                    <div class="ai-conv-journey-card ai-conv-journey-card--checking" role="status">
                      <span class="ai-journey-badge"><i data-lucide="loader-2" class="ai-spin"></i> Guided Intelligence Journey</span>
                      <p class="ai-journey-card-reason">Checking whether another supported analysis is ready for the available evidence…</p>
                    </div>
                  ` : `
              <div class="ai-conv-journey-card">
                <div class="ai-journey-card-header">
                  <span class="ai-journey-badge"><i data-lucide="sparkles"></i> Guided Intelligence Journey</span>
                  <span class="ai-journey-category">${escapeHTML(journeyStep.nextCapability.category)}</span>
                </div>
                <div class="ai-journey-card-body">
                  <div class="ai-journey-card-icon" style="background: ${journeyStep.nextCapability.color}18; color: ${journeyStep.nextCapability.color}">
                    <i data-lucide="${journeyStep.nextCapability.icon}"></i>
                  </div>
                  <div class="ai-journey-card-text">
                    <strong class="ai-journey-card-title">${escapeHTML(journeyStep.nextCapability.title)}</strong>
                    <p class="ai-journey-card-reason">${escapeHTML(journeyStep.reason)}</p>
                  </div>
                  <button type="button" class="ai-journey-continue-btn" data-select-journey-next="${escapeHTML(journeyStep.nextCapability.id)}" data-journey-prompt="${escapeHTML(journeyStep.prompt)}" aria-label="Prepare a question for ${escapeHTML(journeyStep.nextCapability.title)}">
                    <span>Continue with ${escapeHTML(journeyStep.nextCapability.title)}</span>
                    <i data-lucide="arrow-right"></i>
                  </button>
                </div>
              </div>
            `}
          </div>
        ` : ''}
      </article>
    </div>
  `;
}

// ----------------------------------------------------------------------------
// Event Handlers & User Actions
// ----------------------------------------------------------------------------
function attachSidebarItemListeners(container) {
  if (!container) return;
  container.querySelectorAll('[data-restore-conv]').forEach(row => {
    row.addEventListener('click', async (e) => {
      if (e.target.closest('[data-delete-conv]')) return;
      const convId = row.getAttribute('data-restore-conv');
      if (!convId) return;
      const restoreRequestId = ++activeRequestCounter;
      currentAiState = 'idle';
      try {
        const hist = await fetchConversationHistory(convId, { domain: getActiveDomainKey(), portalType: 'individual' });
        if (restoreRequestId !== activeRequestCounter) return;
        if (!hist || hist.conversation_id !== convId) {
          throw new Error('This saved conversation is no longer available. Refresh history and try again.');
        }
        if (hist.portal_type && hist.portal_type !== 'individual') {
          throw new Error('This conversation is not available in the individual workspace.');
        }
        const targetDom = hist?.domain && ['skill', 'market', 'job'].includes(hist.domain)
          ? hist.domain
          : getActiveDomainKey();
        const savedJourney = getActiveDomainSession(targetDom).guidedJourney?.conversationId === convId
          ? getActiveDomainSession(targetDom).guidedJourney
          : null;
        if (targetDom !== getActiveDomainKey()) {
          switchAssistantDomain(targetDom);
        }
        const domState = getActiveDomainSession(targetDom);
        domState.conversation_id = convId;
        if (hist?.filters && typeof hist.filters === 'object') {
          domState.filters = {
            ...createDefaultDomainFilterState(targetDom),
            ...hist.filters,
            scope: normalizeDomainScope(targetDom, hist.filters.scope || domState.filters.scope),
            location: hist.filters.location || domState.filters.location,
            timeRange: hist.time_range || hist.filters.time_range || hist.filters.requested_time_window || domState.filters.timeRange,
            selectedSkill: hist.selected_skills?.[0] || hist.filters.selected_skill || domState.filters.selectedSkill,
            selectedCompany: hist.selected_companies?.[0] || hist.filters.selected_company || domState.filters.selectedCompany,
            selectedRole: hist.active_role || hist.filters.target_role || domState.filters.selectedRole
          };
        }
        domState.draftQuestion = '';
        domState.pendingQuestion = '';
        domState.selectedFeature = null;
        domState.guidedJourney = null;
        domState.selectionReason = '';
        isHistoryDrawerOpen = false;
        isHistoryModalOpen = false;
        historyLoading = false;
        historyLoadError = '';
        setActiveConversationId(convId, 'individual', targetDom, resolveCurrentUserId());
        domState.history = Array.isArray(hist.turns) ? hist.turns.map((t, idx) => {
            const payload = t.response_payload || {};
            const capabilityId = t.filters?.selected_feature || payload.capability_id || null;
            return {
              id: payload.request_id || t.turn_id || `turn_${idx}`,
              conversation_id: convId,
              clientMessageId: t.client_message_id || payload.client_message_id || null,
              domainKey: targetDom,
              capabilityId,
              guidedJourneyId: savedJourney?.completedCapabilityIds?.includes(capabilityId)
                ? savedJourney.id
                : null,
              requestContext: {
                domain: targetDom,
                location: t.filters?.location || hist.location || null,
                timeRange: t.time_range || hist.time_range || 'max',
                targetRole: t.target_role || hist.active_role || null,
                selectedSkills: t.selected_skills || hist.selected_skills || [],
                selectedRoles: t.target_role || hist.active_role ? [t.target_role || hist.active_role] : [],
                selectedCompanies: t.selected_companies || hist.selected_companies || [],
                filters: { ...(t.filters || hist.filters || {}), domain: targetDom }
              },
              userQuestion: t.user_message || t.question || t.message || 'Saved Question',
              timestamp: t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
              status: payload.status || (t.execution_status === 'insufficient_data' ? 'insufficient_data' : 'ready'),
              execution_status: t.execution_status || payload.execution_status || 'completed',
              plan_status: payload.plan_status || 'ready',
              intent: t.intent || payload.intent || 'skill_overview',
              domain: (DOMAIN_CONFIG[targetDom]?.label || 'CORE INTELLIGENCE').toUpperCase(),
              domainIcon: DOMAIN_CONFIG[targetDom]?.icon || 'sparkles',
              badgeClass: 'badge-skill-market',
              answer: payload.answer || t.answer_summary || t.answer || '',
              answer_block: payload.answer_block || t.answer_block || null,
              finding: payload.answer || t.answer_summary || t.answer || '',
              facts: payload.facts || t.facts || [],
              metric_results: payload.metric_results || t.metric_results || [],
              evidence: payload.evidence || t.evidence || [],
              capabilities_used: payload.capabilities_used || t.capabilities_used || [],
              limitations: payload.limitations || t.limitations || [],
              reason_codes: payload.reason_codes || t.reason_codes || [],
              capabilities: payload.capabilities || t.capabilities || {},
              confidence: payload.confidence || t.confidence || null,
              freshness: payload.freshness || {},
              unapplied_filters: payload.unapplied_filters || [],
              follow_up_suggestions: (payload.follow_up_suggestions || t.follow_up_suggestions || []).slice(0, 2),
              followUps: (payload.follow_up_suggestions || t.follow_up_suggestions || []).slice(0, 2),
              actions: []
            };
          }) : [];
        domState.guidedJourney = savedJourney;
        const restoredCapabilityId = [...domState.history].reverse()
          .map(turn => turn.capabilityId)
          .find(capabilityId => capabilityId && getDomainCapabilities(targetDom).some(item => item.id === capabilityId));
        domState.selectedFeature = restoredCapabilityId || null;
        if (savedJourney && !restoredCapabilityId) {
          domState.selectedFeature = getDomainCapabilities(targetDom)
            .some(item => item.id === savedJourney.currentCapabilityId)
            ? savedJourney.currentCapabilityId
            : null;
        }
        syncLegacySessionPointers();
        saveAiSession(activeSession, resolveCurrentUserId());
        renderDedicatedAIAssistantPage();
        requestAnimationFrame(() => document.getElementById('aiComposerInput')?.focus());
        showToast('Restored conversation session');
      } catch (error) {
        if (restoreRequestId === activeRequestCounter) {
          showToast(error?.message || 'Could not restore conversation. Please try again.');
        }
      }
    });
  });

  container.querySelectorAll('[data-delete-conv]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const convId = btn.getAttribute('data-delete-conv');
      if (!convId) return;
      if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
        const confirmed = window.confirm('Delete this conversation from your history?');
        if (!confirmed) return;
      }
      try {
        await deleteIntelligenceConversation(convId, { domain: getActiveDomainKey(), portalType: 'individual' });
        const dom = getActiveDomainKey();
        const domState = getActiveDomainSession(dom);
        if (domState.conversation_id === convId) {
          domState.conversation_id = null;
          domState.history = [];
          setActiveConversationId('', 'individual', dom, resolveCurrentUserId());
          syncLegacySessionPointers();
          saveAiSession(activeSession, resolveCurrentUserId());
        }
        await refreshConversationSidebar();
        renderDedicatedAIAssistantPage();
        showToast('Conversation deleted');
      } catch (_) {
        showToast('Failed to delete conversation');
      }
    });
  });
}

function attachEventListeners(container) {
  const form = container.querySelector('#aiComposerForm');
  const input = container.querySelector('#aiComposerInput');
  const clearBtn = container.querySelector('#btnComposerClear');
  const toggleFilterBtn = container.querySelector('#btnToggleFilterPopover');
  const savedInsightsBtn = container.querySelector('#btnOpenSavedInsights');
  const clearSessionBtn = container.querySelector('#btnClearAiSession');
  const newChatBtn = container.querySelector('#btnNewAiConversation');
  const sidebarNewChatBtn = container.querySelector('#btnSidebarNewChat');
  const historySearchInput = container.querySelector('#aiHistorySearchInput');
  const toggleHistoryBtn = container.querySelector('#btnToggleHistoryModal') || container.querySelector('#btnToggleHistoryDrawer');
  const closeHistoryBtn = container.querySelector('#btnCloseHistoryModal') || container.querySelector('#btnCloseHistoryDrawer');
  const closeHistoryBottomBtn = container.querySelector('#btnCloseHistoryModalBottom');
  const historyBackdrop = container.querySelector('#aiHistoryBackdrop');
  const filterPanel = container.querySelector('#aiUnifiedFilterPanel');
  const profileButton = container.querySelector('#btnAssistantProfile');
  const historyDialog = container.querySelector('#aiHistorySidebar');

  attachSidebarItemListeners(container);

  container.querySelectorAll('#btnRetryCapabilityCatalog').forEach(button => {
    button.addEventListener('click', () => {
      capabilityCatalog = null;
      capabilityCatalogLoadError = false;
      catalogLoadPromise = null;
      renderDedicatedAIAssistantPage();
    });
  });

  container.querySelector('#btnStartGuidedJourney')?.addEventListener('click', () => {
    activateGuidedJourney();
  });

  profileButton?.addEventListener('click', () => {
    isProfileMenuOpen = !isProfileMenuOpen;
    renderDedicatedAIAssistantPage();
    if (isProfileMenuOpen) {
      requestAnimationFrame(() => (document.getElementById('btnToggleHistoryModal') || document.getElementById('btnToggleHistoryDrawer'))?.focus());
    }
  });
  const preserveDraftQuestion = () => {
    if (input) {
      const domState = getActiveDomainSession();
      domState.draftQuestion = input.value;
    }
  };

  function activateGuidedJourney() {
    if (capabilityPlanning || currentAiState === 'analyzing' || currentAiState === 'thinking') return;
    const domState = getActiveDomainSession();
    preserveDraftQuestion();
    domState.selectedFeature = null;
    domState.selectionReason = '';
    domState.guidedJourney = {
      id: globalThis.crypto?.randomUUID?.() || `journey_${Date.now()}`,
      conversationId: domState.conversation_id || null,
      originalQuestion: '',
      completedCapabilityIds: [],
      skippedCapabilityIds: [],
      currentCapabilityId: null,
      remainingCapabilityIds: [],
      evidenceReferences: [],
      isEvaluatingNext: false,
      readinessEvaluated: false,
      readinessCapabilityId: null,
      nextCapabilityReady: false,
      readinessError: ''
    };
    saveAiSession(activeSession, resolveCurrentUserId());
    renderDedicatedAIAssistantPage();
    document.getElementById('aiComposerInput')?.focus();
  }

  async function prepareAnalysisSelection() {
    if (capabilityPlanning) return;
    const domain = getActiveDomainKey();
    const domState = getActiveDomainSession(domain);
    const composerInput = document.getElementById('aiComposerInput');
    const originalQuestion = composerInput?.value?.trim() || domState.draftQuestion || '';
    if (!originalQuestion) {
      composerInput?.focus();
      showToast('Enter a question first so the intelligence planner can recommend an analysis.');
      return;
    }

    const requestId = ++planningRequestCounter;
    capabilityPlanning = true;
    domState.draftQuestion = originalQuestion;
    saveAiSession(activeSession, resolveCurrentUserId());
    renderDedicatedAIAssistantPage();
    try {
      const recommendation = await requestRecommendedCapability(originalQuestion, domain, domState);
      if (requestId !== planningRequestCounter || getActiveDomainKey() !== domain) return;
      if (!recommendation.capability) {
        showToast(recommendation.reason.slice(0, 260));
        return;
      }
      const selectedCapability = recommendation.capability;
      domState.selectedFeature = selectedCapability.id;
      domState.selectionReason = recommendation.reason;
      domState.guidedJourney = null;
      saveAiSession(activeSession, resolveCurrentUserId());
    } catch (error) {
      if (requestId === planningRequestCounter && getActiveDomainKey() === domain) {
        showToast(error?.message || 'The intelligence planner could not select an analysis. You can still send your question normally.');
      }
    } finally {
      if (requestId === planningRequestCounter) {
        capabilityPlanning = false;
        renderDedicatedAIAssistantPage();
        const updatedInput = document.getElementById('aiComposerInput');
        updatedInput?.focus();
        updatedInput?.setSelectionRange(updatedInput.value.length, updatedInput.value.length);
      }
    }
  }

  container.querySelector('#btnRemoveGuidedJourney')?.addEventListener('click', () => {
    const domState = getActiveDomainSession();
    domState.guidedJourney = null;
    domState.selectedFeature = null;
    domState.selectionReason = '';
    saveAiSession(activeSession, resolveCurrentUserId());
    renderDedicatedAIAssistantPage();
    document.getElementById('aiComposerInput')?.focus();
  });

  const closeHistoryHandler = () => {
    preserveDraftQuestion();
    isHistoryModalOpen = false;
    isHistoryDrawerOpen = false;
    renderDedicatedAIAssistantPage();
    requestAnimationFrame(() => document.getElementById('btnAssistantProfile')?.focus());
  };

  if (toggleHistoryBtn) {
    toggleHistoryBtn.addEventListener('click', () => {
      preserveDraftQuestion();
      isProfileMenuOpen = false;
      isHistoryModalOpen = true;
      isHistoryDrawerOpen = true;
      historyLoadError = '';
      historyLoading = true;
      renderDedicatedAIAssistantPage();
      refreshConversationSidebar();
      requestAnimationFrame(() => document.getElementById('aiHistorySearchInput')?.focus());
    });
  }
  if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', closeHistoryHandler);
  if (closeHistoryBottomBtn) closeHistoryBottomBtn.addEventListener('click', closeHistoryHandler);
  if (historyBackdrop) {
    historyBackdrop.addEventListener('click', (e) => {
      if (e.target === historyBackdrop) closeHistoryHandler();
    });
  }
  historyDialog?.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeHistoryHandler();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [...historyDialog.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  if (assistantRootClickContainer && assistantRootClickHandler) {
    assistantRootClickContainer.removeEventListener('click', assistantRootClickHandler);
  }
  assistantRootClickContainer = container;
  assistantRootClickHandler = event => {
    if (isProfileMenuOpen && !event.target.closest('.ai-header-right') && !event.target.closest('.ai-ref-profile')) {
      isProfileMenuOpen = false;
      renderDedicatedAIAssistantPage();
      return;
    }
    if (event.target.closest('#btnRetryAssistantHistory')) {
      historyLoadError = '';
      refreshConversationSidebar();
    }
  };
  container.addEventListener('click', assistantRootClickHandler);

  if (historySearchInput) {
    historySearchInput.addEventListener('input', () => {
      historySearchQuery = historySearchInput.value || '';
      const sidebarBody = container.querySelector('#aiHistoryGroupedList');
      if (sidebarBody) {
        sidebarBody.innerHTML = renderGroupedHistoryItemsHTML();
        attachSidebarItemListeners(container);
        if (window.lucide) window.lucide.createIcons();
      }
    });
  }

  async function handleStartNewChat() {
    if (isCreatingConversation) return;
    const dom = getActiveDomainKey();
    const domState = getActiveDomainSession(dom);
    const newChatButtons = [newChatBtn, sidebarNewChatBtn].filter(Boolean);
    isCreatingConversation = true;
    newChatButtons.forEach(button => {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.querySelector('span')?.replaceChildren(document.createTextNode('Starting…'));
    });
    try {
      const created = await createIntelligenceConversation({
        portalType: 'individual',
        domain: dom,
        title: 'New chat'
      });
      if (!created?.conversation_id) throw new Error('Conversation service did not return an ID.');
      if (created.portal_type && created.portal_type !== 'individual') {
        throw new Error('The conversation service returned an invalid workspace.');
      }
      if (created.domain && created.domain !== dom) {
        throw new Error('The conversation service returned an invalid domain.');
      }
      planningRequestCounter += 1;
      capabilityPlanning = false;
      activeRequestCounter += 1;
      currentAiState = 'idle';
      isProfileMenuOpen = false;
      domState.conversation_id = created.conversation_id;
      setActiveConversationId(created.conversation_id, 'individual', dom, resolveCurrentUserId());
      domState.pendingQuestion = '';
      domState.selectedFeature = null;
      domState.guidedJourney = null;
      domState.selectionReason = '';
      domState.history = [];
      domState.draftQuestion = '';
      isHistoryModalOpen = false;
      isHistoryDrawerOpen = false;
      historyLoading = false;
      historyLoadError = '';
      isFilterPopoverOpen = false;
      draftFilterState = null;
      syncLegacySessionPointers();
      saveAiSession(activeSession, resolveCurrentUserId());
      updateAiState('idle');
      renderDedicatedAIAssistantPage();
      requestAnimationFrame(() => document.getElementById('aiComposerInput')?.focus());
      showToast('Started a new chat');
    } catch (error) {
      showToast(error?.message || 'Could not create a new chat. Please try again.');
    } finally {
      isCreatingConversation = false;
      newChatButtons.forEach(button => {
        button.disabled = false;
        button.removeAttribute('aria-busy');
        button.querySelector('span')?.replaceChildren(document.createTextNode('New chat'));
      });
    }
  }

  if (newChatBtn) newChatBtn.addEventListener('click', handleStartNewChat);
  if (sidebarNewChatBtn) sidebarNewChatBtn.addEventListener('click', handleStartNewChat);

  if (input) {
    input.addEventListener('input', () => {
      const domState = getActiveDomainSession();
      domState.draftQuestion = input.value;
      input.style.height = 'auto';
      input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
      saveAiSession(activeSession, resolveCurrentUserId());
      const val = input.value.trim();
      if (clearBtn) clearBtn.style.display = val.length > 0 ? 'inline-flex' : 'none';
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitComposer();
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      const domState = getActiveDomainSession();
      domState.draftQuestion = '';
      if (input) input.value = '';
      clearBtn.style.display = 'none';
      saveAiSession(activeSession, resolveCurrentUserId());
      input?.focus();
    });
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      submitComposer();
    });
  }

  container.querySelectorAll('[data-assistant-follow-up]').forEach(button => {
    button.addEventListener('click', () => {
      if (!input || currentAiState === 'analyzing' || currentAiState === 'thinking') return;
      input.value = button.dataset.assistantFollowUp;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      submitComposer();
    });
  });

  async function submitComposer() {
    if (!input) return;
    if (capabilityPlanning) {
      showToast('Please wait for the capability recommendation to finish.');
      return;
    }
    if (currentAiState === 'analyzing' || currentAiState === 'thinking') return;
    const query = input.value.trim();
    if (!query) return;
    const domState = getActiveDomainSession();
    const domain = getActiveDomainKey();
    if (domState.guidedJourney?.isComplete) {
      domState.guidedJourney = null;
      domState.selectedFeature = null;
      domState.selectionReason = '';
    }
    let selectedFeatureId = domState.selectedFeature || null;
    if (domState.guidedJourney && !selectedFeatureId) {
      const journeyId = domState.guidedJourney.id;
      const requestId = ++planningRequestCounter;
      domState.draftQuestion = query;
      capabilityPlanning = true;
      saveAiSession(activeSession, resolveCurrentUserId());
      renderDedicatedAIAssistantPage();
      try {
        const recommendation = await requestRecommendedCapability(query, domain, domState);
        if (requestId !== planningRequestCounter || getActiveDomainKey() !== domain
            || getActiveDomainSession(domain).guidedJourney?.id !== journeyId) return;
        if (recommendation.capability) {
          const journey = domState.guidedJourney;
          journey.originalQuestion ||= query;
          journey.currentCapabilityId = recommendation.capability.id;
          journey.remainingCapabilityIds = collectJourneyCapabilityIds(
            recommendation.capability.id,
            getDomainCapabilities(domain)
          );
          domState.selectedFeature = recommendation.capability.id;
          domState.selectionReason = recommendation.reason;
          selectedFeatureId = recommendation.capability.id;
        } else {
          domState.guidedJourney = null;
          domState.selectedFeature = null;
          domState.selectionReason = '';
          showToast('No specialized capability matched. Sending your question through normal chat.');
        }
      } catch (error) {
        if (requestId === planningRequestCounter && getActiveDomainKey() === domain) {
          domState.draftQuestion = query;
          showToast(error?.message || 'The guided planner is unavailable. Your question is still here; try again or remove guided mode.');
        }
        return;
      } finally {
        if (requestId === planningRequestCounter) {
          capabilityPlanning = false;
          saveAiSession(activeSession, resolveCurrentUserId());
          renderDedicatedAIAssistantPage();
        }
      }
    }
    if (selectedFeatureId && !getDomainCapabilities(domain).some(capability => capability.id === selectedFeatureId)) {
      showToast('That capability is not supported in the selected domain. Choose another capability.');
      return;
    }
    domState.draftQuestion = '';
    saveAiSession(activeSession, resolveCurrentUserId());
    await executeAiQuery(query, { selectedFeatureId });
  }

  // Capability Explainer Cards (Landing View): opens explainer modal ONLY. Does NOT execute queries or set feature.
  container.querySelectorAll('[data-open-explainer]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const capId = el.getAttribute('data-open-explainer');
      const caps = getDomainCapabilities(getActiveDomainKey());
      activeExplainerCapability = caps.find(c => c.id === capId) || null;
      renderDedicatedAIAssistantPage();
    });
  });

  // Close Capability Explainer Modal
  const closeExplainerHandler = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const previousCapabilityId = activeExplainerCapability?.id;
    activeExplainerCapability = null;
    renderDedicatedAIAssistantPage();
    requestAnimationFrame(() => {
      document.querySelector(`[data-open-explainer="${previousCapabilityId}"]`)?.focus();
    });
  };
  container.querySelector('#btnCloseCapabilityExplainer')?.addEventListener('click', closeExplainerHandler);
  container.querySelector('#btnCloseCapabilityExplainerBottom')?.addEventListener('click', closeExplainerHandler);
  container.querySelector('#aiExplainerBackdrop')?.addEventListener('click', (e) => {
    if (e.target.id === 'aiExplainerBackdrop') closeExplainerHandler(e);
  });
  const explainerDialog = container.querySelector('.ai-capability-explainer-card');
  if (explainerDialog) {
    requestAnimationFrame(() => explainerDialog.querySelector('#btnCloseCapabilityExplainer')?.focus());
    explainerDialog.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        closeExplainerHandler(event);
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = [...explainerDialog.querySelectorAll('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')];
      if (!focusable.length) return;
      if (event.shiftKey && document.activeElement === focusable[0]) {
        event.preventDefault();
        focusable[focusable.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
        event.preventDefault();
        focusable[0].focus();
      }
    });
  }

  // Select Capability item inside Popover (Requirement 6)
  document.querySelectorAll('[data-select-feature-id]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const featId = el.getAttribute('data-select-feature-id');
      const domState = getActiveDomainSession();
      if (!getDomainCapabilities(getActiveDomainKey()).some(capability => capability.id === featId)) {
        showToast('That capability is not available in this domain.');
        return;
      }
      domState.selectedFeature = featId;
      domState.guidedJourney = null;
      domState.selectionReason = '';
      saveAiSession(activeSession, resolveCurrentUserId());
      isFilterPopoverOpen = false;
      renderDedicatedAIAssistantPage();
      const composerInput = document.getElementById('aiComposerInput');
      if (composerInput) {
        composerInput.focus();
        composerInput.setSelectionRange(composerInput.value.length, composerInput.value.length);
      }
    });
  });

  // Removable feature chip in composer (Requirement 6)
  container.querySelector('#btnRemoveActiveFeature')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const domState = getActiveDomainSession();
    domState.selectedFeature = null;
    domState.guidedJourney = null;
    domState.selectionReason = '';
    saveAiSession(activeSession, resolveCurrentUserId());
    renderDedicatedAIAssistantPage();
    document.getElementById('aiComposerInput')?.focus();
  });

  // Change Active Feature buttons (in composer or focused mode banner)
  const openFeaturePicker = (e) => {
    e.stopPropagation();
    isFilterPopoverOpen = true;
    renderDedicatedAIAssistantPage();
  };
  container.querySelector('#btnChangeActiveFeature')?.addEventListener('click', openFeaturePicker);
  container.querySelector('#btnChangeActiveFeatureBanner')?.addEventListener('click', openFeaturePicker);

  // Remove Active Feature banner button
  container.querySelector('#btnRemoveActiveFeatureBanner')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const domState = getActiveDomainSession();
    domState.selectedFeature = null;
    saveAiSession(activeSession, resolveCurrentUserId());
    renderDedicatedAIAssistantPage();
    document.getElementById('aiComposerInput')?.focus();
  });

  // Recommend My Analysis Quick Action Chip (Guided Journey)
  container.querySelector('#btnRecommendAnalysis')?.addEventListener('click', (e) => {
    e.stopPropagation();
    prepareAnalysisSelection();
  });

  // Guided Intelligence Journey Next Step Selection
  container.querySelectorAll('[data-select-journey-next]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const nextId = el.getAttribute('data-select-journey-next');
      const nextPrompt = el.getAttribute('data-journey-prompt') || '';
      const domState = getActiveDomainSession();
      const capability = getDomainCapabilities(getActiveDomainKey()).find(item => item.id === nextId);
      if (!capability || !domState.guidedJourney?.id) {
        showToast('This journey step is no longer available. Start a new analysis to continue.');
        return;
      }
      domState.selectedFeature = nextId;
      domState.guidedJourney.currentCapabilityId = nextId;
      domState.guidedJourney.isComplete = false;
      domState.guidedJourney.remainingCapabilityIds = domState.guidedJourney.remainingCapabilityIds
        ?.filter(capabilityId => capabilityId !== nextId) || [];
      domState.selectionReason = `Next in your journey: ${capability.desc}`;
      domState.draftQuestion = nextPrompt;
      saveAiSession(activeSession, resolveCurrentUserId());
      renderDedicatedAIAssistantPage();
      const updatedInput = document.getElementById('aiComposerInput');
      if (updatedInput) {
        updatedInput.value = nextPrompt;
        updatedInput.focus();
        updatedInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  });

  // Suggested Prompts Inside Query Panel Click
  container.querySelectorAll('[data-feature-prompt]').forEach(el => {
    el.addEventListener('click', () => {
      const prompt = el.getAttribute('data-feature-prompt');
      if (!prompt || !input) return;
      const domState = getActiveDomainSession();
      input.value = prompt;
      domState.draftQuestion = prompt;
      if (clearBtn) clearBtn.style.display = 'inline-flex';
      saveAiSession(activeSession, resolveCurrentUserId());
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    });
  });

  container.querySelectorAll('[data-prompt]:not([data-feature-prompt])').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const q = el.getAttribute('data-prompt');
      if (q) executeAiQuery(q);
    });
  });

  // Close feature popover button
  document.querySelectorAll('[data-filter-action="cancel"], #btnCloseFeaturePopover').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      isFilterPopoverOpen = false;
      renderDedicatedAIAssistantPage();
    });
  });

  const filtersButton = container.querySelector('#btnOpenFilters');
  const featurePopoverAnchor = container.querySelector('#btnChangeActiveFeature') || filtersButton;
  if (filterPanel && featurePopoverAnchor) {
    document.body.appendChild(filterPanel);
    const rect = featurePopoverAnchor.getBoundingClientRect();
    const isMobile = window.innerWidth <= 640;
    const width = isMobile ? (window.innerWidth - 24) : Math.min(380, window.innerWidth - 24);
    filterPanel.style.position = 'fixed';
    filterPanel.style.width = `${width}px`;
    filterPanel.style.maxWidth = `${width}px`;
    filterPanel.style.maxHeight = '72vh';
    filterPanel.style.overflowY = 'auto';
    if (isMobile) {
      filterPanel.style.left = '12px';
      filterPanel.style.right = '12px';
      filterPanel.style.bottom = '16px';
      filterPanel.style.top = 'auto';
    } else {
      filterPanel.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`;
      const panelHeight = Math.min(filterPanel.offsetHeight || 440, window.innerHeight * 0.72);
      if (rect.top > window.innerHeight / 2) {
        filterPanel.style.top = `${Math.max(12, rect.top - panelHeight - 10)}px`;
      } else {
        filterPanel.style.top = `${Math.min(window.innerHeight - panelHeight - 12, rect.bottom + 8)}px`;
      }
    }
    filterPanel.style.zIndex = '10000';
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
    filterPopoverDismissHandler = (event) => {
      if (!filterPanel.contains(event.target) && !featurePopoverAnchor.contains(event.target)) {
        draftFilterState = null;
        isFilterPopoverOpen = false;
        renderDedicatedAIAssistantPage();
      }
    };
    filterPopoverKeyHandler = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        draftFilterState = null;
        isFilterPopoverOpen = false;
        renderDedicatedAIAssistantPage();
        (document.getElementById('btnChangeActiveFeature') || document.getElementById('btnOpenFilters'))?.focus();
        return;
      }
      if (filterPanel.contains(event.target) && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        const options = [...filterPanel.querySelectorAll('[data-select-feature-id]')];
        if (!options.length) return;
        event.preventDefault();
        const currentIndex = options.indexOf(document.activeElement);
        const nextIndex = event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? options.length - 1
            : (currentIndex + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options[nextIndex < 0 ? 0 : nextIndex].focus();
        return;
      }
      if (event.key === 'Tab') {
        const focusable = [...filterPanel.querySelectorAll('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')];
        if (!focusable.length) return;
        if (event.shiftKey && document.activeElement === focusable[0]) {
          event.preventDefault();
          focusable[focusable.length - 1].focus();
        } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
          event.preventDefault();
          focusable[0].focus();
        }
      }
    };
    document.addEventListener('pointerdown', filterPopoverDismissHandler, true);
    document.addEventListener('keydown', filterPopoverKeyHandler, true);
    requestAnimationFrame(() => {
      filterPanel.querySelector('[data-select-feature-id]')?.focus();
    });
  }
  filtersButton?.addEventListener('click', () => {
    preserveDraftQuestion();
    isFilterPopoverOpen = !isFilterPopoverOpen;
    draftFilterState = isFilterPopoverOpen ? { ...getCommittedFilterSnapshot() } : null;
    renderDedicatedAIAssistantPage();
  });

  // In-place Filter Popover Slot Handlers & Updaters
  const bindFocusSlotListeners = (slot) => {
    if (!slot) return;
    slot.querySelectorAll('[data-draft-filter]').forEach(select => {
      select.addEventListener('change', () => {
        if (!draftFilterState) draftFilterState = { ...getCommittedFilterSnapshot() };
        const key = select.getAttribute('data-draft-filter');
        const value = select.value;
        const dom = getActiveDomainKey();
        if (key === 'entity') {
          if (dom === 'skill') {
            draftFilterState.selectedSkill = value;
            draftFilterState.selectedSkills = value ? [value] : [];
            const help = slot.querySelector('#aiFilterFocusHelp');
            if (help) {
              const isAll = draftFilterState.scope === 'All';
              help.innerHTML = isAll
                ? (value ? `Focused on: <strong>${escapeHTML(value)}</strong>` : 'Querying across all supported skills in the catalog without restriction.')
                : (value ? `Focused on favourite: <strong>${escapeHTML(value)}</strong>` : 'Querying across saved favourite skills.');
            }
          } else if (dom === 'market') {
            draftFilterState.selectedCompany = value;
            const help = slot.querySelector('#aiFilterMarketHelp');
            if (help) {
              help.innerHTML = value ? `Focused on: <strong>${escapeHTML(value)}</strong>` : 'Querying across all indexed market entities.';
            }
          }
        } else if (key === 'company') {
          draftFilterState.selectedCompany = value;
          const help = slot.querySelector('#aiFilterCompanyHelp');
          if (help) {
            help.innerHTML = value ? `Focused on: <strong>${escapeHTML(value)}</strong>` : 'Querying across all supported employers in indexed postings.';
          }
        } else if (key === 'role') {
          draftFilterState.selectedRole = value;
          const help = slot.querySelector('#aiFilterRoleHelp');
          if (help) {
            help.innerHTML = value ? `Focused on role: <strong>${escapeHTML(value)}</strong>` : 'Querying across all indexed role titles.';
          }
        } else if (key === 'entities') {
          draftFilterState.selectedSkills = [...select.selectedOptions].map(option => option.value).filter(Boolean);
          draftFilterState.selectedSkill = draftFilterState.selectedSkills[0] || '';
        }
      });
    });

    slot.querySelectorAll('[data-filter-entity-search]').forEach(search => {
      search.addEventListener('input', () => {
        const select = search.parentElement?.querySelector('select');
        if (!select) return;
        const query = search.value.trim().toLocaleLowerCase();
        [...select.options].forEach(option => {
          option.hidden = Boolean(option.value) && !option.textContent.toLocaleLowerCase().includes(query);
        });
      });
    });
  };

  const bindLocationSlotListeners = (slot) => {
    if (!slot) return;
    slot.querySelectorAll('[data-draft-filter]').forEach(select => {
      select.addEventListener('change', () => {
        if (!draftFilterState) draftFilterState = { ...getCommittedFilterSnapshot() };
        const key = select.getAttribute('data-draft-filter');
        const value = select.value;
        const dom = getActiveDomainKey();
        const domState = getActiveDomainSession(dom);
        const observedOptions = getObservedFilterOptions(dom, domState.history);

        if (key === 'country') {
          draftFilterState.country = value;
          draftFilterState.state = '';
          draftFilterState.city = '';
          draftFilterState.location = value;
          slot.innerHTML = renderLocationCascadeFields(draftFilterState, observedOptions);
          bindLocationSlotListeners(slot);
        } else if (key === 'state') {
          draftFilterState.state = value;
          draftFilterState.city = '';
          draftFilterState.location = value && draftFilterState.country ? `${value}, ${draftFilterState.country}` : (value || draftFilterState.country || '');
          slot.innerHTML = renderLocationCascadeFields(draftFilterState, observedOptions);
          bindLocationSlotListeners(slot);
        } else if (key === 'city') {
          draftFilterState.city = value;
          const hier = getLocationHierarchy(observedOptions.locations);
          const matched = hier.parsed.find(p => p.city.toLowerCase() === value.toLowerCase());
          draftFilterState.location = matched ? matched.raw : (value && draftFilterState.country ? `${value}, ${draftFilterState.country}` : (value || draftFilterState.country || ''));
          const tag = slot.querySelector('.ai-filter-location-active-tag');
          if (tag) tag.textContent = draftFilterState.location || '';
          const help = slot.querySelector('.ai-filter-help-text');
          if (help) {
            help.innerHTML = draftFilterState.location ? `Filtering by: <strong>${escapeHTML(draftFilterState.location)}</strong>` : 'Filtering across all observed telemetry locations.';
          }
        }
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
          window.lucide.createIcons();
        }
      });
    });
  };

  const updateFilterPanelInPlace = () => {
    if (!filterPanel) return;
    if (!draftFilterState) draftFilterState = { ...getCommittedFilterSnapshot() };
    const dom = getActiveDomainKey();
    const domCfg = DOMAIN_CONFIG[dom];
    const domState = getActiveDomainSession(dom);
    const observedOptions = getObservedFilterOptions(dom, domState.history);
    const selectableEntities = getSelectableEntities(dom, draftFilterState.scope, observedOptions);

    // 1. Update Scope buttons and badge
    const badge = filterPanel.querySelector('#aiFilterScopeStatusBadge');
    if (badge) {
      badge.textContent = draftFilterState.scope === 'All' ? 'All Selected' : 'Favourites Selected';
    }
    filterPanel.querySelectorAll('[data-select-scope]').forEach(b => {
      const val = b.getAttribute('data-select-scope');
      const isActive = val === draftFilterState.scope;
      b.classList.toggle('is-active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      const check = b.querySelector('.ai-filter-scope-check');
      if (isActive && !check) {
        b.insertAdjacentHTML('afterbegin', '<span class="ai-filter-scope-check">✓</span>');
      } else if (!isActive && check) {
        check.remove();
      }
    });

    // 2. Update Focus slot
    const focusSlot = filterPanel.querySelector('#aiFilterFocusSlot');
    if (focusSlot) {
      focusSlot.innerHTML = renderEntityFilterFieldHTML(dom, domCfg, draftFilterState, selectableEntities, observedOptions);
      bindFocusSlotListeners(focusSlot);
    }

    // 3. Update Location slot
    const locSlot = filterPanel.querySelector('#aiFilterLocationSlot');
    if (locSlot) {
      locSlot.innerHTML = renderLocationCascadeFields(draftFilterState, observedOptions);
      bindLocationSlotListeners(locSlot);
    }

    // 4. Update Time range
    const timeBadge = filterPanel.querySelector('.ai-filter-time-badge');
    if (timeBadge) {
      timeBadge.textContent = draftFilterState.timeRange || 'Max Available';
    }
    const timeSelect = filterPanel.querySelector('[data-draft-filter="timeRange"]');
    if (timeSelect && draftFilterState.timeRange) {
      timeSelect.value = draftFilterState.timeRange;
    }

    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons();
    }
  };

  // Bind initial slot listeners inside filter panel
  bindFocusSlotListeners(filterPanel?.querySelector('#aiFilterFocusSlot'));
  bindLocationSlotListeners(filterPanel?.querySelector('#aiFilterLocationSlot'));

  // Scope Buttons (All vs Favourites)
  filterPanel?.querySelectorAll('[data-select-scope]').forEach(btn => {
    btn.addEventListener('click', () => {
      const scopeVal = btn.getAttribute('data-select-scope');
      if (!draftFilterState) draftFilterState = { ...getCommittedFilterSnapshot() };
      const dom = getActiveDomainKey();
      draftFilterState.scope = normalizeDomainScope(dom, scopeVal);
      draftFilterState.selectedSkill = '';
      draftFilterState.selectedSkills = [];
      draftFilterState.selectedCompany = '';
      draftFilterState.selectedRole = '';
      updateFilterPanelInPlace();
    });
  });

  // Time Range change listener
  filterPanel?.querySelector('[data-draft-filter="timeRange"]')?.addEventListener('change', (e) => {
    if (!draftFilterState) draftFilterState = { ...getCommittedFilterSnapshot() };
    draftFilterState.timeRange = e.target.value;
    const timeBadge = filterPanel.querySelector('.ai-filter-time-badge');
    if (timeBadge) {
      timeBadge.textContent = draftFilterState.timeRange || 'Max Available';
    }
  });

  // Filter Actions: Apply, Reset, Cancel
  filterPanel?.querySelectorAll('[data-filter-action]').forEach(button => button.addEventListener('click', () => {
    const action = button.getAttribute('data-filter-action');
    const dom = getActiveDomainKey();
    const committed = getCommittedFilterSnapshot(dom);
    const domState = getActiveDomainSession(dom);
    if (action === 'apply') {
      if (currentAiState === 'analyzing' || currentAiState === 'thinking') return;
      const options = getObservedFilterOptions(dom, domState.history);
      const validation = validateAssistantFilterDraft(dom, draftFilterState, options);
      if (!validation.valid) {
        showToast('Choose values supported by the loaded intelligence records.');
        return;
      }
      commitAssistantFilterDraft(domState, dom, draftFilterState);
      syncLegacySessionPointers();
      saveAiSession(activeSession, resolveCurrentUserId());
      const priorQuestion = domState.history.at(-1)?.userQuestion || '';
      isFilterPopoverOpen = false;
      draftFilterState = null;
      renderDedicatedAIAssistantPage();
      if (priorQuestion) executeAiQuery(priorQuestion);
      return;
    } else if (action === 'reset') {
      const options = getObservedFilterOptions(dom, domState.history);
      draftFilterState = resetAssistantFilterDraft(dom, options.ranges);
      updateFilterPanelInPlace();
      return;
    } else {
      draftFilterState = null;
      isFilterPopoverOpen = false;
      renderDedicatedAIAssistantPage();
      document.getElementById('btnOpenFilters')?.focus();
    }
  }));

  // Follow-up & Additional Insights chip click
  container.querySelectorAll('[data-followup]').forEach(el => {
    el.addEventListener('click', () => {
      const fu = el.getAttribute('data-followup');
      const index = parseInt(el.getAttribute('data-turn-index'), 10);
      const turn = getActiveDomainSession().history[index];
      if (fu) {
        const domState = getActiveDomainSession();
        domState.selectedFeature = null;
        saveAiSession(activeSession, resolveCurrentUserId());
        executeAiQuery(fu, {
          requestContext: buildFollowUpRequestContext(turn?.requestContext),
          selectedFeatureId: null
        });
      }
    });
  });
  container.querySelectorAll('[data-clarification-reply]').forEach(button => {
    button.addEventListener('click', () => {
      const reply = button.getAttribute('data-clarification-reply');
      if (reply) executeAiQuery(reply, { selectedFeatureId: null });
    });
  });
  container.querySelectorAll('.ai-retry-turn').forEach(button => {
    button.addEventListener('click', () => {
      const question = button.getAttribute('data-retry-question');
      const turnId = button.getAttribute('data-retry-turn-id');
      const turn = getActiveDomainSession().history.find(item => item.id === turnId);
      if (question) executeAiQuery(question, { selectedFeatureId: turn?.capabilityId || null });
    });
  });

  // Save, copy, and same-turn regeneration actions
  container.querySelectorAll('[data-action="save_insight"]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.getAttribute('data-turn-index'), 10);
      const domState = getActiveDomainSession();
      const turn = domState.history[idx];
      if (turn) {
        const saved = saveInsight(turn, resolveCurrentUserId());
        showToast(saved ? 'Insight saved to your workspace library' : 'Insight already saved');
      }
    });
  });

  container.querySelectorAll('[data-action="copy_answer"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const idx = parseInt(btn.getAttribute('data-turn-index'), 10);
      const domState = getActiveDomainSession();
      const turn = domState.history[idx];
      if (turn) {
        try {
          if (!navigator.clipboard?.writeText) throw new Error('Clipboard access is unavailable.');
          await navigator.clipboard.writeText(cleanConversationAnswer(turn.answer || turn.finding || ''));
          btn.classList.add('is-copied');
          btn.innerHTML = '<i data-lucide="check" style="width:14px; height:14px;"></i><span>Copied!</span>';
          if (window.lucide) window.lucide.createIcons();
          setTimeout(() => {
            btn.classList.remove('is-copied');
            btn.innerHTML = '<i data-lucide="copy" style="width:14px; height:14px;"></i><span>Copy answer</span>';
            if (window.lucide) window.lucide.createIcons();
          }, 2000);
          showToast('Answer copied to clipboard');
        } catch (_) {
          showToast('Could not copy the answer. Check clipboard permissions.');
        }
      }
    });
  });
  container.querySelectorAll('[data-action="regenerate_answer"]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.getAttribute('data-turn-index'), 10);
      const turn = getActiveDomainSession().history[idx];
      if (!turn?.clientMessageId) {
        showToast('This saved answer cannot be regenerated safely.');
        return;
      }
      executeAiQuery(turn.userQuestion, {
        selectedFeatureId: turn.capabilityId || turn.requestContext?.capabilityId || null,
        replaceTurnId: turn.id,
        clientMessageId: turn.clientMessageId,
        requestContext: turn.requestContext,
        regenerate: true
      });
    });
  });

  // User feedback on assistant turns (thumbs up / thumbs down)
  container.querySelectorAll('[data-feedback]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.getAttribute('data-turn-index'), 10);
      const turn = getActiveDomainSession().history[idx];
      if (!turn) return;
      const parent = btn.parentElement;
      if (parent) {
        parent.querySelectorAll('[data-feedback]').forEach(b => {
          const active = b === btn;
          b.classList.toggle('is-active', active);
          b.setAttribute('aria-pressed', String(active));
        });
      }
      const type = btn.getAttribute('data-feedback');
      turn.feedback = type;
      showToast('Thanks for letting us know.');
    });
  });

  if (savedInsightsBtn) {
    savedInsightsBtn.addEventListener('click', () => {
      showSavedInsightsModal();
    });
  }

  if (clearSessionBtn) {
    clearSessionBtn.addEventListener('click', () => {
      const dom = getActiveDomainKey();
      const domState = getActiveDomainSession(dom);
      if (domState.conversation_id) {
        queryCoreIntelligenceAnswer({
          message: 'clear session',
          portalType: 'individual',
          domain: null,
          conversationId: domState.conversation_id,
          clearContext: true
        }).catch(() => {});
      }
      domState.conversation_id = null;
      domState.history = [];
      domState.draftQuestion = '';
      isHistoryDrawerOpen = false;
      setActiveConversationId('', 'individual', dom, resolveCurrentUserId());
      syncLegacySessionPointers();
      saveAiSession(activeSession, resolveCurrentUserId());
      updateAiState('idle');
      renderDedicatedAIAssistantPage();
      showToast(`${DOMAIN_CONFIG[dom]?.label || 'Domain'} conversation reset`);
    });
  }
}

// ----------------------------------------------------------------------------
// Execute Query with Domain-Specific Filter Enforcement
// ----------------------------------------------------------------------------
async function executeAiQuery(question, options = {}) {
  if (currentAiState === 'analyzing' || currentAiState === 'thinking') return;
  initSession();
  const reqId = ++activeRequestCounter;
  const clientMessageId = `aimsg_${Date.now()}_${reqId}`;
  const dom = getActiveDomainKey();
  const domState = getActiveDomainSession(dom);
  const selectedCapabilityId = options.selectedFeatureId || options.requestContext?.capabilityId || null;
  const selectedCapability = selectedCapabilityId
    ? getDomainCapabilities(dom).find(capability => capability.id === selectedCapabilityId)
    : null;
  if (selectedCapabilityId && !selectedCapability) {
    showToast('That capability is not supported in the selected domain. Choose another capability.');
    return;
  }
  const requestContext = {
    domain: null,
    capabilityId: selectedCapabilityId,
    timeRange: 'max',
  };
  const guidedJourneyId = selectedCapabilityId
    && domState.guidedJourney?.currentCapabilityId === selectedCapabilityId
    ? domState.guidedJourney.id
    : null;
  domState.pendingQuestion = options.replaceTurnId ? '' : question;
  updateAiState('analyzing');
  renderDedicatedAIAssistantPage();

  let planResult = null;
  try {
    updateAiState('thinking');

    const currentUid = resolveCurrentUserId();
    const isGuest = currentUid === 'anonymous';
    const storedConversationId = domState.conversation_id
      || getActiveConversationId('individual', dom, currentUid);
    const conversationId = isGuest || isClientGeneratedConversationId(storedConversationId, 'individual', dom)
      ? null
      : (storedConversationId || null);
    if (storedConversationId && !conversationId) {
      domState.conversation_id = null;
      setActiveConversationId(null, 'individual', dom, currentUid);
    }
    planResult = await queryCoreIntelligencePlan({
      message: question,
      portalType: 'individual',
      timeRange: 'max',
      conversationId
    });
    const answerRes = await queryCoreIntelligenceAnswer({
      message: question,
      portalType: 'individual',
      ...requestContext,
      capabilityId: selectedCapabilityId,
      conversationId,
      clientMessageId: options.clientMessageId || clientMessageId,
      regenerate: Boolean(options.regenerate)
    }, { guest: isGuest });

    if (reqId !== activeRequestCounter) return;

    if (answerRes.conversation_id && currentUid !== 'anonymous') {
      domState.conversation_id = answerRes.conversation_id;
      setActiveConversationId(answerRes.conversation_id, 'individual', dom, currentUid);
    }
    if (guidedJourneyId && domState.guidedJourney?.id === guidedJourneyId) {
      domState.guidedJourney.conversationId = answerRes.conversation_id || domState.conversation_id;
    }

    const factsList = Array.isArray(answerRes.facts) ? answerRes.facts.map(fact => (
      fact?.fact_type === 'stored_job_postings'
        ? {
          ...fact,
          details: {
            ...(fact.details || {}),
            postings: Array.isArray(fact.details?.postings)
              ? fact.details.postings.map(posting => ({
                ...posting,
                source_url: safeStoredSourceUrl(posting.source_url)
              }))
              : fact.details?.postings
          }
        }
        : fact
    )) : [];
    const postingsFact = factsList.find(f => f.fact_type === 'stored_job_postings');
    const jobPostings = Array.isArray(postingsFact?.details?.postings) ? postingsFact.details.postings : [];
    const usedCapabilityIds = Array.isArray(answerRes.capabilities_used) ? answerRes.capabilities_used : [];
    const activeCapabilityId = resolveActiveCapabilityId(answerRes, dom);
    const activeCapability = getDomainCapabilities(dom)
      .find(capability => capability.id === activeCapabilityId);
    const routedCapabilityId = activeCapabilityId;
    const routedRequestContext = { ...requestContext, capabilityId: routedCapabilityId };

    const turn = {
      id: answerRes.request_id || `turn_${Date.now()}`,
      clientMessageId: options.clientMessageId || clientMessageId,
      domainKey: dom,
      requestContext: routedRequestContext,
      capabilityId: routedCapabilityId,
      guidedJourneyId: guidedJourneyId || null,
      conversation_id: answerRes.conversation_id || domState.conversation_id || null,
      userQuestion: question,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: answerRes.status || answerRes.execution_status,
      execution_status: answerRes.execution_status,
      plan_status: answerRes.plan_status,
      intent: answerRes.intent,
      domain: (DOMAIN_CONFIG[dom]?.label || 'CORE INTELLIGENCE').toUpperCase(),
      domainIcon: DOMAIN_CONFIG[dom]?.icon || 'sparkles',
      badgeClass: 'badge-skill-market',
      answer: answerRes.answer,
      answer_block: answerRes.answer_block || null,
      answer_origin: answerRes.answer_origin,
      understood: typeof planResult?.understood === 'string' ? planResult.understood : null,
      clarification: Array.isArray(planResult?.clarification_questions) ? planResult.clarification_questions[0] : null,
      clarification_questions: Array.isArray(planResult?.clarification_questions) ? planResult.clarification_questions : [],
      sources: Array.isArray(answerRes.sources) ? answerRes.sources : [],
      finding: answerRes.answer,
      facts: factsList,
      metric_results: answerRes.metric_results || [],
      jobPostings: jobPostings,
      evidence: answerRes.evidence,
      limitations: answerRes.limitations,
      enough_data: answerRes.enough_data,
      degraded: answerRes.degraded,
      degraded_reason: answerRes.degraded_reason,
      reason_codes: answerRes.reason_codes,
      capabilities_used: answerRes.capabilities_used,
      planned_primary_capability: answerRes.planned_primary_capability,
      executed_primary_capability: answerRes.executed_primary_capability,
      dependency_capabilities: answerRes.dependency_capabilities || [],
      planned_capabilities: answerRes.planned_capabilities || [],
      capabilities: answerRes.capabilities || {},
      confidence: answerRes.confidence || null,
      freshness: answerRes.freshness || {},
      unapplied_filters: answerRes.unapplied_filters || [],
      followUps: (answerRes.follow_up_suggestions || answerRes.follow_up_questions || []).slice(0, 2),
      follow_up_questions: (answerRes.follow_up_suggestions || answerRes.follow_up_questions || []).slice(0, 2),
      follow_up_suggestions: (answerRes.follow_up_suggestions || answerRes.follow_up_questions || []).slice(0, 2),
      actions: []
    };

    domState.pendingQuestion = '';
    let journeyEvaluation = null;
    if (guidedJourneyId && domState.guidedJourney?.id === guidedJourneyId && selectedCapabilityId) {
      const journey = domState.guidedJourney;
      if (answerRes.capabilities_used?.includes(selectedCapabilityId)
          && ['ready', 'partial'].includes(turn.status)) {
        if (!journey.completedCapabilityIds.includes(selectedCapabilityId)) {
          journey.completedCapabilityIds.push(selectedCapabilityId);
        }
        journey.evidenceReferences = (answerRes.evidence || [])
          .map(item => item.provenance_id || item.evidence_id)
          .filter(Boolean);
        journey.currentCapabilityId = selectedCapabilityId;
        journey.isEvaluatingNext = true;
        journey.readinessEvaluated = false;
        journey.readinessCapabilityId = null;
        journey.nextCapabilityReady = false;
        journey.readinessError = '';
        journeyEvaluation = {
          domain: dom,
          userId: resolveCurrentUserId(),
          journeyId: journey.id,
          turn
        };
      } else {
        journey.stoppedReason = answerRes.answer;
        journey.isComplete = true;
        journey.currentCapabilityId = null;
        journey.isEvaluatingNext = false;
        domState.selectedFeature = null;
      }
    }
    if (activeCapability) {
      domState.selectedFeature = activeCapability.id;
      domState.selectionReason = `Selected for this question: ${activeCapability.title}.`;
    } else if (answerRes.intent === 'general_explanation') {
      domState.selectedFeature = null;
      domState.selectionReason = 'General explanation; no platform capability was executed.';
    }
    if (options.replaceTurnId) {
      const replaceIndex = domState.history.findIndex(item => item.id === options.replaceTurnId);
      if (replaceIndex >= 0) domState.history[replaceIndex] = turn;
      else domState.history.push(turn);
    } else {
      domState.history.push(turn);
    }
    syncLegacySessionPointers();
    saveAiSession(activeSession, resolveCurrentUserId());

    updateAiState('ready');
    renderDedicatedAIAssistantPage();

    if (journeyEvaluation) {
      void evaluateGuidedJourneyNextStep(
        journeyEvaluation.turn,
        journeyEvaluation.domain,
        journeyEvaluation.userId,
        journeyEvaluation.journeyId
      );
    }

    const stream = document.getElementById('aiConversationStream');
    if (stream && stream.firstElementChild) {
      stream.firstElementChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    setTimeout(() => {
      if (reqId === activeRequestCounter) updateAiState('idle');
    }, 1500);
  } catch (err) {
    if (reqId !== activeRequestCounter) return;
    domState.pendingQuestion = '';
    if (options.replaceTurnId) {
      updateAiState('idle');
      renderDedicatedAIAssistantPage();
      showToast('Could not regenerate this response. The saved answer was kept.');
      return;
    }
    console.warn('Live Core Intelligence query failed:', err);
    let errorStatus = 'failed';
    let errorMessage = 'The intelligence service is temporarily unavailable. Please verify the backend service is running and try again.';
    let reasonCodes = ['SERVICE_ERROR'];

    if (err.name === 'CoreIntelligenceAuthError' || err.status === 401 || err.status === 403) {
      errorStatus = 'blocked';
      reasonCodes = ['UNAUTHORIZED_PORTAL_ACCESS'];
      errorMessage = 'Authentication Required: Please sign in to verify your session and access verified Core Intelligence.';
    } else if (err.name === 'CoreIntelligenceNetworkError') {
      errorStatus = 'failed';
      reasonCodes = ['NETWORK_ERROR'];
      errorMessage = 'The intelligence service is temporarily unavailable. Please verify the backend service is running and try again.';
    } else if (err.message && !err.message.includes('127.0.0.1') && !err.message.includes('http')) {
      errorMessage = err.message;
    }

    const turn = {
      id: `err_${Date.now()}`,
      domainKey: dom,
      requestContext,
      capabilityId: selectedCapabilityId,
      guidedJourneyId: guidedJourneyId || null,
      userQuestion: question,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'error',
      execution_status: errorStatus,
      plan_status: 'blocked',
      intent: 'service_error',
      domain: (DOMAIN_CONFIG[dom]?.label || 'CORE INTELLIGENCE').toUpperCase(),
      domainIcon: 'alert-triangle',
      badgeClass: 'badge-skill',
      answer: errorMessage,
      understood: typeof planResult?.understood === 'string' ? planResult.understood : null,
      clarification: Array.isArray(planResult?.clarification_questions) ? planResult.clarification_questions[0] : null,
      finding: errorMessage,
      facts: [],
      jobPostings: [],
      evidence: [],
      limitations: [errorMessage, 'Zero synthetic scores or fabricated responses are generated on service failure.'],
      reason_codes: reasonCodes,
      capabilities_used: [],
      capabilities: {},
      confidence: null,
      freshness: {},
      unapplied_filters: [],
      followUps: [],
      follow_up_questions: [],
      follow_up_suggestions: [],
      actions: []
    };

    domState.history.push(turn);
    syncLegacySessionPointers();
    saveAiSession(activeSession, resolveCurrentUserId());
    updateAiState('idle');
    renderDedicatedAIAssistantPage();
  }
}

function updateAiState(state) {
  currentAiState = state;
  const label = document.getElementById('aiStateText');
  if (label) {
    const domState = getActiveDomainSession();
    label.textContent = state === 'idle' ? resolveFreshnessInfo(domState).label : getStateLabel(state);
  }
}

function getStateLabel(state) {
  switch (state) {
    case 'typing': return 'Formulating query...';
    case 'analyzing': return 'Querying verified intelligence store...';
    case 'thinking': return 'Evaluating deterministic metrics & provenance...';
    case 'ready': return 'Verified response ready';
    case 'idle':
    default:
      return 'Freshness unavailable';
  }
}

function showSavedInsightsModal() {
  const existing = document.getElementById('aiModalOverlay');
  if (existing) existing.remove();

  const saved = loadSavedInsights(resolveCurrentUserId());

  const modal = document.createElement('div');
  modal.className = 'ai-modal-overlay';
  modal.id = 'aiModalOverlay';
  modal.innerHTML = `
    <div class="ai-modal-box">
      <div class="ai-modal-header">
        <h3>Saved Intelligence Insights (${saved.length})</h3>
        <button class="ai-icon-action-btn" id="btnCloseModal">
          <i data-lucide="x" style="width:16px; height:16px;"></i>
        </button>
      </div>
      <div class="ai-modal-body">
        ${saved.length === 0 ? `
          <div style="text-align:center; padding:30px 10px; color:#625a69;">
            <i data-lucide="bookmark" style="width:32px; height:32px; color:var(--ai-primary); margin-bottom:8px;"></i>
            <p style="margin:0; font-weight:600;">No saved insights yet</p>
            <small style="color:#8d8395;">Bookmark any response card in the assistant to reference it here anytime.</small>
          </div>
        ` : `
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${saved.map(item => `
              <div style="padding:12px 14px; background:#F8F6FC; border:1px solid rgba(178,45,239,0.15); border-radius:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                  <span style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--ai-primary);">${escapeHTML(item.domain)}</span>
                  <small style="color:#8d8395;">${escapeHTML(item.savedAt || '')}</small>
                </div>
                <div style="font-size:13px; font-weight:600; color:#171321; margin-bottom:4px;">${escapeHTML(item.userQuestion)}</div>
                <div style="font-size:12px; color:#625a69; line-height:1.4;">${escapeHTML(item.finding)}</div>
              </div>
            `).join('')}
          </div>
        `}
      </div>
      <div class="ai-modal-footer">
        <button type="button" class="ai-glass-btn" id="btnCloseSaved">Close</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  if (window.lucide) window.lucide.createIcons();

  modal.querySelector('#btnCloseModal').addEventListener('click', () => modal.remove());
  modal.querySelector('#btnCloseSaved').addEventListener('click', () => modal.remove());
}

function showToast(message) {
  if (currentToastTimer) clearTimeout(currentToastTimer);
  const existing = document.getElementById('aiToastNotification');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'ai-toast-container';
  toast.id = 'aiToastNotification';
  toast.innerHTML = `
    <i data-lucide="check-circle-2" style="width:16px; height:16px; color:var(--ai-positive);"></i>
    <span>${escapeHTML(message)}</span>
  `;

  document.body.appendChild(toast);
  if (window.lucide) window.lucide.createIcons();

  currentToastTimer = setTimeout(() => {
    toast.remove();
  }, 3200);
}

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
