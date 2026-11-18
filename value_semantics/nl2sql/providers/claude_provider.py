import os

from value_semantics.nl2sql.providers.base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package is required: pip install anthropic")

        self.model = model
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text.strip()
