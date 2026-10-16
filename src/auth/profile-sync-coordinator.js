export function coalesceProfileSync(inFlight, uid, profile, operation) {
  const key = `${uid}:${JSON.stringify(profile || {})}`;
  const existing = inFlight.get(key);
  if (existing) return { promise: existing, coalesced: true };

  const promise = Promise.resolve().then(operation);
  inFlight.set(key, promise);
  const cleanup = () => {
    if (inFlight.get(key) === promise) inFlight.delete(key);
  };
  promise.then(cleanup, cleanup);
  return { promise, coalesced: false };
}
