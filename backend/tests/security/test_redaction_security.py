from app.logging_setup import redact_data, redaction_processor


def test_redaction_sensitive_keys() -> None:
    """Verify that dictionary keys named password, key, secret, token, etc. are redacted."""
    payload = {
        "user": "alice",
        "password": "SuperSecretPassword123!",
        "api_key": "raw_provider_key_here",
        "secret": "very_secret_data",
        "session_token": "token_12345",
        "authorization": "Bearer lgw_testkey12345678901234567890",
        "cookie": "session=abc123xyz456",
        "master_key": "some_master_key",
        "nested": {
            "token": "inner_token",
            "safe_field": "hello world",
        },
    }

    cleaned = redact_data(payload)

    assert cleaned["user"] == "alice"
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["secret"] == "[REDACTED]"
    assert cleaned["session_token"] == "[REDACTED]"
    assert cleaned["authorization"] == "[REDACTED]"
    assert cleaned["cookie"] == "[REDACTED]"
    assert cleaned["master_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["safe_field"] == "hello world"


def test_redaction_secret_patterns_in_strings() -> None:
    """Verify regex patterns matching secret prefixes (lgw_, sk-, sk-ant-, AIza, Bearer)."""
    test_cases = [
        ("Calling model with key lgw_abc12345678901234567890 in header", "lgw_[REDACTED]"),
        ("OpenAI secret is sk-proj-1234567890abcdef123456", "sk-[REDACTED]"),
        ("Anthropic key is sk-ant-api03-abcdef1234567890", "sk-ant-[REDACTED]"),
        ("Google key is AIzaSyD1234567890abcdef123456", "AIza[REDACTED]"),
        ("Authorization: Bearer secret_token_value_here", "Bearer [REDACTED]"),
        ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "Basic [REDACTED]"),
    ]

    for input_text, expected_substr in test_cases:
        redacted = redact_data(input_text)
        assert expected_substr in redacted
        # None of the raw secret parts should remain
        assert "lgw_abc1234567890" not in redacted
        assert "sk-proj-1234567890" not in redacted
        assert "sk-ant-api03" not in redacted
        assert "AIzaSyD123456" not in redacted


def test_redaction_processor_for_structlog() -> None:
    """Verify the structlog processor strips secrets from event dictionaries."""
    event = {
        "event": "Request completed",
        "status": 200,
        "token": "secret_session_token",
        "message": "Used gateway key lgw_testsecretkey1234567890 to call OpenAI",
    }

    processed = redaction_processor(None, "info", event)
    assert processed["token"] == "[REDACTED]"
    assert "lgw_testsecretkey" not in processed["message"]
    assert "lgw_[REDACTED]" in processed["message"]
