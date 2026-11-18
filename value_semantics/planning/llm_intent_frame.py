import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMIntentFrameExtractor:
    """
    Uses an LLM to extract a generic intent frame.

    This does NOT generate SQL.
    It only converts natural language into a structured planning frame.
    """

    def __init__(self, model=None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def extract(self, intent, schema_summary=None):
        prompt = self._build_prompt(intent, schema_summary or {})

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an intent-frame extractor for semantic query planning. "
                        "You do not generate SQL. Return strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        text = response.choices[0].message.content.strip()

        return self._safe_json(text)

    def _build_prompt(self, intent, schema_summary):
        return f"""
Extract a generic semantic intent frame from the user question.

Do NOT generate SQL.
Do NOT choose exact tables unless strongly implied.
Do NOT invent columns.
Return JSON only.

Question:
{intent}

Available schema summary:
{json.dumps(schema_summary, indent=2)}

Return this JSON structure:

{{
  "task": "select | filter | rank | count | aggregate | trend | persistence | transition | compare",
  "target_entity": "entity being returned or null",
  "measure_phrase": "measure or behavior being computed or null",
  "aggregation": "COUNT | SUM | AVG | MAX | MIN | RATIO | TREND | null",
  "comparison": "high | low | unusual_high | unusual_low | increasing | decreasing | null",
  "filters": [
    {{
      "phrase": "filter phrase",
      "type": "categorical | numeric | temporal | ordinal | policy | unknown"
    }}
  ],
  "grouping_phrase": "grouping dimension or null",
  "requires_join": true,
  "temporal_intent": true,
  "persistence_intent": true,
  "output_shape": "rows | scalar | per_entity | per_group | top_k",
  "top_k": null,
  "ambiguities": [],
  "reasoning_notes": "short explanation"
}}
""".strip()

    def _safe_json(self, text):
        text = text.strip()

        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(text)
        except Exception:
            return {
                "task": "unknown",
                "target_entity": None,
                "measure_phrase": None,
                "aggregation": None,
                "comparison": None,
                "filters": [],
                "grouping_phrase": None,
                "requires_join": None,
                "temporal_intent": None,
                "persistence_intent": None,
                "output_shape": None,
                "top_k": None,
                "ambiguities": ["LLM intent-frame parsing failed"],
                "raw_output": text,
            }