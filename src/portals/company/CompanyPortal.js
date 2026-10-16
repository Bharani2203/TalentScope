// ============================================================================
// TALENTSCOPE.AI — COMPANY PORTAL DISPATCHER
// Master portal controller for Company Executive Intelligence routes (#874FFF)
// ============================================================================

import { renderCompanyHome, bindCompanyHomeEvents } from '../../pages/company/home/Home.js';
import { renderCompanyWorkforce, bindCompanyWorkforceEvents } from '../../pages/company/workforce/Workforce.js';
import { renderCompanyMarketIntelligence, bindCompanyMarketEvents } from '../../pages/company/market/MarketIntelligence.js';
import { renderCompanySkillIntelligence, bindCompanySkillsEvents } from '../../pages/company/skills/SkillIntelligence.js';
import { renderCompanyInternalMobility, bindCompanyMobilityEvents } from '../../pages/company/mobility/InternalMobility.js';
import { renderCompanyWorkforceSimulation, bindCompanySimulationEvents } from '../../pages/company/simulation/WorkforceSimulation.js';
import { renderCompanyAdministration, bindCompanyAdminEvents } from '../../pages/company/admin/Administration.js';
import { renderCompanyProfile, bindCompanyProfileEvents } from '../../pages/company/profile/CompanyProfile.js';
import { renderCompanyAIAssistant, bindCompanyAIAssistantEvents } from '../../pages/company/ai-assistant/AIAssistant.js';
import { renderCompanySettings, bindCompanySettingsEvents } from '../../pages/company/settings/Settings.js';
import { companyRoutes } from './navigation.js';
import { mountCompanyConnectionRequests } from '../../pages/company/workforce/CompanyConnectionRequests.js';

export function renderCompanyRoute(route) {
  const main = document.querySelector('#mainContent');
  if (!main) return;

  const page = companyRoutes[route] || companyRoutes['/company/home'];
  document.title = `TalentScope.ai — ${page.title}`;

  const topbarContext = document.querySelector('#topbarContext');
  if (topbarContext) {
    topbarContext.innerHTML = `
      <span style="display: inline-flex; align-items: center; gap: 8px;">
        <span style="font-weight: 750; color: var(--cmp-deep-primary, #5B2BBF);">${page.eyebrow}</span>
        <span class="portal-badge" style="background: var(--cmp-light-primary, #F0E9FF); color: var(--cmp-deep-primary, #5B2BBF); border: 1px solid var(--cmp-border-accent, #D8C7FF); display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">
          <i data-lucide="building" style="width: 12px; height: 12px;"></i> Company Portal
        </span>
      </span>
    `;
  }

  const rerender = () => renderCompanyRoute(route);

  if (route === '/company/home') {
    main.innerHTML = renderCompanyHome();
    bindCompanyHomeEvents(rerender);
  } else if (route === '/company/workforce') {
    main.innerHTML = renderCompanyWorkforce();
    bindCompanyWorkforceEvents(rerender);
    mountCompanyConnectionRequests(main, rerender);
  } else if (route === '/company/market') {
    main.innerHTML = renderCompanyMarketIntelligence();
    bindCompanyMarketEvents(rerender);
  } else if (route === '/company/skills') {
    main.innerHTML = renderCompanySkillIntelligence();
    bindCompanySkillsEvents(rerender);
  } else if (route === '/company/mobility') {
    main.innerHTML = renderCompanyInternalMobility();
    bindCompanyMobilityEvents(rerender);
  } else if (route === '/company/simulation') {
    main.innerHTML = renderCompanyWorkforceSimulation();
    bindCompanySimulationEvents(rerender);
  } else if (route === '/company/profile') {
    main.innerHTML = renderCompanyProfile();
    bindCompanyProfileEvents(rerender);
  } else if (route === '/company/admin') {
    main.innerHTML = renderCompanyAdministration();
    bindCompanyAdminEvents(rerender);
  } else if (route === '/company/ai-assistant') {
    main.innerHTML = renderCompanyAIAssistant();
    bindCompanyAIAssistantEvents(rerender);
  } else if (route === '/company/settings') {
    main.innerHTML = renderCompanySettings();
    bindCompanySettingsEvents(rerender);
  } else {
    main.innerHTML = renderCompanyHome();
    bindCompanyHomeEvents(rerender);
  }

  main.insertAdjacentHTML('afterbegin', '<aside role="note" style="margin: 12px 0; padding: 10px 14px; border: 1px solid #D6C79A; border-radius: 8px; background: #FFF9E8; color: #574817; font-size: 13px;">Company portal prototype — workforce, market, and employee values are illustrative unless explicitly marked as backend data.</aside>');

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}
