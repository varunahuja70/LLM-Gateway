import os
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def uuid7() -> uuid.UUID:
    """Generate an RFC 9562 compliant time-ordered UUIDv7."""
    ts_ms = time.time_ns() // 1_000_000
    rand = os.urandom(10)
    rand_a = int.from_bytes(rand[:2], "big") & 0x0FFF
    rand_b = int.from_bytes(rand[2:], "big") & 0x3FFFFFFFFFFFFFFF
    int_val = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return uuid.UUID(int=int_val)


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass
