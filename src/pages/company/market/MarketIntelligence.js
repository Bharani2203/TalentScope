import { queryCoreIntelligenceAnswer } from '../../../api/core-intelligence-client.js';
import { renderConversationAnswer } from '../../../components/common/ConversationAnswer.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { renderStructuredIntelligenceDetails } from '../../../components/common/IntelligenceResultDetails.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);

const FEATURE_OPTIONS = {
  market_snapshot: {
    label: 'Market Snapshot',
    capabilityId: 'market_snapshot',
    prompt: 'Give me a market snapshot for Python in India.'
  },
  hiring_signals: {
    label: 'Technology and Hiring Signals',
    domain: 'job',
    capabilityId: 'job_posting_search',
    prompt: 'What hiring signals are available for Python in India?'
  },
  historical_signals: {
    label: 'Historical Skill Signals',
    capabilityId: 'historical_signal_retrieval',
    prompt: 'Show developer adoption signals for Python in India.'
  },
  market_trend: {
    label: 'Market Trend and Velocity',
    capabilityId: 'trend_velocity_analysis',
    prompt: 'Is Python hiring demand increasing in India based on the available observations?'
  },
  evidence_sources: {
    label: 'Evidence and Sources',
    capabilityId: 'evidence_provenance_retrieval',
    prompt: 'Show the evidence and sources for Python market signals.'
  }
};

let selectedFeature = 'market_snapshot';
let marketQuestionDraft = FEATURE_OPTIONS.market_snapshot.prompt;
let marketLocationDraft = '';
let companyMarketData = null;
let companyMarketLoading = false;
let companyMarketError = null;
let companyMarketConversationId = null;
let companyMarketConversationDomain = null;
let companyMarketRequestVersion = 0;

export function buildMarketAnswerRequest({
  feature = selectedFeature,
  message,
  location = '',
  conversationId = companyMarketConversationId
} = {}) {
  const option = FEATURE_OPTIONS[feature] || FEATURE_OPTIONS.market_snapshot;
  return {
    message: String(message || option.prompt).trim(),
    market_feature: feature,
    portal_type: 'company',
    domain: option.domain || 'market',
    capability_id: option.capabilityId,
    location: String(location || '').trim() || null,
    time_range: 'max_available',
    conversation_id: conversationId || null
  };
}

// Retain the prior export for callers/tests while moving it to the authoritative answer API.
export function buildCompanyMarketRequest() {
  return buildMarketAnswerRequest({ feature: 'market_snapshot' });
}

function companyRequestErrorMessage(error) {
  if (error?.status === 401 || error?.status === 403) {
    return 'Company access could not be verified. Sign in with an authorized company account; no market result was loaded.';
  }
  if (error?.status === 503) {
    return 'Market intelligence is temporarily unavailable. No market result was loaded.';
  }
  return 'Market intelligence could not be loaded. No verified result was returned.';
}

export async function submitMarketQuestion(request, rerender) {
  const capabilityFeature = Object.entries(FEATURE_OPTIONS).find(([, feature]) =>
    feature.capabilityId === request?.capability_id
  )?.[0];
  selectedFeature = FEATURE_OPTIONS[request?.market_feature]
    ? request.market_feature
    : capabilityFeature || 'market_snapshot';
  marketQuestionDraft = request?.message || marketQuestionDraft;
  marketLocationDraft = request?.location || '';
  const currentVersion = ++companyMarketRequestVersion;
  companyMarketLoading = true;
  companyMarketError = null;
  if (typeof rerender === 'function') rerender();

  try {
    const response = await queryCoreIntelligenceAnswer(request);
    if (currentVersion !== companyMarketRequestVersion) return null;
    companyMarketData = response;
    companyMarketConversationId = response.conversation_id || request.conversation_id || null;
    companyMarketConversationDomain = response.domain || request.domain || null;
    companyMarketLoading = false;
    if (typeof rerender === 'function') rerender();
    return response;
  } catch (error) {
    if (currentVersion !== companyMarketRequestVersion) return null;
    companyMarketError = companyRequestErrorMessage(error);
    companyMarketLoading = false;
    if (typeof rerender === 'function') rerender();
    return null;
  }
}

export function loadCompanyMarketData(rerender) {
  return submitMarketQuestion(buildCompanyMarketRequest(), rerender);
}

function markdownSafe(text) {
  return escapeHtml(text).replace(/\r?\n/g, '<br>');
}

function renderFollowUps(response) {
  const questions = Array.isArray(response?.follow_up_questions)
    ? response.follow_up_questions.slice(0, 3)
    : [];
  if (!questions.length) return '';
  return `<div class="market-answer-followups" aria-label="Suggested follow-up questions">
    <strong>Follow-up questions</strong>
    ${questions.map((question, index) => `<button type="button" class="cmp-btn-secondary market-follow-up" data-follow-up-index="${index}">${escapeHtml(question)}</button>`).join('')}
  </div>`;
}

