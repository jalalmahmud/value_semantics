class DatabaseSemanticsInferencer:
    def infer_database(self, table_results):
        relational_links = []

        candidates = self._collect_identifier_columns(table_results)

        for col_name, occurrences in candidates.items():
            if len(occurrences) < 2:
                continue

            parent = self._choose_parent_table(occurrences)
            if not parent:
                continue

            for occ in occurrences:
                if occ["table"] == parent["table"]:
                    continue

                link = self._build_fk_link(
                    child=occ,
                    parent=parent,
                    col_name=col_name,
                )

                relational_links.append(link)

        return {
            "relational_links": relational_links,
        }

    def _collect_identifier_columns(self, table_results):
        candidates = {}

        for table_name, result in table_results.items():
            row_count = self._estimate_row_count(result)

            for col_name, sem in result.get("semantics", {}).items():
                vs = sem.get("value_semantics", {})

                if not vs.get("is_identifier"):
                    continue

                col_profile = result.get("columns", {}).get(col_name, {})
                distinct_count = self._estimate_distinct_count(
                    result=result,
                    column_name=col_name,
                )

                unique_ratio = (
                    distinct_count / row_count
                    if row_count and distinct_count is not None
                    else None
                )

                candidates.setdefault(col_name, []).append(
                    {
                        "table": table_name,
                        "column": col_name,
                        "row_count": row_count,
                        "distinct_count": distinct_count,
                        "unique_ratio": unique_ratio,
                        "semantic_type": vs.get("semantic_type"),
                        "sample_values": col_profile.get("sample_values", []),
                    }
                )

        return candidates

    def _choose_parent_table(self, occurrences):
        valid = [
            occ for occ in occurrences
            if occ.get("unique_ratio") is not None
        ]

        if not valid:
            return None

        # Parent table usually has identifier closest to unique per row.
        valid = sorted(
            valid,
            key=lambda x: (
                x.get("unique_ratio", 0.0),
                -x.get("row_count", 0),
            ),
            reverse=True,
        )

        parent = valid[0]

        if parent.get("unique_ratio", 0.0) < 0.7:
            return None

        return parent

    def _build_fk_link(self, child, parent, col_name):
        child_ratio = child.get("unique_ratio") or 0.0
        parent_ratio = parent.get("unique_ratio") or 0.0

        cardinality = "MANY_TO_ONE"

        if child_ratio >= 0.8 and parent_ratio >= 0.8:
            cardinality = "ONE_TO_ONE"
        elif child_ratio < parent_ratio:
            cardinality = "MANY_TO_ONE"

        duplication_risk = cardinality == "MANY_TO_ONE"

        confidence = 0.75

        if parent_ratio >= 0.95:
            confidence += 0.1

        if child["column"] == parent["column"]:
            confidence += 0.05

        if child_ratio < 0.8:
            confidence += 0.05

        confidence = min(confidence, 0.95)

        return {
            "relationship": "FOREIGN_KEY_LIKE",
            "source_table": child["table"],
            "source_column": child["column"],
            "target_table": parent["table"],
            "target_column": parent["column"],
            "cardinality": cardinality,
            "confidence": confidence,
            "join_constraints": {
                "duplication_risk": duplication_risk,
                "parent_table": parent["table"],
                "child_table": child["table"],
                "recommended_count": (
                    f"COUNT(DISTINCT {parent['table']}.{parent['column']})"
                    if duplication_risk
                    else f"COUNT({parent['table']}.{parent['column']})"
                ),
            },
            "evidence": {
                "child_row_count": child.get("row_count"),
                "child_distinct_count": child.get("distinct_count"),
                "child_unique_ratio": round(child_ratio, 4),
                "parent_row_count": parent.get("row_count"),
                "parent_distinct_count": parent.get("distinct_count"),
                "parent_unique_ratio": round(parent_ratio, 4),
            },
            "rationale": (
                "Identifier column appears in multiple tables; "
                "parent selected by higher uniqueness ratio."
            ),
        }

    def _estimate_row_count(self, result):
        columns = result.get("columns", {})
        if not columns:
            return 0

        for col_profile in columns.values():
            stats = col_profile.get("stats", {})
            if stats.get("row_count") is not None:
                return stats["row_count"]

        max_samples = 0
        for col in columns.values():
            samples = col.get("sample_values", [])
            max_samples = max(max_samples, len(samples))

        return max_samples

    def _estimate_distinct_count(self, result, column_name):
        col_profile = result.get("columns", {}).get(column_name, {})
        stats = col_profile.get("stats", {})

        if stats.get("distinct_count") is not None:
            return stats["distinct_count"]

        samples = col_profile.get("sample_values", [])

        if not samples:
            return None

        return len(set(samples))

        