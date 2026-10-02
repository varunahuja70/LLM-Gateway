import pytest

from app.core.security import (
    constant_time_compare,
    generate_csrf_token,
    generate_gateway_key,
    generate_session_token,
    hash_key,
    hash_password,
    hash_token,
    verify_password,
)


def test_generate_gateway_key() -> None:
    full_key, prefix, key_hash = generate_gateway_key()

    assert full_key.startswith("lgw_")
    assert len(full_key) >= 46
    assert prefix == full_key[:8]
    assert key_hash == hash_key(full_key)
    assert len(key_hash) == 64  # SHA-256 hex


def test_generate_session_and_csrf_tokens() -> None:
    session_token, session_hash = generate_session_token()
    assert len(session_token) >= 32
    assert session_hash == hash_token(session_token)

    csrf_token, csrf_hash = generate_csrf_token()
    assert len(csrf_token) >= 32
    assert csrf_hash == hash_token(csrf_token)


def test_argon2id_password_hashing() -> None:
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_password_policy_enforcement() -> None:
    # Too short (<12 chars)
    with pytest.raises(ValueError, match="at least 12 characters"):
        hash_password("short123")

    # Common password
    with pytest.raises(ValueError, match="too common"):
        hash_password("password1234")


def test_constant_time_compare() -> None:
    assert constant_time_compare("hello_token", "hello_token") is True
    assert constant_time_compare("hello_token", "wrong_token") is False
