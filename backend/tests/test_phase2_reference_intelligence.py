"""Automated test suite for Phase 2: Skill & Role Reference Intelligence.

Validates:
1. Exact ID and canonical lookup for skills and occupations (SOC, ESCO, canonical ID).
2. Exact and controlled partial matching.
3. Supported aliases normalization.
4. Ambiguous terms (go, r, cloud, lambda) requiring clarification vs disambiguation in context.
5. Explainable relationship types:
   - direct_technical_relation
   - same_occupation_cooccurrence
   - general_occupational_association
6. PPMI and IOF ranking verifying generic office tools do not dominate technical skills.
7. Truthful role-skill alignment (matched, unmatched, unresolved, ambiguous, non-disqualification disclaimer).
8. Career mobility pathways (O*NET related occupations, tiers, shared and additional skills).
9. Direct API endpoints (/reference/lookup, /reference/related-skills, /reference/role-alignment, /reference/mobility-pathways).
10. V2 Orchestrator natural-language request-to-response integration.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.intelligence_v2.contracts import (
    CareerMobilityResult,
    RelatedSkillsResult,
    RelationshipType,
    RoleSkillAlignmentResult,
    TaxonomyLookupResult,
)
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.reference_intelligence import (
    CareerMobilityEngine,
    ReferenceTaxonomyLookupEngine,
    RelatedSkillsEngine,
    RoleSkillAlignmentEngine,
    AUDITED_TECHNICAL_RELATION_INVENTORY,
    TECHNICAL_RELATION_CLASSIFICATIONS,
    VALIDATED_DIRECT_TECHNICAL_RELATIONS,
    _ppmi_iof_intermediates,
    classify_technical_relation,
    is_validated_direct_technical_relation,
)
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.reference_store import ReferenceDataStore


@pytest.fixture(scope="module")
def ref_store():
    return ReferenceDataStore(read_only=True)


@pytest.fixture(scope="module")
def lookup_engine(ref_store):
    return ReferenceTaxonomyLookupEngine(ref_store)


@pytest.fixture(scope="module")
def related_engine(ref_store):
    return RelatedSkillsEngine(ref_store)


@pytest.fixture(scope="module")
def alignment_engine(ref_store):
    return RoleSkillAlignmentEngine(ref_store)


@pytest.fixture(scope="module")
def mobility_engine(ref_store):
    return CareerMobilityEngine(ref_store)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Skill & Occupation Lookup Tests
# ---------------------------------------------------------------------------

class TestTaxonomyLookup:
    @pytest.mark.parametrize(
        ("alias", "canonical_id"),
        [("k8s", "skill:kubernetes"), ("postgres", "skill:postgresql")],
    )
    def test_registry_alias_ids_are_stable_across_engines(
        self, alias, canonical_id, lookup_engine, related_engine, alignment_engine
    ):
        from app.analytics.skill_registry import canonical_skill_id

        assert f"skill:{canonical_skill_id(alias)}" == canonical_id
        lookup = lookup_engine.lookup(alias, entity_type="skill")
        assert any(row.canonical_id == canonical_id for row in lookup.results)
        related = related_engine.get_related_skills(alias, limit=1)
        assert related.canonical_id == canonical_id
        aligned = alignment_engine.align("Software Developers", [alias])
        assert aligned.status in {"ready", "partial"}

    @pytest.mark.parametrize("ambiguous", ["go", "r", "cloud", "lambda"])
    def test_ambiguous_registry_terms_require_disambiguation(self, ambiguous, lookup_engine, related_engine):
        assert lookup_engine.lookup(ambiguous, entity_type="skill").status == "ambiguous"
        assert related_engine.get_related_skills(ambiguous).status == "ambiguous"

    def test_unknown_registry_input_stays_unmapped(self, lookup_engine, related_engine):
        assert lookup_engine.lookup("UnlistedSkillExample", entity_type="skill").total_matches == 0
        assert related_engine.get_related_skills("UnlistedSkillExample").canonical_id is None

    def test_lookup_exact_canonical_soc_code(self, lookup_engine):
        """Lookup by exact SOC code returns canonical O*NET occupation."""
        res = lookup_engine.lookup("15-1252.00", entity_type="occupation")
        assert res.status == "ready"
        assert res.total_matches >= 1
        item = res.results[0]
        assert item.canonical_id == "15-1252.00"
        assert "Software Developers" in item.name
        assert item.source == "ONET_2024"

    def test_lookup_canonical_skill_id(self, lookup_engine):
        """Lookup by canonical skill ID returns skill entry."""
        res = lookup_engine.lookup("skill:python", entity_type="skill")
        assert res.status == "ready"
        assert res.total_matches >= 1
        item = res.results[0]
        assert item.canonical_id == "skill:python"
        assert item.name == "Python"
        assert item.entity_type == "skill"

    def test_lookup_supported_alias(self, lookup_engine):
        """Lookup using supported alias resolves to canonical target."""
        # 'k8s' -> Kubernetes
        res_k8s = lookup_engine.lookup("k8s", entity_type="skill")
        assert res_k8s.status == "ready"
        assert any("Kubernetes" in r.name for r in res_k8s.results)

        # 'reactjs' -> React
        res_react = lookup_engine.lookup("reactjs", entity_type="skill")
        assert res_react.status == "ready"
        assert any("React" in r.name for r in res_react.results)

    def test_lookup_partial_match(self, lookup_engine):
        """Partial match searches return ranked relevant entries."""
        res = lookup_engine.lookup("Data Scien", entity_type="occupation")
        assert res.status in {"ready", "partial"}
        assert any("Data Scientists" in r.name for r in res.results)

    def test_ambiguous_term_requires_clarification(self, lookup_engine):
        """Single ambiguous term without context triggers clarification."""
        res = lookup_engine.lookup("go", entity_type="skill")
        assert res.clarification_needed is True
        assert res.status == "ambiguous"
        assert any("Go/Golang" in r.ambiguity_note for r in res.results if r.ambiguity_note)

    def test_ambiguous_term_resolved_with_technical_context(self, lookup_engine):
        """Ambiguous term with technical context disambiguates cleanly."""
        res = lookup_engine.lookup("go", entity_type="skill", context="backend developer programming code")
        assert res.clarification_needed is False
        assert res.status == "ready"
        assert any(r.name.lower() in {"go", "golang"} for r in res.results)


# ---------------------------------------------------------------------------
# 2. Explainable Related-Skill Intelligence Tests
# ---------------------------------------------------------------------------

class TestRelatedSkills:
    def test_every_audited_pair_has_one_conservative_classification(self):
        audited_pairs = {
            (target, candidate)
            for target, candidates in AUDITED_TECHNICAL_RELATION_INVENTORY.items()
            for candidate in candidates
        }
        assert set(TECHNICAL_RELATION_CLASSIFICATIONS) == audited_pairs
        assert set(TECHNICAL_RELATION_CLASSIFICATIONS.values()) <= {
            "verified_direct_relation", "ecosystem_compatibility", "not_supported"
        }
        verified_pairs = {
            ("python", candidate)
            for candidate in VALIDATED_DIRECT_TECHNICAL_RELATIONS["python"]
        }
        assert {
            pair for pair, category in TECHNICAL_RELATION_CLASSIFICATIONS.items()
            if category == "verified_direct_relation"
        } == verified_pairs
        assert VALIDATED_DIRECT_TECHNICAL_RELATIONS == {
            "python": AUDITED_TECHNICAL_RELATION_INVENTORY["python"]
        }

    @pytest.mark.parametrize(
        ("counts", "expected"),
        [
            ((0, 10, 5, 100), (0.0, 4.321928094887363, 0.0)),
            ((None, 10, 5, 100), (0.0, 4.321928094887363, 0.0)),
            ((1, None, 5, 100), (0.0, 0.0, 0.5)),
            ((1, 10, None, 100), (0.0, 0.0, 0.5)),
            ((1, 10, 5, None), (0.0, 0.0, 0.5)),
        ],
    )
    def test_ppmi_iof_zero_and_missing_counts(self, counts, expected):
        assert _ppmi_iof_intermediates(*counts) == pytest.approx(expected)

    def test_related_skills_relationship_types(self, related_engine):
        """Related skills return explicit relationship types and explanations."""
        res = related_engine.get_related_skills("Python", limit=10)
        assert res.status == "ready"
        assert len(res.related_skills) > 0
        valid_types = {
            "direct_technical_relation",
            "same_occupation_cooccurrence",
            "general_occupational_association",
        }
        for item in res.related_skills:
            assert item.relationship_type in valid_types
            assert item.ranking_score is not None
            assert len(item.explanation) > 10

    def test_ppmi_iof_exact_numerical_reproduction(self, related_engine):
        """Reproduce exact PPMI/IOF score from local SQLite data for Python and Django.

        Local SQLite ground truth:
        Total occupations N = 923.
        Python occupations n_target = 132.
        Django co_count = 20, total Django occupations n_cand = 21.
        PPMI = log2((20 * 923) / (132 * 21)) = log2(18460 / 2772) = 2.7354 -> round(2.735)
        IOF = log2(923 / 21) = 5.4578 -> round(5.458)
        freq_discount = 20 / (20 + 1) = 0.95238
        base_score = (2.7354 * 0.95238) + (0.15 * 5.4578) + 2.0 = 2.6052 + 0.8187 + 2.0 = 5.424
        """
        res = related_engine.get_related_skills("Python", limit=20)
        django_items = [s for s in res.related_skills if s.skill_name == "Django"]
        assert len(django_items) == 1
        django = django_items[0]
        assert django.ranking_score == 5.424
        assert django.relationship_type == "direct_technical_relation"
        assert django.metadata["co_count"] == 20
        assert django.metadata["n_target"] == 132
        assert django.metadata["n_cand"] == 21
        assert django.metadata["total_occupations"] == 923
        assert django.metadata["ppmi"] == 2.735
        assert django.metadata["iof"] == 5.458

    def test_scores_are_distinct_and_tie_breaking_deterministic(self, related_engine):
        """Verify scores are distinct across distinct co-occurrences and tie-breaking is deterministic."""
        res = related_engine.get_related_skills("Python", limit=20)
        scores = [s.ranking_score for s in res.related_skills]
        assert len(set(scores)) > 5

        # Check deterministic tie-breaking: primary key -ranking_score, secondary -co_count, tertiary name casefold
        for i in range(len(res.related_skills) - 1):
            curr = res.related_skills[i]
            nxt = res.related_skills[i + 1]
            if curr.ranking_score == nxt.ranking_score:
                curr_co = curr.metadata.get("co_count", 0)
                nxt_co = nxt.metadata.get("co_count", 0)
                if curr_co == nxt_co:
                    assert curr.skill_name.casefold() <= nxt.skill_name.casefold()
                else:
                    assert curr_co >= nxt_co
            else:
                assert curr.ranking_score >= nxt.ranking_score

    def test_direct_technical_relation_restricted_to_validated_ecosystem(self, related_engine):
        """Fortran shares O*NET category 2.E.7.e with Python, but must NOT be direct_technical_relation.

        Only documented, validated ecosystem tools receive direct_technical_relation.
        """
        assert is_validated_direct_technical_relation("Python", "Django") is True
        assert is_validated_direct_technical_relation("Python", "Fortran") is False

        # Query related skills to verify Fortran is same_occupation_cooccurrence if present
        res = related_engine.get_related_skills("Python", limit=150)
        fortran_matches = [s for s in res.related_skills if "fortran" in s.skill_name.casefold()]
        for f in fortran_matches:
            assert f.relationship_type != "direct_technical_relation"
            assert f.relationship_type == "same_occupation_cooccurrence"

    def test_ppmi_iof_anti_generic_ranking(self, related_engine):
        """PPMI/IOF ranking suppresses generic office tools from top technical skills."""
        res = related_engine.get_related_skills("Python", limit=15)
        top_names = [item.skill_name.casefold() for item in res.related_skills[:5]]

        # Microsoft Word and Microsoft Excel should NOT dominate top technical co-occurrences
        assert "microsoft word" not in top_names
        assert "microsoft powerpoint" not in top_names

        # Validated direct ecosystem tools should rank at top
        assert any(t in top_names for t in ["django", "pytorch", "pandas", "pyspark", "scikit-learn"])

    def test_related_skills_alias_resolution_target_and_candidate(self, related_engine):
        """Section 1 & 4: Supported alias 'k8s' resolves to Kubernetes with stable canonical IDs."""
        res = related_engine.get_related_skills("k8s", limit=5)
        assert res.status == "ready"
        assert res.target_skill == "Kubernetes"
        assert res.canonical_id == "skill:kubernetes"
        assert len(res.related_skills) > 0

        assert classify_technical_relation("Kubernetes", "Docker") == "ecosystem_compatibility"
        assert all(
            item.relationship_type != "direct_technical_relation"
            or is_validated_direct_technical_relation("Kubernetes", item.skill_name)
            for item in res.related_skills
        )

    def test_validated_direct_technical_allowlist_comprehensive(self):
        """Section 2: Accepted vs rejected technical relationship pairs."""
        # Accepted pairs: documented direct dependencies
        assert is_validated_direct_technical_relation("Python", "Django") is True
        assert is_validated_direct_technical_relation("Python", "pandas") is True

        # Rejected pairs: must not be direct_technical_relation (classified as same_occupation_cooccurrence)
        assert is_validated_direct_technical_relation("SQL", "PostgreSQL") is False
        assert is_validated_direct_technical_relation("Python", "Fortran") is False
        assert is_validated_direct_technical_relation("Python", "Microsoft Excel") is False
        assert is_validated_direct_technical_relation("Python", "Linux") is False
        assert is_validated_direct_technical_relation("Python", "C++") is False
        assert is_validated_direct_technical_relation("Java", "Kotlin") is False
        assert is_validated_direct_technical_relation("Java", "Apache Kafka") is False
        assert is_validated_direct_technical_relation("AWS", "Terraform") is False

    @pytest.mark.parametrize(
        ("target", "candidate", "expected"),
        [
            ("Python", "Django", True),
            ("Python", "pandas", True),
            ("Docker", "Kubernetes", False),
            ("Python", "C++", False),
            ("Python", "Fortran", False),
            ("Java", "Kafka", False),
            ("AWS", "Terraform", False),
            ("SQL", "PostgreSQL", False),
            ("React Native", "iOS", False),
            ("React Native", "Android", False),
            ("AWS Lambda", "Serverless", False),
        ],
    )
    def test_validated_direct_technical_pairs_parameterized(self, target, candidate, expected):
        """Scope 2: Parameterized audit of accepted vs rejected direct technical pairs."""
        assert is_validated_direct_technical_relation(target, candidate) is expected

    @pytest.mark.parametrize(
        ("target", "candidate", "expected"),
        [
            ("Python", "Django", "verified_direct_relation"),
            ("Python", "pandas", "verified_direct_relation"),
            ("Python", "C++", "not_supported"),
            ("Python", "Fortran", "not_supported"),
            ("Java", "Kafka", "ecosystem_compatibility"),
            ("Docker", "Kubernetes", "ecosystem_compatibility"),
            ("AWS", "Terraform", "not_supported"),
        ],
    )
    def test_semantic_relation_classification(self, target, candidate, expected):
        assert classify_technical_relation(target, candidate) == expected

    def test_denominator_safety_and_no_synthetic_substitution(self, related_engine):
        """Section 1: Missing skills return insufficient_data without synthetic records or zero division."""
        # Whitespace / empty query
        res_empty = related_engine.get_related_skills("   ")
        assert res_empty.status == "insufficient_data"
        assert len(res_empty.related_skills) == 0

        # Unknown skill never in database
        res_unknown = related_engine.get_related_skills("NonExistentSkillXYZ12345")
        assert res_unknown.status == "insufficient_data"
        assert len(res_unknown.related_skills) == 0

    def test_unknown_skill_returns_empty_cleanly(self, related_engine):
        """Querying an unknown non-existent skill returns empty result with explanation."""
        res = related_engine.get_related_skills("XylophoneUnicornFramework999")
        assert res.status == "insufficient_data"
        assert len(res.related_skills) == 0

    def test_ppmi_iof_heuristic_limitations_and_ubiquitous_discount(self, related_engine):
        """Scope 1: Verify limitations disclose heuristic parameters and common skills receive discount."""
        res = related_engine.get_related_skills("Python", limit=20)
        assert res.status == "ready"
        # Verify heuristic and non-probability disclosures
        joined_limits = " ".join(res.limitations).lower()
        assert "heuristic" in joined_limits
        assert "not a probability, percentage, confidence level" in joined_limits
        assert "design parameters" in joined_limits
        assert "0.15" in joined_limits
        assert "2.0" in joined_limits

        # Check that candidate skills with n_cand > 300 receive the 0.15 ubiquitous discount if not direct technical
        penalized_skills = [
            s for s in res.related_skills
            if s.relationship_type == "same_occupation_cooccurrence" and s.metadata.get("n_cand", 0) > 300
        ]
        for item in penalized_skills:
            ppmi = item.metadata["ppmi"]
            iof = item.metadata["iof"]
            co = item.metadata["co_count"]
            freq_discount = co / (co + 1.0)
            expected_raw = (ppmi * freq_discount) + (0.15 * iof)
            expected_penalized = round(expected_raw * 0.15, 3)
            assert item.ranking_score == expected_penalized


# ---------------------------------------------------------------------------
# 3. Truthful Role-Skill Alignment Tests
# ---------------------------------------------------------------------------

class TestRoleSkillAlignment:
    def test_role_skill_alignment_truthful_partitioning(self, alignment_engine):
        """Separates matched, not declared, unresolved, and ambiguous skills."""
        target_role = "Software Developers"
        declared = ["Python", "Git", "UnknownAlienTechFoo", "go"]  # go is ambiguous without context

        res = alignment_engine.align(target_role, declared)
        assert res.status == "ready"
        assert res.canonical_occupation_id == "15-1252.00"
        assert len(res.reference_associated_skills) > 0

        # Matched
        assert any("Python" in s for s in res.matched_skills)

        # Unmatched reference skills
        assert len(res.unmatched_reference_skills) > 0

        # Unresolved
        assert "UnknownAlienTechFoo" in res.unresolved_skills

        # Ambiguous
        assert any(a["skill"] == "go" for a in res.ambiguous_skills)

    def test_alignment_contains_non_disqualification_disclaimer(self, alignment_engine):
        """Mandatory disclaimer stating reference skills are baseline taxonomies and not hiring disqualifications."""
        res = alignment_engine.align("Software Developers", ["Python", "Java"])
        assert "not be interpreted as verified live employer requirements" in res.disclaimer
        assert "proven candidate deficiencies or disqualifications" in res.disclaimer

    def test_unresolved_and_ambiguous_skills_preserved_faithfully(self, alignment_engine):
        """Scope 4: Skills that cannot be canonically resolved are preserved as unresolved or ambiguous."""
        declared = ["go", "r", "cloud", "lambda", "NonExistentQuantumLibXYZ"]
        res = alignment_engine.align("Software Developers", declared)
        ambiguous_keys = {a["skill"] for a in res.ambiguous_skills}
        assert "go" in ambiguous_keys
        assert "r" in ambiguous_keys
        assert "cloud" in ambiguous_keys
        assert "lambda" in ambiguous_keys
        assert "NonExistentQuantumLibXYZ" in res.unresolved_skills
        assert "NonExistentQuantumLibXYZ" not in res.matched_skills


# ---------------------------------------------------------------------------
# 4. Career Mobility Pathways Tests
# ---------------------------------------------------------------------------

class TestCareerMobility:
    def test_career_mobility_pathways_grounded_in_onet(self, mobility_engine):
        """Pathways are grounded in O*NET related occupations with tiers, shared and additional skills."""
        res = mobility_engine.get_pathways("Software Developers", limit=5)
        assert res.status == "ready"
        assert res.source_soc_code == "15-1252.00"
        assert len(res.pathways) > 0

        valid_tiers = {"Primary-Short", "Primary-Long", "Supplemental"}
        for p in res.pathways:
            assert p.relatedness_tier in valid_tiers
            assert len(p.destination_occupation_title) > 0
            assert len(p.destination_soc_code) > 0
            assert isinstance(p.shared_skills, list)
            assert isinstance(p.additional_destination_skills, list)
            assert "Primary" in p.relationship_nature or "Supplemental" in p.relationship_nature

    def test_career_mobility_canonical_intersection_and_difference(self, mobility_engine):
        """Scope 3: Shared skills are canonical intersection, additional skills are destination minus source."""
        res = mobility_engine.get_pathways("Software Developers", limit=5)
        assert res.status == "ready"
        for p in res.pathways:
            shared_set = set(p.shared_skills)
            add_set = set(p.additional_destination_skills)
            # Shared and additional must be strictly disjoint
            assert shared_set.isdisjoint(add_set), f"Overlap between shared and additional in {p.destination_occupation_title}"

    def test_career_mobility_tiers_no_unsupported_claims(self, mobility_engine):
        """Scope 3: Mobility pathways must not claim transitions are easy, immediate, or guaranteed."""
        res = mobility_engine.get_pathways("Software Developers", limit=5)
        assert res.status == "ready"
        for p in res.pathways:
            nature_lower = p.relationship_nature.lower()
            assert "immediate transferable" not in nature_lower
            assert "easy" not in nature_lower
            assert "guaranteed" not in nature_lower

        for lim in res.limitations:
            lim_lower = lim.lower()
            assert "guaranteed" in lim_lower or "immediate" in lim_lower or "similarity" in lim_lower

    def test_career_mobility_exact_onet_counts_and_canonical_partition(self, mobility_engine, ref_store):
        """Section 3: Verify with real local SQLite data that Software Developers -> Computer Systems Analysts
        satisfies exact canonical intersection and difference without merging unrelated skills."""
        res = mobility_engine.get_pathways("Software Developers", limit=10)
        assert res.status == "ready"
        analyst_p = next((p for p in res.pathways if p.destination_soc_code == "15-1211.00"), None)
        assert analyst_p is not None
        assert analyst_p.relatedness_tier == "Primary-Short"

        # Verify against direct SQLite counts
        with ref_store._connect() as conn:
            s_rows = conn.execute(
                "SELECT DISTINCT workplace_example FROM ref_onet_software_skills WHERE soc_code = '15-1252.00'"
            ).fetchall()
            d_rows = conn.execute(
                "SELECT DISTINCT workplace_example FROM ref_onet_software_skills WHERE soc_code = '15-1211.00'"
            ).fetchall()

        s_raw = {r["workplace_example"] for r in s_rows}
        d_raw = {r["workplace_example"] for r in d_rows}
        assert len(s_raw) == 430
        assert len(d_raw) == 311

        from app.analytics.skill_registry import normalize_skill_entry
        s_can = {normalize_skill_entry(s).display_name if normalize_skill_entry(s).is_known else s.strip() for s in s_raw}
        d_can = {normalize_skill_entry(s).display_name if normalize_skill_entry(s).is_known else s.strip() for s in d_raw}

        # Canonical normalization resolves duplicate variants (e.g. Spring Framework + Spring Boot -> Spring)
        assert len(s_can) == 429
        assert len(d_can) == 310

        expected_shared = s_can & d_can
        expected_add = d_can - s_can
        assert len(expected_shared) == 247
        assert len(expected_add) == 63
        assert expected_shared.isdisjoint(expected_add)
        assert expected_shared | expected_add == d_can

        assert set(analyst_p.shared_skills) == expected_shared
        assert set(analyst_p.additional_destination_skills) == expected_add
        assert set(analyst_p.shared_skills).isdisjoint(analyst_p.additional_destination_skills)
        assert set(analyst_p.shared_skills) | set(analyst_p.additional_destination_skills) == d_can

    def test_mobility_pathways_unknown_role(self, mobility_engine):
        """Unknown role returns clean insufficient data status."""
        res = mobility_engine.get_pathways("Galactic Starship Captain 99")
        assert res.status == "insufficient_data"
        assert len(res.pathways) == 0


# ---------------------------------------------------------------------------
# 5. Direct API Endpoints Tests & Negative Authorization
# ---------------------------------------------------------------------------

class TestReferenceApiEndpoints:
    def test_guest_answer_success_response_is_isolated(self, client, monkeypatch):
        from app.api.routes.core_intelligence import get_execution_orchestrator_service
        from app.storage.conversation_store import ConversationStore

        local_conversations = ConversationStore()
        monkeypatch.setattr(
            ConversationStore,
            "get_instance",
            classmethod(lambda cls: local_conversations),
        )
        monkeypatch.setattr("app.core.firebase.get_firestore_client", lambda: None)
        service = get_execution_orchestrator_service()
        monkeypatch.setitem(
            app.dependency_overrides,
            get_execution_orchestrator_service,
            lambda: service,
        )
        response = client.post(
            "/api/v1/intelligence/guest/answer",
            json={
                "message": "What are the related skills for Python?",
                "portal_type": "individual",
                "domain": "skill",
                "conversation_id": "private-conversation-sentinel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] is None
        assert "private-conversation-sentinel" not in response.text
        assert data["status"] in {"ready", "partial"}
        assert data["answer_origin"] == "deterministic"
        assert "related_skills" in data["capabilities_used"]
        assert "Top Related Skills for Python" in data["answer"]
        assert "Django" in data["answer"]
        assert local_conversations._conversations == {}

    def test_guest_reference_bodies_contain_no_private_or_tenant_data(self, client):
        urls = [
            "/api/v1/intelligence/guest/sources",
            "/api/v1/intelligence/reference/lookup?query=Python&entity_type=skill",
            "/api/v1/intelligence/reference/related-skills?skill_name=Python&limit=3",
            "/api/v1/intelligence/reference/mobility-pathways?occupation=Software%20Developers&limit=2",
        ]
        forbidden = {"user_id", "uid", "profile", "conversation", "employee_records", "company_id", "tenant_id"}
        def response_keys(value):
            if isinstance(value, dict):
                return {str(key).casefold() for key in value} | set().union(
                    *(response_keys(child) for child in value.values())
                )
            if isinstance(value, list):
                return set().union(*(response_keys(child) for child in value)) if value else set()
            return set()
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200, url
            body = response.json()
            assert not (response_keys(body) & forbidden), (url, body)

    def test_guest_answer_rejects_spoofed_private_fields_without_echo(self, client):
        cases = [
            ("company_id", "private-company-sentinel", 403),
            ("conversation_id", "private-conversation-sentinel", 200),
            ("profile", {"email": "private@example.invalid"}, 422),
        ]
        for field, value, expected_status in cases:
            response = client.post(
                "/api/v1/intelligence/guest/answer",
                json={"message": "public skill lookup", "portal_type": "individual", field: value},
            )
            assert response.status_code == expected_status
            if field == "conversation_id" and response.status_code == 200:
                assert response.json()["conversation_id"] is None
            assert "private-company-sentinel" not in response.text
            assert "private-conversation-sentinel" not in response.text
            assert "private@example.invalid" not in response.text

    def test_guest_answer_payload_is_closed_schema(self, client):
        response = client.post(
            "/api/v1/intelligence/guest/answer",
            json={"message": "public lookup", "portal_type": "individual", "unexpected": "sentinel"},
        )
        assert response.status_code == 422
        assert "sentinel" not in response.text
        malformed = client.post(
            "/api/v1/intelligence/guest/answer",
            content='{"message":',
            headers={"Content-Type": "application/json"},
        )
        assert malformed.status_code == 422
        assert "json decode error" in malformed.text.casefold()

    def test_api_reference_lookup(self, client):
        """GET /api/v1/intelligence/reference/lookup returns public taxonomy data only."""
        resp = client.get("/api/v1/intelligence/reference/lookup?query=Python&entity_type=skill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["total_matches"] >= 1
        assert any(r["name"] == "Python" for r in data["results"])
        # Privacy check: no private identity or workforce records
        assert "user_id" not in data and "company_id" not in data and "employees" not in data

    def test_api_reference_lookup_ambiguous(self, client):
        """GET /api/v1/intelligence/reference/lookup for ambiguous term requires clarification."""
        resp = client.get("/api/v1/intelligence/reference/lookup?query=go&entity_type=skill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["clarification_needed"] is True
        assert data["status"] == "ambiguous"

    def test_api_reference_related_skills(self, client):
        """GET /api/v1/intelligence/reference/related-skills returns public O*NET related skills only."""
        resp = client.get("/api/v1/intelligence/reference/related-skills?skill_name=Python&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert len(data["related_skills"]) == 5
        assert all("relationship_type" in s for s in data["related_skills"])
        # Privacy check: no private identity or workforce records
        assert "user_id" not in data and "company_id" not in data

    def test_api_reference_role_alignment(self, client):
        """POST /api/v1/intelligence/reference/role-alignment returns public alignment with disclaimers."""
        payload = {
            "target_role": "Software Developers",
            "declared_skills": ["Python", "SQL", "Git"],
        }
        resp = client.post("/api/v1/intelligence/reference/role-alignment", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert len(data["matched_skills"]) > 0
        assert "disclaimer" in data
        assert "not be interpreted as verified live employer requirements" in data["disclaimer"]

    def test_api_reference_mobility_pathways(self, client):
        """GET /api/v1/intelligence/reference/mobility-pathways returns public mobility pathways only."""
        resp = client.get("/api/v1/intelligence/reference/mobility-pathways?occupation=Software%20Developers&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert len(data["pathways"]) > 0
        assert data["pathways"][0]["relatedness_tier"] in {"Primary-Short", "Primary-Long", "Supplemental"}
        assert "user_id" not in data and "company_id" not in data

    def test_api_guest_answer_get(self, client):
        """GET /api/v1/intelligence/guest/answer executes public reference intelligence without auth."""
        resp = client.get("/api/v1/intelligence/guest/answer?message=What+are+the+related+skills+for+Python%3F&domain=skill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in {"ready", "partial"}
        assert data["conversation_id"] is None
        assert "Python" in data["answer"] or len(data.get("facts", [])) > 0

    def test_api_guest_answer_post_public_success(self, client):
        """POST /api/v1/intelligence/guest/answer executes public reference request."""
        payload = {
            "message": "Lookup canonical taxonomy details for Python",
            "domain": "skill",
            "portal_type": "individual",
        }
        resp = client.post("/api/v1/intelligence/guest/answer", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in {"ready", "partial"}
        assert data["conversation_id"] is None

    def test_negative_auth_reference_endpoint_forbids_extra_private_fields(self, client):
        """Scope 5: Reference role alignment forbids extra private/company fields (extra='forbid')."""
        payload = {
            "target_role": "Software Developers",
            "declared_skills": ["Python"],
            "company_id": "secret_corp_123",
            "portal_type": "company",
        }
        resp = client.post("/api/v1/intelligence/reference/role-alignment", json=payload)
        assert resp.status_code == 422  # Pydantic extra='forbid' validation error

    def test_negative_auth_guest_answer_rejects_company_and_private_capabilities(self, client):
        """Scope 5: Guest answer rejects company portal, company_id, and private capability requests."""
        # 1. Reject portal_type="company"
        resp_company = client.post(
            "/api/v1/intelligence/guest/answer",
            json={"message": "company skills", "portal_type": "company", "domain": "skill"},
        )
        assert resp_company.status_code == 403

        # 2. Reject company_id
        resp_company_id = client.post(
            "/api/v1/intelligence/guest/answer",
            json={"message": "our skills", "portal_type": "individual", "company_id": "corp_xyz", "domain": "skill"},
        )
        assert resp_company_id.status_code == 403

        # 3. Reject private capability
        resp_private_cap = client.post(
            "/api/v1/intelligence/guest/answer",
            json={"message": "analyze company workforce", "portal_type": "individual", "capability_id": "company_intelligence", "domain": "skill"},
        )
        assert resp_private_cap.status_code == 403

    def test_negative_auth_all_private_endpoints_require_authentication(self, client):
        """Scope 5: All private data endpoints enforce 401 Unauthorized without authentication token."""
        private_endpoints = [
            ("GET", "/api/v1/intelligence/conversations"),
            ("POST", "/api/v1/intelligence/conversations", {"portal_type": "individual"}),
            ("POST", "/api/v1/intelligence/core", {"portal_type": "individual", "intelligence_type": "skill"}),
            ("POST", "/api/v1/intelligence/actions", {"portal_type": "individual", "intelligence_type": "skill"}),
            ("GET", "/api/v1/intelligence/skill"),
            ("GET", "/api/v1/intelligence/job"),
            ("GET", "/api/v1/intelligence/market"),
        ]
        for item in private_endpoints:
            method = item[0]
            url = item[1]
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json=item[2])
            assert resp.status_code in {401, 403}, f"Endpoint {url} failed auth enforcement: {resp.status_code}"
            body = resp.json()
            assert isinstance(body, dict)
            assert set(body) <= {"detail"}
            assert not any(token in resp.text.casefold() for token in (
                "private-user-sentinel", "private-company-sentinel", "private-conversation-sentinel",
                "profile", "conversation contents", "employee records",
            ))


# ---------------------------------------------------------------------------
# 6. Natural Language / Orchestrator Integration Tests
# ---------------------------------------------------------------------------

class TestV2OrchestratorReferenceIntegration:
    def test_orchestrator_routes_taxonomy_lookup_query(self):
        """Natural language query for skill lookup routes through V2 orchestrator."""
        orchestrator = V2Orchestrator()
        req = CoreIntelligenceAnswerRequest(
            message="Lookup canonical ID for Python and its definition in official taxonomies",
            portal_type="individual",
            domain="skill",
        )
        resp = orchestrator.execute_request(req)
        assert resp.status in {"ready", "partial"}
        assert resp.executed_primary_capability in {"skill_lookup", "skill_reference_profile"}
        assert "Python" in resp.answer
        assert len(resp.facts) > 0

    def test_orchestrator_routes_related_skills_query(self):
        """Natural language query for related skills routes through related_skills capability."""
        orchestrator = V2Orchestrator()
        req = CoreIntelligenceAnswerRequest(
            message="What are the related skills and tool associations for Python?",
            portal_type="individual",
            domain="skill",
            selected_skills=["Python"],
        )
        resp = orchestrator.execute_request(req)
        assert resp.status in {"ready", "partial"}
        assert resp.executed_primary_capability in {"related_skills", "skill_reference_profile"}
        assert "Related Skills" in resp.answer or "Python" in resp.answer
        assert len(resp.facts) > 0

    def test_orchestrator_routes_mobility_pathways_query(self):
        """Natural language query for career transition routes through mobility pathways."""
        orchestrator = V2Orchestrator()
        req = CoreIntelligenceAnswerRequest(
            message="Show career transition mobility pathways from Software Developers",
            portal_type="individual",
            domain="job",
            target_role="Software Developers",
        )
        resp = orchestrator.execute_request(req)
        assert resp.status in {"ready", "partial"}
        assert resp.executed_primary_capability in {"job_mobility_pathways", "career_mobility_pathways"}
        assert "Mobility Pathways" in resp.answer or "adjacent" in resp.answer.lower()
        assert len(resp.facts) > 0
