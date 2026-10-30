// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE WORKFORCE INTELLIGENCE DATA
// Unified state, demo profiles & simulation data for Employee Portal
// ============================================================================

// ----------------------------------------------------------------------------
// 1. DUAL EMPLOYEE STATE MANAGEMENT
// ----------------------------------------------------------------------------

const STATE_STORAGE_KEY = 'talentscope-employee-type';

export const EMPLOYEE_TYPES = {
  COMPANY: 'company_employee',
  INDEPENDENT: 'independent_employee'
};

export function getEmployeeType() {
  try {
    const saved = localStorage.getItem(STATE_STORAGE_KEY);
    return saved === EMPLOYEE_TYPES.INDEPENDENT ? EMPLOYEE_TYPES.INDEPENDENT : EMPLOYEE_TYPES.COMPANY;
  } catch {
    return EMPLOYEE_TYPES.COMPANY;
  }
}

export function setEmployeeType(type) {
  try {
    const valid = type === EMPLOYEE_TYPES.INDEPENDENT ? EMPLOYEE_TYPES.INDEPENDENT : EMPLOYEE_TYPES.COMPANY;
    localStorage.setItem(STATE_STORAGE_KEY, valid);
    window.dispatchEvent(new CustomEvent('talentscope:employee-state-changed', { detail: { type: valid } }));
    return valid;
  } catch {
    return EMPLOYEE_TYPES.COMPANY;
  }
}

export function toggleEmployeeType() {
  const current = getEmployeeType();
  const next = current === EMPLOYEE_TYPES.COMPANY ? EMPLOYEE_TYPES.INDEPENDENT : EMPLOYEE_TYPES.COMPANY;
  return setEmployeeType(next);
}

export function isCompanyEmployee() {
  return getEmployeeType() === EMPLOYEE_TYPES.COMPANY;
}

// ----------------------------------------------------------------------------
// 2. EMPLOYEE PROFILES (COMPANY-CONNECTED VS INDEPENDENT)
// ----------------------------------------------------------------------------

export const companyEmployeeProfile = {
  type: EMPLOYEE_TYPES.COMPANY,
  id: 'EMP-88291',
  name: 'Arun Sharma',
  shortName: 'Arun',
  initials: 'AS',
  avatarBg: '#2735F5',
  role: 'AI Engineer',
  level: 'L4 — Professional',
  department: 'Autonomous Systems & Compute',
  company: 'NVIDIA',
  companyInitials: 'NV',
  companyColor: '#76B900',
  tenure: '2 years, 4 months',
  experience: '4.5 years total',
  location: 'Bangalore, India',
  hub: 'Bangalore Campus · Bagmane Tech Park',
  manager: 'Priya Sundaram (Director of AI Infrastructure)',
  targetRole: 'Senior AI Platform Engineer',
  targetLevel: 'L5 — Senior Lead',
  careerGoal: 'Lead High-Performance Distributed AI Systems Architecture',
  email: 'arun.sharma@nvidia.internal',
  mentor: 'David Chen (Distinguished Systems Architect)',
  lastAppraisal: 'Exceeds Expectations (Q2 2026)',
  status: 'Full-Time Active',
  reputationPoints: 1840,
  mentorStatus: 'Active Technical Mentor',
  menteesCount: 6,
  hoursContributed: 38
};

export const independentEmployeeProfile = {
  type: EMPLOYEE_TYPES.INDEPENDENT,
  id: 'IND-40918',
  name: 'Arun Sharma',
  shortName: 'Arun',
  initials: 'AS',
  avatarBg: '#2735F5',
  role: 'AI / ML Systems Engineer',
  level: 'Senior Professional (IC)',
  department: 'Self-Directed Career Track',
  company: 'Independent / Open Workforce',
  companyInitials: 'IND',
  companyColor: '#2735F5',
  tenure: '4.5 years industry experience',
  experience: '4.5 years total',
  location: 'Bangalore, India (Remote & Hybrid)',
  hub: 'Global Tech Ecosystem',
  manager: 'Self-Managed Development',
  targetRole: 'Lead ML Infrastructure Engineer',
  targetLevel: 'Staff Engineer / Tech Lead',
  careerGoal: 'Transition to High-Throughput Distributed Model Serving & Compiler Optimization',
  email: 'arun.sharma.engineer@gmail.com',
  mentor: 'Peer Advisory Network',
  lastAppraisal: 'Self-Assessment: L5 Industry Ready',
  status: 'Available for Strategic Roles',
  reputationPoints: 2150,
  mentorStatus: 'Community Mentor & Question Author',
  menteesCount: 9,
  hoursContributed: 52
};

const EMPLOYEE_PROFILE_STORAGE_KEY = 'talentscope-employee-profile-v1';

let savedEmployeeProfileUid = null;
let savedEmployeeOnboardingProfile = null;

export function setEmployeeOnboardingProfile(uid, roleProfile) {
  if (!uid || roleProfile?.user_type !== 'employee' || !roleProfile.profile) {
    throw new Error('A verified employee profile is required.');
  }
  savedEmployeeProfileUid = uid;
  savedEmployeeOnboardingProfile = roleProfile.profile;
}

