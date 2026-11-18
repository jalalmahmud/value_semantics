class JoinSemanticsInferencer:
    """
    Converts database-level relational links into operational join semantics.

    Input:
      database_vsl["relational_links"]

    Output:
      database_vsl["join_semantics"]
    """

    def infer_database(self, database_vsl):
        relational_links = database_vsl.get("relational_links", [])
        join_semantics = []

        for link in relational_links:
            cardinality = link.get("cardinality")
            constraints = link.get("join_constraints", {})
            evidence = link.get("evidence", {})

            source_table = link.get("source_table")
            target_table = link.get("target_table")
            source_column = link.get("source_column")
            target_column = link.get("target_column")

            if not source_table or not target_table:
                continue

            join_key = source_column

            duplication_risk = constraints.get("duplication_risk", False)

            semantic = {
                "source_table": source_table,
                "target_table": target_table,
                "source_column": source_column,
                "target_column": target_column,
                "join_key": join_key,
                "cardinality": cardinality,
                "duplication_risk": duplication_risk,
                "safe_counting": self._safe_counting(
                    link=link,
                    cardinality=cardinality,
                    duplication_risk=duplication_risk,
                ),
                "aggregation_constraints": self._aggregation_constraints(
                    link=link,
                    cardinality=cardinality,
                    duplication_risk=duplication_risk,
                ),
                "planner_hints": self._planner_hints(
                    link=link,
                    cardinality=cardinality,
                    duplication_risk=duplication_risk,
                ),
                "confidence": link.get("confidence", 0.7),
                "evidence": evidence,
                "rationale": (
                    "Operational join semantics inferred from relational link "
                    "cardinality and duplication-risk evidence."
                ),
            }

            join_semantics.append(semantic)

        return {
            "join_semantics": join_semantics,
        }

    def _safe_counting(self, link, cardinality, duplication_risk):
        parent_table = (
            link.get("join_constraints", {})
            .get("parent_table")
        )

        target_column = link.get("target_column")

        if duplication_risk and parent_table and target_column:
            return {
                "strategy": "COUNT_DISTINCT_PARENT",
                "expression": f"COUNT(DISTINCT {parent_table}.{target_column})",
                "reason": (
                    "Join can duplicate parent rows; count parent entities "
                    "using DISTINCT."
                ),
            }

        if cardinality == "ONE_TO_ONE":
            return {
                "strategy": "COUNT_DIRECT",
                "expression": f"COUNT({link.get('target_table')}.{target_column})",
                "reason": "One-to-one join does not introduce multiplicity.",
            }

        return {
            "strategy": "CHECK_MULTIPLICITY",
            "expression": None,
            "reason": "Join multiplicity is uncertain; planner should verify aggregation scope.",
        }

    def _aggregation_constraints(self, link, cardinality, duplication_risk):
        constraints = {
            "requires_distinct_for_parent_counts": False,
            "parent_measure_duplication_risk": False,
            "child_measure_safe_to_sum": True,
            "requires_grouping_by_join_key": False,
        }

        if duplication_risk:
            constraints.update(
                {
                    "requires_distinct_for_parent_counts": True,
                    "parent_measure_duplication_risk": True,
                    "requires_grouping_by_join_key": True,
                }
            )

        if cardinality in {"MANY_TO_MANY"}:
            constraints.update(
                {
                    "requires_distinct_for_parent_counts": True,
                    "parent_measure_duplication_risk": True,
                    "child_measure_safe_to_sum": False,
                    "requires_grouping_by_join_key": True,
                }
            )

        return constraints

    def _planner_hints(self, link, cardinality, duplication_risk):
        source_table = link.get("source_table")
        target_table = link.get("target_table")
        source_column = link.get("source_column")
        target_column = link.get("target_column")

        hints = []

        hints.append(
            {
                "hint": "JOIN_ON_KEY",
                "expression": (
                    f"{source_table}.{source_column} = "
                    f"{target_table}.{target_column}"
                ),
            }
        )

        if duplication_risk:
            hints.append(
                {
                    "hint": "AVOID_PARENT_OVERCOUNT",
                    "recommended_action": "COUNT_DISTINCT_PARENT",
                    "reason": (
                        "The join may duplicate parent-side rows and inflate "
                        "counts or aggregations."
                    ),
                }
            )

        if cardinality == "MANY_TO_ONE":
            hints.append(
                {
                    "hint": "CHILD_TO_PARENT_LOOKUP",
                    "reason": (
                        "Each source row maps to at most one target entity; "
                        "joining parent attributes onto child rows is usually safe."
                    ),
                }
            )

        if cardinality == "ONE_TO_MANY":
            hints.append(
                {
                    "hint": "PARENT_TO_CHILD_EXPANSION",
                    "reason": (
                        "Joining from parent to child may expand rows; aggregate "
                        "child-side data before joining when counting parents."
                    ),
                }
            )

        return hints