class ProcessOperatorInferencer:
    name = "process_operator_semantics"

    def infer_table(self, table, process_semantics, process_patterns=None):
        if not process_semantics:
            return None

        event_time = process_semantics.get("event_time")
        process_keys = process_semantics.get("process_keys", [])
        event_measures = process_semantics.get("event_measures", [])

        if not event_time:
            return None

        operators = []

        operators.append(
            {
                "operator": "AGGREGATE_OVER_TIME",
                "requires_time_bucketing": True,
                "time_attribute": event_time,
                "time_grain_candidates": ["day", "week", "month"],
                "default_time_grain": "month",
                "confidence": 0.75,
            }
        )

        if event_measures:
            operators.append(
                {
                    "operator": "AGGREGATE_THEN_TREND",
                    "requires_time_bucketing": True,
                    "requires_aggregation": True,
                    "time_attribute": event_time,
                    "measures": event_measures,
                    "trend_metric": "slope",
                    "confidence": 0.7,
                }
            )

        if process_keys:
            operators.append(
                {
                    "operator": "WINDOW_PERSISTENCE",
                    "intent_terms": [
                        "sustained",
                        "persistent",
                        "consistently",
                        "recurring",
                    ],
                    "requires_time_bucketing": True,
                    "requires_window_analysis": True,
                    "process_keys": process_keys,
                    "time_attribute": event_time,
                    "min_periods": 3,
                    "confidence": 0.65,
                }
            )

        for measure in event_measures:
            for key in process_keys:
                operators.append(
                    {
                        "operator": "NORMALIZED_RATE",
                        "intent_terms": ["rate", "risk", "per"],
                        "numerator": measure,
                        "denominator": key,
                        "formula_template": f"SUM({measure}) / COUNT({key})",
                        "requires_normalization": True,
                        "confidence": 0.7,
                    }
                )

        state_candidates = self._state_variable_candidates(table, process_semantics)

        for state_attr in state_candidates:
            operators.append(
                {
                    "operator": "CHANGE_DETECTION",
                    "intent_terms": [
                        "changed",
                        "became",
                        "transition",
                        "moved from",
                        "shifted",
                    ],
                    "state_attribute": state_attr,
                    "process_keys": process_keys,
                    "event_time": event_time,
                    "requires_sequence": True,
                    "confidence": 0.65,
                }
            )

        if not operators:
            return None

        return {
            "process_operators": operators,
            "query_constraints": self._query_constraints(operators),
            "confidence": 0.75,
            "rationale": (
                "Operational process semantics inferred from event time, "
                "process keys, event measures, and process patterns."
            ),
        }

    def _state_variable_candidates(self, table, process_semantics):
        event_time = process_semantics.get("event_time")
        process_keys = set(process_semantics.get("process_keys", []))
        measures = set(process_semantics.get("event_measures", []))

        candidates = []

        for column in table.columns:
            name = column.name

            if name == event_time:
                continue

            if name in process_keys:
                continue

            if name in measures:
                continue

            stats = column.stats
            distinct = stats.distinct_count
            row_count = stats.row_count or 0

            if distinct is None or row_count == 0:
                continue

            if distinct <= min(20, row_count * 0.2):
                candidates.append(name)

        return candidates

    def _query_constraints(self, operators):
        constraints = {
            "requires_temporal_reasoning": False,
            "requires_time_bucketing": False,
            "requires_grouped_trend": False,
            "requires_normalization": False,
            "requires_window_analysis": False,
            "requires_sequence": False,
        }

        for op in operators:
            if op.get("operator") in {
                "AGGREGATE_OVER_TIME",
                "AGGREGATE_THEN_TREND",
                "WINDOW_PERSISTENCE",
                "CHANGE_DETECTION",
            }:
                constraints["requires_temporal_reasoning"] = True

            if op.get("requires_time_bucketing"):
                constraints["requires_time_bucketing"] = True

            if op.get("operator") == "AGGREGATE_THEN_TREND":
                constraints["requires_grouped_trend"] = True

            if op.get("requires_normalization"):
                constraints["requires_normalization"] = True

            if op.get("requires_window_analysis"):
                constraints["requires_window_analysis"] = True

            if op.get("requires_sequence"):
                constraints["requires_sequence"] = True

        return constraints