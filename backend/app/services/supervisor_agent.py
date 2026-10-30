"""Supervisor Agent Orchestrator for TalentScope.ai.

Coordinates the 4 core Intelligence Tools with multi-turn conversation memory,
user profile/context awareness, and Gemini Function Calling (with a deterministic
local tool-routing fallback for 100% offline reliability).

Strictly adheres to Section 6 constraints:
- Evidence-first tool invocation.
- Strict provenance boundary between developer telemetry and hiring requisitions.
- Profile-aware automatic resolution of user_skills and target_role.
- Multi-turn reference resolution across conversation turns.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import re
from typing import Any, AsyncGenerator, Literal
from pydantic import BaseModel, Field

from app.api.routes.career_intelligence import ROLE_METADATA, normalize_target_role
from app.services.assistant_tools import (
    SUPERVISOR_TOOLS,
    analyze_historical_job_demand,
    analyze_market_ecosystem,
    analyze_skill_gap,
    fetch_live_job_openings,
)

logger = logging.getLogger(__name__)

# Standard tech hubs for location extraction
KNOWN_LOCATIONS = [
    "Bengaluru", "Bangalore", "Hyderabad", "Pune", "Mumbai", "Chennai",
    "Delhi", "Delhi NCR", "Gurgaon", "Gurugram", "Noida", "Kolkata", "Ahmedabad", "Kochi", "India"
]

KNOWN_SKILLS = [
    "python", "docker", "kubernetes", "aws", "sql", "react", "typescript",
    "javascript", "pytorch", "tensorflow", "figma", "seo", "google analytics",
    "pandas", "postgresql", "node.js", "ci/cd", "git", "terraform", "generative ai",
    "scikit-learn", "huggingface", "azure", "linux", "rest apis", "microservices"
]


# Known roles and explicit alias mapping
KNOWN_ROLE_ALIASES: dict[str, str] = {
    # UI / UX Design Pillar
    "ui/ux designer": "UI/UX",
    "ui/ux design": "UI/UX",
    "ui/ux": "UI/UX",
    "ux/ui designer": "UI/UX",
    "ux/ui design": "UI/UX",
    "ux/ui": "UI/UX",
    "ui designer": "UI/UX",
    "ux designer": "UI/UX",
    "product designer": "UI/UX",
    "ui design": "UI/UX",
    "ux design": "UI/UX",
    # Standard roles & tech variants
    "backend developer": "Backend Developer",
    "backend engineer": "Backend Developer",
    "backend": "Backend Developer",
    "frontend engineer": "Frontend Engineer",
    "frontend developer": "Frontend Engineer",
    "frontend": "Frontend Engineer",
    "full stack engineer": "Full Stack Engineer",
    "full stack developer": "Full Stack Engineer",
    "full stack": "Full Stack Engineer",
    "fullstack": "Full Stack Engineer",
    "data scientist": "Data Scientist",
    "data science": "Data Scientist",
    "data engineer": "Data Engineer",
    "cloud solutions architect": "Cloud Solutions Architect",
    "cloud architect": "Cloud Solutions Architect",
    "cloud solution": "Cloud Solutions Architect",
    "devops & mlops lead": "DevOps & MLOps Lead",
    "devops lead": "DevOps & MLOps Lead",
    "devops engineer": "DevOps & MLOps Lead",
    "devops": "DevOps & MLOps Lead",
    "mlops": "DevOps & MLOps Lead",
    "machine learning engineer": "Machine Learning Engineer",
    "machine learning": "Machine Learning Engineer",
    "ai engineer": "AI Engineer",
    "artificial intelligence": "AI Engineer",
    "cybersecurity specialist": "Cybersecurity Specialist",
    "cybersecurity": "Cybersecurity Specialist",
    "security engineer": "Cybersecurity Specialist",
    "security": "Cybersecurity Specialist",
    "data & business analyst": "Data & Business Analyst",
    "data analyst": "Data & Business Analyst",
    "business analyst": "Data & Business Analyst",
    "analyst": "Data & Business Analyst",
    "ai product manager": "AI Product Manager",
    "product manager": "AI Product Manager",
}

# Known standalone technologies and programming languages (ordered by specificity)
KNOWN_TECH_ENTITIES: list[tuple[str, str]] = [
    ("google analytics", "Google Analytics"),
    ("generative ai", "Generative AI"),
    ("machine learning", "Machine Learning"),
    ("artificial intelligence", "Artificial Intelligence"),
    ("cloud solutions", "Cloud Solutions Architect"),
    ("rest apis", "REST APIs"),
    ("deep learning", "Deep Learning"),
    ("data science", "Data Science"),
    ("scikit-learn", "Scikit-Learn"),
    ("huggingface", "HuggingFace"),
    ("design system", "UI/UX"),
    ("ui/ux", "UI/UX"),
    ("ux/ui", "UI/UX"),
    ("typescript", "TypeScript"),
    ("javascript", "JavaScript"),
    ("postgresql", "PostgreSQL"),
    ("kubernetes", "Kubernetes"),
    ("tensorflow", "TensorFlow"),
    ("terraform", "Terraform"),
    ("ci/cd", "CI/CD"),
    ("node.js", "Node.js"),
    ("python", "Python"),
    ("docker", "Docker"),
    ("pytorch", "PyTorch"),
    ("figma", "Figma"),
    ("react", "React"),
    ("pandas", "Pandas"),
    ("azure", "Azure"),
    ("linux", "Linux"),
    ("golang", "Golang"),
    ("scala", "Scala"),
    ("spark", "Spark"),
    ("redis", "Redis"),
    ("kafka", "Kafka"),
    ("rust", "Rust"),
    ("java", "Java"),
    ("sql", "SQL"),
    ("aws", "AWS"),
    ("git", "Git"),
    ("seo", "SEO"),
    ("go", "Go"),
    ("c++", "C++"),
    ("c#", "C#"),
    ("ruby", "Ruby"),
    ("php", "PHP"),
    ("swift", "Swift"),
    ("kotlin", "Kotlin"),
    ("angular", "Angular"),
    ("vue", "Vue"),
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("spring boot", "Spring Boot"),
    ("graphql", "GraphQL"),
    ("flutter", "Flutter"),
    ("mongodb", "MongoDB"),
    ("mysql", "MySQL"),
    ("numpy", "NumPy"),
]


# ---------------------------------------------------------------------------
# REQUEST / RESPONSE SCHEMAS
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UserContext(BaseModel):
    user_skills: list[str] = Field(default_factory=list)
    target_role: str = ""
    current_view: str = ""
    location: str = "India"


class SupervisorResponse(BaseModel):
    answer: str
    tools_invoked: list[str] = Field(default_factory=list)
    evidence_payloads: list[dict[str, Any]] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    provenance_summary: str = ""
    target_role: str = ""
    intent: str = ""

    def __init__(self, **data: Any):
        if "suggested_followups" in data and "suggested_questions" not in data:
            data["suggested_questions"] = list(data["suggested_followups"])
        elif "suggested_questions" in data and "suggested_followups" not in data:
            data["suggested_followups"] = list(data["suggested_questions"])
        super().__init__(**data)


# Aliases for cross-module compatibility
SupervisorChatMessage = ChatMessage
SupervisorUserContext = UserContext


# ---------------------------------------------------------------------------
# ENTITY & CONTEXT RESOLUTION (MULTI-TURN MEMORY)
# ---------------------------------------------------------------------------

# Known job modifiers and filter tokens
KNOWN_JOB_FILTERS = [
    "current", "latest", "today", "right now", "active right now", "recent",
    "fresher", "freshers", "entry level", "entry-level", "junior", "senior",
    "intern", "internship", "remote", "hybrid", "onsite", "contract", "full-time", "part-time"
]


def extract_dynamic_filters(text: str) -> tuple[list[str], list[str]]:
    """Dynamically extract universal inclusion and exclusion filters from prompt text.

    Uses Gemini LLM when available to dynamically deduce what words must be included
    and excluded based on common sense (e.g., 'fresher' -> include ['fresher'], exclude ['senior', 'lead', 'principal']).
    Provides robust, dynamic common-sense heuristics for offline/fallback execution.
    """
    if not text or not text.strip():
        return [], []

    # 1. Dynamic Gemini extraction if API key is configured and not in offline test mode
    _candidate_keys = get_configured_gemini_keys()
    api_key = _candidate_keys[0] if _candidate_keys else None
    if api_key and api_key.strip() and os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") != "1":
        try:
            import json
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=api_key.strip())
            extractor_model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                system_instruction=(
                    "You are an expert NLP filter extraction assistant for an enterprise job search engine. "
                    "Analyze the user query and extract two lists of lowercase words: "
                    "1. 'include_filters': specific job types, seniority, or work modes that must be present in the job title or skills. "
                    "2. 'exclude_filters': conflicting words that must be excluded based on common sense (e.g., if fresher/entry, exclude senior, lead, principal, manager; if senior, exclude junior, fresher, entry, intern; if remote, exclude onsite). "
                    "Return ONLY valid JSON: {\"include_filters\": [...], \"exclude_filters\": [...]}."
                ),
            )
            resp = extractor_model.generate_content(f"Extract filters from: {text}")
            if resp and resp.text:
                cleaned = resp.text.strip().replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                inc = [str(x).strip().lower() for x in data.get("include_filters", []) if str(x).strip()]
                exc = [str(x).strip().lower() for x in data.get("exclude_filters", []) if str(x).strip()]
                if inc or exc:
                    return inc, exc
        except Exception as exc:
            logger.debug("Dynamic Gemini filter extraction failed, falling back to dynamic parser: %s", exc)

    # 2. Universal dynamic common-sense fallback parser
    t_lower = text.lower()
    include_filters: list[str] = []
    exclude_filters: list[str] = []

    # Seniority: Fresher / Entry Level / Junior / Intern
    if any(k in t_lower for k in ["fresher", "freshers", "entry level", "entry-level", "junior", "intern", "internship", "trainee"]):
        if any(k in t_lower for k in ["fresher", "freshers"]):
            include_filters.append("fresher")
        elif any(k in t_lower for k in ["entry level", "entry-level"]):
            include_filters.append("entry")
        elif "junior" in t_lower:
            include_filters.append("junior")
        elif any(k in t_lower for k in ["intern", "internship"]):
            include_filters.append("intern")
        exclude_filters.extend(["senior", "lead", "principal", "manager", "staff", "head", "director"])

    # Seniority: Senior / Lead / Principal / Staff / Architect
    elif any(k in t_lower for k in ["senior", "sr", "lead", "principal", "staff", "architect"]):
        if "senior" in t_lower or "sr" in t_lower:
            include_filters.append("senior")
        elif "lead" in t_lower:
            include_filters.append("lead")
        elif "principal" in t_lower:
            include_filters.append("principal")
        elif "architect" in t_lower:
            include_filters.append("architect")
        exclude_filters.extend(["junior", "fresher", "entry", "intern", "trainee"])

    # Work Mode: Remote / Hybrid / Onsite
    if any(k in t_lower for k in ["remote", "work from home", "wfh"]):
        include_filters.append("remote")
        exclude_filters.extend(["onsite", "on-site"])
    elif "hybrid" in t_lower:
        include_filters.append("hybrid")
    elif any(k in t_lower for k in ["onsite", "on-site", "in-office"]):
        include_filters.append("onsite")
        exclude_filters.append("remote")

    # Contract / Employment Type
    if any(k in t_lower for k in ["contract", "contractor", "freelance"]):
        include_filters.append("contract")
    if "part-time" in t_lower:
        include_filters.append("part-time")
    elif "full-time" in t_lower:
        include_filters.append("full-time")

    # Dynamic extraction of "only <X> jobs" or "filter by <X>"
    m_only = re.search(r"\b(?:only|show|filter\s+by)\s+([a-zA-Z0-9\-]+)\s+(?:jobs?|roles?|openings?)\b", t_lower)
    if m_only:
        candidate = m_only.group(1).strip()
        if candidate not in include_filters and candidate not in ["the", "a", "an", "all", "top", "active", "open"]:
            include_filters.append(candidate)

    return list(dict.fromkeys(include_filters)), list(dict.fromkeys(exclude_filters))


def _extract_job_filter(text: str) -> str | None:
    """Extract job modifier or filter context (e.g., 'current', 'fresher', 'remote', 'entry level')."""
    if not text or not text.strip():
        return None
    t_lower = text.lower()
    for flt in KNOWN_JOB_FILTERS:
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(flt)}(?![a-zA-Z0-9])"
        if re.search(pattern, t_lower):
            if flt in ("current", "latest", "today", "right now", "active right now", "recent"):
                return "current"
            if flt in ("freshers", "fresher"):
                return "fresher"
            if flt in ("entry-level", "entry level"):
                return "entry level"
            if flt in ("internship", "intern"):
                return "internship"
            if flt in ("full-time",):
                return "full-time"
            if flt in ("part-time",):
                return "part-time"
            return flt
    return None


def _extract_prompt_entity(text: str) -> str | None:
    """Actively extract the target role or technology skill from user prompt text.
    Explicit prompt entities take absolute precedence over background user context (Prompt > Context).
    Job filters (e.g. 'fresher', 'remote') are treated as modifiers and not candidate role entities.
    """
    if not text or not text.strip():
        return None
    t_lower = text.lower()

    # 1. Check known role aliases (e.g. 'ui/ux', 'backend developer')
    for alias, standard in KNOWN_ROLE_ALIASES.items():
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(alias)}(?![a-zA-Z0-9])"
        if re.search(pattern, t_lower):
            return standard

    # 2. Check standard role metadata keys
    for role_name in ROLE_METADATA.keys():
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(role_name.lower())}(?![a-zA-Z0-9])"
        if re.search(pattern, t_lower):
            return role_name

    # 3. Check standalone technology entities (e.g. 'python', 'figma', 'react', 'docker')
    for tech_lower, tech_name in KNOWN_TECH_ENTITIES:
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(tech_lower)}(?![a-zA-Z0-9])"
        if re.search(pattern, t_lower):
            return tech_name

    # 4. Pattern check for: "<entity> (jobs?|openings?|demand|hiring|offers?|roles?)"
    stop_words = {
        "the", "a", "an", "any", "all", "top", "good", "new", "more", "my", "our", "their",
        "that", "this", "these", "those", "which", "what", "current", "target", "same",
        "each", "every", "such", "some", "skill", "skills", "tech", "technology",
        "technologies", "job", "jobs", "role", "roles", "market", "hiring", "demand",
        "for", "about", "in", "with", "from", "most", "best", "popular", "trending", "trend",
        "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "can", "could", "should", "would", "may", "might", "must", "will", "shall",
        "find", "show", "get", "give", "list", "see", "view", "want", "need", "like", "here", "there",
        "fresher", "freshers", "entry", "level", "entry-level", "junior", "senior", "intern", "internship",
        "remote", "hybrid", "onsite", "contract", "contractor", "freelance", "full-time", "part-time", "only", "just", "filter", "filters", "wfh", "lead", "principal", "staff"
    }

    m = re.search(r"\b([a-zA-Z0-9+#\.\/\-]{2,20})\s+(?:jobs?|openings?|hiring|offers?|roles?|positions?|demand|trends?)\b", t_lower)
    if m:
        candidate = m.group(1).strip()
        if candidate not in stop_words:
            return candidate.upper() if len(candidate) <= 3 else candidate.title()

    # 5. Pattern check for: "(?:jobs?|openings?|demand|hiring|roles?)\s+(?:for|in|with|of|on)\s+<entity>"
    m_prep = re.search(r"\b(?:jobs?|openings?|hiring|demand|trends?|roles?|positions?|offers?)\s+(?:for|in|with|of|on)\s+([a-zA-Z0-9+#\.\/\-]{2,20})\b", t_lower)
    if m_prep:
        candidate = m_prep.group(1).strip()
        if candidate not in stop_words:
            return candidate.upper() if len(candidate) <= 3 else candidate.title()

    return None


def _extract_role(text: str) -> str | None:
    """Extract standard job role or technology entity from text."""
    return _extract_prompt_entity(text)


def _extract_location(text: str) -> str | None:
    """Extract geographical location from user prompt text."""
    t_lower = text.lower()
    for loc in KNOWN_LOCATIONS:
        pattern = rf"\b{loc.lower()}\b"
        if re.search(pattern, t_lower):
            if loc.lower() in ("bangalore", "bengaluru"):
                return "Bengaluru"
            if loc.lower() in ("gurgaon", "gurugram"):
                return "Gurgaon"
            return loc
    return None


def _extract_skill(text: str) -> str | None:
    """Extract single tech skill from text for ecosystem inquiry."""
    if not text:
        return None
    t_lower = text.lower()
    for tech_lower, _ in KNOWN_TECH_ENTITIES:
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(tech_lower)}(?![a-zA-Z0-9])"
        if re.search(pattern, t_lower):
            return tech_lower
    for sk in KNOWN_SKILLS:
        pattern = rf"\b{re.escape(sk)}\b"
        if re.search(pattern, t_lower):
            return sk
    return None


def resolve_multi_turn_context(
    messages: list[ChatMessage],
    user_context: UserContext,
) -> dict[str, Any]:
    """Inspect multi-turn message history and user profile to resolve active entities.
    Strictly enforces Prompt > Context: explicit prompt entities override background context.
    Inherits target_role on follow-up filter queries (e.g. 'Show only fresher jobs').
    """
    latest_user_text = ""
    for msg in reversed(messages):
        if msg.role == "user":
            latest_user_text = msg.content
            break

    # 0. Resolve dynamic inclusion and exclusion filters
    include_filters, exclude_filters = extract_dynamic_filters(latest_user_text)
    filter_context = _extract_job_filter(latest_user_text)
    if not include_filters and not exclude_filters and not filter_context:
        for msg in reversed(messages[:-1]):
            if msg.role == "user":
                prev_inc, prev_exc = extract_dynamic_filters(msg.content)
                prev_flt = _extract_job_filter(msg.content)
                if prev_inc or prev_exc or prev_flt:
                    include_filters, exclude_filters = prev_inc, prev_exc
                    filter_context = prev_flt or (", ".join(prev_inc) if prev_inc else None)
                    break
    if not filter_context and include_filters:
        filter_context = ", ".join(include_filters)

    # 1. Resolve target role/entity: current prompt explicit entity > previous turns > profile default
    explicit_entity = _extract_prompt_entity(latest_user_text)
    if explicit_entity:
        target_role = explicit_entity
    else:
        target_role = None
        for msg in reversed(messages[:-1]):
            if msg.role == "user":
                found = _extract_prompt_entity(msg.content)
                if found:
                    target_role = found
                    break

    if not target_role:
        target_role = user_context.target_role.strip() or user_context.current_view.strip() or "AI Engineer"

    # Only normalize standard role aliases; custom entities like 'Python' or 'UI/UX' remain intact
    target_role = normalize_target_role(target_role)

    # 2. Resolve location: current prompt -> previous turns -> user context -> India
    location = _extract_location(latest_user_text)
    if not location:
        for msg in reversed(messages[:-1]):
            if msg.role == "user":
                found = _extract_location(msg.content)
                if found:
                    location = found
                    break
    if not location:
        location = user_context.location.strip() or "India"

    # 3. Resolve user skills: user context profile (or override if prompt names a single skill)
    user_skills = [s.strip() for s in user_context.user_skills if s and s.strip()]

    # 4. Resolve specific skill query for ecosystem
    queried_skill = _extract_skill(latest_user_text)

    return {
        "latest_prompt": latest_user_text,
        "target_role": target_role,
        "location": location,
        "user_skills": user_skills,
        "queried_skill": queried_skill,
        "filter_context": filter_context,
        "include_filters": include_filters,
        "exclude_filters": exclude_filters,
    }


# ---------------------------------------------------------------------------
# DETERMINISTIC INTENT ROUTER & TOOL EXECUTOR
# ---------------------------------------------------------------------------

def classify_intent(prompt: str) -> list[str]:
    """Classify user intent into one or more intelligence tool categories or GENERAL_QA.

    Enforces laser-focused tool routing & restrictions:
    - LIVE_JOBS: Must trigger for queries containing 'find', 'search', 'show me', 'jobs', 'roles',
      'openings', 'offers', or specific modifiers like 'remote', 'part-time', 'fresher' attached to a role.
    - SKILL_GAP / Readiness: MUST STRICTLY trigger ONLY when the user explicitly references their own
      profile, readiness, or missing skills (e.g., 'am I ready', 'my skills', 'critical gaps', 'what skills am I missing').
      Strict negative constraint: Do NOT trigger SKILL_GAP if the user is asking to 'find', 'show', or 'search' for roles/jobs.
    - HISTORICAL_DEMAND: If user asks for hiring demand statistics/trajectory -> ONLY HISTORICAL_DEMAND.
    - ECOSYSTEM: If user asks for developer community/ecosystem momentum -> ONLY ECOSYSTEM.
    - GENERAL_QA: If user asks for general QA / definition / education -> GENERAL_QA (0 tools invoked).
    - ONLY multi-part questions (e.g. 'trending skills for AI Engineer') trigger multiple tools.
    - If no data retrieval is requested, strictly defaults to GENERAL_QA.
    """
    p_lower = prompt.lower().strip()

    # 1. Check for job search / vacancy keywords (Data Retrieval)
    job_action_keywords = [
        "find", "search", "show me", "jobs", "job", "roles", "role", "openings", "opening",
        "offers", "offer", "positions", "position", "vacanc", "hiring", "apply", "companies hiring"
    ]
    job_modifier_keywords = [
        "remote", "part-time", "full-time", "fresher", "freshers", "internship", "intern", "hybrid", "onsite"
    ]
    has_job_action = any(re.search(rf"\b{re.escape(k)}\b", p_lower) for k in job_action_keywords)
    has_job_modifier = any(re.search(rf"\b{re.escape(k)}\b", p_lower) for k in job_modifier_keywords)
    is_job_query = has_job_action or has_job_modifier

    # 2. Check for demand / historical hiring metrics (Data Retrieval)
    demand_keywords = [
        "demand", "mom", "market size", "top employer", "historical", "trajectory"
    ]
    is_demand_query = any(k in p_lower for k in demand_keywords)

    # 3. Check for learning / gap / readiness keywords (MUST STRICTLY trigger ONLY when user explicitly references their own profile, readiness, or missing skills)
    learning_gap_keywords = [
        "am i ready", "my skills", "critical gap", "critical gaps", "what skills am i missing",
        "which skills am i missing", "missing skill", "missing skills", "skill gap", "skill gaps",
        "my readiness", "role readiness", "readiness score", "am i qualified",
        "what should i learn", "which skill should i learn", "learn first", "should i learn first",
        "should i learn", "what to learn", "skills to learn", "prepare for", "upskill"
    ]
    is_learning_gap_query = any(k in p_lower for k in learning_gap_keywords)
    if not is_learning_gap_query and any(k in p_lower for k in ["gap", "readiness", "missing"]):
        if any(re.search(rf"\b{re.escape(w)}\b", p_lower) for w in ["i", "me", "my", "am", "profile", "ready"]):
            is_learning_gap_query = True

    # STRICT NEGATIVE CONSTRAINT: Do NOT trigger SKILL_GAP if the user is asking to 'find', 'show', or 'search' for roles/jobs
    if is_job_query and not any(k in p_lower for k in ["am i ready", "my skills", "missing", "gap"]):
        is_learning_gap_query = False

    # 4. Check for developer ecosystem telemetry keywords (Data Retrieval)
    ecosystem_keywords = [
        "ecosystem", "github", "stack overflow", "stackoverflow", "wikipedia",
        "developer activity", "community", "open source", "repo", "repositories"
    ]
    is_ecosystem_query = any(k in p_lower for k in ecosystem_keywords)

    # 5. Check for market / trend / popularity keywords (Data Retrieval)
    market_keywords = [
        "trending", "trend", "trends", "top skill", "top skills", "top tech",
        "popular", "growth", "in demand", "fastest growing", "momentum",
        "emerging", "traction", "landscape"
    ]
    is_market_query = any(k in p_lower for k in market_keywords) or ("market" in p_lower and not is_demand_query and not is_job_query)

    # 6. Check for General QA / Definitional / Educational phrasing
    qa_triggers = [
        "explain", "what is", "what are", "what does", "define", "definition",
        "how does", "how do", "difference between", " vs ", " versus ",
        "in simple words", "in simple terms", "for beginners", "eli5",
        "tell me about", "meaning of", "pros and cons", "overview of",
        "compare", "comparison"
    ]
    is_qa_trigger = any(q in p_lower for q in qa_triggers)

    # Bypasses all tools for definitional, educational, or generic questions without data retrieval request
    if is_qa_trigger and not is_job_query and not is_demand_query and not is_market_query and not (is_learning_gap_query and any(w in p_lower for w in ["ready", "readiness", "gap", "missing"])):
        comparison_triggers = [" vs ", " vs. ", " versus ", "difference between", "compare ", "compare", "comparison"]
        if any(w in p_lower for w in comparison_triggers) or re.search(r"\bvs\b", p_lower) is not None:
            return ["CONCEPT_COMPARISON"]
        return ["GENERAL_QA"]

    # Check if prompt explicitly mentions role/skill alongside trend keywords
    has_role_in_prompt = _extract_prompt_entity(prompt) is not None or "for " in p_lower

    # LASER-FOCUSED RULE: Live Jobs query (e.g. 'python job offers', 'Find Backend Developer jobs in India', 'Find remote Data Scientist roles')
    if is_job_query and not is_market_query and not is_learning_gap_query and not is_ecosystem_query:
        if any(term in p_lower for term in ["historical", "past", "history", "volume", "how many"]):
            return ["HISTORICAL_DEMAND"]
        return ["LIVE_JOBS"]

    # LASER-FOCUSED RULE: Hiring demand query (e.g. 'ui/ux demand right now', 'demand for AI Engineer')
    if is_demand_query and not is_job_query and not is_market_query and not is_learning_gap_query and not is_ecosystem_query:
        return ["HISTORICAL_DEMAND"]

    # LASER-FOCUSED RULE: Ecosystem query (e.g. 'Is developer activity around Figma increasing on GitHub and Stack Overflow?')
    if is_ecosystem_query and not is_job_query and not is_demand_query and not is_learning_gap_query:
        return ["ECOSYSTEM"]

    # LASER-FOCUSED RULE: Personal Skill Gap / Readiness query (e.g. 'Am I ready for AI Engineer?')
    if is_learning_gap_query and not is_market_query:
        return ["SKILL_GAP"]

    # MULTI-PART & MARKET QUERIES:
    # A. Multi-part query asking for market trends FOR a specific role/learning (e.g. 'trending skills for AI Engineer')
    if (is_market_query or is_ecosystem_query) and (has_role_in_prompt or is_learning_gap_query):
        return ["ECOSYSTEM", "HISTORICAL_DEMAND", "SKILL_GAP"]

    # B. Pure broad market trend query (e.g. 'What are the trending skills?', 'top skill trends')
    if is_market_query or is_ecosystem_query:
        return ["ECOSYSTEM", "HISTORICAL_DEMAND"]

    # Fallback for personal queries: MUST STRICTLY reference readiness or profile, NEVER match substrings like 'remote'
    if re.search(r"\b(my\s+skills|my\s+readiness|am\s+i\s+ready|my\s+profile)\b", p_lower) and not is_job_query:
        return ["SKILL_GAP"]

    # If user does not explicitly request data retrieval (jobs, market trends, readiness), bypass all tools
    return ["GENERAL_QA"]


def extract_comparison_entities(prompt: str) -> tuple[str, str, str]:
    """Extract compared entities from comparison prompt.
    Returns (entity_a, entity_b, formatted_title).
    Example: 'AI Engineer vs data scientist' -> ('AI Engineer', 'Data Scientist', 'AI Engineer vs Data Scientist')
    """
    clean = re.sub(r"^(?:compare|contrast|difference between|versus|vs)\s+", "", prompt.strip(), flags=re.IGNORECASE).strip()
    clean = re.sub(r"^(?:can you|please|tell me|explain)\s+", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"^(?:the difference between)\s+", "", clean, flags=re.IGNORECASE).strip()
    parts = re.split(r"\s+(?:vs\.?|versus|and)\s+", clean, flags=re.IGNORECASE)

    def _title(s: str) -> str:
        words = s.strip().split()
        titled = []
        for w in words:
            if w.upper() in ("AI", "ML", "UI", "UX", "NLP", "LLM", "SQL", "AWS", "GCP"):
                titled.append(w.upper())
            else:
                titled.append(w.capitalize())
        return " ".join(titled)

    if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
        ent_a = _title(parts[0])
        ent_b = _title(parts[1])
        return ent_a, ent_b, f"{ent_a} vs {ent_b}"

    return "AI Engineer", "Data Scientist", "AI Engineer vs Data Scientist"


def mask_api_key(key: str) -> str:
    """Mask an API key for safe logging, displaying first 4 and last 4 characters."""
    if not key:
        return "***"
    k_str = str(key).strip()
    if len(k_str) <= 8:
        return "***"
    return f"{k_str[:4]}...{k_str[-4:]}"


def get_configured_gemini_keys() -> list[str]:
    """Retrieve all available Gemini API keys in prioritized order, enabling failover.
    Priority order: GEMINI_API_KEY, GEMINI_API_A_KEY, GEMINI_API_B_KEY, GEMINI_API_C_KEY, GOOGLE_API_KEY.
    Explicitly filters out None, empty strings, and placeholder values like 'your_key_here'.
    """
    keys: list[str] = []
    priority_order = [
        "GEMINI_API_KEY",
        "GEMINI_API_A_KEY",
        "GEMINI_API_B_KEY",
        "GEMINI_API_C_KEY",
        "GOOGLE_API_D_KEY",
        "GOOGLE_API_KEY",
    ]
    for var_name in priority_order:
        val = os.getenv(var_name)
        if val:
            clean = val.strip()
            # Ignore empty or placeholder strings like 'your_key_here'
            if clean and clean.lower() not in (
                "your_key_here",
                "your_gemini_api_key",
                "your_gemini_api_key_here",
                "placeholder",
                "none",
                "",
            ) and not clean.lower().startswith("your_") and clean not in keys:
                keys.append(clean)
    if not keys:
        logger.error("Gemini API key is missing or invalid.")
    return keys


def execute_gemini_request_with_fallback(
    payload: dict[str, Any],
    candidate_models: list[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """Execute Gemini generateContent POST request with sequential fallback across all available keys.
    Catches 401, 403, 429, 503, timeouts, and network errors, logging detailed errors:
      logger.error(f"Key {masked_key} failed: {err_msg}")
      logger.warning(f"Key {masked_key} failed with status {status_code}. Trying next key...")
    Returns JSON response dict on first 200 OK, or None if all keys fail or are exhausted.
    """
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
        return None

    import httpx

    keys = get_configured_gemini_keys()
    if not keys:
        return None

    if candidate_models is None:
        gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        candidate_models = [gemini_model_name, "gemini-2.5-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemini-1.5-flash"]
        candidate_models = list(dict.fromkeys(candidate_models))

    for api_key in keys:
        masked = mask_api_key(api_key)
        for mod in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(url, json=payload)
                    resp_text = getattr(resp, "text", "") or ""
                    if resp.status_code == 200:
                        return resp.json()
                    elif resp.status_code == 404:
                        logger.debug("Model %s returned 404 for key %s. Trying next candidate model...", mod, masked)
                        continue
                    elif resp.status_code in (400, 401, 403):
                        err_msg = f"{resp.status_code} Unauthorized / Invalid Key: {resp_text[:120].strip()}"
                        logger.error(f"Key {masked} failed: {err_msg}")
                        logger.warning(f"Key {masked} failed with status {resp.status_code}. Trying next key...")
                        break
                    elif resp.status_code == 429:
                        err_msg = f"429 Quota Exceeded / Rate Limited: {resp_text[:120].strip()}"
                        logger.error(f"Key {masked} failed: {err_msg}")
                        logger.warning(f"Key {masked} failed with status {resp.status_code}. Trying next key...")
                        break
                    elif resp.status_code == 503:
                        err_msg = f"503 Service Unavailable (High Demand): {resp_text[:120].strip()}"
                        logger.error(f"Key {masked} failed: {err_msg}")
                        logger.warning(f"Key {masked} failed with status {resp.status_code}. Trying next key...")
                        break
                    else:
                        err_msg = f"HTTP {resp.status_code}: {resp_text[:120].strip()}"
                        logger.error(f"Key {masked} failed: {err_msg}")
                        logger.warning(f"Key {masked} failed with status {resp.status_code}. Trying next key...")
                        break
            except httpx.HTTPStatusError as http_err:
                status_code = http_err.response.status_code if http_err.response else 500
                logger.error(f"Key {masked} failed: {str(http_err)}")
                logger.warning(f"Key {masked} failed with status {status_code}. Trying next key...")
                break
            except httpx.RequestError as req_err:
                logger.error(f"Key {masked} failed: {type(req_err).__name__}: {str(req_err)}")
                logger.warning(f"Key {masked} failed with status 500. Trying next key...")
                break
            except Exception as exc:
                logger.error(f"Key {masked} failed: {type(exc).__name__}: {str(exc)}")
                logger.warning(f"Key {masked} failed with status 500. Trying next key...")
                break

    logger.warning("All configured Gemini API keys failed or were exhausted. Invoking deterministic fallback.")
    return None


def extract_next_steps_bullets(text: str) -> list[str]:
    """Extract bulleted questions from ### Next Steps section in markdown text."""
    match = re.search(r"### Next Steps\s*\n([\s\S]*?)(?:\Z|\n### )", text)
    if not match:
        return []
    lines = match.group(1).splitlines()
    bullets: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")) or (stripped and stripped[0].isdigit() and stripped[1:3] in (". ", ") ")):
            clean = re.sub(r"^[-*•\d.)\s]+", "", stripped).strip()
            if clean:
                bullets.append(clean)
    return bullets[:3]


