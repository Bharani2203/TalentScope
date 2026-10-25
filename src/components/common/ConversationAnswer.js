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
    label: 'Not enough verified evidence',
    message: 'The requested result could not be calculated from verified information.'
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

function renderStructuredAnswerBlock(block, formatMarkdown) {
  const table = block?.table;
  const columns = Array.isArray(table?.columns) ? table.columns : [];
  const rows = Array.isArray(table?.rows) ? table.rows : [];
  const footer = block?.footer || {};
  const disclosures = Array.isArray(footer.disclosures) ? footer.disclosures : [];
  const bullets = Array.isArray(block?.bullets) ? block.bullets : [];
  const quickReplies = Array.isArray(block?.clarification?.options) ? block.clarification.options : [];
  const escapeAttribute = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  return `<section class="assistant-answer-block" aria-label="Answer">
    <h3 class="assistant-answer-block__verdict">${formatMarkdown(cleanConversationAnswer(block.verdict || 'Answer'))}</h3>
    ${block.summary ? `<p class="assistant-answer-block__summary">${formatMarkdown(cleanConversationAnswer(block.summary))}</p>` : ''}
    ${quickReplies.length ? `<div class="assistant-answer-block__quick-replies" role="group" aria-label="Quick replies">${quickReplies.map(option => `<button type="button" class="assistant-quick-reply" data-clarification-reply="${escapeAttribute(option?.value)}">${formatMarkdown(cleanConversationAnswer(String(option?.label ?? option?.value ?? '')))}</button>`).join('')}</div>` : ''}
    ${columns.length && rows.length ? `<div class="assistant-answer-block__table-wrap" role="region" aria-label="Answer details" tabindex="0"><table class="assistant-answer-block__table"><thead><tr>${columns.map(column => `<th scope="col">${formatMarkdown(String(column))}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(column => `<td>${formatMarkdown(cleanConversationAnswer(String(row?.[column] ?? '')))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}
    ${bullets.length ? `<ul class="assistant-answer-block__bullets">${bullets.map(item => `<li>${formatMarkdown(cleanConversationAnswer(String(item)))}</li>`).join('')}</ul>` : ''}
    ${(footer.based_on || disclosures.length) ? `<footer class="assistant-answer-block__footer">${footer.based_on ? `<p><strong>Based on:</strong> ${formatMarkdown(cleanConversationAnswer(String(footer.based_on)))}</p>` : ''}${disclosures.length ? `<ul>${disclosures.map(item => `<li>${formatMarkdown(cleanConversationAnswer(String(item)))}</li>`).join('')}</ul>` : ''}</footer>` : ''}
  </section>`;
}

export function renderConversationAnswer(response, formatMarkdown, {
  answer = response?.answer || response?.finding || '',
  explanation = ''
} = {}) {
  if (response?.answer_block?.verdict) {
    return renderStructuredAnswerBlock(response.answer_block, formatMarkdown);
  }
  const status = responseStatus(response);
  const intent = String(response?.intent || '').toLowerCase();
  const responsePresentation = {
    general_explanation: {
      unavailable: { label: 'General explanation unavailable', message: 'The general explanation service is unavailable. No TalentScope market finding was produced.' },
      unsupported: { label: 'General explanation unavailable', message: 'No general explanation was returned. No TalentScope market finding was produced.' },
      insufficient_data: { label: 'General explanation unavailable', message: 'No general explanation was returned. No TalentScope market finding was produced.' }
    },
    explain_concept: {
      unavailable: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this concept.' },
      unsupported: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this concept.' },
      insufficient_data: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this concept.' }
    },
    lookup_skill_reference: {
      unavailable: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this skill.' },
      unsupported: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this skill.' },
      insufficient_data: { label: 'Reference information unavailable', message: 'No verified reference entry was available for this skill.' }
    },
    analyze_trend: {
      insufficient_data: { label: 'Trend not calculated', message: 'The selected comparable source series did not meet the trend readiness checks.' },
      data_source_unavailable: { label: 'Trend source unavailable', message: 'The selected source could not provide verified observations; no trend was calculated.' }
    },
    search_jobs: {
      insufficient_data: { label: 'No verified postings retrieved', message: 'No matching postings were retrieved from the stored posting records.' },
      data_source_unavailable: { label: 'Posting source unavailable', message: 'The stored posting source could not provide a verified result.' }
    }
  };
  const presentation = responsePresentation[intent]?.[status] || STATUS_PRESENTATION[status];
  const origin = response?.source_mode === 'ai_general_guidance'
    ? 'General AI guidance'
    : (response?.answer_origin === 'gemini' ? (intent === 'general_explanation' ? 'General AI explanation' : 'AI explanation of evidence') : '');
  const safeAnswer = cleanConversationAnswer(answer);

  return `<div class="conversation-answer">
    ${response?.answer_title ? `<h3 class="conversation-answer__title" style="margin:0 0 8px; font-size:15px;">${formatMarkdown(cleanConversationAnswer(response.answer_title))}</h3>` : ''}
    ${origin ? `<span class="conversation-answer__origin" style="display:inline-block; margin-bottom:6px; color:var(--portal-primary, #6B7280); font-size:11px; font-weight:700;">${origin}</span>` : ''}
    ${presentation ? `<div class="conversation-answer__status" role="${['blocked', 'error', 'failed'].includes(status) ? 'alert' : 'status'}" style="margin:0 0 10px; padding:8px 10px; border:1px solid var(--portal-border, #E5E7EB); border-radius:8px; background:var(--portal-soft, #F9FAFB); color:var(--ink-secondary, #52566E);">
      <strong style="font-size:12px;">${presentation.label}</strong>
      <p style="margin:3px 0 0; font-size:12px; line-height:1.45;">${presentation.message}</p>
    </div>` : ''}
    ${safeAnswer
      ? `<div class="conversation-answer__direct">${formatMarkdown(safeAnswer)}</div>`
      : `<p class="conversation-answer__empty" style="margin:0; color:var(--ink-secondary, #52566E); font-size:13px;">The answer included details that are not shown in the conversation. Review the evidence and limitations below.</p>`}
    ${explanation ? `<section class="conversation-answer__meaning" style="margin-top:10px;"><strong style="font-size:12px;">What this means</strong><p style="margin:3px 0 0;">${formatMarkdown(cleanConversationAnswer(explanation))}</p></section>` : ''}
    ${Array.isArray(response?.next_actions) && response.next_actions.length ? `<section class="conversation-answer__next-actions" aria-label="Next actions"><strong style="font-size:12px;">Next steps</strong><ol>${response.next_actions.slice(0, 5).map(action => `<li>${formatMarkdown(cleanConversationAnswer(action))}</li>`).join('')}</ol></section>` : ''}
  </div>`;
}

export function renderConversationNextAction(nextAction, formatMarkdown) {
  const safeAction = cleanConversationAnswer(nextAction);
  return safeAction
    ? `<section class="conversation-answer__next" style="margin-top:10px;"><strong style="font-size:12px;">Next step</strong><p style="margin:3px 0 0;">${formatMarkdown(safeAction)}</p></section>`
    : '';
}
