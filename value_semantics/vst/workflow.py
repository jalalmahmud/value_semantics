"""
Multi-step analytical workflow planner for VSL.

Extends single-step NL→SQL to a two-or-three-step CTE pipeline:

  NL → decompose into steps (LLM)
     → per-step VST-constrained generation (VSLPlanner + LLM)
     → VST propagation for derived columns
     → composed CTE SQL

Three contributions relative to the single-step planner:
  1. Semantic decomposition  — LLM breaks intent into analytically coherent steps
  2. VST propagation calculus — derived column VSTs inferred from operator patterns
  3. Cross-step validation   — each step validated against source VSTs + all
                               derived VSTs from previous steps
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from value_semantics.nl2sql.providers import BaseLLMProvider
    from value_semantics.vst.model import ColumnVST, ValidationResult
    from value_semantics.vst.policy import PolicyRegistry
    from value_semantics.vst.registry import VSTRegistry


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WorkflowStep:
    step_id: int
    cte_name: str
    description: str
    depends_on: list[str] = field(default_factory=list)

    sql: Optional[str] = None
    detected_intent: Optional[str] = None
    derived_vsts: dict[str, "ColumnVST"] = field(default_factory=dict)
    validation: Optional["ValidationResult"] = None
    retries: int = 0


@dataclass
class WorkflowPlan:
    question: str
    steps: list[WorkflowStep]
    final_sql: Optional[str] = None


@dataclass
class WorkflowResult:
    question: str
    sql: str
    provider: str
    model: str
    workflow_plan: WorkflowPlan
    raw_response: str = ""

    @property
    def steps(self) -> list[WorkflowStep]:
        return self.workflow_plan.steps


# ---------------------------------------------------------------------------
# VST propagation calculus
# ---------------------------------------------------------------------------

class VSTPropagator:
    """
    Infers VSTs for columns produced by a CTE's SELECT clause.

    Propagation rules (SQL operator pattern → VST role):
      SUM(x) / COUNT(x)   → RATE    — non-additive, ComparativeAxis
      SUM(x)              → MEASUREMENT — additive, ComparativeAxis-eligible
      AVG(x)              → MEASUREMENT — comparable
      COUNT(x)            → COUNT   — supports outlier detection
      LAG/LEAD/RANK(x)    → TransitionDerivedState — temporal, change-detection
      DATE_TRUNC/EXTRACT  → EVENT_TIME — time bucket, groupable
      STDDEV(x)           → MEASUREMENT — outlier reference
      plain column        → inherit from source registry (confidence × 0.9)
    """

    def propagate(
        self,
        sql: str,
        cte_name: str,
        source_registry: "VSTRegistry",
    ) -> dict[str, "ColumnVST"]:
        """Return {column_name: ColumnVST} for every derived column in the SELECT."""
        derived: dict[str, "ColumnVST"] = {}
        try:
            import sqlglot
            import sqlglot.expressions as exp

            tree = sqlglot.parse_one(sql, dialect="postgres")
            select = tree.find(exp.Select)
            if not select:
                return derived

            for col_expr in select.expressions:
                if isinstance(col_expr, exp.Alias):
                    col_name = col_expr.alias
                    expr_sql = col_expr.this.sql(dialect="postgres").upper()
                elif isinstance(col_expr, exp.Column):
                    col_name = col_expr.name
                    expr_sql = col_name.upper()
                elif isinstance(col_expr, exp.Star):
                    continue
                else:
                    col_name = col_expr.alias_or_name
                    expr_sql = col_expr.sql(dialect="postgres").upper() if col_name else ""

                if not col_name:
                    continue

                vst = self._classify(col_name, expr_sql, cte_name, source_registry)
                if vst:
                    derived[col_name] = vst

        except Exception:
            pass

        return derived

    def _classify(
        self,
        col_name: str,
        expr_sql: str,
        table: str,
        registry: "VSTRegistry",
    ) -> Optional["ColumnVST"]:
        from value_semantics.vst.model import ColumnVST

        # Ratio: division involving aggregation → RATE (non-additive)
        if "/" in expr_sql and re.search(r"\b(SUM|COUNT|AVG)\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                quantitative_role="RATE", semantic_role="EVIDENCE",
                supports_outlier_detection=True,
                supports_distributional_reasoning=True,
                should_not_sum=True,
                confidence=0.85,
            )

        # SUM → additive aggregate
        if re.search(r"\bSUM\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                quantitative_role="MEASUREMENT", semantic_role="EVIDENCE",
                supports_outlier_detection=True,
                supports_distributional_reasoning=True,
                confidence=0.75,
            )

        # AVG → comparable measure
        if re.search(r"\bAVG\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                quantitative_role="MEASUREMENT", semantic_role="EVIDENCE",
                supports_outlier_detection=True,
                supports_distributional_reasoning=True,
                confidence=0.80,
            )

        # COUNT → count measure
        if re.search(r"\bCOUNT\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                quantitative_role="COUNT", semantic_role="EVIDENCE",
                supports_outlier_detection=True,
                confidence=0.80,
            )

        # Window / lag / lead → temporal delta
        if re.search(r"\b(LAG|LEAD|ROW_NUMBER|RANK|PERCENT_RANK|NTILE)\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                process_role="TransitionDerivedState",
                requires_temporal_context=True,
                supports_change_detection=True,
                supports_state_tracking=True,
                confidence=0.80,
            )

        # Date bucketing → event-time dimension
        if re.search(
            r"\b(DATE_TRUNC|DATE_PART|EXTRACT|TO_CHAR|YEAR|MONTH|WEEK)\s*\(",
            expr_sql,
        ):
            return ColumnVST(
                table=table, column=col_name,
                semantic_role="EVENT_TIME", process_role="EVENT_TIME",
                can_group_by=True,
                confidence=0.85,
            )

        # STDDEV / VARIANCE → outlier reference
        if re.search(r"\b(STDDEV|STDDEV_POP|STDDEV_SAMP|VARIANCE|VAR_POP)\s*\(", expr_sql):
            return ColumnVST(
                table=table, column=col_name,
                quantitative_role="MEASUREMENT", semantic_role="EVIDENCE",
                supports_outlier_detection=True,
                confidence=0.70,
            )

        # Plain column pass-through → inherit from source registry
        candidates = registry.get_by_column(col_name.lower())
        if candidates:
            src = candidates[0]
            return ColumnVST(
                table=table, column=col_name,
                semantic_role=src.semantic_role,
                process_role=src.process_role,
                quantitative_role=src.quantitative_role,
                is_identifier=src.is_identifier,
                should_not_sum=src.should_not_sum,
                can_aggregate=src.can_aggregate,
                can_group_by=src.can_group_by,
                confidence=round(src.confidence * 0.9, 2),
            )

        return None


# ---------------------------------------------------------------------------
# WorkflowPlanner
# ---------------------------------------------------------------------------

_DECOMPOSE_SYSTEM = """\
You are an analytical workflow planner for SQL databases.
Decompose a natural language analytical intent into 2-3 sequential steps.
Each step will become a SQL CTE in the final composed query.

