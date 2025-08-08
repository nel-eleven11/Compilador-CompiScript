import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor
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

class MyVisitor(CompiscriptVisitor):
    # metodos del visitor
    def visitVariableDeclaration(self, ctx):
        var_name = ctx.Identifier().getText()
        print(f"Variable declarada: {var_name}")
        return self.visitChildren(ctx)

def main(argv):
    # archivo de input
    input_stream = FileStream(argv[1])
    
    # lexer
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    
    print("\nTokens encontrados:")
    stream.fill()  # Cargar todos los tokens
    for token in stream.tokens:
        if token.channel != Token.HIDDEN_CHANNEL:
            print(f"{lexer.symbolicNames[token.type]} -> '{token.text}'")
    
    # parser
    parser = CompiscriptParser(stream)
    tree = parser.program()

    # guardando el ast en un JSON
    ast_json = tree_to_json(tree, parser, lexer)
    with open('ast.json', 'w') as f:
        json.dump(ast_json, f, indent=2)

    print("Árbol sintáctico guardado en ast.json")
    
    ### par verlo en consola
    #print("\nRepresentación JSON del árbol:")
    #print(json.dumps(ast_json, indent=2))
    
    ### esto es para printearlo en forma de texto sin json
    #print("\nÁrbol de análisis sintáctico:")
    #print(Trees.toStringTree(tree, None, parser))
    
    # arbol con visitor
    visitor = MyVisitor()
    visitor.visit(tree)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python main.py <archivo_entrada>")
        sys.exit(1)
    main(sys.argv)