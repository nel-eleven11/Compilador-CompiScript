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
        
    def allocate_local(self, size, var_name, function_name):
        # Por implementar cuando ya tengamos TAC de funciones
        pass
        
    def allocate_heap(self, size):
        # por implementar tambien, sino estoy mal este es mas para objetos/clases
        pass
    
    def get_variable_address(self, var_name):
        return self.allocations.get(var_name)