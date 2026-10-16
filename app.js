const jobMarketData = {
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

function renderJobDonutSVG(segments) {
  // SVG donut generator
  const radius = 65;
  const circumference = 2 * Math.PI * radius; // ~408.4
  let accumPercent = 0;

  return `
    <svg viewBox="0 0 160 160" style="width:160px; height:160px; transform: rotate(-90deg);">
      <circle cx="80" cy="80" r="${radius}" fill="none" stroke="#E8DDF0" stroke-width="14" />
      ${segments.map(s => {
        const strokeDasharray = `${(s.percent / 100) * circumference} ${circumference}`;
        const strokeDashoffset = -((accumPercent / 100) * circumference);
        accumPercent += s.percent;
        return `
          <circle class="job-donut-segment${(intelligenceExplorerState.selectedJobSegment || 'roles') === s.id ? ' is-selected' : ''}" data-job-segment="${s.id}" cx="80" cy="80" r="${radius}" fill="none" stroke="${s.color}" stroke-width="14"
                  stroke-dasharray="${strokeDasharray}" stroke-dashoffset="${strokeDashoffset}" stroke-linecap="round" />
        `;
      }).join('')}
    </svg>
  `;
}

const marketFilterOptions = {
  companies: ['All Companies', 'Favorite Companies'],
  locations: ['Global', 'India', 'Tamil Nadu', 'Chennai', 'Bangalore', 'Hyderabad', 'Pune', 'Remote'],
  times: ['7 Days', '30 Days', '90 Days', '6 Months', '1 Year'],
  dates: ['Day', 'Month', 'Year', 'Custom Range']
};

const marketIntelligenceData = {
  signals: {
    investment: [48, 54, 60, 68, 74, 80, 86],
    technology: [52, 58, 64, 72, 78, 85, 92],
    hiring: [40, 46, 52, 60, 66, 72, 78]
  },
  companies: [
    {
      id: 'nvidia',
      name: 'NVIDIA',
      sector: 'AI Hardware & CUDA',
      logoInitials: 'NV',
      signalText: 'Hiring Surge',
      signalType: 'positive',
      change: 28.4,
      openRoles: 1820,
      direction: 'up',
      isFavorite: true,
      history: [35, 48, 60, 72, 85, 94, 98]
    },
    {
      id: 'openai',
      name: 'OpenAI',
      sector: 'Generative Models',
      logoInitials: 'AI',
      signalText: 'High Investment',
      signalType: 'positive',
      change: 32.5,
      openRoles: 940,
      direction: 'up',
      isFavorite: true,
      history: [25, 40, 58, 70, 82, 90, 96]
    },
    {
      id: 'amazon',
      name: 'Amazon',
      sector: 'Cloud Infrastructure & AWS',
      logoInitials: 'AMZ',
      signalText: 'Cloud Expansion',
      signalType: 'positive',
      change: 18.2,
      openRoles: 2100,
      direction: 'up',
      isFavorite: true,
      history: [40, 48, 54, 62, 70, 76, 82]
    },
    {
      id: 'microsoft',
      name: 'Microsoft',
      sector: 'Enterprise Cloud & Copilot',
      logoInitials: 'MS',
      signalText: 'High Investment',
      signalType: 'positive',
      change: 14.8,
      openRoles: 2480,
      direction: 'up',
      isFavorite: true,
      history: [44, 50, 58, 64, 72, 78, 85]
    },
    {
      id: 'google',
      name: 'Google',
      sector: 'Cloud & AI Infrastructure',
      logoInitials: 'GO',
      signalText: 'AI R&D Expansion',
      signalType: 'positive',
      change: 12.2,
      openRoles: 1680,
      direction: 'up',
      isFavorite: true,
      history: [50, 56, 62, 68, 74, 78, 82]
    },
    {
      id: 'apple',
      name: 'Apple',
      sector: 'Devices & Neural Engines',
      logoInitials: 'AAPL',
      signalText: 'Silicon R&D',
      signalType: 'neutral',
      change: 8.5,
      openRoles: 920,
      direction: 'up',
      isFavorite: false,
      history: [52, 54, 57, 60, 63, 66, 68]
    },
    {
      id: 'tsmc',
      name: 'TSMC',
      sector: 'Semiconductor Foundry',
      logoInitials: 'TS',
      signalText: 'Stable Growth',
      signalType: 'neutral',
      change: 6.4,
      openRoles: 880,
      direction: 'up',
      isFavorite: false,
      history: [55, 58, 60, 62, 64, 65, 66]
    },
    {
      id: 'intel',
      name: 'Intel',
      sector: 'Processor Systems',
      logoInitials: 'IN',
      signalText: 'Restructuring',
      signalType: 'decline',
      change: -4.2,
      openRoles: 420,
      direction: 'down',
      isFavorite: false,
      history: [68, 65, 62, 60, 58, 56, 54]
    }
  ]
};

function getMarketDateLabels(marketTime, marketDate) {
  if (marketDate === 'Day' || marketTime === '7 Days') return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  if (marketTime === '30 Days') return ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4'];
  if (marketTime === '90 Days') return ['M1', 'M2', 'M3'];
  if (marketDate === 'Year' || marketTime === '1 Year') return ['Q1', 'Q2', 'Q3', 'Q4'];
  return ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'];
}

function renderMultiLineMarketChart(signals, marketTime, marketDate) {
  const dates = getMarketDateLabels(marketTime, marketDate);
  const getPoints = (arr) => arr.map((val, idx) => {
    const x = 38 + (idx / (arr.length - 1)) * 440;
    const y = 190 - (val / 100) * 150;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const invPoints = getPoints(signals.investment);
  const techPoints = getPoints(signals.technology);
  const hirPoints = getPoints(signals.hiring);

  const lastInv = signals.investment[signals.investment.length - 1];
  const lastTech = signals.technology[signals.technology.length - 1];
  const lastHir = signals.hiring[signals.hiring.length - 1];

  const lastX = 38 + 440;
  const invY = 190 - (lastInv / 100) * 150;
  const techY = 190 - (lastTech / 100) * 150;
  const hirY = 190 - (lastHir / 100) * 150;

  return `
    <div class="market-terminal-chart-wrap">
      <svg id="marketMultiSignalChart" viewBox="0 0 520 225" preserveAspectRatio="none" role="img" aria-label="Market intelligence multi-signal telemetry chart">
        <!-- Terminal Grid Reference Lines -->
        <line x1="38" y1="40" x2="478" y2="40" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="38" y1="90" x2="478" y2="90" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="38" y1="140" x2="478" y2="140" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="38" y1="190" x2="478" y2="190" stroke="#E2D6EC" stroke-width="1" />

        <!-- Reference Y Ticks -->
        <text x="8" y="44" fill="#9C8DA8" font-size="9" font-family="monospace">100%</text>
        <text x="14" y="94" fill="#9C8DA8" font-size="9" font-family="monospace">75%</text>
        <text x="14" y="144" fill="#9C8DA8" font-size="9" font-family="monospace">50%</text>
        <text x="14" y="194" fill="#9C8DA8" font-size="9" font-family="monospace">25%</text>

        <!-- Category 1: Company Financial / Investment Signals (Purple) -->
        <polyline class="market-signal-line" data-market-signal="investment" points="${invPoints}" fill="none" stroke="#8B3DFF" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" />
        <circle class="market-signal-node" data-market-node="investment" cx="${lastX.toFixed(1)}" cy="${invY.toFixed(1)}" r="4.5" fill="#8B3DFF" stroke="#FFFFFF" stroke-width="2" />

        <!-- Category 2: Market / Technology / Location Signals (Green) -->
        <polyline class="market-signal-line" data-market-signal="technology" points="${techPoints}" fill="none" stroke="#10B981" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
        <circle class="market-signal-node" data-market-node="technology" cx="${lastX.toFixed(1)}" cy="${techY.toFixed(1)}" r="4.5" fill="#10B981" stroke="#FFFFFF" stroke-width="2" />

        <!-- Category 3: Job Market Signals (Orange) -->
        <polyline class="market-signal-line" data-market-signal="hiring" points="${hirPoints}" fill="none" stroke="#F59E0B" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
        <circle class="market-signal-node" data-market-node="hiring" cx="${lastX.toFixed(1)}" cy="${hirY.toFixed(1)}" r="4.5" fill="#F59E0B" stroke="#FFFFFF" stroke-width="2" />
      </svg>
    </div>
    <div style="display:flex; justify-content:space-between; padding:0 38px; margin-top:6px; font-size:10px; color:#8A7A97;">
      ${dates.map(d => `<span>${d}</span>`).join('')}
    </div>
  `;
}

const skillFilterOptions = {
  collections: ['My Skills', 'Favorite Skills', 'All Skills'],
  locations: ['Global', 'India', 'Tamil Nadu', 'Chennai', 'Bangalore', 'Hyderabad', 'Pune', 'Remote'],
  times: ['7 Days', '30 Days', '90 Days', '6 Months', '1 Year'],
  dates: ['Day', 'Month', 'Year', 'Custom Range']
};

const skillMarketData = [
  {
    id: 'ml',
    name: 'Machine Learning',
    category: 'AI & Data',
    growth: 22.0,
    direction: 'up',
    isMySkill: true,
    isFavorite: true,
    values: [42, 50, 58, 66, 74, 80, 86],
    adjacentSkills: ['Python', 'Deep Learning', 'PyTorch', 'CUDA', 'SQL']
  },
  {
    id: 'python',
    name: 'Python',
    category: 'Programming',
    growth: 18.4,
    direction: 'up',
    isMySkill: true,
    isFavorite: true,
    values: [50, 58, 64, 72, 78, 85, 92],
    adjacentSkills: ['FastAPI', 'Django', 'SQL', 'Machine Learning', 'PyTorch']
  },
  {
    id: 'cloud',
    name: 'Cloud Computing',
    category: 'Infrastructure',
    growth: 16.7,
    direction: 'up',
    isMySkill: true,
    isFavorite: true,
    values: [45, 52, 58, 64, 70, 74, 78],
    adjacentSkills: ['AWS', 'Docker', 'Kubernetes', 'Terraform', 'SQL']
  },
  {
    id: 'cyber',
    name: 'Cybersecurity',
    category: 'Security',
    growth: 12.1,
    direction: 'up',
    isMySkill: false,
    isFavorite: false,
    values: [55, 58, 62, 65, 68, 70, 73],
    adjacentSkills: ['Network Security', 'SIEM', 'Ethical Hacking', 'Cryptography']
  },
  {
    id: 'sql',
    name: 'SQL',
    category: 'Database',
    growth: 9.8,
    direction: 'up',
    isMySkill: true,
    isFavorite: false,
    values: [40, 44, 48, 52, 55, 58, 60],
    adjacentSkills: ['PostgreSQL', 'Snowflake', 'Database Optimization', 'Python', 'Cloud Computing']
  },
  {
    id: 'react',
    name: 'React',
    category: 'Frontend',
    growth: 9.2,
    direction: 'up',
    isMySkill: true,
    isFavorite: true,
    values: [52, 56, 60, 65, 69, 72, 75],
    adjacentSkills: ['TypeScript', 'Next.js', 'Redux', 'Tailwind', 'Python']
  },
  {
    id: 'genai',
    name: 'Generative AI',
    category: 'AI & Data',
    growth: 8.8,
    direction: 'up',
    isMySkill: false,
    isFavorite: true,
    values: [30, 42, 55, 68, 79, 88, 94],
    adjacentSkills: ['LLMs', 'Prompt Engineering', 'LangChain', 'RAG', 'Python']
  },
  {
    id: 'cuda',
    name: 'CUDA',
    category: 'GPU Systems',
    growth: 7.5,
    direction: 'up',
    isMySkill: false,
    isFavorite: false,
    values: [28, 38, 48, 62, 75, 84, 91],
    adjacentSkills: ['C++', 'GPU Acceleration', 'Parallel Computing', 'PyTorch']
  },
  {
    id: 'java',
    name: 'Java',
    category: 'Backend',
    growth: 6.2,
    direction: 'up',
    isMySkill: false,
    isFavorite: false,
    values: [60, 61, 62, 63, 64, 65, 66],
    adjacentSkills: ['Spring Boot', 'Kotlin', 'Microservices', 'SQL']
  },
  {
    id: 'legacy',
    name: 'Legacy IT',
    category: 'Legacy Systems',
    growth: -4.5,
    direction: 'down',
    isMySkill: false,
    isFavorite: false,
    values: [78, 75, 71, 68, 65, 61, 56],
    adjacentSkills: ['System Administration', 'COBOL', 'Maintenance', 'SQL']
  }
];

const overviewData = {
  skill: {
    domain: 'SKILL',
    name: 'Machine Learning',
    change: 22.4,
    direction: 'up',
    status: 'Demo signal',
    chartPoints: [42, 50, 58, 66, 74, 80, 86]
  },
  market: {
    domain: 'MARKET',
    company: 'NVIDIA',
    change: 28.4,
    direction: 'up',
    status: 'Market signal',
    chartPoints: [35, 48, 60, 72, 85, 94, 98]
  },
  jobs: {
    domain: 'JOBS',
    role: 'AI Engineer',
    openRoles: 2480,
    change: 18.2,
    status: 'Hiring active',
    bars: [45, 60, 75, 50, 85, 90, 95]
  },
  roadmap: {
    domain: 'ROADMAP',
    active: true,
    title: 'Python — Backend Development',
    progress: 64,
    status: 'Active',
    currentStep: 'Assessment'
  }
};

function renderSkillMiniChart(points, direction) {
  const strokeColor = direction === 'down' ? '#E05252' : '#19B77A';
  const fillColor = direction === 'down' ? 'rgba(224, 82, 82, 0.11)' : 'rgba(25, 183, 122, 0.11)';
  const maxVal = Math.max(...points, 100);
  const minVal = Math.min(...points, 0);
  const range = (maxVal - minVal) || 1;
  
  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * 140;
    const y = 32 - ((val - minVal) / range) * 24;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const polyPoints = `0,36 ${coords} 140,36`;

  return `
    <svg viewBox="0 0 140 36" class="overview-mini-chart overview-mini-chart--skill" preserveAspectRatio="none" role="img" aria-label="Skill trend sparkline">
      <polygon points="${polyPoints}" fill="${fillColor}" />
      <polyline points="${coords}" fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `;
}

function renderMarketMiniChart(points, direction) {
  const strokeColor = direction === 'down' ? '#E05252' : '#19B77A';
  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * 140;
    const y = 32 - (Math.max(0, Math.min(100, val)) * .24);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const finalPoint = coords.split(' ').at(-1).split(',');

  return `
    <svg viewBox="0 0 140 36" class="overview-mini-chart overview-mini-chart--market" preserveAspectRatio="none" role="img" aria-label="Market movement line chart">
      <line x1="0" y1="34" x2="140" y2="34" class="overview-market-baseline" />
      <polyline points="${coords}" fill="none" stroke="${strokeColor}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="${finalPoint[0]}" cy="${finalPoint[1]}" r="3.2" fill="${strokeColor}" class="overview-market-endpoint" />
    </svg>
  `;
}

function renderJobsMiniBars(bars, direction = 'up') {
  const maxVal = Math.max(...bars, 100);
  return `
    <div class="mini-bar-chart ${direction === 'down' ? 'is-negative' : 'is-positive'}" role="img" aria-label="Hiring movement bars">
      ${bars.map(val => {
        const height = Math.max(15, (val / maxVal) * 100);
        return `<div class="mini-bar-item" style="height: ${height.toFixed(1)}%;"></div>`;
      }).join('')}
    </div>
  `;
}

function renderRoadmapMiniProgress(active, progress) {
  if (!active) {
    return `
      <div class="mini-roadmap-progress">
        <div class="mini-progress-bar-track" role="progressbar" aria-label="Roadmap progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <div class="mini-progress-bar-fill" style="width: 0%;"></div>
        </div>
        <div class="mini-progress-labels">
          <span>Roadmap progress</span>
          <strong>0%</strong>
        </div>
      </div>
    `;
  }
  return `
    <div class="mini-roadmap-progress">
      <div class="mini-progress-bar-track" role="progressbar" aria-label="Roadmap progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
        <div class="mini-progress-bar-fill" style="width: ${progress}%;"></div>
      </div>
      <div class="mini-progress-labels">
        <span>Roadmap progress</span>
        <strong>${progress}%</strong>
      </div>
    </div>
  `;
}

const locationDataOptions = [
  { group: 'Global', items: [{ id: 'Global', label: 'Global Scope', country: 'Global' }] },
  { group: 'India', items: [
      { id: 'Bangalore, India', label: 'Bangalore, India', country: 'India' },
      { id: 'Mumbai, India', label: 'Mumbai, India', country: 'India' },
      { id: 'Delhi NCR, India', label: 'Delhi NCR, India', country: 'India' }
    ]
  },
  { group: 'United States', items: [
      { id: 'San Francisco, US', label: 'San Francisco, US', country: 'United States' },
      { id: 'New York, US', label: 'New York, US', country: 'United States' },
      { id: 'Austin, US', label: 'Austin, US', country: 'United States' }
    ]
  },
  { group: 'United Kingdom', items: [
      { id: 'London, UK', label: 'London, UK', country: 'United Kingdom' }
    ]
  },
  { group: 'Europe', items: [
      { id: 'Berlin, Germany', label: 'Berlin, Germany', country: 'Germany' },
      { id: 'Munich, Germany', label: 'Munich, Germany', country: 'Germany' }
    ]
  },
  { group: 'Asia Pacific', items: [
      { id: 'Singapore', label: 'Singapore', country: 'Singapore' },
      { id: 'Tokyo, Japan', label: 'Tokyo, Japan', country: 'Japan' }
    ]
  }
];

const user = {
  name: 'Arun Sharma',
  shortName: 'Arun',
  initials: 'AS',
  role: 'AI/ML',
  location: 'India',
  industry: 'Technology'
};

const navigation = [
  { label: 'Main', items: [
    { label: 'Home', icon: 'house', route: '/individual/home' },
    { label: 'My Skills', icon: 'layers-3', route: '/individual/skills' },
    { label: 'Learning', icon: 'book-open', route: '/individual/learning' },
    { label: 'Career', icon: 'briefcase-business', route: '/individual/career' },
    { label: 'Community', icon: 'users-round', route: '/individual/community' }
  ] },
  { label: 'Explore', items: [
    { label: 'Market Insights', icon: 'chart-no-axes-combined', route: '/individual/market-insights' },
    { label: 'Opportunities', icon: 'compass', route: '/individual/opportunities' }
  ] },
  { label: 'Workspace', items: [
    { label: 'AI Assistant', icon: 'sparkles', route: '/individual/ai-assistant' },
    { label: 'Saved', icon: 'bookmark', route: '/individual/saved' }
  ] }
];

const routes = {
  '/individual/home': { eyebrow: 'Individual / Home', title: 'Good morning, Arun', description: 'Stay ahead of the skills, technologies and opportunities shaping your career.', icon: 'sunrise' },
  '/individual/skills': { eyebrow: 'Main', title: 'My Skills', description: 'Build a clear picture of your strengths and the capabilities you want to grow.', icon: 'layers-3' },
  '/individual/learning': { eyebrow: 'Main', title: 'Learning', description: 'Keep your development focused with a learning path shaped around your goals.', icon: 'book-open' },
  '/individual/career': { eyebrow: 'Main', title: 'Career', description: 'Bring your next career move into focus with signals from the skills market.', icon: 'briefcase-business' },
  '/individual/community': { eyebrow: 'Main', title: 'Community', description: 'Connect with people who are building what comes next.', icon: 'users-round' },
  '/individual/market-insights': { eyebrow: 'Explore', title: 'Market Insights', description: 'See where demand is moving across roles, skills, and industries.', icon: 'chart-no-axes-combined' },
  '/individual/opportunities': { eyebrow: 'Explore', title: 'Opportunities', description: 'Discover roles and experiences matched to your evolving skill profile.', icon: 'compass' },
  '/individual/ai-assistant': { eyebrow: 'Workspace', title: 'AI Assistant', description: 'A focused space for turning workforce signals into your next best action.', icon: 'sparkles' },
  '/individual/saved': { eyebrow: 'Workspace', title: 'Saved', description: 'Keep the roles, insights, and learning resources you want close at hand.', icon: 'bookmark' },
  '/individual/profile': { eyebrow: 'Account', title: 'Profile', description: 'Your profile is the foundation for relevant recommendations and opportunities.', icon: 'user-round' },
  '/individual/settings': { eyebrow: 'Account', title: 'Settings', description: 'Manage your portal preferences and notification choices.', icon: 'settings-2' }
};

const skillOptions = ['Python', 'Java', 'JavaScript', 'TypeScript', 'SQL', 'React', 'Node.js', 'Cloud Computing', 'Machine Learning', 'Generative AI', 'AI', 'Cybersecurity', 'Data Analytics'];
const marketOptions = ['Global', 'India', 'United States', 'United Kingdom', 'Germany', 'Canada', 'Australia', 'Singapore', 'Japan'];
const timeRangeOptions = ['7 Days', '30 Days', '90 Days', '6 Months', '1 Year'];

const marketTrends = [
  { label: 'Economic movement', value: 68, direction: 'Growing', icon: 'trending-up' },
  { label: 'Investment signals', value: 54, direction: 'Stable', icon: 'landmark' },
  { label: 'Demand movement', value: 76, direction: 'Accelerating', icon: 'activity' }
];
const technologyTrends = [
  { label: 'AI', value: 82, direction: 'Accelerating' },
  { label: 'Cloud', value: 68, direction: 'Growing' },
  { label: 'Generative AI', value: 91, direction: 'Accelerating' },
  { label: 'Automation', value: 64, direction: 'Growing' },
  { label: 'Cybersecurity', value: 58, direction: 'Stable' },
  { label: 'Developer Tools', value: 72, direction: 'Growing' }
];
const industryTrends = [
  { label: 'Technology adoption', value: 74, direction: 'Growing' },
  { label: 'Automation', value: 62, direction: 'Stable' },
  { label: 'Skill demand', value: 79, direction: 'Accelerating' },
  { label: 'Role changes', value: 48, direction: 'Growing' },
  { label: 'Industry momentum', value: 71, direction: 'Growing' }
];
const jobMarketTrends = [
  { label: 'Software Engineer', value: 78, direction: 'Growing' },
  { label: 'AI Engineer', value: 88, direction: 'Accelerating' },
  { label: 'Data Analyst', value: 61, direction: 'Stable' },
  { label: 'Cloud Engineer', value: 73, direction: 'Growing' }
];
const marketSignalData = {
  Global: { company: 'Microsoft', value: 12 },
  India: { company: 'TCS', value: 15 },
  'United States': { company: 'NVIDIA', value: 18 },
  'United Kingdom': { company: 'Google', value: 10 },
  Germany: { company: 'SAP', value: 9 },
  Canada: { company: 'Shopify', value: 14 },
  Australia: { company: 'Atlassian', value: 11 },
  Singapore: { company: 'Grab', value: 13 },
  Japan: { company: 'Sony', value: 8 }
};
const companyVacancies = { Microsoft: 2480, TCS: 1940, NVIDIA: 1320, Google: 1680, SAP: 1120, Shopify: 760, Atlassian: 540, Grab: 430, Sony: 880 };
const futureSkills = [
  { label: 'Generative AI', status: 'Emerging', direction: 'up', icon: 'sparkles' },
  { label: 'AI Agents', status: 'Growing', direction: 'up', icon: 'bot' },
  { label: 'Cloud Computing', status: 'Accelerating', direction: 'up', icon: 'cloud' },
  { label: 'Cybersecurity', status: 'Stable', direction: 'steady', icon: 'shield-check' },
  { label: 'Data Engineering', status: 'Growing', direction: 'up', icon: 'database' }
];
const skillTrendData = {
  Python: [48, 54, 51, 62, 68, 74, 79],
  Java: [58, 56, 61, 59, 64, 67, 69],
  JavaScript: [52, 60, 57, 66, 71, 73, 78],
  React: [44, 48, 52, 58, 63, 70, 75],
  SQL: [61, 60, 65, 67, 70, 72, 76],
  'Cloud Computing': [42, 49, 55, 63, 67, 75, 84],
  'Machine Learning': [39, 46, 53, 61, 69, 77, 86],
  'Generative AI': [28, 36, 48, 57, 69, 82, 94],
  Cybersecurity: [54, 57, 56, 63, 66, 71, 76],
  'Data Analytics': [51, 55, 60, 64, 69, 73, 78],
  'AI Agents': [24, 31, 43, 54, 65, 78, 91]
};
const contextSkillTrendData = Object.fromEntries(skillOptions.map((skill, skillIndex) => {
  const seed = skillTrendData[skill] || [42, 48, 51, 57, 63, 69, 74];
  return [skill, Object.fromEntries(marketOptions.map((market, marketIndex) => [market, Object.fromEntries(timeRangeOptions.map((range, rangeIndex) => {
    const shift = (marketIndex % 3) * 2 + rangeIndex;
    return [range, seed.map((value, index) => Math.max(20, Math.min(96, value + shift + ((skillIndex + index) % 3) - 1)))];
  }))]))];
}));

const savedSkillState = JSON.parse(localStorage.getItem('talentscope-saved-skills') || '[]');
const skillTrendFilterState = { startDate: '', endDate: '' };
const dashboardState = {
  market: 'Global',
  skillScope: 'All Skills',
  skillLocation: 'Bangalore',
  skillTime: '6 Months',
  skillDate: 'Month',
  isSkillFilterOpen: false,
  marketCompanyScope: 'All Companies',
  marketLocation: 'Bangalore',
  marketTime: '6 Months',
  marketDate: 'Month',
  isMarketFilterOpen: false,
  selectedMarketCompany: 'NVIDIA',
  trendScope: 'Overall Live Trends',
  trendSort: 'Highest Growth',
  timeRange: '6 Months',
  selectedSkill: savedSkillState[0] || 'Machine Learning',
  savedSkills: savedSkillState,
  savedCompanies: JSON.parse(localStorage.getItem('talentscope-saved-companies') || '["Microsoft"]')
};
let liveTrendTick = 0;
const marketTrendState = { scope: 'Global', timeRange: '30 Days', year: '2026', category: 'All Markets', watchlist: 'All Companies', company: '', view: 'Market Overview', customStartDate: '', customEndDate: '' };
const jobTrendState = { period: '6 Months', market: 'Global', category: 'All Jobs', role: 'All Roles', roleScope: 'All Roles' };
const jobRoleOptions = ['Software Engineer', 'AI / ML Engineer', 'AI Engineer', 'Data Scientist', 'Data Analyst', 'UI/UX Designer', 'Cybersecurity Engineer', 'Cloud Engineer'];
let savedJobRoles = JSON.parse(localStorage.getItem('talentscope-saved-roles') || '["Software Engineer","AI Engineer","Data Scientist"]');
let savedMarkets = JSON.parse(localStorage.getItem('talentscope-saved-markets') || '[]');
const intelligenceExplorerState = { domainSelected: false, type: 'skills', scope: 'Global', skillScope: 'My Skills', market: 'Bangalore, India', companyScope: 'My/Favorite Companies', jobScope: 'Regional market', timeRange: '6 Months', selectedCompanies: [], companySignals: ['Technology', 'Investment', 'Jobs'], jobSignals: ['Vacancies', 'Hiring', 'Roles', 'Skills'], favoriteCompanies: JSON.parse(localStorage.getItem('talentscope-favorite-companies') || 'null') || ['NVIDIA', 'Microsoft', 'Google', 'Amazon'], selectedSkills: [], favoriteSkills: JSON.parse(localStorage.getItem('talentscope-favorite-skills') || 'null') || ['Python', 'Machine Learning', 'React', 'AWS'], selected: { skills: 'Machine Learning', companies: 'Microsoft', roles: 'AI Engineer' }, question: '', showWhy: false, hasSearched: false, isAnalyzing: false, analysisStep: 0, isRoadmapPreviewing: false };
const homeJobIntelligenceState = {
  companyScope: 'favorites',
  company: 'NVIDIA',
  region: 'Bangalore',
  role: 'AI/ML',
  period: '6 Months',
  selectedSignal: 'roles'
};
const roadmapStorageKey = 'talentscope-learning-roadmap-v1';
const roadmapStageTemplate = [
  { name: 'Foundations', topic: 'Python for ML', status: 'completed', progress: 100, estimate: '3 — 4 hours', completed: true },
  { name: 'Core Concepts', topic: 'Data Preprocessing', status: 'in-progress', progress: 72, estimate: '5 — 6 hours', completed: false },
  { name: 'Applied Practice', topic: 'Model Training', status: 'not-started', progress: 0, estimate: '4 — 5 hours', completed: false },
  { name: 'Project', topic: 'ML Project', status: 'locked', progress: 0, estimate: '1 — 2 weeks', completed: false },
  { name: 'Assessment', topic: 'Skill Assessment', status: 'not-started', progress: 0, estimate: '1 hour', completed: false },
  { name: 'Interview Preparation', topic: 'Interview Practice', status: 'not-started', progress: 0, estimate: '3 — 4 hours', completed: false }
];
const roadmapActivityTypes = [
  { id: 'learning', label: 'Learning', score: false },
  { id: 'practice', label: 'Practice', score: false },
  { id: 'project', label: 'Project', score: false },
  { id: 'assessment', label: 'Assessment', score: true },
  { id: 'interview', label: 'Interview', score: true }
];
const defaultRoadmapTemplates = {
  'Improve Current Skill': [
    { name: 'Core Foundations', label: 'Advanced Architecture Review', status: 'completed' },
    { name: 'Specialized Concepts', label: 'Async & Concurrency Deep Dive', status: 'completed' },
    { name: 'Assessment', label: 'Technical Proficiency Benchmark', status: 'current' },
    { name: 'Real-world Project', label: 'High-Throughput Optimization Build', status: 'upcoming' },
    { name: 'Role Alignment', label: 'Capability & Benchmark Verification', status: 'upcoming' }
  ],
  'Skill Switch': [
    { name: 'Current Skills', label: 'Baseline Review & Diagnostic', status: 'completed' },
    { name: 'Transferable Skills', label: 'Cross-Domain Mapping', status: 'completed' },
    { name: 'Gap Acquisition', label: 'Core Delta Acquisition', status: 'current' },
    { name: 'Transition Labs', label: 'Hands-on Applied Labs', status: 'upcoming' },
    { name: 'Assessment', label: 'Transition Readiness Assessment', status: 'upcoming' },
    { name: 'Capstone Project', label: 'Portfolio Conversion Build', status: 'upcoming' }
  ],
  'Career Preparation': [
    { name: 'Role Diagnostics', label: 'Target Career Baseline', status: 'completed' },
    { name: 'Core Foundations', label: 'Specialized Stack Fundamentals', status: 'completed' },
    { name: 'Assessment', label: 'Professional Skills Evaluation', status: 'current' },
    { name: 'Applied Systems', label: 'Production Engineering Project', status: 'upcoming' },
    { name: 'Interview Prep', label: 'Technical & System Design Readiness', status: 'upcoming' }
  ],
  'Job Preparation': [
    { name: 'Requisition Match', label: 'Job Role Capabilities Alignment', status: 'completed' },
    { name: 'Assessment', label: 'Domain Technical Assessment', status: 'completed' },
    { name: 'Role Requirements', label: 'Production Requisition Match', status: 'current' },
    { name: 'Domain Project', label: 'Industry Production Case Study', status: 'upcoming' },
    { name: 'Interview Simulation', label: 'Technical Bar Interview Prep', status: 'upcoming' },
    { name: 'Application Ready', label: 'Candidate Profile Activation', status: 'upcoming' }
  ],
  'Company Preparation': [
    { name: 'Company Stack', label: 'Target Enterprise Architecture Review', status: 'completed' },
    { name: 'Internal Systems', label: 'Company Tooling & Standards', status: 'completed' },
    { name: 'Assessment', label: 'Company Challenge Assessment', status: 'current' },
    { name: 'Mock Project', label: 'Production Scale Mock Build', status: 'upcoming' },
    { name: 'Interview Prep', label: 'Engineering Interview Readiness', status: 'upcoming' }
  ]
};

// Aliases for compatibility
defaultRoadmapTemplates['Improve Skill'] = defaultRoadmapTemplates['Improve Current Skill'];
defaultRoadmapTemplates['Learn Skill'] = defaultRoadmapTemplates['Improve Current Skill'];
defaultRoadmapTemplates['Career Transition'] = defaultRoadmapTemplates['Skill Switch'];

function createRoadmapStages() {
  return roadmapStageTemplate.map((stage, index) => ({ ...stage, activities: roadmapActivityTypes.map((activity, activityIndex) => {
    const demoActive = index === 1;
    const complete = index === 0 && activityIndex < 2 || demoActive && activityIndex < 2;
    const progress = complete ? 100 : demoActive && activity.id === 'project' ? 72 : demoActive && activity.id === 'assessment' ? 78 : 0;
    const date = progress ? new Date().toISOString().slice(0, 10) : '';
    return { id: activity.id, label: activity.label, status: progress === 100 ? 'completed' : progress ? 'in-progress' : 'not-started', progress, date, score: activity.id === 'assessment' && demoActive ? 78 : null };
  }) }));
}

function loadRoadmapState() {
  try {
    const saved = JSON.parse(localStorage.getItem(roadmapStorageKey) || 'null');
    if (saved && ['active', 'completed', 'none', 'draft', 'archived', 'paused'].includes(saved.status)) {
      if (saved.status === 'paused') saved.status = 'active';
      return saved;
    }
  } catch (error) { console.warn('Saved roadmap could not be loaded.', error); }

  return {
    id: 'none',
    status: 'none'
  };
}
let roadmapState = loadRoadmapState();
function persistRoadmapState() { localStorage.setItem(roadmapStorageKey, JSON.stringify(roadmapState)); }
const jobTrendData = {
  'AI / ML Engineer': { overallMomentum: 88, changePercentage: 18.2, direction: 'Growing', jobDemand: { value: 91, change: 20.2, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 84, change: 16.4, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 94, change: 22.1, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 83, change: 14.6, trend: 'growing', color: '#6D4AFF' } },
  'All Roles': { overallMomentum: 78, changePercentage: 12.4, direction: 'Growing', jobDemand: { value: 82, change: 14.2, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 74, change: 9.8, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 88, change: 18.6, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 69, change: 6.4, trend: 'growing', color: '#6D4AFF' } },
  'Software Engineer': { overallMomentum: 81, changePercentage: 13.1, direction: 'Growing', jobDemand: { value: 84, change: 15.1, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 78, change: 11.3, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 86, change: 16.8, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 75, change: 8.2, trend: 'growing', color: '#6D4AFF' } },
  'AI Engineer': { overallMomentum: 88, changePercentage: 18.2, direction: 'Growing', jobDemand: { value: 91, change: 20.2, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 84, change: 16.4, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 94, change: 22.1, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 83, change: 14.6, trend: 'growing', color: '#6D4AFF' } },
  'Data Scientist': { overallMomentum: 76, changePercentage: 8.6, direction: 'Growing', jobDemand: { value: 78, change: 10.1, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 71, change: 7.4, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 85, change: 13.5, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 70, change: 5.8, trend: 'growing', color: '#6D4AFF' } },
  'Data Analyst': { overallMomentum: 69, changePercentage: 4.2, direction: 'Growing', jobDemand: { value: 73, change: 5.8, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 66, change: 3.2, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 76, change: 7.1, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 62, change: 2.7, trend: 'growing', color: '#6D4AFF' } },
  'UI/UX Designer': { overallMomentum: 64, changePercentage: 2.1, direction: 'Stable', jobDemand: { value: 67, change: 2.8, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 59, change: 1.1, trend: 'stable', color: '#B04CFF' }, skillDemand: { value: 72, change: 4.2, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 58, change: 0.6, trend: 'stable', color: '#6D4AFF' } },
  'Cybersecurity Engineer': { overallMomentum: 73, changePercentage: 7.4, direction: 'Growing', jobDemand: { value: 79, change: 9.2, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 68, change: 5.7, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 81, change: 11.1, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 64, change: 3.4, trend: 'growing', color: '#6D4AFF' } },
  'Cloud Engineer': { overallMomentum: 71, changePercentage: 6.3, direction: 'Growing', jobDemand: { value: 76, change: 8.1, trend: 'growing', color: '#B22DEF' }, hiringMomentum: { value: 69, change: 6.2, trend: 'growing', color: '#B04CFF' }, skillDemand: { value: 74, change: 7.5, trend: 'growing', color: '#D46CFF' }, roleGrowth: { value: 66, change: 4.1, trend: 'growing', color: '#6D4AFF' } }
};
const marketTrendData = {
  Global: { momentum: 79, change: 12.4, technologyMomentum: [68, 73, 78, 84, 80, 89], jobDemand: [48, 55, 53, 62, 69, 76], investmentSignal: [64, 61, 70, 68, 74, 81] },
  India: { momentum: 76, change: 9.6, technologyMomentum: [62, 68, 74, 81, 79, 86], jobDemand: [52, 58, 61, 68, 73, 82], investmentSignal: [60, 64, 69, 66, 74, 78] },
  'United States': { momentum: 83, change: 14.2, technologyMomentum: [72, 76, 83, 88, 86, 93], jobDemand: [50, 56, 58, 66, 72, 79], investmentSignal: [68, 71, 75, 73, 82, 87] },
  'United Kingdom': { momentum: 74, change: 7.8, technologyMomentum: [63, 69, 73, 78, 75, 82], jobDemand: [48, 53, 58, 60, 66, 71], investmentSignal: [57, 63, 67, 64, 70, 75] },
  Germany: { momentum: 72, change: 6.4, technologyMomentum: [61, 65, 71, 76, 73, 80], jobDemand: [49, 55, 54, 62, 65, 70], investmentSignal: [58, 60, 65, 63, 68, 72] },
  Canada: { momentum: 73, change: 8.1, technologyMomentum: [60, 66, 71, 76, 74, 82], jobDemand: [50, 57, 59, 65, 70, 74], investmentSignal: [56, 61, 66, 64, 69, 74] },
  Australia: { momentum: 75, change: 8.9, technologyMomentum: [62, 68, 72, 79, 77, 84], jobDemand: [53, 57, 62, 68, 72, 78], investmentSignal: [59, 63, 68, 67, 73, 77] },
  Singapore: { momentum: 78, change: 10.7, technologyMomentum: [66, 71, 77, 83, 80, 88], jobDemand: [54, 60, 64, 70, 76, 81], investmentSignal: [63, 67, 72, 71, 78, 83] },
  Japan: { momentum: 71, change: 5.9, technologyMomentum: [60, 64, 70, 74, 72, 79], jobDemand: [47, 51, 56, 59, 63, 69], investmentSignal: [55, 59, 63, 61, 67, 71] }
};
const companyMarketData = {
  microsoft: { name: 'Microsoft', categoryLabel: 'Technology', momentum: 79, change: 12.4, technologyMomentum: [68, 73, 78, 84, 80, 89], jobDemand: [48, 55, 53, 62, 69, 76], investmentSignal: [64, 61, 70, 68, 74, 81], sector: 'AI & Software' },
  google: { name: 'Google', categoryLabel: 'AI & Software', momentum: 75, change: 8.6, technologyMomentum: [64, 69, 75, 79, 77, 84], jobDemand: [46, 52, 58, 61, 67, 72], investmentSignal: [60, 63, 69, 66, 71, 76], sector: 'AI & Software' },
  amazon: { name: 'Amazon', categoryLabel: 'Cloud / E-commerce', momentum: 73, change: 5.1, technologyMomentum: [62, 68, 70, 76, 74, 81], jobDemand: [55, 60, 64, 69, 74, 79], investmentSignal: [58, 60, 65, 62, 68, 71], sector: 'Retail' },
  nvidia: { name: 'NVIDIA', categoryLabel: 'AI / Semiconductor', momentum: 86, change: 18.6, technologyMomentum: [69, 74, 82, 90, 88, 96], jobDemand: [49, 57, 62, 71, 78, 86], investmentSignal: [65, 70, 78, 82, 88, 94], sector: 'AI & Software' },
  meta: { name: 'Meta', categoryLabel: 'Technology', momentum: 61, change: -7.2, technologyMomentum: [82, 78, 73, 68, 62, 57], jobDemand: [73, 70, 66, 63, 58, 54], investmentSignal: [77, 72, 68, 61, 56, 49], sector: 'AI & Software' }
};
const marketCompanyData = Object.values(companyMarketData).map((company, index) => ({ ...company, slug: company.name.toLowerCase().replace(' ', ''), color: ['5E5CE6', '4285F4', 'FF9900', '76B900', '0668E1'][index], points: company.technologyMomentum }));
const sidebar = document.querySelector('#sidebar');
const mainContent = document.querySelector('#mainContent');
const mobileScrim = document.querySelector('#mobileScrim');
const sidebarToggle = document.querySelector('#sidebarToggle');
const mobileMenu = document.querySelector('#mobileMenu');
const profileTrigger = document.querySelector('#profileTrigger');
const profilePopover = document.querySelector('#profilePopover');
const notificationButton = document.querySelector('#notificationButton');
const notificationPopover = document.querySelector('#notificationPopover');

function renderNavigation() {
  document.querySelector('#primaryNav').innerHTML = navigation.map(group => `
    <section class="nav-group" aria-labelledby="nav-${group.label.toLowerCase()}">
      <h2 class="nav-group__heading" id="nav-${group.label.toLowerCase()}">${group.label}</h2>
      ${group.items.map(item => `
        <a class="nav-item" href="#${item.route}" data-route="${item.route}" data-tooltip="${item.label}">
          <i data-lucide="${item.icon}"></i><span class="nav-item__label">${item.label}</span>
        </a>
      `).join('')}
    </section>
  `).join('');
  lucide.createIcons();
}

function currentRoute() {
  return window.location.hash.slice(1) || '/individual/home';
}

function updateUserDetails() {
  const meta = `${user.role}  —  ${user.location}`;
  document.querySelectorAll('[data-user-initials]').forEach(element => { element.textContent = user.initials; });
  document.querySelectorAll('[data-user-name]').forEach(element => { element.textContent = user.name; });
  document.querySelectorAll('[data-user-short-name]').forEach(element => { element.textContent = user.shortName; });
  document.querySelectorAll('[data-user-meta]').forEach(element => { element.textContent = meta; });
}

function optionMarkup(options, selected) {
  return options.map(option => `<option value="${option}" ${option === selected ? 'selected' : ''}>${option}</option>`).join('');
}

function selectControl(id, label, options, selected) {
  return `<label class="dashboard-control"><span>${label}</span><select id="${id}">${optionMarkup(options, selected)}</select><i data-lucide="chevron-down"></i></label>`;
}

function statusClass(status) {
  return status.toLowerCase().replace(/\s+/g, '-');
}

function miniSignalMarkup(items) {
  return items.map(item => `
    <div class="signal-row">
      <span class="signal-row__label">${item.label}</span>
      <span class="signal-row__bar"><span style="--signal-width: ${item.value}%"></span></span>
      <span class="trend-status trend-status--${statusClass(item.direction)}">${item.direction}</span>
    </div>
  `).join('');
}

function trendCard({ title, description, icon, items, cta, route }) {
  return `
    <article class="trend-card">
      <div class="trend-card__header"><span class="trend-card__icon"><i data-lucide="${icon}"></i></span><span class="trend-card__arrow"><i data-lucide="arrow-up-right"></i></span></div>
      <h2>${title}</h2><p>${description}</p>
      <div class="signal-list">${miniSignalMarkup(items)}</div>
      <a class="card-link" href="#${route}">${cta}<i data-lucide="arrow-right"></i></a>
    </article>
  `;
}

function chartLabels() {
  const labels = { '7 Days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], '30 Days': ['W1', 'W2', 'W3', 'W4', 'Now'], '90 Days': ['Jan', 'Feb', 'Mar', 'Now'], '6 Months': ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Now'], '1 Year': ['Q1', 'Q2', 'Q3', 'Q4', 'Now'] };
  return labels[dashboardState.timeRange];
}

function chartValues() {
  const values = skillTrendData[dashboardState.selectedSkill] || skillTrendData.Python;
  const labels = chartLabels();
  return values.slice(values.length - labels.length);
}

function renderSkillChart() {
  const values = chartValues();
  const labels = chartLabels();
  const max = Math.max(...values, 100);
  return `
    <div class="skill-chart" role="img" aria-label="${dashboardState.selectedSkill} skill demand index trend for ${dashboardState.market}">
      <div class="chart-y-axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div>
      <div class="chart-plot"><div class="chart-gridlines"><i></i><i></i><i></i><i></i><i></i></div><div class="chart-bars">
        ${values.map((value, index) => `<div class="chart-bar-wrap ${index === values.length - 1 ? 'is-highlighted' : ''}" title="${labels[index]}: prototype index ${value}"><span class="chart-value">${value}</span><span class="chart-bar" style="--bar-height: ${(value / max) * 100}%"></span><span class="chart-label">${labels[index]}</span></div>`).join('')}
      </div></div>
    </div>
  `;
}

function getSkillSummary() {
  const values = chartValues();
  const current = values[values.length - 1];
  const previous = values[Math.max(0, values.length - 2)];
  const growth = Math.max(1, Math.round(((current - previous) / previous) * 100));
  return { current, growth, direction: current >= previous ? 'Growing' : 'Stable' };
}

function getMarketSummary() {
  return marketSignalData[dashboardState.market] || marketSignalData.Global;
}

function getJobSummary() {
  return dashboardState.savedCompanies.reduce((total, company) => total + (companyVacancies[company] || 0), 0);
}

function renderOverviewSummary() {
  const skill = getSkillSummary();
  const market = getMarketSummary();
  const vacancies = getJobSummary();
  return `<section class="overview-summary" aria-labelledby="overview-summary-title"><div class="overview-summary__intro"><span class="overview-summary__icon"><i data-lucide="layers-3"></i></span><div><h2 id="overview-summary-title">Overview</h2><p>Track what's trending in the market and how it impacts your career.</p></div></div><div class="overview-summary__metrics"><div class="overview-metric"><span class="overview-metric__icon"><i data-lucide="briefcase-business"></i></span><div><strong>Skill Trends</strong><span>${dashboardState.selectedSkill} <b>+${skill.growth}%</b></span><small class="trend-status--${statusClass(skill.direction)}">${skill.direction}</small></div><span class="overview-metric__arrow" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span></div><div class="overview-metric"><span class="overview-metric__icon overview-metric__icon--market"><i data-lucide="bar-chart-3"></i></span><div><strong>Market Trends</strong><span>${market.company} <b>+${market.value}%</b></span><small class="trend-status--growing">Growing</small></div><span class="overview-metric__arrow" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span></div><div class="overview-metric"><span class="overview-metric__icon overview-metric__icon--jobs"><i data-lucide="briefcase"></i></span><div><strong>Job Trends</strong><span>${vacancies.toLocaleString()}</span><small>Open roles</small></div><span class="overview-metric__arrow" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span></div></div></section>`;
}

function renderOverview() {
  const isSaved = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
  const values = chartValues();
  const current = values[values.length - 1];
  const previous = values[Math.max(0, values.length - 2)];
  const momentum = current >= previous ? 'Growing' : 'Stable';
  return `
    <section class="overview-card dashboard-card" aria-labelledby="overview-title">
      <div class="dashboard-card__heading"><div><span class="section-kicker">Market intelligence</span><h2 id="overview-title">Market &amp; Skill Overview</h2><p>Track how skills, technology and job demand are moving across markets.</p></div><div class="live-status"><span class="live-dot"></span><strong>LIVE MARKET SIGNALS</strong><small>Prototype data  —  updated just now</small></div></div>
      <div class="overview-controls">
        ${selectControl('marketSelect', 'Market Scope', marketOptions, dashboardState.market)}
        ${selectControl('skillScopeSelect', 'Skill Scope', ['My Saved Skills', 'All Skills', 'Trending Skills'], dashboardState.skillScope)}
        ${selectControl('timeRangeSelect', 'Time Range', timeRangeOptions, dashboardState.timeRange)}
      </div>
      <div class="skill-toolbar"><div class="skill-picker"><label for="skillSelect">Skill</label><div class="skill-select-wrap"><input id="skillSelect" list="skillOptions" value="${dashboardState.selectedSkill}" autocomplete="off" aria-label="Select skill"><i data-lucide="chevron-down"></i></div><datalist id="skillOptions">${skillOptions.map(skill => `<option value="${skill}">`).join('')}</datalist></div><button class="save-skill ${isSaved ? 'is-saved' : ''}" id="saveSkillButton" type="button" aria-pressed="${isSaved}"><i data-lucide="${isSaved ? 'check' : 'heart'}"></i>${isSaved ? 'Saved' : 'Save'}</button><span class="scope-note"><i data-lucide="globe-2"></i>${dashboardState.market}  —  ${dashboardState.skillScope}</span></div>
      <div class="chart-heading"><div><h3>Skill Trend</h3><p>${dashboardState.selectedSkill}  —  Skill Demand Index</p></div><span class="trend-status trend-status--growing"><i data-lucide="trending-up"></i> Growing</span></div>
      ${renderSkillChart()}
      <div class="insight-strip"><div><span>Skill Demand</span><strong>${current}<small>/100</small></strong><em class="trend-status--growing">Growing</em></div><div><span>Market Momentum</span><strong>${momentum === 'Growing' ? '+12' : '+4'}<small>%</small></strong><em class="trend-status--accelerating">${momentum}</em></div><div><span>Job Demand</span><strong>${Math.min(99, current + 7)}<small>/100</small></strong><em class="trend-status--growing">Growing</em></div></div>
      <p class="prototype-note">Prototype signal for interface testing. Connect this view to market and skill intelligence APIs when available.</p>
    </section>
  `;
}

function renderFutureSkills() {
  return `<article class="future-card dashboard-card"><div class="dashboard-card__heading"><div><span class="section-kicker">Future skill intelligence</span><h2>Future Skill Live Trends</h2><p>Skills gaining momentum across the market.</p></div><span class="trend-card__icon"><i data-lucide="radar"></i></span></div><div class="future-skill-list">${futureSkills.map(skill => `<a class="future-skill" href="#/individual/skills?skill=${encodeURIComponent(skill.label)}"><span class="future-skill__icon"><i data-lucide="${skill.icon}"></i></span><span><strong>${skill.label}</strong><small>${skill.status}</small></span><span class="future-skill__direction future-skill__direction--${skill.direction}"><i data-lucide="${skill.direction === 'up' ? 'trending-up' : 'minus'}"></i></span></a>`).join('')}</div><a class="card-link" href="#/individual/skills">Explore Future Skills <i data-lucide="arrow-right"></i></a></article>`;
}

function renderSparkline(points, label) {
  const coordinates = points.map((point, index) => `${index * 20},${34 - point}`).join(' ');
  return `<svg class="sparkline" viewBox="0 0 120 40" role="img" aria-label="${label} sparkline"><polyline points="${coordinates}" vector-effect="non-scaling-stroke"></polyline></svg>`;
}

function renderPulseCard(title, value, direction, icon, points, extra = '') {
  return `<article class="pulse-card"><div class="pulse-card__top"><span class="pulse-card__icon"><i data-lucide="${icon}"></i></span><span class="pulse-card__context">${extra}</span></div><span class="pulse-card__label">${title}</span><strong>${value}</strong><span class="pulse-card__trend"><i data-lucide="trending-up"></i>${direction}</span>${renderSparkline(points, `${title} trend`)}<a class="pulse-card__link" href="#/individual/${title === 'Job Market' ? 'career' : 'market-insights'}" aria-label="Open ${title} details"><i data-lucide="arrow-up-right"></i></a></article>`;
}

function getContextTrendValues() {
  return contextSkillTrendData[dashboardState.selectedSkill]?.[dashboardState.market]?.[dashboardState.timeRange] || contextSkillTrendData.Python.Global['7 Days'];
}

function renderMiniBars(points, label, context = {}) {
  const labels = chartLabels().slice(-points.length);
  return `<div class="mini-bars" role="img" aria-label="${label} prototype trend">${points.map((point, index) => `<i tabindex="0" data-period="${labels[index]}" data-value="${point}" data-skill="${context.skill || ''}" data-market="${context.market || ''}" style="--mini-height:${point}%; --mini-delay:${index * 80}ms"></i>`).join('')}</div>`;
}

function getChartSkills() {
  return (dashboardState.skillScope === 'All Skills' ? skillOptions : dashboardState.savedSkills).slice(0, 5);
}

function getSavedSkillValues() {
  return getChartSkills().map(skill => {
    const values = contextSkillTrendData[skill]?.[dashboardState.market]?.[dashboardState.timeRange] || contextSkillTrendData[skill]?.Global?.['7 Days'] || [42, 48, 55, 61, 68, 73, 78];
    return { skill, value: values[values.length - 1] };
  });
}

function renderSavedSkillChart() {
  const skills = getSavedSkillValues();
  if (!skills.length) return '<div class="saved-skill-empty"><i data-lucide="bookmark-plus"></i><strong>No saved skills yet</strong><span>Use + to add a skill and track its trend.</span></div>';
  const chartLabel = dashboardState.skillScope === 'All Skills' ? 'All skill trend comparison' : 'Saved skill trend comparison';
  return `<div class="saved-skill-chart" role="img" aria-label="${chartLabel} for ${dashboardState.market}"><div class="saved-chart-y-axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="saved-chart-plot"><div class="saved-chart-gridlines"><i></i><i></i><i></i><i></i><i></i></div><div class="saved-chart-bars">${skills.map(({ skill, value }, index) => `<div class="saved-chart-bar-wrap"><span class="saved-chart-value">${value}</span><i class="saved-chart-bar ${index === skills.length - 1 ? 'is-emphasized' : ''}" data-period="Current" data-value="${value}" data-skill="${skill}" data-market="${dashboardState.market}" style="--saved-bar-height:${value}%"></i><span class="saved-chart-label">${skill}</span></div>`).join('')}</div></div></div>`;
}

function renderSkillPulseCard() {
  const trackedSkills = dashboardState.skillScope === 'All Skills' ? `${skillOptions.length} skills available` : dashboardState.savedSkills.length ? `${dashboardState.savedSkills.length} saved skill${dashboardState.savedSkills.length === 1 ? '' : 's'} tracked` : 'Add skills to track their trends';
  const scopeLabel = dashboardState.skillScope === 'All Skills' ? 'All skills' : 'My saved skills';
  const timeLabel = dashboardState.timeRange.replace(' Days', 'D').replace(' Months', 'M').replace(' Year', 'Y');
  const canAddSkill = dashboardState.savedSkills.length < 5;
  const addPanel = canAddSkill ? `<label for="skillAddSelect">Add skill to chart</label><select id="skillAddSelect"><option value="">Select a skill</option>${skillOptions.filter(skill => !dashboardState.savedSkills.includes(skill)).map(skill => `<option value="${skill}">${skill}</option>`).join('')}</select><button id="confirmAddSkill" type="button">Add skill</button>` : '<strong>Maximum 5 skills tracked</strong><span>Remove one from Saved before adding another.</span>';
  return `<article class="pulse-card pulse-card--skill"><div class="pulse-card__top"><span class="pulse-card__icon"><i data-lucide="layers-3"></i></span><span class="pulse-card__context"><i class="live-dot"></i>Updated recently</span></div><div class="skill-card-heading"><div><span class="pulse-card__label">SKILL TREND</span><strong>${scopeLabel}</strong><span class="pulse-card__meta">${dashboardState.market}  —  ${timeLabel}</span></div><div class="skill-card-actions"><button class="filter-icon-button" id="timeFilterButton" type="button" aria-expanded="false" aria-label="Change time range" title="Time range"><i data-lucide="calendar-days"></i></button><div class="chart-filter-menu" id="timeFilterMenu" hidden>${timeRangeOptions.map(option => `<button type="button" data-time-range="${option}">${option}</button>`).join('')}</div><button class="filter-icon-button" id="marketFilterButton" type="button" aria-expanded="false" aria-label="Change market" title="Market"><i data-lucide="globe-2"></i></button><div class="chart-filter-menu" id="marketFilterMenu" hidden>${marketOptions.map(option => `<button type="button" data-market="${option}">${option}</button>`).join('')}</div><button class="filter-icon-button" id="scopeFilterButton" type="button" aria-expanded="false" aria-label="Change skill view" title="Skill view"><i data-lucide="sliders-horizontal"></i></button><div class="chart-filter-menu" id="scopeFilterMenu" hidden><button type="button" data-scope="My Saved Skills">My saved skills</button><button type="button" data-scope="All Skills">All skills</button></div><button class="add-skill-button" id="addSkillButton" type="button" aria-expanded="false" aria-label="Add skill to trend chart" title="Add skill" ${canAddSkill ? '' : 'disabled'}><i data-lucide="plus"></i></button></div></div><div class="skill-card-status"><span class="pulse-card__trend"><i data-lucide="trending-up"></i>Growing</span><span class="pulse-card__saved-context"><i data-lucide="bookmark"></i>${trackedSkills}</span></div><div class="add-skill-panel" id="addSkillPanel" hidden>${addPanel}</div>${renderSavedSkillChart()}<p class="prototype-note">Prototype market signal  —  Hover a bar to inspect the current demand index.</p><a class="pulse-card__link" href="#/individual/skills" aria-label="Open saved skill details"><i data-lucide="arrow-up-right"></i></a></article>`;
}

function renderMarketPulse() {
  return `<section class="skill-demand-module">${renderSkillTrendAnalyticsCard()}</section>`;
}

function renderSkillTrendCard() {
  const isSaved = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
  return `<section class="skill-trend-card dashboard-card" aria-labelledby="skill-trend-title"><div class="analytics-card__header"><div><span class="eyebrow">SKILL TREND</span><h2 id="skill-trend-title">${dashboardState.selectedSkill}</h2><p>Skill demand index  —  ${dashboardState.market}</p></div><div class="analytics-card__actions"><span class="trend-status trend-status--growing"><i data-lucide="trending-up"></i>Growing</span><button class="save-skill ${isSaved ? 'is-saved' : ''}" id="saveSkillButton" type="button" aria-pressed="${isSaved}"><i data-lucide="${isSaved ? 'check' : 'star'}"></i>${isSaved ? 'Saved' : 'Save Skill'}</button></div></div><div class="analytics-controls"><label>Skill<select id="skillSelect">${optionMarkup(skillOptions, dashboardState.selectedSkill)}</select><i data-lucide="chevron-down"></i></label><label>Market<select id="marketSelect">${optionMarkup(marketOptions, dashboardState.market)}</select><i data-lucide="chevron-down"></i></label><label>Time Range<select id="timeRangeSelect">${optionMarkup(timeRangeOptions, dashboardState.timeRange)}</select><i data-lucide="chevron-down"></i></label></div>${renderSkillChart()}<div class="chart-footnote"><span><i data-lucide="info"></i>Prototype market signal</span><span>Hover a bar for demand index details</span></div></section>`;
}

function renderTechnologyCard() {
  return `<article class="compact-analytics-card dashboard-card"><div class="compact-card__header"><div><span class="eyebrow">TECHNOLOGY TRENDS</span><h2>Technology momentum</h2></div><span class="compact-card__icon"><i data-lucide="cpu"></i></span></div><p>Technologies influencing future work.</p><div class="area-chart"><svg viewBox="0 0 480 110" preserveAspectRatio="none" aria-label="Technology momentum prototype line chart"><defs><linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#B22DEF" stop-opacity=".18"></stop><stop offset="1" stop-color="#B22DEF" stop-opacity="0"></stop></linearGradient></defs><path class="area-chart__fill" d="M0 92 C55 82 70 85 112 68 S178 73 218 54 S270 61 316 42 S370 48 405 26 S450 30 480 12 V110 H0 Z"></path><path class="area-chart__line" d="M0 92 C55 82 70 85 112 68 S178 73 218 54 S270 61 316 42 S370 48 405 26 S450 30 480 12"></path></svg></div><div class="compact-signal-list">${technologyTrends.slice(0, 4).map(item => `<div><span>${item.label}</span><strong>${item.direction}</strong></div>`).join('')}</div><a class="card-link" href="#/individual/market-insights">Explore Technology <i data-lucide="arrow-right"></i></a></article>`;
}

function renderJobMarketCard() {
  return `<article class="compact-analytics-card dashboard-card"><div class="compact-card__header"><div><span class="eyebrow">JOB MARKET TRENDS</span><h2>Role demand</h2></div><span class="compact-card__icon"><i data-lucide="briefcase-business"></i></span></div><p>What employers are asking for across roles.</p><div class="job-bars">${jobMarketTrends.concat([{ label: 'Cybersecurity Engineer', value: 67, direction: 'Growing' }]).map(item => `<div class="job-bar-row"><span>${item.label}</span><span class="job-bar"><i style="--job-width:${item.value}%"></i></span><strong class="trend-status--${statusClass(item.direction)}">${item.direction}</strong></div>`).join('')}</div><a class="card-link" href="#/individual/opportunities">Explore Job Market <i data-lucide="arrow-right"></i></a></article>`;
}

function renderOverviewSparkline(values, label) {
  const source = values.length ? values : [42, 48, 53, 61, 66, 74];
  const min = Math.min(...source), range = Math.max(1, Math.max(...source) - min);
  const coordinates = source.map((value, index) => ({ x: (index / Math.max(1, source.length - 1)) * 100, y: 25 - ((value - min) / range) * 18 }));
  const points = coordinates.map(point => `${point.x},${point.y}`).join(' ');
  const area = `M0,30 L${coordinates.map(point => `${point.x},${point.y}`).join(' L')} L100,30 Z`;
  const last = coordinates.at(-1);
  return `<svg class="intelligence-sparkline" viewBox="0 0 100 32" role="img" aria-label="${label} illustrative trend"><path class="intelligence-sparkline__area" d="${area}"></path><polyline points="${points}" vector-effect="non-scaling-stroke"></polyline><circle class="intelligence-sparkline__point" cx="${last.x}" cy="${last.y}" r="2.2"></circle></svg>`;
}

function renderPersonalIntelligenceOverview() {
  const current = trendDetailsForSkill(dashboardState.selectedSkill);
  const assessment = skillAssessmentFor(dashboardState.selectedSkill, current);
  const selectedCompany = marketTrendState.company && companyMarketData[marketTrendState.company.toLowerCase()];
  const relevantCompany = selectedCompany || dashboardState.savedCompanies
    .map(name => companyMarketData[name.toLowerCase()])
    .filter(Boolean)
    .sort((first, second) => getMarketTrendView(second.name).momentum - getMarketTrendView(first.name).momentum)[0];
  const market = relevantCompany ? getMarketTrendView(relevantCompany.name) : getMarketTrendView();
  const job = getJobTrendView();
  const vacancies = getJobSummary();
  const compactVacancies = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(vacancies);
  const skillChange = Number((((current.current - current.previous) / Math.max(1, current.previous)) * 100).toFixed(1));
  const skillDirection = skillChange > 1 ? 'Growing' : skillChange < -1 ? 'Declining' : 'Stable';
  const jobClass = job.direction === 'Declining' ? 'is-negative' : job.direction === 'Stable' ? 'is-neutral' : 'is-positive';
  const roadmapActive = ['active', 'paused'].includes(roadmapState.status);
  const roadmapStages = roadmapActive ? (roadmapState.stages?.length ? roadmapState.stages : createRoadmapStages()) : [];
  const roadmapDone = roadmapStages.filter(stage => stage.completed).length;
  const roadmapProgress = roadmapActive ? roadmapState.progress ?? Math.round((roadmapState.completedTopics ?? 0) / 28 * 100) : 0;
  const trendIcon = direction => direction === 'Growing' ? 'trending-up' : direction === 'Declining' ? 'trending-down' : 'minus';
  const trendClass = direction => direction === 'Growing' ? 'is-positive' : direction === 'Declining' ? 'is-negative' : 'is-neutral';
  const cards = [
    { tone: 'skill', icon: 'brain-circuit', href: '#/individual/skills', title: 'Skill Intelligence', value: dashboardState.selectedSkill, detail: `${assessment.score} / 100`, trend: `${skillChange > 0 ? '+' : ''}${skillChange}%`, status: skillDirection, values: current.values },
    { tone: 'market', icon: 'chart-no-axes-combined', href: '#/individual/market-insights', title: 'Market Intelligence', value: relevantCompany?.name || dashboardState.market, detail: `${market.change > 0 ? '+' : ''}${market.change.toFixed(1)}% momentum`, trend: `${market.change > 0 ? '+' : ''}${market.change.toFixed(1)}%`, status: market.trend, values: market.technologyMomentum },
    { tone: 'opportunity', icon: 'briefcase-business', href: '#/individual/career', title: 'Job Opportunities', value: compactVacancies, detail: 'Relevant openings', trend: `${job.change > 0 ? '+' : ''}${job.change.toFixed(1)}%`, status: job.direction, values: job.metrics.map(metric => metric.value) },
    { tone: 'roadmap', icon: 'map', href: roadmapActive ? '#/individual/learning' : '#/individual/learning', title: 'Roadmap Progress', value: roadmapActive ? `${roadmapProgress}%` : 'NO ACTIVE ROADMAP', detail: roadmapActive ? `${roadmapState.skill} Roadmap` : 'Build a roadmap from your recommended skills', trend: roadmapActive ? `${roadmapDone} of ${roadmapStages.length} stages complete` : 'Explore Recommendations', status: roadmapActive ? (roadmapState.status === 'paused' ? 'Paused' : 'Tracking') : '', values: roadmapActive ? [20, roadmapProgress * .72, roadmapProgress] : [0, 0, 0] }
  ];
  return `<section class="personal-intelligence-card" aria-labelledby="personal-intelligence-title"><div class="personal-intelligence-heading"><div><span class="section-kicker">Personal intelligence</span><h2 id="personal-intelligence-title">Your Intelligence Overview</h2><p>A live snapshot of the signals, opportunities and progress that matter to you.</p></div><span class="prototype-indicator"><i></i>Illustrative prototype data</span></div><div class="personal-intelligence-signals">${cards.map(card => `<a class="intelligence-signal intelligence-signal--${card.tone}" href="${card.href}" aria-label="Open ${card.title}"><span class="intelligence-signal__icon"><i data-lucide="${card.icon}"></i></span><div class="intelligence-signal__copy"><span class="intelligence-signal__title">${card.title}</span><strong class="intelligence-signal__value">${card.value}</strong><span class="intelligence-signal__detail">${card.detail}</span></div>${card.status ? `<span class="intelligence-signal__status ${trendClass(card.status)}"><i data-lucide="${trendIcon(card.status)}"></i>${card.status}</span>` : ''}<span class="intelligence-signal__trend ${card.tone === 'roadmap' && !roadmapActive ? 'intelligence-signal__trend--action' : ''}">${card.trend}</span>${renderOverviewSparkline(card.values, `${card.title} illustrative trend`)}<span class="intelligence-signal__arrow" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span></a>`).join('')}</div></section>`;
}

function renderExploreFocusSelector() {
  const type = intelligenceExplorerState.type;
  const selected = intelligenceExplorerState.selected[type];
  const listId = `explore-${type}-options`;
  const options = type === 'skills' ? skillOptions : type === 'roles' ? jobRoleOptions : marketCompanyData.map(company => company.name);
  const saved = type === 'skills' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : dashboardState.savedCompanies;
  const scopedOptions = intelligenceExplorerState.scope === 'Saved' ? options.filter(option => saved.includes(option)) : options;
  const isSaved = !!selected && saved.includes(selected);
  const details = type === 'skills' && selected ? trendDetailsForSkill(selected) : null;
  const assessment = details ? skillAssessmentFor(selected, details) : null;
  const role = type === 'roles' && selected ? jobTrendData[selected] : null;
  const company = type === 'companies' && selected ? getMarketTrendView(selected) : null;
  const skillDirection = details ? (details.current > details.previous ? 'Growing' : details.current < details.previous ? 'Declining' : 'Stable') : 'Stable';
  const metrics = type === 'skills' && details ? [
    ['Selected Skill', selected], ['Current Health', `${assessment.score} / 100`], ['Market Demand', skillDirection],
    ['Future Demand', `+${selected === 'Machine Learning' ? 18 : details.growth}%`], ['Relevance', assessment.score >= 70 ? 'High' : 'Building'], ['Last Updated', 'Updated 12 min ago']
  ] : type === 'roles' && role ? [
    ['Selected Role', selected], ['Current Momentum', `${role.overallMomentum} / 100`], ['Market Demand', role.direction],
    ['Future Demand', `+${role.changePercentage}%`], ['Relevance', 'High'], ['Last Updated', 'Updated 12 min ago']
  ] : type === 'companies' && company ? [
    ['Selected Company', selected], ['Market Momentum', `${Math.round(company.momentum)} / 100`], ['Market Direction', company.trend],
    ['Change', `${company.change > 0 ? '+' : ''}${company.change.toFixed(1)}%`], ['Relevance', 'High'], ['Last Updated', 'Updated 12 min ago']
  ] : [];
  const placeholder = `Search or select a ${type === 'skills' ? 'skill' : type === 'roles' ? 'role' : 'company'}...`;
  const typeLabels = { skills: 'Skills', roles: 'Roles', companies: 'Companies' };
  const whyCopy = type === 'skills' ? `${selected || 'This skill'} is showing ${details?.demand.toLowerCase() || 'market movement'}. Tracking its current health alongside future demand can help you prioritize your learning.` : type === 'roles' ? `${selected || 'This role'} demand helps connect your skills to hiring direction and the capabilities employers are emphasizing.` : `${selected || 'This company'} signals can help you understand how technology, investment and hiring activity are shifting in your selected market.`;
  return `<section class="explore-intelligence" aria-labelledby="explore-intelligence-title"><header class="explore-intelligence__heading"><div><span class="section-kicker">Personal focus</span><h2 id="explore-intelligence-title">Explore Your Intelligence</h2><p>Choose a skill, role or company to understand what is changing and why it matters to you.</p></div><span class="explore-intelligence__prototype"><i></i>Illustrative intelligence</span></header><div class="explore-intelligence__card"><div class="explore-intelligence__controls"><div class="explore-intelligence__tabs" role="tablist" aria-label="Intelligence type">${Object.entries(typeLabels).map(([key, label]) => `<button type="button" role="tab" aria-selected="${key === type}" class="${key === type ? 'is-active' : ''}" data-explore-type="${key}">${label}</button>`).join('')}</div><div class="explore-intelligence__scope" role="group" aria-label="Intelligence scope">${['Global', 'My Market', 'Saved'].map(scope => `<button type="button" aria-pressed="${scope === intelligenceExplorerState.scope}" class="${scope === intelligenceExplorerState.scope ? 'is-active' : ''}" data-explore-scope="${scope}">${scope}</button>`).join('')}</div><label class="explore-intelligence__search"><span>${typeLabels[type]} intelligence</span><span class="explore-intelligence__input-wrap"><i data-lucide="search"></i><input id="exploreIntelligenceInput" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" list="${listId}" value="${selected || ''}" placeholder="${placeholder}" autocomplete="off"><i class="explore-intelligence__chevron" data-lucide="chevron-down"></i></span><datalist id="${listId}">${scopedOptions.map(option => `<option value="${option}"></option>`).join('')}</datalist></label><button type="button" class="explore-intelligence__save ${isSaved ? 'is-saved' : ''}" id="saveExploreIntelligence" ${!selected || isSaved || (type === 'skills' && dashboardState.savedSkills.length >= 5) ? 'disabled' : ''}><i data-lucide="${isSaved ? 'check' : 'bookmark-plus'}"></i>${isSaved ? ' —  Saved' : 'Save to My Intelligence'}</button></div><div class="explore-intelligence__content" aria-live="polite">${metrics.length ? `<div class="explore-intelligence__summary"><div><span class="explore-intelligence__item-icon"><i data-lucide="${type === 'skills' ? 'brain-circuit' : type === 'roles' ? 'briefcase-business' : 'building-2'}"></i></span><div><span class="section-kicker">${typeLabels[type].slice(0, -1)} selected</span><h3>${selected}</h3><p>${type === 'skills' ? 'A focused view of skill health and market demand.' : type === 'roles' ? 'A focused view of hiring momentum and role growth.' : 'A focused view of company and market signals.'}</p></div></div><div class="explore-intelligence__actions"><button type="button" class="explore-intelligence__text-button" id="whyIntelligenceButton" aria-expanded="${intelligenceExplorerState.showWhy}"><i data-lucide="circle-help"></i>Why this matters</button><button type="button" class="explore-intelligence__evidence" id="viewIntelligenceEvidence"><i data-lucide="file-search-2"></i>View Evidence</button></div></div><dl class="explore-intelligence__metrics">${metrics.map(([label, value], index) => `<div class="explore-intelligence__metric" style="--metric-delay:${index * 45}ms"><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl><p class="explore-intelligence__why" id="intelligenceWhyCopy" ${intelligenceExplorerState.showWhy ? '' : 'hidden'}>${whyCopy}</p>` : `<div class="explore-intelligence__empty"><i data-lucide="bookmark"></i><strong>No saved ${type} yet</strong><span>Choose a ${type === 'skills' ? 'skill' : type === 'roles' ? 'role' : 'company'} from Global or My Market, then save it to your intelligence.</span></div>`}<p class="explore-intelligence__note">Prototype values for preview only  —  not verified live data</p></div></div></section>`;
}

renderExploreFocusSelector = function() {
  const typeLabels = { skills: 'Skill Intelligence', companies: 'Market Intelligence', roles: 'Job Intelligence' };
  const lists = { skills: skillOptions, companies: marketCompanyData.map(company => company.name), roles: jobRoleOptions };
  const type = intelligenceExplorerState.type;
  const selected = intelligenceExplorerState.selected[type] || '';
  const options = lists[type] || skillOptions;
  const savedItems = type === 'skills' || type === 'technologies' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : type === 'companies' ? intelligenceExplorerState.favoriteCompanies : type === 'markets' ? savedMarkets : dashboardState.savedCompanies;
  const saved = savedItems;
  const selectedSkillItems = intelligenceExplorerState.selectedSkills.length ? intelligenceExplorerState.selectedSkills : (dashboardState.savedSkills.length ? dashboardState.savedSkills.slice(0, 5) : [dashboardState.selectedSkill]);
  const skillScopeOptions = ['All Skills', 'My Skills', 'Favorite Skills'];
  const skillQuestions = intelligenceExplorerState.skillScope === 'All Skills' ? ['What skills are trending globally?', 'Which skills are growing fastest?', 'What are the top emerging skills?', 'Which skills are declining?'] : intelligenceExplorerState.skillScope === 'Favorite Skills' ? ['How are my favorite skills trending?', 'Which favorite skill has the strongest future relevance?', 'Which skill is losing demand?', 'What should I learn next?'] : ['How relevant are my current skills?', 'Which of my skills are growing?', 'Where are my biggest skill gaps?', 'Which skill should I strengthen first?'];
  const questionChips = type === 'skills' ? skillQuestions : type === 'companies' ? ['Which companies are hiring most?', 'What market signals are accelerating?', 'Compare leading companies', 'Where is investment growing?'] : ['Which roles are growing fastest?', 'What skills do employers need?', 'Where is hiring demand strongest?', 'What role fits my skills?'];
  const contextMarkup = type === 'skills' ? `<div class="intelligence-console__dynamic-context"><div class="intelligence-console__context-heading"><div><span>Skill Intelligence</span><small>Set the skills and market to analyze</small></div><span class="intelligence-console__context-state"><i></i>Context synced</span></div><div class="intelligence-console__context-grid"><label><span>Skill Scope</span><select id="skillScopeSelect">${skillScopeOptions.map(option => `<option ${option === intelligenceExplorerState.skillScope ? 'selected' : ''}>${option}</option>`).join('')}</select></label><div class="intelligence-console__context-skills"><span>Skills</span><div>${intelligenceExplorerState.skillScope === 'All Skills' ? '<em class="is-muted">All Skills</em>' : (intelligenceExplorerState.skillScope === 'Favorite Skills' ? intelligenceExplorerState.favoriteSkills : selectedSkillItems).map(skill => `<button type="button" class="intelligence-console__skill-chip ${intelligenceExplorerState.selectedSkills.includes(skill) ? 'is-selected' : ''}" data-context-skill="${skill}" aria-pressed="${intelligenceExplorerState.selectedSkills.includes(skill)}">${skill}${intelligenceExplorerState.skillScope === 'Favorite Skills' ? '<small> —  Growing  —  High relevance</small>' : ''}<i data-lucide="${intelligenceExplorerState.skillScope === 'Favorite Skills' ? 'x' : 'check'}"></i></button>`).join('')} ${intelligenceExplorerState.skillScope !== 'All Skills' ? '<button type="button" class="intelligence-console__add-skill" id="addFavoriteSkill"><i data-lucide="plus"></i>Add skill</button>' : ''}</div><div class="intelligence-console__skill-picker" id="favoriteSkillPicker" hidden><input id="favoriteSkillSearch" type="search" placeholder="Search skills..." aria-label="Search skills"><div>${skillOptions.filter(skill => !intelligenceExplorerState.favoriteSkills.includes(skill)).map(skill => `<button type="button" data-add-skill="${skill}">${skill}<i data-lucide="plus"></i></button>`).join('')}</div></div></div><label><span>Market</span><select id="skillLocationSelect">${optionMarkup(['Global', ...marketOptions.filter(location => location !== 'Global'), ...(!marketOptions.includes(intelligenceExplorerState.market) ? [intelligenceExplorerState.market] : []), 'Custom location'], intelligenceExplorerState.market)}</select></label></div></div>` : `<div class="intelligence-console__dynamic-context"><div class="intelligence-console__context-heading"><div><span>${typeLabels[type]}</span><small>${type === 'companies' ? 'Compare company and workforce signals' : 'Explore hiring demand by role and market'}</small></div><span class="intelligence-console__context-state"><i></i>Context synced</span></div><div class="intelligence-console__context-grid"><label><span>${type === 'companies' ? 'Company' : 'Role'}</span><select id="entityContextSelect">${optionMarkup(options, selected || options[0])}</select></label><label><span>Market</span><select id="skillLocationSelect">${optionMarkup(marketOptions, dashboardState.market)}</select></label><div class="intelligence-console__context-summary"><span>Analysis scope</span><strong>${type === 'companies' ? 'Company signals' : 'Role demand'}</strong></div></div></div>`;
  const scopedOptions = intelligenceExplorerState.scope === 'Saved' ? options.filter(option => saved.includes(option)) : options;
  const isSaved = !!selected && saved.includes(selected);
  const skillForEntity = type === 'technologies' ? ({ AI: 'AI', 'Cloud Computing': 'Cloud Computing', 'Generative AI': 'Generative AI', Automation: 'Machine Learning', Cybersecurity: 'Cybersecurity', 'Developer Tools': 'JavaScript' }[selected] || selected) : selected;
  const skillDetails = ['skills', 'technologies'].includes(type) && selected ? trendDetailsForSkill(skillForEntity) : null;
  const assessment = skillDetails ? skillAssessmentFor(skillForEntity, skillDetails) : null;
  const company = type === 'companies' && selected ? getMarketTrendView(selected) : null;
  const role = type === 'roles' && selected ? jobTrendData[selected] || jobTrendData['All Roles'] : null;
  const market = type === 'markets' && selected ? marketTrendData[selected] || marketTrendData.Global : null;
  const direction = values => values.at(-1) > values.at(-2) ? 'Growing' : values.at(-1) < values.at(-2) ? 'Declining' : 'Stable';
  const directionIcon = value => value === 'Growing' ? 'trending-up' : value === 'Declining' ? 'trending-down' : 'minus';
  const directionClass = value => value === 'Growing' ? 'is-growing' : value === 'Declining' ? 'is-declining' : 'is-stable';
  const change = skillDetails ? Number((((skillDetails.current - skillDetails.values[0]) / Math.max(1, skillDetails.values[0])) * 100).toFixed(1)) : company?.change ?? role?.changePercentage ?? market?.momentum - 70 ?? 0;
  const currentDirection = skillDetails ? direction(skillDetails.values) : company?.trend || role?.direction || (market ? direction(market.technologyMomentum) : 'Stable');
  const entityName = selected || 'your selection';
  const resultMetrics = !selected ? [] : type === 'skills' ? [
    ['Current relevance', `${assessment.score} / 100`], ['Market demand', skillDetails.demand], ['Growth direction', `${change > 0 ? '+' : ''}${change}%`], ['Future demand', `+${selected === 'Machine Learning' ? 18 : skillDetails.growth}%`], ['Skill health', assessment.score >= 80 ? 'Strong' : assessment.score >= 60 ? 'Building' : 'Developing'], ['Related roles', 'AI / ML Engineer  —  Data Scientist']
  ] : type === 'companies' ? [
    ['Company momentum', `${Math.round(company.momentum)} / 100`], ['Market trend', `${company.change > 0 ? '+' : ''}${company.change.toFixed(1)}%`], ['Hiring activity', `${Math.round(company.jobDemand.at(-1))} / 100`], ['Relevant jobs', `${companyVacancies[company.name] || 0}`], ['Technology signal', `${Math.round(company.technologyMomentum.at(-1))} / 100`], ['Demanded skills', 'AI  —  Cloud  —  Data']
  ] : type === 'roles' ? [
    ['Current momentum', `${role.overallMomentum} / 100`], ['Market demand', role.direction], ['Future demand', `+${role.changePercentage}%`], ['Hiring activity', `${role.hiringMomentum.value} / 100`], ['Skill demand', `${role.skillDemand.value} / 100`], ['Related skill', dashboardState.selectedSkill]
  ] : type === 'markets' ? [
    ['Skill demand', `${market.technologyMomentum.at(-1)} / 100`], ['Technology momentum', `${market.momentum} / 100`], ['Job demand', `${market.jobDemand.at(-1)} / 100`], ['Company activity', `${market.investmentSignal.at(-1)} / 100`], ['Emerging skills', 'AI  —  Cloud  —  Data'], ['Relevant opportunities', `${getJobSummary().toLocaleString()}`]
  ] : [
    ['Current relevance', `${skillDetails?.current || 0} / 100`], ['Market demand', skillDetails?.demand || 'Building demand'], ['Growth direction', `${change > 0 ? '+' : ''}${change}%`], ['Future demand', `+${skillDetails?.growth || 0}%`], ['Technology signal', 'Accelerating'], ['Related roles', 'AI Engineer  —  Software Engineer']
  ];
  const evidenceTarget = type === 'skills' || type === 'technologies' ? 'current-skill-intelligence' : type === 'roles' ? 'live-market-intelligence' : 'live-market-intelligence';
  const detailsHref = type === 'skills' || type === 'technologies' ? '#/individual/skills' : type === 'roles' ? '#/individual/career' : type === 'companies' ? '#/individual/market-insights' : '#/individual/market-insights';
  const explanation = type === 'skills' ? `${entityName} is showing ${skillDetails?.demand?.toLowerCase() || 'market movement'} in the selected market. That makes current skill health and applied practice useful signals for your next move.` : type === 'companies' ? `${entityName} is showing ${company?.trend?.toLowerCase() || 'market'} momentum across technology, investment and hiring signals.` : type === 'roles' ? `${entityName} connects your current skill profile to hiring demand and the capabilities employers are emphasizing.` : type === 'markets' ? `${entityName} is a useful lens for comparing technology momentum, job demand and company activity around your career direction.` : `${entityName} is a technology signal connected to the skills and roles you are exploring.`;
  const recommendation = type === 'skills' || type === 'technologies' ? `Strengthen ${skillForEntity} fundamentals and build one applied project that demonstrates your capability.` : type === 'companies' ? `Compare ${company.name}'s demanded skills with your profile, then choose one capability to strengthen.` : type === 'roles' ? `Map the core skills for ${entityName} and build a small project that demonstrates them.` : `Use ${entityName} market signals to prioritize one skill and one role to investigate next.`;
  const values = skillDetails?.values || company?.technologyMomentum || (role ? [role.jobDemand.value, role.skillDemand.value, role.overallMomentum] : market?.technologyMomentum || [42, 48, 56, 63, 72]);
  const emptyState = `<div class="intelligence-console__empty"><div class="intelligence-console__orbit"><span></span><span></span><span></span><i data-lucide="scan-search"></i></div><strong>Search a skill, company, role or market...</strong><small>Choose an investigation type, then enter an entity to reveal contextual intelligence.</small><div class="intelligence-console__scan-line"></div></div>`;
  const resultState = !intelligenceExplorerState.hasSearched || !selected ? emptyState : `<div class="intelligence-console__result"><header class="intelligence-console__result-header"><div><span class="section-kicker">${typeLabels[type].toUpperCase()} INVESTIGATION</span><h3>${entityName}</h3><p>Contextual intelligence for ${user.name}  —  ${type === 'markets' ? 'market view' : dashboardState.market}</p></div><div class="intelligence-console__result-actions"><button type="button" class="explore-intelligence__save ${isSaved ? 'is-saved' : ''}" id="saveExploreIntelligence" ${isSaved ? 'disabled' : ''}><i data-lucide="${isSaved ? 'check' : 'bookmark-plus'}"></i>${isSaved ? 'Saved' : 'Save / Favourite'}</button><a class="intelligence-console__detail-link" href="${detailsHref}">Explore Details <i data-lucide="arrow-up-right"></i></a></div></header><div class="intelligence-console__blocks"><article class="intelligence-console__block intelligence-console__block--change"><span>01  —  WHAT CHANGED?</span><strong>${currentDirection} signal</strong><p>${entityName} has ${currentDirection === 'Growing' ? 'gained momentum' : currentDirection === 'Declining' ? 'lost momentum' : 'remained steady'} across the selected view.</p><b class="${directionClass(currentDirection)}"><i data-lucide="${directionIcon(currentDirection)}"></i>${currentDirection}  —  ${change > 0 ? '+' : ''}${change.toFixed(1)}%</b></article><article class="intelligence-console__block intelligence-console__block--why"><span>02  —  WHY IT MATTERS</span><strong>Relevant to your next move</strong><p>${explanation}</p><div class="intelligence-console__tags"><em>${user.role}</em><em>${dashboardState.selectedSkill}</em></div></article><article class="intelligence-console__block intelligence-console__block--data"><span>03  —  WHAT THE DATA SHOWS</span><div class="intelligence-console__metrics">${resultMetrics.map(([label, value], index) => `<div style="--metric-delay:${index * 45}ms"><small>${label}</small><b>${value}</b></div>`).join('')}</div>${renderOverviewSparkline(values, `${entityName} illustrative signal trend`)}<a href="#${evidenceTarget}" id="viewIntelligenceEvidence"><i data-lucide="file-search-2"></i>View Evidence / Sources</a></article><article class="intelligence-console__block intelligence-console__block--action"><span>04  —  WHAT SHOULD I DO?</span><strong>Recommended next action</strong><p>${recommendation}</p><div class="intelligence-console__action-row">${roadmapState.status === 'active' || roadmapState.status === 'paused' ? `<a class="intelligence-console__primary-action" href="#active-learning-roadmap">View Roadmap <i data-lucide="arrow-right"></i></a>` : `<button class="intelligence-console__primary-action" type="button" data-roadmap-accept>Build Roadmap <i data-lucide="map"></i></button>`}<a class="intelligence-console__secondary-action" href="${detailsHref}">Explore Details</a></div></article></div><p class="intelligence-console__disclaimer">Illustrative prototype intelligence  —  connect verified market and evidence APIs for production use.</p></div>`;
  return `<section class="explore-intelligence intelligence-console" aria-labelledby="explore-intelligence-title"><header class="explore-intelligence__heading"><div><span class="section-kicker">AI-powered investigation</span><h2 id="explore-intelligence-title">Your Intelligence Console</h2><p>Explore a skill, company, role or market and understand what is changing, why it matters and what you can do next.</p></div><span class="explore-intelligence__prototype"><i></i>Illustrative intelligence</span></header><div class="explore-intelligence__card"><div class="explore-intelligence__controls"><div class="explore-intelligence__tabs" role="tablist" aria-label="Intelligence type">${Object.entries(typeLabels).map(([key, label]) => `<button type="button" role="tab" aria-selected="${key === type}" class="${key === type ? 'is-active' : ''}" data-explore-type="${key}">${label}</button>`).join('')}</div><label class="explore-intelligence__search"><span>Investigation target</span><span class="explore-intelligence__input-wrap"><i data-lucide="search"></i><input id="exploreIntelligenceInput" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" list="explore-${type}-options" value="${selected}" placeholder="Search a skill, company, role or market..." autocomplete="off"><i class="explore-intelligence__chevron" data-lucide="chevron-down"></i></span><datalist id="explore-${type}-options">${scopedOptions.map(option => `<option value="${option}"></option>`).join('')}</datalist></label><div class="explore-intelligence__scope" role="group" aria-label="Intelligence scope">${['Global', 'My Market', 'Saved'].map(scope => `<button type="button" aria-pressed="${scope === intelligenceExplorerState.scope}" class="${scope === intelligenceExplorerState.scope ? 'is-active' : ''}" data-explore-scope="${scope}">${scope}</button>`).join('')}</div></div><div class="intelligence-console__result-area" aria-live="polite">${resultState}</div></div></section>`;
};

renderExploreFocusSelector = function() {
  const typeLabels = { skills: 'Skill Intelligence', companies: 'Market Intelligence', roles: 'Job Intelligence' };
  const lists = { skills: skillOptions, companies: marketCompanyData.map(company => company.name), roles: jobRoleOptions };
  const type = intelligenceExplorerState.type;
  const selected = intelligenceExplorerState.selected[type] || '';
  const options = lists[type] || skillOptions;
  const savedItems = type === 'skills' || type === 'technologies' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : type === 'companies' ? intelligenceExplorerState.favoriteCompanies : type === 'markets' ? savedMarkets : dashboardState.savedCompanies;
  const saved = savedItems;
  const selectedSkillItems = intelligenceExplorerState.selectedSkills.length ? intelligenceExplorerState.selectedSkills : (dashboardState.savedSkills.length ? dashboardState.savedSkills.slice(0, 5) : [dashboardState.selectedSkill]);
  const skillScopeOptions = ['All Skills', 'My Skills', 'Favorite Skills'];
  const skillQuestions = intelligenceExplorerState.skillScope === 'All Skills' ? ['What skills are trending globally?', 'Which skills are growing fastest?', 'What are the top emerging skills?', 'Which skills are declining?'] : intelligenceExplorerState.skillScope === 'Favorite Skills' ? ['How are my favorite skills trending?', 'Which favorite skill has the strongest future relevance?', 'Which skill is losing demand?', 'What should I learn next?'] : ['How relevant are my current skills?', 'Which of my skills are growing?', 'Where are my biggest skill gaps?', 'Which skill should I strengthen first?'];
  const focusCompany = intelligenceExplorerState.selectedCompanies[0] || intelligenceExplorerState.favoriteCompanies[0] || options[0] || 'a company';
  const questionChips = type === 'skills' ? (intelligenceExplorerState.selectedSkills.length === 1 ? ['What is ' + intelligenceExplorerState.selectedSkills[0] + ' demand in ' + intelligenceExplorerState.market + '?', 'Is ' + intelligenceExplorerState.selectedSkills[0] + ' still growing?', 'Which skills are paired with ' + intelligenceExplorerState.selectedSkills[0] + '?', 'Which ' + intelligenceExplorerState.selectedSkills[0] + ' roles are growing?'] : skillQuestions) : type === 'companies' ? ['Which companies are growing fastest?', 'What technologies is ' + focusCompany + ' investing in?', 'Which companies are hiring the most?', 'What products are gaining market momentum?', 'Which companies are showing strong investment signals?', 'Which technologies are growing in ' + intelligenceExplorerState.market + '?', 'What is changing in this market?'] : ['Which companies are hiring the most?', 'What roles is ' + focusCompany + ' hiring for?', 'What skills are companies asking for?', 'Which companies are hiring for my skills?', 'What technologies appear most in job postings?', 'What roles are emerging?', 'Where are hiring opportunities growing?'];
  const marketLocations = ['Global', 'India', 'US', 'UK', 'Europe', 'Asia-Pacific', ...(!['Global','India','US','UK','Europe','Asia-Pacific'].includes(intelligenceExplorerState.market) ? [intelligenceExplorerState.market] : []), 'Custom location'];
  const companyContext = (jobMode) => { const scope = jobMode ? intelligenceExplorerState.jobScope : intelligenceExplorerState.companyScope; const scopeId = jobMode ? 'jobScopeSelect' : 'companyScopeSelect'; const scopeOptions = jobMode ? ['All Companies','Favorite Companies','Selected Companies'] : ['All Companies','Favorite Companies','My Companies / Followed Companies']; const companies = scope === 'All Companies' ? options : scope === 'My Companies / Followed Companies' ? dashboardState.savedCompanies : jobMode && scope === 'Selected Companies' ? intelligenceExplorerState.selectedCompanies : intelligenceExplorerState.favoriteCompanies; const signals = jobMode ? ['Vacancies','Hiring','Roles','Skills','Technology','Projects','Tasks','Layoffs','Workforce Growth'] : ['Technology','Investment','Stock','Products','Skills','Jobs','Company Growth','Market Demand']; const selectedSignals = jobMode ? intelligenceExplorerState.jobSignals : intelligenceExplorerState.companySignals; const categoryKey = jobMode ? 'jobSignals' : 'companySignals'; return `<div class="intelligence-console__dynamic-context"><div class="intelligence-console__context-heading"><div><span>${jobMode ? 'Job Intelligence' : 'Market Intelligence'}</span><small>${jobMode ? 'Set company and hiring signals to investigate' : 'Set company and market signals to investigate'}</small></div><span class="intelligence-console__context-state"><i></i>Context synced</span></div><div class="intelligence-console__context-grid intelligence-console__context-grid--company"><label><span>${jobMode ? 'Job Scope' : 'Market Scope'}</span><select id="${scopeId}">${scopeOptions.map(item => `<option ${item === scope ? 'selected' : ''}>${item}</option>`).join('')}</select></label><div class="intelligence-console__context-skills"><span>${scope === 'All Companies' ? 'Companies' : scope === 'Favorite Companies' ? 'Favorite Companies' : 'Selected Companies'}</span><div>${companies.map(company => `<button type="button" class="intelligence-console__skill-chip ${intelligenceExplorerState.selectedCompanies.includes(company) ? 'is-selected' : ''}" data-company-chip="${company}" aria-pressed="${intelligenceExplorerState.selectedCompanies.includes(company)}">${company}<i data-lucide="${scope === 'Favorite Companies' ? 'x' : 'check'}"></i></button>`).join('')}<button type="button" class="intelligence-console__add-skill" id="addCompanyButton"><i data-lucide="plus"></i>Add Company</button></div><div class="intelligence-console__skill-picker" id="companyPicker" hidden><input id="companySearch" type="search" placeholder="Search companies..." aria-label="Search companies"><div>${options.filter(company => !intelligenceExplorerState.favoriteCompanies.includes(company)).map(company => `<button type="button" data-add-company="${company}">${company}<i data-lucide="plus"></i></button>`).join('')}</div></div></div><label><span>${jobMode ? 'Job Market' : 'Market'}</span><select id="skillLocationSelect">${optionMarkup(marketLocations, intelligenceExplorerState.market)}</select></label><div class="intelligence-console__signal-picker"><span>${jobMode ? 'Hiring signals' : 'Investigate'}</span><div>${signals.map(signal => `<button type="button" class="${selectedSignals.includes(signal) ? 'is-selected' : ''}" aria-pressed="${selectedSignals.includes(signal)}" data-signal-key="${categoryKey}" data-signal="${signal}">${signal}</button>`).join('')}</div></div></div></div>`; };
  const contextMarkup = type === 'skills' ? `<div class="intelligence-console__dynamic-context"><div class="intelligence-console__context-heading"><div><span>Skill Intelligence</span><small>Set the skills and market to analyze</small></div><span class="intelligence-console__context-state"><i></i>Context synced</span></div><div class="intelligence-console__context-grid"><label><span>Skill Scope</span><select id="skillScopeSelect">${skillScopeOptions.map(option => `<option ${option === intelligenceExplorerState.skillScope ? 'selected' : ''}>${option}</option>`).join('')}</select></label><div class="intelligence-console__context-skills"><span>Skills</span><div>${intelligenceExplorerState.skillScope === 'All Skills' ? '<em class="is-muted">All Skills market</em>' : (intelligenceExplorerState.skillScope === 'Favorite Skills' ? intelligenceExplorerState.favoriteSkills : selectedSkillItems).map(skill => `<button type="button" class="intelligence-console__skill-chip ${intelligenceExplorerState.selectedSkills.includes(skill) ? 'is-selected' : ''}" data-context-skill="${skill}" aria-pressed="${intelligenceExplorerState.selectedSkills.includes(skill)}">${skill}<i data-lucide="${intelligenceExplorerState.skillScope === 'Favorite Skills' ? 'x' : 'check'}"></i></button>`).join('')} ${intelligenceExplorerState.skillScope !== 'All Skills' ? '<button type="button" class="intelligence-console__add-skill" id="addFavoriteSkill"><i data-lucide="plus"></i>Add skill</button>' : ''}</div><div class="intelligence-console__skill-picker" id="favoriteSkillPicker" hidden><input id="favoriteSkillSearch" type="search" placeholder="Search skills..." aria-label="Search skills"><div>${skillOptions.filter(skill => !intelligenceExplorerState.favoriteSkills.includes(skill)).map(skill => `<button type="button" data-add-skill="${skill}">${skill}<i data-lucide="plus"></i></button>`).join('')}</div></div></div><label><span>Market</span><select id="skillLocationSelect">${optionMarkup(marketLocations, intelligenceExplorerState.market)}</select></label></div></div>` : companyContext(type === 'roles');
  const directionIcon = value => (value === 'Growing' || value === 'Increasing' || value === 'Rising') ? 'trending-up' : value === 'Declining' ? 'trending-down' : 'minus';
  const directionClass = value => (value === 'Growing' || value === 'Increasing' || value === 'Rising') ? 'is-growing' : value === 'Declining' ? 'is-declining' : 'is-stable';

  const apiRes = intelligenceExplorerState.apiResponse;
  const entity = selected || (type === 'skills' ? (intelligenceExplorerState.selectedSkills[0] || 'Python') : type === 'companies' ? (intelligenceExplorerState.selectedCompanies[0] || 'Microsoft') : 'AI Engineer');
  const matchingTrend = apiRes?.historical_trends?.find(t => t.entity_name?.toLowerCase() === entity.toLowerCase() || t.entity_id?.toLowerCase() === entity.toLowerCase().replace(/\s+/g, '_')) || apiRes?.historical_trends?.[0];
  const isTrendReady = Boolean(matchingTrend ? matchingTrend.is_trend_ready : apiRes?.is_trend_ready);

  let currentDirection = isTrendReady ? (matchingTrend?.trend_direction || 'Increasing') : 'Insufficient Data';
  let change = (isTrendReady && matchingTrend && matchingTrend.growth_pct != null) ? matchingTrend.growth_pct : null;
  let formattedChange = change != null ? `${change > 0 ? '+' : ''}${change.toFixed(1)}%` : '—';
  let velocityStr = (isTrendReady && matchingTrend?.formatted_velocity) ? matchingTrend.formatted_velocity : '—';

  let statusTitle = isTrendReady ? `${currentDirection} signal` : 'Insufficient Data signal';
  let statusDesc = isTrendReady
    ? `${entity} has ${currentDirection === 'Increasing' || currentDirection === 'Rising' || currentDirection === 'Growing' ? 'gained momentum' : currentDirection === 'Declining' ? 'lost momentum' : 'held steady'} across verified ${matchingTrend?.signal_badge || 'market signals'}.`
    : `${entity} does not have enough consecutive historical periods to calculate a verified trend or velocity. Minimum 2 consecutive valid periods required by G1.8 quality rules.`;

  let directionBadge = isTrendReady
    ? `<b class="${directionClass(currentDirection)}"><i data-lucide="${directionIcon(currentDirection)}"></i>${currentDirection} — ${formattedChange} (Velocity: ${velocityStr})</b>`
    : `<b class="is-stable"><i data-lucide="minus"></i>Insufficient Data — Trend blocked (0 ready series)</b>`;

  let explanation = apiRes?.explanations?.[0]?.body
    || (isTrendReady
      ? `${entity} is demonstrating measurable ${currentDirection.toLowerCase()} activity across observed platform periods. This informs strategic readiness without speculative forecasting.`
      : `Verified observations for ${entity} are passing through G1.8 and G1.9 readiness gates. Genuine recurring collection is accumulating history; no synthetic values are permitted.`);

  let recommendation = apiRes?.recommendations?.[0]?.description
    || apiRes?.recommendations?.[0]?.rationale
    || (isTrendReady
      ? `Strengthen core capabilities in ${entity} and build demonstrated work evidence while market momentum remains favorable.`
      : `Monitor verified signals for ${entity} as new periods accumulate through automated collection.`);

  let resultMetrics = apiRes ? [
    ['Signal source', matchingTrend ? matchingTrend.source : (apiRes.data_origin || 'real')],
    ['Signal type', matchingTrend ? matchingTrend.signal_badge : (type === 'skills' ? 'Skill Demand' : type === 'companies' ? 'Market Signals' : 'Job Demand')],
    ['Data state', apiRes.data_state ? apiRes.data_state.replace('_', ' ') : 'insufficient data'],
    ['Trend readiness', isTrendReady ? 'Ready (5 periods)' : 'Insufficient Data (< 2 periods)'],
    ['Forecast ready', 'False (G2.0 Foundation)'],
    ['Assessed series', `${apiRes.readiness?.ready_for_trend_count ?? (isTrendReady ? 1 : 0)} ready / ${apiRes.readiness?.total_series_assessed ?? 1} total`]
  ] : [
    ['Signal status', 'Awaiting query execution'],
    ['Data origin', 'real platform observations'],
    ['Trend readiness', 'Evaluated deterministically via G1.9'],
    ['Forecast state', 'Blocked (0 series eligible)'],
    ['Target', entity],
    ['Context', typeLabels[type]]
  ];

  const targetId = type === 'skills' ? 'current-skill-intelligence' : 'live-market-intelligence';
  const detailsHref = type === 'skills' ? '#/individual/skills' : type === 'roles' ? '#/individual/career' : '#/individual/market-insights';
  const isSaved = !!selected && savedItems.includes(selected);

  const sparklineValues = (matchingTrend && matchingTrend.data_points && matchingTrend.data_points.length > 1)
    ? matchingTrend.data_points.map(p => Number(p.value) || 0)
    : null;

  const sparklineMarkup = sparklineValues
    ? renderOverviewSparkline(sparklineValues, `${entity} verified multi-period trend`)
    : `<div class="intelligence-console__no-chart" style="margin: 8px 0; font-size: 12px; color: var(--text-muted);"><i data-lucide="info"></i> Single-period baseline (${matchingTrend?.periods?.[0] || '2026-10'}); multi-period slope blocked until genuine backfill completes.</div>`;

  const analysisSteps = type === 'companies'
    ? ["Querying Core Intelligence API...", "Scanning company market signals...", "Applying G1.8 quality gates...", "Evaluating G1.9 readiness...", "Compiling verified response..."]
    : type === 'roles'
      ? ["Querying Core Intelligence API...", "Checking role demand signals...", "Evaluating G1.8 validation gates...", "Checking multi-period readiness...", "Compiling verified response..."]
      : ["Querying Core Intelligence API...", "Checking skill demand & interest signals...", "Validating observation series...", "Evaluating Theil-Sen trend readiness...", "Compiling verified response..."];

  const analysisState = `<div class="intelligence-console__analysis"><div class="intelligence-console__analysis-orb"><i data-lucide="scan-search"></i><span></span><span></span><span></span></div><strong>${analysisSteps[intelligenceExplorerState.analysisStep] || analysisSteps[0]}</strong><small>Connecting ${typeLabels[type].toLowerCase()} signals to authenticated profile.</small><div class="intelligence-console__analysis-track"><i style="width:${Math.min(100, (intelligenceExplorerState.analysisStep + 1) / analysisSteps.length * 100)}%"></i></div><div class="intelligence-console__analysis-steps">${analysisSteps.map((step, index) => `<span class="${index <= intelligenceExplorerState.analysisStep ? "is-active" : ""}"><i></i>${step}</span>`).join("")}</div></div>`;

  const emptyState = `<div class="intelligence-console__empty"><div class="intelligence-console__orbit"><span></span><span></span><span></span><i data-lucide="scan-search"></i></div><strong>What would you like to understand?</strong><small>Explore live skill, market and job intelligence through one unified AI workspace.</small><div class="intelligence-console__scan-line"></div></div>`;

  const result = intelligenceExplorerState.isAnalyzing
    ? analysisState
    : !intelligenceExplorerState.hasSearched || !selected
      ? emptyState
      : `<div class="intelligence-console__result">
          ${intelligenceExplorerState.apiError ? `<div role="alert" style="background:#FFF0F0; border:1px solid #FFD0D0; border-radius:8px; padding:10px 14px; margin-bottom:12px; color:#C00; font-size:13px; display:flex; align-items:center; gap:8px;"><i data-lucide="alert-triangle"></i><span>${esc(intelligenceExplorerState.apiError)}</span></div>` : ''}
          <header class="intelligence-console__result-header">
            <div>
              <span class="section-kicker">${typeLabels[type]} analysis</span>
              <h3>${entity}</h3>
              <p>Verified intelligence for ${user.name} — ${type === 'markets' ? selected : dashboardState.market}</p>
            </div>
            <div class="intelligence-console__result-actions">
              <button type="button" class="explore-intelligence__save ${isSaved ? 'is-saved' : ''}" id="saveExploreIntelligence" ${isSaved ? 'disabled' : ''}>
                <i data-lucide="${isSaved ? 'check' : 'bookmark-plus'}"></i>${isSaved ? 'Saved' : 'Save to intelligence'}
              </button>
              <a class="intelligence-console__detail-link" href="${detailsHref}">Explore details <i data-lucide="arrow-up-right"></i></a>
            </div>
          </header>
          <div class="intelligence-console__blocks">
            <article class="intelligence-console__block intelligence-console__block--change">
              <span>01 — WHAT CHANGED?</span>
              <strong>${statusTitle}</strong>
              <p>${statusDesc}</p>
              ${directionBadge}
            </article>
            <article class="intelligence-console__block intelligence-console__block--why">
              <span>02 — WHY IT MATTERS</span>
              <strong>Relevant to your next move</strong>
              <p>${explanation}</p>
              <div class="intelligence-console__tags">
                <em>${user.role}</em>
                <em>${entity}</em>
              </div>
            </article>
            <article class="intelligence-console__block intelligence-console__block--data">
              <span>03 — WHAT THE DATA SHOWS</span>
              <div class="intelligence-console__metrics">
                ${resultMetrics.map(([label, value], index) => `<div style="--metric-delay:${index * 45}ms"><small>${label}</small><b>${value}</b></div>`).join('')}
              </div>
              ${sparklineMarkup}
              <a href="#${targetId}" id="viewIntelligenceEvidence"><i data-lucide="file-search-2"></i>View evidence and sources</a>
            </article>
            <article class="intelligence-console__block intelligence-console__block--action">
              <span>04 — WHAT SHOULD I DO?</span>
              <strong>Recommended next action</strong>
              <p>${recommendation}</p>
              <div class="intelligence-console__action-row">
                ${roadmapState.status === 'active' || roadmapState.status === 'paused' ? `<a class="intelligence-console__primary-action" href="#active-learning-roadmap">Continue roadmap <i data-lucide="arrow-right"></i></a>` : `<button class="intelligence-console__primary-action" type="button" data-roadmap-accept>Build roadmap <i data-lucide="map"></i></button>`}
                <a class="intelligence-console__secondary-action" href="${detailsHref}">Explore details</a>
              </div>
            </article>
          </div>
          <p class="intelligence-console__disclaimer">Verified Core Intelligence Engine (G2.0) — Real provider observations with G1.8 quality and G1.9 readiness gates. Zero synthetic or simulated data.</p>
        </div>`;
  return `<section class="explore-intelligence intelligence-console" aria-labelledby="explore-intelligence-title"><header class="explore-intelligence__heading"><div><span class="section-kicker">AI-powered investigation</span><h2 id="explore-intelligence-title">Your Intelligence Console</h2><p>Explore a skill, company, role or market and understand what is changing, why it matters and what you can do next.</p></div><span class="explore-intelligence__prototype"><i></i>Verified intelligence workspace</span></header><div class="explore-intelligence__card"><div class="intelligence-console__workspace"><aside class="intelligence-console__rail"><div class="intelligence-console__rail-heading"><span>Intelligence</span><small>Choose an analysis domain</small></div><div class="intelligence-console__type-list" role="tablist" aria-label="Intelligence type">${Object.entries(typeLabels).map(([key, label]) => `<button type="button" role="tab" aria-selected="${key === type}" class="${key === type ? 'is-active' : ''}" data-explore-type="${key}"><i data-lucide="${key === 'skills' ? 'brain-circuit' : key === 'companies' ? 'building-2' : 'briefcase-business'}"></i>${label}</button>`).join('')}</div><div class="intelligence-console__rail-divider"></div><div class="intelligence-console__rail-status"><i></i><span>Analysis layer ready</span><small>Signals update as context changes</small></div></aside><main class="intelligence-console__main">${contextMarkup}<div class="intelligence-console__prompt"><div class="intelligence-console__prompt-top"><span class="intelligence-console__prompt-icon"><i data-lucide="sparkles"></i></span><div><span>What would you like to understand?</span><small>Natural-language investigation</small></div><span class="intelligence-console__live"><i></i>Verified signals</span></div><div class="intelligence-console__prompt-input"><textarea id="exploreIntelligenceInput" placeholder="Ask anything about your selected intelligence..." autocomplete="off">${intelligenceExplorerState.question}</textarea><button type="button" id="runIntelligenceButton" aria-label="Run intelligence analysis" title="Run intelligence analysis"><i data-lucide="arrow-up"></i></button><datalist id="explore-${type}-options">${options.map(option => `<option value="${option}"></option>`).join('')}</datalist></div><div class="intelligence-console__suggestions"><span>Suggested questions</span>${questionChips.map(question => `<button type="button" data-console-suggestion="${question}">${question}</button>`).join('')}</div></div><div class="intelligence-console__context-bar"><span><i data-lucide="layers-3"></i>${typeLabels[type]}</span><span><i data-lucide="map-pin"></i>${intelligenceExplorerState.market}</span><span><i data-lucide="building-2"></i>${intelligenceExplorerState.selectedCompanies.length ? intelligenceExplorerState.selectedCompanies.join(", ") : type === 'skills' ? intelligenceExplorerState.skillScope : type === 'companies' ? intelligenceExplorerState.companyScope : intelligenceExplorerState.jobScope}</span><span class="intelligence-console__context-ready"><i></i>Context synced</span></div><div class="intelligence-console__result-area" aria-live="polite">${result}</div></main></div></div></section>`;
};

function applyExploreSelection() {
  const { type, scope } = intelligenceExplorerState;
  const selected = intelligenceExplorerState.selected[type];
  const location = intelligenceExplorerState.market || (scope === 'My Market' ? (dashboardState.market === 'Global' ? user.location : dashboardState.market) : scope === 'Saved' ? dashboardState.market : 'Global');
  marketTrendState.scope = location;
  jobTrendState.market = location;
  if (type === 'skills') {
    dashboardState.selectedSkill = selected || 'Machine Learning';
    dashboardState.trendScope = scope === 'Saved' ? 'My Saved Skills' : 'Overall Live Trends';
    dashboardState.market = location;
    marketTrendState.company = '';
    marketTrendState.view = 'Market Overview';
  } else if (type === 'roles') {
    jobTrendState.role = selected || 'All Roles';
    jobTrendState.roleScope = scope === 'Saved' ? 'Saved Roles' : 'All Roles';
    jobTrendState.market = location;
    const relatedSkill = { 'AI / ML Engineer': 'Machine Learning', 'AI Engineer': 'Machine Learning', 'Software Engineer': 'JavaScript', 'Data Scientist': 'Data Analytics', 'Data Analyst': 'SQL', 'UI/UX Designer': 'React', 'Cybersecurity Engineer': 'Cybersecurity', 'Cloud Engineer': 'Cloud Computing' }[selected];
    if (relatedSkill) dashboardState.selectedSkill = relatedSkill;
  } else if (type === 'companies') {
    marketTrendState.company = selected || '';
    marketTrendState.view = selected ? 'Individual Company' : 'Market Overview';
    marketTrendState.watchlist = scope === 'Saved' ? 'Saved Companies' : 'All Companies';
    marketTrendState.scope = location;
    dashboardState.market = location;
  } else if (type === 'technologies') {
    const relatedSkill = { AI: 'AI', 'Cloud Computing': 'Cloud Computing', 'Generative AI': 'Generative AI', Automation: 'Machine Learning', Cybersecurity: 'Cybersecurity', 'Developer Tools': 'JavaScript' }[selected];
    if (relatedSkill) dashboardState.selectedSkill = relatedSkill;
    dashboardState.market = location;
    marketTrendState.company = '';
    marketTrendState.view = 'Market Overview';
  } else if (type === 'markets') {
    dashboardState.market = selected || location;
    marketTrendState.scope = selected || location;
    jobTrendState.market = selected || location;
  }
}

function bindExploreIntelligenceEvents() {
  document.querySelectorAll('[data-explore-type]').forEach(button => button.addEventListener('click', () => {
    intelligenceExplorerState.type = button.dataset.exploreType;
    intelligenceExplorerState.showWhy = false;
    const list = intelligenceExplorerState.type === 'skills' ? skillOptions : intelligenceExplorerState.type === 'roles' ? jobRoleOptions : marketCompanyData.map(company => company.name);
    const saved = intelligenceExplorerState.type === 'skills' ? dashboardState.savedSkills : intelligenceExplorerState.type === 'roles' ? savedJobRoles : dashboardState.savedCompanies;
    const available = intelligenceExplorerState.scope === 'Saved' ? list.filter(item => saved.includes(item)) : list;
    if (!available.includes(intelligenceExplorerState.selected[intelligenceExplorerState.type])) intelligenceExplorerState.selected[intelligenceExplorerState.type] = available[0] || '';
    const previousValues = trendDetailsForSkill(dashboardState.selectedSkill).values;
    applyExploreSelection(); refreshExploreDashboard(previousValues);
  }));
  document.querySelectorAll('[data-explore-scope]').forEach(button => button.addEventListener('click', () => {
    intelligenceExplorerState.scope = button.dataset.exploreScope;
    const type = intelligenceExplorerState.type;
    const list = type === 'skills' ? skillOptions : type === 'roles' ? jobRoleOptions : marketCompanyData.map(company => company.name);
    const saved = type === 'skills' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : dashboardState.savedCompanies;
    const available = intelligenceExplorerState.scope === 'Saved' ? list.filter(item => saved.includes(item)) : list;
    if (!available.includes(intelligenceExplorerState.selected[type])) intelligenceExplorerState.selected[type] = available[0] || '';
    const previousValues = trendDetailsForSkill(dashboardState.selectedSkill).values;
    applyExploreSelection(); refreshExploreDashboard(previousValues);
  }));
  const input = document.querySelector('#exploreIntelligenceInput');
  if (input) {
    const commit = () => {
      const type = intelligenceExplorerState.type;
      const list = type === 'skills' ? skillOptions : type === 'roles' ? jobRoleOptions : marketCompanyData.map(company => company.name);
      const saved = type === 'skills' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : dashboardState.savedCompanies;
      const allowed = intelligenceExplorerState.scope === 'Saved' ? list.filter(item => saved.includes(item)) : list;
      const match = allowed.find(item => item.toLowerCase() === input.value.trim().toLowerCase());
      if (match) { const previousValues = trendDetailsForSkill(dashboardState.selectedSkill).values; intelligenceExplorerState.selected[type] = match; intelligenceExplorerState.showWhy = false; applyExploreSelection(); refreshExploreDashboard(previousValues); }
      else { input.value = intelligenceExplorerState.selected[type] || ''; input.setAttribute('aria-expanded', 'false'); }
    };
    input.addEventListener('change', commit);
    input.addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); commit(); } });
    input.addEventListener('focus', () => input.setAttribute('aria-expanded', 'true'));
    input.addEventListener('blur', () => input.setAttribute('aria-expanded', 'false'));
  }
  document.querySelector('#saveExploreIntelligence')?.addEventListener('click', () => {
    const type = intelligenceExplorerState.type, selected = intelligenceExplorerState.selected[type];
    if (!selected) return;
    if (type === 'skills' && !dashboardState.savedSkills.includes(selected) && dashboardState.savedSkills.length < 5) { dashboardState.savedSkills = [...dashboardState.savedSkills, selected]; localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills)); }
    if (type === 'roles' && !savedJobRoles.includes(selected)) { savedJobRoles = [...savedJobRoles, selected]; localStorage.setItem('talentscope-saved-roles', JSON.stringify(savedJobRoles)); }
    if (type === 'companies' && !dashboardState.savedCompanies.includes(selected)) { dashboardState.savedCompanies = [...dashboardState.savedCompanies, selected]; localStorage.setItem('talentscope-saved-companies', JSON.stringify(dashboardState.savedCompanies)); }
    refreshExploreDashboard();
  });
  document.querySelector('#whyIntelligenceButton')?.addEventListener('click', () => {
    intelligenceExplorerState.showWhy = !intelligenceExplorerState.showWhy;
    const note = document.querySelector('#intelligenceWhyCopy');
    note.hidden = !intelligenceExplorerState.showWhy;
    document.querySelector('#whyIntelligenceButton')?.setAttribute('aria-expanded', String(intelligenceExplorerState.showWhy));
  });
  document.querySelector('#viewIntelligenceEvidence')?.addEventListener('click', () => {
    const target = intelligenceExplorerState.type === 'skills' ? 'current-skill-intelligence' : intelligenceExplorerState.type === 'roles' ? 'live-market-intelligence' : 'trending-intelligence';
    document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

bindExploreIntelligenceEvents = function() {
  const lists = { skills: skillOptions, companies: marketCompanyData.map(company => company.name), roles: jobRoleOptions };
  const savedFor = type => type === 'skills' || type === 'technologies' ? dashboardState.savedSkills : type === 'roles' ? savedJobRoles : type === 'markets' ? savedMarkets : dashboardState.savedCompanies;
  const refresh = () => { applyExploreSelection(); refreshExploreDashboard(); };
  document.querySelector('#skillScopeSelect')?.addEventListener('change', event => { intelligenceExplorerState.skillScope = event.target.value; intelligenceExplorerState.selectedSkills = []; refresh(); });
  document.querySelector('#companyScopeSelect')?.addEventListener('change', event => { intelligenceExplorerState.companyScope = event.target.value; refresh(); });
  document.querySelector('#jobScopeSelect')?.addEventListener('change', event => { intelligenceExplorerState.jobScope = event.target.value; refresh(); });
  document.querySelectorAll('[data-company-chip]').forEach(button => button.addEventListener('click', () => {
    const company = button.dataset.companyChip; const scope = intelligenceExplorerState.type === 'roles' ? intelligenceExplorerState.jobScope : intelligenceExplorerState.companyScope;
    if (scope === 'Favorite Companies') { intelligenceExplorerState.favoriteCompanies = intelligenceExplorerState.favoriteCompanies.filter(item => item !== company); localStorage.setItem('talentscope-favorite-companies', JSON.stringify(intelligenceExplorerState.favoriteCompanies)); }
    else intelligenceExplorerState.selectedCompanies = intelligenceExplorerState.selectedCompanies.includes(company) ? intelligenceExplorerState.selectedCompanies.filter(item => item !== company) : [...intelligenceExplorerState.selectedCompanies, company];
    refresh();
  }));
  document.querySelector('#addCompanyButton')?.addEventListener('click', () => { const picker = document.querySelector('#companyPicker'); picker.hidden = !picker.hidden; document.querySelector('#companySearch')?.focus(); });
  document.querySelectorAll('[data-add-company]').forEach(button => button.addEventListener('click', () => { const company = button.dataset.addCompany; if (!intelligenceExplorerState.favoriteCompanies.includes(company)) intelligenceExplorerState.favoriteCompanies.push(company); if ((intelligenceExplorerState.type === 'roles' && intelligenceExplorerState.jobScope === 'Selected Companies') || (intelligenceExplorerState.type === 'companies' && intelligenceExplorerState.companyScope === 'My Companies / Followed Companies')) if (!intelligenceExplorerState.selectedCompanies.includes(company)) intelligenceExplorerState.selectedCompanies.push(company); localStorage.setItem('talentscope-favorite-companies', JSON.stringify(intelligenceExplorerState.favoriteCompanies)); refresh(); }));
  document.querySelector('#companySearch')?.addEventListener('input', event => { const query = event.target.value.toLowerCase(); document.querySelectorAll('[data-add-company]').forEach(button => { button.hidden = !button.dataset.addCompany.toLowerCase().includes(query); }); });
  document.querySelectorAll('[data-signal-key]').forEach(button => button.addEventListener('click', () => { const key = button.dataset.signalKey; intelligenceExplorerState[key] = intelligenceExplorerState[key].includes(button.dataset.signal) ? intelligenceExplorerState[key].filter(item => item !== button.dataset.signal) : [...intelligenceExplorerState[key], button.dataset.signal]; refresh(); }));
  document.querySelector('#skillLocationSelect')?.addEventListener('change', event => { intelligenceExplorerState.market = event.target.value === 'Custom location' ? (window.prompt('Enter a market location', intelligenceExplorerState.market === 'Global' ? '' : intelligenceExplorerState.market) || 'Global') : event.target.value; dashboardState.market = intelligenceExplorerState.market; refresh(); });
  document.querySelector('#entityContextSelect')?.addEventListener('change', event => { intelligenceExplorerState.selected[intelligenceExplorerState.type] = event.target.value; refresh(); });
  document.querySelectorAll('[data-context-skill]').forEach(button => button.addEventListener('click', () => {
    const skill = button.dataset.contextSkill;
    if (intelligenceExplorerState.skillScope === 'Favorite Skills') { intelligenceExplorerState.favoriteSkills = intelligenceExplorerState.favoriteSkills.filter(item => item !== skill); localStorage.setItem('talentscope-favorite-skills', JSON.stringify(intelligenceExplorerState.favoriteSkills)); }
    else intelligenceExplorerState.selectedSkills = intelligenceExplorerState.selectedSkills.includes(skill) ? intelligenceExplorerState.selectedSkills.filter(item => item !== skill) : [...intelligenceExplorerState.selectedSkills, skill];
    refresh();
  }));
  document.querySelector('#addFavoriteSkill')?.addEventListener('click', () => { const picker = document.querySelector('#favoriteSkillPicker'); picker.hidden = !picker.hidden; document.querySelector('#favoriteSkillSearch')?.focus(); });
  document.querySelectorAll('[data-add-skill]').forEach(button => button.addEventListener('click', () => { const skill = button.dataset.addSkill; if (!intelligenceExplorerState.favoriteSkills.includes(skill)) { intelligenceExplorerState.favoriteSkills.push(skill); localStorage.setItem('talentscope-favorite-skills', JSON.stringify(intelligenceExplorerState.favoriteSkills)); } if (intelligenceExplorerState.skillScope !== 'Favorite Skills') intelligenceExplorerState.selectedSkills.push(skill); refresh(); }));
  document.querySelector('#favoriteSkillSearch')?.addEventListener('input', event => { const query = event.target.value.toLowerCase(); document.querySelectorAll('[data-add-skill]').forEach(button => { button.hidden = !button.dataset.addSkill.toLowerCase().includes(query); }); });
  document.querySelectorAll('[data-explore-type]').forEach(button => button.addEventListener('click', () => {
    intelligenceExplorerState.type = button.dataset.exploreType;
    intelligenceExplorerState.selected[intelligenceExplorerState.type] = '';
    intelligenceExplorerState.hasSearched = false;
    refresh();
  }));
  document.querySelectorAll('[data-explore-scope]').forEach(button => button.addEventListener('click', () => {
    intelligenceExplorerState.scope = button.dataset.exploreScope;
    const type = intelligenceExplorerState.type;
    const available = button.dataset.exploreScope === 'Saved' ? lists[type].filter(item => savedFor(type).includes(item)) : lists[type];
    if (!available.includes(intelligenceExplorerState.selected[type])) intelligenceExplorerState.selected[type] = '';
    intelligenceExplorerState.hasSearched = false;
    refresh();
  }));
  const input = document.querySelector('#exploreIntelligenceInput');
  if (input) {
    const commit = async () => {
      const type = intelligenceExplorerState.type;
      const allowed = intelligenceExplorerState.scope === 'Saved' ? lists[type].filter(item => savedFor(type).includes(item)) : lists[type];
      const query = input.value.trim();
      intelligenceExplorerState.question = query;
      const match = allowed.find(item => item.toLowerCase() === query.toLowerCase()) || allowed.find(item => query.toLowerCase().includes(item.toLowerCase()));
      if (!match && !query) { input.value = intelligenceExplorerState.selected[type] || ''; return; }
      intelligenceExplorerState.selected[type] = match || allowed[0] || '';
      intelligenceExplorerState.hasSearched = true;
      intelligenceExplorerState.isAnalyzing = true;
      intelligenceExplorerState.analysisStep = 0;
      input.setAttribute('aria-expanded', 'false');
      refresh();
      window.clearInterval(intelligenceExplorerState.analysisTimer);
      let step = 0;
      intelligenceExplorerState.analysisTimer = window.setInterval(() => {
        step += 1;
        intelligenceExplorerState.analysisStep = Math.min(step, 4);
        refresh();
      }, 350);

      try {
        const domain = type === 'skills' ? 'skill' : type === 'companies' ? 'market' : 'job';
        const selectedEntity = intelligenceExplorerState.selected[type];
        const { queryCoreIntelligence } = await import('./src/api/core-intelligence-client.js');
        const response = await queryCoreIntelligence({
          portalType: 'individual',
          intelligenceType: domain,
          selectedSkills: type === 'skills' ? (selectedEntity ? [selectedEntity] : (intelligenceExplorerState.selectedSkills || [])) : [],
          selectedCompanies: type === 'companies' ? (selectedEntity ? [selectedEntity] : (intelligenceExplorerState.selectedCompanies || [])) : [],
          selectedRoles: type === 'roles' ? (selectedEntity ? [selectedEntity] : []) : [],
          location: intelligenceExplorerState.market || null,
          timeRange: intelligenceExplorerState.timeRange || '6m',
          query: query || null
        });
        intelligenceExplorerState.apiResponse = response;
        intelligenceExplorerState.apiError = null;
      } catch (err) {
        console.warn('Core intelligence query failed:', err);
        intelligenceExplorerState.apiError = err.message || 'Unable to load live core intelligence.';
      } finally {
        window.clearInterval(intelligenceExplorerState.analysisTimer);
        intelligenceExplorerState.isAnalyzing = false;
        refresh();
      }
    };
    input.addEventListener('change', commit);
    input.addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); commit(); } });
    input.addEventListener('focus', () => input.setAttribute('aria-expanded', 'true'));
    input.addEventListener('blur', () => input.setAttribute('aria-expanded', 'false'));
  }
  document.querySelector('#runIntelligenceButton')?.addEventListener('click', () => document.querySelector('#exploreIntelligenceInput')?.dispatchEvent(new Event('change', { bubbles: true })));
  document.querySelectorAll('[data-console-suggestion]').forEach(button => button.addEventListener('click', () => { const input = document.querySelector('#exploreIntelligenceInput'); if (!input) return; input.value = button.dataset.consoleSuggestion; intelligenceExplorerState.question = input.value; input.dispatchEvent(new Event('change', { bubbles: true })); }));
  document.querySelector('#saveExploreIntelligence')?.addEventListener('click', () => {
    const type = intelligenceExplorerState.type, selected = intelligenceExplorerState.selected[type];
    if (!selected) return;
    if (type === 'skills' || type === 'technologies') {
      if (!dashboardState.savedSkills.includes(selected) && dashboardState.savedSkills.length < 5) dashboardState.savedSkills = [...dashboardState.savedSkills, selected];
      localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    } else if (type === 'companies') {
      if (!intelligenceExplorerState.favoriteCompanies.includes(selected)) intelligenceExplorerState.favoriteCompanies.push(selected);
      localStorage.setItem('talentscope-favorite-companies', JSON.stringify(intelligenceExplorerState.favoriteCompanies));
    } else if (type === 'roles') {
      if (!savedJobRoles.includes(selected)) savedJobRoles = [...savedJobRoles, selected];
      localStorage.setItem('talentscope-saved-roles', JSON.stringify(savedJobRoles));
    } else if (type === 'markets') {
      if (!savedMarkets.includes(selected)) savedMarkets = [...savedMarkets, selected];
      localStorage.setItem('talentscope-saved-markets', JSON.stringify(savedMarkets));
    } else if (!dashboardState.savedCompanies.includes(selected)) {
      dashboardState.savedCompanies = [...dashboardState.savedCompanies, selected];
      localStorage.setItem('talentscope-saved-companies', JSON.stringify(dashboardState.savedCompanies));
    }
    refresh();
  });
  document.querySelector('#viewIntelligenceEvidence')?.addEventListener('click', event => {
    event.preventDefault();
    const type = intelligenceExplorerState.type;
    const target = type === 'skills' || type === 'technologies' ? 'current-skill-intelligence' : 'live-market-intelligence';
    document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
};

function renderLearningRoadmapPreview() {
  const active = roadmapState.status === 'active' || roadmapState.status === 'paused';
  if (!active) return `<section class="home-section learning-roadmap-section" id="active-learning-roadmap" aria-labelledby="learning-roadmap-title"><div class="home-section__heading"><div><span class="section-kicker">Build what comes next</span><h2 id="learning-roadmap-title">Your Learning Roadmap</h2></div></div><div class="roadmap-empty-state"><span class="roadmap-empty-state__icon"><i data-lucide="map"></i></span><div><strong>${roadmapState.status === 'rejected' ? 'Recommendation dismissed' : 'No active roadmap yet'}</strong><p>${roadmapState.status === 'rejected' ? 'Explore another skill plan whenever you are ready to start tracking.' : 'Accept a recommended skill plan to start tracking your progress.'}</p></div><button type="button" class="roadmap-primary-action" data-roadmap-explore>Explore Recommended Skills <i data-lucide="arrow-right"></i></button></div></section>`;
  const stages = roadmapState.stages?.length ? roadmapState.stages : createRoadmapStages();
  const done = stages.filter(stage => stage.completed).length;
  const completedTopics = roadmapState.completedTopics ?? 18;
  const overall = roadmapState.progress ?? Math.round(completedTopics / 28 * 100);
  const unlockedProject = !!stages[2]?.completed;
  const activityRows = (stage, index) => `<details class="roadmap-activity-details" ${roadmapState.expandedStage === index ? 'open' : ''}><summary>View Details <i data-lucide="chevron-down"></i></summary><div class="roadmap-activity-panel"><div class="roadmap-activity-panel__heading"><div><strong>Activity for ${stage.topic}</strong><small>Record progress, dates and scores.</small></div><span>Illustrative tracker</span></div><div class="roadmap-activity-list">${stage.activities.map(activity => {
    const status = activity.progress >= 100 ? 'Completed' : activity.progress > 0 ? 'In progress' : 'Not started';
    const date = activity.date ? new Date(`${activity.date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'No date recorded';
    return `<article class="roadmap-activity-row"><div class="roadmap-activity-row__top"><span>${activity.label}</span><b class="roadmap-activity-status roadmap-activity-status--${activity.progress >= 100 ? 'done' : activity.progress ? 'active' : 'idle'}">${status}</b></div><div class="roadmap-activity-row__control"><input type="range" min="0" max="100" step="1" value="${activity.progress || 0}" aria-label="${activity.label} progress for ${stage.topic}" data-roadmap-activity-progress="${index}" data-activity-id="${activity.id}" ${roadmapState.status === 'paused' ? 'disabled' : ''}><strong>${activity.progress || 0}%</strong></div><div class="roadmap-activity-row__meta"><label>Date<input type="date" value="${activity.date || ''}" data-roadmap-activity-date="${index}" data-activity-id="${activity.id}" ${roadmapState.status === 'paused' ? 'disabled' : ''}></label>${['assessment','interview'].includes(activity.id) ? `<label>Score<input type="number" min="0" max="100" value="${activity.score ?? ''}" placeholder=" — " data-roadmap-activity-score="${index}" data-activity-id="${activity.id}" ${roadmapState.status === 'paused' ? 'disabled' : ''}></label>` : `<span class="roadmap-activity-row__recorded">${date}</span>`}</div></article>`;
  }).join('')}</div></div></details>`;
  const stageRows = stages.map((stage, index) => {
    const locked = index === 3 && !unlockedProject;
    const status = locked ? 'locked' : stage.completed ? 'completed' : stage.progress > 0 ? 'in-progress' : 'not-started';
    const statusLabel = { completed: 'Completed', 'in-progress': 'In progress', 'not-started': 'Not started', locked: 'Locked until previous stage' }[status];
    return `<article class="roadmap-stage ${status === 'completed' ? 'is-complete' : ''} ${locked ? 'is-locked' : ''}" style="--stage-index:${index}"><span class="roadmap-stage__number"><i class="roadmap-stage__circle"></i><i data-lucide="check" class="roadmap-stage__check-icon"></i>${String(index + 1).padStart(2, '0')}</span><div class="roadmap-stage__main"><div class="roadmap-stage__title"><div><span>${stage.name}</span><h3>${stage.topic}</h3></div><span class="roadmap-stage__status roadmap-stage__status--${status}">${statusLabel}</span></div><div class="roadmap-stage__progress"><span><i style="width:${stage.completed ? 100 : stage.progress || 0}%"></i></span><b>${stage.completed ? '100' : stage.progress || 0}%</b></div><small><i data-lucide="clock-3"></i>${stage.estimate}</small></div><label class="roadmap-stage__check" aria-label="Mark ${stage.topic} complete"><input type="checkbox" data-roadmap-stage="${index}" ${stage.completed ? 'checked' : ''} ${locked || roadmapState.status === 'paused' ? 'disabled' : ''}><span><i data-lucide="check"></i></span></label>${activityRows(stage, index)}</article>`;
  }).join('');
  const circumference = 2 * Math.PI * 43;
  const consistency = roadmapState.consistency || [24, 46, 34, 68, 52, 82, 40];
  const assessmentScore = roadmapState.assessmentScore ?? 78;
  const readiness = roadmapState.futureReadiness ?? 72;
  return `<section class="home-section learning-roadmap-section learning-roadmap-section--active" id="active-learning-roadmap" aria-labelledby="learning-roadmap-title"><div class="home-section__heading"><div><span class="section-kicker">Build what comes next</span><h2 id="learning-roadmap-title">Your Active Roadmap</h2><p>${roadmapState.skill}  —  Recommended for your career direction</p></div><div class="roadmap-header-actions"><span class="roadmap-state-badge ${roadmapState.status === 'paused' ? 'is-paused' : ''}"><i></i>${roadmapState.status === 'paused' ? 'Paused' : 'Tracking'}</span><button type="button" class="roadmap-text-action" data-roadmap-toggle>${roadmapState.status === 'paused' ? 'Resume roadmap' : 'Pause roadmap'}</button></div></div><div class="roadmap-why-card"><strong>Why this skill was recommended</strong><div><span><i data-lucide="trending-up"></i>Future demand</span><span><i data-lucide="target"></i>Current skill gap</span><span><i data-lucide="briefcase-business"></i>Career relevance</span><span><i data-lucide="chart-no-axes-combined"></i>Market evidence</span></div></div><div class="roadmap-active-layout"><div class="roadmap-timeline" aria-label="Roadmap stages">${stageRows}</div><aside class="roadmap-progress-card"><div class="roadmap-progress-card__heading"><div><span class="section-kicker">Your progress</span><h3>Progress Summary</h3></div><div class="roadmap-progress-ring" style="--roadmap-circumference:${circumference};--roadmap-offset:${circumference * (1 - overall / 100)}"><svg viewBox="0 0 100 100" aria-hidden="true"><circle class="roadmap-progress-ring__track" cx="50" cy="50" r="43"></circle><circle class="roadmap-progress-ring__value" cx="50" cy="50" r="43"></circle></svg><strong>${overall}%</strong></div></div><div class="roadmap-summary-list"><div><span>Topics completed</span><b>${completedTopics} / 28</b><i><em style="width:${Math.min(100, completedTopics / 28 * 100)}%"></em></i></div><div><span>Completed on time</span><b>${roadmapState.onTime ?? 14}</b></div><div><span>Behind schedule</span><b>${roadmapState.behind ?? 4}</b></div><div><span>Assessment score</span><b>${assessmentScore}%</b><i><em style="width:${assessmentScore}%"></em></i></div><div><span>Future readiness</span><b>${readiness}%</b><i><em style="width:${readiness}%"></em></i></div></div><div class="roadmap-consistency"><div class="roadmap-consistency__heading"><strong>Consistency</strong><small>Learning activity | last 7 days</small></div><div class="roadmap-consistency__chart" role="img" aria-label="Illustrative learning consistency over the last seven days">${consistency.map((value,index) => `<div class="roadmap-consistency__day" style="--bar-value:${value}%;--bar-index:${index}"><span><i></i></span><small>${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][index]}</small></div>`).join("")}</div></div><small class="roadmap-demo-note">Illustrative progress  —  update stages as you learn</small><a class="roadmap-continue-action" href="#/individual/learning">Continue Learning <i data-lucide="arrow-right"></i></a></aside></div></section>`;
}

function refreshRoadmapSection() {
  const section = document.querySelector('#active-learning-roadmap');
  if (!section) return;
  section.outerHTML = renderLearningRoadmapPreview();
  lucide.createIcons();
  bindRoadmapEvents();
}

function refreshRoadmapLinkedIntelligence() {
  if (!['active', 'paused'].includes(roadmapState.status) || roadmapState.skill !== dashboardState.selectedSkill) return;
  const overview = document.querySelector('.personal-intelligence-card');
  if (overview) overview.outerHTML = renderPersonalIntelligenceOverview();
  const explorer = document.querySelector('.explore-intelligence');
  if (explorer) explorer.outerHTML = renderExploreFocusSelector();
  refreshSkillIntelligenceSection();
  lucide.createIcons();
  bindExploreIntelligenceEvents();
}

function recordRoadmapActivity(index, activityId, field, value) {
  const activity = roadmapState.stages?.[index]?.activities?.find(item => item.id === activityId);
  if (!activity || roadmapState.status !== 'active') return;
  if (field === 'progress') {
    activity.progress = Math.max(0, Math.min(100, Number(value) || 0));
    activity.status = activity.progress === 100 ? 'completed' : activity.progress ? 'in-progress' : 'not-started';
    if (activity.progress && !activity.date) activity.date = new Date().toISOString().slice(0, 10);
    if (activity.id === 'interview') roadmapState.futureReadiness = activity.score ?? Math.round(72 + activity.progress * .28);
    const stage = roadmapState.stages[index];
    if (stage && !stage.completed) stage.progress = Math.round(stage.activities.reduce((sum, item) => sum + (item.progress || 0), 0) / stage.activities.length);
  } else if (field === 'date') activity.date = value;
  else if (field === 'score') {
    const previousScore = activity.score;
    activity.score = value === '' ? null : Math.max(0, Math.min(100, Number(value) || 0));
    if (activity.id === 'assessment') {
      roadmapState.assessmentScore = activity.score;
      if (activity.score !== null) roadmapState.skillHealth = Math.max(0, Math.min(100, Math.round((roadmapState.skillHealth ?? 82) + (activity.score - (previousScore ?? activity.score)) * .25)));
    }
    if (activity.id === 'interview' && activity.score !== null) roadmapState.futureReadiness = activity.score;
  }
  const dayIndex = (new Date().getDay() + 6) % 7;
  roadmapState.consistency ||= [24, 46, 34, 68, 52, 82, 40];
  roadmapState.consistency[dayIndex] = Math.min(100, Math.max(roadmapState.consistency[dayIndex] || 0, 24) + 6);
  persistRoadmapState();
  refreshRoadmapSection();
  refreshRoadmapLinkedIntelligence();
}

function bindRoadmapEvents() {
  document.querySelectorAll('[data-roadmap-explore]:not([data-roadmap-bound])').forEach(button => { button.dataset.roadmapBound = 'true'; button.addEventListener('click', () => {
    if (roadmapState.status === 'rejected') { roadmapState = { status: 'empty', skill: '', stages: [] }; persistRoadmapState(); }
    document.querySelector('.explore-intelligence')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    document.querySelector('[data-explore-type="skills"]')?.click();
  }); });
  const toggle = document.querySelector('[data-roadmap-toggle]:not([data-roadmap-bound])');
  if (toggle) { toggle.dataset.roadmapBound = 'true'; toggle.addEventListener('click', () => {
    roadmapState.status = roadmapState.status === 'paused' ? 'active' : 'paused';
    persistRoadmapState(); refreshRoadmapSection();
  }); }
  document.querySelectorAll('[data-roadmap-stage]:not([data-roadmap-bound])').forEach(input => { input.dataset.roadmapBound = 'true'; input.addEventListener('change', () => {
    const index = Number(input.dataset.roadmapStage), stage = roadmapState.stages[index];
    if (!stage || (index === 3 && !roadmapState.stages[2]?.completed)) return;
    stage.completed = input.checked; stage.progress = input.checked ? 100 : 0;
    if (input.checked) stage.activities.forEach(activity => { activity.progress = 100; activity.status = 'completed'; activity.date ||= new Date().toISOString().slice(0, 10); });
    roadmapState.stages.forEach((item, itemIndex) => { item.status = item.completed ? 'completed' : item.progress ? 'in-progress' : 'not-started'; });
    roadmapState.completedTopics = Math.max(0, Math.min(28, (roadmapState.completedTopics ?? 18) + (input.checked ? 1 : -1)));
    roadmapState.progress = Math.round(roadmapState.completedTopics / 28 * 100);
    roadmapState.onTime = Math.max(0, Math.min(28, (roadmapState.onTime ?? 14) + (input.checked ? 1 : -1)));
    roadmapState.behind = Math.max(0, Math.min(28, (roadmapState.behind ?? 4) - (input.checked ? 1 : -1)));
    roadmapState.skillHealth = Math.max(0, Math.min(100, (roadmapState.skillHealth ?? 82) + (input.checked ? 2 : -2)));
    roadmapState.futureReadiness = Math.max(0, Math.min(100, (roadmapState.futureReadiness ?? 72) + (input.checked ? 2 : -2)));
    const dayIndex = (new Date().getDay() + 6) % 7;
    roadmapState.consistency ||= [24, 46, 34, 68, 52, 82, 40];
    roadmapState.consistency[dayIndex] = Math.min(100, Math.max(roadmapState.consistency[dayIndex] || 0, 24) + 6);
    persistRoadmapState(); refreshRoadmapSection(); refreshRoadmapLinkedIntelligence();
  }); });
  document.querySelectorAll('[data-roadmap-activity-progress]:not([data-roadmap-bound]),[data-roadmap-activity-date]:not([data-roadmap-bound]),[data-roadmap-activity-score]:not([data-roadmap-bound])').forEach(input => {
    input.dataset.roadmapBound = 'true';
    const field = input.hasAttribute('data-roadmap-activity-progress') ? 'progress' : input.hasAttribute('data-roadmap-activity-date') ? 'date' : 'score';
    input.addEventListener('change', () => recordRoadmapActivity(Number(input.dataset[field === 'progress' ? 'roadmapActivityProgress' : field === 'date' ? 'roadmapActivityDate' : 'roadmapActivityScore']), input.dataset.activityId, field, input.value));
  });
  document.querySelectorAll('.roadmap-activity-details:not([data-roadmap-bound])').forEach(details => {
    details.dataset.roadmapBound = 'true';
    details.addEventListener('toggle', () => {
      if (details.open) roadmapState.expandedStage = Number(details.closest('.roadmap-stage')?.style.getPropertyValue('--stage-index') || 0);
      else if (roadmapState.expandedStage === Number(details.closest('.roadmap-stage')?.style.getPropertyValue('--stage-index') || 0)) roadmapState.expandedStage = null;
      persistRoadmapState();
    });
  });
  const accept = document.querySelector('[data-roadmap-accept]:not([data-roadmap-bound])');
  if (accept) { accept.dataset.roadmapBound = 'true'; accept.addEventListener('click', () => {
    const selected = intelligenceExplorerState.selected[intelligenceExplorerState.type];
    const skill = intelligenceExplorerState.type === 'skills' ? selected : dashboardState.selectedSkill || 'Machine Learning';
    const goal = intelligenceExplorerState.type === 'roles' ? 'Job Preparation' : intelligenceExplorerState.type === 'companies' ? 'Company Preparation' : dashboardState.selectedSkill === skill ? 'Improve Skill' : 'Learn Skill';
    roadmapState = { status: 'active', skill, goal, name: `${skill} ${goal} Roadmap`, stages: createRoadmapStages(), completedTopics: 18, progress: 64, onTime: 14, behind: 4, assessmentScore: 78, skillHealth: 82, futureReadiness: 72, consistency: [24, 46, 34, 68, 52, 82, 40], expandedStage: 1 };
    persistRoadmapState(); refreshRoadmapSection(); refreshInsightRecommendationSection();
    document.querySelector('#active-learning-roadmap')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }); }
  const reject = document.querySelector('[data-roadmap-reject]:not([data-roadmap-bound])');
  if (reject) { reject.dataset.roadmapBound = 'true'; reject.addEventListener('click', () => {
    roadmapState = { status: 'rejected', skill: '', stages: [] }; persistRoadmapState(); refreshRoadmapSection(); refreshInsightRecommendationSection();
  }); }
}

function renderCareerOpportunityPreview() {
  const type = intelligenceExplorerState.type;
  const selected = intelligenceExplorerState.selected[type] || dashboardState.selectedSkill;
  const roleForSkill = { 'Machine Learning': 'AI / ML Engineer', 'Generative AI': 'AI Engineer', AI: 'AI Engineer', JavaScript: 'Software Engineer', Python: 'AI / ML Engineer', 'Cloud Computing': 'Cloud Engineer', 'Data Analytics': 'Data Analyst', SQL: 'Data Analyst', React: 'Software Engineer', Cybersecurity: 'Cybersecurity Engineer' };
  const targetRole = type === 'roles' ? selected : (roleForSkill[dashboardState.selectedSkill] || 'AI / ML Engineer');
  const relevantSkills = [...new Set([dashboardState.selectedSkill, 'Python', 'Data Analytics'])].slice(0, 3);
  const place = intelligenceExplorerState.scope === 'My Market' ? (dashboardState.market === 'Global' ? user.location : dashboardState.market) : user.location;
  const cards = [
    { kind: 'Recommended role', icon: 'briefcase-business', title: targetRole, match: '82%  —  illustrative profile match', detail: 'A suggested direction based on your selected skill signals.', action: 'Explore role' },
    { kind: 'Matching job', icon: 'search', title: 'No connected job listings', match: 'Match unavailable', detail: 'Connect a verified jobs source to see current openings, employers and locations.', action: 'Browse opportunities', unavailable: true },
    { kind: 'Internal / future opportunity', icon: 'compass', title: `${targetRole} pathway`, match: 'Profile alignment preview  —  illustrative', detail: 'A possible next step as you build experience in your selected skill area.', action: 'Explore pathway' }
  ];
  return `<section class="home-section next-opportunities" id="career-opportunity-preview" aria-labelledby="career-preview-title"><div class="home-section__heading"><div><span class="section-kicker">Next move</span><h2 id="career-preview-title">Next Opportunities</h2><p>Explore jobs, roles and companies connected to your skills, progress and career direction.</p></div><span class="opportunity-context"><i data-lucide="map-pin"></i>${place}  —  ${dashboardState.selectedSkill}</span></div><div class="next-opportunities__grid">${cards.map((card, index) => `<article class="next-opportunity-card ${card.unavailable ? 'is-unavailable' : ''}" style="--opportunity-index:${index}"><div class="next-opportunity-card__head"><span class="next-opportunity-card__icon"><i data-lucide="${card.icon}"></i></span><span>${card.kind}</span></div><h3>${card.title}</h3><strong class="next-opportunity-card__match">${card.match}</strong><div class="next-opportunity-card__skills" aria-label="Related skills">${relevantSkills.map(skill => `<span>${skill}</span>`).join('')}</div><p><i data-lucide="map-pin"></i>${card.unavailable ? 'Location and company appear when listings are connected' : `${place}  —  Suggested direction`}</p><small>${card.detail}</small><a href="#/individual/opportunities">${card.action} <i data-lucide="arrow-up-right"></i></a></article>`).join('')}</div></section>`;
}

function renderLiveIntelligenceSparkline(values, tone, label) {
  const points = values?.length ? values : [0, 0, 0, 0, 0, 0];
  const min = Math.min(...points), range = Math.max(1, Math.max(...points) - min);
  const coords = points.map((value, index) => ({ x: 4 + index * (92 / Math.max(1, points.length - 1)), y: 27 - ((value - min) / range) * 21 }));
  const line = coords.map(point => `${point.x},${point.y}`).join(' ');
  return `<svg class="live-intelligence-sparkline live-intelligence-sparkline--${tone}" viewBox="0 0 100 34" role="img" aria-label="${label} illustrative trend"><polyline points="${line}" vector-effect="non-scaling-stroke"></polyline><circle cx="${coords.at(-1).x}" cy="${coords.at(-1).y}" r="2.4"></circle></svg>`;
}

function renderLiveIntelligenceSection() {
  const { type, scope } = intelligenceExplorerState;
  const selected = intelligenceExplorerState.selected[type] || '';
  const marketLocation = scope === 'Global' ? 'Global' : dashboardState.market === 'Global' ? user.location : dashboardState.market;
  const company = type === 'companies' ? companyMarketData[selected.toLowerCase()] : null;
  const roleForSkill = { 'Machine Learning': 'AI / ML Engineer', 'Generative AI': 'AI Engineer', AI: 'AI Engineer', JavaScript: 'Software Engineer', Python: 'AI / ML Engineer', 'Cloud Computing': 'Cloud Engineer', 'Data Analytics': 'Data Analyst', SQL: 'Data Analyst', React: 'UI/UX Designer', Cybersecurity: 'Cybersecurity Engineer' };
  const companySkill = { Microsoft: 'Machine Learning', NVIDIA: 'Machine Learning', Google: 'Generative AI', Amazon: 'Cloud Computing', Meta: 'Generative AI' }[selected];
  const skillName = type === 'skills' ? selected : type === 'companies' ? companySkill || dashboardState.selectedSkill : dashboardState.selectedSkill;
  const relatedRole = type === 'roles' ? selected : roleForSkill[skillName] || 'All Roles';
  const roleData = jobTrendData[relatedRole] || jobTrendData['All Roles'];
  const roleView = type === 'roles' ? getJobTrendView() : null;
  const skillData = trendDetailsForSkill(skillName || 'Machine Learning');
  const skillGrowth = Number((((skillData.current - skillData.previous) / Math.max(1, skillData.previous)) * 100).toFixed(1));
  const scopeMarket = marketTrendData[marketLocation] || marketTrendData.Global;
  const marketView = company ? getMarketTrendView(selected) : null;
  const marketSeries = marketView || scopeMarket;
  const marketMomentum = marketView?.momentum ?? Math.max(0, Math.min(100, Math.round(scopeMarket.momentum + (type === 'skills' ? (skillData.current - 70) * .15 : type === 'roles' ? (roleData.overallMomentum - 78) * .12 : 0))));
  const marketChange = marketView?.change ?? scopeMarket.change + (type === 'skills' ? skillGrowth * .1 : type === 'roles' ? (roleData.changePercentage - 12.4) * .15 : 0);
  const techSeries = marketView?.technologyMomentum || (type === 'roles' ? [roleData.skillDemand.value - 12, roleData.skillDemand.value - 8, roleData.skillDemand.value - 4, roleData.skillDemand.value - 2, roleData.skillDemand.value - 1, roleData.skillDemand.value] : type === 'skills' ? skillData.values : scopeMarket.technologyMomentum);
  const industryLabel = company?.sector || (type === 'roles' ? 'Technology roles' : 'Technology');
  const industrySeries = marketView?.investmentSignal || (type === 'roles' ? [roleData.jobDemand.value - 10, roleData.jobDemand.value - 7, roleData.jobDemand.value - 4, roleData.jobDemand.value - 2, roleData.jobDemand.value] : type === 'skills' ? [48, 52, 57, 63, 69, Math.min(98, skillData.current)] : scopeMarket.investmentSignal);
  const industryDirection = industrySeries.at(-1) > industrySeries[0] + 1 ? 'Growing' : industrySeries.at(-1) < industrySeries[0] - 1 ? 'Declining' : 'Stable';
  const industryMomentum = industrySeries.at(-1);
  const jobSeries = marketView?.jobDemand || (type === 'roles' ? [roleData.jobDemand.value - 14, roleData.jobDemand.value - 10, roleData.jobDemand.value - 7, roleData.jobDemand.value - 4, roleData.jobDemand.value - 2, roleView.metrics.find(metric => metric.key === 'jobDemand').value] : type === 'skills' ? [48, 53, 57, 64, 70, Math.max(20, Math.min(98, skillData.current + 3))] : scopeMarket.jobDemand);
  const jobHiring = marketView ? Math.round((marketView.jobDemand.at(-1) + marketView.investmentSignal.at(-1)) / 2) : roleView?.metrics.find(metric => metric.key === 'hiringMomentum')?.value ?? roleData.hiringMomentum.value;
  const jobChange = marketView?.change ?? (type === 'roles' ? roleView.change : type === 'skills' ? skillGrowth : scopeMarket.change);
  const directionFor = (values, change) => change > 1 ? 'Growing' : change < -1 ? 'Declining' : values.at(-1) > values.at(-2) ? 'Growing' : values.at(-1) < values.at(-2) ? 'Declining' : 'Stable';
  const deltaPct = values => Number((((values.at(-1) - values[0]) / Math.max(1, values[0])) * 100).toFixed(1));
  const trendIcon = direction => direction === 'Growing' ? 'trending-up' : direction === 'Declining' ? 'trending-down' : 'minus';
  const toneData = [
    { id: 'skill', title: 'Skill Trends', icon: 'brain-circuit', tone: 'skill', value: skillName || 'Skill signals', metric: `${skillGrowth > 0 ? '+' : ''}${skillGrowth}% growth`, detail: `Demand index ${skillData.current} / 100`, direction: directionFor(skillData.values, skillData.current - skillData.previous), values: skillData.values, href: '#current-skill-intelligence' },
    { id: 'market', title: 'Market Trends', icon: 'chart-no-axes-combined', tone: 'market', value: `${Math.round(marketMomentum)} / 100`, metric: `${marketChange > 0 ? '+' : ''}${marketChange.toFixed(1)}% growth`, detail: `${marketLocation} market momentum`, direction: directionFor(marketSeries.technologyMomentum || scopeMarket.technologyMomentum, marketChange), values: marketSeries.technologyMomentum || scopeMarket.technologyMomentum, href: '#live-market-intelligence' },
    { id: 'technology', title: 'Technology Trends', icon: 'cpu', tone: 'technology', value: type === 'companies' ? selected || 'Technology' : type === 'roles' ? selected || 'Technology' : skillName || 'Technology', metric: `${techSeries.at(-1)} / 100 momentum`, detail: 'Adoption direction', direction: directionFor(techSeries, deltaPct(techSeries)), values: techSeries, href: '#live-market-intelligence' },
    { id: 'industry', title: 'Industry Trends', icon: 'building-2', tone: 'industry', value: industryLabel, metric: `${industryMomentum} / 100 signal`, detail: `Growth signal  —  ${industryDirection}`, direction: industryDirection, values: industrySeries, href: '#live-market-intelligence' },
    { id: 'jobs', title: 'Job Trends', icon: 'briefcase-business', tone: 'jobs', value: `${jobSeries.at(-1)} / 100`, metric: `${jobHiring} hiring momentum`, detail: `${jobChange > 0 ? '+' : ''}${jobChange.toFixed(1)}% growth  —  ${type === 'roles' ? selected : relatedRole}`, direction: directionFor(jobSeries, jobChange), values: jobSeries, href: '#live-market-intelligence' }
  ];
  const noSavedSelection = scope === 'Saved' && !selected;
  const cards = toneData.map((card, index) => `<article class="live-intelligence-card live-intelligence-card--${card.tone}" style="--live-card-index:${index}"><div class="live-intelligence-card__head"><span class="live-intelligence-card__icon"><i data-lucide="${card.icon}"></i></span><div><h3>${card.title}</h3><span class="live-intelligence-card__status"><i></i>Live</span></div></div><div class="live-intelligence-card__metric"><strong>${noSavedSelection ? '—' : card.value}</strong><span class="live-intelligence-card__direction live-intelligence-card__direction--${noSavedSelection ? 'stable' : card.direction.toLowerCase()}"><i data-lucide="${trendIcon(noSavedSelection ? 'Stable' : card.direction)}"></i>${noSavedSelection ? 'No saved item' : `${card.metric}  —  ${card.direction}`}</span></div><small class="live-intelligence-card__detail">${noSavedSelection ? `Save a ${type === 'roles' ? 'role' : type === 'companies' ? 'company' : 'skill'} to see saved signals` : card.detail}</small><div class="live-intelligence-card__chart">${renderLiveIntelligenceSparkline(noSavedSelection ? [0,0,0,0,0,0] : card.values, card.tone, card.title)}</div><a href="${card.href}" data-live-scroll="${card.href.slice(1)}" class="live-intelligence-card__explore">Explore <span>→</span></a></article>`).join('');
  return `<section class="home-section live-intelligence-section" id="live-intelligence" aria-labelledby="live-intelligence-title"><div class="home-section__heading"><div><span class="section-kicker">Signals across your career</span><h2 id="live-intelligence-title">Live Intelligence</h2><p>See the signals shaping skills, technology, markets and opportunities.</p></div><span class="live-intelligence-context"><i></i>${selected || 'Select intelligence'}  —  ${scope === 'My Market' ? marketLocation : scope}</span></div><div class="live-intelligence-grid">${cards}</div><small class="live-intelligence-note">Illustrative prototype signals  —  explore detailed charts in the sections above.</small></section>`;
}

let futureSkillChartPreviousValues = null;

function skillAssessmentFor(skill, details) {
  if (skill === 'Machine Learning') {
    const score = ['active', 'paused'].includes(roadmapState.status) && roadmapState.skill === skill ? roadmapState.skillHealth ?? 82 : 82;
    const shift = score - 82;
    return { score, dimensions: [['Knowledge', 86 + shift], ['Practice', 78 + shift], ['Application', 81 + shift], ['Assessment', 76 + shift]].map(([name, value]) => [name, Math.max(0, Math.min(100, value))]) };
  }
  const score = ['active', 'paused'].includes(roadmapState.status) && roadmapState.skill === skill ? roadmapState.skillHealth ?? details.current : details.current;
  const offset = score - 82;
  const clamp = value => Math.max(45, Math.min(98, value));
  return { score: Math.max(35, Math.min(100, score)), dimensions: [['Knowledge', clamp(86 + offset)], ['Practice', clamp(78 + offset)], ['Application', clamp(81 + offset)], ['Assessment', clamp(76 + offset)]] };
}

function skillTrendPath(values, area = false) {
  const safeValues = values.length ? values : [50, 54, 58, 62, 67, 72];
  const points = safeValues.map((value, index) => ({ x: 40 + index * (520 / Math.max(1, safeValues.length - 1)), y: 202 - Math.max(0, Math.min(100, value)) * 1.72 }));
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index++) {
    const first = points[index], next = points[index + 1], dx = next.x - first.x;
    path += ` C ${first.x + dx * .42} ${first.y}, ${next.x - dx * .42} ${next.y}, ${next.x} ${next.y}`;
  }
  return area ? `${path} L ${points.at(-1).x} 208 L ${points[0].x} 208 Z` : path;
}

function renderFutureSkillChart(details) {
  const previous = futureSkillChartPreviousValues || details.values;
  const fromValues = previous.slice(-6), targetValues = details.values.slice(-6);
  const market = getMarketTrendView();
  const labels = ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'];
  const futureDemand = Math.min(98, Math.round(details.current + Math.max(2, details.growth * .65)));
  const pointMarkup = targetValues.map((value, index) => {
    const x = 40 + index * 104, y = 202 - value * 1.72;
    return `<g class="skill-future-point${index === targetValues.length - 1 ? ' is-current' : ''}" data-skill-point="${index}" data-value="${value}" data-month="${labels[index]}" data-change="${(((value - (targetValues[index - 1] || value)) / Math.max(1, targetValues[index - 1] || value)) * 100).toFixed(1)}" tabindex="0" role="button" aria-label="${labels[index]}, demand ${value}, illustrative"><circle class="skill-future-point__halo" cx="${x}" cy="${y}" r="8"></circle><circle class="skill-future-point__dot" cx="${x}" cy="${y}" r="4"></circle></g>`;
  }).join('');
  const change = details.current - details.previous;
  const direction = Math.abs(change) < 1 ? 'Stable' : change > 0 ? 'Growing' : 'Declining';
  futureSkillChartPreviousValues = null;
  return `<div class="skill-future-chart" data-chart-from="${encodeURIComponent(JSON.stringify(fromValues))}" data-chart-to="${encodeURIComponent(JSON.stringify(targetValues))}"><div class="skill-future-chart__plot"><div class="skill-future-chart__y-axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><svg class="skill-future-chart__svg" viewBox="0 0 600 220" preserveAspectRatio="none" role="img" aria-label="Illustrative skill demand, technology momentum and job demand for ${details.skill}"><defs><linearGradient id="skillDemandFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#9a48dc" stop-opacity=".22"></stop><stop offset="1" stop-color="#9a48dc" stop-opacity=".015"></stop></linearGradient><linearGradient id="techDemandFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#5789ed" stop-opacity=".08"></stop><stop offset="1" stop-color="#5789ed" stop-opacity="0"></stop></linearGradient><linearGradient id="jobDemandFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#31b58b" stop-opacity=".08"></stop><stop offset="1" stop-color="#31b58b" stop-opacity="0"></stop></linearGradient></defs><g class="skill-future-grid">${[30,73,116,159,202].map(y => `<line x1="40" x2="560" y1="${y}" y2="${y}"></line>`).join('')}</g><path class="skill-future-series__area skill-future-series__area--technology" d="${skillTrendPath(market.technologyMomentum, true)}"></path><path class="skill-future-series__line skill-future-series__line--technology" d="${skillTrendPath(market.technologyMomentum)}"></path><path class="skill-future-series__area skill-future-series__area--jobs" d="${skillTrendPath(market.jobDemand, true)}"></path><path class="skill-future-series__line skill-future-series__line--jobs" d="${skillTrendPath(market.jobDemand)}"></path><path class="skill-future-series__area skill-future-series__area--skill" d="${skillTrendPath(fromValues, true)}"></path><path class="skill-future-series__line skill-future-series__line--skill" d="${skillTrendPath(fromValues)}"></path>${pointMarkup}</svg><div class="skill-future-chart__tooltip" id="skillFutureTooltip" role="status" hidden></div><div class="skill-future-chart__x-axis">${labels.map(label => `<span>${label}</span>`).join('')}</div></div><div class="skill-future-chart__axis-labels"><span>Skill Demand Index</span><span>Time  —  last 6 months</span></div><div class="skill-future-chart__legend"><span><i class="is-skill"></i>Skill Demand</span><span><i class="is-tech"></i>Technology Momentum</span><span><i class="is-jobs"></i>Job Demand</span></div><div class="skill-future-chart__summary"><div><span>Current Demand</span><strong>${details.current}<small> / 100</small></strong></div><div><span>Future Demand</span><strong>${futureDemand}<small> / 100</small></strong></div><div><span>Growth Direction</span><strong class="is-${direction.toLowerCase()}">${direction === 'Growing' ? '↗' : direction === 'Declining' ? '↘' : '→'} ${direction}</strong></div></div><p class="skill-future-chart__note">Illustrative prototype data  —  not verified live market signals</p></div>`;
}

function renderSkillIntelligenceSection() {
  const details = trendDetailsForSkill(dashboardState.selectedSkill);
  const assessment = skillAssessmentFor(dashboardState.selectedSkill, details);
  const strength = assessment.score >= 80 ? 'Strong' : assessment.score >= 60 ? 'Developing' : 'Building';
  const skillChange = details.current - details.previous;
  const direction = Math.abs(skillChange) < 1 ? 'Stable' : skillChange > 0 ? 'Growing' : 'Declining';
  const circumference = 2 * Math.PI * 72;
  const isSaved = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
  return `<section class="home-section skill-intelligence-section" id="current-skill-intelligence" aria-labelledby="current-skill-section-title"><div class="home-section__heading"><div><span class="section-kicker">Your skill, in context</span><h2 id="current-skill-section-title">Skill Intelligence</h2><p>Where your skill stands today and where demand is heading.</p></div></div><div class="home-section__grid skill-intelligence-grid"><article class="current-skill-health-card" aria-labelledby="current-skill-health-title"><header class="skill-intel-card__header"><div><span class="skill-intel-card__eyebrow">TODAY</span><h3 id="current-skill-health-title">Current Skill Health</h3><p>${dashboardState.selectedSkill}</p></div><div class="skill-intel-card__actions"><button class="skill-favorite-button ${isSaved ? 'is-saved' : ''}" id="filterFavoriteButton" type="button" aria-pressed="${isSaved}" title="${isSaved ? 'Remove from My Intelligence' : 'Save this skill'}"><i data-lucide="${isSaved ? 'check' : 'bookmark-plus'}"></i>${isSaved ? 'Saved' : 'Save skill'}</button><div class="skill-intel-filter-wrap"><button class="skill-filter-button" id="skillFilterButton" type="button" aria-expanded="false"><i data-lucide="sliders-horizontal"></i>Filters</button><div class="skill-filter-panel" id="skillFilterPanel" hidden><div class="skill-filter-panel__heading"><strong>Skill intelligence filters</strong><small>Illustrative prototype signals</small></div><label>Time range<select id="skillFilterTime">${optionMarkup(timeRangeOptions, dashboardState.timeRange)}</select></label><label>Market location<select id="skillFilterMarket">${optionMarkup(marketOptions, dashboardState.market)}</select></label></div></div></div></header><div class="skill-health-card__main"><div class="skill-health-radial" role="img" aria-label="${assessment.score} out of 100, ${strength} skill health"><svg viewBox="0 0 176 176" aria-hidden="true"><circle class="skill-health-radial__track" cx="88" cy="88" r="72"></circle><circle class="skill-health-radial__progress" cx="88" cy="88" r="72" style="--score-offset:${circumference * (1 - assessment.score / 100)};--score-circumference:${circumference}"></circle></svg><div class="skill-health-radial__label"><strong>${assessment.score}</strong><span>/ 100</span><b>${strength}</b></div></div><div class="skill-health-dimensions">${assessment.dimensions.map(([label, value], index) => `<div class="skill-health-dimension" style="--dimension-delay:${index * 70}ms"><div><span>${label}</span><strong>${value}%</strong></div><div class="skill-health-dimension__track"><i style="--dimension-value:${value}%"></i></div></div>`).join('')}</div></div><footer class="skill-health-card__footer"><span><i data-lucide="clock-3"></i>Last assessed 14 days ago</span><a href="#/individual/skills" class="skill-health-assessment-link">View Skill Assessment<i data-lucide="arrow-up-right"></i></a></footer><p class="skill-health-card__note">Your current skill strength based on learning activity, practice and assessment signals. Illustrative prototype measurement; no verified assessment data is connected.</p></article><article class="future-skill-trend-card" aria-labelledby="future-skill-trend-title"><header class="skill-intel-card__header"><div><span class="skill-intel-card__eyebrow">WHAT'S NEXT</span><h3 id="future-skill-trend-title">Future Skill Trend</h3><p>How demand for this skill is changing across the selected market.</p></div><span class="skill-growth-badge skill-growth-badge--${direction.toLowerCase()}"><i></i>${direction === 'Growing' ? '↗' : direction === 'Declining' ? '↘' : '→'} ${direction}</span></header>${renderFutureSkillChart(details)}<div class="skill-future-why"><div><span class="skill-future-why__icon"><i data-lucide="lightbulb"></i></span><div><strong>Why is it changing?</strong><p>AI adoption and increasing demand for data-driven systems are contributing to higher demand for this skill.</p></div></div><a href="#/individual/market-insights" class="skill-future-evidence">View Evidence<i data-lucide="arrow-right"></i></a></div></article></div></section>`;
}

function animateFutureSkillChart() {
  const chart = document.querySelector('.skill-future-chart');
  if (!chart) return;
  const from = JSON.parse(decodeURIComponent(chart.dataset.chartFrom));
  const to = JSON.parse(decodeURIComponent(chart.dataset.chartTo));
  if (!from.some((value, index) => value !== to[index])) return;
  const line = chart.querySelector('.skill-future-series__line--skill');
  const area = chart.querySelector('.skill-future-series__area--skill');
  const points = chart.querySelectorAll('.skill-future-point');
  const started = performance.now(), duration = 700;
  const frame = now => {
    const t = Math.min(1, (now - started) / duration), eased = 1 - Math.pow(1 - t, 3);
    const values = from.map((value, index) => value + (to[index] - value) * eased);
    line.setAttribute('d', skillTrendPath(values)); area.setAttribute('d', skillTrendPath(values, true));
    points.forEach((point, index) => { const y = 202 - values[index] * 1.72; point.querySelectorAll('circle').forEach(circle => circle.setAttribute('cy', y)); });
    if (t < 1) requestAnimationFrame(frame);
    else chart.classList.add('is-settled');
  };
  requestAnimationFrame(frame);
}

function bindFutureSkillChartEvents() {
  const chart = document.querySelector('.skill-future-chart__plot');
  const tooltip = document.querySelector('#skillFutureTooltip');
  if (!chart || !tooltip) return;
  const show = point => {
    const index = Number(point.dataset.skillPoint), bounds = chart.getBoundingClientRect();
    const x = (40 + index * 104) / 600 * bounds.width;
    const y = (202 - Number(point.dataset.value) * 1.72) / 220 * bounds.height;
    tooltip.innerHTML = `<strong>${point.dataset.month}</strong><span>Demand Index <b>${point.dataset.value}</b></span><span>Change <b>${Number(point.dataset.change) >= 0 ? '+' : ''}${point.dataset.change}%</b></span><small>Signal  —  ${Number(point.dataset.change) > 0 ? 'Growing' : Number(point.dataset.change) < 0 ? 'Declining' : 'Stable'}</small>`;
    tooltip.style.left = `${Math.min(bounds.width - 12, Math.max(12, x))}px`;
    tooltip.style.top = `${Math.max(16, y - 10)}px`;
    tooltip.hidden = false;
    chart.querySelectorAll('.skill-future-point.is-active').forEach(active => active.classList.remove('is-active'));
    point.classList.add('is-active');
  };
  chart.querySelectorAll('[data-skill-point]').forEach(point => {
    point.addEventListener('mouseenter', () => show(point)); point.addEventListener('focus', () => show(point));
    point.addEventListener('mouseleave', () => { tooltip.hidden = true; point.classList.remove('is-active'); });
    point.addEventListener('blur', () => { tooltip.hidden = true; point.classList.remove('is-active'); });
  });
}

function refreshSkillIntelligenceSection(previousValues = null) {
  if (previousValues) futureSkillChartPreviousValues = previousValues;
  const section = document.querySelector('#current-skill-intelligence');
  if (!section) return;
  section.outerHTML = renderSkillIntelligenceSection();
  lucide.createIcons();
  bindSkillTrendAnalyticsEvents();
  bindFutureSkillChartEvents();
  animateFutureSkillChart();
}

function renderInsightRecommendationSection() {
  const type = intelligenceExplorerState.type;
  const selected = intelligenceExplorerState.selected[type] || dashboardState.selectedSkill;
  let direction = 'Growing', change = 0, period = dashboardState.timeRange, subject = selected;
  if (type === 'skills') {
    const details = trendDetailsForSkill(selected);
    change = Number((((details.current - details.values[0]) / Math.max(1, details.values[0])) * 100).toFixed(1));
    direction = details.current > details.previous ? 'Growing' : details.current < details.previous ? 'Declining' : 'Stable';
  } else if (type === 'roles') {
    const role = jobTrendData[selected] || jobTrendData['All Roles'];
    change = role.changePercentage; direction = role.direction; period = jobTrendState.period;
  } else {
    const company = getMarketTrendView(selected);
    change = company.change; direction = company.trend; period = marketTrendState.timeRange;
  }
  const sign = change > 0 ? '+' : '';
  const explanation = type === 'skills'
    ? `AI adoption, automation and increased demand for data-driven products are increasing the need for ${selected} capabilities.`
    : type === 'roles'
      ? `Hiring activity and demand for the skills used in ${selected} roles are shaping this direction.`
      : `Technology adoption, investment activity and hiring signals around ${selected} contribute to this market direction.`;
  const recommendation = type === 'skills'
    ? `Strengthen ${selected} fundamentals and build one applied project.`
    : type === 'roles'
      ? `Compare the core skills for ${selected} and build a small project that demonstrates them.`
      : `Review the skills and role signals connected to ${selected}, then choose one capability to strengthen.`;
  const evidence = [
    { type: 'Market Report', icon: 'chart-no-axes-combined', title: `${selected} market movement summary`, reason: `Illustrative ${period.toLowerCase()} demand index and direction.` },
    { type: 'Technology Signal', icon: 'cpu', title: 'Technology adoption signal', reason: `Demo technology momentum associated with ${selected}.` },
    { type: 'Job Demand Signal', icon: 'briefcase-business', title: 'Workforce demand sample', reason: `Prototype job demand trend for the selected intelligence.` }
  ];
  const directionClass = direction === 'Declining' ? 'is-declining' : direction === 'Stable' ? 'is-stable' : 'is-growing';
  const changeWording = direction === 'Growing' ? 'increased' : direction === 'Declining' ? 'declined' : 'remained stable';
  const roadmapAction = roadmapState.status === 'active' || roadmapState.status === 'paused'
    ? `<a class="insight-roadmap-button" href="#active-learning-roadmap" data-insight-scroll="active-learning-roadmap">${roadmapState.status === 'paused' ? 'Resume your roadmap' : 'View your active roadmap'} <i data-lucide="arrow-right"></i></a>`
    : roadmapState.status === 'rejected'
      ? `<button class="insight-roadmap-button" type="button" data-roadmap-explore>Explore Recommended Skills <i data-lucide="arrow-right"></i></button>`
      : `<div class="insight-roadmap-actions"><button class="insight-roadmap-button" type="button" data-roadmap-accept>Accept &amp; Start Roadmap <i data-lucide="arrow-right"></i></button><button class="insight-roadmap-reject" type="button" data-roadmap-reject>Reject recommendation</button></div>`;
  return `<section class="home-section insight-recommendation-section" id="insight-recommendations" aria-labelledby="insight-recommendations-title"><div class="home-section__heading"><div><span class="section-kicker">From signal to next step</span><h2 id="insight-recommendations-title">Insight &amp; Recommendation</h2><p>Understand what changed, why it matters, and how you can respond.</p></div><span class="insight-prototype-tag"><i></i>Illustrative prototype insight</span></div><div class="insight-flow-grid"><article class="insight-flow-card insight-flow-card--change"><header><span class="insight-flow-card__step">01</span><span class="insight-flow-card__eyebrow">SIGNAL</span></header><h3>What Changed?</h3><p>${type === 'skills' ? `${selected} demand has ${changeWording} across ${dashboardState.market === 'Global' ? 'technology roles' : `${dashboardState.market} technology roles`}.` : `${subject} signals are currently ${direction.toLowerCase()} across the selected ${type === 'roles' ? 'role' : 'company'} view.`}</p><div class="insight-change-summary"><strong class="${directionClass}">${direction === 'Growing' ? '↗' : direction === 'Declining' ? '↘' : '→'} ${direction}</strong><span><b>${sign}${change.toFixed(1)}%</b><small>Change</small></span><span><b>${period}</b><small>Time period</small></span></div><div class="insight-flow-card__connector"><span>→</span><small>signal</small></div></article><article class="insight-flow-card insight-flow-card--why"><header><span class="insight-flow-card__step">02</span><span class="insight-flow-card__eyebrow">CONTEXT</span></header><h3>Why It Matters</h3><p>${explanation}</p><div class="insight-contributing-signals"><span><i class="is-tech"></i>Technology adoption</span><span><i class="is-market"></i>Market momentum</span><span><i class="is-jobs"></i>Job demand</span></div><div class="insight-flow-card__connector"><span>→</span><small>implication</small></div></article><article class="insight-flow-card insight-flow-card--action"><header><span class="insight-flow-card__step">03</span><span class="insight-flow-card__eyebrow">NEXT STEP</span></header><h3>What Should You Do?</h3><p>${recommendation}</p>${roadmapAction}<small class="insight-action-note">A suggested action based on illustrative signals.</small></article></div><div class="insight-evidence-block"><header class="insight-evidence-heading"><div><span class="section-kicker">Evidence trail</span><h3>Evidence</h3><p>Prototype signal summaries only; no external sources are connected.</p></div><span class="insight-evidence-disclaimer"><i data-lucide="info"></i>Not verified research</span></header><div class="insight-evidence-grid">${evidence.map((item, index) => `<article class="insight-evidence-card" style="--evidence-delay:${index * 65}ms"><span class="insight-evidence-card__icon"><i data-lucide="${item.icon}"></i></span><div class="insight-evidence-card__body"><span class="insight-evidence-card__type">${item.type}  —  Demo</span><h4>${item.title}</h4><time>Prototype period  —  Aug 2026</time><p>${item.reason}</p><button type="button" data-insight-scroll="${item.type === 'Job Demand Signal' ? 'live-market-intelligence' : 'current-skill-intelligence'}">View Evidence <i data-lucide="arrow-right"></i></button></div></article>`).join('')}</div></div></section>`;
}

function refreshInsightRecommendationSection() {
  const section = document.querySelector('#insight-recommendations');
  if (!section) return;
  section.outerHTML = renderInsightRecommendationSection();
  lucide.createIcons();
  bindInsightRecommendationEvents();
  bindRoadmapEvents();
}

function bindInsightRecommendationEvents() {
  document.querySelectorAll('[data-insight-scroll]').forEach(button => button.addEventListener('click', event => {
    if (button.tagName === 'A') event.preventDefault();
    document.getElementById(button.dataset.insightScroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

function renderLiveMarketSection() {
  return `<section class="home-section market-intelligence-section" id="live-market-intelligence" aria-labelledby="live-market-section-title"><div class="home-section__heading"><div><span class="section-kicker">Workforce signals</span><h2 id="live-market-section-title">Market Intelligence</h2><p>Understand how companies and market signals are changing across your selected scope.</p></div></div><div class="market-intelligence-grid"><section class="market-demand-module market-trend-module">${renderMarketTrendCard({ home: true })}</section><section class="market-demand-module analytics-market-companies">${renderTopMarketCompaniesCard()}</section></div></section>`;
}

function refreshExploreDashboard(previousValues = null) {
  const focus = document.querySelector('.explore-intelligence');
  if (focus) focus.outerHTML = renderExploreFocusSelector();
  refreshSkillIntelligenceSection(previousValues);
  refreshInsightRecommendationSection();
  if (['roles', 'companies', 'technologies', 'markets'].includes(intelligenceExplorerState.type)) {
    const market = document.querySelector('#live-market-intelligence');
    if (market) market.outerHTML = renderLiveMarketSection();
    lucide.createIcons(); bindMarketTrendEvents(); bindJobTrendEvents(); bindMiniChartTooltips();
  }
  const roadmap = document.querySelector('#active-learning-roadmap');
  if (roadmap) { roadmap.outerHTML = renderLearningRoadmapPreview(); bindRoadmapEvents(); }
  const liveIntelligence = document.querySelector('#live-intelligence');
  if (liveIntelligence) liveIntelligence.outerHTML = renderLiveIntelligenceSection();
  const career = document.querySelector('#career-opportunity-preview');
  if (career) career.outerHTML = renderCareerOpportunityPreview();
  lucide.createIcons();
  bindExploreIntelligenceEvents();
  bindLiveIntelligenceEvents();
}

function bindLiveIntelligenceEvents() {
  document.querySelectorAll('[data-live-scroll]:not([data-live-bound])').forEach(link => {
    link.dataset.liveBound = 'true';
    link.addEventListener('click', event => {
      event.preventDefault();
      document.getElementById(link.dataset.liveScroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}


function renderRedesignedPersonalContext() {
  const selectedLoc = dashboardState.selectedLocation || 'Bangalore, India';
  const isOpen = dashboardState.isLocationMenuOpen || false;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const locations = ['Global', 'India', 'Tamil Nadu', 'Chennai', 'Bangalore, India', 'Hyderabad', 'Pune', 'Remote'];

  return `
    <section class="personal-context-hero" aria-label="Personal Intelligence Workspace">
      <div class="personal-context__aura"></div>
      <div class="personal-context__main">
        <span class="personal-context__kicker">
          <i data-lucide="sparkles"></i> PERSONAL INTELLIGENCE WORKSPACE
        </span>
        <h1 class="personal-context__title">${greeting}, <span class="title-name">${user.shortName}</span>.</h1>
      </div>

      <div class="personal-context__status-location">
        <div class="personal-context__live-status" aria-label="Prototype intelligence status">
          <span class="location-control__kicker">LIVE STATUS</span>
          <span class="personal-context__status-value"><span class="status-live-dot"></span>Simulated intelligence signal</span>
        </div>
        <div class="personal-context__location-wrap">
          <span class="location-control__kicker">CURRENT LOCATION</span>
          <div class="location-picker-container" id="locationPickerContainer">
            <button class="location-picker-btn" id="locationPickerBtn" type="button" aria-haspopup="listbox" aria-controls="locationPopoverMenu" aria-expanded="${isOpen ? 'true' : 'false'}">
              <i data-lucide="map-pin" class="location-icon"></i>
              <span class="location-picker-label">${selectedLoc}</span>
              <i data-lucide="chevron-down" class="location-chevron"></i>
            </button>

            ${isOpen ? `
              <div class="location-popover-menu" id="locationPopoverMenu" role="listbox" aria-label="Choose a demo location">
                <div class="location-popover-header">
                  <strong>Choose a location</strong>
                  <span>Demo setting · no GPS tracking</span>
                </div>
                <div class="location-popover-body">
                  ${locations.map(location => `
                    <button type="button" role="option" aria-selected="${location === selectedLoc ? 'true' : 'false'}" class="location-option-item ${location === selectedLoc ? 'is-selected' : ''}" data-location-id="${location}" data-location-label="${location}">
                      <span>${location}</span>
                      ${location === selectedLoc ? '<i data-lucide="check"></i>' : ''}
                    </button>
                  `).join('')}
                </div>
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderRedesignedIntelligenceOverview() {
  const currentSkill = overviewData.skill.name;
  const skillChange = overviewData.skill.change;
  const skillDirection = skillChange < 0 ? 'down' : 'up';
  const marketCompany = overviewData.market.company;
  const marketChange = overviewData.market.change;
  const marketDirection = marketChange < 0 ? 'down' : 'up';
  const openRoles = (homeSimState.jobsOpenRoles ?? getJobSummary() ?? overviewData.jobs.openRoles).toLocaleString();
  const jobRole = overviewData.jobs.role;
  const jobChange = overviewData.jobs.change;
  const jobDirection = jobChange < 0 ? 'down' : 'up';

  const roadmapActive = ['active', 'paused'].includes(roadmapState.status);
  const roadmapTitle = roadmapActive ? (roadmapState.title || (roadmapState.skill ? `${roadmapState.skill} — Development` : overviewData.roadmap.title)) : 'No Active Roadmap';
  const roadmapProgress = roadmapActive ? (roadmapState.progress ?? overviewData.roadmap.progress) : 0;
  const roadmapStep = roadmapActive ? (roadmapState.currentStep?.name || overviewData.roadmap.currentStep) : 'Choose a learning path';
  const skillTrendLabel = skillDirection === 'down' ? '↓ Decreasing' : '↑ Increasing';
  const marketTrendLabel = marketDirection === 'down' ? '↓ Decreasing' : '↑ Increasing';
  const jobTrendLabel = jobDirection === 'down' ? '↓ Decreasing' : '↑ Increasing';

  return `
    <section class="intelligence-overview-strip" aria-label="Intelligence Overview" aria-describedby="intelligence-overview-description">
      <h2 class="sr-only" id="intelligence-overview-description">A snapshot of current skill, market, hiring, and roadmap signals. Prototype values update periodically.</h2>
      <div class="overview-strip__container">
        <a class="overview-card-v2 overview-card-v2--skill" href="#/individual/skills" aria-label="Open Skill Intelligence for ${currentSkill}">
          <div class="overview-card-header">
            <div class="overview-badge-group">
              <span class="overview-kicker">SKILL</span>
              <span class="overview-status-text">Prototype trend</span>
            </div>
            <span class="overview-nav-icon" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span>
          </div>
          <div class="overview-card-body">
            <strong class="overview-entity-name">${currentSkill}</strong>
            <div class="overview-metric-row">
              <span class="overview-direction ${skillDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-direction="skill">${skillTrendLabel}</span>
              <strong class="overview-change-value ${skillDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-value="skill">${skillChange > 0 ? '+' : ''}${skillChange.toFixed(1)}%</strong>
            </div>
          </div>
          <div class="overview-card-footer overview-card-footer--skill">
            ${renderSkillMiniChart(overviewData.skill.chartPoints, skillDirection)}
            <span class="overview-chart-caption">Illustrative skill trend</span>
          </div>
        </a>

        <a class="overview-card-v2 overview-card-v2--market" href="#/individual/market-insights" aria-label="Open Market Intelligence for ${marketCompany}">
          <div class="overview-card-header">
            <div class="overview-badge-group">
              <span class="overview-kicker">MARKET</span>
              <span class="overview-status-text">Prototype market signal</span>
            </div>
            <span class="overview-nav-icon" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span>
          </div>
          <div class="overview-card-body">
            <strong class="overview-entity-name">${marketCompany}</strong>
            <div class="overview-metric-row">
              <span class="overview-direction ${marketDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-direction="market">${marketTrendLabel}</span>
              <strong class="overview-change-value ${marketDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-value="market">${marketChange > 0 ? '+' : ''}${marketChange.toFixed(1)}%</strong>
            </div>
          </div>
          <div class="overview-card-footer overview-card-footer--market">
            ${renderMarketMiniChart(overviewData.market.chartPoints, marketDirection)}
            <span class="overview-chart-caption">Illustrative market movement</span>
          </div>
        </a>

        <a class="overview-card-v2 overview-card-v2--jobs" href="#/individual/career" aria-label="Open Career and Job Intelligence for ${jobRole}">
          <div class="overview-card-header">
            <div class="overview-badge-group">
              <span class="overview-kicker">JOB TREND</span>
              <span class="overview-status-text">Illustrative hiring</span>
            </div>
            <span class="overview-nav-icon" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span>
          </div>
          <div class="overview-card-body">
            <strong class="overview-entity-name">${openRoles} open roles</strong>
            <div class="overview-metric-row">
              <span class="overview-direction ${jobDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-direction="jobs">${jobTrendLabel}</span>
              <strong class="overview-change-value ${jobDirection === 'down' ? 'is-negative' : 'is-positive'}" data-overview-value="jobs">${jobChange > 0 ? '+' : ''}${jobChange.toFixed(1)}%</strong>
            </div>
            <span class="overview-sub-label overview-job-role">${jobRole} hiring signal</span>
          </div>
          <div class="overview-card-footer overview-card-footer--jobs">
            ${renderJobsMiniBars(overviewData.jobs.bars, jobDirection)}
            <span class="overview-chart-caption">Illustrative hiring movement</span>
          </div>
        </a>

        <a class="overview-card-v2 overview-card-v2--roadmap" href="#/individual/learning" aria-label="Open Learning roadmap: ${roadmapTitle}, ${roadmapProgress}% complete">
          <div class="overview-card-header">
            <div class="overview-badge-group">
              <span class="overview-kicker">ROADMAP</span>
              <span class="overview-status-text">${roadmapActive ? (roadmapState.status === 'paused' ? 'Paused' : 'Active') : 'Ready to start'}</span>
            </div>
            <span class="overview-nav-icon" aria-hidden="true"><i data-lucide="arrow-up-right"></i></span>
          </div>
          <div class="overview-card-body">
            <strong class="overview-entity-name">${roadmapTitle}</strong>
            <div class="overview-metric-row">
              <span class="overview-direction overview-roadmap-step">Current step · <strong data-overview-value="roadmap-step">${roadmapStep}</strong></span>
              <strong class="overview-change-value overview-roadmap-value" data-overview-value="roadmap">${roadmapProgress}%</strong>
            </div>
          </div>
          <div class="overview-card-footer overview-card-footer--roadmap">
            ${renderRoadmapMiniProgress(roadmapActive, roadmapProgress)}
            <span class="overview-chart-caption">Roadmap progress</span>
          </div>
        </a>

      </div>
    </section>
  `;
}

function getConsoleIntelligenceData({ mode, query = '', entity = '', location = 'Bangalore, India', timeRange = '6 Months' }) {
  const qLower = (query || '').toLowerCase();
  
  if (mode === 'skills') {
    const skillName = entity || (qLower.includes('python') ? 'Python' : qLower.includes('machine learning') ? 'Machine Learning' : qLower.includes('react') ? 'React' : 'Python');
    
    if (qLower.includes('python demand') || (qLower.includes('python') && qLower.includes('changing')) || skillName === 'Python') {
      return {
        title: `Why Python Demand Is Accelerating in ${location}`,
        entity: 'Python',
        domainKicker: 'SKILL INTELLIGENCE SYNTHESIS',
        changePercent: '+22.4% Momentum',
        whatChangedHeading: `Python requisitions jumped +22.4% over the last ${timeRange}`,
        whatChangedBody: `Demand is surging across ${location} technology corridors, driven by generative AI application orchestration (LangChain, LlamaIndex), agentic workflows, and high-performance ML model serving. Python has consolidated its lead as the primary runtime for enterprise AI applications.`,
        whyItMattersHeading: `Directly leverages your verified core competencies`,
        whyItMattersBody: `Python is already your strongest verified skill (94/100). The market is pivoting from basic scripting toward async service orchestration, streaming inference, and custom tool binding.`,
        impactTag: 'High Career Leverage',
        dataHeading: `Telemetry Across 18,420 Active Postings in ${location}`,
        metrics: [
          { label: 'Active Requisitions', value: '18,420 roles' },
          { label: 'Requisition Velocity', value: '+22.4% YoY' },
          { label: 'Compensation Band', value: '₹32L — ₹55L' },
          { label: 'Profile Alignment', value: '96% Match' }
        ],
        actionHeading: `Deepen Applied Async & Agentic Architecture`,
        actionBody: `Build an asynchronous multi-agent inference service with streaming responses to match senior AI Engineer requisitions.`,
        detailsHref: '#/individual/skills'
      };
    }

    if (qLower.includes('trending') || qLower.includes('which of my skills')) {
      return {
        title: `Your Verified Skills Trend Assessment in ${location}`,
        entity: 'Skill Portfolio',
        domainKicker: 'SKILL INTELLIGENCE SYNTHESIS',
        changePercent: '+18.4% Outperformance',
        whatChangedHeading: `3 of your 5 verified skills are accelerating faster than the regional market average`,
        whatChangedBody: `Python (+22.4%), Machine Learning (+18.4%), and AWS Cloud (+15.2%) are seeing sustained requisition acceleration across ${location} tech employers. Legacy backend requirements are being consolidated into full-lifecycle AI engineering stacks.`,
        whyItMattersHeading: `Puts your profile in the top 8th percentile for AI engineering roles`,
        whyItMattersBody: `Your verified combination of Python and ML provides a strong foundation. Bridging your CUDA and Deep Learning gap elevates you from application developer to AI systems architect.`,
        impactTag: 'Top 8% Candidate Ranking',
        dataHeading: `Regional Alignment Telemetry in ${location}`,
        metrics: [
          { label: 'Top Trending Skill', value: 'Python (+22.4%)' },
          { label: 'Portfolio Health', value: '91/100 Index' },
          { label: 'Qualified Roles', value: '3,840 positions' },
          { label: 'Hiring Urgency', value: 'High Momentum' }
        ],
        actionHeading: `Capitalize on Market Momentum with Targeted Project`,
        actionBody: `Deploy a production-grade inference API to demonstrate full stack mastery of your top 3 trending competencies.`,
        detailsHref: '#/individual/skills'
      };
    }

    if (qLower.includes('learn next') || qLower.includes('what skill')) {
      return {
        title: `High-ROI Skill Acquisition Recommendation for AI Roles`,
        entity: 'CUDA Systems & GPU Acceleration',
        domainKicker: 'SKILL INTELLIGENCE SYNTHESIS',
        changePercent: '+34.2% Premium',
        whatChangedHeading: `CUDA & High-Throughput Inference requisitions rose +34.2%`,
        whatChangedBody: `Due to acute GPU memory constraints and enterprise on-premise model deployments, candidates with CUDA systems knowledge and TensorRT optimization command the fastest interview turnaround times in ${location}.`,
        whyItMattersHeading: `Bridges your primary capability gap for senior compensation tiers`,
        whyItMattersBody: `Your profile already has strong Python and ML foundations. Adding low-level GPU acceleration closes your single largest technical differentiator and unlocks ₹40L+ compensation bands.`,
        impactTag: 'High-Impact Gap Closure',
        dataHeading: `Talent Supply vs Employer Demand in ${location}`,
        metrics: [
          { label: 'Talent Scarcity', value: 'Acute (Top 3%)' },
          { label: 'Salary Premium', value: '+35% vs baseline' },
          { label: 'Open Postings', value: '4,120 positions' },
          { label: 'Estimated Ramp', value: '6 Weeks' }
        ],
        actionHeading: `Activate 6-Week CUDA Systems Learning Roadmap`,
        actionBody: `Follow our structured milestone path covering GPU kernel architecture, memory hierarchies, and applied TensorRT optimization.`,
        detailsHref: '#/individual/skills'
      };
    }

    // Default skill query / Machine Learning
    return {
      title: `${skillName} Growth Trajectory & Hiring Demand in ${location}`,
      entity: skillName,
      domainKicker: 'SKILL INTELLIGENCE SYNTHESIS',
      changePercent: '+18.4% Growth',
      whatChangedHeading: `${skillName} requisitions expanded +18.4% over ${timeRange}`,
      whatChangedBody: `Enterprise investments across ${location} are shifting rapidly from basic machine learning prototypes to automated production pipelines and low-latency inference systems. Requisitions specifying ${skillName} remain among the most competitive.`,
      whyItMattersHeading: `Strong alignment with your current background and target role`,
      whyItMattersBody: `Your verified profile demonstrates core competency in this domain. Deepening your practical project portfolio will differentiate you in senior technical evaluations.`,
      impactTag: 'Core Career Focus',
      dataHeading: `Telemetry & Market Metrics in ${location}`,
      metrics: [
        { label: 'Active Postings', value: '14,200 roles' },
        { label: 'Requisition Momentum', value: '+18.4% Growth' },
        { label: 'Avg Base Salary', value: '₹28L — ₹48L' },
        { label: 'Profile Fit', value: '92% Score' }
      ],
      actionHeading: `Build ${skillName} Project & Learning Roadmap`,
      actionBody: `Complete an end-to-end production pipeline milestone to qualify for Tier-1 technology employer requisitions.`,
      detailsHref: '#/individual/skills'
    };
  }

  if (mode === 'companies') {
    const compName = entity || (qLower.includes('nvidia') ? 'NVIDIA' : qLower.includes('microsoft') ? 'Microsoft' : qLower.includes('google') ? 'Google' : 'NVIDIA');

    if (qLower.includes('nvidia') || compName === 'NVIDIA') {
      return {
        title: `Why NVIDIA Is Gaining Market Momentum in ${location}`,
        entity: 'NVIDIA',
        domainKicker: 'MARKET INTELLIGENCE SYNTHESIS',
        changePercent: '+28.4% Hiring Surge',
        whatChangedHeading: `NVIDIA accelerated regional engineering hiring by +28.4%`,
        whatChangedBody: `NVIDIA has expanded research and engineering centers in ${location}, aggressively staffing CUDA systems, DGX cloud platform services, and enterprise inference runtime teams. Open engineering requisitions increased to 1,820 active roles.`,
        whyItMattersHeading: `Direct referral alignment for AI Systems engineers`,
        whyItMattersBody: `NVIDIA's regional engineering teams prioritize engineers with solid Python backends who understand GPU architecture, memory limits, and hardware-software co-design.`,
        impactTag: 'Tier-1 Target Employer',
        dataHeading: `NVIDIA Telemetry & Hiring Indicators in ${location}`,
        metrics: [
          { label: 'Active Requisitions', value: '1,820 roles' },
          { label: 'Engineering Share', value: '72% of openings' },
          { label: 'Retention Rate', value: '94% Industry Lead' },
          { label: 'Hiring Urgency', value: 'Immediate' }
        ],
        actionHeading: `Target NVIDIA Engineering Requisition Alignment`,
        actionBody: `Align your project portfolio to NVIDIA's core open-source repositories and complete a GPU benchmark capstone.`,
        detailsHref: '#/individual/market-insights'
      };
    }

    if (qLower.includes('which companies are growing') || qLower.includes('growing')) {
      return {
        title: `Top Growing Technology Employers in ${location}`,
        entity: 'Leading Enterprise Firms',
        domainKicker: 'MARKET INTELLIGENCE SYNTHESIS',
        changePercent: '+24.8% Average Velocity',
        whatChangedHeading: `NVIDIA (+28.4%), OpenAI (+32.5%), and Microsoft (+14.8%) lead growth`,
        whatChangedBody: `Across ${location}, tier-1 cloud and AI providers have opened 6,400+ new engineering requisitions in the past 60 days, focusing heavily on infrastructure scalability, vector retrieval engines, and high-concurrency backend services.`,
        whyItMattersHeading: `Direct correlation with your Python and AI Engineer target`,
        whyItMattersBody: `These high-growth firms offer the strongest compensation packages and career acceleration. Their technical interviews emphasize production-grade system design over purely theoretical coding.`,
        impactTag: 'High Growth Cluster',
        dataHeading: `Employer Telemetry Summary across 2,480 Firms`,
        metrics: [
          { label: 'Total Open Roles', value: '6,400+ roles' },
          { label: 'Avg Hiring Growth', value: '+24.8% YoY' },
          { label: 'Top Hiring Sector', value: 'Enterprise AI Cloud' },
          { label: 'Candidate Demand', value: 'Very High' }
        ],
        actionHeading: `Calibrate Skill Profile for Leading Tech Employers`,
        actionBody: `Build an enterprise-grade roadmap targeting the specific architectural patterns favored by Microsoft and NVIDIA.`,
        detailsHref: '#/individual/market-insights'
      };
    }

    // Default company / technologies
    return {
      title: `Technologies Enterprise Companies Are Investing In (${location})`,
      entity: compName,
      domainKicker: 'MARKET INTELLIGENCE SYNTHESIS',
      changePercent: '+42% GenAI Spend',
      whatChangedHeading: `Enterprise tech investments concentrated in Generative AI and GPU Cloud`,
      whatChangedBody: `Telemetry shows strong capital allocation into automated ML operations (+42%), distributed computing clusters (+31%), and enterprise security layers (+26%). Hiring for backend infrastructure engineering has risen +14.8% in ${location}.`,
      whyItMattersHeading: `High match with your target role qualifications`,
      whyItMattersBody: `Leading companies actively source candidates with Python and cloud infrastructure backgrounds, placing heavy weight on scalable API design and verifiable project portfolios.`,
      impactTag: 'Strategic Enterprise Target',
      dataHeading: `Telemetry Indicators for ${compName} in ${location}`,
      metrics: [
        { label: 'Open Engineering Roles', value: '2,480 openings' },
        { label: 'Tech Stack Momentum', value: '+14.8% YoY' },
        { label: 'Target Role Match', value: '91% Alignment' },
        { label: 'Regional Focus', value: `${location} Hub` }
      ],
      actionHeading: `Build Enterprise Readiness Roadmap for ${compName}`,
      actionBody: `Prepare for technical evaluations by aligning your learning milestones with enterprise tech investment patterns.`,
      detailsHref: '#/individual/market-insights'
    };
  }

  // mode === 'roles' (Job Intelligence)
  const roleName = entity || (qLower.includes('ai engineer') ? 'AI Engineer' : qLower.includes('data scientist') ? 'Data Scientist' : qLower.includes('cloud architect') ? 'Cloud Architect' : 'AI Engineer');

  if (qLower.includes('which companies are hiring') || qLower.includes('hiring')) {
    return {
      title: `Top Hiring Employers for ${roleName} in ${location}`,
      entity: roleName,
      domainKicker: 'JOB INTELLIGENCE SYNTHESIS',
      changePercent: '2,480 Active Employers',
      whatChangedHeading: `42,180 total engineering requisitions open across ${location}`,
      whatChangedBody: `Employers including Microsoft, NVIDIA, Google, and 2,400+ regional enterprises are actively recruiting for ${roleName} talent. 64% of technology companies opened new engineering openings in the last 30 days.`,
      whyItMattersHeading: `Favorable hiring dynamics for qualified profiles`,
      whyItMattersBody: `Employers are competing aggressively for candidates who combine applied Python proficiency with hands-on understanding of model deployment, resulting in faster hiring cycles and sign-on bonuses.`,
      impactTag: 'Strong Candidate Leverage',
      dataHeading: `Employer Hiring Telemetry in ${location}`,
      metrics: [
        { label: 'Open Requisitions', value: '42,180 roles' },
        { label: 'Active Employers', value: '2,480 firms' },
        { label: '30-Day Growth', value: '+18.2% acceleration' },
        { label: 'Your Profile Match', value: '88% Alignment' }
      ],
      actionHeading: `Review Verified Open Requisitions`,
      actionBody: `Examine matching requisitions and tailor your portfolio projects to meet Tier-1 employer specifications.`,
      detailsHref: '#/individual/career'
    };
  }

  if (qLower.includes('roles are growing') || qLower.includes('growing')) {
    return {
      title: `High-Growth Technology Roles in ${location}`,
      entity: 'Engineering Roles',
      domainKicker: 'JOB INTELLIGENCE SYNTHESIS',
      changePercent: '+26.4% Acceleration',
      whatChangedHeading: `AI Engineer ranks #1 in hiring demand momentum (+26.4%)`,
      whatChangedBody: `AI Engineer, ML Systems Architect (+22.1%), and Cloud Infrastructure Lead (+17.8%) represent the fastest accelerating role profiles in ${location}. Traditional software development roles are consolidating into AI-assisted development.`,
      whyItMattersHeading: `Validates your career transition trajectory`,
      whyItMattersBody: `Your target role of AI Engineer is experiencing unprecedented employer demand. Position yourself ahead of applicants by closing the practical systems optimization gap.`,
      impactTag: '#1 Demand Role',
      dataHeading: `Role Demand Momentum in ${location}`,
      metrics: [
        { label: 'Role Ranking', value: '#1 Fastest Growing' },
        { label: 'Demand Momentum', value: '+26.4% Growth' },
        { label: 'Avg Salary Tier', value: '₹30L — ₹55L' },
        { label: 'Market Urgency', value: 'High Scarcity' }
      ],
      actionHeading: `Activate Role Alignment Roadmap`,
      actionBody: `Build an interview-ready roadmap focused specifically on passing AI Engineer system architecture screenings.`,
      detailsHref: '#/individual/career'
    };
  }

  // Default job query / What skills are appearing
  return {
    title: `Key Requisition Skills & Requirements for ${roleName} in ${location}`,
    entity: roleName,
    domainKicker: 'JOB INTELLIGENCE SYNTHESIS',
    changePercent: '92% Profile Match',
    whatChangedHeading: `Python, Machine Learning, and Cloud APIs appear in 78% of postings`,
    whatChangedBody: `Employers across ${location} require verified proficiency in Python (78%), ML inference architectures (64%), and AWS/Cloud platforms (58%). Emerging requirements include CUDA kernel optimization and vector database indexing.`,
    whyItMattersHeading: `You currently possess 3 of the 4 most requested core skills`,
    whyItMattersBody: `Your profile is 92% aligned with standard requirements. Bridging your CUDA and Deep Learning gap places you into the 98th percentile of eligible candidates.`,
    impactTag: '92% Profile Fit',
    dataHeading: `Requisition Skill Frequency Telemetry`,
    metrics: [
      { label: 'Python Frequency', value: '78% of postings' },
      { label: 'ML Inference', value: '64% of postings' },
      { label: 'Cloud Architecture', value: '58% of postings' },
      { label: 'Candidate Percentile', value: 'Top 8%' }
    ],
    actionHeading: `Complete Role Alignment Roadmap`,
    actionBody: `Start your customized learning milestones to bridge the remaining skill gaps and maximize interview invitations.`,
    detailsHref: '#/individual/career'
  };
}

function renderRedesignedConsole() {
  const isDomainSelected = intelligenceExplorerState.domainSelected === true;
  const mode = intelligenceExplorerState.type || 'skills';
  const location = dashboardState.selectedLocation || dashboardState.market || 'Bangalore, India';
  const timeRange = intelligenceExplorerState.timeRange || dashboardState.timeRange || '6 Months';
  const isAnalyzing = intelligenceExplorerState.isAnalyzing;
  const analysisStep = intelligenceExplorerState.analysisStep || 0;
  const hasSearched = intelligenceExplorerState.hasSearched;
  const isRoadmapPreviewing = intelligenceExplorerState.isRoadmapPreviewing || false;

  const currentSkill = dashboardState.selectedSkill || 'Machine Learning';
  const currentCompany = intelligenceExplorerState.selected.companies || 'Microsoft';
  const currentRole = intelligenceExplorerState.selected.roles || 'AI Engineer';

  // ============================================================
  // FIRST STEP: If domain is NOT selected yet, show clear choices
  // ============================================================
  if (!isDomainSelected) {
    return `
      <section class="intelligence-console-hero" data-console-theme="skills" aria-label="Intelligence Console">
        <div class="console-bg-glow"></div>
        <div class="console-domain-selection">
          <header class="console-domain-selection__header">
            <div class="console-domain-selection__title-wrap">
              <span class="v2-kicker" style="font-size:11px; font-weight:800; color:var(--b-primary); text-transform:uppercase; letter-spacing:0.06em;">CORE INTELLIGENCE CONSOLE</span>
              <h2>What do you want to understand?</h2>
              <p>Select an intelligence domain below to activate personalized analysis, real-time market signals, and strategic next actions.</p>
            </div>
            <span class="console-domain-selection__badge">
              <i data-lucide="sparkles"></i> Step 1 · Select Intelligence
            </span>
          </header>

          <div class="console-domain-grid">
            <!-- Skill Intelligence Choice -->
            <article class="console-domain-card" data-select-domain="skills" tabindex="0" role="button" aria-label="Select Skill Intelligence">
              <div class="console-domain-card__icon-wrap">
                <div class="console-domain-card__icon">
                  <i data-lucide="brain-circuit"></i>
                </div>
                <span class="console-domain-card__step-tag">Domain 01</span>
              </div>
              <h3>Skill Intelligence</h3>
              <p>Explore skill demand trajectories, rising competencies, salary impact, and personalized learning gap diagnostics.</p>
              <div class="console-domain-card__badges">
                <span class="console-domain-badge"><i data-lucide="trending-up"></i> +18.4% Momentum</span>
                <span class="console-domain-badge">84 Tracked Skills</span>
              </div>
              <button type="button" class="console-domain-card__cta" tabindex="-1">
                <span>Select Skill Intelligence</span> <i data-lucide="arrow-right"></i>
              </button>
            </article>

            <!-- Market Intelligence Choice -->
            <article class="console-domain-card" data-select-domain="companies" tabindex="0" role="button" aria-label="Select Market Intelligence">
              <div class="console-domain-card__icon-wrap">
                <div class="console-domain-card__icon">
                  <i data-lucide="building-2"></i>
                </div>
                <span class="console-domain-card__step-tag">Domain 02</span>
              </div>
              <h3>Market Intelligence</h3>
              <p>Track enterprise tech investments, institutional hiring momentum, cloud modernization, and strategic bets.</p>
              <div class="console-domain-card__badges">
                <span class="console-domain-badge"><i data-lucide="layers"></i> 2,480 Active Firms</span>
                <span class="console-domain-badge">Tech Adoption</span>
              </div>
              <button type="button" class="console-domain-card__cta" tabindex="-1">
                <span>Select Market Intelligence</span> <i data-lucide="arrow-right"></i>
              </button>
            </article>

            <!-- Job Intelligence Choice -->
            <article class="console-domain-card" data-select-domain="roles" tabindex="0" role="button" aria-label="Select Job Intelligence">
              <div class="console-domain-card__icon-wrap">
                <div class="console-domain-card__icon">
                  <i data-lucide="briefcase"></i>
                </div>
                <span class="console-domain-card__step-tag">Domain 03</span>
              </div>
              <h3>Job Intelligence</h3>
              <p>Analyze live role requisitions, regional market dynamics, vacancy velocity, and profile alignment scores.</p>
              <div class="console-domain-card__badges">
                <span class="console-domain-badge"><i data-lucide="user-check"></i> 42,180 Open Roles</span>
                <span class="console-domain-badge">92% Profile Match</span>
              </div>
              <button type="button" class="console-domain-card__cta" tabindex="-1">
                <span>Select Job Intelligence</span> <i data-lucide="arrow-right"></i>
              </button>
            </article>
          </div>
        </div>
      </section>
    `;
  }

  // ============================================================
  // ACTIVE WORKSPACE (Domain is selected): Desktop 2-column layout
  // ============================================================

  // Dynamic suggested prompts map matching Step 3 requirements strictly
  const promptsMap = {
    skills: [
      'Why is Python demand changing?',
      'Which of my skills are trending?',
      'What skill should I learn next?',
      'Why is Machine Learning growing?'
    ],
    companies: [
      'Which companies are growing?',
      'Why is NVIDIA gaining market momentum?',
      'Which technologies are companies investing in?'
    ],
    roles: [
      'Which companies are hiring?',
      'Which roles are growing?',
      'What skills are appearing in current jobs?'
    ]
  };

  const suggestedPrompts = promptsMap[mode] || promptsMap.skills;

  // Domain visual transformation metadata
  const domainMeta = {
    skills: {
      theme: 'skills',
      title: 'Skill Intelligence System',
      icon: 'brain-circuit',
      helperText: 'Analyzing skill demand curves, adjacent competencies & emerging requirements.',
      statusText: 'Ready to analyze skill trajectories',
      analyzingText: 'ANALYZING SKILL SIGNALS',
      targetItem: currentSkill,
      placeholder: `Ask anything about ${currentSkill} demand, trends, or trajectory in ${location}...`
    },
    companies: {
      theme: 'companies',
      title: 'Market Intelligence System',
      icon: 'building-2',
      helperText: 'Tracking organizational hiring velocity, tech adoption & enterprise investment signals.',
      statusText: 'Ready to analyze company momentum',
      analyzingText: 'ANALYZING MARKET SIGNALS',
      targetItem: currentCompany,
      placeholder: `Ask anything about ${currentCompany} investment, hiring, or signals in ${location}...`
    },
    roles: {
      theme: 'roles',
      title: 'Job Intelligence System',
      icon: 'briefcase',
      helperText: 'Evaluating open requisitions, compensation momentum & role fit percentiles.',
      statusText: 'Ready to evaluate role opportunities',
      analyzingText: 'ANALYZING JOB SIGNALS',
      targetItem: currentRole,
      placeholder: `Ask anything about ${currentRole} requisitions or skill requirements in ${location}...`
    }
  };

  const currentMeta = domainMeta[mode] || domainMeta.skills;

  // Dynamic Context Controls (Left Rail)
  let controlsHtml = '';
  if (mode === 'skills') {
    const scope = intelligenceExplorerState.skillScope || 'My Skills';
    let skillsList = ['Python', 'Machine Learning', 'React', 'AWS', 'TypeScript'];
    if (scope === 'Favorite Skills') {
      skillsList = ['Machine Learning', 'Python', 'React', 'AWS'];
    } else if (scope === 'All Skills') {
      skillsList = ['Machine Learning', 'Python', 'React', 'Generative AI', 'CUDA', 'Data Engineering', 'TypeScript', 'Docker'];
    }

    controlsHtml = `
      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Skill Scope</span>
        </div>
        <div class="console-scope-pills" role="radiogroup" aria-label="Skill Scope">
          ${['My Skills', 'Favorite Skills', 'All Skills', 'Add Skill'].map(s => `
            <button type="button" class="console-scope-pill ${s === scope ? 'is-active' : ''}" data-console-skill-scope="${s}">${s}</button>
          `).join('')}
        </div>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Active Skills</span>
          <small style="color:#887898; font-weight:600;">${skillsList.length} options</small>
        </div>
        <div class="console-chips-grid">
          ${skillsList.map(s => `
            <button type="button" class="console-chip-btn ${s === currentSkill ? 'is-active' : ''}" data-select-skill-chip="${s}">
              ${s}
            </button>
          `).join('')}
        </div>
        ${scope === 'Add Skill' ? `
          <div class="console-add-item-wrap" style="margin-top:6px;">
            <input type="text" class="console-add-input" id="newSkillInput" placeholder="Add custom skill..." />
            <button type="button" class="console-add-submit" id="submitNewSkillBtn">Add</button>
          </div>
        ` : ''}
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Location</span>
        </div>
        <select class="console-select" id="consoleLocationSelect" aria-label="Location Context">
          ${marketOptions.map(m => `<option ${m === location ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Time Range</span>
        </div>
        <div class="console-time-pills">
          ${['1 Month', '3 Months', '6 Months', '1 Year'].map(t => `
            <button type="button" class="console-time-pill ${t === timeRange ? 'is-active' : ''}" data-console-time-range="${t}">${t}</button>
          `).join('')}
        </div>
      </div>
    `;
  } else if (mode === 'companies') {
    const scope = intelligenceExplorerState.companyScope || 'My/Favorite Companies';
    let companiesList = ['Microsoft', 'NVIDIA', 'Google', 'OpenAI'];
    if (scope === 'All Companies') {
      companiesList = ['Microsoft', 'NVIDIA', 'Google', 'OpenAI', 'TSMC', 'TCS', 'Amazon', 'Meta'];
    }

    controlsHtml = `
      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Company Scope</span>
        </div>
        <div class="console-scope-pills" role="radiogroup" aria-label="Company Scope">
          ${['My/Favorite Companies', 'All Companies', 'Add Company'].map(s => `
            <button type="button" class="console-scope-pill ${s === scope ? 'is-active' : ''}" data-console-company-scope="${s}">${s}</button>
          `).join('')}
        </div>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Active Companies</span>
          <small style="color:#887898; font-weight:600;">${companiesList.length} firms</small>
        </div>
        <div class="console-chips-grid">
          ${companiesList.map(c => `
            <button type="button" class="console-chip-btn ${c === currentCompany ? 'is-active' : ''}" data-select-company-chip="${c}">
              ${c}
            </button>
          `).join('')}
        </div>
        ${scope === 'Add Company' ? `
          <div class="console-add-item-wrap" style="margin-top:6px;">
            <input type="text" class="console-add-input" id="newCompanyInput" placeholder="Add firm name..." />
            <button type="button" class="console-add-submit" id="submitNewCompanyBtn">Add</button>
          </div>
        ` : ''}
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Location</span>
        </div>
        <select class="console-select" id="consoleLocationSelect" aria-label="Location Context">
          ${marketOptions.map(m => `<option ${m === location ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Time Range</span>
        </div>
        <div class="console-time-pills">
          ${['1 Month', '3 Months', '6 Months', '1 Year'].map(t => `
            <button type="button" class="console-time-pill ${t === timeRange ? 'is-active' : ''}" data-console-time-range="${t}">${t}</button>
          `).join('')}
        </div>
      </div>
    `;
  } else {
    // mode === 'roles' (Job Intelligence)
    const scope = intelligenceExplorerState.jobScope || 'Regional market';
    const rolesList = ['AI Engineer', 'Data Scientist', 'Cloud Architect', 'Backend Engineer', 'Cybersecurity Lead'];

    controlsHtml = `
      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Market Scope</span>
        </div>
        <div class="console-scope-pills" role="radiogroup" aria-label="Market Scope">
          ${['Favorite Companies', 'All Companies', 'Regional market'].map(s => `
            <button type="button" class="console-scope-pill ${s === scope ? 'is-active' : ''}" data-console-job-scope="${s}">${s}</button>
          `).join('')}
        </div>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Target Role</span>
        </div>
        <div class="console-chips-grid">
          ${rolesList.map(r => `
            <button type="button" class="console-chip-btn ${r === currentRole ? 'is-active' : ''}" data-select-role-chip="${r}">
              ${r}
            </button>
          `).join('')}
        </div>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Location</span>
        </div>
        <select class="console-select" id="consoleLocationSelect" aria-label="Location Context">
          ${marketOptions.map(m => `<option ${m === location ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
      </div>

      <div class="console-rail-section">
        <div class="console-rail-label">
          <span>Time Range</span>
        </div>
        <div class="console-time-pills">
          ${['1 Month', '3 Months', '6 Months', '1 Year'].map(t => `
            <button type="button" class="console-time-pill ${t === timeRange ? 'is-active' : ''}" data-console-time-range="${t}">${t}</button>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Right Analysis Stage Content: Scanning, Result, or Idle
  let stageHtml = '';
  if (isAnalyzing) {
    const progressPercent = Math.min(100, Math.round((analysisStep / 5) * 100));
    stageHtml = `
      <div class="console-scanning-glass" aria-live="polite">
        <div class="scanning-top-bar">
          <div class="scanning-orb-wrap">
            <div class="scanning-orb"></div>
            <div class="scanning-orb-ring"></div>
          </div>
          <div class="scanning-title-group">
            <span class="scanning-eyebrow">INTELLIGENCE SCANNER IN PROGRESS</span>
            <h3 class="scanning-headline">${currentMeta.analyzingText}</h3>
            <p class="scanning-subtext">Synthesizing live workforce telemetry for <strong>${currentMeta.targetItem}</strong> in <strong>${location}</strong>...</p>
          </div>
          <div class="scanning-telemetry-badge">
            <span class="telemetry-live-dot"></span>
            <span>Live Stream • Step ${Math.min(5, analysisStep + 1)} of 5</span>
          </div>
        </div>

        <div class="scanning-progress-container">
          <div class="scanning-progress-header">
            <span>Pipeline Progress</span>
            <span class="scanning-progress-percent">${progressPercent}%</span>
          </div>
          <div class="scanning-progress-track">
            <div class="scanning-progress-bar" style="width: ${progressPercent}%;"></div>
          </div>
        </div>

        <div class="scanning-signals-list">
          <div class="scanning-signal-card ${analysisStep >= 1 ? 'is-done' : analysisStep === 0 ? 'is-active' : 'is-pending'}">
            <div class="scanning-signal-status">
              <i data-lucide="${analysisStep >= 1 ? 'check-circle-2' : analysisStep === 0 ? 'loader' : 'circle'}"></i>
            </div>
            <div class="scanning-signal-content">
              <span class="scanning-signal-name">Market demand</span>
              <span class="scanning-signal-detail">Scanning hiring volume, requisition acceleration, and regional density index</span>
            </div>
            <span class="scanning-signal-telemetry">${analysisStep >= 1 ? '+18.4% velocity verified' : analysisStep === 0 ? 'Scanning...' : 'Pending'}</span>
          </div>

          <div class="scanning-signal-card ${analysisStep >= 2 ? 'is-done' : analysisStep === 1 ? 'is-active' : 'is-pending'}">
            <div class="scanning-signal-status">
              <i data-lucide="${analysisStep >= 2 ? 'check-circle-2' : analysisStep === 1 ? 'loader' : 'circle'}"></i>
            </div>
            <div class="scanning-signal-content">
              <span class="scanning-signal-name">Technology signals</span>
              <span class="scanning-signal-detail">Parsing technology adoptions, framework migration, and repo telemetry</span>
            </div>
            <span class="scanning-signal-telemetry">${analysisStep >= 2 ? '14 stack signals ingested' : analysisStep === 1 ? 'Ingesting...' : 'Pending'}</span>
          </div>

          <div class="scanning-signal-card ${analysisStep >= 3 ? 'is-done' : analysisStep === 2 ? 'is-active' : 'is-pending'}">
            <div class="scanning-signal-status">
              <i data-lucide="${analysisStep >= 3 ? 'check-circle-2' : analysisStep === 2 ? 'loader' : 'circle'}"></i>
            </div>
            <div class="scanning-signal-content">
              <span class="scanning-signal-name">Role requirements</span>
              <span class="scanning-signal-detail">Benchmarking qualification tiers, senior vs lead competency requirements</span>
            </div>
            <span class="scanning-signal-telemetry">${analysisStep >= 3 ? '92% qualification match' : analysisStep === 2 ? 'Benchmarking...' : 'Pending'}</span>
          </div>

          <div class="scanning-signal-card ${analysisStep >= 4 ? 'is-done' : analysisStep === 3 ? 'is-active' : 'is-pending'}">
            <div class="scanning-signal-status">
              <i data-lucide="${analysisStep >= 4 ? 'check-circle-2' : analysisStep === 3 ? 'loader' : 'circle'}"></i>
            </div>
            <div class="scanning-signal-content">
              <span class="scanning-signal-name">Location signals</span>
              <span class="scanning-signal-detail">Evaluating regional cluster movements and hiring hubs in ${location}</span>
            </div>
            <span class="scanning-signal-telemetry">${analysisStep >= 4 ? 'Cluster density: High' : analysisStep === 3 ? 'Mapping...' : 'Pending'}</span>
          </div>

          <div class="scanning-signal-card ${analysisStep >= 5 ? 'is-done' : analysisStep === 4 ? 'is-active' : 'is-pending'}">
            <div class="scanning-signal-status">
              <i data-lucide="${analysisStep >= 5 ? 'check-circle-2' : analysisStep === 4 ? 'loader' : 'circle'}"></i>
            </div>
            <div class="scanning-signal-content">
              <span class="scanning-signal-name">User profile</span>
              <span class="scanning-signal-detail">Calculating alignment score with your verified skill graph and target career goal</span>
            </div>
            <span class="scanning-signal-telemetry">${analysisStep >= 5 ? 'Profile alignment: 88/100' : analysisStep === 4 ? 'Synthesizing...' : 'Pending'}</span>
          </div>
        </div>
      </div>
    `;
  } else if (hasSearched) {
    const query = intelligenceExplorerState.question || '';
    const resultData = getConsoleIntelligenceData({
      mode,
      query,
      entity: currentMeta.targetItem,
      location,
      timeRange
    });

    stageHtml = `
      <div class="console-result-surface" aria-live="polite">
        <header class="console-result-header">
          <div class="console-result-header__title">
            <div class="console-result-meta-tags">
              <span class="v2-kicker" style="font-size:10.5px; font-weight:800; color:var(--b-primary); letter-spacing:0.06em;">${resultData.domainKicker}</span>
              <span class="console-badge-pill console-badge-pill--prototype"><i data-lucide="sparkles"></i> Prototype signal</span>
              <span class="console-badge-pill console-badge-pill--simulated"><i data-lucide="activity"></i> Simulated market signal</span>
            </div>
            <h3>${resultData.title}</h3>
            <p class="console-result-subtitle">Context: <strong>${resultData.entity}</strong> • <strong>${location}</strong> • <strong>${timeRange}</strong></p>
          </div>
          <div class="console-result-header__actions">
            <button type="button" class="button" id="saveConsoleResultBtn">
              <i data-lucide="bookmark-plus"></i>
              <span>Save</span>
            </button>
            <button type="button" class="button" id="consoleAskAnotherBtn">
              <i data-lucide="rotate-ccw"></i>
              <span>New Query</span>
            </button>
          </div>
        </header>

        <div class="console-result-blocks">
          <!-- Block 1: What Changed -->
          <article class="console-result-block console-result-block--change">
            <span class="console-result-block__label">01 · What Changed?</span>
            <h4 class="console-result-block__heading">${resultData.whatChangedHeading}</h4>
            <p class="console-result-block__body">${resultData.whatChangedBody}</p>
            <div class="console-result-block__footer">
              <span class="console-pill-signal console-pill-signal--up">
                <i data-lucide="trending-up"></i> ${resultData.changePercent}
              </span>
            </div>
          </article>

          <!-- Block 2: Why It Matters -->
          <article class="console-result-block console-result-block--why">
            <span class="console-result-block__label">02 · Why It Matters</span>
            <h4 class="console-result-block__heading">${resultData.whyItMattersHeading}</h4>
            <p class="console-result-block__body">${resultData.whyItMattersBody}</p>
            <div class="console-result-block__footer">
              <span class="console-pill-signal console-pill-signal--impact">
                <i data-lucide="target"></i> ${resultData.impactTag}
              </span>
            </div>
          </article>

          <!-- Block 3: What The Data Shows -->
          <article class="console-result-block console-result-block--data">
            <span class="console-result-block__label">03 · What The Data Shows</span>
            <h4 class="console-result-block__heading">${resultData.dataHeading}</h4>
            <div class="console-metrics-mini-grid">
              ${resultData.metrics.map(m => `
                <div class="console-metric-mini-cell">
                  <small>${m.label}</small>
                  <strong>${m.value}</strong>
                </div>
              `).join('')}
            </div>
            <p class="console-result-block__footnote"><i data-lucide="info"></i> Simulated market signal • Prototype intelligence telemetry</p>
          </article>

          <!-- Block 4: Recommended Next Action -->
          <article class="console-result-block console-result-block--action">
            <span class="console-result-block__label">04 · What Should I Do?</span>
            <h4 class="console-result-block__heading">${resultData.actionHeading}</h4>
            <p class="console-result-block__body">${resultData.actionBody}</p>
            
            ${isRoadmapPreviewing ? `
              <div class="roadmap-preview-banner" style="margin-top:10px;">
                <div class="roadmap-preview-header">
                  <div>
                    <span class="v2-kicker" style="font-size:10px; font-weight:800; color:var(--b-primary);">ROADMAP PREVIEW</span>
                    <h4>${currentMeta.targetItem} — Career Acceleration Path</h4>
                  </div>
                  <span>6 Weeks · 5 Milestones</span>
                </div>
                <div class="roadmap-preview-stages">
                  <div class="preview-stage-dot"><span>1</span> Foundations</div>
                  <div class="preview-stage-dot"><span>2</span> Core Concepts</div>
                  <div class="preview-stage-dot"><span>3</span> Applied Practice</div>
                  <div class="preview-stage-dot"><span>4</span> System Project</div>
                  <div class="preview-stage-dot"><span>5</span> Assessment</div>
                </div>
                <div class="roadmap-preview-actions">
                  <button type="button" class="button button--assistant" id="confirmActivateRoadmapBtn">
                    <i data-lucide="check-circle-2"></i> Confirm & Activate Roadmap
                  </button>
                  <button type="button" class="button button--secondary" id="cancelRoadmapPreviewBtn">
                    Cancel
                  </button>
                </div>
              </div>
            ` : `
              <div class="console-action-row">
                <button type="button" class="button button--assistant console-action-btn" id="triggerRoadmapPreviewBtn">
                  <i data-lucide="map"></i> Build Roadmap
                </button>
                <a class="button" href="${resultData.detailsHref}">
                  <i data-lucide="arrow-up-right"></i> Explore Details
                </a>
              </div>
            `}
          </article>
        </div>
      </div>
    `;
  } else {
    // Idle / Ready state
    stageHtml = `
      <div class="console-idle-surface">
        <div class="console-idle-orb">
          <i data-lucide="${currentMeta.icon}"></i>
        </div>
        <h4>Ready to Analyze ${currentMeta.title}</h4>
        <p>Select one of the suggested questions above, or enter your own question to activate real-time telemetry and predictive market signals.</p>
        <div class="console-idle-tags">
          <span><i data-lucide="activity"></i> Simulated market signal</span>
          <span><i data-lucide="database"></i> 42,180 Data Points</span>
          <span><i data-lucide="map-pin"></i> ${location}</span>
          <span><i data-lucide="clock"></i> ${timeRange}</span>
        </div>
      </div>
    `;
  }

  return `
    <section class="intelligence-console-hero" data-console-theme="${currentMeta.theme}" aria-label="Intelligence Console">
      <div class="console-bg-glow"></div>
      
      <!-- Console Top Header -->
      <header class="console-header">
        <div class="console-header__title-group">
          <span class="v2-kicker" style="font-size:11px; font-weight:800; color:var(--b-primary); text-transform:uppercase; letter-spacing:0.06em;">LIVE INTELLIGENCE CONSOLE</span>
          <h2>${currentMeta.title}</h2>
          <p>Analyzing telemetry for <strong>${currentMeta.targetItem}</strong> across ${location}.</p>
        </div>

        <div class="console-header__nav-controls">
          <div class="console-mode-selector" role="tablist" aria-label="Intelligence Type">
            <button type="button" role="tab" aria-selected="${mode === 'skills'}" class="console-mode-btn ${mode === 'skills' ? 'is-active' : ''}" data-switch-domain="skills">
              <i data-lucide="brain-circuit"></i> Skill
            </button>
            <button type="button" role="tab" aria-selected="${mode === 'companies'}" class="console-mode-btn ${mode === 'companies' ? 'is-active' : ''}" data-switch-domain="companies">
              <i data-lucide="building-2"></i> Market
            </button>
            <button type="button" role="tab" aria-selected="${mode === 'roles'}" class="console-mode-btn ${mode === 'roles' ? 'is-active' : ''}" data-switch-domain="roles">
              <i data-lucide="briefcase"></i> Job
            </button>
          </div>

          <button type="button" class="console-back-domain-btn" id="changeConsoleDomainBtn" title="Back to domain choices">
            <i data-lucide="arrow-left"></i> Change Domain
          </button>
        </div>
      </header>

      <!-- Two-Column Workspace Layout -->
      <div class="console-workspace-layout">
        <!-- LEFT: Dynamic Context Rail -->
        <aside class="console-context-rail">
          ${controlsHtml}

          <!-- Context Telemetry Footer -->
          <div class="console-rail-telemetry">
            <div class="console-rail-telemetry__icon">
              <i data-lucide="${currentMeta.icon}"></i>
            </div>
            <div class="console-rail-telemetry__content">
              <strong>${currentMeta.statusText}</strong>
              <small>${currentMeta.helperText}</small>
            </div>
          </div>
        </aside>

        <!-- RIGHT: Analysis Stage -->
        <div class="console-analysis-stage">
          <!-- AI Prompt Composer -->
          <div class="console-prompt-composer">
            <span class="console-prompt-icon"><i data-lucide="sparkles"></i></span>
            <input class="console-prompt-input" id="consoleQueryInput" type="text" placeholder="${currentMeta.placeholder}" value="${intelligenceExplorerState.question || ''}">
            ${intelligenceExplorerState.question ? `
              <button type="button" class="console-clear-btn" id="consoleClearInputBtn" title="Clear input" aria-label="Clear input">
                <i data-lucide="x"></i>
              </button>
            ` : ''}
            <button class="console-analyze-btn button--assistant" id="consoleAnalyzeSubmit" type="button">
              <span>Analyze</span> <i data-lucide="arrow-right"></i>
            </button>
          </div>

          <!-- Suggested Questions -->
          <div class="console-suggested-prompts">
            <span>Suggested:</span>
            ${suggestedPrompts.map(p => `<button type="button" class="prompt-chip" data-console-prompt="${p}">${p}</button>`).join('')}
          </div>

          <!-- Dynamic Stage (Idle, Scanning, or Morphed Result) -->
          ${stageHtml}
        </div>
      </div>
    </section>
  `;
}

function skillVisualIcon(skill) {
  const name = (typeof skill === 'string' ? skill : (skill.name || skill.id || '')).toLowerCase();
  if (name.includes('python')) return 'code-xml';
  if (name.includes('machine learning') || name === 'ml') return 'brain-circuit';
  if (name.includes('genai') || name.includes('generative')) return 'sparkles';
  if (name.includes('cloud')) return 'cloud';
  if (name.includes('cyber') || name.includes('security')) return 'shield-check';
  if (name.includes('react')) return 'atom';
  if (name.includes('sql') || name.includes('database')) return 'database';
  if (name.includes('java') && !name.includes('script')) return 'coffee';
  if (name.includes('cuda') || name.includes('gpu')) return 'cpu';
  if (name.includes('docker')) return 'box';
  if (name.includes('kubernetes')) return 'boxes';
  if (name.includes('pytorch') || name.includes('deep learning')) return 'flame';
  if (name.includes('fastapi') || name.includes('api')) return 'zap';
  if (name.includes('django')) return 'layers';
  return 'code-xml';
}

function getSkillVisualClass(skill) {
  const name = (typeof skill === 'string' ? skill : (skill.name || skill.id || '')).toLowerCase();
  if (name.includes('python')) return 'skill-visual--python';
  if (name.includes('machine learning') || name === 'ml') return 'skill-visual--ml';
  if (name.includes('genai') || name.includes('generative')) return 'skill-visual--genai';
  if (name.includes('cloud')) return 'skill-visual--cloud';
  if (name.includes('cyber') || name.includes('security')) return 'skill-visual--cyber';
  if (name.includes('react')) return 'skill-visual--react';
  if (name.includes('sql') || name.includes('database')) return 'skill-visual--sql';
  if (name.includes('java') && !name.includes('script')) return 'skill-visual--java';
  if (name.includes('cuda') || name.includes('gpu')) return 'skill-visual--cuda';
  return 'skill-visual--default';
}

function getAdjacentSkillDetails(skillName) {
  const existing = skillMarketData.find(s => s.name.toLowerCase() === skillName.toLowerCase());
  if (existing) return existing;
  const map = {
    'FastAPI': { id: 'fastapi', name: 'FastAPI', category: 'Backend Framework', growth: 16.2, direction: 'up', isMySkill: false, isFavorite: false, values: [40, 48, 55, 62, 70, 76, 82] },
    'Django': { id: 'django', name: 'Django', category: 'Web Framework', growth: 8.5, direction: 'up', isMySkill: false, isFavorite: false, values: [55, 57, 59, 62, 64, 66, 68] },
    'PyTorch': { id: 'pytorch', name: 'PyTorch', category: 'Deep Learning', growth: 24.1, direction: 'up', isMySkill: false, isFavorite: false, values: [32, 44, 56, 68, 78, 86, 92] },
    'Deep Learning': { id: 'deeplearning', name: 'Deep Learning', category: 'AI Architecture', growth: 21.0, direction: 'up', isMySkill: false, isFavorite: false, values: [38, 48, 58, 68, 76, 84, 88] },
    'AWS': { id: 'aws', name: 'AWS Cloud', category: 'Infrastructure', growth: 15.4, direction: 'up', isMySkill: false, isFavorite: false, values: [50, 56, 62, 68, 74, 78, 82] },
    'Docker': { id: 'docker', name: 'Docker', category: 'Containers', growth: 13.2, direction: 'up', isMySkill: false, isFavorite: false, values: [52, 57, 61, 66, 70, 73, 76] },
    'Kubernetes': { id: 'kubernetes', name: 'Kubernetes', category: 'Orchestration', growth: 17.8, direction: 'up', isMySkill: false, isFavorite: false, values: [44, 52, 60, 68, 75, 80, 85] },
    'Terraform': { id: 'terraform', name: 'Terraform', category: 'Infrastructure as Code', growth: 14.6, direction: 'up', isMySkill: false, isFavorite: false, values: [42, 48, 55, 62, 68, 72, 76] },
    'PostgreSQL': { id: 'postgresql', name: 'PostgreSQL', category: 'Relational DB', growth: 12.4, direction: 'up', isMySkill: false, isFavorite: false, values: [48, 52, 56, 61, 66, 70, 74] },
    'Snowflake': { id: 'snowflake', name: 'Snowflake', category: 'Cloud Data Warehouse', growth: 19.5, direction: 'up', isMySkill: false, isFavorite: false, values: [36, 45, 56, 66, 76, 82, 88] },
    'TypeScript': { id: 'typescript', name: 'TypeScript', category: 'Frontend Language', growth: 18.2, direction: 'up', isMySkill: false, isFavorite: false, values: [45, 54, 62, 70, 78, 84, 90] },
    'Next.js': { id: 'nextjs', name: 'Next.js', category: 'React Framework', growth: 20.4, direction: 'up', isMySkill: false, isFavorite: false, values: [38, 48, 58, 68, 78, 86, 92] }
  };
  return map[skillName] || {
    id: skillName.toLowerCase().replace(/[^a-z0-9]/g, ''),
    name: skillName,
    category: 'Related Tech',
    growth: 10.5,
    direction: 'up',
    isMySkill: false,
    isFavorite: false,
    values: [45, 49, 53, 58, 62, 66, 70]
  };
}

function getSkillChartDateLabels(timeRange, dateType) {
  if (dateType === 'Day' || timeRange === '7 Days') return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  if (timeRange === '30 Days') return ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4'];
  if (timeRange === '90 Days') return ['M1', 'M2', 'M3'];
  if (dateType === 'Year' || timeRange === '1 Year') return ['Q1', 'Q2', 'Q3', 'Q4'];
  return ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'];
}

function renderSkillMultiSeriesChart(skills, timeRange, dateType, selectedSkillName) {
  const dates = getSkillChartDateLabels(timeRange, dateType);
  const strokeStyles = [
    { width: '3.0', opacity: '1.0', dash: 'none' },
    { width: '2.6', opacity: '0.85', dash: 'none' },
    { width: '2.3', opacity: '0.75', dash: '6 3' },
    { width: '2.1', opacity: '0.65', dash: 'none' },
    { width: '1.9', opacity: '0.55', dash: '3 3' }
  ];

  const maxVal = Math.max(...skills.flatMap(s => s.values), 100);
  const minVal = 0;
  const range = (maxVal - minVal) || 1;

  const linesHtml = skills.map((skill, idx) => {
    const isInc = skill.growth >= 0;
    const strokeColor = isInc ? '#10B981' : '#EF4444';
    const style = strokeStyles[idx % strokeStyles.length];
    const coords = skill.values.map((v, i) => {
      const x = 36 + (i / (skill.values.length - 1)) * 436;
      const y = 185 - ((v - minVal) / range) * 150;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const lastVal = skill.values[skill.values.length - 1];
    const lastX = 36 + 436;
    const lastY = 185 - ((lastVal - minVal) / range) * 150;

    return `
      <polyline class="skill-multi-line" data-skill-series="${skill.name}" points="${coords}"
                fill="none" stroke="${strokeColor}" stroke-width="${style.width}"
                stroke-opacity="${style.opacity}" stroke-dasharray="${style.dash}"
                stroke-linecap="round" stroke-linejoin="round" />
      <circle class="skill-multi-node" data-skill-node="${skill.name}" cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}"
              r="4" fill="${strokeColor}" stroke="#FFFFFF" stroke-width="2" />
    `;
  }).join('');

  return `
    <div class="skill-multi-series-wrap">
      <svg id="skillMultiSeriesChart" viewBox="0 0 500 220" preserveAspectRatio="none" role="img" aria-label="Top 5 skill trends comparative chart">
        <line x1="30" y1="35" x2="480" y2="35" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="30" y1="85" x2="480" y2="85" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="30" y1="135" x2="480" y2="135" stroke="#F0EAF4" stroke-width="1" stroke-dasharray="4" />
        <line x1="30" y1="185" x2="480" y2="185" stroke="#E2D6EC" stroke-width="1" />
        ${linesHtml}
      </svg>
    </div>
    <div style="display:flex; justify-content:space-between; padding:0 36px; margin-top:6px; font-size:10px; color:#8A7A97;">
      ${dates.map(d => `<span>${d}</span>`).join('')}
    </div>
  `;
}

function renderSkillSingleChart(matchedSkill, location, timeRange, dateType) {
  const dates = getSkillChartDateLabels(timeRange, dateType);
  const values = matchedSkill.values || [42, 50, 58, 66, 74, 80, 86];
  const maxVal = Math.max(...values, 100);
  const isInc = matchedSkill.growth >= 0;
  const strokeColor = isInc ? '#10B981' : '#EF4444';
  const gradientColor = isInc ? '#10B981' : '#EF4444';

  const coords = values.map((val, idx) => {
    const x = (idx / (values.length - 1)) * 480;
    const y = 200 - (val / maxVal) * 160;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return `
    <div class="skill-svg-chart-wrap skill-single-chart-wrap">
      <svg viewBox="0 0 480 220" preserveAspectRatio="none" role="img" aria-label="${matchedSkill.name} trend telemetry chart">
        <defs>
          <linearGradient id="v2SkillGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${gradientColor}" stop-opacity="0.22"/>
            <stop offset="100%" stop-color="${gradientColor}" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        <polygon points="0,220 ${coords} 480,220" fill="url(#v2SkillGradient)" />
        <polyline points="${coords}" fill="none" stroke="${strokeColor}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        ${values.map((val, idx) => {
          const x = (idx / (values.length - 1)) * 480;
          const y = 200 - (val / maxVal) * 160;
          return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" fill="${strokeColor}" stroke="#FFFFFF" stroke-width="2"/>`;
        }).join('')}
      </svg>
    </div>
    <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:10px; color:#8A7A97;">
      ${dates.map(d => `<span>${d}</span>`).join('')}
    </div>
  `;
}

function renderRedesignedSkillIntelligence() {
  const scope = dashboardState.skillScope || 'All Skills';
  const location = dashboardState.skillLocation || 'Bangalore';
  const timeRange = dashboardState.skillTime || '6 Months';
  const dateType = dashboardState.skillDate || 'Month';
  const isFilterOpen = Boolean(dashboardState.isSkillFilterOpen);

  // Top trending / active skills
  let activeSkills = [...skillMarketData].sort((a, b) => b.growth - a.growth);
  const mySkillsList = skillMarketData.filter(s => s.isMySkill);
  const favoriteSkillsList = skillMarketData.filter(s => s.isFavorite).slice(0, 5);

  let top5 = activeSkills.slice(0, 5);
  if (scope === 'Favorite Skills') {
    top5 = favoriteSkillsList;
  }

  // Selected skill
  let selectedName = dashboardState.selectedSkill;
  if (scope === 'My Skills') {
    if (!mySkillsList.some(s => s.name === selectedName)) {
      selectedName = mySkillsList[0] ? mySkillsList[0].name : 'Machine Learning';
      dashboardState.selectedSkill = selectedName;
    }
  } else if (!selectedName) {
    selectedName = top5[0] ? top5[0].name : 'Machine Learning';
  }
  const matchedSkill = skillMarketData.find(s => s.name === selectedName) || top5[0] || skillMarketData[0];

  const filterSummary = `${scope} · ${location} · ${timeRange}`;

  // ---------------- Render Left Box Content ----------------
  let leftBoxHtml = '';
  if (scope === 'All Skills') {
    leftBoxHtml = `
      <div class="skill-chart-top-bar">
        <div class="skill-chart-info">
          <div style="display:flex; align-items:center; gap:8px;">
            <strong>Overall Top 5 Skill Trends</strong>
            <span class="overview-kicker" style="font-size:9.5px;">LIVE MULTI-SERIES</span>
          </div>
          <span>Comparative momentum trajectory in ${location} (${timeRange})</span>
        </div>
        <span class="skill-badge-trend positive" style="color:#10B981; background:rgba(16, 185, 129, 0.08); padding:4px 10px; border-radius:8px; font-weight:700; font-size:12px; display:inline-flex; align-items:center; gap:4px;">
          <i data-lucide="trending-up"></i>
          Top 5 Telemetry
        </span>
      </div>

      ${renderSkillMultiSeriesChart(top5, timeRange, dateType, matchedSkill.name)}

      <div class="skill-multi-legend" aria-label="Top 5 skill trends">
        ${top5.map((skill, i) => {
          const isInc = skill.growth >= 0;
          const color = isInc ? '#10B981' : '#EF4444';
          const arrow = isInc ? '↑' : '↓';
          return `
            <button type="button" class="skill-legend-pill ${matchedSkill.name === skill.name ? 'is-selected' : ''}" data-select-skill="${skill.name}" data-legend-skill="${skill.name}" title="View ${skill.name} telemetry">
              <span class="skill-legend-dot" style="background:${color};"></span>
              <span class="skill-legend-name">${skill.name}</span>
              <span class="skill-legend-value" style="color:${color};">
                ${skill.growth > 0 ? '+' : ''}${skill.growth.toFixed(1)}% ${arrow}
              </span>
            </button>
          `;
        }).join('')}
      </div>
    `;
  } else if (scope === 'My Skills') {
    const isDecline = matchedSkill.growth < 0;
    const badgeColor = isDecline ? '#EF4444' : '#10B981';
    leftBoxHtml = `
      <!-- User Declared Skills Strip -->
      <div class="my-skills-chips-strip">
        ${mySkillsList.map(s => `
          <button type="button" class="my-skill-chip ${s.name === matchedSkill.name ? 'is-active' : ''}" data-select-skill="${s.name}">
            <i data-lucide="${skillVisualIcon(s)}"></i>
            <span>${s.name}</span>
          </button>
        `).join('')}
      </div>

      <div class="skill-chart-top-bar">
        <div class="skill-chart-info">
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="skill-rail-visual ${getSkillVisualClass(matchedSkill)}" aria-hidden="true" style="width:26px; height:26px;">
              <i data-lucide="${skillVisualIcon(matchedSkill)}"></i>
            </span>
            <strong>${matchedSkill.name}</strong>
            <span class="skill-status-tag tag-my-skill">MY SKILL</span>
            <span class="overview-kicker" style="font-size:9.5px;">${matchedSkill.category}</span>
          </div>
          <span>Demand Index (${matchedSkill.values[matchedSkill.values.length - 1]} / 100) · Target Location: ${location}</span>
        </div>
        <span class="skill-badge-trend ${isDecline ? 'decline' : 'positive'}" style="color:${badgeColor}; background:${isDecline ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)'}; padding:4px 10px; border-radius:8px; font-weight:700; font-size:12px; display:inline-flex; align-items:center; gap:4px;">
          <i data-lucide="${isDecline ? 'trending-down' : 'trending-up'}"></i>
          ${isDecline ? '' : '+'}${matchedSkill.growth.toFixed(1)}% ${isDecline ? 'Decline ↓' : 'Growing ↑'}
        </span>
      </div>

      ${renderSkillSingleChart(matchedSkill, location, timeRange, dateType)}

      <div class="skill-capability-meta-bar" style="display:flex; justify-content:space-between; align-items:center; margin-top:14px; padding:10px 14px; background:#FAF7FC; border:1px solid #EBDDF5; border-radius:10px; font-size:11px;">
        <span style="color:#594868;"><strong style="color:#382848;">Declared Level:</strong> Verified Advanced</span>
        <span style="color:#594868;"><strong style="color:#382848;">Market Fit:</strong> 94% Direct Alignment</span>
        <span style="color:#10B981; font-weight:700;">Active in Profile</span>
      </div>
    `;
  } else {
    // Favorite Skills Mode
    leftBoxHtml = `
      <div class="skill-chart-top-bar">
        <div class="skill-chart-info">
          <div style="display:flex; align-items:center; gap:8px;">
            <strong>Favorite Skills Watchlist</strong>
            <span class="overview-kicker" style="font-size:9.5px;">${favoriteSkillsList.length}/5 MONITORED</span>
          </div>
          <span>Comparative live trajectory for monitored skills · ${location}</span>
        </div>
        <span class="skill-badge-trend positive" style="color:#B22DEF; background:rgba(178, 45, 239, 0.08); padding:4px 10px; border-radius:8px; font-weight:700; font-size:12px; display:inline-flex; align-items:center; gap:4px;">
          <i data-lucide="star"></i>
          Watchlist Active
        </span>
      </div>

      ${renderSkillMultiSeriesChart(favoriteSkillsList, timeRange, dateType, matchedSkill.name)}

      <div class="skill-multi-legend" aria-label="Favorite skill trends">
        ${favoriteSkillsList.map(skill => {
          const isInc = skill.growth >= 0;
          const color = isInc ? '#10B981' : '#EF4444';
          const arrow = isInc ? '↑' : '↓';
          return `
            <button type="button" class="skill-legend-pill ${matchedSkill.name === skill.name ? 'is-selected' : ''}" data-select-skill="${skill.name}" data-legend-skill="${skill.name}">
              <span class="skill-legend-dot" style="background:${color};"></span>
              <span class="skill-legend-name">${skill.name}</span>
              <span class="skill-legend-value" style="color:${color};">
                ${skill.growth > 0 ? '+' : ''}${skill.growth.toFixed(1)}% ${arrow}
              </span>
            </button>
          `;
        }).join('')}
      </div>
    `;
  }

  // ---------------- Render Right Box Content ----------------
  let rightBoxHtml = '';
  if (scope === 'All Skills') {
    rightBoxHtml = `
      <div class="rail-heading" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3>Top 5 Trending Skills</h3>
          <span class="skill-rail-subtitle">Ranked by market momentum in ${location}</span>
        </div>
        <a href="#/individual/skills" class="view-all-skills-link">View All Skills →</a>
      </div>

      <div class="top-skills-list top-skills-list--trending">
        ${top5.map((item, idx) => `
          <div class="skill-rail-row ${item.name === matchedSkill.name ? 'is-active' : ''}" data-select-skill="${item.name}" tabindex="0" role="group" aria-label="${item.name}, ranked ${idx + 1} by market momentum">
            <span class="skill-rail-rank">0${idx + 1}</span>
            <span class="skill-rail-visual ${getSkillVisualClass(item)}" aria-hidden="true">
              <i data-lucide="${skillVisualIcon(item)}"></i>
            </span>
            <span class="skill-rail-copy">
              <span class="skill-rail-name">${item.name}</span>
              <span class="skill-rail-category">${item.category}</span>
            </span>
            <span class="skill-rail-mini-chart">${renderSkillMiniChart(item.values, item.direction)}</span>
            <span class="skill-rail-change ${item.growth < 0 ? 'is-negative' : 'is-positive'}" style="color:${item.growth < 0 ? '#EF4444' : '#10B981'}; font-weight:700;">
              ${item.direction === 'down' ? '↓' : '↑'} ${item.growth > 0 ? '+' : ''}${item.growth.toFixed(1)}%
            </span>
            <button type="button" class="skill-rail-fav-btn ${item.isFavorite ? 'is-fav' : ''}" data-toggle-fav="${item.name}" title="Toggle Favorite" aria-label="${item.isFavorite ? 'Remove' : 'Add'} ${item.name} favorite">
              <i data-lucide="star"></i>
            </button>
          </div>
        `).join('')}
      </div>

      <div class="skill-rail-footer">
        <a href="#/individual/skills" class="view-all-skills-btn">View All Skills →</a>
      </div>
    `;
  } else if (scope === 'My Skills') {
    // Show related / competitor skills
    const rawAdjacent = matchedSkill.adjacentSkills || ['Python', 'Deep Learning', 'PyTorch', 'CUDA'];
    const relatedList = rawAdjacent.map(adj => getAdjacentSkillDetails(adj));

    rightBoxHtml = `
      <div class="rail-heading" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3>Related & Competitor Skills</h3>
          <span class="skill-rail-subtitle">Adjacent technologies aligned with ${matchedSkill.name}</span>
        </div>
        <a href="#/individual/skills" class="view-all-skills-link">View All Skills →</a>
      </div>

      <div class="top-skills-list">
        ${relatedList.map((item, idx) => {
          const isUserSkill = Boolean(item.isMySkill);
          return `
            <div class="skill-rail-row skill-rail-row--related" data-select-skill="${item.name}" tabindex="0" role="group" aria-label="${item.name}, ${isUserSkill ? 'My Skill' : 'Related Skill'}">
              <span class="skill-rail-rank">0${idx + 1}</span>
              <span class="skill-rail-visual ${getSkillVisualClass(item)}" aria-hidden="true">
                <i data-lucide="${skillVisualIcon(item)}"></i>
              </span>
              <span class="skill-rail-copy">
                <span class="skill-rail-name">${item.name}</span>
                <span class="skill-rail-category">${item.category}</span>
              </span>
              <span class="skill-status-tag ${isUserSkill ? 'tag-my-skill' : 'tag-related-skill'}">
                ${isUserSkill ? 'MY SKILL' : 'RELATED SKILL'}
              </span>
              <span class="skill-rail-mini-chart">${renderSkillMiniChart(item.values, item.direction)}</span>
              <span class="skill-rail-change ${item.growth < 0 ? 'is-negative' : 'is-positive'}" style="color:${item.growth < 0 ? '#EF4444' : '#10B981'}; font-weight:700;">
                ${item.direction === 'down' ? '↓' : '↑'} ${item.growth > 0 ? '+' : ''}${item.growth.toFixed(1)}%
              </span>
              <button type="button" class="skill-rail-fav-btn ${item.isFavorite ? 'is-fav' : ''}" data-toggle-fav="${item.name}" title="Toggle Favorite" aria-label="${item.isFavorite ? 'Remove' : 'Add'} ${item.name} favorite">
                <i data-lucide="star"></i>
              </button>
            </div>
          `;
        }).join('')}
      </div>

      <div class="skill-rail-footer">
        <a href="#/individual/skills" class="view-all-skills-btn">View All Skills →</a>
      </div>
    `;
  } else {
    // Favorite Skills Mode
    rightBoxHtml = `
      <div class="rail-heading" style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h3>Favorite Skills (Max 5)</h3>
          <span class="skill-rail-subtitle">Personal watchlist for rapid market telemetry</span>
        </div>
        <a href="#/individual/skills" class="view-all-skills-link">View All Skills →</a>
      </div>

      <div class="top-skills-list">
        ${favoriteSkillsList.map((item, idx) => `
          <div class="skill-rail-row ${item.name === matchedSkill.name ? 'is-active' : ''}" data-select-skill="${item.name}" tabindex="0" role="group" aria-label="${item.name}, favorite ranked ${idx + 1}">
            <span class="skill-rail-rank">0${idx + 1}</span>
            <span class="skill-rail-visual ${getSkillVisualClass(item)}" aria-hidden="true">
              <i data-lucide="${skillVisualIcon(item)}"></i>
            </span>
            <span class="skill-rail-copy">
              <span class="skill-rail-name">${item.name}</span>
              <span class="skill-rail-category">${item.category}</span>
            </span>
            <span class="skill-rail-mini-chart">${renderSkillMiniChart(item.values, item.direction)}</span>
            <span class="skill-rail-change ${item.growth < 0 ? 'is-negative' : 'is-positive'}" style="color:${item.growth < 0 ? '#EF4444' : '#10B981'}; font-weight:700;">
              ${item.direction === 'down' ? '↓' : '↑'} ${item.growth > 0 ? '+' : ''}${item.growth.toFixed(1)}%
            </span>
            <button type="button" class="skill-rail-fav-btn is-fav" data-toggle-fav="${item.name}" title="Remove Favorite" aria-label="Remove ${item.name} favorite">
              <i data-lucide="star"></i>
            </button>
          </div>
        `).join('')}
        ${favoriteSkillsList.length < 5 ? `
          <div style="padding:12px; text-align:center; color:#8A7A97; font-size:11px; border:1px dashed #E2D6EC; border-radius:10px; margin-top:6px;">
            ${favoriteSkillsList.length}/5 favorites monitored. Click star on any skill in All Skills to add.
          </div>
        ` : ''}
      </div>

      <div class="skill-rail-footer">
        <a href="#/individual/skills" class="view-all-skills-btn">View All Skills →</a>
      </div>
    `;
  }

  return `
    <section class="skill-intelligence-section" id="skill-intelligence-section" aria-label="Skill Intelligence">
      <div class="skill-intelligence-header-row">
        <div class="section-v2-header__left">
          <span class="v2-kicker">SKILL FORECAST TELEMETRY</span>
          <h2>Skill Intelligence</h2>
          <p>Real-time demand trends and market momentum across capabilities.</p>
        </div>

        <!-- ONE SINGLE [Filters] CONTROL -->
        <div class="skill-filter-control-wrap">
          <button type="button" class="skill-filter-trigger-btn" id="skillFiltersBtn" aria-expanded="${isFilterOpen ? 'true' : 'false'}" aria-controls="skillFilterPopover">
            <i data-lucide="sliders-horizontal"></i>
            <span>Filters</span>
            <span class="skill-filter-badge-summary">${filterSummary}</span>
            <i data-lucide="chevron-down" class="skill-filter-chevron ${isFilterOpen ? 'is-rotated' : ''}"></i>
          </button>

          <div class="skill-filter-popover ${isFilterOpen ? 'is-open' : ''}" id="skillFilterPopover" role="dialog" aria-label="Skill filters">
            <div class="skill-filter-popover-header">
              <h4><i data-lucide="filter"></i> Filter Skills</h4>
              <button type="button" class="skill-filter-close-btn" id="closeSkillFilterBtn" aria-label="Close filters">
                <i data-lucide="x"></i>
              </button>
            </div>

            <div class="skill-filter-popover-body">
              <!-- COLLECTION -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">COLLECTION</span>
                <div class="skill-filter-pills">
                  ${skillFilterOptions.collections.map(c => `
                    <button type="button" class="skill-filter-pill ${scope === c ? 'is-active' : ''}" data-set-skill-scope="${c}">
                      ${c}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- LOCATION -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">LOCATION</span>
                <div class="skill-filter-pills">
                  ${skillFilterOptions.locations.map(l => `
                    <button type="button" class="skill-filter-pill ${location === l ? 'is-active' : ''}" data-set-skill-location="${l}">
                      ${l}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- TIME -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">TIME</span>
                <div class="skill-filter-pills">
                  ${skillFilterOptions.times.map(t => `
                    <button type="button" class="skill-filter-pill ${timeRange === t ? 'is-active' : ''}" data-set-skill-time="${t}">
                      ${t}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- DATE -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">DATE</span>
                <div class="skill-filter-pills">
                  ${skillFilterOptions.dates.map(d => `
                    <button type="button" class="skill-filter-pill ${dateType === d ? 'is-active' : ''}" data-set-skill-date="${d}">
                      ${d}
                    </button>
                  `).join('')}
                </div>
              </div>
            </div>

            <div class="skill-filter-popover-footer">
              <span class="skill-filter-footer-summary">Showing <strong>${scope}</strong> in <strong>${location}</strong> · <strong>${timeRange}</strong></span>
              <button type="button" class="skill-filter-apply-btn" id="applySkillFilterBtn">Done</button>
            </div>
          </div>
        </div>
      </div>

      <div class="skill-analytical-surface">
        <!-- LEFT PANEL -->
        <div class="skill-chart-main">
          ${leftBoxHtml}
        </div>

        <!-- RIGHT PANEL -->
        <div class="top-skills-rail">
          ${rightBoxHtml}
        </div>
      </div>
    </section>
  `;
}

function getCompanyLogoSvg(company) {
  const name = (company.name || '').toLowerCase();
  if (name.includes('nvidia')) {
    return `<div class="company-logo-badge company-logo--nvidia" title="NVIDIA"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M2 12c0 5 4 9 9 9s9-4 9-9-4-9-9-9-9 4-9 9z"/><path d="M12 7c-3 0-5 2-5 5s2 5 5 5 5-2 5-5"/><circle cx="12" cy="12" r="2"/></svg><span>NV</span></div>`;
  }
  if (name.includes('microsoft')) {
    return `<div class="company-logo-badge company-logo--microsoft" title="Microsoft"><svg viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg><span>MS</span></div>`;
  }
  if (name.includes('google')) {
    return `<div class="company-logo-badge company-logo--google" title="Google"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="9"/><path d="M12 8v8m-4-4h8"/></svg><span>GO</span></div>`;
  }
  if (name.includes('amazon')) {
    return `<div class="company-logo-badge company-logo--amazon" title="Amazon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 16c4 3 12 3 16 0"/><path d="M18 13l2 3-3 1"/></svg><span>AMZ</span></div>`;
  }
  if (name.includes('apple')) {
    return `<div class="company-logo-badge company-logo--apple" title="Apple"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3c.5 1.5-.5 3-1.5 3.5C10 5 11 3.5 12 3z"/><path d="M16 13c0 2.5 1.8 3.5 1.8 3.5-1 2.8-2.6 4-4 4-1.2 0-2-.8-3.4-.8s-2.3.8-3.4.8c-1.8 0-3.6-2-4.5-5.5C1.6 11 3.5 8 5.8 8c1.4 0 2.4.9 3.2.9.8 0 2-.9 3.5-.9 1.4 0 3 .7 3.5 1.8-2.5 1.4-2 3.2 0 3.2z"/></svg><span>AAPL</span></div>`;
  }
  if (name.includes('openai')) {
    return `<div class="company-logo-badge company-logo--openai" title="OpenAI"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/><path d="M12 6v12M6 12h12"/></svg><span>AI</span></div>`;
  }
  if (name.includes('tsmc')) {
    return `<div class="company-logo-badge company-logo--tsmc" title="TSMC"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg><span>TS</span></div>`;
  }
  if (name.includes('intel')) {
    return `<div class="company-logo-badge company-logo--intel" title="Intel"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 15V9m5 6v-3m5 3V9"/></svg><span>IN</span></div>`;
  }
  return `<div class="company-logo-badge" title="${company.name}"><span>${company.logoInitials || company.name.slice(0, 2).toUpperCase()}</span></div>`;
}

function renderRedesignedMarketIntelligence() {
  const scope = dashboardState.marketCompanyScope || 'All Companies';
  const location = dashboardState.marketLocation || 'Bangalore';
  const timeRange = dashboardState.marketTime || '6 Months';
  const dateType = dashboardState.marketDate || 'Month';
  const isFilterOpen = Boolean(dashboardState.isMarketFilterOpen);

  let activeCompanies = [...marketIntelligenceData.companies].sort((a, b) => b.change - a.change);
  if (scope === 'Favorite Companies') {
    activeCompanies = activeCompanies.filter(c => c.isFavorite);
    if (activeCompanies.length === 0) {
      activeCompanies = marketIntelligenceData.companies.slice(0, 4);
    }
  }

  const selectedCompanyName = dashboardState.selectedMarketCompany || intelligenceExplorerState.selected.companies || 'NVIDIA';
  const selectedCompany = marketIntelligenceData.companies.find(c => c.name === selectedCompanyName) || activeCompanies[0];

  const isDecline = selectedCompany.change < 0;
  const badgeColor = isDecline ? '#EF4444' : '#10B981';
  const badgeBg = isDecline ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)';

  const invChange = signals => {
    const s = signals.investment;
    return s[s.length - 1] - s[s.length - 2];
  };
  const techChange = signals => {
    const s = signals.technology;
    return s[s.length - 1] - s[s.length - 2];
  };
  const hirChange = signals => {
    const s = signals.hiring;
    return s[s.length - 1] - s[s.length - 2];
  };

  const deltaInv = invChange(marketIntelligenceData.signals);
  const deltaTech = techChange(marketIntelligenceData.signals);
  const deltaHir = hirChange(marketIntelligenceData.signals);

  const filterSummary = `${scope} · ${location} · ${timeRange}`;

  return `
    <section class="market-intelligence-section" id="market-intelligence-section" aria-label="Market Intelligence">
      <div class="market-intelligence-header-row">
        <div class="section-v2-header__left">
          <span class="v2-kicker">WORKFORCE MARKET SIGNALS</span>
          <h2>Market Intelligence</h2>
          <p>Financial, technology, and workforce shifts across technology market leaders.</p>
        </div>

        <!-- ONE SINGLE [Filters] CONTROL -->
        <div class="market-filter-control-wrap">
          <button type="button" class="skill-filter-trigger-btn" id="marketFiltersBtn" aria-expanded="${isFilterOpen ? 'true' : 'false'}" aria-controls="marketFilterPopover">
            <i data-lucide="sliders-horizontal"></i>
            <span>Filters</span>
            <span class="skill-filter-badge-summary">${filterSummary}</span>
            <i data-lucide="chevron-down" class="skill-filter-chevron ${isFilterOpen ? 'is-rotated' : ''}"></i>
          </button>

          <div class="skill-filter-popover ${isFilterOpen ? 'is-open' : ''}" id="marketFilterPopover" role="dialog" aria-label="Market filters">
            <div class="skill-filter-popover-header">
              <h4><i data-lucide="filter"></i> Filter Market Intelligence</h4>
              <button type="button" class="skill-filter-close-btn" id="closeMarketFilterBtn" aria-label="Close filters">
                <i data-lucide="x"></i>
              </button>
            </div>

            <div class="skill-filter-popover-body">
              <!-- COMPANIES -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">COMPANIES</span>
                <div class="skill-filter-pills">
                  ${marketFilterOptions.companies.map(c => `
                    <button type="button" class="skill-filter-pill ${scope === c ? 'is-active' : ''}" data-set-market-company-scope="${c}">
                      ${c}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- LOCATION -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">LOCATION</span>
                <div class="skill-filter-pills">
                  ${marketFilterOptions.locations.map(l => `
                    <button type="button" class="skill-filter-pill ${location === l ? 'is-active' : ''}" data-set-market-location="${l}">
                      ${l}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- TIME -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">TIME</span>
                <div class="skill-filter-pills">
                  ${marketFilterOptions.times.map(t => `
                    <button type="button" class="skill-filter-pill ${timeRange === t ? 'is-active' : ''}" data-set-market-time="${t}">
                      ${t}
                    </button>
                  `).join('')}
                </div>
              </div>

              <!-- DATE -->
              <div class="skill-filter-group">
                <span class="skill-filter-group-label">DATE</span>
                <div class="skill-filter-pills">
                  ${marketFilterOptions.dates.map(d => `
                    <button type="button" class="skill-filter-pill ${dateType === d ? 'is-active' : ''}" data-set-market-date="${d}">
                      ${d}
                    </button>
                  `).join('')}
                </div>
              </div>
            </div>

            <div class="skill-filter-popover-footer">
              <span class="skill-filter-footer-summary">Showing <strong>${scope}</strong> in <strong>${location}</strong> · <strong>${timeRange}</strong></span>
              <button type="button" class="skill-filter-apply-btn" id="applyMarketFilterBtn">Done</button>
            </div>
          </div>
        </div>
      </div>

      <div class="market-analytical-surface">
        <!-- LEFT PANEL: MARKET-STYLE MULTI-LINE CHART -->
        <div class="skill-chart-main market-panel-left">
          <!-- Company Context Bar -->
          <div class="skill-chart-top-bar">
            <div class="skill-chart-info">
              <div style="display:flex; align-items:center; gap:8px;">
                ${getCompanyLogoSvg(selectedCompany)}
                <strong class="market-analyzed-company">${selectedCompany.name} Market Telemetry</strong>
                <span class="company-signal-tag ${selectedCompany.signalType}">${selectedCompany.signalText}</span>
              </div>
              <span>${selectedCompany.sector} · Target Market: ${location} (${timeRange})</span>
            </div>
            <span class="skill-badge-trend ${isDecline ? 'decline' : 'positive'}" style="color:${badgeColor}; background:${badgeBg}; padding:4px 10px; border-radius:8px; font-weight:700; font-size:12px; display:inline-flex; align-items:center; gap:4px;">
              <i data-lucide="${isDecline ? 'trending-down' : 'trending-up'}"></i>
              ${isDecline ? '' : '+'}${selectedCompany.change.toFixed(1)}% ${isDecline ? 'Restructuring Signal ↓' : 'Market Momentum ↑'}
            </span>
          </div>

          <!-- Market Terminal Multi-Line SVG Chart -->
          ${renderMultiLineMarketChart(marketIntelligenceData.signals, timeRange, dateType)}

          <!-- Three Signal Category Legend with Active Indicators -->
          <div class="market-chart-legend" aria-label="Market signals telemetry">
            <!-- Category 1: Company Financial / Investment Signals (Purple) -->
            <div class="market-legend-item" data-market-legend="investment">
              <span class="market-legend-dot" style="background:#8B3DFF;"></span>
              <span class="market-legend-label">Financial & Investment Signals</span>
              <strong class="market-legend-val ${deltaInv < 0 ? 'is-negative' : 'is-positive'}" style="color:${deltaInv < 0 ? '#EF4444' : '#10B981'}; background:${deltaInv < 0 ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)'}; padding:2px 6px; border-radius:6px;">
                ${deltaInv > 0 ? '+' : ''}${deltaInv.toFixed(1)}% ${deltaInv < 0 ? '↓' : '↑'}
              </strong>
            </div>

            <!-- Category 2: Market / Technology / Location Signals (Green) -->
            <div class="market-legend-item" data-market-legend="technology">
              <span class="market-legend-dot" style="background:#10B981;"></span>
              <span class="market-legend-label">Tech & Location Signals</span>
              <strong class="market-legend-val ${deltaTech < 0 ? 'is-negative' : 'is-positive'}" style="color:${deltaTech < 0 ? '#EF4444' : '#10B981'}; background:${deltaTech < 0 ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)'}; padding:2px 6px; border-radius:6px;">
                ${deltaTech > 0 ? '+' : ''}${deltaTech.toFixed(1)}% ${deltaTech < 0 ? '↓' : '↑'}
              </strong>
            </div>

            <!-- Category 3: Job Market Signals (Orange) -->
            <div class="market-legend-item" data-market-legend="hiring">
              <span class="market-legend-dot" style="background:#F59E0B;"></span>
              <span class="market-legend-label">Job Market Signals</span>
              <strong class="market-legend-val ${deltaHir < 0 ? 'is-negative' : 'is-positive'}" style="color:${deltaHir < 0 ? '#EF4444' : '#10B981'}; background:${deltaHir < 0 ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)'}; padding:2px 6px; border-radius:6px;">
                ${deltaHir > 0 ? '+' : ''}${deltaHir.toFixed(1)}% ${deltaHir < 0 ? '↓' : '↑'}
              </strong>
            </div>
          </div>
        </div>

        <!-- RIGHT PANEL: TOP MARKET COMPANIES -->
        <div class="top-skills-rail market-panel-right">
          <div class="rail-heading" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div>
              <h3>TOP MARKET COMPANIES</h3>
              <span style="font-size:11px; color:#8A7A97;">Ranked by technology & workforce momentum in ${location}</span>
            </div>
            <a href="#/individual/market-insights" class="view-all-market-link">Explore Insights →</a>
          </div>

          <div class="market-table-header">
            <span class="th-cell th-rank">RANK</span>
            <span class="th-cell th-company">COMPANY</span>
            <span class="th-cell th-signal">MARKET SIGNAL</span>
            <span class="th-cell th-percentage">PERCENTAGE</span>
            <span class="th-cell th-trend">TREND</span>
          </div>

          <div class="company-market-list">
            ${activeCompanies.map((c, idx) => `
              <div class="company-market-row ${c.name === selectedCompany.name ? 'is-selected' : ''}" data-select-market-company="${c.name}" tabindex="0" role="row" aria-label="${c.name}, ranked ${idx + 1}, ${c.signalText}">
                <span class="company-rank">0${idx + 1}</span>
                <div class="td-cell-company">
                  ${getCompanyLogoSvg(c)}
                  <div class="company-text-meta">
                    <strong class="company-name-title">${c.name}</strong>
                    <span class="company-sector-sub">${c.sector}</span>
                  </div>
                </div>

                <div class="td-cell-signal">
                  <span class="company-signal-tag ${c.signalType}">${c.signalText}</span>
                </div>

                <div class="td-cell-momentum">
                  <strong class="company-momentum-val ${c.change < 0 ? 'is-negative' : 'is-positive'}" style="color:${c.change < 0 ? '#EF4444' : '#10B981'}; font-weight:700;">
                    ${c.direction === 'down' ? '↓' : '↑'} ${c.change > 0 ? '+' : ''}${c.change.toFixed(1)}%
                  </strong>
                </div>

                <div class="td-cell-trend">
                  <div class="company-sparkline-wrap">
                    ${renderMarketMiniChart(c.history, c.direction)}
                  </div>
                  <button type="button" class="company-fav-btn ${c.isFavorite ? 'is-fav' : ''}" data-toggle-company-fav="${c.name}" title="Toggle Favorite" aria-label="${c.isFavorite ? 'Remove' : 'Add'} ${c.name} favorite">
                    <i data-lucide="star"></i>
                  </button>
                </div>
              </div>
            `).join('')}
          </div>

          <div class="market-rail-footer">
            <a href="#/individual/market-insights" class="view-all-market-btn">View All Market Signals →</a>
          </div>
        </div>
      </div>
    </section>
  `;
}

function getHomeJobContext() {
  const state = homeJobIntelligenceState;
  const roles = { 'All Roles': 'AI Engineer', 'Software Engineering': 'Software Engineer', 'AI/ML': 'AI Engineer', Data: 'Data Engineer', Cloud: 'Cloud Engineer', Cybersecurity: 'Cybersecurity Engineer', Frontend: 'Frontend Engineer', Backend: 'Backend Engineer' };
  const skills = { 'All Roles': 'Python', 'Software Engineering': 'System Design', 'AI/ML': 'CUDA', Data: 'SQL', Cloud: 'AWS', Cybersecurity: 'Cloud Security', Frontend: 'React', Backend: 'Distributed Systems' };
  const companies = state.companyScope === 'favorites'
    ? (intelligenceExplorerState.favoriteCompanies || ['NVIDIA', 'Microsoft', 'Google', 'Amazon'])
    : (marketIntelligenceData.companies || []).map(company => company.name);
  if (!companies.includes(state.company)) state.company = companies[0] || 'NVIDIA';
  const timeFactor = { '7 Days': 0.06, '30 Days': 0.18, '90 Days': 0.46, '6 Months': 1, '1 Year': 1.72 }[state.period] || 1;
  const regionFactor = { Global: 1.42, India: 1.08, 'Tamil Nadu': 0.52, Chennai: 0.36, Bangalore: 0.62, Hyderabad: 0.43, Pune: 0.32, Remote: 0.7 }[state.region] || 1;
  const scale = timeFactor * regionFactor * (state.companyScope === 'favorites' ? 0.42 : 1);
  const company = (marketIntelligenceData.companies || []).find(item => item.name === state.company);
  const openRoles = Math.max(1, Math.round(jobMarketData.totalOpenRoles * scale));
  const hiringCompanies = Math.max(1, Math.round(2480 * scale));
  const signals = [
    { id: 'roles', label: 'Open Roles', percent: 46, color: '#B22DEF', value: `${openRoles.toLocaleString()} roles`, change: '+12.4%', detail: 'Role openings are the largest share of this normalized market signal mix.' },
    { id: 'companies', label: 'Hiring Companies', percent: 25, color: '#8B3DFF', value: `${Math.max(1, Math.round(2480 * scale)).toLocaleString()} companies`, change: '+8.6%', detail: 'Companies with active hiring activity in this illustrative market view.' },
    { id: 'momentum', label: 'Role Demand', percent: 21, color: '#19B77A', value: '+18.4% demand index', change: '+18.4%', detail: 'Demand movement points to continued interest in the selected role group.' },
    { id: 'reduction', label: 'Reduction Signal', percent: 8, color: '#E7A23B', value: 'Low · 8% signal share', change: '−3.1%', detail: 'A smaller consolidation signal is present in the illustrative market mix.' }
  ];
  return {
    ...state, companies, roleTitle: roles[state.role] || roles['All Roles'], skill: skills[state.role] || skills['All Roles'],
    signals, selectedSignal: signals.find(signal => signal.id === state.selectedSignal) || signals[0], openRoles,
    hiringCompanies,
    companyRoles: Math.max(1, Math.round((company?.openRoles || 1320) * timeFactor)),
    newVacancies: Math.max(1, Math.round(openRoles * 0.029)), companyName: state.company || 'NVIDIA'
  };
}

function renderHomeJobDonut(signals) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return `<svg class="home-job-donut" viewBox="0 0 160 160" role="group" aria-label="Job market signal mix">
    <circle cx="80" cy="80" r="${radius}" fill="none" stroke="#F0EAF5" stroke-width="17"></circle>
    ${signals.map(signal => {
      const dash = circumference * signal.percent / 100;
      const markup = `<circle class="home-job-donut__segment" data-home-job-signal="${signal.id}" cx="80" cy="80" r="${radius}" fill="none" stroke="${signal.color}" stroke-width="16" stroke-dasharray="${dash} ${circumference - dash}" stroke-dashoffset="${-offset}" stroke-linecap="butt" tabindex="0" role="button" aria-label="${signal.label}, ${signal.percent} percent, ${signal.value}"></circle>`;
      offset += dash;
      return markup;
    }).join('')}
  </svg>`;
}

function renderHomeJobSignalDetail(context, signal) {
  const changeClass = signal.change.startsWith('−') ? 'is-negative' : 'is-positive';
  return `<div class="home-job-signal-detail__head"><div><span class="home-job-eyebrow">${signal.label} · ${signal.percent}% of mix</span><strong>${signal.value}</strong></div><span class="home-job-signal-change ${changeClass}">${signal.change} <small>change</small></span></div>
    <p>${signal.detail}</p><div class="home-job-supporting-lists"><div><span>Top roles</span><strong>${context.roleTitle} · Backend Engineer · Data Engineer</strong></div><div><span>Top locations</span><strong>${context.region === 'Global' ? 'Bangalore · Hyderabad · Chennai' : `${context.region} · Hyderabad · Chennai`}</strong></div></div>`;
}

function renderHomeJobIntelligenceMarkup() {
  const context = getHomeJobContext();
  const state = homeJobIntelligenceState;
  const recommendations = [
    { label: 'ROLE', title: context.roleTitle, reasons: ['Growing role demand', 'Hiring activity in this market'] },
    { label: 'COMPANY', title: context.companyName, reasons: ['Selected company context', `${context.companyRoles.toLocaleString()} illustrative openings`] },
    { label: 'SKILL', title: context.skill, reasons: [`Relevant to ${context.roleTitle}`, 'Appears in the current skill gap'] },
    { label: 'JOB', title: `${context.roleTitle} — ${context.region}`, reasons: [`${context.period} market window`, `${context.selectedSignal.label} is selected`] },
    { label: 'PREPARATION', title: `Improve ${context.role === 'AI/ML' || context.role === 'All Roles' ? 'Deep Learning' : context.skill}`, reasons: ['Builds toward the selected role', 'Addresses a listed preparation gap'] }
  ];
  const interpretation = context.selectedSignal.id === 'reduction'
    ? `The reduction signal is a smaller part of the ${context.region} mix. Keep role demand and hiring activity in view for ${context.roleTitle} over ${context.period.toLowerCase()}.`
    : `${context.selectedSignal.label} leads the current view for ${context.roleTitle} around ${context.region}. ${context.companyName} and related roles are useful places to focus next.`;

  return `<section class="job-intelligence-section home-job-intelligence" id="job-intelligence-section" aria-label="Job Intelligence">
    <div class="section-v2-header"><div class="section-v2-header__left"><span class="v2-kicker">CAREER & OPPORTUNITIES</span><h2>Job Intelligence</h2><p>Understand what is moving in the job market and what deserves your attention.</p></div></div>
    <div class="home-job-context" aria-label="Job market context filters">
      <div class="home-job-context__intro"><span class="home-job-eyebrow">MARKET CONTEXT</span><h3>What job market do you want to explore?</h3><p>Choose the companies, region, role and time window used by both panels.</p></div>
      <div class="home-job-context__controls">
        <label><span>Company set</span><select data-home-job-filter="companyScope" aria-label="Company set"><option value="favorites" ${state.companyScope === 'favorites' ? 'selected' : ''}>My / Favorite Companies</option><option value="all" ${state.companyScope === 'all' ? 'selected' : ''}>All Companies</option></select></label>
        <label><span>Company</span><select data-home-job-filter="company" aria-label="Selected company">${context.companies.map(company => `<option value="${company}" ${state.company === company ? 'selected' : ''}>${company}</option>`).join('')}</select></label>
        <label><span>Region</span><select data-home-job-filter="region" aria-label="Region">${['Global', 'India', 'Tamil Nadu', 'Chennai', 'Bangalore', 'Hyderabad', 'Pune', 'Remote'].map(region => `<option ${state.region === region ? 'selected' : ''}>${region}</option>`).join('')}</select></label>
        <label><span>Role</span><select data-home-job-filter="role" aria-label="Role">${['All Roles', 'Software Engineering', 'AI/ML', 'Data', 'Cloud', 'Cybersecurity', 'Frontend', 'Backend'].map(role => `<option ${state.role === role ? 'selected' : ''}>${role}</option>`).join('')}</select></label>
        <label><span>Time</span><select data-home-job-filter="period" aria-label="Time period">${['7 Days', '30 Days', '90 Days', '6 Months', '1 Year'].map(period => `<option ${state.period === period ? 'selected' : ''}>${period}</option>`).join('')}</select></label>
      </div>
    </div>
    <div class="job-intelligence-dual-surface home-job-panels">
      <article class="job-trend-card home-job-panel" aria-labelledby="homeJobTrendHeading">
        <div class="home-job-panel-heading"><div><span class="home-job-eyebrow">JOB TREND ANALYSIS</span><h3 id="homeJobTrendHeading">Job Market Signal Mix</h3><p>Normalized shares of illustrative market signals · ${context.region}</p></div><a href="#/individual/career">Career intelligence <span aria-hidden="true">↗</span></a></div>
        <div class="home-job-chart-area"><div class="home-job-donut-wrap">${renderHomeJobDonut(context.signals)}<div class="home-job-donut-center"><strong>${(context.openRoles / 1000).toFixed(1)}K</strong><span>open roles</span></div></div>
          <div class="home-job-signal-list" aria-label="Signal categories">${context.signals.map(signal => `<button type="button" class="home-job-signal-row" data-home-job-signal="${signal.id}" aria-pressed="${state.selectedSignal === signal.id}"><span class="home-job-signal-dot" style="--signal-color:${signal.color}"></span><span class="home-job-signal-label">${signal.label}</span><strong>${signal.percent}%</strong></button>`).join('')}</div></div>
        <div class="home-job-signal-detail" id="homeJobSignalDetail" aria-live="polite">${renderHomeJobSignalDetail(context, context.selectedSignal)}</div>
        <div class="home-job-metrics" aria-label="Compact job market indicators"><div><span>Companies hiring</span><strong>${context.hiringCompanies.toLocaleString()}</strong></div><div><span>Open roles</span><strong>${context.openRoles.toLocaleString()}</strong></div><div><span>New vacancies</span><strong>+${context.newVacancies.toLocaleString()}</strong></div><div><span>Layoff signals</span><strong class="home-job-metric-low">Low · 8%</strong></div><div><span>Top role</span><strong>${context.roleTitle}</strong></div><div><span>Top skill</span><strong>${context.skill}</strong></div></div>
        <p class="home-job-demo-note">Illustrative demo signals; not verified real-time market data.</p>
      </article>
      <article class="job-recommendations-card home-job-panel home-job-recommendations" aria-labelledby="homeJobRecommendationsHeading"><div class="home-job-recommendations__glow" aria-hidden="true"></div>
        <div class="home-job-panel-heading home-job-panel-heading--recommendations"><div><span class="home-job-eyebrow"><i data-lucide="sparkles"></i> INTELLIGENT JOB ANALYSIS</span><h3 id="homeJobRecommendationsHeading">AI recommendations</h3></div><span class="home-job-prototype-badge"><i></i> Prototype signal</span></div>
        <div class="home-job-interpretation"><span>WHAT THIS MEANS FOR YOU</span><p>${interpretation}</p></div>
        <div class="home-job-recommendation-list">${recommendations.map((item, index) => `<article class="home-job-recommendation" style="--recommendation-index:${index}"><span class="home-job-recommendation__type">${item.label}</span><h4>${item.title}</h4><div class="home-job-why"><span>Why this?</span><ul>${item.reasons.map(reason => `<li><i data-lucide="check"></i>${reason}</li>`).join('')}</ul></div></article>`).join('')}</div>
        <a class="home-job-career-link" href="#/individual/career">Explore career opportunities <span aria-hidden="true">↗</span></a>
      </article>
    </div>
  </section>`;
}

function renderRedesignedJobIntelligence() {
  return renderHomeJobIntelligenceMarkup();
}

function getRoadmapTypeDefaults(goalType, skillName) {
  const skill = skillName || 'Python';
  switch (goalType) {
    case 'Skill Switch':
      return {
        title: `${skill} → AI Engineering`,
        currentStep: { name: 'Gap Acquisition', detail: 'CUDA & Model Training · In progress', href: '#/individual/learning' },
        nextStep: { name: 'Transition Labs', detail: 'Hands-on Applied Labs · Queued', href: '#/individual/learning' },
        completedItems: ['Transferable Skills', 'Core Gap Acquisition', 'Transition Assessment', 'Capstone Project']
      };
    case 'Career Preparation':
      return {
        title: `Prepare for AI Engineer`,
        currentStep: { name: 'Assessment', detail: 'Professional Skills Evaluation · In progress', href: '#/individual/learning' },
        nextStep: { name: 'Applied Systems', detail: 'Production Engineering Project · Queued', href: '#/individual/learning' },
        completedItems: ['Role Diagnostics', 'Core Foundations', 'Assessment', 'Systems Project']
      };
    case 'Job Preparation':
      return {
        title: `Prepare for NVIDIA AI Engineer roles`,
        currentStep: { name: 'Role Requirements', detail: 'Production Requisition Match · In progress', href: '#/individual/learning' },
        nextStep: { name: 'Domain Project', detail: 'Industry Production Case Study · Queued', href: '#/individual/learning' },
        completedItems: ['Requisition Match', 'Technical Assessment', 'Domain Case Study', 'Interview Simulation']
      };
    case 'Company Preparation':
      return {
        title: `Prepare for Microsoft backend roles`,
        currentStep: { name: 'Assessment', detail: 'Company Challenge Assessment · In progress', href: '#/individual/learning' },
        nextStep: { name: 'Mock Project', detail: 'Production Scale Mock Build · Queued', href: '#/individual/learning' },
        completedItems: ['Target Architecture', 'Internal Systems', 'Technical Challenge', 'Mock Project']
      };
    case 'Improve Current Skill':
    default:
      return {
        title: `${skill} — Backend Development`,
        currentStep: { name: 'Assessment', detail: 'Technical Benchmark · 12/20 completed', href: '#/individual/learning' },
        nextStep: { name: 'Real-world Project', detail: '2 recommended projects queued', href: '#/individual/learning' },
        completedItems: ['Skill Development', 'Assessment', 'Project', 'Job Preparation']
      };
  }
}

function renderRedesignedRoadmap() {
  const status = roadmapState?.status || 'none';
  const skill = roadmapState?.skill || dashboardState.selectedSkill || 'Python';
  const goalType = roadmapState?.goalType || 'Improve Current Skill';
  const defaults = getRoadmapTypeDefaults(goalType, skill);
  const title = roadmapState?.title || defaults.title;
  const progress = typeof roadmapState?.progress === 'number' ? roadmapState.progress : 64;

  // STATE A: ACTIVE ROADMAP
  if (status === 'active') {
    const milestones = roadmapState?.milestones || defaultRoadmapTemplates[goalType] || defaultRoadmapTemplates['Improve Current Skill'];
    const currentStep = roadmapState?.currentStep || defaults.currentStep;
    const nextStep = roadmapState?.nextStep || defaults.nextStep;
    const completedCount = roadmapState?.completedCount ?? 8;
    const currentCount = roadmapState?.currentCount ?? 1;
    const upcomingCount = roadmapState?.upcomingCount ?? 4;
    const achievementStatus = roadmapState?.achievementStatus || 'On Track · +14% this week';

    return `
      <section class="active-roadmap-section" id="active-roadmap-section" aria-label="Active Roadmap">
        <div class="section-v2-header">
          <div class="section-v2-header__left">
            <span class="v2-kicker">YOUR ACTIVE ROADMAP</span>
            <h2>Your Progress, One Step at a Time</h2>
          </div>
          <div class="roadmap-header-badge">
            <span class="status-live-dot"></span> Active Tracking
          </div>
        </div>

        <div class="roadmap-compact-card">
          <!-- TOP ROW: TITLE, TYPE & PROGRESS -->
          <div class="roadmap-card-top">
            <div class="roadmap-identity-block">
              <div class="roadmap-icon-box">
                <i data-lucide="route"></i>
              </div>
              <div class="roadmap-title-col">
                <div class="roadmap-meta-pills">
                  <span class="roadmap-type-pill">${goalType}</span>
                  <span class="roadmap-status-pill"><span class="pulse-dot"></span> In Progress</span>
                </div>
                <h3 class="roadmap-card-title">${title}</h3>
              </div>
            </div>

            <div class="roadmap-progress-badge-wrap">
              <div class="roadmap-progress-number">
                <span class="progress-val">${progress}%</span>
              </div>
              <span class="roadmap-progress-sub">Overall Progress</span>
            </div>
          </div>

          <!-- ANIMATED PROGRESS BAR -->
          <div class="roadmap-progress-track" role="progressbar" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100">
            <div class="roadmap-progress-fill" style="width: ${progress}%;"></div>
          </div>

          <!-- COMPACT MILESTONE TIMELINE (DESKTOP: HORIZONTAL, MOBILE: VERTICAL) -->
          <div class="roadmap-timeline">
            ${milestones.map((m, idx) => `
              <div class="timeline-step ${m.status || 'upcoming'}">
                <div class="step-indicator">
                  ${m.status === 'completed' ? '<i data-lucide="check"></i>' : (m.status === 'current' ? '<span class="pulse-dot"></span>' : (idx + 1))}
                </div>
                <span class="step-label">${m.name}</span>
              </div>
            `).join('')}
          </div>

          <!-- DUAL STEP GRID: CURRENT STEP & UPCOMING TASK -->
          <div class="roadmap-step-dual-grid">
            <!-- CURRENT STEP -->
            <div class="step-card step-card--current">
              <div class="step-card__header">
                <span class="step-card__badge"><i data-lucide="play" style="width:11px; height:11px;"></i> CURRENT STEP</span>
                <span class="step-card__detail">${currentStep.detail}</span>
              </div>
              <h4 class="step-card__title">${currentStep.name}</h4>
              <a class="button step-card__action" style="background:#B22DEF; color:#FFF; font-weight:700; border-radius:9px; padding:6px 14px; font-size:11px; text-decoration:none; display:inline-flex; align-items:center; gap:6px;" href="#/individual/learning">
                Continue Step <i data-lucide="arrow-right"></i>
              </a>
            </div>

            <!-- UPCOMING TASK -->
            <div class="step-card step-card--next">
              <div class="step-card__header">
                <span class="step-card__badge-next"><i data-lucide="arrow-right-circle" style="width:11px; height:11px;"></i> UPCOMING TASK</span>
                <span class="step-card__detail">${nextStep.detail}</span>
              </div>
              <h4 class="step-card__title">${nextStep.name}</h4>
              <a class="button step-card__action" style="background:#FAF5FF; color:#7E22CE; border:1px solid #E9D8FD; font-weight:700; border-radius:9px; padding:6px 14px; font-size:11px; text-decoration:none; display:inline-flex; align-items:center; gap:6px;" href="#/individual/learning">
                View Task <i data-lucide="chevron-right"></i>
              </a>
            </div>
          </div>

          <!-- COMPACT SUMMARY BADGES ROW -->
          <div class="roadmap-summary-bar">
            <div class="summary-badge summary-badge--completed">
              <i data-lucide="check-circle-2"></i> <strong>${completedCount}</strong> Completed
            </div>
            <div class="summary-badge summary-badge--current">
              <i data-lucide="clock"></i> <strong>${currentCount}</strong> Current
            </div>
            <div class="summary-badge summary-badge--upcoming">
              <i data-lucide="circle"></i> <strong>${upcomingCount}</strong> Upcoming
            </div>
            <div class="summary-badge summary-badge--achievement">
              <i data-lucide="sparkles"></i> <span>${achievementStatus}</span>
            </div>
          </div>

          <!-- FOOTER ACTIONS -->
          <div class="roadmap-card-footer">
            <a class="button button-continue-roadmap" href="#/individual/learning">
              Continue Roadmap <i data-lucide="arrow-right"></i>
            </a>
            <a class="button button-view-full-roadmap" href="#/individual/learning">
              View Full Roadmap <i data-lucide="external-link"></i>
            </a>
            <div class="roadmap-footer-tools" style="margin-left:auto; display:flex; align-items:center; gap:12px;">
              <button type="button" class="roadmap-text-btn" id="simulateCompleteRoadmapBtn" title="Test 100% completed view">
                Simulate 100% Completed
              </button>
              <button type="button" class="roadmap-text-btn" id="resetRoadmapBtn">
                End Roadmap
              </button>
            </div>
          </div>
        </div>
      </section>
    `;
  }

  // STATE B: COMPLETED ROADMAP (100% PROGRESS)
  if (status === 'completed') {
    const completedItems = defaults.completedItems;

    return `
      <section class="active-roadmap-section" id="active-roadmap-section" aria-label="Completed Roadmap">
        <div class="section-v2-header">
          <div class="section-v2-header__left">
            <span class="v2-kicker positive-kicker">✓ ROADMAP COMPLETED</span>
            <h2>${title}</h2>
          </div>
          <span class="context-chip positive" style="color:#059669; background:#ECFDF5; padding:4px 10px; border-radius:8px; font-weight:750; font-size:12px;">100% Completed</span>
        </div>

        <div class="roadmap-completed-surface">
          <div class="completed-hero-icon" style="background:#ECFDF5; color:#059669;">
            <i data-lucide="trophy"></i>
          </div>
          <span class="completed-badge-title" style="color:#059669; font-weight:800; font-size:12px; letter-spacing:0.5px;">ROADMAP COMPLETED</span>
          <div class="completed-percentage-display" style="font-size:36px; font-weight:850; color:#1F162B; line-height:1.1; margin:4px 0;">100%</div>
          <p class="completed-congrats-text" style="color:#6E5C7D; font-size:13px; margin:0 0 16px;">
            All milestones, assessments, and projects for <strong>${title}</strong> have been successfully verified.
          </p>

          <div class="completed-summary-grid">
            ${completedItems.map(item => `
              <div class="completed-summary-item">
                <i data-lucide="check-circle-2"></i> ${item}
              </div>
            `).join('')}
          </div>

          <div class="completed-actions-row" style="margin-top:20px; display:flex; gap:10px; flex-wrap:wrap;">
            <a class="button button--secondary completed-view-results-btn" href="#/individual/learning">
              View Results
            </a>
            <button type="button" class="button button--assistant completed-explore-next-btn" id="exploreNextGoalBtn">
              Explore Next Goal <i data-lucide="arrow-right"></i>
            </button>
          </div>
        </div>
      </section>
    `;
  }

  // STATE C: NO ACTIVE ROADMAP STATE (none, draft, empty, archived)
  return `
    <section class="active-roadmap-section" id="active-roadmap-section" aria-label="No Active Roadmap">
      <div class="section-v2-header">
        <div class="section-v2-header__left">
          <span class="v2-kicker">YOUR ACTIVE ROADMAP</span>
          <h2>Ready to build your next skill?</h2>
        </div>
      </div>

      <div class="roadmap-invitation-surface">
        <div class="invitation-icon-circle">
          <i data-lucide="route"></i>
        </div>
        <h3 class="invitation-title">READY TO BUILD YOUR NEXT SKILL?</h3>
        <p class="invitation-subtext">Explore a skill from Intelligence Console and create a personalized roadmap.</p>
        <div class="invitation-actions" style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          <button type="button" class="button button--assistant" id="exploreSkillIntelligenceBtn">
            Explore Skill Intelligence <i data-lucide="arrow-right"></i>
          </button>
          <button type="button" class="button button--secondary" id="quickStartRoadmapBtn">
            Build Roadmap <i data-lucide="map"></i>
          </button>
        </div>
      </div>
    </section>
  `;
}

function renderRoadmapCreationModal() {
  const currentTitle = roadmapState?.title || 'Python — Backend Development';
  const isAlreadyActive = roadmapState?.status === 'active';
  const skill = dashboardState.selectedSkill || 'Python';
  const selectedGoalType = intelligenceExplorerState.previewGoalType || 'Improve Current Skill';
  const previewMilestones = defaultRoadmapTemplates[selectedGoalType] || defaultRoadmapTemplates['Improve Current Skill'];
  const defaults = getRoadmapTypeDefaults(selectedGoalType, skill);

  return `
    <div class="v2-modal-overlay" id="roadmapPreviewModal" role="dialog" aria-modal="true" aria-label="Roadmap review and activation modal">
      <div class="v2-modal-container">
        <div class="v2-modal-header">
          <div>
            <span class="v2-kicker">AI-GENERATED ROADMAP PREVIEW</span>
            <h3>Personalized Learning Roadmap</h3>
          </div>
          <button type="button" class="v2-modal-close" id="cancelRoadmapPreviewBtn" aria-label="Close modal"><i data-lucide="x"></i></button>
        </div>

        <div class="v2-modal-body">
          ${isAlreadyActive ? `
            <div class="v2-modal-warning">
              <i data-lucide="alert-triangle" style="flex:0 0 16px; width:16px; height:16px;"></i>
              <div>
                <strong>Active Roadmap Notice</strong>
                <p>You currently have an active roadmap ("${currentTitle}"). A user can have ONE active roadmap at a time. Explicitly accepting this will replace it.</p>
              </div>
            </div>
          ` : ''}

          <div class="v2-modal-field-group" style="margin-bottom:12px;">
            <label for="roadmapGoalTypeSelect">Roadmap Goal (Choose Goal Type):</label>
            <select class="v2-modal-select" id="roadmapGoalTypeSelect">
              <option value="Improve Current Skill" ${selectedGoalType === 'Improve Current Skill' ? 'selected' : ''}>TYPE 1: Improve Current Skill (e.g. Improve Python)</option>
              <option value="Skill Switch" ${selectedGoalType === 'Skill Switch' ? 'selected' : ''}>TYPE 2: Skill Switch (e.g. Python → AI Engineering)</option>
              <option value="Career Preparation" ${selectedGoalType === 'Career Preparation' ? 'selected' : ''}>TYPE 3: Career Preparation (e.g. Prepare for AI Engineer)</option>
              <option value="Job Preparation" ${selectedGoalType === 'Job Preparation' ? 'selected' : ''}>TYPE 4: Job Preparation (e.g. Prepare for NVIDIA AI Engineer roles)</option>
              <option value="Company Preparation" ${selectedGoalType === 'Company Preparation' ? 'selected' : ''}>TYPE 5: Company Preparation (e.g. Prepare for Microsoft backend roles)</option>
            </select>
          </div>

          <div class="v2-modal-field-group" style="margin-bottom:12px;">
            <label for="roadmapTargetInput">Roadmap Title (Editable):</label>
            <input type="text" class="v2-modal-input" id="roadmapTargetInput" value="${defaults.title}" />
          </div>

          <div class="v2-modal-field-group" style="margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:#7E6B8E;">
              <span><strong>Estimated Commitment:</strong> 8 — 10 Weeks · 6 hrs/week</span>
              <span><strong>Tracking Mode:</strong> Automated Telemetry</span>
            </div>
          </div>

          <div class="v2-modal-milestones-preview">
            <strong style="font-size:12px; color:#5C526A; display:block; margin-bottom:8px;">Generated Milestone Tracking Sequence:</strong>
            <ul id="roadmapMilestonesPreviewList" class="v2-milestone-preview-list">
              ${previewMilestones.map((m, idx) => `
                <li>
                  <span><strong>${idx + 1}. ${m.name}</strong> &mdash; ${m.label}</span>
                  <span style="font-size:10px; font-weight:700; color:${m.status === 'completed' ? '#10B981' : m.status === 'current' ? '#B22DEF' : '#7A7085'}; text-transform:uppercase;">${m.status}</span>
                </li>
              `).join('')}
            </ul>
          </div>
        </div>

        <div class="v2-modal-footer">
          <button type="button" class="button button--secondary" id="cancelRoadmapPreviewBtn2">Cancel</button>
          <button type="button" class="button button--assistant" id="confirmActivateRoadmapBtn">
            Accept & Activate Roadmap <i data-lucide="arrow-right"></i>
          </button>
        </div>
      </div>
    </div>
  `;
}

function bindRedesignedHomeEvents() {
  document.querySelectorAll('[data-home-job-filter]').forEach(control => {
    control.addEventListener('change', event => {
      const { homeJobFilter } = event.currentTarget.dataset;
      homeJobIntelligenceState[homeJobFilter] = event.currentTarget.value;
      if (homeJobFilter === 'companyScope') {
        const nextContext = getHomeJobContext();
        homeJobIntelligenceState.company = nextContext.companies[0] || 'NVIDIA';
      }
      renderHome();
    });
  });

  document.querySelectorAll('[data-home-job-signal]').forEach(item => {
    const signalId = item.dataset.homeJobSignal;
    const showSignal = id => {
      const context = getHomeJobContext();
      const signal = context.signals.find(candidate => candidate.id === id);
      const detail = document.querySelector('#homeJobSignalDetail');
      if (signal && detail) detail.innerHTML = renderHomeJobSignalDetail(context, signal);
    };
    item.addEventListener('mouseenter', () => showSignal(signalId));
    item.addEventListener('mouseleave', () => showSignal(homeJobIntelligenceState.selectedSignal));
    item.addEventListener('focus', () => showSignal(signalId));
    item.addEventListener('blur', () => showSignal(homeJobIntelligenceState.selectedSignal));
    item.addEventListener('click', () => {
      homeJobIntelligenceState.selectedSignal = signalId;
      renderHome();
    });
    item.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      item.click();
    });
  });

  // Market Intelligence Unified Filters Toggle
  document.querySelector('#marketFiltersBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isMarketFilterOpen = !dashboardState.isMarketFilterOpen;
    renderHome();
  });

  document.querySelector('#closeMarketFilterBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isMarketFilterOpen = false;
    renderHome();
  });

  document.querySelector('#applyMarketFilterBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isMarketFilterOpen = false;
    renderHome();
  });

  // Market Filter Pill Handlers
  document.querySelectorAll('[data-set-market-company-scope]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.marketCompanyScope = pill.dataset.setMarketCompanyScope;
      intelligenceExplorerState.companyScope = pill.dataset.setMarketCompanyScope;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-market-location]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.marketLocation = pill.dataset.setMarketLocation;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-market-time]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.marketTime = pill.dataset.setMarketTime;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-market-date]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.marketDate = pill.dataset.setMarketDate;
      renderHome();
    });
  });

  // Select Market Company Row
  document.querySelectorAll('[data-select-market-company]').forEach(row => {
    row.addEventListener('click', () => {
      dashboardState.selectedMarketCompany = row.dataset.selectMarketCompany;
      intelligenceExplorerState.selected.companies = row.dataset.selectMarketCompany;
      renderHome();
    });
    row.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      row.click();
    });
  });

  // Toggle Favorite Company
  document.querySelectorAll('[data-toggle-company-fav]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const cName = btn.dataset.toggleCompanyFav;
      const target = marketIntelligenceData.companies.find(c => c.name === cName);
      if (target) {
        target.isFavorite = !target.isFavorite;
        renderHome();
      }
    });
  });

  // Skill Intelligence Unified Filters Toggle
  document.querySelector('#skillFiltersBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isSkillFilterOpen = !dashboardState.isSkillFilterOpen;
    renderHome();
  });

  document.querySelector('#closeSkillFilterBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isSkillFilterOpen = false;
    renderHome();
  });

  document.querySelector('#applySkillFilterBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    dashboardState.isSkillFilterOpen = false;
    renderHome();
  });

  // Filter Pill Handlers
  document.querySelectorAll('[data-set-skill-scope]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.skillScope = pill.dataset.setSkillScope;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-skill-location]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.skillLocation = pill.dataset.setSkillLocation;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-skill-time]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.skillTime = pill.dataset.setSkillTime;
      dashboardState.timeRange = pill.dataset.setSkillTime;
      renderHome();
    });
  });

  document.querySelectorAll('[data-set-skill-date]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.skillDate = pill.dataset.setSkillDate;
      renderHome();
    });
  });

  // Toggle Favorite Skill (strictly limited to maximum 5 favorites)
  document.querySelectorAll('[data-toggle-fav]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sName = btn.dataset.toggleFav;
      const target = skillMarketData.find(s => s.name === sName);
      if (target) {
        if (target.isFavorite) {
          target.isFavorite = false;
        } else {
          const currentFavCount = skillMarketData.filter(s => s.isFavorite).length;
          if (currentFavCount >= 5) {
            alert('Maximum 5 favorite skills allowed. Please un-favorite a skill first.');
            return;
          }
          target.isFavorite = true;
        }
        localStorage.setItem('talentscope-favorite-skills', JSON.stringify(skillMarketData.filter(s => s.isFavorite).map(s => s.name)));
        renderHome();
      }
    });
  });

  // Chip selectors for skills, companies, roles
  document.querySelectorAll('[data-select-skill-chip]').forEach(chip => {
    chip.addEventListener('click', () => {
      dashboardState.selectedSkill = chip.dataset.selectSkillChip;
      renderHome();
    });
  });

  document.querySelectorAll('[data-select-company-chip]').forEach(chip => {
    chip.addEventListener('click', () => {
      intelligenceExplorerState.selected.companies = chip.dataset.selectCompanyChip;
      renderHome();
    });
  });

  document.querySelectorAll('[data-select-role-chip]').forEach(chip => {
    chip.addEventListener('click', () => {
      intelligenceExplorerState.selected.roles = chip.dataset.selectRoleChip;
      renderHome();
    });
  });

  // Scope selects
  document.querySelector('#consoleSkillScope')?.addEventListener('change', (e) => {
    intelligenceExplorerState.skillScope = e.target.value;
    renderHome();
  });
  document.querySelector('#consoleCompanyScope')?.addEventListener('change', (e) => {
    intelligenceExplorerState.companyScope = e.target.value;
    renderHome();
  });

  // Add skill submit
  document.querySelector('#submitNewSkillBtn')?.addEventListener('click', () => {
    const input = document.querySelector('#newSkillInput');
    if (input && input.value.trim()) {
      dashboardState.selectedSkill = input.value.trim();
      intelligenceExplorerState.skillScope = 'My Skills';
      renderHome();
    }
  });

  // Add company submit
  document.querySelector('#submitNewCompanyBtn')?.addEventListener('click', () => {
    const input = document.querySelector('#newCompanyInput');
    if (input && input.value.trim()) {
      intelligenceExplorerState.selected.companies = input.value.trim();
      intelligenceExplorerState.companyScope = 'My Companies';
      renderHome();
    }
  });

  // Trigger Roadmap Preview Modal
  document.querySelectorAll('#triggerRoadmapPreviewBtn, [data-roadmap-accept], #startNewRoadmapFlowBtn, #quickStartRoadmapBtn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      intelligenceExplorerState.isRoadmapPreviewing = true;
      renderHome();
    });
  });

  // Empty state: Explore Skill Intelligence button
  document.querySelector('#exploreSkillIntelligenceBtn')?.addEventListener('click', () => {
    const consoleSec = document.getElementById('intelligence-console-hero') || document.getElementById('skill-intelligence-section');
    if (consoleSec) {
      consoleSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      intelligenceExplorerState.isRoadmapPreviewing = true;
      renderHome();
    }
  });

  // Cancel Roadmap Preview
  document.querySelectorAll('#cancelRoadmapPreviewBtn, #cancelRoadmapPreviewBtn2').forEach(btn => {
    btn.addEventListener('click', () => {
      intelligenceExplorerState.isRoadmapPreviewing = false;
      renderHome();
    });
  });

  // Change Roadmap Type Select inside Modal
  document.querySelector('#roadmapGoalTypeSelect')?.addEventListener('change', (e) => {
    intelligenceExplorerState.previewGoalType = e.target.value;
    const skill = dashboardState.selectedSkill || 'Python';
    const defaults = getRoadmapTypeDefaults(e.target.value, skill);
    const titleInput = document.querySelector('#roadmapTargetInput');
    if (titleInput) {
      titleInput.value = defaults.title;
    }
    const previewList = document.querySelector('#roadmapMilestonesPreviewList');
    if (previewList) {
      const milestones = defaultRoadmapTemplates[e.target.value] || defaultRoadmapTemplates['Improve Current Skill'];
      previewList.innerHTML = milestones.map((m, idx) => `
        <li>
          <span><strong>${idx + 1}. ${m.name}</strong> &mdash; ${m.label}</span>
          <span style="font-size:10px; font-weight:700; color:${m.status === 'completed' ? '#10B981' : m.status === 'current' ? '#B22DEF' : '#7A7085'}; text-transform:uppercase;">${m.status}</span>
        </li>
      `).join('');
    }
  });

  // Explicit Confirm and Activate Roadmap (Step 6 of Creation Flow)
  document.querySelector('#confirmActivateRoadmapBtn')?.addEventListener('click', () => {
    const goalType = document.querySelector('#roadmapGoalTypeSelect')?.value || 'Improve Current Skill';
    const inputTitle = document.querySelector('#roadmapTargetInput')?.value;
    const skill = dashboardState.selectedSkill || 'Python';
    const defaults = getRoadmapTypeDefaults(goalType, skill);
    const title = inputTitle && inputTitle.trim() ? inputTitle.trim() : defaults.title;
    const milestones = defaultRoadmapTemplates[goalType] || defaultRoadmapTemplates['Improve Current Skill'];

    roadmapState = {
      id: 'rm-' + Date.now(),
      title: title,
      goalType: goalType,
      status: 'active',
      progress: 64,
      createdFrom: 'Skill Intelligence',
      currentStep: defaults.currentStep,
      nextStep: defaults.nextStep,
      completedCount: 8,
      currentCount: 1,
      upcomingCount: 4,
      achievementStatus: 'On Track · +14% this week',
      milestones: milestones
    };

    persistRoadmapState();
    intelligenceExplorerState.isRoadmapPreviewing = false;
    renderHome();
    document.getElementById('active-roadmap-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // Reset / End Roadmap
  document.querySelector('#resetRoadmapBtn')?.addEventListener('click', () => {
    roadmapState.status = 'none';
    persistRoadmapState();
    renderHome();
  });

  // Simulate 100% Completed
  document.querySelector('#simulateCompleteRoadmapBtn')?.addEventListener('click', () => {
    roadmapState.status = 'completed';
    roadmapState.progress = 100;
    persistRoadmapState();
    renderHome();
  });

  // Explore Next Goal (from Completed state)
  document.querySelector('#exploreNextGoalBtn')?.addEventListener('click', () => {
    roadmapState.status = 'none';
    persistRoadmapState();
    renderHome();
    document.getElementById('intelligence-console-hero')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  document.querySelectorAll('[data-overview-target]').forEach(zone => {
    zone.addEventListener('click', () => {
      const targetId = zone.dataset.overviewTarget;
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // STEP 3: Intelligence Domain Selection (First Step)
  document.querySelectorAll('[data-select-domain]').forEach(card => {
    card.addEventListener('click', () => {
      const domain = card.dataset.selectDomain;
      intelligenceExplorerState.type = domain;
      intelligenceExplorerState.domainSelected = true;
      intelligenceExplorerState.isAnalyzing = false;
      intelligenceExplorerState.hasSearched = false;
      intelligenceExplorerState.question = '';
      renderHome();
    });
    card.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      card.click();
    });
  });

  // Switch Intelligence Domain Tabs
  document.querySelectorAll('[data-switch-domain], [data-console-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      const domain = btn.dataset.switchDomain || btn.dataset.consoleMode;
      intelligenceExplorerState.type = domain;
      intelligenceExplorerState.domainSelected = true;
      intelligenceExplorerState.isAnalyzing = false;
      intelligenceExplorerState.hasSearched = false;
      intelligenceExplorerState.question = '';
      renderHome();
    });
  });

  // Return to First Step (Change Domain)
  document.querySelector('#changeConsoleDomainBtn')?.addEventListener('click', () => {
    intelligenceExplorerState.domainSelected = false;
    intelligenceExplorerState.isAnalyzing = false;
    renderHome();
  });

  // Console Scope Switchers
  document.querySelectorAll('[data-console-skill-scope]').forEach(btn => {
    btn.addEventListener('click', () => {
      intelligenceExplorerState.skillScope = btn.dataset.consoleSkillScope;
      renderHome();
    });
  });
  document.querySelectorAll('[data-console-company-scope]').forEach(btn => {
    btn.addEventListener('click', () => {
      intelligenceExplorerState.companyScope = btn.dataset.consoleCompanyScope;
      renderHome();
    });
  });
  document.querySelectorAll('[data-console-job-scope]').forEach(btn => {
    btn.addEventListener('click', () => {
      intelligenceExplorerState.jobScope = btn.dataset.consoleJobScope;
      renderHome();
    });
  });

  // Console Time Range Switcher
  document.querySelectorAll('[data-console-time-range]').forEach(btn => {
    btn.addEventListener('click', () => {
      intelligenceExplorerState.timeRange = btn.dataset.consoleTimeRange;
      dashboardState.timeRange = btn.dataset.consoleTimeRange;
      renderHome();
    });
  });

  // Console Location Selector
  document.querySelector('#consoleLocationSelect')?.addEventListener('change', (e) => {
    dashboardState.selectedLocation = e.target.value;
    dashboardState.market = e.target.value;
    renderHome();
  });

  // Clear Input Button
  document.querySelector('#consoleClearInputBtn')?.addEventListener('click', () => {
    intelligenceExplorerState.question = '';
    const queryInput = document.querySelector('#consoleQueryInput');
    if (queryInput) queryInput.value = '';
    renderHome();
  });

  // Suggested Prompts
  document.querySelectorAll('[data-console-prompt]').forEach(chip => {
    chip.addEventListener('click', () => {
      const queryInput = document.querySelector('#consoleQueryInput');
      if (queryInput) queryInput.value = chip.dataset.consolePrompt;
      triggerConsoleAnalysis(chip.dataset.consolePrompt);
    });
  });

  // Primary Analyze Submit Button
  document.querySelector('#consoleAnalyzeSubmit')?.addEventListener('click', () => {
    const queryInput = document.querySelector('#consoleQueryInput');
    const query = queryInput ? queryInput.value.trim() : '';
    triggerConsoleAnalysis(query);
  });

  // Enter key submits query
  document.querySelector('#consoleQueryInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      document.querySelector('#consoleAnalyzeSubmit')?.click();
    }
  });

  // Save Result to Intelligence
  document.querySelector('#saveConsoleResultBtn')?.addEventListener('click', (e) => {
    const btn = e.currentTarget;
    btn.innerHTML = '<i data-lucide="check"></i> <span>Saved to intelligence</span>';
    btn.disabled = true;
    lucide.createIcons();
  });

  // New Query Button (Reset Result)
  document.querySelector('#consoleAskAnotherBtn')?.addEventListener('click', () => {
    intelligenceExplorerState.hasSearched = false;
    intelligenceExplorerState.isAnalyzing = false;
    intelligenceExplorerState.question = '';
    renderHome();
  });

  document.querySelectorAll('[data-select-skill]').forEach(row => {
    row.addEventListener('click', () => {
      dashboardState.selectedSkill = row.dataset.selectSkill;
      renderHome();
    });
    row.addEventListener('keydown', event => {
      if (event.target !== row || (event.key !== 'Enter' && event.key !== ' ')) return;
      event.preventDefault();
      row.click();
    });
  });

  document.querySelectorAll('[data-select-company]').forEach(row => {
    row.addEventListener('click', () => {
      intelligenceExplorerState.selected.companies = row.dataset.selectCompany;
      renderHome();
    });
  });

  document.querySelectorAll('[data-skill-range]').forEach(btn => {
    btn.addEventListener('click', () => {
      dashboardState.timeRange = btn.dataset.skillRange;
      renderHome();
    });
  });

  document.querySelectorAll('[data-market-range]').forEach(btn => {
    btn.addEventListener('click', () => {
      dashboardState.timeRange = btn.dataset.marketRange;
      renderHome();
    });
  });

  document.querySelector('#skillLocationSelect')?.addEventListener('change', (e) => {
    dashboardState.market = e.target.value;
    renderHome();
  });
  
  document.querySelector('#marketLocationSelect')?.addEventListener('change', (e) => {
    dashboardState.market = e.target.value;
    renderHome();
  });
  
  // Location picker button
  const locationBtn = document.querySelector('#locationPickerBtn');
  const locationContainer = document.querySelector('#locationPickerContainer');
  if (locationBtn) {
    locationBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dashboardState.isLocationMenuOpen = !dashboardState.isLocationMenuOpen;
      renderHome();
    });
    document.addEventListener('click', () => {
      if (dashboardState.isLocationMenuOpen) {
        dashboardState.isLocationMenuOpen = false;
        renderHome();
      }
    }, { once: true });
  }
  
  // Location option selection
  document.querySelectorAll('[data-location-id]').forEach(opt => {
    opt.addEventListener('click', () => {
      dashboardState.selectedLocation = opt.dataset.locationLabel;
      dashboardState.isLocationMenuOpen = false;
      renderHome();
    });
  });

  // Init scroll-reveal on home sections
  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    
    document.querySelectorAll('.home-dashboard-v2 > *').forEach(section => {
      revealObserver.observe(section);
    });
  }
  
  // Start live simulation
  initHomeSimulation();
}

function triggerConsoleAnalysis(query) {
  intelligenceExplorerState.question = query;
  intelligenceExplorerState.isAnalyzing = true;
  intelligenceExplorerState.analysisStep = 0;
  intelligenceExplorerState.hasSearched = true;
  renderHome();

  let step = 0;
  const totalSteps = 5;
  const interval = setInterval(() => {
    step++;
    intelligenceExplorerState.analysisStep = step;
    if (step >= totalSteps) {
      intelligenceExplorerState.isAnalyzing = false;
      clearInterval(interval);
    }
    renderHome();
  }, 480);
}

// ============================================================
// HOME LIVE SIMULATION ENGINE
// Demo-only frontend simulation. No backend connection.
// ============================================================

const homeSimState = {
  active: false,
  intervalId: null,
  tick: 0,
  skillData: null,   // copy of skillMarketData for mutation
  marketData: null,  // copy of marketIntelligenceData for mutation
  overviewData: null, // copy of overviewData for mutation
  jobsOpenRoles: null
};

function initHomeSimulation() {
  if (homeSimState.active) return;
  homeSimState.active = true;
  if (homeSimState.jobsOpenRoles === null) homeSimState.jobsOpenRoles = getJobSummary() || overviewData.jobs.openRoles;
  // Keep the deterministic sequence moving when Home re-renders after an action.
  
  // Deep-copy mutable sim data
  homeSimState.skillData = skillMarketData.map(s => ({ ...s, values: [...s.values], growth: s.growth }));
  homeSimState.marketData = marketIntelligenceData.companies.map(c => ({ ...c, history: [...c.history], change: c.change }));
  
  // Run simulation tick every 4 seconds (performance-friendly)
  homeSimState.intervalId = setInterval(runHomeSimTick, 5000);
}

function stopHomeSimulation() {
  if (homeSimState.intervalId) {
    clearInterval(homeSimState.intervalId);
    homeSimState.intervalId = null;
  }
  homeSimState.active = false;
}

// Seeded pseudo-random for deterministic behavior
function seededRandom(seed) {
  const x = Math.sin(seed + 1) * 10000;
  return x - Math.floor(x);
}

function smallFluctuation(currentValue, tick, index, maxRange) {
  // Small ±2% fluctuation with occasional trend reversal
  const seed = tick * 13 + index * 7;
  const rand = seededRandom(seed);
  const reversing = tick % 12 >= 8 && tick % 12 <= 10 && index % 3 === 0;
  const delta = (rand - (reversing ? 0.72 : 0.48)) * maxRange;
  return parseFloat((currentValue + delta).toFixed(1));
}

function runHomeSimTick() {
  homeSimState.tick++;
  const t = homeSimState.tick;
  const previousOverviewValues = {
    skill: overviewData.skill.change,
    market: overviewData.market.change,
    jobs: overviewData.jobs.change
  };
  
  // Check if Home is visible
  const homeDash = document.querySelector('.home-dashboard-v2');
  if (!homeDash) { stopHomeSimulation(); return; }
  if (document.visibilityState === 'hidden') return;
  
  // 1. Update skill growth values (small fluctuations)
  skillMarketData.forEach((skill, i) => {
    const newGrowth = smallFluctuation(skill.growth, t, i, 2.0);
    // Clamp to reasonable range
    skill.growth = Math.max(-15, Math.min(50, newGrowth));
    
    // Add new point to values array, drop oldest
    const lastVal = skill.values[skill.values.length - 1];
    const delta = (seededRandom(t * 17 + i * 5) - 0.48) * 4;
    const newVal = Math.max(10, Math.min(98, lastVal + delta));
    skill.values = [...skill.values.slice(1), parseFloat(newVal.toFixed(1))];
    
    // Update direction based on last 3 points
    const last3 = skill.values.slice(-3);
    skill.direction = skill.growth < 0 ? 'down' : last3[2] >= last3[0] ? 'up' : 'down';
  });
  
  // 2. Update market company momentum
  marketIntelligenceData.companies.forEach((company, i) => {
    const newChange = smallFluctuation(company.change, t, i + 20, 1.5);
    company.change = Math.max(-20, Math.min(45, newChange));
    
    const lastVal = company.history[company.history.length - 1];
    const delta = (seededRandom(t * 11 + i * 9) - 0.48) * 3;
    const newVal = Math.max(10, Math.min(99, lastVal + delta));
    company.history = [...company.history.slice(1), parseFloat(newVal.toFixed(1))];
    company.direction = company.change >= 0 ? 'up' : 'down';
    
    // Update signalType based on direction
    company.signalType = company.change > 5 ? 'positive' : company.change < -2 ? 'decline' : 'neutral';
  });

  Object.entries(marketIntelligenceData.signals).forEach(([signal, values], signalIndex) => {
    const latest = values[values.length - 1];
    const delta = (seededRandom(t * 23 + signalIndex * 17) - (t % 12 >= 8 ? 0.66 : 0.42)) * 2.2;
    marketIntelligenceData.signals[signal] = [...values.slice(1), Math.max(12, Math.min(96, Number((latest + delta).toFixed(1))))];
  });
  
  // 3. Update overview card data
  overviewData.skill.change = skillMarketData.find(skill => skill.id === 'ml')?.growth ?? overviewData.skill.change;
  overviewData.market.change = marketIntelligenceData.companies.find(company => company.name === overviewData.market.company)?.change ?? overviewData.market.change;
  overviewData.skill.direction = overviewData.skill.change >= previousOverviewValues.skill ? 'up' : 'down';
  overviewData.market.direction = overviewData.market.change >= previousOverviewValues.market ? 'up' : 'down';
  jobMarketData.demandIndex = Math.max(78, Math.min(98, Number((jobMarketData.demandIndex + (seededRandom(t * 31) - 0.5) * 1.2).toFixed(1))));
  jobMarketData.hiringMomentum = Number(smallFluctuation(jobMarketData.hiringMomentum, t, 42, 1.1).toFixed(1));
  jobMarketData.totalOpenRoles = Math.max(39000, Math.min(47000, jobMarketData.totalOpenRoles + Math.round((seededRandom(t * 37) - 0.48) * 140)));
  homeSimState.jobsOpenRoles = Math.max(1800, Math.min(12000, homeSimState.jobsOpenRoles + Math.round((seededRandom(t * 43) - 0.48) * 22)));
  overviewData.jobs.change = jobMarketData.hiringMomentum;
  overviewData.jobs.direction = overviewData.jobs.change >= previousOverviewValues.jobs ? 'up' : 'down';
  const advanceOverviewSeries = (series, direction, seed) => {
    const step = 0.8 + seededRandom(seed) * 1.2;
    const last = series.at(-1) ?? 50;
    const next = Math.max(8, Math.min(92, last + (direction === 'down' ? -step : step)));
    return [...series.slice(1), Number(next.toFixed(1))];
  };
  overviewData.skill.chartPoints = advanceOverviewSeries(overviewData.skill.chartPoints, overviewData.skill.direction, t * 29);
  overviewData.market.chartPoints = advanceOverviewSeries(overviewData.market.chartPoints, overviewData.market.direction, t * 31);
  overviewData.jobs.bars = advanceOverviewSeries(overviewData.jobs.bars, overviewData.jobs.direction, t * 37);
  
  // 4. Sort market companies by momentum (ranking reorder)
  // Use stable sort to avoid jarring jumps
  marketIntelligenceData.companies.sort((a, b) => b.change - a.change);
  
  // 5. Sort skill data by growth
  skillMarketData.sort((a, b) => b.growth - a.growth);
  
  // 6. Re-render only the changing sections for performance
  updateHomeChartsInPlace();
}

const homePolylineFrames = new WeakMap();

function animateHomePolyline(polyline, nextPoints, duration = 620) {
  const parse = value => (value.match(/-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?/g) || []).map(pair => pair.split(',').map(Number));
  const from = parse(polyline.getAttribute('points') || '');
  const to = parse(nextPoints);
  if (!from.length || from.length !== to.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    polyline.setAttribute('points', nextPoints);
    return;
  }
  const pending = homePolylineFrames.get(polyline);
  if (pending) cancelAnimationFrame(pending);
  const started = performance.now();
  const step = now => {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    polyline.setAttribute('points', from.map((point, index) => `${(point[0] + (to[index][0] - point[0]) * eased).toFixed(1)},${(point[1] + (to[index][1] - point[1]) * eased).toFixed(1)}`).join(' '));
    if (progress < 1) homePolylineFrames.set(polyline, requestAnimationFrame(step));
    else homePolylineFrames.delete(polyline);
  };
  homePolylineFrames.set(polyline, requestAnimationFrame(step));
}

function updateMiniChart(svg, values, direction, palette = 'skill') {
  const points = values.map((value, index) => `${(index / Math.max(1, values.length - 1) * 140).toFixed(1)},${(32 - Math.max(0, Math.min(100, value)) * .24).toFixed(1)}`).join(' ');
  const color = direction === 'down' ? '#E05252' : palette === 'market' ? '#06B6D4' : '#19B77A';
  const line = svg.querySelector('polyline');
  const area = svg.querySelector('polygon');
  if (line) { animateHomePolyline(line, points, 460); line.setAttribute('stroke', color); }
  if (area) animateHomePolyline(area, `0,36 ${points} 140,36`, 460);
}

function reorderHomeRows(selector, rows, rankSelector = null) {
  const list = document.querySelector(selector);
  if (!list || rows.length < 2) return;
  const current = [...list.children];
  const changed = rows.some((row, index) => current[index] !== row);
  rows.forEach((row, index) => {
    if (!rankSelector) return;
    const rank = row.querySelector(rankSelector);
    if (rank) rank.textContent = String(index + 1).padStart(2, '0');
  });
  if (!changed) return;
  const before = new Map(rows.map(row => [row, row.getBoundingClientRect().top]));
  rows.forEach(row => list.appendChild(row));
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  rows.forEach(row => {
    const delta = before.get(row) - row.getBoundingClientRect().top;
    if (Math.abs(delta) > 1) row.animate([{ transform: `translateY(${delta}px)` }, { transform: 'translateY(0)' }], { duration: 480, easing: 'cubic-bezier(.22,1,.36,1)' });
  });
}

function updateMarketChartInPlace() {
  const svg = document.querySelector('#marketMultiSignalChart');
  if (!svg) return;
  const colors = { investment: '#8B3DFF', technology: '#10B981', hiring: '#F59E0B' };
  
  Object.entries(marketIntelligenceData.signals).forEach(([key, values]) => {
    const line = svg.querySelector(`[data-market-signal="${key}"]`);
    const node = svg.querySelector(`[data-market-node="${key}"]`);
    if (!line) return;
    const points = values.map((value, index) => `${(38 + (index / Math.max(1, values.length - 1)) * 440).toFixed(1)},${(190 - value * 1.5).toFixed(1)}`).join(' ');
    const direction = values.at(-1) >= values.at(-2) ? 'up' : 'down';
    animateHomePolyline(line, points);
    line.setAttribute('stroke', colors[key]);
    line.dataset.direction = direction;

    if (node) {
      const lastX = 38 + 440;
      const lastY = 190 - values.at(-1) * 1.5;
      node.style.transition = 'cx 520ms cubic-bezier(.22,1,.36,1), cy 520ms cubic-bezier(.22,1,.36,1)';
      node.setAttribute('cx', lastX.toFixed(1));
      node.setAttribute('cy', lastY.toFixed(1));
    }

    const legendVal = document.querySelector(`[data-market-legend="${key}"] .market-legend-val`);
    if (legendVal) {
      const change = values.at(-1) - values.at(-2);
      const isNegative = change < 0;
      legendVal.textContent = `${change > 0 ? '+' : ''}${change.toFixed(1)}% ${isNegative ? '↓' : '↑'}`;
      legendVal.style.color = isNegative ? '#EF4444' : '#10B981';
      legendVal.style.background = isNegative ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)';
    }
  });

  // Update selected company badge in Left Panel
  const selectedCompanyName = dashboardState.selectedMarketCompany || intelligenceExplorerState.selected.companies || 'NVIDIA';
  const selectedCompany = marketIntelligenceData.companies.find(c => c.name === selectedCompanyName) || marketIntelligenceData.companies[0];
  const marketBadge = document.querySelector('.market-analytical-surface .skill-badge-trend');
  if (marketBadge && selectedCompany) {
    const negative = selectedCompany.change < 0;
    marketBadge.classList.toggle('decline', negative);
    marketBadge.classList.toggle('positive', !negative);
    marketBadge.style.color = negative ? '#EF4444' : '#10B981';
    marketBadge.style.background = negative ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)';
    marketBadge.innerHTML = `<span aria-hidden="true">${negative ? '↓' : '↑'}</span> ${selectedCompany.change > 0 ? '+' : ''}${selectedCompany.change.toFixed(1)}% ${negative ? 'Restructuring Signal ↓' : 'Market Momentum ↑'}`;
  }

  // Update rows in right panel
  document.querySelectorAll('.company-market-row').forEach(row => {
    const company = marketIntelligenceData.companies.find(item => item.name === row.dataset.selectMarketCompany);
    if (!company) return;
    const value = row.querySelector('.company-momentum-val');
    if (value) {
      const isNegative = company.change < 0;
      value.style.color = isNegative ? '#EF4444' : '#10B981';
      setHomeLiveText(value, `${company.direction === 'down' ? '↓' : '↑'} ${company.change > 0 ? '+' : ''}${company.change.toFixed(1)}%`);
    }
    const chart = row.querySelector('.company-sparkline-wrap svg');
    if (chart) updateMiniChart(chart, company.history, company.direction, 'market');
    const signal = row.querySelector('.company-signal-tag');
    if (signal) {
      signal.className = `company-signal-tag ${company.signalType}`;
      signal.textContent = company.signalType === 'decline' ? 'Restructuring' : company.signalText;
    }
  });

  const companyRows = [...document.querySelectorAll('.company-market-row')].sort((a, b) => {
    const left = marketIntelligenceData.companies.find(item => item.name === a.dataset.selectMarketCompany)?.change ?? -Infinity;
    const right = marketIntelligenceData.companies.find(item => item.name === b.dataset.selectMarketCompany)?.change ?? -Infinity;
    return right - left;
  });
  reorderHomeRows('.company-market-list', companyRows, '.company-rank');
}

function updateJobMetricsInPlace() {
  const demand = document.querySelector('.job-metric-pill--demand .job-metric-pill__value strong');
  const hiring = document.querySelector('.job-metric-pill--momentum .job-metric-pill__value strong');
  const roles = document.querySelector('.job-donut-center-copy strong');
  if (demand) setHomeLiveText(demand, jobMarketData.demandIndex.toFixed(0));
  if (hiring) {
    const negative = jobMarketData.hiringMomentum < 0;
    setHomeLiveText(hiring, `${jobMarketData.hiringMomentum > 0 ? '+' : ''}${jobMarketData.hiringMomentum.toFixed(1)}%`);
    hiring.closest('.job-metric-pill__value')?.classList.toggle('is-negative', negative);
    hiring.closest('.job-metric-pill__value')?.classList.toggle('positive', !negative);
  }
  if (roles) setHomeLiveText(roles, `${(jobMarketData.totalOpenRoles / 1000).toFixed(1)}K`);
}

function setHomeLiveText(element, value) {
  if (!element || element.textContent === value) return;
  element.textContent = value;
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    element.animate([{ opacity: .55, transform: 'translateY(4px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'cubic-bezier(.22,1,.36,1)' });
  }
}

function updateHomeChartsInPlace() {
  const scope = dashboardState.skillScope || 'All Skills';
  
  // 1. Update Multi-Series Chart in All Skills or Favorite Skills mode
  const multiSVG = document.querySelector('#skillMultiSeriesChart');
  if (multiSVG) {
    let topList = [...skillMarketData].sort((a, b) => b.growth - a.growth).slice(0, 5);
    if (scope === 'Favorite Skills') {
      topList = skillMarketData.filter(s => s.isFavorite).slice(0, 5);
    }
    
    const maxVal = Math.max(...topList.flatMap(s => s.values), 100);
    const minVal = 0;
    const range = (maxVal - minVal) || 1;

    topList.forEach((skill) => {
      const line = multiSVG.querySelector(`[data-skill-series="${skill.name}"]`);
      const node = multiSVG.querySelector(`[data-skill-node="${skill.name}"]`);
      const legendPill = document.querySelector(`[data-legend-skill="${skill.name}"]`);
      
      const values = skill.values;
      const coords = values.map((v, i) => {
        const x = 36 + (i / (values.length - 1)) * 436;
        const y = 185 - ((v - minVal) / range) * 150;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');

      const color = skill.growth < 0 ? '#EF4444' : '#10B981';

      if (line) {
        animateHomePolyline(line, coords);
        line.setAttribute('stroke', color);
      }

      if (node) {
        const lastVal = values[values.length - 1];
        const lastX = 36 + 436;
        const lastY = 185 - ((lastVal - minVal) / range) * 150;
        node.style.transition = 'cx 520ms cubic-bezier(.22,1,.36,1), cy 520ms cubic-bezier(.22,1,.36,1)';
        node.setAttribute('cx', lastX.toFixed(1));
        node.setAttribute('cy', lastY.toFixed(1));
        node.setAttribute('fill', color);
      }

      if (legendPill) {
        const dot = legendPill.querySelector('.skill-legend-dot');
        const val = legendPill.querySelector('.skill-legend-value');
        if (dot) dot.style.background = color;
        if (val) {
          val.style.color = color;
          val.textContent = `${skill.growth > 0 ? '+' : ''}${skill.growth.toFixed(1)}% ${skill.direction === 'down' ? '↓' : '↑'}`;
        }
      }
    });
  }

  // 2. Update Single Skill Chart in My Skills mode
  const singleSVG = document.querySelector('.skill-chart-main .skill-single-chart-wrap svg');
  const selectedName = dashboardState.selectedSkill || 'Machine Learning';
  const matchedSkill = skillMarketData.find(skill => skill.name === selectedName) || skillMarketData[0];
  if (singleSVG && matchedSkill) {
    const values = matchedSkill.values;
    const maxVal = Math.max(...values, 100);
    const coords = values.map((value, index) => `${(index / (values.length - 1) * 480).toFixed(1)},${(200 - (value / maxVal) * 160).toFixed(1)}`).join(' ');
    const color = matchedSkill.growth < 0 ? '#EF4444' : '#10B981';
    const line = singleSVG.querySelector('polyline');
    const area = singleSVG.querySelector('polygon');
    if (line) { animateHomePolyline(line, coords); line.setAttribute('stroke', color); }
    if (area) {
      area.setAttribute('points', `0,220 ${coords} 480,220`);
      const stop = singleSVG.querySelector('stop:first-child');
      if (stop) stop.setAttribute('stop-color', color);
    }
    singleSVG.querySelectorAll('circle').forEach((circle, index) => {
      if (!values[index]) return;
      circle.style.transition = 'cx 520ms cubic-bezier(.22,1,.36,1), cy 520ms cubic-bezier(.22,1,.36,1)';
      circle.setAttribute('cx', (index / (values.length - 1) * 480).toFixed(1));
      circle.setAttribute('cy', (200 - (values[index] / maxVal) * 160).toFixed(1));
    });

    const badge = document.querySelector('.skill-intelligence-section .skill-chart-main .skill-badge-trend');
    if (badge) {
      const negative = matchedSkill.growth < 0;
      badge.classList.toggle('decline', negative);
      badge.classList.toggle('positive', !negative);
      badge.style.color = negative ? '#EF4444' : '#10B981';
      badge.style.background = negative ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)';
      badge.innerHTML = `<span aria-hidden="true">${negative ? '↓' : '↑'}</span> ${matchedSkill.growth > 0 ? '+' : ''}${matchedSkill.growth.toFixed(1)}% ${negative ? 'Decline ↓' : 'Growing ↑'}`;
    }
  }

  // 3. Update right-box rows
  document.querySelectorAll('.skill-rail-row').forEach(row => {
    const skillName = row.dataset.selectSkill;
    const skill = skillMarketData.find(item => item.name === skillName);
    if (!skill) return;
    const value = row.querySelector('.skill-rail-change');
    const chart = row.querySelector('.skill-rail-mini-chart');
    const negative = skill.growth < 0;
    if (value) {
      value.style.color = negative ? '#EF4444' : '#10B981';
      value.innerHTML = `<span aria-hidden="true">${negative ? '↓' : '↑'}</span> ${skill.growth > 0 ? '+' : ''}${skill.growth.toFixed(1)}%`;
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        value.animate([{ opacity: .6, transform: 'translateY(3px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 280, easing: 'cubic-bezier(.22,1,.36,1)' });
      }
    }
    if (chart) updateMiniChart(chart, skill.values, skill.direction);
  });

  // 4. In All Skills mode, smoothly reorder top skills
  if (scope === 'All Skills') {
    const skillRows = [...document.querySelectorAll('.skill-rail-row')].sort((a, b) => {
      const left = skillMarketData.find(item => item.name === a.dataset.selectSkill)?.growth ?? -Infinity;
      const right = skillMarketData.find(item => item.name === b.dataset.selectSkill)?.growth ?? -Infinity;
      return right - left;
    });
    reorderHomeRows('.top-skills-list', skillRows, '.skill-rail-rank');
  }

  document.querySelectorAll('.company-market-row').forEach(row => {
    const company = marketIntelligenceData.companies.find(item => item.name === row.dataset.selectMarketCompany);
    if (!company) return;
    const value = row.querySelector('.company-momentum-val');
    if (value) {
      value.classList.toggle('down', company.change < 0);
      setHomeLiveText(value, `${company.change > 0 ? '+' : ''}${company.change.toFixed(1)}%`);
    }
    const chart = row.querySelector('.company-sparkline-wrap svg');
    if (chart) updateMiniChart(chart, company.history, company.direction, 'market');
    const signal = row.querySelector('.company-signal-tag');
    if (signal) {
      signal.className = `company-signal-tag ${company.signalType}`;
      signal.textContent = company.signalType === 'decline' ? 'Cooling' : company.signalType === 'neutral' ? 'Steady' : company.signalText;
    }
  });
  const selectedCompanyName = intelligenceExplorerState.selected.companies || 'Microsoft';
  const selectedCompany = marketIntelligenceData.companies.find(company => company.name === selectedCompanyName);
  const marketBadge = document.querySelector('.market-analytical-surface .skill-badge-trend');
  if (marketBadge && selectedCompany) {
    const negative = selectedCompany.change < 0;
    marketBadge.classList.toggle('decline', negative);
    marketBadge.classList.toggle('positive', !negative);
    marketBadge.style.color = negative ? '#E05252' : '#198b62';
    marketBadge.style.background = negative ? 'rgba(224,82,82,.08)' : 'rgba(25,183,122,.08)';
    marketBadge.textContent = `${selectedCompany.change > 0 ? '+' : ''}${selectedCompany.change.toFixed(1)}% Signal Momentum`;
  }
  const companyRows = [...document.querySelectorAll('.company-market-row')].sort((a, b) => {
    const left = marketIntelligenceData.companies.find(item => item.name === a.dataset.selectMarketCompany)?.change ?? -Infinity;
    const right = marketIntelligenceData.companies.find(item => item.name === b.dataset.selectMarketCompany)?.change ?? -Infinity;
    return right - left;
  });
  reorderHomeRows('.company-market-list', companyRows);
  updateMarketChartInPlace();
  updateJobMetricsInPlace();
  updateOverviewCardMetrics();
}

function updateOverviewCardMetrics() {
  const cards = document.querySelectorAll('.overview-card-v2');
  const metrics = [overviewData.skill, overviewData.market, overviewData.jobs];
  cards.forEach((card, index) => {
    const metric = metrics[index];
    if (!metric) return;
    const key = index === 0 ? 'skill' : index === 1 ? 'market' : 'jobs';
    const value = card.querySelector(`[data-overview-value="${key}"]`);
    const chart = card.querySelector('.overview-mini-chart, .mini-bar-chart');
    const direction = metric.direction || (metric.change < 0 ? 'down' : 'up');
    const negative = direction === 'down';

    if (value) {
      const label = `${metric.change > 0 ? '+' : ''}${metric.change.toFixed(1)}%`;
      if (value.dataset.value !== label) setHomeLiveText(value, label);
      value.dataset.value = label;
      value.classList.toggle('is-negative', negative);
      value.classList.toggle('is-positive', !negative);
      const directionLabel = card.querySelector(`[data-overview-direction="${key}"]`);
      if (directionLabel) {
        directionLabel.classList.toggle('is-negative', negative);
        directionLabel.classList.toggle('is-positive', !negative);
        setHomeLiveText(directionLabel, negative ? '↓ Decreasing' : '↑ Increasing');
      }
    }

    const series = metric.chartPoints || metric.bars;
    if (chart && chart.tagName.toLowerCase() === 'svg') {
      updateMiniChart(chart, series, direction, 'skill');
      const area = chart.querySelector('polygon');
      if (area) area.setAttribute('fill', negative ? 'rgba(224,82,82,.11)' : 'rgba(25,183,122,.11)');
      const endpoint = chart.querySelector('.overview-market-endpoint');
      if (endpoint) {
        endpoint.setAttribute('cx', '140');
        endpoint.setAttribute('cy', String(32 - Math.max(0, Math.min(100, series.at(-1))) * .24));
        endpoint.setAttribute('fill', negative ? '#E05252' : '#19B77A');
      }
    } else if (chart && metric.bars) {
      chart.classList.toggle('is-negative', negative);
      chart.classList.toggle('is-positive', !negative);
      chart.querySelectorAll('.mini-bar-item').forEach((bar, barIndex) => { bar.style.height = `${metric.bars[barIndex]}%`; });
    }

    if (index === 2 && homeSimState.jobsOpenRoles !== null) {
      const title = card.querySelector('.overview-entity-name');
      if (title) setHomeLiveText(title, `${homeSimState.jobsOpenRoles.toLocaleString()} open roles`);
    }
  });

  const roadmapCard = document.querySelector('.overview-card-v2--roadmap');
  if (roadmapCard) {
    const active = ['active', 'paused'].includes(roadmapState.status);
    const progress = active ? (roadmapState.progress ?? overviewData.roadmap.progress) : 0;
    const title = roadmapCard.querySelector('.overview-entity-name');
    const step = roadmapCard.querySelector('[data-overview-value="roadmap-step"]');
    const value = roadmapCard.querySelector('[data-overview-value="roadmap"]');
    const track = roadmapCard.querySelector('[role="progressbar"]');
    const fill = roadmapCard.querySelector('.mini-progress-bar-fill');
    if (title) setHomeLiveText(title, active ? (roadmapState.title || (roadmapState.skill ? `${roadmapState.skill} — Development` : overviewData.roadmap.title)) : 'No Active Roadmap');
    if (step) setHomeLiveText(step, active ? (roadmapState.currentStep?.name || overviewData.roadmap.currentStep) : 'Choose a learning path');
    if (value) setHomeLiveText(value, `${progress}%`);
    if (track) track.setAttribute('aria-valuenow', String(progress));
    if (fill) fill.style.width = `${progress}%`;
  }
}
// END HOME LIVE SIMULATION ENGINE
// ============================================================

function renderHome() {
  stopHomeSimulation();
  applyExploreSelection();

  mainContent.innerHTML = `
    <div class="home-dashboard-v2">
      ${renderRedesignedPersonalContext()}
      ${renderRedesignedIntelligenceOverview()}
      ${renderRedesignedConsole()}
      ${renderRedesignedSkillIntelligence()}
      ${renderRedesignedMarketIntelligence()}
      ${renderRedesignedJobIntelligence()}
      ${renderRedesignedRoadmap()}
      ${intelligenceExplorerState.isRoadmapPreviewing ? renderRoadmapCreationModal() : ''}
    </div>
  `;

  lucide.createIcons();
  bindRedesignedHomeEvents();
}


function renderSavedPage() {
  const content = dashboardState.savedSkills.length ? dashboardState.savedSkills.map(skill => `<button class="saved-skill-item" data-skill="${skill}" type="button"><span><i data-lucide="bookmark-check"></i>${skill}</span><i data-lucide="arrow-up-right"></i></button>`).join('') : '<div class="empty-state"><i data-lucide="bookmark"></i><strong>No saved skills yet</strong><p>Save a skill from the Home overview to see it here.</p></div>';
  mainContent.innerHTML = `<div class="page-header"><span class="eyebrow">Workspace</span><h1>Saved Skills</h1><p>Your saved skills are shared with the Home market overview.</p></div><section class="saved-list dashboard-card">${content}</section>`;
  lucide.createIcons();
  document.querySelectorAll('.saved-skill-item').forEach(item => item.addEventListener('click', () => { dashboardState.selectedSkill = item.dataset.skill; window.location.hash = '/individual/home'; }));
}

function bindDashboardEvents() {
  const bindMenu = (buttonId, menuId, selector, updateState) => {
    const button = document.querySelector(buttonId);
    const menu = document.querySelector(menuId);
    if (!button || !menu) return;
    button.addEventListener('click', event => { event.stopPropagation(); const open = menu.hidden; document.querySelectorAll('.chart-filter-menu').forEach(item => { item.hidden = true; }); menu.hidden = !open; button.setAttribute('aria-expanded', String(!open)); });
    menu.querySelectorAll(selector).forEach(option => option.addEventListener('click', () => { updateState(option); renderHome(); }));
  };
  bindMenu('#timeFilterButton', '#timeFilterMenu', '[data-time-range]', option => { dashboardState.timeRange = option.dataset.timeRange; });
  bindMenu('#marketFilterButton', '#marketFilterMenu', '[data-market]', option => { dashboardState.market = option.dataset.market; });
  bindMenu('#scopeFilterButton', '#scopeFilterMenu', '[data-scope]', option => { dashboardState.skillScope = option.dataset.scope; });
  const addButton = document.querySelector('#addSkillButton');
  const addPanel = document.querySelector('#addSkillPanel');
  if (addButton && addPanel) addButton.addEventListener('click', () => { const isOpen = addPanel.hidden; addPanel.hidden = !isOpen; addButton.setAttribute('aria-expanded', String(isOpen)); });
  const confirmAddSkill = document.querySelector('#confirmAddSkill');
  if (confirmAddSkill) confirmAddSkill.addEventListener('click', () => {
    const selected = document.querySelector('#skillAddSelect').value;
    if (!selected || dashboardState.savedSkills.length >= 5) return;
    dashboardState.savedSkills = [...dashboardState.savedSkills, selected];
    dashboardState.selectedSkill = selected;
    localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    renderHome();
  });
}

function animateChart() { requestAnimationFrame(() => document.querySelectorAll('.chart-bar').forEach(bar => { bar.classList.add('is-animated'); })); }

function bindMiniChartTooltips() {
  const chart = document.querySelector('.saved-chart-bars');
  if (!chart) return;
  document.querySelectorAll('.mini-chart-tooltip').forEach(element => element.remove());
  const tooltip = document.createElement('div');
  tooltip.className = 'mini-chart-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  document.body.appendChild(tooltip);
  const showTooltip = bar => {
    tooltip.innerHTML = `<strong>${bar.dataset.skill}</strong><span>Skill Demand Index</span><b>${bar.dataset.value}</b><small>${bar.dataset.market}  —  Growing  —  ${bar.dataset.period}</small>`;
    const rect = bar.getBoundingClientRect();
    tooltip.style.left = `${Math.max(12, rect.left + rect.width / 2 - 74)}px`;
    tooltip.style.top = `${Math.max(12, rect.top - 101)}px`;
    tooltip.classList.add('is-visible');
  };
  const hideTooltip = () => tooltip.classList.remove('is-visible');
  chart.querySelectorAll('.saved-chart-bar').forEach(bar => {
    bar.addEventListener('mouseenter', () => showTooltip(bar));
    bar.addEventListener('focus', () => showTooltip(bar));
    bar.addEventListener('mouseleave', hideTooltip);
    bar.addEventListener('blur', hideTooltip);
  });
  chart.closest('.pulse-card').addEventListener('mouseleave', hideTooltip);
}

const dedicatedSkillState = {
  searchQuery: '',
  sortBy: 'health',
  filterBy: 'all',
  isAddingSkill: false,
  historyMetric: 'relevance',
  historyTimeRange: '6M',
  selectedEventId: null
};

const dedicatedSkillIntelligenceData = {
  overview: {
    overallHealth: 82,
    totalTracked: 12,
    growingCount: 8,
    attentionCount: 2,
    healthyCount: 10
  },
  skills: [
    {
      id: 'ml',
      name: 'Machine Learning',
      category: 'AI & Data',
      level: 'Advanced',
      health: 88,
      relevance: 94,
      halfLifeYears: 4.5,
      decayRisk: 'Low Risk',
      growth: 22.4,
      direction: 'up',
      status: 'healthy',
      lastUpdated: '2d ago',
      icon: 'cpu',
      history: [42, 50, 58, 66, 74, 80, 86],
      aiExplanation: 'Machine Learning demand is accelerating driven by generative model deployment and enterprise ML pipeline engineering. Your Python and SQL background provides strong foundational support.',
      missingSkills: ['CUDA Systems', 'PyTorch 2.0', 'Distributed Training'],
      adjacentSkills: ['Python', 'Deep Learning', 'PyTorch', 'CUDA'],
      requiredInRoles: ['AI Engineer', 'ML Operations Lead', 'Data Scientist'],
      gapSeverity: 'Moderate',
      techVelocity: 86,
      jobDemandCount: 42180,
      topLocations: ['Bangalore', 'San Francisco', 'Hyderabad'],
      evidence: [
        { type: 'Job Signal', text: '42,180 open role requisitions require ML capabilities in your location.' },
        { type: 'Market Report', text: 'Tech Talent Report 2026: ML Engineering is ranked #1 in talent scarcity.' },
        { type: 'Enterprise Hiring', text: 'Microsoft, NVIDIA, and Google increased ML requisitions by +28.4%.' }
      ]
    },
    {
      id: 'python',
      name: 'Python',
      category: 'Programming',
      level: 'Expert',
      health: 92,
      relevance: 96,
      halfLifeYears: 6.0,
      decayRisk: 'Very Low Risk',
      growth: 18.4,
      direction: 'up',
      status: 'healthy',
      lastUpdated: '1d ago',
      icon: 'code-2',
      history: [50, 58, 64, 72, 78, 85, 92],
      aiExplanation: 'Python remains the dominant language for AI, data science, and cloud backend engineering. High core stability with minimal replacement threat over the next 5+ years.',
      missingSkills: ['FastAPI Microservices', 'AsyncIO Deep Dive'],
      adjacentSkills: ['FastAPI', 'Django', 'SQL', 'Machine Learning'],
      requiredInRoles: ['Backend Engineer', 'AI Engineer', 'Data Engineer'],
      gapSeverity: 'Low',
      techVelocity: 90,
      jobDemandCount: 58400,
      topLocations: ['Bangalore', 'New York', 'London'],
      evidence: [
        { type: 'Job Signal', text: '58,400 open requisitions require Python backend proficiency.' },
        { type: 'Market Index', text: 'TIOBE & IEEE Spectrum Rank #1 programming language in 2026.' },
        { type: 'Skill Alignment', text: '96% direct match with your target role preferences.' }
      ]
    },
    {
      id: 'genai',
      name: 'Generative AI',
      category: 'AI & Data',
      level: 'Intermediate',
      health: 95,
      relevance: 98,
      halfLifeYears: 2.5,
      decayRisk: 'Rapid Evolution',
      growth: 34.2,
      direction: 'up',
      status: 'healthy',
      lastUpdated: '3d ago',
      icon: 'sparkles',
      history: [30, 42, 55, 68, 79, 88, 94],
      aiExplanation: 'Generative AI is the fastest growing skill category across enterprise technology. Rapid framework turnover requires continuous learning and hands-on project evidence.',
      missingSkills: ['LangChain / LlamaIndex', 'RAG Vector DBs', 'Fine-Tuning LoRA'],
      adjacentSkills: ['LLMs', 'Prompt Engineering', 'LangChain', 'RAG'],
      requiredInRoles: ['GenAI Engineer', 'AI Product Architect', 'ML Specialist'],
      gapSeverity: 'High Focus',
      techVelocity: 98,
      jobDemandCount: 31200,
      topLocations: ['San Francisco', 'Bangalore', 'Austin'],
      evidence: [
        { type: 'Job Signal', text: '31,200 open roles specifically request Generative AI stack competencies.' },
        { type: 'Venture Capital', text: '$14.2B venture capital invested in LLM applications in Q1 2026.' },
        { type: 'Market Demand', text: '+34.2% quarter-over-quarter surge in employer requisitions.' }
      ]
    },
    {
      id: 'cloud',
      name: 'Cloud Computing',
      category: 'Infrastructure',
      level: 'Advanced',
      health: 78,
      relevance: 82,
      halfLifeYears: 4.0,
      decayRisk: 'Moderate Risk',
      growth: 14.8,
      direction: 'up',
      status: 'healthy',
      lastUpdated: '5d ago',
      icon: 'cloud',
      history: [45, 52, 58, 64, 70, 74, 78],
      aiExplanation: 'Cloud infrastructure skills are steady and essential. Focus is shifting from basic cloud hosting to AI workload infrastructure and cloud security.',
      missingSkills: ['Kubernetes Operators', 'Terraform Modules'],
      adjacentSkills: ['AWS', 'Docker', 'Kubernetes', 'Terraform'],
      requiredInRoles: ['Cloud Architect', 'DevOps Lead', 'Backend Specialist'],
      gapSeverity: 'Low',
      techVelocity: 74,
      jobDemandCount: 38900,
      topLocations: ['Bangalore', 'Seattle', 'Berlin'],
      evidence: [
        { type: 'Job Signal', text: '38,900 cloud requisitions active across enterprise IT employers.' },
        { type: 'Cloud Growth', text: 'AWS & Azure cloud migration requisitions steady at +14.8%.' }
      ]
    },
    {
      id: 'react',
      name: 'React',
      category: 'Frontend',
      level: 'Advanced',
      health: 75,
      relevance: 78,
      halfLifeYears: 3.0,
      decayRisk: 'Moderate Risk',
      growth: 11.2,
      direction: 'up',
      status: 'healthy',
      lastUpdated: '4d ago',
      icon: 'layout',
      history: [52, 56, 60, 65, 69, 72, 75],
      aiExplanation: 'React remains the leading web application frontend library. Ecosystem is evolving toward Server Components (Next.js) and AI UI integration.',
      missingSkills: ['Next.js 15 App Router', 'Tailwind v4'],
      adjacentSkills: ['TypeScript', 'Next.js', 'Redux', 'Tailwind'],
      requiredInRoles: ['Frontend Engineer', 'Fullstack Developer'],
      gapSeverity: 'Low',
      techVelocity: 72,
      jobDemandCount: 28400,
      topLocations: ['Bangalore', 'New York', 'Toronto'],
      evidence: [
        { type: 'Job Signal', text: '28,400 active web application frontend requisitions.' }
      ]
    },
    {
      id: 'cyber',
      name: 'Legacy IT Security',
      category: 'Security',
      level: 'Intermediate',
      health: 54,
      relevance: 52,
      halfLifeYears: 1.8,
      decayRisk: 'High Decay Risk',
      growth: -3.5,
      direction: 'down',
      status: 'attention',
      lastUpdated: '7d ago',
      icon: 'shield-alert',
      history: [76, 75, 74, 73, 72, 71, 70],
      aiExplanation: 'Traditional perimeter security is being superseded by AI Threat Intelligence and Zero-Trust Cloud Security architectures. Upgrade to AI-Assisted Security recommended.',
      missingSkills: ['AI Threat Analysis', 'Cloud Zero Trust', 'Automated SIEM'],
      adjacentSkills: ['Cloud Security', 'Zero Trust', 'DevSecOps'],
      requiredInRoles: ['Security Operations Lead', 'Cybersecurity Specialist'],
      gapSeverity: 'Attention Needed',
      techVelocity: 42,
      jobDemandCount: 9800,
      topLocations: ['Washington DC', 'London', 'Bangalore'],
      evidence: [
        { type: 'Market Risk', text: 'Employer requisitions for legacy perimeter security declined by -3.5%.' },
        { type: 'Technology Shift', text: '84% of enterprises transitioning to Cloud Zero-Trust frameworks.' }
      ]
    }
  ]
};

function getFilteredAndSortedDedicatedSkills() {
  let list = [...dedicatedSkillIntelligenceData.skills];

  if (dedicatedSkillState.searchQuery.trim()) {
    const q = dedicatedSkillState.searchQuery.toLowerCase().trim();
    list = list.filter(s => s.name.toLowerCase().includes(q) || s.category.toLowerCase().includes(q));
  }

  if (dedicatedSkillState.filterBy === 'growing') {
    list = list.filter(s => s.direction === 'up' || s.growth > 0);
  } else if (dedicatedSkillState.filterBy === 'stable') {
    list = list.filter(s => s.growth === 0 || s.direction === 'stable');
  } else if (dedicatedSkillState.filterBy === 'declining') {
    list = list.filter(s => s.direction === 'down' || s.growth < 0);
  } else if (dedicatedSkillState.filterBy === 'attention') {
    list = list.filter(s => s.status === 'attention' || s.health < 65 || s.direction === 'down');
  }

  if (dedicatedSkillState.sortBy === 'health') {
    list.sort((a, b) => b.health - a.health);
  } else if (dedicatedSkillState.sortBy === 'relevance') {
    list.sort((a, b) => b.relevance - a.relevance);
  } else if (dedicatedSkillState.sortBy === 'growth') {
    list.sort((a, b) => b.growth - a.growth);
  } else if (dedicatedSkillState.sortBy === 'updated') {
    const getDays = str => parseInt(str) || 0;
    list.sort((a, b) => getDays(a.lastUpdated) - getDays(b.lastUpdated));
  }

  return list;
}

function renderSkillDecayChart(skillData, market, timeRange) {
  const currentRelevance = skillData.relevance || 84;
  const isDeclining = skillData.direction === 'down' || currentRelevance < 70;
  
  let baseMonths = 18;
  if (typeof skillData.halfLifeYears === 'number') {
    baseMonths = Math.round(skillData.halfLifeYears * 12);
  } else if (skillData.halfLifeYears) {
    baseMonths = parseInt(skillData.halfLifeYears, 10) * 12 || 18;
  }
  
  const marketMult = market === 'Global' ? 1.0 : market === 'India' ? 0.9 : market === 'Region' ? 1.1 : 0.85;
  const timeMult = timeRange === '30D' ? 1.0 : timeRange === '90D' ? 1.05 : timeRange === '6M' ? 1.1 : timeRange === '1Y' ? 1.25 : 1.0;
  
  const halfLifeMonths = Math.max(6, Math.min(60, Math.round(baseMonths * marketMult * timeMult)));
  const maxMonths = Math.max(36, halfLifeMonths + 12);

  const W = 620;
  const H = 210;
  const padL = 55;
  const padR = 35;
  const padT = 25;
  const padB = 40;
  
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const y50 = padT + chartH * 0.5;
  const yCurrent = padT + chartH * (1 - currentRelevance / 100);
  const xCurrent = padL;

  const xHL = padL + (halfLifeMonths / maxMonths) * chartW;
  const yHL = y50;

  const endRel = Math.max(10, Math.round(currentRelevance * 0.35));
  const xEnd = padL + chartW;
  const yEnd = padT + chartH * (1 - endRel / 100);

  const cp1x = xCurrent + (xHL - xCurrent) * 0.55;
  const cp1y = yCurrent + (yHL - yCurrent) * 0.15;
  
  const cp2x = xHL + (xEnd - xHL) * 0.45;
  const cp2y = yHL + (yEnd - yHL) * 0.85;

  const pathD = `M ${xCurrent.toFixed(1)},${yCurrent.toFixed(1)} C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${(xHL - 10).toFixed(1)},${(yHL - 5).toFixed(1)} ${xHL.toFixed(1)},${yHL.toFixed(1)} C ${(xHL + 15).toFixed(1)},${(yHL + 5).toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${xEnd.toFixed(1)},${yEnd.toFixed(1)}`;
  const areaD = `${pathD} L ${xEnd.toFixed(1)},${(padT + chartH).toFixed(1)} L ${xCurrent.toFixed(1)},${(padT + chartH).toFixed(1)} Z`;

  const ticks = [
    { label: 'Now (0M)', m: 0 },
    { label: '6M', m: 6 },
    { label: '12M', m: 12 },
    { label: `${halfLifeMonths}M (HL)`, m: halfLifeMonths, isHL: true },
    { label: `${maxMonths}M`, m: maxMonths }
  ].filter((t, idx, arr) => idx === 0 || idx === arr.length - 1 || Math.abs(t.m - halfLifeMonths) > 3 || t.isHL);

  return `
    <div class="decay-svg-wrapper">
      <svg viewBox="0 0 ${W} ${H}" class="decay-svg-element">
        <defs>
          <linearGradient id="decayAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${isDeclining ? '#EF4444' : '#B22DEF'}" stop-opacity="0.28"/>
            <stop offset="50%" stop-color="${isDeclining ? '#F59E0B' : '#B22DEF'}" stop-opacity="0.10"/>
            <stop offset="100%" stop-color="#42075D" stop-opacity="0.0"/>
          </linearGradient>
          <linearGradient id="decayStrokeGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="${isDeclining ? '#EF4444' : '#B22DEF'}"/>
            <stop offset="${(halfLifeMonths / maxMonths * 100).toFixed(0)}%" stop-color="${isDeclining ? '#F59E0B' : '#B22DEF'}"/>
            <stop offset="100%" stop-color="${isDeclining ? '#DC2626' : '#6366F1'}"/>
          </linearGradient>
        </defs>

        <g class="decay-grid-group">
          <line x1="${padL}" y1="${padT}" x2="${padL + chartW}" y2="${padT}" stroke="#E5E7EB" stroke-dasharray="3,3" />
          <text x="${padL - 10}" y="${padT + 4}" class="decay-axis-text" text-anchor="end">100%</text>

          <line x1="${padL}" y1="${padT + chartH * 0.25}" x2="${padL + chartW}" y2="${padT + chartH * 0.25}" stroke="#F3F4F6" stroke-dasharray="2,2" />
          <text x="${padL - 10}" y="${padT + chartH * 0.25 + 4}" class="decay-axis-text" text-anchor="end">75%</text>

          <line x1="${padL}" y1="${y50}" x2="${padL + chartW}" y2="${y50}" class="half-life-threshold-line" stroke="${isDeclining ? '#EF4444' : '#D97706'}" stroke-width="1.8" stroke-dasharray="5,4" />
          <text x="${padL - 10}" y="${y50 + 4}" class="decay-axis-text decay-axis-text--hl" text-anchor="end">50%</text>

          <line x1="${padL}" y1="${padT + chartH * 0.75}" x2="${padL + chartW}" y2="${padT + chartH * 0.75}" stroke="#F3F4F6" stroke-dasharray="2,2" />
          <text x="${padL - 10}" y="${padT + chartH * 0.75 + 4}" class="decay-axis-text" text-anchor="end">25%</text>

          <line x1="${padL}" y1="${padT + chartH}" x2="${padL + chartW}" y2="${padT + chartH}" stroke="#CBD5E1" stroke-width="1" />
          <text x="${padL - 10}" y="${padT + chartH + 4}" class="decay-axis-text" text-anchor="end">0%</text>
        </g>

        <rect x="${padL + chartW - 130}" y="${y50 - 12}" width="125" height="18" rx="4" fill="${isDeclining ? 'rgba(239,68,68,0.1)' : 'rgba(217,119,6,0.1)'}" stroke="${isDeclining ? '#EF4444' : '#D97706'}" stroke-width="0.8"/>
        <text x="${padL + chartW - 67.5}" y="${y50 + 1}" text-anchor="middle" font-size="10" font-weight="600" fill="${isDeclining ? '#EF4444' : '#D97706'}">50% Half-Life Threshold</text>

        <path d="${areaD}" fill="url(#decayAreaGrad)" />
        <path d="${pathD}" fill="none" stroke="url(#decayStrokeGrad)" stroke-width="3" class="decay-curve-path" />

        <g class="current-node-group">
          <circle cx="${xCurrent}" cy="${yCurrent}" r="7" fill="#B22DEF" stroke="#FFFFFF" stroke-width="2.5" />
          <rect x="${xCurrent - 35}" y="${yCurrent - 24}" width="70" height="18" rx="4" fill="#42075D" />
          <text x="${xCurrent}" y="${yCurrent - 12}" text-anchor="middle" font-size="10" font-weight="700" fill="#FFFFFF">Now: ${currentRelevance}%</text>
        </g>

        <g class="half-life-node-group">
          <circle cx="${xHL.toFixed(1)}" cy="${yHL.toFixed(1)}" r="12" class="half-life-pulse-ring" fill="none" stroke="${isDeclining ? '#EF4444' : '#D97706'}" stroke-width="1.5" opacity="0.6"/>
          <circle cx="${xHL.toFixed(1)}" cy="${yHL.toFixed(1)}" r="6" fill="${isDeclining ? '#EF4444' : '#D97706'}" stroke="#FFFFFF" stroke-width="2" />
          
          <g transform="translate(${Math.min(xHL, padL + chartW - 80)}, ${yHL + 20})">
            <rect x="-45" y="0" width="90" height="20" rx="4" fill="${isDeclining ? '#EF4444' : '#D97706'}" />
            <text x="0" y="13" text-anchor="middle" font-size="10" font-weight="700" fill="#FFFFFF">${halfLifeMonths}M @ 50% Rel.</text>
          </g>
        </g>

        <g class="decay-x-ticks">
          ${ticks.map(t => {
            const x = padL + (t.m / maxMonths) * chartW;
            return `
              <line x1="${x.toFixed(1)}" y1="${padT + chartH}" x2="${x.toFixed(1)}" y2="${padT + chartH + 5}" stroke="${t.isHL ? (isDeclining ? '#EF4444' : '#D97706') : '#94A3B8'}" stroke-width="${t.isHL ? '2' : '1'}" />
              <text x="${x.toFixed(1)}" y="${padT + chartH + 20}" text-anchor="middle" class="decay-x-text ${t.isHL ? 'decay-x-text--hl' : ''}" font-weight="${t.isHL ? '700' : '500'}" fill="${t.isHL ? (isDeclining ? '#EF4444' : '#D97706') : '#64748B'}">${t.label}</text>
            `;
          }).join('')}
        </g>
      </svg>
    </div>
  `;
}

function getHistoricalTrendPoints(skillData, metric, timeRange) {
  const skillName = skillData.name || 'Python';
  const isDeclining = skillData.direction === 'down';
  
  let dates = [];
  if (timeRange === '30D') {
    dates = ['Sep 01', 'Sep 08', 'Sep 15', 'Sep 22', 'Sep 26'];
  } else if (timeRange === '90D') {
    dates = ['Jul 01', 'Jul 15', 'Aug 01', 'Aug 15', 'Sep 01', 'Sep 15', 'Sep 26'];
  } else if (timeRange === '6M') {
    dates = ['Oct 2025', 'Nov 2025', 'Dec 2025', 'Jan 2026', 'Feb 2026', 'Mar 2026'];
  } else if (timeRange === '1Y') {
    dates = ['Apr 2025', 'May 2025', 'Jun 2025', 'Jul 2025', 'Aug 2025', 'Sep 2025', 'Oct 2025', 'Nov 2025', 'Dec 2025', 'Jan 2026', 'Feb 2026', 'Mar 2026'];
  } else {
    dates = ['Nov 2024', 'Jan 2025', 'Mar 2025', 'May 2025', 'Jul 2025', 'Sep 2025', 'Nov 2025', 'Jan 2026', 'Mar 2026'];
  }

  let currentVal = 84;
  let unit = '/ 100';
  let label = 'Skill Relevance';

  if (metric === 'health') {
    currentVal = skillData.health || 84;
    unit = '/ 100';
    label = 'Personal Skill Health';
  } else if (metric === 'relevance') {
    currentVal = skillData.relevance || 91;
    unit = '/ 100';
    label = 'Market Relevance';
  } else if (metric === 'demand') {
    currentVal = skillData.jobDemandCount || 42180;
    unit = ' job requisitions';
    label = 'Market Demand';
  }

  const pointsCount = dates.length;
  const values = [];
  const startVal = isDeclining ? Math.min(100, currentVal + (metric === 'demand' ? 8000 : 12)) : Math.max(20, currentVal - (metric === 'demand' ? 14000 : 18));
  
  for (let i = 0; i < pointsCount; i++) {
    const ratio = i / (pointsCount - 1);
    if (i === pointsCount - 1) {
      values.push(currentVal);
    } else {
      const noise = Math.sin(i * 1.4) * (metric === 'demand' ? 1200 : 2);
      values.push(Math.round(startVal + (currentVal - startVal) * ratio + noise));
    }
  }

  const events = [];
  const midIdx = Math.floor(dates.length * 0.55);
  const earlyIdx = Math.floor(dates.length * 0.25);

  if (skillName.toLowerCase().includes('python')) {
    events.push({
      id: 'ev-python-agentic',
      date: dates[midIdx],
      dateIdx: midIdx,
      title: 'Generative AI & Agentic Loop Adoption Surge',
      impactSummary: '+12.4% Surge',
      whatChanged: 'Enterprise adoption of LangChain, LlamaIndex, and Python agentic workflows grew 44% across tech hubs.',
      whyItMattered: 'Shifted core employer requisitions from legacy web scripting to AI pipeline engineering and autonomous agent design.',
      impact: '+12.4% market relevance surge & higher compensation tier.'
    });
    if (dates.length >= 6) {
      events.push({
        id: 'ev-python-fastapi',
        date: dates[earlyIdx],
        dateIdx: earlyIdx,
        title: 'AsyncIO & FastAPI Microservice Mandate',
        impactSummary: '+8.2% Health',
        whatChanged: 'Top engineering teams standardized on FastAPI and AsyncIO for high-concurrency microservice APIs.',
        whyItMattered: 'Elevated demand for asynchronous Python patterns and containerized API deployment skills.',
        impact: '+8.2% proficiency health score requirement.'
      });
    }
  } else if (skillName.toLowerCase().includes('machine') || skillName.toLowerCase().includes('data') || skillName.toLowerCase().includes('ai')) {
    events.push({
      id: 'ev-ml-rag',
      date: dates[midIdx],
      dateIdx: midIdx,
      title: 'RAG & Vector DB Standardisation',
      impactSummary: '+15.2% Demand',
      whatChanged: 'Production RAG architectures and embedding optimization became mandatory requirements in 72% of open AI postings.',
      whyItMattered: 'Transitioned classical ML engineering roles toward multi-modal retrieval and vector search stacks.',
      impact: '+15.2% active requisition expansion.'
    });
  } else {
    events.push({
      id: `ev-generic-${skillName.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
      date: dates[midIdx],
      dateIdx: midIdx,
      title: `${skillName} Industry Benchmark Refresh`,
      impactSummary: '+9.4% Growth',
      whatChanged: 'Updated tech competency frameworks elevated benchmark standards for production readiness.',
      whyItMattered: 'Employers introduced automated code & architecture verification into interview processes.',
      impact: '+9.4% demand & relevance score increase.'
    });
  }

  const firstVal = values[0];
  const lastVal = values[values.length - 1];
  const rawDiff = lastVal - firstVal;
  const pctChange = ((rawDiff / (firstVal || 1)) * 100).toFixed(1);
  const changePercent = `${rawDiff >= 0 ? '+' : ''}${pctChange}%`;
  const changeDirection = rawDiff >= 0 ? 'up' : 'down';
  const formattedCurrent = metric === 'demand' ? currentVal.toLocaleString() : currentVal;

  return {
    dates,
    values,
    events,
    label,
    unit,
    currentVal,
    formattedCurrent,
    changePercent,
    changeDirection
  };
}

function renderSkillHistoryChart(historyData, selectedEventId) {
  const W = 640;
  const H = 230;
  const padL = 55;
  const padR = 35;
  const padT = 35;
  const padB = 45;
  
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const maxVal = Math.max(...historyData.values) * 1.08;
  const minVal = Math.max(0, Math.min(...historyData.values) * 0.9);
  const valRange = (maxVal - minVal) || 1;

  const coords = historyData.values.map((val, idx) => {
    const x = padL + (idx / (historyData.values.length - 1)) * chartW;
    const y = padT + chartH - ((val - minVal) / valRange) * chartH;
    return { x, y, val, date: historyData.dates[idx], idx };
  });

  let pathD = `M ${coords[0].x.toFixed(1)},${coords[0].y.toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const curr = coords[i];
    const next = coords[i + 1];
    const cpx1 = curr.x + (next.x - curr.x) * 0.45;
    const cpy1 = curr.y;
    const cpx2 = curr.x + (next.x - curr.x) * 0.55;
    const cpy2 = next.y;
    pathD += ` C ${cpx1.toFixed(1)},${cpy1.toFixed(1)} ${cpx2.toFixed(1)},${cpy2.toFixed(1)} ${next.x.toFixed(1)},${next.y.toFixed(1)}`;
  }

  const areaD = `${pathD} L ${(padL + chartW).toFixed(1)},${(padT + chartH).toFixed(1)} L ${padL},${(padT + chartH).toFixed(1)} Z`;

  const gridTicks = [1.0, 0.75, 0.5, 0.25, 0.0].map(r => {
    const val = minVal + valRange * r;
    const y = padT + chartH * (1 - r);
    const label = historyData.unit.includes('requisitions') ? Math.round(val / 1000) + 'k' : Math.round(val);
    return { y, label };
  });

  return `
    <svg viewBox="0 0 ${W} ${H}" class="history-svg-element">
      <defs>
        <linearGradient id="historyAreaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#B22DEF" stop-opacity="0.32"/>
          <stop offset="60%" stop-color="#B22DEF" stop-opacity="0.08"/>
          <stop offset="100%" stop-color="#42075D" stop-opacity="0.0"/>
        </linearGradient>
        <linearGradient id="historyStrokeGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#6366F1"/>
          <stop offset="50%" stop-color="#B22DEF"/>
          <stop offset="100%" stop-color="#10B981"/>
        </linearGradient>
      </defs>

      <g class="history-grid-group">
        ${gridTicks.map(gt => `
          <line x1="${padL}" y1="${gt.y.toFixed(1)}" x2="${padL + chartW}" y2="${gt.y.toFixed(1)}" stroke="#F1F5F9" stroke-dasharray="3,3" />
          <text x="${padL - 10}" y="${(gt.y + 4).toFixed(1)}" class="decay-axis-text" text-anchor="end">${gt.label}</text>
        `).join('')}
      </g>

      <path d="${areaD}" fill="url(#historyAreaGrad)" />
      <path d="${pathD}" fill="none" stroke="url(#historyStrokeGrad)" stroke-width="3" class="history-line-path" />

      ${historyData.events.map(ev => {
        const pt = coords[ev.dateIdx];
        if (!pt) return '';
        const isSelected = selectedEventId === ev.id;
        return `
          <g class="history-event-pin ${isSelected ? 'is-selected' : ''}" data-history-event-id="${ev.id}">
            <line x1="${pt.x.toFixed(1)}" y1="${pt.y.toFixed(1)}" x2="${pt.x.toFixed(1)}" y2="${padT + chartH}" stroke="${isSelected ? 'var(--b-primary)' : '#94A3B8'}" stroke-dasharray="2,2" stroke-width="${isSelected ? '1.8' : '1'}" />
            <g transform="translate(${pt.x.toFixed(1)}, ${Math.max(padT + 12, pt.y - 20)})">
              <rect x="-32" y="-10" width="64" height="20" rx="6" class="event-pin-rect" />
              <text x="0" y="3" text-anchor="middle" class="event-pin-text">✦ Event</text>
            </g>
          </g>
        `;
      }).join('')}

      <g class="history-nodes-group">
        ${coords.map(pt => `
          <g class="history-node-item">
            <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="5.5" class="history-node" />
            <title>${pt.date} | ${historyData.label}: ${historyData.unit.includes('requisitions') ? pt.val.toLocaleString() : pt.val}</title>
          </g>
        `).join('')}
      </g>

      <g class="history-x-ticks">
        ${coords.map(pt => `
          <line x1="${pt.x.toFixed(1)}" y1="${padT + chartH}" x2="${pt.x.toFixed(1)}" y2="${padT + chartH + 5}" stroke="#CBD5E1" />
          <text x="${pt.x.toFixed(1)}" y="${padT + chartH + 20}" text-anchor="middle" class="decay-x-text">${pt.date}</text>
        `).join('')}
      </g>
    </svg>
  `;
}

function renderMarketDemandLocationChart(skillData, market, timeRange) {
  const currentDemand = skillData.jobDemandCount || 42180;
  
  const marketMult = market === 'Global' ? 1.0 : market === 'India' ? 0.85 : market === 'Tamil Nadu' ? 0.65 : market === 'Bangalore' ? 0.78 : market === 'Chennai' ? 0.60 : 0.75;
  const timeMult = timeRange === '30D' ? 1.0 : timeRange === '90D' ? 1.05 : timeRange === '6M' ? 1.1 : timeRange === '1Y' ? 1.25 : 1.0;
  
  const baseDemand = Math.round(currentDemand * marketMult * timeMult);
  const isDeclining = skillData.direction === 'down';

  let dates = [];
  if (timeRange === '30D') dates = ['W1', 'W2', 'W3', 'W4', 'Now'];
  else if (timeRange === '90D') dates = ['Jul', 'Aug 01', 'Aug 15', 'Sep 01', 'Sep 15', 'Sep 26'];
  else if (timeRange === '6M') dates = ['Oct 25', 'Nov 25', 'Dec 25', 'Jan 26', 'Feb 26', 'Mar 26'];
  else if (timeRange === '1Y') dates = ['Apr', 'Jun', 'Aug', 'Oct', 'Dec', 'Feb', 'Mar'];
  else dates = ['2024 H2', '2025 Q1', '2025 Q2', '2025 Q3', '2025 Q4', '2026 Q1'];

  const pointsCount = dates.length;
  const values = [];
  const startVal = isDeclining ? Math.min(80000, baseDemand * 1.2) : Math.max(5000, baseDemand * 0.72);
  
  for (let i = 0; i < pointsCount; i++) {
    const ratio = i / (pointsCount - 1);
    if (i === pointsCount - 1) {
      values.push(baseDemand);
    } else {
      const noise = Math.sin(i * 1.3) * (baseDemand * 0.04);
      values.push(Math.round(startVal + (baseDemand - startVal) * ratio + noise));
    }
  }

  const W = 620;
  const H = 200;
  const padL = 55;
  const padR = 35;
  const padT = 25;
  const padB = 40;
  
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const maxVal = Math.max(...values) * 1.1;
  const minVal = Math.max(0, Math.min(...values) * 0.85);
  const valRange = (maxVal - minVal) || 1;

  const coords = values.map((val, idx) => {
    const x = padL + (idx / (values.length - 1)) * chartW;
    const y = padT + chartH - ((val - minVal) / valRange) * chartH;
    return { x, y, val, date: dates[idx] };
  });

  let pathD = `M ${coords[0].x.toFixed(1)},${coords[0].y.toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const curr = coords[i];
    const next = coords[i + 1];
    const cpx1 = curr.x + (next.x - curr.x) * 0.45;
    const cpy1 = curr.y;
    const cpx2 = curr.x + (next.x - curr.x) * 0.55;
    const cpy2 = next.y;
    pathD += ` C ${cpx1.toFixed(1)},${cpy1.toFixed(1)} ${cpx2.toFixed(1)},${cpy2.toFixed(1)} ${next.x.toFixed(1)},${next.y.toFixed(1)}`;
  }

  const areaD = `${pathD} L ${(padL + chartW).toFixed(1)},${(padT + chartH).toFixed(1)} L ${padL},${(padT + chartH).toFixed(1)} Z`;

  const gridTicks = [1.0, 0.5, 0.0].map(r => {
    const val = minVal + valRange * r;
    const y = padT + chartH * (1 - r);
    return { y, label: Math.round(val / 1000) + 'k' };
  });

  return `
    <svg viewBox="0 0 ${W} ${H}" class="history-svg-element">
      <defs>
        <linearGradient id="marketDemandGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#10B981" stop-opacity="0.30"/>
          <stop offset="100%" stop-color="#10B981" stop-opacity="0.0"/>
        </linearGradient>
      </defs>

      <g class="history-grid-group">
        ${gridTicks.map(gt => `
          <line x1="${padL}" y1="${gt.y.toFixed(1)}" x2="${padL + chartW}" y2="${gt.y.toFixed(1)}" stroke="#F1F5F9" stroke-dasharray="3,3" />
          <text x="${padL - 10}" y="${(gt.y + 4).toFixed(1)}" class="decay-axis-text" text-anchor="end">${gt.label}</text>
        `).join('')}
      </g>

      <path d="${areaD}" fill="url(#marketDemandGrad)" />
      <path d="${pathD}" fill="none" stroke="#10B981" stroke-width="2.5" class="history-line-path" />

      <g class="history-nodes-group">
        ${coords.map(pt => `
          <g class="history-node-item">
            <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="4.5" fill="#FFFFFF" stroke="#10B981" stroke-width="2" />
            <title>${pt.date} | ${market}: ${pt.val.toLocaleString()} requisitions</title>
          </g>
        `).join('')}
      </g>

      <g class="history-x-ticks">
        ${coords.map(pt => `
          <line x1="${pt.x.toFixed(1)}" y1="${padT + chartH}" x2="${pt.x.toFixed(1)}" y2="${padT + chartH + 4}" stroke="#CBD5E1" />
          <text x="${pt.x.toFixed(1)}" y="${padT + chartH + 18}" text-anchor="middle" class="decay-x-text">${pt.date}</text>
        `).join('')}
      </g>
    </svg>
  `;
}

function renderMultiNodeSkillChart(points) {
  const dates = ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'];
  const maxVal = Math.max(...points, 100);
  const minVal = Math.min(...points, 0);
  const range = (maxVal - minVal) || 1;

  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * 520;
    const y = 140 - ((val - minVal) / range) * 100;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const polyPoints = `0,160 ${coords} 520,160`;

  return `
    <div style="position:relative; width:100%;">
      <svg viewBox="0 0 520 160" style="width:100%; height:140px; overflow:visible;" preserveAspectRatio="none">
        <defs>
          <linearGradient id="skillDetailGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#B22DEF" stop-opacity="0.25"/>
            <stop offset="100%" stop-color="#B22DEF" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        <polygon points="${polyPoints}" fill="url(#skillDetailGrad)" />
        <polyline points="${coords}" fill="none" stroke="#B22DEF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        ${points.map((val, idx) => {
          const x = ((idx / (points.length - 1)) * 520).toFixed(1);
          const y = (140 - ((val - minVal) / range) * 100).toFixed(1);
          return `<circle cx="${x}" cy="${y}" r="4.5" fill="#42075D" stroke="#FFFFFF" stroke-width="2" />`;
        }).join('')}
      </svg>
      <div style="display:flex; justify-content:space-between; margin-top:8px; font-size:11px; color:#7A7085; font-weight:600;">
        ${dates.map((d, i) => `<span>${d} (${points[i]})</span>`).join('')}
      </div>
    </div>
  `;
}

function getSkillIntelligenceOverview(location = dashboardState.market, timeRange = dashboardState.timeRange) {
  let baseHealth = 82;
  let growingCount = 8;
  let attentionCount = 2;
  let totalTracked = dedicatedSkillIntelligenceData.skills.length;
  let primaryCount = 5;
  let secondaryCount = totalTracked - primaryCount;
  let avgGrowth = 18.4;

  if (location === 'India' || location === 'Bangalore, India') {
    baseHealth += 1;
    avgGrowth += 1.2;
  } else if (location === 'United States' || location === 'San Francisco, US') {
    baseHealth += 2;
    avgGrowth += 2.5;
  } else if (location === 'Germany' || location === 'Europe') {
    baseHealth -= 1;
    avgGrowth -= 0.8;
  } else if (location === 'Singapore') {
    baseHealth += 1;
    avgGrowth += 1.0;
  }

  if (timeRange === '7 Days' || timeRange === '30D' || timeRange === '30 Days') {
    avgGrowth += 1.5;
  } else if (timeRange === '1 Year' || timeRange === '1Y') {
    avgGrowth -= 1.2;
    attentionCount += 1;
  }

  const overallHealth = Math.min(100, Math.max(0, baseHealth));
  const healthStatus = overallHealth >= 80 ? 'Healthy' : overallHealth >= 65 ? 'Moderate' : 'Needs Focus';

  return {
    overallHealth,
    healthStatus,
    totalTracked,
    primaryCount,
    secondaryCount,
    growingCount,
    attentionCount,
    healthyCount: totalTracked - attentionCount,
    avgGrowth: Number(avgGrowth.toFixed(1))
  };
}

function getSkillGapDetails(selectedSkillData) {
  const targetRole = (selectedSkillData.requiredInRoles && selectedSkillData.requiredInRoles[0]) || 'AI & Backend Specialist';
  
  const missing1 = (selectedSkillData.missingSkills && selectedSkillData.missingSkills[0]) || `Advanced ${selectedSkillData.name}`;
  const missing2 = (selectedSkillData.missingSkills && selectedSkillData.missingSkills[1]) || 'System Architecture';
  const adjacent1 = (selectedSkillData.adjacentSkills && selectedSkillData.adjacentSkills[0]) || 'SQL';

  const gapItems = [
    {
      name: selectedSkillData.name,
      matchType: 'Strong Match',
      matchBadgeClass: 'strong',
      currentLevel: selectedSkillData.level || 'Advanced',
      requiredLevel: 'Advanced',
      gapMagnitude: '0 Levels (Met)',
      priority: 'Low',
      priorityClass: 'low',
      why: `Your verified proficiency in ${selectedSkillData.name} satisfies core baseline criteria for target ${targetRole} positions.`
    },
    {
      name: adjacent1,
      matchType: 'Partial Match',
      matchBadgeClass: 'partial',
      currentLevel: 'Intermediate',
      requiredLevel: 'Advanced',
      gapMagnitude: '1 Level Gap',
      priority: 'Medium',
      priorityClass: 'medium',
      why: `Essential complementary proficiency for linking ${selectedSkillData.name} services with high-throughput production data pipelines.`
    },
    {
      name: missing1,
      matchType: 'Skill Gap',
      matchBadgeClass: 'gap',
      currentLevel: 'Beginner / None',
      requiredLevel: 'Intermediate',
      gapMagnitude: '2 Levels Gap',
      priority: 'High',
      priorityClass: 'high',
      why: `Appears frequently in selected ${targetRole} job requisitions for building resilient enterprise applications.`
    },
    {
      name: missing2,
      matchType: 'Skill Gap',
      matchBadgeClass: 'gap',
      currentLevel: 'None',
      requiredLevel: 'Advanced',
      gapMagnitude: '2 Levels Gap',
      priority: selectedSkillData.gapSeverity?.includes('High') ? 'High' : 'Medium',
      priorityClass: selectedSkillData.gapSeverity?.includes('High') ? 'high' : 'medium',
      why: `Critical requirement for technical leadership evaluation and high-complexity project architecture.`
    }
  ];

  return { targetRole, gapItems };
}

function getAIExplanationAndEvidence(selectedSkillData, market, timeRange) {
  const skillName = selectedSkillData.name;
  
  const whyMatters = `${skillName} remains highly relevant in ${market} (${timeRange}) because it continues to appear across backend engineering, data systems, and emerging AI workloads.`;
  
  const keySignals = [
    { label: 'Job Demand', desc: `${(selectedSkillData.jobDemandCount || 24000).toLocaleString()} open role requisitions` },
    { label: 'Technology Momentum', desc: `+${selectedSkillData.growth}% velocity growth` },
    { label: 'Industry Demand', desc: 'High adoption across SaaS, Fintech & AI' },
    { label: 'User Skill Profile', desc: `Verified ${selectedSkillData.level || 'Intermediate'} level` }
  ];

  const whatChanged = `Over the past ${timeRange}, enterprise requisitions requesting ${skillName} integrated with cloud-native pipelines and modern frameworks increased by +${selectedSkillData.growth}%. Standard frameworks continue to evolve with tighter AI tooling support.`;

  const whatCouldHappenNext = `Based on current signals and technology adoption trends, ${skillName} relevance is projected to remain strong over the next ${selectedSkillData.halfLifeYears ? selectedSkillData.halfLifeYears + ' years' : '18-24 months'}. Current forecast suggests steady demand unless disrupted by new domain-specific runtime shifts.`;

  const evidenceList = selectedSkillData.evidence || [
    {
      type: 'Job Market Signal',
      typeBadgeClass: 'job',
      title: `Active Hiring Demand for ${skillName}`,
      date: 'Updated 2d ago',
      explanation: `Over ${(selectedSkillData.jobDemandCount || 24000).toLocaleString()} open requisitions in ${market} list ${skillName} as a required competency.`
    },
    {
      type: 'Technology Signal',
      typeBadgeClass: 'tech',
      title: `${skillName} Ecosystem Velocity`,
      date: 'Updated 1w ago',
      explanation: `Technology adoption velocity scored ${selectedSkillData.techVelocity || 84}/100 based on open-source momentum and framework updates.`
    },
    {
      type: 'Industry Report',
      typeBadgeClass: 'industry',
      title: 'Global Workforce Skills Survey 2026',
      date: 'Q1 2026 Report',
      explanation: `Enterprise engineering leads rank ${skillName} among top 5 essential technical competencies for modern software architecture.`
    },
    {
      type: 'Company / Role Signal',
      typeBadgeClass: 'company',
      title: `Top Employer Requisitions in ${market}`,
      date: 'Real-time Signal',
      explanation: `Leading technology employers in ${market} increased ${skillName} job postings by +${selectedSkillData.growth}%.`
    }
  ];

  return { whyMatters, keySignals, whatChanged, whatCouldHappenNext, evidenceList };
}

function getSkillNextActionRecommendation(selectedSkillData) {
  const health = selectedSkillData.health || 80;
  const relevance = selectedSkillData.relevance || 80;
  const skillName = selectedSkillData.name;
  const targetRole = (selectedSkillData.requiredInRoles && selectedSkillData.requiredInRoles[0]) || 'AI & Software Engineer';

  const isGap = selectedSkillData.status === 'declining' || (selectedSkillData.missingSkills && selectedSkillData.missingSkills.includes(skillName));
  const isHealthy = health >= 80;
  const isHighRelevance = relevance >= 85;

  let stateType = '';
  let primaryActionTitle = '';
  let rationale = '';
  let suggestedPills = [];

  if (isGap) {
    stateType = 'SKILL GAP';
    primaryActionTitle = `Build targeted ${skillName} roadmap to bridge identified gap`;
    rationale = `${skillName} is a high-priority skill gap required for target ${targetRole} positions. Creating a structured roadmap will accelerate competency build-up.`;
    suggestedPills = ['Build Targeted Roadmap', 'Explore Skill Gap Matrix', 'View Target Role Requisitions'];
  } else if (isHealthy && isHighRelevance) {
    stateType = 'HEALTHY + HIGH RELEVANCE';
    primaryActionTitle = `Strengthen advanced ${skillName} capabilities & project evidence`;
    rationale = `Your ${skillName} proficiency is strong and in high demand for ${targetRole} roles. Focus on advanced specialization, production project evidence, and tracking market shifts.`;
    suggestedPills = ['Explore Advanced Topics', 'Take Practice Assessment', 'Track Regional Demand'];
  } else if (isHealthy && !isHighRelevance) {
    stateType = 'HEALTHY + DECLINING RELEVANCE';
    primaryActionTitle = `Refresh ${skillName} & learn emerging adjacent frameworks`;
    rationale = `While your ${skillName} health remains high, market signals project shifting requirements. We recommend acquiring adjacent frameworks like ${selectedSkillData.adjacentSkills ? selectedSkillData.adjacentSkills[0] : 'FastAPI'}.`;
    suggestedPills = ['Refresh Framework Skills', 'Learn Emerging Adjacent Tech', 'View Adjacent Skills'];
  } else if (!isHealthy && isHighRelevance) {
    stateType = 'LOW HEALTH + HIGH RELEVANCE';
    primaryActionTitle = `Improve ${skillName} health & complete proficiency assessment`;
    rationale = `Market demand for ${skillName} is high in ${dashboardState.market || 'your region'}, but your current activity index indicates a health gap. Dedicated practice and assessment are recommended.`;
    suggestedPills = ['Take Skill Assessment', 'Practice Exercises', 'Build Practice Roadmap'];
  } else {
    stateType = 'LOW HEALTH + LOW RELEVANCE';
    primaryActionTitle = `Explore high-growth adjacent skills & career transition paths`;
    rationale = `Both skill health and market relevance are lower for ${skillName}. Transitioning your focus to higher-growth adjacent skills like ${selectedSkillData.adjacentSkills ? selectedSkillData.adjacentSkills.join(', ') : 'Generative AI'} offers higher ROI.`;
    suggestedPills = ['Explore Adjacent Skills', 'Explore Career Opportunities', 'Assess Transition Roadmap'];
  }

  return { stateType, primaryActionTitle, rationale, suggestedPills };
}

async function renderDedicatedJobPage() {
  try {
    const module = await import('../pages/individual/career/Career.js');
    if (typeof module.renderDedicatedJobPage === 'function') {
      return module.renderDedicatedJobPage();
    } else if (typeof module.renderCareerPage === 'function') {
      return module.renderCareerPage();
    }
  } catch (error) {
    console.warn('Job intelligence module failed to load, falling back to placeholder.', error);
  }
}

async function renderDedicatedMarketPage() {
  try {
    const module = await import('../pages/individual/market/MarketIntelligence.js');
    if (typeof module.renderDedicatedMarketPage === 'function') {
      return module.renderDedicatedMarketPage();
    }
  } catch (error) {
    console.warn('Market intelligence module failed to load, falling back to placeholder.', error);
  }
}

async function renderDedicatedSkillsPage() {
  try {
    const module = await import('../pages/individual/skills/SkillIntelligence.js');
    if (typeof module.renderDedicatedSkillsPage === 'function') {
      return module.renderDedicatedSkillsPage();
    }
  } catch (error) {
    console.warn('Skill intelligence module failed to load, falling back to legacy renderer.', error);
  }

  const selectedName = dashboardState.selectedSkill || 'Machine Learning';
  let selectedSkillData = dedicatedSkillIntelligenceData.skills.find(s => s.name.toLowerCase() === selectedName.toLowerCase());
  if (!selectedSkillData) {
    selectedSkillData = {
      id: 'custom',
      name: selectedName,
      category: 'General Capability',
      level: 'Advanced',
      health: 84,
      relevance: 88,
      halfLifeYears: 3.5,
      decayRisk: 'Moderate Risk',
      growth: 15.2,
      direction: 'up',
      status: 'healthy',
      history: [48, 55, 62, 70, 76, 81, 86],
      aiExplanation: `${selectedName} is showing positive market momentum with steady employer demand across major technology hubs.`,
      missingSkills: [`Advanced ${selectedName}`, 'System Design'],
      adjacentSkills: ['Python', 'Cloud Computing', 'SQL'],
      requiredInRoles: ['Senior Specialist', 'Engineering Lead'],
      gapSeverity: 'Low',
      techVelocity: 78,
      jobDemandCount: 18400,
      topLocations: [dashboardState.market || 'Global'],
      evidence: [{ type: 'Job Signal', text: `18,400 open role requisitions require ${selectedName}.` }]
    };
  }

  const overviewData = getSkillIntelligenceOverview(dashboardState.market, dashboardState.timeRange);
  const filteredSkills = getFilteredAndSortedDedicatedSkills();

  const historyData = getHistoricalTrendPoints(selectedSkillData, dedicatedSkillState.historyMetric, dedicatedSkillState.historyTimeRange);
  let selectedEvent = historyData.events.find(e => e.id === dedicatedSkillState.selectedEventId);
  if (!selectedEvent && historyData.events.length > 0 && dedicatedSkillState.selectedEventId) {
    selectedEvent = historyData.events[0];
  }

  const gapData = getSkillGapDetails(selectedSkillData);
  const aiInsightData = getAIExplanationAndEvidence(selectedSkillData, dashboardState.market, dashboardState.timeRange);
  const nextActionData = getSkillNextActionRecommendation(selectedSkillData);

  mainContent.innerHTML = `
    <div class="dedicated-skill-page">
      <!-- 1. PAGE HEADER -->
      <header class="dedicated-header">
        <div class="dedicated-header__left">
          <span class="v2-kicker">MY SKILLS</span>
          <h1>Skill Intelligence</h1>
          <p>Understand the health, relevance, and future direction of your skills.</p>
        </div>

        <div class="dedicated-header__controls">
          <div class="console-control-group">
            <label>Location:</label>
            <select class="console-select" id="dedicatedSkillMarketSelect">
              ${marketOptions.map(m => `<option ${m === dashboardState.market ? 'selected' : ''}>${m}</option>`).join('')}
            </select>
          </div>
          <div class="console-control-group">
            <label>Time Range:</label>
            <select class="console-select" id="dedicatedSkillTimeSelect">
              ${timeRangeOptions.map(t => `<option ${t === dashboardState.timeRange ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </div>
          <span class="overview-health-status-badge positive" style="margin-left:4px;">
            <i data-lucide="shield-check"></i> Overall Health: ${overviewData.overallHealth}/100
          </span>
        </div>
      </header>

      <!-- 2. STICKY SUB-NAVIGATION BAR -->
      <nav class="sticky-skill-subnav" id="skillSubnav">
        <div class="subnav-container">
          <a href="#section-overview" class="subnav-link is-active" data-subnav-target="section-overview">Overview</a>
          <a href="#section-explorer" class="subnav-link" data-subnav-target="section-explorer">My skills</a>
          <a href="#section-health-relevance" class="subnav-link" data-subnav-target="section-health-relevance">Health & relevance</a>
          <a href="#section-outlook" class="subnav-link" data-subnav-target="section-outlook">Future outlook</a>
          <a href="#section-history" class="subnav-link" data-subnav-target="section-history">Skill history</a>
          <a href="#section-market" class="subnav-link" data-subnav-target="section-market">Market context</a>
          <a href="#section-gap" class="subnav-link" data-subnav-target="section-gap">Skill gap</a>
          <a href="#section-ai-insight" class="subnav-link" data-subnav-target="section-ai-insight">AI insight</a>
          <a href="#section-next-action" class="subnav-link" data-subnav-target="section-next-action">Next action</a>
        </div>
      </nav>

      <!-- 3. UNIFIED HORIZONTAL METRIC STRIP -->
      <section id="section-overview" data-skill-section="overview">
        <div class="skill-overview-strip">
          <div class="strip-item">
            <span class="strip-icon-box"><i data-lucide="shield-check"></i></span>
            <div class="strip-metric-meta">
              <span class="strip-metric-label">Overall Skill Health</span>
              <strong class="strip-metric-val">${overviewData.overallHealth} <span class="denom">/ 100</span></strong>
              <span class="strip-sub-text">${overviewData.healthyCount} healthy · ${overviewData.attentionCount} attention</span>
            </div>
          </div>

          <div class="strip-divider"></div>

          <div class="strip-item">
            <span class="strip-icon-box" style="background:#EEF2FF; color:#4F46E5;"><i data-lucide="layers"></i></span>
            <div class="strip-metric-meta">
              <span class="strip-metric-label">Skills Tracked</span>
              <strong class="strip-metric-val">${overviewData.totalTracked} <span class="unit">skills</span></strong>
              <span class="strip-sub-text">${overviewData.primaryCount} primary · ${overviewData.secondaryCount} secondary</span>
            </div>
          </div>

          <div class="strip-divider"></div>

          <div class="strip-item">
            <span class="strip-icon-box" style="background:#ECFDF5; color:#10B981;"><i data-lucide="trending-up"></i></span>
            <div class="strip-metric-meta">
              <span class="strip-metric-label">Growing Skills</span>
              <strong class="strip-metric-val" style="color:#10B981;">+${overviewData.avgGrowth}%</strong>
              <span class="strip-sub-text">${overviewData.growingCount} skills accelerating</span>
            </div>
          </div>

          <div class="strip-divider"></div>

          <div class="strip-item">
            <span class="strip-icon-box" style="background:#FEF2F2; color:#EF4444;"><i data-lucide="alert-triangle"></i></span>
            <div class="strip-metric-meta">
              <span class="strip-metric-label">Needing Attention</span>
              <strong class="strip-metric-val" style="color:#EF4444;">${overviewData.attentionCount} <span class="unit">skills</span></strong>
              <span class="strip-sub-text">Declining or decay risk</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. WORKSPACE GRID: SKILL EXPLORER (4 COLS) + SELECTED SKILL WORKSPACE (8 COLS) -->
      <section id="section-explorer" data-skill-section="explorer" style="margin-top:24px;">
        <div class="dedicated-workspace-grid">

          <!-- LEFT COLUMN: SKILL EXPLORER -->
          <aside class="current-skills-rail primary-intel-panel" id="current-skills-section">
            <div class="rail-header-v3">
              <div class="rail-header-title-block">
                <span class="v2-kicker">MY PORTFOLIO</span>
                <h3>Current skills</h3>
                <p class="rail-subtitle">Track your capabilities and observe value velocity.</p>
              </div>
              <button type="button" class="add-skill-btn-v3" id="openAddSkillModalBtn">
                <i data-lucide="plus"></i> Add skill
              </button>
            </div>

            <!-- SEARCH & SORT -->
            <div class="skill-search-sort-bar">
              <div class="skill-search-input-wrap">
                <i data-lucide="search" class="search-icon"></i>
                <input type="text" class="skill-search-input" id="currentSkillSearchInput" placeholder="Search skills..." value="${dedicatedSkillState.searchQuery}">
                ${dedicatedSkillState.searchQuery ? `<button type="button" class="clear-search-btn" id="clearSkillSearchBtn"><i data-lucide="x"></i></button>` : ''}
              </div>

              <div class="skill-sort-wrap">
                <label for="currentSkillSortSelect">Sort:</label>
                <select class="console-select-sm" id="currentSkillSortSelect">
                  <option value="health" ${dedicatedSkillState.sortBy === 'health' ? 'selected' : ''}>Skill health</option>
                  <option value="relevance" ${dedicatedSkillState.sortBy === 'relevance' ? 'selected' : ''}>Relevance</option>
                  <option value="growth" ${dedicatedSkillState.sortBy === 'growth' ? 'selected' : ''}>Growth</option>
                  <option value="updated" ${dedicatedSkillState.sortBy === 'updated' ? 'selected' : ''}>Recently updated</option>
                </select>
              </div>
            </div>

            <!-- FILTER TABS -->
            <div class="skill-filter-pills-row">
              <button type="button" class="filter-pill ${dedicatedSkillState.filterBy === 'all' ? 'is-active' : ''}" data-skill-filter="all">
                All <span class="pill-count">${dedicatedSkillIntelligenceData.skills.length}</span>
              </button>
              <button type="button" class="filter-pill ${dedicatedSkillState.filterBy === 'growing' ? 'is-active' : ''}" data-skill-filter="growing">
                <i data-lucide="trending-up"></i> Growing
              </button>
              <button type="button" class="filter-pill ${dedicatedSkillState.filterBy === 'stable' ? 'is-active' : ''}" data-skill-filter="stable">
                <i data-lucide="minus"></i> Stable
              </button>
              <button type="button" class="filter-pill ${dedicatedSkillState.filterBy === 'declining' ? 'is-active' : ''}" data-skill-filter="declining">
                <i data-lucide="trending-down"></i> Declining
              </button>
              <button type="button" class="filter-pill ${dedicatedSkillState.filterBy === 'attention' ? 'is-active' : ''}" data-skill-filter="attention">
                <i data-lucide="alert-triangle"></i> Attention
              </button>
            </div>

            <!-- COMPACT SKILL LIST -->
            <div class="rail-skill-list-v3">
              ${filteredSkills.length === 0 ? `
                <div class="skills-empty-search">
                  <i data-lucide="search-x"></i>
                  <strong>No skills match your filter</strong>
                  <p>Try adjusting your search or filter options.</p>
                  <button type="button" class="button button--secondary" id="resetSkillFiltersBtn">Reset filters</button>
                </div>
              ` : filteredSkills.map(skill => {
                const isSelected = skill.name.toLowerCase() === selectedSkillData.name.toLowerCase();
                const isDecline = skill.direction === 'down';
                const isStable = skill.growth === 0 || skill.direction === 'stable';
                const trendLabel = isDecline ? '↓ Declining' : isStable ? '→ Stable' : '↑ Growing';
                const trendClass = isDecline ? 'declining' : isStable ? 'stable' : 'growing';
                const healthColor = skill.health >= 80 ? '#10B981' : skill.health >= 65 ? '#F59E0B' : '#EF4444';

                return `
                  <article class="compact-skill-row ${isSelected ? 'is-selected' : ''}" data-select-dedicated-skill="${skill.name}">
                    <div class="compact-skill-identity">
                      <span class="compact-icon-badge"><i data-lucide="${skill.icon || 'cpu'}"></i></span>
                      <div class="compact-name-block">
                        <strong class="compact-name">${skill.name}</strong>
                        <span class="compact-category">${skill.category}</span>
                      </div>
                    </div>

                    <div class="compact-skill-level">
                      <select class="level-edit-select" data-edit-skill-level="${skill.id}" title="Edit competency level">
                        <option value="Beginner" ${skill.level === 'Beginner' ? 'selected' : ''}>Beginner</option>
                        <option value="Intermediate" ${skill.level === 'Intermediate' ? 'selected' : ''}>Intermediate</option>
                        <option value="Advanced" ${skill.level === 'Advanced' ? 'selected' : ''}>Advanced</option>
                        <option value="Expert" ${skill.level === 'Expert' ? 'selected' : ''}>Expert</option>
                      </select>
                    </div>

                    <div class="compact-skill-health">
                      <div class="compact-health-meta">
                        <span class="compact-label">Health</span>
                        <strong style="color: ${healthColor};">${skill.health}</strong>
                      </div>
                      <div class="compact-health-bar">
                        <div class="compact-health-fill" style="width: ${skill.health}%; background: ${healthColor};"></div>
                      </div>
                    </div>

                    <div class="compact-skill-relevance">
                      <strong class="relevance-score">${skill.relevance}%</strong>
                      <span class="relevance-label">Relevance</span>
                    </div>

                    <div class="compact-skill-trend">
                      <span class="trend-badge trend-badge--${trendClass}">
                        ${trendLabel}
                      </span>
                    </div>

                    <div class="compact-skill-action">
                      <button type="button" class="row-select-btn" aria-label="View details for ${skill.name}">
                        <i data-lucide="chevron-right"></i>
                      </button>
                    </div>
                  </article>
                `;
              }).join('')}
            </div>
          </aside>

          <!-- RIGHT COLUMN: SELECTED SKILL WORKSPACE -->
          <main class="selected-skill-surface primary-intel-panel" id="selected-skill-surface">
            <div class="skill-intel-profile-card" style="padding:0; border:none; background:transparent; box-shadow:none;">
              <div class="intel-profile-top">
                <div class="intel-profile-identity">
                  <span class="intel-icon-box">
                    <i data-lucide="${selectedSkillData.icon || 'cpu'}"></i>
                  </span>
                  <div>
                    <div class="intel-eyebrow-row">
                      <span class="roadmap-type-pill">${selectedSkillData.category}</span>
                      <span class="skill-level-tag"><i data-lucide="award" style="width:11px; height:11px;"></i> Level: ${selectedSkillData.level}</span>
                      <span class="decay-tag ${selectedSkillData.decayRisk.includes('Decay') ? 'decline' : 'positive'}">
                        <i data-lucide="${selectedSkillData.decayRisk.includes('Decay') ? 'alert-triangle' : 'shield-check'}" style="width:11px; height:11px;"></i>
                        ${selectedSkillData.decayRisk}
                      </span>
                    </div>
                    <h2 class="intel-skill-title">${selectedSkillData.name}</h2>
                  </div>
                </div>

                <div class="intel-profile-header-actions">
                  <button type="button" class="button button--secondary" id="saveSelectedSkillBtn">
                    <i data-lucide="${dashboardState.savedSkills.includes(selectedSkillData.name) ? 'bookmark-check' : 'bookmark'}"></i>
                    ${dashboardState.savedSkills.includes(selectedSkillData.name) ? 'Saved' : 'Save skill'}
                  </button>
                </div>
              </div>

              <!-- KEY METRICS GRID -->
              <div class="selected-metrics-grid">
                <div class="intel-quad-card intel-quad-card--health">
                  <div class="intel-quad-header">
                    <span class="intel-quad-label"><i data-lucide="shield-check"></i> Skill health</span>
                    <span class="intel-quad-status positive">Optimal</span>
                  </div>
                  <div class="intel-quad-val-row">
                    <strong class="intel-quad-val" style="color:var(--b-primary);">${selectedSkillData.health}</strong>
                    <span class="intel-quad-unit">/ 100</span>
                  </div>
                  <span class="intel-quad-sub">Proficiency score</span>
                </div>

                <div class="intel-quad-card intel-quad-card--relevance">
                  <div class="intel-quad-header">
                    <span class="intel-quad-label"><i data-lucide="target"></i> Market relevance</span>
                    <span class="intel-quad-status positive">High match</span>
                  </div>
                  <div class="intel-quad-val-row">
                    <strong class="intel-quad-val" style="color:#10B981;">${selectedSkillData.relevance}</strong>
                    <span class="intel-quad-unit">/ 100</span>
                  </div>
                  <span class="intel-quad-sub">Requisition alignment</span>
                </div>

                <div class="intel-quad-card intel-quad-card--trend">
                  <div class="intel-quad-header">
                    <span class="intel-quad-label"><i data-lucide="activity"></i> Market trend</span>
                    <span class="intel-quad-status ${selectedSkillData.direction === 'down' ? 'decline' : 'positive'}">
                      ${selectedSkillData.direction === 'down' ? 'Declining' : 'Accelerating'}
                    </span>
                  </div>
                  <div class="intel-quad-val-row">
                    <strong class="intel-quad-val ${selectedSkillData.direction === 'down' ? 'decline' : 'positive'}">
                      ${selectedSkillData.growth > 0 ? '+' : ''}${selectedSkillData.growth}%
                    </strong>
                  </div>
                  <span class="intel-quad-sub">6M velocity</span>
                </div>

                <div class="intel-quad-card intel-quad-card--halflife">
                  <div class="intel-quad-header">
                    <span class="intel-quad-label"><i data-lucide="hourglass"></i> Skill half-life</span>
                    <span class="intel-quad-status neutral">Longevity</span>
                  </div>
                  <div class="intel-quad-val-row">
                    <strong class="intel-quad-val">${selectedSkillData.halfLifeYears ? (typeof selectedSkillData.halfLifeYears === 'number' ? Math.round(selectedSkillData.halfLifeYears * 12) + ' months' : selectedSkillData.halfLifeYears) : '18 months'}</strong>
                  </div>
                  <span class="intel-quad-sub">Estimated longevity</span>
                </div>
              </div>

              <!-- ACTION TOOLBAR -->
              <div class="intel-action-toolbar">
                <button type="button" class="intel-action-btn" id="btnExploreMarket">
                  <i data-lucide="globe"></i> Explore market
                </button>
                <button type="button" class="intel-action-btn" id="btnViewSkillGap">
                  <i data-lucide="layers-3"></i> View skill gap
                </button>
                <button type="button" class="intel-action-btn intel-action-btn--primary" id="btnStartBuildRoadmap">
                  <i data-lucide="map"></i> Build roadmap
                </button>
              </div>
            </div>
          </main>
        </div>
      </section>

      <!-- 5. 6/6 GRID: HEALTH & RELEVANCE -->
      <section id="section-health-relevance" data-skill-section="health-relevance" style="margin-top:28px;">
        <div class="health-relevance-dual-grid">

          <!-- LEFT CARD: SKILL HEALTH -->
          <div class="primary-intel-panel intel-analytical-card--health">
            <div class="analytical-card-header">
              <div class="card-header-title">
                <span class="v2-kicker">PERSONAL PROFICIENCY</span>
                <div class="title-with-info">
                  <h3>Skill health</h3>
                  <span class="info-tooltip-wrap" title="Skill Health evaluates personal usage, practice activity, assessment performance, and recency.">
                    <i data-lucide="info"></i>
                  </span>
                </div>
              </div>
              <span class="health-status-badge ${selectedSkillData.health < 65 ? 'decline' : 'positive'}">
                <i data-lucide="${selectedSkillData.health < 65 ? 'alert-triangle' : 'shield-check'}"></i>
                ${selectedSkillData.health >= 80 ? 'Healthy' : selectedSkillData.health >= 65 ? 'Moderate' : 'Needs Focus'}
              </span>
            </div>

            <div class="health-analytical-body">
              <div class="health-radial-gauge-box">
                <svg class="radial-health-svg" viewBox="0 0 100 100" style="width:96px; height:96px; transform:rotate(-90deg); flex-shrink:0;">
                  <circle class="r-track" cx="50" cy="50" r="42" fill="none" stroke="#F1F5F9" stroke-width="8" />
                  <circle class="r-fill ${selectedSkillData.health < 65 ? 'r-fill--decline' : ''}" cx="50" cy="50" r="42" fill="none" stroke="${selectedSkillData.health < 65 ? '#EF4444' : 'var(--b-primary)'}" stroke-width="8" stroke-linecap="round" style="stroke-dasharray: 263.89; stroke-dashoffset: ${(263.89 * (1 - selectedSkillData.health / 100)).toFixed(2)};" />
                </svg>
                <div class="radial-health-center">
                  <strong class="radial-health-num">${selectedSkillData.health}</strong>
                  <span class="radial-health-denom">/ 100</span>
                </div>
              </div>

              <div class="health-factors-list">
                <div class="health-factor-row">
                  <span class="factor-name">Recent usage</span>
                  <div class="factor-bar-wrap">
                    <div class="factor-bar-fill" style="width: ${Math.min(100, selectedSkillData.health + 4)}%;"></div>
                  </div>
                  <strong class="factor-val">${Math.min(100, selectedSkillData.health + 4)}%</strong>
                </div>

                <div class="health-factor-row">
                  <span class="factor-name">Practice activity</span>
                  <div class="factor-bar-wrap">
                    <div class="factor-bar-fill" style="width: ${Math.max(10, selectedSkillData.health - 2)}%;"></div>
                  </div>
                  <strong class="factor-val">${Math.max(10, selectedSkillData.health - 2)}%</strong>
                </div>

                <div class="health-factor-row">
                  <span class="factor-name">Assessment score</span>
                  <div class="factor-bar-wrap">
                    <div class="factor-bar-fill" style="width: ${Math.max(10, selectedSkillData.health - 4)}%;"></div>
                  </div>
                  <strong class="factor-val">${Math.max(10, selectedSkillData.health - 4)}%</strong>
                </div>

                <div class="health-factor-row">
                  <span class="factor-name">Recency</span>
                  <div class="factor-bar-wrap">
                    <div class="factor-bar-fill" style="width: ${Math.min(100, selectedSkillData.health + 2)}%;"></div>
                  </div>
                  <strong class="factor-val">${Math.min(100, selectedSkillData.health + 2)}%</strong>
                </div>

                <div class="health-factor-row">
                  <span class="factor-name">Experience benchmark</span>
                  <div class="factor-bar-wrap">
                    <div class="factor-bar-fill" style="width: ${Math.max(10, selectedSkillData.health - 6)}%;"></div>
                  </div>
                  <strong class="factor-val">${Math.max(10, selectedSkillData.health - 6)}%</strong>
                </div>
              </div>
            </div>

            <div class="health-explanation-note">
              <i data-lucide="sparkles" style="color:var(--b-primary);"></i>
              <p>${selectedSkillData.health >= 75 ? `Your ${selectedSkillData.name} skill remains strong based on recent practice activity and verified assessment proficiency.` : `Your ${selectedSkillData.name} skill shows decay risk due to reduced recent practice and shifting technology benchmarks.`}</p>
            </div>
          </div>

          <!-- RIGHT CARD: SKILL RELEVANCE -->
          <div class="primary-intel-panel intel-analytical-card--relevance">
            <div class="analytical-card-header">
              <div class="card-header-title">
                <span class="v2-kicker">MARKET DEMAND</span>
                <div class="title-with-info">
                  <h3>Skill relevance</h3>
                  <span class="info-tooltip-wrap" title="Skill Relevance evaluates job requisitions, technology adoption, and market trajectory.">
                    <i data-lucide="info"></i>
                  </span>
                </div>
              </div>
              <span class="relevance-status-badge ${selectedSkillData.direction === 'down' ? 'decline' : 'positive'}">
                <i data-lucide="${selectedSkillData.direction === 'down' ? 'trending-down' : 'trending-up'}"></i>
                ${selectedSkillData.relevance >= 85 ? 'High relevance' : selectedSkillData.relevance >= 65 ? 'Moderate' : 'Low relevance'}
              </span>
            </div>

            <div class="relevance-analytical-body">
              <div class="relevance-compare-bar-block">
                <div class="relevance-row-item">
                  <div class="relevance-row-meta">
                    <span>Current relevance</span>
                    <strong>${selectedSkillData.relevance} / 100</strong>
                  </div>
                  <div class="relevance-progress-track">
                    <div class="relevance-progress-fill relevance-progress-fill--current" style="width: ${selectedSkillData.relevance}%;"></div>
                  </div>
                </div>

                <div class="relevance-row-item">
                  <div class="relevance-row-meta">
                    <span>Future relevance (12-24M forecast)</span>
                    <strong>${selectedSkillData.direction === 'down' ? Math.max(20, selectedSkillData.relevance - 12) : Math.min(100, selectedSkillData.relevance + 4)} / 100</strong>
                  </div>
                  <div class="relevance-progress-track">
                    <div class="relevance-progress-fill relevance-progress-fill--future ${selectedSkillData.direction === 'down' ? 'is-declining' : ''}" style="width: ${selectedSkillData.direction === 'down' ? Math.max(20, selectedSkillData.relevance - 12) : Math.min(100, selectedSkillData.relevance + 4)}%;"></div>
                  </div>
                </div>

                <div class="relevance-direction-tag ${selectedSkillData.direction === 'down' ? 'decline' : 'positive'}">
                  <i data-lucide="${selectedSkillData.direction === 'down' ? 'arrow-down-right' : 'arrow-up-right'}"></i>
                  <span>${selectedSkillData.direction === 'down' ? '↓ Declining market demand' : '↑ Accelerating market demand'}</span>
                </div>
              </div>

              <div class="relevance-why-block">
                <strong class="why-title"><i data-lucide="help-circle"></i> Why is this changing?</strong>
                <div class="why-factors-grid">
                  <div class="why-factor-item">
                    <span class="why-factor-label"><i data-lucide="briefcase"></i> Job demand</span>
                    <strong class="why-factor-val">${selectedSkillData.jobDemandCount ? selectedSkillData.jobDemandCount.toLocaleString() : '42,180'} requisitions (${selectedSkillData.growth > 0 ? '+' : ''}${selectedSkillData.growth}%)</strong>
                  </div>

                  <div class="why-factor-item">
                    <span class="why-factor-label"><i data-lucide="cpu"></i> Tech adoption</span>
                    <strong class="why-factor-val">${selectedSkillData.techVelocity || 86} / 100 adoption index</strong>
                  </div>

                  <div class="why-factor-item">
                    <span class="why-factor-label"><i data-lucide="chart-no-axes-combined"></i> Market trend</span>
                    <strong class="why-factor-val">${selectedSkillData.decayRisk || 'Low risk'} · ${selectedSkillData.halfLifeYears ? (typeof selectedSkillData.halfLifeYears === 'number' ? selectedSkillData.halfLifeYears + 'Y' : selectedSkillData.halfLifeYears) : '4.5Y'} longevity</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 6. WIDE PANEL: FUTURE OUTLOOK / SKILL HALF-LIFE -->
      <section id="section-outlook" data-skill-section="outlook" style="margin-top:28px;">
        <div class="primary-intel-panel dedicated-halflife-card" id="dedicatedHalfLifeSection">
          <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start;">
            <div>
              <span class="v2-kicker">WORKFORCE LONGEVITY FORECAST</span>
              <h3 style="margin-top: 2px;"><i data-lucide="hourglass" style="color:var(--b-primary);"></i> Future outlook & skill half-life</h3>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #6C6378;">Understand how long your skill relevance remains strong before market demand shifts.</p>
            </div>
            <span class="halflife-status-badge ${selectedSkillData.relevance < 60 || selectedSkillData.direction === 'down' ? 'decline' : selectedSkillData.relevance < 75 ? 'warning' : 'positive'}">
              <i data-lucide="${selectedSkillData.relevance < 60 || selectedSkillData.direction === 'down' ? 'alert-circle' : selectedSkillData.relevance < 75 ? 'alert-triangle' : 'shield-check'}"></i>
              ${selectedSkillData.relevance < 60 || selectedSkillData.direction === 'down' ? 'Needs refresh' : selectedSkillData.relevance < 75 ? 'Decay risk' : 'Healthy longevity'}
            </span>
          </div>

          <div class="future-outlook-dual-body">
            <!-- LEFT HERO STATS -->
            <div class="outlook-hero-box">
              <div class="stat-group">
                <span class="stat-label">Target skill</span>
                <strong class="stat-value-text">${selectedSkillData.name}</strong>
              </div>

              <div class="stat-group">
                <span class="stat-label">Estimated half-life</span>
                <div class="stat-value-with-unit">
                  <strong class="stat-highlight-num">${(() => {
                    let baseMonths = 18;
                    if (typeof selectedSkillData.halfLifeYears === 'number') baseMonths = Math.round(selectedSkillData.halfLifeYears * 12);
                    else if (selectedSkillData.halfLifeYears) baseMonths = parseInt(selectedSkillData.halfLifeYears, 10) * 12 || 18;
                    const mMult = dashboardState.market === 'Global' ? 1.0 : dashboardState.market === 'India' ? 0.9 : dashboardState.market === 'Region' ? 1.1 : 0.85;
                    const tMult = dashboardState.timeRange === '30D' ? 1.0 : dashboardState.timeRange === '90D' ? 1.05 : dashboardState.timeRange === '6M' ? 1.1 : dashboardState.timeRange === '1Y' ? 1.25 : 1.0;
                    return Math.max(6, Math.min(60, Math.round(baseMonths * mMult * tMult)));
                  })()}</strong>
                  <span class="stat-unit">months</span>
                </div>
                <small class="stat-context-sub">Timeframe to 50% relevance threshold</small>
              </div>

              <div class="stat-group">
                <span class="stat-label">Decay signal risk</span>
                <span class="decay-risk-pill ${selectedSkillData.direction === 'down' ? 'high-risk' : 'low-risk'}">
                  <i data-lucide="${selectedSkillData.direction === 'down' ? 'trending-down' : 'shield-check'}"></i>
                  ${selectedSkillData.decayRisk || (selectedSkillData.direction === 'down' ? 'Accelerated decay' : 'Low decay risk')}
                </span>
              </div>

              <button type="button" class="button button--assistant btn-refresh-skill" id="btnRefreshSkillRoadmap" style="background:var(--b-primary); color:#FFF; border-radius: 10px; padding: 10px 16px; font-weight: 700; width:100%; margin-top:12px;">
                <i data-lucide="refresh-cw"></i> Refresh this skill
              </button>
            </div>

            <!-- RIGHT GRAPH & EDUCATIONAL DETAILS -->
            <div class="outlook-graphic-box">
              <div class="decay-chart-container" style="background:transparent; border:none; padding:0;">
                <div class="decay-chart-header-note">
                  <span class="decay-chart-title"><i data-lucide="activity"></i> Projected relevance decay trajectory</span>
                  <span class="decay-chart-meta">Location: ${dashboardState.market} · Horizon: ${dashboardState.timeRange}</span>
                </div>

                ${renderSkillDecayChart(selectedSkillData, dashboardState.market, dashboardState.timeRange)}

                <div class="halflife-disclaimer-box">
                  <i data-lucide="info" class="disclaimer-icon"></i>
                  <p>
                    <strong>Probabilistic workforce forecast:</strong> Based on current market trend and requisition velocity in <span>${dashboardState.market}</span>, relevance is expected to decline gradually unless refreshed through targeted practice. <em>Estimated signal, not a guaranteed date.</em>
                  </p>
                </div>
              </div>

              <details class="halflife-edu-details" style="margin-top:16px;">
                <summary class="halflife-edu-summary">
                  <span class="edu-summary-left"><i data-lucide="help-circle"></i> What is skill half-life?</span>
                  <span class="edu-summary-badge">Educational guide</span>
                  <i data-lucide="chevron-down" class="chevron-icon"></i>
                </summary>
                <div class="halflife-edu-content">
                  <div class="edu-grid">
                    <div class="edu-card">
                      <h4><i data-lucide="book-open"></i> Definition</h4>
                      <p><strong>Skill half-life</strong> is the estimated duration before a technology skill loses 50% of its initial market relevance or competitive compensation premium.</p>
                    </div>
                    <div class="edu-card">
                      <h4><i data-lucide="alert-triangle"></i> What happens if un-refreshed?</h4>
                      <p>Without periodic practice or framework refreshes, practical proficiency benchmark degrades relative to industry expectations, leading to lower match scores.</p>
                    </div>
                    <div class="edu-card">
                      <h4><i data-lucide="zap"></i> How to extend half-life</h4>
                      <ul>
                        <li><i data-lucide="check"></i> Learn modern adjacent frameworks</li>
                        <li><i data-lucide="check"></i> Complete practical hands-on projects</li>
                        <li><i data-lucide="check"></i> Build a tailored skill roadmap</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      </section>

      <!-- 7. WIDE PANEL: SKILL HISTORY -->
      <section id="section-history" data-skill-section="history" style="margin-top:28px;">
        <div class="primary-intel-panel dedicated-history-card" id="dedicatedSkillHistorySection">
          <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start;">
            <div>
              <span class="v2-kicker">HISTORICAL SIGNAL LOG</span>
              <h3 style="margin-top: 2px;"><i data-lucide="history" style="color:var(--b-primary);"></i> Skill history</h3>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #6C6378;">Track historical performance, proficiency shifts, and market demand trajectory over time.</p>
            </div>
            <span class="historical-data-badge">
              <i data-lucide="clock"></i> Historical data log
            </span>
          </div>

          <div class="history-controls-bar">
            <div class="history-metric-tabs">
              <button type="button" class="history-tab-btn ${dedicatedSkillState.historyMetric === 'health' ? 'is-active' : ''}" data-history-metric="health">
                <i data-lucide="shield-check"></i> Skill health
              </button>
              <button type="button" class="history-tab-btn ${dedicatedSkillState.historyMetric === 'relevance' ? 'is-active' : ''}" data-history-metric="relevance">
                <i data-lucide="trending-up"></i> Skill relevance
              </button>
              <button type="button" class="history-tab-btn ${dedicatedSkillState.historyMetric === 'demand' ? 'is-active' : ''}" data-history-metric="demand">
                <i data-lucide="briefcase"></i> Market demand
              </button>
            </div>

            <div class="history-time-pills">
              ${['30D', '90D', '6M', '1Y', 'All'].map(t => `
                <button type="button" class="history-time-btn ${dedicatedSkillState.historyTimeRange === t ? 'is-active' : ''}" data-history-time="${t}">
                  ${t}
                </button>
              `).join('')}
            </div>
          </div>

          <div class="history-summary-strip">
            <div class="summary-metric-group">
              <span class="summary-metric-label">${historyData.label} current value</span>
              <div class="summary-metric-val">
                <strong>${historyData.formattedCurrent}</strong>
                <span class="summary-metric-unit">${historyData.unit}</span>
              </div>
            </div>

            <div class="summary-divider"></div>

            <div class="summary-metric-group">
              <span class="summary-metric-label">Historical shift (${dedicatedSkillState.historyTimeRange})</span>
              <span class="summary-change-badge ${historyData.changeDirection === 'up' ? 'positive' : 'negative'}">
                <i data-lucide="${historyData.changeDirection === 'up' ? 'arrow-up-right' : 'arrow-down-right'}"></i>
                ${historyData.changePercent}
              </span>
            </div>

            <div class="summary-divider"></div>

            <div class="summary-metric-group">
              <span class="summary-metric-label">Timeline events</span>
              <span class="summary-events-count">
                <i data-lucide="sparkles"></i> ${historyData.events.length} key milestones
              </span>
            </div>
          </div>

          <div class="history-chart-wrapper">
            ${renderSkillHistoryChart(historyData, dedicatedSkillState.selectedEventId)}
          </div>

          ${selectedEvent ? `
            <div class="history-event-breakdown-card" id="eventBreakdownCard">
              <div class="event-breakdown-header">
                <div class="event-title-group">
                  <span class="event-tag"><i data-lucide="zap"></i> HISTORICAL EVENT · ${selectedEvent.date}</span>
                  <h4>${selectedEvent.title}</h4>
                </div>
                <div style="display:flex; align-items:center; gap: 8px;">
                  <span class="event-impact-pill positive">${selectedEvent.impactSummary}</span>
                  <button type="button" class="v2-modal-close" id="closeEventBreakdownBtn" style="width: 28px; height: 28px; font-size: 16px;" aria-label="Close event details">&times;</button>
                </div>
              </div>

              <div class="event-triple-grid">
                <div class="event-info-box">
                  <span class="event-box-label"><i data-lucide="help-circle"></i> WHAT CHANGED?</span>
                  <p>${selectedEvent.whatChanged}</p>
                </div>

                <div class="event-info-box">
                  <span class="event-box-label"><i data-lucide="target"></i> WHY IT MATTERED</span>
                  <p>${selectedEvent.whyItMattered}</p>
                </div>

                <div class="event-info-box event-info-box--impact">
                  <span class="event-box-label"><i data-lucide="trending-up"></i> IMPACT ON THIS SKILL</span>
                  <p><strong>${selectedEvent.impact}</strong></p>
                </div>
              </div>
            </div>
          ` : `
            <div class="history-event-prompt">
              <i data-lucide="info"></i>
              <span>Click any event marker (✦) on the chart timeline to inspect historical market shifts and skill impact details.</span>
            </div>
          `}
        </div>
      </section>

      <!-- 8. 6/6 GRID: MARKET & TECHNOLOGY CONTEXT -->
      <section id="section-market" data-skill-section="market" style="margin-top:28px;">
        <div class="primary-intel-panel dedicated-market-card" id="dedicatedMarketContextSection">
          <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start;">
            <div>
              <span class="v2-kicker">WORKFORCE MARKET INTELLIGENCE</span>
              <h3 style="margin-top: 2px;"><i data-lucide="globe" style="color:var(--b-primary);"></i> Market & technology context</h3>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #6C6378;">External technology adoption trends, regional hiring demand, and sector velocity for ${selectedSkillData.name}.</p>
            </div>
            
            <div class="market-location-sync-wrap">
              <label for="marketSectionLocationSelect" style="font-size: 11px; font-weight: 700; color: #7A7085;">Location:</label>
              <select class="console-select-sm" id="marketSectionLocationSelect">
                <option value="Global" ${dashboardState.market === 'Global' ? 'selected' : ''}>Global</option>
                <option value="India" ${dashboardState.market === 'India' ? 'selected' : ''}>India</option>
                <option value="Tamil Nadu" ${dashboardState.market === 'Tamil Nadu' ? 'selected' : ''}>Tamil Nadu</option>
                <option value="Bangalore" ${dashboardState.market === 'Bangalore' ? 'selected' : ''}>Bangalore</option>
                <option value="Chennai" ${dashboardState.market === 'Chennai' ? 'selected' : ''}>Chennai</option>
              </select>
            </div>
          </div>

          <div class="why-changing-block">
            <div class="why-changing-header">
              <span class="why-changing-title"><i data-lucide="activity"></i> WHY IS THIS SKILL CHANGING?</span>
              <span class="why-changing-subtitle">Real-time external signal matrix</span>
            </div>

            <div class="compact-signals-quad">
              <div class="compact-signal-tile">
                <span class="signal-label"><i data-lucide="briefcase"></i> JOB DEMAND</span>
                <div class="signal-main-val">
                  <strong class="signal-metric-num positive">↑ ${selectedSkillData.growth > 0 ? selectedSkillData.growth : 12.4}%</strong>
                </div>
                <div class="signal-mini-sparkline">
                  <svg viewBox="0 0 60 16" style="width:50px; height:14px;">
                    <path d="M0,14 Q15,10 30,12 T60,2" fill="none" stroke="#10B981" stroke-width="2"/>
                  </svg>
                  <small class="signal-sub-text">${(selectedSkillData.jobDemandCount || 42180).toLocaleString()} open roles</small>
                </div>
              </div>

              <div class="compact-signal-tile">
                <span class="signal-label"><i data-lucide="cpu"></i> TECH MOMENTUM</span>
                <div class="signal-main-val">
                  <strong class="signal-metric-num positive">↑ Strong</strong>
                </div>
                <div class="signal-mini-gauge">
                  <div class="mini-gauge-bar"><div class="mini-gauge-fill" style="width:${selectedSkillData.techVelocity || 86}%;"></div></div>
                  <small class="signal-sub-text">${selectedSkillData.techVelocity || 86} / 100 adoption</small>
                </div>
              </div>

              <div class="compact-signal-tile">
                <span class="signal-label"><i data-lucide="building-2"></i> INDUSTRY DEMAND</span>
                <div class="signal-main-val">
                  <strong class="signal-metric-text">AI & Software</strong>
                </div>
                <small class="signal-sub-text">SaaS, Fintech & Enterprise AI</small>
              </div>

              <div class="compact-signal-tile">
                <span class="signal-label"><i data-lucide="map-pin"></i> LOCATION DEMAND</span>
                <div class="signal-main-val">
                  <strong class="signal-metric-text">${dashboardState.market} / Hubs</strong>
                </div>
                <small class="signal-sub-text">${(selectedSkillData.topLocations || ['Bangalore', 'Chennai']).join(', ')}</small>
              </div>
            </div>
          </div>

          <div class="market-demand-chart-block" style="margin-top:20px;">
            <div class="market-chart-header">
              <div>
                <h4 style="margin:0; font-size:14px; font-weight:800; color:#1A1523; display:flex; align-items:center; gap:6px;">
                  <i data-lucide="trending-up" style="color:var(--b-primary);"></i> MARKET DEMAND FOR ${selectedSkillData.name.toUpperCase()}
                </h4>
                <span class="market-chart-sub">Requisition velocity & hiring index across <strong>${dashboardState.market}</strong> (${dashboardState.timeRange})</span>
              </div>
              <span class="market-demand-badge positive">
                <i data-lucide="check-circle-2"></i> High market liquidity
              </span>
            </div>

            <div class="market-trend-chart-box">
              ${renderMarketDemandLocationChart(selectedSkillData, dashboardState.market, dashboardState.timeRange)}
            </div>
          </div>

          <div class="why-this-matters-card" style="margin-top:16px;">
            <div class="why-matters-header">
              <span class="company-signal-pill positive"><i data-lucide="sparkles"></i> AI explanation</span>
              <span class="why-matters-title-tag">WHY THIS MATTERS</span>
            </div>
            <p class="why-matters-explanation">
              "${selectedSkillData.name} demand remains strong in <strong>${dashboardState.market}</strong> (${dashboardState.timeRange}), while related AI, Data, and Cloud roles continue to require advanced ${selectedSkillData.name}-based frameworks and verified production capabilities."
            </p>
          </div>
        </div>
      </section>

      <!-- 9. WIDE PANEL: SKILL GAP ANALYSIS -->
      <section id="section-gap" data-skill-section="gap" style="margin-top:28px;">
        <div class="primary-intel-panel dedicated-gap-card" id="dedicatedGapSection">
          <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start;">
            <div>
              <span class="v2-kicker">WORKFORCE BENCHMARKING</span>
              <h3 style="margin-top: 2px;"><i data-lucide="layers-3" style="color:var(--b-primary);"></i> Skill gap analysis</h3>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: #6C6378;">Compare current capabilities against requirements for your target role.</p>
            </div>
            <span class="gap-severity-badge ${selectedSkillData.gapSeverity.includes('Attention') || selectedSkillData.gapSeverity.includes('High') ? 'decline' : 'warning'}">
              Severity: ${selectedSkillData.gapSeverity}
            </span>
          </div>

          <div class="gap-flow-banner">
            <div class="gap-flow-step">
              <span class="step-num">1</span>
              <div class="step-meta">
                <strong>YOUR CURRENT SKILLS</strong>
                <small>Verified baseline</small>
              </div>
            </div>
            <div class="gap-flow-arrow"><i data-lucide="chevron-right"></i></div>

            <div class="gap-flow-step">
              <span class="step-num">2</span>
              <div class="step-meta">
                <strong>TARGET ROLE REQUIREMENTS</strong>
                <small>${gapData.targetRole}</small>
              </div>
            </div>
            <div class="gap-flow-arrow"><i data-lucide="chevron-right"></i></div>

            <div class="gap-flow-step">
              <span class="step-num">3</span>
              <div class="step-meta">
                <strong>REQUIRED SKILLS</strong>
                <small>Competency benchmark</small>
              </div>
            </div>
            <div class="gap-flow-arrow"><i data-lucide="chevron-right"></i></div>

            <div class="gap-flow-step">
              <span class="step-num">4</span>
              <div class="step-meta">
                <strong>SKILL GAP</strong>
                <small>Proficiency differential</small>
              </div>
            </div>
            <div class="gap-flow-arrow"><i data-lucide="chevron-right"></i></div>

            <div class="gap-flow-step">
              <span class="step-num">5</span>
              <div class="step-meta">
                <strong>PRIORITY ACTION</strong>
                <small>Targeted upskilling</small>
              </div>
            </div>
          </div>

          <div class="gap-summary-card">
            <div class="gap-summary-left">
              <div class="gap-match-circle-wrap">
                <div class="gap-match-score">78%</div>
                <span class="gap-match-circle-label">Overall role match</span>
              </div>

              <div class="gap-match-tags-strip">
                <span class="gap-match-tag strong"><i data-lucide="check-circle-2"></i> Strong match</span>
                <span class="gap-match-tag partial"><i data-lucide="alert-triangle"></i> Partial match</span>
                <span class="gap-match-tag gap"><i data-lucide="x-circle"></i> Skill gap</span>
              </div>
            </div>

            <div class="gap-summary-right">
              <div class="gap-breakdown-title">
                <i data-lucide="calculator" style="color:var(--b-primary);"></i>
                <strong>Alignment score breakdown</strong>
              </div>
              <div class="gap-breakdown-grid">
                <div class="breakdown-item">
                  <div class="breakdown-item-header">
                    <span class="breakdown-label">Core technical baseline</span>
                    <strong class="breakdown-val">40 / 45 pts</strong>
                  </div>
                  <div class="breakdown-progress"><div class="breakdown-bar" style="width: 88%;"></div></div>
                </div>
                <div class="breakdown-item">
                  <div class="breakdown-item-header">
                    <span class="breakdown-label">Framework & tool proficiency</span>
                    <strong class="breakdown-val">22 / 35 pts</strong>
                  </div>
                  <div class="breakdown-progress"><div class="breakdown-bar" style="width: 62%;"></div></div>
                </div>
                <div class="breakdown-item">
                  <div class="breakdown-item-header">
                    <span class="breakdown-label">Domain capability</span>
                    <strong class="breakdown-val">16 / 20 pts</strong>
                  </div>
                  <div class="breakdown-progress"><div class="breakdown-bar" style="width: 80%;"></div></div>
                </div>
              </div>
            </div>
          </div>

          <div class="gap-items-block" style="margin-top:20px;">
            <div class="gap-items-header">
              <div>
                <span class="gap-items-title"><i data-lucide="list-checks"></i> TARGET ROLE REQUIREMENTS & GAP BREAKDOWN</span>
                <span class="gap-items-sub">Detailed proficiency differential for <strong>${gapData.targetRole}</strong></span>
              </div>
              <span class="gap-severity-badge warning">4 key requirements evaluated</span>
            </div>

            <div class="gap-rows-matrix">
              ${gapData.gapItems.map(item => `
                <div class="gap-item-card gap-item-card--${item.matchBadgeClass}">
                  <div class="gap-item-top">
                    <div class="gap-item-identity">
                      <strong class="gap-item-name">${item.name}</strong>
                      <span class="gap-item-badge ${item.matchBadgeClass}">
                        ${item.matchType === 'Strong Match' ? '<i data-lucide="check-circle-2"></i>' : item.matchType === 'Partial Match' ? '<i data-lucide="alert-triangle"></i>' : '<i data-lucide="x-circle"></i>'}
                        ${item.matchType}
                      </span>
                    </div>

                    <span class="gap-item-priority priority-${item.priorityClass}">
                      <i data-lucide="flag"></i> ${item.priority} priority
                    </span>
                  </div>

                  <div class="gap-item-metrics">
                    <div class="gap-metric">
                      <span class="metric-lbl">Current level</span>
                      <strong class="metric-val">${item.currentLevel}</strong>
                    </div>

                    <div class="gap-metric">
                      <span class="metric-lbl">Required level</span>
                      <strong class="metric-val">${item.requiredLevel}</strong>
                    </div>

                    <div class="gap-metric">
                      <span class="metric-lbl">Gap magnitude</span>
                      <strong class="metric-val highlight">${item.gapMagnitude}</strong>
                    </div>
                  </div>

                  <div class="gap-item-why">
                    <span class="why-tag">WHY IT MATTERS:</span>
                    <p>${item.why}</p>
                  </div>

                  <div class="gap-item-actions">
                    <button type="button" class="gap-cta-btn secondary" data-select-dedicated-skill="${item.name}">
                      Explore skill <i data-lucide="arrow-right"></i>
                    </button>
                    <button type="button" class="gap-cta-btn primary" data-build-roadmap-skill="${item.name}">
                      <i data-lucide="map"></i> Build roadmap
                    </button>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="adjacent-skills-block" style="margin-top:20px;">
            <div class="adjacent-header">
              <div>
                <h4 style="margin:0; font-size:14px; font-weight:800; color:#1A1523; display:flex; align-items:center; gap:6px;">
                  <i data-lucide="share-2" style="color:var(--b-primary);"></i> RELATED & ADJACENT SKILLS FOR ${selectedSkillData.name.toUpperCase()}
                </h4>
                <span class="adjacent-sub">Click any skill to view its detailed intelligence</span>
              </div>
              <span class="company-signal-pill positive" style="font-size:10.5px;">Interactive exploration</span>
            </div>

            <div class="adjacent-cards-grid">
              ${selectedSkillData.adjacentSkills.map(adjName => {
                const adjData = dedicatedSkillIntelligenceData.skills.find(s => s.name.toLowerCase() === adjName.toLowerCase()) || {
                  name: adjName,
                  category: 'Tech Stack',
                  level: 'Intermediate',
                  health: 80,
                  growth: 14.5
                };
                const isActive = dashboardState.selectedSkill.toLowerCase() === adjName.toLowerCase();
                return `
                  <div class="adjacent-skill-card ${isActive ? 'is-active' : ''}" data-select-dedicated-skill="${adjName}">
                    <div class="adj-card-header">
                      <div class="adj-icon-box">
                        <i data-lucide="${adjData.category === 'Programming' ? 'code-2' : adjData.category === 'Frontend' ? 'layout' : adjData.category === 'Infrastructure' ? 'cloud' : 'cpu'}"></i>
                      </div>
                      <div>
                        <strong class="adj-name">${adjName}</strong>
                        <span class="adj-category">${adjData.category || 'Tech Stack'}</span>
                      </div>
                    </div>

                    <div class="adj-card-meta">
                      <span class="adj-level">${adjData.level || 'Intermediate'}</span>
                      <span class="adj-health"><i data-lucide="heart-pulse"></i> Health ${adjData.health || 80}</span>
                      <span class="adj-growth">+${adjData.growth || 12.4}%</span>
                    </div>

                    <div class="adj-card-hover-prompt">
                      Explore intelligence →
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>
      </section>

      <!-- 10. 7/5 GRID: AI INSIGHT & EVIDENCE -->
      <section id="section-ai-insight" data-skill-section="ai-insight" style="margin-top:28px;">
        <div class="ai-insight-evidence-grid">

          <!-- LEFT COLUMN (7 COLS): AI INSIGHT PANEL -->
          <div class="primary-intel-panel dedicated-ai-insight-card" id="dedicatedAiInsightSection">
            <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <div class="ai-sparkle-avatar">
                  <i data-lucide="sparkles"></i>
                </div>
                <div>
                  <span class="v2-kicker">EXPLAINABLE WORKFORCE AI</span>
                  <h3 style="margin: 2px 0 0 0;"><i data-lucide="brain-circuit" style="color:var(--b-primary);"></i> AI insight & explainability</h3>
                  <p style="margin: 4px 0 0 0; font-size: 12px; color: #6C6378;">
                    Transparent breakdown for ${selectedSkillData.name} status in ${dashboardState.market}.
                  </p>
                </div>
              </div>

              <button type="button" class="button button--secondary button--sm" id="btnAskAboutThisSkill" data-skill="${selectedSkillData.name}">
                <i data-lucide="message-square" style="color:var(--b-primary); width: 14px; height: 14px;"></i> Ask about ${selectedSkillData.name}
              </button>
            </div>

            <div class="ai-insight-block" style="margin-top:16px;">
              <span class="insight-block-tag"><i data-lucide="target"></i> WHY THIS SKILL MATTERS</span>
              <p class="insight-lead-text">
                "${aiInsightData.whyMatters}"
              </p>
            </div>

            <div class="ai-insight-block">
              <span class="insight-block-tag"><i data-lucide="check-circle-2"></i> KEY SIGNALS EVALUATED</span>
              <div class="insight-signals-quad">
                ${aiInsightData.keySignals.map(sig => `
                  <div class="insight-signal-item">
                    <span class="sig-check"><i data-lucide="check"></i></span>
                    <div class="sig-meta">
                      <strong class="sig-label">${sig.label}</strong>
                      <span class="sig-desc">${sig.desc}</span>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>

            <div class="ai-insight-block">
              <span class="insight-block-tag"><i data-lucide="history"></i> WHAT CHANGED RECENTLY?</span>
              <p class="insight-body-text">
                ${aiInsightData.whatChanged}
              </p>
            </div>

            <div class="ai-insight-block forecast-block">
              <span class="insight-block-tag forecast"><i data-lucide="trending-up"></i> WHAT COULD HAPPEN NEXT? (PROJECTED)</span>
              <p class="insight-body-text forecast">
                ${aiInsightData.whatCouldHappenNext}
              </p>
              <span class="forecast-disclaimer">
                <i data-lucide="info" style="width:11px; height:11px;"></i> Projection based on available market signals. Not a guaranteed outcome.
              </span>
            </div>
          </div>

          <!-- RIGHT COLUMN (5 COLS): GROUNDING EVIDENCE -->
          <div class="supporting-surface-panel evidence-sources-block" style="margin-top:0;">
            <div class="evidence-header">
              <div>
                <h4 style="margin:0; font-size:14px; font-weight:800; color:#1A1523; display:flex; align-items:center; gap:6px;">
                  <i data-lucide="file-text" style="color:var(--b-primary);"></i> EVIDENCE & SOURCES
                </h4>
                <span class="evidence-sub">Source records backing AI analysis</span>
              </div>
            </div>

            <div class="evidence-cards-grid" style="grid-template-columns: 1fr; gap:12px; margin-top:14px;">
              ${aiInsightData.evidenceList.map((ev, idx) => `
                <div class="evidence-card">
                  <div class="ev-card-top">
                    <span class="ev-source-badge ev-badge--${ev.typeBadgeClass || 'job'}">
                      <i data-lucide="${ev.typeBadgeClass === 'tech' ? 'cpu' : ev.typeBadgeClass === 'industry' ? 'building-2' : ev.typeBadgeClass === 'company' ? 'award' : 'briefcase'}"></i>
                      ${ev.type}
                    </span>
                    <span class="ev-date">${ev.date || 'Recent'}</span>
                  </div>

                  <h5 class="ev-title">${ev.title}</h5>
                  <p class="ev-text">${ev.explanation || ev.text}</p>

                  <button type="button" class="ev-link-btn" data-view-evidence-index="${idx}">
                    View evidence <i data-lucide="external-link"></i>
                  </button>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      </section>

      <!-- 11. PURPLE GRADIENT PANEL: NEXT ACTION -->
      <section id="section-next-action" data-skill-section="next-action" style="margin-top:28px;">
        <div class="purple-gradient-panel dedicated-next-action-card" id="dedicatedNextActionSection">
          <div class="card-title-row" style="flex-wrap: wrap; gap: 12px; align-items: flex-start; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:12px; margin-bottom:16px;">
            <div>
              <span class="v2-kicker" style="color:rgba(255,255,255,0.8);">PERSONALIZED CAREER ACTION</span>
              <h3 style="margin-top: 2px; color:#FFF;"><i data-lucide="compass" style="color:#FFF;"></i> What should I do next?</h3>
              <p style="margin: 4px 0 0 0; font-size: 12px; color: rgba(255,255,255,0.85);">
                Recommendation generated for ${selectedSkillData.name} based on proficiency health and target role trajectory.
              </p>
            </div>
            <span class="company-signal-pill positive" style="font-size:11px; background:rgba(255,255,255,0.2); color:#FFF; border:none;">
              State: ${nextActionData.stateType}
            </span>
          </div>

          ${(roadmapState && (roadmapState.status === 'active' || roadmapState.status === 'paused')) ? `
            <div class="active-roadmap-safeguard-banner" style="background:rgba(255,255,255,0.12); border-color:rgba(255,255,255,0.25);">
              <div class="safeguard-left">
                <div class="safeguard-pulse-dot"></div>
                <div>
                  <span class="safeguard-kicker" style="color:rgba(255,255,255,0.8);">CURRENTLY ACTIVE ROADMAP</span>
                  <strong class="safeguard-title" style="color:#FFF;">${roadmapState.title || (roadmapState.skill + ' — Roadmap')}</strong>
                  <small class="safeguard-sub" style="color:rgba(255,255,255,0.75);">Progress: ${roadmapState.progress || 64}% completed</small>
                </div>
              </div>
              <a href="#/individual/home" class="button button--secondary button--sm" id="btnViewCurrentRoadmap">
                <i data-lucide="map-pin"></i> View current roadmap
              </a>
            </div>
          ` : ''}

          <div class="next-action-recommendation-box" style="background:rgba(255,255,255,0.08); border-color:rgba(255,255,255,0.15);">
            <div class="recommendation-badge-strip">
              <span class="rec-kicker-tag" style="background:rgba(255,255,255,0.2); color:#FFF;"><i data-lucide="sparkles"></i> PRIMARY RECOMMENDED ACTION</span>
              <span class="rec-skill-tag" style="background:rgba(255,255,255,0.15); color:#FFF;">${selectedSkillData.name} (${selectedSkillData.level || 'Intermediate'})</span>
            </div>

            <h4 class="recommendation-title" style="color:#FFF;">
              ${nextActionData.primaryActionTitle}
            </h4>

            <p class="recommendation-rationale" style="color:rgba(255,255,255,0.9);">
              <strong style="color:#FFF;">Reason:</strong> ${nextActionData.rationale}
            </p>

            <div class="next-action-focus-chips">
              ${nextActionData.suggestedPills.map(pill => `
                <span class="focus-chip" style="background:rgba(255,255,255,0.15); color:#FFF; border-color:rgba(255,255,255,0.25);"><i data-lucide="check"></i> ${pill}</span>
              `).join('')}
            </div>

            <div class="next-action-buttons-row">
              <button type="button" class="button button--secondary" id="btnNextActionExploreSkill" data-skill="${selectedSkillData.name}" style="background:rgba(255,255,255,0.2); color:#FFF; border-color:rgba(255,255,255,0.3);">
                <i data-lucide="search"></i> Explore skill
              </button>

              <button type="button" class="button button--secondary" id="btnNextActionTakeAssessment" data-skill="${selectedSkillData.name}" style="background:rgba(255,255,255,0.2); color:#FFF; border-color:rgba(255,255,255,0.3);">
                <i data-lucide="award"></i> Take assessment
              </button>

              <button type="button" class="button button--assistant" style="background:#FFF; color:var(--b-primary); font-weight:700;" id="btnNextActionBuildRoadmap" data-skill="${selectedSkillData.name}">
                <i data-lucide="map"></i> Build roadmap
              </button>
            </div>
          </div>

          <div class="roadmap-flow-footer-strip" style="background:rgba(0,0,0,0.15); border-color:rgba(255,255,255,0.15);">
            <div class="flow-step-mini" style="color:#FFF;"><span style="background:rgba(255,255,255,0.2); color:#FFF;">1</span> Build roadmap</div>
            <div class="flow-arrow-mini" style="color:rgba(255,255,255,0.6);"><i data-lucide="chevron-right"></i></div>
            <div class="flow-step-mini" style="color:#FFF;"><span style="background:rgba(255,255,255,0.2); color:#FFF;">2</span> Preview</div>
            <div class="flow-arrow-mini" style="color:rgba(255,255,255,0.6);"><i data-lucide="chevron-right"></i></div>
            <div class="flow-step-mini" style="color:#FFF;"><span style="background:rgba(255,255,255,0.2); color:#FFF;">3</span> Review & Edit</div>
            <div class="flow-arrow-mini" style="color:rgba(255,255,255,0.6);"><i data-lucide="chevron-right"></i></div>
            <div class="flow-step-mini" style="color:#FFF;"><span style="background:rgba(255,255,255,0.2); color:#FFF;">4</span> Accept & Activate</div>

            <span class="flow-note-text" style="color:rgba(255,255,255,0.75);">
              <i data-lucide="info" style="width:11px; height:11px;"></i> Roadmap preview does not automatically activate tracking.
            </span>
          </div>
        </div>
      </section>

      <!-- MODALS -->
      ${dedicatedSkillState.isAddingSkill ? `
        <div class="v2-modal-overlay" id="addSkillModalOverlay">
          <div class="v2-modal-container" style="max-width: 480px;">
            <div class="v2-modal-header">
              <div>
                <span class="v2-kicker">MY SKILLS</span>
                <h3>Add skill to profile</h3>
              </div>
              <button type="button" class="v2-modal-close" id="closeAddSkillModalBtn"><i data-lucide="x"></i></button>
            </div>

            <div class="v2-modal-body">
              <div class="v2-modal-field-group" style="margin-bottom: 14px;">
                <label for="newSkillNameInput">Skill name:</label>
                <input type="text" class="v2-modal-input" id="newSkillNameInput" placeholder="e.g. TypeScript, PyTorch, Docker" list="suggestedSkillList" autocomplete="off" />
                <datalist id="suggestedSkillList">
                  <option value="TypeScript">
                  <option value="Docker & Kubernetes">
                  <option value="SQL & PostgreSQL">
                  <option value="PyTorch">
                  <option value="GraphQL">
                  <option value="FastAPI">
                  <option value="Rust">
                </datalist>
              </div>

              <div class="v2-modal-field-group" style="margin-bottom: 14px;">
                <label for="newSkillCategorySelect">Category:</label>
                <select class="v2-modal-select" id="newSkillCategorySelect">
                  <option value="Programming">Programming</option>
                  <option value="AI & Data" selected>AI & Data</option>
                  <option value="Frontend">Frontend</option>
                  <option value="Infrastructure">Infrastructure</option>
                  <option value="Security">Security</option>
                  <option value="Design">Design</option>
                </select>
              </div>

              <div class="v2-modal-field-group" style="margin-bottom: 14px;">
                <label for="newSkillLevelSelect">Competency level:</label>
                <select class="v2-modal-select" id="newSkillLevelSelect">
                  <option value="Beginner">Beginner</option>
                  <option value="Intermediate" selected>Intermediate (Default)</option>
                  <option value="Advanced">Advanced</option>
                  <option value="Expert">Expert</option>
                </select>
              </div>
            </div>

            <div class="v2-modal-footer">
              <button type="button" class="button button--secondary" id="cancelAddSkillModalBtn">Cancel</button>
              <button type="button" class="button button--assistant" style="background:var(--b-primary); color:#FFF;" id="confirmAddSkillModalBtn">
                Add skill <i data-lucide="plus"></i>
              </button>
            </div>
          </div>
        </div>
      ` : ''}

      ${dedicatedSkillState.askingSkill ? `
        <div class="v2-modal-overlay" id="askingSkillModalOverlay">
          <div class="v2-modal-container" style="max-width: 520px;">
            <div class="v2-modal-header">
              <div style="display:flex; align-items:center; gap:8px;">
                <i data-lucide="sparkles" style="color:var(--b-primary);"></i>
                <div>
                  <span class="v2-kicker">SKILL INTELLIGENCE CONSOLE</span>
                  <h3 style="margin:0;">Ask about ${dedicatedSkillState.askingSkill}</h3>
                </div>
              </div>
              <button type="button" class="v2-modal-close" id="closeAskSkillModalBtn"><i data-lucide="x"></i></button>
            </div>

            <div class="v2-modal-body">
              <p style="margin:0 0 12px 0; font-size:12.5px; color:#5C526A;">
                Query assistant for <strong>${dedicatedSkillState.askingSkill}</strong> in ${dashboardState.market}:
              </p>

              <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:14px;">
                <button type="button" class="quick-prompt-pill" data-run-ask-prompt="How can I improve my ${dedicatedSkillState.askingSkill} health score?">
                  <i data-lucide="help-circle"></i> How can I improve my ${dedicatedSkillState.askingSkill} health score?
                </button>
                <button type="button" class="quick-prompt-pill" data-run-ask-prompt="What top hiring employers in ${dashboardState.market} require ${dedicatedSkillState.askingSkill}?">
                  <i data-lucide="building"></i> What employers in ${dashboardState.market} require ${dedicatedSkillState.askingSkill}?
                </button>
                <button type="button" class="quick-prompt-pill" data-run-ask-prompt="Show me the half-life forecast and decay risk analysis for ${dedicatedSkillState.askingSkill}.">
                  <i data-lucide="trending-down"></i> Show half-life forecast & decay risks for ${dedicatedSkillState.askingSkill}.
                </button>
              </div>

              <div style="display:flex; gap:8px;">
                <input type="text" class="v2-modal-input" id="askSkillConsoleInput" value="Explain why ${dedicatedSkillState.askingSkill} is essential for ${dashboardState.market} roles." />
                <button type="button" class="button button--assistant" style="background:var(--b-primary); color:#FFF; flex-shrink:0;" id="sendAskSkillConsoleBtn">
                  Ask AI <i data-lucide="send"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      ` : ''}

      ${(dedicatedSkillState.viewingEvidenceIndex !== null && aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex]) ? `
        <div class="v2-modal-overlay" id="evidenceModalOverlay">
          <div class="v2-modal-container" style="max-width: 500px;">
            <div class="v2-modal-header">
              <div>
                <span class="v2-kicker">VERIFIED SOURCE RECORD</span>
                <h3>${aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].title}</h3>
              </div>
              <button type="button" class="v2-modal-close" id="closeEvidenceModalBtn"><i data-lucide="x"></i></button>
            </div>

            <div class="v2-modal-body">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding:8px 12px; background:#FAF9FC; border:1px solid #EBE7F2; border-radius:8px;">
                <span class="ev-source-badge ev-badge--${aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].typeBadgeClass || 'job'}">
                  ${aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].type}
                </span>
                <span style="font-size:11px; color:#7A7085;">${aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].date || 'Verified signal'}</span>
              </div>

              <p style="margin:0 0 14px 0; font-size:13px; color:#382E47; line-height:1.55;">
                ${aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].explanation || aiInsightData.evidenceList[dedicatedSkillState.viewingEvidenceIndex].text}
              </p>
            </div>

            <div class="v2-modal-footer">
              <button type="button" class="button button--secondary" id="closeEvidenceModalBtn2">Close evidence</button>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;

  lucide.createIcons();
  bindDedicatedSkillsEvents();
}

function bindDedicatedSkillsEvents() {
  // Sticky sub-navigation smooth scroll & active link handling
  const subnavLinks = document.querySelectorAll('.subnav-link');
  subnavLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-subnav-target');
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        subnavLinks.forEach(l => l.classList.remove('is-active'));
        link.classList.add('is-active');
        const offset = 80;
        const bodyRect = document.body.getBoundingClientRect().top;
        const elementRect = targetEl.getBoundingClientRect().top;
        const elementPosition = elementRect - bodyRect;
        const offsetPosition = elementPosition - offset;
        window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      }
    });
  });

  // IntersectionObserver for sticky subnav active state
  const sections = document.querySelectorAll('[data-skill-section]');
  if (sections.length > 0 && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const sectionId = entry.getAttribute ? entry.getAttribute('id') : entry.target.id;
          subnavLinks.forEach(l => {
            if (l.getAttribute('data-subnav-target') === sectionId) {
              l.classList.add('is-active');
            } else {
              l.classList.remove('is-active');
            }
          });
        }
      });
    }, { threshold: 0.25, rootMargin: '-70px 0px -40% 0px' });

    sections.forEach(sec => observer.observe(sec));
  }

  document.querySelectorAll('#dedicatedSkillMarketSelect, #marketSectionLocationSelect').forEach(select => {
    select?.addEventListener('change', (e) => {
      dashboardState.market = e.target.value;
      renderDedicatedSkillsPage();
    });
  });

  document.querySelector('#dedicatedSkillTimeSelect')?.addEventListener('change', (e) => {
    dashboardState.timeRange = e.target.value;
    renderDedicatedSkillsPage();
  });

  // Search input event
  const searchInput = document.querySelector('#currentSkillSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      dedicatedSkillState.searchQuery = e.target.value;
      renderDedicatedSkillsPage();
      const updatedInput = document.querySelector('#currentSkillSearchInput');
      if (updatedInput) {
        updatedInput.focus();
        updatedInput.setSelectionRange(updatedInput.value.length, updatedInput.value.length);
      }
    });
  }

  // Clear search
  document.querySelector('#clearSkillSearchBtn')?.addEventListener('click', () => {
    dedicatedSkillState.searchQuery = '';
    renderDedicatedSkillsPage();
  });

  // Sort select
  document.querySelector('#currentSkillSortSelect')?.addEventListener('change', (e) => {
    dedicatedSkillState.sortBy = e.target.value;
    renderDedicatedSkillsPage();
  });

  // Filter pills
  document.querySelectorAll('[data-skill-filter]').forEach(pill => {
    pill.addEventListener('click', () => {
      dedicatedSkillState.filterBy = pill.dataset.skillFilter;
      renderDedicatedSkillsPage();
    });
  });

  // Reset filters
  document.querySelector('#resetSkillFiltersBtn')?.addEventListener('click', () => {
    dedicatedSkillState.searchQuery = '';
    dedicatedSkillState.filterBy = 'all';
    renderDedicatedSkillsPage();
  });

  // Level edit select
  document.querySelectorAll('[data-edit-skill-level]').forEach(select => {
    select.addEventListener('click', (e) => e.stopPropagation());
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const skillId = select.dataset.editSkillLevel;
      const targetSkill = dedicatedSkillIntelligenceData.skills.find(s => s.id === skillId);
      if (targetSkill) {
        targetSkill.level = select.value;
        if (dashboardState.selectedSkill.toLowerCase() === targetSkill.name.toLowerCase()) {
          renderDedicatedSkillsPage();
        }
      }
    });
  });

  // Skill row selection
  document.querySelectorAll('[data-select-dedicated-skill]').forEach(item => {
    item.addEventListener('click', () => {
      dashboardState.selectedSkill = item.dataset.selectDedicatedSkill;
      renderDedicatedSkillsPage();
      if (window.innerWidth < 1024) {
        document.querySelector('.selected-skill-surface')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Save selected skill button
  document.querySelector('#saveSelectedSkillBtn')?.addEventListener('click', () => {
    const skill = dashboardState.selectedSkill || 'Machine Learning';
    const saved = dashboardState.savedSkills.includes(skill);
    dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(s => s !== skill) : [...dashboardState.savedSkills, skill];
    localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    renderDedicatedSkillsPage();
  });

  // Open Add Skill Modal
  document.querySelector('#openAddSkillModalBtn')?.addEventListener('click', () => {
    dedicatedSkillState.isAddingSkill = true;
    renderDedicatedSkillsPage();
  });

  // Close / Cancel Add Skill Modal
  document.querySelectorAll('#closeAddSkillModalBtn, #cancelAddSkillModalBtn').forEach(btn => {
    btn.addEventListener('click', () => {
      dedicatedSkillState.isAddingSkill = false;
      renderDedicatedSkillsPage();
    });
  });

  // Confirm Add Skill
  document.querySelector('#confirmAddSkillModalBtn')?.addEventListener('click', () => {
    const nameInput = document.querySelector('#newSkillNameInput')?.value.trim();
    if (!nameInput) return;
    const category = document.querySelector('#newSkillCategorySelect')?.value || 'AI & Data';
    const level = document.querySelector('#newSkillLevelSelect')?.value || 'Intermediate';

    const newSkill = {
      id: 'skill-' + Date.now(),
      name: nameInput,
      category: category,
      level: level,
      health: 82,
      relevance: 88,
      halfLifeYears: 3.5,
      decayRisk: 'Moderate Risk',
      growth: 16.4,
      direction: 'up',
      status: 'healthy',
      lastUpdated: 'Just now',
      icon: category === 'Programming' ? 'code-2' : category === 'Infrastructure' ? 'cloud' : category === 'Frontend' ? 'layout' : category === 'Security' ? 'shield-check' : 'cpu',
      history: [45, 52, 60, 68, 75, 80, 84],
      aiExplanation: `${nameInput} is a newly added skill in your ${category} portfolio with solid market relevance and positive growth trajectory.`,
      missingSkills: [`Advanced ${nameInput}`, 'System Architecture'],
      adjacentSkills: ['Python', 'Cloud Computing', 'SQL'],
      requiredInRoles: ['Senior Engineer', 'Specialist'],
      gapSeverity: 'Low',
      techVelocity: 80,
      jobDemandCount: 15200,
      topLocations: [dashboardState.market || 'Global'],
      evidence: [{ type: 'Job Signal', text: `15,200 open role requisitions request ${nameInput} capabilities.` }]
    };

    dedicatedSkillIntelligenceData.skills.unshift(newSkill);
    if (!dashboardState.savedSkills.includes(nameInput)) {
      dashboardState.savedSkills.push(nameInput);
      localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    }
    dashboardState.selectedSkill = nameInput;
    dedicatedSkillState.isAddingSkill = false;
    renderDedicatedSkillsPage();
  });

  document.querySelector('#btnAskAboutThisSkill')?.addEventListener('click', (e) => {
    const skill = e.currentTarget.dataset.skill;
    dedicatedSkillState.askingSkill = skill;
    renderDedicatedSkillsPage();
  });

  document.querySelector('#closeAskSkillModalBtn')?.addEventListener('click', () => {
    dedicatedSkillState.askingSkill = null;
    renderDedicatedSkillsPage();
  });

  document.querySelectorAll('[data-run-ask-prompt]').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.querySelector('#askSkillConsoleInput');
      if (input) {
        input.value = btn.dataset.runAskPrompt;
      }
    });
  });

  document.querySelector('#sendAskSkillConsoleBtn')?.addEventListener('click', () => {
    const query = document.querySelector('#askSkillConsoleInput')?.value.trim();
    if (query) {
      alert(`Query submitted to Skill Intelligence Assistant:\n\n"${query}"\n\n(AI Assistant Console Active)`);
      dedicatedSkillState.askingSkill = null;
      renderDedicatedSkillsPage();
    }
  });

  document.querySelectorAll('[data-view-evidence-index]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      dedicatedSkillState.viewingEvidenceIndex = Number(btn.dataset.viewEvidenceIndex);
      renderDedicatedSkillsPage();
    });
  });

  document.querySelectorAll('#closeEvidenceModalBtn, #closeEvidenceModalBtn2').forEach(btn => {
    btn?.addEventListener('click', () => {
      dedicatedSkillState.viewingEvidenceIndex = null;
      renderDedicatedSkillsPage();
    });
  });

  document.querySelector('#btnNextActionExploreSkill')?.addEventListener('click', () => {
    document.querySelector('.selected-skill-surface, #dedicated-skills-workspace')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  document.querySelector('#btnNextActionTakeAssessment')?.addEventListener('click', (e) => {
    const skill = e.currentTarget.dataset.skill || 'this skill';
    alert(`Skill Assessment Initialized for ${skill}!\n\n15 adaptive evaluation questions have been generated to benchmark your proficiency.`);
  });

  document.querySelector('#btnNextActionBuildRoadmap')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const skill = e.currentTarget.dataset.skill || dashboardState.selectedSkill || 'Python';
    
    if (roadmapState && (roadmapState.status === 'active' || roadmapState.status === 'paused')) {
      const activeTitle = roadmapState.title || `${roadmapState.skill} — Roadmap`;
      if (confirm(`You currently have an active roadmap: "${activeTitle}".\n\nWould you like to preview a new roadmap for ${skill}? (Your active tracking roadmap will remain safe in Learning until you review and explicitly accept the new roadmap).`)) {
        roadmapState.skill = skill;
        roadmapState.title = `${skill} — Skill Advancement`;
        intelligenceExplorerState.isRoadmapPreviewing = true;
        window.location.hash = '/individual/home';
      }
    } else {
      roadmapState.skill = skill;
      roadmapState.title = `${skill} — Skill Advancement`;
      intelligenceExplorerState.isRoadmapPreviewing = true;
      window.location.hash = '/individual/home';
    }
  });

  document.querySelector('#dedicatedExploreGapBtn, #btnViewSkillGap')?.addEventListener('click', () => {
    document.querySelector('#section-gap, #dedicatedGapSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  document.querySelector('#btnExploreMarket')?.addEventListener('click', () => {
    document.querySelector('#section-market, #dedicatedMarketContextSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  document.querySelectorAll('#dedicatedBuildRoadmapBtn, #btnStartBuildRoadmap, #btnRefreshSkillRoadmap, .btn-refresh-skill, [data-build-roadmap-skill]').forEach(btn => {
    btn?.addEventListener('click', (e) => {
      e.stopPropagation();
      const skill = btn.dataset.buildRoadmapSkill;
      if (skill) {
        roadmapState.skill = skill;
        roadmapState.title = `${skill} — Skill Advancement`;
      }
      intelligenceExplorerState.isRoadmapPreviewing = true;
      window.location.hash = '/individual/home';
    });
  });

  // History Metric Tab Switching
  document.querySelectorAll('[data-history-metric]').forEach(btn => {
    btn.addEventListener('click', () => {
      dedicatedSkillState.historyMetric = btn.dataset.historyMetric;
      renderDedicatedSkillsPage();
    });
  });

  // History Time Range Pill Switching
  document.querySelectorAll('[data-history-time]').forEach(btn => {
    btn.addEventListener('click', () => {
      dedicatedSkillState.historyTimeRange = btn.dataset.historyTime;
      renderDedicatedSkillsPage();
    });
  });

  // History Event Pin Selection
  document.querySelectorAll('[data-history-event-id]').forEach(pin => {
    pin.addEventListener('click', (e) => {
      e.stopPropagation();
      dedicatedSkillState.selectedEventId = pin.dataset.historyEventId;
      renderDedicatedSkillsPage();
    });
  });

  // Close Event Breakdown Card
  document.querySelector('#closeEventBreakdownBtn')?.addEventListener('click', () => {
    dedicatedSkillState.selectedEventId = null;
    renderDedicatedSkillsPage();
  });
}

function renderPlaceholder(page) {
  mainContent.innerHTML = `<div class="page-header"><span class="eyebrow">${page.eyebrow}</span><h1>${page.title}</h1><p>${page.description}</p></div><section class="placeholder-card dashboard-card"><div class="placeholder-card__top"><div><h2>Workspace ready</h2><p>This route is connected to the Individual Portal shell and ready for its page-specific intelligence view.</p></div><span class="placeholder-icon"><i data-lucide="${page.icon}"></i></span></div></section>`;
  lucide.createIcons();
}

function renderPage() {
  const routePath = currentRoute().split('?')[0];
  let route = routePath;

  // Alias routes
  if (route === '/individual/market-intelligence' || route === '/individual/market') {
    route = '/individual/market-insights';
  }

  // Handle parameterized skill routes e.g. /individual/skills/python or /individual/skills/machine-learning
  if (routePath.startsWith('/individual/skills/')) {
    const rawSkillParam = routePath.replace('/individual/skills/', '').trim();
    if (rawSkillParam) {
      const normalizedParam = rawSkillParam.replace(/-/g, ' ').toLowerCase();
      const matchedSkill = dedicatedSkillIntelligenceData.skills.find(
        s => s.name.toLowerCase() === normalizedParam || s.id.toLowerCase() === rawSkillParam.toLowerCase()
      );
      if (matchedSkill) {
        dashboardState.selectedSkill = matchedSkill.name;
      } else {
        dashboardState.selectedSkill = rawSkillParam.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      }
    }
    route = '/individual/skills';
  }

  if (route === '/individual/job-intelligence' || route === '/individual/job-trend' || route === '/individual/jobs') {
    route = '/individual/career';
  }

  const page = routes[route] || routes['/individual/home'];
  document.title = `TalentScope.ai  —  ${route === '/individual/home' ? 'Home' : page.title}`;
  document.querySelector('#topbarContext').textContent = page.eyebrow;
  document.querySelectorAll('[data-route]').forEach(item => {
    const isTarget = item.dataset.route === route || item.dataset.route === routePath || (route === '/individual/skills' && item.dataset.route === '/individual/skills') || (route === '/individual/market-insights' && item.dataset.route === '/individual/market-insights') || (route === '/individual/career' && item.dataset.route === '/individual/career');
    item.classList.toggle('is-active', isTarget);
  });

  if (route === '/individual/home') renderHome();
  else if (route === '/individual/skills') renderDedicatedSkillsPage();
  else if (route === '/individual/market-insights') renderDedicatedMarketPage();
  else if (route === '/individual/career') renderDedicatedJobPage();
  else if (route === '/individual/saved') renderSavedPage();
  else renderPlaceholder(page);

  mainContent.focus({ preventScroll: true });
  closePopovers();
  closeMobileNav();
}

function setSidebarExpanded(expanded) {
  sidebar.classList.toggle('is-expanded', expanded);
  sidebarToggle.setAttribute('aria-expanded', String(expanded));
  sidebarToggle.setAttribute('aria-label', expanded ? 'Collapse sidebar' : 'Expand sidebar');
  sidebarToggle.setAttribute('title', expanded ? 'Collapse sidebar' : 'Expand sidebar');
  localStorage.setItem('talentscope-sidebar-expanded', String(expanded));
}

function closeMobileNav() { sidebar.classList.remove('is-mobile-open'); mobileScrim.classList.remove('is-visible'); mobileScrim.setAttribute('aria-hidden', 'true'); }
function openMobileNav() { sidebar.classList.add('is-mobile-open'); mobileScrim.classList.add('is-visible'); mobileScrim.setAttribute('aria-hidden', 'false'); }
function closePopovers() { profilePopover.hidden = true; notificationPopover.hidden = true; profileTrigger.setAttribute('aria-expanded', 'false'); notificationButton.setAttribute('aria-expanded', 'false'); }

function trendWindowForSkill(skill) {
  const values = contextSkillTrendData[skill]?.[dashboardState.market]?.[dashboardState.timeRange] || skillTrendData[skill] || [42, 48, 55, 61, 68, 73, 78];
  return values.slice(-6);
}

function trendDetailsForSkill(skill) {
  const values = trendWindowForSkill(skill);
  const skillIndex = Math.max(0, skillOptions.indexOf(skill));
  const liveShift = Math.round(Math.sin((liveTrendTick * .75) + skillIndex) * 2);
  values[values.length - 1] = Math.max(20, Math.min(96, values[values.length - 1] + liveShift));
  const current = values[values.length - 1];
  const previous = values[values.length - 2] || current;
  const growth = Math.max(1, Math.round(((current - previous) / Math.max(previous, 1)) * 100));
  const momentum = Math.max(1, current - (values[values.length - 4] || current));
  const score = Math.min(99, Math.round(current * .68 + growth * 2 + momentum * .3));
  return { skill, values, current, previous, growth, momentum, score, demand: current >= 80 ? 'High demand' : current >= 60 ? 'Growing demand' : 'Building demand' };
}

function trendingSkillsForView() {
  const sortMode = dashboardState.trendSort || 'Highest Growth';
  return skillOptions.map(trendDetailsForSkill).sort((first, second) => {
    if (sortMode === 'Highest Demand') return second.current - first.current;
    if (sortMode === 'Fastest Rising') return second.momentum - first.momentum;
    if (sortMode === 'Most Stable') return Math.abs(first.current - first.previous) - Math.abs(second.current - second.previous);
    if (sortMode === 'Recently Emerging') return (second.growth + (100 - second.values[0])) - (first.growth + (100 - first.values[0]));
    return second.growth - first.growth || second.score - first.score;
  }).slice(0, 5);
}

function renderTrendSparkline(points, label) {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const spread = Math.max(1, max - min);
  const coordinates = points.map((point, index) => `${(index / (points.length - 1)) * 100},${28 - ((point - min) / spread) * 21}`).join(' ');
  return `<svg class="trend-sparkline" viewBox="0 0 100 32" role="img" aria-label="${label} trend"><polyline points="${coordinates}" vector-effect="non-scaling-stroke"></polyline></svg>`;
}

function renderSkillDemandBars(details) {
  const labels = ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'];
  return `<div class="skill-demand-chart" role="img" aria-label="${details.skill} demand trend over the last six months"><div class="skill-demand-chart__axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="skill-demand-chart__plot"><div class="skill-demand-chart__grid"><i></i><i></i><i></i><i></i><i></i></div><div class="skill-demand-chart__bars">${details.values.map((value, index) => `<div class="skill-demand-bar" style="--demand-height:${value}%"><span>${value}</span><i></i><small>${labels[index]}</small></div>`).join('')}</div></div></div>`;
}

function renderSkillTrendAnalyticsCard() {
  const selected = trendDetailsForSkill(dashboardState.selectedSkill);
  const trendingSkills = trendingSkillsForView();
  const isFavorite = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
  const iconMap = { Python: 'code-2', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud' };
  return `<article class="skill-analytics-card" aria-labelledby="skill-analytics-title"><div class="skill-analytics-header"><div class="skill-analytics-title"><span class="skill-analytics-icon"><i data-lucide="activity"></i></span><div><div class="skill-analytics-heading"><h2 id="skill-analytics-title">Skill Trend</h2><span class="live-badge"><i></i>Live</span></div><p>Real-time skill demand signals across the globe.</p></div></div><div class="skill-analytics-controls"><label><span class="sr-only">Time range</span><select id="skillTrendTimeSelect"><option value="6 Months" ${dashboardState.timeRange === '6 Months' ? 'selected' : ''}>Last 6 Months</option><option value="90 Days" ${dashboardState.timeRange === '90 Days' ? 'selected' : ''}>Last 90 Days</option><option value="30 Days" ${dashboardState.timeRange === '30 Days' ? 'selected' : ''}>Last 30 Days</option></select><i data-lucide="calendar-days"></i></label><label><span class="sr-only">Geographic scope</span><select id="skillTrendMarketSelect">${optionMarkup(marketOptions, dashboardState.market)}</select><i data-lucide="globe-2"></i></label><button class="skill-favorite-button ${isFavorite ? 'is-saved' : ''}" id="favoriteSkillButton" type="button" aria-pressed="${isFavorite}"><i data-lucide="${isFavorite ? 'check' : 'plus'}"></i>${isFavorite ? 'Saved' : 'Add to Favorites'}</button><span class="favorite-count">(${dashboardState.savedSkills.length}/5)</span></div></div><div class="skill-analytics-summary"><div class="skill-analytics-current"><span class="skill-current-icon"><i data-lucide="${iconMap[selected.skill] || 'layers-3'}"></i></span><div><strong>${selected.skill}</strong><span>Current demand <b>${selected.current}/100</b></span></div></div><div class="skill-analytics-growth"><strong>+${selected.growth}%</strong><span><i data-lucide="trending-up"></i> ${selected.momentum} pts</span></div><span class="skill-demand-label">${selected.demand}</span></div>${renderSkillDemandBars(selected)}<div class="trending-skills-header"><div><h3>Top Trending Skills</h3><p>Ranked by current market momentum</p></div><label><span class="sr-only">Sort trending skills</span><select id="skillTrendSortSelect"><option ${dashboardState.trendSort === 'Highest Growth' || !dashboardState.trendSort ? 'selected' : ''}>Highest Growth</option><option ${dashboardState.trendSort === 'Highest Demand' ? 'selected' : ''}>Highest Demand</option><option ${dashboardState.trendSort === 'Fastest Rising' ? 'selected' : ''}>Fastest Rising</option><option ${dashboardState.trendSort === 'Most Stable' ? 'selected' : ''}>Most Stable</option><option ${dashboardState.trendSort === 'Recently Emerging' ? 'selected' : ''}>Recently Emerging</option></select><i data-lucide="list-filter"></i></label></div><div class="trending-skill-list">${trendingSkills.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span><span class="trending-skill-icon"><i data-lucide="${iconMap[item.skill] || 'layers-3'}"></i></span><strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}%</span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div></article>`;
}

function bindSkillTrendAnalyticsEvents() {
  const timeSelect = document.querySelector('#skillTrendTimeSelect');
  const marketSelect = document.querySelector('#skillTrendMarketSelect');
  const sortSelect = document.querySelector('#skillTrendSortSelect');
  const favoriteButton = document.querySelector('#favoriteSkillButton');
  if (timeSelect) timeSelect.addEventListener('change', event => { dashboardState.timeRange = event.target.value; renderHome(); });
  if (marketSelect) marketSelect.addEventListener('change', event => { dashboardState.market = event.target.value; renderHome(); });
  if (sortSelect) sortSelect.addEventListener('change', event => { dashboardState.trendSort = event.target.value; renderHome(); });
  if (favoriteButton) favoriteButton.addEventListener('click', () => {
    const saved = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
    if (saved) dashboardState.savedSkills = dashboardState.savedSkills.filter(skill => skill !== dashboardState.selectedSkill);
    else if (dashboardState.savedSkills.length < 5) dashboardState.savedSkills = [...dashboardState.savedSkills, dashboardState.selectedSkill];
    localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    renderHome();
  });
}

function renderSkillDemandBars(details) {
  const labels = ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'];
  return `<div class="skill-demand-chart" role="img" aria-label="${details.skill} demand trend over the last six months"><div class="skill-demand-chart__axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="skill-demand-chart__plot"><div class="skill-demand-chart__grid"><i></i><i></i><i></i><i></i><i></i></div><div class="skill-demand-chart__bars">${details.values.map((value, index) => `<div class="skill-demand-bar" style="--demand-height:${value}%; --bar-delay:${index * 55}ms"><span>${value}</span><i></i><small>${labels[index]}</small><em class="skill-demand-tooltip"><strong>${details.skill}</strong><b>${value}/100 demand</b><span>${labels[index]}  —  ${details.demand}</span></em></div>`).join('')}</div></div></div>`;
}

function trendingSkillsForView() {
  const sortMode = dashboardState.trendSort || 'Highest Growth';
  const sourceSkills = ['My Saved Skills', 'Saved Skills'].includes(dashboardState.trendScope) && dashboardState.savedSkills.length ? dashboardState.savedSkills : skillOptions;
  return sourceSkills.map(trendDetailsForSkill).sort((first, second) => {
    if (sortMode === 'Highest Demand') return second.current - first.current;
    if (sortMode === 'Fastest Rising') return second.momentum - first.momentum;
    if (sortMode === 'Most Stable') return Math.abs(first.current - first.previous) - Math.abs(second.current - second.previous);
    if (sortMode === 'Recently Emerging') return (second.growth + (100 - second.values[0])) - (first.growth + (100 - first.values[0]));
    return second.growth - first.growth || second.score - first.score;
  }).slice(0, 5);
}

function renderSkillTrendAnalyticsCard() {
  const selected = trendDetailsForSkill(dashboardState.selectedSkill);
  const trendingSkills = trendingSkillsForView();
  const isFavorite = dashboardState.savedSkills.includes(dashboardState.selectedSkill);
  const iconMap = { Python: 'code-2', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud' };
  return `<article class="skill-analytics-card" aria-labelledby="skill-analytics-title"><div class="skill-analytics-header"><div class="skill-analytics-title"><span class="skill-analytics-icon"><i data-lucide="activity"></i></span><div><div class="skill-analytics-heading"><h2 id="skill-analytics-title">Skill Trend</h2><span class="live-badge"><i></i>Live</span></div><p>Real-time skill demand signals across the globe.</p></div></div><div class="skill-analytics-controls"><div class="skill-filter-wrap"><button class="skill-filter-button" id="skillFilterButton" type="button" aria-expanded="false"><i data-lucide="sliders-horizontal"></i>Filters</button><div class="skill-filter-panel" id="skillFilterPanel" hidden><div class="skill-filter-panel__heading"><strong>Trend filters</strong><small>Global live intelligence</small></div><label>Time range<select id="skillFilterTime"><option value="7 Days">Last 7 Days</option><option value="30 Days">Last 30 Days</option><option value="90 Days">Last 90 Days</option><option value="6 Months" selected>Last 6 Months</option><option value="1 Year">Last Year</option></select></label><label>Geographic scope<select id="skillFilterMarket">${optionMarkup(marketOptions, dashboardState.market)}</select></label><label>Trending view<select id="skillFilterScope"><option>Overall Live Trends</option><option ${dashboardState.trendScope === 'My Saved Skills' ? 'selected' : ''}>My Saved Skills</option></select></label><label class="custom-date-field">Custom date<input id="skillCustomDate" type="date"></label><button class="skill-filter-favorite ${isFavorite ? 'is-saved' : ''}" id="filterFavoriteButton" type="button"><i data-lucide="${isFavorite ? 'check' : 'star'}"></i>${isFavorite ? 'Saved to favorites' : 'Add current skill to favorites'}</button></div></div><span class="favorite-count">${dashboardState.savedSkills.length}/5 saved</span></div></div><div class="skill-analytics-summary"><div class="skill-analytics-current"><span class="skill-current-icon"><i data-lucide="${iconMap[selected.skill] || 'layers-3'}"></i></span><div><strong>${selected.skill}</strong><span>Current demand <b>${selected.current}/100</b></span></div></div><div class="skill-analytics-growth"><strong>+${selected.growth}%</strong><span><i data-lucide="trending-up"></i> ${selected.momentum} pts</span></div><span class="skill-demand-label">${selected.demand}</span></div>${renderSkillDemandBars(selected)}<div class="trending-skills-header"><div><h3>Top Trending Skills</h3><p>Ranked by current market momentum</p></div><label><span class="sr-only">Sort trending skills</span><select id="skillTrendSortSelect"><option ${dashboardState.trendSort === 'Highest Growth' || !dashboardState.trendSort ? 'selected' : ''}>Highest Growth</option><option ${dashboardState.trendSort === 'Highest Demand' ? 'selected' : ''}>Highest Demand</option><option ${dashboardState.trendSort === 'Fastest Rising' ? 'selected' : ''}>Fastest Rising</option><option ${dashboardState.trendSort === 'Most Stable' ? 'selected' : ''}>Most Stable</option><option ${dashboardState.trendSort === 'Recently Emerging' ? 'selected' : ''}>Recently Emerging</option></select><i data-lucide="list-filter"></i></label></div><div class="trending-skill-list">${trendingSkills.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span><span class="trending-skill-icon"><i data-lucide="${iconMap[item.skill] || 'layers-3'}"></i></span><strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}%</span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div></article>`;
}

function bindSkillTrendAnalyticsEvents() {
  const filterButton = document.querySelector('#skillFilterButton');
  const filterPanel = document.querySelector('#skillFilterPanel');
  const timeSelect = document.querySelector('#skillFilterTime');
  const marketSelect = document.querySelector('#skillFilterMarket');
  const scopeSelect = document.querySelector('#skillFilterScope');
  const sortSelect = document.querySelector('#skillTrendSortSelect');
  const favoriteButton = document.querySelector('#filterFavoriteButton');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (timeSelect) timeSelect.addEventListener('change', event => { dashboardState.timeRange = event.target.value; renderHome(); });
  if (marketSelect) marketSelect.addEventListener('change', event => { dashboardState.market = event.target.value; renderHome(); });
  if (scopeSelect) scopeSelect.addEventListener('change', event => { dashboardState.trendScope = event.target.value === 'My Saved Skills' ? 'My Saved Skills' : 'Overall Live Trends'; renderHome(); });
  if (sortSelect) sortSelect.addEventListener('change', event => { dashboardState.trendSort = event.target.value; renderHome(); });
  if (favoriteButton) favoriteButton.addEventListener('click', () => { const saved = dashboardState.savedSkills.includes(dashboardState.selectedSkill); dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(skill => skill !== dashboardState.selectedSkill) : dashboardState.savedSkills.length < 5 ? [...dashboardState.savedSkills, dashboardState.selectedSkill] : dashboardState.savedSkills; localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills)); renderHome(); });
}

function renderTopTrendingSkillsCard() {
  const trends = getFilteredSkillTrends().slice(0, 5);
  const iconMap = { Python: 'code-2', Java: 'coffee', JavaScript: 'braces', TypeScript: 'braces', React: 'atom', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud', AWS: 'cloud-cog', Docker: 'container', SQL: 'database' };
  const sortMode = dashboardState.trendSort || 'Highest Growth';
  const options = ['Highest Growth', 'Highest Demand', 'Fastest Rising', 'Most Stable', 'Recently Emerging'];
  return `<article class="top-trending-card"><div class="top-trending-card__header"><div><h2>Top Trending Skills</h2><p>Ranked by current market momentum</p></div><div class="trend-sort-wrap"><button class="trend-sort-button" id="skillTrendSortButton" type="button" aria-expanded="false"><i data-lucide="list-filter"></i>${sortMode}<i data-lucide="chevron-down"></i></button><div class="trend-sort-menu" id="skillTrendSortMenu" hidden>${options.map(option => `<button type="button" data-sort-mode="${option}" class="${option === sortMode ? 'is-active' : ''}">${option}<i data-lucide="${option === sortMode ? 'check' : 'arrow-up-right'}"></i></button>`).join('')}</div></div></div><div class="trending-skill-list">${trends.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span><span class="trending-skill-icon"><i data-lucide="${iconMap[item.skill] || 'layers-3'}"></i></span><strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}% <small>${item.demand}</small></span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div></article>`;
}

function bindSkillTrendAnalyticsEvents() {
  const filterButton = document.querySelector('#skillFilterButton');
  const filterPanel = document.querySelector('#skillFilterPanel');
  const timeSelect = document.querySelector('#skillFilterTime');
  const marketSelect = document.querySelector('#skillFilterMarket');
  const scopeSelect = document.querySelector('#skillFilterScope');
  const sortButton = document.querySelector('#skillTrendSortButton');
  const sortMenu = document.querySelector('#skillTrendSortMenu');
  const favoriteButton = document.querySelector('#filterFavoriteButton');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); if (sortMenu) sortMenu.hidden = true; filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (sortButton && sortMenu) sortButton.addEventListener('click', event => { event.stopPropagation(); if (filterPanel) filterPanel.hidden = true; sortMenu.hidden = !sortMenu.hidden; sortButton.setAttribute('aria-expanded', String(!sortMenu.hidden)); });
  if (sortMenu) sortMenu.querySelectorAll('[data-sort-mode]').forEach(option => option.addEventListener('click', () => { dashboardState.trendSort = option.dataset.sortMode; renderHome(); }));
  if (timeSelect) timeSelect.addEventListener('change', event => { dashboardState.timeRange = event.target.value; renderHome(); });
  if (marketSelect) marketSelect.addEventListener('change', event => { dashboardState.market = event.target.value; renderHome(); });
  if (scopeSelect) scopeSelect.addEventListener('change', event => { dashboardState.trendScope = event.target.value === 'My Saved Skills' ? 'My Saved Skills' : 'Overall Live Trends'; renderHome(); });
  if (favoriteButton) favoriteButton.addEventListener('click', () => { const saved = dashboardState.savedSkills.includes(dashboardState.selectedSkill); dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(skill => skill !== dashboardState.selectedSkill) : dashboardState.savedSkills.length < 5 ? [...dashboardState.savedSkills, dashboardState.selectedSkill] : dashboardState.savedSkills; localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills)); renderHome(); });
}

function getFilteredSkillTrends() {
  const sourceSkills = ['My Saved Skills', 'Saved Skills'].includes(dashboardState.trendScope) && dashboardState.savedSkills.length ? dashboardState.savedSkills : skillOptions;
  return sourceSkills.map(trendDetailsForSkill).sort((first, second) => {
    const sortMode = dashboardState.trendSort || 'Highest Growth';
    if (sortMode === 'Highest Demand') return second.current - first.current;
    if (sortMode === 'Fastest Rising') return second.momentum - first.momentum;
    if (sortMode === 'Most Stable') return Math.abs(first.current - first.previous) - Math.abs(second.current - second.previous);
    if (sortMode === 'Recently Emerging') return (second.growth + (100 - second.values[0])) - (first.growth + (100 - first.values[0]));
    return second.growth - first.growth || second.score - first.score;
  });
}

function renderSkillDemandBars(details) {
  const skills = Array.isArray(details) ? details.slice(0, 5) : getFilteredSkillTrends().slice(0, 5);
  return `<div class="skill-demand-chart skill-demand-chart--multi" role="img" aria-label="Multi-skill live demand comparison"><div class="skill-demand-chart__axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="skill-demand-chart__plot"><div class="skill-demand-chart__grid"><i></i><i></i><i></i><i></i><i></i></div><div class="skill-demand-chart__bars">${skills.map((item, index) => `<div class="skill-demand-group" style="--bar-delay:${index * 70}ms"><div class="skill-demand-bar" style="--demand-height:${item.current}%"><span class="skill-demand-bar__value">${item.current}</span><i></i><small>${item.skill}</small><em class="skill-demand-tooltip"><strong>${item.skill}</strong><b>Demand ${item.current}/100</b><span>Growth +${item.growth}%  —  ${item.demand}</span><span>Change +${item.momentum} pts  —  Related market skills</span></em></div></div>`).join('')}</div></div></div>`;
}

function renderSkillTrendAnalyticsCard() {
  const trends = getFilteredSkillTrends();
  const highlighted = trends.find(item => item.skill === dashboardState.selectedSkill) || trendDetailsForSkill(dashboardState.selectedSkill || 'Machine Learning');
  const isFavorite = dashboardState.savedSkills.includes(highlighted.skill);
  const iconMap = { Python: 'code-2', Java: 'coffee', JavaScript: 'braces', TypeScript: 'braces', React: 'atom', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud', AWS: 'cloud-cog', Docker: 'container', SQL: 'database' };
  return `<article class="skill-analytics-card" aria-labelledby="skill-analytics-title"><div class="skill-analytics-header"><div class="skill-analytics-title"><span class="skill-analytics-icon"><i data-lucide="activity"></i></span><div><div class="skill-analytics-heading"><h2 id="skill-analytics-title">Skill Trend</h2><span class="live-badge"><i></i>Live</span></div><p>Real-time skill demand signals across the globe.</p></div></div><div class="skill-analytics-controls"><div class="skill-filter-wrap"><button class="skill-filter-button" id="skillFilterButton" type="button" aria-expanded="false"><i data-lucide="sliders-horizontal"></i>Filters</button><div class="skill-filter-panel" id="skillFilterPanel" hidden><div class="skill-filter-panel__heading"><strong>Trend filters</strong><small>Global live intelligence</small></div><label>Time range<select id="skillFilterTime"><option value="7 Days">Last 7 Days</option><option value="30 Days">Last 30 Days</option><option value="6 Months" ${dashboardState.timeRange === '6 Months' ? 'selected' : ''}>Last 6 Months</option><option value="1 Year">Last 1 Year</option></select></label><label>Time granularity<select id="skillFilterGranularity"><option>Month</option><option>Day</option><option>Year</option></select></label><label>Geographic scope<select id="skillFilterMarket">${optionMarkup(marketOptions, dashboardState.market)}</select></label><label>Trending view<select id="skillFilterScope"><option selected>All Skills</option><option ${dashboardState.trendScope === 'My Saved Skills' ? 'selected' : ''}>My Saved Skills</option></select></label><label>Custom date/range<input id="skillCustomDate" type="date"></label><button class="skill-filter-favorite ${isFavorite ? 'is-saved' : ''}" id="filterFavoriteButton" type="button" ${!isFavorite && dashboardState.savedSkills.length >= 5 ? 'disabled' : ''}><i data-lucide="${isFavorite ? 'check' : 'star'}"></i>${isFavorite ? 'Saved to favorites' : dashboardState.savedSkills.length >= 5 ? '5 skill limit reached' : 'Add highlighted skill'}</button></div></div><span class="favorite-count">${dashboardState.savedSkills.length}/5 saved</span></div></div><div class="skill-analytics-summary"><div class="skill-analytics-current"><span class="skill-current-icon"><i data-lucide="${iconMap[highlighted.skill] || 'layers-3'}"></i></span><div><strong>${highlighted.skill}</strong><span>Demand <b>${highlighted.current}/100</b></span></div></div><div class="skill-analytics-growth"><strong>+${highlighted.growth}%</strong><span><i data-lucide="trending-up"></i> ${highlighted.momentum} pts</span></div><span class="skill-demand-label">${highlighted.demand}</span></div>${renderSkillDemandBars(trends)}<div class="skill-analytics-footnote"><span><i data-lucide="radio"></i> Updated just now</span><span>Hover a bar for market detail</span></div></article>`;
}

function renderTopTrendingSkillsCard() {
  const trends = getFilteredSkillTrends().slice(0, 5);
  const iconMap = { Python: 'code-2', Java: 'coffee', JavaScript: 'braces', TypeScript: 'braces', React: 'atom', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud', AWS: 'cloud-cog', Docker: 'container', SQL: 'database' };
  return `<article class="top-trending-card"><div class="top-trending-card__header"><div><h2>Top Trending Skills</h2><p>Ranked by current market momentum</p></div><label><span class="sr-only">Sort trending skills</span><select id="skillTrendSortSelect"><option ${dashboardState.trendSort === 'Highest Growth' ? 'selected' : ''}>Highest Growth</option><option ${dashboardState.trendSort === 'Highest Demand' ? 'selected' : ''}>Highest Demand</option><option ${dashboardState.trendSort === 'Fastest Rising' ? 'selected' : ''}>Fastest Rising</option><option ${dashboardState.trendSort === 'Most Stable' ? 'selected' : ''}>Most Stable</option><option ${dashboardState.trendSort === 'Recently Emerging' ? 'selected' : ''}>Recently Emerging</option></select><i data-lucide="list-filter"></i></label></div><div class="trending-skill-list">${trends.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span><span class="trending-skill-icon"><i data-lucide="${iconMap[item.skill] || 'layers-3'}"></i></span><strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}% <small>${item.demand}</small></span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div></article>`;
}

function renderMarketPulse() {
  return `<section class="skill-demand-module"><div class="skill-trend-stack">${renderSkillTrendAnalyticsCard()}${renderTopTrendingSkillsCard()}</div></section>`;
}

function bindSkillTrendAnalyticsEvents() {
  const filterButton = document.querySelector('#skillFilterButton');
  const filterPanel = document.querySelector('#skillFilterPanel');
  const timeSelect = document.querySelector('#skillFilterTime');
  const marketSelect = document.querySelector('#skillFilterMarket');
  const scopeSelect = document.querySelector('#skillFilterScope');
  const sortSelect = document.querySelector('#skillTrendSortSelect');
  const favoriteButton = document.querySelector('#filterFavoriteButton');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (timeSelect) timeSelect.addEventListener('change', event => { dashboardState.timeRange = event.target.value; renderHome(); });
  if (marketSelect) marketSelect.addEventListener('change', event => { dashboardState.market = event.target.value; renderHome(); });
  if (scopeSelect) scopeSelect.addEventListener('change', event => { dashboardState.trendScope = event.target.value === 'My Saved Skills' ? 'My Saved Skills' : 'Overall Live Trends'; renderHome(); });
  if (sortSelect) sortSelect.addEventListener('change', event => { dashboardState.trendSort = event.target.value; renderHome(); });
  if (favoriteButton) favoriteButton.addEventListener('click', () => { const saved = dashboardState.savedSkills.includes(dashboardState.selectedSkill); dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(skill => skill !== dashboardState.selectedSkill) : dashboardState.savedSkills.length < 5 ? [...dashboardState.savedSkills, dashboardState.selectedSkill] : dashboardState.savedSkills; localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills)); renderHome(); });
}

renderTopTrendingSkillsCard = function() {
  const trends = getFilteredSkillTrends().slice(0, 5);
  const iconMap = { Python: 'code-2', Java: 'coffee', JavaScript: 'braces', TypeScript: 'braces', React: 'atom', 'Machine Learning': 'brain-circuit', 'Generative AI': 'sparkles', 'Data Analytics': 'chart-no-axes-combined', 'Cloud Computing': 'cloud', AWS: 'cloud-cog', Docker: 'container', SQL: 'database' };
  const sortMode = dashboardState.trendSort || 'Highest Growth';
  const options = ['Highest Growth', 'Highest Demand', 'Fastest Rising', 'Most Stable', 'Recently Emerging'];
  return `<article class="top-trending-card"><div class="top-trending-card__header"><div><h2>Top Trending Skills</h2><p>Ranked by current market momentum</p></div><div class="trend-sort-wrap"><button class="trend-sort-button" id="skillTrendSortButton" type="button" aria-expanded="false"><i data-lucide="list-filter"></i>${sortMode}<i data-lucide="chevron-down"></i></button><div class="trend-sort-menu" id="skillTrendSortMenu" hidden>${options.map(option => `<button type="button" data-sort-mode="${option}" class="${option === sortMode ? 'is-active' : ''}">${option}<i data-lucide="${option === sortMode ? 'check' : 'arrow-up-right'}"></i></button>`).join('')}</div></div></div><div class="trending-skill-columns" aria-hidden="true"><span>#</span><span></span><span>Skill</span><span>Growth</span><span>Demand</span><span>Momentum</span><span>Mini trend</span></div><div class="trending-skill-list">${trends.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span><span class="trending-skill-icon"><i data-lucide="${iconMap[item.skill] || 'layers-3'}"></i></span><strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}% <small>${item.demand}</small></span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div><a class="top-trending-card__footer" href="#/individual/skills">View All Skills <span>&rarr;</span></a></article>`;
};
bindSkillTrendAnalyticsEvents = function() {
  const filterButton = document.querySelector('#skillFilterButton');
  const filterPanel = document.querySelector('#skillFilterPanel');
  const timeSelect = document.querySelector('#skillFilterTime');
  const marketSelect = document.querySelector('#skillFilterMarket');
  const scopeSelect = document.querySelector('#skillFilterScope');
  const sortButton = document.querySelector('#skillTrendSortButton');
  const sortMenu = document.querySelector('#skillTrendSortMenu');
  const favoriteButton = document.querySelector('#filterFavoriteButton');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); if (sortMenu) sortMenu.hidden = true; filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (sortButton && sortMenu) sortButton.addEventListener('click', event => { event.stopPropagation(); if (filterPanel) filterPanel.hidden = true; sortMenu.hidden = !sortMenu.hidden; sortButton.setAttribute('aria-expanded', String(!sortMenu.hidden)); });
  if (sortMenu) sortMenu.querySelectorAll('[data-sort-mode]').forEach(option => option.addEventListener('click', () => { dashboardState.trendSort = option.dataset.sortMode; renderHome(); }));
  if (timeSelect) timeSelect.addEventListener('change', event => { dashboardState.timeRange = event.target.value; renderHome(); });
  if (marketSelect) marketSelect.addEventListener('change', event => { dashboardState.market = event.target.value; renderHome(); });
  if (scopeSelect) scopeSelect.addEventListener('change', event => { dashboardState.trendScope = event.target.value === 'My Saved Skills' ? 'My Saved Skills' : 'Overall Live Trends'; renderHome(); });
  if (favoriteButton) favoriteButton.addEventListener('click', () => { const saved = dashboardState.savedSkills.includes(dashboardState.selectedSkill); dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(skill => skill !== dashboardState.selectedSkill) : dashboardState.savedSkills.length < 5 ? [...dashboardState.savedSkills, dashboardState.selectedSkill] : dashboardState.savedSkills; localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills)); renderHome(); });
};
renderSkillDemandBars = function(details) {
  const skills = Array.isArray(details) ? details.slice(0, 5) : getFilteredSkillTrends().slice(0, 5);
  return `<div class="skill-demand-chart skill-demand-chart--multi" role="img" aria-label="Multi-skill live demand comparison"><div class="skill-demand-chart__axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="skill-demand-chart__plot"><div class="skill-demand-chart__bars">${skills.map((item, index) => `<div class="skill-demand-group" style="--bar-delay:${index * 70}ms"><div class="skill-demand-bar" style="--demand-height:${item.current}%"><span class="skill-demand-bar__value">${item.current}</span><i></i><small>${item.skill}</small><em class="skill-demand-tooltip"><strong>${item.skill}</strong><b>+${item.growth}% Growing</b></em></div></div>`).join('')}</div></div></div>`;
};
function skillLogoMarkup(skill) {
  const logos = { Python: ['python', '3776AB', 'Py'], Java: ['openjdk', '437291', 'J'], JavaScript: ['javascript', 'F7DF1E', 'JS'], TypeScript: ['typescript', '3178C6', 'TS'], React: ['react', '61DAFB', 'R'], AWS: ['amazonaws', '232F3E', 'AWS'], Azure: ['microsoftazure', '0078D4', 'AZ'], Docker: ['docker', '2496ED', 'DK'], Kubernetes: ['kubernetes', '326CE5', 'K8s'], SQL: ['postgresql', '4169E1', 'SQL'], 'Cloud Computing': ['icloud', '3693F3', 'CC'], 'Machine Learning': ['tensorflow', 'FF6F00', 'ML'], 'Generative AI': ['openai', '412991', 'AI'], AI: ['openai', '412991', 'AI'], 'AI Agents': ['openai', '412991', 'AG'], Cybersecurity: ['owasp', '000000', 'CS'], 'Data Analytics': ['databricks', 'FF3621', 'DA'], 'Data Engineering': ['apacheairflow', '017CEE', 'DE'], 'Node.js': ['nodedotjs', '5FA04E', 'N'], Git: ['git', 'F05032', 'Git'], Linux: ['linux', 'FCC624', 'Lx'] };
  const [slug, color, fallback] = logos[skill] || [null, '8B25D4', ' — '];
  return `<span class="skill-logo skill-logo--${skill.toLowerCase().replace(/[^a-z0-9]+/g, '-')}" aria-label="${skill} logo"><span class="skill-logo__fallback">${fallback}</span>${slug ? `<img class="skill-logo__image" src="https://cdn.simpleicons.org/${slug}/${color}" alt="" onerror="this.style.display='none'">` : ''}</span>`;
}
renderTopTrendingSkillsCard = function() {
  const trends = getFilteredSkillTrends().slice(0, 5);
  const sortMode = dashboardState.trendSort || 'Highest Growth';
  const options = ['Highest Growth', 'Highest Demand', 'Fastest Rising', 'Most Stable', 'Recently Emerging'];
  return `<article class="top-trending-card"><div class="top-trending-card__header"><div><h2>Top Trending Skills</h2><p>Ranked by current market momentum</p></div><div class="trend-sort-wrap"><button class="trend-sort-button" id="skillTrendSortButton" type="button" aria-expanded="false"><i data-lucide="list-filter"></i>${sortMode}<i data-lucide="chevron-down"></i></button><div class="trend-sort-menu" id="skillTrendSortMenu" hidden>${options.map(option => `<button type="button" data-sort-mode="${option}" class="${option === sortMode ? 'is-active' : ''}">${option}<i data-lucide="${option === sortMode ? 'check' : 'arrow-up-right'}"></i></button>`).join('')}</div></div></div><div class="trending-skill-columns" aria-hidden="true"><span>#</span><span></span><span>Skill</span><span>Growth</span><span>Demand</span><span>Momentum</span><span>Mini trend</span></div><div class="trending-skill-list">${trends.map((item, index) => `<div class="trending-skill-row" style="--row-delay:${index * 55}ms"><span class="trending-skill-rank">${index + 1}.</span>${skillLogoMarkup(item.skill)}<strong>${item.skill}</strong><span class="trending-skill-growth"><i data-lucide="trending-up"></i> +${item.growth}%</span><span class="trending-skill-status">${item.demand}</span><span class="trending-skill-score">${item.current}/100</span>${renderTrendSparkline(item.values, `${item.skill} demand`)}</div>`).join('')}</div><a class="top-trending-card__footer" href="#/individual/skills">View All Skills <span>&rarr;</span></a></article>`;
};
skillLogoMarkup = function(skill) {
  const logos = { Python: ['python', '3776AB', 'Py'], Java: ['openjdk', '437291', 'J'], JavaScript: ['javascript', 'F7DF1E', 'JS'], TypeScript: ['typescript', '3178C6', 'TS'], React: ['react', '61DAFB', 'R'], AWS: ['amazonaws', '232F3E', 'AWS'], Azure: ['microsoftazure', '0078D4', 'AZ'], Docker: ['docker', '2496ED', 'DK'], Kubernetes: ['kubernetes', '326CE5', 'K8s'], SQL: ['postgresql', '4169E1', 'SQL'], 'Cloud Computing': ['icloud', '3693F3', 'CC'], 'Machine Learning': ['tensorflow', 'FF6F00', 'ML'], 'Generative AI': ['openai', '412991', 'AI'], AI: ['openai', '412991', 'AI'], 'AI Agents': ['openai', '412991', 'AG'], Cybersecurity: ['owasp', '000000', 'CS'], 'Data Analytics': ['databricks', 'FF3621', 'DA'], 'Data Engineering': ['apacheairflow', '017CEE', 'DE'], 'Node.js': ['nodedotjs', '5FA04E', 'N'], Git: ['git', 'F05032', 'Git'], Linux: ['linux', 'FCC624', 'Lx'] };
  const [slug, color, fallback] = logos[skill] || [null, '8B25D4', ' — '];
  return `<span class="skill-logo skill-logo--${skill.toLowerCase().replace(/[^a-z0-9]+/g, '-')}" aria-label="${skill} logo"><span class="skill-logo__fallback" ${slug ? 'hidden' : ''}>${fallback}</span>${slug ? `<img class="skill-logo__image" src="https://cdn.simpleicons.org/${slug}/${color}" alt="${skill} logo" onerror="this.hidden=true; this.previousElementSibling.hidden=false">` : ''}</span>`;
};
renderTrendSparkline = function(points, label) {
  const skillName = label.replace(/ demand$/, '');
  const skillIndex = Math.max(0, skillOptions.indexOf(skillName));
  const profile = skillIndex % 3;
  const visualPoints = points.map((point, index) => profile === 1 ? point + ((points.length - index) * 3) : profile === 2 ? point + ((index % 2) * 2) : point);
  const visualMin = Math.min(...visualPoints);
  const visualMax = Math.max(...visualPoints);
  const visualSpread = Math.max(1, visualMax - visualMin);
  const coordinates = visualPoints.map((point, index) => `${(index / (visualPoints.length - 1)) * 100},${28 - ((point - visualMin) / visualSpread) * 21}`);
  const rising = visualPoints[visualPoints.length - 1] > visualPoints[0] + 1;
  const declining = visualPoints[visualPoints.length - 1] < visualPoints[0] - 1;
  const areaPath = `M0,32 L${coordinates.join(' L')} L100,32 Z`;
  return `<svg class="trend-sparkline ${declining ? 'trend-sparkline--declining' : rising ? 'trend-sparkline--rising' : 'trend-sparkline--stable'}" viewBox="0 0 100 32" role="img" aria-label="${label} trend"><path class="trend-sparkline__area" d="${areaPath}"></path><polyline points="${coordinates.join(' ')}" vector-effect="non-scaling-stroke"></polyline><circle class="trend-sparkline__dot" cx="${coordinates[coordinates.length - 1].split(',')[0]}" cy="${coordinates[coordinates.length - 1].split(',')[1]}" r="2"></circle></svg>`;
};
function getMarketTrendView(companyName = marketTrendState.company) {
  const company = companyName ? companyMarketData[String(companyName).toLowerCase()] : null;
  const scopedMarket = marketTrendData[marketTrendState.scope] || marketTrendData.Global;
  const savedCompanies = !company && !companyName && marketTrendState.watchlist === 'Saved Companies' ? dashboardState.savedCompanies.map(name => companyMarketData[name.toLowerCase()]).filter(Boolean) : [];
  const source = company || (savedCompanies.length ? {
    momentum: Math.round(savedCompanies.reduce((total, item) => total + item.momentum, 0) / savedCompanies.length),
    change: savedCompanies.reduce((total, item) => total + item.change, 0) / savedCompanies.length,
    technologyMomentum: marketTrendData.Global.technologyMomentum.map((_, index) => Math.round(savedCompanies.reduce((total, item) => total + item.technologyMomentum[index], 0) / savedCompanies.length)),
    jobDemand: marketTrendData.Global.jobDemand.map((_, index) => Math.round(savedCompanies.reduce((total, item) => total + item.jobDemand[index], 0) / savedCompanies.length)),
    investmentSignal: marketTrendData.Global.investmentSignal.map((_, index) => Math.round(savedCompanies.reduce((total, item) => total + item.investmentSignal[index], 0) / savedCompanies.length))
  } : scopedMarket);
  const locationOffset = company ? (scopedMarket.momentum - marketTrendData.Global.momentum) * .16 : 0;
  const categoryOffset = { Technology: 2, Finance: -1, Healthcare: 1, Automotive: -2, Energy: 1, Retail: -1, 'AI & Software': 3 }[marketTrendState.category] || 0;
  const yearOffset = (Number(marketTrendState.year) - 2026) * .7;
  const rangeFactor = { '7 Days': .45, '30 Days': .65, '3 Months': .82, '6 Months': 1, '1 Year': 1.18 }[marketTrendState.timeRange] || 1;
  const adjust = values => values.map((value, index) => Math.max(4, Math.min(98, Math.round(value + yearOffset + locationOffset + categoryOffset + (index - 2) * (1 - rangeFactor)))));
  const technologyMomentum = adjust(source.technologyMomentum);
  const jobDemand = adjust(source.jobDemand);
  const investmentSignal = adjust(source.investmentSignal);
  const labels = marketTrendState.timeRange === '7 Days' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] : marketTrendState.timeRange === '30 Days' ? ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5', 'Now'] : marketTrendState.timeRange === '3 Months' ? ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'] : marketTrendState.timeRange === '1 Year' ? ['Oct', 'Dec', 'Feb', 'Apr', 'Jun', 'Aug'] : ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'];
  const dates = labels.map(label => `${label.toUpperCase()} ${marketTrendState.year}`);
  const rangeChange = (source.change + locationOffset * .2 + categoryOffset * .2) * rangeFactor;
  const trend = rangeChange > .25 ? 'Growing' : rangeChange < -.25 ? 'Declining' : 'Stable';
  return { company, labels, dates, momentum: Math.max(0, Math.min(100, source.momentum + yearOffset + locationOffset)), change: rangeChange, technologyMomentum, jobDemand, investmentSignal, trend };
}

function marketLineCoordinates(values) {
  return values.map((value, index) => ({ x: 48 + index * 106, y: 145 - value * 1.25 }));
}

function marketSmoothLine(values) {
  const points = marketLineCoordinates(values);
  return points.reduce((path, point, index, all) => {
    if (!index) return `M${point.x},${point.y}`;
    const previous = all[index - 1], before = all[Math.max(0, index - 2)], after = all[Math.min(all.length - 1, index + 1)];
    const cp1 = [previous.x + (point.x - before.x) * .16, previous.y + (point.y - before.y) * .16];
    const cp2 = [point.x - (after.x - previous.x) * .16, point.y - (after.y - previous.y) * .16];
    return `${path} C${cp1[0]},${cp1[1]} ${cp2[0]},${cp2[1]} ${point.x},${point.y}`;
  }, '');
}

function marketSignalChange(values, index) {
  if (index === 0 || !values[index - 1]) return 0;
  return ((values[index] - values[index - 1]) / values[index - 1]) * 100;
}

function renderMarketTrendChart(view) {
  const series = [
    { key: 'technologyMomentum', label: 'Technology Momentum', values: view.technologyMomentum, color: '#A855F7' },
    { key: 'jobDemand', label: 'Job Demand', values: view.jobDemand, color: '#3B82F6' },
    { key: 'investmentSignal', label: 'Investment Signal', values: view.investmentSignal, color: '#10B981' }
  ];
  const yGrid = [0, 25, 50, 75, 100].map(value => { const y = 145 - value * 1.25; return `<line class="market-line-chart__gridline" x1="42" y1="${y}" x2="596" y2="${y}"></line><text class="market-line-chart__ylabel" x="34" y="${y + 3}" text-anchor="end">${value}</text>`; }).join('');
  const xLabels = view.labels.map((label, index) => `<text class="market-line-chart__xlabel" x="${marketLineCoordinates(view.technologyMomentum)[index].x}" y="174" text-anchor="middle">${label}</text>`).join('');
  const paths = series.map((item, order) => `<path class="market-line-chart__line market-line-chart__line--${item.key}" data-series="${item.key}" style="--line-order:${order}" d="${marketSmoothLine(item.values)}"></path>`).join('');
  const circles = series.map(item => marketLineCoordinates(item.values).map((point, index) => `<circle class="market-line-chart__dot market-line-chart__dot--${item.key}" style="--point-order:${index}" cx="${point.x}" cy="${point.y}" r="3"></circle>`).join('')).join('');
  const targets = series.map(item => marketLineCoordinates(item.values).map((point, index) => `<button class="market-line-chart__target market-line-chart__target--${item.key}" type="button" data-series="${item.key}" data-index="${index}" style="--point-x:${point.x / 6}%;--point-y:${point.y / 1.84}%" aria-label="${item.label}, ${view.dates[index]}, ${item.values[index]}"></button>`).join('')).join('');
  return `<div class="market-line-chart" role="group" aria-label="Three prototype market signals over time"><div class="market-line-chart__plot"><svg viewBox="0 0 600 184" preserveAspectRatio="none" aria-hidden="true">${yGrid}<line class="market-line-chart__x-axis" x1="42" y1="145" x2="596" y2="145"></line>${paths}${circles}${xLabels}</svg><span class="market-line-chart__guide" hidden></span>${targets}<div class="market-line-chart__tooltip" hidden></div></div><div class="market-line-chart__scale-note">Normalized signal index <span>0-100</span></div></div>`;
}
function renderMarketTrendCard() {
  const view = getMarketTrendView();
  const title = view.company ? `${view.company.name} Market Trend` : 'Market Trend';
  const changeClass = view.change < 0 ? 'market-change--negative' : 'market-change--positive';
  const changeIcon = view.change < 0 ? '&#8600;' : '&#8599;';
  return `<article class="market-trend-card" aria-labelledby="market-trend-title"><div class="market-trend-card__header"><div class="market-trend-title"><span class="market-trend-icon"><i data-lucide="chart-no-axes-combined"></i></span><div><div class="market-trend-heading"><h2 id="market-trend-title">${title}</h2><span class="live-badge"><i></i>Live</span></div><p>Demo market intelligence  —  values are illustrative</p></div></div><div class="market-trend-actions"><button class="market-filter-button" id="marketFilterButton" type="button" aria-expanded="false"><i data-lucide="sliders-horizontal"></i>Filters</button><span class="market-updated"><i></i>Updated just now</span><div class="market-filter-panel" id="marketFilterPanel" hidden><strong>Market filters</strong><small>Refine companies and view</small><label>Market category<select id="marketCategoryFilter"><option ${marketTrendState.category === 'All Markets' ? 'selected' : ''}>All Markets</option><option ${marketTrendState.category === 'Technology' ? 'selected' : ''}>Technology</option><option ${marketTrendState.category === 'Finance' ? 'selected' : ''}>Finance</option><option ${marketTrendState.category === 'Healthcare' ? 'selected' : ''}>Healthcare</option><option ${marketTrendState.category === 'Automotive' ? 'selected' : ''}>Automotive</option><option ${marketTrendState.category === 'Energy' ? 'selected' : ''}>Energy</option><option ${marketTrendState.category === 'Retail' ? 'selected' : ''}>Retail</option><option ${marketTrendState.category === 'AI & Software' ? 'selected' : ''}>AI &amp; Software</option></select></label><label>Company watchlist<select id="marketWatchlistFilter"><option ${marketTrendState.watchlist === 'All Companies' ? 'selected' : ''}>All Companies</option><option ${marketTrendState.watchlist === 'Saved Companies' ? 'selected' : ''}>Saved Companies</option><option ${marketTrendState.watchlist === 'Select Companies' ? 'selected' : ''}>Select Companies</option></select></label><label>Company<select id="marketCompanyFilter"><option value="" ${marketTrendState.company === '' ? 'selected' : ''}>All Companies</option>${marketCompanyData.map(company => `<option value="${company.name}" ${company.name === marketTrendState.company ? 'selected' : ''}>${company.name}</option>`).join('')}</select></label><label>View<select id="marketViewFilter"><option ${marketTrendState.view === 'Market Overview' ? 'selected' : ''}>Market Overview</option><option ${marketTrendState.view === 'Company Comparison' ? 'selected' : ''}>Company Comparison</option><option ${marketTrendState.view === 'Individual Company' ? 'selected' : ''}>Individual Company</option></select></label><div class="market-filter-actions"><button id="resetMarketFilters" type="button">Reset</button><button class="is-primary" id="applyMarketFilters" type="button">Apply filters</button></div></div></div></div><section class="market-period-section" aria-label="Market period and location"><div class="market-period-heading"><strong>Explore market trends</strong><span>Choose a period and location</span></div><div class="market-period-controls"><label>Time period<select id="marketTimeFilter"><option ${marketTrendState.timeRange === '7 Days' ? 'selected' : ''}>7 Days</option><option ${marketTrendState.timeRange === '30 Days' ? 'selected' : ''}>30 Days</option><option ${marketTrendState.timeRange === '3 Months' ? 'selected' : ''}>3 Months</option><option ${marketTrendState.timeRange === '6 Months' ? 'selected' : ''}>6 Months</option><option ${marketTrendState.timeRange === '1 Year' ? 'selected' : ''}>1 Year</option></select></label><label>Year<select id="marketYearFilter"><option ${marketTrendState.year === '2024' ? 'selected' : ''}>2024</option><option ${marketTrendState.year === '2025' ? 'selected' : ''}>2025</option><option ${marketTrendState.year === '2026' ? 'selected' : ''}>2026</option><option ${marketTrendState.year === '2027' ? 'selected' : ''}>2027</option></select></label><label>Market location<select id="marketScopeFilter">${optionMarkup(marketOptions, marketTrendState.scope)}</select></label></div></section><div class="market-trend-summary"><div><span>Market Momentum</span><strong>${Math.round(view.momentum)}<small> / 100</small></strong></div><div><span>Current Trend</span><strong class="market-trend-status market-trend-status--${view.trend.toLowerCase()}"><i data-lucide="${view.trend === 'Declining' ? 'trending-down' : view.trend === 'Stable' ? 'minus' : 'trending-up'}"></i>${view.trend}</strong></div><b class="market-change ${changeClass}">${changeIcon} ${view.change > 0 ? '+' : ''}${view.change.toFixed(1)}%</b></div>${renderMarketTrendChart(view)}<div class="market-chart-legend"><span><i class="legend-dot legend-dot--technologyMomentum"></i>Technology Momentum</span><span><i class="legend-dot legend-dot--jobDemand"></i>Job Demand</span><span><i class="legend-dot legend-dot--investmentSignal"></i>Investment Signal</span></div><p class="market-chart-note">Prototype values for preview only  —  not verified live data</p></article>`;
}
function renderMarketSparkline(points, label) {
  const min = Math.min(...points);
  const range = Math.max(1, Math.max(...points) - min);
  const coordinates = points.map((point, index) => `${6 + (index / (points.length - 1)) * 88},${24 - ((point - min) / range) * 16}`).join(' ');
  const trendClass = points.at(-1) >= points[0] ? 'market-company-sparkline--rising' : 'market-company-sparkline--declining';
  return `<svg class="market-company-sparkline ${trendClass}" viewBox="0 0 100 28" role="img" aria-label="${label} market sparkline"><polyline points="${coordinates}" vector-effect="non-scaling-stroke"></polyline><circle cx="${coordinates.split(' ').at(-1).split(',')[0]}" cy="${coordinates.split(' ').at(-1).split(',')[1]}" r="2.5"></circle></svg>`;
}

function renderTopMarketCompaniesCard() {
  let companies = marketCompanyData.slice();
  if (marketTrendState.category !== 'All Markets') companies = companies.filter(company => company.sector === marketTrendState.category || (marketTrendState.category === 'Technology' && company.sector === 'AI & Software'));
  if (marketTrendState.watchlist === 'Saved Companies') companies = companies.filter(company => dashboardState.savedCompanies.includes(company.name));
  companies.sort((a, b) => {
    const selectedOrder = Number(b.name === marketTrendState.company) - Number(a.name === marketTrendState.company);
    return selectedOrder || getMarketTrendView(b.name).momentum - getMarketTrendView(a.name).momentum;
  });
  const content = companies.slice(0, 5).map((company, index) => {
    const companyView = getMarketTrendView(company.name);
    const isDown = companyView.change < 0;
    const trend = isDown ? 'Declining' : companyView.change > 3 ? 'Growing' : 'Stable';
    const initials = company.name === 'NVIDIA' ? 'N' : company.name.slice(0, 1);
    const isSelected = marketTrendState.company === company.name;
    const primarySignal = [
      { label: 'Technology', change: companyView.technologyMomentum.at(-1) - companyView.technologyMomentum.at(-2) },
      { label: 'Hiring', change: companyView.jobDemand.at(-1) - companyView.jobDemand.at(-2) },
      { label: 'Investment', change: companyView.investmentSignal.at(-1) - companyView.investmentSignal.at(-2) }
    ].sort((first, second) => second.change - first.change)[0].label;
    return `<button class="market-company-row${isSelected ? ' is-selected' : ''}" type="button" data-company="${company.name}" aria-pressed="${isSelected}" aria-label="View ${company.name} market trend" title="View market trend"><span class="market-company-rank">${String(index + 1).padStart(2, '0')}</span><span class="market-company-logo" aria-hidden="true">${initials}</span><strong>${company.name}</strong><span class="market-company-category">${company.categoryLabel}</span><span class="market-company-momentum">${Math.round(companyView.momentum)}<small>/100</small></span><span class="market-company-change ${isDown ? 'market-company-change--negative' : ''}">${isDown ? '&#8600;' : '&#8599;'} ${companyView.change > 0 ? '+' : ''}${companyView.change.toFixed(1)}%</span><span class="market-company-status ${isDown ? 'market-company-status--negative' : ''}">${trend}</span><span class="market-company-signal">${primarySignal}</span>${renderMarketSparkline(companyView.technologyMomentum, `${company.name} technology momentum`)}</button>`;
  }).join('') || '<p class="market-empty-state">No demo companies match these filters.</p>';
  return `<article class="top-market-companies-card"><div class="top-market-companies__header"><div><h2>Top Market Companies</h2><p>Workforce and market momentum in your selected scope.</p></div><span class="market-list-scope">${marketTrendState.scope}</span></div><div class="market-company-columns" aria-hidden="true"><span>#</span><span></span><span>Company</span><span>Market category</span><span>Momentum</span><span>Change</span><span>Trend</span><span>6-mo trend</span></div><div class="market-company-list">${content}</div><a class="market-company-card__footer" href="#/individual/market-insights">${marketTrendState.company ? 'VIEW COMPANY INTELLIGENCE' : 'VIEW ALL COMPANIES'} <i data-lucide="arrow-right"></i></a><p class="market-company-footnote">Illustrative signal data. Not verified live market data.</p></article>`;
}
const renderOriginalMarketTrendCard = renderMarketTrendCard;
renderMarketTrendCard = function(options = {}) {
  if (!options.home) return renderOriginalMarketTrendCard();
  const view = getMarketTrendView();
  const companies = marketCompanyData.slice().sort((first, second) => getMarketTrendView(second.name).momentum - getMarketTrendView(first.name).momentum).slice(0, 3);
  const topCompanies = companies.map(company => { const companyView = getMarketTrendView(company.name); return `<div><span>${company.name}</span><strong>${Math.round(companyView.momentum)}<small>/100</small></strong><b class="${companyView.change < 0 ? 'is-negative' : 'is-positive'}">${companyView.change > 0 ? '+' : ''}${companyView.change.toFixed(1)}%</b></div>`; }).join('');
  return `<article class="market-trend-card market-intelligence-trend-card" aria-labelledby="market-trend-title"><div class="market-trend-card__header"><div class="market-trend-title"><span class="market-trend-icon"><i data-lucide="chart-no-axes-combined"></i></span><div><div class="market-trend-heading"><h2 id="market-trend-title">Market Trend</h2><span class="live-badge"><i></i>Live</span></div><p>Technology, hiring and investment signals across the selected market.</p></div></div><span class="market-updated"><i></i>Updated just now</span></div><div class="market-intelligence-filterbar"><div class="market-trend-filter"><button type="button" id="marketFilterButton" aria-expanded="false" aria-controls="marketFilterPanel"><i data-lucide="sliders-horizontal"></i>Filters<span>${marketTrendState.watchlist === 'Saved Companies' ? 'My Companies' : 'All Companies'}</span><i data-lucide="chevron-down"></i></button><div class="market-trend-filter__panel" id="marketFilterPanel" role="dialog" aria-label="Market trend filters" hidden><header><div><strong>Market filters</strong><small>Adjust the companies and period</small></div><button type="button" id="closeMarketFilter" aria-label="Close filters"><i data-lucide="x"></i></button></header><label>Company scope<select id="marketWatchlistFilter"><option value="All Companies" ${marketTrendState.watchlist === 'All Companies' ? 'selected' : ''}>All Companies</option><option value="Saved Companies" ${marketTrendState.watchlist === 'Saved Companies' ? 'selected' : ''}>My Companies</option></select></label><label>Location<select id="marketScopeFilter">${optionMarkup(marketOptions, marketTrendState.scope)}</select></label><label>Time period<select id="marketTimeFilter"><option ${marketTrendState.timeRange === '7 Days' ? 'selected' : ''}>7 Days</option><option ${marketTrendState.timeRange === '30 Days' ? 'selected' : ''}>30 Days</option><option ${marketTrendState.timeRange === '3 Months' ? 'selected' : ''}>3 Months</option><option ${marketTrendState.timeRange === '6 Months' ? 'selected' : ''}>6 Months</option><option ${marketTrendState.timeRange === '1 Year' ? 'selected' : ''}>1 Year</option></select></label><div class="market-trend-filter__dates"><label>Start date<input id="marketStartDate" type="date" value="${marketTrendState.customStartDate || ''}"></label><label>End date<input id="marketEndDate" type="date" value="${marketTrendState.customEndDate || ''}"></label></div><div class="market-trend-filter__actions"><button id="resetMarketFilters" type="button">Reset</button><button class="is-primary" id="applyMarketFilters" type="button">Apply filters</button></div></div></div></div><div class="market-intelligence-summary"><div><span>Market momentum</span><strong>${Math.round(view.momentum)}<small> / 100</small></strong></div><div><span>Current trend</span><strong class="market-trend-status market-trend-status--${view.trend.toLowerCase()}"><i data-lucide="${view.trend === 'Declining' ? 'trending-down' : view.trend === 'Stable' ? 'minus' : 'trending-up'}"></i>${view.trend}</strong></div><b class="market-change ${view.change < 0 ? 'market-change--negative' : 'market-change--positive'}">${view.change > 0 ? '+' : ''}${view.change.toFixed(1)}%</b></div><div class="market-chart-heading"><strong>Market signal movement</strong><span>Location: ${marketTrendState.scope} | Period: ${marketTrendState.timeRange}</span></div>${renderMarketTrendChart(view)}<div class="market-chart-legend" aria-label="Toggle market signals"><button type="button" data-market-signal="technologyMomentum" aria-pressed="true"><i class="legend-dot legend-dot--technologyMomentum"></i>Technology Momentum</button><button type="button" data-market-signal="jobDemand" aria-pressed="true"><i class="legend-dot legend-dot--jobDemand"></i>Job Demand</button><button type="button" data-market-signal="investmentSignal" aria-pressed="true"><i class="legend-dot legend-dot--investmentSignal"></i>Investment Signal</button></div><p class="market-chart-note">Illustrative demo data. Not verified live market data.</p></article>`;
};
const legacyMarketTrendBindings = bindMarketTrendEvents;
bindMarketTrendEvents = function() { legacyMarketTrendBindings(); };
function bindMarketTrendEvents() {
  const filterButton = document.querySelector('#marketFilterButton');
  const filterPanel = document.querySelector('#marketFilterPanel');
  const closeFilter = () => { if (filterPanel) filterPanel.hidden = true; filterButton?.setAttribute('aria-expanded', 'false'); };
  filterButton?.addEventListener('click', event => { event.stopPropagation(); if (!filterPanel) return; filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  document.querySelector('#closeMarketFilter')?.addEventListener('click', closeFilter);
  if (!marketTrendState.filterDismissBound) {
    document.addEventListener('click', event => { const panel = document.querySelector('#marketFilterPanel'); const button = document.querySelector('#marketFilterButton'); if (panel && !panel.hidden && !event.target.closest('.market-trend-filter')) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); } });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') { const panel = document.querySelector('#marketFilterPanel'); const button = document.querySelector('#marketFilterButton'); if (panel && !panel.hidden) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); button?.focus(); } } });
    marketTrendState.filterDismissBound = true;
  }
  document.querySelector('#applyMarketFilters')?.addEventListener('click', () => {
    const startDate = document.querySelector('#marketStartDate')?.value || '';
    const endDate = document.querySelector('#marketEndDate')?.value || '';
    if (startDate && endDate && startDate > endDate) { const end = document.querySelector('#marketEndDate'); end.setCustomValidity('End date must be after the start date.'); end.reportValidity(); return; }
    document.querySelector('#marketEndDate')?.setCustomValidity('');
    marketTrendState.customStartDate = startDate; marketTrendState.customEndDate = endDate;
    marketTrendState.scope = document.querySelector('#marketScopeFilter')?.value || marketTrendState.scope;
    marketTrendState.timeRange = document.querySelector('#marketTimeFilter')?.value || marketTrendState.timeRange;
    marketTrendState.watchlist = document.querySelector('#marketWatchlistFilter')?.value || marketTrendState.watchlist;
    refreshMarketTrendModule();
  });
  document.querySelector('#resetMarketFilters')?.addEventListener('click', () => { Object.assign(marketTrendState, { scope: 'Global', timeRange: '30 Days', watchlist: 'All Companies', customStartDate: '', customEndDate: '' }); refreshMarketTrendModule(); });
  document.querySelectorAll('.market-company-row').forEach(row => { row.onclick = () => { marketTrendState.company = row.dataset.company; marketTrendState.view = 'Individual Company'; refreshMarketTrendModule(); }; });
  const series = [
    { key: 'technologyMomentum', label: 'Technology Momentum', values: 'technologyMomentum' },
    { key: 'jobDemand', label: 'Job Demand', values: 'jobDemand' },
    { key: 'investmentSignal', label: 'Investment Signal', values: 'investmentSignal' }
  ];
  const showTooltip = point => {
    const view = getMarketTrendView();
    const index = Number(point.dataset.index);
    const chart = point.closest('.market-line-chart__plot');
    const tooltip = chart.querySelector('.market-line-chart__tooltip');
    const guide = chart.querySelector('.market-line-chart__guide');
    tooltip.innerHTML = `<strong>${view.dates[index]}</strong>${series.map(signal => { const value = view[signal.values][index]; const change = marketSignalChange(view[signal.values], index); const positive = change >= 0; const arrow = positive ? '&#8599;' : '&#8600;'; return `<span class="market-line-chart__tooltip-row"><i class="legend-dot legend-dot--${signal.key}"></i><span>${signal.label}</span><b>${value}</b><small class="${positive ? 'is-positive' : 'is-negative'}">${arrow} ${positive ? '+' : ''}${change.toFixed(1)}%</small></span>`; }).join('')}<small class="market-line-chart__tooltip-scope">Company ${view.company?.name || 'Selected scope'}  —  ${marketTrendState.scope}  —  illustrative values</small>`;
    guide.style.left = point.style.getPropertyValue('--point-x');
    guide.hidden = false;
    tooltip.style.left = `${Math.min(82, Math.max(18, Number.parseFloat(point.style.getPropertyValue('--point-x'))))}%`;
    tooltip.hidden = false;
    chart.classList.add('is-hovering');
    chart.querySelectorAll(`.market-line-chart__target[data-index="${index}"]`).forEach(item => item.classList.add('is-active'));
  };
  document.querySelectorAll('.market-line-chart__target').forEach(point => {
    point.addEventListener('mouseenter', () => showTooltip(point));
    point.addEventListener('focus', () => showTooltip(point));
    const clear = () => { const chart = point.closest('.market-line-chart__plot'); chart.querySelector('.market-line-chart__tooltip').hidden = true; chart.querySelector('.market-line-chart__guide').hidden = true; chart.classList.remove('is-hovering'); chart.querySelectorAll('.market-line-chart__target.is-active').forEach(item => item.classList.remove('is-active')); };
    point.addEventListener('mouseleave', event => { if (!event.relatedTarget?.closest('.market-line-chart__plot')) clear(); });
    point.addEventListener('blur', clear);
  });
  document.querySelectorAll('.market-chart-legend [data-market-signal]').forEach(button => button.addEventListener('click', () => {
    const isEnabled = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(isEnabled));
    document.querySelector('.market-line-chart')?.classList.toggle(`is-signal-hidden--${button.dataset.marketSignal}`, !isEnabled);
  }));
  const plot = document.querySelector('.market-line-chart__plot');
  if (plot) {
    let activeIndex = -1;
    plot.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch') return;
      const bounds = plot.getBoundingClientRect();
      const normalizedX = ((event.clientX - bounds.left) / bounds.width * 600 - 48) / 530;
      const index = Math.max(0, Math.min(5, Math.round(normalizedX)));
      if (index === activeIndex) return;
      activeIndex = index;
      const nearestPoint = plot.querySelector(`.market-line-chart__target--technologyMomentum[data-index="${index}"]`);
      if (nearestPoint) showTooltip(nearestPoint);
    });
    plot.addEventListener('pointerleave', () => {
      activeIndex = -1;
      plot.querySelector('.market-line-chart__tooltip').hidden = true;
      plot.querySelector('.market-line-chart__guide').hidden = true;
      plot.classList.remove('is-hovering');
      plot.querySelectorAll('.market-line-chart__target.is-active').forEach(point => point.classList.remove('is-active'));
    });
  }
}

function getJobTrendView() {
  const selectedRole = jobTrendState.role;
  const roles = jobTrendState.roleScope === 'Saved Roles'
    ? (selectedRole !== 'All Roles' && savedJobRoles.includes(selectedRole) ? [selectedRole] : savedJobRoles)
    : (selectedRole === 'All Roles' ? ['All Roles'] : [selectedRole]);
  const profiles = roles.map(role => jobTrendData[role]).filter(Boolean);
  const average = field => profiles.reduce((total, profile) => total + profile[field], 0) / Math.max(1, profiles.length);
  const marketOffset = { Global: 0, India: 2, 'United States': 4, 'United Kingdom': 1, Germany: 1, Canada: 2, Australia: 2, Singapore: 3, Japan: 0 }[jobTrendState.market] || 0;
  const categoryOffset = { 'All Jobs': 0, Technology: 2, 'Data & AI': 5, Software: 3, Design: -4, Cybersecurity: 1, Cloud: 2 }[jobTrendState.category] || 0;
  const periodOffset = { '7 Days': -2, '30 Days': -1, '6 Months': 0, '1 Year': 2 }[jobTrendState.period] || 0;
  const offset = marketOffset + categoryOffset + periodOffset;
  const metrics = ['jobDemand', 'hiringMomentum', 'skillDemand', 'roleGrowth'].map(key => {
    const base = profiles.reduce((total, profile) => total + profile[key].value, 0) / Math.max(1, profiles.length);
    const change = profiles.reduce((total, profile) => total + profile[key].change, 0) / Math.max(1, profiles.length);
    return { key, value: Math.max(8, Math.min(98, Math.round(base + offset))), change: Number((change + offset * .35).toFixed(1)), color: profiles[0]?.[key].color || jobTrendData['All Roles'][key].color };
  });
  const periodFactor = { '7 Days': .25, '30 Days': .5, '6 Months': 1, '1 Year': 1.25 }[jobTrendState.period] || 1;
  const change = Number((average('changePercentage') * periodFactor + marketOffset * .2 + categoryOffset * .25).toFixed(1));
  return {
    metrics,
    momentum: Math.max(0, Math.min(100, Math.round(average('overallMomentum') + offset))),
    change,
    direction: change > 2.5 ? 'Growing' : change < -2.5 ? 'Declining' : 'Stable',
    roleLabel: jobTrendState.roleScope === 'Saved Roles' && selectedRole === 'All Roles' ? 'Saved roles' : selectedRole
  };
}

function renderJobTrendRadialChart(view) {
  const labels = { jobDemand: 'Job Demand', hiringMomentum: 'Hiring Momentum', skillDemand: 'Skill Demand', roleGrowth: 'Role Growth' };
  const radii = [94, 76, 58, 40];
  const rings = view.metrics.map((metric, index) => {
    const radius = radii[index];
    const circumference = 2 * Math.PI * radius;
    const dashOffset = circumference * (1 - metric.value / 100);
    return `<g class="job-radial-ring" data-metric="${metric.key}" style="--ring-color:${metric.color};--ring-offset:${dashOffset};--ring-circumference:${circumference};--ring-delay:${index * 120}ms" tabindex="0" role="img" aria-label="${labels[metric.key]}, ${metric.value} percent, ${metric.change > 0 ? '+' : ''}${metric.change}% this period"><circle class="job-radial-track" cx="120" cy="120" r="${radius}"></circle><circle class="job-radial-progress" cx="120" cy="120" r="${radius}"></circle></g>`;
  }).join('');
  return `<div class="job-radial-wrap"><div class="job-radial-chart"><svg viewBox="0 0 240 240" role="group" aria-label="Four job market momentum indicators">${rings}</svg><div class="job-radial-center"><span>JOB MARKET</span><strong>${view.momentum}</strong><small>Overall momentum</small><b class="job-radial-direction job-radial-direction--${view.direction.toLowerCase()}">${view.change < 0 ? '&#8595;' : view.change > 0 ? '&#8593;' : '&#8594;'} ${view.direction}</b></div><div class="job-radial-tooltip" id="jobRadialTooltip" hidden></div></div></div>`;
}

function renderJobTrendCard() {
  const view = getJobTrendView();
  const labels = { jobDemand: 'Job Demand', hiringMomentum: 'Hiring Momentum', skillDemand: 'Skill Demand', roleGrowth: 'Role Growth' };
  const descriptions = { jobDemand: 'More available job openings.', hiringMomentum: 'Change in active hiring.', skillDemand: 'Skills employers request more often.', roleGrowth: 'Growth in this selected role.' };
  const rolesForSelect = jobTrendState.roleScope === 'Saved Roles' ? savedJobRoles : jobRoleOptions;
  const roleOptions = ['All Roles', ...rolesForSelect];
  const isDeclining = view.change < 0;
  const legend = view.metrics.map(metric => `<button class="job-trend-legend-item" type="button" data-metric="${metric.key}" style="--legend-color:${metric.color}"><i></i><span class="job-legend-copy"><span>${labels[metric.key]}</span><small>${descriptions[metric.key]}</small></span><strong>${metric.value}%</strong></button>`).join('');
  return `<article class="job-trend-card market-trend-card" aria-labelledby="job-trend-title"><div class="market-trend-card__header"><div class="market-trend-title"><span class="market-trend-icon job-trend-icon"><i data-lucide="briefcase-business"></i></span><div><div class="market-trend-heading"><h2 id="job-trend-title">Job Trends</h2><span class="live-badge"><i></i>Live</span></div><p>Track how job demand and hiring activity are changing.</p></div></div><div class="market-trend-actions"><button class="market-filter-button" id="jobFilterButton" type="button" aria-expanded="false"><i data-lucide="sliders-horizontal"></i>Filters</button><span class="market-updated"><i></i>Updated just now</span><div class="market-filter-panel job-filter-panel" id="jobFilterPanel" hidden><strong>Job trend filters</strong><small>Explore illustrative workforce signals</small><label>Time period<select id="jobPeriodFilter">${optionMarkup(['7 Days', '30 Days', '6 Months', '1 Year'], jobTrendState.period)}</select></label><label>Market location<select id="jobMarketFilter">${optionMarkup(marketOptions, jobTrendState.market)}</select></label><label>Job category<select id="jobCategoryFilter">${optionMarkup(['All Jobs', 'Technology', 'Data & AI', 'Software', 'Design', 'Cybersecurity', 'Cloud'], jobTrendState.category)}</select></label><label>Role scope<select id="jobRoleScopeFilter">${optionMarkup(['All Roles', 'Saved Roles'], jobTrendState.roleScope)}</select></label><label>Selected role<select id="jobRoleFilter">${optionMarkup(roleOptions, jobTrendState.role)}</select></label><label>View<select id="jobViewFilter">${optionMarkup(['Global View', 'Location-specific View'], jobTrendState.market === 'Global' ? 'Global View' : 'Location-specific View')}</select></label><div class="market-filter-actions"><button id="resetJobFilters" type="button">Reset</button><button class="is-primary" id="applyJobFilters" type="button">Apply filters</button></div></div></div></div><div class="job-trend-summary"><div><span>Job Market Momentum  —  ${view.roleLabel}</span><strong>${view.momentum}<small>/100</small></strong></div><strong class="job-summary-trend job-summary-trend--${view.direction.toLowerCase()}"><i data-lucide="${view.direction === 'Declining' ? 'trending-down' : view.direction === 'Stable' ? 'minus' : 'trending-up'}"></i>${view.direction}</strong><b class="job-summary-change ${isDeclining ? 'is-negative' : 'is-positive'}">${isDeclining ? '&#8600;' : '&#8599;'} ${view.change > 0 ? '+' : ''}${view.change.toFixed(1)}%</b></div>${renderJobTrendRadialChart(view)}<div class="job-trend-legend" aria-label="Job trend dimensions">${legend}</div><p class="job-trend-note">Illustrative workforce data  —  not verified live hiring data</p></article>`;
}

function bindJobTrendEvents() {
  const filterButton = document.querySelector('#jobFilterButton');
  const filterPanel = document.querySelector('#jobFilterPanel');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  const apply = document.querySelector('#applyJobFilters');
  if (apply) apply.addEventListener('click', () => {
    jobTrendState.period = document.querySelector('#jobPeriodFilter').value;
    jobTrendState.market = document.querySelector('#jobMarketFilter').value;
    jobTrendState.category = document.querySelector('#jobCategoryFilter').value;
    jobTrendState.roleScope = document.querySelector('#jobRoleScopeFilter').value;
    jobTrendState.role = document.querySelector('#jobRoleFilter').value;
    const view = document.querySelector('#jobViewFilter').value;
    if (view === 'Global View') jobTrendState.market = 'Global';
    else if (jobTrendState.market === 'Global') jobTrendState.market = 'India';
    refreshJobTrendCard();
  });
  const reset = document.querySelector('#resetJobFilters');
  if (reset) reset.addEventListener('click', () => { Object.assign(jobTrendState, { period: '6 Months', market: 'Global', category: 'All Jobs', role: 'All Roles', roleScope: 'All Roles' }); refreshJobTrendCard(); });
  const showMetric = metricKey => {
    const view = getJobTrendView();
    const metric = view.metrics.find(item => item.key === metricKey);
    if (!metric) return;
    const labels = { jobDemand: 'JOB DEMAND', hiringMomentum: 'HIRING MOMENTUM', skillDemand: 'SKILL DEMAND', roleGrowth: 'ROLE GROWTH' };
    const tooltip = document.querySelector('#jobRadialTooltip');
    if (!tooltip) return;
    tooltip.innerHTML = `<strong>${labels[metricKey]}</strong><b>${metric.value}%</b><span>${metric.change > 0 ? '+' : ''}${metric.change}% this period</span>`;
    tooltip.hidden = false;
    document.querySelector('.job-radial-chart')?.classList.add('is-highlighting');
    document.querySelectorAll('.job-radial-ring,.job-trend-legend-item').forEach(item => item.classList.toggle('is-active', item.dataset.metric === metricKey));
  };
  const clearMetric = () => { const tooltip = document.querySelector('#jobRadialTooltip'); if (tooltip) tooltip.hidden = true; document.querySelector('.job-radial-chart')?.classList.remove('is-highlighting'); document.querySelectorAll('.job-radial-ring,.job-trend-legend-item').forEach(item => item.classList.remove('is-active')); };
  document.querySelectorAll('.job-radial-ring,.job-trend-legend-item').forEach(item => {
    item.addEventListener('pointerenter', () => showMetric(item.dataset.metric));
    item.addEventListener('pointerleave', clearMetric);
    item.addEventListener('focus', () => showMetric(item.dataset.metric));
    item.addEventListener('blur', clearMetric);
  });
}

function refreshJobTrendCard() {
  const module = document.querySelector('.job-trends-module');
  if (!module) return;
  module.classList.add('is-refreshing');
  window.setTimeout(() => {
    if (!module.isConnected) return;
    module.classList.remove('is-refreshing');
    module.innerHTML = renderJobTrendCard();
    lucide.createIcons();
    bindJobTrendEvents();
  }, 120);
}

renderSkillIntelligenceSection = function() {
  const trends = [
    { skill: 'Machine Learning', current: 92, growth: 15, category: 'AI / ML' },
    { skill: 'Cloud Computing', current: 88, growth: 14.3, category: 'Cloud' },
    { skill: 'Generative AI', current: 96, growth: 11.6, category: 'AI / ML' },
    { skill: 'JavaScript', current: 84, growth: 10.5, category: 'Development' },
    { skill: 'AI', current: 76, growth: 7, category: 'AI / ML' },
    { skill: 'Java', current: 74, growth: 7.2, category: 'Development' }
  ];
  trends.forEach(item => { item.values = trendWindowForSkill(item.skill); item.values[item.values.length - 1] = item.current; });
  const topSkill = trends.find(item => item.skill === dashboardState.selectedSkill) || trends[0];
  const scope = dashboardState.trendScope === 'My Saved Skills' ? 'My Skills' : dashboardState.trendScope === 'Saved Skills' ? 'Saved Skills' : 'Global';
  const scopeValue = scope === 'Global' ? 'Overall Live Trends' : 'My Saved Skills';
  const barMarkup = trends.map((item, index) => {
    const change = item.growth;
    const selected = item.skill === topSkill.skill;
    return `<button type="button" class="skill-live-bar${selected ? ' is-selected' : ''}" style="--bar-delay:${index * 80}ms;--bar-height:${item.current}%" aria-label="${item.skill}, demand ${item.current} out of 100, growth plus ${change} percent" aria-pressed="${selected}" data-skill="${item.skill}" data-demand="${item.current}" data-change="${change}" data-category="${item.category}" data-trend="Growing"><span class="skill-live-bar__label"><span>${item.skill}</span><strong>${item.current}</strong></span><span class="skill-live-bar__track"><i class="skill-live-bar__fill skill-live-bar__fill--growing"></i></span><span class="skill-live-bar__change is-growing"><i data-lucide="trending-up"></i>+${change}%</span><span class="skill-live-tooltip"><strong>${item.skill}</strong><span>Demand: ${item.current} / 100</span><span>Growth: +${change}%</span><span>Trend: Growing</span><span>Category: ${item.category}</span></span></button>`;
  }).join('');
  const calculateTrendScore = skill => skill.growth;
  const sortedTrends = [...trends].sort((a, b) => calculateTrendScore(b) - calculateTrendScore(a));
  const rankingMarkup = sortedTrends.map((item, index) => {
    const active = item.skill === topSkill.skill;
    return `<button type="button" class="skill-momentum-row${active ? ' is-selected' : ''}" data-skill="${item.skill}" aria-pressed="${active}"><span class="skill-momentum-row__rank">${String(index + 1).padStart(2, '0')}</span><span class="skill-momentum-row__copy"><strong>${item.skill}</strong><small>${item.category}</small></span>${renderTrendSparkline(item.values, `${item.skill} demand history`)}<span class="skill-momentum-row__growth"><strong><i data-lucide="trending-up"></i>+${item.growth}%</strong><small>Growing</small></span><b class="skill-momentum-row__demand">${item.current}</b></button>`;
  }).join('');
  return `<section class="home-section skill-intelligence-section skill-intelligence-section--live" id="current-skill-intelligence" aria-labelledby="current-skill-section-title"><div class="home-section__heading"><div><span class="section-kicker">Your skill, in context</span><h2 id="current-skill-section-title">Skill Intelligence</h2><p>See which skills are gaining or losing demand.</p></div><span class="skill-intelligence-live-badge"><i></i>Live ranking</span></div><div class="skill-intelligence-live-grid"><article class="skill-live-card" aria-labelledby="skill-live-title"><header class="skill-live-card__header"><div><span class="skill-intel-card__eyebrow">LIVE MARKET SIGNAL</span><h3 id="skill-live-title">Skill Trend</h3><p>Current demand movement across key skills</p></div><div class="skill-live-card__actions"><span class="skill-live-card__updated"><i></i>Live <small>Updated just now</small></span><div class="skill-intelligence-filterbar"><div class="skill-trend-filter"><button type="button" id="skillTrendFilterButton" aria-expanded="false" aria-controls="skillTrendFilterPanel"><i data-lucide="sliders-horizontal"></i>All Skills<i data-lucide="chevron-down"></i></button><div class="skill-trend-filter__panel" id="skillTrendFilterPanel" role="dialog" aria-label="Skill trend filters" hidden><header><div><strong>Trend filters</strong><small>Adjust your skill market view</small></div><button type="button" id="closeSkillTrendFilter" aria-label="Close filters"><i data-lucide="x"></i></button></header><label>Scope<select id="skillIntelScope"><option value="Overall Live Trends" ${scopeValue === 'Overall Live Trends' ? 'selected' : ''}>All Skills</option><option value="My Saved Skills" ${scope === 'My Skills' ? 'selected' : ''}>My Skills</option><option value="Saved Skills" ${scope === 'Saved Skills' ? 'selected' : ''}>Favorite Skills</option></select></label><label>Region<select id="skillIntelRegion">${optionMarkup(marketOptions, dashboardState.market)}</select></label><label>Period<select id="skillIntelPeriod">${optionMarkup(timeRangeOptions, dashboardState.timeRange)}</select></label><div class="skill-trend-filter__dates"><label>Start date<input id="skillIntelStartDate" type="date" value="${skillTrendFilterState.startDate}"></label><label>End date<input id="skillIntelEndDate" type="date" value="${skillTrendFilterState.endDate}"></label></div><button type="button" class="skill-trend-filter__apply" id="applySkillTrendFilter">Apply filters</button></div></div></div></header><div class="skill-live-highlight" data-featured-skill><div class="skill-live-highlight__identity"><span class="skill-live-highlight__eyebrow">TOP RISING SKILL</span><strong data-featured-name>${topSkill.skill}</strong><small data-featured-category>${topSkill.category}</small></div><div class="skill-live-highlight__score"><span>DEMAND SCORE</span><div><strong data-featured-demand>${topSkill.current}</strong><small> / 100</small></div><i><b style="--score:${topSkill.current}%"></b></i></div><div class="skill-live-highlight__momentum"><span>GROWTH</span><strong class="is-growing" data-featured-growth><i data-lucide="trending-up"></i>+${topSkill.growth}%</strong><small class="skill-live-highlight__status is-growing"><i data-lucide="trending-up"></i>Growing</small></div></div><div class="skill-live-chart-heading"><strong>Market demand by skill</strong><span>Top 6 <i></i> Demand score</span></div><div class="skill-live-chart" role="group" aria-label="Live skill demand comparison"><div class="skill-live-chart__axis"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div class="skill-live-chart__plot">${barMarkup}</div></div></article><article class="skill-ranking-card" aria-labelledby="skill-ranking-title"><header class="skill-ranking-card__header"><div><span class="skill-intel-card__eyebrow">MARKET MOMENTUM</span><h3 id="skill-ranking-title">Top Trending Skills</h3><p>Skills showing the strongest market movement</p></div><a class="skill-ranking-card__view" href="#/individual/skills">View All <i data-lucide="arrow-right"></i></a></header><div class="skill-momentum-list">${rankingMarkup}</div><footer class="skill-ranking-card__footer"><span>Updated just now</span><a href="#/individual/skills">View full skill intelligence <i data-lucide="arrow-right"></i></a></footer></article></div></section>`;
};
bindSkillTrendAnalyticsEvents = function() {
  const filterButton = document.querySelector('#skillTrendFilterButton');
  const filterPanel = document.querySelector('#skillTrendFilterPanel');
  const closeFilter = () => { if (filterPanel) filterPanel.hidden = true; filterButton?.setAttribute('aria-expanded', 'false'); };
  filterButton?.addEventListener('click', event => { event.stopPropagation(); if (!filterPanel) return; filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (!skillTrendFilterState.outsideHandlerBound) { document.addEventListener('click', event => { const panel = document.querySelector('#skillTrendFilterPanel'); const button = document.querySelector('#skillTrendFilterButton'); if (panel && !panel.hidden && !event.target.closest('.skill-trend-filter')) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); } }); document.addEventListener('keydown', event => { if (event.key === 'Escape') { const panel = document.querySelector('#skillTrendFilterPanel'); const button = document.querySelector('#skillTrendFilterButton'); if (panel && !panel.hidden) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); button?.focus(); } } }); skillTrendFilterState.outsideHandlerBound = true; }
  document.querySelector('#closeSkillTrendFilter')?.addEventListener('click', closeFilter);
  document.querySelector('#applySkillTrendFilter')?.addEventListener('click', () => {
    const startDate = document.querySelector('#skillIntelStartDate')?.value || '';
    const endDate = document.querySelector('#skillIntelEndDate')?.value || '';
    if (startDate && endDate && startDate > endDate) { document.querySelector('#skillIntelEndDate')?.setCustomValidity('End date must be after the start date.'); document.querySelector('#skillIntelEndDate')?.reportValidity(); return; }
    document.querySelector('#skillIntelEndDate')?.setCustomValidity('');
    skillTrendFilterState.startDate = startDate; skillTrendFilterState.endDate = endDate;
    const scope = document.querySelector('#skillIntelScope')?.value;
    if (scope) dashboardState.trendScope = scope;
    const region = document.querySelector('#skillIntelRegion')?.value;
    if (region) { dashboardState.market = region; marketTrendState.scope = region; jobTrendState.market = region; }
    const period = document.querySelector('#skillIntelPeriod')?.value;
    if (period) dashboardState.timeRange = period;
    renderHome();
  });
  document.querySelectorAll('.skill-live-bar').forEach(bar => {
    const show = () => bar.classList.add('is-hovered');
    const hide = () => bar.classList.remove('is-hovered');
    bar.addEventListener('mouseenter', show); bar.addEventListener('mouseleave', hide); bar.addEventListener('focus', show); bar.addEventListener('blur', hide);
    bar.addEventListener('click', () => {
      dashboardState.selectedSkill = bar.dataset.skill;
      document.querySelectorAll('.skill-live-bar').forEach(candidate => {
        const selected = candidate === bar;
        candidate.classList.toggle('is-selected', selected);
        candidate.setAttribute('aria-pressed', String(selected));
      });
      const featured = document.querySelector('[data-featured-skill]');
      if (!featured) return;
      featured.querySelector('[data-featured-name]').textContent = bar.dataset.skill;
      featured.querySelector('[data-featured-category]').textContent = bar.dataset.category;
      featured.querySelector('[data-featured-demand]').textContent = bar.dataset.demand;
      featured.querySelector('.skill-live-highlight__score > i b').style.setProperty('--score', `${bar.dataset.demand}%`);
      featured.querySelector('[data-featured-growth]').innerHTML = `<i data-lucide="trending-up"></i>+${bar.dataset.change}%`;
      lucide.createIcons();
    });
  });
};
renderLearningRoadmapPreview = function() {
  const active = ['active', 'paused'].includes(roadmapState.status);
  if (!active) return '';
  const stages = roadmapState.stages?.length ? roadmapState.stages : createRoadmapStages();
  const overall = Math.max(0, Math.min(100, roadmapState.progress ?? Math.round((roadmapState.completedTopics ?? 0) / 28 * 100)));
  const currentIndex = stages.findIndex(stage => !stage.completed && (stage.progress > 0 || stage.status === 'in-progress'));
  const resolvedCurrentIndex = currentIndex >= 0 ? currentIndex : stages.findIndex(stage => !stage.completed);
  const currentStage = stages[resolvedCurrentIndex] || stages.at(-1);
  const nextStage = stages.slice(Math.max(0, resolvedCurrentIndex + 1)).find(stage => !stage.completed) || null;
  const completedCount = stages.filter(stage => stage.completed).length;
  const attentionCount = stages.filter(stage => stage.status === 'blocked' || stage.status === 'locked' || stage.attention).length;
  const currentCount = currentStage && !currentStage.completed ? 1 : 0;
  const upcomingCount = Math.max(0, stages.length - completedCount - currentCount - attentionCount);
  const goal = roadmapState.goal || roadmapState.goalType || 'Learn Skill';
  const skill = roadmapState.skill || dashboardState.selectedSkill;
  const currentName = currentStage?.topic || currentStage?.name || 'Choose your first milestone';
  const nextName = nextStage?.topic || nextStage?.name || 'Roadmap complete';
  const circumference = 2 * Math.PI * 43;
  const progressStrip = `<div class="home-roadmap__progress"><div class="home-roadmap__progress-copy"><span>ROADMAP PROGRESS</span><strong data-roadmap-count="${overall}">${overall}%</strong><small>${completedCount} of ${stages.length} milestones complete</small></div><div class="home-roadmap__progress-meter" role="progressbar" aria-label="Roadmap progress" aria-valuenow="${overall}" aria-valuemin="0" aria-valuemax="100"><span style="--progress:${overall}%"></span></div><div class="roadmap-progress-ring" style="--roadmap-circumference:${circumference};--roadmap-offset:${circumference * (1 - overall / 100)}"><svg viewBox="0 0 100 100" aria-hidden="true"><circle class="roadmap-progress-ring__track" cx="50" cy="50" r="43"></circle><circle class="roadmap-progress-ring__value" cx="50" cy="50" r="43"></circle></svg><strong>${overall}%</strong></div></div>`;
  return `<section class="home-section learning-roadmap-section learning-roadmap-section--active roadmap-full-width home-roadmap" id="active-learning-roadmap" aria-labelledby="learning-roadmap-title"><div class="home-section__heading"><div><span class="section-kicker">Build what comes next</span><h2 id="learning-roadmap-title">Your Active Roadmap</h2><p>A focused snapshot of your learning journey.</p></div><div class="roadmap-header-actions"><span class="roadmap-state-badge ${roadmapState.status === 'paused' ? 'is-paused' : ''}"><i></i>${roadmapState.status === 'paused' ? 'Paused' : 'Tracking'}</span><button type="button" class="roadmap-text-action" data-roadmap-toggle>${roadmapState.status === 'paused' ? 'Resume roadmap' : 'Pause roadmap'}</button></div></div><article class="home-roadmap__card"><div class="home-roadmap__identity"><span class="home-roadmap__icon"><i data-lucide="route"></i></span><div><span class="home-roadmap__eyebrow">${goal}  —  ${skill}</span><h3>${roadmapState.name || `${skill} Roadmap`}</h3><p>${roadmapState.goalDescription || `A personalized path to ${goal.toLowerCase()} in ${skill}.`}</p></div></div><div class="home-roadmap__body">${progressStrip}<div class="home-roadmap__milestones"><div class="home-roadmap__milestone is-current"><span class="home-roadmap__node"><i data-lucide="play"></i></span><div><small>Current step</small><strong>${currentName}</strong><span>${currentStage?.name || 'In progress'}${currentStage?.progress ? `  —  ${currentStage.progress}% complete` : ''}</span></div></div><span class="home-roadmap__connector" aria-hidden="true"></span><div class="home-roadmap__milestone ${nextStage ? 'is-next' : 'is-complete'}"><span class="home-roadmap__node"><i data-lucide="${nextStage ? 'arrow-right' : 'check'}"></i></span><div><small>${nextStage ? 'Up next' : 'Next'}</small><strong>${nextName}</strong><span>${nextStage?.name || (nextStage ? 'Upcoming milestone' : 'All milestones complete')}</span></div></div></div><div class="home-roadmap__counts" aria-label="Milestone summary"><span><i class="is-done"></i><b>${completedCount}</b> completed</span><span><i class="is-current"></i><b>${currentCount}</b> current</span><span><i class="is-upcoming"></i><b>${upcomingCount}</b> upcoming</span><span><i class="is-attention"></i><b>${attentionCount}</b> attention</span></div></div><footer class="home-roadmap__footer"><a class="home-roadmap__continue" href="#/individual/learning">Continue Roadmap <i data-lucide="arrow-right"></i></a><a class="home-roadmap__view" href="#/individual/learning">View Full Roadmap <i data-lucide="external-link"></i></a><span>Detailed resources and tracking live in Learning</span></footer></article></section>`;
};
refreshRoadmapSection = function() {
  const active = ['active', 'paused'].includes(roadmapState.status);
  const section = document.querySelector('#active-learning-roadmap');
  if (!section) { if (active) renderHome(); return; }
  if (!active) { section.remove(); return; }
  section.outerHTML = renderLearningRoadmapPreview();
  lucide.createIcons();
  bindRoadmapEvents();
};
renderJobIntelligenceSection = function() {
  const view = getJobTrendView();
  const metrics = [
    { key: 'jobDemand', label: 'Job Demand', description: 'More relevant openings', color: '#B22DEF' },
    { key: 'skillDemand', label: 'Skill Demand', description: 'Skills requested by employers', color: '#4D8DFF' },
    { key: 'hiringMomentum', label: 'Hiring Momentum', description: 'Change in active hiring', color: '#FF9B4A' },
    { key: 'roleGrowth', label: 'Role Growth', description: 'Growth in selected roles', color: '#10B981' }
  ];
  const radii = [130, 104, 78, 52];
  const rings = metrics.map((metric, index) => { const source = view.metrics.find(item => item.key === metric.key); const circumference = 2 * Math.PI * radii[index]; const offset = circumference * (1 - source.value / 100); return `<g class="job-radial-ring" data-metric="${metric.key}" style="--ring-color:${metric.color};--ring-offset:${offset};--ring-circumference:${circumference};--ring-delay:${index * 110}ms" tabindex="0" role="img" aria-label="${metric.label}, ${source.value} percent, ${source.change > 0 ? '+' : ''}${source.change}% this period"><circle class="job-radial-track" cx="150" cy="150" r="${radii[index]}"></circle><circle class="job-radial-progress" cx="150" cy="150" r="${radii[index]}"></circle></g>`; }).join('');
  const legend = metrics.map((metric,index) => { const source = view.metrics.find(item => item.key === metric.key); const trend = source.change > 0 ? 'is-growing' : source.change < 0 ? 'is-declining' : 'is-stable'; return `<article class="job-intelligence-legend" style="--legend-index:${index}" tabindex="0" role="button" aria-label="${metric.label}, ${source.value} percent, ${source.change > 0 ? 'up' : source.change < 0 ? 'down' : 'stable'} ${Math.abs(source.change)} percent" data-metric="${metric.key}" style="--legend-color:${metric.color}"><span class="job-intelligence-legend__top"><i></i><strong>${metric.label}</strong><b class="${trend}">${source.change > 0 ? '?' : source.change < 0 ? '?' : '?'} ${source.change > 0 ? '+' : ''}${source.change}%</b></span><span class="job-intelligence-legend__value">${source.value}<small>%</small></span><small class="job-intelligence-legend__description">${metric.description}</small></article>`; }).join('');
  const skillDetails = trendDetailsForSkill(dashboardState.selectedSkill);
  const roleLabel = view.roleLabel === 'All Roles' ? 'your selected roles' : view.roleLabel;
  const recommendations = [
    { title: `BUILD ${dashboardState.selectedSkill.toUpperCase()} SKILLS`, why: `${dashboardState.selectedSkill} is currently relevant to ${roleLabel}, with skill demand at ${view.metrics.find(item => item.key === 'skillDemand').value}%.`, relevance: `${view.metrics.find(item => item.key === 'skillDemand').value}% relevance`, href: '#/individual/skills', cta: 'Explore Skill Gap', icon: 'layers-3' },
    { title: 'EXPLORE MATCHING ROLES', why: `Hiring momentum is ${view.metrics.find(item => item.key === 'hiringMomentum').value}% for ${roleLabel}; compare roles where your profile can travel next.`, relevance: `${view.metrics.find(item => item.key === 'roleGrowth').value}% role growth`, href: '#/individual/career', cta: 'Explore Roles', icon: 'briefcase-business' },
    { title: roadmapState.status === 'empty' || roadmapState.status === 'rejected' ? 'START RECOMMENDED ROADMAP' : 'CONTINUE YOUR ROADMAP', why: `Job demand is ${view.metrics.find(item => item.key === 'jobDemand').value}%, so a focused learning path can turn market demand into visible evidence.`, relevance: `${view.metrics.find(item => item.key === 'jobDemand').value}% job demand`, href: roadmapState.status === 'active' || roadmapState.status === 'paused' ? '#active-learning-roadmap' : '#current-skill-intelligence', cta: roadmapState.status === 'active' || roadmapState.status === 'paused' ? 'View Roadmap' : 'Start Roadmap', icon: 'map' }
  ];
  return `<section class="home-section job-intelligence-section" id="job-intelligence" aria-labelledby="job-intelligence-title"><div class="home-section__heading"><div><span class="section-kicker">Workforce signals</span><h2 id="job-intelligence-title">Job Intelligence</h2><p>Hiring demand, skill demand and role growth in your selected scope.</p></div><span class="job-intelligence-context"><i></i>${view.roleLabel}  —  ${jobTrendState.market}</span></div><div class="job-intelligence-grid"><article class="job-intelligence-card" aria-labelledby="job-market-intelligence-title"><header class="job-intelligence-card__header"><div><span class="skill-intel-card__eyebrow">Live workforce signals</span><h3 id="job-market-intelligence-title">Job Market Intelligence</h3><p>Understand hiring demand, skill demand and role growth.</p></div><div class="job-intelligence-filters"><button type="button" id="jobTrendFilterButton" aria-expanded="false" aria-controls="jobTrendFilterPanel"><i data-lucide="sliders-horizontal"></i>Filters<span>${jobTrendState.market} ? ${jobTrendState.role === 'All Roles' ? 'All Roles' : jobTrendState.role}</span><i data-lucide="chevron-down"></i></button><div class="job-trend-filter__panel" id="jobTrendFilterPanel" role="dialog" aria-label="Job trend filters" hidden><header><div><strong>Job trend filters</strong><small>Refine hiring signals</small></div><button type="button" id="closeJobTrendFilter" aria-label="Close filters"><i data-lucide="x"></i></button></header><label>Time period<select id="jobPeriodFilter">${optionMarkup(['7 Days', '30 Days', '6 Months', '1 Year'], jobTrendState.period)}</select></label><label>Market<select id="jobMarketFilter">${optionMarkup(marketOptions, jobTrendState.market)}</select></label><label>Role<select id="jobRoleFilter">${optionMarkup(['All Roles', ...jobRoleOptions], jobTrendState.role)}</select></label><button class="job-trend-filter__apply" id="applyJobTrendFilter" type="button">Apply filters</button></div></div></header><div class="job-intelligence-visual-grid"><div class="job-intelligence-radial"><div class="job-radial-chart"><svg viewBox="0 0 300 300" role="group" aria-label="Four independent job market signals">${rings}</svg><div class="job-radial-tooltip" id="jobRadialTooltip" hidden></div></div></div><div class="job-intelligence-legend-grid">${legend}</div></div><p class="job-intelligence-note">Illustrative workforce signals  —  hover a ring or legend for exact value and change.</p></article><article class="job-action-card" aria-labelledby="job-action-title"><header><span class="skill-intel-card__eyebrow">Profile-based actions</span><h3 id="job-action-title">What You Can Do Next</h3><p>Actions generated from your current skills, role direction and live job signals.</p></header><div class="job-action-list">${recommendations.map((recommendation, index) => `<article class="job-action-item" style="--action-delay:${index * 65}ms"><span class="job-action-item__icon"><i data-lucide="${recommendation.icon}"></i></span><div><strong>${recommendation.title}</strong><p>${recommendation.why}</p><small>${recommendation.relevance}</small><a href="${recommendation.href}" ${recommendation.icon === 'map' && !['active', 'paused'].includes(roadmapState.status) ? 'data-roadmap-accept' : ''}>${recommendation.cta} <i data-lucide="arrow-right"></i></a></div></article>`).join('')}</div><small class="job-action-disclaimer">Illustrative recommendations based on prototype workforce data.</small></article></div></section>`;
};
bindJobIntelligenceEvents = function() {
  const filterButton = document.querySelector('#jobTrendFilterButton');
  const filterPanel = document.querySelector('#jobTrendFilterPanel');
  const closeFilter = () => { if (filterPanel) filterPanel.hidden = true; filterButton?.setAttribute('aria-expanded', 'false'); };
  filterButton?.addEventListener('click', event => { event.stopPropagation(); if (!filterPanel) return; filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  document.querySelector('#closeJobTrendFilter')?.addEventListener('click', closeFilter);
  if (!jobTrendState.filterDismissBound) {
    document.addEventListener('click', event => { const panel = document.querySelector('#jobTrendFilterPanel'); const button = document.querySelector('#jobTrendFilterButton'); if (panel && !panel.hidden && !event.target.closest('.job-intelligence-filters')) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); } });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') { const panel = document.querySelector('#jobTrendFilterPanel'); const button = document.querySelector('#jobTrendFilterButton'); if (panel && !panel.hidden) { panel.hidden = true; button?.setAttribute('aria-expanded', 'false'); button?.focus(); } } });
    jobTrendState.filterDismissBound = true;
  }
  document.querySelector('#applyJobTrendFilter')?.addEventListener('click', () => {
    jobTrendState.period = document.querySelector('#jobPeriodFilter')?.value || jobTrendState.period;
    jobTrendState.market = document.querySelector('#jobMarketFilter')?.value || jobTrendState.market;
    marketTrendState.scope = jobTrendState.market;
    const role = document.querySelector('#jobRoleFilter')?.value || jobTrendState.role;
    jobTrendState.role = role;
    dashboardState.selectedSkill = ({ 'AI / ML Engineer': 'Machine Learning', 'AI Engineer': 'Machine Learning', 'Software Engineer': 'JavaScript', 'Data Scientist': 'Data Analytics', 'Data Analyst': 'SQL', 'UI/UX Designer': 'React', 'Cybersecurity Engineer': 'Cybersecurity', 'Cloud Engineer': 'Cloud Computing' }[role] || dashboardState.selectedSkill);
    renderHome();
  });
  const labels = { jobDemand: 'JOB DEMAND', skillDemand: 'SKILL DEMAND', hiringMomentum: 'HIRING MOMENTUM', roleGrowth: 'ROLE GROWTH' };
  const showMetric = metricKey => { const metric = getJobTrendView().metrics.find(item => item.key === metricKey); const tooltip = document.querySelector('#jobRadialTooltip'); if (!metric || !tooltip) return; tooltip.innerHTML = `<strong>${labels[metricKey]}</strong><b>${metric.value}%</b><span>${metric.change > 0 ? '+' : ''}${metric.change}% this period  —  ${getJobTrendView().roleLabel}</span>`; tooltip.hidden = false; document.querySelector('#job-intelligence .job-radial-chart')?.classList.add('is-highlighting'); document.querySelectorAll('#job-intelligence .job-radial-ring,#job-intelligence .job-intelligence-legend').forEach(item => item.classList.toggle('is-active', item.dataset.metric === metricKey)); };
  const clearMetric = () => { const tooltip = document.querySelector('#jobRadialTooltip'); if (tooltip) tooltip.hidden = true; document.querySelector('#job-intelligence .job-radial-chart')?.classList.remove('is-highlighting'); document.querySelectorAll('#job-intelligence .job-radial-ring,#job-intelligence .job-intelligence-legend').forEach(item => item.classList.remove('is-active')); };
  document.querySelectorAll('#job-intelligence .job-radial-ring,#job-intelligence .job-intelligence-legend').forEach(item => { item.addEventListener('pointerenter', () => showMetric(item.dataset.metric)); item.addEventListener('pointerleave', clearMetric); item.addEventListener('focus', () => showMetric(item.dataset.metric)); item.addEventListener('blur', clearMetric); });
};
renderJobIntelligenceSection = function() {
  const view = getJobTrendView();
  const signals = [
    { key: 'jobDemand', label: 'Open role activity', short: 'Open roles', count: 42180, change: 12.4, color: '#B22DEF', icon: 'briefcase-business', roles: 'AI Engineer, Data Scientist' },
    { key: 'hiringMomentum', label: 'Hiring company activity', short: 'Hiring companies', count: 3240, change: 8.6, color: '#42075D', icon: 'building-2', roles: 'NVIDIA, Microsoft' },
    { key: 'roleGrowth', label: 'Role demand momentum', short: 'Role demand', count: 31560, change: 14.2, color: '#10B981', icon: 'trending-up', roles: 'AI Engineer, ML Engineer' },
    { key: 'skillDemand', label: 'Workforce reduction signal', short: 'Reduction signal', count: 4820, change: -3.1, color: '#F59E0B', icon: 'users-round', roles: 'Operations, Support' }
  ].map(signal => { const metric = view.metrics.find(item => item.key === signal.key); return { ...signal, value: metric.value, change: Number((signal.change + metric.change * .12).toFixed(1)) }; });
  const selectedKey = jobTrendState.selectedJobSignal || signals[0].key;
  const selected = signals.find(signal => signal.key === selectedKey) || signals[0];
  const radius = 103, circumference = 2 * Math.PI * radius;
  const rings = signals.map((signal, index) => {
    const segment = circumference / 4 - 8;
    return `<g class="job-radial-ring${selectedKey === signal.key ? ' is-selected' : ''}" data-metric="${signal.key}" style="--ring-color:${signal.color};--ring-circumference:${circumference};--ring-offset:${-index * circumference / 4};--ring-length:${segment};--ring-delay:${index * 100}ms" tabindex="0" role="button" aria-pressed="${selectedKey === signal.key}" aria-label="${signal.label}: ${signal.count.toLocaleString()} signals, ${signal.value}% index, ${signal.change > 0 ? '+' : ''}${signal.change}% change"><circle class="job-radial-track" cx="150" cy="150" r="${radius}"></circle><circle class="job-radial-progress" cx="150" cy="150" r="${radius}" stroke-dasharray="${segment} ${circumference - segment}" stroke-dashoffset="${-index * circumference / 4}"></circle></g>`;
  }).join('');
  const cards = signals.map((signal, index) => `<button type="button" class="job-intelligence-legend${selectedKey === signal.key ? ' is-active' : ''}" data-metric="${signal.key}" aria-pressed="${selectedKey === signal.key}" style="--legend-index:${index};--legend-color:${signal.color}"><span class="job-intelligence-legend__top"><i data-lucide="${signal.icon}"></i><strong>${signal.short}</strong></span><span class="job-intelligence-legend__value">${signal.count.toLocaleString()}</span><small class="job-intelligence-legend__description">${signal.change > 0 ? '↑' : '↓'} ${signal.change > 0 ? '+' : ''}${signal.change}% <span>· ${signal.value}% index</span></small></button>`).join('');
  const role = view.roleLabel === 'All Roles' ? 'AI Engineer' : view.roleLabel;
  const recs = [
    { id: 'role', category: 'ROLE TO EXPLORE', title: role, icon: 'briefcase-business', why: `Your ${dashboardState.selectedSkill} skills align with demand for this role in ${jobTrendState.market}.`, signal: `${selected.short} · ${selected.change > 0 ? '+' : ''}${selected.change}%`, detail: 'Role demand, your skills, career direction', action: 'View Role', href: '#/individual/career', secondary: 'Explore Skill', secondaryHref: '#/individual/skills' },
    { id: 'skill', category: 'SKILL TO STRENGTHEN', title: dashboardState.selectedSkill, icon: 'layers-3', why: `This capability appears across relevant ${role} opportunities; build evidence through a focused project.`, signal: `Skill demand · ${view.metrics.find(item => item.key === 'skillDemand').value}% index`, detail: 'Required skills, profile context, skill gap', action: 'Explore Skill', href: '#/individual/skills', secondary: 'Build Roadmap', secondaryHref: '#active-learning-roadmap' },
    { id: 'company', category: 'COMPANY OPPORTUNITY', title: 'NVIDIA', icon: 'building-2', why: 'Hiring activity is rising in your selected market and overlaps with your role interests.', signal: `Hiring activity · ${signals[1].change > 0 ? '+' : ''}${signals[1].change}%`, detail: 'Hiring activity, selected role, market scope', action: 'View Company', href: '#/individual/market-intelligence', secondary: 'View Jobs', secondaryHref: '#/individual/career' }
  ];
  const recCards = recs.map((item, index) => `<article class="job-action-item${jobTrendState.selectedRecommendation === item.id ? ' is-selected' : ''}" style="--action-delay:${index * 65}ms"><span class="job-action-item__icon"><i data-lucide="${item.icon}"></i></span><div class="job-action-item__content"><small class="job-action-category">${item.category}</small><strong>${item.title}</strong><p>${item.why}</p><small class="job-action-signal">${item.signal}</small><details class="job-action-why" ${jobTrendState.selectedRecommendation === item.id ? 'open' : ''}><summary>Why recommended?</summary><span>${item.detail}</span></details><div class="job-action-buttons"><a href="${item.href}" data-recommendation="${item.id}">${item.action}</a><a class="is-secondary" href="${item.secondaryHref}" data-recommendation="${item.id}">${item.secondary}</a></div></div></article>`).join('');
  return `<section class="home-section job-intelligence-section" id="job-intelligence" aria-labelledby="job-intelligence-title"><div class="home-section__heading"><div><span class="section-kicker">Workforce signals</span><h2 id="job-intelligence-title">Job Intelligence</h2><p>Understand hiring demand and discover opportunities relevant to you.</p></div><div class="job-intelligence-context"><button type="button" id="jobTrendFilterButton" aria-expanded="false" aria-controls="jobTrendFilterPanel"><i data-lucide="sliders-horizontal"></i>Filters</button><span class="job-intelligence-scope">${jobTrendState.market} / ${jobTrendState.role} / ${jobTrendState.period} ▾</span><div class="job-trend-filter__panel" id="jobTrendFilterPanel" role="dialog" aria-label="Job intelligence filters" hidden><header><div><strong>Market filters</strong><small>Both views use the same scope</small></div><button type="button" id="closeJobTrendFilter" aria-label="Close filters"><i data-lucide="x"></i></button></header><label>Time period<select id="jobPeriodFilter">${optionMarkup(['7 Days','30 Days','6 Months','1 Year'],jobTrendState.period)}</select></label><label>Market<select id="jobMarketFilter">${optionMarkup(marketOptions,jobTrendState.market)}</select></label><label>Role<select id="jobRoleFilter">${optionMarkup(['All Roles',...jobRoleOptions],jobTrendState.role)}</select></label><button class="job-trend-filter__apply" id="applyJobTrendFilter" type="button">Apply filters</button></div></div></div><div class="job-intelligence-grid"><article class="job-intelligence-card" aria-labelledby="job-market-intelligence-title"><header class="job-intelligence-card__header"><div><span class="skill-intel-card__eyebrow">Market signals · ${jobTrendState.market}</span><h3 id="job-market-intelligence-title">Job Trend Analysis <span class="job-market-status"><i></i>Illustrative</span></h3><p>Hiring activity across your selected market</p></div></header><div class="job-intelligence-visual-grid"><div class="job-intelligence-radial"><div class="job-radial-chart"><svg viewBox="0 0 300 300" role="group" aria-label="Four job market signals">${rings}</svg><div class="job-radial-center"><span>JOB MARKET</span><strong>SIGNALS</strong><small>${jobTrendState.market} · ${jobTrendState.period}</small></div><div class="job-radial-tooltip" id="jobRadialTooltip" hidden></div></div></div><div class="job-intelligence-legend-grid">${cards}</div></div><p class="job-intelligence-note">Signals are normalized across the selected market and time period. Prototype data, not verified live hiring data.</p></article><article class="job-action-card" aria-labelledby="job-action-title"><header><span class="skill-intel-card__eyebrow">Career context</span><h3 id="job-action-title">AI Recommendations</h3><p>Opportunities based on your skills, goals and current hiring signals.</p></header><div class="job-action-list">${recCards}</div></article></div></section>`;
};
bindJobIntelligenceEvents = function() {
  const button = document.querySelector('#jobTrendFilterButton');
  const panel = document.querySelector('#jobTrendFilterPanel');
  const close = () => { if (panel) panel.hidden = true; button?.setAttribute('aria-expanded','false'); };
  button?.addEventListener('click', event => { event.stopPropagation(); panel.hidden = !panel.hidden; button.setAttribute('aria-expanded',String(!panel.hidden)); });
  document.querySelector('#closeJobTrendFilter')?.addEventListener('click',close);
  if (!jobTrendState.filterDismissBound) {
    document.addEventListener('click',event => { const currentPanel=document.querySelector('#jobTrendFilterPanel'); if(currentPanel&&!currentPanel.hidden&&!event.target.closest('.job-intelligence-context')) { currentPanel.hidden=true; document.querySelector('#jobTrendFilterButton')?.setAttribute('aria-expanded','false'); } });
    document.addEventListener('keydown',event => { if(event.key==='Escape') { const currentPanel=document.querySelector('#jobTrendFilterPanel'); if(currentPanel&&!currentPanel.hidden) { currentPanel.hidden=true; const currentButton=document.querySelector('#jobTrendFilterButton'); currentButton?.setAttribute('aria-expanded','false'); currentButton?.focus(); } } });
    jobTrendState.filterDismissBound=true;
  }
  document.querySelector('#applyJobTrendFilter')?.addEventListener('click',() => { jobTrendState.period = document.querySelector('#jobPeriodFilter').value; jobTrendState.market = document.querySelector('#jobMarketFilter').value; marketTrendState.scope = jobTrendState.market; jobTrendState.role = document.querySelector('#jobRoleFilter').value; dashboardState.selectedSkill = ({'AI / ML Engineer':'Machine Learning','AI Engineer':'Machine Learning','Software Engineer':'JavaScript','Data Scientist':'Data Analytics','Data Analyst':'SQL','UI/UX Designer':'React','Cybersecurity Engineer':'Cybersecurity','Cloud Engineer':'Cloud Computing'}[jobTrendState.role] || dashboardState.selectedSkill); renderHome(); });
  document.querySelectorAll('#job-intelligence .job-radial-ring,#job-intelligence .job-intelligence-legend').forEach(item => {
    const select = () => { jobTrendState.selectedJobSignal = item.dataset.metric; renderHome(); };
    item.addEventListener('click',select); item.addEventListener('keydown',event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } });
    const signal = getJobTrendView().metrics.find(metric => metric.key === item.dataset.metric);
    const meta = {jobDemand:['Open role activity',42180],hiringMomentum:['Hiring company activity',3240],roleGrowth:['Role demand momentum',31560],skillDemand:['Workforce reduction signal',4820]}[item.dataset.metric];
    const show = () => { const tip=document.querySelector('#jobRadialTooltip'); if(!tip)return; tip.innerHTML=`<strong>${meta[0]}</strong><b>${meta[1].toLocaleString()}</b><span>${signal.value}% index · ${signal.change>0?'+':''}${signal.change}% change</span><small>Related: ${item.dataset.metric === 'jobDemand' ? 'AI Engineer, Data Scientist' : item.dataset.metric === 'hiringMomentum' ? 'NVIDIA, Microsoft' : item.dataset.metric === 'roleGrowth' ? 'AI Engineer, ML Engineer' : 'Operations, Support'}</small>`; tip.hidden=false; };
    item.addEventListener('pointerenter',show); item.addEventListener('focus',show); item.addEventListener('pointerleave',()=>{const tip=document.querySelector('#jobRadialTooltip');if(tip)tip.hidden=true;}); item.addEventListener('blur',()=>{const tip=document.querySelector('#jobRadialTooltip');if(tip)tip.hidden=true;});
  });
  document.querySelectorAll('.job-action-item [data-recommendation]').forEach(link => link.addEventListener('click',()=>{jobTrendState.selectedRecommendation=link.dataset.recommendation;}));
};

renderMarketPulse = function() {
  return `<div class="analytics-dashboard-module"><section class="skill-demand-module skill-trend-module">${renderSkillTrendAnalyticsCard()}</section><section class="market-demand-module market-trend-module">${renderMarketTrendCard()}</section><section class="job-trends-module">${renderJobTrendCard()}</section><section class="skill-demand-module top-trending-skills-module">${renderTopTrendingSkillsCard()}</section><section class="market-demand-module analytics-market-companies">${renderTopMarketCompaniesCard()}</section></div>`;
};
bindSkillTrendAnalyticsEvents = function() {
  const filterButton = document.querySelector('#skillFilterButton');
  const filterPanel = document.querySelector('#skillFilterPanel');
  const timeSelect = document.querySelector('#skillFilterTime');
  const marketSelect = document.querySelector('#skillFilterMarket');
  const favoriteButton = document.querySelector('#filterFavoriteButton');
  if (filterButton && filterPanel) filterButton.addEventListener('click', event => { event.stopPropagation(); filterPanel.hidden = !filterPanel.hidden; filterButton.setAttribute('aria-expanded', String(!filterPanel.hidden)); });
  if (timeSelect) timeSelect.addEventListener('change', event => {
    const previousValues = trendDetailsForSkill(dashboardState.selectedSkill).values;
    dashboardState.timeRange = event.target.value;
    refreshSkillIntelligenceSection(previousValues);
    refreshInsightRecommendationSection();
  });
  if (marketSelect) marketSelect.addEventListener('change', event => {
    const previousValues = trendDetailsForSkill(dashboardState.selectedSkill).values;
    dashboardState.market = event.target.value;
    if (event.target.value === 'Global') intelligenceExplorerState.scope = 'Global';
    else intelligenceExplorerState.scope = 'My Market';
    marketTrendState.scope = event.target.value;
    jobTrendState.market = event.target.value;
    refreshExploreDashboard(previousValues);
  });
  if (favoriteButton) favoriteButton.addEventListener('click', () => {
    const skill = dashboardState.selectedSkill;
    const previousValues = trendDetailsForSkill(skill).values;
    const saved = dashboardState.savedSkills.includes(skill);
    dashboardState.savedSkills = saved ? dashboardState.savedSkills.filter(item => item !== skill) : dashboardState.savedSkills.length < 5 ? [...dashboardState.savedSkills, skill] : dashboardState.savedSkills;
    localStorage.setItem('talentscope-saved-skills', JSON.stringify(dashboardState.savedSkills));
    if (intelligenceExplorerState.scope === 'Saved' && !dashboardState.savedSkills.includes(intelligenceExplorerState.selected.skills)) {
      intelligenceExplorerState.selected.skills = dashboardState.savedSkills[0] || '';
      applyExploreSelection();
    }
    refreshExploreDashboard(previousValues);
  });
  const demandFilterButton = document.querySelector('#skillTrendFilterButton');
  const demandFilterPanel = document.querySelector('#skillTrendFilterPanel');
  demandFilterButton?.addEventListener('click', event => { event.stopPropagation(); if (!demandFilterPanel) return; demandFilterPanel.hidden = !demandFilterPanel.hidden; demandFilterButton.setAttribute('aria-expanded', String(!demandFilterPanel.hidden)); });
  document.querySelector('#closeSkillTrendFilter')?.addEventListener('click', () => { if (demandFilterPanel) demandFilterPanel.hidden = true; demandFilterButton?.setAttribute('aria-expanded', 'false'); });
  document.querySelector('#applySkillTrendFilter')?.addEventListener('click', () => {
    const startDate = document.querySelector('#skillIntelStartDate')?.value || '';
    const endDate = document.querySelector('#skillIntelEndDate')?.value || '';
    const endInput = document.querySelector('#skillIntelEndDate');
    if (startDate && endDate && startDate > endDate) { endInput?.setCustomValidity('End date must be after the start date.'); endInput?.reportValidity(); return; }
    endInput?.setCustomValidity('');
    skillTrendFilterState.startDate = startDate; skillTrendFilterState.endDate = endDate;
    dashboardState.trendScope = document.querySelector('#skillIntelScope')?.value || dashboardState.trendScope;
    dashboardState.market = document.querySelector('#skillIntelRegion')?.value || dashboardState.market;
    dashboardState.timeRange = document.querySelector('#skillIntelPeriod')?.value || dashboardState.timeRange;
    marketTrendState.scope = dashboardState.market; jobTrendState.market = dashboardState.market;
    renderHome();
  });
  document.querySelectorAll('.skill-live-bar').forEach(bar => {
    const show = () => bar.classList.add('is-hovered');
    const hide = () => bar.classList.remove('is-hovered');
    bar.addEventListener('mouseenter', show); bar.addEventListener('mouseleave', hide); bar.addEventListener('focus', show); bar.addEventListener('blur', hide);
    bar.addEventListener('click', () => {
      dashboardState.selectedSkill = bar.dataset.skill;
      document.querySelectorAll('.skill-live-bar').forEach(candidate => { const selected = candidate === bar; candidate.classList.toggle('is-selected', selected); candidate.setAttribute('aria-pressed', String(selected)); });
      document.querySelectorAll('.skill-momentum-row').forEach(row => { const selected = row.dataset.skill === bar.dataset.skill; row.classList.toggle('is-selected', selected); row.setAttribute('aria-pressed', String(selected)); });
      const featured = document.querySelector('[data-featured-skill]');
      if (!featured) return;
      featured.querySelector('[data-featured-name]').textContent = bar.dataset.skill;
      featured.querySelector('[data-featured-category]').textContent = bar.dataset.category;
      featured.querySelector('[data-featured-demand]').textContent = bar.dataset.demand;
      featured.querySelector('.skill-live-highlight__score > i b').style.setProperty('--score', `${bar.dataset.demand}%`);
      featured.querySelector('[data-featured-growth]').innerHTML = `<i data-lucide="trending-up"></i>+${bar.dataset.change}%`;
      lucide.createIcons();
    });
  });
  document.querySelectorAll('.skill-momentum-row').forEach(row => row.addEventListener('click', () => document.querySelector(`.skill-live-bar[data-skill="${CSS.escape(row.dataset.skill)}"]`)?.click()));
};

renderNavigation();
updateUserDetails();
setSidebarExpanded(localStorage.getItem('talentscope-sidebar-expanded') === 'true');
renderPage();
function refreshSkillTrendModule() {
  const module = document.querySelector('.skill-trend-module');
  if (!module) return;
  module.classList.add('is-refreshing');
  window.setTimeout(() => {
    if (!module.isConnected) return;
    module.innerHTML = renderSkillTrendAnalyticsCard();
    module.classList.remove('is-refreshing');
    lucide.createIcons();
    bindSkillTrendAnalyticsEvents();
  }, 120);
}
function refreshMarketTrendModule() {
  const module = document.querySelector('.market-trend-module');
  if (!module) return;
  const companyList = document.querySelector('.analytics-market-companies');
  module.classList.add('is-refreshing');
  companyList?.classList.add('is-refreshing');
  window.setTimeout(() => {
    if (!module.isConnected) return;
    module.innerHTML = renderMarketTrendCard({ home: true });
    if (companyList?.isConnected) companyList.innerHTML = renderTopMarketCompaniesCard();
    module.classList.remove('is-refreshing');
    companyList?.classList.remove('is-refreshing');
    lucide.createIcons();
    bindMarketTrendEvents();
  }, 120);
}
setInterval(() => { if (currentRoute().split('?')[0] === '/individual/home') { liveTrendTick += 1; refreshSkillTrendModule(); } }, 600000);

window.addEventListener('hashchange', renderPage);
sidebarToggle.addEventListener('click', () => setSidebarExpanded(!sidebar.classList.contains('is-expanded')));
mobileMenu.addEventListener('click', openMobileNav);
mobileScrim.addEventListener('click', closeMobileNav);
profileTrigger.addEventListener('click', event => { event.stopPropagation(); const willOpen = profilePopover.hidden; closePopovers(); profilePopover.hidden = !willOpen; profileTrigger.setAttribute('aria-expanded', String(willOpen)); });
notificationButton.addEventListener('click', event => { event.stopPropagation(); const willOpen = notificationPopover.hidden; closePopovers(); notificationPopover.hidden = !willOpen; notificationButton.setAttribute('aria-expanded', String(willOpen)); });
document.addEventListener('click', event => { if (!event.target.closest('.profile-menu') && !event.target.closest('.notification-button')) closePopovers(); });
document.querySelector('#searchForm').addEventListener('submit', event => event.preventDefault());
document.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); document.querySelector('#searchInput').focus(); } if (event.key === 'Escape') { closePopovers(); closeMobileNav(); } });