export function clearEmployeeOnboardingProfile() {
  savedEmployeeProfileUid = null;
  savedEmployeeOnboardingProfile = null;
}

export function getEmployeeOnboardingProfile() {
  return savedEmployeeOnboardingProfile
    ? { uid: savedEmployeeProfileUid, ...savedEmployeeOnboardingProfile }
    : null;
}

export function getEmployeeCurrentSkills() {
  const profile = savedEmployeeOnboardingProfile;
  if (!profile) return [];
  const skills = Array.isArray(profile.current_skill_domains) ? profile.current_skill_domains : [];
  const confidence = profile.self_reported_skill_confidence || {};
  return skills.map(name => ({ name, confidence: confidence[name] || '' }));
}

export function getEmployeeProfile() {
  const base = isCompanyEmployee() ? companyEmployeeProfile : independentEmployeeProfile;
  if (savedEmployeeOnboardingProfile) {
    const profile = savedEmployeeOnboardingProfile;
    const name = typeof profile.display_name === 'string' ? profile.display_name : '';
    return {
      ...base,
      id: savedEmployeeProfileUid,
      name,
      shortName: name.trim().split(/\s+/)[0] || '',
      initials: name.trim().split(/\s+/).filter(Boolean).map(part => part[0]).join('').slice(0, 2).toUpperCase(),
      role: profile.current_role_id || '',
      department: profile.team_name_claim || '',
      company: profile.employer_name_claim || '',
      companyVerified: profile.employment_state === 'connected' || Boolean(profile.company_id),
      companyId: profile.company_id || '',
      employmentState: profile.employment_state || (profile.company_id ? 'connected' : 'independent'),
      targetRole: profile.target_role_name || '',
      careerGoal: profile.mobility_interest_type || '',
      experience: profile.field_experience_band || '',
      city: profile.city || '',
      country: profile.country || '',
      location: [profile.city, profile.country].filter(Boolean).join(', '),
      hub: [profile.city, profile.country].filter(Boolean).join(', '),
      skills: Array.isArray(profile.current_skill_domains) ? [...profile.current_skill_domains] : [],
      skillLevels: profile.self_reported_skill_confidence || {},
      growthPriorities: profile.growth_interests || [],
      desiredSkills: profile.desired_skill_domains || [],
      weeklyLearningTime: profile.weekly_learning_time || '',
      preferredHelp: profile.primary_goal || [],
      profileLoaded: true
    };
  }
  try {
    const raw = localStorage.getItem(EMPLOYEE_PROFILE_STORAGE_KEY);
    if (!raw) return { ...base };
    const overrides = JSON.parse(raw);
    return { ...base, ...overrides };
  } catch (e) {
    return { ...base };
  }
}

export function updateEmployeeProfile(updates) {
  try {
    const current = getEmployeeProfile();
    const next = { ...current, ...updates };
    localStorage.setItem(EMPLOYEE_PROFILE_STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent('talentscope:employee-profile-updated', { detail: { profile: next } }));
    return next;
  } catch (e) {
    console.error('Failed to update employee profile', e);
    return null;
  }
}

// Backward-compatible alias for existing imports
export const employeeProfile = companyEmployeeProfile;

// ----------------------------------------------------------------------------
// 3. OVERVIEW METRICS (DUAL STATE AWARE)
// ----------------------------------------------------------------------------

