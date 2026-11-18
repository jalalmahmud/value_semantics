#!/usr/bin/env python3
"""
Experimental v2 value-type inferencer (SEPARATE version; the frozen value_semantics/ is untouched).

Subclasses the frozen ValueTypeInferencer and improves inference from evidence:
  Stage 1 (currency): require an explicit currency symbol ($/€/£/¥, US or EU grouping). The inherited
      money-name path (amount/price/cost/salary/revenue/balance) still applies, so symbol-less but
      money-named numeric columns remain currency; bare numbers with no symbol and no money name are
      NOT asserted as currency (the engine abstains to a plain numeric/code instead).
  Stage 2 (codes + coordinates), applied as evidence before the frozen dispatch:
      - Numeric/string CODES (zip, postal, fips, ssn, phone, *_code/_no/_cd, 'code' token) are
        categorical and NOT additive measures. General, name-based (not keyed to any benchmark).
      - latitude/longitude recognized only with BOTH a coordinate name AND an in-range value span
        (lat in [-90,90], lon in [-180,180]) -- so an arbitrary bounded decimal is NOT a coordinate.
Everything else defers to the frozen engine unchanged.

`make_engine_v2()` returns a ValueSemanticsEngine with this inferencer swapped in via the engine's
existing `modules=` parameter; all other modules are the frozen ones.
"""
import re
from value_semantics.inference.value_type import ValueTypeInferencer


class ValueTypeInferencerV2(ValueTypeInferencer):

    # ---- Stage 1: currency requires an explicit symbol -------------------------------------------
    def _all_currency_like(self, samples):
        pat = r"^[$€£¥]\s?\d{1,3}([.,]\d{3})*([.,]\d{1,2})?$"
        return bool(samples) and all(re.match(pat, str(v).strip()) for v in samples)

    # ---- Stage 2: codes + coordinates pre-empt the frozen dispatch; Stage 3: enrich dates --------
    def infer(self, context):
        column = context.column
        samples = [v for v in column.stats.sample_values if v is not None]
        name = (column.name or "").lower()
        if samples:
            coord = self._coordinate_kind(name, samples)
            if coord:
                return self._result(
                    coord,
                    numeric=self._numeric_payload(samples, is_discrete=False),
                    confidence=0.85,
                    rationale="Column name and in-range values indicate a geographic coordinate; "
                              "not an additive measure.",
                )
            # Only intervene on NUMERIC-valued codes -- that is where the frozen engine mistypes a
            # code as an additive measure/currency. Textual codes are already handled categorically
            # by the frozen engine (keep its segmentation role), so we don't override those.
            if (self._looks_like_code_name(name) and not self._looks_like_identifier_name(name)
                    and self._all_int_like(samples)):
                r = self._result(
                    "CATEGORICAL_CODE",
                    is_categorical=True,
                    confidence=0.8,
                    rationale="Numeric-valued coded column (name indicates a code); groupable but not "
                              "an additive measure.",
                )
                r["code_kind"] = self._code_kind(name)   # 'geographic' vs 'generic' -- not every code is geo
                return r
            # Time-of-day strings ("H:MM"/"HH:MM[:SS]") in a time-named column: event time-of-day,
            # bucketable into hour/period, NOT an additive measure. The frozen engine leaves these as
            # a plain STRING (so a "time slot"/"hour of day" task loses the temporal semantics).
            if self._looks_like_time_name(name) and self._all_time_of_day(samples):
                r = self._result(
                    "TIME_OF_DAY",
                    confidence=0.85,
                    rationale="Time-of-day values (HH:MM); represent event time-of-day and support "
                              "bucketing into hour/period. Not an additive measure; a trend or "
                              "sustained condition is task-dependent, not inferred from the time alone.",
                )
                r["temporal"] = {"supports_time_bucketing": True,
                                 "trend_requires_specification": True,
                                 "granularity": "time_of_day"}
                return r
        # Stage 3: for event-time columns, keep two assertions SEPARATE --
        #   (A) represents event time and supports grouping into time buckets  [asserted]
        #   (B) a trend/sustained condition is task-dependent                  [NOT inferred]
        res = super().infer(context)
        if isinstance(res, dict) and res.get("semantic_type") in {"DATE", "DATETIME"}:
            t = dict(res.get("temporal") or {})
            t["supports_time_bucketing"] = True
            t["trend_requires_specification"] = True
            res = {**res, "temporal": t}
            res["rationale"] = (res.get("rationale", "") +
                " Event time: supports grouping into time buckets; a trend or sustained condition is "
                "task-dependent (needs a supplied period, comparison, threshold, or clarification) and "
                "is not inferred from the date alone.")
        return res

    @staticmethod
    def _tokens(name):
        return {t for t in re.split(r"[^a-z0-9]+", name) if t}

    def _looks_like_code_name(self, name):
        toks = self._tokens(name)
        if toks & {"zip", "zipcode", "postal", "postcode", "code", "fips",
                   "ssn", "phone", "geoid", "msa", "cbsa", "ncesid"}:
            return True
        return name.endswith("_no") or name.endswith("_code") or name.endswith("_cd")

    def _code_kind(self, name):
        toks = self._tokens(name)
        geo = {"zip", "zipcode", "postal", "postcode", "fips", "geoid", "msa", "cbsa", "tract"}
        return "geographic" if (toks & geo) else "generic"

    def _looks_like_time_name(self, name):
        return bool(self._tokens(name) & {"time", "hour", "timestamp"})

    def _all_time_of_day(self, samples):
        pat = r"^\d{1,2}:\d{2}(:\d{2})?$"
        return bool(samples) and all(re.match(pat, str(v).strip()) for v in samples)

    def _coordinate_kind(self, name, samples):
        if not self._all_float_like(samples):
            return None
        vals = [float(v) for v in samples]
        lo, hi = min(vals), max(vals)
        toks = self._tokens(name)
        if (toks & {"lat", "latitude"}) and lo >= -90 and hi <= 90:
            return "GEOGRAPHIC_LATITUDE"
        if (toks & {"lon", "lng", "long", "longitude"}) and lo >= -180 and hi <= 180:
            return "GEOGRAPHIC_LONGITUDE"
        return None


