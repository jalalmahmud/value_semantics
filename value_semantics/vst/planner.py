"""
VSL Query Planner

Classifies natural language intent and generates hard VST constraints
for SQL generation. Unlike prompt-mediated VSL (which dumps all metadata
as hints), the planner:

  1. Detects the semantic failure category from the question text
  2. Looks up only the VST constraints relevant to that category
  3. Injects grounded, actionable constraints (including actual statistical
     thresholds from conditional_value_distribution) into the generation prompt
  4. Produces a rejection prompt with specific violation feedback when the
     validator rejects the generated SQL
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from value_semantics.vst.model import ColumnVST, Violation
from value_semantics.vst.policy import PolicyDefinition, PolicyRegistry
from value_semantics.vst.registry import VSTRegistry


def _is_nan(v) -> bool:
    try:
        import math
        return math.isnan(float(v))
    except Exception:
        return False


class QueryIntent(str, Enum):
    COMPARATIVE = "comparative"           # "unusually high", "extreme", "outlier"
    PROCESS_TEMPORAL = "process_temporal" # "sustained", "worsening over time", "trend"
    POLICY_GROUNDED = "policy_grounded"   # "reportable", "dormant", "VIP", "at risk"
    QUANTITATIVE_DERIVED = "quantitative" # "efficiency", "ratio", "completion rate"
    ROLE_CONFUSION = "role_confusion"     # "top by account_id", "most important"
    GENERAL = "general"                   # no specific semantic failure detected


@dataclass
class PlanConstraint:
    constraint_type: str    # STATISTICAL_THRESHOLD | TEMPORAL_REQUIRED | IDENTIFIER_FORBIDDEN | DERIVED_METRIC
    column: str
    table: Optional[str]
    message: str            # Actionable constraint text for the prompt
    severity: str = "HARD"  # HARD (reject on violation) | SOFT (guidance)


@dataclass
class PlannerOutput:
    intent: QueryIntent
    constraints: list[PlanConstraint]
    constrained_prompt: str
    policy: Optional[PolicyDefinition] = None


# ---------------------------------------------------------------------------
# Intent classification patterns
# ---------------------------------------------------------------------------

_COMPARATIVE = [
    r'\bunusual(?:ly)?\b', r'\bextreme(?:ly)?\b', r'\boutlier\b', r'\babnormal\b',
    r'\banomal(?:y|ous|ies)\b', r'\bdespite\b', r'\blow.*but\b', r'\bhigh.*but\b',
    r'\bmuch larger\b', r'\bmuch higher\b', r'\bmuch lower\b', r'\bmuch smaller\b',
    r'\bhigh.*given\b', r'\blow.*given\b', r'\bcompared to typical\b',
    r'\bfar (?:above|below)\b', r'\boutside.*(?:normal|typical|expected)\b',
    r'\brisky despite\b', r'\bgood.*despite\b',
    r'\bsever(?:e|ely)\b',                              # "severe crashes", "severely high"
    r'\bcrash(?:es)?.*density\b', r'\bdensit(?:y|ies).*crash\b',  # crash density outliers
]

_PROCESS_TEMPORAL = [
    r'\bsustained\b', r'\bover time\b', r'\bincreasing(?:ly)?\b',
    r'\bdecreasing(?:ly)?\b', r'\bworsening\b', r'\bimproving\b',
    r'\baccelerating\b', r'\bslowing\b', r'\btrend\b', r'\bpattern\b',
    r'\brecurring\b', r'\bcycle\b', r'\bconsecutive\b', r'\birregular(?:ity)?\b',
    r'\bdropped sharply\b', r'\bvolatile\b', r'\boscillat\b',
    r'\bfrequency.*(?:over|time)\b', r'\brapidly\b', r'\bpace.*slow\b',
    r'\brepayment.*pace\b', r'\btransaction.*frequency\b', r'\bmonthly.*(?:drop|rise)\b',
    r'\bbalance.*(?:recovery|negative|distress)\b', r'\boverdraft.*cycle\b',
    r'\bage(?:ing|ed)\b', r'\bdelayed\b', r'\bdelay(?:ing)?\b',
    r'\bmonth-over-month\b', r'\byear-over-year\b',
    r'\bconsistently\b', r'\bpersist',                  # "consistently", "persistent", "persistently"
    r'\bacross years\b', r'\bacross months\b',          # "across years"
]

_POLICY = [
    r'\breportable\b', r'\b[Vv][Ii][Pp]\b', r'\bdormant\b', r'\bat risk\b',
    r'\bsuspicious.*(?:pattern|activit|transfer)\b', r'\bcompliant\b',
    r'\bhealthy.*profile\b', r'\bdefault.*risk\b', r'\bat.risk.of.default\b',
    r'\bhit.and.run\b',
    r'\bintoxicat',          # "intoxicated", "intoxication"
    r'\bimpair',             # "impaired", "impairment"
    r'\bviolat',             # "violating", "violation"
    r'\binvestigation\b', r'\bpreventable\b', r'\bdistracted driving\b',
    r'\bmoving violation\b', r'\breporting threshold\b', r'\bexceed\w*.*threshold\b',
    r'\bmajor incident', r'\bminor accident', r'\bthreshold\b',
]

_QUANTITATIVE = [
    r'\befficiency\b', r'\brepayment.*(?:ratio|rate|efficiency)\b',
    r'\bcompletion.*percent\b', r'\bpayback.*ratio\b', r'\bconcentrat\b',
    r'\bhighest.*(?:ratio|efficiency|rate)\b',
    r'\bhigh.*(?:pedestrian|cyclist|motorist).*rate',   # "high pedestrian injury rates"
    r'\binjury risk\b', r'\bfatality rate\b', r'\blethality\b',
    r'\brate per\b', r'\binjury.*ratio\b', r'\bper crash\b',
    r'\bremaining.*balance\b', r'\bunpaid.*balance\b', r'\boutstanding.*balance\b',
]

_ROLE = [
    r'\bmost important\b', r'\btop.*by.*(?:_id|id\b)\b', r'\bheavy user\b',
    r'\bmost profitable\b', r'\bmost active.*saving\b',
    r'\bhighest.*(?:financial dependency|depend)\b',
    r'\btop client.*by.*account\b',
    r'\bmost dangerous\b', r'\bworst\b', r'\bmost responsible\b',  # public-safety role confusion
]


class VSLPlanner:
    """
    Plans a VST-constrained SQL generation prompt.

    Key difference from prompt-mediated VSL:
    - Prompt-mediated: dumps all VST metadata as unstructured text hints
    - Planner: detects semantic failure category → injects only relevant,
      grounded constraints (including actual statistical thresholds from
      conditional_value_distribution)
    """

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def classify_intent(self, question: str) -> QueryIntent:
        q = question.lower()

        # PROCESS checked first: temporal patterns are specific and rarely appear in
        # comparative or policy questions, but comparative words like "severe" or
        # "extreme" can co-occur in process questions (e.g. "recurring severe crashes").
        for p in _PROCESS_TEMPORAL:
            if re.search(p, q):
                return QueryIntent.PROCESS_TEMPORAL
        for p in _COMPARATIVE:
            if re.search(p, q):
                return QueryIntent.COMPARATIVE
        for p in _POLICY:
            if re.search(p, q):
                return QueryIntent.POLICY_GROUNDED
        for p in _QUANTITATIVE:
            if re.search(p, q):
                return QueryIntent.QUANTITATIVE_DERIVED
        for p in _ROLE:
            if re.search(p, q):
                return QueryIntent.ROLE_CONFUSION

        return QueryIntent.GENERAL

    # ------------------------------------------------------------------
    # Constraint generation
    # ------------------------------------------------------------------

    def build_constraints(
        self,
        intent: QueryIntent,
        registry: VSTRegistry,
        question: str = "",
        policy_registry: Optional[PolicyRegistry] = None,
    ) -> list[PlanConstraint]:
        constraints: list[PlanConstraint] = []

        # Always enforce identifier rules
        for vst in registry.all_vsts():
            if vst.is_identifier:
                constraints.append(PlanConstraint(
                    constraint_type="IDENTIFIER_FORBIDDEN",
                    column=vst.column,
                    table=vst.table,
                    message=(
                        f"[{vst.table}.{vst.column}] IDENTIFIER — no magnitude ordering. "
                        f"Do not use SUM/AVG/MAX/MIN({vst.column}) or "
                        f"ORDER BY {vst.column} to rank entities. "
                        f"Use COUNT({vst.column}) or a measure column instead."
                    ),
                    severity="HARD",
                ))

        if intent == QueryIntent.COMPARATIVE:
            self._add_comparative_constraints(registry, constraints)

        elif intent == QueryIntent.PROCESS_TEMPORAL:
            self._add_process_constraints(registry, constraints)

        elif intent == QueryIntent.QUANTITATIVE_DERIVED:
            self._add_quantitative_constraints(registry, constraints)

        # Policy constraints always applied when a policy matches — not gated on intent
        self._add_policy_constraints(registry, constraints, question, policy_registry)

        return constraints

    def _add_comparative_constraints(
        self, registry: VSTRegistry, constraints: list[PlanConstraint]
    ) -> None:
        for vst in registry.all_vsts():
            if not (vst.supports_outlier_detection or vst.supports_distributional_reasoning):
                continue
            if not vst.statistical_profiles:
                continue
            thresholds = self._extract_thresholds(vst)
            if not thresholds:
                continue
            lines = [
                f"[{vst.table}.{vst.column}] For 'unusually high/low' comparisons: "
                f"do NOT use an arbitrary literal threshold.",
                f"REQUIRED: compute the threshold dynamically inside the SQL using one of:",
                f"  (a) Correlated subquery: WHERE {vst.column} > (SELECT AVG({vst.column}) + 2*STDDEV({vst.column}) FROM {vst.table})",
                f"  (b) Window percentile: PERCENT_RANK() OVER (...) >= 0.90",
                f"  (c) Per-group average: WHERE {vst.column} > (SELECT AVG({vst.column}) FROM {vst.table} WHERE group_col = outer.group_col)",
                f"VSL statistical reference (for validation): "
                f"p90 ≈ {thresholds['p90']}, extreme start ≈ {thresholds['extreme_start']}",
            ]
            if thresholds.get("by_group") and thresholds["group_col"]:
                lines.append(
                    f"  If grouping by {thresholds['group_col']}, compute the threshold per group."
                )
            constraints.append(PlanConstraint(
                constraint_type="STATISTICAL_THRESHOLD",
                column=vst.column,
                table=vst.table,
                message="\n  ".join(lines),
                severity="HARD",
            ))

    def _add_process_constraints(
        self, registry: VSTRegistry, constraints: list[PlanConstraint]
    ) -> None:
        for vst in registry.all_vsts():
            if not (vst.requires_temporal_context or vst.supports_change_detection
                    or vst.supports_state_tracking):
                continue
            role_desc = vst.process_role or "process-derived state"

            if vst.process_role == "EVENT_TIME":
                # Temporal dimension column: valid to filter by date range, but
                # trend/worsening queries must aggregate by time bucket first.
                msg = (
                    f"[{vst.table}.{vst.column}] is an EVENT_TIME column. "
                    f"For trend/worsening queries you MUST bucket events by time period "
                    f"(e.g. DATE_TRUNC('month', {vst.column}) or EXTRACT(year FROM {vst.column})) "
                    f"and group by location (borough, zip_code, on_street_name). "
                    f"Then use LAG() or compare aggregate counts across periods. "
                    f"Example: WITH monthly AS (SELECT borough, DATE_TRUNC('month', {vst.column}) AS period, "
                    f"SUM(number_of_persons_injured) AS injuries FROM {vst.table} "
                    f"GROUP BY borough, period) SELECT ... LAG(injuries) OVER (PARTITION BY borough ORDER BY period)"
                )
            else:
                # State variable: row-local filter is semantically wrong; requires temporal CTE.
                msg = (
                    f"[{vst.table}.{vst.column}] is a {role_desc}. "
                    f"Temporal/change queries MUST aggregate events per entity over time. "
                    f"Do NOT filter WHERE {vst.column} < X or WHERE {vst.column} > X directly "
                    f"without first grouping by entity and time. "
                    f"Use a CTE or window function: "
                    f"WITH t AS (SELECT entity_id, event_date, {vst.column} FROM {vst.table} "
                    f"ORDER BY entity_id, event_date) SELECT ... FROM t WHERE ..."
                )

            constraints.append(PlanConstraint(
                constraint_type="TEMPORAL_REQUIRED",
                column=vst.column,
                table=vst.table,
                message=msg,
                severity="HARD",
            ))

    def _add_quantitative_constraints(
        self, registry: VSTRegistry, constraints: list[PlanConstraint]
    ) -> None:
        # Check whether the registry has any derived-metric annotations at all.
        # If not, no guidance is needed.
        has_derived = any(
            dm.get("formula_template")
            for vst in registry.all_vsts()
            for dm in vst.derived_metrics
        )
        if not has_derived:
            return

        # Inject a general normalization directive rather than specific formula
        # templates. Prescriptive templates anchor the model to a particular
        # formula path and can substitute a wrong denominator or join strategy
        # when the question requires a different computation.
        constraints.append(PlanConstraint(
            constraint_type="DERIVED_METRIC",
            column="*",
            table="*",
            message=(
                "This question involves a ratio, rate, efficiency, or normalized measure. "
                "Identify the correct numerator and denominator from the question and schema. "
                "Do NOT return raw counts or totals when a normalized measure is required. "
                "Ensure the denominator captures the right scope for the question "
                "(e.g., total persons involved rather than crash count; "
                "candidates per posting rather than candidates across all postings)."
            ),
            severity="SOFT",
        ))

    def _add_policy_constraints(
        self,
        registry: VSTRegistry,
        constraints: list[PlanConstraint],
        question: str = "",
        policy_registry: Optional[PolicyRegistry] = None,
    ) -> Optional[PolicyDefinition]:
        if policy_registry and question:
            policy = policy_registry.match(question)
            if policy:
                if policy.is_gap:
                    msg_lines = [
                        f"POLICY GAP — {policy.description}",
                        f"  {policy.gap_message}",
                    ]
                    if policy.gap_alternatives:
                        msg_lines.append(
                            "  Best available proxy (use and explicitly flag as approximate):"
                        )
                        for alt in policy.gap_alternatives:
                            msg_lines.append(f"    • {alt}")
                    constraints.append(PlanConstraint(
                        constraint_type="POLICY_GAP",
                        column="*",
                        table="*",
                        message="\n  ".join(msg_lines),
                        severity="SOFT",
                    ))
                else:
                    msg_lines = [
                        f"POLICY DEFINITION — {policy.description}",
                    ]
                    if policy.source:
                        msg_lines.append(f"  Source: {policy.source}")
                    if policy.sql_condition:
                        msg_lines.append(
                            f"  REQUIRED SQL condition: {policy.sql_condition}"
                        )
                    if policy.column_mappings:
                        for col, vals in policy.column_mappings.items():
                            if isinstance(vals, list):
                                msg_lines.append(
                                    f"  {col} must be one of: {vals}"
                                )
                            else:
                                msg_lines.append(f"  {col}: {vals}")
                    if policy.time_window_days:
                        msg_lines.append(
                            f"  Time window: {policy.time_window_days} days of inactivity"
                        )
                    constraints.append(PlanConstraint(
                        constraint_type="POLICY_GROUNDED",
                        column="*",
                        table="*",
                        message="\n  ".join(msg_lines),
                        severity="HARD",
                    ))
                return policy

        # Fallback: no policy registry or no matching policy — inject statistical profiles as proxy
        for vst in registry.all_vsts():
            if not vst.statistical_profiles:
                continue
            thresholds = self._extract_thresholds(vst)
            if not thresholds:
                continue
            constraints.append(PlanConstraint(
                constraint_type="POLICY_THRESHOLD",
                column=vst.column,
                table=vst.table,
                message=(
                    f"[{vst.table}.{vst.column}] No policy definition available. "
                    f"Statistical reference only: p90={thresholds['p90']}, "
                    f"extreme={thresholds['extreme_start']}. "
                    f"Use as a proxy and flag as approximate."
                ),
                severity="SOFT",
            ))
        return None

    def _extract_thresholds(self, vst: ColumnVST) -> Optional[dict]:
        """Extract the best statistical threshold summary from a column's profiles."""
        if not vst.statistical_profiles:
            return None

        for group_col, group_data in vst.statistical_profiles.items():
            profiles = group_data.get("profiles", {})
            if not profiles:
                continue

            all_p90 = [
                (gval, p.get("p90", 0), p.get("extreme_range", [0, 0]))
                for gval, p in profiles.items()
                if p.get("p90") and not _is_nan(p.get("p90", 0))
            ]
            if not all_p90:
                continue

            best_p90 = round(max(x[1] for x in all_p90))
            best_extreme_candidates = [
                x[2][0] for x in all_p90
                if len(x[2]) > 0 and not _is_nan(x[2][0])
            ]
            best_extreme = round(max(best_extreme_candidates)) if best_extreme_candidates else best_p90

            by_group = {
                gval: {
                    "p90": round(p90),
                    "extreme_start": round(extreme[0]) if extreme and not _is_nan(extreme[0]) else round(p90),
                }
                for gval, p90, extreme in all_p90
            }

            return {
                "p90": best_p90,
                "extreme_start": best_extreme,
                "group_col": group_col,
                "by_group": by_group,
            }

        return None

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def build_constrained_prompt(
        self,
        question: str,
        schema_text: str,
        constraints: list[PlanConstraint],
        intent: QueryIntent,
    ) -> str:
        hard = [c for c in constraints if c.severity == "HARD"]
        soft = [c for c in constraints if c.severity == "SOFT"]

        lines = [
            "You are an expert SQL assistant. Generate a single SQL query for the question below.",
            "",
            f"Database schema:",
            "```sql",
            schema_text,
            "```",
            "",
        ]

        if hard:
            lines.append(
                "VALUE SEMANTIC CONSTRAINTS (enforced — the validator will REJECT SQL that "
                "violates these and you will be asked to fix it):"
            )
            for i, c in enumerate(hard, 1):
                lines.append(f"  {i}. {c.message}")
            lines.append("")

        if soft:
            lines.append("SEMANTIC GUIDANCE (follow when applicable to this question):")
            for i, c in enumerate(soft, 1):
                lines.append(f"  {i}. {c.message}")
            lines.append("")

        lines += [
            f"Question: {question}",
            "",
            "Return only a ```sql code block. No explanation.",
        ]

        return "\n".join(lines)

    def build_rejection_prompt(
        self,
        original_question: str,
        schema_text: str,
        rejected_sql: str,
        violations: list[Violation],
        constraints: list[PlanConstraint],
        intent: QueryIntent,
        policy_violations: Optional[list[str]] = None,
    ) -> str:
        lines = [
            "The SQL you generated was REJECTED.",
            "",
            "REJECTED SQL:",
            "```sql",
            rejected_sql,
            "```",
            "",
        ]

        if policy_violations:
            lines += [
                "POLICY CONSTRAINT VIOLATIONS (fix these first):",
                "\n".join(f"  ✗ {v}" for v in policy_violations),
                "",
            ]

        if violations:
            violation_text = "\n".join(
                f"  [{v.violation_type.value}] {v.message}"
                + (f"\n  → Fix: {v.rewrite_hint}" if v.rewrite_hint else "")
                for v in violations
            )
            lines += [
                "VALUE SEMANTICS VIOLATIONS:",
                violation_text,
                "",
            ]

        lines += [
            "Fix ALL violations above and generate corrected SQL.",
            "",
            "Schema:",
            "```sql",
            schema_text,
            "```",
            "",
            f"Question: {original_question}",
            "",
            "Return only corrected ```sql. No explanation.",
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def plan(
        self,
        question: str,
        schema_text: str,
        registry: VSTRegistry,
        policy_registry: Optional[PolicyRegistry] = None,
    ) -> PlannerOutput:
        intent = self.classify_intent(question)
        matched_policy = (
            policy_registry.match(question) if policy_registry and question else None
        )
        constraints = self.build_constraints(
            intent, registry, question=question, policy_registry=policy_registry
        )
        prompt = self.build_constrained_prompt(question, schema_text, constraints, intent)

        return PlannerOutput(
            intent=intent,
            constraints=constraints,
            constrained_prompt=prompt,
            policy=matched_policy,
        )
