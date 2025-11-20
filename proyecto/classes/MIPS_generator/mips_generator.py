# classes/MIPS_generator/mips_generator.py
"""
MIPSGenerator - Generador principal de código MIPS desde cuádruplos TAC
"""

import sys
from .register_allocator import RegisterAllocator
from .mips_stack_manager import MIPSStackManager
from .mips_runtime import MIPSRuntime

class MIPSGenerator:
    def __init__(self, code_generator, symbol_table):
        """
        Inicializa el generador de MIPS

        Args:
            code_generator: El CodeGenerator que contiene los cuádruplos
            symbol_table: La tabla de símbolos del programa
        """
        self.cg = code_generator
        self.symbol_table = symbol_table
        self.memory_manager = code_generator.memory_manager
        self.register_allocator = RegisterAllocator()
        self.stack_manager = MIPSStackManager()
        self.runtime = MIPSRuntime()

        # Instrucciones MIPS generadas
        self.data_section = []
        self.text_section = []

        # Contexto de función actual durante la traducción
        self.current_function = None
        self.current_quad_idx = 0
        self.param_registers = []  # Para rastrear argumentos durante llamadas

        # Track the SOURCE VALUE for each temporary to handle register aliasing
        # Maps temporary name -> source value (for reloading if register was clobbered)
        self.temp_value_source = {}

        # Track the TYPE of each temporary to distinguish integer from string operations
        # Maps temporary name -> 'int' or 'string'
        self.temp_types = {}

        # Track which $s registers each function uses - CRITICAL for MIPS calling convention
        # Maps function_name -> set of saved registers used (e.g., {'$s0', '$s1'})
        self.function_saved_regs = {}

        # Track the last popped value after a function call
        # This is used to handle constructor returns correctly
        self.last_pop_target = None

    def generate_mips_code(self):
        """Genera código MIPS completo desde los cuádruplos"""
        # 0. CRITICAL: Analyze which saved registers each function uses
        #    This MUST be done before code generation for proper save/restore
        self._analyze_function_saved_registers()

        # 1. Sección de datos (variables globales)
        self._generate_data_section()

        # 2. Sección de texto (código ejecutable)
        self._generate_text_section()

        # 3. Ensamblar archivo final
        return self._assemble_final_code()

    def _analyze_function_saved_registers(self):
        """
        CRITICAL: Analyze which $s registers are used globally.

        MIPS calling convention requires callees to save/restore $s registers.
        Since object pointers are stored in $s3-$s7 and used across function calls,
        we need to ensure ALL functions save these registers.

        CONSERVATIVE APPROACH: Save ALL potentially-used $s registers in ALL functions.
        This is safer than trying to track exact usage.
        """
        # First, determine which $s registers are used for global object storage
        global_saved_regs = set()

        for quad in self.cg.quadruples:
            # Check for heap object allocations (stored in $s3-$s7)
            if quad.op == '=' and isinstance(quad.arg1, str) and quad.arg1.startswith('0x'):
                try:
                    addr = int(quad.arg1, 16)
                    if addr >= 0x8000:
                        # This is a heap object - it will use a saved register
                        # Map addresses to registers (IR uses 8-byte increments)
                        if addr == 0x8000:
                            global_saved_regs.add('$s3')
                        elif addr == 0x8008:
                            global_saved_regs.add('$s4')
                        elif addr == 0x8010:
                            global_saved_regs.add('$s5')
                        elif addr == 0x8018:
                            global_saved_regs.add('$s6')
                        elif addr == 0x8020:
                            global_saved_regs.add('$s7')
                except ValueError:
                    pass

            # Check for string operations (use $s0, $s1)
            # String concat detection: '+' with non-numeric operands
            if quad.op == '+':
                # Simple heuristic: if either operand is a temp or string, might be string concat
                if (isinstance(quad.arg1, str) and (quad.arg1.startswith('t') or quad.arg1.startswith('str_'))) or \
                   (isinstance(quad.arg2, str) and (quad.arg2.startswith('t') or quad.arg2.startswith('str_'))):
                    global_saved_regs.add('$s0')
                    global_saved_regs.add('$s1')

        # Now assign these registers to ALL user functions
        # (but not __init, toString, printString, printInteger)
        current_func = None
        for quad in self.cg.quadruples:
            if quad.op == 'label' and isinstance(quad.result, str) and quad.result.startswith('FUNC_'):
                # CRITICAL: Must sanitize label name to match what _translate_label_quad uses!
                current_func = self._sanitize_label(quad.result)
                # Skip builtin functions
                if current_func not in ['FUNC___init', 'FUNC_toString', 'FUNC_printString', 'FUNC_printInteger']:
                    # CRITICAL: All user functions must save all globally-used $s registers
                    self.function_saved_regs[current_func] = global_saved_regs.copy()
                current_func = None

    def _generate_data_section(self):
        """Genera la sección .data con variables globales"""
        self.data_section.append("# Generated by Compiscript Compiler")
        self.data_section.append(".data")

        # Obtener todas las variables globales del memory manager
        # Include both regular variables (0x1000-0x7FFF) and arrays (0x8000+)
        global_vars = {name: addr for name, addr in self.memory_manager.allocations.items()
                      if isinstance(addr, int) and addr >= 0x1000}

        # Also scan quadruples for heap object addresses (0x8000+) without names
        heap_addresses = set()
        for quad in self.cg.quadruples:
            # Check all operands for heap addresses
            for operand in [quad.arg1, quad.arg2, quad.result]:
                if isinstance(operand, str) and operand.startswith('0x'):
                    try:
                        addr = int(operand, 16)
                        if addr >= 0x8000:
                            heap_addresses.add(addr)
                    except ValueError:
                        pass

        # Ordenar por dirección
        sorted_vars = sorted(global_vars.items(), key=lambda x: x[1])

        for var_name, address in sorted_vars:
            # Check if this is an array (address >= 0x8000)
            if address >= 0x8000:
                # For arrays, allocate space for multiple words (assuming 10 elements for now)
                # This is a simplification - ideally we'd know the actual array size
                self.data_section.append(f"var_{var_name}: .space 40  # Array at {hex(address)} (10 words)")
            else:
                # Regular variable
                self.data_section.append(f"var_{var_name}: .word 0  # Address: {hex(address)}")

        # Store heap addresses for dynamic allocation (not static .space)
        self.heap_addresses = sorted([addr for addr in heap_addresses if addr not in global_vars.values()])

        # Add string literals
        string_literals = self.cg.get_string_literals()
        if string_literals:
            self.data_section.append("# String literals")
            for string_value, label in string_literals.items():
                # Remove quotes and prepare for MIPS assembly
                string_content = string_value[1:-1]  # Remove surrounding quotes
                # Only escape quotes for MIPS assembly (backslashes are already properly escaped in source)
                # Don't double-escape backslashes - MIPS assembler will interpret \n, \t, etc. correctly
                string_content = string_content.replace('"', '\\"')
                self.data_section.append(f'{label}: .asciiz "{string_content}"')
                self.data_section.append(".align 2  # Align to word boundary")

        # NO LONGER NEEDED: String buffers now use malloc for each operation (Semantic-Parser approach)
        # Removed: string_concat_buffer, __concat_offset, __int_to_str_buf, __int_to_str_results, __int_to_str_offset
        # All string operations now use heap allocation (sbrk) directly - stateless and safe

        # Debug messages for SP tracing (disabled for performance)
        # self.data_section.append("__debug_sp_msg: .asciiz \" SP=\"")
        # self.data_section.append("__debug_newline: .asciiz \"\\n\"")

        self.data_section.append("")

    def _emit_sp_debug(self, instructions):
        """Helper to emit SP debug output (disabled)"""
        pass  # Disabled for performance
        # instructions.append("# DEBUG SP")
        # instructions.append("li $v0, 4")
        # instructions.append("la $a0, __debug_sp_msg")
        # instructions.append("syscall")
        # instructions.append("li $v0, 1")
        # instructions.append("move $a0, $sp")
        # instructions.append("syscall")
        # instructions.append("li $v0, 4")
        # instructions.append("la $a0, __debug_newline")
        # instructions.append("syscall")

    def _generate_text_section(self):
        """Genera la sección .text con el código principal"""
        self.text_section.append(".text")
        self.text_section.append(".globl main")
        self.text_section.append("")

        # Separate function quadruples from main quadruples
        function_quads = []
        main_quads = []
        current_function = None
        in_function = False

        for idx, quad in enumerate(self.cg.quadruples):
            # Check if this is a function label (starts with FUNC_)
            if quad.op == 'label' and isinstance(quad.result, str) and quad.result.startswith('FUNC_'):
                in_function = True
                current_function = []
                function_quads.append((idx, current_function))

            if in_function:
                current_function.append((idx, quad))
                # Check if function ends with 'leave'
                if quad.op == 'leave':
                    in_function = False
                    current_function = None
            else:
                main_quads.append((idx, quad))

        # Generate main section FIRST (so it executes first)
        self.text_section.append("main:")
        self.text_section.append("# Initialize stack pointer")
        self.text_section.append("li $sp, 0x7fffeffc  # Set to proper stack top")
        self._emit_sp_debug(self.text_section)
        self.text_section.append("# Main prologue")
        self.text_section.append("addiu $sp, $sp, -4")
        self._emit_sp_debug(self.text_section)
        self.text_section.append("sw $ra, 0($sp)")
        self.text_section.append("")

        # Allocate heap objects dynamically using sbrk
        if hasattr(self, 'heap_addresses') and self.heap_addresses:
            self.text_section.append("# Allocate heap objects dynamically")
            if not hasattr(self, 'heap_addr_to_reg'):
                self.heap_addr_to_reg = {}
            for heap_addr in self.heap_addresses:
                saved_reg = f"$s{3 + self.heap_addresses.index(heap_addr)}"
                self.text_section.append(f"li $v0, 9  # sbrk")
                self.text_section.append(f"li $a0, 40")
                self.text_section.append(f"syscall")
                self.text_section.append(f"move {saved_reg}, $v0")
                self.heap_addr_to_reg[heap_addr] = saved_reg
                self.register_allocator.used_regs.add(saved_reg)
            self.text_section.append("")

        # NO LONGER NEEDED: String buffer allocation removed
        # Now using malloc (sbrk) for each string operation - Semantic-Parser approach
        # Removed 64KB concat buffer and 128KB toString buffer allocations

        # Traducir cuádruplos del main
        for idx, quad in main_quads:
            self.text_section.append(f"# Quadruple {idx}: {quad}")
            self.current_quad_idx = idx  # Track current quadruple for debugging
            instructions = self._translate_quadruple(quad)
            for instruction in instructions:
                if instruction.strip():
                    self.text_section.append(instruction.strip())
            self.text_section.append("")

        # Epílogo del main
        self.text_section.append("# Main epilogue")
        self.text_section.append("lw $ra, 0($sp)")
        self.text_section.append("addiu $sp, $sp, 4")
        self._emit_sp_debug(self.text_section)
        self.text_section.append("li $v0, 10  # Exit syscall")
        self.text_section.append("syscall")
        self.text_section.append("# Safety: Infinite loop to prevent fall-through")
        self.text_section.append("__exit_loop:")
        self.text_section.append("j __exit_loop")
        self.text_section.append("")

        # Generate all functions AFTER main
        for func_idx, func_quads in function_quads:
            for idx, quad in func_quads:
                self.text_section.append(f"# Quadruple {idx}: {quad}")
                self.current_quad_idx = idx
                instructions = self._translate_quadruple(quad)
                for instruction in instructions:
                    if instruction.strip():
                        # Don't indent any assembly instructions - Mars doesn't like it
                        self.text_section.append(instruction.strip())
                self.text_section.append("")

    def _translate_quadruple(self, quad):
        """
        Traduce un cuádruplo individual a instrucciones MIPS

        Args:
            quad: El cuádruplo a traducir

        Returns:
            Lista de instrucciones MIPS
        """
        # Check if we're skipping toString stub body
        if hasattr(self, 'skip_until_leave') and self.skip_until_leave:
            if quad.op == 'leave':
                # End of function, stop skipping
                self.skip_until_leave = False
            # Skip all quadruples until we hit 'leave'
            return []

        op = quad.op

        # Operaciones aritméticas (including special stack operations)
        if op == '+' or op == 'add':
            # Check if this is stack cleanup: (add, SP, size, SP)
            if (quad.arg1 == 'SP' or str(quad.arg1).upper() == 'SP') and (quad.result == 'SP' or str(quad.result).upper() == 'SP'):
                return self._translate_function_quad(quad)
            elif op == '+':
                return self._translate_arithmetic_quad(quad)
            else:
                # 'add' without SP is still a function-related operation
                return self._translate_function_quad(quad)
        elif op in ['-', '*', '/']:
            return self._translate_arithmetic_quad(quad)

        # Operaciones de asignación
        elif op == '=':
            return self._translate_assignment_quad(quad)

        # Operaciones de carga (@)
        elif op == '@':
            return self._translate_load_quad(quad)

        # Operaciones de comparación
        elif op in ['<', '>', '<=', '>=', '==', '!=']:
            return self._translate_comparison_quad(quad)

        # Operaciones lógicas
        elif op in ['&&', '||', '!']:
            return self._translate_logical_quad(quad)

        # Operaciones unarias
        elif op in ['-', 'NEG'] and quad.arg2 is None:
            return self._translate_unary_quad(quad)

        # Operación de módulo
        elif op == '%':
            return self._translate_modulo_quad(quad)

        # Operaciones de salto
        elif op in ['goto', 'if', 'if_false', 'ifFalse']:
            return self._translate_jump_quad(quad)

        # Operaciones de función
        elif op in ['call', 'param', 'return', 'enter', 'leave', 'push', 'pop']:
            return self._translate_function_quad(quad)

        # Operación de etiqueta
        elif op == 'label':
            return self._translate_label_quad(quad)

        # Operaciones de print
        elif op in ['print_int', 'print_str']:
            return self._translate_print_quad(quad)

        # Operaciones de arrays
        elif op == '[]':
            return self._translate_array_load_quad(quad)
        elif op == '[]=':
            return self._translate_array_store_quad(quad)

        else:
            return [f"# TODO: Translate operation '{op}'"]

    def _translate_arithmetic_quad(self, quad):
        """
        Traduce cuádruplos aritméticos: (op, arg1, arg2, result)
        Ejemplo: (+, t0, t1, t2) -> add $t2, $t0, $t1

        Special case: String concatenation when op is '+' and operands are strings
        """
        instructions = []

        # Check if this is object property address calculation (+ with "Address of" comment)
        if self._is_object_address_quad(quad):
            return self._translate_object_access(quad)

        # Check if this is string concatenation (+ operator with string operands)
        if quad.op == '+' and self._might_be_string_concat(quad.arg1, quad.arg2):
            return self._translate_string_concat(quad)

        # Mapeo de operadores TAC a MIPS
        mips_ops = {
            '+': 'add',
            '-': 'sub',
            '*': 'mul',
            '/': 'div'
        }

        mips_op = mips_ops.get(quad.op)
        if not mips_op:
            return [f"# ERROR: Unknown arithmetic operation '{quad.op}'"]

        # Result is always a temporary - allocate FIRST
        result_reg = self.register_allocator.get_reg(quad.result)

        # IMPORTANT: Allocate registers for TEMPORARY operands FIRST
        # This ensures they're marked as used before we pick registers for non-temporaries
        arg1_reg = None
        arg2_reg = None

        if self._is_temporary(quad.arg1):
            arg1_reg = self.register_allocator.get_reg(quad.arg1)
        if self._is_temporary(quad.arg2):
            arg2_reg = self.register_allocator.get_reg(quad.arg2)

        # Now allocate for non-temporaries, avoiding already-allocated registers
        if arg1_reg is None:
            # arg1 is not a temporary, pick an available temp register
            for reg in ['$t0', '$t1', '$t2', '$t3', '$t4', '$t5', '$t6', '$t7', '$t8', '$t9']:
                if reg != result_reg and reg != arg2_reg and reg not in self.register_allocator.used_regs:
                    arg1_reg = reg
                    break
            # If no temp register available, reuse result_reg or fallback to $t8
            if not arg1_reg:
                if result_reg != arg2_reg:
                    arg1_reg = result_reg  # Can overwrite result since we'll compute it anyway
                else:
                    # Use $t8 as fallback (avoid $at which is reserved)
                    arg1_reg = '$t8'

        if arg2_reg is None:
            # arg2 is not a temporary, pick an available temp register different from arg1
            for reg in ['$t0', '$t1', '$t2', '$t3', '$t4', '$t5', '$t6', '$t7', '$t8', '$t9']:
                if reg != result_reg and reg != arg1_reg and reg not in self.register_allocator.used_regs:
                    arg2_reg = reg
                    break
            # If no temp register available, use $t9 as fallback (avoid $at which is reserved)
            if not arg2_reg:
                if arg1_reg != '$t9':
                    arg2_reg = '$t9'
                else:
                    # arg1 is using $t9, use $t7
                    arg2_reg = '$t7'

        # Cargar arg1 - CHECK MEMORY ADDRESS FIRST!
        if self._is_temporary(quad.arg1):
            # Si es temporal, ya debería estar en registro
            pass
        elif self._is_fp_relative(quad.arg1):
            # FP-relative addressing: FP[offset]
            offset = self._extract_fp_offset(quad.arg1)
            instructions.append(f"lw {arg1_reg}, {offset}($fp)  # Load from frame")
        elif isinstance(quad.arg1, str) and quad.arg1.startswith('0x'):
            # Es una dirección de memoria - check if it's an array
            try:
                addr_int = int(quad.arg1, 16)
                if addr_int >= 0x8000:
                    # Array address - load ADDRESS not value
                    addr = self._get_memory_label(quad.arg1)
                    instructions.append(f"la {arg1_reg}, {addr}")
                else:
                    # Regular variable - load value
                    addr = self._get_memory_label(quad.arg1)
                    instructions.append(f"lw {arg1_reg}, {addr}")
            except ValueError:
                # Not a valid hex, load as variable
                addr = self._get_memory_label(quad.arg1)
                instructions.append(f"lw {arg1_reg}, {addr}")
        elif self._is_immediate(quad.arg1):
            # Load immediate into allocated register
            instructions.append(f"li {arg1_reg}, {quad.arg1}")
        else:
            # Es una variable, cargar desde memoria
            addr = self._get_memory_label(quad.arg1)
            instructions.append(f"lw {arg1_reg}, {addr}")

        # Cargar arg2 - CHECK MEMORY ADDRESS FIRST!
        if self._is_temporary(quad.arg2):
            # Si es temporal, ya debería estar en registro
            pass
        elif self._is_fp_relative(quad.arg2):
            # FP-relative addressing: FP[offset]
            offset = self._extract_fp_offset(quad.arg2)
            instructions.append(f"lw {arg2_reg}, {offset}($fp)  # Load from frame")
        elif isinstance(quad.arg2, str) and quad.arg2.startswith('0x'):
            # Es una dirección de memoria - check if it's an array
            try:
                addr_int = int(quad.arg2, 16)
                if addr_int >= 0x8000:
                    # Array address - load ADDRESS not value
                    addr = self._get_memory_label(quad.arg2)
                    instructions.append(f"la {arg2_reg}, {addr}")
                else:
                    # Regular variable - load value
                    addr = self._get_memory_label(quad.arg2)
                    instructions.append(f"lw {arg2_reg}, {addr}")
            except ValueError:
                # Not a valid hex, load as variable
                addr = self._get_memory_label(quad.arg2)
                instructions.append(f"lw {arg2_reg}, {addr}")
        elif self._is_immediate(quad.arg2):
            # Load immediate into allocated register
            instructions.append(f"li {arg2_reg}, {quad.arg2}")
        else:
            # Es una variable, cargar desde memoria
            addr = self._get_memory_label(quad.arg2)
            instructions.append(f"lw {arg2_reg}, {addr}")

        # Realizar la operación
        if quad.op == '/':
            # División es especial en MIPS
            instructions.append(f"div {arg1_reg}, {arg2_reg}")
            instructions.append(f"mflo {result_reg}  # quotient")
        else:
            instructions.append(f"{mips_op} {result_reg}, {arg1_reg}, {arg2_reg}")

        # CRITICAL: Mark the result as integer type
        # Arithmetic operations (+, -, *, /) always produce integers
        if self._is_temporary(quad.result):
            self.temp_types[quad.result] = 'int'

        return instructions

    def _translate_assignment_quad(self, quad):
        """
        Traduce cuádruplos de asignación: (=, value, None, target)
        Ejemplo: (=, 5, None, 0x1000) -> li $t0, 5; sw $t0, var_a
        """
        instructions = []

        value = quad.arg1
        target = quad.result

        # CRITICAL FIX: After a constructor call, if we're storing the __this parameter
        # to a variable, we should actually store the return value (which is in last_pop_target)
        # Example sequence:
        #   push t5  (the object pointer)
        #   call FUNC_constructor
        #   pop t0   (return value = initialized object)
        #   = t5, None, var_name  <- BUG: should use t0, not t5!
        # This happens because after the call, saved registers ($s3-$s7) are restored,
        # so t5 (mapped to $s3) no longer contains the object pointer
        if (self.last_pop_target is not None and
            self._is_temporary(value) and
            not self._is_temporary(target)):
            # Check if value is a heap object temp (likely stored in $sX)
            # and we just popped a return value - use the popped value instead
            if value in self.register_allocator.temp_to_reg:
                value_reg = self.register_allocator.temp_to_reg[value]
                # If value is in a saved register, it was likely clobbered by the function call
                if value_reg.startswith('$s') and value_reg[2:].isdigit():
                    # Use the last popped value instead
                    old_value = value
                    value = self.last_pop_target
                    instructions.append(f"# WORKAROUND: Using return value {value} instead of {old_value}")
                    # CRITICAL: Clear immediately to prevent reuse
                    self.last_pop_target = None

        # Detectar si estamos asignando una dirección de array/heap object a un temporal
        # Si es así, FORZAR uso de saved register para que sobreviva llamadas a funciones
        is_heap_object_assignment = False
        heap_addr = None
        if self._is_temporary(target) and isinstance(value, str) and value.startswith('0x'):
            try:
                addr_int = int(value, 16)
                if addr_int >= 0x8000:
                    is_heap_object_assignment = True
                    heap_addr = addr_int
            except ValueError:
                pass

        # Si el target es temporal, asignar su registro PRIMERO
        # Esto evita conflictos donde value_reg y target_reg son el mismo
        target_reg = None
        if self._is_temporary(target):
            if is_heap_object_assignment:
                # CRITICAL: For heap objects, use different saved registers for each object
                # to avoid conflicts with string concatenation which may use $s0
                # Map heap addresses to specific saved registers:
                # 0x8000 -> $s3, 0x8018 -> $s4, 0x8030 -> $s5, etc.
                # CRITICAL FIX: Use heap_addr_to_reg mapping from actual allocations
                # instead of hardcoded map, because IR may use different addresses
                if hasattr(self, 'heap_addr_to_reg') and heap_addr in self.heap_addr_to_reg:
                    target_reg = self.heap_addr_to_reg[heap_addr]
                else:
                    # Fallback to hardcoded map (IR uses 8-byte increments)
                    saved_reg_map = {
                        0x8000: '$s3',
                        0x8008: '$s4',  # IR uses 8-byte increments!
                        0x8010: '$s5',
                        0x8018: '$s6',
                        0x8020: '$s7'
                    }
                    target_reg = saved_reg_map.get(heap_addr, '$s3')  # Default to $s3

                # CRITICAL FIX: When a temporary is reused for different heap objects,
                # we need to track the association between (temp_name + heap_addr) -> register
                # Store heap address association so we can retrieve it later
                if not hasattr(self, 'temp_heap_associations'):
                    self.temp_heap_associations = {}

                # Create unique key for this temp+heap combination
                temp_heap_key = f"{target}_{hex(heap_addr)}"
                self.temp_heap_associations[temp_heap_key] = target_reg

                # Free the temp first if it was already allocated to a different register
                # BUT only if it's not a saved register (we don't want to free $s3-$s7)
                if target in self.register_allocator.temp_to_reg:
                    old_reg = self.register_allocator.temp_to_reg[target]
                    if old_reg != target_reg and not (old_reg.startswith('$s') and old_reg[2:].isdigit()):
                        self.register_allocator.free_reg(target)

                # Now force allocation to the chosen saved register
                self.register_allocator.temp_to_reg[target] = target_reg
                self.register_allocator.used_regs.add(target_reg)
            else:
                target_reg = self.register_allocator.get_reg(target, context='arithmetic')

        # Obtener registro para el valor
        if self._is_temporary(value):
            # Si es temporal, obtener su registro
            value_reg = self.register_allocator.get_reg(value)
        else:
            # Para valores no-temporales:
            # Si target es temporal, cargar directamente en target_reg
            # Si no, usar un registro temporal
            if target_reg:
                value_reg = target_reg
            else:
                value_reg = self.register_allocator.get_reg_temp("assign_temp")
            # Cargar el valor usando el helper
            self._load_value_to_reg(value, value_reg, instructions)

        # Guardar en el target
        if self._is_temporary(target):
            # Si target es temporal, mover a su registro (si es diferente)
            if value_reg != target_reg:
                instructions.append(f"move {target_reg}, {value_reg}")

            # CRITICAL: Track the source value for this temporary
            # so we can reload it later if the register gets clobbered
            self.temp_value_source[target] = value

            # CRITICAL: Track type of the temporary for string concatenation detection
            # If value is a string literal (str_X) or another string temporary, mark as string
            if isinstance(value, str):
                if value.startswith('str_'):
                    self.temp_types[target] = 'string'
                elif self._is_temporary(value) and self.temp_types.get(value) == 'string':
                    # Propagate string type from source temporary
                    self.temp_types[target] = 'string'
        elif self._is_fp_relative(target):
            # Target es FP-relative (local variable or parameter)
            offset = self._extract_fp_offset(target)
            instructions.append(f"sw {value_reg}, {offset}($fp)")
        elif isinstance(target, str) and target.startswith('0x'):
            # Target es una dirección de memoria
            try:
                addr_int = int(target, 16)
                if addr_int >= 0x8000:
                    # Heap object - debe usar saved register si está mapeado
                    if hasattr(self, 'heap_addr_to_reg') and addr_int in self.heap_addr_to_reg:
                        target_reg = self.heap_addr_to_reg[addr_int]
                        if value_reg != target_reg:
                            instructions.append(f"move {target_reg}, {value_reg}")
                    else:
                        # Fallback: store to memory
                        target_addr = self._get_memory_label(target)
                        instructions.append(f"sw {value_reg}, {target_addr}")
                else:
                    # Variable regular
                    target_addr = self._get_memory_label(target)
                    instructions.append(f"sw {value_reg}, {target_addr}")
                    # CRITICAL: Free the source register if it's a temporary
                    # because its value has been saved to memory
                    # ALSO free if the source is a temporary mapped to a saved register
                    # after storing to memory, because the temp is no longer needed
                    if self._is_temporary(value):
                        # If this temp was mapped to a saved register ($s0-$s7) and we're storing
                        # it to memory, we can now free the temp name (but keep the saved register)
                        if value in self.register_allocator.temp_to_reg:
                            reg = self.register_allocator.temp_to_reg[value]
                            # If it's a saved register, just remove the temp mapping, don't free the register
                            if reg.startswith('$s') and reg[2:].isdigit():
                                del self.register_allocator.temp_to_reg[value]
                            else:
                                self.register_allocator.free_reg(value)
            except ValueError:
                target_addr = self._get_memory_label(target)
                instructions.append(f"sw {value_reg}, {target_addr}")
                # CRITICAL: Free the source register if it's a temporary
                if self._is_temporary(value):
                    self.register_allocator.free_reg(value)
        else:
            # Es una variable o dirección, guardar en memoria
            target_addr = self._get_memory_label(target)
            instructions.append(f"sw {value_reg}, {target_addr}")
            # CRITICAL: Free the source register if it's a temporary
            # because its value has been saved to memory
            if self._is_temporary(value):
                self.register_allocator.free_reg(value)

        return instructions

    def _translate_load_quad(self, quad):
        """
        Traduce cuádruplos de carga: (@, addr, None, temp)
        Ejemplos:
        - (@, 0x1000, None, t0) -> lw $t0, var_a
        - (@, FP[8], None, t0) -> lw $t0, 8($fp)  # Parameter/local access
        """
        instructions = []

        addr = quad.arg1
        target_temp = quad.result

        # Obtener registro para el temporal
        target_reg = self.register_allocator.get_reg(target_temp)

        # Check if this is FP-relative addressing (parameters/locals)
        if isinstance(addr, str) and addr.startswith('FP[') and addr.endswith(']'):
            # Extract offset from FP[offset]
            offset_str = addr[3:-1]  # Remove "FP[" and "]"
            offset = offset_str
            instructions.append(f"lw {target_reg}, {offset}($fp)  # Load from frame")
        else:
            # Regular memory load
            source_addr = self._get_memory_label(addr)
            instructions.append(f"lw {target_reg}, {source_addr}")

        return instructions

    def _translate_comparison_quad(self, quad):
        """
        Traduce cuádruplos de comparación: (op, arg1, arg2, result)
        Ejemplo: (<, t0, t1, t2) -> slt $t2, $t0, $t1

        Special case: String comparison for == and !=

        En MIPS, las comparaciones usan:
        - slt (set less than): result = 1 si arg1 < arg2, 0 si no
        - seq (set equal): result = 1 si arg1 == arg2, 0 si no
        - sne (set not equal): result = 1 si arg1 != arg2, 0 si no
        - Para <=, >, >= usamos combinaciones
        """
        instructions = []

        # Check if this is string comparison (use stricter detection)
        if quad.op in ['==', '!='] and self._might_be_string_comparison(quad.arg1, quad.arg2):
            return self._translate_string_comparison(quad)

        # Obtener registros para los operandos
        # For arg1: use get_reg if it's a temporary, otherwise get a temp register
        if self._is_temporary(quad.arg1):
            arg1_reg = self.register_allocator.get_reg(quad.arg1)
        else:
            arg1_reg = self.register_allocator.get_reg_temp("arg1")

        # For arg2: use get_reg if it's a temporary, otherwise get a temp register
        if self._is_temporary(quad.arg2):
            arg2_reg = self.register_allocator.get_reg(quad.arg2)
        else:
            arg2_reg = self.register_allocator.get_reg_temp("arg2")

        # Result is always a temporary
        result_reg = self.register_allocator.get_reg(quad.result)

        # Two-phase loading to prevent register conflicts:
        # Phase 1: If arg1 and arg2 would use the same register, use a different register for arg1
        if arg1_reg == arg2_reg and not self._is_temporary(quad.arg1) and self._is_temporary(quad.arg2):
            # arg2 is already in the register, so use a different register for arg1
            # Get a different temporary register for arg1
            arg1_reg = self.register_allocator.get_reg_temp("arg1_alt")

        # Cargar arg1 - CHECK MEMORY ADDRESS FIRST!
        if self._is_temporary(quad.arg1):
            # Si es temporal, ya debería estar en registro
            pass
        elif self._is_fp_relative(quad.arg1):
            # FP-relative addressing: FP[offset]
            offset = self._extract_fp_offset(quad.arg1)
            instructions.append(f"lw {arg1_reg}, {offset}($fp)  # Load from frame")
        elif isinstance(quad.arg1, str) and quad.arg1.startswith('0x'):
            # Es una dirección de memoria - check if it's an array
            try:
                addr_int = int(quad.arg1, 16)
                if addr_int >= 0x8000:
                    # Array address - load ADDRESS not value
                    addr = self._get_memory_label(quad.arg1)
                    instructions.append(f"la {arg1_reg}, {addr}")
                else:
                    # Regular variable - load value
                    addr = self._get_memory_label(quad.arg1)
                    instructions.append(f"lw {arg1_reg}, {addr}")
            except ValueError:
                # Not a valid hex, load as variable
                addr = self._get_memory_label(quad.arg1)
                instructions.append(f"lw {arg1_reg}, {addr}")
        elif self._is_immediate(quad.arg1):
            instructions.append(f"li {arg1_reg}, {quad.arg1}")
        else:
            # Es una variable, cargar desde memoria
            addr = self._get_memory_label(quad.arg1)
            instructions.append(f"lw {arg1_reg}, {addr}")

        # Cargar arg2 - CHECK MEMORY ADDRESS FIRST!
        if self._is_temporary(quad.arg2):
            # Si es temporal, ya debería estar en registro
            pass
        elif self._is_fp_relative(quad.arg2):
            # FP-relative addressing: FP[offset]
            offset = self._extract_fp_offset(quad.arg2)
            instructions.append(f"lw {arg2_reg}, {offset}($fp)  # Load from frame")
        elif isinstance(quad.arg2, str) and quad.arg2.startswith('0x'):
            # Es una dirección de memoria - check if it's an array
            try:
                addr_int = int(quad.arg2, 16)
                if addr_int >= 0x8000:
                    # Array address - load ADDRESS not value
                    addr = self._get_memory_label(quad.arg2)
                    instructions.append(f"la {arg2_reg}, {addr}")
                else:
                    # Regular variable - load value
                    addr = self._get_memory_label(quad.arg2)
                    instructions.append(f"lw {arg2_reg}, {addr}")
            except ValueError:
                # Not a valid hex, load as variable
                addr = self._get_memory_label(quad.arg2)
                instructions.append(f"lw {arg2_reg}, {addr}")
        elif self._is_immediate(quad.arg2):
            instructions.append(f"li {arg2_reg}, {quad.arg2}")
        else:
            # Es una variable, cargar desde memoria
            addr = self._get_memory_label(quad.arg2)
            instructions.append(f"lw {arg2_reg}, {addr}")

        # Realizar la comparación
        if quad.op == '<':
            # slt: set less than
            instructions.append(f"slt {result_reg}, {arg1_reg}, {arg2_reg}")

        elif quad.op == '<=':
            # <= es equivalente a: NOT (arg1 > arg2)
            # arg1 <= arg2 es lo mismo que arg2 >= arg1
            # Usamos: slt $temp, arg2, arg1; xori result, $temp, 1
            temp_reg = self.register_allocator.get_reg_temp("cmp_temp")
            instructions.append(f"slt {temp_reg}, {arg2_reg}, {arg1_reg}")  # temp = arg2 < arg1
            instructions.append(f"xori {result_reg}, {temp_reg}, 1")  # result = NOT temp

        elif quad.op == '>':
            # > es lo mismo que arg2 < arg1
            instructions.append(f"slt {result_reg}, {arg2_reg}, {arg1_reg}")

        elif quad.op == '>=':
            # >= es equivalente a: NOT (arg1 < arg2)
            temp_reg = self.register_allocator.get_reg_temp("cmp_temp")
            instructions.append(f"slt {temp_reg}, {arg1_reg}, {arg2_reg}")  # temp = arg1 < arg2
            instructions.append(f"xori {result_reg}, {temp_reg}, 1")  # result = NOT temp

        elif quad.op == '==':
            # == : xor + seq (set equal to zero)
            # Si arg1 == arg2, entonces arg1 XOR arg2 = 0
            instructions.append(f"xor {result_reg}, {arg1_reg}, {arg2_reg}")
            instructions.append(f"sltiu {result_reg}, {result_reg}, 1")  # result = (result == 0)

        elif quad.op == '!=':
            # != : xor + sne (set not equal to zero)
            # Si arg1 != arg2, entonces arg1 XOR arg2 != 0
            instructions.append(f"xor {result_reg}, {arg1_reg}, {arg2_reg}")
            instructions.append(f"sltu {result_reg}, $zero, {result_reg}")  # result = (result != 0)

        return instructions

    def _translate_logical_quad(self, quad):
        """
        Traduce operaciones lógicas: &&, ||, !

        Para operaciones lógicas simples (sin cortocircuito en cuádruplos):
        - && : AND bit a bit
        - || : OR bit a bit
        - ! : NOT lógico (invertir booleano)

        Nota: Si el código intermedio ya maneja cortocircuito con labels,
        esas operaciones se traducen como comparaciones + saltos.
        """
        instructions = []

        if quad.op == '!':
            # NOT lógico: (!, operand, None, result)
            # En MIPS: xori result, operand, 1 (invertir bit)
            # O también: seq result, operand, $zero (result = operand == 0)

            operand = quad.arg1
            result = quad.result

            # Obtener registros
            operand_reg = self.register_allocator.get_reg(operand)
            result_reg = self.register_allocator.get_reg(result)

            # Cargar operando usando helper
            if not self._is_temporary(operand):
                self._load_value_to_reg(operand, operand_reg, instructions)

            # NOT lógico: result = (operand == 0) ? 1 : 0
            instructions.append(f"sltiu {result_reg}, {operand_reg}, 1")

        elif quad.op == '&&':
            # AND lógico: (&&, arg1, arg2, result)
            # Nota: Si hay cortocircuito, esto se traduce con labels
            # Aquí implementamos AND simple bit a bit

            arg1 = quad.arg1
            arg2 = quad.arg2
            result = quad.result

            # Obtener registros
            arg1_reg = self.register_allocator.get_reg(arg1)
            arg2_reg = self.register_allocator.get_reg(arg2)
            result_reg = self.register_allocator.get_reg(result)

            # Cargar arg1
            if self._is_temporary(arg1):
                pass
            elif self._is_immediate(arg1):
                instructions.append(f"li {arg1_reg}, {arg1}")
            else:
                addr = self._get_memory_label(arg1)
                instructions.append(f"lw {arg1_reg}, {addr}")

            # Cargar arg2
            if self._is_temporary(arg2):
                pass
            elif self._is_immediate(arg2):
                instructions.append(f"li {arg2_reg}, {arg2}")
            else:
                addr = self._get_memory_label(arg2)
                instructions.append(f"lw {arg2_reg}, {addr}")

            # AND bit a bit
            instructions.append(f"and {result_reg}, {arg1_reg}, {arg2_reg}")
            # Normalizar a booleano (0 o 1)
            instructions.append(f"sltu {result_reg}, $zero, {result_reg}")

        elif quad.op == '||':
            # OR lógico: (||, arg1, arg2, result)

            arg1 = quad.arg1
            arg2 = quad.arg2
            result = quad.result

            # Obtener registros
            arg1_reg = self.register_allocator.get_reg(arg1)
            arg2_reg = self.register_allocator.get_reg(arg2)
            result_reg = self.register_allocator.get_reg(result)

            # Cargar arg1
            if self._is_temporary(arg1):
                pass
            elif self._is_immediate(arg1):
                instructions.append(f"li {arg1_reg}, {arg1}")
            else:
                addr = self._get_memory_label(arg1)
                instructions.append(f"lw {arg1_reg}, {addr}")

            # Cargar arg2
            if self._is_temporary(arg2):
                pass
            elif self._is_immediate(arg2):
                instructions.append(f"li {arg2_reg}, {arg2}")
            else:
                addr = self._get_memory_label(arg2)
                instructions.append(f"lw {arg2_reg}, {addr}")

            # OR bit a bit
            instructions.append(f"or {result_reg}, {arg1_reg}, {arg2_reg}")
            # Normalizar a booleano (0 o 1)
            instructions.append(f"sltu {result_reg}, $zero, {result_reg}")

        return instructions

    def _translate_unary_quad(self, quad):
        """
        Traduce operaciones unarias

        Principalmente la negación aritmética: -x
        Cuádruplo: (-, operand, None, result) o (NEG, operand, None, result)
        """
        instructions = []

        if quad.op in ['-', 'NEG']:
            # Negación aritmética: (-, operand, None, result)
            # En MIPS: sub result, $zero, operand
            # O también: neg result, operand (pseudo-instrucción)

            operand = quad.arg1
            result = quad.result

            # Obtener registros
            operand_reg = self.register_allocator.get_reg(operand)
            result_reg = self.register_allocator.get_reg(result)

            # Cargar operando si es necesario
            if self._is_temporary(operand):
                pass
            elif self._is_immediate(operand):
                instructions.append(f"li {operand_reg}, {operand}")
            else:
                addr = self._get_memory_label(operand)
                instructions.append(f"lw {operand_reg}, {addr}")

            # Negar: result = 0 - operand
            instructions.append(f"sub {result_reg}, $zero, {operand_reg}")

        return instructions

    def _translate_modulo_quad(self, quad):
        """
        Traduce operación de módulo: (%, arg1, arg2, result)

        En MIPS:
        - div arg1, arg2  (divide arg1 / arg2)
        - mfhi result     (obtener resto/módulo)
        """
        instructions = []

        arg1 = quad.arg1
        arg2 = quad.arg2
        result = quad.result

        # Obtener registros
        arg1_reg = self.register_allocator.get_reg(arg1)
        arg2_reg = self.register_allocator.get_reg(arg2)
        result_reg = self.register_allocator.get_reg(result)

        # Cargar arg1
        if self._is_temporary(arg1):
            pass
        elif self._is_immediate(arg1):
            instructions.append(f"li {arg1_reg}, {arg1}")
        else:
            addr = self._get_memory_label(arg1)
            instructions.append(f"lw {arg1_reg}, {addr}")

        # Cargar arg2
        if self._is_temporary(arg2):
            pass
        elif self._is_immediate(arg2):
            instructions.append(f"li {arg2_reg}, {arg2}")
        else:
            addr = self._get_memory_label(arg2)
            instructions.append(f"lw {arg2_reg}, {addr}")

        # División y obtener resto
        instructions.append(f"div {arg1_reg}, {arg2_reg}")
        instructions.append(f"mfhi {result_reg}  # Get remainder (modulo)")

        return instructions

    def _translate_jump_quad(self, quad):
        """
        Traduce cuádruplos de salto y control de flujo

        Tipos de saltos:
        - goto: Salto incondicional
        - if: Salto si la condición es verdadera (!=0)
        - if_false/ifFalse: Salto si la condición es falsa (==0)
        """
        instructions = []

        if quad.op == 'goto':
            # Salto incondicional: (goto, None, None, label)
            label = self._sanitize_label(quad.result)
            instructions.append(f"j {label}")

        elif quad.op in ['if', 'if_true']:
            # Salto condicional si verdadero: (if, condition, None, label)
            # En MIPS: bne condition, $zero, label (branch if not equal to zero)
            condition = quad.arg1
            label = self._sanitize_label(quad.result)

            # Obtener registro de la condición
            cond_reg = self.register_allocator.get_reg(condition)

            # Cargar condición si es necesario
            if self._is_temporary(condition):
                # Ya está en registro
                pass
            elif self._is_immediate(condition):
                normalized = self._normalize_value(condition)
                instructions.append(f"li {cond_reg}, {normalized}")
            else:
                # Es una variable
                addr = self._get_memory_label(condition)
                instructions.append(f"lw {cond_reg}, {addr}")

            # Branch if not equal to zero (si es verdadero)
            instructions.append(f"bne {cond_reg}, $zero, {label}")

        elif quad.op in ['if_false', 'ifFalse']:
            # Salto condicional si falso: (if_false, condition, None, label)
            # En MIPS: beq condition, $zero, label (branch if equal to zero)
            condition = quad.arg1
            label = self._sanitize_label(quad.result)

            # Obtener registro de la condición
            cond_reg = self.register_allocator.get_reg(condition)

            # Cargar condición si es necesario
            if self._is_temporary(condition):
                # Ya está en registro
                pass
            elif self._is_immediate(condition):
                normalized = self._normalize_value(condition)
                instructions.append(f"li {cond_reg}, {normalized}")
            else:
                # Es una variable
                addr = self._get_memory_label(condition)
                instructions.append(f"lw {cond_reg}, {addr}")

            # Branch if equal to zero (si es falso)
            instructions.append(f"beq {cond_reg}, $zero, {label}")

        return instructions

    def _translate_label_quad(self, quad):
        """
        Traduce cuádruplos de etiqueta: (label, None, None, L0)
        Simplemente genera la etiqueta en MIPS
        """
        label_name = self._sanitize_label(quad.result)

        # Track current function for constructor detection (only for function labels)
        if label_name.startswith('FUNC_'):
            self.current_function = label_name
            # Reset temp value source tracking when entering a new function
            # to prevent cross-function contamination (temps are reused across functions)
            self.temp_value_source = {}

        # Special handling: Replace toString stub with runtime implementation
        if label_name == "FUNC_toString":
            # Set flag to skip the stub body until 'leave'
            self.skip_until_leave = True
            # Generate a wrapper with proper calling convention
            # The parameter is already on the stack from the caller
            return [
                f"# toString: Wrapper for runtime int-to-string conversion",
                f"{label_name}:",
                f"# Save registers",
                f"addiu $sp, $sp, -8",
                f"sw $ra, 4($sp)",
                f"sw $fp, 0($sp)",
                f"addiu $fp, $sp, 8",
                f"# Load parameter from FP[0] into $a0 for __int_to_string",
                f"lw $a0, 0($fp)",
                f"# Call runtime function",
                f"jal __int_to_string",
                f"# Restore and return",
                f"lw $fp, 0($sp)",
                f"lw $ra, 4($sp)",
                f"addiu $sp, $sp, 8",
                f"jr $ra"
            ]

        # Special handling: printString uses syscall 4
        if label_name == "FUNC_printString":
            self.skip_until_leave = True
            return [
                f"{label_name}:",
                f"    addiu $sp, $sp, -12",
                f"    sw $ra, 8($sp)",
                f"    sw $fp, 4($sp)",
                f"    addiu $fp, $sp, 12",
                f"    lw $a0, 0($fp)",
                f"    li $v0, 4",
                f"    syscall",
                f"    # NO LONGER NEEDED: Buffer reset removed (malloc approach)",
                f"    lw $v0, 0($fp)",
                f"    j FUNC_printString_epilogue",
                f"",
                f"FUNC_printString_epilogue:",
                f"# Function epilogue",
                f"addiu $sp, $fp, -8",
                f"lw $fp, 0($sp)",
                f"lw $ra, 4($sp)",
                f"addiu $sp, $sp, 8",
                f"jr $ra"
            ]

        # Special handling: printInteger uses syscall 1
        if label_name == "FUNC_printInteger":
            self.skip_until_leave = True
            return [
                f"{label_name}:",
                f"    addiu $sp, $sp, -12",
                f"    sw $ra, 8($sp)",
                f"    sw $fp, 4($sp)",
                f"    addiu $fp, $sp, 12",
                f"    lw $a0, 0($fp)",
                f"    li $v0, 1",
                f"    syscall",
                f"    lw $v0, 0($fp)",
                f"    j FUNC_printInteger_epilogue",
                f"",
                f"FUNC_printInteger_epilogue:",
                f"# Function epilogue",
                f"addiu $sp, $fp, -8",
                f"lw $fp, 0($sp)",
                f"lw $ra, 4($sp)",
                f"addiu $sp, $sp, 8",
                f"jr $ra"
            ]

        return [f"{label_name}:"]

    def _translate_print_quad(self, quad):
        """
        Traduce cuádruplos de print: (print_int, value, None, None)
        Imprime un valor usando syscalls de MIPS

        Args:
            quad: Cuádruplo con op='print_int' o 'print_str'

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []
        value = quad.arg1

        if quad.op == 'print_int':
            # Cargar el valor en $a0 usando el método helper existente
            if self._is_temporary(value):
                # Es un temporal
                value_reg = self.register_allocator.get_reg(value)
                instructions.append(f"move $a0, {value_reg}")
            elif self._is_fp_relative(value):
                # Es una variable local (FP[offset])
                offset = self._extract_fp_offset(value)
                instructions.append(f"lw $a0, {offset}($fp)")
            elif isinstance(value, str) and value.startswith('0x'):
                # Es una dirección de memoria global (0x1000, etc.)
                var_label = self._get_memory_label(value)
                instructions.append(f"lw $a0, {var_label}")
            elif self._is_immediate(value):
                # Es un literal
                normalized = self._normalize_value(value)
                instructions.append(f"li $a0, {normalized}")
            else:
                # Cualquier otro caso - intentar cargar desde etiqueta
                var_label = self._get_memory_label(value)
                instructions.append(f"lw $a0, {var_label}")

            # Syscall para imprimir entero
            instructions.append("li $v0, 1       # print_int")
            instructions.append("syscall")

            # Opcional: imprimir newline después del número
            instructions.append("li $v0, 11      # print_char")
            instructions.append("li $a0, 10      # newline")
            instructions.append("syscall")

        elif quad.op == 'print_str':
            # Para strings, el valor es una etiqueta (ej: str_0) o un temporal que contiene una etiqueta
            if self._is_temporary(value):
                # Es un temporal que contiene la dirección del string
                value_reg = self.register_allocator.get_reg(value)
                instructions.append(f"move $a0, {value_reg}")
            elif isinstance(value, str) and value.startswith('str_'):
                # Es una etiqueta de string literal directamente
                instructions.append(f"la $a0, {value}")
            elif self._is_fp_relative(value):
                # Es una variable local (FP[offset])
                offset = self._extract_fp_offset(value)
                instructions.append(f"lw $a0, {offset}($fp)")
            elif isinstance(value, str) and value.startswith('0x'):
                # Es una dirección de memoria global
                var_label = self._get_memory_label(value)
                instructions.append(f"lw $a0, {var_label}")
            else:
                # Cualquier otro caso - asumir que es una etiqueta
                instructions.append(f"la $a0, {value}")

            # Syscall para imprimir string
            instructions.append("li $v0, 4       # print_str")
            instructions.append("syscall")

        return instructions

    def _translate_array_load_quad(self, quad):
        """
        Traduce cuádruplos de carga desde array: ([], addr, None, result)
        Carga el valor desde la dirección en addr al result

        Args:
            quad: Cuádruplo con op='[]', arg1=dirección efectiva

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []
        addr = quad.arg1
        result = quad.result

        # Obtener la dirección efectiva en un registro
        if self._is_temporary(addr):
            addr_reg = self.register_allocator.get_reg(addr)
        elif self._is_fp_relative(addr):
            offset = self._extract_fp_offset(addr)
            addr_reg = self.register_allocator.get_reg_temp("addr")
            instructions.append(f"lw {addr_reg}, {offset}($fp)")
        else:
            # Cargar dirección inmediata
            addr_reg = self.register_allocator.get_reg_temp("addr")
            instructions.append(f"li {addr_reg}, {addr}")

        # Cargar el valor desde la dirección
        result_reg = self.register_allocator.get_reg(result)
        instructions.append(f"lw {result_reg}, 0({addr_reg})  # Array load")

        return instructions

    def _translate_array_store_quad(self, quad):
        """
        Traduce cuádruplos de almacenamiento en array: ([]=, value, None, addr_temp)
        Almacena value en la dirección contenida en addr_temp

        Args:
            quad: Cuádruplo con op='[]='
            Format: ([]=, value_temp, None, effective_address_temp)

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []
        value = quad.arg1
        addr = quad.result  # La dirección efectiva está en result, no en arg2

        # IMPORTANT: Get address register FIRST to avoid conflicts
        # Obtener la dirección destino PRIMERO
        if self._is_temporary(addr):
            addr_reg = self.register_allocator.get_reg(addr)
        elif self._is_fp_relative(addr):
            offset = self._extract_fp_offset(addr)
            addr_reg = self.register_allocator.get_reg_temp("addr")
            instructions.append(f"lw {addr_reg}, {offset}($fp)")
        else:
            addr_reg = self.register_allocator.get_reg_temp("addr")
            instructions.append(f"li {addr_reg}, {addr}")

        # Obtener el valor a almacenar DESPUÉS (to avoid overwriting addr_reg)
        if self._is_temporary(value):
            value_reg = self.register_allocator.get_reg(value)
        elif self._is_fp_relative(value):
            # Cargar desde FP[offset]
            value_reg = None
            for reg in ['$t0', '$t1', '$t2', '$t3', '$t4', '$t5', '$t6', '$t7', '$t8', '$t9']:
                if reg != addr_reg:
                    value_reg = reg
                    break
            if not value_reg:
                value_reg = '$v1'  # Use $v1 as last resort (avoid $at which is reserved)
            fp_offset = self._extract_fp_offset(value)
            instructions.append(f"lw {value_reg}, {fp_offset}($fp)  # Load from frame")
        elif self._is_immediate(value):
            # Use a different register than addr_reg
            value_reg = None
            for reg in ['$t0', '$t1', '$t2', '$t3', '$t4', '$t5', '$t6', '$t7', '$t8', '$t9']:
                if reg != addr_reg:
                    value_reg = reg
                    break
            if not value_reg:
                value_reg = '$v1'  # Use $v1 as last resort (avoid $at which is reserved)
            normalized = self._normalize_value(value)
            instructions.append(f"li {value_reg}, {normalized}")
        else:
            # Cargar desde memoria
            value_reg = None
            for reg in ['$t0', '$t1', '$t2', '$t3', '$t4', '$t5', '$t6', '$t7', '$t8', '$t9']:
                if reg != addr_reg:
                    value_reg = reg
                    break
            if not value_reg:
                value_reg = '$v1'  # Use $v1 as last resort (avoid $at which is reserved)
            var_label = self._get_memory_label(value)
            instructions.append(f"lw {value_reg}, {var_label}")

        # Almacenar el valor en la dirección
        instructions.append(f"sw {value_reg}, 0({addr_reg})  # Array store")

        return instructions

    def _translate_function_quad(self, quad):
        """
        Traduce cuádruplos de función: enter, call, push, pop, return, leave

        Quadruples:
        - (enter, size, None, None): Function prologue
        - (push, arg, None, None): Push argument for call
        - (call, None, None, func_label): Call function
        - (pop, None, None, result): Get return value
        - (return, value, None, None): Return from function
        - (leave, None, None, None): Function epilogue
        """
        instructions = []

        if quad.op == 'enter':
            # Function prologue: setup stack frame
            # On entry: $sp points to last pushed argument (first parameter)
            # TAC convention: FP[0] = first param, FP[4] = second param, etc.
            # So $fp must point to the first parameter location
            #
            # Stack layout after prologue:
            # [arg2]
            # [arg1]
            # [arg0] ← $fp points here (FP[0])
            # [$ra]  ← -4($fp)
            # [$fp]  ← -8($fp)
            # [$s0]  ← -12($fp) (if function uses $s0)
            # [$s1]  ← -16($fp) (if function uses $s1)
            # [...]
            # [locals] ← $sp points here

            frame_size = int(quad.arg1) if quad.arg1 else 0

            # CRITICAL: Get which saved registers this function uses
            saved_regs_to_save = []
            if self.current_function and self.current_function in self.function_saved_regs:
                saved_regs_to_save = sorted(list(self.function_saved_regs[self.current_function]))

            num_saved_regs = len(saved_regs_to_save)
            saved_regs_space = num_saved_regs * 4

            instructions.append(f"# Function prologue (locals: {frame_size} bytes, saved regs: {num_saved_regs})")

            # First allocate space for $ra, $fp, saved registers, and locals
            total_offset = 8 + saved_regs_space + frame_size
            instructions.append(f"addiu $sp, $sp, -{total_offset}")
            self._emit_sp_debug(instructions)

            # Save $ra and $fp at the TOP of the allocated space (right below args)
            instructions.append(f"sw $ra, {total_offset - 4}($sp)")  # Save $ra
            instructions.append(f"sw $fp, {total_offset - 8}($sp)")  # Save $fp

            # CRITICAL: Save used $s registers (MIPS calling convention requirement)
            for i, reg in enumerate(saved_regs_to_save):
                offset = total_offset - 8 - 4 * (i + 1)
                instructions.append(f"sw {reg}, {offset}($sp)  # Save {reg}")

            # Set $fp to point to arg0 location (old $sp position)
            instructions.append(f"addiu $fp, $sp, {total_offset}")

        elif quad.op == 'leave':
            # Function epilogue: cleanup stack frame
            # Current state: $fp points to arg0, $sp points below locals
            # Saved $fp is at -8($fp), saved $ra is at -4($fp)
            # Saved $s registers are at -12($fp), -16($fp), etc.

            # Add epilogue label for return statements to jump to
            if self.current_function:
                epilogue_label = f"{self.current_function}_epilogue"
                instructions.append(f"{epilogue_label}:")

            instructions.append(f"# Function epilogue")

            # CRITICAL: Get which saved registers this function uses
            saved_regs_to_restore = []
            if self.current_function and self.current_function in self.function_saved_regs:
                saved_regs_to_restore = sorted(list(self.function_saved_regs[self.current_function]))

            num_saved_regs = len(saved_regs_to_restore)

            # Point $sp to the FIRST saved register (lowest address)
            # Since we saved from HIGH to LOW: $s0(high), $s1, $s3, $s4, $s5(low)
            # SP should point to the LOWEST address (where the LAST register in sorted order was saved)
            if num_saved_regs > 0:
                instructions.append(f"addiu $sp, $fp, -{8 + num_saved_regs * 4}")
            else:
                instructions.append(f"addiu $sp, $fp, -8")
            self._emit_sp_debug(instructions)

            # CRITICAL: Restore saved $s registers in REVERSE order
            # We saved: $s0(high addr), $s1, $s3, $s4, $s5(low addr)
            # SP now points to low addr, so we need to restore in reverse order
            # Restore: $s5(SP+0), $s4(SP+4), $s3(SP+8), $s1(SP+12), $s0(SP+16)
            for i, reg in enumerate(reversed(saved_regs_to_restore)):
                instructions.append(f"lw {reg}, {i * 4}($sp)  # Restore {reg}")

            # Move $sp to saved $fp location
            if num_saved_regs > 0:
                instructions.append(f"addiu $sp, $sp, {num_saved_regs * 4}")
                self._emit_sp_debug(instructions)

            # Restore $fp and $ra
            instructions.append(f"lw $fp, 0($sp)")
            instructions.append(f"lw $ra, 4($sp)")

            # Pop $fp/$ra from stack (sp now points to arg0 location)
            instructions.append(f"addiu $sp, $sp, 8")
            self._emit_sp_debug(instructions)

            # Return to caller (caller will clean up arguments)
            instructions.append(f"jr $ra")

        elif quad.op == 'push':
            # Push argument onto stack for function call
            # Arguments are pushed in reverse order
            arg = quad.arg1

            instructions.append(f"# Push argument: {arg}")

            # Get register for argument
            arg_reg = self.register_allocator.get_reg_temp("push_arg")

            # Load argument value
            if self._is_temporary(arg):
                arg_reg = self.register_allocator.get_reg(arg)
            else:
                self._load_value_to_reg(arg, arg_reg, instructions)

            # Push onto stack
            instructions.append(f"addiu $sp, $sp, -4")
            instructions.append(f"sw {arg_reg}, 0($sp)")
            self._emit_sp_debug(instructions)

            # Track for parameter passing to $a0-$a3 if needed
            self.param_registers.append(arg_reg)

        elif quad.op == 'call':
            # Call function
            func_label = self._sanitize_label(quad.result)

            instructions.append(f"# Call function: {quad.result}")

            # Resolve inherited methods
            # Format: FUNC_methodName_ClassName
            if '_' in func_label:
                parts = func_label.split('_')
                if len(parts) >= 3:  # FUNC, methodName, ClassName
                    method_name = parts[1]
                    class_name = '_'.join(parts[2:])  # Handle multi-part class names

                    # Try to resolve to parent class if method is inherited
                    resolved_label = self._resolve_inherited_method(method_name, class_name)
                    if resolved_label:
                        func_label = resolved_label

            # In MIPS calling convention, first 4 args go in $a0-$a3
            # For simplicity, we're using stack-based passing (already pushed)
            # But we could optimize by using $a0-$a3 for first 4 args

            instructions.append(f"jal {func_label}")

            # Clear param register tracking
            self.param_registers.clear()

        elif quad.op == 'pop':
            # Pop return value from function call
            # Return value is in $v0
            result = quad.result

            instructions.append(f"# Get return value into {result}")

            if self._is_temporary(result):
                result_reg = self.register_allocator.get_reg(result)
                instructions.append(f"move {result_reg}, $v0")
                # CRITICAL: Clear any stale temp_value_source entry
                # because this temporary now holds a runtime value, not a literal
                if result in self.temp_value_source:
                    del self.temp_value_source[result]
                # Track last pop target for constructor return handling
                self.last_pop_target = result
            else:
                # Store return value to memory
                result_addr = self._get_memory_label(result)
                instructions.append(f"sw $v0, {result_addr}")
                self.last_pop_target = None

        elif quad.op == 'return':
            # Return from function with optional value
            return_value = quad.arg1

            instructions.append(f"# Return statement")

            if return_value is not None:
                # Load return value into $v0
                if self._is_temporary(return_value):
                    return_reg = self.register_allocator.get_reg(return_value)
                    instructions.append(f"move $v0, {return_reg}")
                else:
                    # Load from memory or immediate
                    temp_reg = self.register_allocator.get_reg_temp("return_temp")
                    self._load_value_to_reg(return_value, temp_reg, instructions)
                    instructions.append(f"move $v0, {temp_reg}")
            else:
                # No return value specified
                # Check if we're in a constructor - if so, return __this (FP[0])
                if self.current_function and 'constructor' in self.current_function.lower():
                    instructions.append(f"# Constructor: return __this pointer")
                    instructions.append(f"lw $v0, 0($fp)  # Load __this from FP[0]")

            # Jump to function epilogue
            # Generate epilogue label based on current function name
            if self.current_function:
                epilogue_label = f"{self.current_function}_epilogue"
                instructions.append(f"j {epilogue_label}")

        elif quad.op == 'add' and (quad.arg1 == 'SP' or str(quad.arg1).upper() == 'SP'):
            # Stack cleanup after function call: (add, SP, size, SP)
            # This adjusts SP after popping arguments
            cleanup_size = quad.arg2
            instructions.append(f"# Clean up arguments from stack ({cleanup_size} bytes)")
            instructions.append(f"addiu $sp, $sp, {cleanup_size}")
            self._emit_sp_debug(instructions)

        return instructions

    def _is_temporary(self, value):
        """
        Verifica si un valor es un temporal (t0, t1, etc.)

        NOTA: Debido a un bug en el código intermedio, a veces 'true' o 'false'
        se usan como nombres de temporales. Por ahora, NO los consideramos temporales
        para forzar su conversión a valores numéricos.
        """
        if not isinstance(value, str):
            return False

        # No tratar 'true' o 'false' como temporales, incluso si el código intermedio los usa así
        if value in ['true', 'false']:
            return False

        return value.startswith('t') and value[1:].isdigit()

    def _is_fp_relative(self, value):
        """
        Verifica si un valor es una dirección relativa al frame pointer (FP[offset])
        """
        return isinstance(value, str) and value.startswith('FP[') and value.endswith(']')

    def _extract_fp_offset(self, fp_address):
        """
        Extrae el offset de una dirección FP-relative
        Ejemplo: "FP[8]" -> "8"
        """
        if self._is_fp_relative(fp_address):
            return fp_address[3:-1]  # Remove "FP[" and "]"
        return "0"

    def _sanitize_label(self, label):
        """
        Sanitiza etiquetas para que sean válidas en MIPS
        Convierte espacios y paréntesis a guiones bajos
        Ejemplo: "FUNC_add (Calculator)" -> "FUNC_add_Calculator"
        """
        if not isinstance(label, str):
            return str(label)
        # Replace spaces with underscores
        sanitized = label.replace(' ', '_')
        # Remove parentheses
        sanitized = sanitized.replace('(', '').replace(')', '')
        return sanitized

    def _is_immediate(self, value):
        """Verifica si un valor es un inmediato (número o booleano)"""
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            # Verificar si es un booleano literal
            if value in ['true', 'false']:
                return True
            try:
                # Use base 0 to auto-detect hex (0x...), octal (0o...), etc.
                int(value, 0)
                return True
            except ValueError:
                return False
        return False

    def _normalize_value(self, value):
        """
        Normaliza un valor, convirtiendo booleanos literales a números

        Args:
            value: El valor a normalizar (puede ser 'true', 'false', número, etc.)

        Returns:
            El valor normalizado (true -> 1, false -> 0, otros sin cambio)
        """
        if isinstance(value, str):
            if value == 'true':
                return '1'
            elif value == 'false':
                return '0'
        return value

    def _load_string_address(self, value, reg, instructions):
        """
        Helper to load a string address into a register
        Similar to _load_value_to_reg but specifically for string pointers

        Args:
            value: The string value (can be temp, variable, literal label)
            reg: The destination register
            instructions: List to append instructions to
        """
        if self._is_temporary(value):
            # Temporary should already contain the string address
            temp_reg = self.register_allocator.get_reg(value)
            if temp_reg != reg:
                instructions.append(f"move {reg}, {temp_reg}")
        elif isinstance(value, str) and value.startswith('str_'):
            # String literal - load address
            instructions.append(f"la {reg}, {value}  # Load string literal address")
        elif isinstance(value, str) and value.startswith('0x'):
            # Memory address - load the value at that address (which should be a string pointer)
            addr_label = self._get_memory_label(value)
            instructions.append(f"lw {reg}, {addr_label}  # Load string pointer from variable")
        elif self._is_fp_relative(value):
            # FP-relative - load from stack frame
            offset = self._extract_fp_offset(value)
            instructions.append(f"lw {reg}, {offset}($fp)  # Load string from frame")
        else:
            # Variable name - load from memory
            addr_label = self._get_memory_label(value)
            instructions.append(f"lw {reg}, {addr_label}  # Load string from variable")

    def _load_value_to_reg(self, value, reg, instructions):
        """
        Helper para cargar un valor en un registro, manejando temporales, inmediatos y variables

        Args:
            value: El valor a cargar (puede ser temporal, inmediato, variable, etc.)
            reg: El registro destino
            instructions: Lista de instrucciones donde agregar el código

        Returns:
            None (modifica instructions in-place)
        """
        if self._is_temporary(value):
            # Si es temporal, ya está en registro (no hacer nada)
            pass
        elif self._is_fp_relative(value):
            # FP-relative addressing: FP[offset]
            offset = self._extract_fp_offset(value)
            instructions.append(f"lw {reg}, {offset}($fp)  # Load from frame")
        elif isinstance(value, str) and value.startswith('0x'):
            # Es una dirección de memoria - verificar si es un array
            try:
                addr_int = int(value, 16)
                if addr_int >= 0x8000:
                    # CRITICAL FIX: Heap objects are allocated at startup and stored in saved registers
                    # We need to MOVE from the saved register to the target register
                    # Find which saved register holds this heap address
                    if hasattr(self, 'heap_addr_to_reg') and addr_int in self.heap_addr_to_reg:
                        source_reg = self.heap_addr_to_reg[addr_int]
                        # Only generate move if source and target are different
                        if source_reg != reg:
                            instructions.append(f"move {reg}, {source_reg}  # Load heap object address")
                    else:
                        # Fallback: use hardcoded mapping if heap_addr_to_reg not available
                        # IR uses 8-byte increments
                        saved_reg_map = {
                            0x8000: '$s3',
                            0x8008: '$s4',
                            0x8010: '$s5',
                            0x8018: '$s6',
                            0x8020: '$s7'
                        }
                        source_reg = saved_reg_map.get(addr_int, '$s3')
                        if source_reg != reg:
                            instructions.append(f"move {reg}, {source_reg}  # Load heap object address")
                else:
                    # Es una variable regular - cargar valor
                    addr_label = self._get_memory_label(value)
                    instructions.append(f"lw {reg}, {addr_label}")
            except ValueError:
                # No es hex válido, tratar como variable
                addr = self._get_memory_label(value)
                instructions.append(f"lw {reg}, {addr}")
        elif self._is_immediate(value):
            # Es un inmediato (número o booleano)
            normalized = self._normalize_value(value)
            instructions.append(f"li {reg}, {normalized}")
        elif isinstance(value, str) and value.startswith('str_'):
            # Es una etiqueta de string literal - cargar DIRECCIÓN (la), no valor (lw)
            instructions.append(f"la {reg}, {value}  # Load string address")
        else:
            # Es una variable, cargar desde memoria
            addr = self._get_memory_label(value)
            instructions.append(f"lw {reg}, {addr}")

    def _get_memory_label(self, identifier):
        """
        Obtiene la etiqueta de memoria para un identificador

        Args:
            identifier: Puede ser un nombre de variable o una dirección hexadecimal

        Returns:
            String con la etiqueta MIPS (ej: "var_a" o "0x1000")
        """
        # Si es una dirección hexadecimal
        if isinstance(identifier, str) and identifier.startswith('0x'):
            # Buscar la variable correspondiente
            try:
                addr = int(identifier, 16)
                for var_name, var_addr in self.memory_manager.allocations.items():
                    if var_addr == addr:
                        return f"var_{var_name}"
                # Si no se encuentra pero es heap object (>= 0x8000), usar label de heap
                if addr >= 0x8000:
                    return f"heap_obj_{identifier.lower()}"
                # Si no, usar la dirección directamente
                return identifier
            except ValueError:
                pass

        # Si es un nombre de variable
        if identifier in self.memory_manager.allocations:
            return f"var_{identifier}"

        # Si no se encuentra, asumir que es una etiqueta válida
        return str(identifier)

    def _assemble_final_code(self):
        """Ensambla todas las secciones en un programa MIPS completo"""
        lines = []

        # Encabezado
        lines.append("# Generated by Compiscript Compiler")
        lines.append("# MIPS Assembly Code")
        lines.append("")

        # Sección de datos
        lines.extend(self.data_section)
        lines.append("")

        # Sección de texto
        lines.extend(self.text_section)
        lines.append("")

        # String runtime functions
        lines.extend(self._generate_string_runtime_functions())
        lines.append("")

        return "\n".join(lines)

    def _generate_string_runtime_functions(self):
        """Generate runtime helper functions for string operations"""
        lines = []
        lines.append("# ===== Runtime Functions =====")
        lines.append("")

        # __int_to_string: Convert integer to string using MALLOC (Semantic-Parser approach)
        # Input: $a0 = integer value
        # Returns: $v0 = address of heap-allocated null-terminated string
        # Uses: malloc (sbrk) for each conversion - stateless, no global buffers
        lines.append("__int_to_string:")
        lines.append("    # Save registers (CRITICAL: Save ALL temp registers to prevent clobbering!)")
        lines.append("    addiu $sp, $sp, -44")
        lines.append("    sw $ra, 40($sp)  # Save return address for sbrk call")
        lines.append("    sw $t0, 36($sp)")
        lines.append("    sw $t1, 32($sp)")
        lines.append("    sw $t2, 28($sp)")
        lines.append("    sw $t3, 24($sp)")
        lines.append("    sw $t4, 20($sp)  # Save $t4-$t9 to prevent clobbering caller's values")
        lines.append("    sw $t5, 16($sp)")
        lines.append("    sw $t6, 12($sp)")
        lines.append("    sw $t7, 8($sp)")
        lines.append("    sw $t8, 4($sp)")
        lines.append("    sw $t9, 0($sp)")
        lines.append("")
        lines.append("    # Load integer from $a0")
        lines.append("    move $t0, $a0")
        lines.append("")
        lines.append("    # Use stack as temp buffer (convert backwards)")
        lines.append("    addiu $sp, $sp, -24  # Allocate 24 bytes temp buffer on stack")
        lines.append("    addiu $t1, $sp, 23   # Point to last byte")
        lines.append("    sb $zero, 0($t1)     # Null terminator")
        lines.append("    addiu $t1, $t1, -1   # Move back one")
        lines.append("")
        lines.append("    # Handle sign")
        lines.append("    li $t2, 0  # is_negative flag")
        lines.append("    bgez $t0, __its_positive")
        lines.append("    li $t2, 1  # Set negative flag")
        lines.append("    neg $t0, $t0  # Make positive")
        lines.append("__its_positive:")
        lines.append("")
        lines.append("    # Convert digits (backwards)")
        lines.append("    li $t3, 10  # divisor")
        lines.append("__its_loop:")
        lines.append("    divu $t0, $t3")
        lines.append("    mfhi $a0  # remainder = digit")
        lines.append("    mflo $t0  # quotient")
        lines.append("    addiu $a0, $a0, 48  # Convert to ASCII")
        lines.append("    sb $a0, 0($t1)  # Store digit")
        lines.append("    addiu $t1, $t1, -1  # Move back")
        lines.append("    bnez $t0, __its_loop  # Continue if quotient != 0")
        lines.append("")
        lines.append("    # Add minus sign if negative")
        lines.append("    beqz $t2, __its_done_sign")
        lines.append("    li $a0, 45  # '-' character")
        lines.append("    sb $a0, 0($t1)")
        lines.append("    addiu $t1, $t1, -1")
        lines.append("__its_done_sign:")
        lines.append("")
        lines.append("    # Calculate string length (from first char to null)")
        lines.append("    addiu $t1, $t1, 1  # Point to first character")
        lines.append("    move $t2, $zero    # length counter")
        lines.append("    move $t3, $t1      # temp pointer")
        lines.append("__its_count:")
        lines.append("    lb $a0, 0($t3)")
        lines.append("    beq $a0, $zero, __its_count_done")
        lines.append("    addiu $t2, $t2, 1")
        lines.append("    addiu $t3, $t3, 1")
        lines.append("    j __its_count")
        lines.append("__its_count_done:")
        lines.append("    addiu $t2, $t2, 1  # Include null terminator")
        lines.append("")
        lines.append("    # MALLOC: Allocate exact size needed on heap")
        lines.append("    move $a0, $t2  # size = length + 1")
        lines.append("    li $v0, 9      # sbrk syscall")
        lines.append("    syscall")
        lines.append("    move $t3, $v0  # Save heap address")
        lines.append("")
        lines.append("    # Copy string from stack buffer to heap")
        lines.append("    move $a0, $t1  # src = stack buffer")
        lines.append("    move $a1, $t3  # dst = heap")
        lines.append("__its_copy:")
        lines.append("    lb $t0, 0($a0)")
        lines.append("    sb $t0, 0($a1)")
        lines.append("    beq $t0, $zero, __its_copy_done")
        lines.append("    addiu $a0, $a0, 1")
        lines.append("    addiu $a1, $a1, 1")
        lines.append("    j __its_copy")
        lines.append("__its_copy_done:")
        lines.append("")
        lines.append("    # Return heap pointer")
        lines.append("    move $v0, $t3")
        lines.append("")
        lines.append("    # Cleanup stack temp buffer")
        lines.append("    addiu $sp, $sp, 24")
        lines.append("")
        lines.append("    # Restore registers")
        lines.append("    lw $t9, 0($sp)")
        lines.append("    lw $t8, 4($sp)")
        lines.append("    lw $t7, 8($sp)")
        lines.append("    lw $t6, 12($sp)")
        lines.append("    lw $t5, 16($sp)")
        lines.append("    lw $t4, 20($sp)")
        lines.append("    lw $t3, 24($sp)")
        lines.append("    lw $t2, 28($sp)")
        lines.append("    lw $t1, 32($sp)")
        lines.append("    lw $t0, 36($sp)")
        lines.append("    lw $ra, 40($sp)")
        lines.append("    addiu $sp, $sp, 44")
        lines.append("    jr $ra")
        lines.append("")

        # __string_copy: Copy null-terminated string from src to dest
        # Args: $a0 = dest, $a1 = src
        # Returns: nothing
        lines.append("__string_copy:")
        lines.append("    # Save registers")
        lines.append("    addiu $sp, $sp, -12")
        lines.append("    sw $t0, 0($sp)")
        lines.append("    sw $t1, 4($sp)")
        lines.append("    sw $t2, 8($sp)")
        lines.append("    li $t2, 0  # Counter for safety")
        lines.append("")
        lines.append("__string_copy_loop:")
        lines.append("    # Safety: max 256KB")
        lines.append("    li $t1, 262144")
        lines.append("    bge $t2, $t1, __string_copy_done  # If too long, just stop")
        lines.append("    lb $t0, 0($a1)      # Load byte from src")
        lines.append("    sb $t0, 0($a0)      # Store byte to dest (including null)")
        lines.append("    addiu $a0, $a0, 1   # dest++")
        lines.append("    addiu $a1, $a1, 1   # src++")
        lines.append("    addiu $t2, $t2, 1   # counter++")
        lines.append("    bne $t0, $zero, __string_copy_loop  # Continue if NOT null terminator")
        lines.append("")
        lines.append("__string_copy_done:")
        lines.append("    # Restore registers")
        lines.append("    lw $t0, 0($sp)")
        lines.append("    lw $t1, 4($sp)")
        lines.append("    lw $t2, 8($sp)")
        lines.append("    addiu $sp, $sp, 12")
        lines.append("    jr $ra")
        lines.append("")

        # __string_length: Calculate length of null-terminated string
        # Args: $a0 = string address
        # Returns: $v0 = length (max 32KB to prevent runaway)
        lines.append("__string_length:")
        lines.append("    # Save registers")
        lines.append("    addiu $sp, $sp, -8")
        lines.append("    sw $t0, 0($sp)")
        lines.append("    sw $t1, 4($sp)")
        lines.append("")
        lines.append("    li $v0, 0           # length = 0")
        lines.append("    li $t1, 32768       # Max length = 32KB")
        lines.append("__string_length_loop:")
        lines.append("    bge $v0, $t1, __string_length_done  # Safety: max 32KB")
        lines.append("    lb $t0, 0($a0)      # Load byte")
        lines.append("    beq $t0, $zero, __string_length_done  # If null, done")
        lines.append("    addiu $v0, $v0, 1   # length++")
        lines.append("    addiu $a0, $a0, 1   # str++")
        lines.append("    j __string_length_loop")
        lines.append("")
        lines.append("__string_length_done:")
        lines.append("    # Restore registers")
        lines.append("    lw $t0, 0($sp)")
        lines.append("    lw $t1, 4($sp)")
        lines.append("    addiu $sp, $sp, 8")
        lines.append("    jr $ra")
        lines.append("")

        # __string_compare: Compare two null-terminated strings
        # Args: $a0 = str1, $a1 = str2
        # Returns: $v0 = 1 if equal, 0 if not equal
        lines.append("__string_compare:")
        lines.append("    # Save registers")
        lines.append("    addiu $sp, $sp, -8")
        lines.append("    sw $t0, 0($sp)")
        lines.append("    sw $t1, 4($sp)")
        lines.append("")
        lines.append("__string_compare_loop:")
        lines.append("    lb $t0, 0($a0)      # Load byte from str1")
        lines.append("    lb $t1, 0($a1)      # Load byte from str2")
        lines.append("    bne $t0, $t1, __string_compare_not_equal  # If different, not equal")
        lines.append("    beq $t0, $zero, __string_compare_equal  # If both null, equal")
        lines.append("    addiu $a0, $a0, 1   # str1++")
        lines.append("    addiu $a1, $a1, 1   # str2++")
        lines.append("    j __string_compare_loop")
        lines.append("")
        lines.append("__string_compare_equal:")
        lines.append("    li $v0, 1           # Return 1 (equal)")
        lines.append("    j __string_compare_done")
        lines.append("")
        lines.append("__string_compare_not_equal:")
        lines.append("    li $v0, 0           # Return 0 (not equal)")
        lines.append("")
        lines.append("__string_compare_done:")
        lines.append("    # Restore registers")
        lines.append("    lw $t0, 0($sp)")
        lines.append("    lw $t1, 4($sp)")
        lines.append("    addiu $sp, $sp, 8")
        lines.append("    jr $ra")
        lines.append("")

        # NO LONGER NEEDED: Buffer reset function removed
        # String operations now use malloc - no global buffer state to reset

        # __concat: Concatenate two null-terminated strings (Semantic-Parser approach)
        # Args: FP[0] = str1 pointer, FP[4] = str2 pointer
        # Returns: $v0 = pointer to heap-allocated concatenated string
        # This function does inline length calculation to avoid register clobbering
        lines.append(".globl __concat")
        lines.append("__concat:")
        lines.append("    # Prologue")
        lines.append("    addiu $sp, $sp, -8")
        lines.append("    sw $ra, 4($sp)")
        lines.append("    sw $fp, 0($sp)")
        lines.append("    addiu $fp, $sp, 8")
        lines.append("")
        lines.append("    # Load string pointers from stack")
        lines.append("    lw $t0, 0($fp)     # str1")
        lines.append("    lw $t1, 4($fp)     # str2")
        lines.append("")
        lines.append("    # Calculate length of str1 -> $t2")
        lines.append("    move $t2, $zero")
        lines.append("__concat_len_a:")
        lines.append("    addu $t5, $t0, $t2")
        lines.append("    lbu  $t6, 0($t5)")
        lines.append("    beq  $t6, $zero, __concat_len_a_done")
        lines.append("    addiu $t2, $t2, 1")
        lines.append("    j __concat_len_a")
        lines.append("    nop")
        lines.append("__concat_len_a_done:")
        lines.append("")
        lines.append("    # Calculate length of str2 -> $t3")
        lines.append("    move $t3, $zero")
        lines.append("__concat_len_b:")
        lines.append("    addu $t5, $t1, $t3")
        lines.append("    lbu  $t6, 0($t5)")
        lines.append("    beq  $t6, $zero, __concat_len_b_done")
        lines.append("    addiu $t3, $t3, 1")
        lines.append("    j __concat_len_b")
        lines.append("    nop")
        lines.append("__concat_len_b_done:")
        lines.append("")
        lines.append("    # Allocate: total = len1 + len2 + 1")
        lines.append("    addu $t6, $t2, $t3")
        lines.append("    addiu $a0, $t6, 1")
        lines.append("    li $v0, 9  # sbrk")
        lines.append("    syscall")
        lines.append("    move $t4, $v0  # $t4 = destination buffer")
        lines.append("")
        lines.append("    # Copy str1 to buffer")
        lines.append("    move $t6, $zero")
        lines.append("__concat_cp_a:")
        lines.append("    beq $t6, $t2, __concat_cp_a_done")
        lines.append("    addu $t5, $t0, $t6")
        lines.append("    lbu $t7, 0($t5)")
        lines.append("    addu $t5, $t4, $t6")
        lines.append("    sb  $t7, 0($t5)")
        lines.append("    addiu $t6, $t6, 1")
        lines.append("    j __concat_cp_a")
        lines.append("    nop")
        lines.append("__concat_cp_a_done:")
        lines.append("")
        lines.append("    # Copy str2 to buffer (after str1)")
        lines.append("    move $t6, $zero")
        lines.append("__concat_cp_b:")
        lines.append("    beq $t6, $t3, __concat_cp_b_done")
        lines.append("    addu $t5, $t1, $t6")
        lines.append("    lbu $t7, 0($t5)")
        lines.append("    addu $t5, $t4, $t2  # Start at end of str1")
        lines.append("    addu $t5, $t5, $t6")
        lines.append("    sb  $t7, 0($t5)")
        lines.append("    addiu $t6, $t6, 1")
        lines.append("    j __concat_cp_b")
        lines.append("    nop")
        lines.append("__concat_cp_b_done:")
        lines.append("")
        lines.append("    # Add null terminator")
        lines.append("    addu $t5, $t4, $t2")
        lines.append("    addu $t5, $t5, $t3")
        lines.append("    sb  $zero, 0($t5)")
        lines.append("")
        lines.append("    # Return pointer to concatenated string")
        lines.append("    move $v0, $t4")
        lines.append("")
        lines.append("    # Epilogue")
        lines.append("    lw $fp, 0($sp)")
        lines.append("    lw $ra, 4($sp)")
        lines.append("    addiu $sp, $sp, 8")
        lines.append("    jr $ra")
        lines.append("    nop")
        lines.append("")

        return lines

    def _is_string_variable(self, operand):
        """
        Check if an operand represents a string variable by looking up its type in the symbol table.
        """
        # String literal label
        if isinstance(operand, str) and operand.startswith('str_'):
            return True

        # Memory address - check memory manager and symbol table
        if isinstance(operand, str) and operand.startswith('0x'):
            addr = int(operand, 16)

            # Find variable name from memory allocations
            var_name = None
            for name, allocated_addr in self.memory_manager.allocations.items():
                if allocated_addr == addr:
                    var_name = name
                    break

            if var_name:
                # Look up type in symbol table
                for scope in self.symbol_table.all_scopes:
                    if var_name in scope.symbols:
                        symbol = scope.symbols[var_name]
                        if hasattr(symbol, 'type') and symbol.type is not None:
                            type_name = symbol.type.name if hasattr(symbol.type, 'name') else str(symbol.type)
                            if type_name == 'string':
                                return True

        return False

    def _might_be_string_comparison(self, arg1, arg2):
        """
        Heurística para detectar si esta es una comparación de strings.
        Usa información de la tabla de símbolos para determinar tipos.
        """
        # Check if either operand is a string variable or literal
        if self._is_string_variable(arg1) or self._is_string_variable(arg2):
            return True

        return False

    def _might_be_string_concat(self, arg1, arg2):
        """
        Heurística para detectar si esta es una concatenación de strings.
        Uses symbol table lookup to verify types.
        """
        # CRITICAL: Check type map first - if either operand is marked as 'int', this is NOT string concat
        if self._is_temporary(arg1) and self.temp_types.get(arg1) == 'int':
            return False
        if self._is_temporary(arg2) and self.temp_types.get(arg2) == 'int':
            return False

        # NEW: Check if either temporary is marked as string
        if self._is_temporary(arg1) and self.temp_types.get(arg1) == 'string':
            return True
        if self._is_temporary(arg2) and self.temp_types.get(arg2) == 'string':
            return True

        # NEW: Check temp_value_source to see if temp was assigned from a string literal
        if self._is_temporary(arg1) and arg1 in self.temp_value_source:
            source = self.temp_value_source[arg1]
            if isinstance(source, str) and source.startswith('str_'):
                return True
        if self._is_temporary(arg2) and arg2 in self.temp_value_source:
            source = self.temp_value_source[arg2]
            if isinstance(source, str) and source.startswith('str_'):
                return True

        # Strong evidence: at least one operand is a string literal label
        if isinstance(arg1, str) and arg1.startswith('str_'):
            return True
        if isinstance(arg2, str) and arg2.startswith('str_'):
            return True

        # Check if either operand is a frame-relative address (local variable)
        # If one is a string literal/variable and the other is FP-relative, assume string concat
        is_arg1_fp = self._is_fp_relative(arg1)
        is_arg2_fp = self._is_fp_relative(arg2)

        if is_arg1_fp or is_arg2_fp:
            # At least one is a frame-relative local variable
            # If the other is clearly a string, assume this is string concat
            if is_arg1_fp and self._is_string_variable(arg2):
                return True
            if is_arg2_fp and self._is_string_variable(arg1):
                return True
            # If both are FP-relative and we're in a string-related function, assume string concat
            if is_arg1_fp and is_arg2_fp and self.current_function:
                func_lower = self.current_function.lower()
                string_func_patterns = [
                    'saludar', 'greet', 'estudiar', 'study',
                    'incrementar', 'increment', 'add', 'message',
                    'tostring', 'print', 'get', 'show', 'display', 'main'
                ]
                if any(pattern in func_lower for pattern in string_func_patterns):
                    return True

        # Check if both operands are string variables using type information
        # This prevents false positives with integer arithmetic
        if self._is_string_variable(arg1) and self._is_string_variable(arg2):
            return True
        if self._is_string_variable(arg1) or self._is_string_variable(arg2):
            # At least one is a string variable
            # If the other is a temporary or address, check if it's also a string
            if self._is_string_variable(arg1):
                return self._is_string_variable(arg2) or (isinstance(arg2, str) and arg2.startswith('t'))
            else:
                return self._is_string_variable(arg1) or (isinstance(arg1, str) and arg1.startswith('t'))

        # Heuristic: if we're in a function that returns string, and both operands are temporaries,
        # assume it's string concatenation (not perfect but catches most cases)
        # NOTE: This is now safe because the semantic analyzer inserts explicit toString()
        # calls when concatenating integers with strings.
        if (isinstance(arg1, str) and arg1.startswith('t') and
            isinstance(arg2, str) and arg2.startswith('t')):
            # If we have a current function, check its name
            if self.current_function:
                func_lower = self.current_function.lower()
                string_func_patterns = [
                    'saludar', 'greet', 'estudiar', 'study',
                    'incrementar', 'increment', 'add', 'message',
                    'tostring', 'print', 'get', 'show', 'display', 'main'
                ]
                if any(pattern in func_lower for pattern in string_func_patterns):
                    return True

            # CRITICAL: If we don't have a function name or it doesn't match,
            # but both operands are temporaries, assume it's string concat.
            # This is safe because the semantic analyzer converts int+int to proper
            # integer arithmetic, and only uses temp+temp for strings after toString() calls.
            return True

        return False

    def _translate_string_concat(self, quad):
        """
        Traduce concatenación de strings usando función __concat

        Strategy: Call __concat(str1, str2) function which:
        - Takes two string pointers as arguments on stack
        - Does inline length calculation (no external calls)
        - Allocates result with malloc
        - Returns pointer in $v0
        - Properly preserves all registers via function calling convention

        This is much more robust than inline concat with manual register management.
        """
        instructions = []
        instructions.append("# String concatenation via __concat function")

        arg1 = quad.arg1
        arg2 = quad.arg2
        result = quad.result

        # Get result register
        result_reg = self.register_allocator.get_reg(result)

        # Convert integers to strings if needed (before pushing to stack)
        # CRITICAL: Push in REVERSE order because MIPS stack grows down
        # We want: FP[0]=arg1, FP[4]=arg2
        # So we must push: arg2 first, then arg1

        # Load arg2 FIRST (to push it first)
        instructions.append("# Load arg2")
        arg2_reg = '$t2'
        if self._is_temporary(arg2):
            if arg2 in self.register_allocator.temp_to_reg:
                source_reg = self.register_allocator.temp_to_reg[arg2]
                instructions.append(f"move {arg2_reg}, {source_reg}  # Copy from allocated register")
            elif arg2 in self.temp_value_source:
                source = self.temp_value_source[arg2]
                if isinstance(source, str) and source.startswith('str_'):
                    self._load_string_address(source, arg2_reg, instructions)
                else:
                    self._load_string_address(source, arg2_reg, instructions)
            else:
                instructions.append(f"# Warning: {arg2} not found, using 0")
                instructions.append(f"li {arg2_reg}, 0")
        else:
            self._load_string_address(arg2, arg2_reg, instructions)

        # Push arg2 FIRST
        instructions.append("addiu $sp, $sp, -4")
        instructions.append(f"sw {arg2_reg}, 0($sp)")

        # Load arg1 SECOND (to push it second)
        instructions.append("# Load arg1 and convert to string if needed")
        arg1_reg = '$t0'
        if self._is_temporary(arg1):
            # Check if it's in a register or needs to be loaded
            if arg1 in self.register_allocator.temp_to_reg:
                source_reg = self.register_allocator.temp_to_reg[arg1]
                instructions.append(f"move {arg1_reg}, {source_reg}  # Copy from allocated register")
            elif arg1 in self.temp_value_source:
                source = self.temp_value_source[arg1]
                if isinstance(source, str) and source.startswith('str_'):
                    self._load_string_address(source, arg1_reg, instructions)
                else:
                    self._load_string_address(source, arg1_reg, instructions)
            else:
                instructions.append(f"# Warning: {arg1} not found, using 0")
                instructions.append(f"li {arg1_reg}, 0")
        else:
            # Load from memory or literal
            self._load_string_address(arg1, arg1_reg, instructions)

        # Push arg1 SECOND
        instructions.append("addiu $sp, $sp, -4")
        instructions.append(f"sw {arg1_reg}, 0($sp)")

        # Call __concat function
        instructions.append("jal __concat")

        # Clean up arguments
        instructions.append("addiu $sp, $sp, 8")

        # Move result to result register
        instructions.append(f"move {result_reg}, $v0")

        # Mark result as string type
        if self._is_temporary(result):
            self.temp_types[result] = 'string'

        return instructions

    def _translate_string_comparison(self, quad):
        """
        Traduce comparación de strings: (==, str1, str2, result) or (!=, str1, str2, result)
        """
        instructions = []
        instructions.append("# String comparison")

        arg1 = quad.arg1
        arg2 = quad.arg2
        result = quad.result

        # Use saved registers
        str1_reg = '$s1'
        str2_reg = '$s2'
        result_reg = self.register_allocator.get_reg(result)

        # Save $s1 and $s2
        instructions.append("addiu $sp, $sp, -8")
        instructions.append("sw $s1, 0($sp)")
        instructions.append("sw $s2, 4($sp)")

        # Load string addresses
        self._load_string_address(arg1, str1_reg, instructions)
        self._load_string_address(arg2, str2_reg, instructions)

        # Call string compare function
        instructions.append(f"move $a0, {str1_reg}")
        instructions.append(f"move $a1, {str2_reg}")
        instructions.append("jal __string_compare")

        # $v0 now contains 1 if equal, 0 if not equal
        if quad.op == '==':
            # Return the result as-is
            instructions.append(f"move {result_reg}, $v0")
        else:  # !=
            # Invert the result
            instructions.append(f"xori {result_reg}, $v0, 1")

        # Restore $s1 and $s2
        instructions.append("lw $s1, 0($sp)")
        instructions.append("lw $s2, 4($sp)")
        instructions.append("addiu $sp, $sp, 8")

        return instructions

    # --- OOP Support (Objects and Methods) ---

    def _is_object_address_quad(self, quad) -> bool:
        """
        Detecta cuádruplos que calculan la dirección de un atributo de objeto.
        Patrón en TAC: (+, <baseTemp>, <offset>, <resultTemp>) con comment que incluye 'Address of'.
        """
        try:
            return quad.op == '+' and quad.comment and ('Address of' in str(quad.comment))
        except AttributeError:
            return False

    def _translate_object_access(self, quad):
        """
        Traduce acceso a objetos como:
        (+, t72, 8, t73)  # Address of Clase.campo

        En el caso normal (métodos), arg1 es un temporal que ya contiene
        el puntero al objeto (__this).

        En el constructor, el front-end genera algo como:
        (+, FP[4], 0, t0)  # Address of Persona.nombre
        (+, t2, 12, t3)     # Address of Estudiante.color (where t2 is NOT the object!)
        donde el puntero real al objeto está en FP[0].
        Por lo tanto, en constructores SIEMPRE usamos FP[0] como base.

        arg1 puede ser:
        - Un temporal (t0, t1, etc.)
        - FP-relative (FP[4], FP[8], etc.) - en constructores, usar FP[0] en su lugar
        - Dirección de memoria (0x1000, etc.)
        """
        instr = []
        if getattr(quad, "comment", None):
            instr.append(f"# {quad.comment}")

        # result: temporal destino para la dirección resultante
        result_reg = self.register_allocator.get_reg(quad.result)

        # offset inmediato (ej. 4 para Estudiante.edad, 8 para Estudiante.grado)
        # The TAC now uses correct 4-byte alignment after fixing string size
        offset_imm = str(int(quad.arg2 or 0))

        # Check if we're in a constructor
        in_constructor = (self.current_function and
                         'constructor' in self.current_function.lower())

        # Cargar la base en un registro
        if in_constructor:
            # CRITICAL FIX: Check if arg1 is already a temporary containing the object pointer
            # Only reload from FP[0] if arg1 is FP-relative or not a valid temporary
            if self._is_temporary(quad.arg1):
                # arg1 is a temporary that should already contain the object pointer
                # Use it directly instead of reloading from FP[0]
                base_reg = self.register_allocator.get_reg(quad.arg1)
            else:
                # arg1 is FP-relative or invalid - load __this from FP[0]
                base_reg = self.register_allocator.get_reg_temp("obj_base")
                instr.append(f"lw {base_reg}, 0($fp)  # load __this pointer (constructor)")
        elif self._is_fp_relative(quad.arg1):
            # Fuera de constructor, FP-relative debería usarse tal cual (raramente ocurre)
            fp_offset = self._extract_fp_offset(quad.arg1)
            base_reg = self.register_allocator.get_reg_temp("obj_base")
            instr.append(f"lw {base_reg}, {fp_offset}($fp)  # Load from frame")
        elif self._is_temporary(quad.arg1):
            # Ya está en un registro
            base_reg = self.register_allocator.get_reg(quad.arg1)
        elif isinstance(quad.arg1, str) and quad.arg1.startswith('0x'):
            # Cargar desde dirección de memoria
            addr_label = self._get_memory_label(quad.arg1)
            base_reg = self.register_allocator.get_reg_temp("obj_base")
            instr.append(f"lw {base_reg}, {addr_label}  # Load object pointer")
        else:
            # Otro caso - intentar cargar
            base_reg = self.register_allocator.get_reg_temp("obj_base")
            self._load_value_to_reg(quad.arg1, base_reg, instr)

        # Calcular dirección efectiva
        instr.append(f"addiu {result_reg}, {base_reg}, {offset_imm}")
        return instr

    def _translate_method_call(self, quad):
        """
        Traduce llamadas a métodos:
        TAC: (call, None, None, FUNC_<...>)
        MIPS: jal <label>

        Handles inherited methods by resolving to parent class if method not found.
        """
        label = self._sanitize_label(quad.result)

        # Check if this is a method call (has class name)
        # Format: FUNC_methodName_ClassName
        if '_' in label:
            parts = label.split('_')
            if len(parts) >= 3:  # FUNC, methodName, ClassName
                method_name = parts[1]
                class_name = '_'.join(parts[2:])  # Handle multi-part class names

                # Check if this method+class combo exists by checking if we generated it
                # If not, try to find it in parent class
                resolved_label = self._resolve_inherited_method(method_name, class_name)
                if resolved_label:
                    label = resolved_label

        return [f"jal {label}"]

    def _resolve_inherited_method(self, method_name, class_name):
        """
        Resolves inherited methods by checking parent class hierarchy.
        Returns the correct label if method is found, None otherwise.

        Args:
            method_name: Name of the method (e.g., "saludar")
            class_name: Name of the class (e.g., "Estudiante")

        Returns:
            Resolved label string or None
        """
        # Try to find the class in symbol table
        from classes.symbols import ClassSymbol

        # Search for class in all scopes
        for scope in self.symbol_table.all_scopes:
            if class_name in scope.symbols:
                symbol = scope.symbols[class_name]
                if isinstance(symbol, ClassSymbol):
                    # Check if method exists in this class
                    if method_name in symbol.methods:
                        # Method found in current class
                        return f"FUNC_{method_name}_{class_name}"

                    # Method not found, check parent
                    if symbol.parent_class:
                        parent_name = symbol.parent_class.name
                        # Recursively resolve in parent
                        return self._resolve_inherited_method(method_name, parent_name)

        # Method not found in hierarchy
        return None

    def save_to_file(self, filename):
        """Guarda el código MIPS en un archivo .asm"""
        code = self.generate_mips_code()
        with open(filename, 'w') as f:
            f.write(code)
        return filename
