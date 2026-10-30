import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

globalThis.window = {
  lucide: { createIcons: () => {} }
};

test('Market Intelligence 7-Section Ecosystem Blueprint', async (t) => {
  const marketPageSource = await readFile(
    new URL('../src/pages/individual/market/MarketIntelligence.js', import.meta.url),
    'utf8'
  );

  await t.test('1. Section 1 - Market Overview: Displays external signals and freshness date', () => {
    assert.match(
      marketPageSource,
      /id="sectionMarketOverview"/,
      'Section 1 container id="sectionMarketOverview" is present'
    );
    assert.match(
      marketPageSource,
      /Total Signals Tracked/,
      'Displays Total Signals Tracked metric'
    );
    assert.match(
      marketPageSource,
      /Signals fresh:/,
      'Displays freshness indicator'
    );
  });

  await t.test('2. Section 2 - Emerging Technologies: Lists top community surging skills', () => {
    assert.match(
      marketPageSource,
      /id="sectionEmergingTech"/,
      'Section 2 container id="sectionEmergingTech" is present'
    );
    assert.match(
      marketPageSource,
      /Emerging Technologies/,
      'Section title Emerging Technologies is present'
    );
    assert.match(
      marketPageSource,
      /mi-growth-surge-tag/,
      'Renders growth surge tags'
    );
  });

  await t.test('3. Section 3 - Technology Trend Analysis: Generates 6-month SVG sparklines', () => {
    assert.match(
      marketPageSource,
      /id="sectionTrendAnalysis"/,
      'Section 3 container id="sectionTrendAnalysis" is present'
    );
    assert.match(
      marketPageSource,
      /renderEcosystemSparklineSVG/,
      'Uses renderEcosystemSparklineSVG generator'
    );
    assert.match(
      marketPageSource,
      /<svg class="mi-sparkline-svg"/,
      'Renders SVG sparklines'
    );
  });

  await t.test('4. Section 4 - Market Changes: Explains developer community traction', () => {
    assert.match(
      marketPageSource,
      /id="sectionMarketChanges"/,
      'Section 4 container id="sectionMarketChanges" is present'
    );
    assert.match(
      marketPageSource,
      /Market Changes &amp; Ecosystem Dynamics/,
      'Section title Market Changes & Ecosystem Dynamics is present'
    );
    assert.match(
      marketPageSource,
      /Ecosystem Trajectory Insights/,
      'Explains community inquiry outpaces general software engineering'
    );
  });

  await t.test('5. Section 5 - Personalized Impact: Custom callout based on target role and skills', () => {
    assert.match(
      marketPageSource,
      /id="sectionPersonalizedImpact"/,
      'Section 5 container id="sectionPersonalizedImpact" is present'
    );
    assert.match(
      marketPageSource,
      /Because you are targeting/,
      'Contains personalized relevance callout statement'
    );
    assert.match(
      marketPageSource,
      /is highly relevant to you/,
      'States relevance to the individual user'
    );
    assert.match(
      marketPageSource,
      /getUserCareerContext\(\)/,
      'Reads target role and skills dynamically from localStorage'
    );
  });

  await t.test('6. Section 6 - Recommended Actions: Buttons for Job Intelligence and Add to Profile', () => {
    assert.match(
      marketPageSource,
      /id="sectionRecommendedActions"/,
      'Section 6 container id="sectionRecommendedActions" is present'
    );
    assert.match(
      marketPageSource,
      /id="btnGoToJobIntelligence"/,
      'Has button View Job Intelligence'
    );
    assert.match(
      marketPageSource,
      /id="btnAddEmergingToProfile"/,
      'Has button Add to Profile'
    );
  });

  await t.test('7. Section 7 - Evidence & Sources: Verbatim mandatory boundary disclaimer', () => {
    assert.match(
      marketPageSource,
      /id="sectionEvidenceSources"/,
      'Section 7 container id="sectionEvidenceSources" is present'
    );
    assert.match(
      marketPageSource,
      /A GitHub, Stack Exchange, or Wikipedia activity increase is a developer activity signal, not proof that companies are hiring more developers\./,
      'Includes mandatory verbatim disclaimer statement'
    );
  });

  await t.test('8. Strict constraint: NO job posting volumes or employer counts are rendered', () => {
    // Check in the main renderMarketIntelligenceHTML function
    const htmlFunc = marketPageSource.slice(
      marketPageSource.indexOf('export function renderMarketIntelligenceHTML'),
      marketPageSource.indexOf('export function renderDedicatedMarketPage')
    );
    assert.ok(
      !htmlFunc.includes('total_active_employers'),
      'Does not render total_active_employers in main UI'
    );
    assert.ok(
      !htmlFunc.includes('total_tracked_postings'),
      'Does not render total_tracked_postings in main UI'
    );
    assert.ok(
      !htmlFunc.includes('Employers in stored postings'),
      'Does not render employer catalog table in main UI'
    );
    assert.ok(
      !htmlFunc.includes('Open Requisitions'),
      'Does not render open requisitions in main UI'
    );
  });
});
