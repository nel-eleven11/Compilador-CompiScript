from .symbols import *
from .scope import *

# symbol_table.py
class SymbolTable:
    def __init__(self):
        self.scopes = []  # Pila de ámbitos activos
        self.all_scopes = []  # Todos los ámbitos creados
        self.next_scope_id = 0  # Contador para IDs únicos
        self._init_global_scope()
        
    def _init_global_scope(self):
        """Inicializa el ámbito global con ID 0"""
        global_scope = Scope(0, "global")
        self.scopes = [global_scope]
        self.all_scopes = [global_scope]
        self.next_scope_id = 1  # El próximo ID será 1
        
    def enter_scope(self, scope_type="block"):
        parent = self.scopes[-1] if self.scopes else None
        new_scope = Scope(self.next_scope_id, scope_type, parent)
        self.next_scope_id += 1  # Incrementa para el próximo ámbito
        
        self.scopes.append(new_scope)
        self.all_scopes.append(new_scope)
        
    def exit_scope(self):
        """Sale del ámbito actual (excepto global)"""
        if len(self.scopes) > 1:  # No salir del ámbito global
            discarded = self.scopes.pop()
            return discarded
        return None
        
    def add_symbol(self, symbol):
        self.scopes[-1].add(symbol)
        
    # symbol_table.py
    def lookup(self, name, current_scope_only=False):
        """Busca un símbolo, opcionalmente solo en el ámbito actual"""
        # Buscar primero en el ámbito actual
        if current_scope_only:
            return self.scopes[-1].lookup(name)
        
        # Buscar en todos los ámbitos activos (desde el más interno hacia afuera)
        for scope in reversed(self.scopes):
            symbol = scope.lookup(name)
            if symbol is not None:
                return symbol
        return None
        
    def lookup_in_class(self, class_name, member_name):
        """Busca un miembro específico en una clase"""
        class_symbol = self.lookup(class_name)
        if not class_symbol or not isinstance(class_symbol, ClassSymbol):
            return None
            
        # Busca en jerarquía de herencia
        current = class_symbol
        while current:
            if member_name in current.attributes:
                return current.attributes[member_name]
            if member_name in current.methods:
                return current.methods[member_name]
            current = current.parent_class
        return None
    
    #Verifica si un símbolo está declarado específicamente en el ámbito actual
    def is_declared_in_current_scope(self, name):
        return self.scopes[-1].lookup(name) is not None