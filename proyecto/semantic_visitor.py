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
        declared_type = self.get_type_from_ctx(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        
        # inicializacion obligatoria
        if not ctx.expression():
            self.add_error(ctx, f"Constante '{const_name}' debe ser inicializada")
            return
            
        # tipo del valor inicializador
        initializer_type = self.visit(ctx.expression())
        
        # si notiene tipo declarado, inferirlo del inicializador
        if not declared_type:
            if initializer_type == NULL_TYPE:
                self.add_error(ctx, f"Constante '{const_name}' requiere tipo explícito cuando se inicializa con null")
                return
            declared_type = initializer_type
        
        # compatibilidad de tipos
        if initializer_type and not initializer_type.can_assign_to(declared_type):
            self.add_error(ctx, f"No se puede asignar {initializer_type.name} a {declared_type.name} en constante")
            return
            
        # Crear símbolo
        symbol = VariableSymbol(
            name=const_name,
            type_=declared_type,
            scope_level=self.symbol_table.current_scope,
            is_const=True
        )
        
        try:
            self.symbol_table.add_symbol(symbol)
        except Exception as e:
            self.add_error(ctx, str(e))
            
        return self.visitChildren(ctx)
    
    def visitLiteralExpr(self, ctx):
        if ctx.NULL():
            return NULL_TYPE
        elif ctx.TRUE() or ctx.FALSE():
            return BOOL_TYPE
        elif ctx.Literal():
            literal = ctx.Literal().getText()
            if literal[0] == '"':  # Es string
                return STRING_TYPE
            else:  # Es numero ya que solo se se tienen definidas 2 liteerales en la gramatica, o string o numero
                return INT_TYPE
        elif ctx.arrayLiteral():
            return self.visit(ctx.arrayLiteral())
        return None
    
    # Determinar el tipo de un array literal
    def visitArrayLiteral(self, ctx):
        
        if not ctx.expression() or len(ctx.expression()) == 0:
            return ArrayType(NULL_TYPE, [0])  # Array vacío de tipo desconocido
        
        # Verificar que todos los elementos sean del mismo tipo
        element_type = self.visit(ctx.expression(0))
        for expr in ctx.expression()[1:]:
            current_type = self.visit(expr)
            if current_type != element_type:
                self.add_error(ctx, f"Elementos de array con tipos inconsistentes: {element_type.name} vs {current_type.name}")
                return None
        
        return ArrayType(element_type, [len(ctx.expression())])

    def visitVariableDeclaration(self, ctx):
        var_name = ctx.Identifier().getText()
        declared_type = self.get_type_from_ctx(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        
        # Inferir tipo si no hay anotación
        initializer_type = self.visit(ctx.initializer().expression()) if ctx.initializer() else None
        
        # Determinar el tipo final
        if declared_type:
            final_type = declared_type
        else:
            final_type = initializer_type if initializer_type else NULL_TYPE
        
        symbol = VariableSymbol(
            name=var_name,
            type_=final_type,
            scope_level=self.symbol_table.current_scope,
            is_const=False
        )

        # Verificar asignación inicial
        if ctx.initializer():
            expr_type = self.visit(ctx.initializer().expression())
            if expr_type and not expr_type.can_assign_to(final_type):
                self.add_error(ctx, f"No se puede asignar {expr_type.name} a {final_type.name}")

        try:
            self.symbol_table.add_symbol(symbol)
        except Exception as e:
            self.add_error(ctx, str(e))
            
        return self.visitChildren(ctx)
    
    #Versión flexible de verificación de tipos
    def check_assignment(self, source_type, target_type, is_nullable):
        
        if source_type == NULL_TYPE:
            return is_nullable
        return source_type.can_assign_to(target_type)
    
    def visitAssignment(self, ctx):
        # Obtener el símbolo de la variable
        var_name = ctx.Identifier().getText() if ctx.Identifier() else None
        if not var_name:
            return self.visitChildren(ctx)
        
        var_symbol = self.symbol_table.lookup(var_name)
        if not var_symbol:
            self.add_error(ctx, f"Variable '{var_name}' no declarada")
            return
            
        if var_symbol.is_const:
            self.add_error(ctx, f"No se puede reasignar la constante '{var_name}'")
            return
            
        # Obtener tipo de la expresión
        expr_ctx = ctx.expression()[0] if isinstance(ctx.expression(), list) else ctx.expression()
        expr_type = self.visit(expr_ctx) if expr_ctx else None
        
        # Regla especial: Permitir cambiar de null a tipo concreto
        if var_symbol.type == NULL_TYPE and expr_type and expr_type != NULL_TYPE:
            #print(f"Info: Variable '{var_name}' cambia de null a {expr_type.name}")
            var_symbol.type = expr_type  # Actualizar el tipo dinámicamente
        elif expr_type and not expr_type.can_assign_to(var_symbol.type):
            self.add_error(ctx, f"No se puede asignar {expr_type.name} a {var_symbol.type.name}")
        
        return expr_type
    
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