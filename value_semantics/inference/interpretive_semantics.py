class InterpretiveSemanticsInferencer:
    name = "interpretive_semantics"

    ORDERINGS = [
        ["low", "medium", "high"],
        ["poor", "fair", "good", "excellent"],
        ["bad", "average", "good"],
        ["bronze", "silver", "gold", "platinum"],
        ["junior", "mid", "senior", "lead", "principal"],
        ["junior", "classic", "gold"],
        ["small", "medium", "large"],
        ["minor", "moderate", "major", "severe", "fatal"],
        ["A", "B", "C", "D"],
    ]

    def infer(self, context):
        column = context.column
        value_semantics = context.get("value_semantics") or {}

        if value_semantics.get("is_identifier"):
            return None

        if value_semantics.get("semantic_type") not in {
            "ENUM_CATEGORY",
            "TEXT_CATEGORY",
            "LABEL",
            "STRING",
            "CONTROLLED_TERM",
        }:
            return None

        raw_values = [
            str(v).strip()
            for v in column.stats.sample_values
            if v is not None and str(v).strip()
        ]

        if not raw_values:
            return None

        lower_to_original = {}
        for v in raw_values:
            lower_to_original[v.lower()] = v

        unique_values = sorted(set(v.lower() for v in raw_values))

        for ordering in self.ORDERINGS:
            ordering_lower = [str(v).lower() for v in ordering]
            matched_lower = [v for v in ordering_lower if v in unique_values]

            if len(matched_lower) >= 2:
                matched = [
                    lower_to_original.get(v, v)
                    for v in matched_lower
                ]

                return {
                    "interpretation_type": self._interpretation_type(column.name, matched_lower),
                    "ordering": matched,
                    "polarity": {
                        "direction": "increasing",
                        "meaning": self._meaning(column.name, matched_lower),
                    },
                    "extreme_regions": {
                        "low": matched[:1],
                        "high": matched[-1:],
                    },
                    "confidence": 0.8,
                    "rationale": "Known ordered categorical pattern detected.",
                    "evidence": {
                        "matched_values": matched,
                        "unique_values": unique_values,
                    },
                }

        return None

    def _interpretation_type(self, column_name, matched_values):
        name = column_name.lower()

        if "severity" in name or any(v in matched_values for v in ["minor", "severe", "fatal"]):
            return "SEVERITY"

        if "risk" in name:
            return "RISK_LEVEL"

        if "tier" in name or any(v in matched_values for v in ["bronze", "silver", "gold", "platinum"]):
            return "TIER"

        return "ORDINAL"

    def _meaning(self, column_name, matched_values):
        name = column_name.lower()

        if "severity" in name or any(v in matched_values for v in ["minor", "severe", "fatal"]):
            return "severity"

        if "risk" in name:
            return "risk"

        if "priority" in name:
            return "priority"

        if "status" in name:
            return "status_level"

        if "tier" in name or "type" in name:
            return "tier"

        return "level"