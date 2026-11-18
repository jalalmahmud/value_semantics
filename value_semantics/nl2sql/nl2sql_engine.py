from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from value_semantics.nl2sql.prompt_builder import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from value_semantics.nl2sql.providers import BaseLLMProvider, get_provider
from value_semantics.nl2sql.sql_extractor import extract_sql

if TYPE_CHECKING:
    from value_semantics.vst.registry import VSTRegistry
    from value_semantics.vst.model import ValidationResult
    from value_semantics.vst.rewriter import RewriteResult
    from value_semantics.vst.planner import PlannerOutput
    from value_semantics.vst.policy import PolicyRegistry
    from value_semantics.vst.workflow import WorkflowResult


@dataclass
class NL2SQLResult:
    question: str
    sql: str
    provider: str
    model: str
    raw_response: str
    # VSL audit fields — populated only when generate_with_vsl() / generate_with_planner() is used
    vsl_validation: Optional["ValidationResult"] = field(default=None, repr=False)
    vsl_rewrite: Optional["RewriteResult"] = field(default=None, repr=False)
    vsl_plan: Optional["PlannerOutput"] = field(default=None, repr=False)
    vsl_retries: int = 0

    @property
    def vsl_violations(self) -> list:
        if self.vsl_validation:
            return self.vsl_validation.violations
        return []

    @property
    def vsl_rewrites_applied(self) -> list[str]:
        if self.vsl_rewrite:
            return self.vsl_rewrite.rewrites_applied
        return []


