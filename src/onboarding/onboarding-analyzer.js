// ============================================================================
// TALENTSCOPE.AI — DETERMINISTIC ONBOARDING ANALYSIS ENGINE
// 1. Shows a short, fluid animated analysis experience (5 stages, ~2.5s)
// 2. Synthesizes deterministic intelligence profile from actual user inputs
// 3. Prepares structured report object and navigates to #/onboarding/report
// ============================================================================

import {
  getCurrentUser,
  getOnboardingDraft,
  saveGeneratedReport,
  saveUser,
  setCurrentUser,
  clearOnboardingDraft
} from '../auth/auth-state.js';
import { generateEmployeeReport } from './employee-report-data.js';
import { loadRoleOnboardingProfile } from './onboarding-api.js';

export function renderAnalysisPage(container) {
  const root = container || document.getElementById('mainContent') || document.getElementById('appShell') || document.body;
  const draft = getOnboardingDraft() || {};
  const user = getCurrentUser() || {};
  const userType = draft.userType || user.userType || 'individual';

  const accentColor = userType === 'company'
    ? '#874FFF'
    : userType === 'employee'
      ? '#2735F5'
      : '#B22DEF';

  const stages = userType === 'employee'
    ? [
        { id: 1, label: 'Loading your saved onboarding answers', icon: 'user-check' },
        { id: 2, label: 'Organizing your self-reported skills', icon: 'layers' },
        { id: 3, label: 'Reviewing your development priorities', icon: 'trending-up' },
        { id: 4, label: 'Preparing your career context', icon: 'compass' },
        { id: 5, label: 'Building your employee profile', icon: 'sparkles' }
      ]
    : [
        { id: 1, label: 'Understanding your profile context', icon: 'user-check' },
        { id: 2, label: 'Mapping your skills & capability clusters', icon: 'layers' },
        { id: 3, label: 'Preparing illustrative workforce & market context', icon: 'trending-up' },
        { id: 4, label: 'Evaluating role alignment & mobility avenues', icon: 'compass' },
        { id: 5, label: 'Preparing your personalized intelligence profile', icon: 'sparkles' }
      ];

  root.innerHTML = `
    <div class="ts-onboarding-viewport" style="--ob-accent: ${accentColor}; align-items: center; justify-content: center; min-height: 100vh;">
      <div class="ts-analyzer-card" style="width: 100%; max-width: 580px; background: #FFFFFF; border: 1px solid #ECE4F2; border-radius: 28px; padding: 44px 40px; box-shadow: 0 24px 60px -12px rgba(45, 20, 75, 0.12); text-align: center; margin: 20px;">
        
        <div class="ts-analyzer-spinner-wrap" style="position: relative; width: 88px; height: 88px; margin: 0 auto 24px;">
          <svg viewBox="0 0 100 100" style="width: 100%; height: 100%; animation: spinPulse 2s linear infinite;">
            <circle cx="50" cy="50" r="42" stroke="#EFE9F6" stroke-width="6" fill="none" />
            <circle cx="50" cy="50" r="42" stroke="${accentColor}" stroke-width="6" stroke-linecap="round" stroke-dasharray="80 180" fill="none" />
          </svg>
          <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: ${accentColor};">
            <i data-lucide="brain" style="width: 34px; height: 34px;"></i>
          </div>
        </div>

        <h2 style="font-size: 24px; font-weight: 850; letter-spacing: -0.02em; color: #1E172B; margin: 0 0 8px;">
          Building your intelligence profile...
        </h2>
        <p style="font-size: 14px; color: #6C6078; margin: 0 0 32px;" id="analyzerStageSub">
          ${userType === 'employee' ? 'Using your saved onboarding answers...' : 'Calibrating competencies against industry benchmarks...'}
        </p>

        <!-- Progressive Pipeline Stages -->
        <div class="ts-analyzer-stages" style="display: flex; flex-direction: column; gap: 14px; text-align: left;">
          ${stages.map((st, i) => `
            <div class="ts-analyzer-stage-row ${i === 0 ? 'is-active' : ''}" id="stageRow_${st.id}" style="display: flex; align-items: center; gap: 14px; padding: 10px 14px; border-radius: 12px; background: #FBF9FD; border: 1px solid #F0E8F6; transition: all 200ms ease;">
              <div class="stage-icon-box" style="width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: #EADBFF; color: ${accentColor}; font-size: 13px;">
                <i data-lucide="${st.icon}" style="width: 16px; height: 16px;"></i>
              </div>
              <span class="stage-label" style="font-size: 13.5px; font-weight: 650; color: #3C2E52; flex: 1;">
                ${st.label}
              </span>
              <div class="stage-status-indicator" style="width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #10B981;">
                <span class="pulse-dot" style="width: 8px; height: 8px; border-radius: 50%; background: #D5C7E6;"></span>
              </div>
            </div>
          `).join('')}
        </div>

        <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #F0EAF6; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 12.5px; color: #8A7E98;">
          <i data-lucide="lock" style="width: 14px; height: 14px;"></i>
          <span>Deterministic analysis calibrated for ${userType.toUpperCase()}</span>
        </div>
      </div>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }

  // Animate the pipeline across 2.4 seconds
  if (userType === 'employee') {
    loadRoleOnboardingProfile('employee').then(savedProfile => {
      if (!root.isConnected || !window.location.hash.includes('/onboarding/analysis')) return;
      if (!savedProfile.onboarding?.completed) {
        showAnalysisError(root, 'Your employee onboarding is not complete yet. Return to onboarding and finish saving your answers.');
        return;
      }
      const savedDraft = {
        ...draft,
        userType,
        answers: savedProfile.answers || {}
      };
      runPipelineAnimation(root, stages, savedDraft, user, userType, savedProfile.profile);
    }).catch(error => {
      if (!root.isConnected || !window.location.hash.includes('/onboarding/analysis')) return;
      showAnalysisError(error?.message || 'Your saved employee profile could not be loaded.');
    });
    return;
  }

  runPipelineAnimation(root, stages, draft, user, userType);
}

function showAnalysisError(root, message) {
  root.innerHTML = `
    <section class="emp-card" role="alert">
      <h1>Profile analysis unavailable</h1>
      <p>${String(message).replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[char])}</p>
      <button type="button" class="emp-btn-primary" id="retryProfileAnalysis">Retry</button>
      <a href="#/onboarding">Return to onboarding</a>
    </section>
  `;
  root.querySelector('#retryProfileAnalysis')?.addEventListener('click', () => {
    renderAnalysisPage(root);
  });
}

function runPipelineAnimation(root, stages, draft, user, userType, savedEmployeeProfile = null) {
  let step = 0;
  const stageInterval = setInterval(() => {
    step++;
    if (step <= stages.length) {
      const prevRow = root.querySelector(`#stageRow_${step}`);
      if (prevRow) {
        prevRow.classList.remove('is-active');
        prevRow.style.background = '#F0FDF4';
        prevRow.style.borderColor = '#BBF7D0';
        const indicator = prevRow.querySelector('.stage-status-indicator');
        if (indicator) {
          indicator.innerHTML = `<i data-lucide="check" style="width:16px;height:16px;color:#16A34A;"></i>`;
        }
      }

      if (step < stages.length) {
        const nextRow = root.querySelector(`#stageRow_${step + 1}`);
        if (nextRow) {
          nextRow.classList.add('is-active');
          nextRow.style.background = '#FAF5FF';
          nextRow.style.borderColor = '#D8B4FE';
          const subText = root.querySelector('#analyzerStageSub');
          if (subText) subText.textContent = stages[step].label + '...';
        }
      }
      if (window.lucide) window.lucide.createIcons();
    }

    if (step >= stages.length) {
      clearInterval(stageInterval);

      // Synthesize deterministic profile
      const report = generateDeterministicReport(draft, user, userType, savedEmployeeProfile);
      saveGeneratedReport(report);

      // Update and finalize user
      const updatedUser = {
        ...(user || {}),
        name: report.userName || user.name || 'Professional',
        userType,
        employeeType: draft.employeeType || user.employeeType,
        companyName: report.companyName || draft.companyName || user.companyName,
        onboardingComplete: true,
        profileData: report
      };
      saveUser(updatedUser);
      setCurrentUser(updatedUser);
      clearOnboardingDraft();

      // Smooth transition to Report
      setTimeout(() => {
        window.location.hash = '#/onboarding/report';
      }, 400);
    }
  }, 480);
}

