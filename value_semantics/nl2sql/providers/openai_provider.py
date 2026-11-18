import os

from value_semantics.nl2sql.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required: pip install openai")

        self.model = model
        self.client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    # Models that reject explicit temperature values
    _NO_TEMPERATURE_MODELS = {"gpt-5", "o1", "o1-mini", "o3", "o3-mini"}

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        kwargs = dict(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if self.model not in self._NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = 0

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()
