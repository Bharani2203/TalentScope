import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clearEmployeeOnboardingProfile,
  getEmployeeProfile,
  setEmployeeOnboardingProfile
} from '../src/data/employee/employee-data.js';
import { renderEmployeeHome } from '../src/pages/employee/home/Home.js';
import { renderEmployeeMySkills } from '../src/pages/employee/skills/MySkills.js';
import {
  employeeNavigation,
  isEmployeeRouteActive,
  isEmployeeRouteCurrent,
  resolveEmployeeRoute
} from '../src/portals/employee/navigation.js';
import { generateEmployeeReport } from '../src/onboarding/employee-report-data.js';

const profile = {
  user_type: 'employee',
  profile: {
    display_name: 'Arun Kumar',
    city: 'Chennai',
    country: 'India',
    employer_name_claim: 'Example Ltd',
    team_name_claim: 'Engineering',
    current_role_id: 'Software Engineer',
    field_experience_band: '3–5 years',
    current_skill_domains: ['Python', 'React'],
    self_reported_skill_confidence: { Python: 'Advanced', React: 'Comfortable' },
    growth_interests: ['My technical skills'],
    target_role_name: 'Move to a senior role',
    desired_skill_domains: ['SQL'],
    weekly_learning_time: '2–5 hours',
    primary_goal: ['Prepare for promotion milestone']
  }
};

test('employee home and skills render the authenticated saved onboarding profile', () => {
  setEmployeeOnboardingProfile('employee-uid-1', profile);
  const home = renderEmployeeHome();
  const skills = renderEmployeeMySkills();
  const employee = getEmployeeProfile();

  assert.match(home, /Good (morning|afternoon|evening), Arun/);
  assert.match(home, /Example Ltd/);
  assert.match(home, /Move to a senior role/);
  assert.match(skills, /Python/);
  assert.match(skills, /React/);
  assert.match(skills, /Advanced/);
  assert.doesNotMatch(skills, /CUDA|PyTorch|NCCL/);
  assert.equal(employee.name, 'Arun Kumar');
  assert.equal(employee.profileLoaded, true);
  assert.equal(employee.companyVerified, false);
});

test('an empty employee skills profile has an empty state and no sample skills', () => {
  setEmployeeOnboardingProfile('employee-uid-2', {
    user_type: 'employee',
    profile: { display_name: '', current_skill_domains: [], self_reported_skill_confidence: {} }
  });

  const skills = renderEmployeeMySkills();
  const home = renderEmployeeHome();
  assert.match(skills, /No skills have been added yet/);
  assert.doesNotMatch(skills, /CUDA|PyTorch|NCCL/);
  assert.match(home, /Good (morning|afternoon|evening)<\/h1>/);
  assert.doesNotMatch(home, /undefined|null/);
});

test('employee routes keep Company Connection distinct and ignore stale skill-page rerenders', () => {
  assert.equal(resolveEmployeeRoute('/employee/career'), '/employee/growth');
  assert.equal(resolveEmployeeRoute('/employee/company'), '/employee/company');
  assert.equal(isEmployeeRouteActive('/employee/growth', '/employee/growth'), true);
  assert.equal(isEmployeeRouteActive('/employee/company', '/employee/company'), true);
  assert.equal(isEmployeeRouteCurrent('/employee/skills', '/employee/home'), false);
  assert.equal(isEmployeeRouteCurrent('/employee/skills', '/employee/skills'), true);
  assert.equal(isEmployeeRouteCurrent('/employee/career', '/employee/growth'), true);
});

test('employee profile report uses saved answers without inventing skills or assessment scores', () => {
  const report = generateEmployeeReport({
    emp_name_and_location: { name: 'Arun' },
    emp_workplace: { company: 'Example Ltd', department: 'Engineering', currentRole: 'Engineer' },
    emp_experience_field: '3–5 years',
    emp_skills: ['Python'],
    emp_skill_confidence: { Python: 'Advanced' },
    emp_improvements: ['My technical skills'],
    emp_trajectory: 'Move to a senior role',
    emp_next_skills: ['SQL'],
    emp_time: '2–5 hours',
    emp_internal_goals: ['Prepare for promotion']
  });

  assert.equal(report.userName, 'Arun');
  assert.equal(report.companyName, 'Example Ltd');
  assert.deepEqual(report.currentSkills, ['Python']);
  assert.deepEqual(report.skillConfidence, { Python: 'Advanced' });
  assert.deepEqual(report.careerGrowthAreas, ['My technical skills', 'SQL']);
  assert.equal(report.weeklyLearningTime, '2–5 hours');
  assert.equal(report.skillHealth.score, null);
  assert.equal(report.isConnected, false);
  assert.deepEqual(report.companyAlignment, null);

  const empty = generateEmployeeReport();
  assert.deepEqual(empty.currentSkills, []);
  assert.equal(empty.userName, '');
  assert.equal(empty.skillHealth.score, null);
});

test.after(() => clearEmployeeOnboardingProfile());

test('Employee AI Assistant page and navigation elements are removed from Employee Portal', () => {
  const allRoutes = employeeNavigation.flatMap(group => group.items.map(item => item.route));
  const allLabels = employeeNavigation.flatMap(group => group.items.map(item => item.label));
  assert.equal(allRoutes.includes('/employee/ai-assistant'), false);
  assert.equal(allLabels.includes('AI Assistant'), false);

  assert.equal(resolveEmployeeRoute('/employee/ai-assistant'), '/employee/home');
  assert.equal(resolveEmployeeRoute('/employee/assistant'), '/employee/home');
});
