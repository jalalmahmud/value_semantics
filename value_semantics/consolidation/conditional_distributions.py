import numpy as np


class ConditionalDistributionInferencer:
    def infer(self, results, table):
        semantics = results.get("semantics", {})
        links = results.get("table_semantics", {}).get("semantic_links", [])

        if not links or not getattr(table, "row_samples", None):
            return results

        for link in links:
            if link.get("relationship") != "SEGMENTS":
                continue

            if link.get("validation_status") not in {"accepted", "provisional"}:
                continue

            if link.get("confidence", 0.0) < 0.65:
                continue

            group_attr = link.get("source")
            value_attr = link.get("target")

            group_sem = semantics.get(group_attr, {})
            value_sem = semantics.get(value_attr, {})

            group_role = group_sem.get("semantic_role", {})
            value_vs = value_sem.get("value_semantics", {})

            if group_role.get("primary_role") != "SEGMENTATION_DRIVER":
                continue

            if value_vs.get("semantic_type") not in {
                "CURRENCY_AMOUNT",
                "INTEGER",
                "FLOAT",
                "NUMERIC_GENERAL",
                "PERCENTAGE",
                "RATIO",
                "DURATION",
            }:
                continue

            cds = self._infer_distribution(
                group_attr=group_attr,
                value_attr=value_attr,
                row_samples=table.row_samples,
            )

            if not cds:
                continue

            existing = value_sem.get("conditional_value_distribution", {})
            existing[group_attr] = cds
            value_sem["conditional_value_distribution"] = existing
            semantics[value_attr] = value_sem

        results["semantics"] = semantics
        return results

    def _infer_distribution(self, group_attr, value_attr, row_samples):
        groups = {}

        for row in row_samples:
            g = row.get(group_attr)
            v = row.get(value_attr)

            if g is None or v is None:
                continue

            try:
                v = float(v)
            except Exception:
                continue

            groups.setdefault(g, []).append(v)

        profiles = {}
        min_support = 10

        for group, values in groups.items():
            key = str(group)

            if len(values) < min_support:
                profiles[key] = {
                    "count": len(values),
                    "typical_range": [],
                    "extreme_range": [],
                    "recommended_stat": None,
                    "confidence": 0.3,
                    "fallback": {
                        "strategy": "GLOBAL_VALUE_AXIS",
                        "axis_attribute": value_attr,
                        "reason": "insufficient samples for stable conditional statistics",
                        "min_support": min_support,
                    },
                }
                continue

            p50 = np.percentile(values, 50)
            p90 = np.percentile(values, 90)
            p99 = np.percentile(values, 99)

            profiles[key] = {
                "count": len(values),
                "p50": round(float(p50), 2),
                "p90": round(float(p90), 2),
                "p99": round(float(p99), 2),
                "typical_range": [
                    round(float(np.min(values)), 2),
                    round(float(p90), 2),
                ],
                "extreme_range": [
                    round(float(p90), 2),
                    round(float(np.max(values)), 2),
                ],
                "recommended_stat": "p99",
                "confidence": 0.75,
            }

        if len(profiles) < 2:
            return None

        if len(profiles) > 10:
            return None

        return {
            "group_attribute": group_attr,
            "value_attribute": value_attr,
            "profiles": profiles,
            "recommended_stat": "p99",
            "confidence": 0.7,
            "rationale": (
                "Conditional distributions inferred from row-aligned numeric behavior; "
                "fallback used for sparse groups."
            ),
        }