def synthesize_general_qa_answer(prompt: str, resolved: dict[str, Any]) -> str:
    """Synthesize clean, educational markdown for conceptual and definitional questions.
    Uses dynamic Gemini generation when API credentials are configured.
    If Gemini call fails, logs error and returns honest error or conceptual explanation.
    """
    p_lower = prompt.lower().strip()
    is_comparison = any(w in p_lower for w in [" vs ", " vs. ", " versus ", "difference between", "compare ", "compare", "comparison"]) or re.search(r"\bvs\b", p_lower) is not None

    # Pre-computed high-quality answers for core AI/ML concept questions
    if (("ai" in p_lower and "ml" in p_lower) or "machine learning" in p_lower or "artificial intelligence" in p_lower) and is_comparison:
        return (
            "### Concept Comparison: Artificial Intelligence vs. Machine Learning\n\n"
            "**Artificial Intelligence (AI)** and **Machine Learning (ML)** are closely related disciplines, but they represent different tiers of modern computational technology.\n\n"
            "| Dimension | Artificial Intelligence (AI) | Machine Learning (ML) |\n"
            "| :--- | :--- | :--- |\n"
            "| **Core Definition** | Broad umbrella discipline of creating systems capable of human-like intelligence, reasoning, and problem-solving. | Specialized subset of AI focused on algorithms that learn patterns from data without explicit procedural programming. |\n"
            "| **Scope** | Expansive: includes robotics, rule engines, NLP, computer vision, knowledge graphs, and ML. | Focused: centers on statistical modeling, neural networks, loss optimization, and feature representation. |\n"
            "| **Operational Method** | Employs symbolic logic, search heuristics, inference trees, and data-driven models. | Ingests training data, tunes model weights, and conducts mathematical inference on unseen inputs. |\n"
            "| **Primary Goal** | Simulate human decision-making and autonomous task execution across diverse domains. | Maximize predictive accuracy and minimize loss function on well-defined task datasets. |\n"
            "| **Key Tools** | Expert systems, automated planners, robotic controllers, reasoning engines. | PyTorch, TensorFlow, Scikit-Learn, XGBoost, Pandas. |\n\n"
            "#### Key Synthesis\n"
            "- **All Machine Learning is Artificial Intelligence**, but **not all Artificial Intelligence is Machine Learning**.\n"
            "- Machine learning is the practical algorithmic engine driving modern AI breakthroughs like Large Language Models (LLMs) and computer vision.\n\n"
            "### Next Steps\n"
            "- Would you like to explore deep learning architectures and transformer models next?\n"
            "- What are the primary mathematical prerequisites for machine learning engineering?\n"
            "- How do enterprise AI pipelines integrate live data pipelines with model inference?"
        )

    table_instruction = (
        " If this is a comparison or 'vs' query, you MUST provide a side-by-side Markdown comparison table with columns '| Dimension | [Concept A] | [Concept B] |' comparing key dimensions (e.g. Core Definition, Scope, Operational Method, Key Tools) before summarizing differences."
        if is_comparison
        else ""
    )
    qa_instruction = (
        f"You are TalentScope's educational AI guide. Explain clearly, simply, with intuitive examples and bullet points: {prompt}.{table_instruction}\n\n"
        "At the very end of every response, you MUST generate a '### Next Steps' section containing exactly 2 to 3 bulleted questions. "
        "These questions must be highly contextual, dynamically based on the exact data or answer you just provided, and designed to help the user explore the current specific topic further. Never use generic fallback questions."
    )

    keys = get_configured_gemini_keys()
    gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # 1. First check if google.generativeai is mocked in sys.modules (for unit test compatibility)
    if "google.generativeai" in sys.modules and keys:
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=keys[0])
            model = genai.GenerativeModel(gemini_model_name)
            resp = model.generate_content(qa_instruction)
            if resp and resp.text and resp.text.strip():
                return resp.text.strip()
            logger.error("Gemini API key is missing or invalid.")
            return "Error: Unable to connect to the Gemini AI service. Please check API keys."
        except Exception as exc:
            logger.error("Gemini API key is missing or invalid.")
            logger.info("google.generativeai generate_content failed: %s", exc)
            return "Error: Unable to connect to the Gemini AI service. Please check API keys."

    # 2. Use modern REST endpoint with sequential key fallback across active Gemini models
    if keys and os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") != "1":
        try:
            payload = {
                "contents": [{"parts": [{"text": qa_instruction}]}],
            }
            candidate_models = [gemini_model_name, "gemini-2.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]
            candidate_models = list(dict.fromkeys(candidate_models))

            json_data = execute_gemini_request_with_fallback(payload, candidate_models=candidate_models)
            if json_data:
                candidates = json_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    texts = [p.get("text") for p in parts if "text" in p and p.get("text")]
                    if texts:
                        return "\n\n".join(texts).strip()
            logger.error("Gemini API key is missing or invalid.")
        except Exception as exc:
            logger.error("Gemini API key is missing or invalid.")
            logger.info("Gemini REST generation in synthesize_general_qa_answer failed: %s", exc)
    else:
        logger.error("Gemini API key is missing or invalid.")

    p_lower = prompt.lower().strip()
    is_comparison = any(w in p_lower for w in [" vs ", " vs. ", " versus ", "difference between", "compare "]) or re.search(r"\bvs\b", p_lower) is not None

    # Pre-computed high-quality answers for core AI/ML concept questions
    if ("ai" in p_lower and "ml" in p_lower) or "machine learning" in p_lower or "artificial intelligence" in p_lower:
        if is_comparison:
            return (
                "### Concept Comparison: Artificial Intelligence vs. Machine Learning\n\n"
                "**Artificial Intelligence (AI)** and **Machine Learning (ML)** are closely related disciplines, but they represent different tiers of modern computational technology.\n\n"
                "| Dimension | Artificial Intelligence (AI) | Machine Learning (ML) |\n"
                "| :--- | :--- | :--- |\n"
                "| **Core Definition** | Broad umbrella discipline of creating systems capable of human-like intelligence, reasoning, and problem-solving. | Specialized subset of AI focused on algorithms that learn patterns from data without explicit procedural programming. |\n"
                "| **Scope** | Expansive: includes robotics, rule engines, NLP, computer vision, knowledge graphs, and ML. | Focused: centers on statistical modeling, neural networks, loss optimization, and feature representation. |\n"
                "| **Operational Method** | Employs symbolic logic, search heuristics, inference trees, and data-driven models. | Ingests training data, tunes model weights, and conducts mathematical inference on unseen inputs. |\n"
                "| **Primary Goal** | Simulate human decision-making and autonomous task execution across diverse domains. | Maximize predictive accuracy and minimize loss function on well-defined task datasets. |\n"
                "| **Key Tools** | Expert systems, automated planners, robotic controllers, reasoning engines. | PyTorch, TensorFlow, Scikit-Learn, XGBoost, Pandas. |\n\n"
                "#### Key Synthesis\n"
                "- **All Machine Learning is Artificial Intelligence**, but **not all Artificial Intelligence is Machine Learning**.\n"
                "- Machine learning is the practical algorithmic engine driving modern AI breakthroughs like Large Language Models (LLMs) and computer vision.\n\n"
                "### Next Steps\n"
                "- Would you like to explore deep learning architectures and transformer models next?\n"
                "- What are the primary mathematical prerequisites for machine learning engineering?\n"
                "- How do enterprise AI pipelines integrate live data pipelines with model inference?"
            )
        else:
            return (
                "### Core Concept: Artificial Intelligence & Machine Learning\n\n"
                "**Artificial Intelligence (AI)** is the broad discipline of engineering intelligent systems capable of performing tasks that traditionally require human cognitive capabilities, such as reasoning, problem-solving, sensory perception, and natural language understanding.\n\n"
                "**Machine Learning (ML)** is the primary computational engine and subdiscipline of AI. Rather than relying on rigid, manually programmed business logic, ML algorithms ingest data and iteratively train statistical models to make accurate predictions and autonomous decisions.\n\n"
                "#### How AI and ML Intersect in Practice:\n"
                "1. **Data Ingestion & Feature Engineering**: Raw observations, telemetry, or text are transformed into numerical vectors.\n"
                "2. **Pattern Recognition & Loss Minimization**: Statistical models optimize parameters to minimize error over training samples.\n"
                "3. **Autonomous Inference**: The overarching AI system deploys the trained model to interact, reason, and act in live environments.\n\n"
                "#### Primary Subfields & Breakthroughs:\n"
                "- **Supervised Learning**: Classification and regression trained with verified ground truth (e.g., fraud detection, spam filtering).\n"
                "- **Unsupervised Learning**: Clustering, anomaly detection, and dimensionality reduction discovering latent structure without labels.\n"
                "- **Deep Learning & Generative Models**: High-dimensional neural architectures powering modern Large Language Models (LLMs) and computer vision systems.\n\n"
                "### Next Steps\n"
                "- Would you like a side-by-side comparison table contrasting AI versus Machine Learning?\n"
                "- What are the core mathematical foundations (calculus, linear algebra, probability) needed for ML?\n"
                "- Which Python frameworks (PyTorch, Scikit-Learn, Hugging Face) should you learn first?"
            )

    # Deterministic Graceful Offline Fallback for Concept / Role Comparisons
    if is_comparison:
        ent_a, ent_b, comp_title = extract_comparison_entities(prompt)
        q1 = f"What is an {ent_a}?"
        q2 = f"What does a {ent_b} do?"
        return (
            f"### Connectivity Issue\n"
            f"We are currently unable to reach the AI service to generate a real-time comparison for **{comp_title}**. "
            "Please check your network connection, API key validity, or try again later.\n\n"
            f"### Next Steps\n"
            f"- {q1}\n"
            f"- {q2}"
        )

    return "Error: Unable to connect to the Gemini AI service. Please check API keys."



# ---------------------------------------------------------------------------
# TOOL SYNTHESIS HELPERS (SECTION 6 STRICT BOUNDARIES)
# ---------------------------------------------------------------------------

def synthesize_skill_gap_answer(payload: dict[str, Any], user_skills: list[str]) -> str:
    """Synthesize concise structured markdown for role-to-skill gap analysis without boilerplate."""
    role = payload.get("targetRole") or payload.get("target_role", "Target Role")
    score = payload.get("readinessScore", 0)
    matched = payload.get("matchedSkills") or []
    missing = payload.get("missingSkills") or []
    matched_cnt = payload.get("matchedCount", len(matched))
    total_cnt = payload.get("totalTopSkills", len(matched) + len(missing))

    if total_cnt == 0 or (not matched and not missing):
        return (
            f"### Role Readiness Assessment: {role}\n\n"
            f"⚠️ **Insufficient Enterprise Data**: No verified job postings were found in PostgreSQL for `{role}`. "
            f"Please specify a tracked standard role (e.g., AI Engineer, Backend Developer, Data Scientist, Cloud Solutions Architect)."
        )

    if score >= 75:
        verdict = f"🟢 **High Readiness ({score}%)**: Your current skill profile demonstrates strong alignment with active market hiring requirements for **{role}** ({matched_cnt} of {total_cnt} skills matched)."
    elif score >= 50:
        verdict = f"🟡 **Moderate Readiness ({score}%)**: You possess solid foundational skills for **{role}** ({matched_cnt} of {total_cnt} skills matched), but bridging critical market gaps will elevate your profile."
    else:
        verdict = f"🟠 **Developing Readiness ({score}%)**: Your profile currently covers {matched_cnt} of the top {total_cnt} demanded skills for **{role}**. Focused upskilling is recommended."

    matched_list = "\n".join([f"- ✅ **{m['name']}** ({m.get('demandFrequency', m.get('frequency', 0)):,} postings)" for m in matched[:6]]) or "- *No direct matches recorded in current profile.*"
    missing_list = "\n".join([f"- ⚠️ **{m['name']}** ({m.get('demandFrequency', m.get('frequency', 0)):,} postings)" for m in missing[:6]]) or "- *All core role skills matched!*"

    recommendation_lines = []
    if missing:
        top_m = missing[0]
        top_name = top_m.get("name") or top_m.get("skill", "Core Skill")
        top_freq = top_m.get("demandFrequency", top_m.get("frequency", 0))
        recommendation_lines = [
            "#### Recommended Skills to Learn First",
            f"Based on real PostgreSQL enterprise postings for **{role}**, prioritize **{top_name}** first (demanded in {top_freq:,} active requisitions)"
            + (f", followed by: {', '.join(['**' + m['name'] + '**' for m in missing[1:4]])}." if len(missing) > 1 else "."),
            "",
        ]

    lines = [
        f"### Role Readiness Assessment: {role}",
        "",
        verdict,
        "",
        "#### Verified Profile Strengths",
        matched_list,
        "",
        "#### Critical Skill Gaps to Bridge",
        missing_list,
        "",
        *recommendation_lines,
        f"> **Provenance**: {payload.get('provenance', 'PostgreSQL Verified Enterprise Hiring Telemetry (India)')}. Readiness scores are weighted by market frequency across real job requisitions.",
    ]
    return "\n".join(lines)


def synthesize_ecosystem_answer(payload: dict[str, Any]) -> str:
    """Synthesize concise structured markdown for developer ecosystem signals without boilerplate."""
    notice = payload.get("boundary_notice", "")
    skill_name = payload.get("skill_name")

    if skill_name:
        mom = payload.get("mom_growth_pct")
        trend = payload.get("trend") or payload.get("momentum_status", "Steady")
        if trend == "Insufficient Data":
            status_desc = "`Insufficient Data` (Fewer than 4 months of baseline telemetry available)"
        elif mom is not None and mom > 0:
            status_desc = f"`{trend}` (+{mom:.1f}% MoM Traction)"
        elif mom is not None:
            status_desc = f"`{trend}` ({mom:.1f}% MoM Traction)"
        else:
            status_desc = f"`{trend}`"

        signals = payload.get("ecosystem_signals", {})
        wiki_pts = signals.get("wikipedia", [])
        so_pts = signals.get("stackoverflow", [])
        gh_pts = signals.get("github", [])

        latest_wiki = wiki_pts[-1]["value"] if wiki_pts else 0
        latest_so = so_pts[-1]["value"] if so_pts else 0
        latest_gh = gh_pts[-1]["value"] if gh_pts else 0

        window_desc = payload.get("observation_window") or "2026-01 to 2026-04"
        lines = [
            f"### Developer Community Traction: {skill_name.title()}",
            "",
            f"- **Community Status**: {status_desc}",
            f"- **Telemetry Window**: **{window_desc}** (4-month mature baseline dynamically evaluated against system date)",
            f"- **Stack Overflow Inquiries**: **{latest_so:,}** active monthly technical inquiries tagged for this ecosystem.",
            f"- **GitHub Repositories**: **{latest_gh:,}** active open-source repositories tracked under matching topics.",
            f"- **Wikipedia Interest**: **{latest_wiki:,}** monthly pageviews in latest observation window.",
            "",
            f"> **Boundary Disclaimer**: {notice}",
        ]
        return "\n".join(lines)

    # Macro ecosystem overview
    meta = payload.get("macro_metrics", {})
    emerging = payload.get("emerging_technologies", [])
    window_desc = payload.get("observation_window") or meta.get("observation_window") or f"{meta.get('historical_baseline_period', '2026-01')} to {meta.get('freshness_period', '2026-04')}"

    emerging_rows = "\n".join([
        f"- **{t['technology']}**: +{t['mom_growth_pct']}% MoM ({t['current_monthly_activity']:,} monthly views)"
        for t in emerging[:5]
    ])

    lines = [
        "### Macro Developer Ecosystem Overview",
        "",
        f"Tracking **{meta.get('total_technologies_tracked', 53)} core technologies** across **{meta.get('total_signals_tracked', 810)} signals** within the mature 4-month telemetry baseline (**{window_desc}**).",
        "",
        "#### Top Emerging Technologies by Community Momentum",
        emerging_rows,
        "",
        f"> **Boundary Disclaimer**: {notice}",
    ]
    return "\n".join(lines)


def synthesize_historical_demand_answer(payload: dict[str, Any]) -> str:
    """Synthesize concise structured markdown for historical hiring demand without boilerplate."""
    role = payload.get("normalized_role", "Job Role")
    total = payload.get("total_postings", 0)
    score = payload.get("demand_score", payload.get("hiring_demand_score", 0))
    trend = payload.get("trend")
    mom = payload.get("mom_growth_pct")

    if total == 0 or trend == "No Active Demand":
        return (
            f"### Enterprise Hiring Demand: {role}\n\n"
            f"- **Hiring Demand Score**: **0 / 100**\n"
            f"- **Total Tracked Postings**: **0** verified requisitions in India catalog\n"
            f"- **Momentum Trajectory**: **No Active Demand**\n\n"
            "There is currently no observable enterprise hiring demand for this role/skill in the tracked database.\n\n"
            f"> **Provenance**: {payload.get('provenance', 'PostgreSQL Enterprise Hiring Requisitions (India)')}."
        )

    if trend == "Insufficient Data":
        trajectory_str = "**Insufficient Data** (< 4 months historical baseline)"
    elif mom is not None and mom > 0:
        trajectory_str = f"**+{mom:.1f}%** ({trend or 'Expanding'} expansion across recent hiring cycles)"
    elif mom is not None:
        trajectory_str = f"**{mom:.1f}%** ({trend or 'Steady'} trajectory across recent hiring cycles)"
    else:
        trajectory_str = f"**Steady** ({trend or 'Baseline'} trajectory)"

    employers = payload.get("top_employers", [])
    top_emp_str = "\n".join([f"- **{e['company_name']}**: {e['posting_count']:,} verified requisitions" for e in employers[:6]])

    lines = [
        f"### Enterprise Hiring Demand: {role}",
        "",
        f"- **Hiring Demand Score**: **{score} / 100**",
        f"- **Total Tracked Postings**: **{total:,}** verified requisitions in India catalog",
        f"- **Momentum Trajectory**: {trajectory_str}",
        "",
        "#### Leading Hiring Employers",
        top_emp_str or "- *Enterprise employers actively recruiting across tech hubs.*",
        "",
        f"> **Provenance**: {payload.get('provenance', 'PostgreSQL Enterprise Hiring Requisitions (India)')}.",
    ]
    return "\n".join(lines)


def synthesize_live_jobs_answer(payload: dict[str, Any]) -> str:
    """Synthesize concise structured markdown for active job openings without boilerplate."""
    role = payload.get("role_name", "Target Role")
    loc = payload.get("location", "India")
    flt = payload.get("filter_context")
    display_role = f"{flt.title()} {role}" if flt else role
    openings = payload.get("openings", [])
    provider = payload.get("source_provider", "Local PostgreSQL Cache")
    transparency = payload.get("source_transparency", f"Verified active requisitions from {provider}.")

    max_data_date = payload.get("max_data_date") or "2026-06-01"
    if not openings:
        freshness_label = "30 days" if ("30 days" in transparency or "30-day" in transparency) else "180 days"
        return (
            f"### Active Job Openings: {display_role} in {loc}\n\n"
            f"**0 active jobs found** matching `{display_role}` in `{loc}`.\n\n"
            f"> **Freshness Notice**: Falling back to local database (Data as of {max_data_date}). Stored records in {provider} older than {freshness_label} of catalog snapshot are omitted. External live feeds returned no active listings.\n\n"
            f"> **Source**: {provider} ({transparency})"
        )

    job_cards = []
    for i, j in enumerate(openings[:5], 1):
        title = j.get("job_title", role)
        company = j.get("company_name", "Enterprise Employer")
        city = j.get("location_city", loc)
        skills = j.get("required_skills", [])
        skills_badge = " · ".join([f"`{s}`" for s in skills[:4]]) if skills else "`Verified Role Skills`"
        apply_url = j.get("apply_url") or "#"
        posted = j.get("posted_at") or "Recently verified"

        job_cards.append(
            f"**{i}. [{title}]({apply_url})** at **{company}**  \n"
            f"📍 {city} · 📅 {posted} · 🏷️ {skills_badge}"
        )

    lines = [
        f"### Active Job Openings: {display_role} in {loc}",
        "",
        "\n\n".join(job_cards),
        "",
        f"> **Source Transparency**: {transparency}",
    ]
    return "\n".join(lines)


def generate_suggested_followups(
    intents: list[str],
    resolved: dict[str, Any],
    has_empty_jobs: bool = False,
    extra_context: dict[str, Any] | None = None,
) -> list[str]:
    """Generate dynamic, role-aware fallback follow-up prompts."""
    role = resolved.get("target_role") or "Software Engineer"
    loc = resolved.get("location") or "India"
    wm = resolved.get("work_mode") or ("remote" if "remote" in str(resolved.get("include_filters", [])) else "")
    wm_str = f"{wm.title()} " if wm else ""

    if "LIVE_JOBS" in intents:
        if has_empty_jobs:
            return [
                f"Broaden search criteria for {role} across other locations and remote work modes",
                f"Which skills are most in demand for {role} in the current hiring landscape?",
                f"Assess role readiness and skill requirements for {role}",
            ]
        return [
            f"What are the typical salary ranges for {wm_str}{role} roles?",
            f"Which specific skills and frameworks are most demanded for {role}?",
            f"Assess my profile readiness for these {role} openings",
        ]
    elif "SKILL_GAP" in intents:
        top_missing = ""
        if extra_context and "missing" in extra_context and extra_context["missing"]:
            top_missing = extra_context["missing"][0].get("name", "")
        missing_phrase = f"in {top_missing}" if top_missing else f"for {role}"
        return [
            f"What are the recommended resources to bridge critical gaps {missing_phrase}?",
            f"Find active {role} jobs matching my current verified skills",
            f"How is enterprise hiring demand trending for {role}?",
        ]
    elif "HISTORICAL_DEMAND" in intents:
        return [
            f"Who are the top enterprise employers hiring for {role}?",
            f"What is the projected hiring trajectory for {role} across upcoming cycles?",
            f"Find active {role} job openings in {loc}",
        ]
    elif "ECOSYSTEM" in intents:
        tech = resolved.get("queried_skill") or role
        return [
            f"How does developer community traction for {tech} compare with hiring demand?",
            f"What related libraries and frameworks are trending alongside {tech}?",
            f"Find active enterprise roles requiring {tech}",
        ]
    else:
        return [
            f"How is {role} applied in real-world enterprise engineering?",
            f"What are the core prerequisites to start learning {role}?",
            f"Show active hiring demand for {role} in {loc}",
        ]


def synthesize_tool_response_with_gemini(
    user_query: str,
    tool_name: str,
    answer_md: str,
    role_disp: str,
    loc_disp: str,
    checked_text: str,
    fallback_followups: list[str],
) -> tuple[str, list[str]]:
    """Synthesize final tool response using Gemini, guaranteeing dynamic, contextual followups."""
    keys = get_configured_gemini_keys()
    if not keys or os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
        final_answer = (
            "### What I Understood\n"
            f"You are searching for active job requisitions matching **{role_disp}** in **{loc_disp}**.\n\n"
            "### What I Checked\n"
            f"{checked_text}\n\n"
            f"### Results\n{answer_md}\n\n"
            "### Next Steps\n" + "\n".join([f"- {f}" for f in fallback_followups])
        )
        return final_answer, fallback_followups

    prompt = (
        "You are TalentScope's Career Intelligence AI assistant. System Date: October 29, 2026.\n"
        f"The user asked: \"{user_query}\"\n"
        f"The verified intelligence tool `{tool_name}` produced the following results:\n\n"
        f"{answer_md}\n\n"
        "Please format the complete final response following this exact structure:\n"
        "### What I Understood\n"
        f"You are searching for active job requisitions matching **{role_disp}** in **{loc_disp}**.\n\n"
        "### What I Checked\n"
        f"{checked_text}\n\n"
        "### Results\n"
        "(Include the verified results above exactly as provided, preserving all real URLs, employer names, and source notices)\n\n"
        "### Next Steps\n"
        "(Generate exactly 2 to 3 bulleted questions. These questions must be highly contextual, dynamically based on the exact data or answer you just provided, and designed to help the user explore the current specific topic further. Never use generic fallback questions.)"
    )

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    json_data = execute_gemini_request_with_fallback(payload)
    if json_data:
        candidates = json_data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [p.get("text") for p in parts if "text" in p and p.get("text")]
            if texts:
                text_resp = "\n\n".join(texts).strip()
                bullets = extract_next_steps_bullets(text_resp)
                if len(bullets) < 2:
                    bullets = fallback_followups
                if "### Next Steps" not in text_resp:
                    text_resp += "\n\n### Next Steps\n" + "\n".join([f"- {b}" for b in bullets])
                return text_resp, bullets

    final_answer = (
        "### What I Understood\n"
        f"You are searching for active job requisitions matching **{role_disp}** in **{loc_disp}**.\n\n"
        "### What I Checked\n"
        f"{checked_text}\n\n"
        f"### Results\n{answer_md}\n\n"
        "### Next Steps\n" + "\n".join([f"- {f}" for f in fallback_followups])
    )
    return final_answer, fallback_followups


# ---------------------------------------------------------------------------
# GEMINI FUNCTION CALLING (OPTIONAL CLOUD INTEGRATION WITH SAFE FALLBACK)
# ---------------------------------------------------------------------------

GEMINI_NATIVE_FUNCTION_DECLARATIONS = [
    {
        "name": "fetch_live_job_openings",
        "description": "Retrieve active job openings matching a specific role, skill, and location across live enterprise ATS feeds and database catalog.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "role_name": {"type": "STRING", "description": "Role or technology name (e.g. Python, Data Scientist, React)"},
                "location": {"type": "STRING", "description": "Target city or country (e.g. India, Remote)"},
                "work_mode": {"type": "STRING", "description": "Work mode filter (e.g. Remote, Hybrid, Onsite)"},
                "employment_type": {"type": "STRING", "description": "e.g. Full-time, Part-time, Contract"},
                "experience_level": {"type": "STRING", "description": "e.g. Fresher, Senior, Entry level"}
            },
            "required": ["role_name"]
        }
    },
    {
        "name": "analyze_historical_job_demand",
        "description": "Query historical enterprise hiring demand volume, trajectory, and top employers for a role or skill.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "role_name": {"type": "STRING", "description": "Standard role or technology name (e.g. AI Engineer, Python, UI/UX)"},
                "location": {"type": "STRING", "description": "Target geography, defaults to India"}
            },
            "required": ["role_name"]
        }
    },
    {
        "name": "analyze_market_ecosystem",
        "description": "Track developer community adoption and traction across Wikipedia, GitHub, and Stack Overflow for a technology or skill.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "technology": {"type": "STRING", "description": "Tracked technology or skill (e.g. Python, Docker, Figma)"}
            },
            "required": ["technology"]
        }
    },
    {
        "name": "run_skill_gap_analysis",
        "description": "Evaluate personal skill readiness and gaps for a target role. STRICTLY trigger ONLY when user explicitly asks about their profile, readiness, or missing skills.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_role": {"type": "STRING", "description": "Target job role title"},
                "user_profile": {"type": "OBJECT", "description": "User profile with user_skills"}
            },
            "required": ["target_role"]
        }
    }
]


