import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.core.crypto import decrypt
from app.core.ssrf import SSRFError, validate_url
from app.db.models.alert import BudgetAlert
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


def compute_webhook_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def deliver_webhook(
    alert_id: uuid.UUID,
    project_id: uuid.UUID,
    webhook_url: str,
    encrypted_secret: bytes | None,
    payload: dict[str, Any],
    db: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    max_retries: int = 3,
) -> bool:
    """Deliver webhook with SSRF validation, HMAC signature, and retries."""
    if db is None:
        maker = session_factory or get_sessionmaker()
        async with maker() as session:
            return await deliver_webhook(
                alert_id,
                project_id,
                webhook_url,
                encrypted_secret,
                payload,
                db=session,
                max_retries=max_retries,
            )

    settings = get_settings()
    backoff_base = 0.05 if settings.ENV == "test" else 1.0

    # 1. Fetch alert
    stmt = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    res = await db.execute(stmt)
    alert = res.scalar_one_or_none()
    if not alert:
        return False

    # 2. SSRF check on target URL
    try:
        validate_url(webhook_url)
    except SSRFError as e:
        alert.webhook_status = "failed"
        alert.webhook_attempts = 1
        alert.last_error = f"SSRF blocked: {e}"
        await db.commit()
        return False

    # 3. Decrypt webhook secret and sign payload
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    if encrypted_secret:
        try:
            secret = decrypt(encrypted_secret, associated_data=str(project_id).encode())
            headers["X-Gateway-Signature"] = compute_webhook_signature(payload_bytes, secret)
        except Exception as e:
            logger.warning("Failed to decrypt webhook secret for project %s: %s", project_id, e)

    # 4. Attempt delivery with retries
    success = False
    last_err: str | None = None
    attempts = 0

    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(1, max_retries + 1):
            attempts = attempt
            try:
                resp = await client.post(webhook_url, content=payload_bytes, headers=headers)
                if 200 <= resp.status_code < 300:
                    success = True
                    break
                else:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as e:
                last_err = str(e)

            if attempt < max_retries:
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))

    alert.webhook_attempts = attempts
    if success:
        alert.webhook_status = "sent"
        alert.last_error = None
    else:
        alert.webhook_status = "failed"
        alert.last_error = last_err

    await db.commit()
    return success
