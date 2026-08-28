"""
Hallucination Detection & Clinical Verification Package
Provides multi-tier verification for healthcare AI outputs:
- Knowledge Retriever (PubMed & Clinical Evidence Store)
- Self-Consistency Analyzer (Multi-path consensus)
- Fact Checker (Claim extraction & NLI factual verification)
- Decision Engine (Safety gating: Verified / Warning / Blocked)
"""

from .knowledge_retriever import MedicalKnowledgeRetriever, MedicalEvidence
from .self_consistency import SelfConsistencyAnalyzer, ConsistencyResult
from .fact_checker import FactChecker, FactCheckReport, ClinicalClaim
from .decision_engine import HallucinationDecisionEngine, VerificationDecision, SafetyStatus

__all__ = [
    "MedicalKnowledgeRetriever",
    "MedicalEvidence",
    "SelfConsistencyAnalyzer",
    "ConsistencyResult",
    "FactChecker",
    "FactCheckReport",
    "ClinicalClaim",
    "HallucinationDecisionEngine",
    "VerificationDecision",
    "SafetyStatus"
]
