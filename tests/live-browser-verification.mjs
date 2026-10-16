// ============================================================================
// TALENTSCOPE.AI — G2.7 LIVE BROWSER VERIFICATION & REVIEW READINESS SUITE
// Automated end-to-end verification in real headless Chrome via Puppeteer-Core
// ============================================================================

import assert from 'node:assert/strict';
import { spawn, execSync } from 'node:child_process';
import { readFileSync, unlinkSync, existsSync } from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://127.0.0.1:8000';
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const EXECUTABLE_PATH = existsSync(CHROME_PATH) ? CHROME_PATH : EDGE_PATH;

const TOKENS_PATH = path.resolve('backend/scripts/.test_tokens.json');

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitForHttp(url, maxRetries = 25, delayMs = 500) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 200 || res.status === 404) return true;
    } catch {}
    await sleep(delayMs);
  }
  return false;
}

let backendProc = null;
async function ensureBackend() {
  const isHealthy = await waitForHttp(`${BACKEND_URL}/api/v1/health`, 2, 200);
  if (isHealthy) {
    console.log('[Setup] Backend is already running on ' + BACKEND_URL);
    return;
  }
  console.log('[Setup] Launching backend uvicorn server on port 8000...');
  backendProc = spawn(
    path.resolve('backend/.venv/Scripts/python.exe'),
    ['-m', 'uvicorn', 'app.main:app', '--port', '8000'],
    { cwd: path.resolve('backend'), stdio: 'ignore' }
  );
  const ready = await waitForHttp(`${BACKEND_URL}/api/v1/health`, 30, 500);
  assert.ok(ready, 'Backend server failed to start on port 8000');
  console.log('[Setup] Backend server is healthy on ' + BACKEND_URL);
}

let frontendProc = null;
async function ensureFrontend() {
  const isReady = await waitForHttp(FRONTEND_URL, 2, 200);
  if (isReady) {
    console.log('[Setup] Frontend is already running on ' + FRONTEND_URL);
    return;
  }
  console.log('[Setup] Launching frontend serve process on port 3000...');
  frontendProc = spawn('node', ['scripts/start-frontend.mjs'], {
    cwd: process.cwd(),
    stdio: 'ignore'
  });
  const ready = await waitForHttp(FRONTEND_URL, 30, 500);
  assert.ok(ready, 'Frontend server failed to start on port 3000');
  console.log('[Setup] Frontend server is serving on ' + FRONTEND_URL);
}

function mintTokens() {
  console.log('[Setup] Minting real Firebase test tokens via backend...');
  const pyExe = path.resolve('backend/.venv/Scripts/python.exe');
  const mintScript = path.resolve('backend/scripts/mint_tokens.py');
  execSync(`"${pyExe}" "${mintScript}" --out "${TOKENS_PATH}"`, {
    stdio: 'inherit',
    cwd: path.resolve('backend')
  });
  const raw = readFileSync(TOKENS_PATH, 'utf-8');
  const tokens = JSON.parse(raw);
  assert.ok(tokens.individual, 'Missing individual token');
  assert.ok(tokens.employee, 'Missing employee token');
  assert.ok(tokens.nvidia, 'Missing nvidia token');
  console.log('[Setup] Real Firebase tokens prepared for Individual, Employee, and Company (NVIDIA)');
  return tokens;
}

