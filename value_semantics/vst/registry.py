from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from value_semantics.vst.model import ColumnVST

# Process roles that require temporal context rather than row-local predicates
_TEMPORAL_PROCESS_ROLES = {
    "TransitionDerivedState",
    "StateVariable",
    "TRANSITION_DERIVED_STATE",
    "STATE_VARIABLE",
}


def _build_column_vst(table: str, column: str, sem: dict) -> ColumnVST:
    """Parse one column's VSL semantics dict into a typed ColumnVST."""
    value_sem = sem.get("value_semantics", {})
    role_sem = sem.get("semantic_role", {})
    qvst = sem.get("quantitative_vst", {})
    process_role_sem = sem.get("process_vst_role", {})
    qc_outer = sem.get("query_constraints", {})
    qc = qc_outer.get("query_constraints", {})

    process_role = process_role_sem.get("role")
    requires_temporal = process_role in _TEMPORAL_PROCESS_ROLES

    # Merge disallowed ops from both query_constraints and semantic_role constraints
    disallowed: list[str] = list(qc.get("disallowed_operations", []))
    role_qc = role_sem.get("query_constraints", {})
    if not role_qc.get("can_aggregate", True):
        for op in ("SUM", "AVG", "MIN", "MAX"):
            if op not in disallowed:
                disallowed.append(op)

    # --- Enriched fields ---
    safe_agg = qvst.get("safe_aggregation", {}) if qvst else {}
    forbidden_aggs: list[str] = list(safe_agg.get("forbidden", []))
    safe_aggs: list[str] = list(safe_agg.get("allowed", []))

    # Fix: quantitative_vst.safe_aggregation.forbidden is authoritative for SUM/AVG prohibition
    should_not_sum = bool(qc.get("should_not_sum", False)) or "SUM" in forbidden_aggs
    should_not_average = bool(qc.get("should_not_average", False)) or "AVG" in forbidden_aggs

    # Merge forbidden aggs into disallowed list for consistent enforcement
    for op in forbidden_aggs:
        if op not in disallowed:
            disallowed.append(op)

    # Statistical profiles: full conditional_value_distribution dict
    statistical_profiles = sem.get("conditional_value_distribution", {})

    # Derived metrics from quantitative_vst
    derived_metrics = list(qvst.get("derived_metric_candidates", [])) if qvst else []

    return ColumnVST(
        table=table,
        column=column,
        semantic_role=role_sem.get("primary_role"),
        process_role=process_role,
        quantitative_role=qvst.get("role") if qvst else None,
        semantic_type=value_sem.get("semantic_type"),
        is_identifier=bool(value_sem.get("is_identifier", False)),
        should_not_sum=should_not_sum,
        should_not_average=should_not_average,
        should_not_compare_magnitude=bool(qc.get("should_not_compare_magnitude", False)),
        can_aggregate=bool(role_qc.get("can_aggregate", True)),
        can_group_by=bool(role_qc.get("can_group_by", True)),
        can_join=bool(role_qc.get("can_join", True)),
        requires_temporal_context=requires_temporal,
        disallowed_operations=disallowed,
        allowed_operations=list(qc.get("allowed_operations", [])),
        confidence=float(value_sem.get("confidence", 0.0)),
        # Enriched
        quantitative_subtype=qvst.get("subtype") if qvst else None,
        safe_aggregations=safe_aggs,
        forbidden_aggregations=forbidden_aggs,
        supports_outlier_detection=bool(qc.get("supports_outlier_detection", False)),
        supports_change_detection=bool(qc.get("supports_change_detection", False)),
        supports_state_tracking=bool(qc.get("supports_state_tracking", False)),
        supports_temporal_aggregation=bool(qc.get("supports_temporal_aggregation", False)),
        supports_distributional_reasoning=bool(qc.get("supports_distributional_reasoning", False)),
        statistical_profiles=statistical_profiles,
        derived_metrics=derived_metrics,
    )


class VSTRegistry:
    """
    Persistent store of typed ColumnVSTs built from VSL JSON output.

    VSTs are addressable by (table, column) and participate directly in
    SQL validation and rewriting — no LLM prompt injection.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], ColumnVST] = {}

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    @classmethod
    def from_vsl_dir(cls, vsl_dir: str | Path) -> "VSTRegistry":
        """
        Build a registry from all *_vsl.json files in a VSL output directory.
        Skips database_vsl.json (cross-table metadata).
        """
        registry = cls()
        vsl_dir = Path(vsl_dir)

        for vsl_file in sorted(vsl_dir.glob("*_vsl.json")):
            if vsl_file.name == "database_vsl.json":
                continue
            registry._load_table_vsl(vsl_file)

        return registry

    @classmethod
    def from_vsl_file(cls, vsl_file: str | Path) -> "VSTRegistry":
        """Build a registry from a single table VSL JSON file."""
        registry = cls()
        registry._load_table_vsl(Path(vsl_file))
        return registry

    def _load_table_vsl(self, path: Path) -> None:
        with open(path) as f:
            data = json.load(f)

        table = data.get("table", path.stem.replace("_vsl", ""))
        semantics = data.get("semantics", {})

        for column, sem in semantics.items():
            vst = _build_column_vst(table, column, sem)
            self._store[(table, column)] = vst

    def merge(self, other: "VSTRegistry") -> None:
        """Merge another registry into this one."""
        self._store.update(other._store)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, table: str, column: str) -> Optional[ColumnVST]:
        vst = self._store.get((table, column))
        if vst:
            return vst
        # Try case-insensitive lookup
        for (t, c), v in self._store.items():
            if t.lower() == table.lower() and c.lower() == column.lower():
                return v
        return None

    def get_by_column(self, column: str) -> list[ColumnVST]:
        """Return all VSTs for a given column name across all tables."""
        return [v for (_, c), v in self._store.items() if c.lower() == column.lower()]

    def has(self, table: str, column: str) -> bool:
        return self.get(table, column) is not None

    def tables(self) -> list[str]:
        return sorted({t for t, _ in self._store})

    def columns(self, table: str) -> list[str]:
        return [c for (t, c) in self._store if t == table]

    def all_vsts(self) -> list[ColumnVST]:
        return list(self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"VSTRegistry({len(self._store)} columns across {len(self.tables())} tables)"
