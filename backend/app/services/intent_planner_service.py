"""Intent Resolver + Context Planner Service for G2.6.

Transforms natural language user messages into a structured, auditable plan.
Enforces the mandatory pipeline:
User Message -> Intent Classification -> Entity Resolution -> Context Requirements
-> Capability Selection -> Capability Readiness Evaluation -> Structured Plan

Strictly preserves:
- G0-G2.6 contracts
- Zero Firestore read/write operations
- Zero external network requests
- Zero synthetic observation or forecast generation
- Full reuse of Entity Registry, Capability Registry, and Analytical Readiness gates
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import SKILLS, _ALIASES, canonical_skill_id
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import (
    CapabilityEvaluationRequest,
    CapabilityEvaluationResult,
    CapabilityRecord,
)
from app.models.entity_registry import (
    CanonicalEntity,
    EntityCandidate,
    EntityResolutionRequest,
)
from app.models.intent_planner import (
    ContextFieldItem,
    ContextSource,
    IntelligencePlanRequest,
    IntelligencePlanResponse,
    IntentCategory,
    PlanStatus,
    ResolvedEntityItem,
)
from app.services.capability_registry_service import (
    CAPABILITY_DOMAINS,
    CAPABILITY_CATALOG,
    CapabilityRegistryService,
)
from app.services.entity_registry_service import EntityRegistryService
from app.storage.conversation_store import ConversationStore


# =============================================================================
# INTENT REGEX PATTERNS (DETERMINISTIC CLASSIFICATION)
# =============================================================================

# 1. Forecasting & future projections
FORECAST_PATTERNS = [
    re.compile(r"\b(will|shall)\b.*\b(grow|increase|rise|decline|drop|demand|change|trend)\b.*\b(next year|in future|in \d{4}|future)\b", re.IGNORECASE),
    re.compile(r"\b(forecasts?|predict(?:ion)?s?|projections?|future demand|future outlook)\b", re.IGNORECASE),
    re.compile(r"\b(?:what|how|where)\s+might\s+.*(?:demand|hiring|market)\s+(?:look\s+like|be)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+reliable\s+is\s+(?:this|the)\s+forecast\b", re.IGNORECASE),
    re.compile(r"\bnext\s+(?:one|two|three|four|five|six|12|24|\d+)\s+months?\b.*\b(?:demand|forecast|trajectory)\b", re.IGNORECASE),
    re.compile(r"\bdemand\b.*\bnext\s+(?:one|two|three|four|five|six|12|24|\d+)\s+months?\b", re.IGNORECASE),
]

# 2. Workforce what-if simulation (planned for future enterprise)
SIMULATION_PATTERNS = [
    re.compile(r"\b(what-if|what if|simulate|simulation|attrition shock|reskilling scenario|headcount scenario)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:affect|impact|implications?)\b.*\b(?:our workforce|workforce|team|employees)\b",
        re.IGNORECASE,
    ),
]

# 3. Entity comparison
COMPARISON_PATTERNS = [
    re.compile(r"\bcompare\b.*?\bacross\s+([A-Za-z0-9\.\+#\s]+?)\s+(?:and|with|to|vs|versus)\s+([A-Za-z0-9\.\+#\s]+)", re.IGNORECASE),
    re.compile(r"\bcompare\b\s+([A-Za-z0-9\.\+#]+)\s+(?:and|with|to|vs|versus)\s+([A-Za-z0-9\.\+#]+)", re.IGNORECASE),
    re.compile(r"\b([A-Za-z0-9\.\+#]+)\s+(?:vs|versus)\s+([A-Za-z0-9\.\+#]+)\b", re.IGNORECASE),
    re.compile(r"\bdifference between\s+([A-Za-z0-9\.\+#]+)\s+and\s+([A-Za-z0-9\.\+#]+)", re.IGNORECASE),
    re.compile(r"\bcompare\b", re.IGNORECASE),
]

# 4. Job postings search
JOB_SEARCH_PATTERNS = [
    re.compile(r"\b(find|search|show|get|list|see)\b.*\b(jobs|postings|openings|vacancies|positions)\b", re.IGNORECASE),
    re.compile(r"\bjob (search|postings|market)\b", re.IGNORECASE),
    re.compile(r"\bhiring (for|demand)\b", re.IGNORECASE),
]

# 5. Occupation software tools / skills crosswalk
OCC_SOFTWARE_PATTERNS = [
    re.compile(r"\b(what|which)\s+(?:skills|tools|software|technologies)(?:\s+(?:skills|tools|software|technologies))?\s+(?:does|do|for|needed for)\s+(?:a|an)?\s*(.*?)\s*(?:need|use|require)\b", re.IGNORECASE),
    re.compile(r"\b(?:skills|software|tools)(?:\s+(?:skills|software|tools))?\s+(?:for|required for|needed by)\s+(?:a|an)?\s*(.*?)\b", re.IGNORECASE),
    re.compile(r"\b([a-zA-Z\s]+?)\s+(?:tools|software tools|tech stack)\b", re.IGNORECASE),
    re.compile(r"\btech stack for\b", re.IGNORECASE),
]

# 6. Related occupations / career mobility
OCC_RELATED_PATTERNS = [
    re.compile(r"\b(related|similar|alternative|next|adjacent)\s+(?:occupations|roles|jobs|careers)\b", re.IGNORECASE),
    re.compile(r"\bcareer (path|pathway|progression|mobility) (?:for|from)\b", re.IGNORECASE),
    re.compile(r"\btransitions? from\b", re.IGNORECASE),
]

# 6b. Role-specific learning guidance
SKILL_LEARNING_PATTERNS = [
    re.compile(r"\b(?:which|what)\s+skills?\s+(?:should|could|can)\s+i\s+(?:learn|develop|focus on)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+skill\s+should\s+i\s+learn\s+next\b", re.IGNORECASE),
    re.compile(r"\b(?:learning|study)\s+roadmap\b", re.IGNORECASE),
    re.compile(r"\broadmap\b.*\b(?:learn|study|skill)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+can\s+i\s+(?:improve|strengthen|develop)\b.*\bskills?\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+skills?\s+should\s+i\s+prioriti[sz]e\b", re.IGNORECASE),
    re.compile(r"\bprioriti[sz]e\b.*\bskills?\b", re.IGNORECASE),
    re.compile(r"\bcreate\b.*\blearning\s+roadmap\b", re.IGNORECASE),
    re.compile(r"\broadmap\b.*\bbased\s+on\s+my\s+current\s+skills\b", re.IGNORECASE),
]

# 7. Occupation lookup
OCC_LOOKUP_PATTERNS = [
    re.compile(r"\b(?:what is|tell me about|describe|lookup)\s+(?:the role of|the occupation of|the job of)\b", re.IGNORECASE),
    re.compile(r"\b(?:what is|tell me about|describe|lookup)\s+(?:the role of|the occupation of|the job of)?\s*([a-zA-Z\s]+(?:developer|engineer|analyst|manager|scientist|architect|designer)s?)\b", re.IGNORECASE),
    re.compile(r"\b\d{2}-\d{4}\.\d{2}\b"),
    re.compile(r"\b(soc code|occupation code)\b", re.IGNORECASE),
]

# 8. Evidence & provenance
EVIDENCE_PATTERNS = [
    re.compile(r"\b(evidence|provenance|source|sources|citation|citations|audit trail|where did this come from|sources used)\b", re.IGNORECASE),
    re.compile(r"\b(is this (?:data )?real|real or estimated|real or fake|is it real|how was this calculated|methodology)\b", re.IGNORECASE),
    re.compile(r"\b(what are the limitations|limitations?|analytical limitations?)\b", re.IGNORECASE),
    re.compile(r"\bwhy\s+(?:are|did)\s+you\s+recommend(?:ing)?\b", re.IGNORECASE),
]

# 9. Skill gap & role alignment
SKILL_GAP_PATTERNS = [
    re.compile(r"\b(skill gaps?|role fits?|am i ready for|gap analysis|missing skills?|skills? needed)\b", re.IGNORECASE),
    re.compile(r"\b(what does this (?:result )?mean for (?:my |our )?career|career impact|career relevance|relevance to my career)\b", re.IGNORECASE),
]

# 10. Action recommendations
ACTION_PATTERNS = [
    re.compile(r"\b(what should i (?:learn|do)|recommendations?|recommended|action plans?|learning actions?|next steps|roadmap|what to learn|career growth actions?)\b", re.IGNORECASE),
    re.compile(r"\b(recommend|recommendation|recommended)\b.*\b(actions?|steps?|learning|growth)\b", re.IGNORECASE),
]

# 11. Company workforce
COMPANY_PATTERNS = [
    re.compile(r"\b(company workforce|our workforce|team skills|department skills|workforce inventory)\b", re.IGNORECASE),
    re.compile(r"\b(?:our\s+company(?:'s)?|the\s+company(?:'s)?|my\s+company(?:'s)?)\s+(?:current\s+)?skill coverage\b", re.IGNORECASE),
    re.compile(r"\bskills?\s+(?:are\s+)?(?:missing\s+from|missing\s+(?:across|in)|represented\s+(?:across|in))\s+(?:our|the)\s+workforce\b", re.IGNORECASE),
    re.compile(r"\b(?:summari[sz]e|show|list)\b.*\bskills?\b.*\b(?:our|the)\s+employees\b", re.IGNORECASE),
    re.compile(r"\bworkforce skills?\b.*\b(?:investigat\w*|review|coverage)\b", re.IGNORECASE),
]

# 11b. Skill Health relative momentum & score
HEALTH_PATTERNS = [
    re.compile(r"\b(?:skill\s+)?health\b", re.IGNORECASE),
    re.compile(r"\bhealth\s+(?:score|category|status|metric)\b", re.IGNORECASE),
    re.compile(r"\brelative\s+momentum\b", re.IGNORECASE),
]

# 11c. Skill Half-Life decay rate & estimate
HALF_LIFE_PATTERNS = [
    re.compile(r"\b(?:skill\s+)?half[- ]life\b", re.IGNORECASE),
    re.compile(r"\bdecay\s+rate\b", re.IGNORECASE),
    re.compile(r"\bexponential\s+decay\b", re.IGNORECASE),
]

# 11d. AI Task Exposure and Disruption
AI_TASK_EXPOSURE_PATTERNS = [
    re.compile(r"\b(?:ai\s+)?task\s+exposure\b", re.IGNORECASE),
    re.compile(r"\bexposure\s+to\s+ai\b", re.IGNORECASE),
    re.compile(r"\btasks?\s+in\s+.*?\s+(?:are|is)?\s*exposed\s+to\s+ai\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+tasks\b.*\b(?:exposed|affected|automated|augmented)\b", re.IGNORECASE),
    re.compile(r"\btask[- ]level\s+(?:exposure|disruption|overlap)\b", re.IGNORECASE),
    re.compile(r"\b(?:ai\s+)?disruption\s+(?:intelligence|analysis|evaluation)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+skills\s+are\s+associated\s+with\s+the\s+(?:affected|exposed)\s+tasks\b", re.IGNORECASE),
    re.compile(r"\bassociated\s+skills?\s+for\s+(?:affected|exposed)\s+tasks\b", re.IGNORECASE),
    re.compile(r"\baugmentation\s+vs(?:\.|\s+)?\s*automation\b", re.IGNORECASE),
    re.compile(r"\bautomation\s+potential\b", re.IGNORECASE),
]

# 12. Trend & velocity
TREND_PATTERNS = [
    re.compile(r"\b(trend|velocity|growing|increasing|declining|decreasing|rising|falling|momentum|market direction|growth rate)\b", re.IGNORECASE),
    re.compile(r"\bis\s+([A-Za-z0-9\.\+#]+)\s+(?:growing|popular|in demand|rising|declining|increasing|decreasing|changing)\b", re.IGNORECASE),
    re.compile(r"\bis\s+([A-Za-z0-9\.\+#]+)\s+(?:increasing\s+or\s+decreasing|growing\s+or\s+declining|rising\s+or\s+falling)\b", re.IGNORECASE),
    re.compile(r"\b(?:demand\s+changing|changing\s+demand|demand\s+shifts?|shifts?\s+in\s+demand|demand\s+movement)\b", re.IGNORECASE),
    re.compile(r"\bwhy\s+(?:is\s+)?.*\b(?:demand\s+changing|changing|moving|shifting)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(?:demand\s+)?trend\b", re.IGNORECASE),
]

ALL_SKILL_TREND_PATTERNS = [
    re.compile(
        r"\b(?:what|which|show|list|rank|compare|identify|find)\b.*\bskills?\b.*"
        r"\b(?:trending|trend(?:s)?|gaining demand|increasing demand|declining|decreasing|rising|falling)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:top|strongest|most)\b.*\b(?:trending|trend(?:s)?|gaining demand|declining|rising)\b.*\bskills?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:currently\s+)?trending\s+skills?\b|\bskills?\s+(?:are\s+)?trending\b", re.IGNORECASE),
]

# 13. Historical observations
HISTORY_PATTERNS = [
    re.compile(r"\b(history|historical|over time|past (?:months|quarters|years)|time series)\b", re.IGNORECASE),
]

# 14. Market snapshot
SNAPSHOT_PATTERNS = [
    re.compile(r"\b(market snapshot|current demand|posting count|market share|current postings)\b", re.IGNORECASE),
]

# 15. Concept explanation / lookup
CONCEPT_PATTERNS = [
    re.compile(r"\b(?:what is|explain|tell me about|overview of|definition of)\s+(?:a\s+|an\s+|the\s+)?([A-Za-z0-9\.\+#]+)\s*[?.!]*$", re.IGNORECASE),
    re.compile(r"\b(explain (?:that|this|it)?\s*(?:in simpler words|more simply|simply|for a beginner)?)\b", re.IGNORECASE),
    re.compile(r"\b(simpler words|in simple terms|eli5|summarize (?:our discussion|this|the conversation|the discussion)|summarize our discussion)\b", re.IGNORECASE),
    re.compile(r"\b(copy (?:the )?(?:previous |last )?answer|copy answer)\b", re.IGNORECASE),
]

# 16. Explicit entity resolution
RESOLVE_PATTERNS = [
    re.compile(r"\b(?:resolve|canonical name of|canonical id of)\s+([A-Za-z0-9\.\+#]+)\b", re.IGNORECASE),
]


class IntentPlannerService:
    """Deterministic Intent Resolver and Context Planner."""

    def __init__(
        self,
        *,
        entity_service: EntityRegistryService | None = None,
        capability_service: CapabilityRegistryService | None = None,
    ) -> None:
        self._entity_service = entity_service or EntityRegistryService()
        self._capability_service = capability_service or CapabilityRegistryService(
            entity_service=self._entity_service
        )

    # -------------------------------------------------------------------------
    # MAIN PLANNING ENTRY POINT
    # -------------------------------------------------------------------------

    def create_plan(
        self,
        request: IntelligencePlanRequest,
        *,
        authenticated_user: AuthenticatedUser | None = None,
    ) -> IntelligencePlanResponse:
        """Create a structured execution plan for a user request without executing operations."""
        request_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        message = request.message.strip()

        # 1. Resolve portal context
        effective_portal = request.portal_type
        if not effective_portal and authenticated_user:
            effective_portal = getattr(authenticated_user, "user_type", None)
        if not effective_portal:
            effective_portal = "individual"

        # Check multi-turn conversation context and follow-up resolution
        effective_message = message
        res_primary = None
        conv_comps: list[str] = []
        conv_role: str | None = None
        user_id = authenticated_user.uid if authenticated_user else "anonymous"
        company_id = request.company_id or (getattr(authenticated_user, "company_id", None) if authenticated_user else None)

        if request.conversation_id:
            conv_store = ConversationStore.get_instance()
            if request.clear_context:
                try:
                    conv_store.clear_conversation(request.conversation_id, user_id=user_id)
                except Exception:
                    pass
            else:
                res_primary, conv_comps, conv_role, rew_msg = conv_store.resolve_follow_up(
                    message,
                    request.conversation_id,
                    user_id=user_id,
                    company_id=company_id,
                )
                if rew_msg:
                    effective_message = rew_msg
                if conv_role and not request.target_role:
                    request = request.model_copy(update={
                        "target_role": conv_role,
                        "selected_roles": request.selected_roles or [conv_role],
                    })

        # 2. Extract and resolve entities mentioned in the query
        resolved_entities = self._extract_and_resolve_entities(effective_message, request)

        # If conversation context resolved a primary entity for follow-up
        if res_primary:
            query_has_explicit_occ = any(
                e.canonical_entity and e.canonical_entity.entity_type == "occupation" and e.raw_token.lower() in message.lower()
                for e in resolved_entities
            )
            if not query_has_explicit_occ:
                res_ent_resp = self._entity_service.resolve(EntityResolutionRequest(name=res_primary))
                if res_ent_resp.status == "resolved" and res_ent_resp.entity:
                    primary_item = ResolvedEntityItem(
                        raw_token=res_primary,
                        resolution_status="resolved",
                        canonical_entity=res_ent_resp.entity,
                        candidates=[],
                        is_primary=True,
                        match_reason="conversation_context",
                    )
                    for e in resolved_entities:
                        e.is_primary = False
                    resolved_entities.insert(0, primary_item)

        # 3. Classify user intent or validate an explicit focused capability.
        forced_capability_issue: str | None = None
        if request.capability_id:
            capability = CAPABILITY_CATALOG[request.capability_id]
            supported_domains = CAPABILITY_DOMAINS[request.capability_id]
            if request.domain not in supported_domains:
                forced_capability_issue = (
                    f"{capability.name} is not supported in the "
                    f"{request.domain or 'selected'} domain."
                )
                intent, confidence, explanation, selected_caps, is_comparison = (
                    "unsupported_or_unclear", 1.0, forced_capability_issue, [], False
                )
            elif capability.global_status not in {"available", "partial"} or not capability.handler:
                forced_capability_issue = (
                    f"{capability.name} is not currently executable: "
                    f"{'; '.join(capability.limitations)}"
                )
                intent, confidence, explanation, selected_caps, is_comparison = (
                    "unsupported_or_unclear", 1.0, forced_capability_issue, [], False
                )
            else:
                intent, confidence, explanation, selected_caps, is_comparison = (
                    capability.supported_intent,
                    1.0,
                    f"Explicitly selected capability: {capability.name}.",
                    [request.capability_id],
                    False,
                )
        else:
            intent, confidence, explanation, selected_caps, is_comparison = self._classify_intent(
                effective_message, resolved_entities
            )
        # The selected workspace domain is part of routing for terse prompts
        # (for example a user entering only a canonical skill name). Explicit
        # request patterns above remain authoritative.
        if request.capability_id is None and request.domain == "job" and intent == "lookup_skill_reference":
            intent, confidence, explanation, selected_caps = (
                "search_jobs", 0.78,
                "The active Job Intelligence domain routes this resolved entity to stored job postings.",
                ["job_posting_search"],
            )
        elif request.capability_id is None and request.domain == "market" and intent == "lookup_skill_reference":
            intent, confidence, explanation, selected_caps = (
                "retrieve_snapshot", 0.78,
                "The active Market Intelligence domain routes this resolved entity to observed market signals.",
                ["market_snapshot"],
            )

        # 4. Derive context fields and detect missing context
        context_summary, missing_context, clarification_questions = self._build_context(
            request,
            authenticated_user,
            effective_portal,
            resolved_entities,
            selected_caps,
            is_comparison,
        )

        # 5. Evaluate runtime readiness of selected capabilities
        readiness_results, plan_limitations = self._evaluate_selected_capabilities(
            selected_caps,
            resolved_entities,
            request,
            effective_portal,
            context_summary,
        )
        if forced_capability_issue:
            plan_limitations.append(forced_capability_issue)

        # 6. Determine overall plan status and clarification requirements
        clarification_required = len(clarification_questions) > 0
        plan_status = self._determine_plan_status(
            intent,
            selected_caps,
            clarification_required,
            readiness_results,
            resolved_entities,
        )
        if forced_capability_issue:
            plan_status = "unsupported"

        # Build auditable structured response
        return IntelligencePlanResponse(
            request_id=request_id,
            user_message=message,
            portal_type=effective_portal,
            intent=intent,
            intent_confidence=confidence,
            intent_explanation=explanation,
            conversation_id=request.conversation_id,
            entities=resolved_entities,
            selected_capabilities=selected_caps,
            context_summary=context_summary,
            missing_context=missing_context,
            clarification_required=clarification_required,
            clarification_questions=clarification_questions,
            readiness_results=readiness_results,
            limitations=sorted(set(plan_limitations)),
            plan_status=plan_status,
            evaluated_at=now,
        )

    # -------------------------------------------------------------------------
    # ENTITY EXTRACTION & RESOLUTION
    # -------------------------------------------------------------------------

    def _extract_and_resolve_entities(
        self,
        message: str,
        request: IntelligencePlanRequest,
    ) -> list[ResolvedEntityItem]:
        """Extract entity mentions from the message and resolve them via EntityRegistryService."""
        tokens_to_resolve: list[tuple[str, bool]] = []  # (token, is_primary)

        # Check comparison pattern for explicit entity pair
        for pat in COMPARISON_PATTERNS:
            m = pat.search(message)
            if m and m.lastindex and m.lastindex >= 2:
                tokens_to_resolve.append((m.group(1).strip(), True))
                tokens_to_resolve.append((m.group(2).strip(), False))
                break

        # Check explicit SOC code pattern
        soc_match = re.search(r"\b\d{2}-\d{4}\.\d{2}\b", message)
        if soc_match:
            tokens_to_resolve.append((soc_match.group(0), True))

        # Check occupation patterns for explicit role mentions from query message
        for pat in [
            re.compile(r"\btasks?\s+in\s+([a-zA-Z\s]+?)(?:\s+(?:are|is)?\s*exposed|\s+exposed|\s+affected|\s+to ai|\s+by ai|\s*$)", re.IGNORECASE),
            re.compile(r"\b(?:skills|tools|software|technologies|tech stack)\s+(?:does|do|for|needed for)\s+(?:a|an)?\s*(.*?)\s*(?:need|use|require)\b", re.IGNORECASE),
            re.compile(r"\b(?:skills|tools|software|technologies|tech stack)\s+(?:for|required for|needed by)\s+(?:a|an)?\s*(.*?)$", re.IGNORECASE),
            re.compile(r"^(.*?)\s+(?:tools|software tools|tech stack|technologies)\b", re.IGNORECASE),
            re.compile(r"\b(?:related|similar|alternative|next|adjacent)\s+(?:occupations|roles|jobs|careers)\s+(?:for|to|from)?\s*(?:a|an)?\s*(.*?)$", re.IGNORECASE),
            re.compile(r"\b(?:role of|occupation of|job of)\s+(?:a|an)?\s*(.*?)$", re.IGNORECASE),
        ]:
            m = pat.search(message)
            if m:
                extracted = m.group(1).strip(" \t\n\r?.!,;:")
                if extracted and len(extracted) >= 3:
                    tokens_to_resolve.append((extracted, not tokens_to_resolve))
                    break

        # Check concept patterns (e.g. "What is XYZ")
        for pat in CONCEPT_PATTERNS:
            m = pat.search(message)
            if m:
                extracted = m.group(1).strip(" \t\n\r?.!,;:")
                if (
                    extracted
                    and len(extracted) >= 2
                    and extracted.lower() not in {"the", "a", "an", "this", "that", "our", "my", "trend", "history", "jobs", "role"}
                ):
                    tokens_to_resolve.append((extracted, not tokens_to_resolve))
        # Check trend / about patterns: e.g. "trend about uiux", "trend for python", "trends in machine learning"
        for pat in [
            re.compile(r"\b(?:trend|trends|trending|growth|adoption)\s+(?:about|for|in|of|on)\s+(.*?)(?:\s+(?:trend|trends|history|data|in|for|over))?$", re.IGNORECASE),
            re.compile(r"\b(?:tell me about|info on|details for|about)\s+(.*?)$", re.IGNORECASE),
        ]:
            m = pat.search(message)
            if m:
                extracted = m.group(1).strip(" \t\n\r?.!,;:")
                if (
                    extracted
                    and len(extracted) >= 2
                    and extracted.lower() not in {"the", "a", "an", "this", "that", "our", "my", "all", "trend", "history"}
                ):
                    tokens_to_resolve.append((extracted, not tokens_to_resolve))
                    break

        # Scan message for registered canonical skills and aliases
        # Sort registered skill names by length descending to match multi-word skills first
        known_terms = sorted(
            set(_ALIASES.keys()),
            key=lambda t: len(t),
            reverse=True,
        )

        msg_lower = f" {message.lower()} "
        found_spans: list[tuple[int, int]] = []

        for term in known_terms:
            if len(term) < 2 and term != "c" and term != "r":
                continue
            # Word boundary matching
            pat = r"(?<![a-zA-Z0-9\+#])" + re.escape(term) + r"(?![a-zA-Z0-9\+#])"
            for match in re.finditer(pat, msg_lower):
                span = match.span()
                # Check for overlap with already found terms
                if not any(s[0] <= span[0] and span[1] <= s[1] for s in found_spans):
                    found_spans.append(span)
                    raw_token = message[match.start() - 1 : match.end() - 1].strip()
                    tokens_to_resolve.append((raw_token, not tokens_to_resolve))

        # Check explicit request target_role as fallback / secondary context
        if request.target_role:
            tokens_to_resolve.append((request.target_role.strip(), not tokens_to_resolve))
        for role in request.selected_roles:
            if role.strip():
                tokens_to_resolve.append((role.strip(), not tokens_to_resolve))

        # Check background user selected skills as fallback / secondary context
        for sk in request.selected_skills:
            if sk.strip():
                tokens_to_resolve.append((sk.strip(), not tokens_to_resolve))

        # Deduplicate while preserving order
        unique_tokens: list[tuple[str, bool]] = []
        seen = set()
        for tok, is_prim in tokens_to_resolve:
            tok = tok.strip(" \t\n\r?.!,;:")
            clean = tok.casefold()
            if clean and clean not in seen:
                seen.add(clean)
                unique_tokens.append((tok, is_prim))

        # Resolve each token via EntityRegistryService
        resolved_items: list[ResolvedEntityItem] = []
        is_first = True
        for tok, is_prim in unique_tokens:
            res = self._entity_service.resolve(EntityResolutionRequest(name=tok))
            if res.status == "resolved" and res.entity:
                resolved_items.append(
                    ResolvedEntityItem(
                        raw_token=tok,
                        resolution_status="resolved",
                        canonical_entity=res.entity,
                        candidates=[],
                        is_primary=is_first,
                        match_reason=res.match_method,
                    )
                )
            elif res.status == "ambiguous":
                resolved_items.append(
                    ResolvedEntityItem(
                        raw_token=tok,
                        resolution_status="ambiguous",
                        canonical_entity=None,
                        candidates=res.candidates,
                        is_primary=is_first,
                        match_reason="ambiguous_candidates_available",
                    )
                )
            else:
                resolved_items.append(
                    ResolvedEntityItem(
                        raw_token=tok,
                        resolution_status="not_found",
                        canonical_entity=None,
                        candidates=[],
                        is_primary=is_first,
                        match_reason="Entity not recognized in taxonomy",
                    )
                )
            is_first = False

        return resolved_items

    # -------------------------------------------------------------------------
    # INTENT CLASSIFICATION
    # -------------------------------------------------------------------------

    def _classify_intent(
        self,
        message: str,
        entities: list[ResolvedEntityItem],
    ) -> tuple[IntentCategory, float, str, list[str], bool]:
        """Classify user intent deterministically and map to registered capabilities."""
        # 1. Forecasting / Future projections
        is_comp = any(pat.search(message) for pat in COMPARISON_PATTERNS)
        is_ev = any(pat.search(message) for pat in EVIDENCE_PATTERNS)
        if is_ev and not is_comp:
            return (
                "retrieve_evidence",
                0.90,
                "Request asks for verifiable evidence, provenance citations, or archives.",
                ["evidence_provenance_retrieval"],
                False,
            )

        if not is_comp:
            for pat in FORECAST_PATTERNS:
                if pat.search(message):
                    return (
                        "forecast_future_demand",
                        0.95,
                        "Request asks for forward-looking skill demand forecasting.",
                        ["skill_forecasting_half_life"],
                        False,
                    )

        # Role-specific learning questions use the authenticated profile-aware
        # recommendation capability, not only a role taxonomy lookup.
        for pat in SKILL_LEARNING_PATTERNS:
            if pat.search(message):
                return (
                    "synthesize_actions",
                    0.90,
                    "Request asks for an individual learning suggestion or roadmap.",
                    ["action_recommendations"],
                    False,
                )

        # 2. What-if simulation
        for pat in SIMULATION_PATTERNS:
            if pat.search(message):
                return (
                    "simulate_workforce_scenarios",
                    0.95,
                    "Request asks for workforce what-if simulation or scenario modeling.",
                    ["workforce_what_if_simulation"],
                    False,
                )

        # 2b. AI Task Exposure and Disruption
        if not is_comp:
            for pat in AI_TASK_EXPOSURE_PATTERNS:
                if pat.search(message):
                    return (
                        "analyze_ai_task_exposure",
                        0.95,
                        "Request asks for AI task exposure, automation potential, or disruption analysis.",
                        ["ai_task_exposure"],
                        False,
                    )

        if any(pat.search(message) for pat in ALL_SKILL_TREND_PATTERNS):
            return (
                "rank_skill_trends",
                0.90,
                "Request asks for a ranked view of eligible observed skill trends.",
                ["trend_velocity_analysis"],
                False,
            )

        # 3. Entity comparison
        for pat in COMPARISON_PATTERNS:
            if pat.search(message):
                is_task_exposure_comparison = any(
                    pattern.search(message) for pattern in AI_TASK_EXPOSURE_PATTERNS
                )
                selected = (
                    ["ai_task_exposure"]
                    if is_task_exposure_comparison
                    else ["trend_velocity_analysis", "market_snapshot", "skill_technology_reference"]
                )
                if any(p.search(message) for p in HEALTH_PATTERNS):
                    selected = ["skill_health_analysis", *selected]
                if any(p.search(message) for p in HALF_LIFE_PATTERNS):
                    selected = ["skill_half_life_analysis", *selected]
                if any(p.search(message) for p in FORECAST_PATTERNS):
                    selected = ["skill_forecasting_half_life", *selected]
                return (
                    "compare_entities",
                    0.90,
                    f"Request compares {len(entities)} entity mentions.",
                    selected,
                    True,
                )

        # 4. Job postings search
        for pat in JOB_SEARCH_PATTERNS:
            if pat.search(message):
                return (
                    "search_jobs",
                    0.90,
                    "Request asks to search job postings matching keywords.",
                    ["job_posting_search"],
                    False,
                )

        # 6. Related occupations / mobility
        for pat in OCC_RELATED_PATTERNS:
            if pat.search(message):
                return (
                    "crosswalk_related_occupations",
                    0.90,
                    "Request asks for career mobility pathways and related occupations.",
                    ["related_occupations"],
                    False,
                )

        # 6b. Occupation software / tools crosswalk
        for pat in OCC_SOFTWARE_PATTERNS:
            if pat.search(message):
                return (
                    "crosswalk_occupation_software",
                    0.90,
                    "Request asks for software tools and technologies mapped to an occupation.",
                    ["occupation_software_skills"],
                    False,
                )

        # Workforce-record queries must not be confused with an individual's
        # skill-gap analysis merely because they use "missing skills" wording.
        for pat in COMPANY_PATTERNS:
            if pat.search(message):
                return (
                    "analyze_company_workforce",
                    0.85,
                    "Request asks for company-scoped workforce skill record coverage.",
                    ["company_intelligence"],
                    False,
                )

        # 7. Skill gap analysis
        for pat in SKILL_GAP_PATTERNS:
            if pat.search(message):
                return (
                    "analyze_skill_gap",
                    0.90,
                    "Request asks for alignment or gap analysis between skills and a role.",
                    ["skill_gap_role_fit"],
                    False,
                )

        # 8. Occupation lookup
        for pat in OCC_LOOKUP_PATTERNS:
            if pat.search(message):
                return (
                    "lookup_occupation",
                    0.85,
                    "Request asks for standardized O*NET occupation reference details.",
                    ["occupation_lookup"],
                    False,
                )

        # 9. Evidence & provenance
        for pat in EVIDENCE_PATTERNS:
            if pat.search(message):
                return (
                    "retrieve_evidence",
                    0.90,
                    "Request asks for verifiable evidence, provenance citations, or archives.",
                    ["evidence_provenance_retrieval"],
                    False,
                )

        # 10. Action recommendations
        for pat in ACTION_PATTERNS:
            if pat.search(message):
                return (
                    "synthesize_actions",
                    0.90,
                    "Request asks for next learning actions or operational recommendations.",
                    ["action_recommendations"],
                    False,
                )

        # 11b. Skill Health relative momentum
        for pat in HEALTH_PATTERNS:
            if pat.search(message):
                return (
                    "analyze_skill_health",
                    0.90,
                    "Request asks for Skill Health relative momentum or health score.",
                    ["skill_health_analysis"],
                    False,
                )

        # 11c. Skill Half-Life decay analysis
        for pat in HALF_LIFE_PATTERNS:
            if pat.search(message):
                return (
                    "estimate_skill_half_life",
                    0.90,
                    "Request asks for empirical Skill Half-Life decay analysis.",
                    ["skill_half_life_analysis"],
                    False,
                )

        # 12. Trend & velocity
        for pat in TREND_PATTERNS:
            if pat.search(message):
                return (
                    "analyze_trend",
                    0.88,
                    "Request asks for Theil-Sen trend, velocity, or direction analysis.",
                    ["trend_velocity_analysis"],
                    False,
                )

        # 13. Historical observations
        for pat in HISTORY_PATTERNS:
            if pat.search(message):
                return (
                    "retrieve_history",
                    0.85,
                    "Request asks for historical time-series observation data.",
                    ["historical_signal_retrieval"],
                    False,
                )

        # 14. Market snapshot
        for pat in SNAPSHOT_PATTERNS:
            if pat.search(message):
                return (
                    "retrieve_snapshot",
                    0.85,
                    "Request asks for latest point-in-time market observations.",
                    ["market_snapshot"],
                    False,
                )

        # 15. Concept explanation / taxonomy lookup
        for pat in CONCEPT_PATTERNS:
            if pat.search(message):
                return (
                    "explain_concept",
                    0.80,
                    "Request asks for a conceptual overview or taxonomy reference lookup.",
                    ["skill_technology_reference"],
                    False,
                )

        # 16. Entity resolution
        for pat in RESOLVE_PATTERNS:
            if pat.search(message):
                return (
                    "resolve_entity",
                    0.90,
                    "Request asks for canonical entity resolution.",
                    ["entity_resolution"],
                    False,
                )

        # If entities are resolved, fallback to skill_technology_reference or trend based on context
        if entities and entities[0].resolution_status == "resolved":
            ent = entities[0].canonical_entity
            if ent and ent.entity_type == "occupation":
                return (
                    "lookup_occupation",
                    0.75,
                    f"Query mentions occupation '{ent.canonical_name}'.",
                    ["occupation_lookup"],
                    False,
                )
            elif ent and ent.entity_type in {"skill", "technology"}:
                return (
                    "lookup_skill_reference",
                    0.75,
                    f"Query mentions skill/technology '{ent.canonical_name}'.",
                    ["skill_technology_reference"],
                    False,
                )

        # Default fallback
        return (
            "unsupported_or_unclear",
            0.30,
            "Could not determine a specific intelligence intent from the message.",
            [],
            False,
        )

    # -------------------------------------------------------------------------
    # CONTEXT PLANNING & CLARIFICATION
    # -------------------------------------------------------------------------

    def _build_context(
        self,
        request: IntelligencePlanRequest,
        auth_user: AuthenticatedUser | None,
        portal_type: str,
        entities: list[ResolvedEntityItem],
        selected_caps: list[str],
        is_comparison: bool,
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        primary_name = None
        occ_entity = next(
            (e.canonical_entity.canonical_name for e in entities if e.canonical_entity and e.canonical_entity.entity_type == "occupation"),
            None,
        )
        if any(c in selected_caps for c in ("occupation_software_skills", "related_occupations", "occupation_lookup")) and (occ_entity or request.target_role):
            primary_name = occ_entity or request.target_role
        elif entities and entities[0].canonical_entity:
            primary_name = entities[0].canonical_entity.canonical_name
        elif entities:
            primary_name = entities[0].raw_token

        explicit_time_range = (
            "time_range" in request.model_fields_set
            or any(
                request.filters.get(key) not in (None, "")
                for key in ("time_range", "requested_time_window")
            )
        )
        effective_time_range = (
            "36m"
            if (
                "skill_half_life_analysis" in selected_caps
                and not explicit_time_range
                and request.time_range == "30d"
            )
            else (
                "24m"
                if (
                    "skill_forecasting_half_life" in selected_caps
                    and not explicit_time_range
                    and request.time_range == "30d"
                )
                else (
                    "6m"
                    if (
                        ("trend_velocity_analysis" in selected_caps or "skill_health_analysis" in selected_caps)
                        and not explicit_time_range
                        and request.time_range == "30d"
                    )
                    else request.time_range
                )
            )
        )

        context_summary: dict[str, Any] = {
            "portal_type": portal_type,
            "domain": request.domain,
            "user_id": auth_user.uid if auth_user else None,
            "company_id": request.company_id or (getattr(auth_user, "claims", {}).get("company_id") if hasattr(auth_user, "claims") and isinstance(getattr(auth_user, "claims"), dict) else getattr(auth_user, "company_id", None)),
            "location": request.location or "Global",
            "time_range": effective_time_range,
            "target_role": request.target_role,
            "selected_skills": request.selected_skills,
            "selected_roles": request.selected_roles,
            "selected_companies": request.selected_companies,
            "filters": dict(request.filters),
            "primary_entity": primary_name,
            "comparison_entities": [e.canonical_entity.canonical_name for e in entities[1:] if e.canonical_entity],
        }

        missing_context: list[str] = []
        clarification_questions: list[str] = []

        # 0. Unsupported capabilities (simulation) never require user clarification
        if selected_caps in (["workforce_what_if_simulation"],):
            return context_summary, [], []

        # 0b. Unclear intent prompts for general clarification
        if not selected_caps:
            ambig = [e for e in entities if e.resolution_status == "ambiguous"]
            if ambig:
                for ent in ambig:
                    cand_names = [c.entity.canonical_name for c in ent.candidates]
                    missing_context.append(f"disambiguation_{ent.raw_token}")
                    clarification_questions.append(
                        f"'{ent.raw_token}' can refer to multiple entities ({', '.join(cand_names)}). Which specific one did you mean?"
                    )
                return context_summary, missing_context, clarification_questions
            return (
                context_summary,
                ["intent_clarification"],
                ["Could you clarify what information or analysis you are looking for (e.g., skill trends, job search, occupation details, or action recommendations)?"],
            )

        # 1. Comparison requires at least 2 distinct entities
        if is_comparison:
            resolved_count = sum(1 for e in entities if e.resolution_status == "resolved")
            if resolved_count < 2:
                missing_context.append("comparison_entity_pair")
                clarification_questions.append(
                    "Comparison requires at least two entities. Which other skill, technology, or role would you like to compare?"
                )

        # 2. Check ambiguous entities
        for ent in entities:
            if ent.resolution_status == "ambiguous":
                cand_names = [c.entity.canonical_name for c in ent.candidates]
                missing_context.append(f"disambiguation_{ent.raw_token}")
                clarification_questions.append(
                    f"'{ent.raw_token}' can refer to multiple entities ({', '.join(cand_names)}). Which specific one did you mean?"
                )

        # 3. Check capability-derived required inputs
        all_skill_trend = any(pat.search(request.message) for pat in ALL_SKILL_TREND_PATTERNS)
        for cap_id in selected_caps:
            cap_record = CAPABILITY_CATALOG.get(cap_id)
            if not cap_record:
                continue

            for req_in in cap_record.required_inputs:
                if req_in == "entity_name":
                    has_entity = any(e.resolution_status in {"resolved", "ambiguous"} for e in entities)
                    if not has_entity and not all_skill_trend:
                        missing_context.append("entity_name")
                        if not clarification_questions:
                            unmatched_entity = next(
                                (entity for entity in entities if entity.resolution_status == "not_found"),
                                None,
                            )
                            if cap_id in ("trend_velocity_analysis", "skill_health_analysis") and unmatched_entity:
                                clarification_questions.append(
                                    f"I couldn't match '{unmatched_entity.raw_token}' to a supported skill. "
                                    "Please try its canonical skill name or a supported alternative."
                                )
                            else:
                                clarification_questions.append("Which skill, technology, or occupation would you like to analyze?")
                elif req_in in {"soc_code", "soc_code_or_title", "soc_code_or_target_role"}:
                    has_role = bool(request.target_role) or any(
                        e.canonical_entity and e.canonical_entity.entity_type == "occupation"
                        for e in entities
                    )
                    if not has_role:
                        missing_context.append("target_occupation")
                        if not clarification_questions:
                            clarification_questions.append("Which occupation or role title would you like to look up?")
                elif req_in == "selected_skills":
                    if not request.selected_skills:
                        missing_context.append("selected_skills")
                        if not clarification_questions:
                            clarification_questions.append("Please specify which skills you'd like to evaluate for this role alignment.")
                elif req_in == "company_id":
                    cid = context_summary.get("company_id")
                    if not cid and portal_type != "company":
                        missing_context.append("company_id")
                        if not clarification_questions:
                            clarification_questions.append("Company workforce intelligence requires a verified company identifier.")

        return context_summary, missing_context, clarification_questions

    # -------------------------------------------------------------------------
    # CAPABILITY EVALUATION
    # -------------------------------------------------------------------------

    def _evaluate_selected_capabilities(
        self,
        selected_caps: list[str],
        entities: list[ResolvedEntityItem],
        request: IntelligencePlanRequest,
        portal_type: str,
        context_summary: dict[str, Any],
    ) -> tuple[list[CapabilityEvaluationResult], list[str]]:
        """Evaluate runtime readiness of each selected capability using CapabilityRegistryService."""
        readiness_results: list[CapabilityEvaluationResult] = []
        limitations: list[str] = []

        primary_ent_name = None
        primary_ent_type = None
        if entities and entities[0].canonical_entity:
            primary_ent_name = entities[0].canonical_entity.canonical_name
            primary_ent_type = entities[0].canonical_entity.entity_type
        elif entities:
            primary_ent_name = entities[0].raw_token

        for cap_id in selected_caps:
            eval_req = CapabilityEvaluationRequest(
                capability_id=cap_id,
                entity_name=primary_ent_name,
                entity_type=primary_ent_type,
                portal_type=portal_type,  # type: ignore[arg-type]
                time_range=context_summary.get("time_range") or request.time_range,
                location=request.location,
                target_role=request.target_role,
                selected_skills=request.selected_skills,
                observations=request.observations,
                task_exposure_records=request.task_exposure_records,
                dataset_provenance=request.dataset_provenance,
                context_override=request.context_override,
            )
            eval_resp = self._capability_service.evaluate(eval_req)
            if eval_resp.results:
                res = eval_resp.results[0]
                readiness_results.append(res)
                limitations.extend(res.limitations)

        return readiness_results, limitations

    # -------------------------------------------------------------------------
    # PLAN STATUS DETERMINATION
    # -------------------------------------------------------------------------

    def _determine_plan_status(
        self,
        intent: IntentCategory,
        selected_caps: list[str],
        clarification_required: bool,
        readiness_results: list[CapabilityEvaluationResult],
        entities: list[ResolvedEntityItem],
    ) -> PlanStatus:
        """Determine plan status based on intent, clarification needs, and readiness results."""
        if intent in {"simulate_workforce_scenarios"}:
            return "unsupported"

        if intent == "unsupported_or_unclear":
            return "requires_clarification"

        if clarification_required:
            return "requires_clarification"

        # A broad ranking evaluates readiness independently for each stored series
        # during execution; a single-entity capability probe is not meaningful here.
        if intent == "rank_skill_trends":
            return "ready_to_execute"

        # Check readiness results
        if not readiness_results:
            return "requires_clarification"

        # If any capability is explicitly blocked by quality/configuration/gates
        if any(r.runtime_status == "blocked" for r in readiness_results):
            return "blocked"

        # If all capabilities have insufficient data and require inputs
        if all(r.runtime_status == "insufficient_data" and not r.can_execute for r in readiness_results):
            return "insufficient_data"

        # If at least one capability can execute or is partially available
        if any(r.can_execute for r in readiness_results):
            return "ready_to_execute"

        return "requires_clarification"
