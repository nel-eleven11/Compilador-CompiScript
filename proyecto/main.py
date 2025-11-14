import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from semantic_visitor import SemanticVisitor
from antlr4.tree.Trees import Trees
from classes.MIPS_generator import MIPSGenerator
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


# --- Serializar la tabla de símbolos ---
def _type_name(t):
    try:
        return t.name if t else None
    except Exception:
        return None

def _serialize_symbol(sym):
    base = {
        "name": getattr(sym, "name", None),
        "category": getattr(sym, "category", None),
        "scope_id": getattr(sym, "scope_id", None),
        "type": _type_name(getattr(sym, "type", None)),
    }
    from classes.symbols import VariableSymbol, FunctionSymbol, ClassSymbol
    if isinstance(sym, VariableSymbol):
        base.update({
            "is_const": getattr(sym, "is_const", False),
            "is_type_inferred": getattr(sym, "is_type_inferred", False),
        })
    elif isinstance(sym, FunctionSymbol):
        base.update({
            "return_type": _type_name(getattr(sym, "return_type", None)),
            "parameters": [{"name": p.name, "type": _type_name(p.type)} for p in sym.parameters],
        })
    elif isinstance(sym, ClassSymbol):
        base.update({
            "parent": getattr(sym.parent_class, "name", None),
            "attributes": [{"name": a.name, "type": _type_name(a.type), "is_const": getattr(a, "is_const", False)}
                           for a in sym.attributes.values()],
            "methods": [{"name": m.name, "return_type": _type_name(m.return_type),
                         "parameters": [{"name": p.name, "type": _type_name(p.type)} for p in m.parameters]}
                        for m in sym.methods.values()],
        })
    return base

def _serialize_symbol_table(symtab):
    data = []
    for scope in symtab.all_scopes:
        data.append({
            "scope_id": scope.scope_id,
            "scope_type": scope.scope_type,
            "parent_id": scope.parent.scope_id if getattr(scope, "parent", None) else None,
            "symbols": [_serialize_symbol(s) for s in scope.symbols.values()],
        })
    return data

#  Serializar los cuádruplos a una lista de dicts 
def _serialize_quadruples(quad_list):
    out = []
    for q in quad_list:
        out.append({
            "op": getattr(q, "op", None),
            "arg1": getattr(q, "arg1", None),
            "arg2": getattr(q, "arg2", None),
            "result": getattr(q, "result", None),
        })
    return out

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

    # AST -> JSON
    ast_json = tree_to_json(tree, parser, lexer)
    with open(ast_path, "w", encoding="utf-8") as f:
        json.dump(ast_json, f, indent=2, ensure_ascii=False)
    print(f"Árbol sintáctico guardado en {ast_path}")

    analyzer = SemanticVisitor()
    analyzer.visit(tree)

    # Código intermedio (cuadruplos)
    print("\n")
    analyzer.codegen.print_quadruples()
    print("\n")
    analyzer.codegen.print_memory_map()

    quadruples_json = _serialize_quadruples(analyzer.codegen.get_quadruples())

    # Resultados
    errors = list(getattr(analyzer, "errors", []))
    if not errors:
        print("\nAnálisis semántico completado sin errores")
    
    symbols_json = _serialize_symbol_table(analyzer.symbol_table)

    # Generar código MIPS si no hay errores
    mips_code = ""
    if not errors:
        mips_gen = MIPSGenerator(analyzer.codegen, analyzer.symbol_table)
        mips_code = mips_gen.generate_mips_code()
        print("\n=== CÓDIGO MIPS GENERADO ===\n")
        print(mips_code)

    return {
        "ast": ast_json,
        "errors": errors,
        "symbols": symbols_json,
        "quadruples": quadruples_json,
        "mips_code": mips_code,
    }


def run_from_text(source_code: str, ast_path="ast.json"):
    """API para el IDE: compila a partir del código en memoria."""
    input_stream = InputStream(source_code)
    return _run_common(input_stream, ast_path=ast_path)


def run_from_file(file_path: str, ast_path="ast.json"):
    """Compatibilidad CLI: compila a partir de un archivo."""
    input_stream = FileStream(file_path, encoding="utf-8")
    return _run_common(input_stream, ast_path=ast_path)


# --- CLI tradicional ---
def main(argv=None):
    argv = argv or sys.argv
    if len(argv) < 2:
        print("Uso: python main.py <archivo_entrada>")
        sys.exit(1)
    run_from_file(argv[1])


if __name__ == "__main__":
    main()