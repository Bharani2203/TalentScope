// ============================================================================
// TALENTSCOPE.AI — SHARED CORE INTELLIGENCE UI COMPONENTS
// Standardized reusable components for Individual, Employee, and Company portals.
// ============================================================================

export const STATUS_CONFIG = {
  completed: {
    label: 'Verified Grounded',
    bg: 'rgba(25,183,122,0.12)',
    color: '#059669',
    borderColor: 'rgba(25,183,122,0.3)',
    icon: 'check-circle-2',
    description: 'Directly grounded against verified platform reference datasets or empirical observations.'
  },
  requires_clarification: {
    label: 'Clarification Required',
    bg: 'rgba(245,158,11,0.12)',
    color: '#D97706',
    borderColor: 'rgba(245,158,11,0.3)',
    icon: 'help-circle',
    description: 'Query requires more specific parameters to execute deterministically.'
  },
  insufficient_data: {
    label: 'Insufficient Data',
    bg: 'rgba(107,114,128,0.12)',
    color: '#4B5563',
    borderColor: 'rgba(107,114,128,0.3)',
    icon: 'database',
    description: 'Required historical series or empirical observations are not currently available.'
  },
  unsupported: {
    label: 'Unsupported in G2.6/G2.7',
    bg: 'rgba(107,114,128,0.12)',
    color: '#4B5563',
    borderColor: 'rgba(107,114,128,0.3)',
    icon: 'ban',
    description: 'Forecasting and workforce what-if simulations are inactive and unsupported.'
  },
  blocked: {
    label: 'Access Restricted',
    bg: 'rgba(239,68,68,0.12)',
    color: '#DC2626',
    borderColor: 'rgba(239,68,68,0.3)',
    icon: 'lock',
    description: 'Request rejected by portal permission boundary or company multi-tenant isolation guard.'
  },
  failed: {
    label: 'Execution Failed',
    bg: 'rgba(239,68,68,0.12)',
    color: '#DC2626',
    borderColor: 'rgba(239,68,68,0.3)',
    icon: 'alert-triangle',
    description: 'Analytical execution failed safely without returning unverified data.'
  }
};

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

function friendlyEvidenceLabel(value) {
  const key = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const labels = {
    forecast_readiness: 'Forecast readiness',
    github_developer_pushers: 'Related developer activity',
    job_demand: 'Job-posting demand',
    language_pushers: 'Related programming languages',
    skill_health_category: 'Skill health category',
    skill_health_component_readiness: 'Skill health input readiness',
    taxonomy_category: 'Taxonomy category',
    topic_pushers: 'Related topics',
    trend_analysis: 'Trend analysis',
    trend_direction: 'Trend direction'
  };
  return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase()) || 'Evidence';
}

/**
 * Standardized status badge
 */
export function renderCapabilityStatusBadge(status, reasonCodes = []) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.completed;
  const reasonTooltip = reasonCodes && reasonCodes.length ? ` title="${esc(reasonCodes.join(', '))}"` : '';

  return `
    <span class="ts-status-badge ts-status-badge--${esc(status)}" style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; background:${cfg.bg}; color:${cfg.color}; border:1px solid ${cfg.borderColor}; padding:3px 9px; border-radius:6px;"${reasonTooltip}>
      <i data-lucide="${cfg.icon}" style="width:12px; height:12px;"></i>
      <span>${esc(cfg.label)}</span>
    </span>
  `;
}

/**
 * Standardized structured facts grid
 */
