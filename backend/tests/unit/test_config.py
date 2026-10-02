import base64

import pytest

from app.config import Settings


def test_valid_master_key() -> None:
    # 32 random bytes encoded in base64
    valid_key = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    settings = Settings(GATEWAY_MASTER_KEY=valid_key)
    assert valid_key == settings.GATEWAY_MASTER_KEY


def test_missing_master_key_fails() -> None:
    with pytest.raises(ValueError, match="GATEWAY_MASTER_KEY is missing"):
        Settings(GATEWAY_MASTER_KEY="")


def test_example_master_key_fails() -> None:
    with pytest.raises(ValueError, match="example value"):
        Settings(GATEWAY_MASTER_KEY="example_key_value_not_allowed_here")


def test_invalid_base64_fails() -> None:
    with pytest.raises(ValueError, match="valid base64"):
        Settings(GATEWAY_MASTER_KEY="!not_valid_base64!")


def test_invalid_length_fails() -> None:
    short_key = base64.b64encode(b"too_short").decode()
    with pytest.raises(ValueError, match="must decode to exactly 32 bytes"):
        Settings(GATEWAY_MASTER_KEY=short_key)


def test_weak_repeating_key_fails() -> None:
    repeating_key = base64.b64encode(b"\x00" * 32).decode()
    with pytest.raises(ValueError, match="too weak"):
        Settings(GATEWAY_MASTER_KEY=repeating_key)
