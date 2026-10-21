const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[char]);

const list = value => Array.isArray(value) ? value : [];
const text = value => typeof value === 'string' ? value.trim() : '';
const humanize = value => text(value).replaceAll('_', ' ') || 'unknown';

function renderSkillGap(fact) {
  const details = fact.details || {};
  const matched = list(details.matched);
  const missing = list(details.missing);
  const unmatched = list(details.unmatched_user);
  const unresolved = list(details.unresolved_user);
  const taxonomy = text(details.taxonomy) || 'unspecified taxonomy';
  const numerator = details.coverage_numerator ?? details.matched_reference_count ?? matched.length;
  const denominator = details.reference_count ?? fact.denominator;
  const percent = details.coverage_percent ?? (typeof fact.metric_value === 'number' ? fact.metric_value * 100 : null);
  const roadmap = details.learning_roadmap || {};
  const steps = list(roadmap.steps);
  const groups = [
    ['Essential reference gaps', missing.filter(item => item.classification === 'essential')],
    ['Optional reference gaps', missing.filter(item => item.classification === 'optional')],
    ['Unclassified reference gaps', missing.filter(item => !['essential', 'optional'].includes(item.classification))]
  ].filter(([, items]) => items.length);
  const taxonomyId = text(fact.canonical_entity_id) || text(details.occupation?.concept_uri) || text(details.occupation?.id);
  const matchedMarkup = matched.length
    ? `<ul>${matched.map(item => `<li><strong>${esc(item.label || item.resolved_label || item.user_text || item.original_text)}</strong>${item.match_method ? ` <small>(${esc(item.match_method)})</small>` : ''}${item.taxonomy_id ? `<small class="ts-intel-id">${esc(item.taxonomy_id)}</small>` : ''}</li>`).join('')}</ul>`
    : '<p class="ts-intel-muted">No supplied skill labels matched the selected reference set.</p>';
  const gapMarkup = groups.length
    ? groups.map(([heading, items]) => `<div class="ts-intel-skill-group"><h4>${esc(heading)}</h4><ul>${items.map(item => `<li><strong>${esc(item.label)}</strong>${item.taxonomy_id ? `<small class="ts-intel-id">${esc(item.taxonomy_id)}</small>` : ''}</li>`).join('')}</ul></div>`).join('')
    : '<p class="ts-intel-muted">No missing reference skills were identified in this comparison.</p>';
  const roadmapMarkup = steps.length
    ? `<ol class="ts-intel-roadmap">${steps.map(step => `<li class="ts-intel-roadmap-step">
        <div class="ts-intel-roadmap-heading"><span>Step ${esc(step.priority ?? '')}</span><strong>${esc(step.target_skill)}</strong><small>${esc(step.priority_group || 'unranked reference gap')}</small></div>
        ${step.why_relevant ? `<p><b>Why:</b> ${esc(step.why_relevant)}</p>` : ''}
        ${step.suggested_task ? `<p><b>Practice task:</b> ${esc(step.suggested_task)}</p>` : ''}
        ${step.tangible_outcome ? `<p><b>Expected outcome:</b> ${esc(step.tangible_outcome)}</p>` : ''}
        ${step.self_check_criterion ? `<p><b>Self-check:</b> ${esc(step.self_check_criterion)}</p>` : ''}
        <small class="ts-intel-muted">Suggested practice only · progress ${esc(humanize(step.progress_state || 'not tracked'))} · proficiency ${step.proficiency_verified === true ? 'verified' : 'not verified'}</small>
      </li>`).join('')}</ol><p class="ts-intel-muted">These are generated practice suggestions, not verified courses. Progress persistence: ${esc(humanize(roadmap.progress_persistence || 'not configured'))}.</p>`
    : '';
  const unaligned = [...unmatched, ...unresolved].map(item => text(item.original_text || item.user_text)).filter(Boolean);
  const limitations = list(roadmap.limitations);
  return `<section class="ts-intel-result-card" aria-label="Personalized skill gap">
    <header><div><span class="ts-intel-kicker">${esc(taxonomy)} reference comparison</span><h3>Skill gap for ${esc(fact.entity_name || details.occupation?.label || 'selected occupation')}</h3></div>${percent != null ? `<strong class="ts-intel-coverage">${esc(Number(percent).toFixed(percent % 1 ? 1 : 0))}%<small>reference coverage</small></strong>` : ''}</header>
    <p class="ts-intel-meta">Coverage: ${esc(numerator)} of ${esc(denominator ?? 'unknown')} distinct applicable reference skills · numerator counts distinct matched taxonomy identities.</p>
    ${taxonomyId ? `<p class="ts-intel-meta">Occupation/reference ID: <code>${esc(taxonomyId)}</code></p>` : ''}
    <div class="ts-intel-result-columns"><table class="ts-intel-comparison-table" aria-label="Matched skills compared with reference gaps">
      <thead><tr><th scope="col">Matched skills</th><th scope="col">Reference gaps</th></tr></thead>
      <tbody><tr><td>${matchedMarkup}</td><td>${gapMarkup}</td></tr></tbody>
    </table></div>
    ${unaligned.length ? `<div class="ts-intel-unmatched"><h4>Unmatched or ambiguous supplied skills</h4><p>${unaligned.map(esc).join(', ')}</p></div>` : ''}
    ${details.coverage_formula ? `<p class="ts-intel-meta">Method: ${esc(details.coverage_formula)}</p>` : ''}
    ${details.proficiency_note || details.interpretation ? `<p class="ts-intel-disclaimer">${esc(details.interpretation || details.proficiency_note)}</p>` : ''}
    ${roadmapMarkup}
    ${limitations.length ? `<ul class="ts-intel-limitations">${limitations.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
  </section>`;
}

function renderReferences(facts) {
  const references = facts.filter(fact => fact.history_type === 'reference_taxonomy'
    && !['personalized_skill_gap', 'skill_gap', 'learning_roadmap_step', 'action_recommendation', 'learning_recommendation_summary', 'learning_recommendation_readiness'].includes(fact.fact_type));
  if (!references.length) return '';
  return `<section class="ts-intel-result-card" aria-label="Reference entities"><h3>Reference entries</h3><ul class="ts-intel-reference-list">${references.map(fact => `<li><strong>${esc(fact.entity_name || 'Reference entry')}</strong><span>${esc(fact.source || 'Taxonomy source')}${fact.details?.taxonomy ? ` · ${esc(fact.details.taxonomy)}` : ''}</span>${fact.canonical_entity_id ? `<code>${esc(fact.canonical_entity_id)}</code>` : ''}${fact.provenance_id && fact.provenance_id !== fact.canonical_entity_id ? `<small>Provenance: ${esc(fact.provenance_id)}</small>` : ''}${fact.details?.source_version ? `<small>Version: ${esc(fact.details.source_version)}</small>` : ''}</li>`).join('')}</ul></section>`;
}

function renderActionRecommendations(facts, evidence, limitations) {
  const recommendations = facts.filter(fact => fact.fact_type === 'action_recommendation');
  const readiness = facts.filter(fact => fact.fact_type === 'learning_recommendation_readiness');
  if (!recommendations.length && !readiness.length) return '';
  const evidenceById = new Map(list(evidence).map(item => [item.evidence_id, item]));
  const items = recommendations.slice(0, 5).map(fact => {
    const details = fact.details || {};
    const sourceEvidence = evidenceById.get(fact.evidence_reference);
    const title = details.action_title || fact.entity_name || fact.metric_value || 'Practice priority';
    const classificationText = details.classification === 'essential' && details.taxonomy === 'esco'
      ? 'essential ESCO relationship'
      : (details.classification ? `${details.classification} priority` : '');
    const practiceText = details.suggested_action || details.next_action;
    return `<li><strong>${esc(title)}</strong>
      ${classificationText ? `<small>${esc(classificationText)}</small>` : ''}
      ${details.reason ? `<p><b>Why:</b> ${esc(details.reason)}</p>` : ''}
      ${details.next_action && details.suggested_action ? `<p><b>Next step:</b> ${esc(details.next_action)}</p>` : ''}
      ${practiceText ? `<p><b>Suggested practice:</b> ${esc(practiceText)}</p>` : ''}
      ${details.recommendation_basis ? `<small>Basis: ${esc(humanize(details.recommendation_basis))}</small>` : ''}
      ${sourceEvidence ? `<small>Evidence: ${esc(sourceEvidence.source)} · ${esc(sourceEvidence.provenance_id || fact.provenance_id || '')}</small>` : ''}
      <small>Proficiency verified: ${details.proficiency_verified === true ? 'yes' : 'no'}</small>
    </li>`;
  }).join('');
  const status = readiness.map(fact => `<p class="ts-intel-empty" role="status">${esc(fact.details?.message || fact.metric_value || 'No recommendation was generated.')}</p>`).join('');
  const limits = list(limitations).filter(item => /course|personalized|proficien|ESCO|taxonomy/i.test(String(item)));
  return `<section class="ts-intel-result-card" aria-label="Action recommendations"><h3>Action Recommendation</h3>
    ${items ? `<ol class="ts-intel-roadmap">${items}</ol>` : ''}${status}
    ${limits.length ? `<ul class="ts-intel-limitations">${limits.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : ''}
  </section>`;
}

function renderReferenceDescriptions(facts) {
  const described = facts.filter(fact => fact.history_type === 'reference_taxonomy'
    && (fact.details?.description || fact.details?.skill_uri || fact.details?.occupation_uri || fact.metric_name === 'relation_type'));
  if (!described.length) return '';
  return `<section class="ts-intel-result-card" aria-label="Taxonomy evidence details"><ul>${described.map(fact => `<li>${fact.details?.description ? `<p>${esc(fact.details.description)}</p>` : ''}${fact.metric_name === 'relation_type' ? `<p>ESCO relationship: ${esc(fact.metric_value)}</p>` : ''}${fact.details?.skill_uri ? `<small>ESCO skill ID: ${esc(fact.details.skill_uri)}</small>` : ''}${fact.details?.occupation_uri ? `<small>ESCO occupation ID: ${esc(fact.details.occupation_uri)}</small>` : ''}${fact.provenance_id ? `<small>Evidence provenance: ${esc(fact.provenance_id)}</small>` : ''}</li>`).join('')}</ul></section>`;
}

function renderAdoption(facts) {
  const fact = facts.find(item => item.fact_type === 'trend_analysis'
    && (item.signal_type === 'adoption' || item.details?.signal_type === 'adoption' || /github/i.test(item.source || '')));
  if (!fact) return '';
  const details = fact.details || {};
  const period = details.start_period && details.end_period
    ? `${details.start_period} to ${details.end_period}`
    : text(fact.period).replace(/_to_/g, ' to ');
  const change = details.change_calculation || details.change_pct || details.growth_pct;
  return `<section class="ts-intel-result-card" aria-label="Developer adoption result"><h3>Developer adoption/activity</h3><p><strong>${esc(fact.entity_name || 'Technology')}</strong>: ${esc(fact.metric_value ?? 'Unavailable')}${fact.unit ? ` ${esc(fact.unit)}` : ''}</p>${details.location || details.geography ? `<p>Geography: ${esc(details.location || details.geography)}</p>` : ''}${period ? `<p>Observed period: ${esc(period)}</p>` : ''}${change != null ? `<p>Reported change: ${esc(typeof change === 'object' ? JSON.stringify(change) : change)}${details.change_pct != null || details.growth_pct != null ? '%' : ''}</p>` : ''}<p class="ts-intel-disclaimer">This source measures developer adoption/activity; it is not hiring demand.</p></section>`;
}

function renderJobs(facts, intent) {
  const fact = facts.find(item => item.fact_type === 'stored_job_postings');
  if (!fact && intent !== 'search_jobs') return '';
  const postings = list(fact?.details?.postings);
  const skills = facts.filter(item => item.fact_type === 'stored_posting_skill');
  const matched = skills.filter(item => !['unmatched', 'ambiguous'].includes(item.details?.mapping_status));
  const unmatched = skills.filter(item => item.details?.mapping_status === 'unmatched');
  const ambiguous = skills.filter(item => item.details?.mapping_status === 'ambiguous');
  const count = Number(fact?.metric_value ?? postings.length);
  const source = fact?.source;
  const safeUrl = value => {
      try { const url = new URL(String(value || '')); return url.protocol === 'https:' && !url.username && !url.password ? url.href : null; } catch { return null; }
  };
  return `<section class="ts-intel-result-card" aria-label="Retrieved job postings"><h3>Stored job-posting sample</h3><p><strong>${esc(count)}</strong> retrieved posting${count === 1 ? '' : 's'}${source ? ` · Source: ${esc(source)}` : ''}</p>
    ${count === 0 ? '<p class="ts-intel-empty" role="status">No stored postings matched this query. This is insufficient data for a posting-skill summary.</p>' : ''}
    ${matched.length ? `<h4>Matched skills in retrieved sample</h4><ul>${matched.map(item => `<li>${esc(item.entity_name)} — ${esc(item.metric_value ?? 0)} of ${esc(item.denominator ?? count)} postings</li>`).join('')}</ul>` : ''}
    ${unmatched.length ? `<h4>Unmatched skill text</h4><ul>${unmatched.map(item => `<li>${esc(item.entity_name)}</li>`).join('')}</ul>` : ''}
    ${ambiguous.length ? `<h4>Ambiguous skill mappings</h4><ul>${ambiguous.map(item => `<li>${esc(item.entity_name)}</li>`).join('')}</ul>` : ''}
    ${postings.length ? `<ul class="ts-intel-postings">${postings.slice(0, 10).map(posting => { const href = safeUrl(posting.source_url); return `<li><strong>${esc(posting.title || 'Untitled posting')}</strong>${posting.company ? `<span>${esc(posting.company)}</span>` : ''}${posting.location ? `<small>${esc(posting.location)}</small>` : ''}<small>${esc(posting.source || source || 'Stored source')}${posting.posting_date ? ` · Posted ${esc(String(posting.posting_date).slice(0, 10))}` : ''}</small>${href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">View source posting</a>` : ''}</li>`; }).join('')}</ul>` : ''}
  </section>`;
}

function renderHistoricalSignals(facts, intent) {
  const observations = facts.filter(fact => fact.fact_type === 'historical_observation');
  const readiness = facts.filter(fact => fact.fact_type === 'analysis_readiness'
    && fact.metric_name === 'historical_series_readiness');
  if (!observations.length && !readiness.length && intent !== 'retrieve_history') return '';
  const rows = observations.slice(0, 20).map(fact => {
    const details = fact.details || {};
    const geography = details.location || details.geography;
    return `<li><strong>${esc(fact.period || 'Period unavailable')}</strong><span>${esc(fact.source || 'Source unavailable')} · ${esc(details.signal_type || fact.metric_name || 'signal')}: ${esc(fact.metric_value ?? 'Unavailable')}${fact.unit ? ` ${esc(fact.unit)}` : ''}</span><small>${esc(details.frequency || 'frequency unspecified')}${geography ? ` · ${esc(geography)}` : ''} · ${esc(fact.history_type || 'history type unavailable')} · ${esc(fact.data_origin || 'origin unavailable')}</small>${fact.series_id ? `<code>${esc(fact.series_id)}</code>` : ''}</li>`;
  }).join('');
  const explanations = readiness.map(fact => esc(fact.details?.reason || fact.metric_value || 'Historical data is unavailable.'));
  return `<section class="ts-intel-result-card" aria-label="Historical skill signals"><h3>Historical Skill Signals</h3>${rows ? `<ul>${rows}</ul>` : ''}${explanations.map(reason => `<p class="ts-intel-empty" role="status">${reason}</p>`).join('')}<p class="ts-intel-disclaimer">Historical sources remain separate; missing periods are not interpolated and current snapshots are not treated as history.</p></section>`;
}

export function renderStructuredIntelligenceDetails(response) {
  if (!response || ['failed', 'error', 'blocked'].includes(String(response.execution_status || '').toLowerCase())) return '';
  const facts = list(response.facts);
  return [
    ...facts.filter(fact => fact.fact_type === 'personalized_skill_gap').map(renderSkillGap),
    renderActionRecommendations(facts, response.evidence, response.limitations),
    renderReferences(facts),
    renderReferenceDescriptions(facts),
    renderAdoption(facts),
    renderHistoricalSignals(facts, response.intent),
    renderJobs(facts, response.intent)
  ].filter(Boolean).join('');
}
