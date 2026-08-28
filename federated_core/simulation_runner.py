"""
Federated Simulation Orchestrator
Simulates multi-round federated training across hospital nodes with PQC encryption and FedAvg.
"""

from typing import List, Dict, Any, Optional
from pqc_security.pqc_manager import PQCManager
from .dataset_loader import MedicalDatasetPartitioner
from .hospital_node import HospitalNode
from .federated_server import FederatedServer, AggregationReport


class FederatedSimulationRunner:
    """
    Coordinates end-to-end multi-round federated training simulation across hospital clients.
    """

    def __init__(
        self,
        hospital_names: Optional[List[Dict[str, str]]] = None,
        distribution_mode: str = "non_iid"
    ):
        self.pqc_manager = PQCManager()
        self.server = FederatedServer(pqc_manager=self.pqc_manager)
        self.partitioner = MedicalDatasetPartitioner()

        hospital_configs = hospital_names or [
            {"id": "Hospital_A_Metro", "name": "Metro General Health (Cardiology & Nephrology)"},
            {"id": "Hospital_B_Regional", "name": "Regional Medical Center (Endocrinology & ID)"},
            {"id": "Hospital_C_Academic", "name": "Academic University Hospital (Neurology & Critical Care)"}
        ]

        # Partition clinical benchmark data
        hospital_ids = [h["id"] for h in hospital_configs]
        partitions = self.partitioner.create_hospital_partitions(
            hospital_ids=hospital_ids,
            distribution_mode=distribution_mode
        )

        # Initialize Hospital Nodes and register Dilithium PKs with the server
        self.hospital_nodes: Dict[str, HospitalNode] = {}
        for config in hospital_configs:
            hid = config["id"]
            node = HospitalNode(
                hospital_id=hid,
                hospital_name=config["name"],
                local_dataset=partitions.get(hid, []),
                pqc_manager=self.pqc_manager
            )
            # Sync initial global model
            node.set_global_weights(self.server.get_global_weights_dict())
            
            # Register public identity on the server
            self.server.register_client(hid, node.dilithium_kp.public_key)
            self.hospital_nodes[hid] = node

    def run_federated_round(self, round_number: Optional[int] = None) -> AggregationReport:
        """
        Executes one full round of:
        1. Local client training on private hospital records.
        2. Dilithium signing & Kyber encryption of weights.
        3. Transmission to Central Server.
        4. Decryption, Dilithium verification & FedAvg aggregation.
        5. Synchronizing new global weights to hospital clients.
        """
        current_rnd = round_number or (self.server.current_round + 1)
        client_payloads = []

        # 1. Edge Training & PQC Packaging
        for hid, node in self.hospital_nodes.items():
            result = node.train_local_epoch(
                server_kyber_pk=self.server.kyber_kp.public_key,
                round_number=current_rnd,
                epochs=2
            )
            client_payloads.append((result.secure_payload, result.num_samples_trained))

        # 2. Server Verification, Decryption & FedAvg
        report = self.server.aggregate_round(client_payloads)

        # 3. Synchronize new global weights to all nodes
        updated_global_weights = self.server.get_global_weights_dict()
        for node in self.hospital_nodes.values():
            node.set_global_weights(updated_global_weights)

        return report

    def get_network_status(self) -> Dict[str, Any]:
        """Returns status summary of the federated healthcare network."""
        return {
            "current_round": self.server.current_round,
            "quantum_security_level": self.pqc_manager.security_level_label,
            "registered_hospitals": [
                {
                    "id": node.hospital_id,
                    "name": node.hospital_name,
                    "dataset_size": len(node.local_dataset),
                    "dilithium_pk_fingerprint": node.dilithium_kp.public_key_b64()[:20] + "...",
                    "kyber_pk_fingerprint": node.kyber_kp.public_key_b64()[:20] + "..."
                }
                for node in self.hospital_nodes.values()
            ],
            "rounds_completed": len(self.server.history),
            "latest_global_loss": self.server.history[-1].global_loss if self.server.history else 1.30
        }
