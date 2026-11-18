import numpy as np

from value_semantics.core.pipeline import InferenceModule


class ValueAxisInferencer(InferenceModule):
    name = "value_axis"
    requires = ["value_semantics", "interpretive_semantics"]
    produces = ["value_axis"]

    NUMERIC_TYPES = {
        "INTEGER",
        "FLOAT",
        "NUMERIC_GENERAL",
        "CURRENCY_AMOUNT",
        "PERCENTAGE",
        "RATIO",
        "DURATION",
    }

    def infer(self, context):
        column = context.column
        value_semantics = context.get("value_semantics") or {}
        interpretive = context.get("interpretive_semantics") or {}

        if value_semantics.get("is_identifier"):
            return None

        # -------------------------------------------------
        # 1. ORDINAL / INTERPRETIVE AXIS
        # -------------------------------------------------
        if interpretive and interpretive.get("confidence", 0.0) >= 0.7:
            ordering = interpretive.get("ordering", [])

            if len(ordering) >= 2:
                return {
                    "axis_type": "ORDINAL",
                    "ordering": ordering,
                    "polarity": interpretive.get(
                        "polarity",
                        {
                            "direction": "increasing",
                            "meaning": "level",
                        },
                    ),
                    "extreme_regions": interpretive.get(
                        "extreme_regions",
                        {
                            "low": ordering[:1],
                            "high": ordering[-1:],
                        },
                    ),
                    "confidence": interpretive.get("confidence", 0.7),
                    "rationale": (
                        "Promoted from interpretive semantics after ordinal "
                        "categorical ordering was detected."
                    ),
                    "source": "interpretive_semantics",
                }

        # -------------------------------------------------
        # 2. NUMERIC / DISTRIBUTIONAL AXIS
        # -------------------------------------------------
        if value_semantics.get("semantic_type") not in self.NUMERIC_TYPES:
            return None

        values = []

        for v in column.stats.sample_values:
            try:
                values.append(float(v))
            except Exception:
                pass

        if len(values) < 3:
            return None

        p10 = np.percentile(values, 10)
        p90 = np.percentile(values, 90)

        return {
            "axis_type": "CONTINUOUS",
            "polarity": {
                "direction": "increasing",
                "meaning": "magnitude",
            },
            "extreme_regions": {
                "small": f"< {round(p10, 2)}",
                "large": f"> {round(p90, 2)}",
            },
            "confidence": 0.7,
            "rationale": "Distributional extremes inferred from numeric samples.",
            "source": "numeric_distribution",
        }