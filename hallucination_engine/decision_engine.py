"""
Hallucination Decision Engine & Safety Gating
Synthesizes Self-Consistency, PubMed Retrieval Relevance, and Factual Entailment
into a single clinical safety verdict: VERIFIED_SAFE, CLINICAL_WARNING, or BLOCKED_HALLUCINATION.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .knowledge_retriever import MedicalKnowledgeRetriever, MedicalEvidence
from .self_consistency import SelfConsistencyAnalyzer, ConsistencyResult
from .fact_checker import FactChecker, FactCheckReport, ClinicalClaim


class SafetyStatus(str, Enum):
    VERIFIED_SAFE = "VERIFIED_SAFE"           # Safe to show to clinician with high confidence
    CLINICAL_WARNING = "CLINICAL_WARNING"     # Show with caution & confidence warnings
    BLOCKED_HALLUCINATION = "BLOCKED"         # Dangerous contradiction or ungrounded hallucination blocked


@dataclass
class VerificationDecision:
    status: SafetyStatus
    composite_confidence: float  # 0.0 to 1.0 (or 0% to 100%)
    action: str                  # "ALLOW", "WARN", "BLOCK"
    recommendation_text: str     # Verified text or safe clinical alternative
    self_consistency_score: float
    evidence_relevance_score: float
    factual_entailment_score: float
    critical_contradiction_found: bool
    evidence_citations: List[Dict[str, Any]]
    claims_breakdown: List[Dict[str, Any]]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class HallucinationDecisionEngine:
    """
    Comprehensive Hallucination Decision Gate.
    Integrates:
    1. Self-Consistency Multi-Path consensus
    2. PubMed / Clinical guideline retrieval
    3. Factual entailment & contraindication verification
    """

    def __init__(
        self,
        retriever: Optional[MedicalKnowledgeRetriever] = None,
        consistency_analyzer: Optional[SelfConsistencyAnalyzer] = None,
        fact_checker: Optional[FactChecker] = None,
        safe_threshold: float = 0.72,
        warn_threshold: float = 0.48
    ):
        self.retriever = retriever or MedicalKnowledgeRetriever()
        self.consistency_analyzer = consistency_analyzer or SelfConsistencyAnalyzer()
        self.fact_checker = fact_checker or FactChecker()
        self.safe_threshold = safe_threshold
        self.warn_threshold = warn_threshold

    def evaluate_response(
        self,
        query: str,
        candidate_responses: List[str]
    ) -> VerificationDecision:
        """
        Executes complete 3-tier hallucination detection on candidate model inferences.
        """
        if not candidate_responses:
            return VerificationDecision(
                status=SafetyStatus.BLOCKED_HALLUCINATION,
                composite_confidence=0.0,
                action="BLOCK",
                recommendation_text="Error: No clinical model responses provided for verification.",
                self_consistency_score=0.0,
                evidence_relevance_score=0.0,
                factual_entailment_score=0.0,
                critical_contradiction_found=True,
                evidence_citations=[],
                claims_breakdown=[],
                explanation="Input generation was empty."
            )

        primary_response = candidate_responses[0]

        # 1. Tier 1: Multi-Path Self-Consistency Analysis
        consistency_res = self.consistency_analyzer.evaluate_consensus(candidate_responses)
        s_cons = consistency_res.consensus_score

        # 2. Tier 2: PubMed / Clinical Evidence Retrieval
        evidence_list = self.retriever.retrieve(query + " " + primary_response, top_k=3)
        top_relevance = evidence_list[0].relevance_score if evidence_list else 0.0
        s_ret = min(1.0, top_relevance * 1.4)

        # 3. Tier 3: Claim-Level Factual Entailment & Red-Flag Checks
        fact_report = self.fact_checker.check_factual_accuracy(primary_response, evidence_list)
        s_ent = fact_report.overall_factual_score

        # 4. Composite Confidence Score Calculation
        # Weights: 40% Factual Entailment + 35% PubMed Retrieval Evidence + 25% Self-Consistency
        composite_score = (0.40 * s_ent) + (0.35 * s_ret) + (0.25 * s_cons)

        # Severe penalty if critical contraindication detected
        if fact_report.has_critical_contradiction:
            composite_score = min(composite_score, 0.15)

        composite_score = round(composite_score, 4)

        # 5. Gating Decision Logic
        citations = [
            {
                "source_id": ev.source_id,
                "title": ev.title,
                "category": ev.category,
                "relevance": ev.relevance_score,
                "url": ev.url,
                "summary": ev.content[:160] + "..."
            }
            for ev in evidence_list if ev.relevance_score > 0.10
        ]

        claims_breakdown = [
            {
                "claim": c.claim_text,
                "status": c.entailment_status,
                "confidence": c.confidence,
                "evidence_source": c.supporting_evidence_pmid,
                "conflict": c.conflict_reason
            }
            for c in fact_report.claims
        ]

        if fact_report.has_critical_contradiction or composite_score < self.warn_threshold:
            status = SafetyStatus.BLOCKED_HALLUCINATION
            action = "BLOCK"
            explanation = (
                "Response BLOCKED: Output contains medical hallucinations or critical clinical contraindications "
                f"(Confidence: {round(composite_score*100, 1)}%). Ground-truth medical guidelines contradict the assertion."
            )
            # Provide safe verified guideline snippet if available
            safe_alt = (
                f"[SAFETY INTERVENTION - RESPONSE BLOCKED]\n"
                f"Reason: Model proposed a potentially harmful recommendation.\n"
                f"Clinical Guideline Evidence ({evidence_list[0].source_id} - {evidence_list[0].title}):\n"
                f"\"{evidence_list[0].content}\""
            ) if evidence_list else "Output blocked due to lack of medical grounding."
            recommendation_text = safe_alt

        elif composite_score < self.safe_threshold:
            status = SafetyStatus.CLINICAL_WARNING
            action = "WARN"
            explanation = (
                f"Clinical Warning: Output has moderate confidence ({round(composite_score*100, 1)}%) "
                "with minor evidence divergence. Physician review strongly advised."
            )
            recommendation_text = primary_response

        else:
            status = SafetyStatus.VERIFIED_SAFE
            action = "ALLOW"
            explanation = (
                f"Response VERIFIED: High confidence ({round(composite_score*100, 1)}%). "
                "Consistent reasoning and fully grounded in peer-reviewed medical guidelines."
            )
            recommendation_text = primary_response

        return VerificationDecision(
            status=status,
            composite_confidence=composite_score,
            action=action,
            recommendation_text=recommendation_text,
            self_consistency_score=round(s_cons, 4),
            evidence_relevance_score=round(s_ret, 4),
            factual_entailment_score=round(s_ent, 4),
            critical_contradiction_found=fact_report.has_critical_contradiction,
            evidence_citations=citations,
            claims_breakdown=claims_breakdown,
            explanation=explanation
        )
