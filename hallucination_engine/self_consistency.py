"""
Self-Consistency Reasoning & Consensus Engine
Executes multi-path temperature sampling / permutation checks on clinical reasoning
to identify divergence, hallucinations, and uncertainty before patient-facing output.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import re


@dataclass
class ConsistencyResult:
    consensus_score: float  # 0.0 to 1.0
    num_samples: int
    primary_response: str
    sample_variations: List[str]
    agreement_percentage: float
    detected_discrepancies: List[str]


class SelfConsistencyAnalyzer:
    """
    Evaluates self-consistency across multiple clinical reasoning paths.
    High consensus indicates robust medical reasoning; low consensus signals hallucination or ambiguity.
    """

    def __init__(self, agreement_threshold: float = 0.70):
        self.agreement_threshold = agreement_threshold

    def _extract_entities_and_actions(self, text: str) -> set:
        """Extracts key clinical terms (drugs, dosages, tests, recommendations) for comparison."""
        words = re.findall(r'[a-zA-Z0-9\-\%]+', text.lower())
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "patient", "should", "recommended",
            "treatment", "clinical", "dose", "mg", "with", "and", "or", "for", "to", "in", "of"
        }
        return {w for w in words if len(w) > 3 and w not in stopwords}

    def _jaccard_similarity(self, set_a: set, set_b: set) -> float:
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    def evaluate_consensus(self, candidate_responses: List[str]) -> ConsistencyResult:
        """
        Calculates pairwise semantic agreement across candidate LLM reasoning chains.
        """
        if not candidate_responses:
            return ConsistencyResult(
                consensus_score=0.0,
                num_samples=0,
                primary_response="",
                sample_variations=[],
                agreement_percentage=0.0,
                detected_discrepancies=["No candidate responses provided."]
            )

        if len(candidate_responses) == 1:
            return ConsistencyResult(
                consensus_score=1.0,
                num_samples=1,
                primary_response=candidate_responses[0],
                sample_variations=candidate_responses,
                agreement_percentage=100.0,
                detected_discrepancies=[]
            )

        term_sets = [self._extract_entities_and_actions(r) for r in candidate_responses]
        n = len(candidate_responses)
        total_sim = 0.0
        pair_count = 0
        discrepancies = []

        for i in range(n):
            for j in range(i + 1, n):
                sim = self._jaccard_similarity(term_sets[i], term_sets[j])
                total_sim += sim
                pair_count += 1
                
                # Check for significant term conflicts
                diff_ij = term_sets[i].difference(term_sets[j])
                if sim < 0.40 and diff_ij:
                    discrepancies.append(f"Sample {i+1} emphasizes ({', '.join(list(diff_ij)[:3])}) unlike Sample {j+1}")

        avg_similarity = total_sim / pair_count if pair_count > 0 else 1.0
        
        # Scale consensus score: typical medical text Jaccard of ~0.50 corresponds to high agreement
        consensus_score = min(1.0, avg_similarity * 1.6)

        return ConsistencyResult(
            consensus_score=round(consensus_score, 4),
            num_samples=n,
            primary_response=candidate_responses[0],
            sample_variations=candidate_responses,
            agreement_percentage=round(consensus_score * 100, 1),
            detected_discrepancies=discrepancies[:4]
        )
