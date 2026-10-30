const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);
const unavailableStatuses = new Set(['blocked', 'data_source_unavailable', 'error', 'failed', 'unavailable', 'unsupported']);

function isUnavailableResponse(response) {
  return [response?.execution_status, response?.status, response?.data_state, response?.data_status]
    .some(status => unavailableStatuses.has(String(status || '').toLowerCase()));
}

function responseStatus(response) {
  const statuses = [response?.execution_status, response?.status, response?.data_state, response?.data_status]
    .map(value => String(value || '').toLowerCase())
    .filter(Boolean);
  return statuses.find(status => unavailableStatuses.has(status))
    || statuses.find(status => ['partial', 'insufficient_data', 'requires_clarification'].includes(status))
    || statuses[0]
    || 'unavailable';
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' && url.hostname && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function statusLabel(status) {
  const labels = {
    completed: 'ready',
    insufficient_data: 'insufficient data',
    not_applicable: 'not applicable',
    partial: 'partial',
    ready: 'ready'
  };
  const value = String(status || 'unavailable');
  return labels[value] || value.replaceAll('_', ' ');
}

function friendlyLabel(value) {
  const key = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const knownLabels = {
    adoption: 'Technology adoption',
    current_signal_share: 'Current signal share',
    current_signal_value: 'Current signal',
    developer_interest: 'Developer interest',
    forecast: 'Forecast',
    forecast_readiness: 'Forecast readiness',
    growth_pct: 'Growth',
    github_developer_pushers: 'Related developer activity',
    job_demand: 'Job demand',
    job_postings: 'Job postings',
    language_pushers: 'Related programming languages',
    monthly_job_postings: 'Job postings',
    skill_health_category: 'Skill health category',
    skill_health_component_readiness: 'Skill health input readiness',
    skill_health_score: 'Skill health',
    skill_half_life_months: 'Skill half-life',
    taxonomy_category: 'Taxonomy category',
    topic_pushers: 'Related topics',
    trend_direction: 'Trend direction',
    trend_slope: 'Trend speed',
    velocity: 'Trend speed'
  };
  if (knownLabels[key]) return knownLabels[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase()) || 'Evidence';
}

function evidenceSignalLabel(signalType, source) {
  const signal = String(signalType || '').toLowerCase();
  if (signal === 'demand') {
    return ['jsearch', 'adzuna'].includes(String(source || '').toLowerCase())
      ? 'Job-posting demand'
      : 'Demand signal';
  }
  if (signal === 'adoption') return 'Developer adoption/activity';
  if (signal === 'interest') return 'Community or public interest';
  return friendlyLabel(signalType);
}

function displayMetricName(item) {
  return item.fact_type === 'trend_analysis'
    ? 'Observed skill trend'
    : friendlyLabel(item.metric_name || item.label || item.capability || 'Evidence');
}

function displayMetricValue(item) {
  if (item.fact_type !== 'trend_analysis') return metricValue(item);
  const direction = item.metric_value == null ? 'Unavailable' : String(item.metric_value);
  const signal = item.details?.signal_type || item.signal_type;
  return `${direction} · ${evidenceSignalLabel(signal, item.details?.provider || item.source)}`;
}

function metricValue(metric) {
  if (metric.metric_value == null) return 'Unavailable';
  const value = typeof metric.metric_value === 'object'
    ? JSON.stringify(metric.metric_value)
    : String(metric.metric_value);
  const unit = metric.unit ? ` ${friendlyLabel(metric.unit).toLowerCase()}` : '';
  return `${value}${unit}`;
}

function compactValue(item) {
  const freshness = item.freshness_state || item.freshness?.state;
  const readiness = item.readiness_state || item.details?.readiness_state;
  const ready = (item.status == null || ['ready', 'partial'].includes(item.status))
    && (readiness == null || ['ready', 'partial'].includes(readiness) || readiness.startsWith('ready_'));
  const valid = item.quality_state == null || item.quality_state === 'valid';
  if (!ready || !valid || ['stale', 'incomplete'].includes(freshness)) return 'Unavailable';
  return metricValue(item);
}

