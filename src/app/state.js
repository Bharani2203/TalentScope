export const dashboardState = {
  market: '',
  timeRange: '30D',
  selectedSkill: '',
  selectedCompany: '',
  selectedRole: '',
  focus: 'skills',
  savedSkills: JSON.parse(localStorage.getItem('talentscope-saved-skills') || '[]'),
  favoriteSkills: [],
  savedCompanies: JSON.parse(localStorage.getItem('talentscope-saved-companies') || '[]'),
  favoriteCompanies: JSON.parse(localStorage.getItem('talentscope-favorite-companies') || '[]'),
  savedRoles: JSON.parse(localStorage.getItem('talentscope-saved-roles') || '[]'),
  favoriteRoles: JSON.parse(localStorage.getItem('talentscope-favorite-roles') || '[]')
};

export const dedicatedSkillState = {
  skillScope: 'My Skills',
  historyMetric: 'demand',
  historyTimeRange: '6M',
  selectedEventId: null,
  activeModal: null,
  modalData: null,
  isLoading: false,
  hasError: false
};

export const dedicatedMarketState = {
  companyScope: 'My Companies',
  selectedCompany: 'NVIDIA',
  selectedTab: 'Overview',
  selectedQuestion: null,
  activeModal: null,
  modalData: null,
  isLoading: false,
  hasError: false
};

export const dedicatedJobState = {
  roleScope: 'My Roles',
  selectedRole: 'AI Engineer',
  selectedCompanyContext: ['NVIDIA', 'Microsoft'],
  selectedTab: 'Overview',
  selectedSignal: 'all',
  selectedQuestion: null,
  activeModal: null,
  modalData: null,
  isLoading: false,
  hasError: false
};

export const intelligenceExplorerState = {
  isRoadmapPreviewing: false
};

export const roadmapState = {
  skill: 'Python',
  isActive: false
};

export const learningState = {
  activeMilestoneId: 'ms-assessment',
  selectedFilter: 'All'
};

export const userProfileState = {
  uid: 'USR-88291',
  name: 'Arun Sharma',
  email: 'arun.sharma@nvidia.internal',
  skills: ['Python', 'Machine Learning', 'Generative AI', 'Cloud Computing', 'SQL'],
  targetRole: 'AI Engineer',
  location: 'Bangalore, India'
};

// Unified platform state and canonical registries
export * from '../data/platform-state.js';
