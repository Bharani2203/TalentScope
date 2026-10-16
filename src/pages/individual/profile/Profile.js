/**
 * TalentScope.ai - Dedicated Individual Profile Page
 * High-fidelity profile with deep intelligence integration
 */

import { updatePlatformUser } from '../../../data/platform-state.js';

const PROFILE_STORAGE_KEY = 'talentscope-user-profile-v1';

const defaultProfileData = {
  name: 'Arun Sharma',
  shortName: 'Arun',
  initials: 'AS',
  headline: 'Lead AI/ML Developer & LLM Systems Engineer',
  currentRole: 'Senior AI/ML Developer',
  targetRole: 'Principal Applied AI Engineer',
  location: 'Bengaluru, India',
  timezone: 'IST (UTC+5:30)',
  experienceYears: '5.5 Years',
  industry: 'Enterprise AI & Autonomous Systems',
  targetSalary: '₹45L - ₹60L / $145,000+',
  workPreference: 'Remote / Hybrid',
  availability: 'Open to High-Signal Roles',
  completionScore: 84,
  bio: 'Specialized in multi-agent orchestration, RAG architectures, model fine-tuning (LoRA/QLoRA), and scalable inference pipelines. Passionate about bringing production-grade LLM applications from research to high-throughput deployment.',
  activeTab: 'overview',
  skills: [
    { name: 'Generative AI', level: 'Expert', score: 94, benchmark: 'Top 3% Global', category: 'AI/ML Core' },
    { name: 'PyTorch', level: 'Advanced', score: 91, benchmark: 'Top 5% Global', category: 'AI/ML Core' },
    { name: 'LangChain & LlamaIndex', level: 'Advanced', score: 88, benchmark: 'Top 7% Global', category: 'Modern LLM Stack' },
    { name: 'Transformers', level: 'Advanced', score: 89, benchmark: 'Top 6% Global', category: 'Modern LLM Stack' },
    { name: 'Python', level: 'Expert', score: 96, benchmark: 'Top 2% Global', category: 'Engineering' },
    { name: 'Vector Databases (Pinecone/Milvus)', level: 'Proficient', score: 84, benchmark: 'Top 12% Global', category: 'Modern LLM Stack' },
    { name: 'Kubernetes & Docker', level: 'Proficient', score: 80, benchmark: 'Top 15% Global', category: 'Infrastructure' },
    { name: 'SQL & Data Pipelines', level: 'Advanced', score: 86, benchmark: 'Top 10% Global', category: 'Engineering' }
  ],
  experiences: [
    {
      role: 'Lead AI/ML Developer',
      company: 'CloudNova Systems',
      period: '2023 - Present (1.5 yrs)',
      description: 'Architected enterprise multi-agent RAG workflow reducing hallucination by 42% across 1.2M monthly queries. Spearheaded quantization pipeline saving 35% GPU memory overhead.',
      tags: ['Multi-Agent', 'vLLM', 'LoRA', 'Kubernetes']
    },
    {
      role: 'Senior Data Scientist / ML Engineer',
      company: 'HyperScale Analytics',
      period: '2021 - 2023 (2 yrs)',
      description: 'Developed production recommendation pipelines serving 8M daily active users. Automated continuous training loops and model monitoring dashboards using MLflow and Prometheus.',
      tags: ['PyTorch', 'Distributed Training', 'MLflow', 'FastAPI']
    },
    {
      role: 'Machine Learning Engineer',
      company: 'TechMatrix Labs',
      period: '2019 - 2021 (2 yrs)',
      description: 'Implemented computer vision and NLP classification systems. Containerized microservices and led migration from monolith to cloud-native microservices.',
      tags: ['Python', 'Docker', 'Scikit-learn', 'PostgreSQL']
    }
  ],
  certifications: [
    { title: 'TalentScope Certified: Principal AI Architect', issuer: 'TalentScope Benchmark Suite', date: 'August 2024', id: 'TS-AI-9942' },
    { title: 'AWS Certified Machine Learning - Specialty', issuer: 'Amazon Web Services', date: 'November 2023', id: 'AWS-ML-5521' },
    { title: 'Deep Learning Specialization', issuer: 'DeepLearning.AI', date: 'May 2022', id: 'DLAI-8831' }
  ]
};

