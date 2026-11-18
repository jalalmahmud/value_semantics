import numpy as np


class ProcessTrendInferencer:
    name = "process_trends"

    def infer_table(self, table, process_semantics):
        if not process_semantics:
            return None

        event_time = process_semantics.get("event_time")
        process_keys = process_semantics.get("process_keys", [])
        event_measures = process_semantics.get("event_measures", [])

        if not event_time or not process_keys or not event_measures:
            return None

        trends = {}

        for key in process_keys:
            key_trends = {}

            for measure in event_measures:
                trend = self._infer_trend(
                    table=table,
                    process_key=key,
                    event_time=event_time,
                    measure=measure,
                )

                if trend:
                    key_trends[measure] = trend

            if key_trends:
                trends[key] = key_trends

        if not trends:
            return None

        return {
            "event_time": event_time,
            "process_keys": process_keys,
            "trends": trends,
            "confidence": 0.7,
            "rationale": "Temporal trends inferred from process-key ordered event measures.",
        }

    def _infer_trend(self, table, process_key, event_time, measure):
        sequences = {}

        for row in table.row_samples:
            k = row.get(process_key)
            t = row.get(event_time)
            v = row.get(measure)

            if k is None or t is None or v is None:
                continue

            try:
                ts = np.datetime64(t)
                value = float(v)
            except Exception:
                continue

            sequences.setdefault(k, []).append((ts, value))

        slopes = []
        volatilities = []
        sequence_count = 0

        for seq in sequences.values():
            seq = sorted(seq, key=lambda x: x[0])

            if len(seq) < 3:
                continue

            xs = np.array(
                [
                    float((t - seq[0][0]) / np.timedelta64(1, "D"))
                    for t, _ in seq
                ]
            )

            ys = np.array([v for _, v in seq])

            if len(set(xs)) < 2:
                continue

            slope = float(np.polyfit(xs, ys, 1)[0])
            mean_abs = float(np.mean(np.abs(ys))) or 1.0
            volatility = float(np.std(ys) / mean_abs)

            slopes.append(slope)
            volatilities.append(volatility)
            sequence_count += 1

        if sequence_count < 3:
            return None

        median_slope = float(np.median(slopes))
        avg_volatility = float(np.mean(volatilities))

        trend = "stable"

        if median_slope > 10:
            trend = "increasing"
        elif median_slope < -10:
            trend = "decreasing"

        if avg_volatility > 0.75:
            stability = "volatile"
        elif avg_volatility < 0.15:
            stability = "stable"
        else:
            stability = "moderately_variable"

        return {
            "measure": measure,
            "process_key": process_key,
            "trend": trend,
            "median_slope_per_day": round(median_slope, 4),
            "avg_volatility": round(avg_volatility, 4),
            "stability": stability,
            "sequence_count": sequence_count,
            "confidence": 0.7,
            "rationale": "Trend inferred by fitting per-process-key measure values over event time.",
        }