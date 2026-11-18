from __future__ import annotations

import json
from pathlib import Path


_TYPE_MAP = {
    "int64": "INTEGER",
    "int32": "INTEGER",
    "float64": "NUMERIC",
    "float32": "NUMERIC",
    "object": "TEXT",
    "str": "TEXT",
    "bool": "BOOLEAN",
    "datetime64": "TIMESTAMP",
    "datetime64[ns]": "TIMESTAMP",
}


def _sql_type(declared_type: str) -> str:
    return _TYPE_MAP.get(declared_type, declared_type.upper())


def load_vsl_schema(index_path: str | Path, dialect: str = "postgresql") -> dict:
    """
    Build a schema dict (compatible with NL2SQLEngine) from a VSL index file.

    Args:
        index_path: Path to the index.json for the VSL database
                    (e.g. "demos/bird_finance_vsl/index.json")
        dialect:    SQL dialect string passed through to the prompt builder

    Returns:
        schema dict with keys: "dialect", "tables"
        Each table entry has: "columns", "primary_key", "foreign_keys"
    """
    index_path = Path(index_path)
    base_dir = index_path.parent.parent.parent  # repo root when path is demos/*/index.json

    with open(index_path) as f:
        index = json.load(f)

    schema: dict = {"dialect": dialect, "tables": {}}

    # 1. Load each table VSL → columns + inferred PK
    for entry in index["tables"]:
        table_name = entry["table"]
        vsl_path = base_dir / entry["path"]

        with open(vsl_path) as f:
            vsl = json.load(f)

        columns = {}
        pk_candidates = []

        for col_name, col_meta in vsl.get("columns", {}).items():
            declared = col_meta.get("declared_type", "TEXT")
            columns[col_name] = _sql_type(declared)

            stats = col_meta.get("stats", {})
            row_count = stats.get("row_count", 0)
            distinct_count = stats.get("distinct_count", 0)
            null_count = stats.get("null_count", 0)

            is_unique = row_count > 0 and distinct_count == row_count
            is_id_col = col_name.endswith("_id") or col_name == "id"

            if is_unique and is_id_col and null_count == 0:
                pk_candidates.append(col_name)

        schema["tables"][table_name] = {
            "columns": columns,
            "primary_key": pk_candidates[:1],  # take the first strong candidate
            "foreign_keys": [],
        }

    # 2. Load FK relationships from database_vsl.json
    db_vsl_path_rel = index.get("database_vsl")
    if db_vsl_path_rel:
        db_vsl_path = base_dir / db_vsl_path_rel
        if db_vsl_path.exists():
            with open(db_vsl_path) as f:
                db_vsl = json.load(f)

            for link in db_vsl.get("relational_links", []):
                child_table = link.get("join_constraints", {}).get("child_table")
                child_col = link.get("source_column")
                parent_table = link.get("join_constraints", {}).get("parent_table")
                parent_col = link.get("target_column")

                if not all([child_table, child_col, parent_table, parent_col]):
                    continue

                if child_table not in schema["tables"]:
                    continue

                fk = {
                    "column": child_col,
                    "references": f"{parent_table}.{parent_col}",
                }

                existing = schema["tables"][child_table]["foreign_keys"]
                if fk not in existing:
                    existing.append(fk)

    return schema


def load_schema(path: str | Path) -> dict:
    """
    Auto-detect schema format and load it.

    Supports:
    - VSL index.json  (has a "tables" list with "path" entries)
    - Raw schema.json (has a "tables" dict with column definitions)
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    tables = data.get("tables", {})
    # VSL index: "tables" is a list of {"table": ..., "path": ...}
    if isinstance(tables, list):
        return load_vsl_schema(path)

    # Raw schema: "tables" is already a dict of table definitions
    return data
