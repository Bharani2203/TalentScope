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
import { loadSkillCatalog, loadMarketCatalog } from '../../../api/intelligence-catalog-client.js';
import {
  queryCoreIntelligenceAnswer,
  fetchIntelligenceConversations,
  fetchConversationHistory,
  deleteIntelligenceConversation,
  createIntelligenceConversation,
  getActiveConversationId,
  setActiveConversationId,
  normalizeAnswerTimeRange,
  getCapabilityCatalog,
  queryCoreIntelligencePlan,
  evaluateCapabilities
} from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { cleanConversationAnswer, renderConversationAnswer } from '../../../components/common/ConversationAnswer.js';
import { API_BASE_URL } from '../../../config/api.js';

function formatMarkdown(content) {
  if (!content) return '';
  const escaped = escapeHTML(content);
  return escaped
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
  if (userProfileState?.uid) return userProfileState.uid;
  try {
    const raw = localStorage.getItem('talentscope-auth-session');
    if (raw) {
      const parsed = JSON.parse(raw);
      return parsed?.uid || parsed?.user?.uid || 'anonymous';
    }
  } catch (_) {}
  return 'anonymous';
}

// ----------------------------------------------------------------------------
// Domain Capability Registry (Source of Truth for All 3 Domains)
// ----------------------------------------------------------------------------
export const DOMAIN_CAPABILITY_REGISTRY = {
  skill: [
    {
      id: 'skill_health',
      title: 'Skill Health',
      category: 'Skill Readiness',
      desc: 'Understand skill momentum from comparable market evidence.',
      cardTagline: 'See whether skill demand is building or cooling.',
      promptHint: 'Ask about skill viability, ecosystem momentum, or health status',
      defaultPrompt: 'What is the skill health for {entity}?',
      icon: 'heart-pulse',
      color: '#EC4899',
      explainer: {
        whatItDoes: 'Evaluates the relative vitality, adoption momentum, and market viability of skills against empirical labor market signals.',
        inputsNeeded: 'Canonical skill name or selected focus skills from the catalog.',
        outputProduced: 'Health category (Emerging, Stable, High Velocity, At Risk), empirical score metrics, and ecosystem momentum.',
        limitations: 'Calculated strictly from verified observation periods; requires at least 1 verified empirical period.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="shGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#FF3366" />
              <stop offset="50%" stop-color="#EC4899" />
              <stop offset="100%" stop-color="#8B5CF6" />
            </linearGradient>
            <linearGradient id="shPulseGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#10B981" />
              <stop offset="100%" stop-color="#38BDF8" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#shGrad)" fill-opacity="0.14" />
          <path d="M22 10 C17 6, 9 11, 9 19 C9 27, 22 35, 22 35 C22 35, 35 27, 35 19 C35 11, 27 6, 22 10 Z" fill="url(#shGrad)" fill-opacity="0.22" stroke="url(#shGrad)" stroke-width="1.8" />
          <path d="M13 21 H17 L19 15 L23 27 L26 18 L28 21 H31" stroke="url(#shPulseGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="23" cy="27" r="2" fill="#10B981" />
        </svg>
      `
    },
    {
      id: 'skill_half_life',
      title: 'Skill Half-Life',
      category: 'Skill Relevance',
      desc: 'Examine how a skill’s measured relevance changes over time.',
      cardTagline: 'Explore how skill relevance changes over time.',
      promptHint: 'Ask about obsolescence risks, decay rates, or tech freshness',
      defaultPrompt: 'What is the skill half-life for {entity}?',
      icon: 'hourglass',
      color: '#8B5CF6',
      explainer: {
        whatItDoes: 'Models empirical decay rate and obsolescence risk of technical knowledge based on multi-period employer postings and developer adoption.',
        inputsNeeded: 'Canonical skill name and historical panel data.',
        outputProduced: 'Half-life estimation in months, decay trajectory, and freshness status.',
        limitations: 'Requires multi-year continuous panel observations; zero synthetic interpolation.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="shlGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#F59E0B" />
              <stop offset="50%" stop-color="#EC4899" />
              <stop offset="100%" stop-color="#8B5CF6" />
            </linearGradient>
            <linearGradient id="sandGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#FDE047" />
              <stop offset="100%" stop-color="#F59E0B" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#shlGrad)" fill-opacity="0.14" />
          <path d="M13 10 H31 M13 34 H31 M15 10 L22 22 L29 10 M15 34 L22 22 L29 34" stroke="url(#shlGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M18 13 H26 L22 19 Z" fill="url(#sandGrad)" />
          <path d="M17 33 H27 L22 27 Z" fill="url(#sandGrad)" />
          <circle cx="22" cy="23" r="1.5" fill="#FDE047" />
          <circle cx="22" cy="25.5" r="1.2" fill="#FDE047" />
        </svg>
      `
    },
    {
      id: 'market_to_person_to_company',
      title: 'Market → Person → Company',
      category: 'Workforce Intelligence',
      desc: 'Connect available market signals to role and skill requirements.',
      cardTagline: 'Connect market signals with people and company needs.',
      promptHint: 'Ask how macroeconomic hiring trends connect to personal growth',
      defaultPrompt: 'How do available market signals connect to people and company needs for {entity}?',
      icon: 'users',
      color: '#06B6D4',
      explainer: {
        whatItDoes: 'Bridges market-level technology adoption, personal skill profiles, and company hiring demands into a unified workforce alignment model.',
        inputsNeeded: 'Target skill, role title, or employer context.',
        outputProduced: 'Three-node alignment matrix showing talent supply, organizational demand, and individual positioning.',
        limitations: 'Bounded strictly to deduplicated postings and authenticated company memberships.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="mpcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#06B6D4" />
              <stop offset="50%" stop-color="#3B82F6" />
              <stop offset="100%" stop-color="#6366F1" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#mpcGrad)" fill-opacity="0.14" />
          <polygon points="22,11 11,31 33,31" stroke="url(#mpcGrad)" stroke-width="1.8" stroke-dasharray="3 2" fill="none" />
          <circle cx="22" cy="11" r="5" fill="#06B6D4" />
          <circle cx="22" cy="11" r="2.5" fill="#FFFFFF" />
          <circle cx="11" cy="31" r="5" fill="#8B5CF6" />
          <circle cx="11" cy="31" r="2.5" fill="#FFFFFF" />
          <circle cx="33" cy="31" r="5" fill="#2563EB" />
          <circle cx="33" cy="31" r="2.5" fill="#FFFFFF" />
          <circle cx="22" cy="24" r="2.5" fill="#38BDF8" />
        </svg>
      `
    },
    {
      id: 'ai_disruption',
      title: 'AI Disruption Impact',
      category: 'Task-Level AI Impact',
      desc: 'Explore verified evidence about task exposure and augmentation.',
      cardTagline: 'Understand where AI may change work tasks.',
      promptHint: 'Ask about automated tasks, AI exposure scores, and human augmentation',
      defaultPrompt: 'How could AI-related task changes affect {entity}?',
      icon: 'zap',
      color: '#F97316',
      explainer: {
        whatItDoes: 'Assesses occupational task-level exposure to AI models based on standardized O*NET work activities and empirical technology adoption.',
        inputsNeeded: 'Role title, SOC code, or skill keyword.',
        outputProduced: 'Theoretical task overlap percentage, augmentation potential, and resilient skills.',
        limitations: 'Measures theoretical capability overlap only; does not predict headcount reduction or job elimination.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="adiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#F59E0B" />
              <stop offset="50%" stop-color="#F97316" />
              <stop offset="100%" stop-color="#EF4444" />
            </linearGradient>
            <linearGradient id="boltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#FEF08A" />
              <stop offset="100%" stop-color="#F59E0B" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#adiGrad)" fill-opacity="0.14" />
          <rect x="10" y="10" width="24" height="24" rx="6" stroke="url(#adiGrad)" stroke-width="1.8" fill="rgba(249, 115, 22, 0.1)" />
          <line x1="7" y1="17" x2="10" y2="17" stroke="#F97316" stroke-width="1.5" stroke-linecap="round" />
          <line x1="7" y1="27" x2="10" y2="27" stroke="#F97316" stroke-width="1.5" stroke-linecap="round" />
          <line x1="34" y1="17" x2="37" y2="17" stroke="#F97316" stroke-width="1.5" stroke-linecap="round" />
          <line x1="34" y1="27" x2="37" y2="27" stroke="#F97316" stroke-width="1.5" stroke-linecap="round" />
          <path d="M24 12 L16 23 H23 L20 32 L28 20 H22 L24 12 Z" fill="url(#boltGrad)" stroke="#B45309" stroke-width="0.8" />
        </svg>
      `
    },
    {
      id: 'forecast',
      title: 'Explainable Forecast',
      category: 'Demand Forecasting',
      desc: 'Review forecasts only when historical data meets readiness requirements.',
      cardTagline: 'Review evidence and assumptions behind a forecast.',
      promptHint: 'Inquire about empirical demand trajectories and readiness states',
      defaultPrompt: 'Show an explainable forecast for {entity} if supported by available evidence.',
      icon: 'trending-up',
      color: '#10B981',
      explainer: {
        whatItDoes: 'Evaluates whether a skill meets rigorous analytical readiness gates (>=6 consecutive valid historical periods) before generating future projections.',
        inputsNeeded: 'At least 6 consecutive monthly observations without panel drift.',
        outputProduced: 'Forecast readiness report, Theil-Sen velocity slope, or honest unreadiness disclosure.',
        limitations: 'Synthetic extrapolation is strictly blocked; unverified predictions are never displayed.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="efGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#10B981" />
              <stop offset="50%" stop-color="#06B6D4" />
              <stop offset="100%" stop-color="#3B82F6" />
            </linearGradient>
            <linearGradient id="efArea" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#10B981" stop-opacity="0.35" />
              <stop offset="100%" stop-color="#10B981" stop-opacity="0" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#efGrad)" fill-opacity="0.14" />
          <path d="M10 32 L16 26 L23 28 L34 14 V32 H10 Z" fill="url(#efArea)" />
          <path d="M10 32 L16 26 L23 28 L34 14" stroke="url(#efGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="16" cy="26" r="2.2" fill="#10B981" />
          <circle cx="23" cy="28" r="2.2" fill="#06B6D4" />
          <circle cx="34" cy="14" r="3" fill="#3B82F6" stroke="#FFFFFF" stroke-width="1.2" />
          <line x1="34" y1="14" x2="34" y2="32" stroke="#3B82F6" stroke-width="1.2" stroke-dasharray="2 2" />
        </svg>
      `
    },
    {
      id: 'action_recommendations',
      title: 'Action Recommendation',
      category: 'Strategic Next Steps',
      desc: 'Explore practical next steps supported by available evidence.',
      cardTagline: 'Turn relevant evidence into practical next steps.',
      promptHint: 'Ask what actions, courses, or adjacent skills you should pursue',
      defaultPrompt: 'What should I learn next based on available evidence for {entity}?',
      icon: 'compass',
      color: '#D946EF',
      explainer: {
        whatItDoes: 'Synthesizes deterministic, verified career steps—such as upskilling in adjacent technologies or closing specific skill gaps.',
        inputsNeeded: 'Current skill profile and optional target role.',
        outputProduced: 'Prioritized recommendations (learn, monitor, bridge gaps) backed by labor market signals.',
        limitations: 'Recommendations are advisory guidance; future salary or placement outcomes are not guaranteed.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="arGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#D946EF" />
              <stop offset="50%" stop-color="#8B3DFF" />
              <stop offset="100%" stop-color="#3B82F6" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#arGrad)" fill-opacity="0.14" />
          <circle cx="22" cy="22" r="14" stroke="url(#arGrad)" stroke-width="1.8" stroke-dasharray="4 2" />
          <circle cx="22" cy="22" r="7" stroke="url(#arGrad)" stroke-width="1.5" />
          <path d="M22 10 L26 22 L22 19 L18 22 Z" fill="#D946EF" />
          <path d="M22 34 L26 22 L22 25 L18 22 Z" fill="#8B3DFF" />
          <circle cx="22" cy="22" r="2.5" fill="#FFFFFF" />
        </svg>
      `
    }
  ],
  market: [
    {
      id: 'market_snapshot',
      title: 'Market Snapshot',
      category: 'Market Telemetry',
      desc: 'Extract latest observations, posting counts, and demand shares.',
      cardTagline: 'See observed demand and adoption signals.',
      promptHint: 'Ask about current market presence, employer demand, or technology adoption',
      defaultPrompt: 'What is the current market demand and technology adoption for {entity}?',
      icon: 'bar-chart-3',
      color: '#3B82F6',
      explainer: {
        whatItDoes: 'Retrieves current point-in-time observations, demand share, and employer hiring volume across verified sources.',
        inputsNeeded: 'Technology name or employer entity.',
        outputProduced: 'Observed posting volume, adoption metrics, and market share indicators.',
        limitations: 'Reflects sample observations collected through configured providers, not the entirety of unindexed jobs.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="msGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#38BDF8" />
              <stop offset="100%" stop-color="#2563EB" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#msGrad)" fill-opacity="0.14" />
          <rect x="11" y="24" width="5" height="10" rx="1.5" fill="url(#msGrad)" />
          <rect x="19" y="17" width="5" height="17" rx="1.5" fill="url(#msGrad)" />
          <rect x="27" y="12" width="5" height="22" rx="1.5" fill="url(#msGrad)" />
          <circle cx="29.5" cy="9.5" r="2" fill="#38BDF8" />
        </svg>
      `
    },
    {
      id: 'market_to_person_to_company',
      title: 'Market-to-Person Impact',
      category: 'Workforce Alignment',
      desc: 'Connect industry hiring patterns to personal skills and company needs.',
      cardTagline: 'Relate hiring patterns to skills and workforce needs.',
      promptHint: 'Ask how market adoption signals at specific companies impact your skills',
      defaultPrompt: 'How do market signals for {entity} affect workforce requirements?',
      icon: 'users',
      color: '#06B6D4',
      explainer: {
        whatItDoes: 'Correlates employer adoption signals with individual capabilities to identify industry workforce shifts.',
        inputsNeeded: 'Employer name or industry technology.',
        outputProduced: 'Workforce impact insights, hiring momentum, and required skill alignment.',
        limitations: 'Requires stored job posting records or company observation telemetry.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="mpcGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#06B6D4" />
              <stop offset="50%" stop-color="#3B82F6" />
              <stop offset="100%" stop-color="#6366F1" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#mpcGrad2)" fill-opacity="0.14" />
          <polygon points="22,11 11,31 33,31" stroke="url(#mpcGrad2)" stroke-width="1.8" stroke-dasharray="3 2" fill="none" />
          <circle cx="22" cy="11" r="5" fill="#06B6D4" />
          <circle cx="11" cy="31" r="5" fill="#8B5CF6" />
          <circle cx="33" cy="31" r="5" fill="#2563EB" />
        </svg>
      `
    },
    {
      id: 'historical_signal_retrieval',
      title: 'Technology & Hiring Signals',
      category: 'Trend Intelligence',
      desc: 'Retrieve multi-period empirical hiring signals without synthetic data.',
      cardTagline: 'Explore observed technology and hiring trends.',
      promptHint: 'Ask about historical demand trends and multi-quarter trajectory',
      defaultPrompt: 'What historical demand signals are observed for {entity}?',
      icon: 'trending-up',
      color: '#10B981',
      explainer: {
        whatItDoes: 'Retrieves empirical multi-period observation time-series across job search feeds, GitHub, and Stack Overflow.',
        inputsNeeded: 'Technology or company name, time range window.',
        outputProduced: 'Verified historical series, period counts, and observation sources.',
        limitations: 'Only verified historical snapshots are returned; zero interpolation across missing periods.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="hsrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#10B981" />
              <stop offset="100%" stop-color="#14B8A6" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#hsrGrad)" fill-opacity="0.14" />
          <path d="M10 28 L18 20 L26 24 L34 14" stroke="url(#hsrGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="18" cy="20" r="2.2" fill="#10B981" />
          <circle cx="26" cy="24" r="2.2" fill="#14B8A6" />
          <circle cx="34" cy="14" r="3" fill="#2563EB" stroke="#FFFFFF" stroke-width="1.2" />
        </svg>
      `
    },
    {
      id: 'action_recommendations',
      title: 'Strategic Next Steps',
      category: 'Market Strategy',
      desc: 'Synthesize actionable market strategies from observed hiring trends.',
      cardTagline: 'Identify practical actions from market evidence.',
      promptHint: 'Ask for practical market positioning and technology investment steps',
      defaultPrompt: 'What strategic actions should I take based on market signals for {entity}?',
      icon: 'compass',
      color: '#D946EF',
      explainer: {
        whatItDoes: 'Produces prioritized next steps for navigating employer market demand and technology adoption.',
        inputsNeeded: 'Observed market or company entity.',
        outputProduced: 'Targeted actions for skill positioning, employer tracking, and readiness.',
        limitations: 'Advisory guidance based strictly on observed market evidence.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="arGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#D946EF" />
              <stop offset="100%" stop-color="#8B3DFF" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#arGrad2)" fill-opacity="0.14" />
          <circle cx="22" cy="22" r="13" stroke="url(#arGrad2)" stroke-width="1.8" stroke-dasharray="4 2" />
          <path d="M22 11 L25 22 L22 19 L19 22 Z" fill="#D946EF" />
          <path d="M22 33 L25 22 L22 25 L19 22 Z" fill="#8B3DFF" />
        </svg>
      `
    }
  ],
  job: [
    {
      id: 'job_posting_search',
      title: 'Verified Job Postings',
      category: 'Job Postings',
      desc: 'Search deduplicated, normalized postings matching keywords and roles.',
      cardTagline: 'Find relevant postings and their listed requirements.',
      promptHint: 'Ask to find active job openings, requirements, and hiring employers',
      defaultPrompt: 'Show verified job postings for {entity}.',
      icon: 'briefcase',
      color: '#8B5CF6',
      explainer: {
        whatItDoes: 'Queries stored, normalized job postings collected from verified sources like JSearch and Adzuna.',
        inputsNeeded: 'Target role, skill keyword, or employer name.',
        outputProduced: 'Deduplicated postings with titles, employers, locations, dates, and required skills.',
        limitations: 'Read-only search against stored collection runs; does not execute unverified web scrapes.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="jpsGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#8B5CF6" />
              <stop offset="100%" stop-color="#6366F1" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#jpsGrad)" fill-opacity="0.14" />
          <rect x="11" y="16" width="22" height="16" rx="4" stroke="url(#jpsGrad)" stroke-width="2" />
          <path d="M17 16 V13 C17 11.5, 18.5 10, 20 10 H24 C25.5 10, 27 11.5, 27 13 V16" stroke="url(#jpsGrad)" stroke-width="1.8" />
          <circle cx="22" cy="24" r="2.5" fill="#8B5CF6" />
        </svg>
      `
    },
    {
      id: 'occupation_software_skills',
      title: 'Role Skill Requirements',
      category: 'O*NET Crosswalk',
      desc: 'Map standardized occupations to workplace software tools and Hot Tech.',
      cardTagline: 'Explore skills and tools linked to a role.',
      promptHint: 'Ask what software tools and core skills are required for specific roles',
      defaultPrompt: 'What software tools and skills are needed for {entity} roles?',
      icon: 'code-2',
      color: '#3B82F6',
      explainer: {
        whatItDoes: 'Crosswalks canonical occupations from O*NET 2018 SOC to required workplace software tools and Hot Technologies.',
        inputsNeeded: 'Standardized occupation title or SOC code.',
        outputProduced: 'Categorized tools, programming languages, and technology popularity flags.',
        limitations: 'Baseline taxonomy representation; specific employer requirements may vary.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="ossGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#3B82F6" />
              <stop offset="100%" stop-color="#8B3DFF" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#ossGrad)" fill-opacity="0.14" />
          <path d="M17 16 L11 22 L17 28 M27 16 L33 22 L27 28" stroke="url(#ossGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <line x1="24" y1="14" x2="20" y2="30" stroke="#38BDF8" stroke-width="2" stroke-linecap="round" />
        </svg>
      `
    },
    {
      id: 'related_occupations',
      title: 'Career Mobility Pathways',
      category: 'Career Mobility',
      desc: 'Traverse career mobility pathways based on shared work activities.',
      cardTagline: 'Discover adjacent roles and transferable work.',
      promptHint: 'Ask about adjacent roles, career transitions, and transferrable skills',
      defaultPrompt: 'What career mobility pathways and adjacent roles exist for {entity}?',
      icon: 'git-branch',
      color: '#06B6D4',
      explainer: {
        whatItDoes: 'Examines career mobility transitions between occupations based on shared work activities and knowledge areas.',
        inputsNeeded: 'Current or target occupation title.',
        outputProduced: 'Related occupations ranked by skill transferability and career transition viability.',
        limitations: 'Mobility viability reflects activity overlap, not hiring guarantees.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="roGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#06B6D4" />
              <stop offset="100%" stop-color="#10B981" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#roGrad)" fill-opacity="0.14" />
          <circle cx="14" cy="30" r="3.5" fill="#06B6D4" />
          <circle cx="30" cy="14" r="3.5" fill="#10B981" />
          <circle cx="30" cy="30" r="3.5" fill="#3B82F6" />
          <path d="M14 26.5 V22 C14 18, 18 14, 26.5 14 M17.5 30 H26.5" stroke="url(#roGrad)" stroke-width="2" stroke-linecap="round" />
        </svg>
      `
    },
    {
      id: 'action_recommendations',
      title: 'Role Preparation Actions',
      category: 'Action Plan',
      desc: 'Formulate concrete preparation steps to target specific roles.',
      cardTagline: 'Plan focused preparation for a target role.',
      promptHint: 'Ask what preparation and learning actions to take to target a role',
      defaultPrompt: 'What career preparation actions do you recommend for {entity}?',
      icon: 'compass',
      color: '#D946EF',
      explainer: {
        whatItDoes: 'Builds a concrete action plan to close skill gaps and prepare for target role requirements.',
        inputsNeeded: 'Target role title and user inventory.',
        outputProduced: 'Milestone actions, skill acquisition priorities, and alignment steps.',
        limitations: 'Grounded in observed posting requirements; individual outcomes depend on execution.'
      },
      motif: `
        <svg class="ai-card-motif-svg" viewBox="0 0 44 44" fill="none">
          <defs>
            <linearGradient id="arGrad3" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#D946EF" />
              <stop offset="100%" stop-color="#8B3DFF" />
            </linearGradient>
          </defs>
          <rect x="4" y="4" width="36" height="36" rx="10" fill="url(#arGrad3)" fill-opacity="0.14" />
          <circle cx="22" cy="22" r="13" stroke="url(#arGrad3)" stroke-width="1.8" stroke-dasharray="4 2" />
          <path d="M22 11 L25 22 L22 19 L19 22 Z" fill="#D946EF" />
          <path d="M22 33 L25 22 L22 25 L19 22 Z" fill="#8B3DFF" />
        </svg>
      `
    }
  ]
};

const capabilityPresentationSources = DOMAIN_CAPABILITY_REGISTRY;
const supportedCapability = (domain, sourceId, id, title, desc, defaultPrompt, followUpCapabilityIds = []) => {
  const source = capabilityPresentationSources[domain].find(capability => capability.id === sourceId);
  return {
    ...source,
    id,
    capabilityId: id,
    supportedDomains: [domain],
    title,
    desc,
    promptHint: desc,
    defaultPrompt,
    explainer: {
      ...source.explainer,
      whatItDoes: desc
    },
    followUpCapabilityIds
  };
};

Object.assign(DOMAIN_CAPABILITY_REGISTRY, {
  skill: [
    supportedCapability('skill', 'skill_health', 'trend_velocity_analysis', 'Skill Demand Trends', 'Review measured demand direction and velocity from verified observations.', 'What demand trend is observed for {entity}?', ['historical_signal_retrieval']),
    supportedCapability('skill', 'skill_half_life', 'historical_signal_retrieval', 'Historical Skill Signals', 'Explore available historical observations without invented periods.', 'What historical skill signals are available for {entity}?', ['evidence_provenance_retrieval']),
    supportedCapability('skill', 'market_to_person_to_company', 'skill_gap_role_fit', 'Skill & Role Alignment', 'Compare your selected skills with a target role when both are available.', 'How do my selected skills align with {entity}?', ['action_recommendations']),
    supportedCapability('skill', 'ai_disruption', 'evidence_provenance_retrieval', 'Evidence & Sources', 'Inspect the verified sources and provenance behind available skill evidence.', 'Show the evidence and sources for {entity}.', ['action_recommendations']),
    supportedCapability('skill', 'forecast', 'skill_technology_reference', 'Skill Reference', 'Look up canonical skill and technology definitions and reference context.', 'What does {entity} mean in the skill catalog?'),
    supportedCapability('skill', 'action_recommendations', 'action_recommendations', 'Action Recommendation', 'Explore practical next steps grounded in your available evidence.', 'What should I learn next based on evidence for {entity}?')
  ],
  market: [
    supportedCapability('market', 'market_snapshot', 'market_snapshot', 'Market Snapshot', 'Review the latest stored market observations for an employer or technology.', 'What current market signals are available for {entity}?', ['historical_signal_retrieval']),
    supportedCapability('market', 'historical_signal_retrieval', 'historical_signal_retrieval', 'Technology & Hiring Signals', 'Explore verified historical hiring and adoption observations.', 'What historical market signals are available for {entity}?', ['evidence_provenance_retrieval']),
    supportedCapability('market', 'action_recommendations', 'trend_velocity_analysis', 'Market Trend & Velocity', 'Review measured market trend direction when comparable observations exist.', 'What trend is observed for {entity}?', ['evidence_provenance_retrieval']),
    supportedCapability('market', 'market_to_person_to_company', 'evidence_provenance_retrieval', 'Evidence & Sources', 'Inspect source records and provenance for market intelligence.', 'Show the evidence and sources for {entity}.')
  ],
  job: [
    supportedCapability('job', 'job_posting_search', 'job_posting_search', 'Verified Job Postings', 'Search previously collected postings; results are not live vacancy totals.', 'Show stored job postings for {entity}.', ['occupation_software_skills']),
    supportedCapability('job', 'occupation_software_skills', 'occupation_software_skills', 'Role Skill Requirements', 'Look up tools and technologies associated with a standardized occupation.', 'What software skills are used in {entity}?', ['skill_gap_role_fit']),
    supportedCapability('job', 'related_occupations', 'related_occupations', 'Career Mobility Pathways', 'Explore occupations connected through shared work activities.', 'What occupations are related to {entity}?', ['job_posting_search']),
    supportedCapability('job', 'action_recommendations', 'skill_gap_role_fit', 'Skill & Role Alignment', 'Compare available skills with a target occupation when both are provided.', 'How do my selected skills align with {entity}?', ['action_recommendations']),
    supportedCapability('job', 'action_recommendations', 'action_recommendations', 'Role Preparation Actions', 'Explore evidence-informed preparation steps for a target role.', 'What should I do next to prepare for {entity}?')
  ]
});

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
  const filters = domState.filters || {};
  const plan = await queryCoreIntelligencePlan({
    message: question,
    domain,
    portalType: 'individual',
    location: filters.location || undefined,
    timeRange: filters.timeRange || filters.timeframe || '30d',
    targetRole: filters.selectedRole || undefined,
    selectedSkills: filters.selectedSkills?.length
      ? filters.selectedSkills
      : filters.selectedSkill ? [filters.selectedSkill] : [],
    selectedCompanies: filters.selectedCompany ? [filters.selectedCompany] : [],
    conversationId: domState.conversation_id || undefined,
    filters: {
      scope: filters.scope,
      location: filters.location,
      selected_role: filters.selectedRole,
      selected_skill: filters.selectedSkill,
      selected_skills: filters.selectedSkills,
      selected_company: filters.selectedCompany,
      requested_time_window: filters.timeRange || filters.timeframe
    }
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
  const filters = requestContext.filters || {};
  const entityFact = (turn.facts || []).find(fact =>
    fact.canonical_entity_id && fact.entity_name && fact.quality_state === 'valid'
  );
  const originalQuestion = journey.originalQuestion || turn.userQuestion || '';
  const entityName = entityFact?.entity_name
    || filters.selected_skill
    || filters.selected_company
    || filters.selected_role
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
        time_range: requestContext.timeRange || '30d',
        location: requestContext.location || undefined,
        target_role: requestContext.targetRole || undefined,
        selected_skills: requestContext.selectedSkills || []
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
    historyLoadError = error?.message || 'Conversation history is temporarily unavailable.';
    conversationsList = [];
    const sidebarBody = document.getElementById('aiHistoryGroupedList');
    if (sidebarBody) sidebarBody.innerHTML = renderGroupedHistoryItemsHTML();
  }
}

function renderGroupedHistoryItemsHTML() {
  const dom = getActiveDomainKey();
  const domCfg = DOMAIN_CONFIG[dom] || DOMAIN_CONFIG.skill;
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
    const incomingDomain = queryParams.get('domain');
    const incomingQuery = queryParams.get('q');

    if (incomingDomain && ['skill', 'market', 'job'].includes(incomingDomain)) {
      switchAssistantDomain(incomingDomain);
    }
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
              <span class="ai-composer-engine-title">${activeDomain === 'skill' ? 'Skill Intelligence' : activeDomain === 'market' ? 'Market Intelligence' : 'Job Intelligence'} Engine</span>
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
            <span class="ai-header-subtitle">Skill, Market & Workforce Intelligence</span>
          </div>
        </div>

        <div class="ai-header-center" role="tablist" aria-label="Select Intelligence Domain">
          <div class="ai-domain-segment-bar">
            <button type="button" role="tab" aria-selected="${activeDomain === 'skill'}" class="ai-domain-tab-pill ${activeDomain === 'skill' ? 'is-active' : ''}" data-ai-domain="skill">
              <i data-lucide="brain-circuit"></i>
              <span>Skill</span>
            </button>
            <button type="button" role="tab" aria-selected="${activeDomain === 'market'}" class="ai-domain-tab-pill ${activeDomain === 'market' ? 'is-active' : ''}" data-ai-domain="market">
              <i data-lucide="building-2"></i>
              <span>Market</span>
            </button>
            <button type="button" role="tab" aria-selected="${activeDomain === 'job'}" class="ai-domain-tab-pill ${activeDomain === 'job' ? 'is-active' : ''}" data-ai-domain="job">
              <i data-lucide="briefcase"></i>
              <span>Job</span>
            </button>
          </div>
        </div>

        <div class="ai-header-right">
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
              <button type="button" role="menuitem" class="ai-profile-menu-item" id="btnNewAiConversation">
                <i data-lucide="plus"></i><span>New Chat</span>
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
function renderTurnChartOrBaselineHTML(turn, trendFact, facts, jobPostings) {
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
                <strong>${escapeHTML(p.title || 'Open Role')}</strong>
                <span class="ai-res-posting-company">${escapeHTML(p.company || 'Employer')}</span>
              </div>
              <div class="ai-res-posting-card__meta">
                <span><i data-lucide="map-pin"></i> ${escapeHTML(p.location || 'Global')}</span>
                ${p.posting_date ? `<span>· ${escapeHTML(String(p.posting_date).slice(0, 10))}</span>` : ''}
                ${p.skill ? `<span>· ${escapeHTML(p.skill)}</span>` : ''}
              </div>
              ${Array.isArray(p.required_skills) && p.required_skills.length
                ? `<div class="ai-res-posting-skills"><strong>Skills recorded:</strong> ${p.required_skills.map(escapeHTML).join(', ')}</div>`
                : '<div class="ai-res-posting-skills">No structured required-skill list was recorded.</div>'}
              ${/^https?:\/\//i.test(String(p.source_url || '')) ? `
                <a href="${escapeHTML(p.source_url)}" target="_blank" rel="noopener noreferrer" class="ai-res-posting-link">
                  View Source (${escapeHTML(p.source || 'Verified')}) ↗
                </a>
              ` : `<span class="ai-res-posting-source">Source: ${escapeHTML(p.source || 'Platform Store')}</span>`}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

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
        <div class="ai-res-mini-chart-box">
          <svg viewBox="0 0 480 116" class="ai-res-trend-svg" role="img" aria-label="Observed multi-period trend">
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
  const domState = getActiveDomainSession(activeDomain);
  const entity = activeDomain === 'skill'
    ? (domState.filters.selectedSkill || '')
    : activeDomain === 'market'
      ? (domState.filters.selectedCompany || '')
      : (domState.filters.selectedRole || '');

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
  const statusInfo = statusKey ? (statusLabels[statusKey] || { label: 'Status unavailable', badge: 'cmp-badge--neutral', icon: 'circle-help' }) : null;
  const isServiceError = ['error', 'failed', 'blocked', 'data_source_unavailable'].includes(statusKey)
    || ['error', 'failed', 'blocked'].includes(turn.execution_status);
  const domState = getActiveDomainSession(activeDomain);
  const usedCapabilityId = turn.capabilityId
    || turn.requestContext?.capabilityId
    || turn.requestContext?.filters?.selected_feature;
  const usedCapability = (DOMAIN_CAPABILITY_REGISTRY[turn.domainKey || activeDomain] || [])
    .find(capability => capability.id === usedCapabilityId);
  const freshness = turn.freshness || {};
  const unappliedFilters = Array.isArray(turn.unapplied_filters) ? turn.unapplied_filters : [];
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
  const hasEvidencePanel = allFacts.length > 0 || evidenceList.length > 0 || metricResults.length > 0;
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

        ${unappliedFilters.length > 0 ? `
          <div class="ai-res-unapplied-banner">
            <strong>Filter Disclosure:</strong> ${unappliedFilters.map(u => `${escapeHTML(u.filter)} (${escapeHTML(u.reason)})`).join(' • ')}
          </div>
        ` : ''}

        <!-- Flowing Conversational Body (Natural AI Answer First, Requirement 10) -->
        <div class="ai-conv-body">
          <!-- Main Markdown Response -->
          ${renderConversationAnswer(turn, formatMarkdown, {
            answer: turn.answer || turn.finding || (isServiceError ? 'The intelligence service did not return an answer.' : ''),
            explanation: whyItMattersText
          })}

          ${['error', 'failed', 'data_source_unavailable'].includes(statusKey) && turn.userQuestion ? `
            <div class="ai-conv-error-retry">
              <button type="button" class="ai-retry-turn" data-retry-turn-id="${escapeHTML(turn.id || '')}" data-retry-question="${escapeHTML(turn.userQuestion)}">
                <i data-lucide="refresh-cw"></i> Retry this question
              </button>
            </div>
          ` : ''}

          ${hasEvidencePanel ? renderIntelligenceEvidencePanel({
            status: turn.status,
            metric_results: metricResults,
            facts: allFacts,
            evidence: evidenceList,
            limitations: turn.limitations,
            freshness: turn.freshness
          }, { title: 'Evidence snapshot', compact: true }) : ''}

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
              finding: payload.answer || t.answer_summary || t.answer || '',
              facts: payload.facts || t.facts || [],
              metric_results: payload.metric_results || t.metric_results || [],
              evidence: payload.evidence || t.evidence || [],
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
    const domainButtons = [...container.querySelectorAll('[data-ai-domain]')];
    isCreatingConversation = true;
    newChatButtons.forEach(button => {
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      button.querySelector('span')?.replaceChildren(document.createTextNode('Starting…'));
    });
    domainButtons.forEach(button => { button.disabled = true; });
    try {
      const created = await createIntelligenceConversation({
        portalType: 'individual',
        domain: dom,
        title: `New ${DOMAIN_CONFIG[dom]?.label || 'Intelligence'} Session`,
        filters: domState.filters
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
      if (currentAiState === 'analyzing' || currentAiState === 'thinking') {
        activeRequestCounter += 1;
        currentAiState = 'idle';
      }
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
      showToast(`Started new ${DOMAIN_CONFIG[dom]?.label || 'Intelligence'} chat`);
    } catch (error) {
      showToast(error?.message || 'Could not create a new chat. Please try again.');
    } finally {
      isCreatingConversation = false;
      newChatButtons.forEach(button => {
        button.disabled = false;
        button.removeAttribute('aria-busy');
        button.querySelector('span')?.replaceChildren(document.createTextNode('New Chat'));
      });
      domainButtons.forEach(button => { button.disabled = false; });
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

  // Domain Selector Pills (Strict Per-Domain Isolation)
  container.querySelectorAll('[data-ai-domain]').forEach(el => {
    el.addEventListener('click', () => {
      const dom = el.getAttribute('data-ai-domain');
      if (!dom || dom === getActiveDomainKey()) return;
      switchAssistantDomain(dom);
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
      if (fu) executeAiQuery(fu, {
        requestContext: turn?.requestContext,
        selectedFeatureId: turn?.capabilityId || null
      });
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
          domain: dom,
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
  const filters = options.filterState || domState.filters;
  const rawScope = filters.scope || (dom === 'skill' ? 'All Skills' : 'All');
  const activeScope = rawScope === 'Favourite Skills' || rawScope === 'Favourite Companies'
    ? 'Favourites'
    : rawScope === 'All Companies'
      ? 'All'
      : rawScope;

  // Resolve scope-specific entities without fabricating fallback values
  let selectedSkillsPayload = [];
  let selectedCompaniesPayload = [];
  let scopeEmpty = false;

  if (dom === 'skill') {
    const focusSkills = Array.isArray(filters.selectedSkills) && filters.selectedSkills.length
      ? filters.selectedSkills
      : (filters.selectedSkill ? [filters.selectedSkill] : []);
    const observedOptions = getObservedFilterOptions(dom, domState.history);
    const availableSkills = new Set(observedOptions.entities);
    if (focusSkills.length) {
      selectedSkillsPayload = focusSkills.filter(name => availableSkills.has(name)).map(name => resolveCanonicalAssistantEntity(dom, name));
    } else if (activeScope === 'Favourites') {
      const uniqueFavs = (observedOptions.favoriteSkills || []).filter(name => availableSkills.has(name));
      if (uniqueFavs.length) {
        selectedSkillsPayload = uniqueFavs.map(name => resolveCanonicalAssistantEntity(dom, name));
      } else {
        scopeEmpty = true;
        selectedSkillsPayload = [];
      }
    } else {
      selectedSkillsPayload = [];
    }
  } else if (dom === 'market') {
    const focusTechnology = filters.selectedCompany || '';
    const observedOptions = getObservedFilterOptions(dom, domState.history);
    const availableTechnologies = new Set(observedOptions.entities);
    const technologyNames = new Set((marketCatalog?.technologies || []).map(item => item.name));
    const companyNames = new Set([...(marketCatalog?.companies_with_job_evidence || []).map(item => item.name), ...(marketCatalog?.registered_company?.name ? [marketCatalog.registered_company.name] : [])]);
    if (focusTechnology) {
      if (technologyNames.has(focusTechnology)) selectedSkillsPayload = [resolveCanonicalAssistantEntity(dom, focusTechnology)];
      else if (companyNames.has(focusTechnology)) selectedCompaniesPayload = [resolveCanonicalAssistantEntity(dom, focusTechnology)];
    } else if (activeScope === 'Favourites') {
      const uniqueFavTechnologies = [...new Set(observedOptions.favoriteMarketEntities || [])]
        .filter(name => availableTechnologies.has(name));
      const favoriteTechnologies = uniqueFavTechnologies.filter(name => technologyNames.has(name));
      const favoriteCompanies = uniqueFavTechnologies.filter(name => companyNames.has(name));
      if (favoriteTechnologies.length || favoriteCompanies.length) {
        selectedSkillsPayload = favoriteTechnologies.map(name => resolveCanonicalAssistantEntity(dom, name));
        selectedCompaniesPayload = favoriteCompanies.map(name => resolveCanonicalAssistantEntity(dom, name));
      } else {
        scopeEmpty = true;
        selectedSkillsPayload = [];
      }
    } else {
      selectedSkillsPayload = [];
    }
  } else {
    if (filters.selectedCompany) {
      selectedCompaniesPayload = [resolveCanonicalAssistantEntity(dom, filters.selectedCompany)];
    }
    if (activeScope === 'Favourites') {
      const observedOptions = getObservedFilterOptions(dom, domState.history);
      const availableCompanies = new Set(observedOptions.entities);
      const uniqueFavCos = (observedOptions.favoriteCompanies || []).filter(name => availableCompanies.has(name));
      if (uniqueFavCos.length) {
        selectedCompaniesPayload = uniqueFavCos.map(name => resolveCanonicalAssistantEntity(dom, name));
      } else {
        scopeEmpty = true;
      }
    }
    selectedSkillsPayload = filters.selectedSkill ? [filters.selectedSkill] : [];
  }

  const requestContext = options.requestContext || {
    domain: dom,
    capabilityId: selectedCapabilityId,
    location: filters.location === 'Global' ? null : (filters.location || null),
    timeRange: normalizeAnswerTimeRange(filters.timeRange || 'Max Available'),
    targetRole: filters.selectedRole || null,
    selectedSkills: selectedSkillsPayload,
    selectedRoles: filters.selectedRole ? [filters.selectedRole] : [],
    selectedCompanies: selectedCompaniesPayload,
    filters: {
      domain: dom,
      scope: activeScope,
      scope_empty: scopeEmpty,
      requested_time_window: filters.timeRange || 'Max Available',
      location: filters.location || null,
      selected_skill: selectedSkillsPayload[0] || null,
      selected_skills: selectedSkillsPayload,
      selected_company: selectedCompaniesPayload[0] || null,
      selected_role: filters.selectedRole || null,
      selected_feature: selectedCapabilityId
    }
  };
  const guidedJourneyId = selectedCapabilityId
    && domState.guidedJourney?.currentCapabilityId === selectedCapabilityId
    ? domState.guidedJourney.id
    : null;
  domState.pendingQuestion = options.replaceTurnId ? '' : question;
  updateAiState('analyzing');
  renderDedicatedAIAssistantPage();

  try {
    updateAiState('thinking');

    const answerRes = await queryCoreIntelligenceAnswer({
      message: question,
      portalType: 'individual',
      ...requestContext,
      capabilityId: selectedCapabilityId,
      conversationId: domState.conversation_id || getActiveConversationId('individual', dom, resolveCurrentUserId()) || null,
      clientMessageId: options.clientMessageId || clientMessageId,
      regenerate: Boolean(options.regenerate)
    });

    if (reqId !== activeRequestCounter) return;

    if (answerRes.conversation_id) {
      domState.conversation_id = answerRes.conversation_id;
      setActiveConversationId(answerRes.conversation_id, 'individual', dom, resolveCurrentUserId());
    }
    if (guidedJourneyId && domState.guidedJourney?.id === guidedJourneyId) {
      domState.guidedJourney.conversationId = answerRes.conversation_id || domState.conversation_id;
    }

    const factsList = Array.isArray(answerRes.facts) ? answerRes.facts : [];
    const postingsFact = factsList.find(f => f.fact_type === 'stored_job_postings');
    const jobPostings = Array.isArray(postingsFact?.details?.postings) ? postingsFact.details.postings : [];

    const turn = {
      id: answerRes.request_id || `turn_${Date.now()}`,
      clientMessageId: options.clientMessageId || clientMessageId,
      domainKey: dom,
      requestContext,
      capabilityId: selectedCapabilityId,
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
      answer_origin: answerRes.answer_origin,
      finding: answerRes.answer,
      facts: factsList,
      metric_results: answerRes.metric_results || [],
      jobPostings: jobPostings,
      evidence: answerRes.evidence,
      limitations: answerRes.limitations,
      reason_codes: answerRes.reason_codes,
      capabilities_used: answerRes.capabilities_used,
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
