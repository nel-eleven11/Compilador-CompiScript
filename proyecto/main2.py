import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from semantic_visitor import SemanticVisitor
import unittest

def analyze_file(file_path):
    """Analiza un archivo y devuelve el visitor con los resultados"""
    input_stream = FileStream(file_path)
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    
    # Análisis sintáctico
    tree = parser.program()
    
    # Análisis semántico
    analyzer = SemanticVisitor()
    analyzer.visit(tree)
    
    return analyzer

def analyze_code(code_string):
    """Analiza un string de código y devuelve el visitor con los resultados"""
    input_stream = InputStream(code_string)
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    
    # Análisis sintáctico
    tree = parser.program()
    
    # Análisis semántico
    analyzer = SemanticVisitor()
    analyzer.visit(tree)
    
    return analyzer

def main(argv):
    if len(argv) < 2:
        print("Uso: python main.py <archivo_entrada>")
        sys.exit(1)
    
    analyzer = analyze_file(argv[1])
    
    # Resultados
    if analyzer.errors:
        print("\n=== Errores encontrados ===")
        for error in analyzer.errors:
            print(error)
    else:
        print("\nAnálisis semántico completado sin errores")
        
    # Mostrar tabla de símbolos (debug)
    print("\n=== Tabla de Símbolos ===")
    for scope in analyzer.symbol_table.all_scopes:
        print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
        for name, symbol in scope.symbols.items():
            print(f"  {symbol}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Si no hay argumentos, ejecutar pruebas
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
    else:
        main(sys.argv)