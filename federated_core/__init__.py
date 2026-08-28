"""
Federated Learning Core Package
Implements privacy-preserving Federated Learning with FedAvg, FedLoRA parameter management,
hospital edge client nodes, and PQC cryptographic transport.
"""

from .dataset_loader import MedicalDatasetPartitioner, ClinicalDataSample
from .hospital_node import HospitalNode
from .federated_server import FederatedServer, AggregationReport
from .simulation_runner import FederatedSimulationRunner

__all__ = [
    "MedicalDatasetPartitioner",
    "ClinicalDataSample",
    "HospitalNode",
    "FederatedServer",
    "AggregationReport",
    "FederatedSimulationRunner"
]
