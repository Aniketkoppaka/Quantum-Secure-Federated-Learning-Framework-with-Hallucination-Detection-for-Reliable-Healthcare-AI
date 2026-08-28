"""
End-to-End System Tests for Quantum-Secure Federated Healthcare AI Framework
Validates:
1. Post-Quantum Cryptography Layer (Kyber & Dilithium)
2. Hallucination Detection & Clinical Evidence Grounding
3. Federated Learning Core (FedAvg & Node Simulation)
"""

import pytest
import json
from run_red_team_model import append_diagnostic
from pqc_security import PQCManager, KyberKEM, DilithiumSigner
from hallucination_engine import (
    HallucinationDecisionEngine,
    MedicalKnowledgeRetriever,
    SafetyStatus
)
from federated_core import FederatedSimulationRunner, MedicalDatasetPartitioner


def test_pqc_kyber_and_dilithium():
    """Validates PQC key generation, encryption, signing, and tamper detection."""
    mgr = PQCManager()
    
    # 1. Hospital Node identity
    h_dil, h_kyb = mgr.generate_hospital_identity("hospital_alpha")
    s_dil, s_kyb = mgr.generate_server_identity()
    
    # 2. Package model weights
    weights = {"lora_q": [0.12, -0.45], "lora_v": [0.89, 0.02]}
    payload = mgr.package_secure_update(
        weights_dict=weights,
        sender_id="hospital_alpha",
        sender_dilithium_sk=h_dil.secret_key,
        server_kyber_pk=s_kyb.public_key,
        round_number=1
    )
    
    # 3. Server unpacks and verifies
    is_valid, recovered_weights, msg = mgr.unpack_and_verify_update(
        secure_payload=payload,
        server_kyber_sk=s_kyb.secret_key,
        sender_dilithium_pk=h_dil.public_key
    )
    
    assert is_valid is True
    assert recovered_weights == weights
    assert "Successfully verified Dilithium" in msg


def test_hallucination_safe_case():
    """Validates that evidence-grounded safe clinical recommendations are ALLOWED."""
    engine = HallucinationDecisionEngine()
    query = "What is the recommended therapy for heart failure with reduced ejection fraction?"
    safe_candidates = [
        "First-line quadruple therapy for HFrEF includes SGLT2 inhibitors, ARNI or ACE inhibitors, beta-blockers, and MRAs.",
        "Guideline directed therapy for HFrEF involves four medication classes: SGLT2i, ARNI/ACEi, beta-blockers, and spironolactone."
    ]
    decision = engine.evaluate_response(query, safe_candidates)
    
    assert decision.status == SafetyStatus.VERIFIED_SAFE
    assert decision.composite_confidence >= 0.70
    assert decision.action == "ALLOW"
    assert len(decision.evidence_citations) > 0


def test_hallucination_blocked_fatal_contraindication():
    """Validates that dangerous medical hallucinations (e.g. NSAIDs in HF) are BLOCKED."""
    engine = HallucinationDecisionEngine()
    query = "Can we prescribe high-dose Ibuprofen for pain relief in acute heart failure?"
    dangerous_candidates = [
        "Yes, you should prescribe high-dose Ibuprofen and give NSAIDs immediately to reduce inflammation in acute heart failure."
    ]
    decision = engine.evaluate_response(query, dangerous_candidates)
    
    assert decision.status == SafetyStatus.BLOCKED_HALLUCINATION
    assert decision.action == "BLOCK"
    assert decision.critical_contradiction_found is True
    assert decision.composite_confidence <= 0.30
    assert "[SAFETY INTERVENTION - RESPONSE BLOCKED]" in decision.recommendation_text


def test_federated_learning_simulation():
    """Validates multi-round federated training with PQC encryption and FedAvg."""
    runner = FederatedSimulationRunner()
    
    status = runner.get_network_status()
    assert len(status["registered_hospitals"]) == 3
    assert status["current_round"] == 0
    
    # Run Round 1
    report_r1 = runner.run_federated_round(1)
    assert report_r1.round_number == 1
    assert len(report_r1.participating_clients) == 3
    assert report_r1.global_loss < 1.30
    
    # Run Round 2
    report_r2 = runner.run_federated_round(2)
    assert report_r2.round_number == 2
    assert report_r2.global_loss < report_r1.global_loss

def test_clinical_warning_class_is_reachable():
    engine = HallucinationDecisionEngine()
    decision = engine.evaluate_response(
        "What should be considered for a patient with persistent fatigue?",
        ["Some causes may include anemia or thyroid disease; clinical examination and laboratory testing are needed."]
    )
    assert decision.status == SafetyStatus.CLINICAL_WARNING
    assert decision.action == "WARN"

def test_case_diagnostic_jsonl_is_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    append_diagnostic({"diagnostic": {"case_id": "TEST-1", "question": "q", "generated_answer": "a", "retrieved_evidence": [], "nli_results": [], "support_score": 0.5, "risk_score": 0.2, "consistency_score": 1.0, "final_confidence": 0.7, "predicted_label": "VERIFIED_SAFE", "ground_truth": "VERIFIED_SAFE", "fallback_used": False}})
    lines = (tmp_path / "results" / "case_diagnostics.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["case_id"] == "TEST-1"
