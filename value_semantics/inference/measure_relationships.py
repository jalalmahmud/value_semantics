class MeasureRelationshipInferencer:
    name = "measure_relationships"

    def infer_table(self, table, column_semantics):
        numeric_cols = []

        for col in table.columns:
            sem = column_semantics.get(col.name, {})
            qvst = sem.get("quantitative_vst", {})
            vs = sem.get("value_semantics", {})

            if vs.get("is_identifier"):
                continue

            if not qvst:
                continue

            numeric_cols.append(col.name)

        relationships = {}

        for total_col in numeric_cols:
            for component_set in self._candidate_component_sets(
                total_col,
                numeric_cols,
            ):
                evidence = self._check_total_component_relation(
                    table,
                    total_col,
                    component_set,
                )

                if not evidence:
                    continue

                relationships[total_col] = {
                    "measure_role": "TOTAL",
                    "components": component_set,
                    "aggregation_constraint": "DO_NOT_SUM_WITH_COMPONENTS",
                    "safe_aggregation": {
                        "default": "SUM",
                        "allowed": ["SUM", "AVG", "MIN", "MAX"],
                        "forbidden_with": component_set,
                        "reason": (
                            "Column appears to be a total composed of component measures; "
                            "avoid summing together with its components."
                        ),
                        "confidence": evidence["confidence"],
                    },
                    "confidence": evidence["confidence"],
                    "evidence": evidence,
                }

                for component in component_set:
                    relationships[component] = {
                        "measure_role": "COMPONENT",
                        "part_of_total": total_col,
                        "aggregation_constraint": "DO_NOT_SUM_WITH_TOTAL",
                        "confidence": evidence["confidence"],
                        "evidence": evidence,
                    }

                break

        return relationships or None

    def _candidate_component_sets(self, total_col, numeric_cols):
        total_lower = total_col.lower()

        candidates = [
            c for c in numeric_cols
            if c != total_col
        ]

        # Simple name-based pruning
        if "total" in total_lower:
            related = [
                c for c in candidates
                if self._name_overlap(total_col, c)
            ]

            if len(related) >= 2:
                yield related

        # Fallback: try small component sets only
        if len(candidates) >= 2 and len(candidates) <= 6:
            yield candidates

    def _name_overlap(self, a, b):
        a_parts = set(a.lower().replace("_", " ").split())
        b_parts = set(b.lower().replace("_", " ").split())

        weak_words = {
            "total",
            "number",
            "num",
            "count",
            "amount",
            "value",
        }

        a_parts -= weak_words
        b_parts -= weak_words

        if not a_parts or not b_parts:
            return True

        return bool(a_parts & b_parts)

    def _check_total_component_relation(self, table, total_col, components):
        checked = 0
        exact = 0
        close = 0
        errors = []

        for row in table.row_samples:
            total = row.get(total_col)

            try:
                total = float(total)
            except Exception:
                continue

            component_values = []

            valid = True
            for c in components:
                try:
                    component_values.append(float(row.get(c)))
                except Exception:
                    valid = False
                    break

            if not valid:
                continue

            component_sum = sum(component_values)
            checked += 1

            error = abs(total - component_sum)
            denom = max(abs(total), abs(component_sum), 1.0)
            rel_error = error / denom

            errors.append(rel_error)

            if error == 0:
                exact += 1

            if rel_error <= 0.05:
                close += 1

        if checked < 20:
            return None

        close_ratio = close / checked
        exact_ratio = exact / checked
        avg_relative_error = sum(errors) / len(errors) if errors else 1.0

        if close_ratio < 0.8:
            return None

        return {
            "total_column": total_col,
            "component_columns": components,
            "rows_checked": checked,
            "close_ratio": round(close_ratio, 3),
            "exact_ratio": round(exact_ratio, 3),
            "avg_relative_error": round(avg_relative_error, 5),
            "confidence": min(0.95, 0.7 + close_ratio * 0.25),
        }