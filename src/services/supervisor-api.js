import { API_BASE_URL } from '../config/api.js';

// Resolve to backend API host (defaulting to http://127.0.0.1:8000 for local development)
const BACKEND_API_BASE_URL = (() => {
  if (typeof API_BASE_URL === 'string' && API_BASE_URL && !API_BASE_URL.match(/:3000|:5173|:5000/)) {
    return API_BASE_URL.replace(/\/$/, '');
  }
  return 'http://127.0.0.1:8000';
})();

/**
 * Builds user context object by inspecting localStorage for user skills, target role, and location.
 * Merges any provided overrides.
 *
 * @param {Object} [overrides={}] - Explicit context overrides.
 * @returns {Object} Structured user_context for the supervisor agent.
 */
export function buildUserContext(overrides = {}) {
  let user_skills = ['Python', 'SQL', 'AWS'];
  let target_role = 'AI Engineer';
  let location = 'India';
  let current_view = '';

  if (typeof localStorage !== 'undefined') {
    try {
      const savedRoles = localStorage.getItem('talentscope-saved-roles');
      if (savedRoles) {
        const parsed = JSON.parse(savedRoles);
        if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'string') {
          target_role = parsed[0];
        }
      }

      const onboarding = localStorage.getItem('talentscope-onboarding-profile');
      if (onboarding) {
        const parsed = JSON.parse(onboarding);
        if (parsed?.targetRole) target_role = parsed.targetRole;
        else if (parsed?.selectedRole) target_role = parsed.selectedRole;
        else if (parsed?.careerDirection) target_role = parsed.careerDirection;
        if (Array.isArray(parsed?.skills) && parsed.skills.length > 0) {
          user_skills = parsed.skills;
        }
      }

      const userProfile = localStorage.getItem('talentscope-user-profile');
      if (userProfile) {
        const parsed = JSON.parse(userProfile);
        if (parsed?.targetRole) target_role = parsed.targetRole;
        else if (parsed?.target_role) target_role = parsed.target_role;
        if (Array.isArray(parsed?.skills) && parsed.skills.length > 0) {
          user_skills = parsed.skills;
        }
      }

      const storedSkills = localStorage.getItem('talentscope-saved-skills');
      if (storedSkills) {
        const parsed = JSON.parse(storedSkills);
        if (Array.isArray(parsed) && parsed.length > 0) {
          user_skills = parsed.map(s => (typeof s === 'string' ? s : s?.name || s?.skill || '')).filter(Boolean);
        }
      }
    } catch {}
  }

  const finalRole = (overrides.target_role && String(overrides.target_role).trim())
    ? String(overrides.target_role).trim()
    : target_role;
  const finalLocation = (overrides.location && String(overrides.location).trim())
    ? String(overrides.location).trim()
    : location;
  const finalSkills = (Array.isArray(overrides.user_skills) && overrides.user_skills.length > 0)
    ? overrides.user_skills
    : user_skills;
  const finalView = (overrides.current_view !== undefined && overrides.current_view !== null)
    ? String(overrides.current_view).trim()
    : current_view;

  return {
    user_skills: finalSkills,
    target_role: finalRole,
    current_view: finalView,
    location: finalLocation
  };
}

/**
 * Sends a multi-turn conversation turn to the Supervisor Agent via POST /api/assistant/chat.
 * Gracefully tries localhost multi-port fallbacks.
 *
 * @param {Array<{role: string, content: string}>} messages - Conversation history.
 * @param {Object} [userContext={}] - Optional user context overrides.
 * @returns {Promise<Object>} Supervisor response containing answer, tools_invoked, evidence_payloads, and suggested_followups.
 */
export async function sendSupervisorMessage(messages, userContext = {}) {
  const context = buildUserContext(userContext);
  const payload = {
    messages: (messages || []).map(m => ({
      role: m.role || 'user',
      content: String(m.content || '')
    })),
    user_context: context
  };

  const urls = [
    `${BACKEND_API_BASE_URL}/api/assistant/chat`,
    `http://127.0.0.1:8000/api/assistant/chat`,
    `http://127.0.0.1:8010/api/assistant/chat`
  ];

  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        if (data && typeof data.answer === 'string') {
          return {
            answer: data.answer,
            tools_invoked: Array.isArray(data.tools_invoked) ? data.tools_invoked : [],
            evidence_payloads: Array.isArray(data.evidence_payloads) ? data.evidence_payloads : [],
            suggested_followups: Array.isArray(data.suggested_followups) ? data.suggested_followups : [],
            provenance_summary: data.provenance_summary || ''
          };
        }
      }
    } catch {
      // try next target
    }
  }

  // Graceful fallback when backend is unreachable
  return {
    answer: "I'm having trouble connecting to the intelligence supervisor right now. Please ensure the backend is running.",
    tools_invoked: [],
    evidence_payloads: [],
    suggested_followups: ["Try again", "Show available roles", "Analyze my skills"],
    provenance_summary: "Local offline fallback"
  };
}

