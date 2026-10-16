// ============================================================================
// TALENTSCOPE.AI — MARKET DATA (LEGACY / PROTOTYPE FALLBACK)
// DEPRECATION NOTICE:
// Live market intelligence is now served via the shared Core Intelligence engine
// at FastAPI `/api/v1/intelligence/market` or `/api/v1/intelligence/core` via
// `src/api/core-intelligence-client.js`.
// The datasets below are retained strictly for backward compatibility and fallback.
// ============================================================================

export const jobMarketData = {
  roles: ['AI Engineer', 'Backend Engineer', 'Data Engineer', 'Cloud Architect', 'Cybersecurity Lead'],
  totalOpenRoles: 42180,
  demandIndex: 91,
  hiringMomentum: 18.2,
  skillAlignment: 88,
  segments: [
    { id: 'roles', label: 'Open Role Activity', percent: 46, color: '#B22DEF', count: '42,180 roles', detail: '42,180 active role requisitions open across top technology employers.' },
    { id: 'companies', label: 'Hiring Company Activity', percent: 25, color: '#06B6D4', count: '2,480 employers', detail: '64% of enterprise employers opened new engineering requisitions in the last 30 days.' },
    { id: 'momentum', label: 'Role Demand Momentum', percent: 21, color: '#10B981', count: '+18.2% acceleration', detail: 'Accelerated demand momentum for AI Infrastructure and ML Backend roles.' },
    { id: 'reduction', label: 'Reduction Signal', percent: 8, color: '#F59E0B', count: '8% consolidation', detail: 'Slight consolidation signal across legacy IT operations roles.' }
  ],
  recommendation: {
    roleTitle: 'AI Engineer',
    growthText: '+18.4% demand growth',
    whyText: 'Your Python and Machine Learning skills align directly with growing AI engineering hiring requisitions in your target location.',
    factors: [
      { name: 'Skill Alignment', val: 'Python, ML, SQL' },
      { name: 'Role Demand', val: 'High (+18.4% momentum)' },
      { name: 'Hiring Activity', val: '2,480 active openings' },
      { name: 'Career Fit', val: 'AI Engineering Goal' }
    ],
    gaps: ['CUDA Systems', 'Deep Learning'],
    topLocations: ['Bangalore', 'Hyderabad', 'Chennai']
  }
};

