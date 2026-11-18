class InferenceModule:
    """
    Base class for all semantic inference modules.
    """

    name = "base"

    def infer(self, table, column, semantics):
        raise NotImplementedError