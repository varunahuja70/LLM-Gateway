import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.core.errors import GatewayAPIException
from app.db.models.provider import ModelPrice, ProviderCredential


async def resolve_model(
    model_requested: str | None,
    fallback_chain: list[dict[str, str]] | None,
    db: AsyncSession,
) -> tuple[str, str]:
    """Resolve requested model name to (provider, model).

    Rules:
    - If model_requested is None or empty: use first entry from fallback_chain.
    - If 'provider/model' is given: return (provider, model).
    - If model name without '/' matches a known ModelPrice, use its provider.
    - Otherwise, infer by known prefix or return 400.
    """
    if not model_requested or not model_requested.strip():
        if fallback_chain and len(fallback_chain) > 0:
            first = fallback_chain[0]
            if "provider" in first and "model" in first:
                return first["provider"].strip().lower(), first["model"].strip()
        raise GatewayAPIException(
            status_code=400,
            message="No model specified and project has no default fallback chain.",
            error_type="invalid_request_error",
            code="model_not_specified",
            param="model",
        )

    clean_model = model_requested.strip()
    if "/" in clean_model:
        provider, model = clean_model.split("/", 1)
        return provider.strip().lower(), model.strip()

    # Model name without prefix -> check model_price table
    stmt = select(ModelPrice.provider, ModelPrice.model).where(ModelPrice.model == clean_model)
    res = await db.execute(stmt)
    rows = res.all()
    if len(rows) == 1:
        return rows[0][0], rows[0][1]

    # Heuristic prefix mapping
    lower_model = clean_model.lower()
    if lower_model.startswith("mock"):
        return "mock", clean_model
    if lower_model.startswith(("gpt-", "o1", "o3", "text-embedding")):
        return "openai", clean_model
    if lower_model.startswith("claude"):
        return "anthropic", clean_model
    if lower_model.startswith("gemini"):
        return "google", clean_model

    raise GatewayAPIException(
        status_code=400,
        message=f"Could not resolve provider for model '{clean_model}'. Please specify as 'provider/model'.",
        error_type="invalid_request_error",
        code="model_not_found",
        param="model",
    )


async def resolve_provider_credentials(
    project_credential_map: dict[str, Any] | None,
    provider: str,
    db: AsyncSession,
) -> tuple[str, str | None]:
    """Resolve active credentials for the requested provider.

    Returns (api_key, base_url).
    """
    if provider == "mock":
        return "mock-api-key", None

    credential_record: ProviderCredential | None = None

    # Check project-specific credential mapping
    if project_credential_map and provider in project_credential_map:
        raw_id = project_credential_map[provider]
        try:
            cred_id = uuid.UUID(str(raw_id))
            stmt = select(ProviderCredential).where(
                ProviderCredential.id == cred_id,
                ProviderCredential.disabled_at.is_(None),
            )
            res = await db.execute(stmt)
            credential_record = res.scalar_one_or_none()
        except (ValueError, TypeError):
            pass

    # Fallback to any active credential for this provider
    if not credential_record:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.provider == provider,
                ProviderCredential.disabled_at.is_(None),
            )
            .order_by(ProviderCredential.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        credential_record = res.scalar_one_or_none()

    if not credential_record:
        raise GatewayAPIException(
            status_code=503,
            message=f"No active credentials configured for provider '{provider}'.",
            error_type="invalid_request_error",
            code="provider_not_configured",
        )

    # Decrypt stored key with row ID as AAD
    aad = str(credential_record.id).encode()
    api_key = decrypt(credential_record.encrypted_key, associated_data=aad)

    return api_key, credential_record.base_url
