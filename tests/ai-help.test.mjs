import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import {
  AI_HELP_MAX_QUESTION_LENGTH,
  AI_HELP_RESPONSE_MODE,
  getTemporaryHelpResponse
} from '../src/pages/individual/ai-help/ai-help-service.js';

test('temporary help answers are labelled demo and explain Skill Intelligence without platform data', async () => {
  const result = await getTemporaryHelpResponse('How do I use Skill Intelligence?');
  assert.equal(result.status, 'ok');
  assert.equal(result.mode, 'demo');
  assert.match(result.text, /^Temporary help response:/);
  assert.match(result.text, /My Skills/);
  assert.match(result.text, /does not read or analyze your profile data/);
});

test('temporary help covers every requested suggestion with clearly labelled responses', async () => {
  const questions = [
    'How do I use Skill Intelligence?',
    'How can I explore Market Intelligence?',
    'How do I find job opportunities?',
    'How can companies identify employee skill gaps?',
    'What does insufficient data mean?',
    'How do I navigate the platform?'
  ];

  for (const question of questions) {
    const result = await getTemporaryHelpResponse(question);
    assert.equal(result.mode, AI_HELP_RESPONSE_MODE);
    assert.match(result.text, /^Temporary help response:/);
  }
});

test('temporary help rejects blank and over-limit questions', async () => {
  await assert.rejects(getTemporaryHelpResponse('  '), /Enter a question/);
  await assert.rejects(getTemporaryHelpResponse('x'.repeat(AI_HELP_MAX_QUESTION_LENGTH + 1)), /1200 characters/);
});

test('AI Help is hidden and its old route redirects to the Assistant', async () => {
  const [appSource, navigationSource] = await Promise.all([
    readFile(new URL('../src/app/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/portals/individual/navigation.js', import.meta.url), 'utf8')
  ]);
  for (const source of [appSource, navigationSource]) {
    assert.doesNotMatch(source, /label: 'AI Help', icon: 'messages-square', route: '\/individual\/ai-help'/);
  }
  assert.match(appSource, /routePath === '\/individual\/ai-help'[\s\S]{0,100}window\.location\.hash = '#\/individual\/ai-assistant'/);
  assert.doesNotMatch(appSource, /import\('\.\.\/pages\/individual\/ai-help\/AiHelp\.js'\)/);
});

test('AI Help page includes required copy actions, demo marker, and suggestion cards', async () => {
  const pageSource = await readFile(new URL('../src/pages/individual/ai-help/AiHelp.js', import.meta.url), 'utf8');
  assert.match(pageSource, /Get help using TalentScope\.ai\./);
  assert.match(pageSource, /Hi! Welcome to TalentScope\.ai Help\./);
  assert.match(pageSource, /Temporary help response · demo/);
  assert.match(pageSource, /data-ai-help-action="copy"/);
  assert.match(pageSource, /data-ai-help-action="clear"/);
  assert.match(pageSource, /Shift\+Enter for a new line/);
});