function getProfileState() {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return { ...defaultProfileData };
    return { ...defaultProfileData, ...JSON.parse(raw) };
  } catch (e) {
    return { ...defaultProfileData };
  }
}

function saveProfileState(data) {
  try {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.error('Failed to save profile state', e);
  }
}

let activeProfileState = getProfileState();
let rootContainer = null;
let currentActions = {};

export function renderProfilePage({ context = {}, actions = {} } = {}) {
  currentActions = actions;
  rootContainer = document.getElementById('mainContent');
  if (!rootContainer) return;

  if (context.user && context.user.name) {
    activeProfileState.name = context.user.name;
    activeProfileState.shortName = context.user.shortName || 'Arun';
  }

  drawProfile();
}

function drawProfile() {
  if (!rootContainer) return;

  const data = activeProfileState;
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (data.completionScore / 100) * circumference;

  rootContainer.innerHTML = `
    <div class="ts-profile-page">
      <!-- Hero Banner -->
      <section class="profile-hero-card" aria-label="Profile Overview">
        <svg width="0" height="0" style="position: absolute;">
          <defs>
            <linearGradient id="profileGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#B22DEF" />
              <stop offset="100%" stop-color="#42075D" />
            </linearGradient>
          </defs>
        </svg>

        <div class="profile-hero-main">
          <div class="profile-identity-wrap">
            <div class="profile-avatar-large">
              ${data.initials}
              <span class="profile-avatar-status" title="${data.availability}"></span>
            </div>
            <div class="profile-meta-block">
              <div class="profile-name-row">
                <h1 class="profile-name">${data.name}</h1>
                <span class="profile-badge-pro"><i data-lucide="user-round-check"></i> Profile Preview</span>
              </div>
              <p class="profile-headline">${data.headline}</p>
              <div class="profile-pills-row">
                <span class="profile-pill-item"><i data-lucide="map-pin"></i> ${data.location}</span>
                <span class="profile-pill-item"><i data-lucide="clock-3"></i> ${data.timezone}</span>
                <span class="profile-pill-item"><i data-lucide="briefcase"></i> ${data.experienceYears} Experience</span>
                <span class="profile-pill-item"><i data-lucide="building-2"></i> ${data.industry}</span>
              </div>
            </div>
          </div>

          <!-- Profile Completion Widget -->
          <div class="profile-completion-box">
            <div class="completion-ring-wrap">
              <svg class="completion-ring-svg" viewBox="0 0 64 64">
                <circle class="completion-ring-track" cx="32" cy="32" r="${radius}"></circle>
                <circle class="completion-ring-bar" cx="32" cy="32" r="${radius}" 
                  stroke-dasharray="${circumference}" 
                  stroke-dashoffset="${offset}"></circle>
              </svg>
              <span class="completion-ring-text">${data.completionScore}%</span>
            </div>
            <div class="completion-text-wrap">
              <h4 class="completion-title">Profile Strength: High</h4>
              <p class="completion-hint">+8% with verified benchmark assessment</p>
            </div>
          </div>
        </div>

        <!-- Action Bar -->
        <div class="profile-actions-bar">
          <div class="profile-action-status-signal">
            <span class="pulse-dot"></span>
            <span>${data.availability}</span>
          </div>

          <div class="profile-btn-group">
            <button class="btn-profile-secondary" id="btnShareProfile" type="button">
              <i data-lucide="share-2"></i> Share Profile
            </button>
            <button class="btn-profile-primary" id="btnEditProfile" type="button">
              <i data-lucide="edit-3"></i> Edit Profile
            </button>
          </div>
        </div>
      </section>

      <!-- Navigation Tabs -->
      <nav class="profile-nav-tabs" role="tablist">
        <button class="profile-tab-btn ${data.activeTab === 'overview' ? 'is-active' : ''}" data-tab="overview" role="tab">
          <i data-lucide="layout-dashboard"></i> Overview
        </button>
        <button class="profile-tab-btn ${data.activeTab === 'skills' ? 'is-active' : ''}" data-tab="skills" role="tab">
          <i data-lucide="layers-3"></i> Skills & Benchmarks
        </button>
        <button class="profile-tab-btn ${data.activeTab === 'experience' ? 'is-active' : ''}" data-tab="experience" role="tab">
          <i data-lucide="briefcase"></i> Experience & Projects
        </button>
        <button class="profile-tab-btn ${data.activeTab === 'credentials' ? 'is-active' : ''}" data-tab="credentials" role="tab">
          <i data-lucide="award"></i> Credentials & Badges
        </button>
      </nav>

      <!-- Tab Content Grid -->
      <div class="profile-content-grid">
        ${renderTabContent(data)}
      </div>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  attachEventListeners();
}

function renderTabContent(data) {
  if (data.activeTab === 'skills') {
    return `
      <div class="profile-main-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="layers-3"></i></span>
              <div>
                <h3 class="profile-card-title">Declared Skills & Illustrative Benchmarks</h3>
                <p class="profile-card-subtitle">Illustrative profile values; live external assessment data is not connected</p>
              </div>
            </div>
            <a href="#/individual/skills" class="btn-profile-secondary" style="font-size: 12px; padding: 6px 12px;">
              <i data-lucide="sparkles"></i> Open Skill Intelligence
            </a>
          </div>

          <div class="profile-skills-grid">
            ${data.skills.map(s => `
              <div class="profile-skill-card">
                <div class="profile-skill-header">
                  <span class="profile-skill-name">${s.name}</span>
                  <span class="profile-skill-badge">${s.level}</span>
                </div>
                <div class="profile-skill-bar-wrap">
                  <div class="profile-skill-bar-fill" style="width: ${s.score}%"></div>
                </div>
                <div class="profile-skill-footer">
                  <span>Score: ${s.score}/100</span>
                  <strong style="color: #B22DEF">${s.benchmark}</strong>
                </div>
              </div>
            `).join('')}
          </div>
        </article>
      </div>

      <div class="profile-side-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="target"></i></span>
              <div>
                <h3 class="profile-card-title">Target Capability Match</h3>
                <p class="profile-card-subtitle">For ${data.targetRole}</p>
              </div>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div style="display: flex; justify-content: space-between; font-size: 13px;">
              <span>Role Readiness Index</span>
              <strong style="color: #10B981">88% Ready</strong>
            </div>
            <div class="profile-skill-bar-wrap">
              <div class="profile-skill-bar-fill" style="width: 88%; background: linear-gradient(90deg, #10B981, #B22DEF);"></div>
            </div>
            <p style="font-size: 12px; color: #796B88; margin: 0; line-height: 1.4;">
              Top gap to close: <strong>Distributed Model Serving (vLLM / Triton)</strong>. Closing this elevates readiness to 96%.
            </p>
            <a href="#/individual/learning" class="btn-profile-primary" style="justify-content: center; margin-top: 6px;">
              <i data-lucide="book-open"></i> Go to Learning Roadmap
            </a>
          </div>
        </article>
      </div>
    `;
  }

  if (data.activeTab === 'experience') {
    return `
      <div class="profile-main-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="history"></i></span>
              <div>
                <h3 class="profile-card-title">Work Experience & Production Impact</h3>
                <p class="profile-card-subtitle">Illustrative career milestones and technical contribution examples</p>
              </div>
            </div>
          </div>

          <div class="experience-timeline">
            ${data.experiences.map(exp => `
              <div class="timeline-item">
                <span class="timeline-dot"></span>
                <h4 class="timeline-role">${exp.role}</h4>
                <div class="timeline-company">${exp.company} &bull; ${exp.period}</div>
                <p class="timeline-desc">${exp.description}</p>
                <div class="timeline-tags">
                  ${exp.tags.map(t => `<span class="timeline-tag">${t}</span>`).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        </article>
      </div>

      <div class="profile-side-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="folder-git-2"></i></span>
              <div>
                <h3 class="profile-card-title">Key Projects</h3>
                <p class="profile-card-subtitle">Public repositories & demos</p>
              </div>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div class="target-stat-tile">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 13px; color: #1a1126;">AgentMesh-Core</strong>
                <span style="font-size: 11px; color: #B22DEF; font-weight: 700;">★ 420 Stars</span>
              </div>
              <p style="font-size: 12px; color: #554863; margin: 4px 0 0 0;">High-throughput multi-agent messaging protocol for localized LLMs.</p>
            </div>
            <div class="target-stat-tile">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 13px; color: #1a1126;">Eval-SmallLM</strong>
                <span style="font-size: 11px; color: #B22DEF; font-weight: 700;">★ 185 Stars</span>
              </div>
              <p style="font-size: 12px; color: #554863; margin: 4px 0 0 0;">Automated rubric benchmark for quantized reasoning models.</p>
            </div>
          </div>
        </article>
      </div>
    `;
  }

  if (data.activeTab === 'credentials') {
    return `
      <div class="profile-main-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="award"></i></span>
              <div>
                <h3 class="profile-card-title">Badge & Industry Credential Examples</h3>
                <p class="profile-card-subtitle">Cryptographically verified proof of competence</p>
              </div>
            </div>
          </div>

          <div class="badges-list">
            ${data.certifications.map(cert => `
              <div class="badge-row-card">
                <div class="badge-row-icon"><i data-lucide="shield-check"></i></div>
                <div class="badge-row-info">
                  <strong>${cert.title}</strong>
                  <small>${cert.issuer} &bull; Issued ${cert.date} &bull; ID: ${cert.id}</small>
                </div>
              </div>
            `).join('')}
          </div>
        </article>
      </div>

      <div class="profile-side-col">
        <article class="profile-card">
          <div class="profile-card-header">
            <div class="profile-card-title-group">
              <span class="profile-card-title-icon"><i data-lucide="check-circle-2"></i></span>
              <div>
                <h3 class="profile-card-title">Assessment Status</h3>
                <p class="profile-card-subtitle">Continuous evaluation</p>
              </div>
            </div>
          </div>
          <p style="font-size: 13px; color: #554863; line-height: 1.45;">
            Your credentials were benchmarked against 14,200+ industry professionals in Enterprise AI.
          </p>
          <a href="#/individual/career" class="btn-profile-secondary" style="justify-content: center; margin-top: 10px;">
            <i data-lucide="briefcase"></i> View Matching Jobs
          </a>
        </article>
      </div>
    `;
  }

  // Default: Overview tab
  return `
    <div class="profile-main-col">
      <!-- Target Career Alignment -->
      <article class="profile-card">
        <div class="profile-card-header">
          <div class="profile-card-title-group">
            <span class="profile-card-title-icon"><i data-lucide="compass"></i></span>
            <div>
              <h3 class="profile-card-title">Career Identity & Strategic Objective</h3>
              <p class="profile-card-subtitle">Where you stand today and where your profile is positioned</p>
            </div>
          </div>
        </div>

        <div class="career-target-grid">
          <div class="target-stat-tile">
            <div class="target-stat-label">Current Role</div>
            <div class="target-stat-val">${data.currentRole}</div>
          </div>
          <div class="target-stat-tile">
            <div class="target-stat-label">Target Role</div>
            <div class="target-stat-val" style="color: #B22DEF">${data.targetRole}</div>
          </div>
          <div class="target-stat-tile">
            <div class="target-stat-label">Target Compensation Band</div>
            <div class="target-stat-val">${data.targetSalary}</div>
          </div>
          <div class="target-stat-tile">
            <div class="target-stat-label">Work Model & Location</div>
            <div class="target-stat-val">${data.workPreference} <small>(${data.location})</small></div>
          </div>
        </div>

        <div style="margin-top: 18px; padding-top: 16px; border-top: 1px solid #F5F0FA;">
          <h4 style="font-size: 13px; font-weight: 700; color: #554863; margin: 0 0 6px 0; text-transform: uppercase; letter-spacing: 0.05em;">Professional Bio</h4>
          <p style="font-size: 14px; color: #1a1126; line-height: 1.5; margin: 0;">${data.bio}</p>
        </div>
      </article>

      <!-- Key Skill Highlights -->
      <article class="profile-card">
        <div class="profile-card-header">
          <div class="profile-card-title-group">
            <span class="profile-card-title-icon"><i data-lucide="cpu"></i></span>
            <div>
              <h3 class="profile-card-title">Core Skills Overview</h3>
              <p class="profile-card-subtitle">High-signal capabilities powering your career match</p>
            </div>
          </div>
          <button class="btn-profile-secondary" id="btnViewAllSkills" type="button" style="font-size: 12px; padding: 6px 12px;">
            View All (${data.skills.length})
          </button>
        </div>

        <div class="profile-skills-grid">
          ${data.skills.slice(0, 4).map(s => `
            <div class="profile-skill-card">
              <div class="profile-skill-header">
                <span class="profile-skill-name">${s.name}</span>
                <span class="profile-skill-badge">${s.level}</span>
              </div>
              <div class="profile-skill-bar-wrap">
                <div class="profile-skill-bar-fill" style="width: ${s.score}%"></div>
              </div>
              <div class="profile-skill-footer">
                <span>Score: ${s.score}/100</span>
                <strong style="color: #B22DEF">${s.benchmark}</strong>
              </div>
            </div>
          `).join('')}
        </div>
      </article>
    </div>

    <div class="profile-side-col">
      <!-- Quick Actions / Intelligence Bridge -->
      <article class="profile-card">
        <div class="profile-card-header">
          <div class="profile-card-title-group">
            <span class="profile-card-title-icon"><i data-lucide="sparkles"></i></span>
            <div>
              <h3 class="profile-card-title">Intelligence Shortcuts</h3>
              <p class="profile-card-subtitle">Connected portal modules</p>
            </div>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 10px;">
          <a href="#/individual/skills" class="target-stat-tile" style="text-decoration: none; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 13px; color: #1a1126;">Skill Intelligence</div>
              <small style="color: #796B88;">Inspect depth & demand shifts</small>
            </div>
            <i data-lucide="arrow-right" style="color: #B22DEF; width: 16px;"></i>
          </a>
          <a href="#/individual/learning" class="target-stat-tile" style="text-decoration: none; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 13px; color: #1a1126;">Active Learning Path</div>
              <small style="color: #796B88;">LLM Systems & Multi-Agent RAG</small>
            </div>
            <i data-lucide="arrow-right" style="color: #B22DEF; width: 16px;"></i>
          </a>
          <a href="#/individual/career" class="target-stat-tile" style="text-decoration: none; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-weight: 700; font-size: 13px; color: #1a1126;">Job Intelligence</div>
              <small style="color: #796B88;">Role alignment & requisitions</small>
            </div>
            <i data-lucide="arrow-right" style="color: #B22DEF; width: 16px;"></i>
          </a>
        </div>
      </article>

      <!-- Profile Visibility Settings Card -->
      <article class="profile-card">
        <div class="profile-card-header">
          <div class="profile-card-title-group">
            <span class="profile-card-title-icon"><i data-lucide="eye"></i></span>
            <div>
              <h3 class="profile-card-title">Profile Visibility</h3>
              <p class="profile-card-subtitle">Recruiter discovery settings</p>
            </div>
          </div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px; font-size: 13px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #554863;">Discovery Status</span>
            <strong style="color: #10B981;">Public to Employers</strong>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #554863;">Direct Inquiries</span>
            <strong>Enabled</strong>
          </div>
          <a href="#/individual/settings" class="btn-profile-secondary" style="justify-content: center; margin-top: 6px;">
            <i data-lucide="settings-2"></i> Manage in Settings
          </a>
        </div>
      </article>
    </div>
  `;
}

function attachEventListeners() {
  // Tab Switching
  document.querySelectorAll('.profile-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-tab');
      if (tab) {
        activeProfileState.activeTab = tab;
        drawProfile();
      }
    });
  });

  const btnViewAll = document.getElementById('btnViewAllSkills');
  if (btnViewAll) {
    btnViewAll.addEventListener('click', () => {
      activeProfileState.activeTab = 'skills';
      drawProfile();
    });
  }

  // Share Profile
  const btnShare = document.getElementById('btnShareProfile');
  if (btnShare) {
    btnShare.addEventListener('click', () => {
      const shareUrl = window.location.href;
      navigator.clipboard?.writeText?.(shareUrl).then(() => {
        showToast('Profile URL copied to clipboard!');
      }).catch(() => {
        showToast('Profile link: ' + shareUrl);
      });
    });
  }

  // Edit Profile Modal
  const btnEdit = document.getElementById('btnEditProfile');
  if (btnEdit) {
    btnEdit.addEventListener('click', openEditModal);
  }
}

