import re
from datetime import date, datetime

from value_semantics.core.pipeline import InferenceModule


class ValueTypeInferencer(InferenceModule):
    name = "value_semantics"
    requires = []
    produces = ["value_semantics"]

    def infer(self, context):
        column = context.column
        samples = [v for v in column.stats.sample_values if v is not None]
        name = column.name.lower()
        declared_type = (column.declared_type or "").lower()

        if not samples:
            return self._result("UNKNOWN", confidence=0.0)

        # Identifier rules
        if self._looks_like_identifier_name(name):
            if self._all_int_like(samples):
                return self._result(
                    "ID_NUMERIC",
                    is_identifier=True,
                    confidence=0.95,
                    rationale="Column name and numeric values indicate identifier semantics.",
                )

            return self._result(
                "ID_STRING",
                is_identifier=True,
                confidence=0.9,
                rationale="Column name indicates identifier semantics.",
            )

        # Native Python / pandas date objects
        if all(isinstance(v, datetime) for v in samples):
            return self._result(
                "DATETIME",
                temporal={"is_datetime": True, "granularity": "timestamp"},
                confidence=0.95,
                rationale="Values are datetime objects.",
            )

        if all(isinstance(v, date) for v in samples):
            return self._result(
                "DATE",
                temporal={"is_date": True, "granularity": "day"},
                confidence=0.95,
                rationale="Values are date objects.",
            )

        # Declared type hints
        if "date" in declared_type and "time" in declared_type:
            return self._result(
                "DATETIME",
                temporal={"is_datetime": True, "granularity": "timestamp"},
                confidence=0.9,
                rationale="Declared type indicates datetime.",
            )

        if "date" in declared_type:
            return self._result(
                "DATE",
                temporal={"is_date": True, "granularity": "day"},
                confidence=0.9,
                rationale="Declared type indicates date.",
            )

        first = samples[0]

        if isinstance(first, bool):
            return self._result("BOOLEAN", confidence=0.95)

        # String-pattern detection
        if isinstance(first, str):
            string_result = self._infer_string_type(column, samples, name)
            if string_result:
                return string_result

        # Numeric detection
        if self._all_int_like(samples):
            numeric = self._numeric_payload(samples, is_discrete=True)

            if self._looks_like_year(name, samples):
                return self._result(
                    "YEAR",
                    numeric=numeric,
                    temporal={"is_date": False, "granularity": "year"},
                    confidence=0.85,
                    rationale="Integer values and column name suggest year semantics.",
                )

            return self._result(
                "INTEGER",
                numeric=numeric,
                confidence=0.9,
            )

        if self._all_float_like(samples):
            numeric = self._numeric_payload(samples, is_discrete=False)

            if self._looks_like_ratio(samples, name):
                return self._result(
                    "RATIO",
                    numeric=numeric,
                    confidence=0.85,
                    rationale="Values fall in a normalized ratio-like range.",
                )

            return self._result(
                "FLOAT",
                numeric=numeric,
                confidence=0.9,
            )

        return self._result("UNKNOWN", confidence=0.3)

    def _infer_string_type(self, column, samples, name):
        distinct = column.stats.distinct_count
        row_count = column.stats.row_count

        if self._all_date_like_strings(samples):
            return self._result(
                "DATE",
                temporal={"is_date": True, "granularity": "day"},
                confidence=0.9,
                rationale="String values match date-like patterns.",
            )

        if self._all_datetime_like_strings(samples):
            return self._result(
                "DATETIME",
                temporal={"is_datetime": True, "granularity": "timestamp"},
                confidence=0.9,
                rationale="String values match datetime-like patterns.",
            )

        if self._all_email_like(samples):
            return self._result(
                "EMAIL",
                confidence=0.95,
                rationale="String values match email pattern.",
            )

        if self._all_url_like(samples):
            return self._result(
                "URL",
                confidence=0.95,
                rationale="String values match URL pattern.",
            )

        if self._all_currency_like(samples) or any(
            term in name for term in ["amount", "price", "cost", "salary", "revenue", "balance"]
        ):
            parsed = self._parse_numeric_strings(samples)
            if parsed:
                return self._result(
                    "CURRENCY_AMOUNT",
                    numeric=self._numeric_payload(parsed, is_discrete=False),
                    confidence=0.8,
                    rationale="Column name or values suggest monetary amount.",
                )

        if self._all_percentage_like(samples) or any(term in name for term in ["percent", "percentage", "pct"]):
            parsed = self._parse_percentage_strings(samples)
            if parsed:
                return self._result(
                    "PERCENTAGE",
                    numeric=self._numeric_payload(parsed, is_discrete=False),
                    confidence=0.85,
                    rationale="Values or column name suggest percentage semantics.",
                )

        if distinct is not None and row_count:
            categorical_threshold = min(50, max(20, int(row_count * 0.2)))

            if distinct <= categorical_threshold:
                return self._result(
                    "ENUM_CATEGORY",
                    is_categorical=True,
                    confidence=0.85,
                    rationale="Low-cardinality string values indicate categorical semantics.",
                )

        if self._looks_like_free_text(samples):
            return self._result(
                "FREE_TEXT",
                is_free_text=True,
                confidence=0.8,
                rationale="Values look like unconstrained natural language text.",
            )

        return self._result(
            "STRING",
            confidence=0.7,
            rationale="String values without stronger detected semantics.",
        )

    def _result(
        self,
        semantic_type,
        *,
        is_identifier=False,
        is_categorical=False,
        is_free_text=False,
        numeric=None,
        temporal=None,
        confidence=0.5,
        rationale=None,
    ):
        return {
            "semantic_type": semantic_type,
            "is_identifier": is_identifier,
            "is_categorical": is_categorical,
            "is_free_text": is_free_text,
            "numeric": numeric or {
                "is_numeric": False,
                "is_continuous": False,
                "is_discrete": False,
                "min": None,
                "max": None,
            },
            "temporal": temporal or {
                "is_date": False,
                "is_datetime": False,
                "is_duration": False,
                "granularity": None,
            },
            "confidence": confidence,
            "rationale": rationale or f"Inferred {semantic_type} from value patterns.",
        }

    def _numeric_payload(self, values, is_discrete):
        nums = [float(v) for v in values]
        return {
            "is_numeric": True,
            "is_continuous": not is_discrete,
            "is_discrete": is_discrete,
            "min": min(nums),
            "max": max(nums),
        }

    def _looks_like_identifier_name(self, name):
        return (
            name == "id"
            or name.endswith("_id")
            or name.endswith("id")
            or name in {"account_id", "client_id", "loan_id", "trans_id", "card_id"}
        )

    def _all_int_like(self, samples):
        try:
            return all(float(v).is_integer() for v in samples)
        except Exception:
            return False

    def _all_float_like(self, samples):
        try:
            [float(v) for v in samples]
            return True
        except Exception:
            return False

    def _looks_like_year(self, name, samples):
        if "year" not in name:
            return False
        try:
            years = [int(v) for v in samples]
            return all(1800 <= y <= 2200 for y in years)
        except Exception:
            return False

    def _looks_like_ratio(self, samples, name):
        if any(term in name for term in ["ratio", "rate", "risk"]):
            return True

        try:
            vals = [float(v) for v in samples]
            return vals and min(vals) >= 0 and max(vals) <= 1
        except Exception:
            return False

    def _all_date_like_strings(self, samples):
        date_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",
            r"^\d{2}/\d{2}/\d{4}$",
            r"^\d{8}$",
        ]
        return all(
            any(re.match(pattern, str(v)) for pattern in date_patterns)
            for v in samples
        )

    def _all_datetime_like_strings(self, samples):
        patterns = [
            r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}",
            r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",
        ]
        return all(
            any(re.match(pattern, str(v)) for pattern in patterns)
            for v in samples
        )

    def _all_email_like(self, samples):
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        return all(re.match(pattern, str(v)) for v in samples)

    def _all_url_like(self, samples):
        return all(str(v).startswith(("http://", "https://")) for v in samples)

    def _all_currency_like(self, samples):
        pattern = r"^\$?\d+(,\d{3})*(\.\d+)?$"
        return all(re.match(pattern, str(v)) for v in samples)

    def _all_percentage_like(self, samples):
        pattern = r"^\d+(\.\d+)?%$"
        return all(re.match(pattern, str(v)) for v in samples)

    def _parse_numeric_strings(self, samples):
        parsed = []
        for v in samples:
            try:
                parsed.append(float(str(v).replace("$", "").replace(",", "")))
            except Exception:
                return []
        return parsed

    def _parse_percentage_strings(self, samples):
        parsed = []
        for v in samples:
            try:
                parsed.append(float(str(v).replace("%", "")))
            except Exception:
                return []
        return parsed

    def _looks_like_free_text(self, samples):
        strings = [str(v) for v in samples]
        avg_len = sum(len(s) for s in strings) / len(strings)
        avg_tokens = sum(len(s.split()) for s in strings) / len(strings)
        return avg_len > 40 or avg_tokens > 6