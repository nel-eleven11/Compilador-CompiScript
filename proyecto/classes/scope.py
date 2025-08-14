class Scope:
    def __init__(self, scope_level, scope_type="block"):
        self.symbols = {}
        self.scope_level = scope_level
        self.scope_type = scope_type  # 'global', 'function', 'class', 'block'
        
    def add(self, symbol):
        if symbol.name in self.symbols:
            raise Exception(f"Symbol '{symbol.name}' ya existe en el scope")
        symbol.scope_level = self.scope_level
        self.symbols[symbol.name] = symbol
        
    def lookup(self, name):
        return self.symbols.get(name)