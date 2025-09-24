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