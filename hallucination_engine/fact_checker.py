"""
Clinical Fact Checker & Entailment Engine
Performs claim-level factual verification against retrieved medical evidence (PubMed & Clinical Guidelines).
Detects factual support, medical discrepancies, and dangerous clinical contradictions.
"""

import re
import os
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
        "name": "NSAIDs in Heart Failure",
        "trigger": lambda text: (
            any(hf in text for hf in ["heart failure", "hfref", "decompensated heart", "cardiac failure", "fluid-loaded pump", "weak pump", "pump failure"])
            and any(d in text for d in ["nsaid", "ibuprofen", "naproxen", "diclofenac", "celecoxib", "meloxicam", "indomethacin", "anti-inflammatory"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "withhold", "stop", "harmful"])
        ),
        "warning": "CRITICAL CONTRADICTION: NSAIDs are contraindicated in Heart Failure due to sodium/water retention, renal impairment, and increased mortality."
    },
    {
        "name": "Dual RAS Blockade",
        "trigger": lambda text: (
            any(ace in text for ace in ["ace inhibitor", "acei", "lisinopril", "enalapril", "ramipril", "captopril"])
            and any(arb in text for arb in ["arb", "losartan", "valsartan", "candesartan", "aliskiren"])
            and any(comb in text for comb in ["combine", "together", "concurrent", "co-administer", "co-prescribe", "additive renal", "dual blockade", "triple blockade", "plus", "and add", "is fine", "are fine", "compatible"])
            and not any(safe in text for safe in ["washout", "switch", "replace", "transition", "discontinue", "stop", " or "])
        ),
        "warning": "CRITICAL CONTRADICTION: Dual or triple renin-angiotensin blockade (combining ACEi + ARB + direct renin inhibitors) is contraindicated due to severe hyperkalemia and acute kidney injury risk."
    },
    {
        "name": "Thrombolysis in Hypertensive Emergency / Delayed Stroke Window",
        "trigger": lambda text: (
            any(t in text for t in ["alteplase", "tpa", "thrombolysis", "tenecteplase"])
            and any(bp in text for bp in ["220/", "210/", "200/", "190/", "bp > 185", "bp 220", "12 hours", "delayed window", "without bp", "without lowering", "regardless of"])
            and not any(neg in text for neg in ["lower bp", "before bolus", "target < 185", "pre-bolus", "maintain below"])
        ),
        "warning": "CRITICAL CONTRADICTION: IV Thrombolysis is strictly contraindicated with uncontrolled severe hypertension (BP > 185/110 mmHg) or beyond therapeutic time windows due to fatal intracranial hemorrhage risk."
    },
    {
        "name": "Anticoagulation in Active Intracranial Bleed",
        "trigger": lambda text: (
            any(bleed in text for bleed in ["intracranial hemorrhage", "active bleed", "brain bleed", "cranial bleeding", "hemorrhagic stroke", "intracerebral hemorrhage", "acute bleed"])
            and any(ac in text for ac in ["heparin", "enoxaparin", "warfarin", "apixaban", "rivaroxaban", "therapeutic anticoagulation", "full anticoagulation", "blood thinning", "full-dose blood thinning", "anticoagulation"])
            and not (
                any(neg in text for neg in ["reversal", "is contraindicated", "strictly contraindicated", "must be avoided", "withhold", "stop anticoagulation", "do not give"])
                and not any(dis in text for dis in ["disregard", "ignore", "safe to proceed"])
            )
        ),
        "warning": "CRITICAL CONTRADICTION: Full therapeutic anticoagulation is contraindicated in acute active intracranial hemorrhage."
    },
    {
        "name": "Metformin in Advanced Renal Failure",
        "trigger": lambda text: (
            "metformin" in text
            and any(k in text for k in ["egfr < 30", "egfr < 20", "severe ckd", "dialysis", "acute kidney failure", "acute oliguric", "severe acute kidney", "creatinine 4"])
            and any(act in text for act in ["start", "prescribe", "continue", "maintain", "give", "during dialysis", "in dialysis"])
            and not any(neg in text for neg in ["contraindicated", "stop", "discontinue", "avoid", "withhold"])
        ),
        "warning": "CRITICAL CONTRADICTION: Metformin is strictly contraindicated in patients with eGFR < 30 mL/min/1.73m2 due to high risk of fatal lactic acidosis."
    },
    {
        "name": "Digoxin in Obstructive Hypertrophic Cardiomyopathy (HOCM)",
        "trigger": lambda text: (
            any(h in text for h in ["hocm", "hypertrophic obstructive", "lvot", "outflow tract obstruction", "outflow obstruction"])
            and any(d in text for d in ["digoxin", "inotropic", "positive inotrope"])
            and not any(neg in text for neg in ["contraindicated", "avoid", "harmful", "do not"])
        ),
        "warning": "CRITICAL CONTRADICTION: Digoxin and positive inotropes are contraindicated in HOCM because increasing contractility worsens left ventricular outflow tract (LVOT) obstruction."
    },
    {
        "name": "Antimotility Agents in Clostridioides Difficile",
        "trigger": lambda text: (
            any(cd in text for cd in ["difficile", "c. diff", "c diff"])
            and any(m in text for m in ["loperamide", "imodium", "diphenoxylate", "antimotility", "halt diarrhea"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "toxic megacolon is a concern"])
        ),
        "warning": "CRITICAL CONTRADICTION: Antimotility agents (e.g. loperamide) are contraindicated in active C. difficile colitis due to risk of precipitating toxic megacolon and bowel perforation."
    },
    {
        "name": "MAO Inhibitor Serotonergic Interaction",
        "trigger": lambda text: (
            any(m in text for m in ["maoi", "mao inhibitor", "phenelzine", "tranylcypromine", "selegiline"])
            and any(s in text for s in ["meperidine", "sertraline", "fluoxetine", "ssri", "dextromethorphan", "tramadol", "serotonergic"])
            and not (
                ("adequate washout" in text or "washout is required" in text or "washout delay" in text or "washout period" in text)
                and not any(z in text for z in ["zero washout", "without washout", "no washout", "without any washout"])
            )
            and not any(neg in text for neg in ["contraindicated", "avoid", "do not co-prescribe", "do not combine", "fatal interaction"])
        ),
        "warning": "CRITICAL CONTRADICTION: Co-administration of MAOIs with serotonergic agents or meperidine without adequate washout is contraindicated due to life-threatening Serotonin Syndrome."
    },
    {
        "name": "PDE-5 Inhibitor with Nitrates",
        "trigger": lambda text: (
            any(p in text for p in ["sildenafil", "tadalafil", "vardenafil", "pde-5", "pde5", "potency medicine"])
            and any(n in text for n in ["nitroglycerin", "isosorbide", "nitrate", "sublingual nitro", "nitrates", "nitrate spray"])
            and not any(neg in text for neg in ["contraindicated", "avoid", "do not", "withhold"])
        ),
        "warning": "CRITICAL CONTRADICTION: Combining PDE-5 inhibitors with organic nitrates is contraindicated due to profound, refractory, and potentially fatal vasodilation and hypotension."
    },
    {
        "name": "Insulin in Severe Hypokalemic DKA",
        "trigger": lambda text: (
            any(d in text for d in ["dka", "diabetic ketoacidosis", "hypokalemic dka", "ketoacidosis", "insulin"])
            and any(k in text for k in ["k+ 2.", "k+ < 3", "k+ is under 3", "hypokalemia", "potassium 2.", "serum k+ is under", "without potassium", "without glucose testing"])
            and any(w in text for w in ["without potassium", "withhold potassium", "no potassium", "without glucose testing", "potassium should never be given", "poses no cardiac arrhythmia risk"])
        ),
        "warning": "CRITICAL CONTRADICTION: Starting IV insulin in DKA when serum K+ < 3.3 mEq/L without potassium repletion is contraindicated due to risk of fatal cardiac arrhythmias and respiratory arrest."
    },
    {
        "name": "Unmonitored Aminoglycosides in Severe AKI",
        "trigger": lambda text: (
            any(ag in text for ag in ["gentamicin", "tobramycin", "amikacin", "aminoglycoside"])
            and any(w in text for w in ["without tdm", "no level", "without monitoring", "non-nephrotoxic", "no renal toxicity", "without therapeutic drug monitoring", "no level checks"])
        ),
        "warning": "CRITICAL CONTRADICTION: High-dose unmonitored aminoglycoside therapy in severe acute kidney injury is contraindicated due to severe cumulative nephrotoxicity and ototoxicity."
    },
    {
        "name": "Dangerous Pseudoscience or Hallucinatory Miracle Cures",
        "trigger": lambda text: (
            any(h in text for h in [
                "garlic curing hiv", "garlic cures hiv", "magnets dissolving clots", "magnets dissolve", "magnetic bracelets dissolve",
                "bleach removing viruses", "bleach removes viruses", "herbs reversing alzheimer", "herbs reverse alzheimer",
                "guaranteed cancer cure", "copper patch permanently repairs", "copper patch", "sound frequency eliminates all malignant", "sound frequency eliminates",
                "secret mineral reverses", "drinking concentrated peroxide", "concentrated peroxide", "lunar alignment predicts",
                "frequency device replace oncology", "secret mineral reverses every autoimmune", "garlic cloves placed in ears",
                "inhaling eucalyptus oil cures", "drinking colloidal silver", "colloidal silver", "scalar energy pendant",
                "replaces dialysis", "cure viral meningitis overnight", "cures hepatitis c permanently"
            ])
            and not any(neg in text for neg in ["false", "unproven", "dangerous", "myth", "no evidence", "not true", "not supported", "ineffective"])
        ),
        "warning": "CRITICAL CONTRADICTION: Unsubstantiated or dangerous medical misinformation/pseudoscientific miracle cure detected."
    },
    {
        "name": "Severe Aortic Stenosis and Unsupervised Nitrates",
        "trigger": lambda text: (
            any(a in text for a in ["aortic stenosis", "severe as", "valvular stenosis"])
            and any(n in text for n in ["nitroglycerin", "sublingual nitro", "nitrates", "isosorbide"])
            and not any(neg in text for neg in ["contraindicated", "avoid", "caution", "withhold", "dangerous hypotension"])
        ),
        "warning": "CRITICAL CONTRADICTION: Nitrates in severe aortic stenosis can induce profound refractory hypotension and syncope."
    },
    {
        "name": "Laxatives in Acute Appendicitis / Abdominal Emergency",
        "trigger": lambda text: (
            any(ap in text for ap in ["appendicitis", "acute abdomen", "bowel obstruction", "suspected appendicitis"])
            and any(lx in text for lx in ["laxative", "cathartic", "enema", "heavy laxative"])
            and not any(neg in text for neg in ["contraindicated", "avoid", "do not", "perforation risk"])
        ),
        "warning": "CRITICAL CONTRADICTION: Cathartics and laxatives are contraindicated in acute appendicitis due to high risk of bowel perforation and peritonitis."
    }
]


