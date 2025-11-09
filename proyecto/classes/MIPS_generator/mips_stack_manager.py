# classes/MIPS_generator/mips_stack_manager.py
"""
MIPSStackManager - Manejo del stack para llamadas y retornos de funciones
"""

class MIPSStackManager:
    def __init__(self):
        """
        Inicializa el manejador de stack
        """
        self.stack_offset = 0
        self.function_frames = {}  # Mapeo de funciones a sus tamaños de frame

    def generate_function_prologue(self, func_name, local_vars_count, param_count=0):
        """
        Genera la secuencia de prólogo para entrada a una función

        El prólogo típico en MIPS:
        1. Reservar espacio en el stack para $ra y $fp
        2. Guardar $ra (return address)
        3. Guardar $fp (frame pointer)
        4. Actualizar $fp al nuevo frame
        5. Reservar espacio para variables locales

        Args:
            func_name: Nombre de la función
            local_vars_count: Cantidad de variables locales
            param_count: Cantidad de parámetros

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []

        # Calcular tamaño del frame
        # 4 bytes para $ra + 4 bytes para $fp + (4 * local_vars_count)
        frame_size = 8 + (local_vars_count * 4)
        self.function_frames[func_name] = frame_size

        instructions.append(f"# PROLOGUE - {func_name}")
        instructions.append(f"# Frame size: {frame_size} bytes")

        # Reservar espacio para $ra y $fp
        instructions.append(f"addiu $sp, $sp, -8")

        # Guardar return address
        instructions.append(f"sw $ra, 4($sp)")

        # Guardar frame pointer
        instructions.append(f"sw $fp, 0($sp)")

        # Establecer nuevo frame pointer
        instructions.append(f"move $fp, $sp")

        # Reservar espacio para variables locales
        if local_vars_count > 0:
            local_space = local_vars_count * 4
            instructions.append(f"addiu $sp, $sp, -{local_space}")

        instructions.append("")

        return instructions

    def generate_function_epilogue(self, func_name):
        """
        Genera la secuencia de epílogo para salida de una función

        El epílogo típico en MIPS:
        1. Restaurar $sp al frame pointer
        2. Restaurar $fp anterior
        3. Restaurar $ra
        4. Retornar con jr $ra

        Args:
            func_name: Nombre de la función

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []

        instructions.append(f"# EPILOGUE - {func_name}")

        # Restaurar stack pointer al frame pointer
        instructions.append(f"move $sp, $fp")

        # Restaurar frame pointer anterior
        instructions.append(f"lw $fp, 0($sp)")

        # Restaurar return address
        instructions.append(f"lw $ra, 4($sp)")

        # Liberar espacio del frame
        instructions.append(f"addiu $sp, $sp, 8")

        # Retornar
        instructions.append(f"jr $ra")
        instructions.append("")

        return instructions

    def generate_call_sequence(self, func_name, args):
        """
        Genera la secuencia de código para llamar una función

        Convención de llamada MIPS:
        1. Los primeros 4 argumentos van en $a0-$a3
        2. Argumentos adicionales van en el stack
        3. Llamar con jal (jump and link)

        Args:
            func_name: Nombre de la función a llamar
            args: Lista de argumentos (registros o valores)

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []

        instructions.append(f"# CALL SEQUENCE - {func_name}")

        # Pasar argumentos en $a0-$a3
        for i, arg in enumerate(args[:4]):
            instructions.append(f"move $a{i}, {arg}")

        # Pasar argumentos adicionales en el stack
        if len(args) > 4:
            # Reservar espacio en el stack para argumentos extra
            extra_args = len(args) - 4
            extra_space = extra_args * 4
            instructions.append(f"addiu $sp, $sp, -{extra_space}")

            for i, arg in enumerate(args[4:], 0):
                offset = i * 4
                instructions.append(f"sw {arg}, {offset}($sp)")

        # Llamar a la función
        instructions.append(f"jal FUNC_{func_name}")

        # Limpiar argumentos del stack (si hubo extras)
        if len(args) > 4:
            extra_space = (len(args) - 4) * 4
            instructions.append(f"addiu $sp, $sp, {extra_space}")

        instructions.append("")

        return instructions

    def generate_return_sequence(self, return_value=None):
        """
        Genera la secuencia de código para retornar de una función

        Args:
            return_value: Registro o valor a retornar (va en $v0)

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []

        instructions.append(f"# RETURN SEQUENCE")

        # Si hay valor de retorno, moverlo a $v0
        if return_value:
            instructions.append(f"move $v0, {return_value}")

        # El epílogo se encargará del resto
        instructions.append("")

        return instructions

    def generate_param_push(self, param_value, param_index):
        """
        Genera código para pasar un parámetro

        Args:
            param_value: Valor o registro del parámetro
            param_index: Índice del parámetro (0-based)

        Returns:
            Lista de instrucciones MIPS
        """
        instructions = []

        if param_index < 4:
            # Los primeros 4 parámetros van en registros $a0-$a3
            instructions.append(f"move $a{param_index}, {param_value}")
        else:
            # Parámetros adicionales van en el stack
            offset = (param_index - 4) * 4
            instructions.append(f"sw {param_value}, {offset}($sp)")

        return instructions

    def get_local_var_offset(self, var_index):
        """
        Calcula el offset de una variable local respecto al frame pointer

        Args:
            var_index: Índice de la variable local (0-based)

        Returns:
            Offset en bytes (negativo, ya que crece hacia abajo)
        """
        # Variables locales están después de $ra y $fp
        # Offset = -(8 + var_index * 4)
        return -(8 + var_index * 4)

    def get_param_offset(self, param_index):
        """
        Calcula el offset de un parámetro respecto al frame pointer

        Args:
            param_index: Índice del parámetro (0-based)

        Returns:
            Offset en bytes (positivo, ya que están antes del frame)
        """
        if param_index < 4:
            # Los primeros 4 parámetros están en registros
            return None  # No tienen offset, están en $a0-$a3
        else:
            # Parámetros adicionales están en el stack antes del frame
            # Offset = 8 + (param_index - 4) * 4
            return 8 + (param_index - 4) * 4

    def reset(self):
        """Resetea el estado del stack manager"""
        self.stack_offset = 0
        self.function_frames.clear()