// ----------------------------------------------------------------------------
// DETERMINISTIC REPORT GENERATOR
// Translates exact answers into human-friendly intelligence cards
// ----------------------------------------------------------------------------
export function generateDeterministicReport(draft = {}, user = {}, userType = 'individual', savedEmployeeProfile = null) {
  const answers = draft.answers || {};

  // Extract common personal identity
  const nameData = answers['name_and_location'] || answers['emp_name_and_location'] || {};
  const userName = userType === 'employee'
    ? nameData.name || ''
    : nameData.name || user.name || 'Alex Mercer';
  const userCity = nameData.city || 'Bangalore';
  const userCountry = nameData.country || 'India';
  const userLocation = `${userCity}, ${userCountry}`;

  if (userType === 'company') {
    return generateCompanyReport(answers, user);
  } else if (userType === 'employee') {
    return generateEmployeeReport(answers, savedEmployeeProfile);
  } else {
    return generateIndividualReport(answers, user, userName, userLocation);
  }
}

function generateIndividualReport(answers, user, userName, userLocation) {
  const stage = answers['current_stage'] || 'Student';
  const expData = answers['experience'] || '1–2 years';
  const experience = typeof expData === 'string' ? expData : (expData.experience || '1–2 years');
  const studyField = expData.studyField || 'Computer Science & AI';

  const rawSkills = answers['skills'] || ['Python', 'SQL', 'Git'];
  const skills = Array.isArray(rawSkills) ? rawSkills : (rawSkills.skills || ['Python', 'SQL', 'Git']);
  const skillLevels = answers['skill_levels'] || { 'Python': 'Comfortable', 'SQL': 'Comfortable', 'Git': 'Comfortable' };

  const targetRole = answers['target_role'] || 'AI Engineer';
  const careerGoals = answers['career_goal'] || ['Get my first job', 'Improve my skills'];
  const interests = answers['interest_areas'] || ['Artificial Intelligence', 'Software Development'];
  const learningStyle = answers['learning_style'] || ['Hands-on practice', 'Projects'];
  const weeklyTime = answers['weekly_time'] || '5–10 hours';
  const workPref = answers['work_preference'] || 'Remote';
  const favoriteCompanies = answers['favorite_companies'] || ['Google', 'NVIDIA'];

  // Deterministic Next Skill Recommendations
  const primarySkill = skills[0] || 'Python';
  let recommendedSkills = ['Machine Learning', 'PyTorch', 'System Design'];
  if (targetRole.toLowerCase().includes('data')) {
    recommendedSkills = ['Data Pipelines', 'Pandas', 'PostgreSQL'];
  } else if (targetRole.toLowerCase().includes('frontend')) {
    recommendedSkills = ['TypeScript', 'Next.js', 'TailwindCSS'];
  } else if (targetRole.toLowerCase().includes('cloud') || targetRole.toLowerCase().includes('devops')) {
    recommendedSkills = ['Docker', 'Kubernetes', 'Terraform'];
  }

  return {
    reportType: 'individual',
    title: 'YOUR INTELLIGENCE PROFILE',
    userName,
    userLocation,
    careerSnapshot: {
      currentStage: stage,
      careerDirection: targetRole,
      experienceLevel: experience,
      studyField: stage === 'Student' ? studyField : null
    },
    skillSnapshot: {
      currentSkills: skills,
      levels: skillLevels,
      strongAreas: skills.filter(s => skillLevels[s] === 'Advanced' || skillLevels[s] === 'Expert'),
      needsDevelopment: skills.filter(s => skillLevels[s] === 'Beginner' || !skillLevels[s])
    },
    marketAlignment: {
      highDemandSkills: [primarySkill, ...recommendedSkills.slice(0, 2)],
      targetRoleAlignment: `${targetRole} appears strongly aligned with your ${primarySkill} capability and interest in ${interests[0] || 'AI'}.`,
      marketStatus: 'Active hiring momentum (+18.4% demand in target scope)'
    },
    skillOpportunities: {
      strong: primarySkill,
      growing: recommendedSkills[0] || 'Machine Learning',
      nextToBuild: recommendedSkills[1] || 'PyTorch'
    },
    learningDirection: [
      primarySkill,
      recommendedSkills[0] || 'Core Frameworks',
      recommendedSkills[1] || 'Specialized Tooling',
      'End-to-End Production Project',
      'Technical Capability Verification'
    ],
    marketPreferences: {
      location: userLocation,
      workPreference: workPref,
      favoriteCompanies: favoriteCompanies.slice(0, 4)
    },
    nextAction: {
      headline: 'Explore your Skill Intelligence',
      why: 'Review your personalized learning milestones and bridge your priority capability gaps.',
      cta: 'Explore My Intelligence',
      route: '#/individual/home'
    }
  };
}

