from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import sqlglot
import sqlglot.expressions as exp


@dataclass
class ColumnOperation:
    """A single (column, SQL operation) pair extracted from a SQL query."""
    column: str
    table: Optional[str]      # None when table cannot be resolved from the SQL
    sql_op: str               # Normalised: SUM, AVG, MAX, MIN, COUNT, WHERE_FILTER,
                              # GROUP_BY, ORDER_BY, GREATER_THAN, LESS_THAN, JOIN

    def __repr__(self) -> str:
        tbl = f"{self.table}." if self.table else ""
        return f"ColumnOperation({tbl}{self.column}, {self.sql_op})"


# Maps sqlglot aggregate expression classes → normalised op name
_AGG_CLASS_TO_OP: dict[type, str] = {
    exp.Sum: "SUM",
    exp.Avg: "AVG",
    exp.Max: "MAX",
    exp.Min: "MIN",
    exp.Count: "COUNT",
    exp.CountIf: "COUNT",
}

# Comparison operators that imply magnitude comparison
_MAGNITUDE_OPS = {">": "GREATER_THAN", "<": "LESS_THAN", ">=": "GREATER_THAN", "<=": "LESS_THAN"}


def _col_name(node: exp.Column) -> tuple[str, Optional[str]]:
    """Return (column_name, table_name_or_None) from a Column AST node."""
    col = node.name.lower()
    tbl = node.table.lower() if node.table else None
    return col, tbl


class SQLAnalyzer:
    """
    Extracts (column, operation) pairs from a SQL string using sqlglot.

    This is the bridge between the LLM-generated SQL and the VSTRegistry:
    it determines which columns are being operated on and how, without
    any LLM involvement.
    """

    def analyze(self, sql: str, default_table: Optional[str] = None) -> list[ColumnOperation]:
        """
        Parse *sql* and return all ColumnOperations found.

        Args:
            sql:           SQL string (may contain VSL comments — they are ignored).
            default_table: Fallback table name when the SQL has no explicit table reference.
        """
        ops: list[ColumnOperation] = []

        try:
            statements = sqlglot.parse(sql, dialect="postgres", error_level=sqlglot.ErrorLevel.WARN)
        except Exception:
            return ops

        for statement in statements:
            if statement is None:
                continue
            ops.extend(self._extract(statement, default_table))

        return ops

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    def _extract(self, tree: exp.Expression, default_table: Optional[str]) -> list[ColumnOperation]:
        ops: list[ColumnOperation] = []

        # 1. Aggregate functions
        for agg_cls, op_name in _AGG_CLASS_TO_OP.items():
            for agg_node in tree.find_all(agg_cls):
                for col_node in agg_node.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, op_name))

        # 2. Window functions (contain aggregates — already captured above via find_all)

        # 3. WHERE predicates
        where = tree.find(exp.Where)
        if where:
            ops.extend(self._extract_where(where, default_table))

        # 4. GROUP BY
        group = tree.find(exp.Group)
        if group:
            for col_node in group.find_all(exp.Column):
                col, tbl = _col_name(col_node)
                ops.append(ColumnOperation(col, tbl or default_table, "GROUP_BY"))

        # 5. ORDER BY
        order = tree.find(exp.Order)
        if order:
            for col_node in order.find_all(exp.Column):
                col, tbl = _col_name(col_node)
                ops.append(ColumnOperation(col, tbl or default_table, "ORDER_BY"))

        # 6. JOIN conditions
        for join in tree.find_all(exp.Join):
            on = join.args.get("on")
            if on:
                for col_node in on.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, "JOIN"))

        return ops

    def _extract_where(
        self, where: exp.Where, default_table: Optional[str]
    ) -> list[ColumnOperation]:
        ops: list[ColumnOperation] = []

        for pred in where.find_all(exp.Condition):
            # Simple equality / IN / LIKE → WHERE_FILTER
            if isinstance(pred, (exp.EQ, exp.In, exp.Like, exp.Is)):
                for col_node in pred.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, "WHERE_FILTER"))

            # Magnitude comparisons → GREATER_THAN / LESS_THAN
            elif isinstance(pred, (exp.GT, exp.GTE)):
                for col_node in pred.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, "GREATER_THAN"))

            elif isinstance(pred, (exp.LT, exp.LTE)):
                for col_node in pred.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, "LESS_THAN"))

            # BETWEEN → both GREATER_THAN and LESS_THAN
            elif isinstance(pred, exp.Between):
                for col_node in pred.find_all(exp.Column):
                    col, tbl = _col_name(col_node)
                    ops.append(ColumnOperation(col, tbl or default_table, "GREATER_THAN"))
                    ops.append(ColumnOperation(col, tbl or default_table, "LESS_THAN"))

        return ops

    def has_window_functions(self, sql: str) -> bool:
        """Return True if the SQL uses any window (OVER) functions."""
        try:
            tree = sqlglot.parse_one(sql, dialect="postgres", error_level=sqlglot.ErrorLevel.WARN)
            return bool(tree and tree.find(exp.Window))
        except Exception:
            return False

    def has_temporal_aggregation(self, sql: str) -> bool:
        """
        Return True if the SQL aggregates over a time-bucketed column
        (DATE_TRUNC, EXTRACT, or time-grain GROUP BY).
        """
        sql_lower = sql.lower()
        temporal_markers = ["date_trunc", "extract(", "epoch", "month", "year", "week", "day"]
        has_group = "group by" in sql_lower
        return has_group and any(m in sql_lower for m in temporal_markers)
