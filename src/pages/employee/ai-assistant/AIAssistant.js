// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE AI ASSISTANT
// Workforce intelligence assistant grounded in role, skills, and growth context
// Adapts dynamically to Company Employee vs Independent Employee
// ============================================================================

import {
  getEmployeeProfile,
  isCompanyEmployee,
  employeeSkillsData,
  roleEvolutionData,
  internalRolesData
} from '../../../data/employee/employee-data.js';

import { getCurrentUser } from '../../../auth/auth-state.js';
import { queryCoreIntelligenceAnswer } from '../../../api/core-intelligence-client.js';
import { renderIntelligenceEvidencePanel } from '../../../components/common/IntelligenceEvidencePanel.js';
import { renderAnswerEvidencePanel } from '../../../components/common/IntelligenceComponents.js';

let activeConversationId = null;

let chatHistory = [
  {
    sender: 'assistant',
    text: `Good morning. I am your **Workforce Intelligence Assistant**. I evaluate your role evolution, skill health, career readiness, and learning pathways against verified empirical platform intelligence. How can I assist you today?`
  }
];

let isAnalyzing = false;
let currentAnalysisStep = 0;
let analysisGeneration = 0;

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function formatMarkdown(content) {
  if (!content) return '';
  return String(content)
    .replace(/^### (.*$)/gim, '<h4 style="margin:8px 0 4px; font-size:13.5px; color:var(--emp-primary); font-weight:800;">$1</h4>')
    .replace(/^## (.*$)/gim, '<h3 style="margin:10px 0 4px; font-size:14.5px; color:var(--emp-primary); font-weight:800;">$1</h3>')
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

export function renderEmployeeAIAssistant() {
  const p = getEmployeeProfile();
  const isCompany = isCompanyEmployee();

  const samplePrompts = isCompany ? [
    "What changed in my company?",
    "Which skills do I need for Senior AI Platform Engineer?",
    "Why is CUDA recommended for me?",
    "Which internal roles match my current skills?",
    "How does Blackwell technology affect my role?"
  ] : [
    "What are the top market trends in AI infrastructure?",
    "What capabilities are required for Staff ML Infra Engineer?",
    "Why is CUDA recommended for me?",
    "Which industry opportunities match my profile?",
    "How can I turn my verified skills into reputation?"
  ];

  return `
    <div class="employee-page">
      <!-- Header -->
      <section class="emp-hero">
        <div class="emp-hero-content">
          <span class="emp-eyebrow">
            <i data-lucide="sparkles"></i>
            WORKFORCE INTELLIGENCE COPILOT
          </span>
          <h1 class="emp-hero-title">Employee AI Assistant</h1>
          <p class="emp-hero-desc">
            Grounded in your role (${esc(p.role)}), verified skill health, target career goals (${esc(p.targetRole)}), and community contributions.
          </p>
        </div>
        <div class="emp-hero-actions">
          <button type="button" class="emp-btn-ghost" id="empClearChatBtn" style="height: auto; padding: 6px 12px; font-size: 12px; border-radius: 8px; border: 1px solid var(--emp-border); display: inline-flex; align-items: center; gap: 6px;">
            <i data-lucide="rotate-ccw" style="width: 13px; height: 13px;"></i>
            <span>Clear Session</span>
          </button>
          <div class="emp-stat-pill" style="background: var(--emp-light); border: 1px solid rgba(39, 53, 245, 0.2);">
            <strong style="color: var(--emp-primary);">Context Active</strong>
            <small style="color: var(--emp-text-muted);">${isCompany ? 'NVIDIA APAC L4' : 'Independent ML Lead'}</small>
          </div>
        </div>
      </section>

      <!-- Main Chat Area & Suggested Prompts -->
      <div style="display: grid; grid-template-columns: 1fr 340px; gap: 20px; align-items: start;">
        
        <!-- Chat Surface -->
        <div class="emp-card" style="display: flex; flex-direction: column; height: 580px; padding: 20px;">
          <!-- Messages Scroll View -->
          <div id="empChatMessages" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; padding-right: 8px;">
            ${chatHistory.map(msg => {
              const statusCfg = msg.status ? statusBadgeMap[msg.status] : null;
              return `
              <div style="display: flex; gap: 12px; align-items: flex-start; ${msg.sender === 'user' ? 'flex-direction: row-reverse;' : ''}">
                <div style="width: 34px; height: 34px; border-radius: 10px; background: ${msg.sender === 'assistant' ? 'var(--emp-primary)' : 'var(--emp-deep-primary)'}; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; flex-shrink: 0;">
                  ${msg.sender === 'assistant' ? '<i data-lucide="sparkles" style="width: 16px; height: 16px;"></i>' : esc(p.initials)}
                </div>
                <div style="max-width: 82%; background: ${msg.sender === 'assistant' ? '#FFFFFF' : 'var(--emp-light)'}; border: 1px solid var(--emp-border); padding: 14px 18px; border-radius: 14px; font-size: 13.5px; line-height: 1.55; color: var(--emp-text-primary); box-shadow: var(--emp-shadow-sm);">
                  ${statusCfg ? `
                    <div style="margin-bottom:8px;">
                      <span style="display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:700; background:${statusCfg.bg}; color:${statusCfg.color}; padding:2px 8px; border-radius:6px;">
                        <i data-lucide="${statusCfg.icon}" style="width:11px; height:11px;"></i>
                        ${statusCfg.label}
                      </span>
                    </div>
                  ` : ''}
                  <div>${formatMarkdown(msg.text)}</div>
                  ${msg.metric_results?.length ? renderIntelligenceEvidencePanel({
                    status: msg.status,
                    metric_results: msg.metric_results,
                    limitations: msg.limitations
                  }, { title: 'Structured answer metrics' }) : ''}

                  ${renderAnswerEvidencePanel(msg.facts, msg.evidence)}

                  ${msg.limitations && msg.limitations.length ? `
                    <div style="margin-top:8px; padding:6px 10px; background:#FEF3C7; border:1px solid #FCD34D; border-radius:6px; font-size:11px; color:#92400E;">
                      <strong>Limitations:</strong> ${msg.limitations.map(l => esc(l)).join('; ')}
                    </div>
                  ` : ''}

                  ${msg.followUps && msg.followUps.length ? `
                    <div style="margin-top:10px; display:flex; gap:6px; flex-wrap:wrap;">
                      ${msg.followUps.map(fu => `
                        <button type="button" class="emp-btn-ghost" data-quick-prompt="${esc(fu)}" style="height:auto; padding:4px 8px; font-size:11px; border-radius:6px;">
                          <i data-lucide="corner-down-right" style="width:10px; height:10px;"></i>
                          <span>${esc(fu)}</span>
                        </button>
                      `).join('')}
                    </div>
                  ` : ''}
                  ${msg.retryQuery && msg.status === 'failed' ? `
                    <button type="button" class="emp-btn-ghost emp-chat-retry-btn" data-retry-question="${esc(msg.retryQuery)}" style="margin-top:8px;">
                      Retry this question
                    </button>
                  ` : ''}
                </div>
              </div>
            `;
            }).join('')}

            ${isAnalyzing ? `
              <div style="display: flex; gap: 12px; align-items: flex-start;">
                <div style="width: 34px; height: 34px; border-radius: 10px; background: var(--emp-primary); color: #FFF; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; flex-shrink: 0;">
                  <i data-lucide="sparkles" style="width: 16px; height: 16px;"></i>
                </div>
                <div style="flex: 1; max-width: 82%; background: #FAFAFF; border: 1px solid var(--emp-border); padding: 14px 18px; border-radius: 14px;">
                  <div style="font-weight: 750; color: var(--emp-primary); font-size: 13px; margin-bottom: 8px;">
                    Synthesizing workforce intelligence...
                  </div>
                  <div style="display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--emp-text-secondary);">
                    <div>Step ${currentAnalysisStep}/4: Inspecting verified skill profile and role benchmarks</div>
                  </div>
                </div>
              </div>
            ` : ''}
          </div>

          <!-- Input Bar -->
          <form id="empChatForm" style="display: flex; gap: 10px; padding-top: 14px; border-top: 1px solid var(--emp-border-subtle); margin-top: 8px;">
            <input type="text" id="empChatInput" placeholder="Ask about role shifts, CUDA requirements, internal mobility, or mentoring..." style="flex: 1; height: 42px; border-radius: 10px; border: 1px solid var(--emp-border); padding: 0 16px; font-size: 13.5px; background: #FFF; color: var(--emp-text-primary);" ${isAnalyzing ? 'disabled' : ''} />
            <button type="submit" class="emp-btn-primary" style="height: 42px; padding: 0 18px;" ${isAnalyzing ? 'disabled' : ''}>
              <i data-lucide="send"></i>
              <span>Ask</span>
            </button>
          </form>
        </div>

        <!-- Right Side: Grounded Context & Sample Prompts -->
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <!-- Active Context Card -->
          <div class="emp-card" style="padding: 20px;">
            <h4 style="font-size: 11.5px; font-weight: 800; color: var(--emp-text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px;">
              Active Profile Context
            </h4>
            <div style="display: flex; flex-direction: column; gap: 8px; font-size: 12.5px;">
              <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--emp-text-secondary);">Employee:</span>
                <strong style="color: var(--emp-text-primary);">${esc(p.name)}</strong>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--emp-text-secondary);">Role:</span>
                <strong style="color: var(--emp-text-primary);">${esc(p.role)}</strong>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--emp-text-secondary);">Target:</span>
                <strong style="color: var(--emp-primary);">${esc(p.targetRole)}</strong>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--emp-text-secondary);">Top Gap:</span>
                <strong style="color: var(--emp-attention);">CUDA Kernel Tuning</strong>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--emp-text-secondary);">Reputation:</span>
                <strong style="color: var(--emp-success);">${p.reputationPoints.toLocaleString()} Points</strong>
              </div>
            </div>
          </div>

          <!-- Suggested Questions -->
          <div class="emp-card" style="padding: 20px;">
            <h4 style="font-size: 11.5px; font-weight: 800; color: var(--emp-text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px;">
              Suggested Questions
            </h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${samplePrompts.map(prompt => `
                <button type="button" class="emp-btn-ghost" data-quick-prompt="${esc(prompt)}" style="justify-content: flex-start; text-align: left; height: auto; padding: 9px 12px; font-size: 12px; line-height: 1.35; border-radius: 8px;">
                  <i data-lucide="help-circle" style="width: 14px; height: 14px; flex-shrink: 0; color: var(--emp-primary);"></i>
                  <span>${esc(prompt)}</span>
                </button>
              `).join('')}
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function runAnalysisAndRespond(query, rerenderFn) {
  if (isAnalyzing || !query) return;
  isAnalyzing = true;
  const generation = ++analysisGeneration;
  currentAnalysisStep = 1;
  rerenderFn();

  const user = getCurrentUser();
  const targetRole = user?.target_role
    || user?.targetRole
    || user?.target_roles?.[0]
    || user?.targetRoles?.[0]
    || null;
  const profileSkills = user?.skills || user?.selected_skills;
  const selectedSkills = Array.isArray(profileSkills) ? profileSkills.filter(Boolean) : [];
  const location = typeof user?.location === 'string'
    ? user.location
    : user?.location?.city || user?.location?.region || null;

  try {
    currentAnalysisStep = 2;
    rerenderFn();

    const res = await queryCoreIntelligenceAnswer({
      message: query,
      portalType: 'employee',
      targetRole,
      selectedSkills,
      location,
      conversationId: activeConversationId || null
    });

    if (generation !== analysisGeneration) return;
    if (res.conversation_id) {
      activeConversationId = res.conversation_id;
    }

    isAnalyzing = false;
    currentAnalysisStep = 0;
    chatHistory.push({
      sender: 'assistant',
      status: res.status || res.execution_status,
      conversation_id: res.conversation_id || activeConversationId,
      text: res.answer,
      facts: res.facts,
      metric_results: res.metric_results,
      evidence: res.evidence,
      limitations: res.limitations,
      reasonCodes: res.reason_codes,
      followUps: res.follow_up_questions
    });
  } catch (err) {
    if (generation !== analysisGeneration) return;
    console.warn('Employee AI query failed:', err);
    isAnalyzing = false;
    currentAnalysisStep = 0;
    let errMsg = err.message || 'Error communicating with intelligence engine.';
    let errStatus = 'failed';
    let reasonCodes = ['SERVICE_ERROR'];

    if (err.name === 'CoreIntelligenceAuthError' || err.status === 401 || err.status === 403) {
      errMsg = 'Authentication Required: Please sign in with your enterprise credentials to query employee workforce intelligence.';
      errStatus = 'blocked';
      reasonCodes = ['UNAUTHORIZED_PORTAL_ACCESS'];
    } else if (err.name === 'CoreIntelligenceNetworkError') {
      errMsg = 'The intelligence service is temporarily unavailable. Please try again shortly.';
      errStatus = 'failed';
      reasonCodes = ['NETWORK_ERROR'];
    }

    chatHistory.push({
      sender: 'assistant',
      status: errStatus,
      text: errMsg,
      facts: [],
      evidence: [],
      limitations: [errMsg],
      reasonCodes: reasonCodes,
      followUps: [],
      retryQuery: errStatus === 'failed' ? query : null
    });
  }

  if (generation !== analysisGeneration) return;
  rerenderFn();
  const box = document.querySelector('#empChatMessages');
  if (box) {
    box.scrollTop = box.scrollHeight;
  }
}

export function bindEmployeeAIAssistantEvents(rerenderFn) {
  const form = document.querySelector('#empChatForm');
  const input = document.querySelector('#empChatInput');
  const clearBtn = document.querySelector('#empClearChatBtn');

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      analysisGeneration += 1;
      isAnalyzing = false;
      currentAnalysisStep = 0;
      if (activeConversationId) {
        queryCoreIntelligenceAnswer({
          message: 'clear context',
          portalType: 'employee',
          conversationId: activeConversationId,
          clearContext: true
        }).catch(() => {});
      }
      activeConversationId = null;
      chatHistory = [
        {
          sender: 'assistant',
          text: 'Session reset. Workforce Intelligence Copilot ready. How can I assist your career and skill growth today?'
        }
      ];
      rerenderFn();
    });
  }

  const box = document.querySelector('#empChatMessages');
  if (box) {
    box.scrollTop = box.scrollHeight;
  }

  if (form && input) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (isAnalyzing) return;
      const val = input.value.trim();
      if (!val) return;

      chatHistory.push({ sender: 'user', text: val });
      input.value = '';
      runAnalysisAndRespond(val, rerenderFn);
    });
  }

  document.querySelectorAll('[data-quick-prompt]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (isAnalyzing) return;
      const prompt = btn.dataset.quickPrompt;
      chatHistory.push({ sender: 'user', text: prompt });
      runAnalysisAndRespond(prompt, rerenderFn);
    });
  });
  document.querySelectorAll('.emp-chat-retry-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      runAnalysisAndRespond(btn.dataset.retryQuestion, rerenderFn);
    });
  });
}
