import assert from 'node:assert/strict';
import test from 'node:test';
import { formatMarkdown, renderEvidenceCards } from '../src/pages/individual/assistant/CleanAIHelp.js';
import CleanAIHelp from '../src/pages/individual/assistant/CleanAIHelp.js';
import { sendSupervisorMessage, buildUserContext } from '../src/services/supervisor-api.js';

test('AI Co-Pilot (Chat Interface) Enhanced Conversational & Structured Rendering Suite', async t => {
  await t.test('1. formatMarkdown renders formatted text, headers, lists, code, and links', () => {
    const rawMarkdown = `
### Concept Overview
Machine Learning is a **branch** of *artificial intelligence*.
Key techniques include:
- Supervised learning with \`scikit-learn\`
- Neural networks with \`pytorch\`

Visit [Official Docs](https://python.org) for details.
`;

    const html = formatMarkdown(rawMarkdown);

    // Header rendering
    assert.ok(html.includes('<h4'), '### headers must render as <h4>');
    assert.ok(html.includes('Concept Overview'), 'Header text must be preserved');

    // Bold, italic, code
    assert.ok(html.includes('<strong>branch</strong>'), 'Double asterisks must render as <strong>');
    assert.ok(html.includes('<em>artificial intelligence</em>'), 'Single asterisks must render as <em>');
    assert.ok(html.includes('<code'), 'Backtick code must render as <code>');
    assert.ok(html.includes('scikit-learn'), 'Inline code contents must be preserved');

    // Bullet lists
    assert.ok(html.includes('<ul'), 'Markdown bullets must be wrapped in <ul>');
    assert.ok(html.includes('<li'), 'Markdown bullets must render as <li>');

    // Clickable links
    assert.ok(html.includes('<a href="https://python.org"'), 'Markdown links must convert to <a href>');
    assert.ok(html.includes('target="_blank"'), 'Links must open in new tab with target="_blank"');
    assert.ok(html.includes('rel="noopener noreferrer"'), 'Links must have rel="noopener noreferrer"');
    assert.ok(html.includes('Official Docs</a>'), 'Link anchor text must be preserved');
  });

  await t.test('2. formatMarkdown renders responsive markdown comparison tables', () => {
    const comparisonMarkdown = `
| Dimension | Artificial Intelligence (AI) | Machine Learning (ML) |
|---|---|---|
| Scope | Broad umbrella field | Specific subfield of AI |
| Approach | Logic, search algorithms, rules, learning | Statistical algorithms learning from data |
| Goal | Simulate natural intelligence | Learn tasks autonomously from data |
`;

    const html = formatMarkdown(comparisonMarkdown);

    // Table elements
    assert.ok(html.includes('<div class="ai-table-wrap"'), 'Table must be wrapped in responsive container');
    assert.ok(html.includes('<table class="ai-table"'), 'Table element must have class ai-table');
    assert.ok(html.includes('<thead><tr>'), 'Table must contain <thead> with header cells');
    assert.ok(html.includes('<th'), 'Header cells must use <th>');
    assert.ok(html.includes('Artificial Intelligence (AI)'), 'Header text must be preserved');
    assert.ok(html.includes('<tbody>'), 'Table must contain <tbody> with body rows');
    assert.ok(html.includes('<td'), 'Data cells must use <td>');
    assert.ok(html.includes('Broad umbrella field'), 'Cell content must be preserved');
    assert.ok(html.includes('Specific subfield of AI'), 'Comparison content must be preserved');
  });

  await t.test('3. renderEvidenceCards gracefully handles null, empty, and conversational queries', () => {
    // Zero empty containers for conversational queries
    assert.equal(renderEvidenceCards(null), '', 'Null evidence must return empty string');
    assert.equal(renderEvidenceCards(undefined), '', 'Undefined evidence must return empty string');
    assert.equal(renderEvidenceCards([]), '', 'Empty evidence array must return empty string');
    assert.equal(renderEvidenceCards([{ tool: 'general_qa' }]), '', 'Conversational QA must return empty string (no empty containers)');
    assert.equal(renderEvidenceCards([{ tool: 'fetch_live_job_openings', jobs: null }]), '', 'Missing jobs must not render broken container');
    assert.equal(renderEvidenceCards([{ tool: 'fetch_live_job_openings', jobs: [] }]), '', 'Empty jobs array must return empty string');
  });

  await t.test('4. renderEvidenceCards renders structured live job cards with apply links', () => {
    const jobEvidence = [
      {
        tool: 'fetch_live_job_openings',
        jobs: [
          {
            job_title: 'Senior Remote Python Developer',
            company_name: 'TechCorp India',
            location_city: 'Remote / Bengaluru',
            required_skills: ['Python', 'FastAPI', 'Docker', 'AWS'],
            source_provider: 'Enterprise ATS',
            apply_url: 'https://techcorp.com/careers/python-dev-123'
          }
        ]
      }
    ];

    const html = renderEvidenceCards(jobEvidence);

    assert.ok(html.includes('Verified Live Openings (1)'), 'Must render verified live openings header with count');
    assert.ok(html.includes('Senior Remote Python Developer'), 'Must render job title');
    assert.ok(html.includes('TechCorp India'), 'Must render company name');
    assert.ok(html.includes('Remote / Bengaluru'), 'Must render location');
    assert.ok(html.includes('Enterprise ATS'), 'Must render provider badge');
    assert.ok(html.includes('FastAPI'), 'Must render required skills');
    assert.ok(html.includes('href="https://techcorp.com/careers/python-dev-123"'), 'Must render apply link');
  });

  await t.test('5. CleanAIHelp preserves conversation history in multi-turn interactions', async () => {
    const component = CleanAIHelp();
    assert.equal(typeof component.handleSubmit, 'function', 'Component must expose handleSubmit');

    const appends = [];
    const appendMessage = msg => appends.push(msg);

    // Call handleSubmit with previous turn history
    const existingMessages = [
      { role: 'user', content: 'What is Machine Learning?' },
      { role: 'assistant', content: 'Machine learning is a subset of AI focusing on data-driven learning.' }
    ];

    const result = await component.handleSubmit('Explain that more simply', appendMessage, existingMessages);

    assert.ok(result, 'handleSubmit must return a supervisor response');
    assert.ok(result.answer, 'Supervisor response must have an answer');
    assert.equal(appends.length, 2, 'Must append both user and assistant messages');
    assert.equal(appends[0].role, 'user');
    assert.equal(appends[0].content, 'Explain that more simply');
    assert.equal(appends[1].role, 'assistant');
    assert.ok(appends[1].content.length > 0);
  });

  await t.test('6. Live Verification: General Knowledge Query ("What is Machine Learning?")', async () => {
    const userContext = buildUserContext();
    const response = await sendSupervisorMessage(
      [{ role: 'user', content: 'What is Machine Learning?' }],
      userContext
    );

    assert.ok(response.answer, 'Must return an answer for general knowledge');
    assert.ok(
      response.answer.toLowerCase().includes('machine learning') || response.answer.toLowerCase().includes('data'),
      'Answer must explain machine learning'
    );
    // Conversational query does not invent job evidence
    const htmlEvidence = renderEvidenceCards(response.evidence_payloads);
    assert.equal(htmlEvidence, '', 'General knowledge must produce ZERO empty evidence card placeholders');
  });

  await t.test('7. Live Verification: Concept Comparison Query ("Compare AI and ML")', async () => {
    const userContext = buildUserContext();
    const response = await sendSupervisorMessage(
      [{ role: 'user', content: 'Compare AI and ML' }],
      userContext
    );

    assert.ok(response.answer, 'Must return an answer for concept comparison');
    assert.ok(response.answer.includes('|'), 'Comparison answer must contain a Markdown table');
    assert.ok(response.answer.includes('Dimension') || response.answer.includes('Scope'), 'Table must contain dimension headers');

    // Verify formatMarkdown formats this table cleanly
    const html = formatMarkdown(response.answer);
    assert.ok(html.includes('<table class="ai-table"'), 'Must format comparison into HTML table');
    assert.ok(html.includes('Artificial Intelligence') || html.includes('AI'), 'Must render AI column');
    assert.ok(html.includes('Machine Learning') || html.includes('ML'), 'Must render ML column');
  });

  await t.test('8. Live Verification: Structured Live Jobs Query ("Find Remote Python Jobs")', async () => {
    const userContext = buildUserContext();
    const response = await sendSupervisorMessage(
      [{ role: 'user', content: 'Find Remote Python Jobs' }],
      userContext
    );

    assert.ok(response.tools_invoked.includes('fetch_live_job_openings'), 'Must invoke fetch_live_job_openings');
    assert.ok(Array.isArray(response.evidence_payloads), 'Must return evidence payloads');

    // Verify structured job cards render
    const html = renderEvidenceCards(response.evidence_payloads);
    assert.ok(html.includes('Verified Live Openings'), 'Must render Verified Live Openings section');
    assert.ok(html.includes('ai-job-card'), 'Must render ai-job-card elements');
  });
});

