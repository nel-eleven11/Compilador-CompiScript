class Scope:
    def __init__(self, scope_level=0):
        self.symbols = {}
        self.scope_level = scope_level
        
    def add(self, symbol):
        if symbol.name in self.symbols:
            raise Exception(f"Symbol '{symbol.name}' already exists in this scope")
        self.symbols[symbol.name] = symbol
        
    def lookup(self, name):
        return self.symbols.get(name)

class SymbolTable:
    def __init__(self):
        self.scopes = [Scope(0)]  # Ámbito global inicial
        self.current_scope = 0
        
    def enter_scope(self):
        """Crea un nuevo ámbito anidado"""
        self.current_scope += 1
        self.scopes.append(Scope(self.current_scope))
        
    def exit_scope(self):
        """Elimina el ámbito más interno"""
        if self.current_scope > 0:
            self.scopes.pop()
            self.current_scope -= 1
            
    def add_symbol(self, symbol):
        """Añade símbolo al ámbito actual"""
        self.scopes[self.current_scope].add(symbol)
        
    def lookup(self, name):
        """Busca símbolo desde el ámbito actual hacia afuera"""
        for scope in reversed(self.scopes):
            symbol = scope.lookup(name)
            if symbol is not None:
                return symbol
        return None