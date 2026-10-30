import assert from 'node:assert/strict';
import test from 'node:test';

import {
  COMPANY_QUESTIONS,
  EMPLOYEE_QUESTIONS,
  filterOnboardingDraft,
  resolveRoleStepIndex
} from '../src/onboarding/onboarding-data.js';

test('COMPANY_QUESTIONS defines 11 questions starting with Organization and ending with Platform Usage', () => {
  assert.equal(COMPANY_QUESTIONS.length, 11, 'Company onboarding must have exactly 11 questions');

  const q1 = COMPANY_QUESTIONS[0];
  assert.equal(q1.id, 'cmp_organization');
  assert.equal(q1.stepNumber, 1);
  assert.equal(q1.title, 'Tell us about your organization');
  assert.equal(q1.category, 'Organization');
  assert.deepEqual(q1.fields.map(f => f.name), ['companyName', 'industry', 'city', 'country']);

  const q2 = COMPANY_QUESTIONS[1];
  assert.equal(q2.id, 'cmp_workforce_size');
  assert.equal(q2.stepNumber, 2);
  assert.equal(q2.title, 'How large is your workforce?');

  const q11 = COMPANY_QUESTIONS[10];
  assert.equal(q11.id, 'cmp_platform_usage');
  assert.equal(q11.stepNumber, 11);
  assert.equal(q11.title, 'How would you like to start using the platform?');
  assert.equal(q11.category, 'Decisions');
});

test('filterOnboardingDraft strictly isolates by userType and prevents cross-role draft leaks', () => {
  const individualDraft = {
    userType: 'individual',
    stepIndex: 10,
    answers: { name_and_location: { name: 'Alice' } }
  };

  // Company query must reject individual draft
  assert.equal(filterOnboardingDraft(individualDraft, 'company'), null);

  // Employee query must reject individual draft
  assert.equal(filterOnboardingDraft(individualDraft, 'employee'), null);

  // Matching userType query returns the draft
  assert.deepEqual(filterOnboardingDraft(individualDraft, 'individual'), individualDraft);

  // Invalid / null / empty inputs handled safely
  assert.equal(filterOnboardingDraft(null, 'company'), null);
  assert.equal(filterOnboardingDraft({}, 'company'), null);
  assert.equal(filterOnboardingDraft({ stepIndex: 5 }, 'company'), null);
});

test('resolveRoleStepIndex starts a brand new company admin at Question 1 (index 0)', () => {
  const stepIndex = resolveRoleStepIndex({
    remote: { answers: {}, onboarding: { current_step: 1, completed_steps: [], completed: false } },
    draft: null,
    userType: 'company'
  });

  assert.equal(stepIndex, 0, 'Brand new company admin must start at Question 1 (index 0)');
  assert.equal(COMPANY_QUESTIONS[stepIndex].id, 'cmp_organization');
});

test('resolveRoleStepIndex protects against erroneous backend response reporting step 11 with empty answers', () => {
  // Bug reproduction scenario: Backend inherited individual onboarding progress (current_step: 11)
  // but company_onboarding_answers is completely empty.
  const stepIndex = resolveRoleStepIndex({
    remote: {
      answers: {},
      onboarding: { current_step: 11, completed_steps: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], completed: true }
    },
    draft: null,
    userType: 'company'
  });

  // Because answers are empty, resolveRoleStepIndex must enforce step 0 (Question 1)
  assert.equal(stepIndex, 0, 'Must not skip to Question 11 when answers are empty');
  assert.equal(COMPANY_QUESTIONS[stepIndex].title, 'Tell us about your organization');
});

test('resolveRoleStepIndex resumes at Question 2 when Question 1 has been answered', () => {
  const stepIndex = resolveRoleStepIndex({
    remote: {
      answers: {
        cmp_organization: { companyName: 'Acme Corp', industry: 'Technology', city: 'Austin', country: 'USA' }
      },
      onboarding: { current_step: 2, completed_steps: [1], completed: false }
    },
    draft: null,
    userType: 'company'
  });

  assert.equal(stepIndex, 1, 'Must advance to Question 2 (index 1)');
  assert.equal(COMPANY_QUESTIONS[stepIndex].id, 'cmp_workforce_size');
  assert.equal(COMPANY_QUESTIONS[stepIndex].title, 'How large is your workforce?');
});

test('resolveRoleStepIndex respects active local draft with answered questions', () => {
  const stepIndex = resolveRoleStepIndex({
    remote: null,
    draft: {
      userType: 'company',
      stepIndex: 2,
      answers: {
        cmp_organization: { companyName: 'Acme Corp' },
        cmp_workforce_size: '51–200 employees'
      }
    },
    userType: 'company'
  });

  assert.equal(stepIndex, 2, 'Must resume at draft step index 2 (Question 3)');
  assert.equal(COMPANY_QUESTIONS[stepIndex].id, 'cmp_description');
});

test('resolveRoleStepIndex clamps out-of-range steps to valid boundaries', () => {
  const clampedMax = resolveRoleStepIndex({
    remote: {
      answers: { cmp_organization: 'Acme' },
      onboarding: { current_step: 99, completed_steps: [] }
    },
    draft: null,
    userType: 'company'
  });
  assert.equal(clampedMax, COMPANY_QUESTIONS.length - 1, 'Should clamp to final question index (10)');

  const clampedMin = resolveRoleStepIndex({
    remote: {
      answers: { cmp_organization: 'Acme' },
      onboarding: { current_step: -5, completed_steps: [] }
    },
    draft: null,
    userType: 'company'
  });
  assert.equal(clampedMin, 0, 'Should clamp to first question index (0)');
});

