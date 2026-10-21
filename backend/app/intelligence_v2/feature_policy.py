"""User-facing answer and fallback policy for the canonical V2 features."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureAnswerPolicy:
    domain: str
    handler: str
    sufficient_data: str
    gemini_b_fallback: bool
    provider_data_required: bool
    answer_type: str
    title: str
    guidance_instruction: str


FEATURE_ANSWER_POLICIES: dict[str, FeatureAnswerPolicy] = {
    "skill_future_relevance_score": FeatureAnswerPolicy(
        "skill", "run_future_relevance_score", "Historical and technology adoption signals are available.",
        True, False, "explanation", "Skill Future Relevance Score",
        "Assess a skill's potential future relevance using available historical and technology-adoption signals."
    ),
    "skill_change_alert": FeatureAnswerPolicy(
        "skill", "run_change_alert", "Comparable historical skill signals are available.",
        True, False, "explanation", "Skill Change Alert",
        "Identify supported increases, decreases, or stable patterns in comparable skill signals."
    ),
    "adaptive_skill_roadmap": FeatureAnswerPolicy(
        "skill", "run_adaptive_roadmap", "Target role and curriculum reference data are available.",
        True, False, "roadmap", "Adaptive Skill Roadmap",
        "Recommend an ordered learning plan based on current skills, a target role, and available skill relationships."
    ),
    "technology_adoption_shift_detector": FeatureAnswerPolicy(
        "market", "run_adoption_shift_detector", "Comparable technology adoption signals from supported sources are available.",
        True, False, "explanation", "Technology Adoption Shift Detector",
        "Compare supported technology-adoption signals over comparable periods and identify meaningful changes."
    ),
    "technology_impact_explorer": FeatureAnswerPolicy(
        "market", "run_impact_explorer", "Supported relationships between technologies, skills, and occupations are available.",
        True, False, "explanation", "Technology Impact Explorer",
        "Explore supported relationships between technologies, skills, and occupations."
    ),
    "skill_based_job_match": FeatureAnswerPolicy(
        "job", "run_job_match", "User skills and verified job postings are available.",
        False, True, "comparison", "Skill-Based Job Match",
        "Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps."
    ),
    "career_transition_opportunity": FeatureAnswerPolicy(
        "job", "run_transition_opportunity", "Current or target role and reference mappings are available.",
        True, False, "roadmap", "Career Transition Opportunity",
        "Identify possible related target roles and the skills that may be needed for a transition."
    ),
}


def get_feature_answer_policy(capability_id: str, domain: str | None = None) -> FeatureAnswerPolicy | None:
    """Retrieve the policy for a capability, resolving any legacy or alias ID to its canonical entry."""
    from app.intelligence_v2.capability_registry import canonical_capability_id
    cap = canonical_capability_id(capability_id, domain)
    return FEATURE_ANSWER_POLICIES.get(cap)

