import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import puppeteer from 'puppeteer-core';

const browserPath = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
].find(existsSync);
assert.ok(browserPath, 'Chrome or Edge must be installed for the AI Help browser checks.');

const browser = await puppeteer.launch({
  executablePath: browserPath,
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
});

try {
  const page = await browser.newPage();
  page.setDefaultTimeout(8000);
  page.on('pageerror', error => console.error('[browser page error]', error.message));
  await page.setViewport({ width: 1280, height: 900 });
  await page.evaluateOnNewDocument(() => {
    window.lucide = { createIcons() {} };
    const uid = 'ai-help-browser-check';
    localStorage.setItem('talentscope_session_v2', JSON.stringify({
      authSource: 'firebase',
      userId: uid,
      user: { uid, id: uid, name: 'AI Help Check', userType: 'individual', onboardingComplete: true }
    }));
  });
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = request.url();
    if (url.startsWith('http://127.0.0.1:3000/') || url.startsWith('data:') || url.startsWith('blob:')) request.continue();
    else request.abort();
  });

  await page.goto('http://127.0.0.1:3000/#/individual/ai-help', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#primaryNav .nav-item');

  const menuOrder = await page.$$eval('#primaryNav .nav-item', items =>
    items.map(item => ({ label: item.innerText.trim(), route: item.dataset.route }))
  );
  const notificationIndex = menuOrder.findIndex(item => item.route === '/individual/notifications');
  assert.equal(menuOrder[notificationIndex + 1]?.route, '/individual/ai-help');

  await page.click('#primaryNav [data-route="/individual/ai-help"]');
  await page.waitForSelector('#aiHelpTitle');
  assert.equal(await page.$eval('#aiHelpTitle', node => node.textContent), 'AI Help');
  assert.equal(await page.$$eval('.ai-help-suggestion', items => items.length), 6);
  assert.match(await page.$eval('.ai-help-demo-notice', node => node.innerText), /Demo responses/);
  assert.ok(await page.$eval('#primaryNav [data-route="/individual/ai-help"]', node => node.classList.contains('is-active')));

  await page.click('.ai-help-suggestion');
  await page.waitForSelector('.ai-help-typing');
  await page.waitForFunction(() => document.querySelectorAll('.ai-help-message-row').length === 3
    && !document.querySelector('.ai-help-typing'));
  assert.match(await page.$eval('.ai-help-demo-label', node => node.innerText), /Temporary help response.*demo/i);
  assert.ok(await page.$('.ai-help-copy'));

  assert.equal(await page.$eval('.ai-help-send', button => button.disabled), false);
  await page.$eval('.ai-help-composer', form => form.requestSubmit());
  await page.waitForSelector('.ai-help-error');
  assert.match(await page.$eval('.ai-help-error', node => node.innerText), /Enter a question/);

  await page.evaluate(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: async text => { window.__aiHelpCopiedText = text; } }
    });
  });
  await page.click('.ai-help-copy');
  await page.waitForFunction(() => document.querySelector('.ai-help-copy span')?.textContent === 'Copied');
  assert.ok(await page.evaluate(() => window.__aiHelpCopiedText?.startsWith('Hi! Welcome to TalentScope.ai Help.')));

  await page.click('#aiHelpInput');
  await page.keyboard.type('First line');
  await page.keyboard.down('Shift');
  await page.keyboard.press('Enter');
  await page.keyboard.up('Shift');
  await page.keyboard.type('Second line');
  const multilineState = await page.$eval('#aiHelpInput', node => ({ value: node.value, disabled: node.disabled, active: document.activeElement === node }));
  assert.equal(multilineState.value, 'First line\nSecond line', JSON.stringify(multilineState));
  await page.$eval('#aiHelpInput', node => { node.value = ''; });
  await page.keyboard.type('What does insufficient data mean?');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => [...document.querySelectorAll('.ai-help-message.assistant p')]
    .some(node => node.textContent.includes('available evidence did not meet the requirements')));

  await page.evaluate(() => {
    const originalSetTimeout = window.setTimeout.bind(window);
    window.__aiHelpOriginalSetTimeout = originalSetTimeout;
    window.setTimeout = (callback, delay, ...args) => {
      if (delay === 350) throw new Error('Simulated temporary provider failure.');
      return originalSetTimeout(callback, delay, ...args);
    };
  });
  await page.focus('#aiHelpInput');
  await page.keyboard.type('How do I navigate the platform?');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.querySelector('.ai-help-error')?.textContent.includes('Simulated temporary provider failure'));
  await page.evaluate(() => { window.setTimeout = window.__aiHelpOriginalSetTimeout || window.setTimeout; });
  await page.click('[data-ai-help-action="retry"]');
  await page.waitForFunction(() => [...document.querySelectorAll('.ai-help-message.assistant p')]
    .some(node => node.textContent.includes('Use the left navigation')));

  await page.click('[data-ai-help-action="clear"]');
  assert.equal(await page.$$eval('.ai-help-message-row', items => items.length), 1);

  await page.click('#primaryNav [data-route="/individual/notifications"]');
  await page.waitForFunction(() => window.location.hash.split('?')[0] === '#/individual/notifications');
  assert.ok(await page.$eval('#primaryNav [data-route="/individual/notifications"]', node => node.classList.contains('is-active')));
  await page.click('#primaryNav [data-route="/individual/ai-help"]');
  await page.waitForSelector('#aiHelpTitle');

  await page.click('#primaryNav [data-route="/individual/ai-assistant"]');
  await page.waitForFunction(() => window.location.hash.split('?')[0] === '#/individual/ai-assistant');
  assert.ok(await page.$eval('#primaryNav [data-route="/individual/ai-assistant"]', node => node.classList.contains('is-active')));
  await page.click('#primaryNav [data-route="/individual/ai-help"]');
  await page.waitForSelector('#aiHelpTitle');

  await page.setViewport({ width: 375, height: 812 });
  await new Promise(resolve => setTimeout(resolve, 100));
  const mobileLayout = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    chatVisible: document.querySelector('.ai-help-chat-card').getBoundingClientRect().width > 0,
    suggestionsVisible: document.querySelector('.ai-help-suggestions').getBoundingClientRect().width > 0
  }));
  assert.ok(mobileLayout.chatVisible && mobileLayout.suggestionsVisible);
  assert.ok(mobileLayout.document <= mobileLayout.viewport, `Unexpected horizontal overflow: ${JSON.stringify(mobileLayout)}`);

  console.log('AI Help browser checks passed: menu ordering, route/active state, suggestions, loading, demo replies, empty input, Shift+Enter, copy, error/retry, new chat, Notifications and AI Assistant navigation, and mobile layout.');
} finally {
  await browser.close();
}
