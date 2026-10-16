import assert from 'node:assert/strict';
import { CATALOG_PAGE_SIZE, paginateCatalog } from '../src/utils/catalog-pagination.js';
import { getSkillTrendSummary, sortCatalogByName } from '../src/utils/skill-catalog.js';
import { readFile } from 'node:fs/promises';

const records = Array.from({ length: 23 }, (_, index) => ({ id: index + 1, name: `Entity ${String(index + 1).padStart(2, '0')}` }));
assert.equal(CATALOG_PAGE_SIZE, 10);
assert.deepEqual(paginateCatalog(records, 1), {
  items: records.slice(0, 10), page: 1, pageCount: 3, total: 23, start: 1, end: 10
});
assert.equal(paginateCatalog(records, 2).items.length, 10);
assert.deepEqual(paginateCatalog(records, 3), {
  items: records.slice(20), page: 3, pageCount: 3, total: 23, start: 21, end: 23
});
assert.equal(paginateCatalog(records, 99).page, 3);
assert.deepEqual(paginateCatalog([], 1), {
  items: [], page: 1, pageCount: 1, total: 0, start: 0, end: 0
});

// The views filter and sort their complete fetched catalogs before slicing.
const skillPage = await readFile(new URL('../src/pages/individual/skills/SkillIntelligence.js', import.meta.url), 'utf8');
const marketPage = await readFile(new URL('../src/pages/individual/market/MarketIntelligence.js', import.meta.url), 'utf8');
const homePage = await readFile(new URL('../src/app/app.js', import.meta.url), 'utf8');
const assistantPage = await readFile(new URL('../src/pages/individual/ai-assistant/AIAssistant.js', import.meta.url), 'utf8');
assert.match(skillPage, /paginateCatalog\(rows, pageState\.catalogPage\)/);
assert.match(skillPage, /pageState\.catalogPage = 1/);
assert.match(marketPage, /paginateCatalog\(visibleCompanies, marketCompanyPage\)/);
assert.match(marketPage, /marketCompanyPage = 1/);
assert.match(marketPage, /s\.coverage\?\.source_job_count \?\? s\.metadata\?\.source_job_count \?\? null/);
assert.doesNotMatch(marketPage, /source_job_count:\s*s\.value/);
assert.match(skillPage, /<th>Skill<\/th><th>Source<\/th><th>Latest period<\/th><th>Trend<\/th><th scope="col" title="Save this skill to your favourites">Favourite<\/th>/);
assert.match(skillPage, /data-lucide="star"/);
assert.match(skillPage, /saveFavouriteSkillIds\(next\)/);
assert.match(skillPage, /detail: \{ domain: 'skill', skill_ids: pageState\.favoriteSkillIds \}/);
assert.match(homePage, /saveFavouriteSkillIds\(nextIds\)/);
assert.match(homePage, /skill_ids: savedIds/);
assert.match(homePage, /\.\.\.skillFavoriteNames/);
assert.doesNotMatch(homePage, /dashboardState\.savedSkills\.push\(ent\)/);
assert.match(homePage, /No favourite skills yet\./);
assert.match(assistantPage, /talentscope:favourites-updated/);
assert.match(marketPage, /saveFavouriteSkillIds\(next\)/);
assert.match(marketPage, /data-toggle-market-favourite/);

const unsortedSkills = [
  { skill_id: 'z', name: 'zebra' }, { skill_id: 'b', name: 'Beta' },
  { skill_id: 'a', name: 'alpha' }, { skill_id: 'd', name: 'Delta' },
  { skill_id: 'c', name: 'charlie' }, { skill_id: 'e', name: 'Echo' },
  { skill_id: 'g', name: 'golf' }, { skill_id: 'f', name: 'Foxtrot' },
  { skill_id: 'i', name: 'India' }, { skill_id: 'h', name: 'hotel' },
  { skill_id: 'j', name: 'Juliet' }
];
const sortedSkills = sortCatalogByName(unsortedSkills);
assert.deepEqual(sortedSkills.map(skill => skill.name), [
  'alpha', 'Beta', 'charlie', 'Delta', 'Echo', 'Foxtrot', 'golf', 'hotel', 'India', 'Juliet', 'zebra'
]);
assert.deepEqual(paginateCatalog(sortedSkills, 2).items.map(skill => skill.name), ['zebra']);
assert.deepEqual(
  paginateCatalog(sortCatalogByName(unsortedSkills.filter(skill => skill.name.toLowerCase().includes('o'))), 1)
    .items.map(skill => skill.name),
  ['Echo', 'Foxtrot', 'golf', 'hotel']
);

const trend = getSkillTrendSummary({
  developer_activity: [{
    trend_ready: true,
    trend_direction: 'Rising',
    metric: 'language_pushers',
    unit: 'unique developers per quarter',
    period_grain: 'quarter',
    latest_trend_period: '2025-Q4',
    latest: { period: '2025-Q4' },
    period_over_period_change: -3,
    velocity_per_quarter: 2.5
  }]
});
assert.equal(trend.direction, 'Rising');
assert.equal(trend.latestChange, -3);
assert.equal(trend.velocity, 2.5);
assert.equal(trend.grain, 'quarter');

const unavailableTrend = getSkillTrendSummary({
  status: 'reference_only',
  analysis_readiness: { trend: { reason: 'Reference data is static.' } }
});
assert.equal(unavailableTrend.direction, 'Unavailable');
assert.equal(unavailableTrend.period, '');
assert.equal(unavailableTrend.unavailableReason, 'Reference data is static.');
for (const [input, expected] of [
  ['Falling', 'Falling'],
  ['Stable', 'Stable'],
  ['Mixed', 'Mixed']
]) {
  assert.equal(getSkillTrendSummary({
    developer_activity: [{
      trend_ready: true,
      trend_direction: input,
      metric: 'topic_pushers',
      unit: 'unique developers per quarter',
      period_grain: 'quarter',
      latest: { period: '2026-Q1' }
    }]
  }).direction, expected);
}
assert.match(skillPage, /pageState\.favoriteSkillIds = previousIds/);
assert.match(skillPage, /aria-pressed="\$\{isFavourite\}"/);
assert.match(homePage, /homeSkillIntelligenceState\.favoriteSkills = new Set\(favoriteNames\)/);
assert.doesNotMatch(homePage, /dashboardState\.savedSkills\.push\(ent\)/);
assert.doesNotMatch(assistantPage, /talentscope_fav_skills_v1/);

console.log('catalog pagination tests passed');
