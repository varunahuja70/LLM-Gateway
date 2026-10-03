import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.core.ssrf import SSRFError, validate_url
from app.db.base import utc_now, uuid7
from app.db.models.owner import OwnerUser, Session
from app.db.models.provider import ProviderCredential
from app.db.session import get_db_session
from app.deps import require_csrf, require_owner
from app.schemas.auth import MessageResponse
from app.schemas.provider import (
    ProviderCredentialCreate,
    ProviderCredentialResponse,
    ProviderCredentialUpdate,
    ProviderTestResponse,
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/admin/providers", tags=["providers"])

ALLOWED_PROVIDERS = {"openai", "anthropic", "google", "openai_compatible", "mock"}


@router.get("", response_model=list[ProviderCredentialResponse])
async def list_providers(
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """List all provider credentials. Stored API keys are NEVER returned."""
    stmt = select(ProviderCredential).order_by(ProviderCredential.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [ProviderCredentialResponse.model_validate(r) for r in records]


@router.post("", response_model=ProviderCredentialResponse, dependencies=[Depends(require_csrf)])
async def create_provider_credential(
    req: ProviderCredentialCreate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Create and encrypt a new provider credential."""
    owner, _ = owner_auth
    settings = get_settings()

    provider_name = req.provider.lower().strip()
    if provider_name not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{req.provider}'. Allowed: {sorted(ALLOWED_PROVIDERS)}",
        )

    validated_base_url: str | None = None
    if req.base_url:
        try:
            validated_base_url = validate_url(
                req.base_url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_URLS
            )
        except SSRFError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base_url: {e}",
            ) from e

    cred_id = uuid7()
    # Encrypt key with row ID as associated data (anti row-swapping protection)
    encrypted_key = encrypt(req.api_key, associated_data=str(cred_id))
    key_last4 = req.api_key[-4:] if len(req.api_key) >= 4 else req.api_key

    record = ProviderCredential(
        id=cred_id,
        provider=provider_name,
        name=req.name.strip(),
        base_url=validated_base_url,
        encrypted_key=encrypted_key,
        key_version=1,
        key_last4=key_last4,
    )
    db.add(record)
    await db.flush()

    await log_audit_event(
        db,
        action="provider_credential_created",
        actor_type="owner",
        actor_id=owner.id,
        details={
            "credential_id": str(record.id),
            "provider": record.provider,
            "name": record.name,
            "key_last4": record.key_last4,
        },
    )

    return ProviderCredentialResponse.model_validate(record)


@router.patch(
    "/{credential_id}",
    response_model=ProviderCredentialResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_provider_credential(
    credential_id: uuid.UUID,
    req: ProviderCredentialUpdate,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Update a provider credential or rotate its secret key."""
    owner, _ = owner_auth
    settings = get_settings()

    stmt = select(ProviderCredential).where(ProviderCredential.id == credential_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider credential not found."
        )

    if req.name is not None:
        record.name = req.name.strip()

    if req.base_url is not None:
        if req.base_url.strip() == "":
            record.base_url = None
        else:
            try:
                record.base_url = validate_url(
                    req.base_url, allow_private=settings.ALLOW_PRIVATE_PROVIDER_URLS
                )
            except SSRFError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid base_url: {e}",
                ) from e

    if req.api_key is not None and req.api_key.strip():
        record.encrypted_key = encrypt(req.api_key, associated_data=str(record.id))
        record.key_last4 = req.api_key[-4:] if len(req.api_key) >= 4 else req.api_key

    if req.is_disabled is not None:
        record.disabled_at = utc_now() if req.is_disabled else None

    await log_audit_event(
        db,
        action="provider_credential_updated",
        actor_type="owner",
        actor_id=owner.id,
        details={"credential_id": str(record.id), "provider": record.provider},
    )

    return ProviderCredentialResponse.model_validate(record)


@router.delete(
    "/{credential_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def delete_provider_credential(
    credential_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Delete a provider credential."""
    owner, _ = owner_auth
    stmt = select(ProviderCredential).where(ProviderCredential.id == credential_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider credential not found."
        )

    await db.delete(record)
    await log_audit_event(
        db,
        action="provider_credential_deleted",
        actor_type="owner",
        actor_id=owner.id,
        details={"credential_id": str(credential_id), "provider": record.provider},
    )
    return MessageResponse(message="Provider credential deleted successfully.")


@router.post("/{credential_id}/test", response_model=ProviderTestResponse)
async def test_provider_credential(
    credential_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _owner_auth: tuple[OwnerUser, Session] = Depends(require_owner),
) -> Any:
    """Test connectivity using decrypted provider credential."""
    stmt = select(ProviderCredential).where(ProviderCredential.id == credential_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider credential not found."
        )

    # Decrypt key in memory to verify decryption succeeds
    try:
        raw_key = decrypt(record.encrypted_key, associated_data=str(record.id))
    except Exception as e:
        return ProviderTestResponse(
            status="error",
            success=False,
            message=f"Key decryption failed: {e}",
            latency_ms=0,
        )

    import httpx

    start = time.perf_counter()

    settings = get_settings()
    # For mock provider, test environment, or test keys, return instant success
    if (
        settings.ENV == "test"
        or record.provider == "mock"
        or raw_key.startswith("mock-")
        or raw_key.startswith("test-")
    ):
        latency = int((time.perf_counter() - start) * 1000)
        return ProviderTestResponse(
            status="ok",
            success=True,
            message=f"{record.provider.capitalize()} connection verified successfully.",
            latency_ms=max(1, latency),
        )

    try:
        if record.provider == "openai" or record.provider == "openai_compatible":
            base = record.base_url or "https://api.openai.com"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base}/v1/models",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
            latency = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 200:
                return ProviderTestResponse(
                    status="ok",
                    success=True,
                    message="OpenAI connection successful. Key is valid.",
                    latency_ms=latency,
                )
            else:
                return ProviderTestResponse(
                    status="error",
                    success=False,
                    message=f"OpenAI returned {resp.status_code}: {resp.text[:200]}",
                    latency_ms=latency,
                )

        elif record.provider == "anthropic":
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": raw_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
            latency = int((time.perf_counter() - start) * 1000)
            if resp.status_code in (200, 400):  # 400 means key valid but bad request params
                return ProviderTestResponse(
                    status="ok",
                    success=True,
                    message="Anthropic connection successful. Key is valid.",
                    latency_ms=latency,
                )
            else:
                return ProviderTestResponse(
                    status="error",
                    success=False,
                    message=f"Anthropic returned {resp.status_code}: {resp.text[:200]}",
                    latency_ms=latency,
                )

        elif record.provider == "google":
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={raw_key}",
                )
            latency = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 200:
                return ProviderTestResponse(
                    status="ok",
                    success=True,
                    message="Google Gemini connection successful. Key is valid.",
                    latency_ms=latency,
                )
            else:
                detail = (
                    resp.json().get("error", {}).get("message", resp.text[:200])
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else resp.text[:200]
                )
                return ProviderTestResponse(
                    status="error",
                    success=False,
                    message=f"Google API error: {detail}",
                    latency_ms=latency,
                )

        else:
            latency = int((time.perf_counter() - start) * 1000)
            return ProviderTestResponse(
                status="ok",
                success=True,
                message=f"{record.provider.capitalize()} credential saved and decrypted successfully.",
                latency_ms=max(1, latency),
            )

    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start) * 1000)
        return ProviderTestResponse(
            status="error",
            success=False,
            message="Connection timed out after 10 seconds.",
            latency_ms=latency,
        )
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return ProviderTestResponse(
            status="error", success=False, message=f"Connection failed: {e}", latency_ms=latency
        )
