class Scope:
    def __init__(self, scope_id, scope_type="block", parent=None):
        self.symbols = {}
        self.scope_id = scope_id
        self.scope_type = scope_type
        self.parent = parent # referencia al padre
        
    def add(self, symbol):
        if symbol.name in self.symbols:
            raise Exception(f"Symbol '{symbol.name}' ya existe en el scope")
        symbol.scope_id = self.scope_id  # Usar scope_id 
        self.symbols[symbol.name] = symbol
        
    def lookup(self, name):
        return self.symbols.get(name)