export function renderHomePage({
  mainContent,
  lucide,
  applyExploreSelection,
  renderPersonalContext,
  renderIntelligenceOverview,
  renderConsole,
  renderSkillIntelligence,
  renderMarketIntelligence,
  renderJobIntelligence,
  renderRoadmap,
  isRoadmapPreviewing,
  renderRoadmapModal,
  bindEvents
}) {
  applyExploreSelection();
  mainContent.innerHTML = `
    <div class="home-dashboard-v2">
      ${renderPersonalContext()}
      ${renderIntelligenceOverview()}
      ${renderSkillIntelligence()}
      ${renderMarketIntelligence()}
      ${renderJobIntelligence()}
      ${renderRoadmap()}
    </div>
    ${isRoadmapPreviewing ? renderRoadmapModal() : ''}
  `;
  lucide.createIcons();
  bindEvents();
}
