// ============================================================================
// TALENTSCOPE.AI — ONBOARDING QUESTIONS & CATALOG DATA
// Structured according to User Specifications:
// Every question follows: WHAT (title), WHY (human reason), OPTIONS, ACTIONS
// User types: Individual, Employee (Connected / Independent), Company Admin
// ============================================================================

export const POPULAR_SKILLS = [
  'Python', 'JavaScript', 'TypeScript', 'React', 'Node.js',
  'Machine Learning', 'SQL', 'Docker', 'Kubernetes', 'AWS',
  'Deep Learning', 'PyTorch', 'Data Analysis', 'Git', 'System Design',
  'Go', 'C++', 'Java', 'Cybersecurity', 'Cloud Architecture',
  'CUDA & GPU Optimization', 'LLM Fine-tuning', 'MLOps', 'PostgreSQL',
  'Product Design', 'Leadership', 'Strategic Workforce Planning'
];

export const POPULAR_ROLES = [
  'AI Engineer', 'Software Engineer', 'Backend Developer',
  'Data Scientist', 'Machine Learning Engineer', 'Cloud Architect',
  'Frontend Developer', 'Full Stack Developer', 'DevOps & MLOps Lead',
  'Cybersecurity Specialist', 'Product Manager', 'Data Engineer',
  'UI/UX Designer', 'Enterprise Architect', 'Systems Engineer'
];

export const POPULAR_COMPANIES = [
  'Google', 'NVIDIA', 'Microsoft', 'Amazon', 'Apple', 'Meta',
  'TechCorp Global', 'NovaTech Solutions', 'OpenAI', 'Anthropic',
  'Salesforce', 'Infosys', 'TCS', 'Stripe', 'Databricks'
];

export const POPULAR_INDUSTRIES = [
  'Artificial Intelligence & Enterprise Software',
  'Enterprise Cloud & Infrastructure',
  'Financial Technology & Banking',
  'Healthcare & Biotechnology',
  'E-Commerce & Digital Platforms',
  'Automotive & Autonomous Systems',
  'Telecommunications & Network Systems',
  'Aerospace & Defense'
];

