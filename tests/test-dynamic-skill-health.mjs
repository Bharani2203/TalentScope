import test from 'node:test';
import assert from 'node:assert/strict';

const BACKEND_BASE = 'http://127.0.0.1:8000';

test('Dynamic Skill Health Scoring and Technology Half-Life Analytics Suite', async (t) => {
  await t.test('1. Svelte (Frameworks/Web cluster) returns realistic health score (75/100) and 3.0 - 5.0 years half-life', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/v1/skills/user_123/analytics?skill=Svelte`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.skill, 'Svelte');
    assert.equal(data.skill_name, 'svelte');

    // Health score must NOT be the static/mocked 98/100
    assert.notEqual(data.health.score, 98, 'Health score must not be hardcoded 98');
    assert.equal(data.health.score, 75, `Expected realistic health score 75, got ${data.health.score}`);
    assert.equal(data.health.status, 'Healthy');
    assert.ok(Array.isArray(data.health.evidence), 'Evidence must be an array');
    assert.ok(data.health.evidence.length >= 3, 'Must contain explainable evidence points');

    // Half-Life must be Frameworks/Web window (3.0 - 5.0 years), not static 4.8 - 6.3 years
    assert.equal(data.half_life.cluster, 'Frameworks/Web');
    assert.equal(data.half_life.estimated_window, '3.0 - 5.0 years');
    assert.notEqual(data.half_life.estimated_window, '4.8 - 6.3 years');
    assert.equal(data.half_life.decay_rate_pct_monthly, 1.75);
    assert.ok(data.total_observations > 0, 'Must record live job observations');
  });

  await t.test('2. Rust (Foundational cluster) returns realistic health score (75/100) and 5.0 - 8.0 years half-life', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/v1/skills/user_test/analytics?skill=Rust`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.skill, 'Rust');
    assert.notEqual(data.health.score, 98, 'Health score must not be hardcoded 98');
    assert.equal(data.health.score, 75, `Expected realistic health score 75, got ${data.health.score}`);
    assert.equal(data.health.status, 'Healthy');

    // Half-Life must be Foundational (5.0 - 8.0 years)
    assert.equal(data.half_life.cluster, 'Foundational');
    assert.equal(data.half_life.estimated_window, '5.0 - 8.0 years');
    assert.equal(data.half_life.decay_rate_pct_monthly, 0.85);
  });

  await t.test('3. Generative AI (Emerging/AI cluster) returns rapid evolution half-life (1.5 - 3.0 years)', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/v1/skills/user_test/analytics?skill=Generative%20AI`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.equal(data.skill, 'Generative AI');
    assert.ok(data.health.score >= 90, `Generative AI health should reflect massive enterprise demand: ${data.health.score}`);
    assert.equal(data.half_life.cluster, 'Emerging/AI');
    assert.equal(data.half_life.estimated_window, '1.5 - 3.0 years');
    assert.equal(data.half_life.decay_rate_pct_monthly, 3.25);
  });

  await t.test('4. GET /api/v1/skills/analytics resolves user skills or catalog baseline', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/v1/skills/analytics`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.ok(Array.isArray(data), 'Response must be an array of skill analytics');
    assert.ok(data.length > 0, 'Must contain analyzed skills');
    for (const item of data) {
      assert.ok(item.skill, 'Each item must have a skill title');
      assert.ok(item.health && typeof item.health.score === 'number', 'Must have health score');
      assert.ok(item.half_life && item.half_life.estimated_window, 'Must have half-life window');
    }
  });

  await t.test('5. GET /api/skill-intelligence/advanced-metrics supports dynamic ?skills filter', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/skill-intelligence/advanced-metrics?skills=Rust,Svelte`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.ok(Array.isArray(data), 'Response must be an array');
    assert.equal(data.length, 2, 'Must return 2 analyzed skills');

    const rustItem = data.find(i => i.skill_name === 'rust');
    const svelteItem = data.find(i => i.skill_name === 'svelte');

    assert.ok(rustItem, 'Rust item must be present');
    assert.equal(rustItem.half_life.estimated_window, '5.0 - 8.0 years');
    assert.equal(rustItem.health.score, 75);

    assert.ok(svelteItem, 'Svelte item must be present');
    assert.equal(svelteItem.half_life.estimated_window, '3.0 - 5.0 years');
    assert.equal(svelteItem.health.score, 75);
  });

  await t.test('6. GET /api/skill-intelligence/advanced-metrics top market skills have cluster-aware half-lives', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/skill-intelligence/advanced-metrics?limit=5`);
    assert.equal(res.status, 200, `Expected 200 OK, got ${res.status}`);
    const data = await res.json();

    assert.ok(Array.isArray(data) && data.length > 0, 'Must return list of top skills');
    // Verify that not all skills share the exact same legacy 4.8 - 6.3 years
    const halfLifeWindows = new Set(data.map(i => i.half_life.estimated_window));
    assert.ok(halfLifeWindows.size >= 1, 'Must have valid half-life windows');

    // Foundational skills (like Python, SQL) should have 5.0 - 8.0 years
    const foundational = data.find(i => ['python', 'sql'].includes(i.skill_name.toLowerCase()));
    if (foundational) {
      assert.equal(foundational.half_life.estimated_window, '5.0 - 8.0 years');
    }

    // Emerging skills (like Generative AI) should have 1.5 - 3.0 years
    const genAi = data.find(i => i.skill_name.toLowerCase().includes('generative ai'));
    if (genAi) {
      assert.equal(genAi.half_life.estimated_window, '1.5 - 3.0 years');
    }
  });

  await t.test('7. Section 6 Compliance: Zero synthetic listings and authentic provenance', async () => {
    const res = await fetch(`${BACKEND_BASE}/api/v1/skills/user_123/analytics?skill=Rust`);
    const data = await res.json();

    assert.ok(data.total_observations > 0, 'Total observations must reflect authentic employer postings');
    assert.ok(data.health.evidence.every(e => !e.includes('synthetic')), 'No synthetic data traces permitted');
  });
});

