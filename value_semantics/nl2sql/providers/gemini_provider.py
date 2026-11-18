import os

from value_semantics.nl2sql.providers.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "google-genai package is required: pip install google-genai"
            )

        self.model_name = model
        self._types = types
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
            ),
        )
        return response.text.strip()