export function getEmployeeOverviewMetrics() {
  if (isCompanyEmployee()) {
    return {
      primaryContext: {
        title: 'Company Tech Adoption',
        value: 'Tech Adoption ↑ 18.4%',
        headline: 'Blackwell GPU Cluster Expansion',
        summary: 'NVIDIA is expanding enterprise inference clusters across APAC hubs, prioritizing low-latency kernel profiling.',
        signalType: 'positive',
        evidenceCount: 6,
        impactLevel: 'Direct Impact on Role',
        actionLabel: 'Explore Company Context',
        route: '/employee/growth'
      },
      skillHealth: {
        title: 'Skill Health',
        score: 88,
        maxScore: 100,
        status: 'Strong Alignment',
        headline: 'Core competencies remain resilient',
        summary: 'Your core proficiency in Python, PyTorch, and inference pipelines matches 86% of current project deliverables.',
        signalType: 'healthy',
        trend: '+4.2% this quarter',
        actionLabel: 'View Skill Breakdown',
        route: '/employee/skills'
      },
      skillGap: {
        title: 'Role Skill Gap',
        gapPercent: 14,
        criticalGapsCount: 2,
        headline: '2 Emerging Requirements for L5',
        summary: 'CUDA kernel optimization and NCCL distributed tracing are required in 72% of upcoming team deliverables.',
        signalType: 'attention',
        gaps: ['CUDA Kernels', 'Distributed Tracing (NCCL)'],
        actionLabel: 'Close Skill Gaps',
        route: '/employee/skills'
      },
      roleEvolution: {
        title: 'Promotion Readiness',
        score: 82,
        readinessLevel: 'High (82%)',
        headline: 'Progress toward Senior AI Platform Engineer',
        summary: '2 of 3 milestones completed for L5 elevation. Completing CUDA profiling certifies internal eligibility.',
        signalType: 'neutral',
        evolutionState: 'L4 → L5 Readiness',
        actionLabel: 'Review Growth Path',
        route: '/employee/growth'
      },
      nextAction: {
        title: 'Next Best Action',
        primarySkill: 'CUDA Acceleration',
        headline: 'Build Deep CUDA & NCCL Optimization',
        summary: 'Required in 68% of targeted Senior AI Platform Engineer requisitions within NVIDIA APAC.',
        eta: '3 Weeks · 12 Modules',
        urgency: 'Recommended this quarter',
        actionLabel: 'Start Learning Path',
        route: '/employee/growth'
      },
      contribution: {
        title: 'Community Contribution',
        headline: 'Top 5% Technical Contributor',
        summary: 'You have contributed 16 assessment questions and mentored 6 engineers across NVIDIA Bangalore AI Guild.',
        rating: '4.9 / 5.0 (24 reviews)',
        actionLabel: 'Open Community Hub',
        route: '/employee/community'
      }
    };
  }

  // Independent Employee Metrics (Zero fake company data)
  return {
    primaryContext: {
      title: 'Market Skill Demand',
      value: 'Market Demand ↑ 24.8%',
      headline: 'High Industry Demand for ML Infra',
      summary: 'Distributed inference and GPU compiler engineers are seeing an 24.8% surge across global AI technology hubs.',
      signalType: 'positive',
      evidenceCount: 14,
      impactLevel: 'High Industry Mobility',
      actionLabel: 'Explore Career Opportunities',
      route: '/employee/opportunities'
    },
    skillHealth: {
      title: 'Skill Health',
      score: 86,
      maxScore: 100,
      status: 'High Market Fit',
      headline: 'Benchmark exceeds 84% of peer engineers',
      summary: 'Your verified skills in Python, PyTorch, and TensorRT rank in the top quartile among senior AI engineers.',
      signalType: 'healthy',
      trend: '+5.8% verified growth',
      actionLabel: 'Inspect Verified Skills',
      route: '/employee/skills'
    },
    skillGap: {
      title: 'Target Role Gap',
      gapPercent: 16,
      criticalGapsCount: 2,
      headline: '2 Target Capability Gaps',
      summary: 'Closing CUDA kernel memory optimization and distributed NCCL communication will position you for Staff ML Infra roles.',
      signalType: 'attention',
      gaps: ['CUDA Kernels', 'NCCL Scaling'],
      actionLabel: 'Target Market Benchmarks',
      route: '/employee/skills'
    },
    roleEvolution: {
      title: 'Career Readiness',
      score: 85,
      readinessLevel: 'Lead/Staff Ready (85%)',
      headline: 'Ready for Staff ML Infrastructure Positions',
      summary: 'You match 85% of market benchmarks for Lead ML Infrastructure and Distributed Inference roles.',
      signalType: 'neutral',
      evolutionState: 'Market Readiness',
      actionLabel: 'View Career Pathways',
      route: '/employee/growth'
    },
    nextAction: {
      title: 'Next Best Action',
      primarySkill: 'CUDA & Kernel Engineering',
      headline: 'Complete Advanced CUDA Optimization',
      summary: 'Mastering shared memory banking and warp divergence bridges the final gap to senior technical leadership.',
      eta: '2.5 Weeks · Hands-on Labs',
      urgency: 'High Market ROI',
      actionLabel: 'Explore Roadmap',
      route: '/employee/growth'
    },
    contribution: {
      title: 'Community & Mentorship',
      headline: '2,150 Reputation Points Earned',
      summary: '142 peer learners have taken your Python & Distributed ML assessments with 98% positive accuracy ratings.',
      rating: '4.95 / 5.0 (31 reviews)',
      actionLabel: 'Open Mentorship & Questions',
      route: '/employee/community'
    }
  };
}

// Backward-compatible export
export const employeeOverviewMetrics = getEmployeeOverviewMetrics();

// ----------------------------------------------------------------------------
// 4. SKILLS WITH EVIDENCE, MENTOR ELIGIBILITY & CONTRIBUTION HOOKS
// ----------------------------------------------------------------------------

