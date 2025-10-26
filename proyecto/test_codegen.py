from classes.code_generator import CodeGenerator
from classes.symbol_table import SymbolTable
from classes.symbols import VariableSymbol
from classes.types import INT_TYPE

def test_simple_arithmetic():
    st = SymbolTable()
    cg = CodeGenerator(st)
    
    # x = 5
    cg.generate_load_immediate('5', None)
    t0 = cg.current_temp
    print(f"Load 5 -> {t0}")
    
    # y = 3
    cg.generate_load_immediate('3', None)
    t1 = cg.current_temp
    print(f"Load 3 -> {t1}")
    
    # z = x + y
    result = cg.generate_arithmetic_operation(t0, t1, '+', None)
    print(f"Add {t0} + {t1} -> {result}")
    
    # Imprimir cuádruplos
    print("\n=== Cuádruplos ===")
    for i, quad in enumerate(cg.quadruples):
        print(f"{i}: {quad}")
    
    # Validaciones
    assert len(cg.quadruples) == 3, "Deberían ser 3 cuádruplos"
    assert cg.quadruples[2].op == '+', "El tercer cuádruplo debe ser suma"
    print("\n Test pasado!")

if __name__ == "__main__":
    test_simple_arithmetic()