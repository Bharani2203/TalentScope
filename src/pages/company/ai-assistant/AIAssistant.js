// ============================================================================
// TALENTSCOPE.AI — COMPANY STRATEGIC AI COPILOT
// Grounded Executive Decision Copilot: Answer, Why, Evidence, Affected Teams & Actions (#874FFF)
// All data clearly marked as simulated prototype intelligence
// ============================================================================

import { companyProfile } from '../../../data/company/company-data.js';
import { getCurrentUser } from '../../../auth/auth-state.js';
import { queryCoreIntelligenceAnswer } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { renderAnswerEvidencePanel } from '../../../components/common/IntelligenceComponents.js';

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function formatMarkdown(content) {
  if (!content) return '';
  return String(content)
    .replace(/^### (.*$)/gim, '<h4 style="margin:10px 0 4px; font-size:14px; color:var(--cmp-primary); font-weight:800;">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 style="margin:12px 0 6px; font-size:15px; color:var(--cmp-primary); font-weight:800;">$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left:14px; list-style-type:disc;">$1</li>')
    .replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li style="margin-left:14px; list-style-type:decimal;">$2</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

const statusBadgeMap = {
  completed: { label: 'Verified Grounded', bg: 'rgba(25,183,122,0.12)', color: '#059669', icon: 'check-circle-2' },
  ready: { label: 'Verified Grounded', bg: 'rgba(25,183,122,0.12)', color: '#059669', icon: 'check-circle-2' },
  partial: { label: 'Partial Coverage', bg: 'rgba(245,158,11,0.12)', color: '#D97706', icon: 'alert-circle' },
  unavailable: { label: 'Capability Unavailable', bg: 'rgba(107,114,128,0.12)', color: '#4B5563', icon: 'ban' },
  error: { label: 'Service Error', bg: 'rgba(239,68,68,0.12)', color: '#DC2626', icon: 'alert-triangle' },
  requires_clarification: { label: 'Clarification Required', bg: 'rgba(245,158,11,0.12)', color: '#D97706', icon: 'help-circle' },
  insufficient_data: { label: 'Insufficient Data', bg: 'rgba(107,114,128,0.12)', color: '#4B5563', icon: 'database' },
  unsupported: { label: 'Unsupported in G2.6/G2.7', bg: 'rgba(107,114,128,0.12)', color: '#4B5563', icon: 'ban' },
  blocked: { label: 'Access Restricted', bg: 'rgba(239,68,68,0.12)', color: '#DC2626', icon: 'lock' },
  failed: { label: 'Query Failed', bg: 'rgba(239,68,68,0.12)', color: '#DC2626', icon: 'alert-triangle' }
};

const exampleQuestions = [
  { label: 'Workforce Changes', query: 'What changed in our workforce?' },
  { label: 'Critical Skills', query: 'Which skills are becoming critical?' },
  { label: 'Team Gaps', query: 'Which teams have the largest skill gaps?' },
  { label: 'Future Role Fit', query: 'Which employees could fit this future role?' },
  { label: 'Reskilling Strategy', query: 'Where should we reskill or redeploy?' },
  { label: 'CUDA Importance', query: 'Why is CUDA becoming important?' }
];

let activeConversationId = null;
let isCopilotAnalyzing = false;
let inquiryGeneration = 0;

let copilotMessages = [
  {
    sender: 'assistant',
    structured: {
      answer: `Welcome to the **Executive Strategic AI Copilot**. Answers use evidence available to your authenticated organization. The surrounding company profile and dashboard are simulated demo data.`,
      why: 'Company-specific records are returned only when the backend confirms organization membership.',
      evidence: [],
      affectedTeams: [],
      action: 'Select a question to check which supported evidence is available.'
    }
  }
];

export function renderCompanyAIAssistant() {
  const p = companyProfile;

  return `
    <div class="company-page company-ai-assistant">
      <!-- 1. HERO -->
      <section class="cmp-hero">
        <div class="cmp-hero__content">
          <div class="cmp-hero__greeting">
            <span class="cmp-eyebrow">
              <i data-lucide="sparkles" class="cmp-icon-inline"></i>
              STRATEGIC DECISION COPILOT
            </span>
            <h1>Strategic Workforce AI Copilot</h1>
            <p>Ask questions about evidence available to your authenticated organization. Workforce simulations and unsupported metrics remain unavailable.</p>
          </div>

          <div class="cmp-hero__context-badge">
            <div class="cmp-hero__company-logo">${esc(p.logoInitials)}</div>
            <div class="cmp-hero__context-info">
              <strong>${esc(p.name)}</strong>
              <span>Authenticated organization context</span>
              <div class="cmp-hero__context-meta">
                <span class="cmp-badge cmp-badge--neutral">Simulated Demo Data</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. QUICK EXECUTIVE INQUIRY CHIPS (Section 21) -->
      <section class="cmp-section" style="margin-bottom: 16px;">
        <span style="font-size: 11px; font-weight: 750; color: var(--cmp-text-muted); text-transform: uppercase; display: block; margin-bottom: 8px;">
          Strategic Questions
        </span>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          ${exampleQuestions.map(q => `
            <button type="button" class="cmp-btn-secondary cmp-copilot-chip-btn" data-query="${esc(q.query)}" style="height: 32px; padding: 0 12px; font-size: 12px;">
              <i data-lucide="sparkles" style="width: 13px; height: 13px;"></i>
              <span>${esc(q.query)}</span>
            </button>
          `).join('')}
        </div>
      </section>

      <!-- 3. CHAT WORKSPACE -->
      <section class="cmp-section">
        <div class="cmp-card" style="padding: 0; overflow: hidden; display: flex; flex-direction: column; min-height: 540px;">
          <!-- Top bar -->
          <div style="padding: 12px 18px; background: var(--cmp-very-light); border-bottom: 1px solid var(--cmp-border); display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 24px; height: 24px; border-radius: 50%; background: var(--cmp-primary); color: #FFF; display: flex; align-items: center; justify-content: center; font-size: 12px;">
                <i data-lucide="sparkles" style="width: 12px; height: 12px;"></i>
              </div>
              <strong style="font-size: 13px; color: var(--cmp-text-primary);">TalentScope Strategic Copilot</strong>
              <span class="cmp-badge cmp-badge--neutral" style="font-size: 10.5px;">Evidence checked per response</span>
            </div>
            <button type="button" class="cmp-btn-ghost" id="cmpClearChatBtn" style="padding: 2px 8px; font-size: 11.5px;">
              <i data-lucide="trash-2"></i>
              <span>Reset</span>
            </button>
          </div>

          <!-- Messages Area -->
          <div id="cmpCopilotChatArea" style="flex: 1; padding: 18px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; max-height: 480px;">
            ${copilotMessages.map(msg => renderCopilotMessage(msg)).join('')}
          </div>

          <!-- Thinking Indicator -->
          <div id="cmpCopilotThinkingIndicator" style="display: none; padding: 10px 18px; background: var(--cmp-light-primary); border-top: 1px solid var(--cmp-border-accent); font-size: 12px; color: var(--cmp-deep-primary);">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="cmp-spinner" style="width: 14px; height: 14px; border: 2px solid var(--cmp-border); border-top-color: var(--cmp-primary); border-radius: 50%; animation: cmpSpin 0.7s linear infinite;"></div>
              <span id="cmpThinkingText">Grounding inquiry against Workday and DLI benchmarks...</span>
            </div>
          </div>

          <!-- Input Bar -->
          <div style="padding: 14px 18px; background: #FFFFFF; border-top: 1px solid var(--cmp-border);">
            <form id="cmpCopilotForm" style="display: flex; gap: 8px; align-items: center;">
              <input
                type="text"
                id="cmpCopilotInputField"
                placeholder="Ask about available company evidence, workforce records, or source limitations..."
                style="flex: 1; height: 40px; padding: 0 14px; border-radius: 8px; border: 1px solid var(--cmp-border); font-size: 13px; outline: none;"
                autocomplete="off"
                ${isCopilotAnalyzing ? 'disabled' : ''}
              />
              <button type="submit" class="cmp-btn-primary" style="height: 40px; padding: 0 16px;" ${isCopilotAnalyzing ? 'disabled' : ''}>
                <i data-lucide="send"></i>
                <span>Ask</span>
              </button>
            </form>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderCopilotMessage(msg) {
  if (msg.sender === 'user') {
    return `
      <div style="display: flex; justify-content: flex-end;">
        <div style="max-width: 75%; background: var(--cmp-primary); color: #FFFFFF; padding: 10px 14px; border-radius: 12px; font-size: 13.5px; font-weight: 500;">
          ${esc(msg.text)}
        </div>
      </div>
    `;
  }

  // Structured response (Section 21: ANSWER, WHY, EVIDENCE, AFFECTED TEAMS, RECOMMENDED ACTION)
  const s = msg.structured;
  const statusCfg = msg.status ? statusBadgeMap[msg.status] : null;

  return `
    <div style="display: flex; gap: 10px; align-items: flex-start;">
      <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--cmp-light-primary); color: var(--cmp-deep-primary); display: flex; align-items: center; justify-content: center; font-size: 13px; flex-shrink: 0; border: 1px solid var(--cmp-border-accent);">
        <i data-lucide="sparkles" style="width: 16px; height: 16px;"></i>
      </div>
      <div style="max-width: 85%; background: var(--cmp-very-light); border: 1px solid var(--cmp-border); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 12px;">
        ${statusCfg ? `
          <div>
            <span style="display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:700; background:${statusCfg.bg}; color:${statusCfg.color}; padding:2px 8px; border-radius:6px;">
              <i data-lucide="${statusCfg.icon}" style="width:11px; height:11px;"></i>
              ${statusCfg.label}
            </span>
          </div>
        ` : ''}

        <!-- Answer -->
        <div style="font-size: 13.5px; color: var(--cmp-text-primary); line-height: 1.55;">
          ${formatMarkdown(s.answer)}
        </div>
        ${s.metric_results?.length ? renderIntelligenceEvidencePanel({
          status: msg.status,
          metric_results: s.metric_results,
          limitations: s.limitations
        }, { title: 'Structured answer metrics' }) : ''}

        ${renderAnswerEvidencePanel(s.facts, s.evidence)}

        ${s.why ? `
          <div style="background: #FFFFFF; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--cmp-border-subtle); font-size: 12.5px;">
            <strong style="color: var(--cmp-text-muted); text-transform: uppercase; font-size: 10.5px; display: block; margin-bottom: 2px;">Why It Matters:</strong>
            <span style="color: var(--cmp-text-secondary);">${esc(s.why)}</span>
          </div>
        ` : ''}

        ${s.affectedTeams && s.affectedTeams.length ? `
          <div style="font-size: 12px; color: var(--cmp-text-muted);">
            <strong style="text-transform: uppercase; font-size: 10.5px; color: var(--cmp-text-muted);">Affected Teams:</strong>
            <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px;">
              ${s.affectedTeams.map(t => `<span class="cmp-badge cmp-badge--neutral" style="font-size: 11px;">${esc(t)}</span>`).join('')}
            </div>
          </div>
        ` : ''}

        ${s.action ? `
          <div style="background: var(--cmp-light-primary); border-left: 3px solid var(--cmp-primary); padding: 8px 12px; border-radius: 0 8px 8px 0; font-size: 12.5px; color: var(--cmp-deep-primary);">
            <strong>Recommended Action:</strong> ${esc(s.action)}
          </div>
        ` : ''}

        ${s.limitations && s.limitations.length ? `
          <div style="padding: 6px 10px; background:#FEF3C7; border: 1px solid #FCD34D; border-radius:6px; font-size:11px; color:#92400E;">
            <strong>Limitations:</strong> ${s.limitations.map(l => esc(l)).join('; ')}
          </div>
        ` : ''}

        ${s.followUps && s.followUps.length ? `
          <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;">
            ${s.followUps.map(fu => `
              <button type="button" class="cmp-btn-secondary cmp-copilot-chip-btn" data-query="${esc(fu)}" style="height:26px; padding:0 8px; font-size:11px;">
                <i data-lucide="corner-down-right" style="width:10px; height:10px;"></i>
                <span>${esc(fu)}</span>
              </button>
            `).join('')}
          </div>
        ` : ''}

        ${msg.retryQuery && msg.status === 'failed' ? `
          <button type="button" class="cmp-btn-secondary cmp-copilot-retry-btn" data-query="${esc(msg.retryQuery)}" style="align-self:flex-start;">
            Retry this question
          </button>
        ` : ''}
      </div>
    </div>
  `;
}

export function bindCompanyAIAssistantEvents(rerender) {
  // Query chips
  document.querySelectorAll('.cmp-copilot-chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      handleCopilotInquiry(q, rerender);
    });
  });
  document.querySelectorAll('.cmp-copilot-retry-btn').forEach(btn => {
    btn.addEventListener('click', () => handleCopilotInquiry(btn.dataset.query, rerender, false));
  });

  // Form submit
  document.querySelector('#cmpCopilotForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const input = document.querySelector('#cmpCopilotInputField');
    const q = input?.value.trim();
    if (q && !isCopilotAnalyzing) {
      handleCopilotInquiry(q, rerender);
      input.value = '';
    }
  });

  // Clear chat
  document.querySelector('#cmpClearChatBtn')?.addEventListener('click', () => {
    inquiryGeneration += 1;
    isCopilotAnalyzing = false;
    if (activeConversationId) {
      queryCoreIntelligenceAnswer({
        message: 'clear context',
        portalType: 'company',
        companyId: getAuthenticatedCompanyId(),
        conversationId: activeConversationId,
        clearContext: true
      }).catch(() => {});
    }
    activeConversationId = null;
    copilotMessages = [
      {
        sender: 'assistant',
        structured: {
          answer: 'Session reset. Ask a question to check what evidence is available to your authenticated organization.',
          why: 'The company dashboard shown around this conversation is simulated demo data.',
          evidence: [],
          affectedTeams: [],
          action: 'Select a question or ask anything.'
        }
      }
    ];
    rerender();
  });

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function getAuthenticatedCompanyId() {
  const user = getCurrentUser();
  return user?.companyId || user?.company_id || null;
}

async function handleCopilotInquiry(query, rerender, appendUser = true) {
  if (isCopilotAnalyzing || !query) return;
  isCopilotAnalyzing = true;
  const generation = ++inquiryGeneration;
  if (appendUser) copilotMessages.push({ sender: 'user', text: query });
  rerender();

  const indicator = document.querySelector('#cmpCopilotThinkingIndicator');
  if (indicator) indicator.style.display = 'block';

  try {
    const res = await queryCoreIntelligenceAnswer({
      message: query,
      portalType: 'company',
      companyId: getAuthenticatedCompanyId(),
      conversationId: activeConversationId || null
    });

    if (generation !== inquiryGeneration) return;
    if (res.conversation_id) {
      activeConversationId = res.conversation_id;
    }

    if (indicator) indicator.style.display = 'none';

    copilotMessages.push({
      sender: 'assistant',
      status: res.status || res.execution_status,
      conversation_id: res.conversation_id || activeConversationId,
      reasonCodes: res.reason_codes,
      structured: {
        answer: res.answer,
        why: res.limitations.length ? res.limitations.join('; ') : '',
        facts: res.facts,
        metric_results: res.metric_results,
        evidence: res.evidence,
        limitations: res.limitations,
        affectedTeams: [],
        action: res.execution_status === 'requires_clarification' ? 'Provide more specific parameters' : '',
        followUps: res.follow_up_questions
      }
    });
  } catch (err) {
    if (generation !== inquiryGeneration) return;
    if (indicator) indicator.style.display = 'none';

    let errText = err.message || 'Strategic copilot encountered an error.';
    let errWhy = 'Connection or permission restriction.';
    let errAction = 'Verify connectivity and corporate credentials.';
    let errStatus = 'failed';
    let reasonCodes = ['SERVICE_ERROR'];

    if (err.name === 'CoreIntelligenceAuthError' || err.status === 401 || err.status === 403) {
      errText = 'Access Restricted: Enterprise workforce intelligence requires authenticated company organization credentials.';
      errWhy = 'Strict multi-tenant security prevents unauthorized access to internal workforce structures.';
      errAction = 'Sign in with an active enterprise corporate account.';
      errStatus = 'blocked';
      reasonCodes = ['UNAUTHORIZED_PORTAL_ACCESS'];
    } else if (err.name === 'CoreIntelligenceNetworkError') {
      errText = 'The intelligence service is temporarily unavailable. Please try again shortly.';
      errWhy = 'Network connection to the analytical service failed.';
      errAction = 'Verify backend is running and retry.';
      errStatus = 'failed';
      reasonCodes = ['NETWORK_ERROR'];
    }

    copilotMessages.push({
      sender: 'assistant',
      status: errStatus,
      reasonCodes: reasonCodes,
      structured: {
        answer: errText,
        why: errWhy,
        facts: [],
        evidence: [],
        limitations: [errText],
        affectedTeams: [],
        action: errAction,
        followUps: []
      },
      retryQuery: errStatus === 'failed' ? query : null
    });
  } finally {
    if (generation === inquiryGeneration) isCopilotAnalyzing = false;
  }

  if (generation === inquiryGeneration) rerender();
}
