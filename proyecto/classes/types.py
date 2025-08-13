class Type:
    def __init__(self, name):
        self.name = name
        
    def __eq__(self, other):
        return isinstance(other, Type) and self.name == other.name
        
    def __str__(self):
        return self.name

# Tipos básicos predefinidos
INT_TYPE = Type("integer")
BOOL_TYPE = Type("boolean")
STRING_TYPE = Type("string")
VOID_TYPE = Type("void")

def get_type_from_string(type_str):
    """Convierte texto de tipo a objeto Type"""
    type_map = {
        "integer": INT_TYPE,
        "boolean": BOOL_TYPE,
        "string": STRING_TYPE,
        "void": VOID_TYPE
    }
    return type_map.get(type_str, None)