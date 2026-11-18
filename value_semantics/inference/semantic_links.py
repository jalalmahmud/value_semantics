from value_semantics.validation.link_validation import LinkValidator


class SemanticLinkInferencer:
    name = "semantic_links"

    def __init__(self):
        self.validator = LinkValidator()

    def infer_table(self, table, column_semantics):
        links = []

        for source_col in table.columns:
            for target_col in table.columns:
                if source_col.name == target_col.name:
                    continue

                source_sem = column_semantics.get(source_col.name, {})
                target_sem = column_semantics.get(target_col.name, {})

                source_vs = source_sem.get("value_semantics", {})
                target_vs = target_sem.get("value_semantics", {})
                target_qvst = target_sem.get("quantitative_vst", {}) or {}
                target_role = target_qvst.get("role")

                if source_vs.get("is_identifier") or target_vs.get("is_identifier"):
                    continue

                if target_role not in {
                    "MEASUREMENT",
                    "COUNT",
                    "MAGNITUDE",
                    "STATE_MEASURE",
                }:
                    continue

                if self.grouped_distribution_signal(table, source_col, target_col):
                    candidate = {
                        "source": source_col.name,
                        "target": target_col.name,
                        "relationship": "SEGMENTS",
                        "signal": "grouped_distribution",
                        "confidence": 0.7,
                        "rationale": "Grouping source values produces meaningfully different target distributions.",
                    }

                    validation = self.validator.validate(
                        candidate,
                        column_semantics,
                        table,
                    )

                    if validation.get("validation_status") == "rejected":
                        continue

                    candidate["validation_status"] = validation.get(
                        "validation_status"
                    )
                    candidate["validation_evidence"] = validation.get(
                        "evidence", {}
                    )
                    candidate["validation_reason"] = validation.get("reason")

                    candidate["confidence"] = min(
                        1.0,
                        max(
                            0.0,
                            candidate["confidence"]
                            + validation.get("confidence_adjustment", 0.0),
                        ),
                    )

                    links.append(candidate)

        return links

    def grouped_distribution_signal(self, table, group_col, value_col):
        groups = {}

        for row in table.row_samples:
            g = row.get(group_col.name)
            v = row.get(value_col.name)

            if g is None or v is None:
                continue

            try:
                v = float(v)
            except Exception:
                continue

            groups.setdefault(g, []).append(v)

        if len(groups) < 2:
            return False

        supported_groups = [vals for vals in groups.values() if len(vals) >= 1]
        if len(supported_groups) < 2:
            return False

        means = [sum(vals) / len(vals) for vals in supported_groups]

        max_mean = max(abs(m) for m in means) if means else 0.0
        if max_mean == 0:
            return False

        spread = max(means) - min(means)
        avg_mean = sum(abs(m) for m in means) / len(means)
        relative_spread = spread / avg_mean if avg_mean > 0 else 0.0

        return spread > 0.12 * max_mean or relative_spread > 0.18