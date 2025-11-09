import sys
import os
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from semantic_visitor import SemanticVisitor
from classes.MIPS_generator import MIPSGenerator
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

    if analyzer.warnings:
        print("\nWarnings")
        for warning in analyzer.warnings:
            print(warning)
        
    # Mostrar tabla de símbolos (debug)
    print("\n=== Tabla de Símbolos ===")
    for scope in analyzer.symbol_table.all_scopes:
        print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
        for name, symbol in scope.symbols.items():
            print(f"  {symbol}")

    # Mostrar TAC, con cuadruplos
    print("\n")
    analyzer.codegen.print_quadruples()

    print("\n")
    analyzer.codegen.print_memory_map()

    # Generar código MIPS
    if not analyzer.errors:
        print("\n=== GENERANDO CÓDIGO MIPS ===\n")
        mips_gen = MIPSGenerator(analyzer.codegen, analyzer.symbol_table)
        mips_code = mips_gen.generate_mips_code()

        # Determinar nombre y ubicación del archivo de salida
        input_file = argv[1]
        base_name = os.path.basename(input_file)
        file_name = os.path.splitext(base_name)[0]

        # Guardar en la carpeta test_asm
        output_dir = "test_asm"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{file_name}.asm")

        with open(output_file, 'w') as f:
            f.write(mips_code)

        print(f"Código MIPS generado en: {output_file}")
        print("\n=== CÓDIGO MIPS GENERADO ===\n")
        print(mips_code)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Si no hay argumentos, ejecutar pruebas
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
    else:
        main(sys.argv)