function openEditModal() {
  const modalContainer = document.createElement('div');
  modalContainer.className = 'ts-modal-overlay';
  modalContainer.id = 'editProfileModal';

  modalContainer.innerHTML = `
    <div class="ts-modal-card" role="dialog" aria-modal="true" aria-labelledby="editModalTitle">
      <div class="ts-modal-header">
        <h3 id="editModalTitle">Edit Individual Profile</h3>
        <button type="button" class="btn-profile-secondary" id="modalCloseBtn" style="padding: 6px 10px; border: none;">
          <i data-lucide="x"></i>
        </button>
      </div>
      <div class="ts-modal-body">
        <div class="ts-input-group">
          <label for="inputProfileName">Full Name</label>
          <input type="text" id="inputProfileName" value="${activeProfileState.name}" />
        </div>
        <div class="ts-input-group">
          <label for="inputHeadline">Professional Headline</label>
          <input type="text" id="inputHeadline" value="${activeProfileState.headline}" />
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div class="ts-input-group">
            <label for="inputCurrentRole">Current Role</label>
            <input type="text" id="inputCurrentRole" value="${activeProfileState.currentRole}" />
          </div>
          <div class="ts-input-group">
            <label for="inputTargetRole">Target Role</label>
            <input type="text" id="inputTargetRole" value="${activeProfileState.targetRole}" />
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
          <div class="ts-input-group">
            <label for="inputLocation">Location</label>
            <input type="text" id="inputLocation" value="${activeProfileState.location}" />
          </div>
          <div class="ts-input-group">
            <label for="inputSalary">Target Compensation</label>
            <input type="text" id="inputSalary" value="${activeProfileState.targetSalary}" />
          </div>
        </div>
        <div class="ts-input-group">
          <label for="inputBio">Professional Bio</label>
          <textarea id="inputBio" rows="4">${activeProfileState.bio}</textarea>
        </div>
      </div>
      <div class="ts-modal-footer">
        <button type="button" class="btn-profile-secondary" id="modalCancelBtn">Cancel</button>
        <button type="button" class="btn-profile-primary" id="modalSaveBtn">Save Changes</button>
      </div>
    </div>
  `;

  document.body.appendChild(modalContainer);
  if (window.lucide) window.lucide.createIcons();

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') close();
  };
  window.addEventListener('keydown', handleKeyDown);

  const close = () => {
    window.removeEventListener('keydown', handleKeyDown);
    modalContainer.remove();
  };

  modalContainer.addEventListener('click', (e) => {
    if (e.target === modalContainer) close();
  });

  document.getElementById('modalCloseBtn')?.addEventListener('click', close);
  document.getElementById('modalCancelBtn')?.addEventListener('click', close);

  document.getElementById('modalSaveBtn')?.addEventListener('click', () => {
    const newName = document.getElementById('inputProfileName')?.value?.trim();
    const newHeadline = document.getElementById('inputHeadline')?.value?.trim();
    const newCurrentRole = document.getElementById('inputCurrentRole')?.value?.trim();
    const newTargetRole = document.getElementById('inputTargetRole')?.value?.trim();
    const newLocation = document.getElementById('inputLocation')?.value?.trim();
    const newSalary = document.getElementById('inputSalary')?.value?.trim();
    const newBio = document.getElementById('inputBio')?.value?.trim();

    if (newName) {
      activeProfileState.name = newName;
      activeProfileState.shortName = newName.split(' ')[0] || newName;
      activeProfileState.initials = newName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    }
    if (newHeadline) activeProfileState.headline = newHeadline;
    if (newCurrentRole) activeProfileState.currentRole = newCurrentRole;
    if (newTargetRole) activeProfileState.targetRole = newTargetRole;
    if (newLocation) activeProfileState.location = newLocation;
    if (newSalary) activeProfileState.targetSalary = newSalary;
    if (newBio) activeProfileState.bio = newBio;

    saveProfileState(activeProfileState);
    updatePlatformUser({
      name: activeProfileState.name,
      role: activeProfileState.currentRole
    });

    close();
    drawProfile();
    showToast('Profile updated successfully!');
  });
}

function showToast(message) {
  const existing = document.querySelector('.ts-toast-banner');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'ts-toast-banner';
  toast.innerHTML = `<i data-lucide="check-circle" style="color: #10B981; width: 18px; height: 18px;"></i> <span>${message}</span>`;
  document.body.appendChild(toast);
  if (window.lucide) window.lucide.createIcons();

  setTimeout(() => {
    toast.remove();
  }, 3200);
}
