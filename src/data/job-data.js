// ============================================================================
// TALENTSCOPE.AI — JOB DATA (LEGACY / PROTOTYPE FALLBACK)
// DEPRECATION NOTICE:
// Live job intelligence is now served via the shared Core Intelligence engine
// at FastAPI `/api/v1/intelligence/job` or `/api/v1/intelligence/core` via
// `src/api/core-intelligence-client.js`.
// The datasets below are retained strictly for backward compatibility and fallback.
// ============================================================================

export const jobMarketTrends = [
  { role: 'AI Engineer', openings: 18400, growth: 22.4 },
  { role: 'Backend Engineer', openings: 14200, growth: 12.8 },
  { role: 'Data Engineer', openings: 9600, growth: 15.6 },
  { role: 'Cloud Architect', openings: 7800, growth: 11.2 }
];

export const jobTrendState = {
  selectedSegment: 'roles'
};

// Normalized Job Market Signal Distribution (Step 16)
export const jobMarketSignalMix = [
  { id: 'open_roles', label: 'Open Role Activity', percent: 46, color: '#B22DEF', count: 'Active Requisitions Stream', change: 'Live Demand', detail: 'Live role requisition demand streams tracked across technology employers.', topRoles: ['AI Engineer', 'Backend Developer', 'Machine Learning Engineer'], topLocations: ['Bangalore', 'Hyderabad', 'Chennai'], topSkills: ['Python', 'Machine Learning', 'Cloud'] },
  { id: 'hiring_companies', label: 'Hiring Company Activity', percent: 25, color: '#06B6D4', count: 'Employer Activity Stream', change: 'Active', detail: 'Enterprise employers with open engineering requisitions across active observation windows.', topCompanies: ['NVIDIA', 'Microsoft', 'Google', 'Amazon', 'OpenAI'], topHubs: ['Bangalore', 'Remote', 'Pune'] },
  { id: 'role_momentum', label: 'Role Demand Momentum', percent: 21, color: '#19B77A', count: 'Demand Acceleration', change: 'Rising', detail: 'Demand momentum telemetry observed in AI Infrastructure, Distributed Systems, and MLOps roles.', fastGrowing: ['AI Infrastructure Engineer', 'ML Platform Engineer', 'Compiler Engineer'] },
  { id: 'reduction_signal', label: 'Workforce Reduction Signal', percent: 8, color: '#F59E0B', count: 'Consolidation Telemetry', change: 'Shift', detail: 'Signal telemetry indicating consolidation across legacy routine IT operations and maintenance support roles.', impacted: ['Legacy QA Support', 'On-premise IT SysAdmin'] }
];

