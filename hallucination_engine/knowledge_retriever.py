"""
PubMed & Clinical Guidelines Evidence Retriever
Maintains indexed medical knowledge and retrieves relevant clinical evidence
to ground and verify LLM clinical responses.
"""

import math
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MedicalEvidence:
    source_id: str  # e.g., "PMID:34195721" or "AHA-2023-GL"
    title: str
    category: str
    content: str
    relevance_score: float = 0.0
    url: Optional[str] = None


# Curated clinical ground-truth knowledge base covering key clinical domains
VERIFIED_MEDICAL_CORPUS = [
    {
        "source_id": "PMID:33245481",
        "title": "AHA/ACC 2023 Guidelines for the Management of Heart Failure",
        "category": "Cardiology",
        "content": "First-line therapy for heart failure with reduced ejection fraction (HFrEF) includes quadruple therapy: "
                   "SGLT2 inhibitors (e.g. Empagliflozin, Dapagliflozin), ARNI (Sacubitril/Valsartan) or ACE inhibitors, "
                   "evidence-based beta-blockers (Carvedilol, Metoprolol succinate, Bisoprolol), and Mineralocorticoid receptor antagonists (Spironolactone). "
                   "NSAIDs are contraindicated as they cause fluid retention and worsen renal function in HF patients.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33245481/"
    },
    {
        "source_id": "PMID:35871239",
        "title": "ADA Standards of Medical Care in Diabetes - 2024",
        "category": "Endocrinology",
        "content": "Metformin remains the foundational first-line pharmacological agent for Type 2 Diabetes mellitus unless contraindicated (e.g., eGFR < 30 mL/min/1.73m2). "
                   "For patients with established ASCVD, heart failure, or CKD, GLP-1 receptor agonists (Semaglutide, Liraglutide) or SGLT2 inhibitors are recommended regardless of baseline HbA1c. "
                   "Metformin should be held temporarily prior to iodinated radiocontrast procedures in patients with eGFR between 30-60.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/35871239/"
    },
    {
        "source_id": "PMID:31618580",
        "title": "ATS/IDSA Guidelines for Diagnosis and Treatment of Community-Acquired Pneumonia in Adults",
        "category": "Infectious Diseases",
        "content": "For outpatient adults with CAP without comorbidities, recommended empiric antibiotics are Amoxicillin 1g TID, Doxycycline 100mg BID, or a macrolide (Azithromycin 500mg then 250mg) only if local pneumococcal resistance is <25%. "
                   "For outpatients with comorbidities (cardiac, renal, liver disease, diabetes), combination therapy with Amoxicillin/Clavulanate or Cefpodoxime PLUS a macrolide or Doxycycline, OR respiratory fluoroquinolone monotherapy (Levofloxacin 750mg QD, Moxifloxacin 400mg QD) is indicated.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/31618580/"
    },
    {
        "source_id": "PMID:28982544",
        "title": "AHA/ACC Hypertension Clinical Practice Guidelines",
        "category": "Cardiology / Hypertension",
        "content": "Stage 1 hypertension is defined as SBP 130-139 mmHg or DBP 80-89 mmHg. Stage 2 hypertension is SBP >= 140 mmHg or DBP >= 90 mmHg. "
                   "First-line agents for non-Black patients include Thiazide diuretics (Chlorthalidone, Hydrochlorothiazide), CCBs (Amlodipine), and ACEi/ARBs (Lisinopril, Losartan). "
                   "For Black adults, initial treatment should include a CCB or thiazide diuretic. Avoid combining ACE inhibitors with ARBs due to hyperkalemia and renal failure risk.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/28982544/"
    },
    {
        "source_id": "PMID:32768565",
        "title": "KDIGO Clinical Practice Guideline for Acute Kidney Injury",
        "category": "Nephrology",
        "content": "AKI is defined as an increase in Serum Creatinine by >= 0.3 mg/dL within 48 hours or >= 1.5 times baseline within 7 days. "
                   "Discontinue potentially nephrotoxic medications including NSAIDs, Aminoglycosides, and high-dose Amphotericin B. "
                   "Adjust dosing for renally cleared medications. Contrast-induced nephropathy should be mitigated with volume expansion using isotonic saline.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/32768565/"
    },
    {
        "source_id": "PMID:30154085",
        "title": "AAN Practice Guideline: Acute Ischemic Stroke Management",
        "category": "Neurology",
        "content": "Intravenous thrombolysis with IV Alteplase (0.9 mg/kg, max 90 mg) is recommended within 4.5 hours of ischemic stroke symptom onset for eligible patients. "
                   "Mechanical thrombectomy is indicated for large vessel occlusion (LVO) in the anterior circulation within 6 to 24 hours of last known normal based on DAWN/DEFUSE-3 trial criteria. "
                   "Strict blood pressure control (<185/110 mmHg) is required before initiating IV thrombolytic therapy.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/30154085/"
    },
    {
        "source_id": "PMID:33687352",
        "title": "Gold Report: Global Strategy for Prevention, Diagnosis and Management of COPD",
        "category": "Pulmonology",
        "content": "Spirometry showing post-bronchodilator FEV1/FVC < 0.70 confirms persistent airflow limitation. "
                   "Initial pharmacological therapy: Group A: SABA or LABA; Group B: LABA + LAMA; Group E (high exacerbation risk): LABA + LAMA combination, with addition of Inhaled Corticosteroids (ICS) if blood eosinophil count is >= 300 cells/uL.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33687352/"
    },
    {
        "source_id": "PMID:34262100",
        "title": "Clinical Toxicology: Acetaminophen Toxicity and N-Acetylcysteine Dosing",
        "category": "Pharmacology & Toxicology",
        "content": "In acute acetaminophen (paracetamol) overdose, treatment with N-acetylcysteine (NAC) is indicated if serum acetaminophen levels fall above the Rumack-Matthew nomogram line starting at 4 hours post-ingestion. "
                   "Standard IV NAC regimen is 150 mg/kg over 60 minutes, followed by 50 mg/kg over 4 hours, then 100 mg/kg over 16 hours.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/34262100/"
    }
]


