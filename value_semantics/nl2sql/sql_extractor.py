import re


def extract_sql(text: str) -> str:
    """
    Pull the SQL query out of a model response.

    Handles:
    - ```sql ... ``` fenced blocks
    - ``` ... ``` generic fenced blocks
    - Plain SQL (no fencing) — returned as-is after stripping
    """
    # Try ```sql ... ``` first, then generic ``` ... ```
    for pattern in (
        r"```sql\s*(.*?)```",
        r"```\s*(.*?)```",
    ):
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: strip and return the whole response
    return text.strip()
