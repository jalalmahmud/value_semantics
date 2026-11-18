class InferenceRegistry:
    """
    Registry for semantic inference modules.
    """

    def __init__(self):
        self.modules = []

    def register(self, module):
        self.modules.append(module)

    def run(self, table, column, semantics):
        for module in self.modules:
            result = module.infer(table, column, semantics)

            if result is not None:
                semantics[module.name] = result

        return semantics
