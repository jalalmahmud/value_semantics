class LinkValidator:
    def validate(self, link, column_semantics, table):
        relationship = link.get("relationship")

        if relationship == "SEGMENTS":
            return self._validate_segments(link, column_semantics, table)

        return {
            "validation_status": "provisional",
            "confidence_adjustment": -0.1,
            "reason": "No specific validator available.",
        }

    def _validate_segments(self, link, column_semantics, table):
        source = link["source"]
        target = link["target"]

        source_sem = column_semantics.get(source, {})
        target_sem = column_semantics.get(target, {})

        source_vs = source_sem.get("value_semantics", {})
        target_vs = target_sem.get("value_semantics", {})

        target_qvst = target_sem.get("quantitative_vst", {})

        # SEGMENTS should usually be categorical -> quantitative
        if source_vs.get("semantic_type") not in {
            "ENUM_CATEGORY",
            "TEXT_CATEGORY",
            "LABEL",
            "STRING",
        }:
            return {
                "validation_status": "rejected",
                "confidence_adjustment": -1.0,
                "reason": "SEGMENTS source must be categorical or label-like.",
            }

        if not target_qvst and target_vs.get("semantic_type") not in {
            "INTEGER",
            "FLOAT",
            "NUMERIC_GENERAL",
            "CURRENCY_AMOUNT",
            "PERCENTAGE",
            "RATIO",
            "DURATION",
        }:
            return {
                "validation_status": "rejected",
                "confidence_adjustment": -1.0,
                "reason": "SEGMENTS target must be quantitative.",
            }

        support = self._group_support(table, source, target)

        if support["num_groups"] < 2:
            return {
                "validation_status": "rejected",
                "confidence_adjustment": -1.0,
                "reason": "Insufficient number of source groups.",
                "evidence": support,
            }

        if support["supported_groups"] < 2:
            return {
                "validation_status": "rejected",
                "confidence_adjustment": -1.0,
                "reason": "Insufficient supported source groups.",
                "evidence": support,
            }

        return {
            "validation_status": "accepted",
            "confidence_adjustment": 0.05,
            "reason": "Categorical source has sufficient support and segments quantitative target.",
            "evidence": support,
        }

    def _group_support(self, table, source, target):
        groups = {}

        for row in table.row_samples:
            g = row.get(source)
            v = row.get(target)

            if g is None or v is None:
                continue

            try:
                float(v)
            except Exception:
                continue

            groups.setdefault(g, 0)
            groups[g] += 1

        return {
            "num_groups": len(groups),
            "supported_groups": sum(1 for count in groups.values() if count >= 1),
            "group_counts": dict(groups),
        }