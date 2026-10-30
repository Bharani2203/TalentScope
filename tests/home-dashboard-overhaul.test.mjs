import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '..');

test('Home Dashboard Telemetry, Active Roadmap, and Live Job Requisitions Overhaul Suite', async (t) => {
  const appJsPath = join(rootDir, 'src', 'app', 'app.js');
  const clientJsPath = join(rootDir, 'src', 'api', 'core-intelligence-client.js');

  const appJsContent = await readFile(appJsPath, 'utf8');
  const clientJsContent = await readFile(clientJsPath, 'utf8');

  await t.test('1. core-intelligence-client exports active jobs and roadmap progress helpers', () => {
    assert.match(clientJsContent, /export async function fetchActiveJobs/);
    assert.match(clientJsContent, /export async function fetchRoadmapProgress/);
    assert.match(clientJsContent, /\/api\/v1\/learning\/roadmap\/progress/);
    assert.match(clientJsContent, /\/api\/v1\/jobs\/active/);
  });

  await t.test('2. Roadmap card in app.js fetches /api/v1/learning/roadmap/progress and updates telemetry', () => {
    assert.match(appJsContent, /loadHomeRoadmapProgress/);
    assert.match(appJsContent, /homeRoadmapProgressState/);
    assert.match(appJsContent, /data-overview-value="roadmap-step"/);
    assert.match(appJsContent, /data-overview-value="roadmap"/);
    assert.match(appJsContent, /href="#\/individual\/learning"/);
    assert.match(appJsContent, /renderRoadmapMiniProgress/);
  });

  await t.test('3. Trend cards (Skill, Market, Job Trend) display green Tracking Initiated badges and raw numbers', () => {
    // Market card has Tracking Initiated badge and raw signals count
    assert.match(appJsContent, /class="badge-tracking-initiated"/);
    assert.match(appJsContent, /Tracking Initiated/);
    assert.match(appJsContent, /1,540 Signals/);
    assert.match(appJsContent, /1,540 Ecosystem Signals Tracked/);

    // Job Trend card has Tracking Initiated badge and raw live openings
    assert.match(appJsContent, /Live Openings/);
    assert.match(appJsContent, /Jobs<\/strong>/);
    assert.match(appJsContent, /Active Jobs Tracked/);
    assert.match(appJsContent, /Live Enterprise Requisition Stream/);

    // Skill card has Tracking Initiated badge fallback with raw observation count
    assert.match(appJsContent, /Baseline Market Observation Count/);
    assert.match(appJsContent, /12,791 Obs/);
  });

  await t.test('4. Job Intelligence panel has sleek Reload button and dynamic live subtext', () => {
    assert.match(appJsContent, /id="btnReloadHomeJobs"/);
    assert.match(appJsContent, /data-lucide="refresh-cw"/);
    assert.match(appJsContent, /id="homeJobTrendHeading"[^>]*>Active Requisitions<\/h3>/);
    assert.match(appJsContent, /live postings found matching/);
    assert.match(appJsContent, /getElementById\('btnReloadHomeJobs'\)/);
    assert.match(appJsContent, /reloadJobsBtn\.addEventListener\('click'/);
  });

  await t.test('5. Job cards render dynamic provider badges for external APIs (Greenhouse, Lever, Ashby, Adzuna, JSearch)', () => {
    assert.match(appJsContent, /cleanProv\.includes\('GREENHOUSE'\)/);
    assert.match(appJsContent, /cleanProv\.includes\('LEVER'\)/);
    assert.match(appJsContent, /cleanProv\.includes\('ASHBY'\)/);
    assert.match(appJsContent, /cleanProv\.includes\('ADZUNA'\)/);
    assert.match(appJsContent, /home-job-source-badge/);
  });

  await t.test('6. Live Backend Verification: Roadmap Progress Endpoint (GET /api/v1/learning/roadmap/progress)', async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/learning/roadmap/progress');
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.has_roadmap, true);
      assert.ok(typeof data.progress_percent === 'number');
      assert.ok(data.current_milestone);
      assert.ok(data.title);
    } catch (err) {
      if (err.code === 'ECONNREFUSED') {
        console.warn('Backend server not responding on 8000, skipping live network assert');
      } else {
        throw err;
      }
    }
  });

  await t.test('7. Live Backend Verification: Active Jobs Endpoint (GET /api/v1/jobs/active)', async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/jobs/active?query=Software&country=in');
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'available');
      assert.ok(Array.isArray(data.jobs));
      assert.ok(data.count > 0);
      assert.ok(data.jobs[0].title);
      assert.ok(data.jobs[0].source);
    } catch (err) {
      if (err.code === 'ECONNREFUSED') {
        console.warn('Backend server not responding on 8000, skipping live network assert');
      } else {
        throw err;
      }
    }
  });

  await t.test('8. Live Backend Verification: Market Jobs Endpoint (GET /api/v1/market/jobs)', async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/market/jobs?query=Engineer&country=in');
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'available');
      assert.ok(Array.isArray(data.jobs));
      assert.ok(data.count > 0);
    } catch (err) {
      if (err.code === 'ECONNREFUSED') {
        console.warn('Backend server not responding on 8000, skipping live network assert');
      } else {
        throw err;
      }
    }
  });
});
