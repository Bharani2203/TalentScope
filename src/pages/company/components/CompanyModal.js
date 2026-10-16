// ============================================================================
// TALENTSCOPE.AI — COMPANY PORTAL UNIFIED MODAL SYSTEM
// Centered, backdrop-blurred, keyboard accessible (ESC, overlay click), smooth animation
// Used for: Company Profile Setup, Invite Employee, Employee Analysis, Mobility Action, etc.
// ============================================================================

const esc = str => String(str ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

let activeModalCleanup = null;

export function openCompanyModal({
  title,
  subtitle = '',
  icon = 'info',
  maxWidth = '640px',
  contentHtml = '',
  cancelText = 'Cancel',
  confirmText = 'Confirm',
  confirmIcon = 'check',
  onConfirm = null,
  hideFooter = false,
  customFooterHtml = null,
  onOpen = null
}) {
  // Close any existing modal first
  closeCompanyModal();

  const modalRoot = document.createElement('div');
  modalRoot.id = 'cmpGlobalModalContainer';
  modalRoot.innerHTML = `
    <div class="cmp-modal-scrim" id="cmpGlobalModalScrim" role="dialog" aria-modal="true" aria-labelledby="cmpModalTitle">
      <div class="cmp-modal-dialog" style="max-width: ${maxWidth};">
        <!-- Modal Header -->
        <div class="cmp-modal-header">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 38px; height: 38px; border-radius: 10px; background: var(--cmp-light-primary, #F0E9FF); color: var(--cmp-deep-primary, #5B2BBF); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
              <i data-lucide="${esc(icon)}" style="width: 18px; height: 18px;"></i>
            </div>
            <div>
              <h3 class="cmp-modal-title" id="cmpModalTitle">${esc(title)}</h3>
              ${subtitle ? `<span style="font-size: 12.5px; color: var(--cmp-text-secondary, #70677C); display: block; margin-top: 2px;">${esc(subtitle)}</span>` : ''}
            </div>
          </div>
          <button type="button" class="cmp-modal-close-btn" id="cmpModalCloseBtn" aria-label="Close modal">
            <i data-lucide="x" style="width: 16px; height: 16px;"></i>
          </button>
        </div>

        <!-- Modal Body Content -->
        <div class="cmp-modal-body" style="font-size: 13.5px; color: var(--cmp-text-primary, #241B32); line-height: 1.55;">
          ${contentHtml}
        </div>

        <!-- Modal Footer -->
        ${!hideFooter ? `
          <div class="cmp-modal-footer" style="display: flex; justify-content: flex-end; align-items: center; gap: 10px; padding-top: 16px; border-top: 1px solid var(--cmp-border, #E6DEF7);">
            ${customFooterHtml ? customFooterHtml : `
              <button type="button" class="cmp-btn-ghost" id="cmpModalCancelBtn" style="height: 38px; padding: 0 16px;">
                ${esc(cancelText)}
              </button>
              <button type="button" class="cmp-btn-primary" id="cmpModalConfirmBtn" style="height: 38px; padding: 0 18px;">
                ${confirmIcon ? `<i data-lucide="${esc(confirmIcon)}" style="width: 15px; height: 15px;"></i>` : ''}
                <span>${esc(confirmText)}</span>
              </button>
            `}
          </div>
        ` : ''}
      </div>
    </div>
  `;

  document.body.appendChild(modalRoot);
  document.body.style.overflow = 'hidden';

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  // Focus trap / escape key listener
  const keyHandler = (e) => {
    if (e.key === 'Escape') {
      closeCompanyModal();
    }
  };
  window.addEventListener('keydown', keyHandler);

  // Overlay click to close
  const scrim = modalRoot.querySelector('#cmpGlobalModalScrim');
  const scrimClickHandler = (e) => {
    if (e.target === scrim) {
      closeCompanyModal();
    }
  };
  scrim.addEventListener('click', scrimClickHandler);

  // Close & Cancel buttons
  modalRoot.querySelector('#cmpModalCloseBtn')?.addEventListener('click', closeCompanyModal);
  modalRoot.querySelector('#cmpModalCancelBtn')?.addEventListener('click', closeCompanyModal);

  // Confirm button
  if (onConfirm) {
    modalRoot.querySelector('#cmpModalConfirmBtn')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      if (button.disabled) return;
      try {
        const shouldClose = await onConfirm();
        if (shouldClose !== false) closeCompanyModal();
      } catch {
        // Modal actions own their user-facing error state.
      }
    });
  }

  activeModalCleanup = () => {
    window.removeEventListener('keydown', keyHandler);
    document.body.style.overflow = '';
    modalRoot.remove();
    activeModalCleanup = null;
  };

  if (typeof onOpen === 'function') {
    onOpen(modalRoot);
  }
}

export function closeCompanyModal() {
  if (activeModalCleanup) {
    activeModalCleanup();
  } else {
    const existing = document.getElementById('cmpGlobalModalContainer');
    if (existing) existing.remove();
    document.body.style.overflow = '';
  }
}