async function authenticatePortalUser(page, userTokenInfo, portalUser) {
  await page.evaluate(async (tok, user) => {
    // 1. Sign in to client Firebase auth
    try {
      const { signInWithCustomToken } = await import('https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js');
      const { auth } = await import('./src/auth/firebase-client.js');
      await signInWithCustomToken(auth, tok.custom_token);
    } catch (e) {
      console.warn('signInWithCustomToken notice:', e.message);
    }

    // 2. Persist verified session
    localStorage.setItem('talentscope_session_v2', JSON.stringify({
      authSource: 'firebase',
      userId: tok.uid,
      _token: tok.id_token,
      user: {
        uid: tok.uid,
        id: tok.uid,
        email: tok.email,
        name: user.name,
        userType: user.userType,
        companyId: user.companyId || null,
        companyName: user.companyName || null,
        onboardingComplete: true
      }
    }));

    // 3. Fallback token hook
    window.talentscopeGetAuthToken = async () => tok.id_token;

    // 4. Notify app router
    window.dispatchEvent(new Event('talentscope-auth-state-changed'));
  }, userTokenInfo, portalUser);
  await sleep(400);
}

async function runLiveBrowserVerification() {
  console.log('\n================================================================');
  console.log(' STARTING G2.7 LIVE BROWSER VERIFICATION');
  console.log('================================================================\n');

  await ensureBackend();
  await ensureFrontend();
  const tokens = mintTokens();

  console.log(`[Browser] Launching headless browser from: ${EXECUTABLE_PATH}`);
  const browser = await puppeteer.launch({
    executablePath: EXECUTABLE_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--window-size=1280,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const consoleLogs = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push({ type: msg.type(), text });
    if (msg.type() === 'error' || msg.type() === 'warn') {
      console.warn(`  [Browser Console ${msg.type()}] ${text}`);
    }
  });

  const networkRequests = [];
  page.on('request', req => {
    if (req.url().includes('/api/v1/intelligence/')) {
      networkRequests.push({
        url: req.url(),
        method: req.method(),
        hasAuth: Boolean(req.headers()['authorization'])
      });
    }
  });

  try {
    // ------------------------------------------------------------------------
    // FLOW 1: Individual Portal (Multi-turn, Grounding, Clearing, Limitations)
    // ------------------------------------------------------------------------
    console.log('\n--- [FLOW 1: Individual AI Assistant] ---');
    await page.goto(`${FRONTEND_URL}/#/login`, { waitUntil: 'domcontentloaded' });
    await authenticatePortalUser(page, tokens.individual, { name: 'Alex Rivera', userType: 'individual' });

    // Navigate to Individual AI Assistant
    await page.evaluate(() => { window.location.hash = '#/individual/ai-assistant'; });
    await sleep(600);
    await page.waitForSelector('#aiComposerInput', { visible: true });
    await page.waitForSelector('#aiComposerForm', { visible: true });

    // Turn 1: Software Tools query
    console.log('1. Submitting query: "What software tools does a Software Developer use?"');
    await page.type('#aiComposerInput', 'What software tools does a Software Developer use?');
    await page.keyboard.press('Enter');

    // Wait for response card to mount in stream
    await page.waitForFunction(() => {
      const stream = document.querySelector('#aiConversationStream');
      return stream && stream.querySelectorAll('.ai-turn-item').length >= 1;
    }, { timeout: 15000 });

    const turn1Status = await page.$eval('.ai-turn-item .cmp-badge', el => el.textContent.trim());
    const turn1Answer = await page.$eval('.ai-turn-item .ai-finding-text', el => el.textContent.trim());
    const turn1FactCount = await page.$$eval('.ai-turn-item .ai-section-block:nth-child(2) > div > div, .ai-turn-item .ai-section-block:nth-child(3) > div > div', els => els.length);

    console.log(`   Execution Status: [${turn1Status}]`);
    console.log(`   Facts Rendered: ${turn1FactCount} verified metrics`);
    assert.match(turn1Status, /Verified Grounded/i);
    assert.ok(turn1Answer.length > 20, 'Expected non-empty answer');
    assert.ok(turn1FactCount > 0, 'Expected structured facts in DOM');

    // Turn 2: Follow-up question verifying conversation continuity & anaphora
    console.log('2. Submitting follow-up query: "What are its related occupations?"');
    await sleep(600);
    await page.waitForSelector('#aiComposerInput', { visible: true });
    await page.type('#aiComposerInput', 'What are its related occupations?');
    await page.keyboard.press('Enter');

    await page.waitForFunction(() => {
      const stream = document.querySelector('#aiConversationStream');
      return stream && stream.querySelectorAll('.ai-turn-item').length >= 2;
    }, { timeout: 15000 });

    const turn2Status = await page.$eval('.ai-turn-item:nth-child(2) .cmp-badge', el => el.textContent.trim());
    const turn2Answer = await page.$eval('.ai-turn-item:nth-child(2) .ai-finding-text', el => el.textContent.trim());
    console.log(`   Follow-up Status: [${turn2Status}]`);
    assert.match(turn2Status, /Verified Grounded/i);
    assert.match(turn2Answer, /Related Occupations|Computer Systems|Engineers|Architects/i);

    // Turn 3: Clear session
    console.log('3. Clicking Clear Session (#btnClearAiSession)...');
    await page.click('#btnClearAiSession');
    await sleep(400);

    const clearedTurns = await page.$$eval('.ai-turn-item', els => els.length);
    console.log(`   Turns remaining after clear: ${clearedTurns}`);
    assert.equal(clearedTurns, 0, 'Expected 0 turns in DOM after clearing session');

    // Turn 4: Insufficient Data Test
    console.log('4. Testing insufficient-data query: "Show Python\'s historical market demand trend"');
    await page.type('#aiComposerInput', "Show Python's historical market demand trend");
    await page.click('#aiComposerForm button[type="submit"]');

    await page.waitForFunction(() => {
      const stream = document.querySelector('#aiConversationStream');
      return stream && stream.querySelectorAll('.ai-turn-item').length >= 1;
    }, { timeout: 15000 });

    const insuffStatus = await page.$eval('.ai-turn-item .cmp-badge', el => el.textContent.trim());
    const insuffLimitation = await page.$eval('.ai-turn-item [style*="background:#FEF3C7"]', el => el.textContent.trim());
    console.log(`   Insufficient Data Status: [${insuffStatus}]`);
    console.log(`   Limitation Banner: "${insuffLimitation.replace(/\s+/g, ' ').slice(0, 80)}..."`);
    assert.match(insuffStatus, /Insufficient Observation Data/i);
    assert.match(insuffLimitation, /consecutive monthly periods|panel drift|gaps/i);

    // Turn 5: Unsupported Forecasting Test
    console.log('5. Testing unsupported forecasting query: "Forecast future demand for Python over the next 2 years"');
    await page.type('#aiComposerInput', 'Forecast future demand for Python over the next 2 years');
    await page.click('#aiComposerForm button[type="submit"]');

    await page.waitForFunction(() => {
      const stream = document.querySelector('#aiConversationStream');
      return stream && stream.querySelectorAll('.ai-turn-item').length >= 2;
    }, { timeout: 15000 });

    const unsuppStatus = await page.$eval('.ai-turn-item:nth-child(2) .cmp-badge', el => el.textContent.trim());
    const unsuppLimitation = await page.$eval('.ai-turn-item:nth-child(2) [style*="background:#FEF3C7"]', el => el.textContent.trim());
    console.log(`   Unsupported Status: [${unsuppStatus}]`);
    console.log(`   Limitation Banner: "${unsuppLimitation.replace(/\s+/g, ' ').slice(0, 80)}..."`);
    assert.match(unsuppStatus, /Capability Unsupported/i);
    assert.match(unsuppLimitation, /Forecasting engine is explicitly disabled|inactive/i);

    console.log('>>> Individual Portal live browser flows passed successfully!');

    // ------------------------------------------------------------------------
    // FLOW 2: Employee Portal (Context Passing, No Invented Data, Privacy Guard)
    // ------------------------------------------------------------------------
    console.log('\n--- [FLOW 2: Employee AI Assistant] ---');
    await authenticatePortalUser(page, tokens.employee, {
      name: 'Sarah Chen',
      userType: 'employee',
      companyId: 'nvidia',
      companyName: 'NVIDIA'
    });

    await page.evaluate(() => { window.location.hash = '#/employee/ai-assistant'; });
    await page.waitForSelector('#empChatInput', { visible: true });

    // Check Employee context pill
    const contextActive = await page.$eval('.emp-stat-pill', el => el.textContent.trim());
    console.log(`1. Employee context active: "${contextActive.replace(/\s+/g, ' ')}"`);
    assert.match(contextActive, /Context Active/i);

    // Query skill guidance
    console.log('2. Asking career question: "What capabilities are required for Staff ML Infra Engineer?"');
    await page.type('#empChatInput', 'What capabilities are required for Staff ML Infra Engineer?');
    await page.click('#empChatForm button[type="submit"]');

    await page.waitForFunction(() => {
      const msgs = document.querySelector('#empChatMessages');
      return msgs && msgs.children.length >= 3;
    }, { timeout: 15000 });

    const empResponse = await page.$eval('#empChatMessages > div:last-child', el => el.textContent.trim());
    console.log(`   Employee Response received (${empResponse.length} chars)`);
    assert.ok(empResponse.length > 50, 'Expected substantive grounded response');
    assert.doesNotMatch(empResponse, /fake_score|manufactured_gap|invented_skill/i);

    // Clear employee chat
    console.log('3. Clicking Clear Session (#empClearChatBtn)...');
    await page.click('#empClearChatBtn');
    await sleep(300);
    const empClearedMsg = await page.$eval('#empChatMessages > div:last-child', el => el.textContent.trim());
    console.log(`   Reset state: "${empClearedMsg.slice(0, 60)}..."`);
    assert.match(empClearedMsg, /Session reset/i);

    console.log('>>> Employee Portal live browser flows passed successfully!');

    // ------------------------------------------------------------------------
    // FLOW 3: Company Admin Strategic Copilot (Tenant Isolation, Honest Limits)
    // ------------------------------------------------------------------------
    console.log('\n--- [FLOW 3: Company Strategic Copilot] ---');
    await authenticatePortalUser(page, tokens.nvidia, {
      name: 'NVIDIA Workforce Director',
      userType: 'company',
      companyId: 'nvidia',
      companyName: 'NVIDIA'
    });

    await page.evaluate(() => { window.location.hash = '#/company/ai-assistant'; });
    await page.waitForSelector('#cmpCopilotInputField', { visible: true });

    // Check enterprise grounding badge
    const companyBadge = await page.$eval('.cmp-hero__context-info', el => el.textContent.trim());
    console.log(`1. Company Header: "${companyBadge.replace(/\s+/g, ' ').slice(0, 60)}..."`);
    assert.match(companyBadge, /Enterprise Grounding Active/i);

    // Query 1: Strategic inquiry
    console.log('2. Querying workforce capability: "What is our company workforce capability?"');
    await page.type('#cmpCopilotInputField', 'What is our company workforce capability?');
    await page.click('#cmpCopilotForm button[type="submit"]');

    await page.waitForFunction(() => {
      const container = document.querySelector('#cmpCopilotMessages');
      return container && container.children.length >= 3;
    }, { timeout: 15000 });

    const compRespText = await page.$eval('#cmpCopilotMessages > div:last-child', el => el.textContent.trim());
    console.log(`   Company Copilot Response rendered (${compRespText.length} chars)`);
    assert.ok(compRespText.length > 50);
    assert.match(compRespText, /Verified Grounded|Grounded against verified/i);

    // Query 2: Unsupported simulation
    console.log('3. Querying unsupported simulation: "Simulate what happens if 50% of workforce shifts to AI"');
    await page.type('#cmpCopilotInputField', 'Simulate what happens if 50% of workforce shifts to AI');
    await page.click('#cmpCopilotForm button[type="submit"]');

    await page.waitForFunction(() => {
      const container = document.querySelector('#cmpCopilotMessages');
      return container && container.children.length >= 5;
    }, { timeout: 15000 });

    const simRespText = await page.$eval('#cmpCopilotMessages > div:last-child', el => el.textContent.trim());
    console.log(`   Simulation Response: "${simRespText.slice(0, 100)}..."`);
    assert.match(simRespText, /Unsupported in G2.6\/G2.7|inactive and unsupported/i);

    // Multi-tenant Isolation Guard: Querying Google workforce with NVIDIA token
    console.log('4. Testing multi-tenant guard: Querying Google workforce with NVIDIA credentials...');
    const tenantViolationResult = await page.evaluate(async (token) => {
      const res = await fetch('http://127.0.0.1:8000/api/v1/intelligence/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: 'What is our company workforce capability?',
          portal_type: 'company',
          company_id: 'google'
        })
      });
      return res.json();
    }, tokens.nvidia.id_token);

    console.log(`   Tenant Guard Status: [${tenantViolationResult.execution_status}] Reason: [${tenantViolationResult.reason_codes[0]}]`);
    assert.equal(tenantViolationResult.execution_status, 'blocked');
    assert.equal(tenantViolationResult.reason_codes[0], 'UNAUTHORIZED_CROSS_COMPANY_ACCESS');

    console.log('>>> Company Strategic Copilot live browser flows passed successfully!');

    // ------------------------------------------------------------------------
    // FLOW 4: Product UI & Existing Dashboard Navigation Sanity
    // ------------------------------------------------------------------------
    console.log('\n--- [FLOW 4: Product UI & Dashboard Route Sanity] ---');
    const pagesToVerify = [
      { name: 'Individual Home', route: '#/individual/home', checkSelector: '.app-main' },
      { name: 'Individual Skills', route: '#/individual/skills', checkSelector: '.app-main' },
      { name: 'Individual Career', route: '#/individual/career', checkSelector: '.app-main' },
      { name: 'Individual Learning', route: '#/individual/learning', checkSelector: '.app-main' },
      { name: 'Employee Home', route: '#/employee/home', checkSelector: '.app-main' },
      { name: 'Company Home', route: '#/company/home', checkSelector: '.app-main' },
      { name: 'Onboarding Flow', route: '#/onboarding', checkSelector: '#mainContent' }
    ];

    for (const p of pagesToVerify) {
      await page.evaluate((r) => { window.location.hash = r; }, p.route);
      await sleep(300);
      const exists = await page.$(p.checkSelector);
      assert.ok(exists, `Page selector missing for ${p.name} on ${p.route}`);
      console.log(`   ✓ ${p.name} (${p.route}) rendered cleanly`);
    }

    // ------------------------------------------------------------------------
    // Step 3 API & Network Audit Check
    // ------------------------------------------------------------------------
    console.log('\n--- [Step 3: Network & API Audit] ---');
    console.log(`Total Core Intelligence API requests tracked in browser: ${networkRequests.length}`);
    assert.ok(networkRequests.length >= 4, 'Expected real HTTP requests over the wire');
    const allHaveAuth = networkRequests.every(r => r.hasAuth);
    console.log(`All requests carried Authorization Bearer header: ${allHaveAuth}`);
    assert.ok(allHaveAuth, 'All live intelligence requests must transmit Bearer authorization');

  } finally {
    await browser.close();
    if (existsSync(TOKENS_PATH)) {
      unlinkSync(TOKENS_PATH);
    }
  }

  console.log('\n================================================================');
  console.log(' ALL G2.7 LIVE BROWSER VERIFICATION FLOWS PASSED SUCCESSFULLY!');
  console.log('================================================================\n');
}

runLiveBrowserVerification().catch(err => {
  console.error('\n❌ LIVE BROWSER VERIFICATION FAILED:');
  console.error(err);
  process.exit(1);
});
