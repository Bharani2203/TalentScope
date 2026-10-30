import { getTemporaryHelpResponse, AI_HELP_MAX_QUESTION_LENGTH } from './ai-help-service.js';
import { sendSupervisorMessage, buildUserContext } from '../../../services/supervisor-api.js';

const welcomeText = 'Hi! Welcome to TalentScope.ai Help. You can ask questions about platform features, navigation, and how to use the application.';

const suggestedQuestions = [
  'How do I use Skill Intelligence?',
  'How can I explore Market Intelligence?',
  'How do I find job opportunities?',
  'How can companies identify employee skill gaps?',
  'What does insufficient data mean?',
  'How do I navigate the platform?'
];

let messages = [];
let isLoading = false;
let errorText = '';
let lastFailedQuestion = '';
let rootContainer = null;
let activeRequestId = 0;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]);
}

function makeId() {
  return globalThis.crypto?.randomUUID?.() || `ai-help-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function welcomeMessage() {
  return { id: 'ai-help-welcome', role: 'assistant', text: welcomeText, mode: 'demo' };
}

export function renderAiHelpPage() {
  activeRequestId += 1;
  rootContainer = document.getElementById('mainContent');
  if (!rootContainer) return;

  messages = [welcomeMessage()];
  isLoading = false;
  errorText = '';
  lastFailedQuestion = '';
  drawPage();
}

function drawPage({ keepScroll = false } = {}) {
  if (!rootContainer) return;
  const oldHistory = rootContainer.querySelector('.ai-help-chat-history');
  const wasNearBottom = oldHistory
    ? oldHistory.scrollHeight - oldHistory.scrollTop - oldHistory.clientHeight < 80
    : true;
  const oldScrollTop = oldHistory?.scrollTop || 0;

  rootContainer.innerHTML = `
    <section class="ai-help-page" aria-labelledby="aiHelpTitle">
      <header class="ai-help-header">
        <div class="ai-help-heading">
          <span class="ai-help-heading-icon" aria-hidden="true"><i data-lucide="messages-square"></i></span>
          <div>
            <p class="ai-help-eyebrow">TALENTSCOPE.AI SUPPORT</p>
            <h1 id="aiHelpTitle">AI Help</h1>
            <p class="ai-help-subtitle">Get help using TalentScope.ai.</p>
          </div>
        </div>
        <button class="ai-help-new-chat" type="button" data-ai-help-action="clear">
          <i data-lucide="rotate-ccw" aria-hidden="true"></i><span>New Chat</span>
        </button>
      </header>

      <div class="ai-help-demo-notice" role="note">
        <i data-lucide="info" aria-hidden="true"></i>
        <span><strong>Demo responses:</strong> this temporary help guide is not connected to an AI model or live platform data.</span>
      </div>

      <div class="ai-help-layout">
        <section class="ai-help-chat-card" aria-label="AI Help conversation">
          <div class="ai-help-chat-topline">
            <div><span class="ai-help-online-dot" aria-hidden="true"></span><strong>TalentScope Help</strong></div>
            <span>Temporary demo</span>
          </div>

          <div class="ai-help-chat-history" role="log" aria-label="Chat messages" aria-live="polite" aria-relevant="additions text">
            ${messages.map(renderMessage).join('')}
            ${isLoading ? `
              <div class="ai-help-message-row assistant" role="status" aria-label="Preparing a temporary response">
                <span class="ai-help-avatar" aria-hidden="true"><i data-lucide="sparkles"></i></span>
                <div class="ai-help-message assistant ai-help-typing"><span>Preparing a demo response</span><i></i><i></i><i></i></div>
              </div>` : ''}
          </div>

          ${errorText ? `
            <div class="ai-help-error" role="alert">
              <span>${escapeHtml(errorText)}</span>
              ${lastFailedQuestion ? '<button type="button" data-ai-help-action="retry">Retry</button>' : ''}
            </div>` : ''}

          <form class="ai-help-composer" novalidate>
            <label class="sr-only" for="aiHelpInput">Your question</label>
            <textarea id="aiHelpInput" name="question" rows="2" maxlength="${AI_HELP_MAX_QUESTION_LENGTH}" placeholder="Ask how to use TalentScope.ai…" aria-describedby="aiHelpInputHint" ${isLoading ? 'disabled' : ''}></textarea>
            <div class="ai-help-composer-footer">
              <span id="aiHelpInputHint">Enter to send · Shift+Enter for a new line · ${AI_HELP_MAX_QUESTION_LENGTH} character limit</span>
              <button class="ai-help-send" type="submit" ${isLoading ? 'disabled' : ''}>
                <span>${isLoading ? 'Sending…' : 'Send'}</span><i data-lucide="arrow-up" aria-hidden="true"></i>
              </button>
            </div>
          </form>
        </section>

        <aside class="ai-help-suggestions" aria-labelledby="aiHelpSuggestionsTitle">
          <div class="ai-help-suggestions-heading">
            <span class="ai-help-suggestions-icon" aria-hidden="true"><i data-lucide="lightbulb"></i></span>
            <div><h2 id="aiHelpSuggestionsTitle">Suggested questions</h2><p>Choose one to add it to the chat.</p></div>
          </div>
          <div class="ai-help-suggestion-list">
            ${suggestedQuestions.map((question, index) => `
              <button class="ai-help-suggestion" type="button" data-ai-help-question="${index}">
                <span>${escapeHtml(question)}</span><i data-lucide="arrow-up-right" aria-hidden="true"></i>
              </button>`).join('')}
          </div>
        </aside>
      </div>
    </section>
  `;

  rootContainer.onclick = handleClick;
  rootContainer.onsubmit = handleSubmit;
  rootContainer.onkeydown = handleKeyDown;

  if (window.lucide) window.lucide.createIcons();
  const history = rootContainer.querySelector('.ai-help-chat-history');
  if (history) {
    if (!keepScroll || wasNearBottom) history.scrollTop = history.scrollHeight;
    else history.scrollTop = oldScrollTop;
  }
}

function renderMessage(message) {
  const isUser = message.role === 'user';
  const copyButton = !isUser
    ? `<button class="ai-help-copy" type="button" data-ai-help-action="copy" data-message-id="${escapeHtml(message.id)}" aria-label="Copy response"><i data-lucide="copy" aria-hidden="true"></i><span>Copy</span></button>`
    : '';
  return `
    <article class="ai-help-message-row ${isUser ? 'user' : 'assistant'}" data-message-id="${escapeHtml(message.id)}">
      ${isUser ? '' : '<span class="ai-help-avatar" aria-hidden="true"><i data-lucide="sparkles"></i></span>'}
      <div class="ai-help-message ${isUser ? 'user' : 'assistant'}">
        ${isUser ? '' : '<span class="ai-help-demo-label"><i data-lucide="info" aria-hidden="true"></i> Temporary help response · demo</span>'}
        <p>${escapeHtml(message.text).replace(/\n/g, '<br>')}</p>
        ${copyButton}
      </div>
    </article>`;
}

function handleKeyDown(event) {
  if (event.target?.id === 'aiHelpInput' && event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    event.target.form?.requestSubmit();
  }
}

function handleSubmit(event) {
  if (!event.target.matches('.ai-help-composer')) return;
  event.preventDefault();
  const input = event.target.elements.question;
  const question = input.value.trim();
  if (!question) {
    errorText = 'Enter a question before sending.';
    lastFailedQuestion = '';
    drawPage({ keepScroll: true });
    rootContainer.querySelector('#aiHelpInput')?.focus();
    return;
  }
  void sendQuestion(question);
}

function handleClick(event) {
  const questionButton = event.target.closest('[data-ai-help-question]');
  if (questionButton) {
    const question = suggestedQuestions[Number(questionButton.dataset.aiHelpQuestion)];
    if (question) void sendQuestion(question);
    return;
  }

  const actionButton = event.target.closest('[data-ai-help-action]');
  if (!actionButton) return;
  const action = actionButton.dataset.aiHelpAction;
  if (action === 'clear') {
    activeRequestId += 1;
    messages = [welcomeMessage()];
    isLoading = false;
    errorText = '';
    lastFailedQuestion = '';
    drawPage();
    rootContainer.querySelector('#aiHelpInput')?.focus();
  } else if (action === 'retry' && lastFailedQuestion && !isLoading) {
    void sendQuestion(lastFailedQuestion, { appendUser: false });
  } else if (action === 'copy') {
    const message = messages.find(item => item.id === actionButton.dataset.messageId);
    if (message) void copyResponse(message.text, actionButton);
  }
}

async function sendQuestion(question, { appendUser = true } = {}) {
  if (isLoading) return;
  const normalizedQuestion = question.trim();
  if (!normalizedQuestion) {
    errorText = 'Enter a question before sending.';
    drawPage({ keepScroll: true });
    return;
  }

  if (normalizedQuestion.length > AI_HELP_MAX_QUESTION_LENGTH) {
    errorText = `Keep your question to ${AI_HELP_MAX_QUESTION_LENGTH} characters or fewer.`;
    lastFailedQuestion = '';
    drawPage({ keepScroll: true });
    return;
  }

  if (appendUser) messages.push({ id: makeId(), role: 'user', text: normalizedQuestion });
  errorText = '';
  lastFailedQuestion = '';
  isLoading = true;
  const requestId = ++activeRequestId;
  drawPage();

  try {
    const userContext = buildUserContext();
    const history = messages.map(m => ({ role: m.role, content: m.text }));
    history.push({ role: 'user', content: normalizedQuestion });
    const supervisorResp = await sendSupervisorMessage(history, userContext);
    if (requestId !== activeRequestId || !isPageActive()) return;
    messages.push({
      id: makeId(),
      role: 'assistant',
      text: supervisorResp.answer || 'Analysis complete.',
      mode: 'supervisor'
    });
  } catch (err) {
    try {
      const response = await getTemporaryHelpResponse(normalizedQuestion);
      if (requestId !== activeRequestId || !isPageActive()) return;
      messages.push({ id: makeId(), role: 'assistant', text: response.text, mode: response.mode });
    } catch (fallbackErr) {
      if (requestId !== activeRequestId || !isPageActive()) return;
      errorText = err?.message || 'The temporary help response could not be prepared.';
      lastFailedQuestion = normalizedQuestion;
    }
  } catch (error) {
    if (requestId !== activeRequestId || !isPageActive()) return;
    errorText = error?.message || 'The temporary help response could not be prepared.';
    lastFailedQuestion = normalizedQuestion;
  } finally {
    if (requestId !== activeRequestId || !isPageActive()) return;
    isLoading = false;
    drawPage();
    rootContainer.querySelector('#aiHelpInput')?.focus();
  }
}

function isPageActive() {
  return typeof window === 'undefined' || window.location.hash.split('?')[0] === '#/individual/ai-help';
}

async function copyResponse(text, button) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const temporaryInput = document.createElement('textarea');
      temporaryInput.value = text;
      temporaryInput.style.position = 'fixed';
      temporaryInput.style.opacity = '0';
      document.body.appendChild(temporaryInput);
      temporaryInput.select();
      const copied = document.execCommand('copy');
      temporaryInput.remove();
      if (!copied) throw new Error('Copy is unavailable in this browser.');
    }
    const label = button.querySelector('span');
    if (label) {
      label.textContent = 'Copied';
      window.setTimeout(() => { if (label.isConnected) label.textContent = 'Copy'; }, 1200);
    }
  } catch {
    errorText = 'Could not copy the response. Select and copy the text instead.';
    drawPage({ keepScroll: true });
  }
}
