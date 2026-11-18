class ProcessSemanticsInferencer:
    name = "process_semantics"

    def infer_table(self, table, column_semantics):
        event_time = self._find_event_time(column_semantics)
        event_key = self._find_event_key(table, column_semantics)
        process_keys = self._find_process_keys(table, column_semantics, event_key)
        event_measures = self._find_event_measures(column_semantics)

        if not event_time:
            return None

        confidence = 0.4
        if event_key:
            confidence += 0.15
        if process_keys:
            confidence += 0.25
        if event_measures:
            confidence += 0.2

        if confidence < 0.6:
            return None

        return {
            "row_semantics": "EVENT",
            "event_time": event_time,
            "event_key": event_key,
            "process_keys": process_keys,
            "event_measures": event_measures,
            "constraints": {
                "requires_temporal_reasoning": True,
                "requires_time_bucketing": True,
                "row_local_substitution_invalid": True,
            },
            "confidence": min(confidence, 0.9),
            "rationale": (
                "Detected event-time attribute with event key, repeated process keys, "
                "and quantitative event measures."
            ),
        }

    def _find_event_time(self, column_semantics):
        for name, sem in column_semantics.items():
            vs = sem.get("value_semantics", {})
            role = sem.get("semantic_role", {})

            if role.get("primary_role") == "EVENT_TIME":
                return name

            if vs.get("semantic_type") in {"DATE", "DATETIME", "TIME"}:
                return name

        return None

    def _identifier_columns(self, column_semantics):
        ids = []

        for name, sem in column_semantics.items():
            role = sem.get("semantic_role", {})
            vs = sem.get("value_semantics", {})

            if role.get("primary_role") == "IDENTIFIER" or vs.get("is_identifier"):
                ids.append(name)

        return ids

    def _column_counts(self, table, column_name):
        counts = {}

        for row in table.row_samples:
            value = row.get(column_name)
            if value is None:
                continue
            counts[value] = counts.get(value, 0) + 1

        return counts

    def _find_event_key(self, table, column_semantics):
        row_count = len(table.row_samples or [])
        if row_count == 0:
            return None

        best = None
        best_score = 0.0

        for name in self._identifier_columns(column_semantics):
            counts = self._column_counts(table, name)
            if not counts:
                continue

            distinct_count = len(counts)
            unique_ratio = distinct_count / row_count
            max_count = max(counts.values())

            # Event key: nearly one unique id per row.
            score = unique_ratio

            if name.lower() in {"id"} or name.lower().endswith("_id"):
                score += 0.05

            # Penalize repeated IDs.
            if max_count > 1:
                score -= 0.2

            if score > best_score:
                best = name
                best_score = score

        if best_score >= 0.85:
            return best

        return None

    def _find_process_keys(self, table, column_semantics, event_key=None):
        row_count = len(table.row_samples or [])
        if row_count == 0:
            return []

        process_keys = []

        for name in self._identifier_columns(column_semantics):
            if name == event_key:
                continue

            counts = self._column_counts(table, name)
            if not counts:
                continue

            distinct_count = len(counts)
            repeated_values = sum(1 for c in counts.values() if c >= 2)
            repeated_fraction = repeated_values / distinct_count if distinct_count else 0.0
            avg_events_per_key = row_count / distinct_count if distinct_count else 0.0

            # Process key: repeated entity identifier across event rows.
            if repeated_fraction >= 0.2 or avg_events_per_key >= 1.5:
                process_keys.append(name)

        return process_keys

    def _find_event_measures(self, column_semantics):
        measures = []

        for name, sem in column_semantics.items():
            lower = name.lower()

            # Exclude identifier-like names
            if lower == "account":
                continue

            if lower.endswith("_id"):
                continue

            if lower in {
                "zip",
                "zipcode",
                "postal_code",
                "phone",
                "ssn",
            }:
                continue

            value_semantics = sem.get("value_semantics", {})
            semantic_role = sem.get("semantic_role", {})
            quantitative_vst = sem.get("quantitative_vst", {})

            # Exclude identifiers
            if value_semantics.get("is_identifier"):
                continue

            # Require quantitative semantics
            if not quantitative_vst:
                continue

            # Require evidence role
            if semantic_role.get("primary_role") != "EVIDENCE":
                continue

            measures.append(name)

        return measures
        