from value_semantics.core.pipeline import InferenceModule


class SemanticRoleInferencer(InferenceModule):
    name = "semantic_role"
    requires = ["value_semantics"]
    produces = ["semantic_role"]

    def infer(self, context):
        column = context.column
        value_semantics = context.get("value_semantics") or {}
        quantitative_vst = context.get("quantitative_vst") or {}

        if value_semantics.get("is_identifier"):
            return {
                "primary_role": "IDENTIFIER",
                "confidence": 0.95,
                "role_arguments": {},
                "query_constraints": {
                    "can_select": True,
                    "can_join": True,
                    "can_group_by": False,
                    "can_filter_equality": True,
                    "can_order_as_measure": False,
                    "can_aggregate": False,
                },
                "justification": {"rule": "identifier_flag"},
            }

        semantic_type = value_semantics.get("semantic_type")
        name = column.name.lower()

        if semantic_type in {"DATE", "DATETIME", "TIME"}:
            return {
                "primary_role": "EVENT_TIME",
                "confidence": 0.7,
                "role_arguments": {},
                "query_constraints": {
                    "can_filter_range": True,
                    "can_bucket_time": True,
                    "can_order": True,
                },
                "justification": {"type_prior": semantic_type},
            }

        if quantitative_vst:
            return {
                "primary_role": "EVIDENCE",
                "confidence": quantitative_vst.get("confidence", 0.7),
                "role_arguments": {"quantitative_role": quantitative_vst.get("role")},
                "query_constraints": {
                    "can_aggregate": True,
                    "can_compare": True,
                    "can_order_as_measure": True,
                },
                "justification": {"source": "quantitative_vst"},
            }

        if semantic_type in {"ENUM_CATEGORY", "TEXT_CATEGORY", "LABEL"}:
            return {
                "primary_role": "DESCRIPTIVE",
                "confidence": 0.55,
                "role_arguments": {},
                "query_constraints": {
                    "can_group_by": True,
                    "can_filter_equality": True,
                    "can_compare_magnitude": False,
                },
                "justification": {"type_prior": semantic_type},
            }

        return {
            "primary_role": "DESCRIPTIVE",
            "confidence": 0.4,
            "role_arguments": {},
            "query_constraints": {},
            "justification": {"reason": "no stronger semantic role detected"},
        }