def try_gemini_function_calling(
    messages: list[ChatMessage],
    user_context: UserContext,
    resolved: dict[str, Any],
) -> SupervisorResponse | None:
    """Attempt native Gemini function calling if GEMINI_API_KEY is configured."""
    keys = get_configured_gemini_keys()
    if not keys:
        return None

    # In strict offline test mode, do not invoke unmocked external Gemini cloud endpoints
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
        return None

    latest_prompt = resolved.get("latest_prompt", "Help me assess my career readiness.")
    intents = classify_intent(latest_prompt)
    if "CONCEPT_COMPARISON" in intents:
        return None

    try:
        if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
            return None
        import httpx

        # Prepare messages into standard Gemini contents format
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        system_instruction = {
            "parts": [{
                "text": (
                    "You are TalentScope's Career Intelligence AI assistant. System Date: October 29, 2026. "
                    "You have access to native tools for fetching live jobs, analyzing hiring demand, assessing skill gaps, and tracking developer ecosystem signals. "
                    "When answering conceptual or general questions, respond conversationally in clean markdown. "
                    "At the very end of every response, you MUST generate a '### Next Steps' section containing exactly 2 to 3 bulleted questions. "
                    "These questions must be highly contextual, dynamically based on the exact data or answer you just provided, and designed to help the user explore the current specific topic further. Never use generic fallback questions."
                )
            }]
        }

        payload = {
            "system_instruction": system_instruction,
            "contents": contents,
            "tools": [{"function_declarations": GEMINI_NATIVE_FUNCTION_DECLARATIONS}],
            "tool_config": {"function_calling_config": {"mode": "AUTO"}}
        }

        data = execute_gemini_request_with_fallback(payload)
        if not data:
            return None

        candidates = data.get("candidates", [])
        if not candidates:
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        function_calls = [p.get("functionCall") for p in parts if "functionCall" in p]

        # Case A: Gemini decided to call a native tool
        if function_calls:
            fc = function_calls[0]
            func_name = fc.get("name")
            args = fc.get("args") or {}
            logger.info("Gemini Native Function Call: %s with args: %s", func_name, args)

            tools_invoked: list[str] = []
            evidence_payloads: list[dict[str, Any]] = []
            role_disp = resolved.get("target_role", "Target Role")
            loc_disp = resolved.get("location", "India")
            answer_md = ""
            mapped_intent = "CAREER_INTELLIGENCE"
            has_empty_jobs = False

            if func_name == "fetch_live_job_openings":
                role_arg = args.get("role_name") or resolved.get("target_role") or "Software Engineer"
                loc_arg = args.get("location") or resolved.get("location") or "India"
                wm_arg = args.get("work_mode")
                emp_arg = args.get("employment_type")
                exp_arg = args.get("experience_level")
                inc_flts = list(resolved.get("include_filters") or [])
                if wm_arg and wm_arg.lower() not in inc_flts:
                    inc_flts.append(wm_arg.lower())
                jobs_data = fetch_live_job_openings(
                    role_name=role_arg,
                    location=loc_arg,
                    limit=5,
                    filter_context=resolved.get("filter_context"),
                    include_filters=inc_flts,
                    exclude_filters=resolved.get("exclude_filters"),
                    work_mode=wm_arg,
                    employment_type=emp_arg,
                    experience_level=exp_arg,
                )
                openings = jobs_data.get("openings", [])
                if not openings:
                    has_empty_jobs = True
                answer_md = synthesize_live_jobs_answer(jobs_data)
                tools_invoked.append("fetch_live_job_openings")
                evidence_payloads.append({"tool": "fetch_live_job_openings", "data": jobs_data})
                role_disp = role_arg
                loc_disp = loc_arg
                mapped_intent = "LIVE_JOBS"

            elif func_name == "analyze_historical_job_demand":
                role_arg = args.get("role_name") or resolved.get("target_role") or "AI Engineer"
                loc_arg = args.get("location") or resolved.get("location") or "India"
                demand_data = analyze_historical_job_demand(role_name=role_arg, location=loc_arg)
                answer_md = synthesize_historical_demand_answer(demand_data)
                tools_invoked.append("analyze_historical_job_demand")
                evidence_payloads.append({"tool": "analyze_historical_job_demand", "data": demand_data})
                role_disp = role_arg
                loc_disp = loc_arg
                mapped_intent = "HISTORICAL_DEMAND"

            elif func_name == "analyze_market_ecosystem":
                tech_arg = args.get("technology") or resolved.get("queried_skill") or resolved.get("target_role") or "Python"
                eco_data = analyze_market_ecosystem(skill_name=tech_arg)
                answer_md = synthesize_ecosystem_answer(eco_data)
                tools_invoked.append("analyze_market_ecosystem")
                evidence_payloads.append({"tool": "analyze_market_ecosystem", "data": eco_data})
                role_disp = tech_arg.title()
                mapped_intent = "ECOSYSTEM"

            elif func_name == "run_skill_gap_analysis":
                role_arg = args.get("target_role") or resolved.get("target_role") or "AI Engineer"
                profile_skills: list[str] = []
                if isinstance(args.get("user_profile"), dict):
                    profile_skills = args["user_profile"].get("user_skills", [])
                if not profile_skills:
                    profile_skills = resolved.get("user_skills") or user_context.user_skills
                gap_data = analyze_skill_gap(
                    target_role=role_arg,
                    user_skills=profile_skills,
                    location=user_context.location or "India",
                )
                answer_md = synthesize_skill_gap_answer(gap_data)
                tools_invoked.append("analyze_skill_gap")
                evidence_payloads.append({"tool": "analyze_skill_gap", "data": gap_data})
                role_disp = role_arg
                mapped_intent = "SKILL_GAP"

            followups = generate_suggested_followups([mapped_intent], resolved, has_empty_jobs=has_empty_jobs)

            if mapped_intent == "LIVE_JOBS":
                understood_text = f"You are searching for active job requisitions matching **{role_disp}** in **{loc_disp}**."
                provider = jobs_data.get("source_provider", "Local PostgreSQL Cache")
                if "ATS" in provider or "Live" in provider or jobs_data.get("live_api_status") == "live_ats":
                    checked_text = f"Queried real-time live enterprise ATS job boards (Greenhouse, Lever, Ashby) for '{role_disp}' in '{loc_disp}'."
                else:
                    from app.services.live_job_connectors import get_postgres_max_date
                    max_d = get_postgres_max_date()
                    checked_text = f"Falling back to local database (Data as of {max_d}) with dynamic universal filters."
            elif mapped_intent == "HISTORICAL_DEMAND":
                understood_text = f"You are examining enterprise hiring demand volume and growth trajectory for **{role_disp}** in **{loc_disp}**."
                checked_text = "Queried authentic enterprise hiring requisitions from PostgreSQL database catalog across India tech hubs."
            elif mapped_intent == "ECOSYSTEM":
                understood_text = f"You are tracking developer community adoption and ecosystem momentum for **{role_disp}**."
                checked_text = "Evaluated developer community activity across Wikipedia monthly views, GitHub repositories, and Stack Overflow inquiries."
            elif mapped_intent == "SKILL_GAP":
                understood_text = f"You want to assess role readiness and identify critical skill priorities for **{role_disp}**."
                checked_text = "Evaluated your profile skills against verified enterprise skill frequency distributions from PostgreSQL."
            else:
                understood_text = f"You are exploring market trends, hiring demand, and skill requirements for **{role_disp}**."
                checked_text = "Verified enterprise intelligence telemetry from PostgreSQL catalog."

            final_answer, final_followups = synthesize_tool_response_with_gemini(
                user_query=latest_prompt,
                tool_name=func_name,
                answer_md=answer_md,
                role_disp=role_disp,
                loc_disp=loc_disp,
                checked_text=checked_text,
                fallback_followups=followups,
            )

            return SupervisorResponse(
                answer=final_answer,
                tools_invoked=tools_invoked,
                evidence_payloads=evidence_payloads,
                suggested_followups=final_followups,
                provenance_summary="Gemini Native Function Calling backed by TalentScope Intelligence Tools",
                target_role=role_disp,
                intent=mapped_intent,
            )

        # Case B: Gemini returned pure conversational text (e.g. GENERAL_QA)
        text_parts = [p.get("text") for p in parts if "text" in p and p.get("text")]
        if text_parts:
            natural_text = "\n\n".join(text_parts).strip()
            role_disp = resolved.get("target_role", "AI Engineer")
            followups = extract_next_steps_bullets(natural_text)
            if len(followups) < 2:
                followups = generate_suggested_followups(["GENERAL_QA"], resolved)
                if "### Next Steps" not in natural_text:
                    natural_text += "\n\n### Next Steps\n" + "\n".join([f"- {f}" for f in followups])

            if "### What I Understood" in natural_text:
                formatted_answer = natural_text
            else:
                formatted_answer = (
                    "### What I Understood\n"
                    f"You asked: \"{latest_prompt}\".\n\n"
                    f"### Results\n{natural_text}"
                )
            return SupervisorResponse(
                answer=formatted_answer,
                tools_invoked=[],
                evidence_payloads=[],
                suggested_followups=followups,
                provenance_summary="General Knowledge Synthesis (Gemini AI Native Execution)",
                target_role=resolved.get("target_role", ""),
                intent="GENERAL_QA",
            )

        return None
    except Exception as exc:
        logger.info("Gemini function calling skipped/failed, executing deterministic supervisor fallback: %s", exc)
        return None


