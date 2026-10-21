import assert from 'node:assert/strict';
import { resolveAssistantUserId } from '../src/auth/assistant-user-identity.js';

const storage = value => ({ getItem: key => key === 'talentscope_session_v2' ? value : null });

assert.equal(resolveAssistantUserId(storage(JSON.stringify({
  authSource: 'firebase',
  userId: 'firebase-user-a',
  user: { uid: 'firebase-user-a' }
}))), 'firebase-user-a');
assert.equal(resolveAssistantUserId(storage(JSON.stringify({
  authSource: 'firebase',
  userId: 'firebase-user-a',
  user: { uid: 'firebase-user-b' }
}))), 'anonymous', 'mismatched session identity cannot scope conversations');
assert.equal(resolveAssistantUserId(storage(JSON.stringify({
  authSource: 'local',
  userId: 'seeded-user',
  user: { uid: 'seeded-user' }
}))), 'anonymous', 'local onboarding users do not acquire Firebase conversation identity');
assert.equal(resolveAssistantUserId(storage('{malformed')), 'anonymous');
assert.equal(resolveAssistantUserId(storage(null)), 'anonymous');
assert.equal(resolveAssistantUserId({ getItem: () => { throw new Error('storage unavailable'); } }), 'anonymous');
console.log('Assistant conversation identity tests passed.');
