export function sortCatalogByName(items) {
  return [...(Array.isArray(items) ? items : [])].sort((left, right) => (
    String(left.name || '').localeCompare(String(right.name || ''), undefined, { sensitivity: 'base' })
    || String(left.skill_id || '').localeCompare(String(right.skill_id || ''))
  ));
}

export function getSkillTrendSummary(item) {
  const githubSeries = Array.isArray(item?.developer_activity) ? item.developer_activity : [];
  if (item?.trend_available && item.trend) {
    const directions = {
      Increasing: 'Rising',
      Declining: 'Falling',
      Stable: 'Stable',
      Mixed: 'Mixed'
    };
    return {
      direction: directions[item.trend.direction] || 'Unavailable',
      source: item.trend.source || item.latest?.source || '',
      metric: item.trend.metric || item.latest?.metric || '',
      unit: item.trend.unit || item.latest?.unit || '',
      grain: item.trend.period_grain || 'month',
      period: item.trend.period || item.latest?.period || '',
      latestChange: item.trend.change,
      velocity: item.trend.velocity ?? null,
      velocityMetric: item.trend.velocity_metric || '',
      unavailableReason: ''
    };
  }

  const availableSeries = githubSeries
    .filter(series => series.trend_ready)
    .sort((left, right) => String(right.latest?.period || '').localeCompare(String(left.latest?.period || '')));
  const github = availableSeries[0];
  const latestSeries = [...githubSeries]
    .sort((left, right) => String(right.latest?.period || '').localeCompare(String(left.latest?.period || '')))[0];

  if (github) {
    const direction = github.trend_direction;
    return {
      direction: ['Rising', 'Falling', 'Stable', 'Mixed'].includes(direction) ? direction : 'Unavailable',
      source: 'GitHub Innovation Graph',
      metric: github.metric,
      unit: github.unit,
      grain: github.period_grain,
      period: github.latest_trend_period || github.latest?.period || '',
      latestChange: github.period_over_period_change,
      velocity: github.velocity_per_quarter,
      velocityMetric: github.velocity_metric || '',
      unavailableReason: github.stale_reason || ''
    };
  }

  if (latestSeries) {
    return {
      direction: 'Unavailable',
      source: 'GitHub Innovation Graph',
      metric: latestSeries.metric,
      unit: latestSeries.unit,
      grain: latestSeries.period_grain,
      period: latestSeries.latest?.period || '',
      latestChange: latestSeries.period_over_period_change,
      velocity: null,
      velocityMetric: '',
      unavailableReason: latestSeries.trend_unavailable_reason || ''
    };
  }

  return {
    direction: 'Unavailable',
    source: '',
    metric: '',
    unit: '',
    grain: '',
    period: '',
    latestChange: null,
    velocity: null,
    velocityMetric: '',
    unavailableReason: item?.analysis_readiness?.trend?.reason || item?.trend_unavailable_reason || ''
  };
}
