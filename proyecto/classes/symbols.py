from .types import Type

class Symbol:
    def __init__(self, name, type_, category, scope_id):
        self.name = name
        self.type = type_      # Objeto Type
        self.category = category  # 'variable', 'function', 'class'
        self.scope_id = scope_id  # ID único del ambito
        self.line_number = -1  # Para reportes de errores
        
    def __str__(self):
        type_name = self.type.name if self.type else '?'
        return f"{self.category.capitalize()} {self.name}: {type_name}, scope: {self.scope_id}"

class VariableSymbol(Symbol):
    def __init__(self, name, type_, scope_id, is_const=False, is_type_inferred=False):
        super().__init__(name, type_, "variable", scope_id)
        self.is_const = is_const
        self.initialized = False
        self.offset = 0
        self.is_nullable = True
        self.is_type_inferred = is_type_inferred  # Nuevo atributo
    
    def __str__(self):
        const_str = " (const)" if self.is_const else ""
        type_str = f"Type: {self.type.name}" if self.type else 'Type: ?'
        inferred_str = " (inferred)" if self.is_type_inferred else ""
        return f"Var: {self.name}{const_str}{inferred_str} | {type_str} | Scope: {self.scope_id}"

class FunctionSymbol(Symbol):
    def __init__(self, name, return_type, scope_id, params=None):
        super().__init__(name, return_type, "function", scope_id)
        self.return_type = return_type
        self.parameters = params or []
        self.locals = []
        self.return_statements = []
        
    def __str__(self):
        params_str = ", ".join([f"{p.name}: {p.type.name}" for p in self.parameters])
        return_type_name = self.return_type.name if self.return_type else 'void'
        
        return (f"Func: {self.name}({params_str}) -> {return_type_name} | Scope: {self.scope_id} | "
                f"Params: {len(self.parameters)} | Locals: {len(self.locals)}")
        
    def add_parameter(self, param):
        self.parameters.append(param)
        
    def add_local(self, local):
        self.locals.append(local)

class ClassSymbol(Symbol):
    def __init__(self, name, scope_id, parent_class=None):
        super().__init__(name, None, "class", scope_id)
        self.parent_class = parent_class
        self.attributes = {}
        self.methods = {}
        
    def __str__(self):
        
        parent_str = f" extends {self.parent_class.name}" if self.parent_class else ""
        header = f"Class: {self.name}{parent_str} | Scope: {self.scope_id}"
        
        attr_list = [f"  - {attr}" for attr in self.attributes.values()]
        method_list = [f"  - {method}" for method in self.methods.values()]
        
        attributes_str = "\n".join(attr_list) if attr_list else "  - (no attributes)"
        methods_str = "\n".join(method_list) if method_list else "  - (no methods)"
        
        return f"{header}\nAttributes:\n{attributes_str}\nMethods:\n{methods_str}"
        
    def add_attribute(self, attr):
        self.attributes[attr.name] = attr
        
    def add_method(self, method):
        self.methods[method.name] = method