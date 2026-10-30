import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '..');

test('Intelligence Dashboard Fallbacks, 1-Hour Caching, and Concurrency Verification Suite', async (t) => {
  const skillIntelligencePath = join(rootDir, 'src', 'pages', 'individual', 'skills', 'SkillIntelligence.js');
  const marketIntelligencePath = join(rootDir, 'src', 'pages', 'individual', 'market', 'MarketIntelligence.js');
  const appJsPath = join(rootDir, 'src', 'app', 'app.js');
  const liveConnectorsPath = join(rootDir, 'backend', 'app', 'services', 'live_job_connectors.py');
  const marketRoutePath = join(rootDir, 'backend', 'app', 'api', 'routes', 'market.py');
  const skillRoutePath = join(rootDir, 'backend', 'app', 'api', 'routes', 'skill_intelligence.py');
  const marketOverviewPath = join(rootDir, 'backend', 'app', 'api', 'routes', 'market_intelligence.py');

  const [
    skillContent,
    marketContent,
    appContent,
    liveConnectorsContent,
    marketRouteContent,
    skillRouteContent,
    marketOverviewContent
  ] = await Promise.all([
    readFile(skillIntelligencePath, 'utf8'),
    readFile(marketIntelligencePath, 'utf8'),
    readFile(appJsPath, 'utf8'),
    readFile(liveConnectorsPath, 'utf8'),
    readFile(marketRoutePath, 'utf8'),
    readFile(skillRoutePath, 'utf8'),
    readFile(marketOverviewPath, 'utf8')
  ]);

  await t.test('1. Frontend SkillIntelligence.js handles is_baseline_only with exact tooltip copy', () => {
    assert.match(skillContent, /is_baseline_only/, 'SkillIntelligence must check is_baseline_only');
    assert.match(skillContent, /Showing current snapshot \(historical trend data pending\)/, 'Must contain exact required tooltip copy');
    assert.match(skillContent, /Snapshot/, 'Must render Snapshot badge for baseline data');
  });

  await t.test('2. Frontend MarketIntelligence.js handles is_baseline_only with exact tooltip copy', () => {
    assert.match(marketContent, /is_baseline_only/, 'MarketIntelligence must check is_baseline_only');
    assert.match(marketContent, /Showing current snapshot \(historical trend data pending\)/, 'Must contain exact required tooltip copy');
  });

  await t.test('3. Frontend app.js Home Dashboard handles is_baseline_only with exact tooltip copy', () => {
    assert.match(appContent, /is_baseline_only/, 'app.js must track is_baseline_only');
    assert.match(appContent, /Showing current snapshot \(historical trend data pending\)/, 'Must contain exact required tooltip copy in home view');
  });

  await t.test('4. Backend live_job_connectors.py implements TTLCache(ttl=3600) and ThreadPoolExecutor concurrency', () => {
    assert.match(liveConnectorsContent, /TTLCache\s*\(\s*maxsize\s*=\s*\d+,\s*ttl\s*=\s*3600\s*\)/, 'Must configure exact 1-hour TTL (3600s) cache');
    assert.match(liveConnectorsContent, /ThreadPoolExecutor/, 'Must use concurrent ThreadPoolExecutor for external providers');
    assert.match(liveConnectorsContent, /timeout\s*=\s*6\.0/, 'Must specify strict timeout per provider');
  });

  await t.test('5. Backend market.py implements TTLCache(ttl=3600) for job search queries', () => {
    assert.match(marketRouteContent, /TTLCache\s*\(\s*maxsize\s*=\s*\d+,\s*ttl\s*=\s*3600\s*\)/, 'Must configure 1-hour (3600s) TTL cache in market.py');
    assert.match(marketRouteContent, /_MARKET_JOBS_CACHE/, 'Must reference market jobs cache');
  });

  await t.test('6. Backend routes provide is_baseline_only field in skill and market intelligence', () => {
    assert.match(skillRouteContent, /is_baseline_only:\s*bool/, 'TrendingSkillItem must define is_baseline_only');
    assert.match(marketOverviewContent, /is_baseline_only:\s*bool/, 'MarketEcosystemOverview must define is_baseline_only');
  });

  // Live Backend Verification against running server on port 8000
  const BACKEND_BASE = 'http://127.0.0.1:8000';

  await t.test('7. Live Backend: GET /api/market-intelligence/overview returns valid response with is_baseline_only', async () => {
    try {
      const resp = await fetch(`${BACKEND_BASE}/api/market-intelligence/overview?role=AI%20Engineer&location=India`, {
        signal: AbortSignal.timeout(10000)
      });
      assert.equal(resp.status, 200, 'Market ecosystem endpoint must return 200');
      const data = await resp.json();
      assert.ok('is_baseline_only' in data, 'Response must have is_baseline_only field');
      assert.equal(typeof data.is_baseline_only, 'boolean', 'is_baseline_only must be a boolean');
      assert.ok(Array.isArray(data.emerging_technologies), 'emerging_technologies must be an array');
    } catch (err) {
      if (err.cause?.code === 'ECONNREFUSED') {
        assert.fail('FastAPI server is not responding at ' + BACKEND_BASE);
      }
      throw err;
    }
  });

  await t.test('8. Live Backend: GET /api/v1/jobs/active validates 1-hour cache hit performance (< 50ms)', async () => {
    const testQuery = 'Software';
    // Ensure cache is warmed
    const resp1 = await fetch(`${BACKEND_BASE}/api/v1/jobs/active?query=${testQuery}&country=in`, {
      signal: AbortSignal.timeout(20000)
    });
    assert.equal(resp1.status, 200, 'First call must return 200 OK');
    const data1 = await resp1.json();
    assert.equal(data1.status, 'available');
    assert.ok(Array.isArray(data1.jobs));
    assert.ok(data1.count > 0);

    // Second call: Should hit in-memory TTLCache immediately (< 50ms)
    const start2 = performance.now();
    const resp2 = await fetch(`${BACKEND_BASE}/api/v1/jobs/active?query=${testQuery}&country=in`, {
      signal: AbortSignal.timeout(5000)
    });
    const duration2 = performance.now() - start2;
    assert.equal(resp2.status, 200, 'Second call must return 200 OK');
    const data2 = await resp2.json();
    assert.equal(data2.status, 'available');
    assert.equal(data2.jobs.length, data1.jobs.length, 'Cached response must match first call data length');
    assert.ok(duration2 < 50, `Cached call must resolve in < 50ms, took ${duration2.toFixed(2)}ms`);
  });

  await t.test('9. Section 6 Compliance: Job items contain verifiable provenance and zero hallucinations', async () => {
    const resp = await fetch(`${BACKEND_BASE}/api/v1/jobs/active?query=Software&country=in`, {
      signal: AbortSignal.timeout(10000)
    });
    assert.equal(resp.status, 200);
    const data = await resp.json();
    assert.ok(data.jobs && data.jobs.length > 0, 'Must return at least one authentic job');
    for (const job of data.jobs.slice(0, 5)) {
      assert.ok(job.title && job.title.trim().length > 0, 'Job title must not be empty');
      assert.ok(job.company_name && job.company_name.trim().length > 0, 'Job company_name must not be empty');
      assert.ok(job.source_url && job.source_url.startsWith('http'), 'Job source_url must be a valid HTTP URL');
      assert.ok(job.source && job.source.trim().length > 0, 'Job must have verifiable source provider');
      assert.ok(job.source_type && job.source_type.trim().length > 0, 'Job must have verifiable source_type');
    }
  });
});

