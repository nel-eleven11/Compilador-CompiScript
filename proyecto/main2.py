import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from semantic_visitor import SemanticVisitor

def main(argv):
    # configracion
    input_stream = FileStream(argv[1])
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    
    # sintactico
    tree = parser.program()
    
    # semantico
    analyzer = SemanticVisitor()
    analyzer.visit(tree)
    
    # resultados
    if analyzer.errors:
        print("\n=== Errores encontrados ===")
        for error in analyzer.errors:
            print(error)
    else:
        print("\nAnálisis semántico completado sin errores")
        
    # 5. Mostrar tabla de símbolos (debug)
    print("\n=== Tabla de Símbolos ===")
    for scope in analyzer.symbol_table.scopes:
        print(f"\nÁmbito {scope.scope_level}:")
        for name, symbol in scope.symbols.items():
            print(f"  {symbol}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python main.py <archivo_entrada>")
        sys.exit(1)
    main(sys.argv)