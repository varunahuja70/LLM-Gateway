import base64
import os

import pytest

from app.core.crypto import DecryptionError, decrypt, encrypt


@pytest.fixture(autouse=True)
def setup_master_key() -> None:
    # Valid 32-byte key base64
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    os.environ["GATEWAY_MASTER_KEY"] = valid_key
    # Reset cached settings
    import app.config as config_module

    config_module._settings = None


def test_provider_key_round_trip() -> None:
    """Security Test 3 part A: Encrypt, store, decrypt round-trip works."""
    original_key = "sk-proj-super-secret-provider-key-12345"
    row_id_1 = "row-uuid-001"

    ciphertext = encrypt(original_key, associated_data=row_id_1)
    assert ciphertext != original_key.encode()

    decrypted = decrypt(ciphertext, associated_data=row_id_1)
    assert decrypted == original_key


def test_tampered_ciphertext_fails() -> None:
    """Security Test 3 part B: Tampered ciphertext must fail decryption."""
    original_key = "sk-proj-super-secret-provider-key-12345"
    row_id = "row-uuid-001"

    ciphertext = encrypt(original_key, associated_data=row_id)

    # Tamper with the ciphertext body
    tampered = bytearray(ciphertext)
    tampered[-5] ^= 0xFF  # Flip bits in authentication tag/ciphertext

    with pytest.raises(DecryptionError, match="Decryption failed"):
        decrypt(bytes(tampered), associated_data=row_id)


def test_swapping_ciphertext_between_rows_fails() -> None:
    """Security Test 3 part C: Swapping ciphertext between rows fails due to AAD mismatch."""
    key_for_row_1 = "sk-openai-key-row-1"
    row_id_1 = "row-uuid-001"
    row_id_2 = "row-uuid-002"

    ciphertext_1 = encrypt(key_for_row_1, associated_data=row_id_1)

    # Attempt to decrypt row 1's ciphertext using row 2's id as associated data
    with pytest.raises(DecryptionError, match="Decryption failed"):
        decrypt(ciphertext_1, associated_data=row_id_2)


def test_invalid_key_version_fails() -> None:
    """Verify that unsupported key versions are rejected."""
    key = "secret"
    ciphertext = encrypt(key, associated_data="row-1", key_version=1)

    # Tamper version byte to 2
    tampered_ver = bytearray(ciphertext)
    tampered_ver[0] = 2

    with pytest.raises(DecryptionError, match="Unsupported key version"):
        decrypt(bytes(tampered_ver), associated_data="row-1", expected_key_version=1)
