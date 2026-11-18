class QueryConstraintInferencer:
    def infer(self, semantics):
        constraints = {}

        value_semantics = semantics.get("value_semantics", {})
        semantic_role = semantics.get("semantic_role", {})
        quantitative_vst = semantics.get("quantitative_vst", {})
        process_role = semantics.get("process_vst_role", {})
        value_axis = semantics.get("value_axis", {})
        interpretive = semantics.get("interpretive_semantics", {})

        semantic_type = value_semantics.get("semantic_type")
        role = semantic_role.get("primary_role")
        process_vst_role = process_role.get("role")
        axis_type = value_axis.get("axis_type")

        # -------------------------------------------------
        # IDENTIFIER
        # -------------------------------------------------
        if value_semantics.get("is_identifier") or role == "IDENTIFIER":
            constraints.update({
                "should_not_sum": True,
                "should_not_average": True,
                "should_not_compare_magnitude": True,
                "allowed_operations": [
                    "SELECT",
                    "JOIN",
                    "GROUP_BY",
                    "COUNT_DISTINCT",
                    "EQUALITY_FILTER",
                ],
                "disallowed_operations": [
                    "SUM",
                    "AVG",
                    "MIN",
                    "MAX",
                    "GREATER_THAN",
                    "LESS_THAN",
                ],
                "reason": "Identifiers support equality/join semantics only.",
            })

        # -------------------------------------------------
        # NUMERIC / QUANTITATIVE
        # -------------------------------------------------
        elif semantic_type in {
            "INTEGER",
            "FLOAT",
            "NUMERIC_GENERAL",
            "CURRENCY_AMOUNT",
            "PERCENTAGE",
            "RATIO",
            "DURATION",
        }:
            constraints.update({
                "supports_aggregation": True,
                "allowed_aggregations": [
                    "SUM",
                    "AVG",
                    "MIN",
                    "MAX",
                ],
                "supports_range_filtering": True,
                "supports_distributional_reasoning": True,
                "supports_outlier_detection": True,
            })

        # -------------------------------------------------
        # ORDINAL AXES
        # -------------------------------------------------
        if axis_type == "ORDINAL":
            constraints.update({
                "supports_ordering": True,
                "supports_ranking": True,
                "supports_threshold_reasoning": True,
                "should_not_sum": True,
                "reason": "Ordinal semantics support ranking but not arithmetic aggregation.",
            })

        # -------------------------------------------------
        # ENUMS / CATEGORIES
        # -------------------------------------------------
        if semantic_type in {
            "ENUM_CATEGORY",
            "TEXT_CATEGORY",
            "LABEL",
        }:
            constraints.update({
                "supports_grouping": True,
                "supports_equality_filtering": True,
                "supports_segmentation": True,
                "should_not_average": True,
                "should_not_sum": True,
            })

        # -------------------------------------------------
        # TEMPORAL
        # -------------------------------------------------
        if semantic_type in {
            "DATE",
            "DATETIME",
            "TIME",
        } or process_vst_role == "EVENT_TIME":
            constraints.update({
                "supports_temporal_filtering": True,
                "supports_time_bucketing": True,
                "supports_trend_analysis": True,
                "supports_windowing": True,
            })

        # -------------------------------------------------
        # PROCESS MEASURES
        # -------------------------------------------------
        if process_vst_role == "EVENT_MEASURE":
            constraints.update({
                "supports_temporal_aggregation": True,
                "supports_rate_computation": True,
                "supports_window_aggregation": True,
            })

        # -------------------------------------------------
        # STATE VARIABLES
        # -------------------------------------------------
        if process_vst_role == "STATE_VARIABLE":
            constraints.update({
                "supports_change_detection": True,
                "supports_transition_analysis": True,
                "supports_state_tracking": True,
            })

        # -------------------------------------------------
        # CONDITIONAL / SEGMENTATION
        # -------------------------------------------------
        if role == "SEGMENTATION_DRIVER":
            constraints.update({
                "supports_conditional_distribution": True,
                "supports_group_conditioning": True,
                "supports_cohort_analysis": True,
            })

        return {
            "query_constraints": constraints,
            "confidence": 0.85,
            "rationale": "Operational query constraints inferred from semantic roles and value semantics.",
        }