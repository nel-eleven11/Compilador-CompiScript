# classes/MIPS_generator/register_allocator.py
"""
RegisterAllocator - Implementa el algoritmo getReg() para asignación de registros
"""

class RegisterAllocator:
    def __init__(self):
        """
        Inicializa el asignador de registros con los registros disponibles en MIPS
        """
        # Registros disponibles por categoría
        self.available_regs = {
            'temp': [f'$t{i}' for i in range(10)],      # $t0-$t9
            'saved': [f'$s{i}' for i in range(8)],      # $s0-$s7
            'arg': [f'$a{i}' for i in range(4)]         # $a0-$a3
        }

        # Mapeo de temporales/variables a registros físicos
        self.temp_to_reg = {}

        # Registros actualmente en uso
        self.used_regs = set()

        # Pool de registros libres (para asignación rápida)
        self.free_regs = list(self.available_regs['temp'])

        # Offset para spill en el stack (cuando no hay registros disponibles)
        self.spill_offset = 0

        # Mapeo de temporales que se hicieron spill
        self.spilled_temps = {}

    def get_reg(self, temp_name, context='arithmetic'):
        """
        Implementa el algoritmo getReg() famoso

        Asigna un registro físico para un temporal o variable.
        Si el temporal ya tiene un registro asignado, lo devuelve.
        Si no hay registros disponibles, hace spill al stack.

        Args:
            temp_name: Nombre del temporal o variable (ej: 't0', 'a', '5')
            context: Contexto de uso ('arithmetic', 'function', 'save')

        Returns:
            String con el registro MIPS asignado (ej: '$t0')
        """
        # Si es None, usar un registro temporal
        if temp_name is None:
            return self.get_reg_temp("null_temp")

        # Si es un inmediato, no necesita registro fijo
        # (se cargará con 'li' cuando sea necesario)
        if self._is_immediate(temp_name):
            # Retornar un registro temporal para el inmediato
            return self.get_reg_temp(f"imm_{temp_name}")

        # Si ya tiene un registro asignado, retornarlo
        if temp_name in self.temp_to_reg:
            return self.temp_to_reg[temp_name]

        # Si el temporal está en spill, restaurarlo (futuro)
        if temp_name in self.spilled_temps:
            # TODO: Implementar restauración desde stack
            pass

        # Asignar un nuevo registro
        reg = self._allocate_new_register(context)

        if reg:
            self.temp_to_reg[temp_name] = reg
            self.used_regs.add(reg)
            return reg
        else:
            # No hay registros disponibles, hacer spill
            return self._spill_and_allocate(temp_name)

    def get_reg_temp(self, hint="temp"):
        """
        Obtiene un registro temporal sin asignación permanente
        Útil para valores inmediatos o cálculos intermedios

        Args:
            hint: Pista sobre el uso del registro

        Returns:
            String con el registro MIPS
        """
        if self.free_regs:
            reg = self.free_regs[0]  # Tomar el primero disponible
            return reg
        else:
            # Si no hay libres, usar $t9 como registro temporal por defecto
            return '$t9'

    def _allocate_new_register(self, context):
        """
        Asigna un nuevo registro del pool disponible

        Args:
            context: Contexto de uso

        Returns:
            String con el registro asignado, o None si no hay disponibles
        """
        # Seleccionar pool de registros según contexto
        if context == 'function' or context == 'save':
            # Para funciones, preferir registros saved ($s)
            pool = 'saved'
        elif context == 'arg':
            # Para argumentos, usar registros de argumentos ($a)
            pool = 'arg'
        else:
            # Por defecto, usar registros temporales ($t)
            pool = 'temp'

        # Buscar un registro libre en el pool
        for reg in self.available_regs[pool]:
            if reg not in self.used_regs:
                return reg

        # Si no hay en el pool preferido, buscar en otros pools
        for pool_name in ['temp', 'saved', 'arg']:
            if pool_name != pool:
                for reg in self.available_regs[pool_name]:
                    if reg not in self.used_regs:
                        return reg

        # No hay registros disponibles
        return None

    def free_reg(self, temp_name):
        """
        Libera un registro para reutilización

        Args:
            temp_name: Nombre del temporal a liberar
        """
        if temp_name in self.temp_to_reg:
            reg = self.temp_to_reg[temp_name]
            self.used_regs.discard(reg)
            del self.temp_to_reg[temp_name]

            # Agregar de vuelta al pool de registros libres si es $t
            if reg.startswith('$t'):
                if reg not in self.free_regs:
                    self.free_regs.append(reg)

    def _spill_and_allocate(self, temp_name):
        """
        Hace spill de un registro al stack y asigna el registro liberado

        Args:
            temp_name: Nombre del temporal que necesita registro

        Returns:
            String con el registro asignado
        """
        # Seleccionar un registro para hacer spill (LRU simple: el primero usado)
        if not self.temp_to_reg:
            # No debería pasar, pero por seguridad
            return '$t9'

        # Obtener el primer temporal en el mapeo (víctima del spill)
        victim_temp = next(iter(self.temp_to_reg))
        victim_reg = self.temp_to_reg[victim_temp]

        # Guardar el valor en el stack
        # TODO: Generar instrucciones de spill
        # sw victim_reg, spill_offset($sp)
        self.spilled_temps[victim_temp] = self.spill_offset
        self.spill_offset += 4

        # Liberar el registro
        self.free_reg(victim_temp)

        # Asignar el registro liberado al nuevo temporal
        self.temp_to_reg[temp_name] = victim_reg
        self.used_regs.add(victim_reg)

        return victim_reg

    def reset(self):
        """Resetea el estado del allocator (útil entre funciones)"""
        self.temp_to_reg.clear()
        self.used_regs.clear()
        self.free_regs = list(self.available_regs['temp'])
        self.spill_offset = 0
        self.spilled_temps.clear()

    def _is_immediate(self, value):
        """Verifica si un valor es un inmediato (número)"""
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                int(value)
                return True
            except ValueError:
                return False
        return False

    def get_register_info(self):
        """Retorna información de debug sobre el estado de los registros"""
        return {
            'used': list(self.used_regs),
            'free': self.free_regs,
            'mappings': dict(self.temp_to_reg),
            'spilled': dict(self.spilled_temps)
        }
