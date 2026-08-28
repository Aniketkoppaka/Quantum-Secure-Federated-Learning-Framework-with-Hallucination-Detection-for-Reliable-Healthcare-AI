"""
Clinical Fact Checker & Entailment Engine
Performs claim-level factual verification against retrieved medical evidence (PubMed & Clinical Guidelines).
Detects factual support, medical discrepancies, and dangerous clinical contradictions.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .knowledge_retriever import MedicalEvidence


@dataclass
class ClinicalClaim:
    claim_text: str
    entailment_status: str  # "ENTAILED" (supported), "NEUTRAL" (unverified), "CONTRADICTED" (fatal conflict)
    confidence: float
    supporting_evidence_pmid: Optional[str] = None
    evidence_snippet: Optional[str] = None
    conflict_reason: Optional[str] = None


@dataclass
class FactCheckReport:
    overall_factual_score: float  # 0.0 to 1.0
    claims: List[ClinicalClaim]
    has_critical_contradiction: bool
    evidence_sources_used: List[str]
    summary_verdict: str


# Critical known clinical red flags & contraindications to safeguard against fatal hallucinations
CRITICAL_CONTRAINDICATIONS = [
    {
        "keywords": ["heart failure", "hfref", "nsaid", "ibuprofen", "naproxen"],
        "trigger": lambda text: ("heart failure" in text or "hfref" in text) and ("give nsaid" in text or "prescribe ibuprofen" in text or "recommend naproxen" in text or "administer nsaid" in text),
        "warning": "CRITICAL CONTRADICTION: NSAIDs are contraindicated in Heart Failure due to fluid retention and risk of acute decompensation."
    },
    {
        "keywords": ["ace inhibitor", "arb", "lisinopril", "losartan"],
        "trigger": lambda text: ("ace" in text and "arb" in text and ("combine" in text or "together" in text or "concurrent" in text)),
        "warning": "CRITICAL CONTRADICTION: Dual renin-angiotensin blockade (combining ACEi + ARB) is contraindicated due to increased hyperkalemia and renal failure risk."
    },
    {
        "keywords": ["stroke", "alteplase", "tpa", "blood pressure"],
        "trigger": lambda text: ("alteplase" in text or "tpa" in text) and ("bp > 185" in text or "bp > 200" in text or "hypertension > 185" in text),
        "warning": "CRITICAL CONTRADICTION: Thrombolysis with IV Alteplase is contraindicated if blood pressure is > 185/110 mmHg without prior reduction."
    },
    {
        "keywords": ["metformin", "egfr < 30", "severe ckd"],
        "trigger": lambda text: ("metformin" in text) and ("egfr < 30" in text or "dialysis" in text) and ("start" in text or "prescribe" in text or "continue" in text),
        "warning": "CRITICAL CONTRADICTION: Metformin is strictly contraindicated in patients with eGFR < 30 mL/min/1.73m2 due to lactic acidosis risk."
    }
]


class FactChecker:
    """
    Evaluates factual alignment of clinical AI statements against retrieved medical literature.
    """

    def __init__(self):
        pass

    def _split_into_claims(self, response_text: str) -> List[str]:
        """Splits output into individual medical assertions/sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', response_text.strip())
        claims = [s.strip() for s in sentences if len(s.strip()) > 15]
        return claims if claims else [response_text]

    def _check_critical_contraindications(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for rule in CRITICAL_CONTRAINDICATIONS:
            if rule["trigger"](text_lower):
                return rule["warning"]
        return None

    def _calculate_claim_support(self, claim: str, evidence_list: List[MedicalEvidence]) -> Tuple[str, float, Optional[MedicalEvidence], Optional[str]]:
        claim_lower = claim.lower()

        # 1. First check critical medical contraindications
        conflict = self._check_critical_contraindications(claim)
        if conflict:
            return "CONTRADICTED", 0.0, None, conflict

        # 2. Check overlap and entailment against retrieved evidence
        best_evidence = None
        highest_overlap = 0.0

        claim_words = set(re.findall(r'[a-zA-Z0-9\-]+', claim_lower))
        stopwords = {"the", "a", "an", "is", "are", "patient", "treatment", "with", "for", "and", "in", "to", "of", "should"}
        key_claim_words = {w for w in claim_words if len(w) > 3 and w not in stopwords}

        for ev in evidence_list:
            ev_words = set(re.findall(r'[a-zA-Z0-9\-]+', ev.content.lower()))
            overlap = len(key_claim_words.intersection(ev_words)) / len(key_claim_words) if key_claim_words else 0.0
            
            if overlap > highest_overlap:
                highest_overlap = overlap
                best_evidence = ev

        if highest_overlap >= 0.45:
            return "ENTAILED", min(1.0, highest_overlap * 1.3), best_evidence, None
        elif highest_overlap >= 0.20:
            return "NEUTRAL", 0.50, best_evidence, "Partially supported by retrieved guidelines"
        else:
            return "NEUTRAL", 0.30, None, "Insufficient direct evidence in reference corpus"

    def check_factual_accuracy(
        self,
        response_text: str,
        retrieved_evidence: List[MedicalEvidence]
    ) -> FactCheckReport:
        """
        Extracts claims, validates against evidence, and outputs a factual verification report.
        """
        claim_texts = self._split_into_claims(response_text)
        clinical_claims = []
        sources_used = set()
        has_fatal_contradiction = False
        total_score = 0.0

        for text in claim_texts:
            status, conf, ev, reason = self._calculate_claim_support(text, retrieved_evidence)
            
            pmid = ev.source_id if ev else None
            snippet = (ev.content[:150] + "...") if ev else None
            
            if status == "CONTRADICTED":
                has_fatal_contradiction = True
                conf = 0.0
            elif status == "ENTAILED" and pmid:
                sources_used.add(f"{pmid} ({ev.title})")

            clinical_claims.append(
                ClinicalClaim(
                    claim_text=text,
                    entailment_status=status,
                    confidence=round(conf, 3),
                    supporting_evidence_pmid=pmid,
                    evidence_snippet=snippet,
                    conflict_reason=reason
                )
            )
            total_score += conf

        avg_score = total_score / len(clinical_claims) if clinical_claims else 0.0
        if has_fatal_contradiction:
            avg_score = min(avg_score, 0.15)

        verdict = "FAILS_VERIFICATION" if has_fatal_contradiction else ("HIGH_EVIDENCE" if avg_score >= 0.70 else "MODERATE_EVIDENCE")

        return FactCheckReport(
            overall_factual_score=round(avg_score, 3),
            claims=clinical_claims,
            has_critical_contradiction=has_fatal_contradiction,
            evidence_sources_used=list(sources_used),
            summary_verdict=verdict
        )
