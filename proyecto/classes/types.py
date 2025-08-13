from functools import reduce

class Type:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent  
        self.width = 0       # bytes
        self.methods = {}    # 
        
    def __eq__(self, other):
        return isinstance(other, Type) and self.name == other.name
    
    # Verifica compatibilidad de tipos en asignaciones
    def can_assign_to(self, other_type):
        
        if self == NULL_TYPE:
            # null puede asignarse a cualquier tipo excepto primitivos no-nullables
            return other_type not in (INT_TYPE, BOOL_TYPE, VOID_TYPE)
        return self == other_type or (self.parent and self.parent.can_assign_to(other_type))

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
NULL_TYPE = Type("null")

TYPE_MAP = {
    "integer": INT_TYPE,
    "boolean": BOOL_TYPE,
    "string": STRING_TYPE,
    "void": VOID_TYPE
}

#Obtiene tipo desde texto, soportando arrays
def get_type_from_string(type_str):
    if type_str == "null":
        return NULL_TYPE
    
    if type_str == "void":
        return VOID_TYPE
    
    if type_str.endswith("[]"):
        element_type = get_type_from_string(type_str[:-2])
        return ArrayType(element_type, [0])  # 0 = dimensión dinámica
    return TYPE_MAP.get(type_str, None)