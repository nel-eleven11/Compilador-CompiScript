from .types import Type

class Symbol:
    def __init__(self, name, type_, category):
        self.name = name
        self.type = type_  # Objeto Type
        self.category = category  # 'variable', 'function', etc.
        
    def __str__(self):
        return f"{self.category} {self.name}: {self.type}"

class VariableSymbol(Symbol):
    def __init__(self, name, type_, is_const=False):
        super().__init__(name, type_, "variable")
        self.is_const = is_const
        self.initialized = False