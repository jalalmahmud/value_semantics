class SQLGroundingPlanner:
    """
    Converts inferred VSL metadata into SQL-planning hints.
    """

    def ground(self, question: str, vsl_metadata: dict) -> dict:
        question_lower = question.lower()

        hints = {
            "question": question,
            "grounding_hints": [],
        }

        semantics = vsl_metadata.get("semantics", {})

        for column_name, column_semantics in semantics.items():
            value_axis = column_semantics.get("value_axis")
            semantic_role = column_semantics.get("semantic_role", {})
            quantitative_vst = column_semantics.get("quantitative_vst", {})

            hints["grounding_hints"].extend(
                self._conditional_distribution_hints(
                    question_lower=question_lower,
                    column_name=column_name,
                    column_semantics=column_semantics,
                )
            )

            if semantic_role.get("primary_role") != "EVIDENCE":
                continue

            if value_axis and any(
                term in question_lower
                for term in [
                    "large",
                    "high",
                    "highest",
                    "unusually high",
                    "unusually large",
                ]
            ):
                hints["grounding_hints"].append(
                    {
                        "type": "comparative_grounding",
                        "column": column_name,
                        "direction": "high",
                        "threshold_strategy": "value_axis_extreme_region",
                        "threshold": value_axis.get("extreme_regions", {}).get("large"),
                        "recommended_predicate": f"{column_name} {value_axis.get('extreme_regions', {}).get('large')}",
                        "source": "value_axis",
                        "confidence": value_axis.get("confidence", 0.7),
                        "match_score": self._score_column_match(
                            question_lower, column_name
                        ),
                    }
                )

            if value_axis and any(
                term in question_lower
                for term in [
                    "small",
                    "low",
                    "lowest",
                    "unusually low",
                    "unusually small",
                ]
            ):
                hints["grounding_hints"].append(
                    {
                        "type": "comparative_grounding",
                        "column": column_name,
                        "direction": "low",
                        "threshold_strategy": "value_axis_extreme_region",
                        "threshold": value_axis.get("extreme_regions", {}).get("small"),
                        "recommended_predicate": f"{column_name} {value_axis.get('extreme_regions', {}).get('small')}",
                        "source": "value_axis",
                        "confidence": value_axis.get("confidence", 0.7),
                        "match_score": self._score_column_match(
                            question_lower, column_name
                        ),
                    }
                )

            if any(term in question_lower for term in ["rate", "risk", "per", "ratio"]):
                for candidate in quantitative_vst.get(
                    "derived_metric_candidates", []
                ):
                    hints["grounding_hints"].append(
                        {
                            "type": "derived_metric_grounding",
                            "column": column_name,
                            "metric_type": candidate.get("metric_type"),
                            "formula_template": candidate.get("formula_template"),
                            "denominator_candidates": candidate.get(
                                "denominator_candidates", []
                            ),
                            "preferred_denominator": candidate.get(
                                "preferred_denominator"
                            ),
                            "requires_query_context": candidate.get(
                                "requires_query_context", True
                            ),
                            "ambiguity": candidate.get("ambiguity", {}),
                            "source": "quantitative_vst",
                            "confidence": candidate.get("confidence", 0.6),
                            "match_score": self._score_column_match(
                                question_lower, column_name
                            ),
                        }
                    )

        hints["grounding_hints"] = sorted(
            hints["grounding_hints"],
            key=lambda h: (
                h.get("match_score", 0.0),
                h.get("confidence", 0.0),
            ),
            reverse=True,
        )

        return hints

    def _score_column_match(self, question_lower: str, column_name: str) -> float:
        column_lower = column_name.lower()
        score = 0.0

        if column_lower in question_lower:
            score += 0.4

        if (
            "loan" in question_lower
            and column_lower
            in {"amount", "principal", "principal_amount", "loan_amount"}
        ):
            score += 0.5

        if any(
            term in question_lower
            for term in ["large", "high", "unusually large", "unusually high"]
        ):
            if column_lower in {
                "amount",
                "balance",
                "principal",
                "principal_amount",
                "salary",
                "revenue",
                "cost",
                "price",
            }:
                score += 0.3

        if any(
            term in question_lower
            for term in ["duration", "term", "tenure", "period"]
        ):
            if column_lower in {"duration", "term", "months", "years"}:
                score += 0.5

        if any(term in question_lower for term in ["payment", "payments"]):
            if column_lower in {"payment", "payments", "installment"}:
                score += 0.5

        return score

        def _conditional_distribution_hints(
            self,
            question_lower: str,
            column_name: str,
            column_semantics: dict,
        ) -> list:
            hints = []

            cds = column_semantics.get("conditional_value_distribution", {})
            if not cds:
                return hints

            trigger_terms = ["given", "within", "by", "per", "for each", "conditioned"]

            if not any(term in question_lower for term in trigger_terms):
                return hints

            for group_attr, dist in cds.items():
                if group_attr.lower() not in question_lower and not any(
                    term in question_lower for term in ["given", "within", "by"]
                ):
                    continue

                profiles = dist.get("profiles", {})
                recommended_stat = dist.get("recommended_stat", "p99")

                hints.append(
                    {
                        "type": "conditional_comparative_grounding",
                        "column": column_name,
                        "group_attribute": group_attr,
                        "threshold_strategy": "conditional_distribution",
                        "recommended_stat": recommended_stat,
                        "profiles": profiles,
                        "source": "conditional_value_distribution",
                        "confidence": dist.get("confidence", 0.7),
                        "match_score": self._score_column_match(
                            question_lower,
                            column_name,
                        )
                        + 0.3,
                        "rationale": (
                            f"Use group-conditioned distribution of {column_name} "
                            f"within {group_attr} groups instead of global threshold."
                        ),
                    }
                )

            return hints