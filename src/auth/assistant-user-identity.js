const AUTH_SESSION_KEY = 'talentscope_session_v2';

/** Return only the UID from the validated Firebase session shape. */
export function resolveAssistantUserId(storage) {
  try {
    const source = storage ?? globalThis.localStorage;
    const raw = source?.getItem(AUTH_SESSION_KEY);
    if (!raw) return 'anonymous';
    const session = JSON.parse(raw);
    const userId = session?.userId;
    return session?.authSource === 'firebase'
      && typeof userId === 'string'
      && userId.length > 0
      && session?.user?.uid === userId
      ? userId
      : 'anonymous';
  } catch {
    return 'anonymous';
  }
}