export const marketOptions = ['Global', 'India', 'Tamil Nadu', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Remote', 'United States', 'United Kingdom', 'Germany', 'Singapore'];
export const timeRangeOptions = ['7 Days', '30 Days', '3 Months', '6 Months'];

export const marketTrends = [
  { region: 'Global', growth: 14.8, index: 88, topSkills: ['Generative AI', 'Python', 'Cloud Computing'] },
  { region: 'India', growth: 19.2, index: 92, topSkills: ['Python', 'Machine Learning', 'FastAPI'] },
  { region: 'United States', growth: 12.4, index: 86, topSkills: ['Generative AI', 'CUDA', 'Cloud Infrastructure'] }
];

export const technologyTrends = [
  { tech: 'LLM & RAG Systems', velocity: 34.2, status: 'High Adoption' },
  { tech: 'CUDA Acceleration', velocity: 28.6, status: 'High Demand' },
  { tech: 'FastAPI Backend', velocity: 18.4, status: 'Growing' }
];

export const industryTrends = [
  { sector: 'AI & Enterprise Software', momentum: '+22.4%', roles: 18400 },
  { sector: 'Fintech & Digital Banking', momentum: '+14.2%', roles: 12100 },
  { sector: 'Semiconductors & AI Hardware', momentum: '+28.1%', roles: 9400 }
];

export const marketSignalData = {
  totalSignals: 42180,
  activeEmployers: 2480,
  topHub: 'Bangalore / India'
};

export const companyVacancies = {
  Microsoft: 2480,
  TCS: 1940,
  NVIDIA: 1820,
  Google: 1680,
  OpenAI: 940,
  SAP: 1120,
  Shopify: 760,
  Atlassian: 540,
  Grab: 430,
  Sony: 880
};

export const marketTrendState = {
  company: 'Microsoft',
  view: 'Multi-Signal View'
};

// ============================================================================
// DEDICATED MARKET INTELLIGENCE DATA ARCHITECTURE
// ============================================================================

export const dedicatedMarketCompanies = [
  {
    id: 'nvidia',
    name: 'NVIDIA',
    logoInitials: 'NV',
    brandColor: '#76B900',
    sector: 'AI Hardware & Compute',
    industry: 'Semiconductors & AI Hardware',
    size: 'Enterprise (29,600+)',
    headcount: '29,600+',
    location: 'Global',
    primaryLocation: 'Bangalore & Santa Clara',
    marketMomentum: 88,
    technologyMomentum: 28.4,
    hiringMomentum: 18.2,
    investmentSignal: 24.6,
    change: 28.4,
    direction: 'up',
    signalText: 'Hiring Surge',
    signalType: 'positive',
    openRoles: 1820,
    isFavorite: true,
    isMyCompany: true,
    history: [42, 54, 62, 74, 82, 91, 98],
    multiSignals: {
      market: [48, 56, 65, 76, 82, 90, 98],
      technology: [52, 60, 68, 79, 86, 92, 99],
      hiring: [38, 46, 55, 68, 77, 85, 91],
      investment: [44, 52, 63, 72, 80, 88, 95]
    },
    companySignals: [
      { name: 'Blackwell Architecture Scale', type: 'Technology & Compute', time: '2 days ago', impact: '+14.2%', dir: 'up', desc: 'Hyperscale datacenters accelerating adoption of NVLink and B200 accelerated compute nodes.' },
      { name: 'Enterprise CUDA Cloud Requisitions', type: 'Hiring Surge', time: '4 days ago', impact: '+18.6%', dir: 'up', desc: '480+ new openings for AI Infrastructure and distributed compiler engineers across Indian & US hubs.' },
      { name: 'Sovereign AI Compute Infrastructure', type: 'Capital Investment', time: '1 week ago', impact: '+22.0%', dir: 'up', desc: 'Multi-billion dollar infrastructure initiatives expanding regional supercomputing centers.' }
    ],
    technologies: [
      { name: 'CUDA', trend: '+32.4%', adoption: 'Foundational Standard', roles: ['AI Infrastructure Engineer', 'Compiler Engineer'], skills: ['C++', 'Kernel Optimization', 'GPU Parallelism'], skillLink: 'CUDA' },
      { name: 'Python', trend: '+19.4%', adoption: 'High Enterprise Adoption', roles: ['ML Platform Engineer', 'AI Systems Engineer'], skills: ['PyTorch', 'NumPy', 'Triton'], skillLink: 'Python' },
      { name: 'Machine Learning', trend: '+24.6%', adoption: 'Core Production Focus', roles: ['ML Engineer', 'Research Scientist'], skills: ['Deep Learning', 'LLM Inference', 'Quantization'], skillLink: 'Machine Learning' },
      { name: 'Generative AI', trend: '+38.5%', adoption: 'Rapid Deployment', roles: ['Generative AI Specialist', 'Solution Architect'], skills: ['RAG Systems', 'NeMo Framework'], skillLink: 'Generative AI' },
      { name: 'Cloud Computing', trend: '+16.4%', adoption: 'Hybrid & DGX Cloud', roles: ['Cloud AI Architect', 'DevOps Engineer'], skills: ['Kubernetes', 'Slurm', 'Multi-Cloud'], skillLink: 'Cloud Computing' }
    ],
    productSignals: [
      { title: 'NVIDIA DGX Cloud & SuperPOD Cluster', date: 'Active Q3 2026', status: 'Scaling', note: 'Accelerating AI enterprise cluster provisioning by 4x across tier-1 cloud providers.' },
      { title: 'CUDA-X AI Accelerated Inference Libraries', date: 'Recent', status: 'High Adoption', note: 'Standardized kernel acceleration integrated into major open-source inference stacks.' },
      { title: 'NeMo Microservices & NIM RAG Framework', date: 'Recent Update', status: 'Enterprise Expansion', note: 'Production-ready generative AI microservice deployment containers.' }
    ],
    roles: [
      { title: 'AI Infrastructure Engineer', momentum: '+24.2%', openCount: '480 open', location: 'Bangalore / Remote', requiredSkills: ['CUDA', 'Python', 'Kubernetes'], careerLink: true },
      { title: 'Machine Learning Systems Engineer', momentum: '+18.6%', openCount: '340 open', location: 'Global / Remote', requiredSkills: ['Machine Learning', 'PyTorch', 'C++'], careerLink: true },
      { title: 'Compiler Engineer (Triton / CUDA)', momentum: '+15.8%', openCount: '190 open', location: 'Hyderabad / US', requiredSkills: ['LLVM', 'CUDA', 'C++'], careerLink: true },
      { title: 'Cloud AI Solutions Architect', momentum: '+12.4%', openCount: '220 open', location: 'Bangalore / Chennai', requiredSkills: ['Cloud Computing', 'Distributed Systems'], careerLink: true }
    ],
    investments: [
      { focus: 'Frontier AI Compute & Silicon Packaging', scale: '$8.4B allocation', signal: '+26.8% YoY', detail: 'Capital expenditures dedicated to advanced packaging and next-generation optical interconnects.' },
      { focus: 'Developer Ecosystem & Academic Lab Grants', scale: '$1.2B deployment', signal: '+18.4% YoY', detail: 'Accelerating university and enterprise researcher access to accelerated DGX clusters.' }
    ],
    evidence: [
      { source: 'SEC Form 10-Q Quarterly Filing', type: 'Regulatory Report', date: 'Aug 2026', verified: true, signal: '+122% Data Center Revenue Growth', supports: 'Validates sustained enterprise AI infrastructure demand and hiring acceleration.' },
      { source: 'IEEE Spectrum Semiconductor Analysis', type: 'Industry Research', date: 'Sep 2026', verified: true, signal: '94% LLM Training Share', supports: 'Confirms dominant ecosystem moat across CUDA and accelerated software stack.' },
      { source: 'Global Tech Hiring Index (GTHI)', type: 'Workforce Data', date: 'Sep 2026', verified: true, signal: '+34% AI System Openings', supports: 'Supports high-momentum hiring for engineers with low-level acceleration proficiency.' }
    ],
    aiInsight: {
      whatChanged: 'NVIDIA has expanded hardware dominance into software platform infrastructure, driving a +28.4% surge in technology adoption and hiring demand across global AI hubs.',
      why: 'Frontier model training and inference workloads require specialized memory bandwidth and low-level kernel optimizations that currently favor CUDA-accelerated systems.',
      whatItMeans: 'Engineers with skills in Python, CUDA, and Machine Learning systems are seeing unprecedented role premiums, while generalist backend roles face consolidation.',
      whatToWatch: ['Next-generation Blackwell deployment timelines', 'Custom ASIC competition from cloud hyperscalers', 'Distributed compiler adoption (Triton / TorchDynamo)'],
      recommendations: [
        { action: 'Bridge CUDA and GPU parallel systems skills to qualify for AI Infrastructure roles.', tag: 'Skill Development', skill: 'CUDA' },
        { action: 'Evaluate 480+ open requisitions in Bangalore and Global hubs matching your Python background.', tag: 'Career Opportunity', role: 'AI Infrastructure Engineer' },
        { action: 'Monitor quarterly chip allocation signals to gauge timing for AI engineering expansions.', tag: 'Market Tracking' }
      ]
    },
    competitors: [
      { name: 'AMD', momentum: '+14.2%', diff: 'ROCm ecosystem & Instinct MI300X expansion' },
      { name: 'Google', momentum: '+12.2%', diff: 'TPU v5p internal infrastructure' },
      { name: 'Intel', momentum: '-4.2%', diff: 'Gaudi accelerator transition' }
    ]
  },
  {
    id: 'microsoft',
    name: 'Microsoft',
    logoInitials: 'MS',
    brandColor: '#00A4EF',
    sector: 'Enterprise Cloud & AI',
    industry: 'Enterprise Cloud & Software',
    size: 'Enterprise (220,000+)',
    headcount: '221,000+',
    location: 'Global',
    primaryLocation: 'Bangalore & Redmond',
    marketMomentum: 82,
    technologyMomentum: 21.2,
    hiringMomentum: 14.8,
    investmentSignal: 19.4,
    change: 14.8,
    direction: 'up',
    signalText: 'High Investment',
    signalType: 'positive',
    openRoles: 2480,
    isFavorite: true,
    isMyCompany: true,
    history: [44, 50, 58, 64, 72, 78, 85],
    multiSignals: {
      market: [50, 56, 62, 69, 74, 80, 85],
      technology: [54, 61, 67, 72, 78, 83, 89],
      hiring: [42, 48, 56, 62, 68, 74, 81],
      investment: [46, 54, 60, 68, 75, 82, 88]
    },
    companySignals: [
      { name: 'Azure OpenAI Enterprise Tier Expansion', type: 'Technology & Cloud', time: '1 day ago', impact: '+16.5%', dir: 'up', desc: 'Over 65% of Fortune 500 organizations adopting Azure AI foundry for internal copilots.' },
      { name: 'Copilot Studio Agent Framework', type: 'Product Milestone', time: '3 days ago', impact: '+12.8%', dir: 'up', desc: 'Rollout of multi-agent autonomous enterprise workflows driving cloud compute consumption.' },
      { name: 'Global Datacenter Capital Expansion', type: 'Infrastructure Investment', time: '5 days ago', impact: '+19.2%', dir: 'up', desc: '$10B+ infrastructure commit across India, Japan, and Western Europe.' }
    ],
    technologies: [
      { name: 'Cloud Computing', trend: '+18.2%', adoption: 'Market Standard (Azure)', roles: ['Cloud Solutions Architect', 'DevOps Lead'], skills: ['Azure Resource Manager', 'Terraform', 'Kubernetes'], skillLink: 'Cloud Computing' },
      { name: 'Generative AI', trend: '+28.7%', adoption: 'Core Copilot Stack', roles: ['AI Copilot Engineer', 'NLP Specialist'], skills: ['Prompt Architecture', 'RAG Pipelines', 'OpenAI APIs'], skillLink: 'Generative AI' },
      { name: 'Python', trend: '+16.4%', adoption: 'Broad Cloud Engineering', roles: ['Backend Cloud Engineer', 'Data Engineer'], skills: ['FastAPI', 'Pandas', 'Microservices'], skillLink: 'Python' },
      { name: 'SQL', trend: '+9.8%', adoption: 'Azure SQL & Fabric', roles: ['Data Architect', 'Analytics Engineer'], skills: ['Transact-SQL', 'Synapse', 'Fabric Lakehouse'], skillLink: 'SQL' }
    ],
    productSignals: [
      { title: 'Microsoft Copilot Studio & Multi-Agent Engine', date: 'Q3 2026', status: 'Enterprise Active', note: 'Standardizing autonomous workflow orchestration for enterprise customers.' },
      { title: 'Azure Fabric Lakehouse Intelligence', date: 'Recent', status: 'High Growth', note: 'Unified real-time analytics engine integrating SQL and automated ML telemetry.' }
    ],
    roles: [
      { title: 'Azure Cloud Solutions Architect', momentum: '+16.4%', openCount: '620 open', location: 'Bangalore / Hyderabad', requiredSkills: ['Cloud Computing', 'Azure', 'Kubernetes'], careerLink: true },
      { title: 'AI Copilot Backend Engineer', momentum: '+22.8%', openCount: '480 open', location: 'Global / Remote', requiredSkills: ['Python', 'Generative AI', 'Microservices'], careerLink: true },
      { title: 'Enterprise Data Platform Engineer', momentum: '+11.5%', openCount: '310 open', location: 'Chennai / Pune', requiredSkills: ['SQL', 'Data Engineering', 'Azure'], careerLink: true }
    ],
    investments: [
      { focus: 'Next-Generation Datacenter Footprint', scale: '$14.2B quarterly CAPEX', signal: '+28.4% YoY', detail: 'Massive capital expenditure dedicated to power infrastructure and dedicated AI cluster cooling.' },
      { focus: 'OpenAI Strategic Partnership Integration', scale: '$13B+ cumulative', signal: '+15.2% YoY', detail: 'Deep silicon and platform integration for frontier inference hosting.' }
    ],
    evidence: [
      { source: 'Microsoft Earnings Call Q4 FY26', type: 'Financial Disclosure', date: 'Jul 2026', verified: true, signal: '+31% Azure Cloud Revenue Growth', supports: 'Confirms accelerated enterprise migration to generative cloud microservices.' },
      { source: 'Gartner Magic Quadrant Cloud Platforms', type: 'Industry Research', date: 'Aug 2026', verified: true, signal: 'Leader in Cloud & AI Foundational Services', supports: 'Underscores strategic platform strength and persistent hiring demand.' }
    ],
    aiInsight: {
      whatChanged: 'Microsoft cloud services are experiencing strong tailwinds from enterprise Copilot adoption, with Azure revenue growing +31% YoY.',
      why: 'Enterprise clients are shifting from isolated LLM proofs-of-concept into full-scale multi-agent enterprise deployments.',
      whatItMeans: 'Specialists in Cloud Computing and Python-based API orchestration are in strong demand across Microsoft partner ecosystems.',
      whatToWatch: ['Copilot average revenue per user growth', 'Datacenter capacity constraints in regional hubs', 'Azure Fabric data lakehouse migrations'],
      recommendations: [
        { action: 'Expand Cloud Computing and Azure architectural mastery to target 620+ regional roles.', tag: 'Skill Development', skill: 'Cloud Computing' },
        { action: 'Review open AI Copilot engineering roles in Bangalore and Hyderabad.', tag: 'Career Opportunity', role: 'AI Copilot Backend Engineer' }
      ]
    },
    competitors: [
      { name: 'Amazon', momentum: '+16.4%', diff: 'AWS Bedrock & enterprise cloud leadership' },
      { name: 'Google', momentum: '+12.2%', diff: 'GCP Gemini enterprise stack' }
    ]
  },
  {
    id: 'google',
    name: 'Google',
    logoInitials: 'GO',
    brandColor: '#4285F4',
    sector: 'Cloud & AI Infrastructure',
    industry: 'Enterprise Cloud & Software',
    size: 'Enterprise (182,000+)',
    headcount: '182,500+',
    location: 'Global',
    primaryLocation: 'Bangalore & Mountain View',
    marketMomentum: 78,
    technologyMomentum: 18.6,
    hiringMomentum: 12.2,
    investmentSignal: 16.5,
    change: 12.2,
    direction: 'up',
    signalText: 'Tech Lead',
    signalType: 'positive',
    openRoles: 1680,
    isFavorite: true,
    isMyCompany: true,
    history: [50, 56, 62, 68, 74, 78, 82],
    multiSignals: {
      market: [52, 57, 63, 68, 73, 77, 82],
      technology: [58, 64, 70, 75, 80, 84, 88],
      hiring: [40, 46, 52, 58, 64, 70, 76],
      investment: [48, 55, 62, 67, 72, 79, 84]
    },
    companySignals: [
      { name: 'Gemini 1.5 Pro Long-Context Production', type: 'Technology Breakthrough', time: '3 days ago', impact: '+15.4%', dir: 'up', desc: 'Rapid enterprise adoption of 2M token context windows for multimodal code and document analytics.' },
      { name: 'Google Cloud Platform AI Growth', type: 'Market Momentum', time: '1 week ago', impact: '+13.8%', dir: 'up', desc: 'Google Cloud achieving sustained operating margin expansion driven by Vertex AI.' }
    ],
    technologies: [
      { name: 'Python', trend: '+19.4%', adoption: 'Core Language Standard', roles: ['Software Engineer', 'Research Scientist'], skills: ['JAX', 'TensorFlow', 'Flax'], skillLink: 'Python' },
      { name: 'Generative AI', trend: '+34.0%', adoption: 'Gemini Platform Stack', roles: ['AI Research Engineer', 'Applied Scientist'], skills: ['Multimodal Models', 'Vertex AI', 'RLHF'], skillLink: 'Generative AI' },
      { name: 'Cloud Computing', trend: '+13.8%', adoption: 'GCP Enterprise Footprint', roles: ['Cloud Architect', 'Site Reliability Engineer'], skills: ['Kubernetes / GKE', 'BigQuery', 'Anthos'], skillLink: 'Cloud Computing' }
    ],
    productSignals: [
      { title: 'Gemini Workspace & Vertex AI Agent Builder', date: 'Q3 2026', status: 'Production', note: 'Empowering enterprises to build grounded conversational agents with zero infrastructure overhead.' },
      { title: 'TPU v5e & Ironwood Cloud Pods', date: 'Active', status: 'Scaleup', note: 'Cost-efficient inference silicon tailored for large multimodal architectures.' }
    ],
    roles: [
      { title: 'Cloud Infrastructure Engineer (GKE)', momentum: '+15.2%', openCount: '410 open', location: 'Bangalore / Hyderabad', requiredSkills: ['Cloud Computing', 'Kubernetes', 'Go'], careerLink: true },
      { title: 'AI Research & Applied Scientist', momentum: '+18.4%', openCount: '280 open', location: 'Global / Bangalore', requiredSkills: ['Machine Learning', 'Python', 'JAX'], careerLink: true }
    ],
    investments: [
      { focus: 'Custom TPU Silicon & Clean Power Datacenters', scale: '$12.0B capital spend', signal: '+22.4% YoY', detail: 'Significant capital deployed into nuclear and geothermal energy contracts to power AI clusters.' }
    ],
    evidence: [
      { source: 'Alphabet Inc. 10-Q SEC Filing', type: 'Regulatory Filing', date: 'Aug 2026', verified: true, signal: '+29% Google Cloud Revenue', supports: 'Highlights GCP growth acceleration tied directly to Vertex AI adoption.' }
    ],
    aiInsight: {
      whatChanged: 'Google continues to lead in foundational research while expanding GCP profitability through Vertex AI customer expansions.',
      why: 'Frontier context window capabilities and custom TPU silicon reduce inference costs for enterprise customers.',
      whatItMeans: 'High opportunity for engineers experienced in Python, Kubernetes/GKE, and distributed training systems.',
      whatToWatch: ['TPU v5 deployment volumes', 'Vertex AI developer migration metrics', 'Gemini ecosystem monetization'],
      recommendations: [
        { action: 'Target Google Cloud and Kubernetes infrastructure competencies to match open GKE roles.', tag: 'Skill Focus', skill: 'Cloud Computing' },
        { action: 'Explore 410+ Cloud Engineering roles across Indian hubs.', tag: 'Hiring Requisition', role: 'Cloud Infrastructure Engineer (GKE)' }
      ]
    },
    competitors: [
      { name: 'Microsoft', momentum: '+14.8%', diff: 'Enterprise Copilot distribution' },
      { name: 'OpenAI', momentum: '+32.5%', diff: 'Frontier model velocity' }
    ]
  },
  {
    id: 'openai',
    name: 'OpenAI',
    logoInitials: 'AI',
    brandColor: '#10A37F',
    sector: 'Generative Models & Frontier AI',
    industry: 'Generative AI & Frontier',
    size: 'Growth (1,800+)',
    headcount: '1,800+',
    location: 'Global',
    primaryLocation: 'San Francisco & Remote',
    marketMomentum: 96,
    technologyMomentum: 34.5,
    hiringMomentum: 26.8,
    investmentSignal: 32.5,
    change: 32.5,
    direction: 'up',
    signalText: 'High Investment',
    signalType: 'positive',
    openRoles: 940,
    isFavorite: true,
    isMyCompany: false,
    history: [25, 40, 58, 70, 82, 90, 96],
    multiSignals: {
      market: [30, 48, 64, 75, 84, 91, 97],
      technology: [35, 52, 68, 78, 88, 94, 99],
      hiring: [22, 38, 54, 66, 76, 85, 92],
      investment: [40, 58, 72, 82, 89, 95, 99]
    },
    companySignals: [
      { name: 'Next-Generation Reasoning Architecture', type: 'Model Breakthrough', time: '1 day ago', impact: '+28.4%', dir: 'up', desc: 'Introduction of reinforcement learning-driven chain-of-thought models solving complex engineering tasks.' },
      { name: 'Enterprise API Adoption Surge', type: 'Market Growth', time: '3 days ago', impact: '+24.1%', dir: 'up', desc: 'Over 1M business developers utilizing Assistants API and fine-tuned GPT endpoints.' }
    ],
    technologies: [
      { name: 'Generative AI', trend: '+42.0%', adoption: 'Frontier Benchmark', roles: ['Research Scientist', 'Prompt Engineer'], skills: ['RLHF', 'Transformer Architectures', 'Alignment'], skillLink: 'Generative AI' },
      { name: 'Python', trend: '+28.2%', adoption: 'Primary Research Stack', roles: ['ML Platform Engineer', 'Backend Engineer'], skills: ['Triton', 'PyTorch', 'Distributed Training'], skillLink: 'Python' },
      { name: 'CUDA', trend: '+28.6%', adoption: 'Kernel Tuning', roles: ['Hardware Optimization Lead', 'Kernel Engineer'], skills: ['GPU Kernels', 'Memory Optimizers'], skillLink: 'CUDA' }
    ],
    productSignals: [
      { title: 'OpenAI o1 Reasoning Models', date: 'Recent Release', status: 'Frontier Production', note: 'Breakthrough mathematical and competitive coding capabilities for autonomous agents.' },
      { title: 'Enterprise Assistants & Function Calling', date: 'Active', status: 'High Adoption', note: 'Standard for building enterprise retrieval and execution agents.' }
    ],
    roles: [
      { title: 'Inference Infrastructure Engineer', momentum: '+32.4%', openCount: '160 open', location: 'San Francisco / Remote', requiredSkills: ['CUDA', 'Python', 'Distributed Systems'], careerLink: true },
      { title: 'Applied AI Alignment Researcher', momentum: '+28.0%', openCount: '110 open', location: 'Global / Remote', requiredSkills: ['Machine Learning', 'Python', 'RLHF'], careerLink: true }
    ],
    investments: [
      { focus: 'Frontier Compute Cluster Financing', scale: '$6.6B venture round', signal: '+45.0% YoY', detail: 'Secured landmark private capital funding at $157B valuation to finance compute and data acquisition.' }
    ],
    evidence: [
      { source: 'OpenAI Enterprise Growth Disclosure', type: 'Company Release', date: 'Sep 2026', verified: true, signal: '$3.7B Annualized Revenue Run Rate', supports: 'Illustrates rapid commercial growth and enterprise monetization.' }
    ],
    aiInsight: {
      whatChanged: 'OpenAI has accelerated enterprise adoption and secured substantial compute financing, driving massive demand for low-level inference engineers.',
      why: 'Complex reasoning models require 10x compute during inference, shifting engineering focus to latency reduction and kernel efficiency.',
      whatItMeans: 'Engineers with combined Python + CUDA skill sets have the highest leverage in the modern talent market.',
      whatToWatch: ['Model inference compute costs', 'Enterprise security certifications', 'Open-source frontier model competition'],
      recommendations: [
        { action: 'Build advanced competence in CUDA and PyTorch kernel optimization.', tag: 'Priority Skill', skill: 'CUDA' },
        { action: 'Review Generative AI benchmarks and agent architectures.', tag: 'Intelligence', skill: 'Generative AI' }
      ]
    },
    competitors: [
      { name: 'Anthropic', momentum: '+34.0%', diff: 'Claude 3.5 Sonnet coding leadership' },
      { name: 'Google', momentum: '+12.2%', diff: 'Gemini multimodal integration' }
    ]
  },
  {
    id: 'amazon',
    name: 'Amazon',
    logoInitials: 'AM',
    brandColor: '#FF9900',
    sector: 'Cloud Infrastructure & E-Commerce',
    industry: 'Enterprise Cloud & Software',
    size: 'Enterprise (1,500,000+)',
    headcount: '1,540,000+',
    location: 'Global',
    primaryLocation: 'Bangalore, Chennai & Seattle',
    marketMomentum: 76,
    technologyMomentum: 16.4,
    hiringMomentum: 13.9,
    investmentSignal: 18.2,
    change: 13.9,
    direction: 'up',
    signalText: 'Cloud Leader',
    signalType: 'positive',
    openRoles: 2150,
    isFavorite: false,
    isMyCompany: true,
    history: [46, 52, 58, 64, 70, 74, 79],
    multiSignals: {
      market: [48, 54, 60, 66, 72, 76, 80],
      technology: [52, 58, 64, 70, 75, 80, 84],
      hiring: [38, 44, 52, 59, 66, 72, 78],
      investment: [45, 52, 58, 65, 71, 78, 83]
    },
    companySignals: [
      { name: 'AWS Bedrock Multi-Model Hub Scale', type: 'Product Adoption', time: '2 days ago', impact: '+17.1%', dir: 'up', desc: 'Over 10,000 organizations routing LLM workloads through Amazon Bedrock.' },
      { name: 'Trainium & Inferentia Silicon Deployment', type: 'Hardware & Silicon', time: '5 days ago', impact: '+14.5%', dir: 'up', desc: 'Enterprise cost savings driving migration to Amazon custom silicon instances.' }
    ],
    technologies: [
      { name: 'Cloud Computing', trend: '+16.4%', adoption: 'Global Infrastructure Leader', roles: ['Solutions Architect', 'DevOps Specialist'], skills: ['AWS Lambda', 'ECS/EKS', 'IAM', 'Terraform'], skillLink: 'Cloud Computing' },
      { name: 'Python', trend: '+15.2%', adoption: 'Serverless & ML Pipelines', roles: ['Backend Developer', 'Data Engineer'], skills: ['Boto3', 'FastAPI', 'Pandas'], skillLink: 'Python' },
      { name: 'SQL', trend: '+11.0%', adoption: 'Redshift & Aurora DB', roles: ['Database Engineer', 'BI Analyst'], skills: ['PostgreSQL', 'Redshift', 'DynamoDB'], skillLink: 'SQL' }
    ],
    productSignals: [
      { title: 'Amazon Bedrock Enterprise Governance Guardrails', date: 'Q3 2026', status: 'Production', note: 'Filtering hallucinations and enforcing PII protection at enterprise scale.' },
      { title: 'AWS Trainium2 Accelerated Clusters', date: 'Recent', status: 'Expanding', note: 'Delivering up to 4x better training price-performance versus legacy nodes.' }
    ],
    roles: [
      { title: 'Senior Cloud Solutions Architect', momentum: '+14.8%', openCount: '580 open', location: 'Bangalore / Chennai', requiredSkills: ['Cloud Computing', 'AWS', 'Distributed Systems'], careerLink: true },
      { title: 'AWS Bedrock Generative AI Specialist', momentum: '+21.5%', openCount: '320 open', location: 'Hyderabad / Remote', requiredSkills: ['Generative AI', 'Python', 'Cloud Computing'], careerLink: true }
    ],
    investments: [
      { focus: 'Regional Cloud Datacenters & Custom Silicon Fab', scale: '$11.5B investment', signal: '+20.5% YoY', detail: 'Major regional infrastructure investments in India and southeast Asia.' }
    ],
    evidence: [
      { source: 'Amazon Q2 Financial Release', type: 'Earnings Report', date: 'Aug 2026', verified: true, signal: '$105B AWS Run-Rate (+19% YoY)', supports: 'Demonstrates resilient cloud spending and enterprise expansion.' }
    ],
    aiInsight: {
      whatChanged: 'AWS growth has re-accelerated as corporate clients finish cloud cost optimizations and begin active generative AI deployments.',
      why: 'Enterprise clients value Bedrock multi-model flexibility without being locked into a single model vendor.',
      whatItMeans: 'Cloud Computing and AWS architectural skills remain among the highest-volume hiring criteria across enterprise tech.',
      whatToWatch: ['AWS Bedrock customer growth rates', 'Trainium2 customer adoption benchmark', 'Enterprise serverless adoption'],
      recommendations: [
        { action: 'Deepen AWS Cloud Computing architecture certifications and system design.', tag: 'High Volume Skill', skill: 'Cloud Computing' },
        { action: 'Review 580+ open cloud architect requisitions across India.', tag: 'Open Role', role: 'Senior Cloud Solutions Architect' }
      ]
    },
    competitors: [
      { name: 'Microsoft', momentum: '+14.8%', diff: 'Azure enterprise AI integration' },
      { name: 'Google', momentum: '+12.2%', diff: 'GCP data & AI stack' }
    ]
  },
  {
    id: 'meta',
    name: 'Meta',
    logoInitials: 'ME',
    brandColor: '#0668E1',
    sector: 'Open-Source AI & Platforms',
    industry: 'Enterprise Cloud & Software',
    size: 'Enterprise (67,000+)',
    headcount: '67,300+',
    location: 'Global',
    primaryLocation: 'Menlo Park & Global Remote',
    marketMomentum: 80,
    technologyMomentum: 22.8,
    hiringMomentum: 15.6,
    investmentSignal: 21.0,
    change: 15.6,
    direction: 'up',
    signalText: 'Open Source AI',
    signalType: 'positive',
    openRoles: 1140,
    isFavorite: false,
    isMyCompany: false,
    history: [48, 55, 62, 69, 75, 80, 84],
    multiSignals: {
      market: [50, 56, 63, 69, 76, 81, 85],
      technology: [55, 62, 70, 78, 84, 89, 93],
      hiring: [41, 47, 54, 61, 68, 74, 80],
      investment: [48, 56, 64, 71, 79, 85, 90]
    },
    companySignals: [
      { name: 'Llama 3.1 & Open Weights Ecosystem', type: 'Open-Source Breakthrough', time: '4 days ago', impact: '+21.4%', dir: 'up', desc: 'Over 350M Llama downloads globally establishing open-source industry standard.' },
      { name: 'PyTorch 2.4 Distributed Compiler', type: 'Developer Tools', time: '1 week ago', impact: '+16.8%', dir: 'up', desc: 'Automatic graph capture and kernel fusion speeding up open-source training.' }
    ],
    technologies: [
      { name: 'Python', trend: '+19.4%', adoption: 'Foundational Ecosystem (PyTorch)', roles: ['AI Researcher', 'Systems Engineer'], skills: ['PyTorch', 'Distributed Training', 'TorchScript'], skillLink: 'Python' },
      { name: 'Machine Learning', trend: '+22.5%', adoption: 'Core Recommendation & LLM', roles: ['ML Platform Lead', 'Recommender Engineer'], skills: ['Deep Learning', 'GPU Clustering'], skillLink: 'Machine Learning' },
      { name: 'Generative AI', trend: '+31.2%', adoption: 'Llama Architecture', roles: ['Generative AI Engineer', 'Model Optimizer'], skills: ['Quantization', 'Fine-tuning', 'LoRA'], skillLink: 'Generative AI' }
    ],
    productSignals: [
      { title: 'Llama 3.1 405B Frontier Open Weights', date: 'Active', status: 'Industry Benchmark', note: 'Rivaling top proprietary closed models and powering hundreds of enterprise fine-tunes.' }
    ],
    roles: [
      { title: 'Distributed Systems & PyTorch Engineer', momentum: '+21.8%', openCount: '310 open', location: 'Global / Remote', requiredSkills: ['Python', 'C++', 'PyTorch'], careerLink: true },
      { title: 'AI Infrastructure Performance Engineer', momentum: '+17.4%', openCount: '240 open', location: 'Menlo Park / Remote', requiredSkills: ['CUDA', 'Python', 'Systems Tuning'], careerLink: true }
    ],
    investments: [
      { focus: 'GPU Cluster Buildout & Infrastructure', scale: '$37B-40B annual CAPEX', signal: '+32.0% YoY', detail: 'Deploying over 350,000 H100 GPU equivalents to power continuous model training and ranking.' }
    ],
    evidence: [
      { source: 'Meta Investor Relations Q2 2026', type: 'Public Disclosure', date: 'Jul 2026', verified: true, signal: '+22% Ad Revenue Powered by Advantage+ AI', supports: 'Demonstrates tangible return on investment from AI recommendation systems.' }
    ],
    aiInsight: {
      whatChanged: 'Meta open-source Llama strategy has made them the default foundation for on-premise and privacy-conscious enterprise AI deployments.',
      why: 'Enterprises prefer owning model weights and fine-tuning locally rather than sending proprietary data to closed cloud APIs.',
      whatItMeans: 'Engineers who know how to fine-tune, quantize, and host open models using Python and PyTorch are highly prized.',
      whatToWatch: ['Llama enterprise commercial adoption', 'CAPEX guidance for next-gen datacenter clusters', 'Edge AI integration in consumer hardware'],
      recommendations: [
        { action: 'Master PyTorch distributed training and model quantization techniques.', tag: 'Key Skill', skill: 'Python' },
        { action: 'Explore roles in open-source AI infrastructure.', tag: 'Career', role: 'Distributed Systems & PyTorch Engineer' }
      ]
    },
    competitors: [
      { name: 'Google', momentum: '+12.2%', diff: 'Proprietary Gemini ecosystem' },
      { name: 'OpenAI', momentum: '+32.5%', diff: 'Closed frontier API models' }
    ]
  },
  {
    id: 'tsmc',
    name: 'TSMC',
    logoInitials: 'TS',
    brandColor: '#D91F26',
    sector: 'Semiconductor Foundry',
    industry: 'Semiconductors & AI Hardware',
    size: 'Enterprise (76,000+)',
    headcount: '76,500+',
    location: 'Global',
    primaryLocation: 'Hsinchu & Arizona',
    marketMomentum: 72,
    technologyMomentum: 14.5,
    hiringMomentum: 8.4,
    investmentSignal: 19.8,
    change: 6.4,
    direction: 'up',
    signalText: 'Stable Growth',
    signalType: 'neutral',
    openRoles: 880,
    isFavorite: false,
    isMyCompany: false,
    history: [55, 58, 60, 62, 64, 65, 66],
    multiSignals: {
      market: [54, 57, 59, 62, 64, 66, 68],
      technology: [58, 62, 65, 68, 71, 73, 76],
      hiring: [48, 50, 52, 54, 56, 57, 59],
      investment: [56, 60, 65, 70, 74, 78, 82]
    },
    companySignals: [
      { name: '2nm (N2) Node Tooling & Production Ramping', type: 'Manufacturing Process', time: '1 week ago', impact: '+9.4%', dir: 'up', desc: 'Full capacity booked for next-generation mobile silicon and AI accelerators.' },
      { name: 'CoWoS Advanced Packaging Expansion', type: 'Packaging Capacity', time: '2 weeks ago', impact: '+12.6%', dir: 'up', desc: 'Doubling monthly advanced chip-on-wafer packaging capacity to relieve AI accelerator backlogs.' }
    ],
    technologies: [
      { name: 'Semiconductor Fabrication', trend: '+14.2%', adoption: 'Global Monopoly (Advanced Nodes)', roles: ['Lithography Engineer', 'Process Integration Lead'], skills: ['EUV Lithography', 'Yield Analytics'], skillLink: 'Cloud Computing' },
      { name: 'CoWoS Packaging', trend: '+28.4%', adoption: 'Critical AI Chokepoint', roles: ['Advanced Packaging Specialist'], skills: ['Silicon Interposer', 'Thermal Design'], skillLink: 'CUDA' }
    ],
    productSignals: [
      { title: 'N2 with Gate-All-Around (GAA) Nanosheet', date: 'Target 2026', status: 'Pilot Trials', note: 'Providing 15% speed improvement and 30% power reduction over 3nm.' }
    ],
    roles: [
      { title: 'Process Integration & Yield Analytics Engineer', momentum: '+9.2%', openCount: '280 open', location: 'Global / Taiwan / US', requiredSkills: ['Data Analytics', 'Python', 'Physics'], careerLink: true },
      { title: 'Advanced Packaging Systems Architect', momentum: '+16.5%', openCount: '190 open', location: 'Global / US', requiredSkills: ['Thermal Simulation', 'System Packaging'], careerLink: true }
    ],
    investments: [
      { focus: 'Global Fab Expansion (Arizona, Kumamoto, Dresden)', scale: '$32B CAPEX budget', signal: '+18.0% YoY', detail: 'Diversifying advanced fabrication hubs across North America, Japan, and Europe.' }
    ],
    evidence: [
      { source: 'TSMC Monthly Revenue Report', type: 'Public Filing', date: 'Aug 2026', verified: true, signal: '+33% YoY Monthly Revenue Surge', supports: 'Underscores unstoppable demand for advanced node wafers from Apple, NVIDIA, and AMD.' }
    ],
    aiInsight: {
      whatChanged: 'TSMC remains the indispensable physical manufacturing bottleneck for all advanced artificial intelligence and high-performance computing.',
      why: 'CoWoS advanced packaging capacity directly determines how many AI GPUs NVIDIA and hyperscalers can ship.',
      whatItMeans: 'Stable long-term momentum; companies dependent on TSMC supply must plan architectures years in advance.',
      whatToWatch: ['CoWoS monthly wafer output metrics', 'N2 node yield benchmarks', 'Geopolitical diversification progress'],
      recommendations: [
        { action: 'Understand semiconductor supply chain timing when evaluating hardware accelerator roadmap availability.', tag: 'Ecosystem Intel' }
      ]
    },
    competitors: [
      { name: 'Intel', momentum: '-4.2%', diff: 'Intel Foundry IFS restructuring' },
      { name: 'Samsung Foundry', momentum: '+3.1%', diff: 'GAA 3nm alternative foundry' }
    ]
  },
  {
    id: 'intel',
    name: 'Intel',
    logoInitials: 'IN',
    brandColor: '#0071C5',
    sector: 'Processor Systems & Silicon',
    industry: 'Semiconductors & AI Hardware',
    size: 'Enterprise (124,000+)',
    headcount: '124,000+',
    location: 'Global',
    primaryLocation: 'Oregon & Bangalore',
    marketMomentum: 54,
    technologyMomentum: 6.8,
    hiringMomentum: -4.2,
    investmentSignal: 12.0,
    change: -4.2,
    direction: 'down',
    signalText: 'Restructuring',
    signalType: 'decline',
    openRoles: 420,
    isFavorite: false,
    isMyCompany: false,
    history: [68, 65, 62, 60, 58, 56, 54],
    multiSignals: {
      market: [65, 62, 59, 57, 55, 54, 52],
      technology: [60, 58, 56, 55, 54, 53, 52],
      hiring: [52, 48, 44, 40, 37, 34, 31],
      investment: [58, 56, 54, 52, 50, 48, 46]
    },
    companySignals: [
      { name: 'Workforce Consolidation & Reorganization', type: 'Restructuring', time: '1 week ago', impact: '-6.5%', dir: 'down', desc: 'Streamlining business units to refocus capital on Intel 18A node execution.' },
      { name: 'Intel 18A Node Customer Tape-outs', type: 'Foundry Milestone', time: '2 weeks ago', impact: '+8.2%', dir: 'up', desc: 'First commercial external customer chips successfully taping out on RibbonFET process.' }
    ],
    technologies: [
      { name: 'x86 Systems Architecture', trend: '+4.2%', adoption: 'Legacy Enterprise Standard', roles: ['Systems Architect', 'Validation Lead'], skills: ['C++', 'Assembly', 'BIOS/UEFI'], skillLink: 'Python' },
      { name: 'Gaudi 3 AI Accelerators', trend: '+11.5%', adoption: 'Cost-Competitive AI Node', roles: ['Firmware Engineer', 'AI Platform Engineer'], skills: ['OpenVINO', 'PyTorch'], skillLink: 'CUDA' }
    ],
    productSignals: [
      { title: 'Intel Xeon 6 Granite Rapids Processors', date: 'Active', status: 'Server Rollout', note: 'Providing high core density and built-in AMX matrix acceleration for datacenter workloads.' }
    ],
    roles: [
      { title: 'Silicon Architecture Verification Engineer', momentum: '-2.4%', openCount: '160 open', location: 'Bangalore / Oregon', requiredSkills: ['SystemVerilog', 'UVM', 'Python'], careerLink: true },
      { title: 'OpenVINO Compiler Optimization Engineer', momentum: '+5.8%', openCount: '90 open', location: 'Bangalore / Remote', requiredSkills: ['C++', 'Python', 'Compiler Ops'], careerLink: true }
    ],
    investments: [
      { focus: 'US CHIPS Act Co-Funded Foundry Buildouts', scale: '$8.5B federal direct funding', signal: '+10.2%', detail: 'Direct non-dilutive government capital supporting Ohio and Oregon foundry developments.' }
    ],
    evidence: [
      { source: 'Intel Form 8-K Regulatory Filing', type: 'SEC Filing', date: 'Aug 2026', verified: true, signal: 'Cost Reduction Plan ($10B in 2025-2026)', supports: 'Confirms operational restructuring and targeted headcount reductions.' }
    ],
    aiInsight: {
      whatChanged: 'Intel is executing an aggressive turnaround plan, reducing operational costs while betting company future on 18A process commercialization.',
      why: 'Loss of datacenter market share to AMD and NVIDIA necessitated urgent capital reallocation towards leading-edge fabrication nodes.',
      whatItMeans: 'Hiring is conservative and highly targeted towards process verification and packaging, while generalist roles face hiring freezes.',
      whatToWatch: ['Intel 18A manufacturing yields in late 2026', 'Major foundry customer commitments', 'Gaudi 3 revenue run-rate'],
      recommendations: [
        { action: 'Focus applications on high-priority process validation and AI software integration teams.', tag: 'Strategic Targeting' }
      ]
    },
    competitors: [
      { name: 'AMD', momentum: '+14.2%', diff: 'Server market share gains with EPYC' },
      { name: 'TSMC', momentum: '+6.4%', diff: 'Foundry execution dominance' }
    ]
  },
  {
    id: 'snowflake',
    name: 'Snowflake',
    logoInitials: 'SN',
    brandColor: '#29B5E8',
    sector: 'Cloud Data Platform',
    industry: 'Cloud Data Platforms',
    size: 'Enterprise (7,200+)',
    headcount: '7,200+',
    location: 'Global',
    primaryLocation: 'San Mateo & Pune',
    marketMomentum: 74,
    technologyMomentum: 17.5,
    hiringMomentum: 11.8,
    investmentSignal: 14.2,
    change: 11.8,
    direction: 'up',
    signalText: 'Data Surge',
    signalType: 'positive',
    openRoles: 640,
    isFavorite: false,
    isMyCompany: false,
    history: [46, 52, 57, 63, 68, 71, 74],
    multiSignals: {
      market: [48, 54, 58, 64, 68, 71, 75],
      technology: [52, 58, 64, 70, 75, 78, 82],
      hiring: [38, 44, 50, 56, 61, 65, 70],
      investment: [45, 50, 55, 60, 65, 70, 74]
    },
    companySignals: [
      { name: 'Snowflake Cortex AI LLM Integration', type: 'Product Milestone', time: '3 days ago', impact: '+15.2%', dir: 'up', desc: 'Direct execution of LLM functions inside SQL data warehouse without data egress.' },
      { name: 'Iceberg Tables Universal Data Format', type: 'Open Data Standard', time: '1 week ago', impact: '+13.4%', dir: 'up', desc: 'Allowing enterprise customers to read Apache Iceberg storage with high performance.' }
    ],
    technologies: [
      { name: 'SQL', trend: '+14.5%', adoption: 'Core Query Engine', roles: ['Data Engineer', 'Analytics Engineer'], skills: ['SnowSQL', 'Window Functions', 'Query Profiling'], skillLink: 'SQL' },
      { name: 'Python', trend: '+18.2%', adoption: 'Snowpark Container Services', roles: ['Data Scientist', 'ML Engineer'], skills: ['Snowpark', 'DataFrames', 'FastAPI'], skillLink: 'Python' },
      { name: 'Cloud Computing', trend: '+12.4%', adoption: 'Multi-Cloud Architecture', roles: ['Cloud Data Architect'], skills: ['AWS', 'Azure', 'GCP Data Fabric'], skillLink: 'Cloud Computing' }
    ],
    productSignals: [
      { title: 'Snowflake Cortex Search & AI Functions', date: 'Active', status: 'High Adoption', note: 'Enabling enterprise vector search and sentiment extraction directly within SQL queries.' }
    ],
    roles: [
      { title: 'Senior Data Platform Engineer', momentum: '+15.6%', openCount: '210 open', location: 'Pune / Remote', requiredSkills: ['SQL', 'Python', 'Snowflake'], careerLink: true },
      { title: 'Cloud Infrastructure Data Architect', momentum: '+11.2%', openCount: '140 open', location: 'Global / US', requiredSkills: ['Cloud Computing', 'SQL', 'Kubernetes'], careerLink: true }
    ],
    investments: [
      { focus: 'Cortex AI Research & Data Clean Rooms', scale: '$450M R&D investment', signal: '+18.6% YoY', detail: 'Expanding enterprise data privacy, secure sharing, and native ML compute capabilities.' }
    ],
    evidence: [
      { source: 'Snowflake Q2 Financial Results', type: 'Public Earnings', date: 'Aug 2026', verified: true, signal: '+30% Product Revenue Growth ($829M)', supports: 'Demonstrates durable enterprise data lakehouse migration spend.' }
    ],
    aiInsight: {
      whatChanged: 'Snowflake has evolved from a pure data warehouse into an active AI application engine through Cortex AI and Snowpark.',
      why: 'Enterprises want to execute LLM inferences where their clean, governed customer data already lives.',
      whatItMeans: 'Engineers who combine SQL data modeling with Python machine learning are uniquely positioned for high-comp roles.',
      whatToWatch: ['Apache Iceberg adoption impact on storage margins', 'Cortex AI API call volumes', 'Databricks Lakehouse competition'],
      recommendations: [
        { action: 'Combine SQL query optimization with Python Snowpark capabilities.', tag: 'Skill Blend', skill: 'SQL' },
        { action: 'Review 210+ data platform engineering requisitions in Pune and Remote.', tag: 'Hiring Openings', role: 'Senior Data Platform Engineer' }
      ]
    },
    competitors: [
      { name: 'Databricks', momentum: '+18.4%', diff: 'Spark lakehouse & open source ML leadership' },
      { name: 'Google', momentum: '+12.2%', diff: 'BigQuery serverless analytics' }
    ]
  },
  {
    id: 'apple',
    name: 'Apple',
    logoInitials: 'AP',
    brandColor: '#A2AAAD',
    sector: 'On-Device AI & Hardware',
    industry: 'Consumer Technology & Silicon',
    size: 'Enterprise (161,000+)',
    headcount: '161,000+',
    location: 'Global',
    primaryLocation: 'Cupertino & Hyderabad',
    marketMomentum: 81,
    technologyMomentum: 19.4,
    hiringMomentum: 11.2,
    investmentSignal: 17.6,
    change: 11.2,
    direction: 'up',
    signalText: 'Private Cloud Compute',
    signalType: 'positive',
    openRoles: 1120,
    isFavorite: false,
    isMyCompany: false,
    history: [52, 58, 64, 69, 74, 78, 81],
    multiSignals: {
      market: [54, 59, 64, 69, 73, 77, 81],
      technology: [56, 61, 67, 72, 78, 82, 87],
      hiring: [42, 47, 52, 57, 62, 68, 73],
      investment: [50, 56, 62, 68, 74, 80, 85]
    },
    companySignals: [
      { name: 'Apple Intelligence On-Device Rollout', type: 'Product Ecosystem', time: '2 days ago', impact: '+14.6%', dir: 'up', desc: 'Deployment of 3B parameter on-device neural models integrated across iOS & macOS.' },
      { name: 'Private Cloud Compute Security Verification', type: 'Privacy Architecture', time: '1 week ago', impact: '+12.0%', dir: 'up', desc: 'Custom Apple Silicon server clusters verifying tamper-proof server-side AI execution.' }
    ],
    technologies: [
      { name: 'Python', trend: '+14.2%', adoption: 'Core Research & Model Training', roles: ['ML Engineer', 'Research Scientist'], skills: ['CoreML', 'PyTorch', 'Quantization'], skillLink: 'Python' },
      { name: 'Machine Learning', trend: '+20.5%', adoption: 'Neural Engine Acceleration', roles: ['On-Device ML Lead'], skills: ['Edge Optimization', 'Pruning', 'Metal'], skillLink: 'Machine Learning' },
      { name: 'Generative AI', trend: '+26.8%', adoption: 'Foundation Model Research', roles: ['Applied Researcher'], skills: ['Diffusion Models', 'On-Device LLMs'], skillLink: 'Generative AI' }
    ],
    productSignals: [
      { title: 'Apple Silicon M4 & A18 Pro Neural Engine', date: 'Active', status: 'Scale Production', note: 'Delivering up to 38 TOPS on-device neural processing with hardware ray tracing.' }
    ],
    roles: [
      { title: 'On-Device Machine Learning Engineer', momentum: '+18.4%', openCount: '240 open', location: 'Hyderabad / Cupertino', requiredSkills: ['Machine Learning', 'Python', 'C++'], careerLink: true },
      { title: 'Private Cloud Compute Systems Engineer', momentum: '+14.2%', openCount: '180 open', location: 'Global / Remote', requiredSkills: ['Cloud Computing', 'Security', 'Rust'], careerLink: true }
    ],
    investments: [
      { focus: 'M-Series Server Silicon & Data Privacy Infrastructure', scale: '$5.5B allocation', signal: '+21.4% YoY', detail: 'Constructing proprietary privacy-first datacenters built on custom M4 Max silicon.' }
    ],
    evidence: [
      { source: 'Apple Security Engineering Research Publication', type: 'Technical Paper', date: 'Jul 2026', verified: true, signal: 'Cryptographic Attestation for Cloud AI', supports: 'Validates industry-first end-to-end verifiable private cloud compute.' }
    ],
    aiInsight: {
      whatChanged: 'Apple is setting the privacy benchmark for consumer AI by combining on-device Neural Engines with Private Cloud Compute.',
      why: 'Users and enterprise clients demand AI capabilities without relinquishing data rights to third-party model hosts.',
      whatItMeans: 'Surging demand for engineers skilled in on-device quantization, edge acceleration, and compact model pruning.',
      whatToWatch: ['Apple Intelligence global localization timeline', 'Private Cloud Compute developer audit reports', 'Siri multi-app action reliability'],
      recommendations: [
        { action: 'Learn model quantization and low-power inference acceleration.', tag: 'Edge AI Skill', skill: 'Machine Learning' },
        { action: 'Explore 240+ on-device machine learning openings across Hyderabad and Global hubs.', tag: 'Role Fit', role: 'On-Device Machine Learning Engineer' }
      ]
    },
    competitors: [
      { name: 'Google', momentum: '+12.2%', diff: 'Android on-device Gemini Nano' },
      { name: 'Microsoft', momentum: '+14.8%', diff: 'Copilot+ PC ecosystem' }
    ]
  }
];

// Preserves backward compatibility: provides old companies array format
export const marketIntelligenceData = {
  signals: {
    investment: [48, 54, 60, 68, 74, 80, 86],
    technology: [52, 58, 64, 72, 78, 85, 92],
    hiring: [40, 46, 52, 60, 66, 72, 78]
  },
  companies: dedicatedMarketCompanies.map(c => ({
    name: c.name,
    sector: c.sector,
    logoInitials: c.logoInitials,
    signalText: c.signalText,
    signalType: c.signalType,
    change: c.change,
    openRoles: c.openRoles,
    direction: c.direction,
    isFavorite: c.isFavorite,
    history: c.history
  }))
};

// ============================================================================
// HELPER FUNCTIONS FOR MARKET INTELLIGENCE
// ============================================================================

export function getCompaniesForScope(scope = 'All Companies', favorites = [], saved = []) {
  if (scope === 'Favorite Companies') {
    return dedicatedMarketCompanies.filter(c => favorites.includes(c.name) || c.isFavorite);
  }
  if (scope === 'My Companies') {
    return dedicatedMarketCompanies.filter(c => saved.includes(c.name) || c.isMyCompany);
  }
  return dedicatedMarketCompanies;
}

export function getCompanyMarketDetails(companyName = 'NVIDIA', location = 'Global', timeRange = '30D') {
  const normalized = (companyName || '').toLowerCase().trim();
  const company = dedicatedMarketCompanies.find(c => c.name.toLowerCase() === normalized || c.id === normalized) || dedicatedMarketCompanies[0];
  
  // Adjust metrics based on time range and location multipliers for dynamic fidelity
  const locMultipliers = {
    Global: 1.0, India: 1.04, 'Tamil Nadu': 0.98, Bangalore: 1.06, Chennai: 0.96, Hyderabad: 1.02, Pune: 0.95, Remote: 1.01
  };
  const rangeMultipliers = {
    '7 Days': 0.45, '7D': 0.45, '30 Days': 1.0, '30D': 1.0, '3 Months': 1.35, '3M': 1.35, '6 Months': 1.8, '6M': 1.8
  };
  
  const locFactor = locMultipliers[location] || 1.0;
  const rangeFactor = rangeMultipliers[timeRange] || 1.0;
  
  const adjustedChange = Number((company.change * (company.direction === 'down' ? -1 : 1) * locFactor * (rangeFactor > 1 ? 1 + (rangeFactor - 1) * 0.3 : rangeFactor)).toFixed(1));
  const adjustedRoles = Math.round(company.openRoles * locFactor);
  
  return {
    ...company,
    adjustedChange,
    adjustedRoles,
    currentLocation: location,
    currentTimeRange: timeRange
  };
}

export function searchCompanies(query = '', scope = 'All Companies', favorites = [], saved = []) {
  const base = getCompaniesForScope(scope, favorites, saved);
  const q = query.toLowerCase().trim();
  if (!q) return base;
  return base.filter(c => 
    c.name.toLowerCase().includes(q) ||
    c.sector.toLowerCase().includes(q) ||
    c.industry.toLowerCase().includes(q) ||
    (c.technologies || []).some(t => t.name.toLowerCase().includes(q))
  );
}

export function getRelatedCompanySignals(companyName = 'NVIDIA') {
  const normalized = (companyName || '').toLowerCase().trim();
  const selected = dedicatedMarketCompanies.find(c => c.name.toLowerCase() === normalized || c.id === normalized) || dedicatedMarketCompanies[0];
  
  // Return competitors or top movers related to the company
  const others = dedicatedMarketCompanies
    .filter(c => c.name !== selected.name)
    .slice(0, 4)
    .map(c => ({
      name: c.name,
      logoInitials: c.logoInitials,
      brandColor: c.brandColor,
      sector: c.sector,
      signalText: c.signalText,
      signalType: c.signalType,
      change: c.change,
      direction: c.direction,
      momentum: c.marketMomentum
    }));
  return others;
}