export const employeeSkillsData = [
  {
    id: 'sk-python',
    name: 'Python',
    category: 'Core Programming',
    proficiency: 'Expert',
    healthScore: 94,
    relevance: 96,
    momentum: '+12%',
    halfLife: '4.8 Years',
    status: 'Strong',
    roleRequirement: 'Required (Current & Future)',
    companyDemand: 'Very High (98% of AI Teams)',
    gap: 'None (Benchmark Exceeded)',
    verifiedDate: 'Aug 2026',
    icon: 'code-2',
    description: 'Advanced asynchronous programming, Cython bindings, vectorized NumPy operations, and enterprise ML pipelines.',
    trend: [82, 85, 88, 90, 92, 94, 96],
    mentorEligible: true,
    contributorRole: 'Question Bank Author',
    questionsAuthoredCount: 16,
    activeMenteesCount: 4,
    evidenceBadge: 'Verified L5 Code Standard'
  },
  {
    id: 'sk-pytorch',
    name: 'PyTorch & Deep Learning',
    category: 'AI Frameworks',
    proficiency: 'Advanced',
    healthScore: 90,
    relevance: 94,
    momentum: '+15%',
    halfLife: '3.6 Years',
    status: 'Strong',
    roleRequirement: 'Required (Current & Future)',
    companyDemand: 'Critical (Core Framework)',
    gap: 'None (Well-Aligned)',
    verifiedDate: 'Jul 2026',
    icon: 'flame',
    description: 'Custom autograd functions, distributed data parallel (DDP), TorchScript compilation, and dynamic graph debugging.',
    trend: [76, 80, 83, 86, 89, 91, 94],
    mentorEligible: true,
    contributorRole: 'Mock Interviewer & Question Author',
    questionsAuthoredCount: 12,
    activeMenteesCount: 3,
    evidenceBadge: 'DDP Benchmarked'
  },
  {
    id: 'sk-cuda',
    name: 'CUDA & GPU Optimization',
    category: 'Hardware Acceleration',
    proficiency: 'Intermediate',
    healthScore: 62,
    relevance: 98,
    momentum: '+28%',
    halfLife: '5.2 Years',
    status: 'Gap',
    roleRequirement: 'Critical for Target Role (Senior)',
    companyDemand: 'Urgent (Team Top Priority)',
    gap: 'High Gap (-24% vs Target L5 Requirement)',
    verifiedDate: 'Self-Assessed June 2026',
    icon: 'cpu',
    description: 'Kernel memory hierarchy tuning, warp divergence mitigation, shared memory banking, and cooperative groups.',
    trend: [40, 44, 48, 52, 55, 58, 62],
    mentorEligible: false,
    contributorRole: 'Active Learner',
    questionsAuthoredCount: 0,
    activeMenteesCount: 0,
    evidenceBadge: 'DLI Module 8/12 In Progress'
  },
  {
    id: 'sk-dist-sys',
    name: 'Distributed Systems & NCCL',
    category: 'Systems Architecture',
    proficiency: 'Developing',
    healthScore: 54,
    relevance: 91,
    momentum: '+24%',
    halfLife: '4.2 Years',
    status: 'Gap',
    roleRequirement: 'Emerging Requirement (68% internal roles)',
    companyDemand: 'High (Cluster Scaling)',
    gap: 'Medium Gap (-22% vs Target Requirement)',
    verifiedDate: 'Assessment Recommended',
    icon: 'network',
    description: 'All-Reduce algorithms, NVLink multi-node interconnects, RoCE/InfiniBand RDMA, and cluster health monitoring.',
    trend: [38, 41, 45, 48, 50, 52, 56],
    mentorEligible: false,
    contributorRole: 'Assessment Candidate',
    questionsAuthoredCount: 0,
    activeMenteesCount: 0,
    evidenceBadge: 'Next Recommended Assessment'
  },
  {
    id: 'sk-tensorrt',
    name: 'TensorRT & Model Deployment',
    category: 'Inference Acceleration',
    proficiency: 'Proficient',
    healthScore: 86,
    relevance: 88,
    momentum: '+18%',
    halfLife: '3.0 Years',
    status: 'Strong',
    roleRequirement: 'Required (Current Role)',
    companyDemand: 'Very High (Production Serving)',
    gap: 'Minimal Gap (-4%)',
    verifiedDate: 'May 2026',
    icon: 'zap',
    description: 'INT8 post-training quantization, engine serialization, dynamic batching, and Triton server custom backends.',
    trend: [68, 72, 75, 78, 81, 84, 88],
    mentorEligible: true,
    contributorRole: 'Guild Reviewer',
    questionsAuthoredCount: 8,
    activeMenteesCount: 2,
    evidenceBadge: 'Production Triton Pipeline'
  },
  {
    id: 'sk-llm-eval',
    name: 'LLM Evaluation & RAG Systems',
    category: 'Generative AI',
    proficiency: 'Advanced',
    healthScore: 92,
    relevance: 92,
    momentum: '+22%',
    halfLife: '2.4 Years',
    status: 'Strong',
    roleRequirement: 'High Value Add',
    companyDemand: 'Very High (Enterprise Solutions)',
    gap: 'None',
    verifiedDate: 'Aug 2026',
    icon: 'sparkles',
    description: 'Retrieval augmentation with hybrid reranking, hallucination benchmarking, and semantic cache optimization.',
    trend: [65, 71, 78, 83, 87, 90, 93],
    mentorEligible: true,
    contributorRole: 'Hackathon Lead & Mentor',
    questionsAuthoredCount: 14,
    activeMenteesCount: 3,
    evidenceBadge: 'Sovereign RAG Deployed'
  }
];

// ----------------------------------------------------------------------------
// 5. QUESTION BANK ENGINE & ASSESSMENTS
// ----------------------------------------------------------------------------

