from value_semantics.core.runtime.pipeline_runner import PipelineRunner
from value_semantics.inference.value_type import ValueTypeInferencer
from value_semantics.inference.value_axis import ValueAxisInferencer
from value_semantics.inference.quantitative import QuantitativeInferencer
from value_semantics.inference.semantic_role import SemanticRoleInferencer
from value_semantics.inference.semantic_links import SemanticLinkInferencer
from value_semantics.consolidation.semantic_consolidator import SemanticConsolidator
from value_semantics.inference.process_semantics import ProcessSemanticsInferencer
from value_semantics.consolidation.conditional_distributions import ConditionalDistributionInferencer
from value_semantics.inference.process_patterns import ProcessPatternInferencer
from value_semantics.inference.process_operators import ProcessOperatorInferencer
from value_semantics.inference.measure_relationships import MeasureRelationshipInferencer
from value_semantics.consolidation.process_roles import ProcessRoleAssigner
from value_semantics.inference.interpretive_semantics import InterpretiveSemanticsInferencer
from value_semantics.inference.query_constraints import QueryConstraintInferencer
from value_semantics.inference.process_trends import ProcessTrendInferencer

class ValueSemanticsEngine:
    def __init__(self, modules=None):
        self.modules = modules or [
            ValueTypeInferencer(),
            InterpretiveSemanticsInferencer(),
            ValueAxisInferencer(),
            QuantitativeInferencer(),
            SemanticRoleInferencer(),
        ]
        self.runner = PipelineRunner(self.modules)
        self.semantic_link_inferencer = SemanticLinkInferencer()
        self.consolidator = SemanticConsolidator()
        self.process_semantics_inferencer = ProcessSemanticsInferencer()
        self.conditional_distribution_inferencer = ConditionalDistributionInferencer()
        self.process_pattern_inferencer = ProcessPatternInferencer()
        self.process_operator_inferencer = ProcessOperatorInferencer()
        self.measure_relationship_inferencer = MeasureRelationshipInferencer()
        self.process_role_assigner = ProcessRoleAssigner()
        self.query_constraint_inferencer = QueryConstraintInferencer()
        self.process_trend_inferencer = ProcessTrendInferencer()

    def infer_table(self, table):
        results = {
            "table": table.table_name,
            "columns": {},
            "semantics": {},
        }

        for column in table.columns:
            results["columns"][column.name] = {
                "declared_type": column.declared_type,
                "sample_values": column.stats.sample_values[:5],
                "stats": {
                    "row_count": column.stats.row_count,
                    "distinct_count": column.stats.distinct_count,
                    "null_count": column.stats.null_count,
                    "null_fraction": (
                        column.stats.null_count / column.stats.row_count
                        if column.stats.row_count
                        else None
                    ),
                },
            }
            

            results["semantics"][column.name] = self.runner.run_column(
                table=table,
                column=column,
            )

        measure_relationships = self.measure_relationship_inferencer.infer_table(
            table=table,
            column_semantics=results["semantics"],
        )

        if measure_relationships:
            for col_name, relationship in measure_relationships.items():
                if col_name not in results["semantics"]:
                    continue

                qvst = results["semantics"][col_name].get("quantitative_vst", {})
                qvst.update(relationship)
                results["semantics"][col_name]["quantitative_vst"] = qvst
        
        links = self.semantic_link_inferencer.infer_table(
            table=table,
            column_semantics=results["semantics"],
        )

        if links:
            results["table_semantics"] = {
                "semantic_links": links,
            }

        results = self.consolidator.consolidate(results)

        results = self.conditional_distribution_inferencer.infer(
           results=results,
           table=table,
        )
        
        process_semantics = self.process_semantics_inferencer.infer_table(
            table=table,
            column_semantics=results["semantics"],
        )

        if process_semantics:
            results.setdefault("table_semantics", {})
            results["table_semantics"]["process_semantics"] = process_semantics

            process_patterns = self.process_pattern_inferencer.infer_table(
                table=table,
                process_semantics=process_semantics,
            )

            if process_patterns:
                results["table_semantics"]["process_patterns"] = process_patterns

            process_operator_semantics = self.process_operator_inferencer.infer_table(
                table=table,
                process_semantics=process_semantics,
                process_patterns=process_patterns,
            )

            if process_operator_semantics:
                results["table_semantics"]["process_operator_semantics"] = (
                    process_operator_semantics
                )

            process_trends = self.process_trend_inferencer.infer_table(
                table=table,
                process_semantics=process_semantics,
            )

            if process_trends:
                results["table_semantics"]["process_trends"] = process_trends
                
            results = self.process_role_assigner.assign(results)

        for col, sem in results["semantics"].items():
            qc = self.query_constraint_inferencer.infer(sem)

            if qc:
                sem["query_constraints"] = qc
        return results