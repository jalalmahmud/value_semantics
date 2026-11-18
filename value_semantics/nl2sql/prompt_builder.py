from __future__ import annotations


SYSTEM_PROMPT = """\
You are an expert SQL assistant. Your job is to convert natural language questions into \
correct, executable SQL queries.

Rules:
- Output only a single SQL query inside a ```sql code block.
- Do not explain your reasoning outside the code block.
- Use standard SQL that is compatible with PostgreSQL unless told otherwise.
- If the question is ambiguous, make the most reasonable interpretation.
- Use table and column names exactly as provided in the schema.
- Never hallucinate columns or tables that are not in the schema.
"""


def build_schema_text(schema: dict) -> str:
    """
    Convert a schema dict into a DDL-style text block.

    schema format:
      {
        "tables": {
          "table_name": {
            "columns": {
              "col_name": "TYPE",
              ...
            },
            "primary_key": ["col"],          # optional
            "foreign_keys": [                # optional
              {"column": "col", "references": "other_table.other_col"}
            ],
            "description": "...",            # optional
          }
        },
        "dialect": "postgresql"              # optional
      }
    """
    lines: list[str] = []
    tables = schema.get("tables", {})

    for table_name, table_def in tables.items():
        description = table_def.get("description")
        if description:
            lines.append(f"-- {description}")

        lines.append(f"CREATE TABLE {table_name} (")

        columns = table_def.get("columns", {})
        col_profiles = table_def.get("column_profiles", {})
        col_lines = []
        for col_name, col_type in columns.items():
            profile = col_profiles.get(col_name, {})
            samples = profile.get("sample_values", [])
            distinct = profile.get("distinct_count")
            null_frac = profile.get("null_fraction")
            comment_parts = []
            if distinct is not None:
                comment_parts.append(f"distinct={distinct}")
            if null_frac is not None and null_frac > 0:
                comment_parts.append(f"nulls={null_frac:.0%}")
            if samples:
                sample_str = ", ".join(repr(s) for s in samples[:5])
                comment_parts.append(f"e.g. {sample_str}")
            comment = f"  -- {', '.join(comment_parts)}" if comment_parts else ""
            col_lines.append(f"    {col_name} {col_type}{comment}")

        pk = table_def.get("primary_key", [])
        if pk:
            col_lines.append(f"    PRIMARY KEY ({', '.join(pk)})")

        fks = table_def.get("foreign_keys", [])
        for fk in fks:
            col_lines.append(
                f"    FOREIGN KEY ({fk['column']}) REFERENCES {fk['references']}"
            )

        lines.append(",\n".join(col_lines))
        lines.append(");\n")

    return "\n".join(lines)


def build_user_prompt(question: str, schema: dict) -> str:
    dialect = schema.get("dialect", "PostgreSQL")
    schema_text = build_schema_text(schema)

    return f"""\
Database dialect: {dialect}

Schema:
```sql
{schema_text}
```

Question: {question}

Write a SQL query that answers the question.
"""
