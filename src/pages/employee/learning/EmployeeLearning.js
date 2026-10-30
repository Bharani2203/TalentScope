// ============================================================================
// TALENTSCOPE.AI — EMPLOYEE LEARNING WORKSPACE
// Dedicated Employee wrapper for the Learning & Progression Workspace
// Retains full learning functionality with Employee Portal styling
// ============================================================================

import {
  renderDedicatedLearningPage,
  renderLearningWorkspaceHTML
} from '../../individual/learning/Learning.js';

export function renderEmployeeLearning(state) {
  return renderLearningWorkspaceHTML(state);
}

export function renderEmployeeLearningPage() {
  return renderDedicatedLearningPage();
}

export { renderDedicatedLearningPage, renderLearningWorkspaceHTML };

