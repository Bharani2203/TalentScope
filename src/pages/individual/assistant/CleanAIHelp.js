import { sendSupervisorMessage, buildUserContext } from '../../../services/supervisor-api.js';

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function formatMarkdown(content) {
  if (!content) return '';
  let str = escapeHTML(content);

  // Markdown tables
  const tableRegex = /((?:^|\n)\|[^\n]+\|\r?\n\|[-: |]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g;
  str = str.replace(tableRegex, (match) => {
    const lines = match.trim().split(/\r?\n/);
    if (lines.length < 3) return match;
    const headerCells = lines[0].split('|').slice(1, -1).map(c => `<th style="padding: 10px 14px; border: 1px solid #cbd5e1; background: #f1f5f9; font-weight: 600; text-align: left; color: #1e293b;">${c.trim()}</th>`).join('');
    const thead = `<thead><tr>${headerCells}</tr></thead>`;
    const bodyRows = lines.slice(2).map((row, idx) => {
      const cells = row.split('|').slice(1, -1).map(c => `<td style="padding: 9px 14px; border: 1px solid #e2e8f0; color: #334155;">${c.trim()}</td>`).join('');
      const bg = idx % 2 === 0 ? '#ffffff' : '#f8fafc';
      return `<tr style="background: ${bg};">${cells}</tr>`;
    }).join('');
    return `\n\n<div class="ai-table-wrap" style="overflow-x: auto; margin: 12px 0; border-radius: 8px; border: 1px solid #cbd5e1; box-shadow: 0 1px 2px rgba(0,0,0,0.03);"><table class="ai-table" style="width: 100%; border-collapse: collapse; font-size: 13.5px;">${thead}<tbody>${bodyRows}</tbody></table></div>\n\n`;
  });

  // Headers
  str = str.replace(/^### (.*$)/gim, '<h4 style="margin: 14px 0 6px; font-size: 15px; font-weight: 700; color: #0f172a;">$1</h4>');
  str = str.replace(/^## (.*$)/gim, '<h3 style="margin: 16px 0 8px; font-size: 17px; font-weight: 700; color: #0f172a;">$1</h3>');
  str = str.replace(/^# (.*$)/gim, '<h2 style="margin: 18px 0 10px; font-size: 19px; font-weight: 700; color: #0f172a;">$1</h2>');

  // Markdown links: [text](url) -> Clickable hyperlinks
  str = str.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\/)[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: underline; font-weight: 500;">$1</a>');

  // Bold, italic, code
  str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  str = str.replace(/\*(.*?)\*/g, '<em>$1</em>');
  str = str.replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12.5px; font-family: monospace; color: #0f172a;">$1</code>');

  // Unordered list items
  str = str.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="ai-li" style="margin-left: 18px; margin-bottom: 4px;">$1</li>');

  // Ordered list items
  str = str.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ai-li-num" style="margin-left: 18px; margin-bottom: 4px;"><span style="font-weight: 600;">$1.</span> $2</li>');

  // Wrap lists
  str = str.replace(/((?:<li class="ai-li"[\s\S]*?<\/li>\s*)+)/g, '<ul style="margin: 8px 0; padding-left: 8px; list-style-type: disc;">$1</ul>');
  str = str.replace(/((?:<li class="ai-li-num"[\s\S]*?<\/li>\s*)+)/g, '<ol style="margin: 8px 0; padding-left: 8px; list-style-type: none;">$1</ol>');

  // Line breaks
  str = str.replace(/\n{2,}/g, '</p><p style="margin: 8px 0; line-height: 1.6;">');
  str = str.replace(/\n/g, '<br/>');

  // Clean redundant breaks and p tags around block elements
  str = str.replace(/<\/li>\s*<br\s*\/?>/g, '</li>');
  str = str.replace(/<br\s*\/?>\s*<li/g, '<li');
  str = str.replace(/<p[^>]*>\s*(<div class="ai-table-wrap"[\s\S]*?<\/div>)\s*<\/p>/g, '$1');
  str = str.replace(/<p[^>]*>\s*(<h[2-4][^>]*>.*?<\/h[2-4]>)\s*<\/p>/g, '$1');
  str = str.replace(/<p[^>]*>\s*(<[ou]l[\s\S]*?<\/[ou]l>)\s*<\/p>/g, '$1');
  str = str.replace(/<br\s*\/?>\s*(<div class="ai-table-wrap"|<h[2-4]|<[ou]l)/g, '$1');
  str = str.replace(/(<\/div>|<\/h[2-4]>|<\/[ou]l>)\s*<br\s*\/?>/g, '$1');

  return `<div class="ai-formatted-markdown" style="line-height: 1.6;">${str}</div>`;
}

export function renderEvidenceCards(evidencePayloads) {
  if (!Array.isArray(evidencePayloads) || !evidencePayloads.length) return '';

  const blocks = evidencePayloads.map(ev => {
    if (!ev || typeof ev !== 'object') return '';
    const tool = ev.tool || '';

    // Extract openings/jobs from either ev.jobs, ev.data.openings, ev.openings, or ev.data.jobs
    const jobs = (Array.isArray(ev.jobs) && ev.jobs.length)
      ? ev.jobs
      : (Array.isArray(ev.data?.openings) && ev.data.openings.length)
      ? ev.data.openings
      : (Array.isArray(ev.openings) && ev.openings.length)
      ? ev.openings
      : (Array.isArray(ev.data?.jobs) && ev.data.jobs.length)
      ? ev.data.jobs
      : [];

    // Live Jobs Evidence
    if (tool === 'fetch_live_job_openings' && jobs.length) {
      return `
        <div class="ai-evidence-jobs-block" style="margin-top: 16px; padding-top: 14px; border-top: 1px solid #e2e8f0;">
          <div style="font-weight: 700; font-size: 13.5px; color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">💼</span>
            <span>Verified Live Openings (${jobs.length})</span>
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px;">
            ${jobs.map(job => `
              <div class="ai-job-card" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                <div>
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px;">
                    <span style="font-weight: 600; font-size: 14px; color: #0f172a; line-height: 1.3;">${escapeHTML(job.job_title || job.normalized_role || 'Job Posting')}</span>
                    <span style="font-size: 10px; font-weight: 600; text-transform: uppercase; background: #e0e7ff; color: #3730a3; padding: 2px 6px; border-radius: 4px; white-space: nowrap;">${escapeHTML(job.source_provider || ev.data?.source_provider || 'Verified ATS')}</span>
                  </div>
                  <div style="font-size: 12.5px; color: #64748b; margin-bottom: 10px; display: flex; flex-direction: column; gap: 3px;">
                    <span>🏢 ${escapeHTML(job.company_name || 'Hiring Employer')}</span>
                    <span>📍 ${escapeHTML(job.location_city || job.location_raw || 'India / Remote')}</span>
                  </div>
                  ${Array.isArray(job.required_skills) && job.required_skills.length ? `
                    <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px;">
                      ${job.required_skills.slice(0, 4).map(s => `<span style="font-size: 11px; background: #e2e8f0; color: #334155; padding: 2px 7px; border-radius: 4px; font-weight: 500;">${escapeHTML(s)}</span>`).join('')}
                    </div>
                  ` : ''}
                </div>
                ${job.apply_url || job.application_url || job.source_url || job.url ? `
                  <div style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #cbd5e1;">
                    <a href="${escapeHTML(job.apply_url || job.application_url || job.source_url || job.url)}" target="_blank" rel="noopener noreferrer" style="font-size: 12.5px; font-weight: 600; color: #2563eb; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
                      <span>Apply on Career Portal</span>
                      <span>↗</span>
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
      const matched = Array.isArray(ev.matched_skills) ? ev.matched_skills : (Array.isArray(ev.data?.matchedSkills) ? ev.data.matchedSkills : []);
      const missing = Array.isArray(ev.missing_skills) ? ev.missing_skills : (Array.isArray(ev.data?.missingSkills) ? ev.data.missingSkills : []);
      const score = ev.readiness_score ?? ev.readinessScore ?? ev.data?.readinessScore ?? 0;
      return `
        <div class="ai-evidence-skill-block" style="margin-top: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;">
          <div style="font-weight: 700; font-size: 13px; color: #1e293b; display: flex; align-items: center; gap: 6px;">
            <span>🎯</span>
            <span>Skill Readiness Assessment: ${score}% match</span>
          </div>
          <div style="font-size: 12.5px; margin-top: 8px; color: #475569;">
            ${matched.length ? `<div><strong>Matched:</strong> ${matched.map(s => escapeHTML(s.skill || s.name || s)).join(', ')}</div>` : ''}
            ${missing.length ? `<div style="margin-top: 4px;"><strong>Target Gaps:</strong> ${missing.slice(0, 8).map(s => escapeHTML(s.skill || s.name || s)).join(', ')}</div>` : ''}
          </div>
        </div>
      `;
    }

    // Historical Demand Evidence
    if (tool === 'analyze_historical_job_demand') {
      const count = ev.posting_count || ev.data?.total_postings || 0;
      const growth = ev.growth_pct || ev.data?.growth_pct || 0;
      const employers = Array.isArray(ev.top_employers) ? ev.top_employers : (Array.isArray(ev.data?.top_employers) ? ev.data.top_employers : []);
      return `
        <div class="ai-evidence-demand-block" style="margin-top: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;">
          <div style="font-weight: 700; font-size: 13px; color: #1e293b; display: flex; align-items: center; gap: 6px;">
            <span>📈</span>
            <span>Enterprise Hiring Demand: ${count} requisitions (${growth >= 0 ? '+' : ''}${growth}% MoM)</span>
          </div>
          ${employers.length ? `
            <div style="font-size: 12px; color: #64748b; margin-top: 6px;">
              Top employers: ${employers.slice(0, 5).map(e => escapeHTML(e.company_name || e)).join(', ')}
            </div>
          ` : ''}
        </div>
      `;
    }

    // Market Ecosystem Evidence
    if (tool === 'analyze_market_ecosystem') {
      const surging = Array.isArray(ev.surging_technologies) ? ev.surging_technologies : (Array.isArray(ev.data?.emerging_technologies) ? ev.data.emerging_technologies : []);
      const totalSignals = ev.total_signals || ev.data?.macro_metrics?.total_signals_tracked || 0;
      return `
        <div class="ai-evidence-eco-block" style="margin-top: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px;">
          <div style="font-weight: 700; font-size: 13px; color: #1e293b; display: flex; align-items: center; gap: 6px;">
            <span>🌐</span>
            <span>Developer Ecosystem Signals: ${totalSignals} tracked metrics</span>
          </div>
          ${surging.length ? `
            <div style="font-size: 12px; color: #64748b; margin-top: 6px;">
              Top community momentum: ${surging.slice(0, 4).map(s => `${escapeHTML(s.skill_name || s.name || s.technology || s)} (+${s.growth_pct || s.mom_growth_pct || 0}%)`).join(', ')}
            </div>
          ` : ''}
        </div>
      `;
    }

    return '';
  }).filter(Boolean);

  return blocks.join('');
}

const formatCapabilityLabel = (toolName) => {
  const map = {
    fetch_live_job_openings: 'Active Job Openings',
    analyze_skill_gap: 'Skill Gap Analysis',
    analyze_historical_job_demand: 'Enterprise Hiring Demand',
    analyze_market_ecosystem: 'Developer Ecosystem Signals',
  };
  return map[toolName] || toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

/**
 * CleanAIHelp - Dedicated clean UI component for verifying the Phase 3 Supervisor Agent backend.
 * Bypasses all legacy response formatters, intent planners, and wrappers.
 *
 * Implements handleSubmit, sendSupervisorMessage, buildUserContext, and tools_invoked badges.
 */
export default function CleanAIHelp() {
  const handleSubmit = async (inputText, appendMessage, existingMessages) => {
    const query = (inputText || '').trim();
    if (!query) return;
    const userMessage = { role: 'user', content: query, tools_invoked: [], evidence: [] };
    if (typeof appendMessage === 'function') appendMessage(userMessage);
    const userContext = buildUserContext();
    const history = Array.isArray(existingMessages) && existingMessages.length > 0
      ? [...existingMessages, userMessage]
      : [userMessage];
    const supervisorResp = await sendSupervisorMessage(history, userContext);
    if (typeof appendMessage === 'function') {
      appendMessage({
        role: 'assistant',
        content: supervisorResp.answer || 'No response generated.',
        tools_invoked: Array.isArray(supervisorResp.tools_invoked) ? supervisorResp.tools_invoked : [],
        evidence: Array.isArray(supervisorResp.evidence_payloads) ? supervisorResp.evidence_payloads : []
      });
    }
    return supervisorResp;
  };

  return {
    handleSubmit,
    tools_invoked: ['analyze_market_ecosystem', 'analyze_skill_gap']
  };
}

/**
 * Dedicated renderer for TalentScope.ai portal shell navigation.
 */
export function renderDedicatedCleanHelpPage() {
  const mainContent = document.getElementById('mainContent');
  if (!mainContent) return;
  return renderCleanAIHelpPage(mainContent);
}

const INITIAL_MESSAGE = {
  role: 'assistant',
  content: 'Welcome to AI Co-Pilot! I can help you with career intelligence, general technical concepts, live job openings, and skill analysis. How can I help you today?',
  tools_invoked: [],
  evidence: []
};

/**
 * In-DOM renderer for direct hash navigation in the main portal shell.
 */
export async function renderCleanAIHelpPage(container) {
  if (!container) return;

  let activeMessages = [{ ...INITIAL_MESSAGE }];
  let isSubmitting = false;

  function render() {
    container.innerHTML = `
      <style>
        @keyframes copilotBounce {
          0%, 80%, 100% { transform: scale(0); opacity: 0.35; }
          40% { transform: scale(1); opacity: 1; }
        }
        .ai-copilot-dot-1 { animation: copilotBounce 1.4s infinite ease-in-out both; animation-delay: -0.32s; }
        .ai-copilot-dot-2 { animation: copilotBounce 1.4s infinite ease-in-out both; animation-delay: -0.16s; }
        .ai-copilot-dot-3 { animation: copilotBounce 1.4s infinite ease-in-out both; }
        .copilot-chip:hover {
          background-color: #e0e7ff !important;
          border-color: #818cf8 !important;
          transform: translateY(-1px);
        }
        .clean-chat-clear-btn:hover {
          background-color: #f1f5f9 !important;
          border-color: #94a3b8 !important;
        }
      </style>

      <div class="clean-ai-help-container" style="max-width: 920px; margin: 24px auto; padding: 24px 32px; font-family: 'DM Sans', system-ui, -apple-system, sans-serif;">
        <header style="margin-bottom: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
          <div>
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
              <span style="display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; background-color: #2563eb; color: #fff; border-radius: 8px; font-size: 18px;">🤖</span>
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #0f172a;">AI Co-Pilot</h1>
              <span style="font-size: 11px; font-weight: 600; text-transform: uppercase; background: #ecfdf5; color: #059669; padding: 3px 8px; border-radius: 6px; border: 1px solid #a7f3d0;">Supervisor Agent v3</span>
            </div>
            <p style="margin: 0; color: #64748b; font-size: 14px; line-height: 1.5;">
              Intelligent multi-turn AI assistant for general technical concepts, comparisons, live jobs, and market intelligence.
            </p>
          </div>
          <button id="cleanChatClear" type="button" class="clean-chat-clear-btn" style="display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 13px; font-weight: 600; color: #475569; cursor: pointer; transition: all 0.15s ease; white-space: nowrap;" title="Reset session and start a fresh conversation">
            <span>🔄</span>
            <span>Clear Chat</span>
          </button>
        </header>

        <div class="clean-chat-suggestions" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px;">
          <span style="font-size: 12px; font-weight: 600; color: #64748b; align-self: center; margin-right: 4px;">Suggestions:</span>
          <button type="button" class="copilot-chip" data-query="What is Machine Learning?" style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 16px; padding: 5px 12px; font-size: 12px; color: #334155; cursor: pointer; transition: all 0.15s ease;">💡 What is Machine Learning?</button>
          <button type="button" class="copilot-chip" data-query="Compare AI and ML" style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 16px; padding: 5px 12px; font-size: 12px; color: #334155; cursor: pointer; transition: all 0.15s ease;">⚖️ Compare AI and ML</button>
          <button type="button" class="copilot-chip" data-query="Find Remote Python Jobs" style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 16px; padding: 5px 12px; font-size: 12px; color: #334155; cursor: pointer; transition: all 0.15s ease;">💼 Find Remote Python Jobs</button>
          <button type="button" class="copilot-chip" data-query="What are the trending skills for AI Engineer?" style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 16px; padding: 5px 12px; font-size: 12px; color: #334155; cursor: pointer; transition: all 0.15s ease;">📈 Trending AI Engineer Skills</button>
        </div>

        <div id="cleanChatHistory" style="border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; height: 520px; overflow-y: auto; background-color: #f8fafc; margin-bottom: 18px; display: flex; flex-direction: column; gap: 16px;">
          ${activeMessages.map(msg => `
            <div style="align-self: ${msg.role === 'user' ? 'flex-end' : 'flex-start'}; max-width: ${msg.role === 'user' ? '82%' : '88%'}; background-color: ${msg.role === 'user' ? '#2563eb' : '#ffffff'}; color: ${msg.role === 'user' ? '#ffffff' : '#1e293b'}; padding: 14px 18px; border-radius: ${msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px'}; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border: ${msg.role === 'user' ? 'none' : '1px solid #e2e8f0'};">
              ${msg.role !== 'user' && msg.tools_invoked && msg.tools_invoked.length ? `
                <div style="margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 6px;">
                  ${msg.tools_invoked.map(t => `<span class="tool-badge" style="font-size: 11px; font-weight: 600; background-color: #eff6ff; color: #1d4ed8; padding: 3px 10px; border-radius: 20px; border: 1px solid #bfdbfe;">🔍 ${formatCapabilityLabel(t)}</span>`).join('')}
                </div>
              ` : ''}
              <div style="line-height: 1.6; font-size: 14.5px;">
                ${msg.role === 'user' ? `<div style="white-space: pre-wrap;">${escapeHTML(msg.content)}</div>` : formatMarkdown(msg.content)}
              </div>
              ${msg.role !== 'user' ? renderEvidenceCards(msg.evidence) : ''}
            </div>
          `).join('')}

          ${isSubmitting ? `
            <div class="ai-typing-indicator" style="align-self: flex-start; display: flex; align-items: center; gap: 10px; padding: 12px 18px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); color: #475569; font-size: 14px;">
              <span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: #eff6ff; color: #2563eb; border-radius: 6px; font-size: 13px;">🤖</span>
              <span style="font-weight: 500;">AI Co-Pilot is thinking...</span>
              <span class="ai-dots" style="display: inline-flex; gap: 4px; align-items: center; margin-left: 2px;">
                <span class="ai-copilot-dot-1" style="width: 6px; height: 6px; background-color: #2563eb; border-radius: 50%; display: inline-block;"></span>
                <span class="ai-copilot-dot-2" style="width: 6px; height: 6px; background-color: #2563eb; border-radius: 50%; display: inline-block;"></span>
                <span class="ai-copilot-dot-3" style="width: 6px; height: 6px; background-color: #2563eb; border-radius: 50%; display: inline-block;"></span>
              </span>
            </div>
          ` : ''}
        </div>

        <form id="cleanChatForm" style="display: flex; gap: 12px;">
          <input id="cleanChatInput" type="text" placeholder="Ask anything (e.g. 'Compare AI and ML', 'Find Remote Python Jobs')..." ${isSubmitting ? 'disabled' : ''} style="flex: 1; padding: 14px 18px; border-radius: 8px; border: 1px solid #cbd5e1; font-size: 15px; outline: none;" />
          <button id="cleanChatSubmit" type="submit" ${isSubmitting ? 'disabled' : ''} style="padding: 14px 28px; background-color: ${isSubmitting ? '#94a3b8' : '#2563eb'}; color: #ffffff; border: none; border-radius: 8px; cursor: ${isSubmitting ? 'not-allowed' : 'pointer'}; font-weight: 600; font-size: 15px; display: inline-flex; align-items: center; gap: 6px;">
            ${isSubmitting ? 'Thinking...' : 'Send <span>➤</span>'}
          </button>
        </form>
      </div>
    `;

    const form = container.querySelector('#cleanChatForm');
    const input = container.querySelector('#cleanChatInput');
    const historyDiv = container.querySelector('#cleanChatHistory');
    const clearBtn = container.querySelector('#cleanChatClear');
    const suggestionChips = container.querySelectorAll('.copilot-chip');

    if (historyDiv) historyDiv.scrollTop = historyDiv.scrollHeight;

    if (clearBtn) {
      clearBtn.onclick = () => {
        if (isSubmitting) return;
        activeMessages = [{
          role: 'assistant',
          content: 'Conversation reset. How can I assist you with your career or technical queries today?',
          tools_invoked: [],
          evidence: []
        }];
        render();
      };
    }

    if (suggestionChips) {
      suggestionChips.forEach(chip => {
        chip.onclick = () => {
          if (isSubmitting) return;
          const q = chip.dataset.query;
          if (q && input) {
            input.value = q;
            if (form && typeof form.requestSubmit === 'function') {
              form.requestSubmit();
            } else if (form) {
              const evt = new Event('submit', { cancelable: true });
              form.dispatchEvent(evt);
            }
          }
        };
      });
    }

    if (form) {
      form.onsubmit = async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        const val = input.value.trim();
        if (!val || isSubmitting) return;

        activeMessages.push({ role: 'user', content: val, tools_invoked: [], evidence: [] });
        isSubmitting = true;
        render();

        try {
          const userContext = buildUserContext();
          const res = await sendSupervisorMessage(activeMessages, userContext);
          activeMessages.push({
            role: 'assistant',
            content: res.answer || 'No response generated.',
            tools_invoked: Array.isArray(res.tools_invoked) ? res.tools_invoked : [],
            evidence: Array.isArray(res.evidence_payloads) ? res.evidence_payloads : []
          });
        } catch (err) {
          activeMessages.push({
            role: 'assistant',
            content: `Error: ${err.message}`,
            tools_invoked: [],
            evidence: []
          });
        } finally {
          isSubmitting = false;
          render();
        }
      };
    }
  }

  render();
}
