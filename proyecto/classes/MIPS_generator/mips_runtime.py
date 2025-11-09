# classes/MIPS_generator/mips_runtime.py
"""
MIPSRuntime - Funciones de runtime para soporte de ejecución en MIPS
"""

class MIPSRuntime:
    def __init__(self):
        """
        Inicializa el generador de funciones de runtime
        """
        pass

    def get_runtime_functions(self):
        """
        Devuelve código MIPS para funciones de runtime/biblioteca

        Estas funciones proporcionan funcionalidad básica como:
        - Impresión de enteros
        - Impresión de strings
        - Lectura de entrada
        - Operaciones auxiliares

        Returns:
            Lista de strings con las funciones MIPS
        """
        functions = []

        functions.append("# ===== RUNTIME SUPPORT FUNCTIONS =====")
        functions.append("")

        # Función para imprimir enteros
        functions.extend(self._generate_print_int())
        functions.append("")

        # Función para imprimir strings
        functions.extend(self._generate_print_string())
        functions.append("")

        # Función para imprimir newline
        functions.extend(self._generate_print_newline())
        functions.append("")

        # Función para leer entero
        functions.extend(self._generate_read_int())
        functions.append("")

        return functions

    def _generate_print_int(self):
        """Genera función para imprimir un entero"""
        return [
            "# print_int: Imprime el entero en $a0",
            "print_int:",
            "    li $v0, 1       # syscall 1: print_int",
            "    syscall",
            "    jr $ra"
        ]

    def _generate_print_string(self):
        """Genera función para imprimir un string"""
        return [
            "# print_string: Imprime el string en $a0",
            "print_string:",
            "    li $v0, 4       # syscall 4: print_string",
            "    syscall",
            "    jr $ra"
        ]

    def _generate_print_newline(self):
        """Genera función para imprimir un newline"""
        return [
            "# print_newline: Imprime un salto de línea",
            "print_newline:",
            "    li $v0, 11      # syscall 11: print_char",
            "    li $a0, 10      # ASCII code for newline",
            "    syscall",
            "    jr $ra"
        ]

    def _generate_read_int(self):
        """Genera función para leer un entero"""
        return [
            "# read_int: Lee un entero y lo retorna en $v0",
            "read_int:",
            "    li $v0, 5       # syscall 5: read_int",
            "    syscall",
            "    jr $ra"
        ]

    def get_print_int_call(self, value_reg):
        """
        Genera código para llamar a print_int

        Args:
            value_reg: Registro que contiene el valor a imprimir

        Returns:
            Lista de instrucciones MIPS
        """
        return [
            f"move $a0, {value_reg}",
            "jal print_int"
        ]

    def get_syscall_exit(self):
        """Genera código para terminar el programa"""
        return [
            "li $v0, 10      # syscall 10: exit",
            "syscall"
        ]

    def get_syscall_print_int(self, value_reg):
        """
        Genera código para imprimir un entero directamente (sin función)

        Args:
            value_reg: Registro que contiene el valor

        Returns:
            Lista de instrucciones MIPS
        """
        return [
            f"move $a0, {value_reg}",
            "li $v0, 1       # print_int",
            "syscall"
        ]

    def get_syscall_print_string(self, label):
        """
        Genera código para imprimir un string directamente

        Args:
            label: Etiqueta del string en la sección .data

        Returns:
            Lista de instrucciones MIPS
        """
        return [
            f"la $a0, {label}",
            "li $v0, 4       # print_string",
            "syscall"
        ]

    def get_newline(self):
        """Genera código para imprimir un newline"""
        return [
            "li $v0, 11      # print_char",
            "li $a0, 10      # newline",
            "syscall"
        ]
