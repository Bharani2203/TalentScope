import assert from 'node:assert/strict';
import {
  loadLearningRoadmapState,
  calculateRoadmapProgress,
  ROADMAP_PRESETS,
  roadmapStorageKey
} from '../src/data/roadmap-data.js';

// Setup minimal localStorage mock for testing environment
globalThis.localStorage = (() => {
  let store = {};
  return {
    getItem: (k) => store[k] || null,
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear: () => { store = {}; }
  };
})();

console.log('--- STARTING G2.6 REMEDIATION UNIT TESTS ---');

// Test 1: Empty Roadmap Contract
{
  localStorage.clear();
  const state = loadLearningRoadmapState();
  assert.equal(state.status, 'none', 'Unset roadmap must have status "none"');
  assert.equal(state.progress, 0, 'Unset roadmap must have progress 0%');
  assert.equal(state.title, 'No Active Roadmap', 'Title must be "No Active Roadmap"');
  assert.equal(state.currentStep?.name, 'Choose a learning path', 'Current step must be "Choose a learning path"');
  assert.deepEqual(state.milestones, [], 'Milestones must be empty array');
  console.log('PASS: Empty Roadmap Contract returns honest zero state');
}

// Test 2: Progress calculation on empty roadmap
{
  const emptyProgress = calculateRoadmapProgress({ status: 'none', milestones: [] });
  assert.equal(emptyProgress, 0, 'calculateRoadmapProgress must return 0 for status none');
  console.log('PASS: calculateRoadmapProgress returns 0 for status none');
}

// Test 3: Active Roadmap preservation
{
  localStorage.clear();
  const preset = JSON.parse(JSON.stringify(ROADMAP_PRESETS['Improve Skill']));
  preset.status = 'active';
  localStorage.setItem(roadmapStorageKey, JSON.stringify(preset));

  const loaded = loadLearningRoadmapState();
  assert.equal(loaded.status, 'active');
  assert.equal(loaded.skill, 'Python');
  assert.ok(loaded.milestones.length > 0);
  console.log('PASS: Saved active roadmap correctly deserialized');
}

// Test 4: Learning.js Exports Audit
{
  const learningModule = await import('../src/pages/individual/learning/Learning.js');
  assert.equal(typeof learningModule.renderDedicatedLearningPage, 'function', 'renderDedicatedLearningPage must be exported');
  assert.equal(typeof learningModule.renderLearningPage, 'function', 'renderLearningPage must be exported');
  console.log('PASS: Learning.js exports renderDedicatedLearningPage and renderLearningPage');
}

console.log('ALL G2.6 REMEDIATION UNIT TESTS PASSED!');
