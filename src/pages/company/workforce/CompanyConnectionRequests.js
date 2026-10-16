import { loadPendingCompanyRequests, reviewCompanyConnection } from '../../../data/company-relationships-api.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

export function mountCompanyConnectionRequests(main, rerender) {
  const section = document.createElement('section');
  section.className = 'cmp-card';
  section.setAttribute('aria-labelledby', 'connection-requests-title');
  section.innerHTML = '<h2 id="connection-requests-title">Employee connection requests</h2><p role="status">Loading requests from the verified company profile…</p><div data-request-list></div>';
  main.append(section);
  const status = section.querySelector('[role="status"]');
  const list = section.querySelector('[data-request-list]');

  loadPendingCompanyRequests().then(rows => {
    if (!rows.length) { status.textContent = 'There are no pending employee requests.'; return; }
    status.textContent = 'Pending requests';
    list.innerHTML = rows.map(row => `<article class="cmp-card" style="margin-top:10px"><strong>${escapeHtml(row.email || 'Employee')}</strong><p>Employee account: ${escapeHtml(row.employee_uid)}</p><button type="button" data-review="approve" data-uid="${escapeHtml(row.employee_uid)}">Approve</button> <button type="button" data-review="decline" data-uid="${escapeHtml(row.employee_uid)}">Decline</button></article>`).join('');
    list.querySelectorAll('[data-review]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try { await reviewCompanyConnection(button.dataset.uid, button.dataset.review); rerender(); }
      catch (error) { status.textContent = error.message; button.disabled = false; }
    }));
  }).catch(error => { status.textContent = error.message; });
}