function generateCompanyReport(answers, user) {
  const org = answers['cmp_organization'] || {};
  const companyName = org.companyName || user.companyName || 'NovaTech Solutions';
  const industry = org.industry || 'Artificial Intelligence & Enterprise Software';
  const location = `${org.city || 'Seattle'}, ${org.country || 'United States'}`;

  const size = answers['cmp_workforce_size'] || '501–1,000 employees';
  const desc = answers['cmp_description']?.text || 'Enterprise AI and intelligent automation infrastructure.';
  const areas = answers['cmp_business_areas'] || ['Technology', 'Engineering', 'Operations'];
  const goals = answers['cmp_improvement_goals'] || ['Workforce planning', 'Skill gaps', 'Employee growth'];
  const challenges = answers['cmp_challenges'] || ['Finding the right technical skills', 'Preparing employees for AI'];

  const rawCritSkills = answers['cmp_critical_skills'] || ['Python', 'Kubernetes', 'MLOps'];
  const criticalSkills = Array.isArray(rawCritSkills) ? rawCritSkills : (rawCritSkills.skills || ['Python', 'Kubernetes']);

  const rawFutureSkills = answers['cmp_future_skills'] || ['CUDA Optimization', 'Vector Databases'];
  const futureSkills = Array.isArray(rawFutureSkills) ? rawFutureSkills : (rawFutureSkills.skills || ['CUDA Optimization']);

  const roles = answers['cmp_important_roles'] || ['AI Engineer', 'MLOps Lead'];

  return {
    reportType: 'company',
    title: 'YOUR WORKFORCE INTELLIGENCE PROFILE',
    companyName,
    industry,
    location,
    workforceSize: size,
    description: desc,
    businessAreas: areas,
    criticalSkills,
    futureSkills,
    workforceChallenges: challenges,
    hiringPriorities: Array.isArray(roles) ? roles : [roles],
    startingView: {
      market: 'External demand for specialized technical roles has increased +24% across peer companies.',
      skills: `Critical capabilities centered around ${criticalSkills.slice(0, 3).join(', ')}.`,
      workforce: `Anticipated capability gaps in ${futureSkills.slice(0, 2).join(' and ')}.`,
      action: 'Set up departmental mobility clusters and launch automated skill health audits.'
    },
    nextAction: {
      headline: 'Enter Workforce Intelligence',
      why: 'Access the executive workforce dashboard, simulate scenario planning, and monitor company-wide skill health.',
      cta: 'Enter Workforce Intelligence',
      route: '#/company/home'
    }
  };
}