export function renderStructuredFactsGrid(facts, options = {}) {
  if (!facts || !facts.length) return '';

  const title = options.title || 'Structured Facts';
  const primaryColor = options.primaryColor || 'var(--cmp-primary, var(--emp-primary, #7C3AED))';

  return `
    <div class="ts-facts-block" style="background:#FFFFFF; padding:12px 14px; border-radius:10px; border:1px solid rgba(0,0,0,0.08); margin:8px 0;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <strong style="color:#6B7280; text-transform:uppercase; font-size:10.5px; letter-spacing:0.05em;">${esc(title)} (${facts.length})</strong>
        <span style="font-size:10px; color:#9CA3AF;"><i data-lucide="shield-check" style="width:11px; height:11px; vertical-align:middle;"></i> Verifiable Provenance</span>
      </div>
      <div class="ts-facts-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:8px;">
        ${facts.map(f => `
          <div class="ts-fact-card" style="background:#F9FAFB; border:1px solid #E5E7EB; border-radius:8px; padding:8px 10px; font-size:12px;">
            <div style="font-weight:600; color:#4B5563; font-size:11px; margin-bottom:2px;">${esc(f.metric_name || f.name)}</div>
            <div style="font-size:13.5px; font-weight:800; color:${primaryColor};">
              ${esc(f.metric_value !== undefined ? f.metric_value : f.value)}
              ${f.unit ? `<small style="font-weight:normal; font-size:10.5px; color:#6B7280;"> ${esc(f.unit)}</small>` : ''}
            </div>
            <div style="font-size:10px; color:#9CA3AF; margin-top:3px; display:flex; justify-content:space-between;">
              <span>${esc(f.source)}</span>
              ${f.quality_state ? `<span style="color:#059669;">${esc(f.quality_state)}</span>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

export function renderAnswerEvidencePanel(facts = [], evidence = [], options = {}) {
  const title = options.title || 'Evidence & provenance';
  const unavailableStatuses = new Set(['blocked', 'data_source_unavailable', 'error', 'failed', 'unavailable', 'unsupported']);
  const unavailable = [options.executionStatus, options.status]
    .some(status => unavailableStatuses.has(String(status || '').toLowerCase()));
  const validFacts = unavailable ? [] : Array.isArray(facts) ? facts : [];
  const validEvidence = unavailable ? [] : Array.isArray(evidence) ? evidence : [];
  const postings = validFacts
    .filter(fact => fact.fact_type === 'stored_job_postings')
    .flatMap(fact => Array.isArray(fact.details?.postings) ? fact.details.postings : [])
    .slice(0, 5);

  if (!validFacts.length && !validEvidence.length && !postings.length) return '';

  const factKind = fact => {
    if (fact.data_origin === 'demo') return 'Demo data';
    if (['reference', 'static_dataset'].includes(fact.data_origin)
      || fact.history_type === 'static_dataset'
      || String(fact.source || '').toLowerCase().startsWith('reference')) {
      return 'Reference';
    }
    if (fact.metric_kind === 'observed') return 'Observed measurement';
    if (fact.metric_kind === 'derived') return 'Derived analysis';
    if (fact.metric_kind === 'predicted') return 'Forecast';
    if (/forecast|prediction/i.test(fact.fact_type || '')) return 'Forecast';
    if (/readiness/i.test(fact.fact_type || '')) return 'Readiness';
    if (/trend|health|half.life|analysis/i.test(fact.fact_type || '')) return 'Derived';
    return 'Evidence-backed fact';
  };
  const safeSourceUrl = value => {
    try {
      const url = new URL(String(value || '').trim());
      return url.protocol === 'https:' && url.hostname && !url.username && !url.password
        ? url.href
        : null;
    } catch {
      return null;
    }
  };
  const trendSignalLabel = (signalType, source) => {
    if (signalType === 'demand') {
      return ['jsearch', 'adzuna'].includes(String(source || '').toLowerCase())
        ? 'Job-posting demand'
        : 'Demand signal';
    }
    return ({
      adoption: 'Developer adoption/activity',
      interest: 'Community or public interest'
    })[signalType] || 'Source-specific signal';
  };

  return `
    <section class="ts-answer-evidence" aria-label="${esc(title)}" style="display:flex; flex-direction:column; gap:8px; margin-top:10px; padding-top:8px; border-top:1px solid #E5E7EB;">
      <strong style="font-size:11px; text-transform:uppercase; color:#6B7280;">${esc(title)}</strong>
      ${validFacts.length ? `
        <div class="ts-answer-evidence__facts" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:6px;">
          ${validFacts.map(fact => {
            if (fact.fact_type === 'trend_analysis') {
              const details = fact.details || {};
              const source = details.provider || fact.source;
              const signalType = details.signal_type;
              const period = details.start_period && details.end_period
                ? `${details.start_period} to ${details.end_period}`
                : fact.period;
              return `
                <article class="ts-answer-evidence__fact ts-answer-evidence__trend" style="display:flex; flex-direction:column; gap:4px; background:#F9FAFB; border:1px solid #E5E7EB; border-radius:7px; padding:9px; font-size:11px;">
                  <strong>Observed skill trend · ${esc(fact.entity_name || 'Skill')}</strong>
                  <div>${esc(fact.metric_value == null ? 'Unavailable' : fact.metric_value)} ${esc(trendSignalLabel(signalType, source))}</div>
                  ${period ? `<small>Observation period: ${esc(period)}</small>` : ''}
                  ${fact.unit ? `<small>Measured rate unit: ${esc(fact.unit)}</small>` : ''}
                  ${fact.denominator != null ? `<small>Denominator: ${esc(fact.denominator)}${details.denominator_unit ? ` ${esc(details.denominator_unit)}` : ''}</small>` : ''}
                  ${source ? `<small>Source: ${esc(source)}</small>` : ''}
                  ${details.location || details.scope ? `<small>Scope: ${esc(details.location || details.scope)}</small>` : ''}
                  ${details.freshness_state ? `<small>Freshness: ${esc(details.freshness_state)}</small>` : ''}
                  ${details.history_complete === true ? '<small>History completeness: complete within the requested range</small>' : ''}
                  ${fact.calculation_version ? '<small>Method: Theil-Sen trend</small>' : ''}
                </article>
              `;
            }
            return `
              <article class="ts-answer-evidence__fact" style="display:flex; flex-direction:column; gap:3px; background:#F9FAFB; border:1px solid #E5E7EB; border-radius:7px; padding:8px; font-size:11px;">
                <strong>${esc(friendlyEvidenceLabel(fact.metric_name || fact.fact_type || 'Fact'))}</strong>
                <div>${fact.metric_value == null ? 'Unavailable' : esc(fact.metric_value)}${fact.metric_value != null && fact.unit ? ` ${esc(fact.unit)}` : ''}</div>
                <small>${esc(factKind(fact))}${fact.source ? ` · ${esc(fact.source)}` : ''}</small>
                ${fact.period ? `<small>Period: ${esc(fact.period)}</small>` : ''}
                ${fact.denominator != null ? `<small>Denominator: ${esc(fact.denominator)}${fact.denominator_unit ? ` ${esc(fact.denominator_unit)}` : ''}</small>` : ''}
                ${fact.readiness_state ? `<small>Readiness: ${esc(friendlyEvidenceLabel(fact.readiness_state))}</small>` : ''}
                ${fact.provenance_id ? `<small>Provenance: ${esc(fact.provenance_id)}</small>` : ''}
                ${fact.calculation_version ? `<small>Method: ${esc(fact.calculation_version)}</small>` : ''}
              </article>
            `;
          }).join('')}
        </div>
      ` : ''}
      ${validEvidence.length ? `
        <div class="ts-answer-evidence__citations" style="display:flex; flex-direction:column; gap:6px;">
          ${validEvidence.map(item => {
            const sourceUrl = safeSourceUrl(item.source_url);
            return `
              <article class="ts-answer-evidence__citation" style="display:flex; flex-direction:column; gap:3px; background:#FFFFFF; border:1px solid #E5E7EB; border-radius:7px; padding:8px; font-size:11px;">
                <strong>${esc(item.source || 'Source unavailable')}</strong>
                <span>${esc(item.measured_signal_type || item.signal_type || 'Signal unavailable')}${item.period ? ` · ${esc(item.period)}` : ''}${item.unit ? ` · ${esc(item.unit)}` : ''}</span>
                <p>${esc(item.description || '')}</p>
                <small>${item.data_origin ? `Origin: ${esc(item.data_origin)}` : ''}${item.history_type ? ` · History: ${esc(item.history_type)}` : ''}${item.series_id ? ` · Series: ${esc(item.series_id)}` : ''}${item.fetch_run_id ? ` · Fetch run: ${esc(item.fetch_run_id)}` : ''}${item.provenance_id ? ` · Provenance: ${esc(item.provenance_id)}` : ''}</small>
                ${item.freshness_state ? `<small>Freshness: ${esc(item.freshness_state)}</small>` : ''}
                ${item.supporting_fetch_run_ids?.length ? `<small>Collection runs: ${item.supporting_fetch_run_ids.map(esc).join(', ')}</small>` : ''}
                ${item.supporting_observation_ids?.length ? `<small>Observation records: ${item.supporting_observation_ids.map(esc).join(', ')}</small>` : ''}
                ${sourceUrl ? `<a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : ''}
                ${item.supporting_source_urls?.length ? item.supporting_source_urls.map(value => {
                  const supportingUrl = safeSourceUrl(value);
                  return supportingUrl
                    ? `<a href="${esc(supportingUrl)}" target="_blank" rel="noopener noreferrer">Open supporting source ↗</a>`
                    : '';
                }).join('') : ''}
              </article>
            `;
          }).join('')}
        </div>
      ` : ''}
      ${postings.length ? `
        <div class="ts-answer-evidence__postings" style="display:flex; flex-direction:column; gap:6px;">
          <strong>Skills listed in stored job postings</strong>
          ${postings.map(posting => {
            const sourceUrl = safeSourceUrl(posting.source_url);
            const skills = Array.isArray(posting.required_skills)
              ? posting.required_skills.filter(skill => typeof skill === 'string' && skill.trim())
              : [];
            return `
              <article style="display:flex; flex-direction:column; gap:3px; background:#FFFFFF; border:1px solid #E5E7EB; border-radius:7px; padding:8px; font-size:11px;">
                <strong>${esc(posting.title || 'Stored posting')}${posting.company ? ` · ${esc(posting.company)}` : ''}</strong>
                <span>${esc(posting.posting_date || 'Posting date unavailable')}${posting.location ? ` · ${esc(posting.location)}` : ''}</span>
                ${skills.length
                  ? `<p>Required skills: ${skills.map(esc).join(', ')}</p>`
                  : '<p>No structured required-skill list was recorded for this posting.</p>'}
                ${sourceUrl ? `<a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">View posting ↗</a>` : ''}
              </article>
            `;
          }).join('')}
        </div>
      ` : ''}
    </section>
  `;
}

/**
 * Standardized expandable evidence drawer
 */
export function renderEvidenceDrawer(evidence, turnIndex = 0) {
  if (!evidence || !evidence.length) return '';

  return `
    <div class="ts-evidence-drawer" style="margin-top:6px; border-top:1px solid rgba(0,0,0,0.06); padding-top:8px;">
      <button type="button" class="ts-evidence-toggle-btn" data-toggle="evidence" data-turn-index="${turnIndex}" style="background:none; border:none; padding:4px 0; font-size:11.5px; font-weight:600; color:#6B7280; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
        <i data-lucide="file-check-2" style="width:13px; height:13px; color:#059669;"></i>
        <span>Grounding Citations & Artifacts (${evidence.length})</span>
        <i data-lucide="chevron-down" style="width:12px; height:12px;"></i>
      </button>
      <div class="ts-evidence-list" id="evidenceList_${turnIndex}" style="display:none; flex-direction:column; gap:6px; margin-top:8px;">
        ${evidence.map(e => `
          <div style="background:#FFFFFF; border:1px solid #E5E7EB; border-radius:6px; padding:7px 10px; font-size:11.5px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
              <strong style="color:#374151;">${esc(e.source || e.title || 'Platform Store')}</strong>
              <span style="background:#F3F4F6; padding:1px 6px; border-radius:4px; font-size:10px; color:#4B5563; font-family:monospace;">
                ${esc(e.signal_type || e.type || 'reference')}${e.period ? ` · ${esc(e.period)}` : ''}
              </span>
            </div>
            <p style="margin:2px 0 4px; color:#4B5563; line-height:1.4;">${esc(e.description || e.text || '')}</p>
            <div style="font-size:10px; color:#9CA3AF; display:flex; gap:10px;">
              <span>Origin: <strong>${esc(e.data_origin || 'real')}</strong></span>
              <span>Quality: <strong style="color:#059669;">${esc(e.quality || 'valid')}</strong></span>
              ${e.evidence_id ? `<span>Ref: <code>${esc(e.evidence_id)}</code></span>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

/**
 * Standardized limitations and boundary notice
 */
export function renderLimitationsNotice(limitations, status = null) {
  if (!limitations || !limitations.length) return '';

  const isUnsupported = status === 'unsupported';
  const isInsufficient = status === 'insufficient_data';
  const bg = isUnsupported ? '#F3F4F6' : isInsufficient ? '#FEF3C7' : '#FFFBEB';
  const border = isUnsupported ? '#D1D5DB' : isInsufficient ? '#FCD34D' : '#FDE68A';
  const textColor = isUnsupported ? '#4B5563' : '#92400E';

  return `
    <div class="ts-limitations-notice" style="background:${bg}; border:1px solid ${border}; border-radius:8px; padding:8px 12px; font-size:11.5px; color:${textColor}; margin:6px 0;">
      <strong style="display:block; margin-bottom:2px;">
        <i data-lucide="${isUnsupported ? 'ban' : 'alert-circle'}" style="width:12px; height:12px; vertical-align:middle;"></i>
        ${isUnsupported ? 'Capability Boundary:' : 'Analytical Limitations & Scope:'}
      </strong>
      <ul style="margin:0; padding-left:16px;">
        ${limitations.map(lim => `<li>${esc(lim)}</li>`).join('')}
      </ul>
    </div>
  `;
}

/**
 * Standardized follow-up question chips
 */
export function renderFollowUpChips(followUps, attributeName = 'data-query') {
  if (!followUps || !followUps.length) return '';

  return `
    <div class="ts-follow-up-chips" style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
      ${followUps.map(fu => `
        <button type="button" class="ts-chip-btn" ${attributeName}="${esc(fu)}" style="display:inline-flex; align-items:center; gap:5px; background:#FFFFFF; border:1px solid #D1D5DB; border-radius:20px; padding:4px 10px; font-size:11.5px; color:#374151; cursor:pointer;">
          <i data-lucide="corner-down-right" style="width:11px; height:11px; color:#7C3AED;"></i>
          <span>${esc(fu)}</span>
        </button>
      `).join('')}
    </div>
  `;
}

/**
 * Standardized error state renderer
 */
export function renderIntelligenceErrorNotice({ error, portalType = 'individual', onRetry = null }) {
  const isAuth = error?.name === 'CoreIntelligenceAuthError' || error?.status === 401 || error?.status === 403;
  const isNetwork = error?.name === 'CoreIntelligenceNetworkError';

  let title = 'Core Intelligence Service Notice';
  let message = error?.message || 'The intelligence pipeline encountered an unexpected condition.';
  let icon = 'alert-triangle';
  let bg = '#FEF2F2';
  let border = '#FCA5A5';
  let color = '#B91C1C';

  if (isAuth) {
    title = portalType === 'company'
      ? 'Access Restricted: Enterprise Multi-Tenant Boundary'
      : 'Authentication Required';
    message = portalType === 'company'
      ? 'Enterprise workforce intelligence requires validated company organization credentials. Cross-company access is strictly prohibited.'
      : 'Please sign in to verify your session and access verified platform intelligence.';
    icon = 'lock';
  } else if (isNetwork) {
    title = 'Service Unavailable';
    message = 'The intelligence service is temporarily unavailable. Please try again shortly.';
    icon = 'wifi-off';
  }

  return `
    <div class="ts-error-notice" role="alert" style="background:${bg}; border:1px solid ${border}; border-radius:10px; padding:12px 16px; color:${color}; font-size:12.5px; margin:8px 0;">
      <div style="display:flex; align-items:center; gap:8px; font-weight:700; margin-bottom:4px;">
        <i data-lucide="${icon}" style="width:16px; height:16px;"></i>
        <span>${esc(title)}</span>
      </div>
      <p style="margin:0 0 6px 24px; line-height:1.45;">${esc(message)}</p>
    </div>
  `;
}
