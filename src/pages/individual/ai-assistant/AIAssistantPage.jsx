import { useEffect, useRef, useState } from 'react';
import { auth } from '../../../auth/firebase-client.js';
import { API_BASE_URL } from '../../../config/api.js';

const INITIAL_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  text: 'Hi! I’m your AI Career Assistant. Ask me about career paths, skills to build, or your next professional step.'
};

function newMessageId() {
  return globalThis.crypto?.randomUUID?.() || `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getAssistantMessage(response) {
  const block = response?.answer_block;
  return {
    id: newMessageId(),
    role: 'assistant',
    title: response?.answer_title || block?.verdict || '',
    text: block?.summary || response?.answer || 'The assistant returned an empty response.',
    bullets: Array.isArray(block?.bullets) ? block.bullets : [],
    nextActions: Array.isArray(response?.next_actions) ? response.next_actions : [],
    disclosures: Array.isArray(block?.footer?.disclosures) ? block.footer.disclosures : [],
    basedOn: block?.footer?.based_on || ''
  };
}

function formatRequestError(error) {
  if (error?.status === 401 || error?.status === 403) {
    return 'Your sign-in session could not be verified. Sign in again, then retry your message.';
  }
  if (error instanceof TypeError) {
    return 'Could not reach the local backend. Check that it is running at http://127.0.0.1:8010.';
  }
  return error?.message || 'Something went wrong while getting a response. Please try again.';
}

/**
 * Standalone TalentScope AI Career Assistant page.
 * The app must be opened with ?firebaseEmulator=1 when using local emulators.
 */
export default function AIAssistantPage() {
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [draft, setDraft] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const historyRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const history = historyRef.current;
    if (history) history.scrollTop = history.scrollHeight;
  }, [messages, isLoading]);

  async function sendMessage(event) {
    event?.preventDefault();
    const message = draft.trim();
    if (!message || isLoading) return;

    const emulatorMode = typeof window !== 'undefined'
      && new URLSearchParams(window.location.search).get('firebaseEmulator') === '1';
    if (!emulatorMode) {
      setErrorMessage('Open the local app with ?firebaseEmulator=1 to use the local AI assistant.');
      return;
    }

    const user = auth.currentUser;
    if (!user) {
      setErrorMessage('Sign in to use the AI Career Assistant.');
      return;
    }

    setErrorMessage('');
    setDraft('');
    setMessages(current => [...current, { id: newMessageId(), role: 'user', text: message }]);
    setIsLoading(true);

    try {
      const idToken = await user.getIdToken();
      const response = await fetch(`${API_BASE_URL}/api/v1/intelligence/answer`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${idToken}`
        },
        body: JSON.stringify({
          message,
          portal_type: 'individual',
          conversation_id: conversationId,
          client_message_id: newMessageId()
        })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail = typeof payload?.detail === 'string' ? payload.detail : payload?.detail?.message;
        const requestError = new Error(detail || `The assistant request failed (HTTP ${response.status}).`);
        requestError.status = response.status;
        throw requestError;
      }

      const result = await response.json();
      if (result?.conversation_id) setConversationId(result.conversation_id);
      setMessages(current => [...current, getAssistantMessage(result)]);
    } catch (error) {
      setErrorMessage(formatRequestError(error));
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleInputKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage(event);
    }
  }

  return (
    <main className="flex h-dvh min-h-[560px] w-full overflow-hidden bg-slate-50 text-slate-900">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-5 md:flex">
        <a href="#/individual/home" className="mb-10 flex items-center gap-3 font-semibold tracking-tight" aria-label="TalentScope home">
          <span className="grid size-9 place-items-center rounded-xl bg-violet-600 text-lg text-white" aria-hidden="true">✦</span>
          <span>TalentScope<span className="text-violet-600">.ai</span></span>
        </a>
        <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Workspace</p>
        <nav aria-label="Assistant navigation" className="space-y-1">
          <a href="#/individual/ai-assistant" aria-current="page" className="flex items-center gap-3 rounded-xl bg-violet-50 px-3 py-2.5 text-sm font-medium text-violet-700">
            <span aria-hidden="true">✧</span> Career assistant
          </a>
          <a href="#/individual/career" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50">
            <span aria-hidden="true">↗</span> Career opportunities
          </a>
          <a href="#/individual/skills" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50">
            <span aria-hidden="true">◇</span> Skill intelligence
          </a>
        </nav>
        <div className="mt-auto rounded-2xl bg-violet-50 p-4">
          <p className="text-sm font-semibold text-violet-950">Make your next move</p>
          <p className="mt-1 text-xs leading-5 text-violet-800">Ask for practical guidance based on your career goals.</p>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[72px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-8">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-violet-600">Career workspace</p>
            <h1 className="mt-0.5 text-lg font-semibold">AI Career Assistant</h1>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
            <span className="size-2 rounded-full bg-emerald-500" aria-hidden="true" /> Ready to help
          </div>
        </header>

        <div ref={historyRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-8" aria-label="Conversation history" aria-live="polite">
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {messages.map(message => (
              <article key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[88%] rounded-2xl px-4 py-3 shadow-sm sm:max-w-[78%] ${message.role === 'user'
                  ? 'rounded-br-md bg-violet-600 text-white'
                  : `rounded-bl-md border border-slate-200 bg-white text-slate-800 ${message.isError ? 'border-rose-200 text-rose-700' : ''}`}`}>
                  {message.role === 'assistant' && (
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-violet-600">{message.title || 'Career assistant'}</p>
                  )}
                  <p className="whitespace-pre-wrap text-sm leading-6">{message.text}</p>
                  {message.bullets?.length > 0 && (
                    <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6">
                      {message.bullets.map((bullet, index) => <li key={`${message.id}-bullet-${index}`}>{bullet}</li>)}
                    </ul>
                  )}
                  {message.basedOn && <p className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500">Based on: {message.basedOn}</p>}
                  {message.disclosures?.length > 0 && (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-500">
                      {message.disclosures.map((item, index) => <li key={`${message.id}-disclosure-${index}`}>{item}</li>)}
                    </ul>
                  )}
                  {message.nextActions?.length > 0 && (
                    <div className="mt-3 border-t border-slate-100 pt-2">
                      <p className="mb-1 text-xs font-semibold text-slate-600">Suggested next steps</p>
                      <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
                        {message.nextActions.map((item, index) => <li key={`${message.id}-action-${index}`}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </article>
            ))}

            {isLoading && (
              <div className="flex justify-start" role="status" aria-label="Assistant is typing">
                <div className="flex items-center gap-2 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                  <span>Thinking</span>
                  <span className="flex gap-1" aria-hidden="true">
                    <span className="size-1.5 animate-bounce rounded-full bg-violet-500 [animation-delay:-0.2s]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-violet-500 [animation-delay:-0.1s]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-violet-500" />
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="sticky bottom-0 shrink-0 border-t border-slate-200 bg-white/95 px-4 py-4 backdrop-blur sm:px-8">
          <form onSubmit={sendMessage} className="mx-auto max-w-3xl">
            {errorMessage && <p className="mb-2 text-sm text-rose-600" role="alert">{errorMessage}</p>}
            <div className="flex items-end gap-3 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-100">
              <label className="sr-only" htmlFor="career-assistant-message">Your message</label>
              <textarea
                ref={inputRef}
                id="career-assistant-message"
                value={draft}
                onChange={event => setDraft(event.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="Ask about your career, skills, or next steps…"
                rows={1}
                maxLength={2000}
                disabled={isLoading}
                className="max-h-32 min-h-11 flex-1 resize-y bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-slate-400 disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={isLoading || !draft.trim()}
                className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-violet-600 px-4 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span>Send</span><span aria-hidden="true">↑</span>
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-slate-400">Press Enter to send · Shift+Enter for a new line</p>
          </form>
        </footer>
      </section>
    </main>
  );
}
