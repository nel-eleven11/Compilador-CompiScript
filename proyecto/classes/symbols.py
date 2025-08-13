from .types import Type

class Symbol:
    def __init__(self, name, type_, category, scope_level):
        self.name = name
        self.type = type_      # Objeto Type
        self.category = category  # 'variable', 'function', 'class'
        self.scope_level = scope_level
        self.line_number = -1  # errores
        
    def __str__(self):
        return f"{self.category} {self.name}: {self.type} (scope: {self.scope_level})"

class VariableSymbol(Symbol):
    def __init__(self, name, type_, scope_level, is_const=False):
        super().__init__(name, type_, "variable", scope_level)
        self.is_const = is_const
        self.initialized = False
        self.offset = 0  # para el futuro, generacion de codigo

class FunctionSymbol(Symbol):
    def __init__(self, name, return_type, scope_level, params=None):
        super().__init__(name, return_type, "function", scope_level)
        self.return_type = return_type
        self.parameters = params or []
        self.locals = []
        self.return_statements = []
        
    def __str__(self):
        params = ", ".join([f"{p.name}: {p.type}" for p in self.parameters])
        return f"function {self.name}({params}): {self.return_type}"
        
    def add_parameter(self, param):
        self.parameters.append(param)
        
    def add_local(self, local):
        self.locals.append(local)

class ClassSymbol(Symbol):
    def __init__(self, name, scope_level, parent_class=None):
        super().__init__(name, None, "class", scope_level)
        self.parent_class = parent_class
        self.attributes = {}
        self.methods = {}
        
    def add_attribute(self, attr):
        self.attributes[attr.name] = attr
        
    def add_method(self, method):
        self.methods[method.name] = method