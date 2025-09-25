# classes/memory_manager.py
class MemoryManager:
    def __init__(self):
        self.global_address = 0x1000
        self.heap_start  = 0x8000  
        self.stack_start = 0xF000

        # Contadores actuales
        self.global_current = self.global_address
        self.heap_current = self.heap_start
        self.stack_current = self.stack_start
        
        # Mapeo de variables a direcciones
        self.allocations = {}
        
    def allocate_global(self, var_name, size=4):
        if var_name in self.allocations:
            return self.allocations[var_name]
            
        # Alineación a 4 bytes
        if self.global_current % 4 != 0:
            self.global_current += 4 - (self.global_current % 4)
            
        address = self.global_current
        self.global_current += size
        self.allocations[var_name] = address
        return address
        
    def allocate_local(self, var_name, size, function_name):
        """
        Aloca variables locales en el stack frame de una función
        Las variables locales se almacenan con direcciones relativas al FP (Frame Pointer)
        """
        key = f"{function_name}::{var_name}"
        if key in self.allocations:
            return self.allocations[key]

        # Para variables locales, usamos offsets relativos al Frame Pointer
        # Las variables locales tienen offsets positivos (crecen hacia arriba)
        current_offset = len([k for k in self.allocations.keys() if k.startswith(f"{function_name}::")]) * 4

        address = f"FP[{current_offset}]"
        self.allocations[key] = address
        return address

    def allocate_heap(self, size, object_type="object"):
        """
        Aloca memoria en el heap para objetos dinámicos (arrays, objetos de clases)
        """
        # Alineación a 4 bytes
        if self.heap_current % 4 != 0:
            self.heap_current += 4 - (self.heap_current % 4)

        address = self.heap_current
        self.heap_current += size
        return address

    def allocate_array(self, var_name, element_count, element_size=4):
        """
        Aloca memoria para arrays en el heap
        """
        total_size = element_count * element_size
        if var_name in self.allocations:
            return self.allocations[var_name]

        address = self.allocate_heap(total_size, "array")
        self.allocations[var_name] = address
        return address

    def get_stack_frame_size(self, function_name):
        """
        Calcula el tamaño del stack frame para una función
        """
        local_vars = [k for k in self.allocations.keys() if k.startswith(f"{function_name}::")]
        return len(local_vars) * 4  # 4 bytes por variable
    
    def get_variable_address(self, var_name):
        return self.allocations.get(var_name)