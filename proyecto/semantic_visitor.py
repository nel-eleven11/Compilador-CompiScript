from antlr4 import *
from classes.types import *
from classes.symbols import *
from classes.symbol_table import SymbolTable
from CompiscriptVisitor import CompiscriptVisitor

class SemanticVisitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors = []
        self.current_function = None
        self.current_class = None
        
    # Helper methods
    def add_error(self, ctx, message):
        line = ctx.start.line if ctx else "unknown"
        self.errors.append(f"Error semántico. Línea {line}: {message}")
        #print(self.errors[-1])
        
    def get_type_from_ctx(self, type_ctx):
        if not type_ctx:
            return None
        type_str = type_ctx.getText()
        return get_type_from_string(type_str)
    
    # Visit methods
    def visitProgram(self, ctx):
        return self.visitChildren(ctx)
        
    def visitConstantDeclaration(self, ctx):
        const_name = ctx.Identifier().getText()
        const_type = self.get_type_from_ctx(ctx.typeAnnotation().type_() if ctx.typeAnnotation() else None)
        
        if not ctx.expression():
            self.add_error(ctx, f"Constante '{const_name}' debe ser inicializada")
            
        symbol = VariableSymbol(
            name=const_name,
            type_=const_type or VOID_TYPE,
            scope_level=self.symbol_table.current_scope,
            is_const=True
        )
        
        try:
            self.symbol_table.add_symbol(symbol)
            #print(f"Constante '{const_name}' registrada")
        except Exception as e:
            self.add_error(ctx, str(e))
            
        return self.visitChildren(ctx)
    
    def visitVariableDeclaration(self, ctx):
        var_name = ctx.Identifier().getText()
        var_type = self.get_type_from_ctx(ctx.typeAnnotation().type_() if ctx.typeAnnotation() else None)
        
        symbol = VariableSymbol(
            name=var_name,
            type_=var_type or VOID_TYPE,
            scope_level=self.symbol_table.current_scope,
            is_const=False
        )
        
        try:
            self.symbol_table.add_symbol(symbol)
            #print(f"Variable '{var_name}' registrada")
        except Exception as e:
            self.add_error(ctx, str(e))
            
        return self.visitChildren(ctx)
    
    def visitFunctionDeclaration(self, ctx):
        func_name = ctx.Identifier().getText()
        return_type = self.get_type_from_ctx(ctx.type_()) if ctx.type_() else VOID_TYPE
        
        if return_type == VOID_TYPE and ctx.type_():
            self.add_error(ctx, f"Uso explícito de 'void' no permitido en funciones")
            return
    
        func_symbol = FunctionSymbol(
            name=func_name,
            return_type=return_type,
            scope_level=self.symbol_table.current_scope
        )
        
        # Registrar función en ámbito padre
        try:
            self.symbol_table.add_symbol(func_symbol)
        except Exception as e:
            self.add_error(ctx, str(e))
            return
            
        # Entrar en ámbito de función
        self.symbol_table.enter_scope("function")
        self.current_function = func_symbol
        
        # Procesar parámetros
        if ctx.parameters():
            for i, param_ctx in enumerate(ctx.parameters().parameter()):
                param_name = param_ctx.Identifier().getText()
                param_type = self.get_type_from_ctx(param_ctx.type_() if param_ctx.type_() else None)
                
                param_symbol = VariableSymbol(
                    name=param_name,
                    type_=param_type or VOID_TYPE,
                    scope_level=self.symbol_table.current_scope,
                    is_const=False
                )
                
                func_symbol.add_parameter(param_symbol)
                try:
                    self.symbol_table.add_symbol(param_symbol)
                except Exception as e:
                    self.add_error(param_ctx, str(e))
        
        # Procesar cuerpo
        self.visit(ctx.block())
        
        # Verificar retornos
        if return_type != VOID_TYPE and not func_symbol.return_statements:
            self.add_error(ctx, f"Función '{func_name}' debe retornar un valor")
            
        # Salir del ámbito
        self.symbol_table.exit_scope()
        self.current_function = None
        
        return None
    
    # En semantic_visitor.py
    def visitReturnStatement(self, ctx):
        if not self.current_function:
            self.add_error(ctx, "return fuera de función")
            return
            
        expr_type = self.visit(ctx.expression()) if ctx.expression() else VOID_TYPE
        
        if self.current_function.return_type == VOID_TYPE:
            if ctx.expression():
                self.add_error(ctx, "Función void no debe retornar valor")
        elif expr_type != self.current_function.return_type:
            self.add_error(ctx, f"Tipo de retorno no coincide. Esperado: {self.current_function.return_type.name}")
        
        self.current_function.return_statements.append(expr_type)
        return expr_type