# ---------------------------------------------------------------------------
# MAIN SUPERVISOR ORCHESTRATION ENTRY POINTS
# ---------------------------------------------------------------------------

def execute_deterministic_supervisor(
    messages: list[ChatMessage],
    user_context: UserContext,
) -> SupervisorResponse:
    """Execute deterministic tool routing, evidence gathering, and response synthesis."""
    resolved = resolve_multi_turn_context(messages, user_context)
    latest_prompt = resolved["latest_prompt"]
    intents = classify_intent(latest_prompt)

    # 1. Handle GENERAL_QA and CONCEPT_COMPARISON: strictly bypass all tools and answer conceptually
    p_lower_prompt = latest_prompt.lower()
    is_comp_prompt = any(w in p_lower_prompt for w in [" vs ", " vs. ", " versus ", "difference between", "compare "]) or re.search(r"\bvs\b", p_lower_prompt) is not None
    if "GENERAL_QA" in intents or "CONCEPT_COMPARISON" in intents or is_comp_prompt:
        results_markdown = synthesize_general_qa_answer(latest_prompt, resolved)
        role_disp = resolved.get("target_role", "AI Engineer")

        # Specific Handling for CONCEPT_COMPARISON intent
        if "CONCEPT_COMPARISON" in intents or is_comp_prompt:
            ent_a, ent_b, comp_title = extract_comparison_entities(latest_prompt)
            suggested_qs = [f"What is an {ent_a}?", f"What does a {ent_b} do?"]
            followups = extract_next_steps_bullets(results_markdown) or suggested_qs

            if "### Connectivity Issue" in results_markdown:
                final_answer = results_markdown
            elif "### What I Understood" in results_markdown or "### Concept Comparison" in results_markdown:
                final_answer = results_markdown
            else:
                final_answer = (
                    "### What I Understood\n"
                    f"You asked for a concept comparison: \"{latest_prompt}\".\n\n"
                    f"### Results\n{results_markdown}"
                )

            return SupervisorResponse(
                answer=final_answer,
                tools_invoked=[],
                evidence_payloads=[],
                suggested_followups=followups,
                suggested_questions=suggested_qs,
                provenance_summary="Concept Comparison (Deterministic Fallback)",
                target_role=resolved.get("target_role", ent_a),
                intent="CONCEPT_COMPARISON",
            )

        followups = extract_next_steps_bullets(results_markdown)
        if len(followups) < 2:
            followups = generate_suggested_followups(["GENERAL_QA"], resolved)
            if "### Next Steps" not in results_markdown:
                results_markdown += "\n\n### Next Steps\n" + "\n".join([f"- {f}" for f in followups])

        understood_text = f"You asked for an educational explanation or conceptual overview: \"{latest_prompt}\"."

        if results_markdown.startswith("Error: Unable to connect"):
            final_answer = (
                f"### Connectivity Issue\n"
                f"We are currently unable to reach the AI service to generate a real-time response for **{latest_prompt}**. "
                "Please check your network connection, API key validity, or try again later."
            )
            followups = [
                "What career paths are available?",
                "Which skills should I develop first?",
            ]
        elif "### What I Understood" in results_markdown or "### Connectivity Issue" in results_markdown:
            final_answer = results_markdown
        else:
            final_answer = (
                "### What I Understood\n"
                f"{understood_text}\n\n"
                f"### Results\n{results_markdown}"
            )

        return SupervisorResponse(
            answer=final_answer,
            tools_invoked=[],
            evidence_payloads=[],
            suggested_followups=followups,
            suggested_questions=followups,
            provenance_summary="General Knowledge Synthesis (Zero external tools triggered)",
            target_role=resolved.get("target_role", ""),
            intent="GENERAL_QA",
        )

    tools_invoked: list[str] = []
    evidence_payloads: list[dict[str, Any]] = []
    answer_sections: list[str] = []

    # Order tools based on whether the primary question is market trends or personal skill readiness
    p_lower = latest_prompt.lower()
    is_market_primary = any(k in p_lower for k in [
        "trending", "trend", "trends", "top skill", "top skills", "top tech", "popular", "growth", "market", "landscape"
    ])

    if is_market_primary:
        execution_order = [i for i in ["ECOSYSTEM", "HISTORICAL_DEMAND", "SKILL_GAP", "LIVE_JOBS"] if i in intents]
    else:
        execution_order = [i for i in ["SKILL_GAP", "LIVE_JOBS", "HISTORICAL_DEMAND", "ECOSYSTEM"] if i in intents]

    for intent in execution_order:
        if intent == "SKILL_GAP":
            gap_data = analyze_skill_gap(
                target_role=resolved["target_role"],
                user_skills=resolved["user_skills"],
            )
            tools_invoked.append("analyze_skill_gap")
            evidence_payloads.append({"tool": "analyze_skill_gap", "data": gap_data})
            answer_sections.append(synthesize_skill_gap_answer(gap_data, resolved["user_skills"]))
        elif intent == "LIVE_JOBS":
            jobs_data = fetch_live_job_openings(
                role_name=resolved["target_role"],
                location=resolved["location"],
                limit=5,
                filter_context=resolved.get("filter_context"),
                include_filters=resolved.get("include_filters"),
                exclude_filters=resolved.get("exclude_filters"),
            )
            tools_invoked.append("fetch_live_job_openings")
            evidence_payloads.append({"tool": "fetch_live_job_openings", "data": jobs_data})
            answer_sections.append(synthesize_live_jobs_answer(jobs_data))
        elif intent == "HISTORICAL_DEMAND":
            demand_data = analyze_historical_job_demand(
                role_name=resolved["target_role"],
                location=resolved["location"],
            )
            tools_invoked.append("analyze_historical_job_demand")
            evidence_payloads.append({"tool": "analyze_historical_job_demand", "data": demand_data})
            answer_sections.append(synthesize_historical_demand_answer(demand_data))
        elif intent == "ECOSYSTEM":
            eco_data = analyze_market_ecosystem(skill_name=resolved.get("queried_skill"))
            tools_invoked.append("analyze_market_ecosystem")
            evidence_payloads.append({"tool": "analyze_market_ecosystem", "data": eco_data})
            answer_sections.append(synthesize_ecosystem_answer(eco_data))

    results_markdown = "\n\n---\n\n".join(answer_sections)

    has_empty_jobs = False
    for ev in evidence_payloads:
        if ev.get("tool") == "fetch_live_job_openings":
            openings = ev.get("data", {}).get("openings", [])
            if len(openings) == 0:
                has_empty_jobs = True
                break

    followups = generate_suggested_followups(intents, resolved, has_empty_jobs=has_empty_jobs)

    # Build plain English What I Understood
    role_disp = resolved.get("target_role", "Target Role")
    loc_disp = resolved.get("location", "India")
    if "LIVE_JOBS" in intents and len(intents) == 1:
        understood_text = f"You are searching for active job requisitions matching **{role_disp}** in **{loc_disp}**."
    elif "HISTORICAL_DEMAND" in intents and len(intents) == 1:
        understood_text = f"You are examining enterprise hiring demand volume and growth trajectory for **{role_disp}** in **{loc_disp}**."
    elif "ECOSYSTEM" in intents and len(intents) == 1:
        sk_q = resolved.get("queried_skill")
        understood_text = f"You are tracking developer community adoption and ecosystem momentum for **{sk_q.title()}**." if sk_q else "You are exploring macro developer community trends across tracked technologies."
    elif "SKILL_GAP" in intents and len(intents) == 1:
        understood_text = f"You want to assess role readiness and identify critical skill priorities for **{role_disp}**."
    else:
        understood_text = f"You are exploring market trends, hiring demand, and skill requirements for **{role_disp}**."

    # Build plain English What I Checked (NEVER output raw technical tool names)
    checked_sources: list[str] = []
    if "LIVE_JOBS" in intents:
        live_payload = next((ep.get("data") for ep in evidence_payloads if ep.get("tool") == "fetch_live_job_openings"), None)
        prov = (live_payload or {}).get("source_provider", "")
        st = (live_payload or {}).get("live_api_status", "")
        if "ATS" in prov or "Live" in prov or st in ("live_ats", "live_aggregator"):
            checked_sources.append(f"Queried real-time live enterprise ATS job boards and aggregators for '{role_disp}' in '{loc_disp}'")
        else:
            from app.services.live_job_connectors import get_postgres_max_date
            max_d = get_postgres_max_date()
            checked_sources.append(f"Falling back to local database (Data as of {max_d}) with dynamic universal filters")
    if "HISTORICAL_DEMAND" in intents:
        checked_sources.append("Queried authentic enterprise hiring requisitions from PostgreSQL database catalog across India tech hubs")
    if "ECOSYSTEM" in intents:
        checked_sources.append("Evaluated developer community activity across Wikipedia monthly views, GitHub repositories, and Stack Overflow inquiries")
    if "SKILL_GAP" in intents:
        checked_sources.append("Evaluated your profile skills against verified enterprise skill frequency distributions from PostgreSQL")

    checked_text = ". ".join(checked_sources) + "." if checked_sources else "Verified enterprise intelligence telemetry from PostgreSQL catalog."

    final_answer, final_followups = synthesize_tool_response_with_gemini(
        user_query=latest_prompt,
        tool_name=tools_invoked[0] if tools_invoked else "intelligence_catalog",
        answer_md=results_markdown,
        role_disp=role_disp,
        loc_disp=loc_disp,
        checked_text=checked_text,
        fallback_followups=followups,
    )

    return SupervisorResponse(
        answer=final_answer,
        tools_invoked=tools_invoked,
        evidence_payloads=evidence_payloads,
        suggested_followups=final_followups,
        provenance_summary="PostgreSQL Verified Enterprise Catalog & external_skill_signals",
        target_role=resolved.get("target_role", ""),
        intent=intents[0] if intents else "CAREER_INTELLIGENCE",
    )


