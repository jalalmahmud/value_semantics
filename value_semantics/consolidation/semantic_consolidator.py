class SemanticConsolidator:
    def consolidate(self, results):
        semantics = results.get("semantics", {})
        links = (
            results.get("table_semantics", {})
            .get("semantic_links", [])
        )

        if not links:
            return results

        # Promote sources of accepted SEGMENTS links
        segments_by_source = {}

        for link in links:
            if link.get("relationship") != "SEGMENTS":
                continue

            if link.get("validation_status") not in {"accepted", "provisional"}:
                continue

            if link.get("confidence", 0.0) < 0.65:
                continue

            source = link["source"]
            segments_by_source.setdefault(source, []).append(link)

        for source, source_links in segments_by_source.items():
            col_sem = semantics.get(source, {})
            old_role = col_sem.get("semantic_role", {})

            confidence = min(
                0.95,
                sum(l.get("confidence", 0.7) for l in source_links) / len(source_links),
            )

            col_sem["semantic_role"] = {
                "primary_role": "SEGMENTATION_DRIVER",
                "confidence": confidence,
                "role_arguments": {
                    "segments": [l["target"] for l in source_links],
                },
                "query_constraints": {
                    "can_group_by": True,
                    "can_filter_equality": True,
                    "can_compare_magnitude": False,
                },
                "justification": {
                    "source": "validated_semantic_links",
                    "previous_role": old_role.get("primary_role"),
                    "link_count": len(source_links),
                },
            }

            semantics[source] = col_sem

        results["semantics"] = semantics
        return results