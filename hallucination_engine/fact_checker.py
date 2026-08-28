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
        "name": "NSAIDs in Heart Failure",
        "trigger": lambda text: (
            any(hf in text for hf in ["heart failure", "hfref", "decompensated heart", "cardiac failure"])
            and any(d in text for d in ["nsaid", "ibuprofen", "naproxen", "diclofenac", "celecoxib", "meloxicam", "indomethacin"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "withhold", "stop", "harmful"])
        ),
        "warning": "CRITICAL CONTRADICTION: NSAIDs are contraindicated in Heart Failure due to sodium/water retention, renal impairment, and increased mortality."
    },
    {
        "name": "Dual RAS Blockade",
        "trigger": lambda text: (
            any(ace in text for ace in ["ace inhibitor", "lisinopril", "enalapril", "ramipril", "captopril"])
            and any(arb in text for arb in ["arb", "losartan", "valsartan", "candesartan", "aliskiren"])
            and any(comb in text for comb in ["combine", "together", "concurrent", "co-administer", "co-prescribe", "additive renal", "dual blockade", "triple blockade", "plus", "and add"])
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
            any(bleed in text for bleed in ["intracranial hemorrhage", "active bleed", "brain bleed", "hemorrhagic stroke", "intracerebral hemorrhage", "acute bleed"])
            and any(ac in text for ac in ["heparin", "enoxaparin", "warfarin", "apixaban", "rivaroxaban", "therapeutic anticoagulation", "full anticoagulation"])
            and not any(neg in text for neg in ["reversal", "contraindicated", "avoid", "withhold", "stop", "do not"])
        ),
        "warning": "CRITICAL CONTRADICTION: Full therapeutic anticoagulation is contraindicated in acute active intracranial hemorrhage."
    },
    {
        "name": "Metformin in Advanced Renal Failure",
        "trigger": lambda text: (
            "metformin" in text
            and any(k in text for k in ["egfr < 30", "egfr < 20", "severe ckd", "dialysis", "acute kidney failure", "acute oliguric", "severe acute kidney", "creatinine 4"])
            and any(act in text for act in ["start", "prescribe", "continue", "maintain", "give"])
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
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "toxic megacolon"])
        ),
        "warning": "CRITICAL CONTRADICTION: Antimotility agents (e.g. loperamide) are contraindicated in active C. difficile colitis due to risk of precipitating toxic megacolon and bowel perforation."
    },
    {
        "name": "MAO Inhibitor Serotonergic Interaction",
        "trigger": lambda text: (
            any(m in text for m in ["maoi", "mao inhibitor", "phenelzine", "tranylcypromine", "selegiline"])
            and any(s in text for s in ["meperidine", "sertraline", "fluoxetine", "ssri", "dextromethorphan", "tramadol"])
            and not any(neg in text for neg in ["washout", "contraindicated", "avoid", "do not", "serotonin syndrome"])
        ),
        "warning": "CRITICAL CONTRADICTION: Co-administration of MAOIs with serotonergic agents or meperidine without adequate washout is contraindicated due to life-threatening Serotonin Syndrome."
    },
    {
        "name": "PDE-5 Inhibitor with Nitrates",
        "trigger": lambda text: (
            any(p in text for p in ["sildenafil", "tadalafil", "vardenafil", "pde-5", "pde5"])
            and any(n in text for n in ["nitroglycerin", "isosorbide", "nitrate", "sublingual nitro", "nitrates"])
            and not any(neg in text for neg in ["contraindicated", "avoid", "do not", "withhold"])
        ),
        "warning": "CRITICAL CONTRADICTION: Combining PDE-5 inhibitors with organic nitrates is contraindicated due to profound, refractory, and potentially fatal vasodilation and hypotension."
    },
    {
        "name": "Insulin in Severe Hypokalemic DKA",
        "trigger": lambda text: (
            any(d in text for d in ["dka", "diabetic ketoacidosis"])
            and any(k in text for k in ["k+ 2.", "k+ < 3", "hypokalemia", "potassium 2."])
            and any(w in text for w in ["without potassium", "withhold potassium", "no potassium"])
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
        "name": "Methotrexate with Trimethoprim / TMP-SMX",
        "trigger": lambda text: (
            "methotrexate" in text
            and any(t in text for t in ["tmp-smx", "bactrim", "trimethoprim", "cotrimoxazole", "septra"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "withhold", "stop"])
        ),
        "warning": "CRITICAL CONTRADICTION: Combining Methotrexate with Trimethoprim/TMP-SMX is contraindicated due to synergistic antifolate bone marrow toxicity and fatal pancytopenia."
    },
    {
        "name": "Lithium with ACE Inhibitors",
        "trigger": lambda text: (
            "lithium" in text
            and any(ace in text for ace in ["lisinopril", "enalapril", "ramipril", "captopril", "ace inhibitor", "acei"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not give", "do not prescribe", "withhold", "stop", "monitor level closely", "dose reduction"])
        ),
        "warning": "CRITICAL CONTRADICTION: Co-prescribing Lithium with ACE inhibitors reduces renal lithium clearance by 30-50%, risking severe neurotoxicity and lithium intoxication."
    },
    {
        "name": "Live Attenuated Vaccines in Active Leukemia / Immunosuppression",
        "trigger": lambda text: (
            any(v in text for v in ["live attenuated", "mmr", "varicella", "yellow fever", "live vaccine"])
            and any(c in text for c in ["leukemia", "chemotherapy", "immunosuppressed", "induction", "neutropenia"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not give", "do not administer", "withhold", "stop", "defer"])
        ),
        "warning": "CRITICAL CONTRADICTION: Live attenuated vaccines are strictly contraindicated during active immunosuppression or leukemia induction due to risk of fatal disseminated infection."
    },
    {
        "name": "ACEi and ARBs in Pregnancy",
        "trigger": lambda text: (
            any(d in text for d in ["losartan", "valsartan", "lisinopril", "enalapril", "arb", "ace inhibitor"])
            and any(p in text for p in ["pregnant", "pregnancy", "gestation", "trimester"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not give", "teratogen", "stop", "withhold"])
        ),
        "warning": "CRITICAL CONTRADICTION: ACE inhibitors and ARBs are major teratogens in pregnancy, causing fetal renal dysgenesis, oligohydramnios, and neonatal death."
    },
    {
        "name": "Aspirin in Pediatric Viral Illness (Reye Syndrome)",
        "trigger": lambda text: (
            any(a in text for a in ["aspirin", "acetylsalicylic acid", "bayer"])
            and any(p in text for p in ["pediatric", "child", "children", "influenza", "varicella", "6-year-old", "4-year-old"])
            and any(f in text for f in ["fever", "antipyretic", "viral", "myalgia", "febrile"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not give", "reye syndrome", "kawasaki"])
        ),
        "warning": "CRITICAL CONTRADICTION: Aspirin is contraindicated in pediatric viral illnesses due to high risk of precipitating fatal Reye Syndrome (acute encephalopathy and fatty liver failure)."
    },
    {
        "name": "LABA Monotherapy in Persistent Asthma",
        "trigger": lambda text: (
            any(l in text for l in ["salmeterol", "formoterol", "laba monotherapy", "standalone laba"])
            and "asthma" in text
            and any(w in text for w in ["without ics", "without inhaled", "alone", "standalone", "without steroid"])
        ),
        "warning": "CRITICAL CONTRADICTION: LABA monotherapy without an Inhaled Corticosteroid (ICS) is contraindicated in asthma due to increased risk of severe, life-threatening asthma exacerbations."
    },
    {
        "name": "Metoclopramide in Parkinson Disease",
        "trigger": lambda text: (
            "parkinson" in text
            and any(d in text for d in ["metoclopramide", "reglan", "d2 blocker", "dopamine receptor antagonist"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "do not", "withhold", "stop", "worsens"])
        ),
        "warning": "CRITICAL CONTRADICTION: Metoclopramide and central D2 dopamine antagonists are contraindicated in Parkinson's disease as they precipitate acute severe extrapyramidal motor crisis."
    },
    {
        "name": "IV Calcium in Acute Digitalis / Digoxin Toxicity",
        "trigger": lambda text: (
            any(d in text for d in ["digoxin", "digitalis", "digitoxin"])
            and any(c in text for c in ["calcium gluconate", "calcium chloride", "iv calcium"])
            and any(t in text for t in ["toxicity", "overdose", "halo", "yellow-green", "arrhythmia"])
            and not any(neg in text for neg in ["avoid", "contraindicated", "stone heart", "do not"])
        ),
        "warning": "CRITICAL CONTRADICTION: Rapid IV Calcium is contraindicated in severe Digoxin toxicity due to the risk of precipitating irreversible systolic cardiac arrest ('stone heart')."
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
