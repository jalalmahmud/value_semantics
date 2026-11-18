from __future__ import annotations

from value_semantics.vst.analyzer import SQLAnalyzer, ColumnOperation
from value_semantics.vst.model import (
    ColumnVST,
    ValidationResult,
    Violation,
    ViolationType,
    Severity,
)
from value_semantics.vst.registry import VSTRegistry

# Aggregation ops that are meaningful magnitude operations on numeric columns
_NUMERIC_AGG_OPS = {"SUM", "AVG", "MAX", "MIN"}


class VSTValidator:
    """
    Validates a SQL string against VST constraints in a VSTRegistry.

    No LLM involved — purely programmatic constraint checking based on
    the typed ColumnVST artifacts in the registry.
    """

    def __init__(self) -> None:
        self._analyzer = SQLAnalyzer()

    def validate(
        self,
        sql: str,
        registry: VSTRegistry,
        default_table: str | None = None,
    ) -> ValidationResult:
        result = ValidationResult(sql=sql)
        ops = self._analyzer.analyze(sql, default_table=default_table)

        has_window = self._analyzer.has_window_functions(sql)
        has_temporal_agg = self._analyzer.has_temporal_aggregation(sql)

        seen: set[tuple[str, str, str]] = set()

        for op in ops:
            vst = self._resolve_vst(op, registry, default_table)
            if vst is None:
                continue

            key = (op.column, op.sql_op, vst.table)
            if key in seen:
                continue
            seen.add(key)

            violations = self._check(op, vst, has_window, has_temporal_agg)
            result.violations.extend(violations)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_vst(
        self,
        op: ColumnOperation,
        registry: VSTRegistry,
        default_table: str | None,
    ) -> ColumnVST | None:
        # Try explicit table from SQL first
        if op.table:
            vst = registry.get(op.table, op.column)
            if vst:
                return vst

        # Fall back to default_table
        if default_table:
            vst = registry.get(default_table, op.column)
            if vst:
                return vst

        # Search by column name across all tables (unambiguous single match)
        candidates = registry.get_by_column(op.column)
        if len(candidates) == 1:
            return candidates[0]

        return None

    def _check(
        self,
        op: ColumnOperation,
        vst: ColumnVST,
        has_window: bool,
        has_temporal_agg: bool,
    ) -> list[Violation]:
        violations: list[Violation] = []

        # ----------------------------------------------------------
        # 1. Aggregation on identifier column
        # ----------------------------------------------------------
        if op.sql_op in _NUMERIC_AGG_OPS and (
            vst.is_identifier or vst.semantic_role == "IDENTIFIER"
        ):
            vtype = (
                ViolationType.SUM_ON_IDENTIFIER
                if op.sql_op == "SUM"
                else ViolationType.NUMERIC_AGG_ON_IDENTIFIER
            )
            hint = f"Use COUNT({vst.column}) to count entities, not {op.sql_op}({vst.column})."
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op=op.sql_op,
                    violation_type=vtype,
                    severity=Severity.CRITICAL,
                    message=(
                        f"{op.sql_op}({vst.column}) is invalid: '{vst.column}' is an identifier "
                        f"(role={vst.semantic_role}) and cannot be meaningfully aggregated."
                    ),
                    rewrite_hint=hint,
                )
            )
            return violations  # don't stack more violations on the same op

        # ----------------------------------------------------------
        # 2. SUM/AVG forbidden by VST constraint
        # ----------------------------------------------------------
        if op.sql_op == "SUM" and vst.should_not_sum:
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op="SUM",
                    violation_type=ViolationType.SUM_FORBIDDEN,
                    severity=Severity.CRITICAL,
                    message=(
                        f"SUM({vst.column}) is forbidden: '{vst.column}' has "
                        f"should_not_sum=True (semantic_type={vst.semantic_type}, "
                        f"role={vst.semantic_role})."
                    ),
                    rewrite_hint=f"Use COUNT({vst.column}) or a distribution-aware aggregate.",
                )
            )
            return violations

        if op.sql_op == "AVG" and vst.should_not_average:
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op="AVG",
                    violation_type=ViolationType.AVG_FORBIDDEN,
                    severity=Severity.WARNING,
                    message=(
                        f"AVG({vst.column}) is discouraged: '{vst.column}' has "
                        f"should_not_average=True (role={vst.semantic_role})."
                    ),
                    rewrite_hint="Use PERCENTILE_CONT(0.5) for ordinal/categorical columns.",
                )
            )

        # ----------------------------------------------------------
        # 3. Explicit disallowed_operations check
        # ----------------------------------------------------------
        if vst.forbids_sql_op(op.sql_op):
            if not any(v.column == vst.column and v.sql_op == op.sql_op for v in violations):
                violations.append(
                    Violation(
                        table=vst.table,
                        column=vst.column,
                        sql_op=op.sql_op,
                        violation_type=ViolationType.AGG_ON_NON_MEASURE,
                        severity=Severity.CRITICAL,
                        message=(
                            f"{op.sql_op}({vst.column}) is disallowed by VST constraints "
                            f"(role={vst.semantic_role}, type={vst.semantic_type})."
                        ),
                        rewrite_hint=None,
                    )
                )

        # ----------------------------------------------------------
        # 4. Magnitude comparison on identifier
        # ----------------------------------------------------------
        if op.sql_op in ("GREATER_THAN", "LESS_THAN") and vst.should_not_compare_magnitude:
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op=op.sql_op,
                    violation_type=ViolationType.MAGNITUDE_COMPARE_ON_IDENTIFIER,
                    severity=Severity.CRITICAL,
                    message=(
                        f"Magnitude comparison ({op.sql_op}) on '{vst.column}' is invalid: "
                        f"'{vst.column}' is an identifier and has no meaningful magnitude ordering."
                    ),
                    rewrite_hint=f"Use equality filter ({vst.column} = value) or COUNT/GROUP BY instead.",
                )
            )

        # ----------------------------------------------------------
        # 5. Row-local filter on process-derived state column
        #    Catches both equality (WHERE_FILTER) and comparison (GREATER_THAN/LESS_THAN)
        # ----------------------------------------------------------
        if (
            op.sql_op in ("WHERE_FILTER", "GREATER_THAN", "LESS_THAN")
            and vst.requires_temporal_context
            and not has_window
            and not has_temporal_agg
        ):
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op=op.sql_op,
                    violation_type=ViolationType.ROW_LOCAL_ON_PROCESS_STATE,
                    severity=Severity.WARNING,
                    message=(
                        f"Row-local filter on '{vst.column}' may be semantically incorrect: "
                        f"'{vst.column}' is a {vst.process_role} requiring temporal aggregation "
                        f"over event sequences, not row-level filtering."
                    ),
                    rewrite_hint=(
                        "Rewrite using a CTE that aggregates events per entity over time "
                        "before applying the filter."
                    ),
                )
            )

        # ----------------------------------------------------------
        # 6. ORDER BY on identifier column used as ranking signal
        # ----------------------------------------------------------
        if op.sql_op == "ORDER_BY" and vst.is_identifier:
            violations.append(
                Violation(
                    table=vst.table,
                    column=vst.column,
                    sql_op="ORDER_BY",
                    violation_type=ViolationType.ORDER_BY_IDENTIFIER,
                    severity=Severity.CRITICAL,
                    message=(
                        f"ORDER BY {vst.column} is semantically invalid: '{vst.column}' is an "
                        f"IDENTIFIER with no magnitude meaning. Ranking by ID does not represent "
                        f"any business metric."
                    ),
                    rewrite_hint=(
                        f"Replace ORDER BY {vst.column} with a measure column "
                        f"(e.g. COUNT(*), SUM(amount)) to rank entities meaningfully."
                    ),
                )
            )

        return violations
