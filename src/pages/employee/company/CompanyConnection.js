import { loadRoleOnboardingProfile } from '../../../onboarding/onboarding-api.js';
import { acceptCompanyInvitation, declineCompanyInvitation, requestCompanyConnection, searchCompanies, setEmployeeIndependent } from '../../../data/company-relationships-api.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

export function renderEmployeeCompanyConnection() {
  let hasInvitation = false;
  try { hasInvitation = Boolean(sessionStorage.getItem('talentscope_pending_company_invitation')); } catch {}
  return `<div class="employee-page"><section class="emp-hero"><div class="emp-hero-content"><span class="emp-eyebrow">COMPANY CONNECTION</span><h1 class="emp-hero-title">Company connection</h1><p class="emp-hero-desc">Company membership is verified and managed by TalentScope.</p></div></section><section class="emp-card"><div id="employeeConnectionStatus" role="status">Loading your server connection status…</div>${hasInvitation ? '<div class="emp-card" role="group" aria-label="Company invitation"><p>A company invitation token was preserved during sign-in. Verify your email and choose whether to accept it.</p><button id="acceptBackendInvitation" class="emp-btn-primary" type="button">Accept invitation</button> <button id="declineBackendInvitation" class="emp-btn-ghost" type="button">Decline invitation</button></div>' : ''}<form id="companySearchForm"><label for="companySearchInput">Find a company</label><div style="display:flex;gap:8px;flex-wrap:wrap"><input id="companySearchInput" name="query" minlength="2" maxlength="120" required autocomplete="organization" placeholder="Enter company name"><button class="emp-btn-primary" type="submit">Search</button></div></form><div id="companySearchResults" aria-live="polite"></div><button id="setIndependentButton" class="emp-btn-ghost" type="button">Continue independently</button></section></div>`;
}

export function bindEmployeeCompanyConnection() {
  const status = document.querySelector('#employeeConnectionStatus');
  const results = document.querySelector('#companySearchResults');
  const form = document.querySelector('#companySearchForm');
  const independent = document.querySelector('#setIndependentButton');
  const showError = error => { status.textContent = error.message || 'The request could not be completed.'; };

  loadRoleOnboardingProfile('employee').then(result => {
    const profile = result.profile || {};
    const state = profile.employment_state || 'independent';
    status.textContent = state === 'connected'
      ? `Connected to the verified company (${profile.company_id || 'company ID unavailable'}).`
      : state === 'requesting'
        ? 'Your connection request is pending company review.'
        : 'You are independent. You can request a connection or continue independently.';
  }).catch(showError);

  const invitationToken = (() => { try { return sessionStorage.getItem('talentscope_pending_company_invitation'); } catch { return null; } })();
  const settleInvitation = async accept => {
    const button = document.querySelector(accept ? '#acceptBackendInvitation' : '#declineBackendInvitation');
    if (!invitationToken || !button) return;
    button.disabled = true;
    try {
      const result = accept
        ? await acceptCompanyInvitation(invitationToken)
        : await declineCompanyInvitation(invitationToken);
      try { sessionStorage.removeItem('talentscope_pending_company_invitation'); } catch {}
      status.textContent = accept
        ? `Invitation accepted. Company connection status: ${result.status}.`
        : 'Invitation declined. You remain independent.';
      button.closest('[role="group"]')?.remove();
    } catch (error) { showError(error); button.disabled = false; }
  };
  document.querySelector('#acceptBackendInvitation')?.addEventListener('click', () => settleInvitation(true));
  document.querySelector('#declineBackendInvitation')?.addEventListener('click', () => settleInvitation(false));

  form?.addEventListener('submit', async event => {
    event.preventDefault();
    results.textContent = 'Searching verified company profiles…';
    try {
      const companies = await searchCompanies(new FormData(form).get('query').trim());
      if (!companies.length) { results.textContent = 'No matching verified companies were found.'; return; }
      results.innerHTML = companies.map(company => `<article class="emp-card" style="margin-top:10px"><strong>${escapeHtml(company.company_name || 'Company')}</strong><p>${escapeHtml(company.industry || 'Industry unavailable')}</p><button type="button" class="emp-btn-primary" data-company-id="${escapeHtml(company.company_id)}">Request connection</button></article>`).join('');
      results.querySelectorAll('[data-company-id]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const result = await requestCompanyConnection(button.dataset.companyId);
          status.textContent = result.status === 'connected' ? 'You are connected to this company.' : 'Your request is pending company review.';
          results.replaceChildren();
        } catch (error) { button.disabled = false; showError(error); }
      }));
    } catch (error) { results.textContent = error.message; }
  });

  independent?.addEventListener('click', async () => {
    independent.disabled = true;
    try { await setEmployeeIndependent(); status.textContent = 'Your server profile is set to independent.'; results.replaceChildren(); }
    catch (error) { showError(error); independent.disabled = false; }
  });
}
