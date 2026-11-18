from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
import sqlglot.expressions as exp

from value_semantics.vst.model import (
    ValidationResult,
    Violation,
    ViolationType,
    Severity,
)
from value_semantics.vst.registry import VSTRegistry


@dataclass
class RewriteResult:
    original_sql: str
    rewritten_sql: str
    rewrites_applied: list[str] = field(default_factory=list)
    rewrites_skipped: list[str] = field(default_factory=list)

    @property
    def was_rewritten(self) -> bool:
        return self.original_sql.strip() != self.rewritten_sql.strip()


class SQLRewriter:
    """
    Programmatically rewrites SQL to fix VST constraint violations.

    Handles the violation types that can be corrected without changing
    query semantics: identifier aggregation rewrites and annotation of
    process-state violations requiring temporal restructuring.
    """

    def rewrite(
        self,
        validation: ValidationResult,
        registry: VSTRegistry,
    ) -> RewriteResult:
        sql = validation.sql
        applied: list[str] = []
        skipped: list[str] = []

        for violation in validation.violations:
            if violation.severity != Severity.CRITICAL:
                continue

            if violation.violation_type in (
                ViolationType.SUM_ON_IDENTIFIER,
                ViolationType.NUMERIC_AGG_ON_IDENTIFIER,
                ViolationType.SUM_FORBIDDEN,
            ):
                new_sql, changed = self._rewrite_agg_to_count(sql, violation)
                if changed:
                    sql = new_sql
                    applied.append(
                        f"Rewrote {violation.sql_op}({violation.column}) → "
                        f"COUNT({violation.column}) [{violation.violation_type.value}]"
                    )
                else:
                    skipped.append(
                        f"Could not rewrite {violation.sql_op}({violation.column}): "
                        "parse or substitution failed"
                    )

            elif violation.violation_type == ViolationType.ROW_LOCAL_ON_PROCESS_STATE:
                # Cannot safely auto-rewrite temporal restructuring — annotate instead
                sql = self._annotate_process_violation(sql, violation)
                applied.append(
                    f"Annotated row-local filter on process column '{violation.column}': "
                    "temporal restructuring required"
                )

            elif violation.violation_type == ViolationType.MAGNITUDE_COMPARE_ON_IDENTIFIER:
                skipped.append(
                    f"Magnitude comparison on '{violation.column}': "
                    "manual rewrite required (intent unclear)"
                )

        return RewriteResult(
            original_sql=validation.sql,
            rewritten_sql=sql,
            rewrites_applied=applied,
            rewrites_skipped=skipped,
        )

    # ------------------------------------------------------------------
    # Private rewrite helpers
    # ------------------------------------------------------------------

    def _rewrite_agg_to_count(self, sql: str, violation: Violation) -> tuple[str, bool]:
        """
        Replace SUM(col)/AVG(col)/MAX(col)/MIN(col) with COUNT(col) for
        identifier/forbidden columns.
        """
        try:
            tree = sqlglot.parse_one(sql, dialect="postgres", error_level=sqlglot.ErrorLevel.WARN)
        except Exception:
            return sql, False

        changed = False
        col_lower = violation.column.lower()

        agg_classes = {
            "SUM": exp.Sum,
            "AVG": exp.Avg,
            "MAX": exp.Max,
            "MIN": exp.Min,
        }
        target_cls = agg_classes.get(violation.sql_op)
        if target_cls is None:
            return sql, False

        for agg_node in list(tree.find_all(target_cls)):
            cols = list(agg_node.find_all(exp.Column))
            if any(c.name.lower() == col_lower for c in cols):
                # Replace the aggregation node with COUNT(col)
                new_agg = exp.Count(this=exp.Column(this=exp.Identifier(this=violation.column)))
                agg_node.replace(new_agg)
                changed = True

        if not changed:
            return sql, False

        rewritten = tree.sql(dialect="postgres")
        # Prepend a VSL audit comment
        comment = (
            f"-- VSL rewrite: {violation.sql_op}({violation.column}) → "
            f"COUNT({violation.column}) [{violation.violation_type.value}]\n"
        )
        return comment + rewritten, True

    def _annotate_process_violation(self, sql: str, violation: Violation) -> str:
        """
        Prepend a VSL warning comment for process-state violations that
        require temporal restructuring beyond automated rewriting.
        """
        hint = violation.rewrite_hint or (
            "Rewrite using a CTE that aggregates events per entity over time."
        )
        comment = (
            f"-- VSL WARNING: Row-local filter on process column '{violation.column}' "
            f"({violation.violation_type.value})\n"
            f"-- {hint}\n"
        )
        return comment + sql
