from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ViolationType(str, Enum):
    # Aggregation violations
    SUM_ON_IDENTIFIER = "SUM_ON_IDENTIFIER"
    AVG_ON_IDENTIFIER = "AVG_ON_IDENTIFIER"
    NUMERIC_AGG_ON_IDENTIFIER = "NUMERIC_AGG_ON_IDENTIFIER"
    SUM_FORBIDDEN = "SUM_FORBIDDEN"           # should_not_sum=True
    AVG_FORBIDDEN = "AVG_FORBIDDEN"           # should_not_average=True
    # Process violations
    ROW_LOCAL_ON_PROCESS_STATE = "ROW_LOCAL_ON_PROCESS_STATE"   # WHERE on TransitionDerivedState
    MISSING_TEMPORAL_CONTEXT = "MISSING_TEMPORAL_CONTEXT"       # process column used without window
    # Quantitative violations
    MAGNITUDE_COMPARE_ON_IDENTIFIER = "MAGNITUDE_COMPARE_ON_IDENTIFIER"  # > < on ID
    # Role violations
    AGG_ON_NON_MEASURE = "AGG_ON_NON_MEASURE"
    ORDER_BY_IDENTIFIER = "ORDER_BY_IDENTIFIER"  # ORDER BY on identifier to rank entities


class Severity(str, Enum):
    CRITICAL = "critical"   # definitely wrong
    WARNING = "warning"     # likely wrong
    INFO = "info"


@dataclass
class ColumnVST:
    """Typed operational semantic constraints for a single column, built from VSL JSON."""
    table: str
    column: str

    # Roles
    semantic_role: Optional[str] = None          # IDENTIFIER, EVIDENCE, SEGMENTATION_DRIVER, etc.
    process_role: Optional[str] = None           # EVENT_KEY, EVENT_MEASURE, TransitionDerivedState, etc.
    quantitative_role: Optional[str] = None      # MEASUREMENT, COUNT, RATE, DURATION, etc.
    semantic_type: Optional[str] = None          # ID_NUMERIC, CURRENCY_AMOUNT, ENUM_CATEGORY, etc.

    # Hard boolean flags from query_constraints
    is_identifier: bool = False
    should_not_sum: bool = False
    should_not_average: bool = False
    should_not_compare_magnitude: bool = False
    can_aggregate: bool = True
    can_group_by: bool = True
    can_join: bool = True

    # Process-specific
    requires_temporal_context: bool = False      # True for TransitionDerivedState / StateVariable

    # Explicit operation lists from VSL JSON
    disallowed_operations: list[str] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)

    confidence: float = 0.0

    # --- Enriched fields (populated from full VSL JSON) ---

    # Quantitative subtype from quantitative_vst (e.g. "snapshot_value", "flow_amount")
    quantitative_subtype: Optional[str] = None

    # Safe/forbidden aggregations from quantitative_vst.safe_aggregation
    safe_aggregations: list[str] = field(default_factory=list)
    forbidden_aggregations: list[str] = field(default_factory=list)

    # Capability flags from query_constraints.supports_*
    supports_outlier_detection: bool = False
    supports_change_detection: bool = False
    supports_state_tracking: bool = False
    supports_temporal_aggregation: bool = False
    supports_distributional_reasoning: bool = False

    # Per-group statistical profiles from conditional_value_distribution
    # Structure: {group_col: {profiles: {group_val: {p50, p90, p99, typical_range, extreme_range}}}}
    statistical_profiles: dict = field(default_factory=dict)

    # Derived metric candidates from quantitative_vst.derived_metric_candidates
    derived_metrics: list[dict] = field(default_factory=list)

    def forbids_sql_op(self, sql_op: str) -> bool:
        """
        Check whether a SQL operation is forbidden by this column's VST constraints.
        sql_op is a normalized uppercase string: SUM, AVG, MAX, MIN, COUNT, WHERE_FILTER,
        GROUP_BY, ORDER_BY, GREATER_THAN, LESS_THAN.
        """
        # Explicit disallow list from VSL JSON takes priority
        if sql_op in self.disallowed_operations:
            return True

        if sql_op == "SUM" and (self.is_identifier or self.should_not_sum):
            return True
        if sql_op == "AVG" and (self.is_identifier or self.should_not_average):
            return True
        if sql_op in ("MAX", "MIN") and self.is_identifier and not self.can_aggregate:
            return True
        if sql_op in ("GREATER_THAN", "LESS_THAN") and self.should_not_compare_magnitude:
            return True

        return False


@dataclass
class Violation:
    table: str
    column: str
    sql_op: str
    violation_type: ViolationType
    severity: Severity
    message: str
    rewrite_hint: Optional[str] = None


@dataclass
class ValidationResult:
    sql: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(v.severity == Severity.CRITICAL for v in self.violations)

    @property
    def critical_violations(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.CRITICAL]

    @property
    def warning_violations(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.WARNING]

    def summary(self) -> dict:
        return {
            "valid": self.is_valid,
            "total_violations": len(self.violations),
            "critical": len(self.critical_violations),
            "warnings": len(self.warning_violations),
            "violations": [
                {
                    "column": v.column,
                    "table": v.table,
                    "operation": v.sql_op,
                    "type": v.violation_type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "rewrite_hint": v.rewrite_hint,
                }
                for v in self.violations
            ],
        }
