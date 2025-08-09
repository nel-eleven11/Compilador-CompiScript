grammar Compiscript;

// ------------------
// Parser Rules
// ------------------

program: statement* EOF;

statement
  : variableDeclaration
  | constantDeclaration
  | assignment
  | functionDeclaration
  | classDeclaration
  | expressionStatement
  | printStatement
  | block
  | ifStatement
  | whileStatement
  | doWhileStatement
  | forStatement
  | foreachStatement
  | tryCatchStatement
  | switchStatement
  | breakStatement
  | continueStatement
  | returnStatement
  ;

block: LBRACE statement* RBRACE;

variableDeclaration
  : (LET | VAR) Identifier typeAnnotation? initializer? SEMICOLON
  ;

constantDeclaration
  : CONST Identifier typeAnnotation? ASSIGN expression SEMICOLON
  ;

typeAnnotation: COLON type;
initializer: ASSIGN expression;

assignment
  : Identifier ASSIGN expression SEMICOLON
  | expression DOT Identifier ASSIGN expression SEMICOLON // property assignment
  ;

expressionStatement: expression SEMICOLON;
printStatement: PRINT LPAREN expression RPAREN SEMICOLON;

ifStatement: IF LPAREN expression RPAREN block (ELSE block)?;
whileStatement: WHILE LPAREN expression RPAREN block;
doWhileStatement: DO block WHILE LPAREN expression RPAREN SEMICOLON;
forStatement: FOR LPAREN (variableDeclaration | assignment | SEMICOLON) expression? SEMICOLON expression? RPAREN block;
foreachStatement: FOREACH LPAREN Identifier IN expression RPAREN block;
breakStatement: BREAK SEMICOLON;
continueStatement: CONTINUE SEMICOLON;
returnStatement: RETURN expression? SEMICOLON;

tryCatchStatement: TRY block CATCH LPAREN Identifier RPAREN block;

switchStatement: SWITCH LPAREN expression RPAREN LBRACE switchCase* defaultCase? RBRACE;
switchCase: CASE expression COLON statement*;
defaultCase: DEFAULT COLON statement*;

functionDeclaration: FUNCTION Identifier LPAREN parameters? RPAREN (COLON type)? block;
parameters: parameter (COMMA parameter)*;
parameter: Identifier (COLON type)?;

classDeclaration: CLASS Identifier (COLON Identifier)? LBRACE classMember* RBRACE;
classMember: functionDeclaration | variableDeclaration | constantDeclaration;

// ------------------
// Expression Rules — Operator Precedence
// ------------------

expression: assignmentExpr;

assignmentExpr
  : lhs=leftHandSide ASSIGN assignmentExpr                      # AssignExpr
  | lhs=leftHandSide DOT Identifier ASSIGN assignmentExpr       # PropertyAssignExpr
  | conditionalExpr                                             # ExprNoAssign
  ;

conditionalExpr
  : logicalOrExpr (QUESTION expression COLON expression)?       # TernaryExpr
  ;

logicalOrExpr
  : logicalAndExpr (OR logicalAndExpr)*
  ;

logicalAndExpr
  : equalityExpr (AND equalityExpr)*
  ;

equalityExpr
  : relationalExpr ((EQ | NEQ) relationalExpr)*
  ;

relationalExpr
  : additiveExpr ((LT | LE | GT | GE) additiveExpr)*
  ;

additiveExpr
  : multiplicativeExpr ((PLUS | MINUS) multiplicativeExpr)*
  ;

multiplicativeExpr
  : unaryExpr ((MULT | DIV | MOD) unaryExpr)*
  ;

unaryExpr
  : (MINUS | NOT) unaryExpr
  | primaryExpr
  ;

primaryExpr
  : literalExpr
  | leftHandSide
  | LPAREN expression RPAREN
  ;

literalExpr
  : Literal
  | arrayLiteral
  | NULL
  | TRUE
  | FALSE
  ;

leftHandSide
  : primaryAtom (suffixOp)*
  ;

primaryAtom
  : Identifier                                 # IdentifierExpr
  | NEW Identifier LPAREN arguments? RPAREN    # NewExpr
  | THIS                                       # ThisExpr
  ;

suffixOp
  : LPAREN arguments? RPAREN                   # CallExpr
  | LBRACK expression RBRACK                   # IndexExpr
  | DOT Identifier                             # PropertyAccessExpr
  ;

arguments: expression (COMMA expression)*;

arrayLiteral: LBRACK (expression (COMMA expression)*)? RBRACK;

// ------------------
// Types
// ------------------

type: baseType (LBRACK RBRACK)*;
baseType: BOOLEAN | INTEGER | STRING | Identifier;

// ------------------
// Lexer Rules
// ------------------
CONST: 'const';
LET: 'let';
VAR: 'var';
FUNCTION: 'function';
CLASS: 'class';
PRINT: 'print';
IF: 'if';
ELSE: 'else';
WHILE: 'while';
DO: 'do';
FOR: 'for';
FOREACH: 'foreach';
IN: 'in';
BREAK: 'break';
CONTINUE: 'continue';
RETURN: 'return';
TRY: 'try';
CATCH: 'catch';
SWITCH: 'switch';
CASE: 'case';
DEFAULT: 'default';
NEW: 'new';
THIS: 'this';
NULL: 'null';
TRUE: 'true';
FALSE: 'false';
BOOLEAN: 'boolean';
INTEGER: 'integer';
STRING: 'string';

// Operadores y símbolos
ASSIGN: '=';
COLON: ':';
SEMICOLON: ';';
COMMA: ',';
DOT: '.';
LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
LBRACK: '[';
RBRACK: ']';
QUESTION: '?';
PLUS: '+';
MINUS: '-';
MULT: '*';
DIV: '/';
MOD: '%';
NOT: '!';
EQ: '==';
NEQ: '!=';
LT: '<';
LE: '<=';
GT: '>';
GE: '>=';
AND: '&&';
OR: '||';

Literal
  : IntegerLiteral
  | StringLiteral
  ;

IntegerLiteral: [0-9]+;
StringLiteral: '"' (~["\r\n])* '"';

Identifier: [a-zA-Z_][a-zA-Z0-9_]*;

WS: [ \t\r\n]+ -> skip;
LINE_COMMENT: '//' ~[\r\n]* -> skip;
BLOCK_COMMENT: '/*' .*? '*/' -> skip;
