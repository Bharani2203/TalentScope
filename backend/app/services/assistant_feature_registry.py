"""Single source of truth for executable assistant feature handlers."""

HANDLER_METHODS: dict[str, str] = {
    "entity_resolution": "_handle_entity_resolution",
    "skill_technology_reference": "_handle_skill_technology_reference",
    "occupation_lookup": "_handle_occupation_lookup",
    "occupation_software_skills": "_handle_occupation_software_skills",
    "related_occupations": "_handle_related_occupations",
    "market_snapshot": "_handle_market_snapshot",
    "historical_signal_retrieval": "_handle_historical_signal_retrieval",
    "trend_velocity_analysis": "_handle_trend_velocity_analysis",
    "skill_health_analysis": "_handle_skill_health_analysis",
    "skill_half_life_analysis": "_handle_skill_half_life_analysis",
    "skill_forecasting_half_life": "_handle_skill_demand_forecasting",
    "evidence_provenance_retrieval": "_handle_evidence_provenance_retrieval",
    "skill_gap_role_fit": "_handle_skill_gap_role_fit",
    "action_recommendations": "_handle_action_recommendations",
    "job_posting_search": "_handle_job_posting_search",
    "collected_posting_skills": "_handle_collected_posting_skills",
    "company_intelligence": "_handle_company_intelligence",
    # Catalog aliases are advertised only when they dispatch to a real
    # implementation with compatible semantics.
    "skill_change_alert": "_handle_trend_velocity_analysis",
    "technology_adoption_shift_detector": "_handle_trend_velocity_analysis",
    "technology_impact_explorer": "_handle_skill_technology_reference",
    "career_transition_opportunity": "_handle_related_occupations",
}

EXECUTABLE_FEATURES = frozenset(HANDLER_METHODS)

# The structured router may choose only a handler that is registered for its
# selected intent. Aliases are listed explicitly to keep routing auditable.
INTENT_FEATURES: dict[str, frozenset[str]] = {
    "resolve_entity": frozenset({"entity_resolution"}),
    "lookup_skill_reference": frozenset({"skill_technology_reference", "technology_impact_explorer"}),
    "lookup_github_adoption": frozenset({"skill_technology_reference", "historical_signal_retrieval"}),
    "lookup_occupation": frozenset({"occupation_lookup"}),
    "crosswalk_occupation_software": frozenset({"occupation_software_skills"}),
    "crosswalk_related_occupations": frozenset({"related_occupations", "career_transition_opportunity"}),
    "retrieve_snapshot": frozenset({"market_snapshot"}),
    "retrieve_history": frozenset({"historical_signal_retrieval"}),
    "analyze_trend": frozenset({"trend_velocity_analysis", "skill_change_alert", "technology_adoption_shift_detector"}),
    "analyze_skill_health": frozenset({"skill_health_analysis"}),
    "estimate_skill_half_life": frozenset({"skill_half_life_analysis"}),
    "rank_skill_trends": frozenset({"trend_velocity_analysis"}),
    "compare_entities": frozenset({"market_snapshot", "trend_velocity_analysis", "occupation_software_skills", "related_occupations"}),
    "retrieve_evidence": frozenset({"evidence_provenance_retrieval"}),
    "analyze_skill_gap": frozenset({"skill_gap_role_fit"}),
    "synthesize_actions": frozenset({"action_recommendations"}),
    "search_jobs": frozenset({"job_posting_search"}),
    "aggregate_posting_skills": frozenset({"collected_posting_skills"}),
    "analyze_company_workforce": frozenset({"company_intelligence"}),
    "forecast_future_demand": frozenset({"skill_forecasting_half_life"}),
    "analyze_ai_task_exposure": frozenset({"skill_technology_reference"}),
    "simulate_workforce_scenarios": frozenset(),
    "general_explanation": frozenset(),
    "explain_concept": frozenset({"skill_technology_reference"}),
    "platform_help": frozenset(),
    "company_postings_summary": frozenset({"job_posting_search"}),
    "unsupported_or_unclear": frozenset(),
}

KNOWN_INTENTS = frozenset({
    "unsupported_or_unclear",
    "retrieve_evidence",
    "lookup_github_adoption",
    "forecast_future_demand",
    "analyze_skill_gap",
    "synthesize_actions",
    "general_explanation",
    "platform_help",
    "company_postings_summary",
    "simulate_workforce_scenarios",
    "analyze_ai_task_exposure",
    "rank_skill_trends",
    "compare_entities",
    "retrieve_snapshot",
    "search_jobs",
    "aggregate_posting_skills",
    "lookup_skill_reference",
    "analyze_trend",
    "crosswalk_related_occupations",
    "crosswalk_occupation_software",
    "analyze_company_workforce",
    "lookup_occupation",
    "retrieve_history",
    "explain_concept",
    "analyze_skill_health",
    "estimate_skill_half_life",
    "resolve_entity",
})

PLANNED_FEATURES = {
    "skill_future_relevance_score": "Future Relevance Score",
    "adaptive_skill_roadmap": "Full prerequisite roadmap",
    "workforce_what_if_simulation": "What-if workforce simulation",
}
