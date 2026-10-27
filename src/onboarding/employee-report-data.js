export function generateEmployeeReport(answers = {}, savedProfile = {}) {
  const nameData = answers.emp_name_and_location || {};
  const workplaceData = answers.emp_workplace || {};
  const improvements = savedProfile.growth_interests || answers.emp_improvements || [];
  const desiredSkills = savedProfile.desired_skill_domains || answers.emp_next_skills || [];
  const skills = savedProfile.current_skill_domains || answers.emp_skills || [];
  const skillConfidence = savedProfile.self_reported_skill_confidence || answers.emp_skill_confidence || {};

  return {
    reportType: 'employee-profile',
    title: 'YOUR EMPLOYEE PROFILE',
    userName: savedProfile.display_name || nameData.name || '',
    companyName: savedProfile.employer_name_claim || workplaceData.company || null,
    department: savedProfile.team_name_claim || workplaceData.department || null,
    currentRole: savedProfile.current_role_id || workplaceData.currentRole || null,
    industry: savedProfile.company_industry_claim || workplaceData.industry || null,
    experience: savedProfile.field_experience_band || answers.emp_experience_field || null,
    isConnected: false,
    currentSkills: skills,
    skillHealth: {
      score: null,
      status: 'Self-reported; not assessed'
    },
    roleDirection: {
      targetTrajectory: savedProfile.mobility_interest_type || answers.emp_trajectory || null,
      keyAreas: improvements
    },
    companyAlignment: null,
    careerGrowthAreas: [...improvements, ...desiredSkills],
    weeklyLearningTime: savedProfile.weekly_learning_time || answers.emp_time || null,
    preferredHelp: savedProfile.primary_goal || answers.emp_internal_goals || [],
    skillConfidence,
    nextAction: {
      headline: 'Continue to your Employee Portal',
      why: 'Review your saved employee profile and self-reported skills.',
      cta: 'Open Employee Portal',
      route: '#/employee/home'
    }
  };
}