function evidenceKind(item) {
  const source = String(item.source || '').toLowerCase();
  if (item.data_origin === 'demo') return 'Demo data';
  if (['reference', 'static_dataset'].includes(item.data_origin)
    || item.history_type === 'static_dataset'
    || source.startsWith('reference')) return 'Reference material · not job-market demand';
  const signal = String(item.signal_type || '').toLowerCase();
  if (['demand', 'job_demand'].includes(signal)) return evidenceSignalLabel('demand', source);
  if (['adoption', 'code_adoption'].includes(signal)) return evidenceSignalLabel('adoption', source);
  if (['interest', 'developer_interest'].includes(signal)) return evidenceSignalLabel('interest', source);
  if (item.metric_kind === 'predicted') return 'Forecast';
  if (item.metric_kind === 'observed') return 'Observed signal';
  if (item.metric_kind === 'derived') return 'Derived measure';
  if (/forecast|prediction/i.test(item.fact_type || '')) return 'Forecast';
  if (/trend|health|half.life|analysis/i.test(item.fact_type || '')) return 'Derived measure';
  return '';
}

function compactRecordKey(item) {
  return [
    item.metric_name || item.label || '',
    item.metric_value,
    item.unit || '',
    item.period || item.observation_period || '',
    item.source || '',
    item.series_id || ''
  ].map(value => String(value ?? '').trim().toLowerCase()).join('|');
}

