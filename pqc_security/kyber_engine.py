"""
CRYSTALS-Kyber (NIST FIPS 203 / ML-KEM-768) Hybrid Encryption Engine
Implements authentic lattice-based Module Learning With Errors (M-LWE) cryptography
for quantum-resistant encryption of federated learning model parameters.
"""

import os
import json
import base64
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from pqcrypto.kem import ml_kem_768, ml_kem_512, ml_kem_1024
    HAS_NATIVE_PQC = True
except ImportError:
    HAS_NATIVE_PQC = False


@dataclass
class KyberKeyPair:
    public_key: bytes
    secret_key: bytes
    variant: str = "Kyber-768 (ML-KEM-768)"

    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key).decode("utf-8")

    def secret_key_b64(self) -> str:
        return base64.b64encode(self.secret_key).decode("utf-8")


@dataclass
class KyberCiphertext:
    kem_ciphertext: bytes
    encrypted_payload: bytes
    nonce: bytes
    variant: str = "Kyber-768 (ML-KEM-768)"

    def to_dict(self) -> Dict[str, str]:
        return {
            "kem_ciphertext": base64.b64encode(self.kem_ciphertext).decode("utf-8"),
            "encrypted_payload": base64.b64encode(self.encrypted_payload).decode("utf-8"),
            "nonce": base64.b64encode(self.nonce).decode("utf-8"),
            "variant": self.variant,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "KyberCiphertext":
        return cls(
            kem_ciphertext=base64.b64decode(data["kem_ciphertext"]),
            encrypted_payload=base64.b64decode(data["encrypted_payload"]),
            nonce=base64.b64decode(data["nonce"]),
            variant=data.get("variant", "Kyber-768 (ML-KEM-768)")
        )


class KyberKEM:
    """
    CRYSTALS-Kyber / ML-KEM Module-LWE Key Encapsulation Mechanism.
    Implements NIST FIPS 203 standards:
    - Kyber-512 (ML-KEM-512 / Security Level 1)
    - Kyber-768 (ML-KEM-768 / Security Level 3 - Primary NIST Standard)
    - Kyber-1024 (ML-KEM-1024 / Security Level 5)
    Pairs lattice-based quantum shared secret encapsulation with authenticated AES-256-GCM symmetric encryption.
    """

    def __init__(self, variant: str = "Kyber-768"):
        if "512" in variant:
            self.variant = "Kyber-512 (ML-KEM-512)"
            self._module = ml_kem_512 if HAS_NATIVE_PQC else None
        elif "1024" in variant:
            self.variant = "Kyber-1024 (ML-KEM-1024)"
            self._module = ml_kem_1024 if HAS_NATIVE_PQC else None
        else:
            self.variant = "Kyber-768 (ML-KEM-768)"
            self._module = ml_kem_768 if HAS_NATIVE_PQC else None

    def generate_keypair(self) -> KyberKeyPair:
        """
        Generates an authentic NIST FIPS 203 ML-KEM public and private keypair.
        ML-KEM-768 public key size: 1,184 bytes; secret key size: 2,400 bytes.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        pk, sk = self._module.keygen()
        return KyberKeyPair(public_key=bytes(pk), secret_key=bytes(sk), variant=self.variant)

    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Kyber.Encaps(pk) -> (shared_secret, kem_ciphertext)
        Derives an authentic quantum-safe 256-bit symmetric shared secret via lattice encapsulation.
        ML-KEM-768 ciphertext size: 1,088 bytes.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        kem_ct, shared_secret = self._module.encaps(public_key)
        return bytes(shared_secret), bytes(kem_ct)

    def decapsulate(self, kem_ciphertext: bytes, secret_key: bytes) -> bytes:
        """
        Kyber.Decaps(sk, ct) -> shared_secret
        Decapsulates the 256-bit shared secret from the quantum ciphertext using the private key.
        """
        if not HAS_NATIVE_PQC or self._module is None:
            raise RuntimeError("pqcrypto library is required for authentic NIST PQC operations.")
        
        shared_secret = self._module.decaps(secret_key, kem_ciphertext)
        return bytes(shared_secret)

    def encrypt_payload(self, payload_bytes: bytes, public_key: bytes) -> KyberCiphertext:
        """
        Hybrid Quantum-Safe Authenticated Encryption:
        1. Encapsulate 256-bit shared secret using recipient's Kyber public key.
        2. Encrypt arbitrary model tensor payload using AES-256-GCM keyed by the shared secret.
        """
        shared_secret, kem_ciphertext = self.encapsulate(public_key)

        aesgcm = AESGCM(shared_secret)
        nonce = os.urandom(12)
        encrypted_payload = aesgcm.encrypt(nonce, payload_bytes, associated_data=kem_ciphertext[:32])

        return KyberCiphertext(
            kem_ciphertext=kem_ciphertext,
            encrypted_payload=encrypted_payload,
            nonce=nonce,
            variant=self.variant
        )

    def decrypt_payload(self, kyber_ct: KyberCiphertext, secret_key: bytes) -> bytes:
        """
        Hybrid Quantum-Safe Authenticated Decryption:
        1. Decapsulate 256-bit shared secret using Kyber secret key.
        2. Decrypt & authenticate AES-256-GCM payload.
        """
        shared_secret = self.decapsulate(kyber_ct.kem_ciphertext, secret_key)
        aesgcm = AESGCM(shared_secret)
        decrypted_payload = aesgcm.decrypt(
            kyber_ct.nonce, 
            kyber_ct.encrypted_payload, 
            associated_data=kyber_ct.kem_ciphertext[:32]
        )
        return decrypted_payload
