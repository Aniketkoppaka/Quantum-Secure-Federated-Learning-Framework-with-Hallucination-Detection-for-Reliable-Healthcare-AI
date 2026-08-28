"""
Federated Learning Aggregation Server
Coordinates multi-hospital federated training:
- Maintains registry of authorized hospital Dilithium public keys.
- Decrypts client update payloads using CRYSTALS-Kyber KEM private key.
- Verifies authenticity and non-tampering of each update using CRYSTALS-Dilithium.
- Performs secure weighted Federated Averaging (FedAvg):
  $$\\theta_{t+1} = \\theta_t + \\sum_{k=1}^K \\frac{n_k}{N} \\Delta \\theta_k$$
- Tracks global model convergence, security audit logs, and communication payload stats.
"""

import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from pqc_security.pqc_manager import PQCManager, SecurePayload
from pqc_security.dilithium_signer import DilithiumKeyPair
from pqc_security.kyber_engine import KyberKeyPair


@dataclass
class AggregationReport:
    round_number: int
    participating_clients: List[str]
    rejected_clients: List[str]
    total_samples_aggregated: int
    global_loss: float
    security_verifications: List[Dict[str, Any]]
    quantum_encryption_type: str
    aggregation_timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FederatedServer:
    """
    Central Coordinator & FedAvg Aggregation Server with Post-Quantum Security.
    """

    def __init__(
        self,
        pqc_manager: PQCManager,
        initial_dim: int = 16
    ):
        self.pqc_manager = pqc_manager
        
        # Server PQC keypairs (Dilithium for server broadcasts, Kyber for client-to-server encryption)
        self.dilithium_kp, self.kyber_kp = self.pqc_manager.generate_server_identity()
        
        # Hospital public key registry {hospital_id: dilithium_public_key}
        self.registered_client_pks: Dict[str, bytes] = {}

        # Global model parameter state (simulated base LoRA adapters)
        self.global_weights: Dict[str, np.ndarray] = {
            "lora_attn_q.weight": np.random.normal(0, 0.02, size=(initial_dim, initial_dim)).astype(np.float32),
            "lora_attn_v.weight": np.random.normal(0, 0.02, size=(initial_dim, initial_dim)).astype(np.float32),
            "lora_mlp_gate.weight": np.random.normal(0, 0.02, size=(initial_dim, initial_dim)).astype(np.float32)
        }
        
        self.current_round: int = 0
        self.history: List[AggregationReport] = []

    def register_client(self, hospital_id: str, dilithium_pk: bytes):
        """Registers a verified hospital node's Dilithium public key."""
        self.registered_client_pks[hospital_id] = dilithium_pk

    def get_global_weights_dict(self) -> Dict[str, List[float]]:
        """Returns JSON-serializable representation of global weights."""
        return {k: v.tolist() for k, v in self.global_weights.items()}

    def aggregate_round(
        self,
        payloads: List[Tuple[SecurePayload, int]]  # List of (SecurePayload, sample_count)
    ) -> AggregationReport:
        """
        Executes a secure FedAvg round:
        1. Verifies Dilithium signatures.
        2. Decrypts Kyber ciphertexts.
        3. Computes sample-weighted FedAvg update:
           $$\\Delta \\theta_{\\text{global}} = \\sum_k \\frac{n_k}{N} \\Delta \\theta_k$$
        4. Updates global weights $\\theta \\leftarrow \\theta + \\Delta \\theta_{\\text{global}}$.
        """
        self.current_round += 1
        start_time = time.time()

        accepted_deltas: List[Tuple[Dict[str, np.ndarray], int, str]] = []
        rejected_clients: List[str] = []
        security_logs: List[Dict[str, Any]] = []
        total_samples = 0

        for payload, sample_count in payloads:
            sender_id = payload.sender_id
            
            # Look up registered Dilithium PK
            if sender_id not in self.registered_client_pks:
                rejected_clients.append(sender_id)
                security_logs.append({
                    "hospital_id": sender_id,
                    "status": "REJECTED",
                    "reason": "Unregistered sender ID (unknown Dilithium public key)"
                })
                continue

            client_pk = self.registered_client_pks[sender_id]

            # Unpack, decrypt with server Kyber SK, and verify Dilithium signature
            is_valid, deltas_dict, status_msg = self.pqc_manager.unpack_and_verify_update(
                secure_payload=payload,
                server_kyber_sk=self.kyber_kp.secret_key,
                sender_dilithium_pk=client_pk
            )

            if is_valid and deltas_dict is not None:
                numpy_deltas = {k: np.array(v, dtype=np.float32) for k, v in deltas_dict.items()}
                accepted_deltas.append((numpy_deltas, sample_count, sender_id))
                total_samples += sample_count
                security_logs.append({
                    "hospital_id": sender_id,
                    "status": "VERIFIED_AND_DECRYPTED",
                    "reason": status_msg,
                    "pqc_algorithm": payload.quantum_security_level
                })
            else:
                rejected_clients.append(sender_id)
                security_logs.append({
                    "hospital_id": sender_id,
                    "status": "TAMPER_REJECTED",
                    "reason": status_msg
                })

        # Apply Weighted Federated Averaging (FedAvg)
        if accepted_deltas and total_samples > 0:
            for key in self.global_weights.keys():
                weighted_sum = np.zeros_like(self.global_weights[key])
                for deltas, n_k, _ in accepted_deltas:
                    if key in deltas:
                        weight_factor = n_k / total_samples
                        weighted_sum += weight_factor * deltas[key]
                
                # Apply global step
                self.global_weights[key] += weighted_sum

        # Calculate estimated simulated global loss
        simulated_loss = max(0.10, 1.30 * (0.82 ** self.current_round))

        report = AggregationReport(
            round_number=self.current_round,
            participating_clients=[sender for _, _, sender in accepted_deltas],
            rejected_clients=rejected_clients,
            total_samples_aggregated=total_samples,
            global_loss=round(float(simulated_loss), 4),
            security_verifications=security_logs,
            quantum_encryption_type=self.pqc_manager.security_level_label,
            aggregation_timestamp=time.time()
        )

        self.history.append(report)
        return report
