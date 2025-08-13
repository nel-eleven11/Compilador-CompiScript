from antlr4 import *
from classes.types import *
from classes.symbols import *
from classes.symbol_table import SymbolTable
from CompiscriptVisitor import CompiscriptVisitor

class SemanticVisitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors = []
        
    def visitProgram(self, ctx):
        return self.visitChildren(ctx)
        
    def visitConstantDeclaration(self, ctx):
        const_name = ctx.Identifier().getText()
        
        # Obtener tipo (si tiene anotación)
        type_annotation = ctx.typeAnnotation()
        const_type = VOID_TYPE
        if type_annotation:
            type_str = type_annotation.type_().getText()
            const_type = get_type_from_string(type_str)
            
        # Crear símbolo de constante
        symbol = VariableSymbol(const_name, const_type, is_const=True)
        
        try:
            self.symbol_table.add_symbol(symbol)
            print(f"✅ Constante '{const_name}' declarada correctamente")
        except Exception as e:
            error_msg = f"❌ Línea {ctx.start.line}: {str(e)}"
            self.errors.append(error_msg)
            print(error_msg)
            
        return self.visitChildren(ctx)
        
    def visitVariableDeclaration(self, ctx):
        var_name = ctx.Identifier().getText()
        
        # Obtener tipo (si tiene anotación)
        type_annotation = ctx.typeAnnotation()
        var_type = VOID_TYPE
        if type_annotation:
            type_str = type_annotation.type_().getText()
            var_type = get_type_from_string(type_str)
            
        # Crear símbolo de variable
        symbol = VariableSymbol(var_name, var_type, is_const=False)
        
        try:
            self.symbol_table.add_symbol(symbol)
            print(f"✅ Variable '{var_name}' declarada correctamente")
        except Exception as e:
            error_msg = f"❌ Línea {ctx.start.line}: {str(e)}"
            self.errors.append(error_msg)
            print(error_msg)
            
        return self.visitChildren(ctx)