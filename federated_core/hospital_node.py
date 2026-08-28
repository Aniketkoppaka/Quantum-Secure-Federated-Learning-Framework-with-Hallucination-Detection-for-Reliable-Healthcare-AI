"""
Hospital Edge Client Node
Simulates an independent hospital datacenter:
- Maintains private on-premise electronic health records & QA pairs (zero raw data leaves the premises).
- Trains local LoRA adapter parameters on local medical data.
- Digitally signs parameter updates with CRYSTALS-Dilithium.
- Encrypts parameter updates using Server's CRYSTALS-Kyber public key.
"""

import time
import copy
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from pqc_security.pqc_manager import PQCManager, SecurePayload
from pqc_security.dilithium_signer import DilithiumKeyPair
from pqc_security.kyber_engine import KyberKeyPair
from .dataset_loader import ClinicalDataSample


@dataclass
class LocalTrainingResult:
    hospital_id: str
    round_number: int
    num_samples_trained: int
    local_loss_initial: float
    local_loss_final: float
    parameter_deltas: Dict[str, List[float]]
    secure_payload: SecurePayload
    compute_time_seconds: float


class HospitalNode:
    """
    Simulated Hospital Edge Client for Quantum-Secure Federated Learning.
    """

    def __init__(
        self,
        hospital_id: str,
        hospital_name: str,
        local_dataset: List[ClinicalDataSample],
        pqc_manager: PQCManager,
        learning_rate: float = 0.01
    ):
        self.hospital_id = hospital_id
        self.hospital_name = hospital_name
        self.local_dataset = local_dataset
        self.pqc_manager = pqc_manager
        self.learning_rate = learning_rate

        # Initialize PQC Cryptographic Keys for this hospital node
        self.dilithium_kp, self.kyber_kp = self.pqc_manager.generate_hospital_identity(self.hospital_id)
        
        # Local model weights representation (FedLoRA adapter matrices)
        self.local_weights: Dict[str, np.ndarray] = {}

    def set_global_weights(self, global_weights: Dict[str, List[float]]):
        """Receives new global model weights from central server."""
        self.local_weights = {k: np.array(v, dtype=np.float32) for k, v in global_weights.items()}

    def train_local_epoch(
        self,
        server_kyber_pk: bytes,
        round_number: int = 1,
        epochs: int = 2
    ) -> LocalTrainingResult:
        """
        Executes local private training round:
        1. Optimizes local LoRA adapter parameters on private hospital records.
        2. Computes parameter update deltas ($\Delta \theta_k = \theta_k - \theta_{\text{global}}$).
        3. Encrypts with Kyber KEM and signs with Dilithium.
        """
        start_time = time.time()
        initial_weights = copy.deepcopy(self.local_weights)

        # Baseline loss simulation based on dataset size and specialty
        n_samples = len(self.local_dataset)
        base_loss = max(0.20, 1.45 - (0.08 * round_number) + (np.random.rand() * 0.05))
        
        # Simulate gradient descent steps over local samples
        updated_weights = {}
        deltas_dict = {}

        for key, tensor in self.local_weights.items():
            # Stochastic simulated gradient descent on LoRA rank adapters
            noise_scale = 0.015 / (round_number ** 0.5)
            grad = np.random.normal(loc=-0.03, scale=noise_scale, size=tensor.shape).astype(np.float32)
            
            # Step: w_new = w - lr * grad
            new_tensor = tensor - (self.learning_rate * grad)
            updated_weights[key] = new_tensor
            
            # Compute delta
            delta = new_tensor - initial_weights[key]
            deltas_dict[key] = delta.tolist()

        self.local_weights = updated_weights
        final_loss = max(0.12, base_loss - (0.15 * epochs * (n_samples / 5.0)))

        # Encrypt and Sign payload using PQC Manager
        secure_payload = self.pqc_manager.package_secure_update(
            weights_dict=deltas_dict,
            sender_id=self.hospital_id,
            sender_dilithium_sk=self.dilithium_kp.secret_key,
            server_kyber_pk=server_kyber_pk,
            round_number=round_number
        )

        compute_duration = time.time() - start_time

        return LocalTrainingResult(
            hospital_id=self.hospital_id,
            round_number=round_number,
            num_samples_trained=n_samples,
            local_loss_initial=round(float(base_loss), 4),
            local_loss_final=round(float(final_loss), 4),
            parameter_deltas=deltas_dict,
            secure_payload=secure_payload,
            compute_time_seconds=round(compute_duration, 4)
        )
