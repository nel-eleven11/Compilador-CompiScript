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
        # Manejar tanto ParserRuleContext como TerminalNode
        if hasattr(ctx, 'start'):
            line = ctx.start.line
        elif hasattr(ctx, 'symbol'):
            line = ctx.symbol.line
        else:
            line = "unknown"
        
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
    
    # ===============================================================================================
    # OPERACIONES ARITMETICAS
    #
    #
    # Esta función verifica operaciones aritméticas
    def check_arithmetic(self, left_type, right_type, ctx):
        from classes.types import INT_TYPE, ERROR_TYPE

        # Si alguno es None, lo convertimos a ERROR_TYPE
        if left_type is None or right_type is None:
            return ERROR_TYPE

        # Si alguno ya es ERROR_TYPE, simplemente propagamos sin imprimir error
        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE

        # Verificar que ambos sean enteros
        if left_type != INT_TYPE or right_type != INT_TYPE:
            left_name = left_type.name if left_type else "None"
            right_name = right_type.name if right_type else "None"
            self.add_error(ctx, f"Operación aritmética requiere operandos integer, got {left_name} y {right_name}")
            return ERROR_TYPE

        return INT_TYPE

    # Visitor para multiplicativeExpr (* / %)
    def visitMultiplicativeExpr(self, ctx):
        children = list(ctx.getChildren())
        if len(children) == 1:
            return self.visit(ctx.unaryExpr(0))

        left_type = self.visit(ctx.unaryExpr(0))
        for i, op_node in enumerate(ctx.children[1::2]):
            right_expr = ctx.unaryExpr(i + 1)
            right_type = self.visit(right_expr)
            # Pasamos el contexto de la expresión derecha
            left_type = self.check_arithmetic(left_type, right_type, right_expr)
        return left_type

    # Visitor para additiveExpr (+ -)
    def visitAdditiveExpr(self, ctx):
        children = list(ctx.getChildren())
        if len(children) == 1:
            return self.visit(ctx.multiplicativeExpr(0))

        left_type = self.visit(ctx.multiplicativeExpr(0))
        for i, op_node in enumerate(ctx.children[1::2]):  # operadores
            right_expr = ctx.multiplicativeExpr(i + 1)     # contexto de la expresión derecha
            right_type = self.visit(right_expr)
            # Pasamos el contexto de la expresión derecha, no el nodo terminal
            left_type = self.check_arithmetic(left_type, right_type, right_expr)
        return left_type
    
     # ===============================================================================================
    
    
    # OPERACIONES LOGICAS
    #
    #
    # Funciones de verificación para operaciones lógicas
    def check_logical(self, left_type, right_type, ctx):
        from classes.types import BOOL_TYPE, ERROR_TYPE
        
        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE
        
        if left_type != BOOL_TYPE or right_type != BOOL_TYPE:
            left_name = left_type.name if left_type else "None"
            right_name = right_type.name if right_type else "None"
            self.add_error(ctx, f"Operación lógica requiere operandos boolean, got {left_name} y {right_name}")
            return ERROR_TYPE
        
        return BOOL_TYPE
    
    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())
        elif ctx.leftHandSide():
            return self.visit(ctx.leftHandSide())
        elif ctx.LPAREN():
            return self.visit(ctx.expression())
        else:
            self.add_error(ctx, "Expresión primaria inválida")
            return ERROR_TYPE

    # Funciones de verificación para operaciones de comparación
    def check_comparison(self, left_type, right_type, ctx):
        
        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE
        
        # Caso especial: comparación con null
        if left_type == NULL_TYPE or right_type == NULL_TYPE:
            if (left_type == NULL_TYPE and right_type == NULL_TYPE):
                return BOOL_TYPE
            if (left_type == NULL_TYPE and right_type not in (INT_TYPE, BOOL_TYPE)) or \
            (right_type == NULL_TYPE and left_type not in (INT_TYPE, BOOL_TYPE)):
                return BOOL_TYPE
            self.add_error(ctx.parentCtx, f"No se puede comparar null con {right_type.name if left_type == NULL_TYPE else left_type.name}")
            return ERROR_TYPE
        
        # Verificar compatibilidad de tipos
        if left_type != right_type:
            left_name = left_type.name if left_type else "None"
            right_name = right_type.name if right_type else "None"
            op = ctx.getText() if ctx else "=="
            self.add_error(ctx.parentCtx, f"Operación de comparación '{op}' requiere tipos compatibles, got {left_name} y {right_name}")
            return ERROR_TYPE
        
        return BOOL_TYPE

    def check_relational(self, left_type, right_type, ctx):
        
        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE
        
        # Verificar que ambos sean enteros
        if left_type != INT_TYPE or right_type != INT_TYPE:
            left_name = left_type.name if left_type else "None"
            right_name = right_type.name if right_type else "None"
            op = ctx.getText() if ctx else "rel_op"
            self.add_error(ctx.parentCtx, f"Operación relacional '{op}' requiere operandos integer, got {left_name} y {right_name}")
            return ERROR_TYPE
        
        return BOOL_TYPE
    
    # Visitor para operaciones lógicas (&&, ||)
    def visitLogicalOrExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.logicalAndExpr(0))
        
        left_type = self.visit(ctx.logicalAndExpr(0))
        # Iterar por cada expresión adicional
        for i in range(1, len(ctx.logicalAndExpr())):
            right_expr = ctx.logicalAndExpr(i)
            right_type = self.visit(right_expr)
            left_type = self.check_logical(left_type, right_type, right_expr)
        return left_type

    def visitLogicalAndExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.equalityExpr(0))
        
        left_type = self.visit(ctx.equalityExpr(0))
        # Iterar por cada expresión adicional
        for i in range(1, len(ctx.equalityExpr())):
            right_expr = ctx.equalityExpr(i)
            right_type = self.visit(right_expr)
            left_type = self.check_logical(left_type, right_type, right_expr)
        return left_type

    # Visitor para operaciones de igualdad (==, !=)
    def visitEqualityExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.relationalExpr(0))
        
        left_type = self.visit(ctx.relationalExpr(0))
        result_type = left_type
        
        for i in range(1, ctx.getChildCount(), 2):
            if i+1 >= ctx.getChildCount():
                break
                
            op_node = ctx.getChild(i)
            right_expr = ctx.relationalExpr((i+1)//2)
            right_type = self.visit(right_expr)
            result_type = self.check_comparison(left_type, right_type, op_node)
            left_type = right_type
        
        return result_type

    def visitRelationalExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.additiveExpr(0))
        
        left_type = self.visit(ctx.additiveExpr(0))
        result_type = left_type
        
        for i in range(1, ctx.getChildCount(), 2):
            if i+1 >= ctx.getChildCount():
                break
                
            op_node = ctx.getChild(i)
            right_expr = ctx.additiveExpr((i+1)//2)
            right_type = self.visit(right_expr)
            result_type = self.check_relational(left_type, right_type, op_node)
            left_type = right_type
        
        return result_type

    # Actualizar el visitUnaryExpr para manejar el operador !
    def visitUnaryExpr(self, ctx):
        if ctx.NOT():
            expr_type = self.visit(ctx.unaryExpr())
            if expr_type != BOOL_TYPE and expr_type != ERROR_TYPE:
                self.add_error(ctx, f"Operador '!' requiere operando booleano, got {expr_type.name}")
                return ERROR_TYPE
            return BOOL_TYPE
        elif ctx.MINUS():
            # Manejo existente para el operador -
            return self.visitChildren(ctx)
        else:
            return self.visit(ctx.primaryExpr())
        
    # ===============================================================================================
    # REGLAS DE DECLARACIONES DE CONSTANTES Y VARIABLES
    #
    #    
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
        current_scope_id = self.symbol_table.scopes[-1].scope_id
        symbol = VariableSymbol(
            name=const_name,
            type_=declared_type,
            scope_id=current_scope_id,
            is_const=True
        )
        
        try:
            self.symbol_table.add_symbol(symbol)
        except Exception as e:
            self.add_error(ctx, str(e))
            
        return None
    
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

        current_scope_id = self.symbol_table.scopes[-1].scope_id
        symbol = VariableSymbol(
            name=var_name,
            type_=final_type,
            scope_id=current_scope_id,
            is_const=False
        )

        # Verificar asignación inicial
        if ctx.initializer():
            expr_type = initializer_type
            if expr_type != ERROR_TYPE and not expr_type.can_assign_to(final_type):
                self.add_error(ctx, f"No se puede asignar {expr_type.name} a {final_type.name}")

        try:
            self.symbol_table.add_symbol(symbol)
        except Exception as e:
            self.add_error(ctx, str(e))

        return None

    
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
            return ERROR_TYPE

        if var_symbol.is_const:
            self.add_error(ctx, f"No se puede reasignar la constante '{var_name}'")
            return ERROR_TYPE

        # Obtener tipo de la expresión
        expr_ctx = ctx.expression()[0] if isinstance(ctx.expression(), list) else ctx.expression()
        expr_type = self.visit(expr_ctx) if expr_ctx else None

        # Regla especial: Permitir cambiar de null a tipo concreto
        if var_symbol.type == NULL_TYPE and expr_type and expr_type != NULL_TYPE and expr_type != ERROR_TYPE:
            var_symbol.type = expr_type  # Actualizar tipo dinámicamente
        elif expr_type != ERROR_TYPE and not expr_type.can_assign_to(var_symbol.type):
            self.add_error(ctx, f"No se puede asignar {expr_type.name} a {var_symbol.type.name}")

        # Siempre propagamos el tipo de la expresión para la verificación de errores en operaciones encadenadas
        return expr_type if expr_type else ERROR_TYPE

    # =========================================================================================================
    # RREGLAS DE FUNCIONES
    #
    #
    def visitBlock(self, ctx):
        # Solo crear nuevo ámbito si no es función/clase (ya tienen su propio ámbito)
        current_scope = self.symbol_table.scopes[-1]
        if current_scope.scope_type not in ['function', 'class']:
            self.symbol_table.enter_scope("block")
        
        result = self.visitChildren(ctx)
        
        if current_scope.scope_type not in ['function', 'class']:
            self.symbol_table.exit_scope()
        
        return result
    
    def visitIdentifierExpr(self, ctx):
        name = ctx.getText()
        symbol = self.symbol_table.lookup(name)
        
        if not symbol:
            self.add_error(ctx, f"Identificador '{name}' no declarado")
            return ERROR_TYPE
        
        # Verificar que el símbolo sea accesible (nueva lógica)
        current_scope_ids = [scope.scope_id for scope in self.symbol_table.scopes]
        if symbol.scope_id not in current_scope_ids:
            if symbol.category == 'variable':
                self.add_error(ctx, f"Variable '{name}' no es accesible en este ámbito")
            return ERROR_TYPE
            
        return symbol.type
        
    def visitFunctionDeclaration(self, ctx):
        func_name = ctx.Identifier().getText()
        return_type = self.get_type_from_ctx(ctx.type_()) if ctx.type_() else VOID_TYPE
        
        if return_type == VOID_TYPE and ctx.type_():
            self.add_error(ctx, f"Uso explícito de 'void' no permitido en funciones")
            return
        
        current_scope_id = self.symbol_table.scopes[-1].scope_id
        func_symbol = FunctionSymbol(
            name=func_name,
            return_type=return_type,
            scope_id=current_scope_id
        )
        
        # Registrar función en ámbito padre
        try:
            self.symbol_table.add_symbol(func_symbol)
        except Exception as e:
            self.add_error(ctx, str(e))
            return
            
        # Entrar en ámbito de función (¡NUEVO: esto crea un ámbito permanente!)
        self.symbol_table.enter_scope("function")
        self.current_function = func_symbol
        
        # Procesar parámetros (igual que antes)
        if ctx.parameters():
            for i, param_ctx in enumerate(ctx.parameters().parameter()):
                param_name = param_ctx.Identifier().getText()
                param_type = self.get_type_from_ctx(param_ctx.type_() if param_ctx.type_() else None)
                
                param_symbol = VariableSymbol(
                    name=param_name,
                    type_=param_type or VOID_TYPE,
                    scope_id=current_scope_id,
                    is_const=False
                )
                
                func_symbol.add_parameter(param_symbol)
                try:
                    self.symbol_table.add_symbol(param_symbol)
                except Exception as e:
                    self.add_error(param_ctx, str(e))
        
        # Procesar cuerpo de la funcion
        self.visit(ctx.block())
        
        # Verificar retornos
        if return_type != VOID_TYPE and not func_symbol.return_statements:
            self.add_error(ctx, f"Función '{func_name}' debe retornar un valor")
        
        # Restaurar ámbito padre
        self.symbol_table.exit_scope() 
        self.current_function = None
        
        # ¡NO hacer exit_scope aquí!
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