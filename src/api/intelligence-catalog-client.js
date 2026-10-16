import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

async function loadCatalog(path) {
  const token = await getAuthIdToken();
  if (!token) throw new Error('Sign in to load supported intelligence entities.');
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
    });
  } catch {
    throw new Error('Could not reach the intelligence catalog. Please try again.');
  }
  if (response.status === 401 || response.status === 403) throw new Error('Your sign-in session could not be verified.');
  if (!response.ok) throw new Error('The intelligence catalog is temporarily unavailable.');
  return response.json();
}

export const loadSkillCatalog = () => loadCatalog('/api/v1/intelligence/catalog/skills');
export const loadMarketCatalog = () => loadCatalog('/api/v1/intelligence/catalog/market');

export async function saveMarketFavourites(entity_ids) {
  const token = await getAuthIdToken();
  if (!token) throw new Error('Sign in to save market favourites.');
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/intelligence/catalog/market/favourites`, {
      method: 'PUT',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ entity_ids })
    });
  } catch {
    throw new Error('Could not reach the market favourites service. Please try again.');
  }
  if (response.status === 401 || response.status === 403) throw new Error('Your sign-in session could not be verified.');
  if (response.status === 422) throw new Error('One or more selected entities are no longer supported. Refresh the catalog and try again.');
  if (!response.ok) throw new Error('Market favourites are temporarily unavailable.');
  return response.json();
}

export function formatObservationPeriod(period) {
  const text = String(period || '');
  const match = /^(\d{4})-(\d{1,2})$/.exec(text) || /^(\d{1,2})-(\d{4})$/.exec(text);
  if (!match) return text || 'Unavailable';
  const year = match[1].length === 4 ? Number(match[1]) : Number(match[2]);
  const month = match[1].length === 4 ? Number(match[2]) : Number(match[1]);
  if (month < 1 || month > 12) return text;
  return new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, 1)));
}
