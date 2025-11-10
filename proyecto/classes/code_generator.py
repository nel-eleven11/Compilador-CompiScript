# classes/code_generator.py
from .quadruple import Quadruple
from .activation_record_design import ActivationRecordDesign
from .memory_manager import MemoryManager

class CodeGenerator:
    def __init__(self, symbol_table):
        self.quadruples = []
        self.symbol_table = symbol_table
        self.temp_counters = {}
        self.current_function = "global"
        self.label_counter = 0
        self.ar_designs = {}
        self.current_ar = None
        self.current_temp = None
        self.memory_manager = MemoryManager()
        self.class_layouts = {}

        # Para optimización de temporales
        self.last_assigned_temp = None
        self.reusable_temps = set()
        self.used_temps_in_expr = set()
        self.in_assignment_context = False  # NUEVO

    def set_current_function(self, function_name):
        self.current_function = function_name
        if function_name not in self.temp_counters:
            self.temp_counters[function_name] = 0
        self.reusable_temps.clear()
        self.used_temps_in_expr.clear()
        self.last_assigned_temp = None

    def new_temp(self):
        """Genera un nuevo temporal, reutilizando si es posible"""
        if self.current_function not in self.temp_counters:
            self.temp_counters[self.current_function] = 0
        
        if self.reusable_temps:
            temp = self.reusable_temps.pop()
        else:
            temp = f"t{self.temp_counters[self.current_function]}"
            self.temp_counters[self.current_function] += 1
        
        self.last_assigned_temp = temp
        return temp

    def mark_temp_used(self, temp):
        """Marca un temporal como usado en la expresión actual"""
        if not temp:
            return
        
        # fix: Validar que es realmente un temporal
        if isinstance(temp, str) and temp.startswith('t'):
            self.used_temps_in_expr.add(temp)
            # Remover de reusables si estaba ahí
            self.reusable_temps.discard(temp) 

    def mark_temp_reusable(self, temp):
        """Marca un temporal como reusable"""
        if (temp and isinstance(temp, str) and
            temp.startswith('t') and len(temp) > 1 and temp[1:].isdigit() and
            temp not in self.used_temps_in_expr):
            self.reusable_temps.add(temp)

    def end_expression(self):
        """Llamar al final de una expresión para resetear estado"""
        self.used_temps_in_expr.clear()
        self.last_assigned_temp = None
        self.in_assignment_context = False

    def generate_arithmetic_operation(self, left_operand, right_operand, operator, ctx=None):
        self.mark_temp_used(left_operand)
        self.mark_temp_used(right_operand)
        
        # Solo reutilizar si NO está activo en la expresión
        result_temp = None
        if (left_operand.startswith('t') and 
            left_operand not in self.used_temps_in_expr and
            left_operand != right_operand):  # NUEVO: evitar conflicto
            result_temp = left_operand
        elif (right_operand.startswith('t') and 
            right_operand not in self.used_temps_in_expr and
            right_operand != left_operand):  # NUEVO: evitar conflicto
            result_temp = right_operand
        else:
            result_temp = self.new_temp()
        
        self.emit_quad(operator, left_operand, right_operand, result_temp)
        self.current_temp = result_temp
        
        # Solo liberar si NO se reutilizó
        if left_operand != result_temp and left_operand.startswith('t'):
            self.mark_temp_reusable(left_operand)
        if right_operand != result_temp and right_operand.startswith('t'):
            self.mark_temp_reusable(right_operand)
            
        self.last_assigned_temp = result_temp
        return result_temp

    def get_type_size(self, type_obj):
        """Calcula el tamaño de un tipo en bytes"""
        if hasattr(type_obj, 'width') and type_obj.width:
            # un print de dbug que puse para ver si estamos usando el tamaño
            # si lo usamos, pero luego en el memory_manager fijamos espacio a 4bytes con el fin
            # de hacer mas facil el calculo y acceso a datos
            #print("se uso width: ", type_obj.width)
            return type_obj.width
        
        # Valores por defecto basados en el tipo
        type_sizes = {
            'integer': 4,
            'boolean': 1,
            'string': 8,  # Puntero a string
            'void': 0,
            'null': 4,    # Puntero
        }
        return type_sizes.get(type_obj.name, 4)

    # version anterior, pero que era muy simple  
    # def new_temp(self):
    #     """Genera un nuevo temporal"""
    #     temp = f"t{self.temp_counter}"
    #     self.temp_counter += 1
    #     return temp
        
    def new_label(self):
        """Genera una nueva etiqueta"""
        label = f"L{self.label_counter}"
        self.label_counter += 1
        return label
        
    def emit_quad(self, op, arg1, arg2, result, comment=None):
        """Emite un cuádruplo a la lista"""
        quad = Quadruple(op, arg1, arg2, result, comment)
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
            return f"UNDEFINED_{var_name}"
            
        # Variables globales
        if symbol.scope_id == 0:
            size = self.get_type_size(symbol.type)

            # Para arrays, alocar en heap
            if hasattr(symbol.type, 'element_type'):  # Es un array
                # Estimamos 10 elementos por defecto si no se especifica
                element_count = 10  # TODO: obtener el tamaño real del array
                address = self.memory_manager.allocate_array(var_name, element_count, size)
                return f"0x{address:04X}"
            else:
                # Variable simple global
                address = self.memory_manager.allocate_global(var_name, size)
                return f"0x{address:04X}"

        # Variables locales
        if self.current_ar:
            function_name = self.current_ar.function_name
            size = self.get_type_size(symbol.type)

            # Usar el MemoryManager para variables locales
            address = self.memory_manager.allocate_local(var_name, size, function_name)
            return address  # Ya retorna "FP[offset]"

        return f"UNKNOWN_{var_name}"
        
    def get_quadruples(self):
        """Devuelve la lista de cuádruplos generados"""
        return self.quadruples
    
    # En CodeGenerator
    def print_memory_map(self):
        """Imprime el mapa de memoria para debugging"""
        print("=== MAPA DE MEMORIA ===")
        for var_name, address in self.memory_manager.allocations.items():
            # Separar variables locales (que contienen ::)
            if "::" in var_name:
                func_name, local_var = var_name.split("::", 1)

                # Buscar en todos los scopes de la tabla de símbolos
                symbol = None
                type_name = "unknown"

                # Buscar en todos los scopes disponibles
                for scope in self.symbol_table.all_scopes:
                    if local_var in scope.symbols:
                        symbol = scope.symbols[local_var]
                        break

                if symbol and hasattr(symbol, 'type') and symbol.type:
                    type_name = symbol.type.name

                print(f"{address}: {func_name}::{local_var} ({type_name})")
            else:
                symbol = self.symbol_table.lookup(var_name)
                type_name = symbol.type.name if symbol and symbol.type else "unknown"
                # Verificar si address es numérico o string
                if isinstance(address, int):
                    print(f"0x{address:04X}: {var_name} ({type_name})")
                else:
                    print(f"{address}: {var_name} ({type_name})")
        
    def print_quadruples(self):
        """Imprime todos los cuádruplos generados"""
        print("=== CUÁDruplos Generados ===")
        for i, quad in enumerate(self.quadruples):
            print(f"{i}: {quad}")

    # version previa de generacion de operaciones aritmeticas
    # def generate_arithmetic_operation(self, left_operand, right_operand, operator, ctx=None):
    #     """Genera código para operaciones aritméticas binarias"""
    #     result_temp = self.new_temp()
    #     self.emit_quad(operator, left_operand, right_operand, result_temp)
    #     self.current_temp = result_temp
    #     return result_temp
        
    def generate_unary_operation(self, operand, operator, ctx=None):
        """
        Genera código para operaciones unarias optimizadas
        """
        self.mark_temp_used(operand)
        
        # Intentar reutilizar temporal
        if (self.last_assigned_temp and 
            self.last_assigned_temp not in self.used_temps_in_expr):
            result_temp = self.last_assigned_temp
        else:
            result_temp = self.new_temp()
            
        self.emit_quad(operator, operand, None, result_temp)
        self.current_temp = result_temp
        self.last_assigned_temp = result_temp
        return result_temp
        
    def generate_assignment(self, target, value, ctx=None):
        """
        OPTIMIZADO: Asignación directa sin temporales intermedios cuando es posible
        """
        # Caso 1: Asignación directa de literal o valor simple
        if not value.startswith('t'):
            # value es un literal o dirección, asignar directamente
            self.emit_quad('=', value, None, target)
        else:
            # value es un temporal, asignación normal
            self.emit_quad('=', value, None, target)
            # Marcar el temporal como reusable después de usarlo
            self.mark_temp_reusable(value)
        
        return target
        
    def generate_load_immediate(self, value, ctx=None):
        """
        OPTIMIZADO: No genera temporal para literales en contexto de asignación
        """
        # Si estamos en contexto de asignación, retornar el valor directamente
        if self.in_assignment_context:
            self.current_temp = value
            return value
        
        # En expresiones complejas, sí necesitamos temporal
        temp = self.new_temp()
        self.emit_quad('=', value, None, temp)
        self.current_temp = temp
        return temp

    def generate_load_variable(self, var_name, ctx=None):
        """
        OPTIMIZADO: Retorna dirección directamente en contextos simples,
        evitando operaciones @ innecesarias.
        Prioridad: Parámetro > Local > Global
        """
        # 1. Verificar si es un parámetro de la función actual
        function_context = getattr(self, 'function_context', None)
        if function_context:
            ar_design = function_context['ar_design']
            offset = ar_design.get_offset(var_name)

            if offset is not None:
                # Es un parámetro o local - retornar dirección FP[offset]
                address = f"FP[{offset}]"
                self.current_temp = address
                return address

        # 2. Variable global - retornar dirección directamente
        address = self.get_variable_address(var_name)
        self.current_temp = address
        return address

    def generate_address_of_variable(self, var_name, ctx=None):
        """
        Devuelve en un temporal la *dirección base* de una variable sin des-referenciarla.
        Útil para arreglos (arr) y para cualquier dato que se trate como puntero/base.
        """
        addr = self.get_variable_address(var_name)
        # addr puede venir como int (0xNNNN) o como string tipo "FP[...]" / "0x...."
        if isinstance(addr, int):
            addr_str = f"0x{addr:04X}"
        else:
            addr_str = addr
        tmp = self.new_temp()
        self.emit_quad('=', addr_str, None, tmp)
        self.current_temp = tmp
        return tmp

    def generate_indexed_load(self, base_addr_temp, index_temp, elem_size=4, ctx=None):
        """
        Carga genérica: result = *(base + index*elem_size)
        Sirve para arr[i] donde base_addr_temp es la dirección base (o puntero) del arreglo.
        """
        # offset = index * elem_size
        offset = self.new_temp()
        self.emit_quad('*', index_temp, str(elem_size), offset)
        # eff = base + offset
        eff = self.new_temp()
        self.emit_quad('+', base_addr_temp, offset, eff)
        # result = [eff]
        result = self.new_temp()
        self.emit_quad('[]', eff, None, result)
        self.current_temp = result
        return result

    def generate_indexed_store(self, base_addr_temp, index_temp, value_temp, elem_size=4, ctx=None):
        """
        Asignación genérica: *(base + index*elem_size) = value
        """
        offset = self.new_temp()
        self.emit_quad('*', index_temp, str(elem_size), offset)
        eff = self.new_temp()
        self.emit_quad('+', base_addr_temp, offset, eff)
        self.emit_quad('[]=', value_temp, None, eff)
        return eff

        
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
        Genera código para acceso a elementos de array, Acceso a arreglo por nombre de variable.
        Patrón: t = array[index]
        """
        # Dirección base en un temporal
        base_tmp = self.generate_address_of_variable(array_name, ctx)

        # Tamaño de elemento según el tipo del símbolo
        symbol = self.symbol_table.lookup(array_name)
        elem_size = 4
        if symbol and hasattr(symbol.type, 'element_type'):
            elem_size = self.get_type_size(symbol.type.element_type)

        return self.generate_indexed_load(base_tmp, index_temp, elem_size, ctx)

    def generate_array_assignment(self, array_name, index_temp, value_temp, ctx=None):
        """
        Genera código para asignación a elementos de array
        Patrón: array[index] = value
        """
        base_tmp = self.generate_address_of_variable(array_name, ctx)

        symbol = self.symbol_table.lookup(array_name)
        elem_size = 4
        if symbol and hasattr(symbol.type, 'element_type'):
            elem_size = self.get_type_size(symbol.type.element_type)

        return self.generate_indexed_store(base_tmp, index_temp, value_temp, elem_size, ctx)

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

    def generate_method_declaration(self, class_name, method_name, parameters, return_type, body_func, ctx=None):
        func_key = self._method_key(class_name, method_name)
        self.set_current_function(func_key)
        
        ar_design = self.create_ar_design(func_key)
        
        # CRÍTICO: __this SIEMPRE es el primer parámetro (FP[0])
        ar_design.add_parameter('__this', None)
        
        # Parámetros del usuario
        for param_name, param_type in parameters or []:
            ar_design.add_parameter(param_name, param_type)
        
        # 🔍 DEBUG: Imprimir estructura del AR
        print(f"\n=== AR para {class_name}::{method_name} ===")
        print(f"Size total: {ar_design.size}")
        for i, param in enumerate(ar_design.parameters):
            print(f"  FP[{param['offset']}]: {param['name']} ({param['type'].name if param['type'] else 'unknown'})")
        print()
        
        # Resto del código igual...
        func_label = self._method_label(class_name, method_name)
        self.emit_quad('label', None, None, func_label)
        self.emit_quad('enter', str(ar_design.size), None, None)
        
        old_function_context = getattr(self, 'function_context', None)
        self.function_context = {
            'name': func_key,
            'ar_design': ar_design,
            'return_type': return_type,
            'func_label': func_label,
            'class_name': class_name,
            'method_name': method_name
        }
        
        if body_func:
            body_func()
        
        if return_type and getattr(return_type, 'name', None) == 'void':
            self.emit_quad('return', None, None, None)
        
        self.emit_quad('leave', None, None, None)
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

            # También registrar en el memory manager
            function_name = function_context['name']
            size = self.get_type_size(var_type)
            self.memory_manager.allocate_local(var_name, size, function_name)

            return ar_design.get_offset(var_name)
        return None

    # ========== COMPARISON AND LOGICAL OPERATIONS ==========

    def generate_comparison(self, left_temp, right_temp, operator, ctx=None):
        self.mark_temp_used(left_temp)
        self.mark_temp_used(right_temp)
        
        # fix: Comparaciones siempre necesitan nuevo temporal (resultado booleano)
        result_temp = self.new_temp()
        
        self.emit_quad(operator, left_temp, right_temp, result_temp)
        self.current_temp = result_temp
        self.last_assigned_temp = result_temp
        
        # Liberar operandos después de usarlos
        if left_temp.startswith('t'):
            self.mark_temp_reusable(left_temp)
        if right_temp.startswith('t'):
            self.mark_temp_reusable(right_temp)
        
        return result_temp

    def generate_logical_operation(self, left_temp, right_temp, operator, ctx=None):
        """
        Genera código para operaciones lógicas (&&, ||) optimizadas
        Utiliza evaluación con cortocircuito
        """
        # Marcar operandos como usados
        self.mark_temp_used(left_temp)
        self.mark_temp_used(right_temp)
        
        if operator == '&&':
            return self._generate_and_operation(left_temp, right_temp, ctx)
        elif operator == '||':
            return self._generate_or_operation(left_temp, right_temp, ctx)
        else:
            # Operación lógica simple - optimizada
            if (self.last_assigned_temp and 
                self.last_assigned_temp not in self.used_temps_in_expr):
                result_temp = self.last_assigned_temp
            else:
                result_temp = self.new_temp()
                
            self.emit_quad(operator, left_temp, right_temp, result_temp)
            self.current_temp = result_temp
            self.last_assigned_temp = result_temp
            return result_temp

    def _generate_and_operation(self, left_temp, right_temp, ctx=None):
        """
        Genera código para AND con cortocircuito optimizado
        """
        # Para operaciones complejas con cortocircuito, crear nuevo temporal
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
        self.last_assigned_temp = result_temp
        return result_temp

    def _generate_or_operation(self, left_temp, right_temp, ctx=None):
        """
        Genera código para OR con cortocircuito optimizado
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
        self.last_assigned_temp = result_temp
        return result_temp

    def generate_logical_not(self, operand_temp, ctx=None):
        """
        Genera código para NOT lógico optimizado
        """
        self.mark_temp_used(operand_temp)

        # NOT siempre necesita nuevo temporal para el resultado
        result_temp = self.new_temp()

        self.emit_quad('!', operand_temp, None, result_temp)
        self.current_temp = result_temp
        self.last_assigned_temp = result_temp
        return result_temp

    #========= CLASSES AND OBJECTS ==========

    def define_class_layout(self, class_symbol):
        """
        Construye (si no existe) el layout de la clase con offsets de atributos
        y tamaño total de la instancia, considerando herencia.
        """
        name = getattr(class_symbol, "name", None)
        if not name:
            return None
        if name in self.class_layouts:
            return self.class_layouts[name]

        # Herencia: comenzar con el layout del padre (si hay)
        base_size = 0
        fields = {}
        parent = getattr(class_symbol, "parent_class", None)
        if parent:
            parent_layout = self.define_class_layout(parent)
            if parent_layout:
                base_size = parent_layout["size"]
                fields.update(parent_layout["fields"])

        # Alinear a 4 bytes
        def _align4(n): 
            return n if n % 4 == 0 else n + (4 - (n % 4))

        offset = _align4(base_size)
        # Atributos propios
        for attr_name, attr_sym in class_symbol.attributes.items():
            sz = self.get_type_size(attr_sym.type) if getattr(attr_sym, "type", None) else 4
            offset = _align4(offset)
            fields[attr_name] = {"offset": offset, "type": getattr(attr_sym, "type", None)}
            offset += sz

        layout = {"size": offset, "fields": fields}
        self.class_layouts[name] = layout
        return layout

    def instantiate_object(self, class_name):
        """
        Emite TAC para crear una nueva instancia:
        - Reserva memoria en heap usando el layout de la clase
        - Devuelve un temporal con la dirección base de la instancia
        """
        layout = self.class_layouts.get(class_name)
        if not layout:
            # Si aún no se definió, crear layout vacío (fallback) para no romper
            layout = {"size": 0, "fields": {}}
            self.class_layouts[class_name] = layout

        addr = self.memory_manager.allocate_object(class_name, layout["size"])
        temp = self.new_temp()
        # Guardamos la dirección como inmediato (puede refactorizarse a un 'alloc' si deseas)
        self.emit_quad('=', f"0x{addr:04X}", None, temp)
        self.current_temp = temp
        return temp

    def property_address(self, base_temp, class_name, member_name):
        """
        Calcula la dirección (base + offset) de un atributo de objeto.
        CRÍTICO: base_temp DEBE ser el temporal que contiene la dirección del objeto
        """
        # Validación estricta
        if not base_temp or not isinstance(base_temp, str):
            raise Exception(f"property_address: base_temp inválido '{base_temp}'")
        
        layout = self.class_layouts.get(class_name, {})
        if not layout:
            raise Exception(f"Layout de clase '{class_name}' no existe")
        
        fields = layout.get("fields", {})
        info = fields.get(member_name)
        
        if not info:
            raise Exception(f"Atributo '{member_name}' no existe en clase '{class_name}'")
        
        off = info["offset"]
        addr_temp = self.new_temp()
        
        # CRÍTICO: base_temp YA contiene la dirección del objeto
        # Solo sumamos el offset
        self.emit_quad('+', base_temp, str(off), addr_temp,
                    comment=f"Address of {class_name}.{member_name}")
        
        return addr_temp
    
    def load_this_pointer(self, ctx=None):
        """
        Carga el puntero 'this' desde el parámetro oculto __this en FP[0]
        Debe llamarse al inicio de cada acceso a miembro en métodos
        """
        this_temp = self.new_temp()
        self.emit_quad('@', 'FP[0]', None, this_temp, 
                    comment="Load __this pointer")
        self.mark_temp_used(this_temp)  # Proteger de reutilización
        return this_temp

    def generate_property_load(self, base_temp, class_name, member_name, ctx=None):
        """
        Carga el valor de un atributo del objeto: result = [base + offset]
        """
        if not base_temp or base_temp == 'None':
            raise Exception(f"Base temporal inválida para {class_name}.{member_name}")
        
        if class_name not in self.class_layouts:
            raise Exception(f"Layout de clase '{class_name}' no definido")
        
        # CAMBIO: property_address YA calcula base + offset
        addr_temp = self.property_address(base_temp, class_name, member_name)
        result_temp = self.new_temp()
        
        # Load indirecto: result = [addr]
        self.emit_quad('[]', addr_temp, None, result_temp, 
            comment=f"Load {class_name}.{member_name}")
        self.current_temp = result_temp
        return result_temp

    def generate_property_store(self, base_temp, class_name, member_name, value_temp, ctx=None):
        """
        Almacena un valor en un atributo del objeto: [base + offset] = value
        """
        if not base_temp or base_temp == 'None':
            raise Exception(f"Base temporal inválida para {class_name}.{member_name}")
        
        if class_name not in self.class_layouts:
            raise Exception(f"Layout de clase '{class_name}' no definido")
        
        # CAMBIO: property_address calcula base + offset
        addr_temp = self.property_address(base_temp, class_name, member_name)
        
        # Store indirecto: [addr] = value
        self.emit_quad('[]=', value_temp, None, addr_temp,
            comment=f"Store {class_name}.{member_name}")
        return addr_temp

    def generate_method_call(self, this_temp, class_name, method_name, arguments, ctx=None):
        """
        Llamada a método de instancia:
        - Empuja '__this' y luego los argumentos
        - call FUNC_<method_name> (ClassName)
        - Limpia la pila y hace pop del valor de retorno
        """
        func_key = self._method_key(class_name, method_name)
    
        ar_design = self.get_ar_design(func_key)
        if not ar_design:
            ar_design = self.create_ar_design(func_key)
            ar_design.add_parameter('__this', None)
        
        # 🔍 DEBUG
        print(f"\n=== Llamada a {class_name}.{method_name} ===")
        print(f"  this_temp: {this_temp}")
        print(f"  args: {arguments}")
        
        # Push en orden: args reverso, luego this
        for arg in reversed(arguments or []):
            self.emit_quad('push', arg, None, None)
        
        self.emit_quad('push', this_temp, None, None, 
                    comment=f"Push __this (será FP[0])")
        
        func_label = self._method_label(class_name, method_name)
        self.emit_quad('call', None, None, func_label,
            comment=f"Call {class_name}.{method_name}")
        
        total = ((len(arguments) or 0) + 1) * 4
        self.emit_quad('add', 'SP', str(total), 'SP')
        
        result_temp = self.new_temp()
        self.emit_quad('pop', None, None, result_temp)
        self.current_temp = result_temp
        return result_temp

    def _method_key(self, class_name: str, method_name: str) -> str:
        """Clave única para AR/allocs de un método de clase."""
        return f"{class_name}::{method_name}"

    def _method_label(self, class_name: str, method_name: str) -> str:
        """Etiqueta visible en TAC para un método de clase."""
        return f"FUNC_{method_name} ({class_name})"