export const questionBanksData = [
  {
    id: 'qb-python-async',
    title: 'Python Asynchronous & High-Throughput Pipelines',
    skill: 'Python',
    difficulty: 'Advanced',
    totalQuestions: 16,
    totalAttempts: 128,
    averageScore: 78,
    passRate: '82%',
    createdByMe: true,
    author: 'Arun Sharma (You)',
    lastUpdated: 'Sep 2026',
    status: 'Active & Verified',
    description: 'Practical debugging scenarios covering asyncio event loops, uvloop integration, threadpool executor contention, and zero-copy memory buffers.',
    sampleQuestions: [
      {
        id: 'q-101',
        title: 'Mitigating Event Loop Starvation in High-Frequency Inference Handlers',
        difficulty: 'Hard',
        type: 'Multiple Choice & Code Review',
        attempts: 124,
        correctPct: 74
      },
      {
        id: 'q-102',
        title: 'GIL Bypass Strategies using NumPy Buffers and Multiprocessing Pipes',
        difficulty: 'Medium',
        type: 'Code Analysis',
        attempts: 118,
        correctPct: 81
      }
    ]
  },
  {
    id: 'qb-pytorch-ddp',
    title: 'PyTorch Distributed Data Parallel (DDP) Architecture',
    skill: 'PyTorch & Deep Learning',
    difficulty: 'Advanced',
    totalQuestions: 12,
    totalAttempts: 84,
    averageScore: 71,
    passRate: '75%',
    createdByMe: true,
    author: 'Arun Sharma (You)',
    lastUpdated: 'Aug 2026',
    status: 'Active & Verified',
    description: 'Evaluating gradient bucketing, all-reduce communication overlap, Torch Dynamo compiler graphs, and autograd memory optimization.',
    sampleQuestions: [
      {
        id: 'q-201',
        title: 'Gradient Bucketing Tuning for 8x H100 Interconnect Bandwidth',
        difficulty: 'Hard',
        type: 'Architecture Scenario',
        attempts: 84,
        correctPct: 69
      }
    ]
  },
  {
    id: 'qb-cuda-memory',
    title: 'CUDA Kernel Memory Coalescing & Bank Conflicts',
    skill: 'CUDA & GPU Optimization',
    difficulty: 'Expert',
    totalQuestions: 10,
    totalAttempts: 46,
    averageScore: 59,
    passRate: '56%',
    createdByMe: false,
    author: 'David Chen (Distinguished Systems Architect)',
    lastUpdated: 'Jul 2026',
    status: 'Recommended Practice',
    description: 'Benchmarking shared memory stride access patterns, warp voting intrinsics, and WMMA tensor core usage.',
    sampleQuestions: [
      {
        id: 'q-301',
        title: 'Resolving 32-way Shared Memory Bank Conflicts in GEMM Inner Loops',
        difficulty: 'Expert',
        type: 'CUDA C++ Profiling',
        attempts: 46,
        correctPct: 52
      }
    ]
  }
];

// ----------------------------------------------------------------------------
// 6. MOCK INTERVIEWS & MENTORSHIP SCHEDULE
// ----------------------------------------------------------------------------

export const mockInterviewsData = {
  mentorProfile: {
    eligible: true,
    verifiedSkills: ['Python (Expert)', 'PyTorch (Advanced)', 'TensorRT (Proficient)', 'LLM Evaluation (Advanced)'],
    rating: 4.9,
    reviewsCount: 24,
    totalSessionsCompleted: 18,
    activeLearnersAssisted: 142
  },
  availableSlots: [
    {
      id: 'slot-1',
      date: 'Tomorrow, Sep 29',
      time: '5:00 PM — 5:45 PM IST',
      format: '45 min Technical Mock Interview',
      focusArea: 'Distributed ML Serving & Inference Architecture',
      status: 'Open for Booking',
      candidate: null
    },
    {
      id: 'slot-2',
      date: 'Thursday, Oct 1',
      time: '6:00 PM — 6:45 PM IST',
      format: '45 min Code & Optimization Review',
      focusArea: 'Python Async Systems & Production Triton Pipelines',
      status: 'Open for Booking',
      candidate: null
    }
  ],
  upcomingSessions: [
    {
      id: 'session-101',
      date: 'Today, Sep 28',
      time: '4:30 PM — 5:15 PM IST',
      menteeName: 'Kavita Nair',
      menteeRole: 'Associate ML Engineer',
      focus: 'PyTorch Gradient Accumulation & DDP Profiling',
      channel: 'Google Meet · Internal Guild Room',
      status: 'Confirmed'
    }
  ],
  recentFeedback: [
    {
      mentee: 'Rohan Mehra',
      role: 'Backend Engineer transitioning to ML',
      rating: 5,
      date: '3 days ago',
      comment: 'Arun helped me understand why our Triton inference server was bottlenecked on CPU preprocessing. Extremely actionable breakdown.'
    },
    {
      mentee: 'Ananya Sen',
      role: 'Junior AI Engineer',
      rating: 5,
      date: '1 week ago',
      comment: 'The mock technical interview mirror the actual L4 assessment questions. His feedback on async patterns was spot-on.'
    }
  ]
};

// ----------------------------------------------------------------------------
// 7. ROLE EVOLUTION & GROWTH PATHS
// ----------------------------------------------------------------------------