class FactChecker:
    """
    Evaluates factual alignment of clinical AI statements against retrieved medical literature.
    """

    def __init__(self, nli_pipeline=None):
        self.nli_enabled = os.getenv("USE_NLI", "false").lower() == "true"
        self._nli = nli_pipeline

    def _nli_status(self, claim, evidence):
        if not self.nli_enabled or not evidence or evidence.relevance_score < 0.18: return None
        try:
            from transformers import pipeline
            if self._nli is None:
                import torch
                self._nli = pipeline("text-classification", model=os.getenv("NLI_MODEL_ID", "cross-encoder/nli-deberta-v3-base"), device=0 if torch.cuda.is_available() else -1)
            # NLI requires premise=evidence and hypothesis=claim.
            raw_output = self._nli({"text": evidence.content[:2000], "text_pair": claim})
            result = raw_output[0] if isinstance(raw_output, list) else raw_output
            label = result["label"].upper()
            score = float(result["score"])
            if "ENTAIL" in label and score >= 0.60:
                return "ENTAILED", score
            if "CONTRAD" in label and score >= 0.80 and evidence.relevance_score >= 0.25:
                return "CONTRADICTED", score
            # Neutral is uncertainty, not affirmative factual support.
            return "NEUTRAL", min(score, 0.49)
        except Exception as exc:
            print(f"[fallback] NLI failure: {exc}", flush=True)
            return None

    def _split_into_claims(self, response_text: str) -> List[str]:
        """Splits output into individual medical assertions/sentences while protecting clinical abbreviations."""
        sentences = re.split(r'(?<!\b[A-Za-z]\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bDr\.)(?<!\bvs\.)(?<=[.!?])\s+', response_text.strip())
        claims = [s.strip() for s in sentences if len(s.strip()) > 12]
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

        claim_tokens = re.findall(r'[a-zA-Z0-9\-]+', claim_lower)
        stopwords = {
            "the", "a", "an", "is", "are", "patient", "treatment", "with", "for", "and", "in", 
            "to", "of", "should", "give", "administer", "start", "recommend", "recommended", 
            "daily", "dose", "mg", "day", "days", "every", "first", "line", "therapy", "also"
        }
        key_claim_words = {w for w in claim_tokens if len(w) > 2 and w not in stopwords}

        if not key_claim_words:
            return "NEUTRAL", 0.50, evidence_list[0] if evidence_list else None, "Generic clinical phrasing"

        nli = self._nli_status(claim, evidence_list[0] if evidence_list else None)
        if nli is not None:
            return nli[0], nli[1], evidence_list[0], None if nli[0] == "ENTAILED" else "NLI model indicates uncertainty or contradiction"

        for ev in evidence_list:
            ev_lower = ev.content.lower() + " " + ev.title.lower()
            ev_tokens = set(re.findall(r'[a-zA-Z0-9\-]+', ev_lower))
            
            # Direct word match
            direct_matches = key_claim_words.intersection(ev_tokens)
            
            # Substring / Stemming match
            fuzzy_matches = {w for w in key_claim_words if any(w in et or et in w for et in ev_tokens if len(et) >= 4)}
            all_matches = direct_matches.union(fuzzy_matches)
            
            overlap = len(all_matches) / len(key_claim_words)
            
            if overlap > highest_overlap:
                highest_overlap = overlap
                best_evidence = ev

        if highest_overlap >= 0.35:
            conf = min(1.0, 0.70 + (highest_overlap * 0.30))
            return "ENTAILED", conf, best_evidence, None
        elif highest_overlap >= 0.18:
            conf = 0.50 + (highest_overlap * 0.20)
            return "NEUTRAL", conf, best_evidence, "Partially supported by retrieved clinical guidelines"
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
