class ProcessRoleAssigner:
    def assign(self, results):
        table_semantics = results.get("table_semantics", {})
        process = table_semantics.get("process_semantics")

        if not process:
            return results

        semantics = results.get("semantics", {})

        event_key = process.get("event_key")
        event_time = process.get("event_time")
        process_keys = set(process.get("process_keys", []))
        event_measures = set(process.get("event_measures", []))

        for col, sem in semantics.items():
            role = None

            if col == event_key:
                role = {
                    "role": "EVENT_KEY",
                    "confidence": 0.9,
                    "rationale": "Unique identifier for event rows.",
                }

            elif col in process_keys:
                role = {
                    "role": "PROCESS_KEY",
                    "confidence": 0.9,
                    "rationale": "Repeated entity identifier across event rows.",
                }

            elif col == event_time:
                role = {
                    "role": "EVENT_TIME",
                    "confidence": 0.9,
                    "rationale": "Timestamp/date ordering events in the process.",
                }

            elif col in event_measures:
                qvst_role = sem.get("quantitative_vst", {}).get("role")

                role = {
                    "role": (
                        "STATE_VARIABLE"
                        if qvst_role == "STATE_MEASURE"
                        else "EVENT_MEASURE"
                    ),
                    "confidence": 0.85,
                    "rationale": "Quantitative attribute recorded on event rows.",
                }

            if role:
                sem["process_vst_role"] = role
                semantics[col] = sem

        results["semantics"] = semantics
        return results