export const roleEvolutionData = {
  currentRole: 'AI Engineer',
  targetRole: 'Senior AI Platform Engineer',
  targetLevel: 'L5',
  department: 'Autonomous Systems & Compute',
  evolutionSummary: 'Transitioning from standalone model experimentation to high-scale cluster inference, compiler optimization, and production resiliency.',
  trajectoryState: 'Stable → Evolving',
  aiDisruptionIndex: 'Low Risk / High Augmentation',
  currentResponsibilities: [
    'Fine-tune open weights LLMs and multi-modal models for internal tools.',
    'Build and maintain model evaluation benchmarks and automated CI pipelines.',
    'Package models with Triton Inference Server for customer staging environments.',
    'Write reproducible data transformation scripts and telemetry loggers.'
  ],
  emergingResponsibilities: [
    'Write custom CUDA C++ kernels for non-standard transformer attention layers.',
    'Debug distributed training latency bottlenecks across 128+ GPU nodes using NCCL profiling tools.',
    'Optimize memory bandwidth utilization with FP4 and FP8 kernel compilation.',
    'Architect resilient failover mechanisms for mission-critical Sovereign AI endpoints.'
  ],
  skillComparison: [
    { skill: 'Python', status: 'Strong', currentFit: 95, targetReq: 90 },
    { skill: 'PyTorch', status: 'Strong', currentFit: 92, targetReq: 90 },
    { skill: 'TensorRT / Inference', status: 'Developing', currentFit: 86, targetReq: 90 },
    { skill: 'CUDA Kernel Tuning', status: 'Gap', currentFit: 62, targetReq: 85 },
    { skill: 'Distributed Clusters (NCCL)', status: 'Gap', currentFit: 54, targetReq: 82 },
    { skill: 'C++ Systems Programming', status: 'Developing', currentFit: 66, targetReq: 80 }
  ]
};

export const careerPathsData = [
  {
    pathTitle: 'AI Platform Engineering Track',
    currentStage: 'AI Engineer (L4)',
    nextStage: 'Senior AI Platform Engineer (L5)',
    ultimateStage: 'Staff Distributed AI Architect (L6)',
    readinessScore: 82,
    timeframe: '6-9 Months Readiness Horizon',
    keyMilestones: [
      { name: 'CUDA Kernel Certification (Internal L5 Standard)', status: 'In Progress (68%)', deadline: 'Oct 2026' },
      { name: 'Lead Multi-GPU Benchmarking Project', status: 'Completed', deadline: 'Aug 2026' },
      { name: 'Internal Architecture Review Approval', status: 'Pending CUDA Milestone', deadline: 'Nov 2026' }
    ],
    growthExpectation: '+28% Scope Expansion & Lead Technical Mentorship'
  },
  {
    pathTitle: 'ML Compiler & Systems Specialist Track',
    currentStage: 'AI Engineer (L4)',
    nextStage: 'Optimization & Compiler Specialist (L5)',
    ultimateStage: 'Principal Silicon Software Engineer (L6)',
    readinessScore: 68,
    timeframe: '12-15 Months Horizon',
    keyMilestones: [
      { name: 'Complete LLVM & TVM Compiler Guild Labs', status: 'Planned', deadline: 'Q4 2026' },
      { name: 'Kernel Optimization Performance PRs', status: 'In Progress (2/5)', deadline: 'Dec 2026' }
    ],
    growthExpectation: 'Focus on Hardware/Software Co-Design'
  }
];

// ----------------------------------------------------------------------------
// 8. OPPORTUNITIES (INTERNAL REQUISITIONS VS MARKET OPPORTUNITIES)
// ----------------------------------------------------------------------------

export const internalRolesData = [
  {
    id: 'role-req-101',
    title: 'Senior AI Platform Engineer',
    team: 'Hyperscale Acceleration Group',
    department: 'Autonomous Systems & Compute',
    location: 'Bangalore, India (Hybrid)',
    hiringManager: 'Kavita Raman (Senior Director)',
    matchScore: 84,
    experienceRequired: '4-6 Years',
    status: 'Actively Interviewing Internals',
    requiredSkills: ['Python', 'CUDA', 'PyTorch', 'Distributed Systems', 'C++'],
    matchedSkills: ['Python', 'PyTorch', 'TensorRT', 'Data Engineering'],
    gaps: ['CUDA Kernels', 'Distributed Tracing'],
    summary: 'Lead system performance tuning for multi-node GPU inference platforms deployed across Tier-1 enterprise partners.',
    urgency: 'Priority Fill Q3'
  },
  {
    id: 'role-req-102',
    title: 'ML Compiler & Optimization Specialist',
    team: 'Deep Learning Software (DLS)',
    department: 'Software Infrastructure',
    location: 'Bangalore / Pune (Hybrid)',
    hiringManager: 'Marcus Weber (Principal Architect)',
    matchScore: 76,
    experienceRequired: '3-5 Years',
    status: 'Open Internal Requisition',
    requiredSkills: ['C++', 'CUDA', 'LLVM', 'TensorRT', 'PyTorch'],
    matchedSkills: ['PyTorch', 'Python', 'TensorRT'],
    gaps: ['LLVM Compiler Backends', 'CUDA Kernel Optimization'],
    summary: 'Develop automated graph rewriting passes and memory placement optimizations for emerging Blackwell hardware architectures.',
    urgency: 'Open'
  },
  {
    id: 'role-req-103',
    title: 'Generative AI Systems Lead',
    team: 'NeMo Enterprise Solutions',
    department: 'Cloud Software',
    location: 'Bangalore / Remote India',
    hiringManager: 'Priya Sundaram',
    matchScore: 91,
    experienceRequired: '3-5 Years',
    status: 'Team Internal Transfer Preferred',
    requiredSkills: ['Python', 'PyTorch', 'RAG Pipelines', 'Triton Server', 'Docker'],
    matchedSkills: ['Python', 'PyTorch', 'RAG Pipelines', 'TensorRT'],
    gaps: ['Advanced Multi-Agent Orchestration'],
    summary: 'Drive high-throughput enterprise agentic systems and scalable vector search retrieval architectures for enterprise customers.',
    urgency: 'Immediate'
  }
];

