import assert from 'node:assert/strict';
import { renderConversationAnswer } from '../src/components/common/ConversationAnswer.js';

const block = {
  answer_block: {
    verdict: 'Python — High demand in collected postings (28 of 114)',
    summary: 'Current snapshot only.',
    table: {
      columns: ['Skill', 'Postings', 'Demand'],
      rows: [{ Skill: 'Python', Postings: 28, Demand: 'High' }]
    },
    bullets: [],
    clarification: {
      classification: 'TOO BROAD',
      slot: 'location',
      round_count: 1,
      options: [
        { label: 'Bengaluru (82)', value: 'Bengaluru' },
        { label: 'Show everything', value: 'Show everything' },
        { label: 'Skip', value: 'Skip' }
      ]
    },
    footer: {
      based_on: 'Firestore jobs.skills_raw',
      disclosures: [
        'Sample size: N=114 all stored India postings after dedupe.',
        'Developer adoption measures developer activity, not hiring demand.'
      ]
    }
  }
};

const html = renderConversationAnswer(block, value => String(value));
assert.match(html, /assistant-answer-block__verdict/);
assert.match(html, /<table/);
assert.match(html, /<th scope="col">Skill<\/th>/);
assert.match(html, /Based on:<\/strong> Firestore jobs\.skills_raw/);
assert.match(html, /Sample size: N=114/);
assert.match(html, /not hiring demand/);
assert.match(html, /data-clarification-reply="Bengaluru"/);
assert.match(html, /Bengaluru \(82\)/);
assert.match(html, /data-clarification-reply="Show everything"/);
assert.match(html, /data-clarification-reply="Skip"/);
assert.doesNotMatch(html, /firestore_request_reads/);
console.log('structured-answer-blocks: passed');