// 10 Comprehensive Dedicated Roles (Step 8, 10, 58)
export const dedicatedJobRoles = [
  {
    id: 'ai-engineer',
    name: 'AI Engineer',
    category: 'AI / ML',
    icon: 'bot',
    demandScore: 88,
    growthPercentage: 18.4,
    change: 18.4,
    direction: 'up',
    status: 'High Growth',
    openRoles: 12480,
    hiringCompaniesCount: 840,
    isFavorite: true,
    isMyRole: true,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹28L - ₹55L / yr ($165k - $240k)',
    locations: ['Bangalore', 'Hyderabad', 'Chennai', 'Pune', 'Remote', 'Global'],
    history: [48, 56, 64, 72, 80, 85, 91],
    projection: [93, 96, 99],
    signals: {
      openRoles: [40, 48, 58, 68, 76, 84, 91],
      companyActivity: [45, 52, 60, 70, 78, 83, 89],
      momentum: [50, 58, 66, 75, 82, 88, 94],
      reduction: [12, 10, 9, 8, 7, 6, 6]
    },
    overview: 'Designs, deploys, and optimizes production AI pipelines, large language model integrations, and accelerated inference infrastructure.',
    responsibilities: [
      'Architect and deploy high-throughput LLM and RAG microservices.',
      'Optimize neural network inference pipelines with GPU kernel acceleration.',
      'Integrate vector search indices and context retrieval platforms.',
      'Collaborate with data engineering teams on feature store pipelines and fine-tuning.'
    ],
    evolution: {
      current: ['Python', 'Machine Learning', 'SQL', 'FastAPI'],
      emerging: ['Generative AI', 'CUDA', 'Cloud Computing', 'MLOps'],
      future: ['Autonomous Multi-Agent Orchestration', 'On-Device Quantization', 'Kernel Compilation (Triton)']
    },
    adjacentRoles: ['Machine Learning Engineer', 'AI Infrastructure Architect', 'Backend Developer'],
    careerProgression: [
      { step: 'Current Profile', title: 'AI/ML Professional', match: 'Aligned (Python, ML)' },
      { step: 'Target Role', title: 'Senior AI Engineer', match: 'Next Target (Bridge CUDA/Infra)' },
      { step: 'Advanced Track', title: 'Lead AI Systems Architect', match: 'Strategic Leadership' }
    ],
    alignmentFactors: {
      skillAlignment: 'Strong (Python, Machine Learning, SQL match 82%)',
      roleDemand: 'High (+18.4% acceleration, 12,480 openings)',
      experienceFit: 'Developing (3+ years analytical experience aligns well)',
      locationFit: 'Optimal (Bangalore & Hyderabad are top hubs)',
      skillGaps: 'CUDA Systems, Deep Learning optimization'
    },
    companiesHiring: [
      { name: 'NVIDIA', logoInitials: 'NV', brandColor: '#76B900', signalText: '+28.4% Hiring Surge', change: 28.4, dir: 'up', openCount: 480, location: 'Bangalore / Remote' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+14.8% Active Hiring', change: 14.8, dir: 'up', openCount: 620, location: 'Bangalore / Hyderabad' },
      { name: 'Google', logoInitials: 'GO', brandColor: '#4285F4', signalText: '+12.2% Steady Growth', change: 12.2, dir: 'up', openCount: 410, location: 'Bangalore / Pune' },
      { name: 'Amazon', logoInitials: 'AM', brandColor: '#FF9900', signalText: '+13.9% Cloud Scale', change: 13.9, dir: 'up', openCount: 580, location: 'Chennai / Hyderabad' },
      { name: 'OpenAI', logoInitials: 'AI', brandColor: '#10A37F', signalText: '+32.5% Frontier Expansion', change: 32.5, dir: 'up', openCount: 160, location: 'Remote / US' }
    ],
    jobOpportunities: [
      { id: 'job-nv-1', company: 'NVIDIA', role: 'AI Infrastructure Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['CUDA', 'Python', 'Kubernetes'], posted: '2 days ago', signal: 'High Demand' },
      { id: 'job-ms-1', company: 'Microsoft', role: 'AI Copilot Backend Engineer', location: 'Hyderabad, India', type: 'Full-time', reqSkills: ['Python', 'Generative AI', 'Azure'], posted: '3 days ago', signal: 'Priority Hire' },
      { id: 'job-am-1', company: 'Amazon', role: 'AWS Bedrock Generative AI Specialist', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Cloud Computing', 'Python', 'RAG'], posted: '4 days ago', signal: 'Expanding' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Core runtime for model orchestration and service logic.' },
      { name: 'Machine Learning', importance: 'Critical', trend: '+24.6%', status: 'Known', level: 'Intermediate', notes: 'Algorithmic grounding, loss functions, and evaluation metrics.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Containerized deployment across Kubernetes and AWS/Azure clouds.' },
      { name: 'CUDA', importance: 'High', trend: '+32.4%', status: 'Gap', level: 'Needs Development', notes: 'Hardware accelerator memory management and GPU kernel tuning.' },
      { name: 'Generative AI', importance: 'High', trend: '+38.5%', status: 'Developing', level: 'Intermediate', notes: 'Prompt architectures, RAG vector pipelines, and fine-tuning.' },
      { name: 'SQL', importance: 'Medium', trend: '+11.2%', status: 'Known', level: 'Advanced', notes: 'Data extraction, feature stores, and telemetry analysis.' }
    ],
    evidence: [
      { source: 'Global Tech Hiring Index (GTHI)', type: 'Workforce Report', date: 'Sep 2026', verified: true, signal: '+34% Requisition Growth for AI Infrastructure', supports: 'Validates rapid market expansion for AI engineering professionals with low-level systems familiarity.' },
      { source: 'IEEE Spectrum Engineering Workforce Benchmark', type: 'Industry Research', date: 'Aug 2026', verified: true, signal: 'Python & CUDA Top Required Stack in 78% of Postings', supports: 'Confirms that hardware acceleration skills command high role leverage and compensation premiums.' },
      { source: 'NASSCOM India AI Talent Landscape', type: 'Regional Industry Study', date: 'Jul 2026', verified: true, signal: 'Bangalore Accounts for 41% of National AI Openings', supports: 'Highlights regional concentration and high requisition density in target hub.' }
    ],
    aiInsight: {
      whatChanged: 'Requisitions for AI Engineers in the selected market increased +18.4%, with employers placing higher emphasis on production deployment and latency optimization.',
      whyItMatters: 'Organizations are transitioning from exploratory LLM prototypes into production systems requiring robust API SLAs, GPU cluster governance, and cost efficiency.',
      whatItMeans: 'Your background in Python and Machine Learning provides a solid baseline; bridging CUDA systems acceleration will position you in the top candidate percentile.',
      whatYouShouldDo: 'Focus immediate development on GPU parallel architecture and Triton/CUDA kernels, then target open requisitions at infrastructure leaders.',
      recommendations: [
        { type: 'Skill Focus', title: 'Bridge CUDA and GPU Acceleration Gap', desc: 'Appears as a recurring requirement across 480+ AI infrastructure roles.', skill: 'CUDA', primaryAction: 'Build Roadmap' },
        { type: 'Target Employer', title: 'Explore NVIDIA Engineering Openings', desc: 'NVIDIA is expanding Bangalore datacenter engineering operations with 480+ live requisitions.', company: 'NVIDIA', primaryAction: 'Explore in Market' },
        { type: 'Role Opportunity', title: 'Prepare for AI Infrastructure Engineer Requisitions', desc: 'Review benchmark assessment and role requirements.', role: 'AI Infrastructure Engineer', primaryAction: 'View Role Details' }
      ]
    }
  },
  {
    id: 'ml-engineer',
    name: 'Machine Learning Engineer',
    category: 'AI / ML',
    icon: 'brain-circuit',
    demandScore: 85,
    growthPercentage: 16.2,
    change: 16.2,
    direction: 'up',
    status: 'High Growth',
    openRoles: 9800,
    hiringCompaniesCount: 620,
    isFavorite: true,
    isMyRole: true,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹24L - ₹48L / yr ($150k - $210k)',
    locations: ['Bangalore', 'Hyderabad', 'Pune', 'Global', 'Remote'],
    history: [50, 56, 62, 70, 77, 81, 86],
    projection: [88, 91, 94],
    signals: {
      openRoles: [42, 50, 57, 66, 74, 80, 86],
      companyActivity: [46, 52, 60, 68, 75, 80, 85],
      momentum: [48, 55, 63, 71, 78, 83, 88],
      reduction: [10, 9, 8, 8, 7, 7, 6]
    },
    overview: 'Specializes in training, validating, and monitoring predictive statistical models, deep neural networks, and automated retraining pipelines.',
    responsibilities: [
      'Develop distributed training pipelines in PyTorch and JAX.',
      'Build feature engineering stores and continuous evaluation benchmarks.',
      'Deploy models using containerized inference servers and model registries.',
      'Mitigate model drift and conduct performance benchmarking.'
    ],
    evolution: {
      current: ['Python', 'Machine Learning', 'PyTorch', 'Pandas'],
      emerging: ['MLOps', 'Cloud Computing', 'FastAPI', 'Kubeflow'],
      future: ['Automated Model Distillation', 'Synthetic Data Generation']
    },
    adjacentRoles: ['AI Engineer', 'Data Scientist', 'MLOps Engineer'],
    careerProgression: [
      { step: 'Current Profile', title: 'ML Practitioner', match: 'Strong match' },
      { step: 'Target Role', title: 'Senior ML Engineer', match: 'Target' },
      { step: 'Advanced Track', title: 'Principal Research Engineer', match: 'Specialist' }
    ],
    alignmentFactors: {
      skillAlignment: 'High (Core Python, Scikit, PyTorch match 88%)',
      roleDemand: 'Strong (+16.2% acceleration, 9,800 openings)',
      experienceFit: 'Strong fit for analytical and software modeling',
      locationFit: 'High across Bangalore, Hyderabad and Remote',
      skillGaps: 'Production MLOps pipelines and cluster orchestration'
    },
    companiesHiring: [
      { name: 'Google', logoInitials: 'GO', brandColor: '#4285F4', signalText: '+18.4% ML Research', change: 18.4, dir: 'up', openCount: 280, location: 'Bangalore' },
      { name: 'Meta', logoInitials: 'ME', brandColor: '#0668E1', signalText: '+21.8% PyTorch Systems', change: 21.8, dir: 'up', openCount: 310, location: 'Remote / US' },
      { name: 'NVIDIA', logoInitials: 'NV', brandColor: '#76B900', signalText: '+24.6% Triton ML', change: 24.6, dir: 'up', openCount: 340, location: 'Bangalore' }
    ],
    jobOpportunities: [
      { id: 'job-go-1', company: 'Google', role: 'Machine Learning Systems Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Machine Learning', 'Python', 'JAX'], posted: '1 day ago', signal: 'Hot' },
      { id: 'job-me-1', company: 'Meta', role: 'Applied ML Recommender Engineer', location: 'Remote, India', type: 'Full-time', reqSkills: ['PyTorch', 'Python', 'Distributed Systems'], posted: '3 days ago', signal: 'High Match' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Core data modeling language.' },
      { name: 'Machine Learning', importance: 'Critical', trend: '+24.6%', status: 'Known', level: 'Advanced', notes: 'Deep theoretical and practical modeling mastery.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Cloud storage and distributed GPU training clusters.' },
      { name: 'CUDA', importance: 'Medium', trend: '+32.4%', status: 'Gap', level: 'Needs Development', notes: 'Low-level performance tuning.' }
    ],
    evidence: [
      { source: 'ACM Tech Workforce Review', type: 'Industry Benchmark', date: 'Aug 2026', verified: true, signal: 'Demand for ML Production Specialists up +28%', supports: 'Confirms continuous corporate hiring for production-grade model developers.' }
    ],
    aiInsight: {
      whatChanged: 'Employers are shifting hiring criteria from theoretical notebook prototyping toward production deployment reliability and pipeline automation.',
      whyItMatters: 'Enterprises have built prototype models but require robust engineering to maintain accuracy, prevent drift, and manage cloud training expenses.',
      whatItMeans: 'Strengthening your MLOps and cloud deployment skills will directly unlock senior compensation tiers.',
      whatYouShouldDo: 'Formalize your production deployment portfolio with continuous training and automated testing pipelines.',
      recommendations: [
        { type: 'Skill Focus', title: 'Formalize MLOps and Deployment Pipelines', desc: 'Accelerate containerized serving and automated testing.', skill: 'Cloud Computing', primaryAction: 'Build Roadmap' },
        { type: 'Employer Intel', title: 'Investigate Google Cloud ML Openings', desc: 'Google has 280+ active requisitions in Bangalore.', company: 'Google', primaryAction: 'Explore in Market' }
      ]
    }
  },
  {
    id: 'backend-dev',
    name: 'Backend Developer',
    category: 'Software Engineering',
    icon: 'server',
    demandScore: 82,
    growthPercentage: 12.8,
    change: 12.8,
    direction: 'up',
    status: 'Steady Growth',
    openRoles: 18200,
    hiringCompaniesCount: 1450,
    isFavorite: false,
    isMyRole: true,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹18L - ₹38L / yr ($130k - $185k)',
    locations: ['Bangalore', 'Chennai', 'Pune', 'Hyderabad', 'Remote'],
    history: [54, 60, 66, 71, 76, 79, 83],
    projection: [85, 87, 89],
    signals: {
      openRoles: [50, 56, 62, 69, 74, 78, 83],
      companyActivity: [52, 58, 64, 70, 75, 79, 82],
      momentum: [48, 54, 60, 67, 72, 76, 80],
      reduction: [9, 8, 8, 7, 7, 6, 6]
    },
    overview: 'Builds scalable API services, distributed transaction systems, microservices architectures, and persistent database interfaces.',
    responsibilities: [
      'Design high-throughput RESTful and gRPC endpoints.',
      'Optimize database queries and distributed caching layers.',
      'Implement authentication, rate-limiting, and telemetry monitoring.',
      'Ensure zero-downtime database migrations and continuous deployment.'
    ],
    evolution: {
      current: ['Python', 'SQL', 'FastAPI', 'PostgreSQL', 'Docker'],
      emerging: ['Cloud Computing', 'Go', 'Event-Driven Architectures', 'Kafka'],
      future: ['AI Copilot Integration', 'Edge Microservices']
    },
    adjacentRoles: ['Full Stack Engineer', 'Cloud Solutions Architect', 'Data Engineer'],
    careerProgression: [
      { step: 'Current Profile', title: 'Software Engineer', match: 'Direct match' },
      { step: 'Target Role', title: 'Senior Backend Architect', match: 'Target' }
    ],
    alignmentFactors: {
      skillAlignment: 'High (Python, SQL, Microservices match 85%)',
      roleDemand: 'Very High Volume (18,200 open positions)',
      experienceFit: 'Solid foundation across core web architectures',
      locationFit: 'Extensive requisition spread across all tier-1 cities',
      skillGaps: 'Distributed event systems and high-throughput Kafka design'
    },
    companiesHiring: [
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+16.5% Enterprise APIs', change: 16.5, dir: 'up', openCount: 620, location: 'Bangalore' },
      { name: 'Amazon', logoInitials: 'AM', brandColor: '#FF9900', signalText: '+14.2% Distributed Services', change: 14.2, dir: 'up', openCount: 580, location: 'Chennai' },
      { name: 'Snowflake', logoInitials: 'SN', brandColor: '#29B5E8', signalText: '+15.6% Cloud Infrastructure', change: 15.6, dir: 'up', openCount: 210, location: 'Pune' }
    ],
    jobOpportunities: [
      { id: 'job-ms-be', company: 'Microsoft', role: 'Senior Backend Cloud Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Python', 'SQL', 'Azure'], posted: '2 days ago', signal: 'High Match' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Core development stack.' },
      { name: 'SQL', importance: 'Critical', trend: '+11.2%', status: 'Known', level: 'Advanced', notes: 'Relational data design.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Container orchestration.' }
    ],
    evidence: [
      { source: 'Stack Overflow Developer Survey', type: 'Community Survey', date: '2026', verified: true, signal: 'Backend & Cloud APIs remain highest hiring volume', supports: 'Shows enduring stability of core backend engineering talent requisitions.' }
    ],
    aiInsight: {
      whatChanged: 'Backend roles are increasingly requiring cloud-native infrastructure automation and AI API integration capabilities.',
      whyItMatters: 'Every modern enterprise application is integrating AI orchestration into existing business transaction backends.',
      whatItMeans: 'Your core skills are strong; adding cloud architectural credentials will elevate your positioning.',
      whatYouShouldDo: 'Master cloud microservice patterns and distributed streaming systems.',
      recommendations: [
        { type: 'Skill Focus', title: 'Advance Cloud Computing & Microservices', desc: 'Target 18,200+ open enterprise backend requisitions.', skill: 'Cloud Computing', primaryAction: 'Build Roadmap' }
      ]
    }
  },
  {
    id: 'data-engineer',
    name: 'Data Engineer',
    category: 'Data',
    icon: 'database',
    demandScore: 84,
    growthPercentage: 15.6,
    change: 15.6,
    direction: 'up',
    status: 'High Growth',
    openRoles: 11400,
    hiringCompaniesCount: 780,
    isFavorite: false,
    isMyRole: true,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹22L - ₹42L / yr ($140k - $195k)',
    locations: ['Bangalore', 'Hyderabad', 'Pune', 'Chennai', 'Remote'],
    history: [52, 58, 64, 71, 77, 81, 85],
    projection: [87, 90, 93],
    signals: {
      openRoles: [46, 52, 59, 67, 74, 80, 85],
      companyActivity: [48, 54, 61, 69, 76, 81, 84],
      momentum: [50, 56, 63, 70, 77, 82, 86],
      reduction: [9, 8, 8, 7, 7, 6, 6]
    },
    overview: 'Designs, operates, and scales robust ETL pipelines, lakehouse architectures, and real-time streaming data infrastructures.',
    responsibilities: [
      'Build batch and real-time streaming pipelines with Spark and Kafka.',
      'Optimize Snowflake and BigQuery data warehouse performance.',
      'Implement data governance, lineage tracking, and automated testing.',
      'Maintain reliable data interfaces for downstream ML and analytics teams.'
    ],
    evolution: {
      current: ['SQL', 'Python', 'Spark', 'Airflow', 'Snowflake'],
      emerging: ['Cloud Computing', 'dbt', 'Lakehouse (Iceberg)', 'Vector DBs'],
      future: ['Autonomous Data Quality Agents', 'Real-time Vector Streaming']
    },
    adjacentRoles: ['Backend Developer', 'Machine Learning Engineer', 'Analytics Engineer'],
    careerProgression: [
      { step: 'Current Profile', title: 'Data/Backend Engineer', match: 'Strong match' },
      { step: 'Target Role', title: 'Senior Data Architect', match: 'Target' }
    ],
    alignmentFactors: {
      skillAlignment: 'High (SQL, Python match 90%)',
      roleDemand: 'High (+15.6% momentum, 11,400 open positions)',
      experienceFit: 'Solid foundation in data manipulation and modeling',
      locationFit: 'Substantial requisitions in Bangalore and Pune',
      skillGaps: 'Lakehouse optimization and distributed Spark tuning'
    },
    companiesHiring: [
      { name: 'Snowflake', logoInitials: 'SN', brandColor: '#29B5E8', signalText: '+15.2% Lakehouse Expansion', change: 15.2, dir: 'up', openCount: 210, location: 'Pune' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+11.5% Fabric Requisitions', change: 11.5, dir: 'up', openCount: 310, location: 'Bangalore' },
      { name: 'Amazon', logoInitials: 'AM', brandColor: '#FF9900', signalText: '+14.8% Redshift Pipelines', change: 14.8, dir: 'up', openCount: 380, location: 'Hyderabad' }
    ],
    jobOpportunities: [
      { id: 'job-sn-de', company: 'Snowflake', role: 'Senior Data Platform Engineer', location: 'Pune, India', type: 'Full-time', reqSkills: ['SQL', 'Python', 'Snowflake'], posted: '3 days ago', signal: 'Priority Hire' }
    ],
    requiredSkills: [
      { name: 'SQL', importance: 'Critical', trend: '+14.5%', status: 'Known', level: 'Advanced', notes: 'Core data query and schema modeling.' },
      { name: 'Python', importance: 'Critical', trend: '+18.2%', status: 'Known', level: 'Advanced', notes: 'ETL orchestration and transformation scripts.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+12.4%', status: 'Known', level: 'Intermediate', notes: 'Cloud data warehousing and object storage.' }
    ],
    evidence: [
      { source: 'Gartner Data & Analytics Workforce Study', type: 'Research Report', date: 'Jul 2026', verified: true, signal: 'Clean data infrastructure is primary bottleneck for enterprise AI', supports: 'Underlines critical market leverage for skilled data engineering specialists.' }
    ],
    aiInsight: {
      whatChanged: 'Organizations are investing heavily in data foundation cleanup to feed proprietary enterprise data to LLMs and agents.',
      whyItMatters: 'AI applications fail without clean, governed, real-time data pipelines.',
      whatItMeans: 'Data engineers who understand vector embeddings and lakehouse formats enjoy rapid compensation growth.',
      whatYouShouldDo: 'Deepen lakehouse integration knowledge combining SQL with streaming pipelines.',
      recommendations: [
        { type: 'Skill Focus', title: 'Deepen SQL & Lakehouse Orchestration', desc: 'Expand cloud data platform expertise.', skill: 'SQL', primaryAction: 'Build Roadmap' }
      ]
    }
  },
  {
    id: 'cloud-architect',
    name: 'Cloud Solutions Architect',
    category: 'Cloud',
    icon: 'cloud',
    demandScore: 80,
    growthPercentage: 14.2,
    change: 14.2,
    direction: 'up',
    status: 'Steady Growth',
    openRoles: 8600,
    hiringCompaniesCount: 590,
    isFavorite: true,
    isMyRole: false,
    experienceLevel: 'Senior / Principal',
    averageComp: '₹32L - ₹65L / yr ($180k - $255k)',
    locations: ['Bangalore', 'Hyderabad', 'Chennai', 'Remote', 'Global'],
    history: [50, 56, 62, 68, 73, 77, 81],
    projection: [83, 86, 88],
    signals: {
      openRoles: [44, 50, 57, 65, 71, 76, 81],
      companyActivity: [46, 52, 59, 66, 72, 77, 82],
      momentum: [48, 54, 61, 68, 74, 79, 83],
      reduction: [8, 8, 7, 7, 6, 6, 5]
    },
    overview: 'Defines end-to-end enterprise cloud topography, high-availability multi-region systems, cloud security, and infrastructure economics.',
    responsibilities: [
      'Design multi-region cloud topology across AWS, Azure, and GCP.',
      'Implement zero-trust security postures and regulatory compliance.',
      'Optimize cloud computing economics, reserved capacity, and FinOps.',
      'Lead infrastructure migration and automated Terraform provisioning.'
    ],
    evolution: {
      current: ['Cloud Computing', 'Kubernetes', 'Terraform', 'Security'],
      emerging: ['AI Cloud Infrastructure', 'FinOps', 'Multi-Cloud Mesh'],
      future: ['Autonomous Self-Healing Infrastructure']
    },
    adjacentRoles: ['DevOps Lead', 'AI Infrastructure Architect', 'Backend Developer'],
    careerProgression: [
      { step: 'Current Profile', title: 'Senior Software Engineer', match: 'Aligned' },
      { step: 'Target Role', title: 'Enterprise Cloud Architect', match: 'Target' }
    ],
    alignmentFactors: {
      skillAlignment: 'Moderate (Cloud foundations known, system architecture developing)',
      roleDemand: 'High senior requisition density (8,600 roles)',
      experienceFit: 'Strong for senior technical leads',
      locationFit: 'High concentration across Bangalore and Hyderabad',
      skillGaps: 'Enterprise multi-cloud FinOps and zero-trust policies'
    },
    companiesHiring: [
      { name: 'Amazon', logoInitials: 'AM', brandColor: '#FF9900', signalText: '+16.4% AWS Architect Hiring', change: 16.4, dir: 'up', openCount: 580, location: 'Bangalore' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+16.4% Azure Platform Lead', change: 16.4, dir: 'up', openCount: 620, location: 'Hyderabad' }
    ],
    jobOpportunities: [
      { id: 'job-am-ca', company: 'Amazon', role: 'Senior Cloud Solutions Architect', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Cloud Computing', 'AWS', 'Distributed Systems'], posted: '1 day ago', signal: 'Urgent' }
    ],
    requiredSkills: [
      { name: 'Cloud Computing', importance: 'Critical', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Enterprise system design.' },
      { name: 'Python', importance: 'High', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Automation and infrastructure as code.' }
    ],
    evidence: [
      { source: 'IDC Worldwide Cloud Infrastructure Tracker', type: 'Industry Analysis', date: 'Aug 2026', verified: true, signal: 'Enterprise Cloud spend growing +21% YoY', supports: 'Highlights sustained high-value hiring for cloud architectural decision makers.' }
    ],
    aiInsight: {
      whatChanged: 'Cloud architecture roles now require deep familiarity with GPU cluster provisioning and automated FinOps monitoring.',
      whyItMatters: 'Unmanaged AI compute workloads can rapidly exceed enterprise cloud budgets without proactive capacity planning.',
      whatItMeans: 'Positioning yourself with cloud architecture credentials commands leadership compensation.',
      whatYouShouldDo: 'Pursue multi-cloud infrastructure and FinOps competencies.',
      recommendations: [
        { type: 'Skill Focus', title: 'Deepen Cloud Computing Multi-Region Architecture', desc: 'Target 8,600+ open senior architect positions.', skill: 'Cloud Computing', primaryAction: 'Build Roadmap' }
      ]
    }
  },
  {
    id: 'cybersecurity-specialist',
    name: 'Cybersecurity Specialist',
    category: 'Cybersecurity',
    icon: 'shield-check',
    demandScore: 83,
    growthPercentage: 17.1,
    change: 17.1,
    direction: 'up',
    status: 'High Growth',
    openRoles: 6200,
    hiringCompaniesCount: 440,
    isFavorite: false,
    isMyRole: false,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹22L - ₹45L / yr ($145k - $205k)',
    locations: ['Bangalore', 'Hyderabad', 'Chennai', 'Remote'],
    history: [46, 52, 60, 68, 74, 79, 84],
    projection: [86, 89, 92],
    signals: {
      openRoles: [42, 48, 56, 64, 72, 78, 83],
      companyActivity: [44, 50, 58, 66, 73, 78, 82],
      momentum: [48, 55, 62, 70, 77, 82, 86],
      reduction: [6, 6, 5, 5, 4, 4, 4]
    },
    overview: 'Protects critical digital infrastructure, secures CI/CD delivery pipelines, manages threat detection, and enforces cryptographic governance.',
    responsibilities: [
      'Conduct vulnerability assessments and penetration testing.',
      'Deploy automated DevSecOps scanners in cloud build pipelines.',
      'Investigate security incidents and manage threat hunting telemetry.',
      'Enforce zero-trust architecture and cryptographic identity standards.'
    ],
    evolution: {
      current: ['Network Security', 'Python', 'Linux', 'SIEM'],
      emerging: ['Cloud Security (CSPM)', 'AI Model Security (Prompt Injection)', 'DevSecOps'],
      future: ['Post-Quantum Cryptography', 'Autonomous Defensive Agents']
    },
    adjacentRoles: ['Cloud Solutions Architect', 'DevOps Lead'],
    careerProgression: [
      { step: 'Target Role', title: 'Cybersecurity Lead', match: 'Specialist' }
    ],
    alignmentFactors: {
      skillAlignment: 'Moderate (Python & Linux known, security frameworks developing)',
      roleDemand: 'High resilience and defense demand (+17.1% acceleration)',
      experienceFit: 'Good technical foundation',
      locationFit: 'High in financial and IT enterprise centers',
      skillGaps: 'Threat intelligence and DevSecOps tooling'
    },
    companiesHiring: [
      { name: 'Apple', logoInitials: 'AP', brandColor: '#A2AAAD', signalText: '+12.0% Private Cloud Security', change: 12.0, dir: 'up', openCount: 180, location: 'Hyderabad' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+15.2% Sentinel Cloud Security', change: 15.2, dir: 'up', openCount: 290, location: 'Bangalore' }
    ],
    jobOpportunities: [
      { id: 'job-ap-sec', company: 'Apple', role: 'Private Cloud Compute Systems Security Engineer', location: 'Hyderabad, India', type: 'Full-time', reqSkills: ['Cloud Computing', 'Security', 'Python'], posted: '4 days ago', signal: 'Priority' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'High', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Security automation scripting.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Cloud posture security.' }
    ],
    evidence: [
      { source: 'Cybersecurity Ventures Global Talent Report', type: 'Industry Study', date: '2026', verified: true, signal: 'Zero percent unemployment rate in specialized cloud security', supports: 'Underscores persistent shortage of qualified defense engineers.' }
    ],
    aiInsight: {
      whatChanged: 'Security teams are urgently developing defenses against automated AI attacks and cloud supply chain exploits.',
      whyItMatters: 'Data privacy regulations and enterprise security breaches carry catastrophic financial penalties.',
      whatItMeans: 'Engineers who understand cloud infrastructure security enjoy virtually insulated job stability.',
      whatYouShouldDo: 'Learn cloud security posture management and automated vulnerability scanning.',
      recommendations: [
        { type: 'Skill Focus', title: 'Learn Cloud Security & Threat Modeling', desc: 'Strengthen enterprise security posture.', skill: 'Cloud Computing', primaryAction: 'Build Roadmap' }
      ]
    }
  },
  {
    id: 'devops-mlops',
    name: 'DevOps & MLOps Lead',
    category: 'DevOps',
    icon: 'git-merge',
    demandScore: 86,
    growthPercentage: 19.5,
    change: 19.5,
    direction: 'up',
    status: 'High Growth',
    openRoles: 7100,
    hiringCompaniesCount: 510,
    isFavorite: false,
    isMyRole: false,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹26L - ₹52L / yr ($160k - $225k)',
    locations: ['Bangalore', 'Hyderabad', 'Pune', 'Remote'],
    history: [48, 55, 63, 72, 80, 85, 90],
    projection: [92, 95, 98],
    signals: {
      openRoles: [42, 50, 58, 68, 76, 83, 89],
      companyActivity: [45, 52, 60, 69, 77, 82, 87],
      momentum: [50, 58, 66, 75, 83, 88, 93],
      reduction: [7, 7, 6, 6, 5, 5, 4]
    },
    overview: 'Automates distributed model deployments, CI/CD pipelines, Kubernetes GPU scheduling, and production observability platforms.',
    responsibilities: [
      'Manage Kubernetes GPU clusters using Slurm and KubeFlow.',
      'Build end-to-end automated model retraining and canary rollout pipelines.',
      'Monitor inference latencies, throughput, and hardware utilization.',
      'Enforce infrastructure-as-code with Terraform and GitOps.'
    ],
    evolution: {
      current: ['Kubernetes', 'Docker', 'Python', 'Terraform', 'CI/CD'],
      emerging: ['GPU Scheduling (Triton)', 'MLflow', 'Slurm', 'Ray'],
      future: ['Autonomous Self-Healing AI Clusters']
    },
    adjacentRoles: ['AI Engineer', 'Cloud Solutions Architect', 'Backend Developer'],
    careerProgression: [
      { step: 'Target Role', title: 'Lead MLOps Platform Engineer', match: 'Target' }
    ],
    alignmentFactors: {
      skillAlignment: 'High (Python, Cloud match 85%)',
      roleDemand: 'Very High (+19.5% momentum, 7,100 roles)',
      experienceFit: 'Natural bridge for engineers with software and cloud backgrounds',
      locationFit: 'Concentrated in AI innovation centers',
      skillGaps: 'Slurm and GPU cluster scheduling'
    },
    companiesHiring: [
      { name: 'NVIDIA', logoInitials: 'NV', brandColor: '#76B900', signalText: '+28.4% DGX Cloud Ops', change: 28.4, dir: 'up', openCount: 190, location: 'Bangalore' },
      { name: 'Google', logoInitials: 'GO', brandColor: '#4285F4', signalText: '+15.2% GKE AI Platform', change: 15.2, dir: 'up', openCount: 410, location: 'Bangalore' }
    ],
    jobOpportunities: [
      { id: 'job-nv-ops', company: 'NVIDIA', role: 'DGX Cloud Infrastructure Operations Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Cloud Computing', 'CUDA', 'Python'], posted: '3 days ago', signal: 'Hot' }
    ],
    requiredSkills: [
      { name: 'Cloud Computing', importance: 'Critical', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Cluster orchestration.' },
      { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Automation tooling.' },
      { name: 'CUDA', importance: 'High', trend: '+32.4%', status: 'Gap', level: 'Needs Development', notes: 'GPU driver & hardware optimization.' }
    ],
    evidence: [
      { source: 'CNCF Annual Cloud Native Survey', type: 'Technical Survey', date: '2026', verified: true, signal: '84% of organizations running AI workloads on Kubernetes', supports: 'Confirms surging requirement for Kubernetes engineers with AI hardware experience.' }
    ],
    aiInsight: {
      whatChanged: 'Traditional DevOps is transitioning rapidly to MLOps as companies prioritize GPU utilization over standard CPU workloads.',
      whyItMatters: 'Idle GPU nodes cost organizations tens of thousands of dollars per month without automated orchestration.',
      whatItMeans: 'Engineers who master GPU scheduling in Kubernetes command top-of-market compensation.',
      whatYouShouldDo: 'Gain hands-on expertise with Ray, Triton, and Kubernetes GPU device plugins.',
      recommendations: [
        { type: 'Skill Focus', title: 'Master Kubernetes GPU Cluster Scheduling', desc: 'Target 7,100+ open MLOps roles.', skill: 'Cloud Computing', primaryAction: 'Build Roadmap' }
      ]
    }
  },
  {
    id: 'frontend-engineer',
    name: 'Frontend Engineer',
    category: 'Frontend',
    icon: 'layout',
    demandScore: 75,
    growthPercentage: 8.4,
    change: 8.4,
    direction: 'up',
    status: 'Moderate',
    openRoles: 10200,
    hiringCompaniesCount: 730,
    isFavorite: false,
    isMyRole: false,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹16L - ₹32L / yr ($115k - $165k)',
    locations: ['Bangalore', 'Chennai', 'Pune', 'Remote'],
    history: [56, 60, 64, 68, 71, 73, 76],
    projection: [77, 79, 81],
    signals: {
      openRoles: [52, 56, 61, 66, 70, 72, 75],
      companyActivity: [54, 58, 62, 67, 70, 72, 74],
      momentum: [50, 54, 58, 62, 66, 69, 72],
      reduction: [10, 10, 9, 9, 8, 8, 7]
    },
    overview: 'Creates responsive, hardware-accelerated user interfaces, accessible design system components, and interactive data visualizations.',
    responsibilities: [
      'Build responsive client interfaces in modern JavaScript frameworks.',
      'Optimize web performance, Core Web Vitals, and rendering budgets.',
      'Implement accessible design systems adhering to WCAG 2.2 standards.',
      'Integrate streaming conversational AI interfaces and realtime websockets.'
    ],
    evolution: {
      current: ['JavaScript', 'TypeScript', 'React', 'CSS', 'HTML5'],
      emerging: ['Streaming UI / AI Components', 'WebAssembly', 'Micro-Frontends'],
      future: ['Voice & Multimodal Canvas Interfaces']
    },
    adjacentRoles: ['Full Stack Engineer', 'Product Designer'],
    careerProgression: [
      { step: 'Target Role', title: 'Senior Frontend Architect', match: 'Aligned' }
    ],
    alignmentFactors: {
      skillAlignment: 'Moderate (Software principles known, modern UI frameworks developing)',
      roleDemand: 'Substantial volume across all consumer and enterprise SaaS',
      experienceFit: 'Applicable for web-focused software development',
      locationFit: 'Broad across all tech hubs',
      skillGaps: 'Advanced canvas rendering and streaming state management'
    },
    companiesHiring: [
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+11.2% Copilot Web UX', change: 11.2, dir: 'up', openCount: 380, location: 'Bangalore' },
      { name: 'Google', logoInitials: 'GO', brandColor: '#4285F4', signalText: '+9.4% Gemini Workspace UI', change: 9.4, dir: 'up', openCount: 290, location: 'Hyderabad' }
    ],
    jobOpportunities: [
      { id: 'job-ms-fe', company: 'Microsoft', role: 'Frontend Design Systems Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['TypeScript', 'React', 'CSS'], posted: '4 days ago', signal: 'Standard' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'Medium', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Full-stack integration.' },
      { name: 'Cloud Computing', importance: 'Medium', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Edge CDN deployments.' }
    ],
    evidence: [
      { source: 'W3C Web Standards Workforce Survey', type: 'Industry Study', date: '2026', verified: true, signal: 'Frontend roles emphasizing AI streaming UX and latency budgets', supports: 'Reflects shifting demands toward interactive AI consumer experiences.' }
    ],
    aiInsight: {
      whatChanged: 'Frontend demand is steady, with premium compensation shifting toward developers capable of building streaming AI canvases.',
      whyItMatters: 'Users interact with AI through modern web clients; sluggish interfaces degrade the entire model experience.',
      whatItMeans: 'Combining frontend skill with backend API integration provides full-stack resilience.',
      whatYouShouldDo: 'Master streaming state management and responsive design systems.',
      recommendations: [
        { type: 'Career Focus', title: 'Explore Full-Stack AI Canvas Architecture', desc: 'Expand frontend capabilities to match full-stack requisitions.', role: 'Frontend Engineer', primaryAction: 'View Details' }
      ]
    }
  },
  {
    id: 'ai-pm',
    name: 'AI Product Manager',
    category: 'Product',
    icon: 'compass',
    demandScore: 79,
    growthPercentage: 13.6,
    change: 13.6,
    direction: 'up',
    status: 'Growing',
    openRoles: 4300,
    hiringCompaniesCount: 380,
    isFavorite: false,
    isMyRole: false,
    experienceLevel: 'Senior',
    averageComp: '₹28L - ₹60L / yr ($170k - $240k)',
    locations: ['Bangalore', 'Hyderabad', 'Remote', 'Global'],
    history: [46, 52, 59, 66, 72, 76, 80],
    projection: [82, 85, 87],
    signals: {
      openRoles: [40, 46, 54, 62, 69, 73, 77],
      companyActivity: [44, 50, 58, 65, 71, 75, 79],
      momentum: [48, 54, 61, 68, 74, 78, 82],
      reduction: [8, 8, 7, 7, 6, 6, 5]
    },
    overview: 'Defines AI product strategy, user discovery, evaluation metrics, model cost economics, and cross-functional engineering execution.',
    responsibilities: [
      'Define model evaluation benchmarks and acceptable hallucination thresholds.',
      'Model unit economics (token cost per user action vs lifetime value).',
      'Lead cross-functional teams of research scientists, engineers, and designers.',
      'Ensure regulatory compliance and AI safety governance.'
    ],
    evolution: {
      current: ['Product Strategy', 'User Research', 'Data Analysis', 'Agile'],
      emerging: ['AI Model Evaluation', 'Token Economics', 'Prompt Architecture'],
      future: ['Agentic Autonomous Workflow Design']
    },
    adjacentRoles: ['AI Engineer', 'Data Scientist'],
    careerProgression: [
      { step: 'Target Role', title: 'Group Product Manager — AI Platform', match: 'Strategic Leadership' }
    ],
    alignmentFactors: {
      skillAlignment: 'Moderate (Strong technical acumen, product methodology developing)',
      roleDemand: 'Selective high-impact hiring (4,300 roles)',
      experienceFit: 'Favorable for technical leaders transitioning into strategic product roles',
      locationFit: 'High in tier-1 product hubs',
      skillGaps: 'AI unit economics and enterprise customer discovery'
    },
    companiesHiring: [
      { name: 'OpenAI', logoInitials: 'AI', brandColor: '#10A37F', signalText: '+32.5% Enterprise PM Hiring', change: 32.5, dir: 'up', openCount: 90, location: 'Remote / US' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+14.8% Copilot Product Studio', change: 14.8, dir: 'up', openCount: 160, location: 'Bangalore' }
    ],
    jobOpportunities: [
      { id: 'job-ai-pm-ms', company: 'Microsoft', role: 'Principal AI Product Manager — Copilot Studio', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Product Management', 'Generative AI', 'Python'], posted: '5 days ago', signal: 'Leadership' }
    ],
    requiredSkills: [
      { name: 'Machine Learning', importance: 'High', trend: '+24.6%', status: 'Known', level: 'Intermediate', notes: 'Technical empathy with research teams.' },
      { name: 'Python', importance: 'Medium', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Data extraction and pipeline benchmarking.' }
    ],
    evidence: [
      { source: 'Product School AI PM Benchmark', type: 'Industry Report', date: '2026', verified: true, signal: '72% of software companies now require dedicated AI product leads', supports: 'Confirms emerging category shift from generalist PMs to technically grounded AI PMs.' }
    ],
    aiInsight: {
      whatChanged: 'Companies are hiring technically grounded product managers who can evaluate model performance beyond simple vanity metrics.',
      whyItMatters: 'Generalist PMs struggle to evaluate model failure modes and tokens-per-second infrastructure bottlenecks.',
      whatItMeans: 'Engineers with technical depth and communication skills make the highest-performing AI product leaders.',
      whatYouShouldDo: 'Study token unit economics and AI evaluation frameworks.',
      recommendations: [
        { type: 'Role Focus', title: 'Evaluate Transition into Technical AI Product Management', desc: 'Leverage technical background to lead AI initiatives.', role: 'AI Product Manager', primaryAction: 'View Details' }
      ]
    }
  },
  {
    id: 'fullstack-engineer',
    name: 'Full Stack Engineer',
    category: 'Software Engineering',
    icon: 'layers',
    demandScore: 78,
    growthPercentage: 11.5,
    change: 11.5,
    direction: 'up',
    status: 'Steady Growth',
    openRoles: 14800,
    hiringCompaniesCount: 920,
    isFavorite: false,
    isMyRole: false,
    experienceLevel: 'Mid to Senior',
    averageComp: '₹20L - ₹42L / yr ($135k - $185k)',
    locations: ['Bangalore', 'Hyderabad', 'Pune', 'Chennai', 'Remote'],
    history: [52, 57, 63, 69, 74, 78, 81],
    projection: [83, 85, 87],
    signals: {
      openRoles: [48, 54, 60, 67, 72, 76, 80],
      companyActivity: [50, 56, 62, 68, 73, 77, 81],
      momentum: [48, 54, 60, 66, 71, 75, 78],
      reduction: [9, 9, 8, 8, 7, 7, 6]
    },
    overview: 'Engineers responsive client experiences, scalable backend microservices, database schemas, and continuous delivery pipelines end-to-end.',
    responsibilities: [
      'Build end-to-end features spanning modern frontend and backend architectures.',
      'Design database schemas and optimize query patterns.',
      'Deploy applications to cloud container services with automated CI/CD.',
      'Integrate AI services and third-party APIs into user workflows.'
    ],
    evolution: {
      current: ['Python', 'SQL', 'JavaScript', 'Docker', 'FastAPI'],
      emerging: ['Cloud Computing', 'TypeScript', 'Serverless', 'AI APIs'],
      future: ['Agentic Co-Development Workflows']
    },
    adjacentRoles: ['Backend Developer', 'Frontend Engineer', 'AI Engineer'],
    careerProgression: [
      { step: 'Target Role', title: 'Senior Full Stack Lead', match: 'Aligned' }
    ],
    alignmentFactors: {
      skillAlignment: 'High (Python, SQL match 85%)',
      roleDemand: 'High volume across startup and enterprise ecosystems (14,800 roles)',
      experienceFit: 'Strong versatile software background',
      locationFit: 'Widely available across all cities and remote',
      skillGaps: 'Modern reactive frontend framework optimization'
    },
    companiesHiring: [
      { name: 'Amazon', logoInitials: 'AM', brandColor: '#FF9900', signalText: '+13.9% Web Platforms', change: 13.9, dir: 'up', openCount: 420, location: 'Bangalore' },
      { name: 'Microsoft', logoInitials: 'MS', brandColor: '#00A4EF', signalText: '+14.8% Cloud Solutions', change: 14.8, dir: 'up', openCount: 510, location: 'Hyderabad' }
    ],
    jobOpportunities: [
      { id: 'job-am-fs', company: 'Amazon', role: 'Full Stack Cloud Engineer', location: 'Bangalore, India', type: 'Full-time', reqSkills: ['Python', 'SQL', 'Cloud Computing'], posted: '2 days ago', signal: 'Active' }
    ],
    requiredSkills: [
      { name: 'Python', importance: 'Critical', trend: '+19.4%', status: 'Known', level: 'Advanced', notes: 'Core backend development.' },
      { name: 'SQL', importance: 'Critical', trend: '+11.2%', status: 'Known', level: 'Advanced', notes: 'Database schema modeling.' },
      { name: 'Cloud Computing', importance: 'High', trend: '+16.4%', status: 'Known', level: 'Intermediate', notes: 'Deployment and serverless hosting.' }
    ],
    evidence: [
      { source: 'Hired State of Software Engineering', type: 'Annual Report', date: '2026', verified: true, signal: 'Full-stack engineers receiving 2.1x more employer interview requests', supports: 'Confirms broad industry appetite for versatile end-to-end engineers.' }
    ],
    aiInsight: {
      whatChanged: 'Full-stack engineers with AI API integration experience are in higher demand than single-stack specialists in agile product teams.',
      whyItMatters: 'Small teams can ship complete generative AI products with fewer coordination bottlenecks.',
      whatItMeans: 'Your Python and SQL skills make you highly competitive for full-stack AI requisitions.',
      whatYouShouldDo: 'Highlight end-to-end product delivery in your career portfolio.',
      recommendations: [
        { type: 'Role Opportunity', title: 'Review 14,800+ Full Stack Opportunities', desc: 'High flexibility across startups and global enterprises.', role: 'Full Stack Engineer', primaryAction: 'View Opportunities' }
      ]
    }
  }
];

// ============================================================================
// HELPER FUNCTIONS FOR JOB INTELLIGENCE
// ============================================================================

export function getRolesForScope(scope = 'All Roles', favorites = [], saved = []) {
  if (scope === 'Favorite Roles') {
    return dedicatedJobRoles.filter(r => favorites.includes(r.name) || r.isFavorite);
  }
  if (scope === 'My Roles') {
    return dedicatedJobRoles.filter(r => saved.includes(r.name) || r.isMyRole);
  }
  return dedicatedJobRoles;
}

export function getRoleJobDetails(roleName = 'AI Engineer', location = 'Bangalore', timeRange = '30D', companyContext = []) {
  const normalized = (roleName || '').toLowerCase().trim();
  const role = dedicatedJobRoles.find(r => r.name.toLowerCase() === normalized || r.id === normalized) || dedicatedJobRoles[0];

  const locMultipliers = {
    Global: 1.0, India: 1.06, 'Tamil Nadu': 0.96, Bangalore: 1.08, Chennai: 0.98, Hyderabad: 1.04, Pune: 0.97, Remote: 1.02
  };
  const rangeMultipliers = {
    '7 Days': 0.45, '7D': 0.45, '30 Days': 1.0, '30D': 1.0, '3 Months': 1.35, '3M': 1.35, '6 Months': 1.8, '6M': 1.8
  };

  const locFactor = locMultipliers[location] || 1.0;
  const rangeFactor = rangeMultipliers[timeRange] || 1.0;

  const adjustedGrowth = Number((role.growthPercentage * locFactor * (rangeFactor > 1 ? 1 + (rangeFactor - 1) * 0.25 : rangeFactor)).toFixed(1));
  const adjustedOpenRoles = Math.round(role.openRoles * locFactor);
  const adjustedCompaniesCount = Math.round(role.hiringCompaniesCount * locFactor);

  // If specific company context is selected, filter companiesHiring
  let activeCompanies = role.companiesHiring || [];
  if (companyContext && companyContext.length > 0) {
    const matched = activeCompanies.filter(c => companyContext.includes(c.name));
    if (matched.length > 0) activeCompanies = matched;
  }

  return {
    ...role,
    adjustedGrowth,
    adjustedOpenRoles,
    adjustedCompaniesCount,
    currentLocation: location,
    currentTimeRange: timeRange,
    activeCompanies
  };
}

export function searchRoles(query = '', scope = 'All Roles', favorites = [], saved = []) {
  const base = getRolesForScope(scope, favorites, saved);
  const q = query.toLowerCase().trim();
  if (!q) return base;
  return base.filter(r =>
    r.name.toLowerCase().includes(q) ||
    r.category.toLowerCase().includes(q) ||
    (r.requiredSkills || []).some(s => s.name.toLowerCase().includes(q))
  );
}
