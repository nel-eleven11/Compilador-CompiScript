import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from semantic_visitor import SemanticVisitor
from antlr4.tree.Trees import Trees
import json

def tree_to_json(node, parser, lexer=None):
    # Para nodos terminales (tokens)
    if isinstance(node, TerminalNode):
        token = node.getSymbol()
        token_type = lexer.symbolicNames[token.type] if lexer else token.type
        return {
            "type": "TOKEN",
            "name": token_type,
            "text": token.text,
            "line": token.line,
            "column": token.column
        }
    
    # Para nodos de reglas (no terminales)
    rule_name = parser.ruleNames[node.getRuleIndex()] if hasattr(node, 'getRuleIndex') else type(node).__name__
    
    result = {
        "type": rule_name,
        "children": []
    }
    
    # Agregar todos los hijos
    if hasattr(node, 'children'):
        for child in node.children:
            if child is not None:  # Filtrar nodos nulos
                result["children"].append(tree_to_json(child, parser, lexer))
    
    # Agregar información de posición para nodos no terminales
    if hasattr(node, 'start') and hasattr(node, 'stop'):
        result["start_line"] = node.start.line
        result["start_column"] = node.start.column
        result["end_line"] = node.stop.line
        result["end_column"] = node.stop.column
    
    return result

def _run_common(input_stream, ast_path="ast.json"):
    # lexer
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)

    print("\nTokens encontrados:")
    stream.fill()
    for token in stream.tokens:
        if token.channel != Token.HIDDEN_CHANNEL:
            print(f"{lexer.symbolicNames[token.type]} -> '{token.text}'")

    # parser
    parser = CompiscriptParser(stream)
    tree = parser.program()

    # AST → JSON
    ast_json = tree_to_json(tree, parser, lexer)
    with open(ast_path, "w", encoding="utf-8") as f:
        json.dump(ast_json, f, indent=2, ensure_ascii=False)
    print(f"Árbol sintáctico guardado en {ast_path}")

    analyzer = SemanticVisitor()
    analyzer.visit(tree)

    # resultados
    if analyzer.errors:
        error = getattr(analyzer, "errors", [])        
    else:
        print("\nAnálisis semántico completado sin errores")
        
    # 5. Mostrar tabla de símbolos (debug)
    try:
        print("\n=== Tabla de Símbolos ===")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")
    except Exception:
        # Si no existe symbol_table/all_scopes no reventar el proceso
        pass

    return {"ast": ast_json, "errors": error}


def run_from_text(source_code: str, ast_path="ast.json"):
    """API para el IDE: compila a partir del código en memoria."""
    input_stream = InputStream(source_code)
    return _run_common(input_stream, ast_path=ast_path)


def run_from_file(file_path: str, ast_path="ast.json"):
    """Compatibilidad CLI: compila a partir de un archivo."""
    input_stream = FileStream(file_path, encoding="utf-8")
    return _run_common(input_stream, ast_path=ast_path)


# --- CLI tradicional (opcional) ---
def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print("Uso: python main.py <archivo_entrada>")
        sys.exit(1)
    run_from_file(argv[1])


if __name__ == "__main__":
    main()