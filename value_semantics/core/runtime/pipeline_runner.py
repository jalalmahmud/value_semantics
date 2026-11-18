from value_semantics.core.runtime.context import InferenceContext


class PipelineRunner:
    def __init__(self, modules):
        self.modules = modules

    def run_column(self, table, column):
        context = InferenceContext(table=table, column=column)

        for module in self.modules:
            if not self._requirements_satisfied(module, context):
                continue

            result = module.infer(context)

            if result is not None:
                context.set(module.name, result)

        return context.semantics

    def _requirements_satisfied(self, module, context):
        for requirement in getattr(module, "requires", []):
            if context.get(requirement) is None:
                return False
        return True