import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Password hasher using recommended Argon2id parameters
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

COMMON_PASSWORDS = {
    "password1234",
    "password12345",
    "123456789012",
    "admin1234567",
    "qwerty123456",
    "letmein12345",
    "welcome12345",
}


def hash_token(token: str) -> str:
    """Return SHA-256 hex digest of a token or key."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_key(key: str) -> str:
    """Return SHA-256 hex digest of a gateway key."""
    return hash_token(key)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def generate_gateway_key() -> tuple[str, str, str]:
    """Generate a new gateway key with 256 bits of entropy.

    Format: lgw_ + 43 URL-safe random chars.
    Returns: (full_key, prefix_8_chars, key_hash)
    """
    random_part = secrets.token_urlsafe(32)  # 256 bits of randomness (~43 chars)
    full_key = f"lgw_{random_part}"
    prefix = full_key[:8]
    key_hash = hash_key(full_key)
    return full_key, prefix, key_hash


def generate_session_token() -> tuple[str, str]:
    """Generate random 256-bit session token and its SHA-256 hash.

    Returns: (session_token, token_hash)
    """
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def generate_csrf_token() -> tuple[str, str]:
    """Generate random CSRF token and its SHA-256 hash.

    Returns: (csrf_token, csrf_token_hash)
    """
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def validate_password_strength(password: str) -> None:
    """Validate owner password meets security policy.

    Must be at least 12 characters and not in common passwords list.
    """
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common. Please choose a stronger password.")


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    validate_password_strength(password)
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against Argon2id hash in constant time."""
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False
