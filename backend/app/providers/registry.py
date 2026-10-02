from app.providers.anthropic import AnthropicAdapter
from app.providers.base import ProviderAdapter, ProviderBadRequestError
from app.providers.google import GoogleGeminiAdapter
from app.providers.mock import MockProviderAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.openai_compatible import OpenAICompatibleAdapter

_ADAPTERS: dict[str, ProviderAdapter] = {
    "mock": MockProviderAdapter(),
    "openai": OpenAIAdapter(),
    "openai_compatible": OpenAICompatibleAdapter(),
    "anthropic": AnthropicAdapter(),
    "google": GoogleGeminiAdapter(),
}


def get_adapter(provider: str) -> ProviderAdapter:
    """Retrieve the singleton adapter for the specified provider name."""
    clean_name = provider.lower().strip()
    adapter = _ADAPTERS.get(clean_name)
    if not adapter:
        raise ProviderBadRequestError(
            f"Unsupported provider '{provider}'. Available: {list(_ADAPTERS.keys())}",
            provider=clean_name,
        )
    return adapter
