from value_semantics.nl2sql.providers.base import BaseLLMProvider


def get_provider(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
) -> BaseLLMProvider:
    """
    Factory that returns a provider instance by name.

    provider: "openai" | "gemini" | "claude"
    model:    optional model override; each provider has a sensible default
    api_key:  optional key override; falls back to the relevant env var
    """
    name = provider.lower()

    if name == "openai":
        from value_semantics.nl2sql.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model or "gpt-4o", api_key=api_key)

    if name in ("gemini", "google"):
        from value_semantics.nl2sql.providers.gemini_provider import GeminiProvider
        return GeminiProvider(model=model or "gemini-1.5-pro", api_key=api_key)

    if name in ("claude", "anthropic"):
        from value_semantics.nl2sql.providers.claude_provider import ClaudeProvider
        return ClaudeProvider(model=model or "claude-sonnet-4-6", api_key=api_key)

    raise ValueError(
        f"Unknown provider '{provider}'. Choose from: openai, gemini, claude"
    )


__all__ = ["BaseLLMProvider", "get_provider"]