function renderAnswer() {
  if (companyMarketLoading) {
    return `<div class="cmp-card market-answer-state" role="status" aria-live="polite">Checking the selected market evidence…</div>`;
  }
  if (companyMarketError) {
    return `<div class="cmp-card market-answer-state" role="alert">${escapeHtml(companyMarketError)}</div>`;
  }
  if (!companyMarketData) {
    return `<div class="cmp-card market-answer-state" role="status">Choose a market feature and ask a question to retrieve verified results.</div>`;
  }

  const feature = FEATURE_OPTIONS[selectedFeature] || FEATURE_OPTIONS.market_snapshot;
  const executed = companyMarketData.executed_primary_capability;
  const planned = companyMarketData.planned_primary_capability;
  const capabilityMatches = (executed || planned) === feature.capabilityId
    && (!companyMarketData.domain || companyMarketData.domain === (feature.domain || 'market'));
  const consistencyNotice = capabilityMatches
    ? ''
    : '<p class="market-answer-state" role="alert">The selected feature did not execute. No result is attributed to it.</p>';

  return `<section class="market-answer" aria-label="Market intelligence answer">
    <header class="market-answer__header">
      <div><span class="cmp-eyebrow">${escapeHtml(feature.label)}</span><h2>Market answer</h2></div>
      <button type="button" class="cmp-btn-secondary" id="marketNewConversation">New conversation</button>
    </header>
    ${consistencyNotice}
    ${renderConversationAnswer(companyMarketData, markdownSafe)}
    ${renderStructuredIntelligenceDetails(companyMarketData)}
    ${renderIntelligenceEvidencePanel(companyMarketData, { title: 'Evidence and provenance' })}
    ${renderFollowUps(companyMarketData)}
  </section>`;
}

export function renderCompanyMarketIntelligence() {
  const options = Object.entries(FEATURE_OPTIONS).map(([key, feature]) =>
    `<option value="${key}" ${selectedFeature === key ? 'selected' : ''}>${escapeHtml(feature.label)}</option>`
  ).join('');
  const selected = FEATURE_OPTIONS[selectedFeature] || FEATURE_OPTIONS.market_snapshot;

  return `<div class="company-page company-market">
    <section class="cmp-hero">
      <div class="cmp-hero__content">
        <span class="cmp-eyebrow">MARKET INTELLIGENCE</span>
        <h1>Explore observed market signals</h1>
        <p>Answers use stored, source-specific evidence. Sampled job postings are not a count of all vacancies. Reference datasets and developer activity are not hiring demand.</p>
      </div>
    </section>
    <section class="cmp-section">
      <div class="cmp-card market-query-card">
        <label for="marketFeature">Market feature</label>
        <select id="marketFeature" class="market-query-control">${options}</select>
        <form id="marketQuestionForm">
          <label for="marketQuestion">Question</label>
          <textarea id="marketQuestion" class="market-query-control" rows="3" required>${escapeHtml(marketQuestionDraft || selected.prompt)}</textarea>
          <div class="market-query-row">
            <div class="market-query-location"><label for="marketLocation">Geography (optional)</label><input id="marketLocation" class="market-query-control" type="text" maxlength="160" placeholder="For example, India" value="${escapeHtml(marketLocationDraft)}"></div>
            <button type="submit" class="cmp-btn-primary" ${companyMarketLoading ? 'disabled' : ''}>${companyMarketLoading ? 'Checking…' : 'Ask market intelligence'}</button>
          </div>
        </form>
      </div>
    </section>
    <section class="cmp-section" aria-live="polite">${renderAnswer()}</section>
  </div>`;
}

export function bindCompanyMarketEvents(rerender) {
  const featureSelect = document.querySelector('#marketFeature');
  const form = document.querySelector('#marketQuestionForm');
  const questionInput = document.querySelector('#marketQuestion');
  const locationInput = document.querySelector('#marketLocation');

  featureSelect?.addEventListener('change', () => {
    const nextFeature = featureSelect.value;
    if (!FEATURE_OPTIONS[nextFeature]) return;
    companyMarketRequestVersion += 1;
    companyMarketLoading = false;
    const nextDomain = FEATURE_OPTIONS[nextFeature].domain || 'market';
    if (companyMarketConversationDomain && companyMarketConversationDomain !== nextDomain) {
      companyMarketConversationId = null;
      companyMarketConversationDomain = null;
    }
    selectedFeature = nextFeature;
    companyMarketData = null;
    companyMarketError = null;
    marketQuestionDraft = FEATURE_OPTIONS[nextFeature].prompt;
    if (questionInput) questionInput.value = marketQuestionDraft;
    if (typeof rerender === 'function') rerender();
  });

  form?.addEventListener('submit', event => {
    event.preventDefault();
    marketQuestionDraft = questionInput?.value || '';
    marketLocationDraft = locationInput?.value || '';
    const request = buildMarketAnswerRequest({
      feature: featureSelect?.value || selectedFeature,
      message: marketQuestionDraft,
      location: marketLocationDraft,
      conversationId: companyMarketConversationId
    });
    selectedFeature = featureSelect?.value || selectedFeature;
    void submitMarketQuestion(request, rerender);
  });

  document.querySelector('#marketNewConversation')?.addEventListener('click', () => {
    companyMarketConversationId = null;
    companyMarketConversationDomain = null;
    companyMarketData = null;
    companyMarketError = null;
    if (typeof rerender === 'function') rerender();
  });

  document.querySelectorAll('.market-follow-up').forEach(button => {
    button.addEventListener('click', () => {
      const index = Number(button.dataset.followUpIndex);
      const question = companyMarketData?.follow_up_questions?.[index];
      if (!question) return;
      marketQuestionDraft = question;
      void submitMarketQuestion(buildMarketAnswerRequest({ message: question }), rerender);
    });
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
}
