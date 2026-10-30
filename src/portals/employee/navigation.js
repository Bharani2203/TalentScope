// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE PORTAL NAVIGATION
// Streamlined Information Architecture for Employee Growth Platform
// ============================================================================

export const employeeNavigation = [
  {
    label: 'Growth & Work',
    items: [
      { label: 'Home', icon: 'house', route: '/employee/home' },
      { label: 'My Skills', icon: 'layers-3', route: '/employee/skills' },
      { label: 'My Growth', icon: 'trending-up', route: '/employee/growth' },
      { label: 'Learning & Roadmaps', icon: 'book-open', route: '/employee/learning' },
      { label: 'Company Connection', icon: 'building-2', route: '/employee/company' },
      { label: 'Community', icon: 'users-round', route: '/employee/community' },
      { label: 'Opportunities', icon: 'compass', route: '/employee/opportunities' }
    ]
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Notifications', icon: 'bell', route: '/employee/notifications' }
    ]
  }
];

export function resolveEmployeeRoute(route) {
  if (route === '/employee/career') return '/employee/growth';
  if (route === '/employee/ai-assistant' || route === '/employee/assistant') return '/employee/home';
  return route;
}

export function isEmployeeRouteActive(currentRoute, itemRoute) {
  return itemRoute === resolveEmployeeRoute(currentRoute);
}

export function isEmployeeRouteCurrent(renderedRoute, currentRoute) {
  return resolveEmployeeRoute(renderedRoute) === resolveEmployeeRoute(currentRoute);
}

export const employeeRoutes = {
  '/employee/home': {
    eyebrow: 'GROWTH & WORKFORCE PLATFORM',
    title: 'Employee Overview',
    description: 'Track your capabilities, role alignment, learning paths, and community contributions.',
    icon: 'house'
  },
  '/employee/skills': {
    eyebrow: 'SKILL INTELLIGENCE & EVIDENCE',
    title: 'My Skills',
    description: 'Benchmarking your verified skill health, relevance, and mentor eligibility.',
    icon: 'layers-3'
  },
  '/employee/growth': {
    eyebrow: 'ROLE & CAREER PROGRESSION',
    title: 'My Growth',
    description: 'Role evolution, promotion readiness milestones, and targeted capability roadmaps.',
    icon: 'trending-up'
  },
  '/employee/learning': {
    eyebrow: 'MY LEARNING & ROADMAPS',
    title: 'Learning & Roadmaps',
    description: 'Active learning roadmaps, practice modules, and skill certifications.',
    icon: 'book-open'
  },
  '/employee/career': {
    eyebrow: 'ROLE & CAREER PROGRESSION',
    title: 'My Growth',
    description: 'Role evolution, promotion readiness milestones, and targeted capability roadmaps.',
    icon: 'trending-up'
  },
  '/employee/company': {
    eyebrow: 'COMPANY CONNECTION',
    title: 'Company Connection',
    description: 'Manage your verified company connection request.',
    icon: 'building-2'
  },
  '/employee/community': {
    eyebrow: 'SKILL-TO-CONTRIBUTION PLATFORM',
    title: 'Community & Contribution',
    description: 'Contribute question banks, host mock interviews, mentor peers, and earn reputation.',
    icon: 'users-round'
  },
  '/employee/opportunities': {
    eyebrow: 'CAREER MOBILITY & OPPORTUNITIES',
    title: 'Opportunities',
    description: 'Internal requisitions and high-impact career pathways matched to your skills.',
    icon: 'compass'
  },
  '/employee/notifications': {
    eyebrow: 'UPDATES & ALERTS',
    title: 'Employee Notifications',
    description: 'Assessment results, mentee bookings, requisition matches, and learning reminders.',
    icon: 'bell'
  },
  '/employee/profile': {
    eyebrow: 'EMPLOYEE PROFILE',
    title: 'My Profile',
    description: 'Verified credentials, role progression, mentor stats, and contribution history.',
    icon: 'user-round'
  },
  '/employee/settings': {
    eyebrow: 'PORTAL PREFERENCES',
    title: 'Employee Settings',
    description: 'Dynamic employee mode toggle, visibility preferences, and notification frequency.',
    icon: 'settings-2'
  }
};
