from value_semantics.core.pipeline import InferenceModule


class QuantitativeInferencer(InferenceModule):
    name = "quantitative_vst"
    requires = ["value_semantics"]
    produces = ["quantitative_vst"]

    NUMERIC_TYPES = {
        "INTEGER",
        "FLOAT",
        "NUMERIC_GENERAL",
        "CURRENCY_AMOUNT",
        "PERCENTAGE",
        "RATIO",
        "DURATION",
    }

    def _looks_identifier_like(self, column_name):
        name = column_name.lower()

        if name.endswith("_id"):
            return True

        if name in {
            "id",
            "account",
            "account_no",
            "account_num",
            "account_number",
            "code",
            "number",
            "num",
            "identifier",
        }:
            return True

        return False

    def infer(self, context):
        column = context.column

        if self._looks_identifier_like(column.name):
            return None

        table = context.table
        value_semantics = context.get("value_semantics") or {}
        value_axis = context.get("value_axis") or {}

        if value_semantics.get("is_identifier"):
            return None

        semantic_type = value_semantics.get("semantic_type")
        if semantic_type not in self.NUMERIC_TYPES:
            return None

        nums = self.get_numeric_samples(column)
        if not nums:
            return None

        qvst = self.infer_quantitative_role(
            column=column,
            value_semantics=value_semantics,
            value_axis=value_axis,
            nums=nums,
        )

        if not qvst:
            return None

        qvst["safe_aggregation"] = self.infer_safe_aggregation(
            value_semantics=value_semantics,
            qvst=qvst,
        )

        derived = self.infer_derived_metric_candidates(
            column=column,
            table=table,
            value_semantics=value_semantics,
            qvst=qvst,
        )

        if derived:
            qvst["derived_metric_candidates"] = derived

        return qvst

    def get_numeric_samples(self, column):
        nums = []
        for v in column.stats.sample_values:
            try:
                nums.append(float(v))
            except Exception:
                pass
        return nums

    def infer_quantitative_role(self, column, value_semantics, value_axis, nums):
        semantic_type = value_semantics.get("semantic_type")
        name = column.name.lower()

        # State / snapshot measures
        if any(k in name for k in ["balance", "inventory", "stock", "remaining"]):
            return {
                "role": "STATE_MEASURE",
                "subtype": "snapshot_value",
                "confidence": 0.9,
                "rationale": "Column name suggests a state/snapshot measure that should not be summed directly.",
            }

        # Flow / additive measures
        if any(
            k in name
            for k in ["amount", "payment", "price", "cost", "salary", "revenue"]
        ):
            return {
                "role": "MEASUREMENT",
                "subtype": "flow_amount",
                "confidence": 0.85,
                "rationale": "Column name suggests an additive monetary or transactional amount.",
            }

        if value_axis:
            axis_type = value_axis.get("axis_type")

            if axis_type == "DISCRETE_COUNT":
                return {
                    "role": "COUNT",
                    "confidence": 0.9,
                    "rationale": "Sparse discrete count behavior inferred via value axis.",
                }

            if axis_type == "CONTINUOUS":
                return {
                    "role": "MEASUREMENT",
                    "confidence": 0.85,
                    "rationale": "Continuous ordered magnitude inferred via value axis.",
                }

        if semantic_type in {"CURRENCY_AMOUNT", "DURATION"}:
            return {
                "role": "MEASUREMENT",
                "confidence": 0.9,
                "rationale": f"{semantic_type} represents a measurable quantity.",
            }

        if semantic_type in {"PERCENTAGE", "RATIO"}:
            return {
                "role": "COMPUTATIONAL",
                "subtype": "ratio_or_percentage",
                "confidence": 0.85,
                "rationale": "Ratio or percentage values represent derived/normalized metrics.",
            }

        if semantic_type == "INTEGER":
            if self.is_sparse_count_axis(value_semantics, column, nums):
                threshold = self.infer_tail_threshold(nums)
                return {
                    "role": "COUNT",
                    "subtype": "sparse_count",
                    "tail_threshold": threshold,
                    "confidence": 0.85,
                    "rationale": "Sparse or zero-inflated integer distribution indicates count semantics.",
                }

            min_val, max_val = min(nums), max(nums)

            if 0 <= min_val and max_val <= 150:
                return {
                    "role": "MEASUREMENT",
                    "subtype": "bounded_quantity",
                    "confidence": 0.75,
                    "rationale": "Integer values fall within a bounded real-world measurement range.",
                }

            return {
                "role": "MAGNITUDE",
                "confidence": 0.7,
                "rationale": "General integer magnitude.",
            }

        if semantic_type in {"FLOAT", "NUMERIC_GENERAL"}:
            numeric = value_semantics.get("numeric", {}) or {}

            if numeric.get("is_discrete", False) and self.is_sparse_count_axis(
                value_semantics, column, nums
            ):
                return {
                    "role": "COUNT",
                    "confidence": 0.75,
                    "rationale": "Discrete sparse numeric behavior indicates count semantics.",
                }

            min_val, max_val = min(nums), max(nums)

            if 0 <= min_val and max_val <= 1:
                return {
                    "role": "COMPUTATIONAL",
                    "subtype": "normalized",
                    "confidence": 0.75,
                    "rationale": "Values fall within normalized [0,1] range.",
                }

            return {
                "role": "MAGNITUDE",
                "confidence": 0.65,
                "rationale": "Continuous numeric magnitude.",
            }

        if any(k in name for k in ["count", "num_", "total_", "cnt"]):
            return {
                "role": "COUNT",
                "confidence": 0.7,
                "rationale": "Column name suggests count semantics.",
            }

        if any(k in name for k in ["rate", "ratio", "percent", "pct"]):
            return {
                "role": "COMPUTATIONAL",
                "confidence": 0.7,
                "rationale": "Column name suggests derived metric semantics.",
            }

        return None

    def infer_safe_aggregation(self, value_semantics, qvst):
        semantic_type = value_semantics.get("semantic_type")
        role = qvst.get("role")
        subtype = qvst.get("subtype")

        safe = {
            "default": None,
            "allowed": [],
            "forbidden": [],
            "reason": "No quantitative aggregation rule inferred.",
            "confidence": 0.4,
        }

        if role == "COUNT":
            safe.update(
                {
                    "default": "SUM",
                    "allowed": ["SUM", "AVG", "MIN", "MAX"],
                    "forbidden": [],
                    "reason": "Count-like measures are usually additive across groups.",
                    "confidence": 0.8,
                }
            )

        elif role == "STATE_MEASURE":
            safe.update(
                {
                    "default": "AVG",
                    "allowed": ["AVG", "MIN", "MAX"],
                    "forbidden": ["SUM"],
                    "reason": "State/snapshot measures such as balances should not be summed across rows.",
                    "confidence": 0.9,
                }
            )

        elif role == "MEASUREMENT":
            safe.update(
                {
                    "default": "SUM",
                    "allowed": ["SUM", "AVG", "MIN", "MAX"],
                    "forbidden": [],
                    "reason": "Measurement values can often be summed or averaged unless constrained by context.",
                    "confidence": 0.7,
                }
            )

        elif role == "MAGNITUDE":
            safe.update(
                {
                    "default": "AVG",
                    "allowed": ["AVG", "MIN", "MAX", "SUM"],
                    "forbidden": [],
                    "reason": "Magnitude values are often compared or averaged; SUM may be valid depending on context.",
                    "confidence": 0.65,
                }
            )

        elif role == "COMPUTATIONAL":
            safe.update(
                {
                    "default": "AVG",
                    "allowed": ["AVG", "MIN", "MAX"],
                    "forbidden": ["SUM"],
                    "reason": "Ratios, rates, percentages, and normalized values should not be summed directly.",
                    "confidence": 0.85,
                }
            )

        if semantic_type == "CURRENCY_AMOUNT" and role != "STATE_MEASURE":
            safe.update(
                {
                    "default": "SUM",
                    "allowed": ["SUM", "AVG", "MIN", "MAX"],
                    "forbidden": [],
                    "reason": "Currency amount is commonly additive unless marked as a state/snapshot measure, rate, or ratio.",
                    "confidence": max(safe.get("confidence", 0.0), 0.75),
                }
            )

        if semantic_type in {"RATIO", "PERCENTAGE"} or subtype in {
            "ratio_or_percentage",
            "normalized",
        }:
            safe.update(
                {
                    "default": "AVG",
                    "allowed": ["AVG", "MIN", "MAX"],
                    "forbidden": ["SUM"],
                    "reason": "Ratio-like values should not be summed directly.",
                    "confidence": max(safe.get("confidence", 0.0), 0.85),
                }
            )

        return safe

    def infer_derived_metric_candidates(self, column, table, value_semantics, qvst):
        semantic_type = value_semantics.get("semantic_type")
        role = qvst.get("role")

        if role == "STATE_MEASURE":
            return []

        if semantic_type in {"PERCENTAGE", "RATIO"}:
            return []

        if role == "COMPUTATIONAL":
            return []

        denominator_candidates = []

        for other in table.columns:
            if other.name == column.name:
                continue

            other_name = other.name.lower()
            other_samples = other.stats.sample_values

            if other_name.endswith("_id") or other_name == "id":
                denominator_candidates.append(
                    {
                        "attribute": other.name,
                        "denominator_role": "IDENTIFIER",
                        "reason": "Identifier-like attribute can serve as COUNT denominator.",
                        "confidence": 0.75,
                        "source": "name_heuristic",
                    }
                )
                continue

            if other.stats.distinct_count == other.stats.row_count:
                denominator_candidates.append(
                    {
                        "attribute": other.name,
                        "denominator_role": "UNIQUE_KEY",
                        "reason": "Column appears unique and can serve as count denominator.",
                        "confidence": 0.65,
                        "source": "profile_statistics",
                    }
                )

        if not denominator_candidates:
            return []

        return [
            {
                "metric_type": "NORMALIZED_RATE",
                "intent_terms": ["rate", "risk", "per", "ratio"],
                "formula_template": f"SUM({column.name}) / COUNT({{denominator}})",
                "numerator": column.name,
                "denominator_candidates": denominator_candidates,
                "preferred_denominator": denominator_candidates[0]["attribute"],
                "requires_query_context": True,
                "confidence": denominator_candidates[0]["confidence"],
            }
        ]

    def is_sparse_count_axis(self, value_semantics, column, values):
        if not values:
            return False

        semantic_type = value_semantics.get("semantic_type")

        if semantic_type not in {"INTEGER", "NUMERIC_GENERAL"}:
            return False

        name = column.name.lower()

        if name in {"latitude", "longitude", "lat", "lon", "lng"}:
            return False

        numeric = value_semantics.get("numeric", {}) or {}

        if numeric and not numeric.get("is_discrete", True):
            return False

        n = len(values)
        zero_frac = sum(v == 0 for v in values) / n
        max_val = max(values)
        distinct = len(set(values))

        if zero_frac >= 0.7 and distinct <= 10:
            return True

        if zero_frac >= 0.4 and max_val >= 5:
            return True

        return False

    def infer_tail_threshold(self, values):
        values = sorted(values)
        n = len(values)

        non_zero = [v for v in values if v > 0]

        if not non_zero:
            return None

        if max(non_zero) <= 3:
            return 1

        for threshold in [5, 10, 15, 20]:
            frac = sum(v >= threshold for v in values) / n

            if frac < 0.01:
                return threshold

        return max(values)