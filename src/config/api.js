const configuredApiOrigin = (
  (typeof window !== 'undefined' ? window.TALENTSCOPE_API_BASE_URL : null) ||
  (typeof globalThis !== 'undefined' ? globalThis.TALENTSCOPE_API_BASE_URL : null)
);
const currentOrigin = typeof window !== 'undefined' && /^https?:\/\//i.test(window.location?.origin || '')
  ? window.location.origin
  : '';
const localFrontendApiOrigin = (() => {
  if (!currentOrigin) return '';
  try {
    const pageUrl = new URL(currentOrigin);
    if (!['localhost', '127.0.0.1'].includes(pageUrl.hostname) || pageUrl.port !== '3000') return '';
    pageUrl.port = '8000';
    return pageUrl.origin;
  } catch {
    return '';
  }
})();

export const API_BASE_URL = String(configuredApiOrigin || localFrontendApiOrigin || currentOrigin).replace(/\/$/, '');