// ----------------------------------------------------------------------------
// 1. INDIVIDUAL ONBOARDING QUESTIONS (12 STEPS)
// ----------------------------------------------------------------------------
export const INDIVIDUAL_QUESTIONS = [
  {
    id: 'name_and_location',
    category: 'About You',
    stepNumber: 1,
    title: 'What should we call you?',
    why: 'We use your name and location to personalize your intelligence console and filter local market hiring demand.',
    illustration: 'profile',
    type: 'personal-identity',
    fields: [
      { name: 'name', label: 'Full Name', type: 'text', placeholder: 'e.g. Alex Mercer', required: true },
      {
        name: 'ageGroup',
        label: 'Which age group are you in? (Optional)',
        type: 'select',
        options: ['Prefer not to say', 'Under 18', '18–21', '22–25', '26–30', '31–40', '40+']
      },
      { name: 'city', label: 'Current City', type: 'text', placeholder: 'e.g. Bangalore', required: true },
      { name: 'country', label: 'Country', type: 'text', placeholder: 'e.g. India', required: true }
    ]
  },
  {
    id: 'current_stage',
    category: 'About You',
    stepNumber: 2,
    title: 'Where are you right now?',
    why: 'Knowing your starting point shapes whether we focus on foundational building blocks, industry transitions, or senior growth.',
    illustration: 'journey',
    type: 'single-select',
    options: [
      { label: 'Student', desc: 'Currently enrolled in university or a training program', icon: 'graduation-cap' },
      { label: 'Recently graduated', desc: 'Finished education in the last 12 months', icon: 'award' },
      { label: 'Looking for my first job', desc: 'Actively searching for entry-level opportunities', icon: 'search' },
      { label: 'Working professional', desc: 'Currently working and developing industry capabilities', icon: 'briefcase' },
      { label: 'Changing careers', desc: 'Transitioning from another discipline into tech or AI', icon: 'git-branch' },
      { label: 'Learning for personal growth', desc: 'Curious and exploring forward-looking capabilities', icon: 'sparkles' }
    ]
  },
  {
    id: 'experience',
    category: 'Experience',
    stepNumber: 3,
    title: 'How much experience do you have?',
    why: 'Helps us calibrate project recommendations, roadmap complexity, and role demand expectations.',
    illustration: 'experience',
    type: 'experience-conditional',
    options: [
      { label: 'No experience yet', desc: 'Starting fresh from the fundamentals' },
      { label: 'Less than 1 year', desc: 'Have built projects or done internships' },
      { label: '1–2 years', desc: 'Early career practitioner' },
      { label: '3–5 years', desc: 'Established mid-level professional' },
      { label: '5+ years', desc: 'Seasoned or senior practitioner' }
    ],
    studyFieldPrompt: 'What are you studying or planning to study?'
  },
  {
    id: 'skills',
    category: 'Skills',
    stepNumber: 4,
    title: 'What skills do you already have?',
    why: 'Add the capabilities you already feel familiar with. This forms the baseline for your Skill Gap & Health analysis.',
    illustration: 'skills',
    type: 'skill-selector',
    allowSkip: true,
    skipText: 'Not sure? You can skip this and add them later'
  },
  {
    id: 'skill_levels',
    category: 'Skills',
    stepNumber: 5,
    title: 'What is your level in your top skills?',
    why: 'Simple self-assessments help calibrate whether you need core practice or advanced architectural challenges.',
    illustration: 'levels',
    type: 'skill-level-matrix',
    levels: [
      { key: 'Beginner', label: 'Beginner', desc: "I'm still learning" },
      { key: 'Comfortable', label: 'Comfortable', desc: 'I can use it on my own' },
      { key: 'Advanced', label: 'Advanced', desc: 'I can build and solve problems confidently' },
      { key: 'Expert', label: 'Expert', desc: 'I can guide others and handle complex work' }
    ]
  },
  {
    id: 'career_goal',
    category: 'Goals',
    stepNumber: 6,
    title: 'What are you working toward?',
    why: 'Select the primary outcomes you want to achieve over the next 6 to 12 months.',
    illustration: 'target',
    type: 'multi-select',
    options: [
      { label: 'Get my first job', icon: 'rocket' },
      { label: 'Get a better job', icon: 'trending-up' },
      { label: 'Grow in my current role', icon: 'award' },
      { label: 'Move into a new role', icon: 'compass' },
      { label: 'Change careers', icon: 'shuffle' },
      { label: 'Start a business', icon: 'briefcase' },
      { label: 'Improve my skills', icon: 'layers' },
      { label: 'Explore opportunities', icon: 'globe' }
    ]
  },
  {
    id: 'target_role',
    category: 'Goals',
    stepNumber: 7,
    title: 'What kind of work interests you?',
    why: 'We will map your current competencies against live requisition requirements for this target trajectory.',
    illustration: 'roles',
    type: 'role-selector',
    allowNotSure: true
  },
  {
    id: 'interest_areas',
    category: 'Interests',
    stepNumber: 8,
    title: 'What areas are you interested in?',
    why: 'Lets us spotlight relevant industry trends, specialized technologies, and project ideas.',
    illustration: 'interests',
    type: 'multi-select-pills',
    options: [
      'Artificial Intelligence', 'Software Development', 'Data Engineering', 'Cloud & DevOps',
      'Cybersecurity', 'Electronics & Embedded', 'Healthcare Tech', 'Fintech',
      'Design & UX', 'Business Analytics', 'AI Research', 'Automation'
    ]
  },
  {
    id: 'learning_style',
    category: 'Learning',
    stepNumber: 9,
    title: 'How do you prefer to learn?',
    why: 'Adapts roadmap modules to emphasize what keeps you engaged and building momentum.',
    illustration: 'learning',
    type: 'multi-select',
    options: [
      { label: 'Short lessons', desc: 'Bite-sized daily concepts', icon: 'clock' },
      { label: 'Hands-on practice', desc: 'Interactive coding & labs', icon: 'terminal' },
      { label: 'Projects', desc: 'Building end-to-end applications', icon: 'folder-code' },
      { label: 'Videos', desc: 'Visual walkthroughs & explanations', icon: 'play-circle' },
      { label: 'Reading', desc: 'In-depth documentation & papers', icon: 'book-open' },
      { label: 'Quizzes', desc: 'Knowledge checks & flashcards', icon: 'check-square' },
      { label: 'Learning with a mentor', desc: '1-on-1 guidance & review', icon: 'users' }
    ]
  },
  {
    id: 'weekly_time',
    category: 'Learning',
    stepNumber: 10,
    title: 'How much time can you spend learning each week?',
    why: 'We size your milestones so they stay realistic and manageable alongside your daily routine.',
    illustration: 'time',
    type: 'single-select',
    options: [
      { label: 'Less than 2 hours', desc: 'Micro-learning / occasional refresh' },
      { label: '2–5 hours', desc: 'Steady weekend or evening progress' },
      { label: '5–10 hours', desc: 'Focused career acceleration' },
      { label: '10+ hours', desc: 'Full-time transition or bootcamp pace' }
    ]
  },
  {
    id: 'work_preference',
    category: 'Preferences',
    stepNumber: 11,
    title: 'Where would you like to work?',
    why: 'Filters hiring momentum and salary signals according to your remote or geographic preferences.',
    illustration: 'location',
    type: 'single-select',
    options: [
      { label: 'Remote', desc: 'Work from anywhere with distributed teams', icon: 'laptop' },
      { label: 'My current city', desc: 'In-office or hybrid in your local area', icon: 'map-pin' },
      { label: 'Within my country', desc: 'Open to opportunities across your nation', icon: 'compass' },
      { label: 'Open to relocating', desc: 'Willing to move internationally or to top hubs', icon: 'plane' },
      { label: 'Anywhere', desc: 'Flexible to any great opportunity', icon: 'globe' }
    ]
  },
  {
    id: 'favorite_companies',
    category: 'Preferences',
    stepNumber: 12,
    title: "Are there companies you'd like to work for?",
    why: 'We will track workforce demand patterns, hiring sprees, and required stacks at your dream employers.',
    illustration: 'companies',
    type: 'company-selector',
    allowSkip: true
  }
];

