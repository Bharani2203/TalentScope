import assert from 'node:assert/strict';
import test from 'node:test';

import {
  setEmployeeOnboardingProfile,
  clearEmployeeOnboardingProfile
} from '../src/data/employee/employee-data.js';
import {
  renderEmployeeOpportunities,
  resetOpportunitiesState,
  setOpportunitiesStateForTest
} from '../src/pages/employee/opportunities/Opportunities.js';
import { calculateSkillMatch } from '../src/api/jobs-client.js';

test('calculateSkillMatch correctly computes match score, matched competencies, and gaps', () => {
  const userSkills = ['Python', 'PyTorch', 'Docker'];
  const jobSkills = ['Python', 'PyTorch', 'CUDA', 'Distributed Systems'];

  const result = calculateSkillMatch(userSkills, jobSkills);
  assert.equal(result.matchScore, 50); // 2 out of 4 = 50%
  assert.deepEqual(result.matchedSkills, ['Python', 'PyTorch']);
  assert.deepEqual(result.gaps, ['CUDA', 'Distributed Systems']);

  // Full match
  const fullMatch = calculateSkillMatch(['Python', 'SQL'], ['Python', 'SQL']);
  assert.equal(fullMatch.matchScore, 100);
  assert.deepEqual(fullMatch.matchedSkills, ['Python', 'SQL']);
  assert.deepEqual(fullMatch.gaps, []);

  // Empty job skills fallback
  const emptyReq = calculateSkillMatch(['Python'], []);
  assert.equal(emptyReq.matchScore, 80);
});

test('renderEmployeeOpportunities fixes header typos and renders company context', () => {
  resetOpportunitiesState();
  setEmployeeOnboardingProfile('emp-test-1', {
    user_type: 'employee',
    profile: {
      display_name: 'Arun Kumar',
      employer_name_claim: 'NVIDIA',
      current_skill_domains: ['Python', 'PyTorch'],
      target_role_name: 'Senior AI Platform Engineer'
    }
  });

  const html = renderEmployeeOpportunities();

  // 1. Verify header typo fixes
  assert.match(html, /INTERNAL MOBILITY & REQUISITIONS/);
  assert.doesNotMatch(html, /LNTERNAL MOBlLlTY & REQUlSlTlONS/);
  assert.doesNotMatch(html, /lNTERNAL/);
  assert.match(html, /Internal Mobility & Open Requisitions/);
  assert.doesNotMatch(html, /lnternal Mobility/);

  // 2. Company description mentions the company name
  assert.match(html, /NVIDIA/);

  // 3. Clean empty state before fetch loads
  assert.match(html, /No open internal requisitions at the moment/);
  assert.match(html, /0 Matched/);
  assert.match(html, /Keep building your skills!/);
});

test('renderEmployeeOpportunities handles employees without a connected company', () => {
  resetOpportunitiesState();
  setEmployeeOnboardingProfile('emp-test-2', {
    user_type: 'employee',
    profile: {
      display_name: 'Independent Developer',
      employer_name_claim: '',
      current_skill_domains: ['JavaScript', 'React'],
      target_role_name: 'Frontend Architect'
    }
  });

  const html = renderEmployeeOpportunities();
  assert.match(html, /Connect Your Company to Access Internal Mobility/);
  assert.match(html, /Company Connection/);
});

test('renderEmployeeOpportunities renders mapped job cards with match %, competencies, gaps, and express interest button', () => {
  resetOpportunitiesState();
  setEmployeeOnboardingProfile('emp-test-3', {
    user_type: 'employee',
    profile: {
      display_name: 'Arun Kumar',
      employer_name_claim: 'NVIDIA',
      current_skill_domains: ['Python', 'PyTorch', 'Docker'],
      target_role_name: 'Senior AI Platform Engineer'
    }
  });

  setOpportunitiesStateForTest({
    status: 'loaded',
    companyKey: 'NVIDIA',
    companyJobs: [
      {
        id: 'pg-101',
        title: 'Senior System Software Engineer',
        team: 'Autonomous Systems & Compute',
        department: 'Technology',
        hiringManager: 'Priya Sundaram',
        location: 'Bangalore, India (Hybrid)',
        status: 'Open Internal Requisition',
        urgency: 'Priority Fill',
        summary: 'Core engineering opportunity at NVIDIA platform teams.',
        requiredSkills: ['Python', 'PyTorch', 'CUDA', 'C++'],
        matchedSkills: ['Python', 'PyTorch'],
        gaps: ['CUDA', 'C++'],
        matchScore: 92,
        compensationRange: '$180k - $220k'
      },
      {
        id: 'pg-102',
        title: 'GPU Profiling Engineer',
        team: 'GPU Performance',
        department: 'Technology',
        hiringManager: 'David Chen',
        location: 'Bangalore, India (Hybrid)',
        status: 'Open Internal Requisition',
        urgency: null,
        summary: 'Evaluate GPU runtime bottlenecks and kernel execution.',
        requiredSkills: ['C++', 'Linux', 'Debugging'],
        matchedSkills: [],
        gaps: ['C++', 'Linux', 'Debugging'],
        matchScore: 40,
        compensationRange: null
      }
    ]
  });

  const html = renderEmployeeOpportunities();

  // 1. Matched counter
  assert.match(html, /2 Matched/);
  assert.match(html, /All Opportunities \(2\)/);

  // 2. Card 1 details
  assert.match(html, /Senior System Software Engineer/);
  assert.match(html, /92% Skill Match/);
  assert.match(html, /Open Internal Requisition/);
  assert.match(html, /Autonomous Systems &amp; Compute/);
  assert.match(html, /Priya Sundaram/);
  assert.match(html, /Matched Competencies:/);
  assert.match(html, /Python, PyTorch/);
  assert.match(html, /Growth Areas:/);
  assert.match(html, /CUDA, C\+\+/);
  assert.match(html, /Express Interest/);
  assert.match(html, /data-apply-opp="pg-101"/);

  // 3. Card 2 details
  assert.match(html, /GPU Profiling Engineer/);
  assert.match(html, /40% Skill Match/);
});

test.after(() => {
  clearEmployeeOnboardingProfile();
  resetOpportunitiesState();
});
