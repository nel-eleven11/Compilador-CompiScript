from functools import reduce

class Type:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent  # Para herencia
        self.width = 0       # Tamaño en bytes
        self.methods = {}    # Métodos disponibles
        
    def __eq__(self, other):
        return isinstance(other, Type) and self.name == other.name
        
    def can_assign_to(self, other_type):
        """Verifica compatibilidad de tipos en asignaciones"""
        if self == other_type:
            return True
        # Verifica herencia
        if self.parent:
            return self.parent.can_assign_to(other_type)
        return False

class PrimitiveType(Type):
    def __init__(self, name, width):
        super().__init__(name)
        self.width = width

class ArrayType(Type):
    def __init__(self, element_type, dimensions):
        super().__init__(f"array<{element_type.name}>")
        self.element_type = element_type
        self.dimensions = dimensions
        self.width = element_type.width * reduce(lambda x, y: x*y, dimensions, 1)

# Tipos básicos
INT_TYPE = PrimitiveType("integer", 4)
BOOL_TYPE = PrimitiveType("boolean", 1)
STRING_TYPE = PrimitiveType("string", 16)
VOID_TYPE = Type("void")

TYPE_MAP = {
    "integer": INT_TYPE,
    "boolean": BOOL_TYPE,
    "string": STRING_TYPE,
    "void": VOID_TYPE 
}


def get_type_from_string(type_str):
    """Obtiene tipo desde texto, soportando arrays"""
    if type_str == "void":
        return VOID_TYPE
    
    if type_str.endswith("[]"):
        element_type = get_type_from_string(type_str[:-2])
        return ArrayType(element_type, [0])  # 0 = dimensión dinámica
    return TYPE_MAP.get(type_str, None)