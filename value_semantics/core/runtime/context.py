class InferenceContext:
    def __init__(self, table, column=None, semantics=None):
        self.table = table
        self.column = column
        self.semantics = semantics or {}

    def get(self, key, default=None):
        return self.semantics.get(key, default)

    def set(self, key, value):
        self.semantics[key] = value