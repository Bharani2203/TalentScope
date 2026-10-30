import { navigation, renderNavigation } from '../components/layout/Sidebar.js';
import { updateTopbarContext, closePopovers } from '../components/layout/Topbar.js';
import { renderPlaceholder } from '../components/common/EmptyState.js';
import { dashboardState } from './state.js';

export { navigation };

export const routes = {
  '/individual/home': { title: 'Personal Intelligence', eyebrow: 'INDIVIDUAL PORTAL', description: 'Profile insights and illustrative market examples; current market feeds are not connected.' },
  '/individual/skills': { title: 'Skill Intelligence', eyebrow: 'MY SKILLS', description: 'Deep health, relevance, and half-life analysis of your skill portfolio.' },
  '/individual/learning': { title: 'Learning & Roadmaps', eyebrow: 'MY LEARNING', description: 'Active learning roadmaps, practice modules, and skill certifications.' },
  '/individual/career': { title: 'Career Opportunities', eyebrow: 'MY CAREER', description: 'Matching job requisitions and career progression insights.' },
  '/individual/community': { title: 'Peer Community', eyebrow: 'COMMUNITY', description: 'Connect with peers and mentors across engineering domains.' },
  '/individual/settings': { title: 'Account Settings', eyebrow: 'PREFERENCES', description: 'Manage your profile preferences and notification thresholds.', icon: 'settings-2' },
  '/individual/profile': { title: 'My Profile', eyebrow: 'PROFILE', description: 'Declared skills, experience, and career goals.', icon: 'user-round' },
  '/individual/clean-help': { title: 'AI Co-Pilot', eyebrow: 'WORKSPACE', description: 'Unified AI Co-Pilot powered by Phase 3 Supervisor Agent.', icon: 'bot' }
};

export function currentRoute() {
  const hash = window.location.hash.replace(/^#/, '');
  return hash || '/individual/home';
}

export function handleRouting(renderHomeFn, renderSkillsFn) {
  const routePath = currentRoute().split('?')[0];
  let route = routePath;

  if (route === '/individual/ai-assistant' || route === '/individual/assistant' || route === '/assistant' || route === '/ai') {
    window.location.hash = '#/individual/home';
    route = '/individual/home';
  }

  if (route === '/individual/market-intelligence') {
    route = '/individual/market-insights';
  }

  if (route.startsWith('/individual/skills/')) {
    const skillParam = routePath.replace('/individual/skills/', '');
    if (skillParam) {
      const formatted = decodeURIComponent(skillParam.replace(/-/g, ' '));
      dashboardState.selectedSkill = formatted;
    }
    route = '/individual/skills';
  }

  const page = routes[route] || routes['/individual/home'];
  updateTopbarContext(page.title);
  renderNavigation(route);
  closePopovers();

  if (route === '/individual/home') {
    if (typeof renderHomeFn === 'function') renderHomeFn();
  } else if (route === '/individual/skills') {
    if (typeof renderSkillsFn === 'function') renderSkillsFn();
  } else {
    renderPlaceholder(page);
  }
}

// Backwards compatibility aliases
export const handleeouting = handleRouting;
export const currenteoute = currentRoute;
