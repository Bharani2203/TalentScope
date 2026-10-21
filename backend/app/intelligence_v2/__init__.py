"""Greenfield Intelligence Engine V2.

Clean, modular, evidence-backed intelligence engine supporting all 15
Skill Intelligence, Market Intelligence, and Job Intelligence features.
"""

from app.intelligence_v2.adapter import V2ExecutionOrchestratorAdapter
from app.intelligence_v2.capability_registry import CAPABILITIES, V2CapabilityRegistry
from app.intelligence_v2.contracts import (
    DataOrigin,
    SignalFamily,
    TimeGrain,
    V2EvidenceItem,
    V2ExecutionStatus,
    V2StructuredFact,
)
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.india_collector_design import V2IndiaCollectorPipeline
from app.intelligence_v2.intent_planner import PlannedIntent, V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.market_intelligence import V2MarketIntelligenceEngine
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.intelligence_v2.role_actions import V2RoleActionEngine
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine
from app.intelligence_v2.skill_mapping import RoleSkillAlignment, SkillMappingResult, V2SkillMapper
from app.intelligence_v2.source_registry import (
    SOURCE_REGISTRY,
    DataIntegrityValidator,
    IntegrityViolationError,
    SourceDefinition,
    SourceMetricDefinition,
    StandardizedObservation,
    V2SourceRegistry,
)

__all__ = [
    "CAPABILITIES",
    "DataOrigin",
    "PlannedIntent",
    "RoleSkillAlignment",
    "SignalFamily",
    "SkillMappingResult",
    "SOURCE_REGISTRY",
    "SourceDefinition",
    "SourceMetricDefinition",
    "StandardizedObservation",
    "TimeGrain",
    "V2CapabilityRegistry",
    "V2EvidenceItem",
    "V2EvidenceRetriever",
    "V2ExecutionOrchestratorAdapter",
    "V2ExecutionStatus",
    "V2IndiaCollectorPipeline",
    "V2IntentPlanner",
    "V2JobIntelligenceEngine",
    "V2MarketIntelligenceEngine",
    "V2Orchestrator",
    "V2ResponseFormatter",
    "V2RoleActionEngine",
    "V2SkillIntelligenceEngine",
    "V2SkillMapper",
    "V2SourceRegistry",
    "V2StructuredFact",
    "DataIntegrityValidator",
    "IntegrityViolationError",
]