class MedicalKnowledgeRetriever:
    """
    Retrieves evidence documents and guidelines matching clinical queries or LLM claims.
    Uses TF-IDF tokenization and Cosine Vector Relevance ranking.
    """

    def __init__(self, custom_corpus: Optional[List[Dict[str, str]]] = None):
        self.corpus = custom_corpus if custom_corpus else VERIFIED_MEDICAL_CORPUS
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'[a-zA-Z0-9\-\_]+', text.lower())
        # Filter out common stop words
        stopwords = {"the", "a", "an", "is", "in", "for", "where", "with", "and", "or", "to", "of", "on", "at", "by", "from", "be"}
        return [w for w in words if len(w) > 2 and w not in stopwords]

    def _build_index(self):
        self.doc_tokens = []
        self.vocab = set()
        self.idf = {}
        
        for doc in self.corpus:
            combined = f"{doc['title']} {doc['category']} {doc['content']}"
            tokens = self._tokenize(combined)
            self.doc_tokens.append(tokens)
            self.vocab.update(tokens)

        n_docs = len(self.corpus)
        for term in self.vocab:
            doc_freq = sum(1 for tokens in self.doc_tokens if term in tokens)
            self.idf[term] = math.log((n_docs + 1) / (doc_freq + 1)) + 1.0

    def _compute_vector(self, tokens: List[str]) -> Dict[str, float]:
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        
        vec = {}
        norm_sq = 0.0
        for t, count in tf.items():
            if t in self.idf:
                weight = (1 + math.log(count)) * self.idf[t]
                vec[t] = weight
                norm_sq += weight ** 2
        
        norm = math.sqrt(norm_sq)
        if norm > 0:
            for t in vec:
                vec[t] /= norm
        return vec

    def retrieve(self, query: str, top_k: int = 3) -> List[MedicalEvidence]:
        """
        Searches the medical knowledge base and returns the top-k most relevant verified medical evidence items.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        query_vec = self._compute_vector(query_tokens)
        results = []

        for idx, doc in enumerate(self.corpus):
            doc_vec = self._compute_vector(self.doc_tokens[idx])
            # Cosine similarity
            dot_product = sum(query_vec.get(t, 0.0) * doc_vec.get(t, 0.0) for t in query_vec)
            
            # Category booster
            if any(tok in doc['category'].lower() for tok in query_tokens):
                dot_product = min(1.0, dot_product + 0.15)

            results.append((dot_product, doc))

        # Sort by similarity descending
        results.sort(key=lambda x: x[0], reverse=True)

        evidence_list = []
        for score, doc in results[:top_k]:
            evidence_list.append(
                MedicalEvidence(
                    source_id=doc["source_id"],
                    title=doc["title"],
                    category=doc["category"],
                    content=doc["content"],
                    relevance_score=round(float(score), 4),
                    url=doc.get("url")
                )
            )

        return evidence_list
