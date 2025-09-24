# activation_record_design.py
# Representacion de registros de activacion

class ActivationRecordDesign:
    def __init__(self, function_name):
        self.function_name = function_name
        self.size = 0
        self.offsets = {}  # {variable_name: offset}
        self.parameters = []
        self.locals = []
        
    def add_parameter(self, name, type):
        # Los parámetros generalmente tienen offsets negativos (crecen hacia abajo)
        offset = -4 * (len(self.parameters) + 1)  # -4, -8, -12, etc.
        self.offsets[name] = offset
        self.parameters.append(name)
        # No aumentamos el size total para parámetros (se manejan en el frame del llamador)
        
    def add_local(self, name, type):
        # Las variables locales tienen offsets positivos (crecen hacia arriba)
        type_size = self._get_type_size(type)
        self.offsets[name] = self.size
        self.locals.append(name)
        self.size += type_size
        
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
        return self.offsets.get(name, None)
    
    def __str__(self):
        return (f"AR Design for {self.function_name}: "
                f"Size={self.size}, Params={self.parameters}, Locals={self.locals}")