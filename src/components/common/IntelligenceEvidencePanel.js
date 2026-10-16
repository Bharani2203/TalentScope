const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);

function statusLabel(status) {
  return String(status || 'unavailable').replaceAll('_', ' ');
}

function metricValue(metric) {
  if (metric.metric_value == null) return 'Unavailable';
  const value = typeof metric.metric_value === 'object'
    ? JSON.stringify(metric.metric_value)
    : String(metric.metric_value);
  return `${value}${metric.unit ? ` ${metric.unit}` : ''}`;
}

function renderMetric(metric) {
  const stale = ['stale', 'incomplete'].includes(metric.freshness_state);
  const metricStatus = stale ? metric.freshness_state : metric.status || 'unavailable';
  const hasValue = !stale && ['ready', 'partial'].includes(metricStatus) && metric.metric_value != null;
  const periods = Array.isArray(metric.observation_periods) ? metric.observation_periods : [];
  const urls = Array.isArray(metric.source_urls)
    ? metric.source_urls.filter(url => /^https?:\/\//i.test(String(url || '').trim()))
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

  return `<article class="intel-evidence-metric" data-status="${esc(metricStatus)}">
    <div class="intel-evidence-metric__heading">
      <strong>${esc(metric.metric_name || metric.capability || 'Metric')}</strong>
      <span class="intel-evidence-badge">${esc(statusLabel(metricStatus))}</span>
    </div>
    <div class="intel-evidence-metric__value">${hasValue ? esc(metricValue(metric)) : 'Unavailable'}</div>
    <div class="intel-evidence-meta">
      <span>${esc(label)}</span>
      ${metric.canonical_entity_id ? `<span>Entity: ${esc(metric.canonical_entity_id)}</span>` : ''}
      ${metric.series_id ? `<span>Series: ${esc(metric.series_id)}</span>` : ''}
      ${metric.source ? `<span>Source: ${esc(metric.source)}</span>` : ''}
      ${metric.signal_type ? `<span>Signal: ${esc(metric.signal_type)}</span>` : ''}
      ${metric.denominator != null ? `<span>Denominator: ${esc(metric.denominator)}${metric.denominator_unit ? ` ${esc(metric.denominator_unit)}` : ''}</span>` : ''}
      ${metric.period ? `<span>Period: ${esc(metric.period)}</span>` : ''}
      ${periods.length ? `<span>Observed periods: ${periods.map(esc).join(', ')}</span>` : ''}
      ${metric.latest_observed_at ? `<span>Last observed: ${esc(metric.latest_observed_at)}</span>` : ''}
      ${metric.freshness_state ? `<span>Freshness: ${esc(metric.freshness_state)}</span>` : ''}
      ${metric.readiness_state ? `<span>Readiness: ${esc(metric.readiness_state)}</span>` : ''}
      ${metric.method_version ? `<span>Method: ${esc(metric.method_version)}</span>` : ''}
      ${metric.query_id ? `<span>Query: ${esc(metric.query_id)}</span>` : ''}
    </div>
    ${provenance.length ? `<p class="intel-evidence-provenance">${provenance.map(esc).join(' · ')}</p>` : ''}
    ${urls.length ? `<p class="intel-evidence-links">${urls.map((url, index) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Source ${index + 1}</a>`).join(' · ')}</p>` : ''}
    ${metric.reason ? `<p class="intel-evidence-reason">${esc(metric.reason)}</p>` : ''}
    ${limitations.length ? `<ul class="intel-evidence-limitations">${limitations.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
  </article>`;
}

export function renderIntelligenceEvidencePanel(response, {
  title = 'Intelligence evidence',
  loading = false,
  error = null,
  metrics = null
} = {}) {
  const rawMetricItems = Array.isArray(metrics)
    ? metrics
    : Array.isArray(response?.metric_results) ? response.metric_results : [];
  const metricItems = rawMetricItems.map(metric => {
    const capability = response?.capabilities?.[metric.capability];
    const capabilityStatus = capability?.status || response?.[metric.capability]?.status;
    if (capabilityStatus && !['ready', 'partial'].includes(capabilityStatus)
      && ['ready', 'partial'].includes(metric.status)) {
      return {
        ...metric,
        status: 'unavailable',
        metric_value: null,
        reason: capability.reason || response?.[metric.capability]?.reason || 'The capability is not ready.'
      };
    }
    return metric;
  });
  const limitations = [
    ...(Array.isArray(response?.limitations) ? response.limitations : []),
    ...(Array.isArray(response?.blocking_reasons) ? response.blocking_reasons : []),
    ...(Array.isArray(response?.readiness?.blocking_reasons) ? response.readiness.blocking_reasons : [])
  ];
  const status = error ? 'error' : loading ? 'loading'
    : response?.data_state || response?.data_status || response?.status || 'unavailable';
  const message = error
    ? String(error)
    : loading
      ? 'Loading verified intelligence…'
      : response?.history_completeness_reason || response?.unavailable_reason || '';

  return `<section class="intel-evidence-panel" aria-label="${esc(title)}">
    <header class="intel-evidence-panel__header">
      <h3>${esc(title)}</h3>
      <span class="intel-evidence-badge" data-state="${esc(status)}">${esc(statusLabel(status))}</span>
    </header>
    ${message ? `<p class="intel-evidence-panel__message" role="${error ? 'alert' : 'status'}">${esc(message)}</p>` : ''}
    ${metricItems.length ? `<div class="intel-evidence-grid">${metricItems.map(renderMetric).join('')}</div>`
      : !loading && !error ? `<p class="intel-evidence-panel__message" role="status">${limitations.length
        ? 'No metric values are available for this response.'
        : 'The API did not return structured metric evidence for this response.'}</p>` : ''}
    ${limitations.length ? `<ul class="intel-evidence-panel__limitations">${[...new Set(limitations)].map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
    ${response?.forecast && response.forecast.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Forecast unavailable: ${esc(response.forecast.reason || response.forecast.readiness_state || response.forecast.status)}.</p>` : ''}
    ${response?.skill_health && response.skill_health.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Skill Health unavailable: ${esc(response.skill_health.reason || response.skill_health.status)}.</p>` : ''}
    ${response?.skill_half_life && response.skill_half_life.status !== 'ready'
      ? `<p class="intel-evidence-panel__message" role="status">Skill Half-Life unavailable: ${esc(response.skill_half_life.reason || response.skill_half_life.status)}.</p>` : ''}
  </section>`;
}
