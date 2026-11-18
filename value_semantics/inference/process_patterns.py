import numpy as np


class ProcessPatternInferencer:
    name = "process_patterns"

    def infer_table(self, table, process_semantics):
        if not process_semantics:
            return None

        event_time = process_semantics.get("event_time")
        process_keys = process_semantics.get("process_keys", [])

        if not event_time or not process_keys:
            return None

        patterns = {}

        for key in process_keys:
            pattern = self._infer_pattern_for_key(
                table=table,
                key=key,
                event_time=event_time,
            )

            if pattern:
                patterns[key] = pattern

        if not patterns:
            return None

        return {
            "event_time": event_time,
            "patterns": patterns,
            "confidence": 0.7,
            "rationale": "Temporal event patterns inferred from process-key event sequences.",
        }

    def _infer_pattern_for_key(self, table, key, event_time):
        sequences = {}

        for row in table.row_samples:
            k = row.get(key)
            t = row.get(event_time)

            if k is None or t is None:
                continue

            try:
                ts = np.datetime64(t)
            except Exception:
                continue

            sequences.setdefault(k, []).append(ts)

        dense_sequences = [
            sorted(seq)
            for seq in sequences.values()
            if len(seq) >= 3
        ]

        if len(dense_sequences) < 3:
            return None

        intervals = []

        for seq in dense_sequences:
            for i in range(1, len(seq)):
                delta = (seq[i] - seq[i - 1]) / np.timedelta64(1, "D")
                if delta > 0:
                    intervals.append(float(delta))

        if len(intervals) < 10:
            return None

        mean_interval = float(np.mean(intervals))
        std_interval = float(np.std(intervals))

        cadence = "irregular"

        if abs(mean_interval - 1) < 0.5:
            cadence = "daily"
        elif abs(mean_interval - 7) < 2:
            cadence = "weekly"
        elif abs(mean_interval - 30) < 5:
            cadence = "monthly"
        elif abs(mean_interval - 365) < 30:
            cadence = "yearly"

        irregularity = (
            std_interval / mean_interval
            if mean_interval > 0
            else None
        )

        return {
            "process_key": key,
            "event_time": event_time,
            "sequence_count": len(dense_sequences),
            "interval_count": len(intervals),
            "expected_interval_days": round(mean_interval, 2),
            "interval_std_days": round(std_interval, 2),
            "cadence": cadence,
            "irregularity": round(irregularity, 3) if irregularity is not None else None,
            "irregularity_threshold_days": round(std_interval * 2, 2),
            "confidence": 0.7,
            "rationale": "Detected temporal cadence from repeated process-key events.",
        }