def run_supervisor_turn(
    messages: list[ChatMessage],
    user_context: UserContext | None = None,
) -> SupervisorResponse:
    """Synchronous entry point to execute a supervisor turn deterministically."""
    ctx = user_context or UserContext()
    return execute_deterministic_supervisor(messages, ctx)


async def run_supervisor_agent(
    messages: list[ChatMessage],
    user_context: UserContext,
) -> SupervisorResponse:
    """Run Supervisor Agent, attempting Gemini Function Calling with seamless deterministic fallback."""
    resolved = resolve_multi_turn_context(messages, user_context)

    # 1. Try Gemini Function Calling if API key is present and environment allows
    gemini_resp = try_gemini_function_calling(messages, user_context, resolved)
    if gemini_resp is not None:
        return gemini_resp

    # 2. Seamlessly execute deterministic intent routing and tool synthesis
    return execute_deterministic_supervisor(messages, user_context)


async def stream_supervisor_agent(
    messages: list[ChatMessage],
    user_context: UserContext,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream Supervisor Agent execution events for Server-Sent Events (SSE).

    Yields structured event dictionaries:
    - {'event': 'tool_call', 'data': {'tool': ...}}
    - {'event': 'evidence', 'data': {'tool': ..., 'payload': ...}}
    - {'event': 'token', 'data': {'token': ...}}
    - {'event': 'done', 'data': {...}}
    """
    resolved = resolve_multi_turn_context(messages, user_context)
    latest_prompt = resolved["latest_prompt"]
    intents = classify_intent(latest_prompt)

    tools_to_run: list[str] = []
    if "SKILL_GAP" in intents:
        tools_to_run.append("analyze_skill_gap")
    if "LIVE_JOBS" in intents:
        tools_to_run.append("fetch_live_job_openings")
    if "HISTORICAL_DEMAND" in intents:
        tools_to_run.append("analyze_historical_job_demand")
    if "ECOSYSTEM" in intents:
        tools_to_run.append("analyze_market_ecosystem")

    # Notify tool calls
    for tool_name in tools_to_run:
        yield {"event": "tool_call", "data": {"tool": tool_name}}

    # Execute tools and yield evidence
    supervisor_resp = execute_deterministic_supervisor(messages, user_context)
    for ev in supervisor_resp.evidence_payloads:
        yield {"event": "evidence", "data": ev}

    # Stream answer tokens in readable chunks
    answer = supervisor_resp.answer
    words = answer.split(" ")
    chunk_size = 6
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size]) + " "
        yield {"event": "token", "data": {"token": chunk}}
        await asyncio.sleep(0.01)

    # Yield done event
    yield {
        "event": "done",
        "data": {
            "answer": supervisor_resp.answer,
            "tools_invoked": supervisor_resp.tools_invoked,
            "suggested_followups": supervisor_resp.suggested_followups,
            "provenance_summary": supervisor_resp.provenance_summary,
        },
    }