from value_semantics.inference.semantic_role import SemanticRoleInferencer


class SemanticRoleInferencerV2(SemanticRoleInferencer):
    """Give numeric CATEGORICAL_CODE columns explicit groupable, non-additive planner operations
    (so ZIP is groupable without being an additive quantity), carrying a geographic/generic marker."""

    def infer(self, context):
        vs = context.get("value_semantics") or {}
        if vs.get("semantic_type") == "TIME_OF_DAY":
            # event time-of-day: bucketable (hour/period), range-filterable, orderable; NOT additive.
            return {
                "primary_role": "EVENT_TIME",
                "confidence": 0.85,
                "role_arguments": {"granularity": "time_of_day"},
                "query_constraints": {
                    "can_select": True,
                    "can_filter_range": True,
                    "can_bucket_time": True,
                    "can_order": True,
                    "can_aggregate": False,
                    "can_order_as_measure": False,
                },
                "justification": {"rule": "time_of_day"},
            }
        if vs.get("semantic_type") == "CATEGORICAL_CODE":
            return {
                "primary_role": "SEGMENTATION_DRIVER",
                "confidence": 0.8,
                "role_arguments": {"code_kind": vs.get("code_kind", "generic")},
                "query_constraints": {
                    "can_select": True,
                    "can_group_by": True,
                    "can_filter_equality": True,
                    "can_aggregate": False,
                    "can_order_as_measure": False,
                    "can_compare_magnitude": False,
                },
                "justification": {"rule": "categorical_code"},
            }
        if vs.get("semantic_type") in ("GEOGRAPHIC_LATITUDE", "GEOGRAPHIC_LONGITUDE"):
            # a spatial coordinate: usable for selection and range/bounding-box filtering and spatial
            # proximity, but NOT an additive magnitude (no SUM/AVG, no order-as-measure).
            return {
                "primary_role": "SPATIAL_COORDINATE",
                "confidence": 0.85,
                "role_arguments": {"axis": "lat" if "LAT" in vs["semantic_type"] else "lon"},
                "query_constraints": {
                    "can_select": True,
                    "can_filter_range": True,
                    "can_aggregate": False,
                    "can_order_as_measure": False,
                    "can_compare_magnitude": False,
                },
                "justification": {"rule": "geographic_coordinate"},
            }
        return super().infer(context)


def make_engine_v2():
    """A ValueSemanticsEngine with the v2 value-type + semantic-role inferencers; others frozen."""
    from value_semantics.engine import ValueSemanticsEngine
    from value_semantics.inference.interpretive_semantics import InterpretiveSemanticsInferencer
    from value_semantics.inference.value_axis import ValueAxisInferencer
    from value_semantics.inference.quantitative import QuantitativeInferencer
    return ValueSemanticsEngine(modules=[
        ValueTypeInferencerV2(),
        InterpretiveSemanticsInferencer(),
        ValueAxisInferencer(),
        QuantitativeInferencer(),
        SemanticRoleInferencerV2(),
    ])
