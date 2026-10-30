import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

const browserPath = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
].find(existsSync);

async function runTest() {
  console.log('Launching headless browser to verify Dashboard & Telemetry Snapshots...');
  const browser = await puppeteer.launch({
    executablePath: browserPath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(12000);
    await page.setViewport({ width: 1280, height: 900 });

    const uid = 'test-snapshot-user';
    await page.evaluateOnNewDocument((userUid) => {
      window.lucide = { createIcons() {} };
      const user = {
        uid: userUid,
        id: userUid,
        name: 'Arun Sharma',
        userType: 'individual',
        onboardingComplete: true,
        skills: ['Python', 'SQL'],
        targetRole: 'AI Engineer'
      };
      const sessionData = JSON.stringify({
        authSource: 'firebase',
        userId: userUid,
        user
      });
      localStorage.setItem('talentscope_session_v2', sessionData);
      localStorage.setItem('talentscope-saved-skills', JSON.stringify(['Python', 'SQL']));
      const origRemove = localStorage.removeItem.bind(localStorage);
      localStorage.removeItem = (key) => {
        if (key === 'talentscope_session_v2') return;
        origRemove(key);
      };
      window.talentscopeGetAuthToken = async () => 'mock-test-token';
    }, uid);

    page.on('console', msg => {
      const txt = msg.text();
      if (!txt.includes('AUTH_DIAGNOSTIC') && !txt.includes('401')) {
        console.log('PAGE LOG:', txt);
      }
    });

    // Navigate to Home Dashboard
    await page.goto('http://localhost:3000/#/individual/home', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));

    // 1. Verify Signal Cards (JSearch & Adzuna, GitHub, Stack Exchange)
    const pillarValues = await page.$$eval('.market-pillar-card', cards => cards.map(c => ({
      title: c.querySelector('.market-pillar-card__title')?.innerText?.trim() || '',
      source: c.querySelector('.market-pillar-source-tag')?.innerText?.trim() || '',
      val: c.querySelector('.market-pillar-val')?.innerText?.trim() || ''
    })));
    console.log('Market Signal Pillar Cards:', pillarValues);

    const jsearchCard = pillarValues.find(c => c.source.includes('JSearch') || c.source.includes('Adzuna'));
    assert.ok(jsearchCard, 'JSearch & Adzuna signal card must exist');
    assert.notEqual(jsearchCard.val, '0 observations', 'JSearch & Adzuna signal must not be 0 observations');
    console.log('✓ PASS: JSearch & Adzuna signal card displays real observation numbers:', jsearchCard.val);

    const githubCard = pillarValues.find(c => c.source.includes('GitHub'));
    assert.ok(githubCard, 'GitHub signal card must exist');
    assert.notEqual(githubCard.val, '0 series', 'GitHub signal must not be 0 series');
    console.log('✓ PASS: GitHub signal card displays real series numbers:', githubCard.val);

    const stackCard = pillarValues.find(c => c.source.includes('Stack Exchange'));
    assert.ok(stackCard, 'Stack Exchange signal card must exist');
    assert.notEqual(stackCard.val, '0 series', 'Stack Exchange signal must not be 0 series');
    console.log('✓ PASS: Stack Exchange signal card displays real series numbers:', stackCard.val);

    // 2. Verify Home Top 5 Trending Skills
    const topSkills = await page.$$eval('.skill-rail-row', rows => rows.map(r => ({
      name: r.querySelector('.skill-rail-name')?.innerText?.trim(),
      change: r.querySelector('.skill-rail-change')?.innerText?.trim()
    })));
    console.log('Home Top 5 Trending Skills rows:', topSkills);
    assert.ok(topSkills.length > 0, 'Top 5 Trending Skills must display skills');
    assert.ok(!topSkills.some(s => s.name?.includes('Try again')), 'Top 5 Trending Skills must not show Try again error');
    console.log('✓ PASS: Home Top 5 Trending Skills displays skills based on current job volume without Try again error');

    // 3. Verify Analytical Gate refactor: Theil-Sen Gate Status / Forecast Readiness replaced with Current Snapshot
    const baselineSurfaceText = await page.$eval('.skill-chart-main', el => el.innerText).catch(() => '');
    assert.ok(!baselineSurfaceText.includes('Theil-Sen Gate Status'), 'Strict Theil-Sen Gate Status must be disabled in snapshot view');
    assert.ok(!baselineSurfaceText.includes('Inactive (0 models)'), 'Strict Forecast Readiness 0 models must be disabled in snapshot view');
    assert.ok(baselineSurfaceText.includes('Current Snapshot') || baselineSurfaceText.includes('Snapshot Status'), 'Must render Current Snapshot status');
    console.log('✓ PASS: Analytical Gates refactored to Current Snapshot view');

    // 4. Verify Skills Page (#/individual/skills)
    console.log('Navigating to My Skills page (#/individual/skills)...');
    await page.goto('http://localhost:3000/#/individual/skills', { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));

    // Check that Skills page renders Top 5 Trending Skills without "Try again" error
    const skillsPageHtml = await page.content();
    assert.ok(!skillsPageHtml.includes('data-action="retry">Try again<'), 'Skills page must not render Try again error button');
    
    const trendingListItems = await page.$$eval('.si-trending-row', rows => rows.map(r => r.innerText.trim()));
    console.log('Skills Page Trending Items count:', trendingListItems.length);
    assert.ok(trendingListItems.length > 0, 'Skills Page must render trending skills');
    console.log('✓ PASS: Skills Page displays top skills based on current job volume without Try again error button');

    console.log('\n======================================================');
    console.log('ALL DASHBOARD & TELEMETRY SNAPSHOT CHECKS PASSED 100%!');
    console.log('======================================================\n');
  } finally {
    await browser.close();
  }
}

runTest().catch(err => {
  console.error('VERIFICATION FAILED:', err);
  process.exit(1);
});

