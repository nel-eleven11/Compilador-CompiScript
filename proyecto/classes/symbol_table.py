from .symbols import *
from .scope import *

class SymbolTable:
    def __init__(self):
        self.scopes = [Scope(0, "global")]
        self.current_scope = 0
        
    def enter_scope(self, scope_type="block"):
        self.current_scope += 1
        self.scopes.append(Scope(self.current_scope, scope_type))
        
    def exit_scope(self):
        if self.current_scope > 0:
            discarded = self.scopes.pop()
            self.current_scope -= 1
            return discarded
        raise Exception("Cannot exit global scope")
        
    def add_symbol(self, symbol):
        self.scopes[-1].add(symbol)
        
    def lookup(self, name, current_scope_only=False):
        """Busca un símbolo, opcionalmente solo en el ámbito actual"""
        if current_scope_only:
            return self.scopes[-1].lookup(name)
            
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