export const externalOpportunitiesData = [
  {
    id: 'ext-opp-201',
    title: 'Staff ML Infrastructure Engineer',
    organization: 'Top-Tier Generative AI Research Lab',
    type: 'Full-Time Lead Role',
    location: 'Bangalore / Remote Friendly',
    matchScore: 88,
    requiredSkills: ['Python', 'PyTorch', 'Distributed Training', 'Triton', 'CUDA'],
    matchedSkills: ['Python', 'PyTorch', 'TensorRT', 'RAG'],
    compensationRange: '₹65L – ₹85L + Equity',
    summary: 'Scale inference clusters across 1,000+ GPUs with dynamic batch scheduling and KV cache optimizations.',
    status: 'Actively Hiring'
  },
  {
    id: 'ext-opp-202',
    title: 'Technical Mentor & Code Reviewer: Distributed AI',
    organization: 'Global AI Fellowship Guild',
    type: 'Selective Mentorship (5 hrs/week)',
    location: 'Remote Global',
    matchScore: 96,
    requiredSkills: ['Python', 'PyTorch', 'System Architecture', 'Mentoring'],
    matchedSkills: ['Python', 'PyTorch', 'Mentoring', 'TensorRT'],
    compensationRange: '₹3,500/hr + Contributor Grants',
    summary: 'Guide select cohorts of senior engineers mastering PyTorch distributed computing and kernel optimization.',
    status: 'Immediate Invitation'
  },
  {
    id: 'ext-opp-203',
    title: 'Open Source Grant: PyTorch Kernel Optimizer',
    organization: 'AI Compute Foundation',
    type: 'Funded Research Grant',
    location: 'Remote',
    matchScore: 82,
    requiredSkills: ['CUDA', 'PyTorch C++ Extensions', 'Benchmarking'],
    matchedSkills: ['PyTorch', 'Python', 'Benchmarking'],
    compensationRange: '$15,000 Grant Fund',
    summary: 'Develop reproducible benchmarks and automated memory allocation passes for non-standard attention models.',
    status: 'Applications Open'
  }
];

export function getOpportunitiesData() {
  return isCompanyEmployee() ? internalRolesData : externalOpportunitiesData;
}

// ----------------------------------------------------------------------------
// 9. COMPANY SIGNALS & COMMUNITY GUILDS
// ----------------------------------------------------------------------------

export const companySignals = [
  {
    id: 'sig-1',
    category: 'Technology Adoption',
    title: 'Blackwell Enterprise Cluster Rollout',
    change: '+32.4%',
    indicator: 'positive',
    timeframe: 'Last 60 Days',
    summary: 'Internal migration toward Blackwell B200 compute pods for hyperscale customer inference workloads.',
    whyItMatters: 'Requires team engineers to profile CUDA memory bandwidth and utilize FP4 quantization kernels.',
    affectedRoles: ['AI Engineer', 'ML Platform Engineer', 'Performance Architect'],
    affectedSkills: ['CUDA', 'TensorRT-LLM', 'Distributed Training'],
    evidence: 'Engineering Town Hall Q2 & Internal Tech Memo #4482',
    metric: '480+ Nodes Deployed'
  },
  {
    id: 'sig-2',
    category: 'Workforce & Hiring',
    title: 'Bangalore Systems Engineering Expansion',
    change: '+24.8%',
    indicator: 'positive',
    timeframe: 'Ongoing Q3',
    summary: '55 new requisitions opened in Bangalore focusing on Autonomous Machine software stacks and edge compute.',
    whyItMatters: 'Higher internal mobility into high-priority compute platform teams.',
    affectedRoles: ['Software Engineer', 'AI Engineer', 'Embedded Systems Lead'],
    affectedSkills: ['C++', 'Linux Kernel', 'Real-time Inference'],
    evidence: 'Internal Mobility Portal — 18 Matched Internal Openings',
    metric: '55 Open Requisitions'
  },
  {
    id: 'sig-3',
    category: 'Market Movement',
    title: 'Sovereign AI Infrastructure Engagements',
    change: '+41.0%',
    indicator: 'positive',
    timeframe: 'YTD 2026',
    summary: 'Multi-billion dollar infrastructure initiatives across Indian public sector & telecom partnerships.',
    whyItMatters: 'Demands strict data residency compliance, local model fine-tuning, and offline edge deployment expertise.',
    affectedRoles: ['AI Solution Architect', 'AI Engineer', 'Security Specialist'],
    affectedSkills: ['Model Quantization', 'Enterprise Cloud', 'Compliance'],
    evidence: 'Corporate Press Release & APAC Executive Briefing',
    metric: '8 Major Regional Contracts'
  },
  {
    id: 'sig-4',
    category: 'Product Evolution',
    title: 'TensorRT-LLM & NeMo Microservices Integration',
    change: '+19.5%',
    indicator: 'positive',
    timeframe: 'Recent 30 Days',
    summary: 'Standardization of microservice-based RAG inference pipelines across all customer-facing software products.',
    whyItMatters: 'Replaces legacy custom REST endpoints with standardized Triton inference containers.',
    affectedRoles: ['AI Engineer', 'Backend Infrastructure Engineer'],
    affectedSkills: ['Triton Server', 'Docker / K8s', 'RAG Pipelines'],
    evidence: 'Software Architecture Guild Release Notes v4.2',
    metric: '92% Architecture Adoption'
  }
];

