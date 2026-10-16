import { API_BASE_URL } from '../config/api.js';
import { AUTH_TRACE_ENABLED, clearAuthDiagnosticEvents, getAuthDiagnosticSnapshot } from './auth-trace.js';

let panel;

export function ensureAuthDiagnosticsPanel() {
  if (!AUTH_TRACE_ENABLED || !document.body) return;
  if (panel?.isConnected) return;

  panel = document.createElement('details');
  panel.id = 'authDiagnosticsPanel';
  panel.style.cssText = 'position:fixed;z-index:99999;right:16px;bottom:16px;width:min(560px,calc(100vw - 32px));max-height:min(72vh,680px);overflow:hidden;background:#111827;color:#f9fafb;border:1px solid #4b5563;border-radius:10px;box-shadow:0 12px 36px #0008;font:13px/1.45 system-ui,sans-serif;';
  panel.innerHTML = `
    <summary style="cursor:pointer;padding:12px 14px;font-weight:700;list-style-position:inside">Auth Diagnostics <span id="authDiagnosticsCount" style="font-weight:400;opacity:.75"></span></summary>
    <div style="padding:0 14px 14px;overflow:auto;max-height:calc(min(72vh,680px) - 48px)">
      <div id="authDiagnosticsState" style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;margin:0 0 10px"></div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;opacity:.85">
        <span>Frontend: <code id="authDiagnosticsOrigin"></code></span>
        <span>Backend: <code id="authDiagnosticsApi"></code></span>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <button type="button" id="copyAuthDiagnostics" style="padding:6px 9px">Copy safe diagnostic log</button>
        <button type="button" id="clearAuthDiagnostics" style="padding:6px 9px">Clear</button>
      </div>
      <ol id="authDiagnosticsEvents" style="margin:0;padding-left:24px;max-height:340px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere"></ol>
    </div>`;
  document.body.appendChild(panel);

  const eventsNode = panel.querySelector('#authDiagnosticsEvents');
  const countNode = panel.querySelector('#authDiagnosticsCount');
  const stateNode = panel.querySelector('#authDiagnosticsState');
  panel.querySelector('#authDiagnosticsOrigin').textContent = window.location.origin;
  panel.querySelector('#authDiagnosticsApi').textContent = API_BASE_URL;

  function renderState() {
    const snapshot = getAuthDiagnosticSnapshot();
    const rows = [
      ['Firebase user', snapshot.firebase_user ? 'YES' : 'NO'],
      ['Email verified', snapshot.email_verified ? 'YES' : 'NO'],
      ['Provider', snapshot.provider_ids.join(', ') || 'UNKNOWN'],
      ['ID token', snapshot.id_token],
      ['Profile sync', snapshot.profile_sync],
      ['Profile', snapshot.profile],
      ['Onboarding', snapshot.onboarding]
    ];
    stateNode.replaceChildren(...rows.map(([label, value]) => {
      const row = document.createElement('div');
      row.textContent = `${label}: ${value}`;
      return row;
    }));
    countNode.textContent = `(${snapshot.events.length} events)`;
  }

  function formatEvent(event) {
    const date = new Date(event.timestamp);
    const time = `${date.toLocaleTimeString(undefined, { hour12: false })}.${String(date.getMilliseconds()).padStart(3, '0')}`;
    const details = [];
    for (const key of ['duration_ms', 'elapsed_ms', 'status', 'result', 'category', 'error_name', 'error_message', 'url', 'method', 'request_id', 'backend_request_id', 'content_type', 'body_bytes', 'profile_status', 'route']) {
      if (event[key] !== undefined) details.push(`${key}=${event[key]}`);
    }
    const item = document.createElement('li');
    item.textContent = `[${time}] ${event.event}${details.length ? ` ${details.join(' ')}` : ''}`;
    return item;
  }

  function renderEvents() {
    const snapshot = getAuthDiagnosticSnapshot();
    eventsNode.replaceChildren(...snapshot.events.map(formatEvent));
    countNode.textContent = `(${snapshot.events.length} events)`;
    eventsNode.scrollTop = eventsNode.scrollHeight;
  }

  function onEvent(event) {
    if (event.detail) eventsNode.appendChild(formatEvent(event.detail));
    renderState();
    renderEvents();
  }
  window.addEventListener('talentscope-auth-diagnostic-event', onEvent);
  window.addEventListener('talentscope-auth-diagnostic-update', renderState);

  panel.querySelector('#copyAuthDiagnostics').addEventListener('click', async () => {
    const snapshot = getAuthDiagnosticSnapshot();
    const lines = [
      'AUTH DIAGNOSTIC',
      `Frontend: ${snapshot.frontend_origin}`,
      `Backend: ${snapshot.api_base_url}`,
      ...snapshot.events.map(event => formatEventText(event))
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      panel.querySelector('#copyAuthDiagnostics').textContent = 'Copied safe log';
    } catch {
      panel.querySelector('#copyAuthDiagnostics').textContent = 'Clipboard unavailable';
    }
  });
  panel.querySelector('#clearAuthDiagnostics').addEventListener('click', clearAuthDiagnosticEvents);
  window.addEventListener('talentscope-auth-diagnostic-clear', () => {
    eventsNode.replaceChildren();
    renderState();
  });
  renderState();
  renderEvents();
}

function formatEventText(event) {
  const date = new Date(event.timestamp);
  const time = `${date.toLocaleTimeString(undefined, { hour12: false })}.${String(date.getMilliseconds()).padStart(3, '0')}`;
  const details = [];
  for (const key of ['duration_ms', 'elapsed_ms', 'status', 'result', 'category', 'error_name', 'error_message', 'url', 'method', 'request_id', 'backend_request_id', 'content_type', 'body_bytes', 'profile_status', 'route']) {
    if (event[key] !== undefined) details.push(`${key}=${event[key]}`);
  }
  return `[${time}] ${event.event}${details.length ? ` ${details.join(' ')}` : ''}`;
}
