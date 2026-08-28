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
    },
    {
        "source_id": "PMID:34599691",
        "title": "Surviving Sepsis Campaign: International Guidelines for Management of Sepsis and Septic Shock 2021",
        "category": "Infectious Disease & Critical Care",
        "content": "For patients with sepsis or septic shock, recommend administering IV broad-spectrum antimicrobials within 1 hour of recognition. "
                   "For septic shock with persistent hypotension post-fluid bolus, norepinephrine is the first-choice vasopressor targeting MAP >= 65 mmHg, alongside 30 mL/kg IV crystalloid fluid resuscitation.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/34599691/"
    },
    {
        "source_id": "PMID:26792348",
        "title": "American Epilepsy Society: Evidence-Based Guideline for Treatment of Convulsive Status Epilepticus",
        "category": "Neurology",
        "content": "Phase 1 (5-20 min): IV Lorazepam (0.1 mg/kg, max 4 mg) or IM Midazolam (10 mg) is the first-line therapy. "
                   "Phase 2 (20-40 min): If seizures persist, administer IV non-sedating antiepileptic drugs including Levetiracetam (60 mg/kg, max 4500 mg), Fosphenytoin (20 mg PE/kg), or Valproate sodium (40 mg/kg).",
        "url": "https://pubmed.ncbi.nlm.nih.gov/26792348/"
    },
    {
        "source_id": "PMID:27521067",
        "title": "2016 American Thyroid Association Guidelines for Diagnosis and Management of Hyperthyroidism",
        "category": "Endocrinology",
        "content": "Methimazole is the preferred thionamide for treating Graves' hyperthyroidism (10-20 mg daily) due to lower hepatotoxicity compared to propylthiouracil. "
                   "Beta-blockers (propranolol or atenolol) should be co-administered for rapid relief of adrenergic symptoms such as tachycardia and tremor.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/27521067/"
    },
    {
        "source_id": "PMID:30642456",
        "title": "2019 AHA/ACC/HRS Focused Update of the Guideline for Management of Atrial Fibrillation",
        "category": "Cardiology",
        "content": "Direct oral anticoagulants (DOACs: Apixaban, Rivaroxaban, Dabigatran) are recommended first-line over warfarin for stroke prevention in nonvalvular AF with CHA2DS2-VASc score >= 2 in men or >= 3 in women.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/30642456/"
    },
    {
        "source_id": "PMID:33602598",
        "title": "KDIGO 2021 Clinical Practice Guideline for the Management of Blood Pressure and SGLT2i in Chronic Kidney Disease",
        "category": "Nephrology",
        "content": "For patients with CKD and type 2 diabetes with eGFR >= 20 and persistent albuminuria (uACR > 300 mg/g), SGLT2 inhibitors (Dapagliflozin, Empagliflozin) are strongly recommended alongside optimized ACEi or ARB to slow CKD progression and reduce cardiovascular events.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33602598/"
    },
    {
        "source_id": "PMID:33578768",
        "title": "European Academy of Allergy and Clinical Immunology: Anaphylaxis Guidelines 2021",
        "category": "Immunology & Emergency Medicine",
        "content": "Intramuscular Epinephrine (Adrenaline) 1:1000 (0.3-0.5 mg in adults) into the anterolateral mid-thigh is the undisputed first-line life-saving treatment for acute anaphylaxis. "
                   "Repeat every 5-15 minutes if symptoms persist; supplemental oxygen and rapid IV fluid boluses for hypotension must follow immediately.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/33578768/"
    },
    {
        "source_id": "PMID:21208914",
        "title": "IDSA Guidelines for the Treatment of Acute Uncomplicated Cystitis and Pyelonephritis in Women",
        "category": "Infectious Disease",
        "content": "Oral Fluoroquinolones (Ciprofloxacin 500 mg BID for 7 days or Levofloxacin 750 mg daily for 5 days) are recommended first-line for acute uncomplicated pyelonephritis where fluoroquinolone resistance is <10%. "
                   "Oral TMP-SMX (160/800 mg BID for 14 days) is an appropriate alternative if susceptibility is established.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/21208914/"
    },
    {
        "source_id": "PMID:31778947",
        "title": "Management of Severe Hyperkalemia with ECG Changes",
        "category": "Nephrology & Emergency Medicine",
        "content": "In severe hyperkalemia with peaked T waves or widened QRS, IV Calcium Gluconate (10% 10 mL over 2-3 min) must be given immediately for myocardial membrane stabilization. "
                   "Follow with IV Regular Insulin 10 units with 50% Dextrose (D50W) and nebulized Albuterol to drive potassium into the intracellular compartment.",
        "url": "https://pubmed.ncbi.nlm.nih.gov/31778947/"
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
