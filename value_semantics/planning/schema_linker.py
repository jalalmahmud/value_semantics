import re


class VSLSchemaLinker:
    """
    Links an LLM intent frame to VSL-backed columns.

    This does not generate SQL.
    It returns ranked candidate columns for:
      - measure
      - grouping
      - temporal
      - process key
      - ordinal/filter columns
    """

    MEASURE_HINTS = {
        "amount": ["amount", "loan", "principal", "transaction", "payment", "withdrawal", "deposit"],
        "balance": ["balance", "account balance"],
        "duration": ["duration", "term", "period"],
        "payments": ["payment", "payments", "repayment", "installment"],
    }

    GROUP_HINTS = {
        "status": ["status", "state", "category", "class"],
        "type": ["type", "tier", "kind"],
        "district": ["district", "region", "area"],
    }

    def link(self, intent_frame, table_name, semantics, table_semantics=None):
        table_semantics = table_semantics or {}

        measure_phrase = intent_frame.get("measure_phrase") or ""
        grouping_phrase = intent_frame.get("grouping_phrase") or ""
        target_entity = intent_frame.get("target_entity") or ""
        comparison = intent_frame.get("comparison")
        aggregation = intent_frame.get("aggregation")
        temporal_intent = bool(intent_frame.get("temporal_intent"))
        persistence_intent = bool(intent_frame.get("persistence_intent"))

        candidates = {
            "measure_candidates": [],
            "group_candidates": [],
            "ordinal_candidates": [],
            "time_candidates": [],
            "process_key_candidates": [],
            "state_variable_candidates": [],
        }

        for column, sem in semantics.items():
            score_context = {
                "measure_phrase": measure_phrase,
                "grouping_phrase": grouping_phrase,
                "target_entity": target_entity,
                "comparison": comparison,
                "aggregation": aggregation,
                "temporal_intent": temporal_intent,
                "persistence_intent": persistence_intent,
                "all_semantics": semantics,
            }
            

            measure_score = self._score_measure(column, sem, score_context)
            if measure_score > 0:
                candidates["measure_candidates"].append(
                    self._candidate(table_name, column, sem, measure_score, "measure")
                )

            group_score = self._score_group(column, sem, score_context)
            if group_score > 0:
                candidates["group_candidates"].append(
                    self._candidate(table_name, column, sem, group_score, "group")
                )

            ordinal_score = self._score_ordinal(column, sem, score_context)
            if ordinal_score > 0:
                candidates["ordinal_candidates"].append(
                    self._candidate(table_name, column, sem, ordinal_score, "ordinal")
                )

            time_score = self._score_time(column, sem, score_context)
            if time_score > 0:
                candidates["time_candidates"].append(
                    self._candidate(table_name, column, sem, time_score, "time")
                )

            process_key_score = self._score_process_key(column, sem, score_context)
            if process_key_score > 0:
                candidates["process_key_candidates"].append(
                    self._candidate(table_name, column, sem, process_key_score, "process_key")
                )

            state_score = self._score_state_variable(column, sem, score_context)
            if state_score > 0:
                candidates["state_variable_candidates"].append(
                    self._candidate(table_name, column, sem, state_score, "state_variable")
                )

        for key in candidates:
            candidates[key] = sorted(
                candidates[key],
                key=lambda x: x["score"],
                reverse=True,
            )

        return candidates

    def _candidate(self, table, column, sem, score, role):
        return {
            "table": table,
            "column": column,
            "candidate_role": role,
            "score": round(score, 3),
            "semantic_type": sem.get("value_semantics", {}).get("semantic_type"),
            "semantic_role": sem.get("semantic_role", {}).get("primary_role"),
            "process_role": sem.get("process_vst_role", {}).get("role"),
            "qvst_role": sem.get("quantitative_vst", {}).get("role"),
            "axis_type": sem.get("value_axis", {}).get("axis_type"),
            "has_conditional_distribution": bool(
                sem.get("conditional_value_distribution")
            ),
        }

    def _score_measure(self, column, sem, ctx):
        score = 0.0
        value_sem = sem.get("value_semantics", {})
        qvst = sem.get("quantitative_vst", {})
        role = sem.get("semantic_role", {})
        axis = sem.get("value_axis", {})

        if value_sem.get("is_identifier"):
            return 0.0

        if value_sem.get("semantic_type") in {
            "INTEGER",
            "FLOAT",
            "NUMERIC_GENERAL",
            "CURRENCY_AMOUNT",
            "PERCENTAGE",
            "RATIO",
            "DURATION",
        }:
            score += 0.25

        if qvst:
            score += 0.25

        if role.get("primary_role") == "EVIDENCE":
            score += 0.15

        if axis and axis.get("axis_type") != "ORDINAL":
            score += 0.15

        score += self._phrase_match_score(
            column,
            ctx.get("measure_phrase", ""),
            self.MEASURE_HINTS,
        )

        if ctx.get("comparison") in {
            "high",
            "low",
            "unusual_high",
            "unusual_low",
        } and axis:
            score += 0.15

        if ctx.get("aggregation") in {"SUM", "AVG", "MAX", "MIN"} and qvst:
            score += 0.10

        return min(score, 1.0)

    def _score_group(self, column, sem, ctx):
        score = 0.0
        value_sem = sem.get("value_semantics", {})
        role = sem.get("semantic_role", {})

        if value_sem.get("is_identifier"):
            score += 0.15

        if value_sem.get("semantic_type") in {
            "ENUM_CATEGORY",
            "TEXT_CATEGORY",
            "LABEL",
            "STRING",
            "ID_NUMERIC",
            "ID_STRING",
        }:
            score += 0.25

        if role.get("primary_role") in {
            "SEGMENTATION_DRIVER",
            "IDENTIFIER",
        }:
            score += 0.35

        score += self._phrase_match_score(
            column,
            ctx.get("grouping_phrase", ""),
            self.GROUP_HINTS,
        )

        # If a measure has conditional distributions keyed by this column,
        # this column is likely a good group candidate.
        for _, candidate_sem in ctx.get("all_semantics", {}).items():
            cds = candidate_sem.get("conditional_value_distribution", {})
            if column in cds:
                score += 0.2

        return min(score, 1.0)

    def _score_ordinal(self, column, sem, ctx):
        axis = sem.get("value_axis", {})
        if axis.get("axis_type") != "ORDINAL":
            return 0.0

        score = 0.45

        meaning = axis.get("polarity", {}).get("meaning", "")
        text = " ".join(
            [
                ctx.get("measure_phrase", "") or "",
                ctx.get("grouping_phrase", "") or "",
                ctx.get("target_entity", "") or "",
            ]
        ).lower()

        if column.lower() in text:
            score += 0.25

        if meaning and meaning.lower() in text:
            score += 0.25

        if ctx.get("comparison") in {"high", "low"}:
            score += 0.15

        return min(score, 1.0)

    def _score_time(self, column, sem, ctx):
        value_sem = sem.get("value_semantics", {})
        process_role = sem.get("process_vst_role", {})

        score = 0.0

        if value_sem.get("semantic_type") in {"DATE", "DATETIME", "TIME"}:
            score += 0.4

        if process_role.get("role") == "EVENT_TIME":
            score += 0.5

        if ctx.get("temporal_intent"):
            score += 0.1

        return min(score, 1.0)

    def _score_process_key(self, column, sem, ctx):
        process_role = sem.get("process_vst_role", {})
        role = sem.get("semantic_role", {})

        score = 0.0

        if process_role.get("role") == "PROCESS_KEY":
            score += 0.7

        if role.get("primary_role") == "IDENTIFIER":
            score += 0.2

        if ctx.get("temporal_intent") or ctx.get("persistence_intent"):
            score += 0.1

        return min(score, 1.0)

    def _score_state_variable(self, column, sem, ctx):
        process_role = sem.get("process_vst_role", {})
        axis = sem.get("value_axis", {})

        score = 0.0

        if process_role.get("role") == "STATE_VARIABLE":
            score += 0.6

        if axis:
            score += 0.15

        score += self._phrase_match_score(
            column,
            ctx.get("measure_phrase", ""),
            self.MEASURE_HINTS,
        )

        if ctx.get("temporal_intent") or ctx.get("persistence_intent"):
            score += 0.15

        return min(score, 1.0)

    def _phrase_match_score(self, column, phrase, hints):
        phrase = (phrase or "").lower()
        col = column.lower()

        if not phrase:
            return 0.0

        if col in phrase:
            return 0.35

        tokens = set(re.findall(r"[a-zA-Z_]+", phrase))

        if col in tokens:
            return 0.3

        for canonical, terms in hints.items():
            if col == canonical and any(t in phrase for t in terms):
                return 0.3

        return 0.0