/**
 * Streams the Supervisor Agent execution events via Server-Sent Events (SSE).
 * Falls back to sendSupervisorMessage in environments without SSE reader support.
 *
 * @param {Array<{role: string, content: string}>} messages
 * @param {Object} [userContext={}]
 * @param {Object} [callbacks={}]
 * @returns {Promise<Object>} Final supervisor response.
 */
export async function streamSupervisorMessage(messages, userContext = {}, callbacks = {}) {
  const {
    onToolCall = () => {},
    onEvidence = () => {},
    onToken = () => {},
    onDone = () => {},
    onError = () => {}
  } = callbacks;

  const context = buildUserContext(userContext);
  const payload = {
    messages: (messages || []).map(m => ({
      role: m.role || 'user',
      content: String(m.content || '')
    })),
    user_context: context
  };

  const urls = [
    `${BACKEND_API_BASE_URL}/api/assistant/stream`,
    `http://127.0.0.1:8000/api/assistant/stream`,
    `http://127.0.0.1:8010/api/assistant/stream`
  ];
  const uniqueUrls = [...new Set(urls)];

  for (const url of uniqueUrls) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream'
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const contentType = res.headers ? (res.headers.get('content-type') || '') : '';
        if (contentType.includes('application/json')) {
          const data = await res.json();
          for (const tool of (data.tools_invoked || [])) {
            onToolCall(tool);
          }
          for (const ev of (data.evidence_payloads || [])) {
            onEvidence(ev);
          }
          if (data.answer) {
            onToken(data.answer);
          }
          onDone(data);
          return data;
        }

        if (res.body && typeof res.body.getReader === 'function') {
          const reader = res.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';
          let fullAnswer = '';
          let toolsInvoked = [];
          let evidenceList = [];
          let followups = [];
          let provenance = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const events = buffer.split('\n\n');
            buffer = events.pop();

            for (const rawEvent of events) {
              if (!rawEvent.trim()) continue;
              const lines = rawEvent.split('\n');
              let eventType = 'message';
              let eventDataStr = '';

              for (const line of lines) {
                if (line.startsWith('event: ')) {
                  eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                  eventDataStr = line.slice(6).trim();
                }
              }

              if (!eventDataStr) continue;
              try {
                const data = JSON.parse(eventDataStr);
                if (eventType === 'tool_call') {
                  if (data.tool) toolsInvoked.push(data.tool);
                  onToolCall(data.tool || data);
                } else if (eventType === 'evidence') {
                  evidenceList.push(data);
                  onEvidence(data);
                } else if (eventType === 'token') {
                  if (data.token) fullAnswer += data.token;
                  onToken(data.token || '');
                } else if (eventType === 'done') {
                  if (data.answer) fullAnswer = data.answer;
                  if (data.tools_invoked) toolsInvoked = data.tools_invoked;
                  if (data.suggested_followups) followups = data.suggested_followups;
                  if (data.provenance_summary) provenance = data.provenance_summary;
                  const finalResp = {
                    answer: fullAnswer,
                    tools_invoked: toolsInvoked,
                    evidence_payloads: evidenceList,
                    suggested_followups: followups,
                    provenance_summary: provenance
                  };
                  onDone(finalResp);
                  return finalResp;
                } else if (eventType === 'error') {
                  onError(new Error(data.error || 'Stream error'));
                }
              } catch {
                // Ignore partial parse
              }
            }
          }

          const fallbackResp = {
            answer: fullAnswer,
            tools_invoked: toolsInvoked,
            evidence_payloads: evidenceList,
            suggested_followups: followups,
            provenance_summary: provenance
          };
          onDone(fallbackResp);
          return fallbackResp;
        }
      }
    } catch {
      // Try next url
    }
  }

  // Graceful fallback to standard request
  try {
    const resp = await sendSupervisorMessage(messages, context);
    for (const tool of resp.tools_invoked) {
      onToolCall(tool);
    }
    for (const ev of resp.evidence_payloads) {
      onEvidence(ev);
    }
    if (resp.answer) {
      onToken(resp.answer);
    }
    onDone(resp);
    return resp;
  } catch (err) {
    onError(err);
    throw err;
  }
}