// ----------------------------------------------------------------------------
// 2. EMPLOYEE ONBOARDING QUESTIONS (10 STEPS)
// ----------------------------------------------------------------------------
export const EMPLOYEE_QUESTIONS = [
  {
    id: 'emp_name_and_location',
    category: 'About You',
    stepNumber: 1,
    title: 'What should we call you?',
    why: 'Personalizes your employee workspace and career health diagnostics.',
    illustration: 'profile',
    type: 'personal-identity',
    fields: [
      { name: 'name', label: 'Full Name', type: 'text', placeholder: 'e.g. Sarah Jenkins', required: true },
      { name: 'city', label: 'City', type: 'text', placeholder: 'e.g. San Francisco', required: true },
      { name: 'country', label: 'Country', type: 'text', placeholder: 'e.g. United States', required: true }
    ]
  },
  {
    id: 'emp_workplace',
    category: 'Workplace',
    stepNumber: 2,
    title: 'Where do you work?',
    why: 'Contextualizes whether your skill health is measured against company department goals or independent industry standards.',
    illustration: 'workplace',
    type: 'employee-workplace'
  },
  {
    id: 'emp_experience_field',
    category: 'Experience',
    stepNumber: 3,
    title: 'How long have you been working in this field?',
    why: 'Establishes seniority benchmarking against internal levels and industry expectations.',
    illustration: 'experience',
    type: 'single-select',
    options: [
      { label: 'New to the field', desc: 'Less than 6 months in this role' },
      { label: 'Less than 1 year', desc: 'Onboarding & ramp-up phase' },
      { label: '1–2 years', desc: 'Fully independent contributor' },
      { label: '3–5 years', desc: 'Experienced practitioner' },
      { label: '5–10 years', desc: 'Senior or specialist leader' },
      { label: '10+ years', desc: 'Staff, principal, or veteran director' }
    ]
  },
  {
    id: 'emp_skills',
    category: 'Skills',
    stepNumber: 4,
    title: 'Which skills do you use most at work?',
    why: 'These form the core of your Skill Health Index and role alignment evaluation.',
    illustration: 'skills',
    type: 'skill-selector',
    allowSkip: false
  },
  {
    id: 'emp_skill_confidence',
    category: 'Skills',
    stepNumber: 5,
    title: 'How confident are you in these skills?',
    why: 'Self-ratings help spot which skills need reinforcement and which qualify you for internal mentorship.',
    illustration: 'levels',
    type: 'skill-level-matrix',
    levels: [
      { key: 'Beginner', label: 'Beginner', desc: "I'm still learning" },
      { key: 'Comfortable', label: 'Comfortable', desc: 'I can use it on my own' },
      { key: 'Advanced', label: 'Advanced', desc: 'I can build and solve problems confidently' },
      { key: 'Expert', label: 'Expert', desc: 'I can guide others and handle complex work' }
    ]
  },
  {
    id: 'emp_improvements',
    category: 'Growth',
    stepNumber: 6,
    title: 'What do you want to improve?',
    why: 'Targeting specific growth dimensions keeps your recommendations actionable and performance-driven.',
    illustration: 'growth',
    type: 'multi-select',
    options: [
      { label: 'My technical skills', desc: 'Architecture, coding, infrastructure', icon: 'code-2' },
      { label: 'My ability to work with AI', desc: 'Tooling, prompting, agentic automation', icon: 'bot' },
      { label: 'My role performance', desc: 'Efficiency, quality, impact', icon: 'zap' },
      { label: 'My leadership', desc: 'Mentoring, influence, decision making', icon: 'shield' },
      { label: 'My communication', desc: 'Cross-functional alignment & writing', icon: 'message-square' },
      { label: 'My career growth', desc: 'Promotion, title change, compensation', icon: 'trending-up' }
    ]
  },
  {
    id: 'emp_trajectory',
    category: 'Growth',
    stepNumber: 7,
    title: 'Where do you want your career to go?',
    why: 'Calibrates internal mobility avenues and next-level criteria.',
    illustration: 'target',
    type: 'single-select',
    options: [
      { label: 'Grow in my current role', desc: 'Deepen expertise without changing title' },
      { label: 'Move to a senior role', desc: 'Step up to Senior, Staff, or Lead' },
      { label: 'Move to another team', desc: 'Internal transfer to a new domain' },
      { label: 'Move into a new role', desc: 'Transition into AI, Management, or Product' },
      { label: 'Become a specialist', desc: 'Deep vertical technical authority' },
      { label: 'Move into management', desc: 'Leading teams and people operations' },
      { label: 'Explore another company', desc: 'Testing external market demand' }
    ]
  },
  {
    id: 'emp_next_skills',
    category: 'Skills',
    stepNumber: 8,
    title: 'What skills do you want to build next?',
    why: 'We will suggest targeted learning sprints to prepare you for upcoming project or promotion requirements.',
    illustration: 'skills',
    type: 'skill-selector',
    allowSkip: true,
    skipText: 'Not sure — help me discover them'
  },
  {
    id: 'emp_time',
    category: 'Preferences',
    stepNumber: 9,
    title: 'How much time can you spend improving each week?',
    why: 'Structures your learning sprints around actual working schedules.',
    illustration: 'time',
    type: 'single-select',
    options: [
      { label: 'Less than 2 hours', desc: 'Quick weekly micro-skills' },
      { label: '2–5 hours', desc: 'Dedicated focus hours during workweek' },
      { label: '5–10 hours', desc: 'Aggressive promotion or reskilling sprint' },
      { label: '10+ hours', desc: 'Intensive career transformation' }
    ]
  },
  {
    id: 'emp_internal_goals',
    category: 'Opportunities',
    stepNumber: 10,
    title: 'What would you like help with most?',
    why: 'Tailors your dashboard spotlight towards internal milestones, promotion packets, or market signals.',
    illustration: 'companies',
    type: 'multi-select',
    options: [
      { label: 'Improve my current role performance', icon: 'target' },
      { label: 'Prepare for promotion milestone', icon: 'award' },
      { label: 'Find another role internally', icon: 'git-merge' },
      { label: 'Build verified skill evidence', icon: 'check-circle' },
      { label: 'Understand where my role is going with AI', icon: 'sparkles' },
      { label: 'Prepare for future industry changes', icon: 'trending-up' }
    ]
  }
];

