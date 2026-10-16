import { API_BASE_URL } from '../config/api.js';

async function request(path, method = 'GET', body) {
  const { auth } = await import('../auth/firebase-client.js');
  const user = auth.currentUser;
  if (!user) throw new Error('Sign in to manage company connections.');
  const token = await user.getIdToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
        ...(body ? { 'Content-Type': 'application/json' } : {})
      },
      ...(body ? { body: JSON.stringify(body) } : {})
    });
  } catch {
    throw new Error('The company connection service is unavailable. Try again later.');
  }
  if (!response.ok) {
    let detail = null;
    try {
      const payload = await response.json();
      detail = typeof payload?.detail === 'string' ? payload.detail : payload?.detail?.message;
    } catch {}
    if (response.status === 401 || response.status === 403) {
      throw new Error(detail || 'Your account is not authorized for this company connection action.');
    }
    if (response.status === 409) throw new Error(detail || 'This connection request has already changed. Refresh and try again.');
    if (response.status === 410) throw new Error(detail || 'This invitation has expired. Ask the company admin for a new link.');
    if (response.status === 422) throw new Error(detail || 'Check the submitted information and try again.');
    throw new Error(detail || 'The company connection request could not be completed.');
  }
  return response.json();
}

export function searchCompanies(query) {
  return request(`/api/v1/company-relationships/companies?query=${encodeURIComponent(query)}`);
}

export function requestCompanyConnection(companyId) {
  return request('/api/v1/company-relationships/connection-requests', 'POST', { company_id: companyId });
}

export function acceptCompanyInvitation(token) {
  return request('/api/v1/company-relationships/invitations/accept', 'POST', { token });
}

export function declineCompanyInvitation(token) {
  return request('/api/v1/company-relationships/invitations/decline', 'POST', { token });
}

export function createCompanyInvitation({ email, role, team }) {
  return request('/api/v1/company-relationships/invitations', 'POST', { email, role, team });
}

export function loadCompanyInvitations() {
  return request('/api/v1/company-relationships/invitations');
}

export function loadPendingCompanyRequests() {
  return request('/api/v1/company-relationships/connection-requests');
}

export function reviewCompanyConnection(employeeUid, decision) {
  return request(`/api/v1/company-relationships/connection-requests/${encodeURIComponent(employeeUid)}`, 'PUT', { decision });
}

export function setEmployeeIndependent() {
  return request('/api/v1/company-relationships/independent', 'PUT');
}