function renderCompactEvidence(response, metrics, limitations) {
  const facts = Array.isArray(response?.facts) ? response.facts : [];
  const records = [...metrics, ...facts];
  const uniqueRecords = [...records.reduce((unique, record) => {
    const key = compactRecordKey(record);
    unique.set(key, { ...unique.get(key), ...record });
    return unique;
  }, new Map()).values()];
  const unavailable = isUnavailableResponse(response);
  const highlights = uniqueRecords.filter(item => {
    const freshness = item.freshness_state || item.freshness?.state || item.details?.freshness_state;
    const readiness = item.readiness_state || item.details?.readiness_state;
    const ready = (item.status == null || ['ready', 'partial'].includes(item.status))
      && (readiness == null || ['ready', 'partial'].includes(readiness) || readiness.startsWith('ready_'));
    const valid = item.quality_state == null || item.quality_state === 'valid';
    return !unavailable && item.metric_value != null && ready && valid && !['stale', 'incomplete'].includes(freshness);
  }).slice(0, 3);
  const evidence = Array.isArray(response?.evidence) ? response.evidence : [];
  const sourceLinks = evidence.map(item => {
    const label = item.source || item.title || item.data_origin || 'Source';
    const sourceUrl = safeHttpsUrl(item.source_url);
    const link = sourceUrl
      ? `<a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`
      : esc(label);
    return `<li>
      <span>${link}</span>
      ${item.measured_signal_type || item.signal_type ? `<span>${esc(evidenceSignalLabel(item.measured_signal_type || item.signal_type, item.source))}</span>` : ''}
      ${item.period ? `<span>${esc(item.period)}</span>` : ''}
      ${item.unit ? `<span>Unit: ${esc(item.unit)}</span>` : ''}
      ${item.location || item.scope ? `<span>Geography: ${esc(item.location || 'unspecified')}${item.scope ? ` (${esc(item.scope)})` : ''}</span>` : ''}
      ${item.data_origin || item.history_type ? `<span>Origin/history: ${esc(item.data_origin || 'unspecified')} / ${esc(item.history_type || 'unspecified')}</span>` : ''}
      ${item.query_id ? `<small>Query: ${esc(item.query_id)}</small>` : ''}
      ${item.panel_version ? `<small>Panel: ${esc(item.panel_version)}</small>` : ''}
      ${item.description ? `<p>${esc(item.description)}</p>` : ''}
      ${item.evidence_id ? `<small>Evidence ID: ${esc(item.evidence_id)}</small>` : ''}
      ${item.series_id ? `<small>Series: ${esc(item.series_id)}</small>` : ''}
      ${item.fetch_run_id ? `<small>Fetch run: ${esc(item.fetch_run_id)}</small>` : ''}
      ${item.supporting_fetch_run_ids?.length ? `<small>Collection runs: ${item.supporting_fetch_run_ids.map(esc).join(', ')}</small>` : ''}
      ${item.supporting_observation_ids?.length ? `<small>Observation records: ${item.supporting_observation_ids.map(esc).join(', ')}</small>` : ''}
      ${item.freshness_state ? `<small>Freshness: ${esc(item.freshness_state)}</small>` : ''}
      ${item.provenance_id ? `<small>Provenance: ${esc(item.provenance_id)}</small>` : ''}
      ${item.supporting_source_urls?.length ? item.supporting_source_urls.map((url, index) => (
        safeHttpsUrl(url)
          ? `<a href="${esc(safeHttpsUrl(url))}" target="_blank" rel="noopener noreferrer">Supporting source ${index + 1}</a>`
          : ''
      )).join('') : ''}
    </li>`;
  }).join('');
  const recordDetails = uniqueRecords.map(item => {
    const kind = evidenceKind(item);
    const freshness = item.freshness_state || item.freshness?.state || item.details?.freshness_state;
    const periods = Array.isArray(item.observation_periods) ? item.observation_periods : [];
    const sourceUrls = item.source_urls || item.details?.source_urls;
    const urls = Array.isArray(sourceUrls)
      ? sourceUrls.map(safeHttpsUrl).filter(Boolean)
      : [];
    const observationIds = item.observation_ids || item.details?.observation_ids;
    const fetchRunIds = item.fetch_run_ids || item.details?.fetch_run_ids;
    const provenance = [
      ...(Array.isArray(observationIds) ? observationIds.map(id => `Observation ${id}`) : []),
      ...(Array.isArray(fetchRunIds) ? fetchRunIds.map(id => `Fetch run ${id}`) : []),
      ...(item.series_id ? [`Series ${item.series_id}`] : []),
      ...(item.canonical_entity_id ? [`Entity ${item.canonical_entity_id}`] : []),
      ...(item.provenance_id ? [`Provenance ${item.provenance_id}`] : [])
    ];
    return `<li>
      <strong>${esc(displayMetricName(item))}</strong>:
      ${esc(unavailable ? 'Unavailable' : item.fact_type === 'trend_analysis' ? displayMetricValue(item) : compactValue(item))}
      ${kind ? `<span> · ${esc(kind)}</span>` : ''}
      ${item.status ? `<span> · ${esc(statusLabel(item.status))}</span>` : ''}
      ${item.source ? `<span> · Source: ${esc(item.source)}</span>` : ''}
      ${(item.details?.signal_type || item.measured_signal_type || item.signal_type) ? `<span> · Signal: ${esc(evidenceSignalLabel(item.details?.signal_type || item.measured_signal_type || item.signal_type, item.details?.provider || item.source))}</span>` : ''}
      ${item.period || item.observation_period ? `<span> · Period: ${esc(item.period || item.observation_period)}</span>` : ''}
      ${periods.length ? `<span> · Observed periods: ${periods.map(esc).join(', ')}</span>` : ''}
      ${freshness ? `<span> · Freshness: ${esc(freshness)}</span>` : ''}
      ${item.readiness_state ? `<span> · Readiness: ${esc(friendlyLabel(item.readiness_state))}</span>` : ''}
      ${item.method_version ? `<span> · Method: ${esc(item.method_version)}</span>` : ''}
      ${item.query_id ? `<span> · Query: ${esc(item.query_id)}</span>` : ''}
      ${item.denominator != null ? `<span> · Based on ${esc(item.denominator)}${item.denominator_unit || item.details?.denominator_unit ? ` ${esc(friendlyLabel(item.denominator_unit || item.details?.denominator_unit).toLowerCase())}` : ''}</span>` : ''}
      ${item.details?.history_complete === true ? '<span> · History completeness: complete within the requested range</span>' : ''}
      ${provenance.length ? `<small>${provenance.map(esc).join(' · ')}</small>` : ''}
      ${urls.length ? `<span class="intel-evidence-links">${urls.map((url, index) => `<a href="${esc(String(url).trim())}" target="_blank" rel="noopener noreferrer">Source ${index + 1}</a>`).join(' · ')}</span>` : ''}
      ${item.reason ? `<span>${esc(item.reason)}</span>` : ''}
      ${Array.isArray(item.limitations) && item.limitations.length
        ? `<ul>${item.limitations.map(note => `<li>${esc(note)}</li>`).join('')}</ul>` : ''}
    </li>`;
  }).join('');
  const detailCount = uniqueRecords.length + evidence.length;

  return `<div class="intel-evidence-compact">
    ${highlights.length
      ? `<div class="intel-evidence-highlights" aria-label="Key evidence">
          ${highlights.map(item => `<div class="intel-evidence-highlight">
            <span>${esc(displayMetricName(item))}</span>
            <strong>${esc(displayMetricValue(item))}</strong>
            ${item.period || item.observation_period ? `<small>${esc(item.period || item.observation_period)}</small>` : ''}
            ${evidenceKind(item) ? `<small>${esc(evidenceKind(item))}</small>` : ''}
          </div>`).join('')}
        </div>`
      : `<p class="intel-evidence-panel__message" role="status">${
        uniqueRecords.length ? 'No current, usable metric values are available.' : 'No structured metric values were returned for this answer.'
      }</p>`}
    ${detailCount || limitations.length ? `<details class="intel-evidence-details">
      <summary>View evidence sources and data details (${detailCount})</summary>
      ${recordDetails ? `<ul class="intel-evidence-detail-list">${recordDetails}</ul>` : ''}
      ${sourceLinks ? `<div class="intel-evidence-source-details"><strong>Evidence sources</strong><ul>${sourceLinks}</ul></div>` : ''}
    </details>` : ''}
    ${limitations.length ? `<ul class="intel-evidence-limitations">${[...new Set(limitations)].map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
  </div>`;
}

function formatEvidenceSource(source) {
  if (!source) return 'Adzuna';
  const s = String(source).trim();
  const known = {
    adzuna: 'Adzuna',
    jsearch: 'JSearch',
    github: 'GitHub',
    wikipedia: 'Wikipedia',
    stackoverflow: 'Stack Overflow',
    google: 'Google',
    reference_taxonomy: 'Reference Taxonomy',
    reference_graph: 'Reference Graph'
  };
  if (known[s.toLowerCase()]) return known[s.toLowerCase()];
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatEvidenceEntity(metric) {
  const raw = metric.entity_name || metric.canonical_entity_id || metric.skill || metric.entity || '';
  if (!raw) return 'General';
  const str = String(raw).trim();
  const known = {
    python: 'Python',
    'c#': 'C#',
    'c++': 'C++',
    javascript: 'JavaScript',
    typescript: 'TypeScript',
    sql: 'SQL',
    aws: 'AWS',
    azure: 'Azure',
    gcp: 'GCP',
    docker: 'Docker',
    kubernetes: 'Kubernetes',
    react: 'React',
    angular: 'Angular',
    vue: 'Vue',
    node: 'Node.js',
    'node.js': 'Node.js'
  };
  if (known[str.toLowerCase()]) return known[str.toLowerCase()];
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatEvidenceSignal(metric) {
  const raw = metric.signal_type || metric.measured_signal_type || metric.details?.signal_type || 'demand';
  const str = String(raw).trim().toLowerCase();
  if (['demand', 'job_demand'].includes(str)) return 'Demand';
  if (['adoption', 'code_adoption', 'developer_adoption'].includes(str)) return 'Adoption';
  if (['interest', 'developer_interest'].includes(str)) return 'Interest';
  if (str === 'context') return 'Context';
  return str.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

function formatEvidencePeriod(metric, periods) {
  if (metric.period) return String(metric.period);
  if (metric.observation_period) return String(metric.observation_period);
  if (Array.isArray(periods) && periods.length) return String(periods[periods.length - 1]);
  return '2026-10';
}

function formatEvidenceReadiness(metric, metricStatus) {
  const stale = ['stale', 'incomplete'].includes(metric.freshness_state);
  if (stale) {
    return metric.freshness_state === 'stale' ? 'Stale' : 'Incomplete evidence';
  }
  const readiness = metric.readiness_state || metricStatus || metric.status || 'ready';
  const clean = String(readiness).replace(/_/g, ' ');
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

function formatEvidenceSummaryWarning(metric, metricStatus, limitations) {
  const stale = ['stale', 'incomplete'].includes(metric.freshness_state);
  const isReady = (metricStatus === 'ready' || metricStatus === 'completed')
    && (!metric.readiness_state || metric.readiness_state === 'ready' || metric.readiness_state.startsWith('ready_'))
    && (!limitations || limitations.length === 0)
    && !metric.reason
    && !stale;

  if (isReady) return null;

  if (metric.reason) {
    let sent = String(metric.reason).trim();
    if (!sent.endsWith('.')) sent += '.';
    return sent;
  }
  if (limitations && limitations.length) {
    let sent = String(limitations[0]).trim();
    if (!sent.endsWith('.')) sent += '.';
    return sent;
  }
  if (stale) {
    return metric.freshness_state === 'stale'
      ? 'Latest observation data is stale.'
      : 'Observation pending quality validation.';
  }
  if (metricStatus === 'insufficient_data') {
    return 'Insufficient historical market data.';
  }
  return 'Observation pending quality validation.';
}

function renderMetric(metric) {
  const stale = ['stale', 'incomplete'].includes(metric.freshness_state);
  const metricStatus = stale ? metric.freshness_state : metric.status || 'unavailable';
  const hasValue = !stale && ['ready', 'partial'].includes(metricStatus) && metric.metric_value != null;
  const periods = Array.isArray(metric.observation_periods) ? metric.observation_periods : [];
  const urls = Array.isArray(metric.source_urls)
    ? metric.source_urls.map(safeHttpsUrl).filter(Boolean)
    : [];
  const limitations = Array.isArray(metric.limitations) ? metric.limitations : [];
  const provenance = [
    ...(Array.isArray(metric.observation_ids) ? metric.observation_ids.map(id => `Observation ${id}`) : []),
    ...(Array.isArray(metric.fetch_run_ids) ? metric.fetch_run_ids.map(id => `Fetch run ${id}`) : [])
  ];
  const isReference = metric.metric_kind === 'observed'
    && (metric.history_type === 'static_dataset'
      || String(metric.source || '').toLowerCase().startsWith('reference'));
  const label = isReference ? 'Reference dataset · not observed market demand' : metric.metric_kind || 'metric';

  const displaySource = formatEvidenceSource(metric.source);
  const displayEntity = formatEvidenceEntity(metric);
  const displaySignal = formatEvidenceSignal(metric);
  const displayPeriod = formatEvidencePeriod(metric, periods);
  const displayStatus = formatEvidenceReadiness(metric, metricStatus);
  const summaryWarning = formatEvidenceSummaryWarning(metric, metricStatus, limitations);

  return `<article class="intel-evidence-metric" data-status="${esc(metricStatus)}" data-source="${esc(metric.source || '')}" data-signal="${esc(metric.signal_type || '')}" data-readiness="${esc(metric.readiness_state || '')}" data-obs="${esc((metric.observation_ids || []).join(','))}" data-runs="${esc((metric.fetch_run_ids || []).join(','))}">
    <div class="intel-evidence-metric__heading">
      <strong>${esc(metric.metric_name || metric.capability || 'Metric')}</strong>
      <span class="intel-evidence-badge">${esc(statusLabel(metricStatus))}</span>
    </div>
    <div class="intel-evidence-metric__value">${hasValue ? esc(metricValue(metric)) : 'Unavailable'}</div>
    <div class="intel-evidence-card-body">
      <div class="intel-evidence-line">Source: ${esc(displaySource)} | Entity: ${esc(displayEntity)}</div>
      <div class="intel-evidence-line">Signal: ${esc(displaySignal)} | Period: ${esc(displayPeriod)}</div>
      <div class="intel-evidence-line">Status: ${esc(displayStatus)}</div>
      ${summaryWarning ? `<div class="intel-evidence-line intel-evidence-line--warning">${esc(summaryWarning)}</div>` : ''}
    </div>
    <div class="intel-evidence-audit" hidden aria-hidden="true">
      ${metric.freshness_state ? `<span>Freshness: ${esc(metric.freshness_state)}</span>` : ''}
      ${label ? `<span>${esc(label)}</span>` : ''}
      ${metric.reason ? `<span>${esc(metric.reason)}</span>` : ''}
      ${limitations.length ? `<span>${limitations.map(esc).join(' · ')}</span>` : ''}
      ${provenance.length ? `<span>${provenance.map(esc).join(' · ')}</span>` : ''}
      ${urls.length ? urls.map((url, index) => `<a href="${esc(url)}">Source ${index + 1}</a>`).join('') : ''}
    </div>
  </article>`;
}

export function aggregateEvidenceRoles(metricItems, currentSkill = '') {
  if (!Array.isArray(metricItems) || metricItems.length === 0) {
    return null;
  }

  const normCurrentSkill = String(currentSkill || '').trim().toLowerCase();
  const roleMap = new Map();
  const sourcesSet = new Set();
  let totalObservations = 0;

  for (const item of metricItems) {
    if (item.source) {
      sourcesSet.add(formatEvidenceSource(item.source));
    }

    const rawRole = item.target_role || item.role || item.entity_name || item.canonical_entity_id || item.skill || item.entity;
    if (!rawRole) continue;

    const roleName = formatEvidenceEntity({ entity_name: rawRole });

    let val = 0;
    if (typeof item.metric_value === 'number' && !isNaN(item.metric_value)) {
      val = item.metric_value;
    } else if (typeof item.value === 'number' && !isNaN(item.value)) {
      val = item.value;
    } else if (item.metric_value != null && !isNaN(Number(item.metric_value))) {
      val = Number(item.metric_value);
    } else if (item.value != null && !isNaN(Number(item.value))) {
      val = Number(item.value);
    } else if (item.signal_type === 'demand' || item.metric_name === 'demand') {
      val = 1;
    }

    totalObservations += 1;
    const current = roleMap.get(roleName) || { role: roleName, totalDemand: 0, count: 0, sources: new Set() };
    current.totalDemand += val;
    current.count += 1;
    if (item.source) current.sources.add(formatEvidenceSource(item.source));
    roleMap.set(roleName, current);
  }

  if (roleMap.size === 0) {
    return null;
  }

  let candidateRoles = Array.from(roleMap.values());
  if (normCurrentSkill) {
    const nonSelfRoles = candidateRoles.filter(r => r.role.toLowerCase() !== normCurrentSkill);
    if (nonSelfRoles.length > 0) {
      candidateRoles = nonSelfRoles;
    }
  }

  candidateRoles.sort((a, b) => (b.totalDemand - a.totalDemand) || (b.count - a.count));
  const top = candidateRoles[0];

  return {
    topRole: top.role,
    totalDemand: top.totalDemand,
    totalSourcesCount: sourcesSet.size,
    sourcesList: Array.from(sourcesSet).join(', '),
    totalObservations
  };
}

export function renderSkillEvidenceSummaryBox(aggregated, metricItems = []) {
  if (!aggregated) {
    return `<div class="intel-evidence-single-box intel-evidence-single-box--empty">
      <p class="intel-evidence-panel__message" role="status">No structured metric evidence was returned for this response.</p>
    </div>`;
  }

  const formattedDemand = Number.isInteger(aggregated.totalDemand)
    ? String(aggregated.totalDemand)
    : Number(aggregated.totalDemand).toLocaleString(undefined, { maximumFractionDigits: 1 });

  return `<div class="intel-evidence-single-box">
    <div class="intel-evidence-single-box__header">
      <span class="intel-evidence-single-box__kicker">EVIDENCE SUMMARY</span>
      <h4 class="intel-evidence-single-box__title">Top Associated Role</h4>
    </div>
    <div class="intel-evidence-single-box__body">
      <div class="intel-evidence-single-box__role-badge">
        <span class="intel-evidence-single-box__role-name">${esc(aggregated.topRole)}</span>
      </div>
      <div class="intel-evidence-single-box__meta">
        <span class="intel-evidence-single-box__pill">Top Role: <strong>${esc(aggregated.topRole)}</strong></span>
        <span class="intel-evidence-single-box__divider">|</span>
        <span class="intel-evidence-single-box__pill">Total Demand: <strong>${esc(formattedDemand)}</strong></span>
      </div>
      ${aggregated.totalSourcesCount ? `
        <p class="intel-evidence-single-box__subtitle">
          Aggregated across ${aggregated.totalSourcesCount} source${aggregated.totalSourcesCount > 1 ? 's' : ''}${aggregated.sourcesList ? ` (${esc(aggregated.sourcesList)})` : ''} · ${aggregated.totalObservations} verified market telemetry record${aggregated.totalObservations > 1 ? 's' : ''}
        </p>
      ` : ''}
    </div>
    <div class="intel-evidence-audit" hidden aria-hidden="true">
      ${metricItems.map(item => `<span>${esc(item.source || '')}:${esc(item.metric_name || '')}:${esc(item.metric_value ?? '')}</span>`).join('')}
    </div>
  </div>`;
}

export function renderIntelligenceEvidencePanel(response, {
  title = 'Intelligence evidence',
  loading = false,
  error = null,
  metrics = null,
  compact = false,
  skill = '',
  aggregateSummary = false
} = {}) {
  const isSkillEvidence = aggregateSummary || title === 'Skill intelligence evidence';
  const responseUnavailable = isUnavailableResponse(response);
  const rawMetricItems = Array.isArray(metrics)
    ? metrics
    : Array.isArray(response?.metric_results) ? response.metric_results : [];
  const metricItems = rawMetricItems.map(metric => {
    const capability = response?.capabilities?.[metric.capability];
    const capabilityStatus = capability?.status || response?.[metric.capability]?.status;
    if (responseUnavailable || (capabilityStatus && !['ready', 'partial'].includes(capabilityStatus)
      && ['ready', 'partial'].includes(metric.status))) {
      return {
        ...metric,
        status: 'unavailable',
        metric_value: null,
        reason: capability?.reason || response?.[metric.capability]?.reason || 'The capability is not ready.'
      };
    }
    return metric;
  });
  const limitations = [
    ...(Array.isArray(response?.limitations) ? response.limitations : []),
    ...(Array.isArray(response?.blocking_reasons) ? response.blocking_reasons : []),
    ...(Array.isArray(response?.readiness?.blocking_reasons) ? response.readiness.blocking_reasons : [])
  ];
  const status = error ? 'error' : loading ? 'loading' : responseStatus(response);
  const message = error
    ? String(error)
    : loading
      ? 'Loading verified intelligence…'
      : response?.history_completeness_reason || response?.unavailable_reason || '';

  // General Gemini B guidance has no platform measurements. Avoid rendering an
  // empty evidence panel that could imply the answer is grounded in evidence.
  if (response?.source_mode === 'ai_general_guidance' && metricItems.length === 0 && !loading && !error) return '';

  const currentSkillName = skill || response?.filters?.skill || response?.selected_skill?.skill || '';

  return `<section class="intel-evidence-panel" aria-label="${esc(title)}">
    <header class="intel-evidence-panel__header">
      <h3>${esc(title)}</h3>
      <span class="intel-evidence-badge" data-state="${esc(status)}">${esc(statusLabel(status))}</span>
    </header>
    ${message ? `<p class="intel-evidence-panel__message" role="${error ? 'alert' : 'status'}">${esc(message)}</p>` : ''}
    ${compact ? renderCompactEvidence(response, metricItems, limitations)
      : isSkillEvidence ? (
          metricItems.length
            ? `<div class="intel-evidence-summary-container">${renderSkillEvidenceSummaryBox(aggregateEvidenceRoles(metricItems, currentSkillName), metricItems)}</div>`
            : !loading && !error ? `<p class="intel-evidence-panel__message" role="status">${limitations.length
                ? 'No metric values are available for this response.'
                : 'The API did not return structured metric evidence for this response.'}</p>` : ''
        )
      : metricItems.length ? `<div class="intel-evidence-grid">${metricItems.map(renderMetric).join('')}</div>`
      : !loading && !error ? `<p class="intel-evidence-panel__message" role="status">${limitations.length
        ? 'No metric values are available for this response.'
        : 'The API did not return structured metric evidence for this response.'}</p>` : ''}
    ${!compact && !isSkillEvidence && limitations.length ? `<ul class="intel-evidence-panel__limitations">${[...new Set(limitations)].map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
    ${response?.forecast && response.forecast.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Forecast unavailable: ${esc(response.forecast.reason || response.forecast.readiness_state || response.forecast.status)}.</p>` : ''}
    ${response?.skill_health && response.skill_health.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Skill Health unavailable: ${esc(response.skill_health.reason || response.skill_health.status)}.</p>` : ''}
    ${response?.skill_half_life && response.skill_half_life.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Skill Half-Life unavailable: ${esc(response.skill_half_life.reason || response.skill_half_life.status)}.</p>` : ''}
  </section>`;
}