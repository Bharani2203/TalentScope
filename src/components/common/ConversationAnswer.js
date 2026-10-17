const STATUS_PRESENTATION = {
  blocked: {
    label: 'Access restricted',
    message: 'This request could not be answered with the current access.'
  },
  data_source_unavailable: {
    label: 'Data unavailable',
    message: 'A required data source is not available, so no verified result can be shown.'
  },
  error: {
    label: 'Could not complete',
    message: 'The request did not complete, so no verified result can be shown.'
  },
  failed: {
    label: 'Could not complete',
    message: 'The request did not complete, so no verified result can be shown.'
  },
  insufficient_data: {
    label: 'Not enough data',
    message: 'There is not enough verified information to answer this reliably.'
  },
  partial: {
    label: 'Partial evidence',
    message: 'This answer uses partial evidence; review the coverage and limitations below.'
  },
  requires_clarification: {
    label: 'More detail needed',
    message: 'A little more detail is needed before this can be answered reliably.'
  },
  unavailable: {
    label: 'Unavailable',
    message: 'This capability is not currently available, so no result is provided.'
  },
  unsupported: {
    label: 'Not supported',
    message: 'This analysis is not currently supported; no estimate or projection was produced.'
  }
};

const RAW_FIELD_LINE = /(?:^|[\s*`])(?:forecast_readiness|skill_health_component_readiness|skill_health_category|trend_direction|topic_pushers|language_pushers|taxonomy_category|github_developer_pushers)\s*[:=]/i;
const GENERIC_INTERNAL_FIELD_LINE = /^\s*(?:[-*]\s*)?(?:["'`])?(?:\*\*)?[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?:\*\*)?(?:["'`])?\s*[:=]/i;
const DUPLICATE_HEADING_LINE = /^\s*(?:#{1,6}\s*)?(?:evidence highlights|observed details|sources)\s*:?\s*$/i;
const EMPTY_STRUCTURED_LINE = /^\s*[{}\[\],]+\s*$/;
const UNAVAILABLE_STATUSES = new Set(['blocked', 'data_source_unavailable', 'error', 'failed', 'unavailable', 'unsupported']);

function responseStatus(response) {
  const statuses = [response?.execution_status, response?.status, response?.data_state, response?.data_status]
    .map(value => String(value || '').toLowerCase())
    .filter(Boolean);
  return statuses.find(value => UNAVAILABLE_STATUSES.has(value))
    || statuses.find(value => STATUS_PRESENTATION[value])
    || statuses[0]
    || '';
}

export function cleanConversationAnswer(text) {
  if (typeof text !== 'string') return '';
  return text
    .split(/\r?\n/)
    .filter(line => !RAW_FIELD_LINE.test(line)
      && !GENERIC_INTERNAL_FIELD_LINE.test(line)
      && !DUPLICATE_HEADING_LINE.test(line)
      && !EMPTY_STRUCTURED_LINE.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function renderConversationAnswer(response, formatMarkdown, {
  answer = response?.answer || response?.finding || '',
  explanation = ''
} = {}) {
  const status = responseStatus(response);
  const presentation = STATUS_PRESENTATION[status];
  const origin = response?.answer_origin === 'gemini'
    ? 'AI explanation'
    : response?.answer_origin === 'deterministic'
      ? 'Platform-generated answer'
      : '';
  const safeAnswer = cleanConversationAnswer(answer);

  return `<div class="conversation-answer">
    ${origin ? `<span class="conversation-answer__origin" style="display:inline-block; margin-bottom:6px; color:var(--portal-primary, #6B7280); font-size:11px; font-weight:700;">${origin}</span>` : ''}
    ${presentation ? `<div class="conversation-answer__status" role="${['blocked', 'error', 'failed'].includes(status) ? 'alert' : 'status'}" style="margin:0 0 10px; padding:8px 10px; border:1px solid var(--portal-border, #E5E7EB); border-radius:8px; background:var(--portal-soft, #F9FAFB); color:var(--ink-secondary, #52566E);">
      <strong style="font-size:12px;">${presentation.label}</strong>
      <p style="margin:3px 0 0; font-size:12px; line-height:1.45;">${presentation.message}</p>
    </div>` : ''}
    ${safeAnswer
      ? `<div class="conversation-answer__direct">${formatMarkdown(safeAnswer)}</div>`
      : `<p class="conversation-answer__empty" style="margin:0; color:var(--ink-secondary, #52566E); font-size:13px;">The answer included details that are not shown in the conversation. Review the evidence and limitations below.</p>`}
    ${explanation ? `<section class="conversation-answer__meaning" style="margin-top:10px;"><strong style="font-size:12px;">What this means</strong><p style="margin:3px 0 0;">${formatMarkdown(cleanConversationAnswer(explanation))}</p></section>` : ''}
  </div>`;
}

export function renderConversationNextAction(nextAction, formatMarkdown) {
  const safeAction = cleanConversationAnswer(nextAction);
  return safeAction
    ? `<section class="conversation-answer__next" style="margin-top:10px;"><strong style="font-size:12px;">Next step</strong><p style="margin:3px 0 0;">${formatMarkdown(safeAction)}</p></section>`
    : '';
}
