import assert from 'node:assert/strict';
import test from 'node:test';

// Set up localStorage mock
const mockStorage = new Map();
globalThis.localStorage = {
  getItem: key => mockStorage.get(key) || null,
  setItem: (key, val) => mockStorage.set(key, String(val)),
  removeItem: key => mockStorage.delete(key),
  clear: () => mockStorage.clear()
};

test('Supervisor Frontend Phase 3 Integration Suite', async t => {
  // 1. Test buildUserContext reading from localStorage
  await t.test('1. buildUserContext reads profile, skills, and target role from localStorage', async () => {
    mockStorage.clear();
    mockStorage.set('talentscope-saved-roles', JSON.stringify(['Cloud Solutions Architect', 'AI Engineer']));
    mockStorage.set('talentscope-onboarding-profile', JSON.stringify({
      targetRole: 'Cloud Solutions Architect',
      skills: ['AWS', 'Docker', 'Kubernetes']
    }));
    mockStorage.set('talentscope-saved-skills', JSON.stringify(['AWS', 'Docker', 'Kubernetes', 'Terraform']));

    const { buildUserContext } = await import('../src/services/supervisor-api.js');
    const context = buildUserContext();

    assert.equal(context.target_role, 'Cloud Solutions Architect');
    assert.equal(context.location, 'India');
    assert.equal(context.current_view, '');
    assert.ok(context.user_skills.includes('AWS'));
    assert.ok(context.user_skills.includes('Terraform'));

    // Test overrides
    const overridden = buildUserContext({
      current_view: 'AI Engineer',
      location: 'Bengaluru'
    });
    assert.equal(overridden.target_role, 'Cloud Solutions Architect');
    assert.equal(overridden.current_view, 'AI Engineer');
    assert.equal(overridden.location, 'Bengaluru');
  });

  // 2. Test sendSupervisorMessage calling POST /api/assistant/chat with multi-turn memory
  await t.test('2. sendSupervisorMessage transmits multi-turn messages and user_context', async () => {
    const originalFetch = globalThis.fetch;
    const calls = [];

    const mockApiResponse = {
      answer: 'Found 2 verified live job openings for AI Engineer in Bengaluru.',
      tools_invoked: ['fetch_live_job_openings', 'analyze_skill_gap'],
      evidence_payloads: [
        {
          tool: 'fetch_live_job_openings',
          count: 1,
          jobs: [
            {
              job_title: 'Senior AI Engineer',
              normalized_role: 'AI Engineer',
              company_name: 'Thoughtworks',
              location_city: 'Bengaluru',
              source_provider: 'Greenhouse',
              apply_url: 'https://boards.greenhouse.io/thoughtworks/jobs/401',
              required_skills: ['Python', 'PyTorch', 'Docker']
            }
          ]
        },
        {
          tool: 'analyze_skill_gap',
          readiness_score: 80,
          matched_skills: ['Python', 'Docker'],
          missing_skills: ['PyTorch']
        }
      ],
      suggested_followups: [
        'What is the historical hiring demand in Bengaluru?',
        'Show market ecosystem signals for PyTorch'
      ],
      provenance_summary: 'Unified Supervisor Agent evidence synthesis'
    };

    globalThis.fetch = async (url, options) => {
      calls.push({ url, options, body: JSON.parse(options.body) });
      return new Response(JSON.stringify(mockApiResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    try {
      const { sendSupervisorMessage } = await import('../src/services/supervisor-api.js');

      // Turn 1
      const turn1Messages = [{ role: 'user', content: 'Show me live AI Engineer openings in Bengaluru' }];
      const turn1Context = { target_role: 'AI Engineer', current_view: 'AI Engineer', location: 'Bengaluru' };
      const resp1 = await sendSupervisorMessage(turn1Messages, turn1Context);

      assert.equal(resp1.answer, mockApiResponse.answer);
      assert.deepEqual(resp1.tools_invoked, ['fetch_live_job_openings', 'analyze_skill_gap']);
      assert.equal(resp1.evidence_payloads.length, 2);
      assert.equal(resp1.suggested_followups.length, 2);

      // Turn 2: Multi-turn continuation
      const turn2Messages = [
        ...turn1Messages,
        { role: 'assistant', content: resp1.answer },
        { role: 'user', content: 'What about their skill requirements?' }
      ];
      await sendSupervisorMessage(turn2Messages, turn1Context);

      assert.equal(calls.length, 2);
      assert.equal(calls[0].body.messages.length, 1);
      assert.equal(calls[1].body.messages.length, 3);
      assert.equal(calls[1].body.messages[2].content, 'What about their skill requirements?');
      assert.equal(calls[1].body.user_context.target_role, 'AI Engineer');
      assert.equal(calls[1].body.user_context.location, 'Bengaluru');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  // 3. Test streamSupervisorMessage callback execution
  await t.test('3. streamSupervisorMessage invokes callbacks gracefully', async () => {
    const originalFetch = globalThis.fetch;
    const mockApiResponse = {
      answer: 'PyTorch and Docker demand has risen 24% MoM.',
      tools_invoked: ['analyze_market_ecosystem'],
      evidence_payloads: [{ tool: 'analyze_market_ecosystem', total_signals_tracked: 120 }],
      suggested_followups: ['Show live openings'],
      provenance_summary: 'Ecosystem telemetry'
    };

    globalThis.fetch = async () => {
      return new Response(JSON.stringify(mockApiResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    };

    try {
      const { streamSupervisorMessage } = await import('../src/services/supervisor-api.js');
      const toolCalls = [];
      const evidence = [];
      let tokenReceived = '';
      let donePayload = null;

      const result = await streamSupervisorMessage(
        [{ role: 'user', content: 'Analyze PyTorch ecosystem' }],
        { target_role: 'AI Engineer' },
        {
          onToolCall: tool => toolCalls.push(tool),
          onEvidence: ev => evidence.push(ev),
          onToken: token => { tokenReceived += token; },
          onDone: res => { donePayload = res; }
        }
      );

      assert.ok(result.answer.includes('PyTorch'));
      assert.ok(toolCalls.includes('analyze_market_ecosystem'));
      assert.equal(evidence.length, 1);
      assert.equal(donePayload.answer, result.answer);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  // 4. Test Career.js markup and evidence rendering contracts
  await t.test('4. Career.js renders multi-turn conversation thread, job evidence cards, and followup chips', async () => {
    const { readFile } = await import('node:fs/promises');
    const careerSource = await readFile(new URL('../src/pages/individual/career/Career.js', import.meta.url), 'utf8');

    // DOM IDs and containers
    assert.ok(careerSource.includes('id="jiConversationThread"'), 'Conversation thread container is present');
    assert.ok(careerSource.includes('id="jiConsoleQueryInput"'), 'Query input field is present');
    assert.ok(careerSource.includes('id="btnRunJobAnalysis"'), 'Run analysis button is present');

    // Multi-turn and Supervisor integration
    assert.ok(careerSource.includes('sendSupervisorMessage(ui.consoleMessages'), 'Calls sendSupervisorMessage with multi-turn messages');
    assert.ok(careerSource.includes('renderConsoleMessageHTML(msg, index)'), 'Renders conversation messages');
    assert.ok(careerSource.includes('renderSupervisorEvidence(msg.evidence)'), 'Renders evidence payloads');
    assert.ok(careerSource.includes('ji-tool-pill'), 'Renders tool pills for invoked supervisor tools');
    assert.ok(careerSource.includes('ji-evidence-job-card'), 'Renders structured live job evidence cards');
    assert.ok(careerSource.includes('ji-job-apply-link'), 'Renders clickable apply links');
    assert.ok(careerSource.includes('data-action="ask-followup"'), 'Renders interactive follow-up chips');
  });

  // 5. Test SkillIntelligence.js console wiring
  await t.test('5. SkillIntelligence.js console wires to sendSupervisorMessage with skill context', async () => {
    const { readFile } = await import('node:fs/promises');
    const skillSource = await readFile(new URL('../src/pages/individual/skills/SkillIntelligence.js', import.meta.url), 'utf8');

    assert.ok(skillSource.includes('sendSupervisorMessage'), 'SkillIntelligence imports/uses sendSupervisorMessage');
    assert.ok(skillSource.includes('current_view: skill'), 'Passes active skill in user_context.current_view');
    assert.ok(skillSource.includes('data-form="analysis"'), 'Analysis form is preserved');
    assert.ok(skillSource.includes('use-console-question'), 'Question selection buttons are preserved');
  });
});