Rules:
- Step 1 always computes a per-entity, per-period intermediate
  (monthly totals, event counts per group, running values).
- Step 2 applies analytical reasoning on step 1 output
  (trend detection, outlier filtering, consecutive-period checks, ranking).
- Use 3 steps only when step 2 itself produces an intermediate
  that step 3 further filters or ranks.
- CTE names must be short, descriptive, snake_case.
- Respond with JSON only.
"""

_DECOMPOSE_PROMPT = """\
Decompose this analytical intent into 2-3 sequential SQL steps.

Intent: {question}

Schema (for context only — do not generate SQL yet):
{schema_excerpt}

Return JSON:
{{
  "steps": [
    {{"step": 1, "cte_name": "...", "description": "...", "depends_on": []}},
    {{"step": 2, "cte_name": "...", "description": "...", "depends_on": ["<step1_cte_name>"]}}
  ]
}}
"""

_STEP_SYSTEM = """\
You are an expert SQL assistant generating one step of a multi-step analytical workflow.
Generate a SELECT query that will be used as a SQL CTE.
Do not include a WITH clause — write only the SELECT body.
"""


class WorkflowPlanner:
    """
    Orchestrates multi-step analytical workflow generation using VSL.

    Typical call flow (via NL2SQLEngine.generate_workflow):
      1. decompose()     — LLM splits NL intent into WorkflowSteps
      2. plan_step()     — for each step: VSLPlanner constraints + LLM generation
                           + VST propagation for derived columns
      3. compose()       — assembles step SQLs into WITH … SELECT

    The key difference from single-step planning:
      - Cross-step validation: each step is validated against source VSTs
        PLUS derived VSTs from all previous steps.
      - Derived columns produced in step N get propagated VSTs that the
        planner in step N+1 can use for constraint-building.
    """

    def __init__(self) -> None:
        self._propagator = VSTPropagator()

    # ------------------------------------------------------------------
    # 1. Decompose
    # ------------------------------------------------------------------

    def decompose(
        self,
        question: str,
        schema_text: str,
        provider: "BaseLLMProvider",
    ) -> list[WorkflowStep]:
        prompt = _DECOMPOSE_PROMPT.format(
            question=question,
            schema_excerpt=schema_text[:2000],
        )
        raw = provider.complete(_DECOMPOSE_SYSTEM, prompt)

        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                data = json.loads(m.group())
                return [
                    WorkflowStep(
                        step_id=s["step"],
                        cte_name=s["cte_name"],
                        description=s["description"],
                        depends_on=s.get("depends_on", []),
                    )
                    for s in data.get("steps", [])
                ]
        except Exception:
            pass

        # Graceful fallback: treat as single-step
        return [WorkflowStep(step_id=1, cte_name="result", description=question)]

    # ------------------------------------------------------------------
    # 2. Plan one step
    # ------------------------------------------------------------------

    def plan_step(
        self,
        step: WorkflowStep,
        question: str,
        schema_text: str,
        registry: "VSTRegistry",
        previous_steps: list[WorkflowStep],
        provider: "BaseLLMProvider",
        policy_registry: Optional["PolicyRegistry"] = None,
        max_retries: int = 2,
    ) -> None:
        """Generate, validate, and propagate VSTs for *step* (mutates in place)."""
        from value_semantics.vst.planner import VSLPlanner
        from value_semantics.vst.validator import VSTValidator
        from value_semantics.nl2sql.sql_extractor import extract_sql

        planner = VSLPlanner()
        validator = VSTValidator()

        merged = self._merged_registry(registry, previous_steps)
        full_schema = self._augmented_schema(schema_text, previous_steps)

        intent = planner.classify_intent(step.description + " " + question)
        constraints = planner.build_constraints(
            intent, merged,
            question=step.description,
            policy_registry=policy_registry,
        )

        step_question = (
            f"[Step {step.step_id}] {step.description}\n"
            f"(Overall intent: {question})"
        )
        prompt = planner.build_constrained_prompt(
            question=step_question,
            schema_text=full_schema,
            constraints=constraints,
            intent=intent,
        )

        raw = provider.complete(_STEP_SYSTEM, prompt)
        sql = extract_sql(raw)
        retries = 0

        for _ in range(max_retries):
            validation = validator.validate(sql, merged)
            if validation.is_valid:
                break
            retries += 1
            rejection_prompt = planner.build_rejection_prompt(
                original_question=step_question,
                schema_text=full_schema,
                rejected_sql=sql,
                violations=validation.critical_violations,
                constraints=constraints,
                intent=intent,
            )
            raw = provider.complete(_STEP_SYSTEM, rejection_prompt)
            sql = extract_sql(raw)

        step.sql = sql
        step.detected_intent = intent.value
        step.retries = retries
        step.validation = validator.validate(sql, merged)
        step.derived_vsts = self._propagator.propagate(sql, step.cte_name, registry)

    # ------------------------------------------------------------------
    # 3. Compose
    # ------------------------------------------------------------------

    def compose(self, steps: list[WorkflowStep]) -> str:
        """Assemble step SQLs into a single WITH … SELECT query."""
        if not steps:
            return ""
        if len(steps) == 1:
            return steps[0].sql or ""

        cte_parts = [
            f"{s.cte_name} AS (\n{self._indent(s.sql)}\n)"
            for s in steps[:-1]
            if s.sql
        ]
        last_sql = steps[-1].sql or "SELECT NULL"

        return "WITH " + ",\n".join(cte_parts) + "\n" + last_sql

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merged_registry(
        self,
        source: "VSTRegistry",
        previous_steps: list[WorkflowStep],
    ) -> "VSTRegistry":
        from value_semantics.vst.registry import VSTRegistry
        merged = VSTRegistry()
        merged._store.update(source._store)
        for step in previous_steps:
            for col_name, vst in step.derived_vsts.items():
                merged._store[(step.cte_name, col_name)] = vst
        return merged

    def _augmented_schema(
        self,
        schema_text: str,
        previous_steps: list[WorkflowStep],
    ) -> str:
        if not previous_steps:
            return schema_text
        cte_notes = ["-- Available CTEs from previous workflow steps:"]
        for step in previous_steps:
            cols = "\n".join(
                f"  {col}  -- {vst.quantitative_role or vst.semantic_role or 'value'}"
                for col, vst in step.derived_vsts.items()
            ) or "  -- (columns unknown)"
            cte_notes.append(f"-- {step.cte_name}: {step.description}\n{cols}")
        return "\n".join(cte_notes) + "\n\n" + schema_text

    @staticmethod
    def _indent(sql: str) -> str:
        return "\n".join("  " + line for line in sql.splitlines())
