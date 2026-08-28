"""
Medical Dataset Partitioner for Federated Learning
Generates realistic Non-IID / IID medical data partitions across simulated hospital edge clients.
Simulates real-world hospital data silos (e.g. specialized cardiac hospital vs endocrine hospital).
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import random


@dataclass
class ClinicalDataSample:
    id: str
    specialty: str
    question: str
    context: str
    ground_truth_answer: str
    contraindications: List[str]


# Rich benchmark clinical dataset (PubMedQA / MedQA style)
CLINICAL_BENCHMARK_SAMPLES = [
    ClinicalDataSample(
        id="MED-001",
        specialty="Cardiology",
        question="What is the optimal quadruple medical therapy for HFrEF patients?",
        context="Patient presents with NYHA Class III heart failure and LVEF of 28%.",
        ground_truth_answer="Quadruple therapy comprising SGLT2 inhibitor (Dapagliflozin/Empagliflozin), ARNI (Sacubitril/Valsartan), beta-blocker (Carvedilol/Metoprolol), and MRA (Spironolactone).",
        contraindications=["NSAIDs", "Non-dihydropyridine CCBs"]
    ),
    ClinicalDataSample(
        id="MED-002",
        specialty="Cardiology",
        question="Can ACE inhibitors and ARBs be administered concurrently for hypertension?",
        context="55-year-old with resistant hypertension already on Lisinopril 20mg.",
        ground_truth_answer="No. Combining ACE inhibitors with ARBs is not recommended due to increased risks of hyperkalemia, syncope, and acute kidney injury.",
        contraindications=["ACEi + ARB combination"]
    ),
    ClinicalDataSample(
        id="MED-003",
        specialty="Endocrinology",
        question="What is the first-line medication for Type 2 Diabetes with established atherosclerotic cardiovascular disease (ASCVD)?",
        context="62-year-old diabetic male with prior myocardial infarction and HbA1c 8.4%.",
        ground_truth_answer="GLP-1 receptor agonist with proven CVD benefit (e.g., Semaglutide, Dulaglutide) or SGLT2 inhibitor (Empagliflozin), along with Metformin if eGFR allows.",
        contraindications=["Metformin when eGFR < 30"]
    ),
    ClinicalDataSample(
        id="MED-004",
        specialty="Endocrinology",
        question="When should Metformin be held in patients undergoing contrast CT?",
        context="Diabetic patient with baseline eGFR 42 mL/min scheduled for IV iodinated contrast scan.",
        ground_truth_answer="Metformin should be withheld at the time of or prior to the procedure and re-evaluated 48 hours post-scan after confirming stable renal function.",
        contraindications=["Continuing Metformin without renal monitoring"]
    ),
    ClinicalDataSample(
        id="MED-005",
        specialty="Infectious Diseases",
        question="What is the recommended outpatient empiric therapy for Community-Acquired Pneumonia (CAP) in adults with chronic heart/lung comorbidities?",
        context="68-year-old with COPD and CAP with fever and productive cough.",
        ground_truth_answer="Combination of beta-lactam (Amoxicillin/Clavulanate or Cefuroxime) plus macrolide (Azithromycin) or Doxycycline, OR respiratory fluoroquinolone monotherapy (Levofloxacin/Moxifloxacin).",
        contraindications=["Macrolide monotherapy in high-resistance areas"]
    ),
    ClinicalDataSample(
        id="MED-006",
        specialty="Neurology",
        question="What is the critical blood pressure threshold before administering IV Alteplase in acute ischemic stroke?",
        context="70-year-old presenting 2 hours after acute left hemiparesis, BP 195/115 mmHg.",
        ground_truth_answer="Blood pressure must be safely lowered to below 185/110 mmHg using IV labetalol or nicardipine before initiating IV Alteplase thrombolytic therapy.",
        contraindications=["Alteplase with BP >= 185/110 mmHg"]
    ),
    ClinicalDataSample(
        id="MED-007",
        specialty="Nephrology",
        question="What initial medication adjustments are mandated upon diagnosing Stage 2 Acute Kidney Injury?",
        context="Patient in ICU with creatinine rising from 1.0 to 2.4 mg/dL within 48 hours.",
        ground_truth_answer="Discontinue all nephrotoxic agents (NSAIDs, aminoglycosides), optimize volume status with isotonic crystalloids, and adjust renally cleared drug dosages.",
        contraindications=["NSAIDs", "Aminoglycosides", "Radiocontrast"]
    )
]


class MedicalDatasetPartitioner:
    """
    Distributes clinical datasets among hospital clients to simulate real-world federated learning settings.
    """

    def __init__(self, samples: Optional[List[ClinicalDataSample]] = None, seed: int = 42):
        self.samples = samples or CLINICAL_BENCHMARK_SAMPLES
        self.rng = random.Random(seed)

    def create_hospital_partitions(
        self,
        hospital_ids: List[str] = ["Hospital_A_Metro", "Hospital_B_General", "Hospital_C_University"],
        distribution_mode: str = "non_iid"
    ) -> Dict[str, List[ClinicalDataSample]]:
        """
        Partitions samples across the specified hospital IDs.
        - 'non_iid': Partitions by clinical specialty (simulating specialized centers).
        - 'iid': Random balanced distribution across all nodes.
        """
        partitions = {hid: [] for hid in hospital_ids}

        if distribution_mode == "non_iid":
            # Assign specialties to hospitals
            specialty_map = {
                "Cardiology": hospital_ids[0 % len(hospital_ids)],
                "Nephrology": hospital_ids[0 % len(hospital_ids)],
                "Endocrinology": hospital_ids[1 % len(hospital_ids)],
                "Infectious Diseases": hospital_ids[1 % len(hospital_ids)],
                "Neurology": hospital_ids[2 % len(hospital_ids)],
            }
            for sample in self.samples:
                target_hospital = specialty_map.get(sample.specialty, hospital_ids[0])
                partitions[target_hospital].append(sample)
        else:
            # IID uniform distribution
            shuffled = list(self.samples)
            self.rng.shuffle(shuffled)
            for idx, sample in enumerate(shuffled):
                target_hospital = hospital_ids[idx % len(hospital_ids)]
                partitions[target_hospital].append(sample)

        return partitions
