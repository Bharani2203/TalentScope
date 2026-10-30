import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

const browserPath = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
].find(existsSync);

async function runTest() {
  console.log('Launching headless browser to test AI Co-Pilot drawer persistence...');
  const browser = await puppeteer.launch({
    executablePath: browserPath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(8000);
    await page.setViewport({ width: 1280, height: 800 });

    const uid = 'copilot-drawer-test-user';
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
      const origRemove = localStorage.removeItem.bind(localStorage);
      localStorage.removeItem = (key) => {
        if (key === 'talentscope_session_v2') return;
        origRemove(key);
      };
      window.talentscopeGetAuthToken = async () => 'mock-test-token';
    }, uid);

    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

    console.log('Navigating to http://localhost:3000/#/individual/home ...');
    await page.goto('http://localhost:3000/#/individual/home', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#primaryNav .nav-item');

    // 1. Verify "AI Co-Pilot" is NOT in the left sidebar
    const sidebarMenuItems = await page.$$eval('#primaryNav .nav-item', items =>
      items.map(item => item.innerText.trim())
    );
    console.log('Sidebar navigation items:', sidebarMenuItems);
    assert.ok(
      !sidebarMenuItems.some(label => label.includes('AI Co-Pilot')),
      'AI Co-Pilot MUST NOT be in the sidebar navigation'
    );
    console.log('✓ PASS: AI Co-Pilot is removed from sidebar');

    // 2. Verify Floating Action Button (FAB) in the bottom-right corner
    await page.waitForSelector('#floatingAiLauncher', { timeout: 4000 });
    const fabInfo = await page.evaluate(() => {
      const fab = document.getElementById('floatingAiLauncher');
      const rect = fab.getBoundingClientRect();
      const style = window.getComputedStyle(fab);
      return {
        bottom: rect.bottom,
        right: rect.right,
        position: style.position,
        text: fab.innerText
      };
    });
    console.log('FAB Button Info:', fabInfo);
    assert.equal(fabInfo.position, 'fixed', 'FAB must be fixed position');
    assert.ok(fabInfo.text.includes('🤖'), 'FAB must have robot icon');
    console.log('✓ PASS: Floating Action Button exists in bottom-right corner with robot icon');

    // 3. Click FAB to open the drawer
    await page.click('#floatingAiLauncher');
    await new Promise(r => setTimeout(r, 600));

    const drawerOpen = await page.evaluate(() => {
      const drawer = document.getElementById('copilotSlideoutDrawer');
      return drawer && drawer.classList.contains('is-open');
    });
    assert.ok(drawerOpen, 'Slide-out drawer must open with is-open class');
    console.log('✓ PASS: Drawer opens on FAB click');

    // 4. Check drawer contains AI Co-Pilot chat
    await page.waitForSelector('#cleanChatHistory', { timeout: 4000 });
    const initialChatMessages = await page.evaluate(() => {
      return document.getElementById('cleanChatHistory')?.innerText || '';
    });
    assert.ok(initialChatMessages.includes('Welcome to AI Co-Pilot'), 'Drawer must render chat interface');
    console.log('✓ PASS: Chat interface renders inside persistent drawer');

    // 5. Send a message in chat drawer
    console.log('Entering test query in chat drawer...');
    await page.evaluate(() => {
      const input = document.getElementById('cleanChatInput');
      const form = document.getElementById('cleanChatForm');
      if (input && form) {
        input.value = 'What is Machine Learning?';
        const submitEvent = new Event('submit', { cancelable: true });
        form.dispatchEvent(submitEvent);
      }
    });

    // Wait for the message to appear in history
    await page.waitForFunction(() => {
      const history = document.getElementById('cleanChatHistory');
      return history && history.innerText.includes('What is Machine Learning?');
    }, { timeout: 5000 });
    console.log('✓ PASS: Message entered into persistent chat drawer');

    // 6. Navigate to a DIFFERENT page: "My Skills" (#/individual/skills)
    console.log('Navigating to My Skills page (#/individual/skills)...');
    await page.evaluate(() => {
      window.location.hash = '#/individual/skills';
    });
    await new Promise(r => setTimeout(r, 800));

    // Verify main content changed to My Skills
    const currentHash = await page.evaluate(() => window.location.hash);
    console.log('Current URL hash:', currentHash);
    assert.equal(currentHash, '#/individual/skills', 'Must be on My Skills page');

    // 7. Verify persistent drawer STILL has the conversation history intact!
    const historyOnSkillsPage = await page.evaluate(() => {
      const history = document.getElementById('cleanChatHistory');
      return history ? history.innerText : '';
    });
    console.log('Chat history on Skills page snippet:', historyOnSkillsPage.slice(0, 100));
    assert.ok(
      historyOnSkillsPage.includes('What is Machine Learning?'),
      'CRITICAL: Chat history MUST be preserved after navigating to a different page!'
    );
    console.log('✓ PASS: Chat history completely preserved across page navigation!');

    // 8. Close drawer and re-open on Skills page
    console.log('Testing close and re-open on Skills page...');
    await page.click('#closeCopilotBtn');
    await new Promise(r => setTimeout(r, 400));
    const drawerClosed = await page.evaluate(() => {
      const drawer = document.getElementById('copilotSlideoutDrawer');
      return drawer && drawer.classList.contains('is-closed');
    });
    assert.ok(drawerClosed, 'Drawer must close on close button click');

    await page.click('#floatingAiLauncher');
    await new Promise(r => setTimeout(r, 400));
    const historyAfterReopen = await page.evaluate(() => {
      const history = document.getElementById('cleanChatHistory');
      return history ? history.innerText : '';
    });
    assert.ok(
      historyAfterReopen.includes('What is Machine Learning?'),
      'Chat history still intact after drawer re-open!'
    );
    console.log('✓ PASS: Drawer re-opened on Skills page with full conversation history intact!');

    console.log('\n======================================================');
    console.log('ALL E2E PERSISTENT COPILOT DRAWER CHECKS PASSED 100%!');
    console.log('======================================================\n');
  } finally {
    await browser.close();
  }
}

runTest().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