// ----------------------------------------------------------------------------
// 3. COMPANY ADMIN ONBOARDING QUESTIONS (11 STEPS)
// ----------------------------------------------------------------------------
export const COMPANY_QUESTIONS = [
  {
    id: 'cmp_organization',
    category: 'Organization',
    stepNumber: 1,
    title: 'Tell us about your organization',
    why: 'Calibrates workforce intelligence benchmarks against your specific industry peer group and location.',
    illustration: 'workplace',
    type: 'personal-identity',
    fields: [
      { name: 'companyName', label: 'Company Name', type: 'text', placeholder: 'e.g. NovaTech Solutions', required: true },
      { name: 'industry', label: 'Primary Industry', type: 'select', options: POPULAR_INDUSTRIES, required: true },
      { name: 'city', label: 'Headquarters City', type: 'text', placeholder: 'e.g. Seattle', required: true },
      { name: 'country', label: 'Country', type: 'text', placeholder: 'e.g. United States', required: true }
    ]
  },
  {
    id: 'cmp_workforce_size',
    category: 'Organization',
    stepNumber: 2,
    title: 'How large is your workforce?',
    why: 'Enables accurate mobility simulation, team clustering, and benchmark percentiles.',
    illustration: 'companies',
    type: 'single-select',
    options: [
      { label: '1–50 employees', desc: 'Early-stage startup / high agility' },
      { label: '51–200 employees', desc: 'Growth stage organization' },
      { label: '201–500 employees', desc: 'Mid-market business unit' },
      { label: '501–1,000 employees', desc: 'Scaling enterprise' },
      { label: '1,000+ employees', desc: 'Large global enterprise' }
    ]
  },
  {
    id: 'cmp_description',
    category: 'Organization',
    stepNumber: 3,
    title: 'What does your organization do?',
    why: 'Provides semantic context for our AI matching engine when interpreting proprietary job titles and skills.',
    illustration: 'profile',
    type: 'textarea',
    placeholder: 'Briefly describe your core products, services, or technical mission (e.g. We build enterprise cloud analytics and automated workflow infrastructure for global logistics).'
  },
  {
    id: 'cmp_business_areas',
    category: 'Workforce',
    stepNumber: 4,
    title: 'Which areas are most important to your workforce?',
    why: 'Focuses departmental health diagnostics on your primary capability centers.',
    illustration: 'journey',
    type: 'multi-select-pills',
    options: [
      'Technology', 'Engineering', 'Product & Design', 'Data & Analytics',
      'Sales & Business Dev', 'Operations & Logistics', 'Finance & Risk',
      'Customer Support', 'Research & Development', 'Cybersecurity & Compliance'
    ]
  },
  {
    id: 'cmp_improvement_goals',
    category: 'Strategy',
    stepNumber: 5,
    title: 'What are you trying to improve?',
    why: 'Select your key workforce transformation priorities to configure default dashboard widgets.',
    illustration: 'target',
    type: 'multi-select',
    options: [
      { label: 'Workforce planning', desc: 'Forecasting role capacity & retirement', icon: 'calendar' },
      { label: 'Hiring efficiency', desc: 'Faster qualification and talent sourcing', icon: 'user-plus' },
      { label: 'Skill gaps', desc: 'Identifying blindspots before project roadblocks', icon: 'alert-triangle' },
      { label: 'Employee growth', desc: 'Retention through transparent career ladders', icon: 'trending-up' },
      { label: 'Internal mobility', desc: 'Redeploying existing talent across teams', icon: 'git-merge' },
      { label: 'Reskilling & AI readiness', desc: 'Preparing technical staff for AI workflows', icon: 'sparkles' }
    ]
  },
  {
    id: 'cmp_challenges',
    category: 'Strategy',
    stepNumber: 6,
    title: 'What workforce challenges are you facing today?',
    why: 'Enables tailored anomaly alerts and workforce risk indicators.',
    illustration: 'levels',
    type: 'multi-select',
    options: [
      { label: 'Finding the right technical skills', icon: 'search' },
      { label: 'Keeping employee skills current with fast-moving tech', icon: 'refresh-cw' },
      { label: 'Knowing which capabilities will matter in 12–24 months', icon: 'compass' },
      { label: 'Hiring for highly competitive, scarce roles', icon: 'users' },
      { label: 'Preparing employees for generative AI disruption', icon: 'bot' },
      { label: 'Retaining high-performing senior individual contributors', icon: 'shield-alert' }
    ]
  },
  {
    id: 'cmp_important_roles',
    category: 'Capabilities',
    stepNumber: 7,
    title: 'Which roles are most critical to your organization?',
    why: 'We will continuously track market supply, compensation drift, and skill evolution for these roles.',
    illustration: 'roles',
    type: 'role-selector'
  },
  {
    id: 'cmp_critical_skills',
    category: 'Capabilities',
    stepNumber: 8,
    title: 'Which skills are most important across your teams today?',
    why: 'These define the foundation of your company skill architecture.',
    illustration: 'skills',
    type: 'skill-selector'
  },
  {
    id: 'cmp_future_skills',
    category: 'Capabilities',
    stepNumber: 9,
    title: 'Which skills do you expect to need next?',
    why: 'Powers forward-looking gap modeling and reskilling curriculum recommendations.',
    illustration: 'skills',
    type: 'skill-selector',
    allowSkip: true,
    skipText: 'Not sure — help me discover them'
  },
  {
    id: 'cmp_decisions',
    category: 'Decisions',
    stepNumber: 10,
    title: 'What workforce decisions do you want to improve?',
    why: 'Ensures executive reports directly answer your operational and boardroom questions.',
    illustration: 'time',
    type: 'multi-select',
    options: [
      { label: 'Hiring vs. Upskilling trade-offs', icon: 'scale' },
      { label: 'Promotion readiness scoring', icon: 'award' },
      { label: 'Cross-functional talent redeployment', icon: 'git-branch' },
      { label: 'Workforce budget & compensation planning', icon: 'pie-chart' },
      { label: 'Enterprise AI tooling adoption', icon: 'cpu' },
      { label: 'Competitor talent benchmark analysis', icon: 'bar-chart-2' }
    ]
  },
  {
    id: 'cmp_platform_usage',
    category: 'Decisions',
    stepNumber: 11,
    title: 'How would you like to start using the platform?',
    why: 'Sets your primary landing perspective inside the Company Portal.',
    illustration: 'companies',
    type: 'single-select',
    options: [
      { label: 'Understand market hiring signals and skill demand', desc: 'External talent intelligence focus' },
      { label: 'Audit our existing workforce and find critical skill gaps', desc: 'Internal health & diagnostics focus' },
      { label: 'Simulate future team scenarios and plan workforce transitions', desc: 'Strategic workforce forecasting' },
      { label: 'Launch employee upskilling and career progression tracks', desc: 'Talent development focus' }
    ]
  }
];

// ----------------------------------------------------------------------------
// 4. STEP RESOLUTION & DRAFT VALIDATION HELPERS
// ----------------------------------------------------------------------------
export function filterOnboardingDraft(parsed, userType) {
  if (!parsed || typeof parsed !== 'object') return null;
  if (userType && (!parsed.userType || parsed.userType !== userType)) return null;
  return parsed;
}

export function resolveRoleStepIndex({ remote, draft, userType }) {
  const type = userType || 'company';
  const questions = type === 'employee' ? EMPLOYEE_QUESTIONS : COMPANY_QUESTIONS;
  const maxSteps = questions.length;

  const hasRemoteAnswers = remote?.answers && Object.keys(remote.answers).length > 0;
  const hasDraftAnswers = draft?.answers && Object.keys(draft.answers).length > 0;

  // When no answers exist yet, user must strictly start at Step 1 (index 0)
  if (!hasRemoteAnswers && !hasDraftAnswers) {
    return 0;
  }

  const candidateStep = remote?.onboarding?.current_step || (typeof draft?.stepIndex === 'number' ? draft.stepIndex + 1 : 1);
  return Math.max(0, Math.min(candidateStep - 1, maxSteps - 1));
}