export const companyWorkforceData = {
  companyName: 'NVIDIA Corporation',
  ticker: 'NASDAQ: NVDA',
  headcount: '29,600+ Global (4,200+ India Engineering Hub)',
  primaryIndiaCampus: 'Bagmane Tech Park, Bangalore',
  industry: 'Semiconductors & Accelerated AI Compute',
  topHiringDisciplines: [
    { discipline: 'AI Infrastructure & CUDA Optimization', share: '38%', count: '142 Openings' },
    { discipline: 'Autonomous Vehicles & Robotics', share: '24%', count: '88 Openings' },
    { discipline: 'Enterprise Cloud & NeMo Services', share: '21%', count: '74 Openings' },
    { discipline: 'Silicon Architecture & Verification', share: '17%', count: '60 Openings' }
  ],
  technologyShifts: [
    { tech: 'CUDA 13 & Blackwell Kernels', adoption: 'Rapid Growth (+44%)', employeeImpact: 'High Priority' },
    { tech: 'FP4 / FP8 Precision Serving', adoption: 'Emerging Standard (+62%)', employeeImpact: 'Direct Relevance' },
    { tech: 'TensorRT-LLM', adoption: 'Universal Rollout (+36%)', employeeImpact: 'Skill Mastered' },
    { tech: 'Legacy FP32 Training Scripts', adoption: 'Phasing Out (-28%)', employeeImpact: 'Deprecating' }
  ]
};

export const employeeCommunitiesData = [
  {
    id: 'comm-1',
    name: 'Bangalore AI Systems Guild',
    type: 'Technical Guild & Working Group',
    membersCount: 486,
    activeTopic: 'Optimizing NCCL Ring All-Reduce on 64-Node InfiniBand Clusters',
    lastActivity: '12 mins ago',
    icon: 'cpu',
    joined: true,
    myRole: 'Active Question Author'
  },
  {
    id: 'comm-2',
    name: 'CUDA Performance Architects APAC',
    type: 'Technical Special Interest Group',
    membersCount: 312,
    activeTopic: 'Shared Memory Bank Conflict Mitigation in FP4 Quantized GEMM',
    lastActivity: '45 mins ago',
    icon: 'zap',
    joined: true,
    myRole: 'Member & Learner'
  },
  {
    id: 'comm-3',
    name: 'Peer Technical Mentorship Circle',
    type: 'Mentorship & Interview Coaching',
    membersCount: 198,
    activeTopic: 'Mock Interview Slots for Q3: 14 sessions completed this week',
    lastActivity: '1 hour ago',
    icon: 'users-round',
    joined: true,
    myRole: 'Host & Mentor'
  },
  {
    id: 'comm-4',
    name: 'AI Infrastructure Hackathon 2026',
    type: 'Engineering Challenge',
    membersCount: 640,
    activeTopic: 'Registration open: 24 teams submitted proposals for local LLM pipelines',
    lastActivity: 'Today',
    icon: 'trophy',
    joined: true,
    myRole: 'Participant'
  }
];

export const employeeLearningTrack = {
  activeTrack: 'CUDA Kernel Tuning for AI Platform Engineers',
  provider: 'NVIDIA Deep Learning Institute (DLI Enterprise)',
  progressPercent: 68,
  completedModules: 8,
  totalModules: 12,
  nextModule: 'Module 9: Cooperative Groups & Warp-Level Matrix Multiply-Accumulate (WMMA)',
  estimatedTimeLeft: '3.8 Hours remaining',
  certificationBadge: 'NVIDIA Certified Associate: Accelerated Computing',
  earnedCredentials: [
    { title: 'Accelerated Deep Learning with PyTorch', date: 'June 2026', grade: '96/100' },
    { title: 'Production Inference with Triton Server', date: 'April 2026', grade: '92/100' },
    { title: 'Generative AI Prompt Engineering & RAG Design', date: 'Feb 2026', grade: '98/100' }
  ]
};
