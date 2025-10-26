# activation_record_design.py
# Representacion de registros de activacion

class ActivationRecordDesign:
    def __init__(self, function_name):
        self.function_name = function_name
        self.size = 0
        self.offsets = {}  # {variable_name: offset}
        self.parameters = []
        self.locals = []
        
    def add_parameter(self, name, type_):
        """
        Parámetros:
        FP[0] = primer parámetro (__this en métodos, o primer param en funciones)
        FP[4] = segundo parámetro
        FP[8] = tercer parámetro, etc.
        """
        offset = len(self.parameters) * 4
        self.parameters.append({
            'name': name,
            'type': type_,
            'offset': offset
        })
        # Actualizar tamaño total
        self.size = max(self.size, offset + 4)
        
    def add_local(self, name, type_):
        """
        Variables locales van DESPUÉS de los parámetros
        """
        # Offset base: después de todos los parámetros
        base_offset = len(self.parameters) * 4
        local_offset = base_offset + (len(self.locals) * 4)
        
        self.locals.append({
            'name': name,
            'type': type_,
            'offset': local_offset
        })
        # Actualizar tamaño total
        self.size = max(self.size, local_offset + 4)
        
    def _get_type_size(self, type):
        # Usar el width del tipo si está disponible, sino valores por defecto
        if hasattr(type, 'width'):
            return type.width
        # Valores por defecto basados en el nombre del tipo
        type_sizes = {
            'integer': 4,
            'boolean': 1,
            'string': 16,  # Puntero a string
            'void': 0,
            'null': 4,     # Puntero
        }
        return type_sizes.get(type.name, 4)  # 4 bytes por defecto (puntero)
    
    def get_offset(self, name):
        """Busca offset de parámetro o local por nombre"""
        # Buscar en parámetros
        for param in self.parameters:
            if param['name'] == name:
                return param['offset']
        # Buscar en locales
        for local in self.locals:
            if local['name'] == name:
                return local['offset']
        return None
    
    def __str__(self):
        return f"AR({self.function_name}): size={self.size}, params={len(self.parameters)}, locals={len(self.locals)}"
