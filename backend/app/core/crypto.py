import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


class CryptoError(Exception):
    """Base exception for cryptographic operations."""


class DecryptionError(CryptoError):
    """Raised when decryption fails due to invalid key, tampered ciphertext, or mismatched AAD."""


def get_master_key_bytes() -> bytes:
    settings = get_settings()
    key_b64 = settings.GATEWAY_MASTER_KEY
    if not key_b64:
        raise CryptoError("GATEWAY_MASTER_KEY is not configured.")
    try:
        raw_key = base64.b64decode(key_b64, validate=True)
    except Exception as e:
        raise CryptoError(f"Invalid base64 in GATEWAY_MASTER_KEY: {e}") from e
    if len(raw_key) != 32:
        raise CryptoError(f"GATEWAY_MASTER_KEY must be exactly 32 bytes (got {len(raw_key)}).")
    return raw_key


def _normalize_aad(associated_data: str | bytes) -> bytes:
    if isinstance(associated_data, str):
        return associated_data.encode("utf-8")
    return associated_data


def encrypt(
    plaintext: str | bytes,
    associated_data: str | bytes,
    key_version: int = 1,
) -> bytes:
    """Encrypt plaintext using AES-256-GCM with associated data (AAD).

    Payload format: 1 byte key_version + 12 bytes nonce + ciphertext_with_tag
    """
    key = get_master_key_bytes()
    aesgcm = AESGCM(key)

    data_bytes = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    aad_bytes = _normalize_aad(associated_data)

    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, data_bytes, aad_bytes)

    # Prefix with 1 byte key_version + 12 bytes nonce
    version_byte = key_version.to_bytes(1, "big")
    return version_byte + nonce + ciphertext


def decrypt(
    payload: bytes,
    associated_data: str | bytes,
    expected_key_version: int = 1,
) -> str:
    """Decrypt payload using AES-256-GCM and verify associated data (AAD).

    Returns decoded UTF-8 plaintext string.
    Raises DecryptionError if tampered, wrong AAD, or wrong key.
    """
    if len(payload) < 1 + 12 + 16:  # 1 byte ver + 12 bytes nonce + 16 bytes tag minimum
        raise DecryptionError("Ciphertext payload is too short.")

    version_byte = payload[0]
    key_version = int(version_byte)
    if key_version != expected_key_version:
        raise DecryptionError(
            f"Unsupported key version {key_version} (expected {expected_key_version})."
        )

    nonce = payload[1:13]
    ciphertext = payload[13:]

    key = get_master_key_bytes()
    aesgcm = AESGCM(key)
    aad_bytes = _normalize_aad(associated_data)

    try:
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
        return decrypted_bytes.decode("utf-8")
    except InvalidTag as e:
        raise DecryptionError(
            "Decryption failed: invalid authentication tag, tampered ciphertext, "
            "or mismatched associated data."
        ) from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {e}") from e
