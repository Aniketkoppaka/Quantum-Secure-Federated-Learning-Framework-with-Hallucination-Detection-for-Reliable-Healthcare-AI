"""
CRYSTALS-Dilithium (NIST FIPS 204 / ML-DSA-65) Digital Signature Engine
Implements authentic lattice-based Module-SIS / Fiat-Shamir with Aborts cryptography
for quantum-resistant identity authentication and model update integrity in Federated Learning.
"""

import json
import base64
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from pqcrypto.sign import ml_dsa_65, ml_dsa_44, ml_dsa_87
    from pqcrypto import InvalidSignatureError
    HAS_NATIVE_PQC = True
except ImportError:
    HAS_NATIVE_PQC = False


@dataclass
class DilithiumKeyPair:
    public_key: bytes
    secret_key: bytes
    variant: str = "Dilithium3 (ML-DSA-65)"

    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key).decode("utf-8")

    def secret_key_b64(self) -> str:
        return base64.b64encode(self.secret_key).decode("utf-8")


@dataclass
class DilithiumSignature:
    signature_bytes: bytes
    signer_id: str
    variant: str = "Dilithium3 (ML-DSA-65)"

    def to_dict(self) -> Dict[str, str]:
        return {
            "signature_bytes": base64.b64encode(self.signature_bytes).decode("utf-8"),
            "signer_id": self.signer_id,
            "variant": self.variant
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "DilithiumSignature":
        return cls(
            signature_bytes=base64.b64decode(data["signature_bytes"]),
            signer_id=data["signer_id"],
            variant=data.get("variant", "Dilithium3 (ML-DSA-65)")
        )


class DilithiumSigner:
    """
    CRYSTALS-Dilithium / ML-DSA Lattice Signature Engine.
    Implements NIST FIPS 204 standards:
    - Dilithium2 (ML-DSA-44 / Security Level 2)
    - Dilithium3 (ML-DSA-65 / Security Level 3 - Recommended)
    - Dilithium5 (ML-DSA-87 / Security Level 5)
    """

    def __init__(self, variant: str = "Dilithium3"):
        if "2" in variant or "44" in variant:
            self.variant = "Dilithium2 (ML-DSA-44)"
            self._module = ml_dsa_44 if HAS_NATIVE_PQC else None
        elif "5" in variant or "87" in variant:
            self.variant = "Dilithium5 (ML-DSA-87)"
            self._module = ml_dsa_87 if HAS_NATIVE_PQC else None
        else:
            self.variant = "Dilithium3 (ML-DSA-65)"
            self._module = ml_dsa_65 if HAS_NATIVE_PQC else None

    def generate_keypair(self, signer_id: str = "hospital_node") -> DilithiumKeyPair:
        """
        Generates an authentic NIST FIPS 204 ML-DSA public and private keypair for a node.
        ML-DSA-65 public key size: 1,952 bytes; secret key size: 4,032 bytes.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        pk, sk = self._module.keygen()
        return DilithiumKeyPair(public_key=bytes(pk), secret_key=bytes(sk), variant=self.variant)

    def sign(self, message: bytes, secret_key: bytes, signer_id: str = "hospital_node") -> DilithiumSignature:
        """
        Dilithium.Sign(sk, M) -> Signature
        Produces an authentic lattice-based digital signature over the model update hash.
        ML-DSA-65 signature size: 3,309 bytes.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        # Prepend signer ID context to message to bind identity cryptographically
        contextual_msg = f"{signer_id}:".encode("utf-8") + message
        signature_bytes = self._module.sign(secret_key, contextual_msg)

        return DilithiumSignature(
            signature_bytes=bytes(signature_bytes),
            signer_id=signer_id,
            variant=self.variant
        )

    def verify(self, message: bytes, signature: DilithiumSignature, public_key: bytes) -> bool:
        """
        Dilithium.Verify(pk, M, sig) -> {True, False}
        Authenticates that the message was signed by the registered hospital node and has not been tampered with.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        try:
            contextual_msg = f"{signature.signer_id}:".encode("utf-8") + message
            self._module.verify(public_key, contextual_msg, signature.signature_bytes)
            return True
        except (InvalidSignatureError, Exception):
            return False

