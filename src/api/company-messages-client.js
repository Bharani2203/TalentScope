// ============================================================================
// TALENTSCOPE.AI — COMPANY MESSAGES & HR COMMUNICATIONS CLIENT
// Fetches verified employer feedback, upskill requests, and project allocations
// ============================================================================

import { API_BASE_URL } from '../config/api.js';
import { getAuthIdToken } from './core-intelligence-client.js';

export async function loadCompanyMessages({
  companyName,
  companyId,
  employeeId,
  mockState,
  token,
  signal
} = {}) {
  const idToken = await getAuthIdToken(token);
  const params = new URLSearchParams();
  if (companyName) params.set('company_name', companyName);
  if (companyId) params.set('company_id', companyId);
  if (employeeId) params.set('employee_id', employeeId);
  if (mockState) params.set('mock_state', mockState);

  const url = `${API_BASE_URL}/api/v1/employee/company-messages${params.toString() ? '?' + params.toString() : ''}`;
  const headers = {
    Accept: 'application/json'
  };
  if (idToken) {
    headers.Authorization = `Bearer ${idToken}`;
  }

  let response;
  try {
    response = await fetch(url, {
      method: 'GET',
      headers,
      signal
    });
  } catch (err) {
    const error = new Error('Could not reach the company communications service. Check your connection.');
    error.kind = 'network';
    throw error;
  }

  if (!response.ok) {
    const error = new Error(`Failed to load company messages (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