class NL2SQLEngine:
    """
    Convert natural language questions to SQL using a pluggable LLM provider.

    Usage:
        engine = NL2SQLEngine(provider="claude")
        result = engine.generate(question="Find large loans", schema={...})
        print(result.sql)

    Supported providers: "openai", "gemini", "claude"
    """

    def __init__(
        self,
        provider: str | BaseLLMProvider = "openai",
        model: str | None = None,
        api_key: str | None = None,
    ):
        if isinstance(provider, BaseLLMProvider):
            self._provider = provider
            self._provider_name = type(provider).__name__
            self._model_name = model or getattr(provider, "model", "unknown")
        else:
            self._provider = get_provider(provider, model=model, api_key=api_key)
            self._provider_name = provider
            self._model_name = model or getattr(self._provider, "model", "unknown")

    def generate(self, question: str, schema: dict) -> NL2SQLResult:
        """
        Generate SQL for the given natural language question.

        Args:
            question: Natural language question, e.g. "Find all loans over $10k"
            schema: Database schema dict. See prompt_builder.build_schema_text for format.

        Returns:
            NL2SQLResult with .sql, .provider, .model, and .raw_response fields.
        """
        user_prompt = build_user_prompt(question=question, schema=schema)
        raw = self._provider.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        sql = extract_sql(raw)

        return NL2SQLResult(
            question=question,
            sql=sql,
            provider=self._provider_name,
            model=self._model_name,
            raw_response=raw,
        )

    def generate_with_vsl(
        self,
        question: str,
        schema: dict,
        vst_registry: "VSTRegistry",
        default_table: Optional[str] = None,
    ) -> NL2SQLResult:
        """
        Generate SQL, then validate and rewrite it using the VST registry.

        Unlike generate(), VST constraints are enforced programmatically
        after generation — no semantic metadata is injected into the LLM prompt.
        The LLM receives only the schema (DDL); VSL acts as post-generation
        infrastructure.

        Args:
            question:      Natural language question.
            schema:        Schema dict (same format as generate()).
            vst_registry:  VSTRegistry built from VSL JSON output.
            default_table: Optional single-table name for column resolution.

        Returns:
            NL2SQLResult with .sql set to the validated/rewritten SQL, plus
            .vsl_validation and .vsl_rewrite audit fields.
        """
        from value_semantics.vst.validator import VSTValidator
        from value_semantics.vst.rewriter import SQLRewriter

        # Step 1: Generate SQL using schema-only prompt (no VST injection)
        base_result = self.generate(question=question, schema=schema)
        if not base_result.sql:
            return base_result

        # Step 2: Validate generated SQL against VST registry
        validator = VSTValidator()
        validation = validator.validate(
            sql=base_result.sql,
            registry=vst_registry,
            default_table=default_table,
        )

        # Step 3: Rewrite violations that can be corrected programmatically
        rewriter = SQLRewriter()
        rewrite = rewriter.rewrite(validation=validation, registry=vst_registry)

        final_sql = rewrite.rewritten_sql if rewrite.was_rewritten else base_result.sql

        return NL2SQLResult(
            question=question,
            sql=final_sql,
            provider=self._provider_name,
            model=self._model_name,
            raw_response=base_result.raw_response,
            vsl_validation=validation,
            vsl_rewrite=rewrite,
        )

    @staticmethod
    def _check_policy_violations(sql: str, policy: Optional[object]) -> list[str]:
        """
        Check whether generated SQL honours the policy's threshold and categorical conditions.

        VSTValidator is policy-blind — it only checks column type/aggregation correctness.
        This method catches cases where the model uses a plausible-but-wrong numeric threshold
        (e.g. 10000 instead of the required 5000) or omits a required IN-list value.
        """
        if policy is None:
            return []

        import re

        violations: list[str] = []
        sql_upper = sql.upper()

        # --- numeric threshold check ---
        threshold = getattr(policy, "threshold", None)
        if threshold is not None:
            # Find all numeric literals that appear after comparison operators in the SQL.
            # We look for every number in the SQL; if the required threshold isn't among
            # them, that's a violation (the model used a different value).
            numbers_in_sql = {float(n) for n in re.findall(r"\b(\d+(?:\.\d+)?)\b", sql)}
            if threshold not in numbers_in_sql:
                # Also check sql_condition for the column involved so the message is helpful.
                col_hint = ""
                sql_cond = getattr(policy, "sql_condition", None) or ""
                col_match = re.search(r"(\w+)\s*[><=!]+\s*" + str(int(threshold)), sql_cond)
                if col_match:
                    col_hint = f" on column `{col_match.group(1)}`"
                violations.append(
                    f"Wrong threshold{col_hint}: the required value is {threshold:g} "
                    f"but none of the numeric literals in the generated SQL match it. "
                    f"Required SQL condition: `{sql_cond}`"
                )

        # --- categorical / IN-list check ---
        column_mappings = getattr(policy, "column_mappings", {}) or {}
        for col, spec in column_mappings.items():
            if not isinstance(spec, list):
                continue  # skip ">= N" string specs — covered by threshold check above
            col_upper = col.upper()
            # Check each required value appears somewhere in the SQL (case-insensitive).
            for val in spec:
                val_str = str(val).upper()
                if val_str not in sql_upper:
                    violations.append(
                        f"Missing categorical condition: column `{col}` must include value "
                        f"`{val}` (from policy `{getattr(policy, 'concept', 'unknown')}`). "
                        f"Required condition: {col} IN ({', '.join(str(v) for v in spec)})"
                    )

        return violations

    def generate_with_planner(
        self,
        question: str,
        schema: dict,
        vst_registry: "VSTRegistry",
        default_table: Optional[str] = None,
        max_retries: int = 2,
        policy_registry: Optional["PolicyRegistry"] = None,
    ) -> NL2SQLResult:
        """
        Planner-enforced VSL generation.

        1. Classify query intent from the question text
        2. Build hard VST constraints relevant to that intent (including
           statistical thresholds from conditional_value_distribution)
        3. Generate SQL under those constraints
        4. Validate; if violations → build rejection prompt → retry (up to max_retries)

        Unlike generate_with_vsl(), constraints are selective and grounded —
        the LLM receives only what matters for this specific semantic failure type.
        """
        from value_semantics.vst.planner import VSLPlanner
        from value_semantics.vst.validator import VSTValidator
        from value_semantics.nl2sql.prompt_builder import build_schema_text

        planner = VSLPlanner()
        validator = VSTValidator()
        schema_text = build_schema_text(schema)

        plan = planner.plan(
            question=question,
            schema_text=schema_text,
            registry=vst_registry,
            policy_registry=policy_registry,
        )

        # Initial constrained generation
        raw = self._provider.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=plan.constrained_prompt,
        )
        sql = extract_sql(raw)
        retries = 0

        # Rejection loop
        for _ in range(max_retries):
            validation = validator.validate(sql, vst_registry, default_table=default_table)
            policy_violations = self._check_policy_violations(sql, plan.policy)
            if validation.is_valid and not policy_violations:
                break
            retries += 1
            rejection_prompt = planner.build_rejection_prompt(
                original_question=question,
                schema_text=schema_text,
                rejected_sql=sql,
                violations=validation.critical_violations,
                constraints=plan.constraints,
                intent=plan.intent,
                policy_violations=policy_violations,
            )
            raw = self._provider.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=rejection_prompt,
            )
            sql = extract_sql(raw)

        final_validation = validator.validate(sql, vst_registry, default_table=default_table)

        return NL2SQLResult(
            question=question,
            sql=sql,
            provider=self._provider_name,
            model=self._model_name,
            raw_response=raw,
            vsl_validation=final_validation,
            vsl_plan=plan,
            vsl_retries=retries,
        )

    def generate_workflow(
        self,
        question: str,
        schema: dict,
        vst_registry: "VSTRegistry",
        policy_registry: Optional["PolicyRegistry"] = None,
        max_step_retries: int = 2,
    ) -> "WorkflowResult":
        """
        Multi-step VSL workflow generation.

        1. Decomposes NL intent into 2-3 steps (LLM)
        2. Generates VST-constrained SQL for each step (VSLPlanner + LLM)
        3. Propagates VSTs for derived columns across steps
        4. Composes all steps into a final CTE SQL

        Returns WorkflowResult with per-step audit trail and composed SQL.
        """
        from value_semantics.vst.workflow import WorkflowPlanner, WorkflowPlan, WorkflowResult
        from value_semantics.nl2sql.prompt_builder import build_schema_text

        schema_text = build_schema_text(schema)
        planner = WorkflowPlanner()

        steps = planner.decompose(question, schema_text, self._provider)

        for i, step in enumerate(steps):
            planner.plan_step(
                step=step,
                question=question,
                schema_text=schema_text,
                registry=vst_registry,
                previous_steps=steps[:i],
                provider=self._provider,
                policy_registry=policy_registry,
                max_retries=max_step_retries,
            )

        final_sql = planner.compose(steps)

        workflow_plan = WorkflowPlan(
            question=question,
            steps=steps,
            final_sql=final_sql,
        )

        return WorkflowResult(
            question=question,
            sql=final_sql,
            provider=self._provider_name,
            model=self._model_name,
            workflow_plan=workflow_plan,
        )
