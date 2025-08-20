from antlr4 import *
from classes.types import *
from classes.symbols import *
from classes.symbol_table import SymbolTable
from CompiscriptVisitor import CompiscriptVisitor
from CompiscriptParser import CompiscriptParser

class SemanticVisitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors = []
        self.current_function = None
        self.current_class = None
        self.in_loop = False
        self.loop_depth = 0
        self.warnings = []  # Para advertencias de código muerto
        self.unreachable_code = False  # Flag para detectar código muerto
        
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
    
    def add_warning(self, ctx, message):
        # Agregar advertencias para código muerto u otros problemas no críticos
        if hasattr(ctx, 'start'):
            line = ctx.start.line
        elif hasattr(ctx, 'symbol'):
            line = ctx.symbol.line
        else:
            line = "unknown"
        
        self.warnings.append(f"Advertencia. Línea {line}: {message}")
    
    def check_unreachable_code(self, ctx, description="código"):
        """Verifica si el código es inalcanzable y agrega advertencia"""
        if self.unreachable_code:
            self.add_warning(ctx, f"Código muerto: {description} nunca se ejecutará")
            return True
        return False
    
    def validate_semantic_expression(self, ctx, expr_type, operation, operands=None):
        """Valida que una expresión tenga sentido semántico"""
        if expr_type == ERROR_TYPE:
            return False
            
        # Validar operaciones aritméticas sin sentido
        if operation in ['add', 'subtract', 'multiply', 'divide', 'modulo']:
            if expr_type not in [INT_TYPE, ERROR_TYPE]:
                self.add_error(ctx, f"Operación aritmética '{operation}' con resultado no numérico ({expr_type.name})")
                return False
        
        # Validar comparaciones sin sentido
        if operation in ['compare']:
            if operands and len(operands) == 2:
                left, right = operands
                if left != right and left != NULL_TYPE and right != NULL_TYPE:
                    self.add_warning(ctx, f"Comparación entre tipos diferentes: {left.name} y {right.name}")
        
        # Validar asignaciones sin sentido
        if operation == 'assignment':
            if operands and len(operands) == 2:
                target_type, value_type = operands
                if value_type != ERROR_TYPE and not value_type.can_assign_to(target_type):
                    return False
        
        return True
    
    def check_division_by_zero(self, ctx, right_operand_ctx):
        """Verifica división por cero en tiempo de compilación si es posible"""
        if hasattr(right_operand_ctx, 'Literal'):
            literal = right_operand_ctx.Literal()
            if literal and literal.getText() == '0':
                self.add_warning(ctx, "Posible división por cero")
                return True
        return False
        
    def get_type_from_ctx(self, type_ctx):
        if not type_ctx:
            return None
        type_str = type_ctx.getText()
        t = get_type_from_string(type_str)
        
        if t is not None:
            return t
        # Si no es primitivo/array, puede ser una clase declarada
        cls = self._lookup_class(type_str)
        if cls:
            return self._class_type(type_str)
        return None
    
    # Visit methods
    def visitProgram(self, ctx):
        return self.visitChildren(ctx)
    
    def visitStatement(self, ctx):
        # Verificar código muerto antes de procesar cualquier statement
        self.check_unreachable_code(ctx, "statement")
        return self.visitChildren(ctx)
    
    # ===============================================================================================
    # OPERACIONES ARITMETICAS
    #
    #
    # Esta función verifica operaciones aritméticas
    def check_additive_operation(self, left_type, right_type, operator, ctx):
        
        # Si alguno es None, lo convertimos a ERROR_TYPE
        if left_type is None or right_type is None:
            return ERROR_TYPE

        # Si alguno ya es ERROR_TYPE, propagamos sin error adicional
        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE

        # Determinar el operador
        op = operator.getText() if hasattr(operator, 'getText') else operator

        # Caso concatenación: operador + con strings
        if op == '+' and left_type == STRING_TYPE and right_type == STRING_TYPE:
            result_type = STRING_TYPE
            self.validate_semantic_expression(ctx, result_type, 'concatenation', [left_type, right_type])
            return result_type
            
        # Caso suma aritmética
        if op == '+' or op == '-':
            if left_type == INT_TYPE and right_type == INT_TYPE:
                result_type = INT_TYPE
                operation_name = 'add' if op == '+' else 'subtract'
                self.validate_semantic_expression(ctx, result_type, operation_name)
                return result_type
            else:
                left_name = left_type.name
                right_name = right_type.name
                self.add_error(ctx, 
                    f"Operación '{op}' requiere operandos integer, got {left_name} y {right_name}")
                return ERROR_TYPE

        # Operador no reconocido
        self.add_error(ctx, f"Operador no soportado: {op}")
        return ERROR_TYPE


    # Visitor para additiveExpr (+ -)
    def visitAdditiveExpr(self, ctx):
        children = list(ctx.getChildren())
        if len(children) == 1:
            return self.visit(ctx.multiplicativeExpr(0))

        left_type = self.visit(ctx.multiplicativeExpr(0))
        
        # Procesar cada operador y su expresión derecha
        for i in range(len(ctx.children) // 2):
            operator = ctx.children[2*i + 1]  # El operador está en posición impar
            right_expr = ctx.multiplicativeExpr(i + 1)
            right_type = self.visit(right_expr)
            
            left_type = self.check_additive_operation(
                left_type, 
                right_type, 
                operator,  # Pasa el operador
                right_expr
            )
        
        return left_type
    
    def visitMultiplicativeExpr(self, ctx):
        children = list(ctx.getChildren())
        if len(children) == 1:
            return self.visit(ctx.unaryExpr(0))

        left_type = self.visit(ctx.unaryExpr(0))
        
        # Procesar cada operador y su expresión derecha
        for i in range(len(ctx.children) // 2):
            operator = ctx.children[2*i + 1]  # El operador está en posición impar
            right_expr = ctx.unaryExpr(i + 1)
            right_type = self.visit(right_expr)
            
            left_type = self.check_arithmetic(  # Mantenemos función original para * / %
                left_type, 
                right_type, 
                right_expr
            )
        
        return left_type

    # Mantenemos check_arithmetic solo para * / %
    def check_arithmetic(self, left_type, right_type, ctx):
        from classes.types import INT_TYPE, ERROR_TYPE

        if left_type is None or right_type is None:
            return ERROR_TYPE

        if left_type == ERROR_TYPE or right_type == ERROR_TYPE:
            return ERROR_TYPE

        # Verificar que ambos sean enteros
        if left_type != INT_TYPE or right_type != INT_TYPE:
            left_name = left_type.name
            right_name = right_type.name
            self.add_error(ctx, f"Operación aritmética requiere operandos integer, got {left_name} y {right_name}")
            return ERROR_TYPE

        return INT_TYPE
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

        # Verificar si ya está declarado en el ámbito actual
        if self.symbol_table.is_declared_in_current_scope(const_name):
            existing_symbol = self.symbol_table.lookup_in_current_scope(const_name)
            symbol_type = "constante" if existing_symbol and hasattr(existing_symbol, 'is_const') and existing_symbol.is_const else "variable"
            self.add_error(ctx, f"Constante '{const_name}' ya declarada como {symbol_type} en este ámbito")
            return
        
        declared_type = self.get_type_from_ctx(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        
        # inicializacion obligatoria
        if not ctx.expression():
            self.add_error(ctx, f"Constante '{const_name}' debe ser inicializada")
            return
            
        # tipo del valor inicializador
        initializer_type = self.visit(ctx.expression())
        
        # si notiene tipo declarado, inferirlo del inicializador
        if not declared_type:
            # Comentado de momento por const si deberia de poder inicialzarse con null, si no tiene tipo
            #if initializer_type == NULL_TYPE:
            #    self.add_error(ctx, f"Constante '{const_name}' requiere tipo explícito cuando se inicializa con null")
            #    return
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
        
        if self.symbol_table.is_declared_in_current_scope(var_name):
            existing_symbol = self.symbol_table.lookup_in_current_scope(var_name)
            symbol_type = "constante" if existing_symbol and hasattr(existing_symbol, 'is_const') and existing_symbol.is_const else "variable"
            self.add_error(ctx, f"Variable '{var_name}' ya declarada como {symbol_type} en este ámbito")
            return
        
        declared_type = self.get_type_from_ctx(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        initializer_type = self.visit(ctx.initializer().expression()) if ctx.initializer() else None
        
        # Determinar tipo y si fue inferido
        if declared_type:
            final_type = declared_type
            is_type_inferred = False
        else:
            final_type = initializer_type if initializer_type else NULL_TYPE
            is_type_inferred = True  # Tipo inferido, no explícito

        current_scope_id = self.symbol_table.scopes[-1].scope_id
        symbol = VariableSymbol(
            name=var_name,
            type_=final_type,
            scope_id=current_scope_id,
            is_const=False,
            is_type_inferred=is_type_inferred  # Pasar nuevo atributo
        )

        # Verificar asignación inicial
        if ctx.initializer():
            expr_type = initializer_type
            if expr_type and expr_type != ERROR_TYPE and not expr_type.can_assign_to(final_type):
                self.add_error(ctx, f"No se puede asignar {expr_type.name} a {final_type.name}")

        try:
            self.symbol_table.add_symbol(symbol)
        except Exception as e:
            self.add_error(ctx, str(e))

        # Si se está dentro de una clase, registrar como atributo
        if self.current_class:
            self.current_class.add_attribute(symbol)

        return None

    
    #Versión flexible de verificación de tipos
    def check_assignment(self, source_type, target_type, is_nullable):
        
        if source_type == NULL_TYPE:
            return is_nullable
        return source_type.can_assign_to(target_type)
    
    def visitAssignment(self, ctx):

        # Caso b) property assign: hay DOS expresiones en el contexto
        if len(ctx.expression()) == 2:
            base_expr = ctx.expression(0)
            value_expr = ctx.expression(1)
            member_name = ctx.Identifier().getText()

            base_type = self.visit(base_expr)
            value_type = self.visit(value_expr)

            if base_type == ERROR_TYPE:
                return ERROR_TYPE

            # Debe ser instancia de clase
            cls_sym = self._lookup_class(base_type.name) if base_type else None
            if not cls_sym:
                self.add_error(ctx, f"No se puede asignar a miembro '{member_name}' de tipo no-clase '{base_type.name if base_type else '?'}'")
                return ERROR_TYPE

            # Buscar atributo en la jerarquía (incluye herencia)
            attr = self.symbol_table.lookup_in_class(cls_sym.name, member_name)
            if not isinstance(attr, VariableSymbol):
                self.add_error(ctx, f"Miembro '{member_name}' no existe en clase '{cls_sym.name}'")
                return ERROR_TYPE

            if attr.is_const:
                self.add_error(ctx, f"No se puede reasignar la constante '{member_name}'")
                return ERROR_TYPE

            if value_type != ERROR_TYPE and not value_type.can_assign_to(attr.type):
                self.add_error(ctx, f"No se puede asignar {value_type.name} a {attr.type.name}")
                return ERROR_TYPE

            return value_type if value_type else ERROR_TYPE

        # Caso a) asignación simple a variable
        # Obtener el nombre de la variable
        var_name = ctx.Identifier().getText() if ctx.Identifier() else None
        if not var_name:
            return self.visitChildren(ctx)

        # Buscar la variable en el ámbito actual primero, luego en superiores
        symbol = self.symbol_table.lookup(var_name)
        
        # Si no se encuentra en ningún ámbito
        if not symbol:
            self.add_error(ctx, f"Variable '{var_name}' no declarada")
            return ERROR_TYPE

        # Verificar si es constante
        if symbol.is_const:
            self.add_error(ctx, f"No se puede reasignar la constante '{var_name}'")
            return ERROR_TYPE

        # Obtener tipo de la expresión
        expr_ctx = ctx.expression()[0] if isinstance(ctx.expression(), list) else ctx.expression()
        expr_type = self.visit(expr_ctx) if expr_ctx else None

        # Caso especial: variable con tipo inferido inicializado con null
        if (symbol.type == NULL_TYPE and 
            symbol.is_type_inferred and
            expr_type != NULL_TYPE and 
            expr_type != VOID_TYPE and 
            expr_type != ERROR_TYPE):
            # Actualizar el tipo de la variable dinámicamente
            symbol.type = expr_type
        else:
            # Verificación normal de tipos
            if expr_type != ERROR_TYPE and not expr_type.can_assign_to(symbol.type):
                self.add_error(ctx, f"No se puede asignar {expr_type.name} a {symbol.type.name}")

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
        
        # Reset del flag de código muerto al inicio de cada bloque
        old_unreachable = self.unreachable_code
        self.unreachable_code = False
        
        result = self.visitChildren(ctx)
        
        # Restaurar el estado previo
        self.unreachable_code = old_unreachable
        
        if current_scope.scope_type not in ['function', 'class']:
            self.symbol_table.exit_scope()
        
        return result
    
    def visitIdentifierExpr(self, ctx):
        name = ctx.getText()
        symbol = self.symbol_table.lookup(name)
        
        if not symbol:
            self.add_error(ctx, f"Identificador '{name}' no declarado")
            return ERROR_TYPE
            
        return symbol.type
        
    def visitFunctionDeclaration(self, ctx):
        func_name = ctx.Identifier().getText()
        return_type = self.get_type_from_ctx(ctx.type_()) if ctx.type_() else VOID_TYPE
        
        if return_type == VOID_TYPE and ctx.type_():
            self.add_error(ctx, f"Uso explícito de 'void' no permitido en funciones")
            return
        
        # CHECK FOR DUPLICATE FUNCTIONS IN CURRENT SCOPE
        if self.symbol_table.is_declared_in_current_scope(func_name):
            existing_symbol = self.symbol_table.lookup_in_current_scope(func_name)
            if hasattr(existing_symbol, 'category'):
                symbol_type = existing_symbol.category
            else:
                symbol_type = "símbolo"
            self.add_error(ctx, f"Función '{func_name}' ya declarada como {symbol_type} en este ámbito")
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
        
        # VALIDATE RETURN TYPE - Check if all return statements match declared type
        if return_type != VOID_TYPE:
            if not func_symbol.return_statements:
                self.add_error(ctx, f"Función '{func_name}' debe retornar un valor")
            else:
                # Check each return statement type
                for ret_type in func_symbol.return_statements:
                    if ret_type != ERROR_TYPE and ret_type != return_type:
                        self.add_error(ctx, f"Tipo de retorno inconsistente en función '{func_name}'. Esperado: {return_type.name}, encontrado: {ret_type.name}")
        else:
            # VOID functions should not have return values
            for ret_type in func_symbol.return_statements:
                if ret_type != VOID_TYPE and ret_type != ERROR_TYPE:
                    self.add_error(ctx, f"Función void '{func_name}' no debe retornar valor")
        
        # Restaurar ámbito padre
        self.symbol_table.exit_scope() 
        self.current_function = None

        # Si está dentro de clase y no es 'constructor', agregar a los métodos
        if self.current_class:
            self.current_class.add_method(func_symbol)
        
        return None
    
    # En semantic_visitor.py
    def visitReturnStatement(self, ctx):
        # Verificar código muerto antes del return
        self.check_unreachable_code(ctx, "statement return")
        
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
        
        # Marcar que cualquier código después de este return es inalcanzable
        self.unreachable_code = True
        
        return expr_type
    
    # FUNCTION CALL VALIDATION
    def visitCallExpr(self, ctx):
        # Get function name from the leftHandSide parent
        parent_ctx = ctx.parentCtx
        if not parent_ctx or not hasattr(parent_ctx, 'primaryAtom'):
            return ERROR_TYPE
            
        func_name = parent_ctx.primaryAtom().getText()
        func_symbol = self.symbol_table.lookup(func_name)
        
        if not func_symbol:
            self.add_error(ctx, f"Función '{func_name}' no declarada")
            return ERROR_TYPE
            
        if not isinstance(func_symbol, FunctionSymbol):
            self.add_error(ctx, f"'{func_name}' no es una función")
            return ERROR_TYPE
        
        # Get arguments
        args = []
        if ctx.arguments():
            for arg_expr in ctx.arguments().expression():
                arg_type = self.visit(arg_expr)
                args.append(arg_type)
        
        # Validate number of arguments
        expected_params = len(func_symbol.parameters)
        actual_args = len(args)
        
        if actual_args != expected_params:
            self.add_error(ctx, f"Función '{func_name}' espera {expected_params} argumentos, pero recibió {actual_args}")
            return func_symbol.return_type
        
        # Validate argument types
        for i, (param, arg_type) in enumerate(zip(func_symbol.parameters, args)):
            if arg_type != ERROR_TYPE and not arg_type.can_assign_to(param.type):
                self.add_error(ctx, f"Argumento {i+1} de función '{func_name}': esperado {param.type.name}, encontrado {arg_type.name}")
        
        return func_symbol.return_type
    
    # CONTROL FLOW VALIDATION
    def visitIfStatement(self, ctx):
        condition_type = self.visit(ctx.expression())
        if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
            self.add_error(ctx.expression(), f"Condición de 'if' debe ser boolean, encontrado {condition_type.name}")
        
        # Visit the blocks
        self.visit(ctx.block(0))  # if block
        if ctx.block(1):  # else block
            self.visit(ctx.block(1))
        
        return None
    
    def visitWhileStatement(self, ctx):
        condition_type = self.visit(ctx.expression())
        if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
            self.add_error(ctx.expression(), f"Condición de 'while' debe ser boolean, encontrado {condition_type.name}")
        
        # Enter loop context
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1
        
        self.visit(ctx.block())
        
        # Exit loop context
        self.loop_depth -= 1
        self.in_loop = prev_in_loop or self.loop_depth > 0
        
        return None
    
    def visitDoWhileStatement(self, ctx):
        condition_type = self.visit(ctx.expression())
        if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
            self.add_error(ctx.expression(), f"Condición de 'do-while' debe ser boolean, encontrado {condition_type.name}")
        
        # Enter loop context
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1
        
        self.visit(ctx.block())
        
        # Exit loop context
        self.loop_depth -= 1
        self.in_loop = prev_in_loop or self.loop_depth > 0
        
        return None
    
    def visitForStatement(self, ctx):
        # Create new scope for for loop
        self.symbol_table.enter_scope("for")
        
        # Visit initialization
        if ctx.variableDeclaration():
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment():
            self.visit(ctx.assignment())
        
        # Visit condition
        if ctx.expression(0):  # condition expression
            condition_type = self.visit(ctx.expression(0))
            if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
                self.add_error(ctx.expression(0), f"Condición de 'for' debe ser boolean, encontrado {condition_type.name}")
        
        # Visit increment
        if ctx.expression(1):  # increment expression
            self.visit(ctx.expression(1))
        
        # Enter loop context
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1
        
        self.visit(ctx.block())
        
        # Exit loop context
        self.loop_depth -= 1
        self.in_loop = prev_in_loop or self.loop_depth > 0
        
        # Exit for scope
        self.symbol_table.exit_scope()
        
        return None
    
    def visitForeachStatement(self, ctx):
        # Enter loop context
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1
        
        # Create new scope for foreach
        self.symbol_table.enter_scope("foreach")
        
        # Visit the iterable expression
        iterable_type = self.visit(ctx.expression())
        
        # Check if it's an array type
        if isinstance(iterable_type, ArrayType):
            # Create iterator variable
            iterator_name = ctx.Identifier().getText()
            iterator_symbol = VariableSymbol(
                name=iterator_name,
                type_=iterable_type.element_type,
                scope_id=self.symbol_table.scopes[-1].scope_id,
                is_const=False
            )
            
            try:
                self.symbol_table.add_symbol(iterator_symbol)
            except Exception as e:
                self.add_error(ctx, str(e))
        elif iterable_type != ERROR_TYPE:
            self.add_error(ctx.expression(), f"foreach requiere un array, encontrado {iterable_type.name}")
        
        self.visit(ctx.block())
        
        # Exit foreach scope
        self.symbol_table.exit_scope()
        
        # Exit loop context
        self.loop_depth -= 1
        self.in_loop = prev_in_loop or self.loop_depth > 0
        
        return None
    
    # BREAK AND CONTINUE VALIDATION
    def visitBreakStatement(self, ctx):
        # Verificar código muerto antes del break
        self.check_unreachable_code(ctx, "statement break")
        
        if not self.in_loop:
            self.add_error(ctx, "break solo puede usarse dentro de un bucle")
        
        # Marcar que cualquier código después de este break es inalcanzable
        self.unreachable_code = True
        return None
    
    def visitContinueStatement(self, ctx):
        # Verificar código muerto antes del continue
        self.check_unreachable_code(ctx, "statement continue")
        
        if not self.in_loop:
            self.add_error(ctx, "continue solo puede usarse dentro de un bucle")
        # Marcar que cualquier código después de este continue es inalcanzable
        self.unreachable_code = True
        return None
      

    # =========================================================================================================
    # REGLAS DE CLASES Y OBJETOS
    #
    #

    def _class_type(self, class_name: str) -> Type:
    #Crea un Type para instancias de clase (comparación por nombre).
        return Type(class_name)

    def _lookup_class(self, name: str):
        sym = self.symbol_table.lookup(name)
        return sym if isinstance(sym, ClassSymbol) else None

    def _report(self, ctx, msg):
        self.add_error(ctx, msg)

    def visitThisExpr(self, ctx):
        if not self.current_class:
            self.add_error(ctx, "Uso de 'this' fuera de una clase")
            return ERROR_TYPE
        return self._class_type(self.current_class.name)

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        class_name = ctx.Identifier(0).getText()

        # Evitar redeclaración en el mismo ámbito
        if self.symbol_table.is_declared_in_current_scope(class_name):
            self.add_error(ctx, f"Clase '{class_name}' ya declarada en este ámbito")
            return None

        # Herencia (opcional)
        parent_cls = None
        if ctx.Identifier(1):
            parent_name = ctx.Identifier(1).getText()
            parent_cls = self._lookup_class(parent_name)
            if not parent_cls:
                self.add_error(ctx, f"Clase padre '{parent_name}' no declarada")

        cls_sym = ClassSymbol(class_name, scope_id=self.symbol_table.scopes[-1].scope_id, parent_class=parent_cls)

        # Registrar clase en el ámbito actual (global usualmente)
        try:
            self.symbol_table.add_symbol(cls_sym)
        except Exception as e:
            self.add_error(ctx, str(e))
            return None

        # Entrar en ámbito de clase
        self.symbol_table.enter_scope("class")
        prev_cls = self.current_class
        self.current_class = cls_sym

        # Procesar miembros
        for member in ctx.classMember():
            if member.functionDeclaration():
                # Reutilizamos visitFunctionDeclaration pero añadimos a methods
                func_ctx = member.functionDeclaration()
                func_name = func_ctx.Identifier().getText()

                # Constructor: nombre especial 'constructor'
                if func_name == "constructor":
                    # El constructor no debe declarar tipo de retorno
                    if func_ctx.type_():
                        self.add_error(func_ctx, "El constructor no debe declarar tipo de retorno")
                    # Crear símbolo con retorno VOID explícito
                    current_scope_id = self.symbol_table.scopes[-1].scope_id
                    func_symbol = FunctionSymbol("constructor", VOID_TYPE, current_scope_id)
                    # Guardar antes de entrar al cuerpo para permitir recursión indirecta si aplica
                    cls_sym.add_method(func_symbol)
                    try:
                        self.symbol_table.add_symbol(func_symbol)
                    except Exception as e:
                        self.add_error(func_ctx, str(e))

                    # Entrar a ámbito de función y parámetros
                    self.symbol_table.enter_scope("function")
                    self.current_function = func_symbol
                    if func_ctx.parameters():
                        for p in func_ctx.parameters().parameter():
                            p_name = p.Identifier().getText()
                            p_type = self.get_type_from_ctx(p.type_() if p.type_() else None) or VOID_TYPE
                            p_sym = VariableSymbol(p_name, p_type, scope_id=self.symbol_table.scopes[-1].scope_id, is_const=False)
                            func_symbol.add_parameter(p_sym)
                            try:
                                self.symbol_table.add_symbol(p_sym)
                            except Exception as e:
                                self.add_error(p, str(e))

                    # Procesar cuerpo
                    self.visit(func_ctx.block())

                    # Validación: los constructores no retornan valor
                    for ret_t in func_symbol.return_statements:
                        if ret_t != VOID_TYPE and ret_t != ERROR_TYPE:
                            self.add_error(func_ctx, "El constructor no debe retornar un valor")

                    self.symbol_table.exit_scope()
                    self.current_function = None

                else:
                    # Método normal: delegar a visitFunctionDeclaration y luego adjuntarlo a la clase
                    before_funcs = len(self.symbol_table.scopes[-1].symbols)
                    self.visit(func_ctx)
                    # Recuperar el último FunctionSymbol agregado en este scope
                    # (forma simple: buscar por nombre)
                    added = self.symbol_table.lookup(func_name, current_scope_only=True)
                    if isinstance(added, FunctionSymbol):
                        cls_sym.add_method(added)

            elif member.variableDeclaration():
                # Atributos: reutilizamos visitVariableDeclaration y lo adjuntamos
                before = len(self.symbol_table.scopes[-1].symbols)
                self.visit(member.variableDeclaration())
                # Adjuntar el último símbolo agregado por nombre
                var_name = member.variableDeclaration().Identifier().getText()
                sym = self.symbol_table.lookup(var_name, current_scope_only=True)
                if isinstance(sym, VariableSymbol):
                    cls_sym.add_attribute(sym)

            elif member.constantDeclaration():
                self.visit(member.constantDeclaration())
                const_name = member.constantDeclaration().Identifier().getText()
                sym = self.symbol_table.lookup(const_name, current_scope_only=True)
                if isinstance(sym, VariableSymbol):
                    cls_sym.add_attribute(sym)

        # Salir de la clase
        self.symbol_table.exit_scope()
        self.current_class = prev_cls
        return None

    # =========================================================================================================
    # REGLAS DE LISTAS Y ESTRUCTURAS DE DATOS
    #
    #

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        # valide indexación
        # busque atributos/métodos recorriendo herencia
        # permita llamadas a métodos (encadenadas)
        base = ctx.primaryAtom()

        current_type = None
        pending_func = None  # FunctionSymbol pendiente de invocar

        # -------- Base ----------
        if isinstance(base, CompiscriptParser.IdentifierExprContext):
            name = base.Identifier().getText()
            sym = self.symbol_table.lookup(name)
            if isinstance(sym, VariableSymbol):
                current_type = sym.type
            elif isinstance(sym, FunctionSymbol):
                pending_func = sym
            elif isinstance(sym, ClassSymbol):
                self.add_error(base, f"Uso inválido del nombre de clase '{name}' como valor")
                return ERROR_TYPE
            else:
                self.add_error(base, f"Identificador '{name}' no declarado")
                return ERROR_TYPE

        elif isinstance(base, CompiscriptParser.NewExprContext):
            class_name = base.Identifier().getText()
            cls = self._lookup_class(class_name)
            if not cls:
                self.add_error(base, f"Clase '{class_name}' no declarada")
                return ERROR_TYPE

            # Tipos de argumentos reales
            arg_types = []
            if base.arguments():
                for e in base.arguments().expression():
                    arg_types.append(self.visit(e))

            # Verificación de constructor
            ctor = cls.methods.get("constructor")
            if ctor:
                if len(arg_types) != len(ctor.parameters):
                    self.add_error(base, f"Constructor de '{class_name}' espera {len(ctor.parameters)} argumentos, recibió {len(arg_types)}")
                else:
                    for i, (p, a) in enumerate(zip(ctor.parameters, arg_types), start=1):
                        if a != ERROR_TYPE and not a.can_assign_to(p.type):
                            self.add_error(base, f"Argumento {i} del constructor de '{class_name}': esperado {p.type.name}, encontrado {a.name}")
            elif len(arg_types) != 0:
                self.add_error(base, f"Clase '{class_name}' no define constructor; se esperaban 0 argumentos")

            current_type = self._class_type(class_name)

        elif isinstance(base, CompiscriptParser.ThisExprContext):
            if not self.current_class:
                self.add_error(base, "Uso de 'this' fuera de una clase")
                return ERROR_TYPE
            current_type = self._class_type(self.current_class.name)

        else:
            return self.visitChildren(ctx)

        # -------- Sufijos ----------
        suffixes = list(ctx.suffixOp())
        i = 0
        while i < len(suffixes):
            s = suffixes[i]

            # Llamada: (...)
            if isinstance(s, CompiscriptParser.CallExprContext):
                args = []
                if s.arguments():
                    for e in s.arguments().expression():
                        args.append(self.visit(e))

                if pending_func:
                    if len(args) != len(pending_func.parameters):
                        self.add_error(s, f"Función '{pending_func.name}' espera {len(pending_func.parameters)} argumentos, recibió {len(args)}")
                    else:
                        for j, (p, a) in enumerate(zip(pending_func.parameters, args), start=1):
                            if a != ERROR_TYPE and not a.can_assign_to(p.type):
                                self.add_error(s, f"Argumento {j} de '{pending_func.name}': esperado {p.type.name}, encontrado {a.name}")
                    current_type = pending_func.return_type
                    pending_func = None
                else:
                    self.add_error(s, "Intento de invocar una expresión que no es función")
                    current_type = ERROR_TYPE

            # Indexación: [expr]
            elif isinstance(s, CompiscriptParser.IndexExprContext):
                if not isinstance(current_type, ArrayType):
                    self.add_error(s, "Indexación sobre expresión que no es un arreglo")
                    current_type = ERROR_TYPE
                else:
                    idx_t = self.visit(s.expression())
                    if idx_t != ERROR_TYPE and idx_t != INT_TYPE:
                        self.add_error(s.expression(), f"El índice de un arreglo debe ser integer, encontrado {idx_t.name}")
                    current_type = current_type.element_type
                pending_func = None

            # Acceso a propiedad: .ident  (atributo o método, con herencia)
            elif isinstance(s, CompiscriptParser.PropertyAccessExprContext):
                member = s.Identifier().getText()

                # Resolver clase del tipo actual
                cls = self._lookup_class(current_type.name) if current_type else None
                if not cls:
                    self.add_error(s, f"No se puede acceder a miembro '{member}' de '{current_type.name if current_type else '?'}'")
                    current_type = ERROR_TYPE
                    pending_func = None
                else:
                    # Buscar miembro en jerarquía (atributo / método)
                    found = self.symbol_table.lookup_in_class(cls.name, member)

                    if isinstance(found, VariableSymbol):
                        current_type = found.type
                        pending_func = None

                    elif isinstance(found, FunctionSymbol):
                        # ¿Se invoca de inmediato?
                        if i + 1 < len(suffixes) and isinstance(suffixes[i + 1], CompiscriptParser.CallExprContext):
                            call = suffixes[i + 1]
                            args = []
                            if call.arguments():
                                for e in call.arguments().expression():
                                    args.append(self.visit(e))
                            if len(args) != len(found.parameters):
                                self.add_error(call, f"Método '{member}' espera {len(found.parameters)} argumentos, recibió {len(args)}")
                            else:
                                for j, (p, a) in enumerate(zip(found.parameters, args), start=1):
                                    if a != ERROR_TYPE and not a.can_assign_to(p.type):
                                        self.add_error(call, f"Argumento {j} de método '{member}': esperado {p.type.name}, encontrado {a.name}")
                            current_type = found.return_type
                            i += 1  # consumimos el CallExpr
                            pending_func = None
                        else:
                            self.add_error(s, f"Se esperaba invocar al método '{member}'")
                            current_type = ERROR_TYPE
                            pending_func = None
                    else:
                        self.add_error(s, f"Miembro '{member}' no existe en clase '{cls.name}'")
                        current_type = ERROR_TYPE
                        pending_func = None
            else:
                current_type = ERROR_TYPE
                pending_func = None

            i += 1

        # Si queda una función pendiente sin invocar en la cola: error
        if pending_func:
            self.add_error(ctx, f"Se esperaba invocar a la función '{pending_func.name}'")
            return ERROR_TYPE

        return current_type if current_type else ERROR_TYPE

