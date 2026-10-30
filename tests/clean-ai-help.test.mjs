import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';

// Set up localStorage mock
const mockStorage = new Map();
globalThis.localStorage = {
  getItem: key => mockStorage.get(key) || null,
  setItem: (key, val) => mockStorage.set(key, String(val)),
  removeItem: key => mockStorage.delete(key),
  clear: () => mockStorage.clear()
};

test('CleanAIHelp Component & Live Supervisor Backend Verification', async t => {
  await t.test('1. CleanAIHelp source verification', async () => {
    const cleanHelpPath = path.resolve('src/pages/individual/assistant/CleanAIHelp.js');
    assert.ok(fs.existsSync(cleanHelpPath), 'CleanAIHelp.js file must exist');

    const source = fs.readFileSync(cleanHelpPath, 'utf8');
    assert.ok(source.includes('sendSupervisorMessage'), 'Must import and call sendSupervisorMessage');
    assert.ok(source.includes('buildUserContext'), 'Must import and call buildUserContext');
    assert.ok(source.includes('handleSubmit'), 'Must implement handleSubmit');
    assert.ok(source.includes('tools_invoked'), 'Must render tools_invoked badges');
    assert.ok(!source.includes('queryCoreIntelligenceAnswer'), 'Must NOT call legacy queryCoreIntelligenceAnswer');
    assert.ok(!source.includes('queryCoreIntelligencePlan'), 'Must NOT call legacy queryCoreIntelligencePlan');
  });

  await t.test('2. App.js route registration verification', async () => {
    const appPath = path.resolve('src/App.js');
    assert.ok(fs.existsSync(appPath), 'src/App.js must exist');
    const appSource = fs.readFileSync(appPath, 'utf8');
    assert.ok(appSource.includes('/individual/clean-help'), 'Must define route /individual/clean-help');
    assert.ok(appSource.includes('CleanAIHelp'), 'Must render CleanAIHelp component');
  });

  await t.test('3. Live Execution: "What are the trending skills for AI Engineer?"', async () => {
    const { sendSupervisorMessage, buildUserContext } = await import('../src/services/supervisor-api.js');

    const userPrompt = 'What are the trending skills for AI Engineer?';
    const messages = [
      { role: 'user', content: userPrompt }
    ];
    const userContext = buildUserContext({
      target_role: 'AI Engineer',
      location: 'India'
    });

    console.log('\n======================================================================');
    console.log('SENDING PROMPT VIA SUPERVISOR API:');
    console.log(`Prompt: "${userPrompt}"`);
    console.log(`Target Role Context: "${userContext.target_role}"`);
    console.log('======================================================================');

    const response = await sendSupervisorMessage(messages, userContext);

    console.log('\n======================================================================');
    console.log('EXACT JSON RESPONSE RETURNED BY SUPERVISOR BACKEND:');
    console.log('======================================================================');
    console.log(JSON.stringify(response, null, 2));
    console.log('======================================================================\n');

    // Verification 1: Both tools must be executed for this multi-part query
    assert.ok(
      response.tools_invoked.includes('analyze_market_ecosystem'),
      'Must invoke analyze_market_ecosystem for trending skills inquiry'
    );
    assert.ok(
      response.tools_invoked.includes('analyze_skill_gap'),
      'Must invoke analyze_skill_gap for specific role readiness (AI Engineer)'
    );

    // Verification 2: Legacy wrapper strings must be completely absent
    const fullJson = JSON.stringify(response);
    assert.ok(!fullJson.includes('Understood:'), 'Legacy string "Understood:" must be completely absent');
    assert.ok(!fullJson.includes('I understand you'), 'Legacy string "I understand you" must be completely absent');

    // Verification 3: Section 6 Evidence check
    assert.ok(response.evidence_payloads.length >= 2, 'Must deliver multi-tool evidence payloads');
    assert.ok(response.answer.includes('Macro Developer Ecosystem Overview') || response.answer.includes('Developer Community Traction'));
    assert.ok(response.answer.includes('AI Engineer'));
  });
});

