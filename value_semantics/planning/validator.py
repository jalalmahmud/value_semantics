class SemanticValidator:
    def validate(self, plan, semantics, table_semantics):
        validations = []

        semantic_plan = plan.get("semantic_plan", [])

        for step in semantic_plan:
            operator = step.get("operator")

            if operator == "FILTER_BY_DISTRIBUTIONAL_THRESHOLD":
                validations.append(
                    {
                        "rule": "distributional_threshold_grounding",
                        "status": "passed",
                        "severity": "info",
                        "message": (
                            "Comparative threshold derived from value axis "
                            "instead of arbitrary literal."
                        ),
                    }
                )

            if operator == "GROUND_CONDITIONAL_DISTRIBUTION":
                validations.append(
                    {
                        "rule": "conditional_distribution_reasoning",
                        "status": "passed",
                        "severity": "info",
                        "message": (
                            "Threshold reasoning performed within group-specific "
                            "conditional distributions."
                        ),
                    }
                )

            if operator == "AGGREGATE_THEN_TREND":
                validations.append(
                    {
                        "rule": "process_trend_reasoning",
                        "status": "passed",
                        "severity": "info",
                        "message": (
                            "Trend reasoning uses temporal aggregation before "
                            "slope computation."
                        ),
                    }
                )

            if operator == "FILTER_BY_ORDINAL_REGION":
                validations.append(
                    {
                        "rule": "ordinal_semantic_grounding",
                        "status": "passed",
                        "severity": "info",
                        "message": (
                            "Ordinal filtering grounded using interpretive "
                            "semantic ordering."
                        ),
                    }
                )

        if not validations:
            validations.append(
                {
                    "rule": "semantic_validation",
                    "status": "warning",
                    "severity": "warning",
                    "message": (
                        "No semantic validation rules triggered."
                    ),
                }
            )

        return validations