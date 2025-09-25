# classes/code_generator.py
from .quadruple import Quadruple
from .activation_record_design import ActivationRecordDesign

class CodeGenerator:
    def __init__(self, symbol_table):
        self.quadruples = []
        self.symbol_table = symbol_table
        self.temp_counter = 0
        self.label_counter = 0
        self.ar_designs = {}  # function_name que usa -> ActivationRecordDesign
        self.current_ar = None
        self.current_temp = None
        
    def new_temp(self):
        """Genera un nuevo temporal"""
        temp = f"t{self.temp_counter}"
        self.temp_counter += 1
        return temp
        
    def new_label(self):
        """Genera una nueva etiqueta"""
        label = f"L{self.label_counter}"
        self.label_counter += 1
        return label
        
    def emit_quad(self, op, arg1, arg2, result):
        """Emite un cuádruplo a la lista"""
        quad = Quadruple(op, arg1, arg2, result)
        self.quadruples.append(quad)
        return quad
        
    def get_ar_design(self, function_name):
        """Obtiene el diseño de registro de activación para una función"""
        return self.ar_designs.get(function_name)
        
    def create_ar_design(self, function_name):
        """Crea un nuevo registro de activación"""
        ar_design = ActivationRecordDesign(function_name)
        self.ar_designs[function_name] = ar_design
        self.current_ar = ar_design
        return ar_design
        
    def get_variable_address(self, var_name):
        """Obtiene la dirección de una variable (para uso en cuádruplos)"""
        # Buscar la variable en la tabla de símbolos
        symbol = self.symbol_table.lookup(var_name)
        if not symbol:
            return f"UNDEFINED_{var_name}"  # Para manejar errores
            
        # Si es global
        if symbol.scope_id == 0:  # el scope global es el primero entonces es 0
            return f"G_{var_name}"
            
        # Si es local a una función
        if self.current_ar:
            offset = self.current_ar.get_offset(var_name)
            if offset is not None:
                return f"FP[{offset}]"  # Frame Pointer + offset
                
        # Si es de una clase (atributo)
        # NOTA IMPORTANTE: Esto requerira mas implementación cuando se haga
        # la parte relacionada a las clases
        return f"OBJ_{var_name}"
        
    def get_quadruples(self):
        """Devuelve la lista de cuádruplos generados"""
        return self.quadruples
        
    def print_quadruples(self):
        """Imprime todos los cuádruplos generados"""
        print("=== CUÁDruplos Generados ===")
        for i, quad in enumerate(self.quadruples):
            print(f"{i}: {quad}")

    def generate_arithmetic_operation(self, left_operand, right_operand, operator, ctx=None):
        """Genera código para operaciones aritméticas binarias"""
        result_temp = self.new_temp()
        self.emit_quad(operator, left_operand, right_operand, result_temp)
        self.current_temp = result_temp
        return result_temp
        
    def generate_unary_operation(self, operand, operator, ctx=None):
        """Genera código para operaciones unarias"""
        result_temp = self.new_temp()
        self.emit_quad(operator, operand, None, result_temp)
        self.current_temp = result_temp
        return result_temp
        
    def generate_assignment(self, target, value, ctx=None):
        """Genera código para asignaciones"""
        self.emit_quad('=', value, None, target)
        return target
        
    def generate_load_immediate(self, value, ctx=None):
        """Genera código para cargar valores inmediatos (literales)"""
        temp = self.new_temp()
        self.emit_quad('=', value, None, temp)
        self.current_temp = temp
        return temp
    
    def generate_load_variable(self, var_name, ctx=None):
        """Genera código para cargar una variable desde memoria"""
        address = self.get_variable_address(var_name)
        temp = self.new_temp()
        self.emit_quad('@', address, None, temp)  # @ indica carga desde memoria
        return temp
        
    def generate_variable_reference(self, var_name, ctx=None):
        """Genera código para referencias a variables"""
        address = self.get_variable_address(var_name)
        temp = self.new_temp()
        self.emit_quad('@', address, None, temp)  # @ para indicar desreferenciación
        self.current_temp = temp
        return temp
        
    def generate_variable_declaration(self, var_name, initial_value=None, ctx=None):
        """Genera código para declaración de variables"""
        address = self.get_variable_address(var_name)
        if initial_value is not None:
            self.generate_assignment(address, initial_value, ctx)
        return address
        
    def generate_constant_declaration(self, const_name, initial_value, ctx=None):
        """Genera código para declaración de constantes"""
        address = self.get_variable_address(const_name)
        self.generate_assignment(address, initial_value, ctx)
        return address

    # ========== CONTROL FLOW METHODS ==========

    def generate_if_else(self, condition_temp, then_statements=None, else_statements=None, ctx=None):
        """
        Genera código para if-else con etiquetas y saltos
        Patrón:
        if condition_temp goto L1
        goto L2
        L1: then_statements
        goto L3
        L2: else_statements
        L3: (continuación)
        """
        label_then = self.new_label()  # L1
        label_else = self.new_label()  # L2
        label_end = self.new_label()   # L3

        # Salto condicional: si la condición es verdadera, ir a then
        self.emit_quad('if', condition_temp, None, label_then)

        # Si la condición es falsa, ir a else
        self.emit_quad('goto', None, None, label_else)

        # Etiqueta then
        self.emit_quad('label', None, None, label_then)
        if then_statements:
            then_statements()  # Ejecutar las declaraciones del then
        self.emit_quad('goto', None, None, label_end)

        # Etiqueta else
        self.emit_quad('label', None, None, label_else)
        if else_statements:
            else_statements()  # Ejecutar las declaraciones del else

        # Etiqueta final
        self.emit_quad('label', None, None, label_end)

        return {'then_label': label_then, 'else_label': label_else, 'end_label': label_end}

    def generate_while_loop(self, condition_func, body_func, ctx=None):
        """
        Genera código para bucles while
        Patrón:
        L1: (inicio del bucle)
        if !condition goto L2
        body_statements
        goto L1
        L2: (fin del bucle)
        """
        label_start = self.new_label()   # L1
        label_end = self.new_label()     # L2

        # Guardar contexto de bucle para break/continue
        old_loop_context = getattr(self, 'loop_context', None)
        self.loop_context = {
            'start_label': label_start,
            'end_label': label_end,
            'type': 'while'
        }

        # Etiqueta de inicio del bucle
        self.emit_quad('label', None, None, label_start)

        # Evaluar condición
        condition_temp = condition_func() if condition_func else None
        if condition_temp:
            # Si la condición es falsa, salir del bucle
            self.emit_quad('if_false', condition_temp, None, label_end)

        # Cuerpo del bucle
        if body_func:
            body_func()

        # Salto incondicional al inicio
        self.emit_quad('goto', None, None, label_start)

        # Etiqueta de fin del bucle
        self.emit_quad('label', None, None, label_end)

        # Restaurar contexto de bucle
        self.loop_context = old_loop_context

        return {'start_label': label_start, 'end_label': label_end}

    def generate_for_loop(self, init_func, condition_func, update_func, body_func, ctx=None):
        """
        Genera código para bucles for
        Patrón:
        init_statements
        L1: (inicio del bucle)
        if !condition goto L3
        body_statements
        L2: (continue apunta aquí)
        update_statements
        goto L1
        L3: (fin del bucle)
        """
        label_start = self.new_label()      # L1
        label_continue = self.new_label()   # L2
        label_end = self.new_label()        # L3

        # Guardar contexto de bucle para break/continue
        old_loop_context = getattr(self, 'loop_context', None)
        self.loop_context = {
            'start_label': label_start,
            'continue_label': label_continue,
            'end_label': label_end,
            'type': 'for'
        }

        # Inicialización
        if init_func:
            init_func()

        # Etiqueta de inicio del bucle
        self.emit_quad('label', None, None, label_start)

        # Evaluar condición
        condition_temp = condition_func() if condition_func else None
        if condition_temp:
            # Si la condición es falsa, salir del bucle
            self.emit_quad('if_false', condition_temp, None, label_end)

        # Cuerpo del bucle
        if body_func:
            body_func()

        # Etiqueta de continue
        self.emit_quad('label', None, None, label_continue)

        # Actualización
        if update_func:
            update_func()

        # Salto incondicional al inicio
        self.emit_quad('goto', None, None, label_start)

        # Etiqueta de fin del bucle
        self.emit_quad('label', None, None, label_end)

        # Restaurar contexto de bucle
        self.loop_context = old_loop_context

        return {'start_label': label_start, 'continue_label': label_continue, 'end_label': label_end}

    def generate_break(self, ctx=None):
        """Genera código para break - salta al final del bucle actual"""
        loop_context = getattr(self, 'loop_context', None)
        if not loop_context:
            return None  # Error: break fuera de bucle (manejado en semántico)

        end_label = loop_context['end_label']
        self.emit_quad('goto', None, None, end_label)
        return end_label

    def generate_continue(self, ctx=None):
        """Genera código para continue - salta al inicio/continue del bucle actual"""
        loop_context = getattr(self, 'loop_context', None)
        if not loop_context:
            return None  # Error: continue fuera de bucle (manejado en semántico)

        # Para while, continue va al inicio
        # Para for, continue va a la etiqueta de actualización
        if loop_context['type'] == 'for':
            continue_label = loop_context['continue_label']
        else:
            continue_label = loop_context['start_label']

        self.emit_quad('goto', None, None, continue_label)
        return continue_label

    # ========== ARRAY AND MATRIX METHODS ==========

    def generate_array_access(self, array_name, index_temp, ctx=None):
        """
        Genera código para acceso a elementos de array
        Patrón: t = array[index]
        """
        array_address = self.get_variable_address(array_name)
        result_temp = self.new_temp()

        # Calcular dirección: base + index * size
        # Asumimos que los arrays son de enteros (4 bytes cada uno)
        offset_temp = self.new_temp()
        self.emit_quad('*', index_temp, '4', offset_temp)  # index * 4

        address_temp = self.new_temp()
        self.emit_quad('+', array_address, offset_temp, address_temp)  # base + offset

        # Carga indirecta
        self.emit_quad('[]', address_temp, None, result_temp)  # result = [address]

        self.current_temp = result_temp
        return result_temp

    def generate_array_assignment(self, array_name, index_temp, value_temp, ctx=None):
        """
        Genera código para asignación a elementos de array
        Patrón: array[index] = value
        """
        array_address = self.get_variable_address(array_name)

        # Calcular dirección: base + index * size
        offset_temp = self.new_temp()
        self.emit_quad('*', index_temp, '4', offset_temp)  # index * 4

        address_temp = self.new_temp()
        self.emit_quad('+', array_address, offset_temp, address_temp)  # base + offset

        # Asignación indirecta
        self.emit_quad('[]=', value_temp, None, address_temp)  # [address] = value

        return address_temp

    def generate_matrix_access(self, matrix_name, row_index_temp, col_index_temp, cols_count, ctx=None):
        """
        Genera código para acceso a elementos de matriz
        Patrón: t = matrix[row][col]
        Dirección = base + (row * cols + col) * size
        """
        matrix_address = self.get_variable_address(matrix_name)
        result_temp = self.new_temp()

        # Calcular offset: row * cols
        row_offset_temp = self.new_temp()
        self.emit_quad('*', row_index_temp, str(cols_count), row_offset_temp)

        # Sumar col: (row * cols) + col
        total_index_temp = self.new_temp()
        self.emit_quad('+', row_offset_temp, col_index_temp, total_index_temp)

        # Multiplicar por tamaño del elemento
        offset_temp = self.new_temp()
        self.emit_quad('*', total_index_temp, '4', offset_temp)  # * 4 para enteros

        # Calcular dirección final
        address_temp = self.new_temp()
        self.emit_quad('+', matrix_address, offset_temp, address_temp)

        # Carga indirecta
        self.emit_quad('[]', address_temp, None, result_temp)

        self.current_temp = result_temp
        return result_temp

    def generate_matrix_assignment(self, matrix_name, row_index_temp, col_index_temp, cols_count, value_temp, ctx=None):
        """
        Genera código para asignación a elementos de matriz
        Patrón: matrix[row][col] = value
        """
        matrix_address = self.get_variable_address(matrix_name)

        # Calcular offset: row * cols
        row_offset_temp = self.new_temp()
        self.emit_quad('*', row_index_temp, str(cols_count), row_offset_temp)

        # Sumar col: (row * cols) + col
        total_index_temp = self.new_temp()
        self.emit_quad('+', row_offset_temp, col_index_temp, total_index_temp)

        # Multiplicar por tamaño del elemento
        offset_temp = self.new_temp()
        self.emit_quad('*', total_index_temp, '4', offset_temp)

        # Calcular dirección final
        address_temp = self.new_temp()
        self.emit_quad('+', matrix_address, offset_temp, address_temp)

        # Asignación indirecta
        self.emit_quad('[]=', value_temp, None, address_temp)

        return address_temp

    # ========== FUNCTION METHODS ==========

    def generate_function_declaration(self, function_name, parameters, return_type, body_func, ctx=None):
        """
        Genera código para declaración de funciones
        Incluye el diseño del registro de activación
        """
        # Crear registro de activación
        ar_design = self.create_ar_design(function_name)

        # Agregar parámetros al registro de activación
        for param_name, param_type in parameters:
            ar_design.add_parameter(param_name, param_type)

        # Etiqueta de inicio de función
        func_label = f"FUNC_{function_name}"
        self.emit_quad('label', None, None, func_label)

        # Prólogo de función: configurar el frame pointer
        self.emit_quad('enter', str(ar_design.size), None, None)

        # Guardar el contexto actual de función
        old_function_context = getattr(self, 'function_context', None)
        self.function_context = {
            'name': function_name,
            'ar_design': ar_design,
            'return_type': return_type,
            'func_label': func_label
        }

        # Generar código del cuerpo
        if body_func:
            body_func()

        # Si es función void y no hay return explícito, agregar return vacío
        if return_type and return_type.name == 'void':
            self.emit_quad('return', None, None, None)

        # Epílogo de función
        self.emit_quad('leave', None, None, None)

        # Restaurar contexto de función
        self.function_context = old_function_context

        return {'func_label': func_label, 'ar_design': ar_design}

    def generate_function_call(self, function_name, arguments, ctx=None):
        """
        Genera código para llamadas a funciones
        Patrón:
        push arg1
        push arg2
        ...
        call FUNC_function_name
        add sp, n*4  ; limpiar argumentos de la pila
        t = pop      ; obtener valor de retorno (si hay)
        """
        # Obtener diseño del registro de activación
        ar_design = self.get_ar_design(function_name)
        if not ar_design:
            # Si no existe, crear uno básico
            ar_design = self.create_ar_design(function_name)

        # Push de argumentos en orden reverso (convención C)
        for arg_temp in reversed(arguments):
            self.emit_quad('push', arg_temp, None, None)

        # Llamada a la función
        func_label = f"FUNC_{function_name}"
        self.emit_quad('call', None, None, func_label)

        # Limpiar argumentos de la pila (caller cleanup)
        if arguments:
            args_size = len(arguments) * 4  # 4 bytes por argumento
            self.emit_quad('add', 'SP', str(args_size), 'SP')

        # Obtener valor de retorno (si la función no es void)
        result_temp = self.new_temp()
        self.emit_quad('pop', None, None, result_temp)

        self.current_temp = result_temp
        return result_temp

    def generate_return_statement(self, value_temp=None, ctx=None):
        """
        Genera código para statement return
        """
        function_context = getattr(self, 'function_context', None)
        if not function_context:
            return None  # Error: return fuera de función (manejado en semántico)

        if value_temp:
            # Return con valor: almacenar en registro de retorno
            self.emit_quad('return', value_temp, None, None)
        else:
            # Return sin valor (función void)
            self.emit_quad('return', None, None, None)

        return value_temp

    def generate_parameter_access(self, param_name, ctx=None):
        """
        Genera código para acceso a parámetros de función
        """
        function_context = getattr(self, 'function_context', None)
        if not function_context:
            return self.generate_load_variable(param_name, ctx)

        ar_design = function_context['ar_design']
        offset = ar_design.get_offset(param_name)

        if offset is not None:
            # Parámetro encontrado en el registro de activación
            result_temp = self.new_temp()
            self.emit_quad('@', f"FP[{offset}]", None, result_temp)
            return result_temp
        else:
            # Fallback a variable normal
            return self.generate_load_variable(param_name, ctx)

    def add_local_variable_to_ar(self, var_name, var_type):
        """
        Agrega una variable local al registro de activación actual
        """
        function_context = getattr(self, 'function_context', None)
        if function_context:
            ar_design = function_context['ar_design']
            ar_design.add_local(var_name, var_type)
            return ar_design.get_offset(var_name)
        return None

    # ========== COMPARISON AND LOGICAL OPERATIONS ==========

    def generate_comparison(self, left_temp, right_temp, operator, ctx=None):
        """
        Genera código para operaciones de comparación
        Operadores: ==, !=, <, <=, >, >=
        """
        result_temp = self.new_temp()
        self.emit_quad(operator, left_temp, right_temp, result_temp)
        self.current_temp = result_temp
        return result_temp

    def generate_logical_operation(self, left_temp, right_temp, operator, ctx=None):
        """
        Genera código para operaciones lógicas (&&, ||)
        Utiliza evaluación con cortocircuito
        """
        if operator == '&&':
            return self._generate_and_operation(left_temp, right_temp, ctx)
        elif operator == '||':
            return self._generate_or_operation(left_temp, right_temp, ctx)
        else:
            # Operación lógica simple
            result_temp = self.new_temp()
            self.emit_quad(operator, left_temp, right_temp, result_temp)
            self.current_temp = result_temp
            return result_temp

    def _generate_and_operation(self, left_temp, right_temp, ctx=None):
        """
        Genera código para AND con cortocircuito
        Patrón:
        if !left goto L1
        result = right
        goto L2
        L1: result = false
        L2: (continuar)
        """
        result_temp = self.new_temp()
        label_false = self.new_label()
        label_end = self.new_label()

        # Si left es falso, resultado es falso
        self.emit_quad('if_false', left_temp, None, label_false)

        # Si left es verdadero, resultado depende de right
        self.emit_quad('=', right_temp, None, result_temp)
        self.emit_quad('goto', None, None, label_end)

        # Caso falso
        self.emit_quad('label', None, None, label_false)
        self.emit_quad('=', 'false', None, result_temp)

        # Continuación
        self.emit_quad('label', None, None, label_end)

        self.current_temp = result_temp
        return result_temp

    def _generate_or_operation(self, left_temp, right_temp, ctx=None):
        """
        Genera código para OR con cortocircuito
        Patrón:
        if left goto L1
        result = right
        goto L2
        L1: result = true
        L2: (continuar)
        """
        result_temp = self.new_temp()
        label_true = self.new_label()
        label_end = self.new_label()

        # Si left es verdadero, resultado es verdadero
        self.emit_quad('if', left_temp, None, label_true)

        # Si left es falso, resultado depende de right
        self.emit_quad('=', right_temp, None, result_temp)
        self.emit_quad('goto', None, None, label_end)

        # Caso verdadero
        self.emit_quad('label', None, None, label_true)
        self.emit_quad('=', 'true', None, result_temp)

        # Continuación
        self.emit_quad('label', None, None, label_end)

        self.current_temp = result_temp
        return result_temp

    def generate_logical_not(self, operand_temp, ctx=None):
        """
        Genera código para NOT lógico
        """
        result_temp = self.new_temp()
        self.emit_quad('!', operand_temp, None, result_temp)
        self.current_temp = result_temp
        return result_temp
