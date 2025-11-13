from antlr4 import *
from classes.types import *
from classes.symbols import *
from classes.symbol_table import SymbolTable
from classes.code_generator import CodeGenerator
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
        self.codegen = CodeGenerator(self.symbol_table)
        self.codegen.current_visitor = self  # Allow code generator to call visitor methods
        self.current_temp = None
        
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

        # Visitar primera expresión
        left_type = self.visit(ctx.multiplicativeExpr(0))
        left_temp = self.codegen.current_temp
        
        # fix: Marcar left_temp como usado en la expresión completa
        self.codegen.mark_temp_used(left_temp)
        
        for i in range(len(ctx.children) // 2):
            operator = ctx.children[2*i + 1]
            right_expr = ctx.multiplicativeExpr(i + 1)
            
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp
            
            # NUEVO: Marcar right_temp como usado
            self.codegen.mark_temp_used(right_temp)
            
            result_type = self.check_additive_operation(
                left_type, right_type, operator, right_expr
            )
            
            if result_type != ERROR_TYPE:
                op_text = operator.getText()
                result_temp = self.codegen.generate_arithmetic_operation(
                    left_temp, right_temp, op_text, ctx
                )
                left_temp = result_temp
                self.codegen.current_temp = result_temp
            
            left_type = result_type
        
        return left_type
    
    def visitMultiplicativeExpr(self, ctx):

        children = list(ctx.getChildren())
        if len(children) == 1:
            return self.visit(ctx.unaryExpr(0))

        # Visitar la primera expresión
        left_type = self.visit(ctx.unaryExpr(0))
        left_temp = self.codegen.current_temp  # Guardar el temporal izquierdo
        
        # Procesar cada operador y su expresión derecha
        for i in range(len(ctx.children) // 2):
            operator = ctx.children[2*i + 1]  # El operador está en posición impar
            right_expr = ctx.unaryExpr(i + 1)
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp  # Guardar el temporal derecho
            
            # Verificación semántica
            result_type = self.check_arithmetic(left_type, right_type, right_expr)
            
            # Generación de código
            if result_type != ERROR_TYPE:
                op_text = operator.getText()
                self.codegen.generate_arithmetic_operation(left_temp, right_temp, op_text, ctx)
                left_temp = self.codegen.current_temp  # Actualizar para la siguiente operación
            
            left_type = result_type  # Actualizar el tipo para la siguiente operación
        
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
        
        # Visitar la primera expresión y obtener su tipo y temporal
        left_type = self.visit(ctx.logicalAndExpr(0))
        left_temp = self.codegen.current_temp
        
        # Iterar por cada expresión adicional
        for i in range(1, len(ctx.logicalAndExpr())):
            right_expr = ctx.logicalAndExpr(i)
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp
            
            # Verificación semántica
            result_type = self.check_logical(left_type, right_type, right_expr)
            
            # Generación de código
            if result_type != ERROR_TYPE:
                op_text = '||' if isinstance(ctx, CompiscriptParser.LogicalOrExprContext) else '&&'
                result_temp = self.codegen.generate_logical_operation(left_temp, right_temp, '||', ctx)
                left_temp = result_temp
                self.codegen.current_temp = result_temp
            
            left_type = result_type
        
        return left_type

    def visitLogicalAndExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.equalityExpr(0))
        
        # Visitar la primera expresión y obtener su tipo y temporal
        left_type = self.visit(ctx.equalityExpr(0))
        left_temp = self.codegen.current_temp
        
        # Iterar por cada expresión adicional
        for i in range(1, len(ctx.equalityExpr())):
            right_expr = ctx.equalityExpr(i)
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp
            
            # Verificación semántica
            result_type = self.check_logical(left_type, right_type, right_expr)
            
            # Generación de código
            if result_type != ERROR_TYPE:
                result_temp = self.codegen.generate_logical_operation(left_temp, right_temp, '&&', ctx)
                left_temp = result_temp
                self.codegen.current_temp = result_temp
            
            left_type = result_type
        
        return left_type

    # Visitor para operaciones de igualdad (==, !=)
    def visitEqualityExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.relationalExpr(0))
        
        # Visitar la primera expresión y obtener su tipo y temporal
        left_type = self.visit(ctx.relationalExpr(0))
        left_temp = self.codegen.current_temp
        result_type = left_type
        
        for i in range(1, ctx.getChildCount(), 2):
            if i+1 >= ctx.getChildCount():
                break
                
            op_node = ctx.getChild(i)
            right_expr = ctx.relationalExpr((i+1)//2)
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp
            
            # Verificación semántica
            result_type = self.check_comparison(left_type, right_type, op_node)
            
            # Generación de código
            if result_type != ERROR_TYPE:
                op_text = op_node.getText()  # '==' o '!='
                result_temp = self.codegen.generate_comparison(left_temp, right_temp, op_text, ctx)
                left_temp = result_temp
                self.codegen.current_temp = result_temp
            
            left_type = right_type
        
        return result_type

    def visitRelationalExpr(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.additiveExpr(0))
        
        # Visitar la primera expresión y obtener su tipo y temporal
        left_type = self.visit(ctx.additiveExpr(0))
        left_temp = self.codegen.current_temp
        result_type = left_type
        
        for i in range(1, ctx.getChildCount(), 2):
            if i+1 >= ctx.getChildCount():
                break
                
            op_node = ctx.getChild(i)
            right_expr = ctx.additiveExpr((i+1)//2)
            right_type = self.visit(right_expr)
            right_temp = self.codegen.current_temp
            
            # Verificación semántica
            result_type = self.check_relational(left_type, right_type, op_node)
            
            # Generación de código
            if result_type != ERROR_TYPE:
                op_text = op_node.getText()  # '<', '<=', '>', '>='
                result_temp = self.codegen.generate_comparison(left_temp, right_temp, op_text, ctx)
                left_temp = result_temp
                self.codegen.current_temp = result_temp
            
            left_type = right_type
        
        return result_type

    # Actualizar el visitUnaryExpr para manejar el operador !
    def visitUnaryExpr(self, ctx):
        if ctx.NOT():
            expr_type = self.visit(ctx.unaryExpr())
            if expr_type != BOOL_TYPE and expr_type != ERROR_TYPE:
                self.add_error(ctx, f"Operador '!' requiere operando booleano, got {expr_type.name}")
                return ERROR_TYPE
            
            # Generación de código
            if expr_type != ERROR_TYPE:
                # caso para operacion de negacion booleana
                operand_temp = self.codegen.current_temp
                
                self.codegen.generate_logical_not(operand_temp, ctx)
            
            return BOOL_TYPE
        elif ctx.MINUS():
            expr_type = self.visit(ctx.unaryExpr())
            if expr_type != INT_TYPE and expr_type != ERROR_TYPE:
                self.add_error(ctx, f"Operador '-' requiere operando entero, got {expr_type.name}")
                return ERROR_TYPE
            
            # Generación de código
            if expr_type != ERROR_TYPE:
                operand_temp = self.codegen.current_temp
                self.codegen.generate_unary_operation(operand_temp, 'NEG', ctx)  # NEG para negación unaria es el -
            
            return INT_TYPE
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
        self.codegen.in_assignment_context = True
        initializer_type = self.visit(ctx.expression())
        self.codegen.in_assignment_context = False
        
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
        
        # GENERACIÓN DE CÓDIGO
        if not self.errors:
            init_value = self.codegen.current_temp
            const_address = self.codegen.get_variable_address(const_name)
            self.codegen.generate_assignment(const_address, init_value, ctx)
        
        self.codegen.end_expression()
        
        return None
    
    def visitLiteralExpr(self, ctx):
        # Análisis semántico existente
        if ctx.NULL():
            result_type = NULL_TYPE
        elif ctx.TRUE() or ctx.FALSE():
            result_type = BOOL_TYPE
        elif ctx.Literal():
            literal = ctx.Literal().getText()
            if literal[0] == '"':  # Es string
                result_type = STRING_TYPE
            else:  # Es numero
                result_type = INT_TYPE
        elif ctx.arrayLiteral():
            result_type = self.visit(ctx.arrayLiteral())
        else:
            result_type = None
        
        # Generación de código
        if result_type != ERROR_TYPE:
            if ctx.NULL():
                self.codegen.generate_load_immediate('null', ctx)
            elif ctx.TRUE():
                self.codegen.generate_load_immediate('true', ctx)
            elif ctx.FALSE():
                self.codegen.generate_load_immediate('false', ctx)
            elif ctx.Literal():
                literal = ctx.Literal().getText()
                self.codegen.generate_load_immediate(literal, ctx)
            # Para arrays, es una implementación más compleja
            # DE MOMENTO TA PENDIENTE
        
        return result_type
    
    # Determinar el tipo de un array literal
    def visitArrayLiteral(self, ctx):

        if not ctx.expression() or len(ctx.expression()) == 0:
            return ArrayType(NULL_TYPE, [0])  # Array vacío de tipo desconocido

        # Verificar que todos los elementos sean del mismo tipo y guardar los valores
        element_values = []
        element_type = self.visit(ctx.expression(0))
        element_values.append(self.codegen.current_temp)

        for expr in ctx.expression()[1:]:
            current_type = self.visit(expr)
            element_values.append(self.codegen.current_temp)
            if current_type != element_type:
                self.add_error(ctx, f"Elementos de array con tipos inconsistentes: {element_type.name} vs {current_type.name}")
                return None

        # Store the element values for later initialization
        # We'll pass this through current_temp as a special marker
        self.codegen.current_temp = ('array_literal', element_values)

        return ArrayType(element_type, [len(ctx.expression())])

    def visitVariableDeclaration(self, ctx):
        var_name = ctx.Identifier().getText()
        
        if self.symbol_table.is_declared_in_current_scope(var_name):
            existing_symbol = self.symbol_table.lookup_in_current_scope(var_name)
            symbol_type = "constante" if existing_symbol and hasattr(existing_symbol, 'is_const') and existing_symbol.is_const else "variable"
            self.add_error(ctx, f"Variable '{var_name}' ya declarada como {symbol_type} en este ámbito")
            return
        
        declared_type = self.get_type_from_ctx(ctx.typeAnnotation().type_()) if ctx.typeAnnotation() else None
        
        # unica VISITA con contexto de asignación
        initializer_type = None
        if ctx.initializer():
            self.codegen.in_assignment_context = True
            initializer_type = self.visit(ctx.initializer().expression())
            self.codegen.in_assignment_context = False
        
        # Determinar tipo y si fue inferido
        if declared_type:
            final_type = declared_type
            is_type_inferred = False
        else:
            final_type = initializer_type if initializer_type else NULL_TYPE
            is_type_inferred = True

        current_scope_id = self.symbol_table.scopes[-1].scope_id
        symbol = VariableSymbol(
            name=var_name,
            type_=final_type,
            scope_id=current_scope_id,
            is_const=False,
            is_type_inferred=is_type_inferred
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

        # GENERACIÓN DE CÓDIGO (ya visitamos arriba)
        if not self.errors and ctx.initializer():
            init_value = self.codegen.current_temp  # Puede ser literal, temporal, o array literal

            # Check if it's an array literal initialization
            if isinstance(init_value, tuple) and init_value[0] == 'array_literal':
                # Generate code to initialize each array element
                element_values = init_value[1]
                var_address = self.codegen.get_variable_address(var_name)
                self.codegen.generate_array_literal_init(var_address, element_values, ctx)
            else:
                # Regular assignment
                var_address = self.codegen.get_variable_address(var_name)
                self.codegen.generate_assignment(var_address, init_value, ctx)
        
        # Si se está dentro de una clase, registrar como atributo
        if self.current_class:
            self.current_class.add_attribute(symbol)

        self.codegen.end_expression()

        return None

    
    #Versión flexible de verificación de tipos
    def check_assignment(self, source_type, target_type, is_nullable):
        
        if source_type == NULL_TYPE:
            return is_nullable
        return source_type.can_assign_to(target_type)
    
    def visitAssignment(self, ctx):
        # Caso b) property assign: hay DOS expresiones en el contexto,  baseExpr . Identifier = valueExpr
        if len(ctx.expression()) == 2 and ctx.Identifier():
            base_expr = ctx.expression(0)
            value_expr = ctx.expression(1)
            member_name = ctx.Identifier().getText()

            # PROBLEMA ANTERIOR: visitamos base primero
            # Esto carga 'this' pero luego al visitar value_expr,
            # current_temp se sobrescribe!
            
            # SOLUCIÓN: Visitar value PRIMERO, guardar su temporal
            value_type = self.visit(value_expr)
            value_temp = self.codegen.current_temp  # Guardar INMEDIATAMENTE
            
            # AHORA sí visitar base (puede ser 'this' o una variable)
            base_type = self.visit(base_expr)
            base_temp = self.codegen.current_temp

            if base_type == ERROR_TYPE or value_type == ERROR_TYPE:
                return ERROR_TYPE

            # Debe ser instancia de clase
            cls_sym = self._lookup_class(base_type.name) if base_type else None
            if not cls_sym:
                self.add_error(ctx, f"No se puede asignar a miembro '{member_name}' de tipo no-clase")
                return ERROR_TYPE

            # Buscar atributo en la jerarquía
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

            # GENERACIÓN DE CÓDIGO con temporales CORRECTOS
            if not self.errors:
                self.codegen.generate_property_store(
                    base_temp, cls_sym.name, member_name, value_temp, ctx
                )

            return value_type

        # Caso a) asignación simple a variable
        var_name = ctx.Identifier().getText() if ctx.Identifier() else None
        if not var_name:
            return self.visitChildren(ctx)

        symbol = self.symbol_table.lookup(var_name)
        
        if not symbol:
            self.add_error(ctx, f"Variable '{var_name}' no declarada")
            return ERROR_TYPE

        if symbol.is_const:
            self.add_error(ctx, f"No se puede reasignar la constante '{var_name}'")
            return ERROR_TYPE

        expr_ctx = ctx.expression()[0] if isinstance(ctx.expression(), list) else ctx.expression()
        self.codegen.in_assignment_context = True
        expr_type = self.visit(expr_ctx)
        self.codegen.in_assignment_context = False

        # Caso especial: variable con tipo inferido
        if (symbol.type == NULL_TYPE and 
            symbol.is_type_inferred and
            expr_type != NULL_TYPE and 
            expr_type != VOID_TYPE and 
            expr_type != ERROR_TYPE):
            symbol.type = expr_type
        else:
            if expr_type != ERROR_TYPE and not expr_type.can_assign_to(symbol.type):
                self.add_error(ctx, f"No se puede asignar {expr_type.name} a {symbol.type.name}")

        # GENERACIÓN DE CÓDIGO
        if not self.errors:
            expr_value = self.codegen.current_temp
            var_address = self.codegen.get_variable_address(var_name)
            self.codegen.generate_assignment(var_address, expr_value, ctx)

        self.codegen.end_expression()

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
    
    # luego de probar varias veces con prints y logs, realmente parece que esto no hace nada
    # pero por miedo a romper algo, mejor lo dejo
    def visitIdentifierExpr(self, ctx):
        name = ctx.getText()
        symbol = self.symbol_table.lookup(name)
        
        if not symbol:
            self.add_error(ctx, f"Identificador '{name}' no declarado")
            return ERROR_TYPE
            
        # GENERACIÓN DE CÓDIGO
        if symbol.category == 'variable':
            # USAR generate_load_variable optimizado
            temp = self.codegen.generate_load_variable(name, ctx)
            self.codegen.current_temp = temp
        
        return symbol.type
        
    def visitFunctionDeclaration(self, ctx):
        func_name = ctx.Identifier().getText()

        # identificar el inicio de la nueva funcion
        self.codegen.set_current_function(func_name)

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
        
        # Generate function code only if no errors
        if not self.errors:
            # Prepare parameters for code generation
            parameters = []
            if ctx.parameters():
                for param_ctx in ctx.parameters().parameter():
                    param_name = param_ctx.Identifier().getText()
                    param_type = self.get_type_from_ctx(param_ctx.type_() if param_ctx.type_() else None)
                    parameters.append((param_name, param_type or VOID_TYPE))

            def body_func():
                self.visit(ctx.block())

            # Generate function declaration code
            self.codegen.generate_function_declaration(
                function_name=func_name,
                parameters=parameters,
                return_type=return_type,
                body_func=body_func,
                ctx=ctx
            )
        else:
            # Still perform semantic analysis
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

        # Clear the current activation record so subsequent code is treated as global
        self.codegen.current_ar = None

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

        # Generate return statement code only if no errors
        if not self.errors and self.current_function:
            value_temp = self.codegen.current_temp if ctx.expression() else None
            self.codegen.generate_return_statement(value_temp, ctx)

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
        arg_temps = []  # For code generation
        if ctx.arguments():
            for arg_expr in ctx.arguments().expression():
                arg_type = self.visit(arg_expr)
                args.append(arg_type)
                if self.codegen.current_temp:
                    arg_temps.append(self.codegen.current_temp)

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

        # Generate function call code only if no errors
        if not self.errors:
            result_temp = self.codegen.generate_function_call(func_name, arg_temps, ctx)
            self.codegen.current_temp = result_temp

        return func_symbol.return_type

    def visitIndexExpr(self, ctx):
        """Visit array indexing expression: arr[index]"""
        # Get the parent context to find the array name
        parent_ctx = ctx.parentCtx
        if not parent_ctx or not hasattr(parent_ctx, 'primaryAtom'):
            return ERROR_TYPE

        array_name = parent_ctx.primaryAtom().getText()
        array_symbol = self.symbol_table.lookup(array_name)

        if not array_symbol:
            self.add_error(ctx, f"Array '{array_name}' no declarado")
            return ERROR_TYPE

        if not isinstance(array_symbol.type, ArrayType):
            self.add_error(ctx, f"'{array_name}' no es un array")
            return ERROR_TYPE

        # Visit the index expression
        index_type = self.visit(ctx.expression())
        if index_type != INT_TYPE and index_type != ERROR_TYPE:
            self.add_error(ctx, f"Índice de array debe ser integer, encontrado {index_type.name}")
            return ERROR_TYPE

        # Generate code for array access (load)
        if not self.errors:
            index_temp = self.codegen.current_temp
            result_temp = self.codegen.generate_array_access(array_name, index_temp, ctx)
            self.codegen.current_temp = result_temp

        # Return the element type of the array
        return array_symbol.type.element_type

    def visitAssignExpr(self, ctx):
        """Visit assignment expression: lhs = value"""
        # Check if lhs contains array indexing
        lhs_ctx = ctx.lhs

        # Check if lhs has suffixOp (array indexing or property access)
        has_index = False
        if hasattr(lhs_ctx, 'suffixOp') and lhs_ctx.suffixOp():
            for suffix in lhs_ctx.suffixOp():
                if hasattr(suffix, 'expression'):  # This is IndexExpr
                    has_index = True
                    break

        # Handle array index assignment: arr[index] = value
        if has_index:
            # Get array name
            array_name = lhs_ctx.primaryAtom().getText()
            array_symbol = self.symbol_table.lookup(array_name)

            if not array_symbol:
                self.add_error(ctx, f"Array '{array_name}' no declarado")
                return ERROR_TYPE

            if not isinstance(array_symbol.type, ArrayType):
                self.add_error(ctx, f"'{array_name}' no es un array")
                return ERROR_TYPE

            # Find the IndexExpr suffix
            index_ctx = None
            for suffix in lhs_ctx.suffixOp():
                if hasattr(suffix, 'expression'):
                    index_ctx = suffix
                    break

            if not index_ctx:
                return ERROR_TYPE

            # Visit index expression FIRST
            index_type = self.visit(index_ctx.expression())
            if index_type != INT_TYPE and index_type != ERROR_TYPE:
                self.add_error(ctx, f"Índice de array debe ser integer, encontrado {index_type.name}")
                return ERROR_TYPE
            index_temp = self.codegen.current_temp

            # Visit value expression
            value_type = self.visit(ctx.assignmentExpr())
            value_temp = self.codegen.current_temp

            # Type check
            element_type = array_symbol.type.element_type
            if value_type != ERROR_TYPE and not value_type.can_assign_to(element_type):
                self.add_error(ctx, f"No se puede asignar {value_type.name} a array de {element_type.name}")
                return ERROR_TYPE

            # Generate array store code
            if not self.errors:
                self.codegen.generate_array_assignment(array_name, index_temp, value_temp, ctx)

            return value_type

        # Handle simple variable assignment: var = value
        if hasattr(lhs_ctx, 'primaryAtom') and not lhs_ctx.suffixOp():
            var_name = lhs_ctx.primaryAtom().getText()
            symbol = self.symbol_table.lookup(var_name)

            if not symbol:
                self.add_error(ctx, f"Variable '{var_name}' no declarada")
                return ERROR_TYPE

            if symbol.is_const:
                self.add_error(ctx, f"No se puede reasignar la constante '{var_name}'")
                return ERROR_TYPE

            # Visit value expression
            value_type = self.visit(ctx.assignmentExpr())
            value_temp = self.codegen.current_temp

            # Type check
            if value_type != ERROR_TYPE and not value_type.can_assign_to(symbol.type):
                self.add_error(ctx, f"No se puede asignar {value_type.name} a {symbol.type.name}")
                return ERROR_TYPE

            # Generate assignment code
            if not self.errors:
                var_address = self.codegen.get_variable_address(var_name)
                self.codegen.generate_assignment(var_address, value_temp, ctx)

            return value_type

        # Otherwise, not an assignment, just visit children
        return self.visitChildren(ctx)

    # CONTROL FLOW VALIDATION
    def visitIfStatement(self, ctx):
        condition_type = self.visit(ctx.expression())
        if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
            self.add_error(ctx.expression(), f"Condición de 'if' debe ser boolean, encontrado {condition_type.name}")

        # Generate code only if no errors
        if not self.errors:
            condition_temp = self.codegen.current_temp

            def then_statements():
                self.visit(ctx.block(0))  # if block

            def else_statements():
                if ctx.block(1):  # else block exists
                    self.visit(ctx.block(1))

            # Generate if-else code
            self.codegen.generate_if_else(
                condition_temp=condition_temp,
                then_statements=then_statements if ctx.block(0) else None,
                else_statements=else_statements if ctx.block(1) else None,
                ctx=ctx
            )
        else:
            # Still visit for semantic analysis
            self.visit(ctx.block(0))  # if block
            if ctx.block(1):  # else block
                self.visit(ctx.block(1))

        return None
    
    def visitPrintStatement(self, ctx):
        """Visit print statement: print(expression);"""
        # Visit the expression to get its type
        expr_type = self.visit(ctx.expression())

        if expr_type == ERROR_TYPE:
            return None

        # Validate that the type is printable (integer, string, boolean)
        if expr_type not in [INT_TYPE, STRING_TYPE, BOOL_TYPE]:
            self.add_error(ctx, f"print() no puede imprimir tipo '{expr_type.name}'")
            return None

        # Generate print code only if no errors
        if not self.errors:
            value_temp = self.codegen.current_temp
            self.codegen.generate_print_statement(value_temp, expr_type, ctx)

        return None

    def visitWhileStatement(self, ctx):
        # Enter loop context first
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1

        # Generate code only if no errors
        if not self.errors:
            def condition_func():
                condition_type = self.visit(ctx.expression())
                if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
                    self.add_error(ctx.expression(), f"Condición de 'while' debe ser boolean, encontrado {condition_type.name}")
                return self.codegen.current_temp

            def body_func():
                self.visit(ctx.block())

            # Generate while loop code
            self.codegen.generate_while_loop(
                condition_func=condition_func,
                body_func=body_func,
                ctx=ctx
            )
        else:
            # Still perform semantic analysis
            condition_type = self.visit(ctx.expression())
            if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
                self.add_error(ctx.expression(), f"Condición de 'while' debe ser boolean, encontrado {condition_type.name}")
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

        # Enter loop context
        prev_in_loop = self.in_loop
        self.in_loop = True
        self.loop_depth += 1

        # Generate code only if no errors
        if not self.errors:
            def init_func():
                if ctx.variableDeclaration():
                    self.visit(ctx.variableDeclaration())
                elif ctx.assignment():
                    self.visit(ctx.assignment())

            def condition_func():
                if ctx.expression(0):  # condition expression
                    condition_type = self.visit(ctx.expression(0))
                    if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
                        self.add_error(ctx.expression(0), f"Condición de 'for' debe ser boolean, encontrado {condition_type.name}")
                    return self.codegen.current_temp
                return None

            def update_func():
                if ctx.expression(1):  # increment expression
                    self.visit(ctx.expression(1))

            def body_func():
                self.visit(ctx.block())

            # Generate for loop code
            self.codegen.generate_for_loop(
                init_func=init_func if (ctx.variableDeclaration() or ctx.assignment()) else None,
                condition_func=condition_func if ctx.expression(0) else None,
                update_func=update_func if ctx.expression(1) else None,
                body_func=body_func,
                ctx=ctx
            )
        else:
            # Still perform semantic analysis
            if ctx.variableDeclaration():
                self.visit(ctx.variableDeclaration())
            elif ctx.assignment():
                self.visit(ctx.assignment())

            if ctx.expression(0):  # condition expression
                condition_type = self.visit(ctx.expression(0))
                if condition_type != BOOL_TYPE and condition_type != ERROR_TYPE:
                    self.add_error(ctx.expression(0), f"Condición de 'for' debe ser boolean, encontrado {condition_type.name}")

            if ctx.expression(1):  # increment expression
                self.visit(ctx.expression(1))

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

        # Generate code only if no errors and we're in a loop
        if not self.errors and self.in_loop:
            self.codegen.generate_break(ctx)

        # Marcar que cualquier código después de este break es inalcanzable
        self.unreachable_code = True
        return None

    def visitContinueStatement(self, ctx):
        # Verificar código muerto antes del continue
        self.check_unreachable_code(ctx, "statement continue")

        if not self.in_loop:
            self.add_error(ctx, "continue solo puede usarse dentro de un bucle")

        # Generate code only if no errors and we're in a loop
        if not self.errors and self.in_loop:
            self.codegen.generate_continue(ctx)

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
        
        # CAMBIO: Usar el helper para cargar 'this'
        tmp = self.codegen.load_this_pointer(ctx)
        self.codegen.current_temp = tmp
        
        return self._class_type(self.current_class.name)


    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        class_name = ctx.Identifier(0).getText()
        
        # Evitar redeclaración
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
        
        # Registrar clase
        try:
            self.symbol_table.add_symbol(cls_sym)
        except Exception as e:
            self.add_error(ctx, str(e))
            return None
        
        # Entrar ámbito de clase
        self.symbol_table.enter_scope("class")
        prev_cls = self.current_class
        self.current_class = cls_sym
        
        # fix: Procesar PRIMERO los atributos para construir el layout
        for member in ctx.classMember():
            if member.variableDeclaration():
                self.visit(member.variableDeclaration())
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
        
        # CREAR EL LAYOUT AHORA (antes de procesar métodos)
        try:
            self.codegen.define_class_layout(cls_sym)
        except Exception as e:
            self.add_error(ctx, f"Error al crear layout de clase '{class_name}': {str(e)}")
        
        # AHORA procesar los métodos (que ya pueden usar el layout)
        for member in ctx.classMember():
            if member.functionDeclaration():
                func_ctx = member.functionDeclaration()
                func_name = func_ctx.Identifier().getText()
                
                # === CONSTRUCTOR ===
                if func_name == "constructor":
                    # ... código del constructor (igual que antes) ...
                    if func_ctx.type_():
                        self.add_error(func_ctx, "El constructor no debe declarar tipo de retorno")
                    
                    current_scope_id = self.symbol_table.scopes[-1].scope_id
                    func_symbol = FunctionSymbol("constructor", VOID_TYPE, current_scope_id)
                    cls_sym.add_method(func_symbol)
                    try:
                        self.symbol_table.add_symbol(func_symbol)
                    except Exception as e:
                        self.add_error(func_ctx, str(e))
                    
                    self.symbol_table.enter_scope("function")
                    self.current_function = func_symbol
                    
                    # Parámetros del constructor
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
                    
                    if not self.errors:
                        params_for_codegen = []
                        if func_ctx.parameters():
                            for p in func_ctx.parameters().parameter():
                                pn = p.Identifier().getText()
                                pt = self.get_type_from_ctx(p.type_() if p.type_() else None)
                                params_for_codegen.append((pn, pt or VOID_TYPE))
                        
                        def body_func():
                            self.visit(func_ctx.block())
                        
                        self.codegen.generate_method_declaration(
                            class_name=cls_sym.name,
                            method_name="constructor",
                            parameters=params_for_codegen,
                            return_type=VOID_TYPE,
                            body_func=body_func,
                            ctx=func_ctx
                        )
                    else:
                        self.visit(func_ctx.block())
                    
                    for ret_t in func_symbol.return_statements:
                        if ret_t != VOID_TYPE and ret_t != ERROR_TYPE:
                            self.add_error(func_ctx, "El constructor no debe retornar un valor")
                    
                    self.symbol_table.exit_scope()
                    self.current_function = None
                
                # === MÉTODO NORMAL ===
                else:
                    # ... código de métodos normales (igual que antes) ...
                    return_type = self.get_type_from_ctx(func_ctx.type_()) if func_ctx.type_() else VOID_TYPE
                    if return_type == VOID_TYPE and func_ctx.type_():
                        self.add_error(func_ctx, "Uso explícito de 'void' no permitido en funciones")
                        continue
                    
                    current_scope_id = self.symbol_table.scopes[-1].scope_id
                    func_symbol = FunctionSymbol(func_name, return_type, current_scope_id)
                    cls_sym.add_method(func_symbol)
                    try:
                        self.symbol_table.add_symbol(func_symbol)
                    except Exception as e:
                        self.add_error(func_ctx, str(e))
                        continue
                    
                    self.symbol_table.enter_scope("function")
                    self.current_function = func_symbol
                    
                    if func_ctx.parameters():
                        for p in func_ctx.parameters().parameter():
                            pn = p.Identifier().getText()
                            pt = self.get_type_from_ctx(p.type_() if p.type_() else None)
                            p_sym = VariableSymbol(pn, pt or VOID_TYPE, scope_id=self.symbol_table.scopes[-1].scope_id, is_const=False)
                            func_symbol.add_parameter(p_sym)
                            try:
                                self.symbol_table.add_symbol(p_sym)
                            except Exception as e:
                                self.add_error(p, str(e))
                    
                    if not self.errors:
                        params_for_codegen = []
                        if func_ctx.parameters():
                            for p in func_ctx.parameters().parameter():
                                pn = p.Identifier().getText()
                                pt = self.get_type_from_ctx(p.type_() if p.type_() else None)
                                params_for_codegen.append((pn, pt or VOID_TYPE))
                        
                        def body_func():
                            self.visit(func_ctx.block())
                        
                        self.codegen.generate_method_declaration(
                            class_name=cls_sym.name,
                            method_name=func_name,
                            parameters=params_for_codegen,
                            return_type=return_type,
                            body_func=body_func,
                            ctx=func_ctx
                        )
                    else:
                        self.visit(func_ctx.block())
                    
                    if return_type != VOID_TYPE:
                        if not func_symbol.return_statements:
                            self.add_error(func_ctx, f"Función '{func_name}' debe retornar un valor")
                        else:
                            for ret_type in func_symbol.return_statements:
                                if ret_type != ERROR_TYPE and ret_type != return_type:
                                    self.add_error(func_ctx, f"Tipo de retorno inconsistente en método '{func_name}'. Esperado: {return_type.name}, encontrado: {ret_type.name}")
                    else:
                        for ret_type in func_symbol.return_statements:
                            if ret_type != VOID_TYPE and ret_type != ERROR_TYPE:
                                self.add_error(func_ctx, f"Método void '{func_name}' no debe retornar valor")
                    
                    self.symbol_table.exit_scope()
                    self.current_function = None
        
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
                # === CAMBIO CLAVE ===
                # Si es arreglo, NO desreferenciamos; necesitamos la dirección base.
                if isinstance(current_type, ArrayType):
                    addr_tmp = self.codegen.generate_address_of_variable(name, base)
                    self.codegen.current_temp = addr_tmp
                else:
                    tmp = self.codegen.generate_load_variable(name, base)
                    self.codegen.current_temp = tmp
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

            # Instanciación y constructor
            # Recolectar temporales de argumentos
            arg_types = []
            arg_temps = []
            if base.arguments():
                for e in base.arguments().expression():
                    t = self.visit(e)
                    arg_types.append(t)
                    arg_temps.append(self.codegen.current_temp)

            # Instanciar objeto en heap
            obj_temp = self.codegen.instantiate_object(class_name)

            # Si hay constructor válido y no se han levantado errores, invocarlo
            if ctor and not self.errors:
                self.codegen.generate_method_call(
                    this_temp=obj_temp,
                    class_name=class_name,
                    method_name="constructor",
                    arguments=arg_temps,
                    ctx=base
                )

            # Devolver el tipo de la clase; dejar el 'this' en current_temp
            self.codegen.current_temp = obj_temp
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
                    pending_func = None
                else:
                    # Guardar base antes de visitar el índice (la visita cambia current_temp)
                    base_addr_tmp = self.codegen.current_temp
                    idx_t = self.visit(s.expression())
                    idx_tmp = self.codegen.current_temp
                    if idx_t != ERROR_TYPE and idx_t != INT_TYPE:
                        self.add_error(s.expression(), f"El índice de un arreglo debe ser integer, encontrado {idx_t.name}")
                    else:
                        # Generar acceso: result = *(base + idx*elem_size)
                        elem_size = self.codegen.get_type_size(current_type.element_type)
                        self.codegen.generate_indexed_load(base_addr_tmp, idx_tmp, elem_size, s)
                    current_type = current_type.element_type
                pending_func = None


            # Acceso a propiedad: .ident  (atributo o método, con herencia)
            elif isinstance(s, CompiscriptParser.PropertyAccessExprContext):
                member = s.Identifier().getText()
                
                # NUEVO: Si la base es 'this', recargar desde FP[0]
                if isinstance(base, CompiscriptParser.ThisExprContext):
                    obj_temp_for_method = self.codegen.load_this_pointer(s)
                else:
                    # Usar el temporal actual (ya cargado)
                    obj_temp_for_method = self.codegen.current_temp
                
                # VALIDACIÓN
                if not obj_temp_for_method or obj_temp_for_method == 'None':
                    self.add_error(s, f"Acceso a propiedad '{member}' sobre valor inválido")
                    current_type = ERROR_TYPE
                    pending_func = None
                    i += 1
                    continue
                
                cls = self._lookup_class(current_type.name) if current_type else None
                if not cls:
                    self.add_error(s, f"No se puede acceder a miembro '{member}' de '{current_type.name if current_type else '?'}'")
                    current_type = ERROR_TYPE
                    pending_func = None
                else:
                    found = self.symbol_table.lookup_in_class(cls.name, member)
                    
                    if isinstance(found, VariableSymbol):
                        # CAMBIO: Pasar obj_temp_for_method (que es 'this' correcto)
                        load_temp = self.codegen.generate_property_load(
                            base_temp=obj_temp_for_method,
                            class_name=cls.name,
                            member_name=member,
                            ctx=s
                        )
                        current_type = found.type
                        pending_func = None
                    
                    elif isinstance(found, FunctionSymbol):
                        # Llamada a método...
                        if i + 1 < len(suffixes) and isinstance(suffixes[i + 1], CompiscriptParser.CallExprContext):
                            call = suffixes[i + 1]
                            args_types = []
                            args_temps = []
                            if call.arguments():
                                for e in call.arguments().expression():
                                    t = self.visit(e)
                                    args_types.append(t)
                                    args_temps.append(self.codegen.current_temp)
                            
                            # Validaciones...
                            if len(args_types) != len(found.parameters):
                                self.add_error(call, f"Método '{member}' espera {len(found.parameters)} argumentos, recibió {len(args_types)}")
                            
                            if not self.errors:
                                # CAMBIO: Pasar obj_temp_for_method (this correcto)
                                result_temp = self.codegen.generate_method_call(
                                    this_temp=obj_temp_for_method,
                                    class_name=cls.name,
                                    method_name=member,
                                    arguments=args_temps,
                                    ctx=call
                                )
                                self.codegen.current_temp = result_temp
                            
                            current_type = found.return_type
                            i += 1
                            pending_func = None
                        else:
                            self.add_error(s, f"Se esperaba invocar al método '{member}'")
                            current_type = ERROR_TYPE
                            pending_func = None
                    else:
                        self.add_error(s, f"Miembro '{member}' no existe en clase '{cls.name}'")
                        current_type = ERROR_TYPE
                        pending_func = None

            i += 1

        # Si queda una función pendiente sin invocar en la cola: error
        if pending_func:
            self.add_error(ctx, f"Se esperaba invocar a la función '{pending_func.name}'")
            return ERROR_TYPE

        return current_type if current_type else ERROR_TYPE


    def visitSwitchStatement(self, ctx):
        """Visit switch statement"""
        # Visit the switch expression
        switch_expr_type = self.visit(ctx.expression())
        
        if switch_expr_type == ERROR_TYPE:
            return None
        
        # Switch expression must be integer or boolean
        if switch_expr_type not in [INT_TYPE, BOOL_TYPE]:
            self.add_error(ctx.expression(), f"Switch expression must be integer or boolean, found {switch_expr_type.name}")
            return None
        
        # Generate code only if no errors
        if not self.errors:
            switch_value_temp = self.codegen.current_temp
            
            # Visit all case statements
            cases = []
            for case_ctx in ctx.switchCase():
                # Visit case expression
                case_expr_type = self.visit(case_ctx.expression())
                if case_expr_type != ERROR_TYPE and case_expr_type != switch_expr_type:
                    self.add_error(case_ctx.expression(), f"Case expression type {case_expr_type.name} doesn't match switch type {switch_expr_type.name}")
                case_value_temp = self.codegen.current_temp
                cases.append((case_value_temp, case_ctx))
            
            # Check for default case
            default_case = ctx.defaultCase() if ctx.defaultCase() else None
            
            # Generate switch code
            self.codegen.generate_switch_statement(
                switch_value_temp,
                cases,
                default_case,
                ctx
            )
        else:
            # Still visit children for semantic analysis
            for case_ctx in ctx.switchCase():
                self.visit(case_ctx.expression())
                for stmt in case_ctx.statement():
                    self.visit(stmt)
            
            if ctx.defaultCase():
                for stmt in ctx.defaultCase().statement():
                    self.visit(stmt)
        
        return None

    def visitSwitchCase(self, ctx):
        """Visit switch case - handled by visitSwitchStatement"""
        pass

    def visitDefaultCase(self, ctx):
        """Visit default case - handled by visitSwitchStatement"""
        pass
