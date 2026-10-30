import assert from 'node:assert/strict';
import test from 'node:test';

import {
  setEmployeeOnboardingProfile,
  clearEmployeeOnboardingProfile
} from '../src/data/employee/employee-data.js';
import {
  renderEmployeeCompanyConnection,
  resetConnectionState,
  setConnectionStateForTest
} from '../src/pages/employee/company/CompanyConnection.js';

test.beforeEach(() => {
  resetConnectionState();
  clearEmployeeOnboardingProfile();
});

test.afterEach(() => {
  resetConnectionState();
  clearEmployeeOnboardingProfile();
});

test('CompanyConnection renders Find a company and Continue independently for independent employees', () => {
  setEmployeeOnboardingProfile('emp-ind-1', {
    user_type: 'employee',
    profile: {
      display_name: 'Independent Arun',
      employer_name_claim: '',
      employment_state: 'independent',
      current_skill_domains: ['Python']
    }
  });

  const html = renderEmployeeCompanyConnection();

  // 1. Should render search form and independent button
  assert.match(html, /id="companySearchForm"/);
  assert.match(html, /Find a company/);
  assert.match(html, /id="companySearchInput"/);
  assert.match(html, /id="setIndependentButton"/);
  assert.match(html, /Continue independently/);

  // 2. Should NOT render Connected Company Feedback Hub
  assert.doesNotMatch(html, /COMPANY CONNECTION &amp; FEEDBACK HUB/);
  assert.doesNotMatch(html, /Verified Member/);
  assert.doesNotMatch(html, /company-message-card/);
});

test('CompanyConnection renders Pending Review banner when request is pending', () => {
  setEmployeeOnboardingProfile('emp-req-1', {
    user_type: 'employee',
    profile: {
      display_name: 'Pending Arun',
      employer_name_claim: 'NVIDIA',
      employment_state: 'requesting',
      current_skill_domains: ['Python']
    }
  });

  setConnectionStateForTest({
    employmentState: 'requesting',
    companyName: 'NVIDIA'
  });

  const html = renderEmployeeCompanyConnection();

  // Should render pending banner
  assert.match(html, /Connection Request Pending Review/);
  assert.match(html, /pending company review/i);

  // Still shows search form and independent options
  assert.match(html, /id="companySearchForm"/);
  assert.match(html, /Continue independently/);

  // Should NOT render feedback hub
  assert.doesNotMatch(html, /Verified Member/);
});

test('CompanyConnection renders Company Feedback Hub and hides search box when connected', () => {
  setEmployeeOnboardingProfile('emp-conn-1', {
    user_type: 'employee',
    profile: {
      display_name: 'Connected Arun',
      employer_name_claim: 'TechCorp Global',
      employment_state: 'connected',
      company_id: 'comp-100',
      current_skill_domains: ['Python', 'Docker']
    }
  });

  setConnectionStateForTest({
    status: 'loaded',
    employmentState: 'connected',
    companyName: 'TechCorp Global',
    companyId: 'comp-100',
    messages: [
      {
        id: 'msg-up-1',
        type: 'upskill_request',
        title: 'HR Upskill Directive: Distributed PyTorch',
        company_name: 'TechCorp Global',
        sender: 'People Operations & Technical Learning Pod',
        date: 'Oct 28, 2026',
        message: 'HR requested you upskill in PyTorch to support upcoming model serving pods.',
        skill_name: 'PyTorch',
        target_date: 'Q4 2026',
        details: 'Focus on tensor parallelism and distributed data parallel workflows.'
      },
      {
        id: 'msg-pr-1',
        type: 'project_assignment',
        title: 'Project Assignment: Autonomous Fleet Compute Pod',
        company_name: 'TechCorp Global',
        sender: 'Engineering Resource Planning',
        date: 'Oct 24, 2026',
        message: 'You have been assigned to Project Autonomous Fleet Compute Pod.',
        project_name: 'Autonomous Fleet Compute Pod',
        project_role: 'Platform Acceleration Contributor',
        team: 'Autonomous Systems & Compute',
        start_date: 'Nov 15, 2026',
        details: 'Lead GPU benchmark profiling and low-latency driver telemetry.'
      },
      {
        id: 'msg-fb-1',
        type: 'general_feedback',
        title: 'Q3 Engineering Performance & Growth Review',
        company_name: 'TechCorp Global',
        sender: 'Director of Engineering',
        date: 'Oct 15, 2026',
        message: 'Exceptional progress on the backend architecture sprint. Management noted proactive code reviews and reliability.',
        sentiment: 'Exceeds Expectations'
      }
    ]
  });

  const html = renderEmployeeCompanyConnection();

  // 1. Search box must be hidden
  assert.doesNotMatch(html, /id="companySearchForm"/);
  assert.doesNotMatch(html, /Find a company/);

  // 2. Active Company Header with Verified Member badge
  assert.match(html, /COMPANY CONNECTION &amp; FEEDBACK HUB/);
  assert.match(html, /TechCorp Global/);
  assert.match(html, /Verified Member/);
  assert.match(html, /3 Active/);
  assert.match(html, /Company Communications/);

  // 3. Card a: Skill / Upskill Request with direct Start Learning button
  assert.match(html, /Upskill Request/);
  assert.match(html, /HR requested you upskill in PyTorch/);
  assert.match(html, /Start Learning/);
  assert.match(html, /href="#\/employee\/learning\?skill=PyTorch"/);

  // 4. Card b: Project Assignment with project details & start dates
  assert.match(html, /Project Assignment/);
  assert.match(html, /Autonomous Fleet Compute Pod/);
  assert.match(html, /Platform Acceleration Contributor/);
  assert.match(html, /Nov 15, 2026/);
  assert.match(html, /Autonomous Systems &amp; Compute/);
  assert.match(html, /View Pod Requisitions/);

  // 5. Card c: General HR Feedback with management notes
  assert.match(html, /General HR Feedback/);
  assert.match(html, /Director of Engineering/);
  assert.match(html, /Exceptional progress on the backend architecture sprint/);
  assert.match(html, /Exceeds Expectations/);

  // 6. Disconnect action button is present
  assert.match(html, /id="setIndependentButton"/);
  assert.match(html, /Disconnect/);
});

