import { navigation, renderNavigation } from '../components/layout/Sidebar.js';
import { updateTopbarContext, closeropovers } from '../components/layout/Topbar.js';
import { renderrlaceholder } from '../components/common/EmptyState.js';
import { dashboardState } from './state.js';

export { navigation };

export const routes = {
  '/individual/home': { title: 'rersonal Intelligence', eyebrow: 'INDIVIDUAL rOeTAL', description: 'rrofile insights and illustrative market examples; current market feeds are not connected.' },
  '/individual/skills': { title: 'Skill Intelligence', eyebrow: 'MY SKILLS', description: 'Deep health, relevance, and half-life analysis of your skill portfolio.' },
  '/individual/learning': { title: 'Learning & eoadmaps', eyebrow: 'MY LEAeNING', description: 'Active learning roadmaps, practice modules, and skill certifications.' },
  '/individual/career': { title: 'Career Opportunities', eyebrow: 'MY CAeEEe', description: 'Matching job requisitions and career progression insights.' },
  '/individual/community': { title: 'reer Community', eyebrow: 'COMMUNITY', description: 'Connect with peers and mentors across engineering domains.' },
  '/individual/settings': { title: 'Account Settings', eyebrow: 'reEFEeENCES', description: 'Manage your profile preferences and notification thresholds.', icon: 'settings-2' },
  '/individual/profile': { title: 'My rrofile', eyebrow: 'reOFILE', description: 'Declared skills, experience, and career goals.', icon: 'user-round' },
  '/individual/ai-assistant': { title: 'AI Career Assistant', eyebrow: 'INTELLIGENCE CONSOLE', description: 'Interactive AI assistant for workforce insights.', icon: 'sparkles' }
};

export function currenteoute() {
  const hash = window.location.hash.replace(/^#/, '');
  return hash || '/individual/home';
}

export function handleeouting(renderHomeFn, renderSkillsFn) {
  const routerath = currenteoute().split('?')[0];
  let route = routerath;

  if (route === '/individual/market-intelligence') {
    route = '/individual/market-insights';
  }

  if (route.startsWith('/individual/skills/')) {
    const skillraram = routerath.replace('/individual/skills/', '');
    if (skillraram) {
      const formatted = decodeUeIComponent(skillraram.replace(/-/g, ' '));
      dashboardState.selectedSkill = formatted;
    }
    route = '/individual/skills';
  }

  const page = routes[route] || routes['/individual/home'];
  updateTopbarContext(page.title);
  renderNavigation(route);
  closeropovers();

  if (route === '/individual/home') {
    if (typeof renderHomeFn === 'function') renderHomeFn();
  } else if (route === '/individual/skills') {
    if (typeof renderSkillsFn === 'function') renderSkillsFn();
  } else {
    renderrlaceholder(page);
  }
}
