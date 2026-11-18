from value_semantics.planning.llm_intent_frame import LLMIntentFrameExtractor
from value_semantics.planning.schema_linker import VSLSchemaLinker

class SemanticGroundingPlanner:

    def plan(self, intent, table_name, semantics, table_semantics):
        intent_lower = intent.lower()

        intent_frame = LLMIntentFrameExtractor().extract(
            intent=intent,
            schema_summary={
                "table": table_name,
                "columns": list(semantics.keys()),
            },
        )

        linked_schema = VSLSchemaLinker().link(
            intent_frame=intent_frame,
            table_name=table_name,
            semantics=semantics,
            table_semantics=table_semantics,
        )

        grounding = []
        operators = []
        sql = None
        semantic_plan = []

        # -------------------------------------------------
        # 1. ORDINAL / INTERPRETIVE GROUNDING
        # -------------------------------------------------
        ordinal_grounding = self._ground_ordinal_intent(
            intent_lower=intent_lower,
            table_name=table_name,
            semantics=semantics,
        )

        #ordinal_grounding = self._ground_ordinal_intent(
        #    intent_lower=intent_lower,
        #    table_name=table_name,
        #    semantics=semantics,
        #    linked_schema=linked_schema,
        #    intent_frame=intent_frame,
        #)

        if ordinal_grounding:
            grounding.extend(ordinal_grounding)

        # -------------------------------------------------
        # 2. COMPARATIVE / DISTRIBUTIONAL GROUNDING
        # -------------------------------------------------
        comparative_grounding = self._ground_comparative_intent(
            intent_lower=intent_lower,
            table_name=table_name,
            semantics=semantics,
        )

        #comparative_grounding = self._ground_comparative_intent(
        #    intent_lower=intent_lower,
        #    table_name=table_name,
        #    semantics=semantics,
        #    linked_schema=linked_schema,
        #    intent_frame=intent_frame,
        #)

        if comparative_grounding:
            grounding.extend(comparative_grounding)

        # -------------------------------------------------
        # 3. PROCESS TREND GROUNDING
        # -------------------------------------------------
        process_grounding = self._ground_process_trends(
            intent_lower=intent_lower,
            table_semantics=table_semantics,
        )

        if process_grounding:
            grounding.extend(process_grounding)

        # -------------------------------------------------
        # 4. PROCESS OPERATORS
        # -------------------------------------------------
        operators.extend(
            self._match_process_operators(
                intent_lower=intent_lower,
                table_semantics=table_semantics,
            )
        )

        # -------------------------------------------------
        # 5. SEMANTIC PLAN + SQL GENERATION
        # -------------------------------------------------
        if ordinal_grounding:
            semantic_plan = self._build_ordinal_plan(
                table_name=table_name,
                grounding=ordinal_grounding[0],
            )

            sql = self._generate_ordinal_sql(
                table_name=table_name,
                grounding=ordinal_grounding[0],
            )

        elif comparative_grounding:
            semantic_plan = self._build_comparative_plan(
                table_name=table_name,
                grounding=comparative_grounding[0],
            )

            sql = self._generate_comparative_sql(
                table_name=table_name,
                grounding=comparative_grounding[0],
            )

        elif process_grounding:
            semantic_plan = self._build_process_trend_plan(
                table_name=table_name,
                table_semantics=table_semantics,
                grounding=process_grounding[0],
            )

            sql = self._generate_process_trend_sql(
                table_name=table_name,
                table_semantics=table_semantics,
                grounding=process_grounding[0],
            )

        #return {
        #    "intent": intent,
        #    "grounding": grounding,
        #    "operators": operators,
        #    "semantic_plan": semantic_plan,
        #    "sql": sql,
        #}

        #return {
        #    "intent": intent,
        #    "intent_frame": intent_frame,
        #    "grounding": grounding,
        #    "operators": operators,
        #    "semantic_plan": semantic_plan,
        #    "sql": sql,
        #}

        return {
            "intent": intent,
            "intent_frame": intent_frame,
            "linked_schema": linked_schema,
            "grounding": grounding,
            "operators": operators,
            "semantic_plan": semantic_plan,
            "sql": sql,
        }

    # -------------------------------------------------
    # SEMANTIC PLAN BUILDERS
    # -------------------------------------------------
    def _build_ordinal_plan(self, table_name, grounding):
        return [
            {
                "step": 1,
                "operator": "GROUND_ORDINAL_VALUE_AXIS",
                "table": table_name,
                "column": grounding["column"],
                "direction": grounding["direction"],
                "selected_values": grounding["values"],
                "source": grounding["source"],
                "rationale": grounding["rationale"],
            },
            {
                "step": 2,
                "operator": "FILTER_BY_ORDINAL_REGION",
                "table": table_name,
                "predicate": {
                    "column": grounding["column"],
                    "op": "IN",
                    "values": grounding["values"],
                },
            },
            {
                "step": 3,
                "operator": "PROJECT_ROWS",
                "table": table_name,
                "output_shape": "rows",
            },
        ]

    def _build_comparative_plan(self, table_name, grounding):
        if grounding["type"] == "conditional_comparative_grounding":
            return [
                {
                    "step": 1,
                    "operator": "GROUND_CONDITIONAL_DISTRIBUTION",
                    "table": table_name,
                    "value_column": grounding["column"],
                    "group_attribute": grounding["group_attribute"],
                    "direction": grounding["direction"],
                    "threshold_stat": grounding.get("recommended_stat", "p99"),
                    "source": grounding["source"],
                    "rationale": grounding["rationale"],
                },
                {
                    "step": 2,
                    "operator": "COMPUTE_GROUP_THRESHOLDS",
                    "table": table_name,
                    "group_by": [grounding["group_attribute"]],
                    "value_column": grounding["column"],
                    "threshold_stat": grounding.get("recommended_stat", "p99"),
                },
                {
                    "step": 3,
                    "operator": "FILTER_BY_GROUP_THRESHOLD",
                    "table": table_name,
                    "predicate": {
                        "column": grounding["column"],
                        "direction": grounding["direction"],
                        "threshold_source": "group_thresholds",
                    },
                },
                {
                    "step": 4,
                    "operator": "PROJECT_ROWS",
                    "table": table_name,
                    "output_shape": "rows",
                },
            ]

        return [
            {
                "step": 1,
                "operator": "GROUND_VALUE_AXIS",
                "table": table_name,
                "column": grounding["column"],
                "direction": grounding["direction"],
                "threshold": grounding["threshold"],
                "source": grounding["source"],
                "rationale": grounding["rationale"],
            },
            {
                "step": 2,
                "operator": "FILTER_BY_DISTRIBUTIONAL_THRESHOLD",
                "table": table_name,
                "predicate": grounding["predicate"],
            },
            {
                "step": 3,
                "operator": "PROJECT_ROWS",
                "table": table_name,
                "output_shape": "rows",
            },
        ]

    def _build_process_trend_plan(self, table_name, table_semantics, grounding):
        process = table_semantics.get("process_semantics", {})
        event_time = process.get("event_time")

        process_key = grounding["process_key"]
        measure = grounding["measure"]
        matched_trend = grounding["matched_trend"]

        direction = "< 0" if matched_trend == "decreasing" else "> 0"

        return [
            {
                "step": 1,
                "operator": "GROUND_PROCESS_STRUCTURE",
                "table": table_name,
                "process_key": process_key,
                "event_time": event_time,
                "measure": measure,
                "source": "process_semantics",
            },
            {
                "step": 2,
                "operator": "AGGREGATE_OVER_TIME",
                "table": table_name,
                "group_by": [process_key, "month"],
                "time_bucket": {
                    "column": event_time,
                    "grain": "month",
                },
                "measure": {
                    "column": measure,
                    "aggregation": "AVG",
                },
            },
            {
                "step": 3,
                "operator": "AGGREGATE_THEN_TREND",
                "table": table_name,
                "partition_by": [process_key],
                "order_by": ["month"],
                "trend_metric": "REGR_SLOPE",
                "measure": f"avg_{measure}",
            },
            {
                "step": 4,
                "operator": "FILTER_TREND",
                "predicate": {
                    "metric": f"{measure}_trend_slope",
                    "op": direction.split()[0],
                    "value": 0,
                    "meaning": matched_trend,
                },
            },
            {
                "step": 5,
                "operator": "PROJECT_ENTITIES",
                "entity": process_key,
                "output_columns": [
                    process_key,
                    f"{measure}_trend_slope",
                ],
            },
        ]

    # -------------------------------------------------
    # ORDINAL / INTERPRETIVE
    # -------------------------------------------------
    def _ground_ordinal_intent(self, intent_lower, table_name, semantics):
        high_terms = {
            "premium",
            "top",
            "high",
            "higher",
            "highest",
            "best",
            "gold",
        }

        low_terms = {
            "low",
            "lower",
            "lowest",
            "basic",
            "junior",
            "poor",
        }

        if not any(t in intent_lower for t in high_terms | low_terms):
            return []

        direction = "high" if any(t in intent_lower for t in high_terms) else "low"

        hints = []

        for col, sem in semantics.items():
            axis = sem.get("value_axis", {})

            if axis.get("axis_type") != "ORDINAL":
                continue

            regions = axis.get("extreme_regions", {})
            values = regions.get(direction, [])

            if not values:
                continue

            axis_meaning = (
                axis.get("polarity", {})
                .get("meaning", "")
                .lower()
            )

            col_match = col.lower() in intent_lower
            meaning_match = axis_meaning and axis_meaning in intent_lower

            generic_match = (
                direction == "high"
                and any(t in intent_lower for t in {"premium", "top", "best", "gold"})
            )

            if not (col_match or meaning_match or generic_match):
                continue

            hints.append(
                {
                    "type": "ordinal_value_axis_grounding",
                    "table": table_name,
                    "column": col,
                    "direction": direction,
                    "values": values,
                    "source": "value_axis",
                    "confidence": axis.get("confidence", 0.7),
                    "rationale": (
                        f"Ordinal intent grounded using ordered value axis for {col}."
                    ),
                }
            )

        return sorted(
            hints,
            key=lambda h: h.get("confidence", 0),
            reverse=True,
        )

    def _generate_ordinal_sql(self, table_name, grounding):
        column = grounding["column"]
        values = grounding["values"]

        quoted = ", ".join(f"'{v}'" for v in values)

        return f"""
-- VSL grounding:
-- source = ordinal value_axis
-- column = {column}
-- selected_values = {values}

SELECT
    *
FROM {table_name}
WHERE {column} IN ({quoted});
""".strip()

    # -------------------------------------------------
    # COMPARATIVE / DISTRIBUTIONAL
    # -------------------------------------------------
    def _ground_comparative_intent(self, intent_lower, table_name, semantics):
        high_terms = [
            "large",
            "high",
            "highest",
            "unusually high",
            "unusually large",
            "abnormally high",
            "abnormally large",
            "top",
        ]

        low_terms = [
            "small",
            "low",
            "lowest",
            "unusually low",
            "unusually small",
            "abnormally low",
            "abnormally small",
            "bottom",
        ]

        if not any(t in intent_lower for t in high_terms + low_terms):
            return []

        direction = "high" if any(t in intent_lower for t in high_terms) else "low"

        hints = []

        for col, sem in semantics.items():
            value_axis = sem.get("value_axis", {})
            role = sem.get("semantic_role", {})
            qvst = sem.get("quantitative_vst", {})
            cds = sem.get("conditional_value_distribution", {})

            if value_axis.get("axis_type") == "ORDINAL":
                continue

            if role.get("primary_role") != "EVIDENCE":
                continue

            if not value_axis:
                continue

            match_score = self._score_column_match(intent_lower, col)

            if match_score == 0 and not self._generic_measure_match(
                intent_lower,
                col,
                qvst,
            ):
                continue

            conditional_hint = self._conditional_distribution_hint(
                intent_lower=intent_lower,
                column=col,
                direction=direction,
                cds=cds,
                match_score=match_score,
            )

            if conditional_hint:
                hints.append(conditional_hint)
                continue

            extreme_regions = value_axis.get("extreme_regions", {})
            threshold = (
                extreme_regions.get("large")
                if direction == "high"
                else extreme_regions.get("small")
            )

            if not threshold:
                continue

            hints.append(
                {
                    "type": "comparative_distributional_grounding",
                    "table": table_name,
                    "column": col,
                    "direction": direction,
                    "threshold_strategy": "global_value_axis_extreme_region",
                    "threshold": threshold,
                    "predicate": f"{col} {threshold}",
                    "source": "value_axis",
                    "qvst_role": qvst.get("role"),
                    "confidence": value_axis.get("confidence", 0.7),
                    "match_score": match_score,
                    "rationale": (
                        f"Comparative intent grounded using global distributional "
                        f"extreme region for {col}."
                    ),
                }
            )

        return sorted(
            hints,
            key=lambda h: (
                h.get("match_score", 0),
                h.get("confidence", 0),
            ),
            reverse=True,
        )

    def _conditional_distribution_hint(
        self,
        intent_lower,
        column,
        direction,
        cds,
        match_score,
    ):
        if not cds:
            return None

        conditional_terms = [
            "given",
            "within",
            "by",
            "per",
            "for each",
            "conditioned",
            "relative to",
        ]

        mentioned_group = None

        for group_attr in cds.keys():
            if group_attr.lower() in intent_lower:
                mentioned_group = group_attr
                break

        if not mentioned_group and not any(t in intent_lower for t in conditional_terms):
            return None

        group_attr = mentioned_group or next(iter(cds.keys()))
        dist = cds[group_attr]

        return {
            "type": "conditional_comparative_grounding",
            "column": column,
            "group_attribute": group_attr,
            "direction": direction,
            "threshold_strategy": "conditional_distribution",
            "recommended_stat": dist.get("recommended_stat", "p99"),
            "profiles": dist.get("profiles", {}),
            "source": "conditional_value_distribution",
            "confidence": dist.get("confidence", 0.7),
            "match_score": match_score + 0.3,
            "rationale": (
                f"Comparative intent grounded using conditional distribution "
                f"of {column} within {group_attr} groups."
            ),
        }

    def _score_column_match(self, intent_lower, column):
        col = column.lower()

        if col in intent_lower:
            return 1.0

        synonyms = {
            "amount": [
                "amount",
                "loan",
                "withdrawal",
                "deposit",
                "payment",
                "transaction",
                "principal",
            ],
            "balance": ["balance", "account balance"],
            "duration": ["duration", "term", "period"],
            "payments": ["payment", "payments", "installment", "repayment"],
        }

        for canonical, terms in synonyms.items():
            if col == canonical and any(t in intent_lower for t in terms):
                return 0.8

        return 0.0

    def _generic_measure_match(self, intent_lower, column, qvst):
        if qvst.get("role") not in {"MEASUREMENT", "MAGNITUDE", "COUNT"}:
            return False

        generic_terms = [
            "large",
            "high",
            "small",
            "low",
            "unusually",
            "abnormally",
            "top",
            "bottom",
        ]

        return any(t in intent_lower for t in generic_terms)

    def _generate_comparative_sql(self, table_name, grounding):
        if grounding["type"] == "conditional_comparative_grounding":
            column = grounding["column"]
            group_attr = grounding["group_attribute"]
            direction = grounding["direction"]
            stat = grounding.get("recommended_stat", "p99")

            operator = ">" if direction == "high" else "<"
            percentile = self._stat_to_percentile(stat)

            return f"""
-- VSL grounding:
-- source = conditional_value_distribution
-- group_attribute = {group_attr}
-- value_column = {column}
-- threshold_stat = {stat}

WITH group_thresholds AS (
    SELECT
        {group_attr},
        PERCENTILE_CONT({percentile}) WITHIN GROUP (ORDER BY {column}) AS threshold
    FROM {table_name}
    GROUP BY {group_attr}
)
SELECT
    t.*
FROM {table_name} t
JOIN group_thresholds g
    ON t.{group_attr} = g.{group_attr}
WHERE t.{column} {operator} g.threshold;
""".strip()

        column = grounding["column"]
        threshold = grounding["threshold"]

        return f"""
-- VSL grounding:
-- source = value_axis
-- threshold_strategy = global extreme region

SELECT
    *
FROM {table_name}
WHERE {column} {threshold};
""".strip()

    def _stat_to_percentile(self, stat):
        if stat == "p90":
            return 0.90

        if stat == "p95":
            return 0.95

        if stat == "p99":
            return 0.99

        return 0.99

    # -------------------------------------------------
    # PROCESS TRENDS
    # -------------------------------------------------
    def _ground_process_trends(self, intent_lower, table_semantics):
        grounding = []

        process_trends = table_semantics.get("process_trends", {})
        trends = process_trends.get("trends", {})

        for process_key, measure_trends in trends.items():
            for measure, trend_info in measure_trends.items():
                trend = trend_info.get("trend")
                stability = trend_info.get("stability")

                if (
                    measure.lower() in intent_lower
                    or str(trend).lower() in intent_lower
                    or str(stability).lower() in intent_lower
                ):
                    grounding.append(
                        {
                            "type": "process_trend_grounding",
                            "process_key": process_key,
                            "measure": measure,
                            "matched_trend": trend,
                            "stability": stability,
                            "source": "process_trends",
                            "confidence": trend_info.get("confidence"),
                            "rationale": trend_info.get("rationale"),
                        }
                    )

        return grounding

    def _match_process_operators(self, intent_lower, table_semantics):
        process_ops = table_semantics.get("process_operator_semantics", {})
        operators = process_ops.get("process_operators", [])

        matched_ops = []

        for op in operators:
            terms = op.get("intent_terms", [])
            operator_name = op.get("operator", "")

            if any(term in intent_lower for term in terms):
                matched_ops.append(op)

            if any(
                term in intent_lower
                for term in ["trend", "increasing", "decreasing", "volatile"]
            ):
                if operator_name == "AGGREGATE_THEN_TREND":
                    matched_ops.append(op)

        deduped = []
        seen = set()

        for op in matched_ops:
            key = str(op)

            if key not in seen:
                deduped.append(op)
                seen.add(key)

        return deduped

    def _generate_process_trend_sql(
        self,
        table_name,
        table_semantics,
        grounding,
    ):
        process = table_semantics.get("process_semantics", {})
        event_time = process.get("event_time")

        if not event_time:
            return None

        process_key = grounding["process_key"]
        measure = grounding["measure"]
        matched_trend = grounding["matched_trend"]

        direction = "< 0" if matched_trend == "decreasing" else "> 0"

        return f"""
-- VSL grounding:
-- source = process_trends
-- process_key = {process_key}
-- measure = {measure}
-- process_operator = AGGREGATE_THEN_TREND

WITH monthly_measure AS (
    SELECT
        {process_key},
        DATE_TRUNC('month', "{event_time}") AS month,
        AVG({measure}) AS avg_{measure}
    FROM {table_name}
    GROUP BY {process_key}, DATE_TRUNC('month', "{event_time}")
),
trend_features AS (
    SELECT
        {process_key},
        REGR_SLOPE(
            avg_{measure},
            EXTRACT(EPOCH FROM month)
        ) AS {measure}_trend_slope
    FROM monthly_measure
    GROUP BY {process_key}
)
SELECT
    {process_key},
    {measure}_trend_slope
FROM trend_features
WHERE {measure}_trend_slope {direction}
ORDER BY {measure}_trend_slope ASC;
""".strip()