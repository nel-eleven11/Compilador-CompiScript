import unittest
import os
from pathlib import Path
from main2 import analyze_file

def print_results(analyzer):
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

class TestSemanticAnalysis(unittest.TestCase):
    TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), 'test_files')
    
    def test_variables_declaration(self):
        """Prueba la declaración de variables"""
        file_path = os.path.join(self.TEST_FILES_DIR, 'variables_test.cps')
        analyzer = analyze_file(file_path)
        
        # Verifica que no hay errores
        self.assertEqual(len(analyzer.errors), 0, 
                        f"Se encontraron errores: {analyzer.errors}")
        
        # Verifica que las variables están en la tabla de símbolos del scope global, el cual es el primer scope dentro de la tabla
        global_scope = analyzer.symbol_table.all_scopes[0]
        self.assertIn('PI', global_scope.symbols)
        self.assertIn('greeting', global_scope.symbols)
        self.assertIn('flag', global_scope.symbols)
        self.assertIn('a1', global_scope.symbols)
        self.assertIn('b1', global_scope.symbols)
        self.assertIn('c1', global_scope.symbols)
        self.assertIn('d1', global_scope.symbols)
        
        # Verifica los tipos
        self.assertEqual(global_scope.symbols['PI'].type.name, 'integer')
        self.assertEqual(global_scope.symbols['greeting'].type.name, 'string')
        self.assertEqual(global_scope.symbols['flag'].type.name, 'boolean')
        self.assertEqual(global_scope.symbols['a1'].type.name, 'integer')
        self.assertEqual(global_scope.symbols['b1'].type.name, 'string')
        self.assertEqual(global_scope.symbols['c1'].type.name, 'boolean')
        self.assertEqual(global_scope.symbols['d1'].type.name, 'null')

        print("\n\nPrueba de variables------------------------------------------")
        print_results(analyzer)

class TestScopeAnalysis(unittest.TestCase):
    TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), 'test_files')
    
    def setUp(self):
        """Cargar el archivo de prueba una vez para todos los tests"""
        file_path = os.path.join(self.TEST_FILES_DIR, 'scope_test.cps')
        self.analyzer = analyze_file(file_path)
        
    def test_no_errors(self):
        """Verifica que no hay errores semánticos"""
        self.assertEqual(len(self.analyzer.errors), 0, 
                        f"Se encontraron errores: {self.analyzer.errors}")
    
    def test_scope_count(self):
        # Deberían ser 4 scopes: global + 3 funciones
        self.assertEqual(len(self.analyzer.symbol_table.all_scopes), 4)
    
    def test_global_scope_content(self):
        """Verifica el contenido del scope global"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        # Verifica variables y funciones en el scope global
        self.assertEqual(len(global_scope.symbols), 4)  # 1 variable + 3 funciones
        
        # Verifica la variable 't'
        self.assertIn('t', global_scope.symbols)
        t_var = global_scope.symbols['t']
        self.assertEqual(t_var.type.name, 'boolean')
        self.assertFalse(t_var.is_const)  # No es constante
        
        # Verifica las funciones
        self.assertIn('greet_a', global_scope.symbols)
        self.assertIn('greet2_extra', global_scope.symbols)
        self.assertIn('greet_num_2', global_scope.symbols)
        
        # Verifica detalles de una función
        greet_a_func = global_scope.symbols['greet_a']
        self.assertEqual(greet_a_func.return_type.name, 'void')
        self.assertEqual(len(greet_a_func.parameters), 1)
        self.assertEqual(greet_a_func.parameters[0].type.name, 'string')
    
    def test_function_scopes_content(self):
        """Verifica el contenido de los scopes de función"""
        # Scope de greet_a (scope_id=1)
        scope_1 = self.analyzer.symbol_table.all_scopes[1]
        self.assertEqual(scope_1.scope_type, 'function')
        self.assertEqual(len(scope_1.symbols), 3)  # name, new_name, casa
        
        self.assertIn('name', scope_1.symbols)
        self.assertEqual(scope_1.symbols['name'].type.name, 'string')
        
        self.assertIn('new_name', scope_1.symbols)
        self.assertEqual(scope_1.symbols['new_name'].type.name, 'string')
        
        self.assertIn('casa', scope_1.symbols)
        self.assertEqual(scope_1.symbols['casa'].type.name, 'integer')
        
        # Scope de greet2_extra (scope_id=2)
        scope_2 = self.analyzer.symbol_table.all_scopes[2]
        self.assertEqual(scope_2.scope_type, 'function')
        self.assertEqual(len(scope_2.symbols), 2)  # name2, t
        
        self.assertIn('name2', scope_2.symbols)
        self.assertEqual(scope_2.symbols['name2'].type.name, 'string')
        
        self.assertIn('t', scope_2.symbols)
        self.assertEqual(scope_2.symbols['t'].type.name, 'string')
        self.assertTrue(scope_2.symbols['t'].is_const)  # Es constante
        
        # Scope de greet_num_2 (scope_id=3)
        scope_3 = self.analyzer.symbol_table.all_scopes[3]
        self.assertEqual(scope_3.scope_type, 'function')
        self.assertEqual(len(scope_3.symbols), 2)  # name3, num
        
        self.assertIn('name3', scope_3.symbols)
        self.assertEqual(scope_3.symbols['name3'].type.name, 'string')
        
        self.assertIn('num', scope_3.symbols)
        self.assertEqual(scope_3.symbols['num'].type.name, 'integer')
    
    def test_shadowing_variable(self):
        """Verifica que la variable 't' en greet2_extra hace shadowing de la global"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        scope_2 = self.analyzer.symbol_table.all_scopes[2]
        
        # 't' en scope global es boolean
        global_t = global_scope.symbols['t']
        self.assertEqual(global_t.type.name, 'boolean')
        
        # 't' en scope 2 es string y constante
        local_t = scope_2.symbols['t']
        self.assertEqual(local_t.type.name, 'string')
        self.assertTrue(local_t.is_const)
        
        # Son símbolos diferentes
        self.assertNotEqual(global_t, local_t)

        print("\n\nPrueba de scope ------------------------------------------")
        print_results(self.analyzer)

class TestNumericOperations(unittest.TestCase):
    TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), 'test_files')
    
    def setUp(self):
        """Cargar el archivo de prueba una vez para todos los tests"""
        file_path = os.path.join(self.TEST_FILES_DIR, 'num_operations_test.cps')
        self.analyzer = analyze_file(file_path)
        
    def test_no_errors(self):
        """Verifica que no hay errores semánticos"""
        self.assertEqual(len(self.analyzer.errors), 0, 
                        f"Se encontraron errores: {self.analyzer.errors}")
    
    def test_global_scope_variables(self):
        """Verifica que todas las variables están declaradas en el scope global"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        # Verifica que las variables están presentes
        expected_vars = {'a', 'b', 'c', 'x', 'y', 'z', 'result'}
        declared_vars = set(global_scope.symbols.keys())
        
        # Eliminamos las funciones (si las hubiera) para solo ver variables
        declared_vars = {name for name in declared_vars 
                        if global_scope.symbols[name].category == 'variable'}
        
        self.assertEqual(declared_vars, expected_vars,
                        f"Faltan variables: {expected_vars - declared_vars}")
    
    def test_variable_types(self):
        """Verifica que todas las variables son de tipo integer"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        for var_name, symbol in global_scope.symbols.items():
            if symbol.category == 'variable':  # Solo verificamos variables, no funciones
                self.assertEqual(symbol.type.name, 'integer',
                               f"La variable {var_name} debería ser integer pero es {symbol.type.name}")
    
    def test_constant_expressions(self):
        """Verifica expresiones constantes (asignaciones directas)"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        self.assertIn('a', global_scope.symbols)
        self.assertIn('b', global_scope.symbols)
        self.assertIn('c', global_scope.symbols)
    
    def test_variable_based_expressions(self):
        """Verifica expresiones basadas en otras variables"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        # Verifica que las variables base existen
        self.assertIn('x', global_scope.symbols)
        self.assertIn('y', global_scope.symbols)
        self.assertIn('z', global_scope.symbols)
        
    
    def test_chained_operations(self):
        """Verifica operaciones encadenadas"""
        global_scope = self.analyzer.symbol_table.all_scopes[0]
        
        self.assertIn('result', global_scope.symbols)
        result_var = global_scope.symbols['result']
        self.assertEqual(result_var.type.name, 'integer')

        print("\n\nPrueba de operaciones aritmeticas ------------------------------------------")
        print_results(self.analyzer)

class TestLogicalOperations(unittest.TestCase):
    TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), 'test_files')
    
    def setUp(self):
        """Cargar el archivo de prueba una vez para todos los tests"""
        file_path = os.path.join(self.TEST_FILES_DIR, 'logical_operations_test.cps')
        self.analyzer = analyze_file(file_path)
        self.global_scope = self.analyzer.symbol_table.all_scopes[0]
        
    def test_no_errors(self):
        """Verifica que no hay errores semánticos en operaciones lógicas"""
        self.assertEqual(len(self.analyzer.errors), 0, 
                        f"Se encontraron errores: {self.analyzer.errors}")
    
    def test_all_variables_boolean(self):
        """Verifica que todas las variables son de tipo boolean"""
        for var_name, symbol in self.global_scope.symbols.items():
            if symbol.category == 'variable':
                self.assertEqual(symbol.type.name, 'boolean',
                               f"La variable {var_name} debería ser boolean pero es {symbol.type.name}")
    
    def test_basic_logical_operations(self):
        """Verifica las operaciones lógicas básicas (AND, OR, NOT)"""
        self.assertIn('a', self.global_scope.symbols)
        self.assertIn('b', self.global_scope.symbols)
        self.assertIn('c', self.global_scope.symbols)
        
    
    def test_equality_comparisons(self):
        """Verifica las comparaciones de igualdad"""
        self.assertIn('g', self.global_scope.symbols)  # 5 == 5
        self.assertIn('h', self.global_scope.symbols)  # "a" == "a"
        self.assertIn('i', self.global_scope.symbols)  # null == null
        self.assertIn('j', self.global_scope.symbols)  # "texto" == null
        
        # Verifica que las comparaciones entre tipos diferentes no generan errores
    
    def test_relational_operations(self):
        """Verifica las operaciones relacionales"""
        self.assertIn('n', self.global_scope.symbols)  # 5 < 10
        self.assertIn('o', self.global_scope.symbols)  # 10 >= 5
        
    
    def test_combined_expressions(self):
        """Verifica expresiones combinadas más complejas"""
        self.assertIn('pa', self.global_scope.symbols)  # (1 == 1) != (2 > 3)
        self.assertIn('pb', self.global_scope.symbols)  # "hola" == null
        self.assertIn('ps', self.global_scope.symbols)  # true && (5 == 5)

        print("\n\nPrueba de operaciones logicas ------------------------------------------")
        print_results(self.analyzer)

class TestFunctionSemantics(unittest.TestCase):
    """Tests for function-related semantic rules"""
    
    def setUp(self):
        """Configurar variables para las pruebas"""
        from main2 import analyze_code
        self.analyze_code = analyze_code
    
    def test_function_declaration_and_calls(self):
        """Test valid function declarations and calls"""
        code = '''
        function add(a: integer, b: integer): integer {
            return a + b;
        }
        
        function greet(name: string): string {
            return "Hello " + name;
        }
        
        function printNumber(num: integer) {
            // void function
        }
        
        let result: integer = add(5, 10);
        let greeting: string = greet("World");
        '''
        
        analyzer = self.analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
        
        # Verify function symbols exist
        global_scope = analyzer.symbol_table.all_scopes[0]
        self.assertIn('add', global_scope.symbols)
        self.assertIn('greet', global_scope.symbols)
        self.assertIn('printNumber', global_scope.symbols)
        
        print("\n\nPrueba de declaraciones y llamadas de funciones ------------------------------------------")
        print("Esta prueba verifica:")
        print("- Declaración correcta de funciones con diferentes tipos de retorno")
        print("- Función 'add' que retorna integer y recibe 2 parámetros integer")
        print("- Función 'greet' que retorna string y usa concatenación")
        print("- Función 'printNumber' void (sin tipo de retorno especificado)")
        print("- Llamadas a funciones con argumentos correctos")
        print("- Asignación de valores de retorno a variables del tipo apropiado")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
        
        print("\n=== Tabla de Símbolos ===")
        print("Verifica que las funciones y variables están correctamente registradas:")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")
    
    def test_function_argument_validation(self):
        """Test function argument number and type validation"""
        code = '''
        function multiply(x: integer, y: integer): integer {
            return x * y;
        }
        
        let result1: integer = multiply(5);
        let result2: integer = multiply("text", 5);
        let result3: integer = multiply(1, 2, 3);
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        
        # Verificar que hay errores específicos
        error_messages = ' '.join(analyzer.errors)
        self.assertTrue("espera 2 argumentos, recibió 1" in error_messages)
        self.assertTrue("espera 2 argumentos, recibió 3" in error_messages)
        
        print("\n\nPrueba de validación de argumentos de funciones ------------------------------------------")
        print("Esta prueba verifica la detección de errores en llamadas a funciones:")
        print("- Función 'multiply' declarada correctamente con 2 parámetros integer")
        print("- Caso 1: multiply(5) - Error: falta 1 argumento (espera 2, recibe 1)")
        print("- Caso 2: multiply('text', 5) - Error: primer argumento es string, debe ser integer")
        print("- Caso 3: multiply(1, 2, 3) - Error: sobran argumentos (espera 2, recibe 3)")
        print("- Validación de número correcto de argumentos")
        print("- Validación de tipos correctos de argumentos")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")

    def test_function_return_type_validation(self):
        """Test function return type validation"""
        # Caso 1: Función que retorna tipo incorrecto
        code1 = '''
        function getString(): string {
            return 42;
        }
        '''
        
        analyzer1 = self.analyze_code(code1)
        self.assertGreater(len(analyzer1.errors), 0)
        self.assertTrue(any("Tipo de retorno no coincide" in error for error in analyzer1.errors))
        
        # Caso 2: Función void que retorna valor
        code2 = '''
        function doSomething() {
            return 42;
        }
        '''
        
        analyzer2 = self.analyze_code(code2)
        self.assertGreater(len(analyzer2.errors), 0)
        self.assertTrue(any("void no debe retornar valor" in error for error in analyzer2.errors))
        
        # Caso 3: Función sin return cuando debería tenerlo
        code3 = '''
        function getNumber(): integer {
            let x: integer = 5;
        }
        '''
        
        analyzer3 = self.analyze_code(code3)
        self.assertGreater(len(analyzer3.errors), 0)
        self.assertTrue(any("debe retornar un valor" in error for error in analyzer3.errors))
        
        print("\n\nPrueba de validación de tipos de retorno ------------------------------------------")
        print("Esta prueba verifica la correcta validación de tipos de retorno en funciones:")
        print("- PRIORIDAD: Validación exhaustiva de tipos de retorno")
        print("- Caso 1: getString() declara retorno string pero retorna integer (42)")
        print("- Caso 2: doSomething() es función void pero intenta retornar valor (42)")
        print("- Caso 3: getNumber() declara retorno integer pero no tiene statement return")
        print("- Detección de inconsistencias entre tipo declarado y tipo retornado")
        print("- Validación de funciones que requieren return pero no lo tienen")
        print("- Validación de funciones void que no deben retornar valores")
        
        all_errors = analyzer1.errors + analyzer2.errors + analyzer3.errors
        if all_errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(all_errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")

    def test_multiple_function_declarations(self):
        """Test detection of multiple function declarations with same name"""
        code = '''
        function calculate(x: integer): integer {
            return x * 2;
        }
        
        function calculate(y: string): string {
            return y + y;
        }
        
        function process(): void {
        }
        
        function process(data: integer): integer {
            return data;
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        
        # Verificar que detecta funciones duplicadas
        error_messages = ' '.join(analyzer.errors)
        self.assertTrue("ya declarada" in error_messages)
        
        # Debería haber al menos 1 error por cada función duplicada detectada
        duplicate_errors = [error for error in analyzer.errors if "ya declarada" in error]
        self.assertGreaterEqual(len(duplicate_errors), 1)
        
        print("\n\nPrueba de declaraciones múltiples de funciones ------------------------------------------")
        print("Esta prueba verifica la detección de funciones con nombres duplicados:")
        print("- RESALTADO: Característica crítica para evitar ambigüedad")
        print("- Caso 1: 'calculate' declarada 2 veces con diferentes tipos de parámetros")
        print("  - Primera: calculate(x: integer): integer")
        print("  - Segunda: calculate(y: string): string (DUPLICADA)")
        print("- Caso 2: 'process' declarada 2 veces con diferentes signatures")
        print("  - Primera: process(): void")
        print("  - Segunda: process(data: integer): integer (DUPLICADA)")
        print("- CompiScript no soporta sobrecarga de funciones")
        print("- Debe detectar nombres duplicados independientemente de parámetros")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")

    def test_recursive_functions(self):
        """Test support for recursive functions"""
        code = '''
        function factorial(n: integer): integer {
            if (n <= 1) {
                return 1;
            }
            return n * factorial(n - 1);
        }
        
        function fibonacci(n: integer): integer {
            if (n <= 1) {
                return n;
            }
            return fibonacci(n - 1) + fibonacci(n - 2);
        }
        
        let fact5: integer = factorial(5);
        let fib10: integer = fibonacci(10);
        '''
        
        analyzer = self.analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores en funciones recursivas: {analyzer.errors}")
        
        # Verificar que las funciones están declaradas correctamente
        global_scope = analyzer.symbol_table.all_scopes[0]
        self.assertIn('factorial', global_scope.symbols)
        self.assertIn('fibonacci', global_scope.symbols)
        
        print("\n\nPrueba de funciones recursivas ------------------------------------------")
        print("Esta prueba verifica el soporte completo para funciones recursivas:")
        print("- Función factorial: ejemplo clásico de recursión simple")
        print("  - Caso base: n <= 1 retorna 1")
        print("  - Caso recursivo: n * factorial(n - 1)")
        print("- Función fibonacci: ejemplo de recursión múltiple")
        print("  - Caso base: n <= 1 retorna n")
        print("  - Caso recursivo: fibonacci(n-1) + fibonacci(n-2)")
        print("- Llamadas recursivas dentro del cuerpo de la función")
        print("- Uso correcto de las funciones recursivas: factorial(5), fibonacci(10)")
        print("- Validación de tipos en llamadas recursivas")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
            
        print("\n=== Tabla de Símbolos ===")
        print("Verifica registro correcto de funciones recursivas y variables:")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")
        
    def test_nested_functions_and_closures(self):
        """Test support for nested functions and closures"""
        code = '''
        function outerFunction(x: integer): integer {
            let outerVar: integer = x * 2;
            
            function innerFunction(y: integer): integer {
                return outerVar + y;
            }
            
            return innerFunction(5);
        }
        
        let result: integer = outerFunction(10);
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de funciones anidadas ------------------------------------------")
        print("Esta prueba evalúa el soporte para funciones anidadas y closures:")
        print("- Función externa 'outerFunction' con parámetro x: integer")
        print("- Variable local 'outerVar' en el scope externo")
        print("- Función anidada 'innerFunction' declarada dentro de outerFunction")
        print("- Acceso a variable del scope padre (outerVar) desde función anidada")
        print("- Llamada a función anidada desde función externa")
        print("- Comportamiento de closure: función interna accede a variables externas")
        print("- Manejo correcto de scopes anidados")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            print("Nota: Si hay errores, indica que la gramática no soporta funciones anidadas")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")
            print("Las funciones anidadas son soportadas correctamente")
            
        print("\n=== Tabla de Símbolos ===")
        print("Estructura de scopes para funciones anidadas:")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")
    
    def test_undefined_function_call(self):
        """Test calling undefined function"""
        code = '''
        let result: integer = unknownFunction(5);
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("no declarado" in error for error in analyzer.errors))

class TestControlFlowSemantics(unittest.TestCase):
    """Tests for control flow semantic rules"""
    
    def setUp(self):
        """Configurar variables para las pruebas"""
        from main2 import analyze_code
        self.analyze_code = analyze_code
    
    def test_boolean_conditions_valid(self):
        """Test that control flow statements accept valid boolean conditions"""
        code = '''
        let flag: boolean = true;
        let count: integer = 0;
        
        if (flag) {
            let x: integer = 5;
        }
        
        while (flag && count < 10) {
            count = count + 1;
        }
        
        do {
            count = count - 1;
        } while (count > 0);
        
        for (let i: integer = 0; i < 10; i = i + 1) {
            if (i > 5) {
                break;
            }
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores en condiciones válidas: {analyzer.errors}")
        
        print("\n\nPrueba de condiciones boolean válidas ------------------------------------------")
        print("Esta prueba verifica que todas las estructuras de control acepten condiciones boolean:")
        print("- if (flag): condición boolean simple válida")
        print("- while (flag && count < 10): expresión boolean compuesta válida")
        print("  - Operador lógico && entre boolean y comparación relacional")
        print("- do-while con condición (count > 0): comparación relacional válida")
        print("- for con condición (i < 10): comparación relacional en bucle")
        print("- Todas las condiciones evalúan a tipo boolean")
        print("- Uso correcto de break dentro de estructura de bucle")
        print("- Manejo adecuado de variables en diferentes scopes")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
            
        print("\n=== Tabla de Símbolos ===")
        print("Estructura de scopes generada por las estructuras de control:")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")
    
    def test_invalid_condition_types(self):
        """Test invalid condition types in control structures"""
        # Caso 1: if con condición no-boolean
        code_if = '''
        let num: integer = 5;
        if (num) {
            let x: integer = 10;
        }
        '''
        
        # Caso 2: while con condición no-boolean  
        code_while = '''
        let text: string = "hello";
        while (text) {
            break;
        }
        '''
        
        # Caso 3: do-while con condición no-boolean
        code_do_while = '''
        let arr: integer[] = [1, 2, 3];
        do {
            break;
        } while (arr);
        '''
        
        # Caso 4: for con condición no-boolean
        code_for = '''
        for (let i: integer = 0; i; i = i + 1) {
            break;
        }
        '''
        
        analyzer_if = self.analyze_code(code_if)
        analyzer_while = self.analyze_code(code_while) 
        analyzer_do_while = self.analyze_code(code_do_while)
        analyzer_for = self.analyze_code(code_for)
        
        # Verificar que cada caso produce errores
        self.assertGreater(len(analyzer_if.errors), 0)
        self.assertGreater(len(analyzer_while.errors), 0)
        self.assertGreater(len(analyzer_do_while.errors), 0)
        self.assertGreater(len(analyzer_for.errors), 0)
        
        # Verificar mensajes específicos
        self.assertTrue(any("debe ser boolean" in error for error in analyzer_if.errors))
        self.assertTrue(any("debe ser boolean" in error for error in analyzer_while.errors))
        self.assertTrue(any("debe ser boolean" in error for error in analyzer_do_while.errors))
        self.assertTrue(any("debe ser boolean" in error for error in analyzer_for.errors))
        
        print("\n\nPrueba de condiciones inválidas en control de flujo ------------------------------------------")
        print("Esta prueba verifica la detección de tipos incorrectos en condiciones:")
        print("- REGLA: Todas las estructuras de control requieren condiciones boolean")
        print("- Caso 1: if (num) - Error: 'num' es integer, debe ser boolean")
        print("- Caso 2: while (text) - Error: 'text' es string, debe ser boolean")
        print("- Caso 3: do-while (arr) - Error: 'arr' es array<integer>, debe ser boolean")
        print("- Caso 4: for (i) - Error: 'i' es integer, debe ser boolean")
        print("- Detección precisa del tipo incorrecto encontrado")
        print("- Mensajes de error descriptivos especificando tipo esperado vs encontrado")
        
        all_errors = analyzer_if.errors + analyzer_while.errors + analyzer_do_while.errors + analyzer_for.errors
        if all_errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(all_errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")

    def test_break_continue_validation(self):
        """Test break and continue validation inside and outside loops"""
        # Caso 1: break y continue fuera de bucles (ERROR)
        code_outside = '''
        function testBreakOutside() {
            break;
        }
        
        function testContinueOutside() {
            continue;
        }
        
        if (true) {
            break;
        }
        '''
        
        # Caso 2: break y continue dentro de bucles (VÁLIDO)
        code_inside = '''
        for (let i: integer = 0; i < 10; i = i + 1) {
            if (i == 5) {
                break;
            }
            if (i == 3) {
                continue;
            }
        }
        
        while (true) {
            break;
        }
        
        do {
            continue;
        } while (false);
        
        let numbers: integer[] = [1, 2, 3, 4, 5];
        foreach (num in numbers) {
            if (num > 3) {
                break;
            }
        }
        '''
        
        analyzer_outside = self.analyze_code(code_outside)
        analyzer_inside = self.analyze_code(code_inside)
        
        # Verificar errores fuera de bucles
        self.assertGreater(len(analyzer_outside.errors), 0)
        break_errors = [e for e in analyzer_outside.errors if "break solo puede usarse dentro de un bucle" in e]
        continue_errors = [e for e in analyzer_outside.errors if "continue solo puede usarse dentro de un bucle" in e]
        self.assertGreater(len(break_errors), 0)
        self.assertGreater(len(continue_errors), 0)
        
        # Verificar que dentro de bucles es válido
        self.assertEqual(len(analyzer_inside.errors), 0, f"Errores en break/continue válidos: {analyzer_inside.errors}")
        
        print("\n\nPrueba de validación de break y continue ------------------------------------------")
        print("Esta prueba verifica las reglas de uso de break y continue:")
        print("- REGLA: break y continue solo pueden usarse dentro de bucles")
        print("- Casos de ERROR (fuera de bucles):")
        print("  - break dentro de función: testBreakOutside()")
        print("  - continue dentro de función: testContinueOutside()")
        print("  - break dentro de if (no es bucle)")
        print("- Casos VÁLIDOS (dentro de bucles):")
        print("  - break/continue en for loop con condiciones")
        print("  - break en while loop")
        print("  - continue en do-while loop")
        print("  - break en foreach loop")
        print("- Validación correcta del contexto de bucle")
        
        if analyzer_outside.errors:
            print("\n=== Errores encontrados (casos inválidos) ===")
            for i, error in enumerate(analyzer_outside.errors, 1):
                print(f"{i}. {error}")
        
        if analyzer_inside.errors:
            print("\n=== Errores inesperados (casos válidos) ===")
            for error in analyzer_inside.errors:
                print(error)
        else:
            print("\nCasos válidos: Análisis semántico completado sin errores")

    def test_return_validation(self):
        """Test return statement validation inside and outside functions"""
        # Caso 1: return fuera de función (ERROR)
        code_outside = '''
        let x: integer = 5;
        return x;
        
        if (true) {
            return 42;
        }
        '''
        
        # Caso 2: return dentro de función (VÁLIDO)
        code_inside = '''
        function getValue(): integer {
            return 42;
        }
        
        function processData(data: integer): string {
            if (data > 0) {
                return "positive";
            } else {
                return "negative";
            }
        }
        
        function voidFunction() {
            if (true) {
                return;
            }
        }
        '''
        
        analyzer_outside = self.analyze_code(code_outside)
        analyzer_inside = self.analyze_code(code_inside)
        
        # Verificar errores fuera de funciones
        self.assertGreater(len(analyzer_outside.errors), 0)
        return_errors = [e for e in analyzer_outside.errors if "return fuera de función" in e]
        self.assertGreater(len(return_errors), 0)
        
        # Verificar que dentro de funciones es válido
        self.assertEqual(len(analyzer_inside.errors), 0, f"Errores en return válidos: {analyzer_inside.errors}")
        
        print("\n\nPrueba de validación de return ------------------------------------------")
        print("Esta prueba verifica las reglas de uso del statement return:")
        print("- REGLA: return solo puede usarse dentro de funciones")
        print("- Casos de ERROR (fuera de funciones):")
        print("  - return x; en scope global")
        print("  - return 42; dentro de if en scope global")
        print("- Casos VÁLIDOS (dentro de funciones):")
        print("  - getValue(): return con valor en función no-void")
        print("  - processData(): múltiples return en diferentes ramas (if/else)")
        print("  - voidFunction(): return sin valor en función void")
        print("- Validación correcta del contexto de función")
        print("- Return statements en estructuras de control dentro de funciones")
        
        if analyzer_outside.errors:
            print("\n=== Errores encontrados (casos inválidos) ===")
            for i, error in enumerate(analyzer_outside.errors, 1):
                print(f"{i}. {error}")
        
        if analyzer_inside.errors:
            print("\n=== Errores inesperados (casos válidos) ===")
            for error in analyzer_inside.errors:
                print(error)
        else:
            print("\nCasos válidos: Análisis semántico completado sin errores")

    def test_switch_statement_conditions(self):
        """Test switch statement condition validation"""
        code = '''
        let value: integer = 5;
        switch (value) {
            case 1:
                break;
            case 2:
                break;
            default:
                break;
        }
        
        let flag: boolean = true;
        switch (flag) {
            case true:
                break;
            case false:
                break;
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de switch statement ------------------------------------------")
        print("Esta prueba evalúa el soporte para switch statements:")
        print("- Switch con expresión integer: switch (value)")
        print("  - case 1, case 2, default")
        print("- Switch con expresión boolean: switch (flag)")
        print("  - case true, case false")
        print("- Uso de break en casos del switch")
        print("- Verificación de soporte en la gramática actual")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            print("Nota: Errores indican que switch no está soportado en la gramática actual")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nAnálisis semántico completado sin errores")
            print("Switch statements son soportados correctamente")

    def test_complex_control_flow_combinations(self):
        """Test complex combinations of control flow structures"""
        code = '''
        function complexFlow(data: integer[]): integer {
            let result: integer = 0;
            
            for (let i: integer = 0; i < 10; i = i + 1) {
                if (i > 5) {
                    while (result < 100) {
                        result = result + i;
                        if (result > 50) {
                            break;
                        }
                    }
                    continue;
                }
                
                do {
                    result = result + 1;
                    if (result > 30) {
                        break;
                    }
                } while (result < 20);
            }
            
            return result;
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores en control de flujo complejo: {analyzer.errors}")
        
        print("\n\nPrueba de control de flujo complejo ------------------------------------------")
        print("Esta prueba verifica combinaciones complejas de estructuras de control:")
        print("- Función 'complexFlow' con parámetro array y retorno integer")
        print("- Bucle for externo: for (i = 0; i < 10; i++)")
        print("- Estructura anidada compleja:")
        print("  - if (i > 5) dentro del for")
        print("  - while (result < 100) anidado en el if")
        print("  - if (result > 50) con break del while")
        print("  - continue del for después del while")
        print("  - do-while (result < 20) en la rama else del if principal")
        print("  - if (result > 30) con break del do-while")
        print("- Return al final de la función")
        print("- Validación de scopes anidados correctos")
        print("- Uso correcto de break/continue en contextos apropiados")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
            
        print("\n=== Tabla de Símbolos ===")
        print("Estructura compleja de scopes generada:")
        for scope in analyzer.symbol_table.all_scopes:
            print(f"\nÁmbito {scope.scope_id} ({scope.scope_type}):")
            for name, symbol in scope.symbols.items():
                print(f"  {symbol}")

class TestDeadCodeDetection(unittest.TestCase):
    """Tests for dead code detection"""
    
    def setUp(self):
        """Configurar variables para las pruebas"""
        from main2 import analyze_code
        self.analyze_code = analyze_code
    
    def test_dead_code_after_return(self):
        """Test detection of dead code after return statements"""
        code = '''
        function testDeadCode(): integer {
            let x: integer = 5;
            return x;
            let y: integer = 10;  // Dead code
            x = x + 1;           // Dead code
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        # Verificar que se detectó código muerto
        self.assertGreater(len(analyzer.warnings), 0)
        
        print("\n\nPrueba de detección de código muerto después de return ------------------------------------------")
        print("Esta prueba verifica la detección de código inalcanzable después de return:")
        print("- Función testDeadCode() con return válido")
        print("- let y: integer = 10; después del return (CÓDIGO MUERTO)")
        print("- x = x + 1; después del return (CÓDIGO MUERTO)")
        print("- Detección automática de código inalcanzable")
        
        if analyzer.warnings:
            print("\n=== Advertencias encontradas ===")
            for i, warning in enumerate(analyzer.warnings, 1):
                print(f"{i}. {warning}")
        else:
            print("\nNo se detectaron advertencias de código muerto")
            
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
    
    def test_dead_code_after_break_continue(self):
        """Test detection of dead code after break and continue"""
        code = '''
        function testLoopDeadCode(): void {
            for (let i: integer = 0; i < 10; i = i + 1) {
                if (i == 5) {
                    break;
                    let unused: integer = 42;  // Dead code
                }
                if (i == 3) {
                    continue;
                    i = i + 2;  // Dead code
                }
            }
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de detección de código muerto en bucles ------------------------------------------")
        print("Esta prueba verifica la detección de código inalcanzable después de break/continue:")
        print("- Bucle for con condiciones de break y continue")
        print("- let unused: integer = 42; después de break (CÓDIGO MUERTO)")
        print("- i = i + 2; después de continue (CÓDIGO MUERTO)")
        print("- Detección en contexto de bucles")
        
        if analyzer.warnings:
            print("\n=== Advertencias encontradas ===")
            for i, warning in enumerate(analyzer.warnings, 1):
                print(f"{i}. {warning}")
        else:
            print("\nNo se detectaron advertencias de código muerto")
            
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")
    
    def test_reachable_code_in_branches(self):
        """Test that code in different branches is not marked as dead"""
        code = '''
        function testBranches(flag: boolean): integer {
            if (flag) {
                return 1;
            } else {
                return 2;  // This should NOT be dead code
            }
        }
        
        function testValidFlow(): integer {
            let result: integer = 0;
            for (let i: integer = 0; i < 5; i = i + 1) {
                result = result + i;
            }
            return result;  // This should NOT be dead code
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de código alcanzable en ramas ------------------------------------------")
        print("Esta prueba verifica que el código válido NO se marque como muerto:")
        print("- return en rama else (VÁLIDO - no es código muerto)")
        print("- return después de bucle (VÁLIDO - no es código muerto)")
        print("- Diferenciación entre código muerto y ramas alternativas")
        
        if analyzer.warnings:
            print("\n=== Advertencias encontradas ===")
            for warning in analyzer.warnings:
                print(warning)
            print("NOTA: Si hay advertencias aquí, puede indicar falsos positivos")
        else:
            print("\nNo se detectaron advertencias (CORRECTO para esta prueba)")
            
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")

class TestSemanticExpressionValidation(unittest.TestCase):
    """Tests for semantic expression validation"""
    
    def setUp(self):
        """Configurar variables para las pruebas"""
        from main2 import analyze_code
        self.analyze_code = analyze_code
    
    def test_invalid_arithmetic_expressions(self):
        """Test detection of semantically invalid arithmetic expressions"""
        code = '''
        function testInvalidArithmetic(): void {
            let text: string = "hello";
            let flag: boolean = true;
            let number: integer = 42;
            
            let result1: integer = text + number;     // Error: string + integer
            let result2: boolean = flag + flag;       // Error: boolean + boolean
            let result3: string = number + text;      // Error: integer + string
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        
        print("\n\nPrueba de validación de expresiones aritméticas inválidas ------------------------------------------")
        print("Esta prueba verifica la detección de expresiones aritméticas sin sentido semántico:")
        print("- text + number: string + integer (INVÁLIDO)")
        print("- flag + flag: boolean + boolean (INVÁLIDO)")
        print("- number + text: integer + string (INVÁLIDO)")
        print("- Solo se permiten: integer + integer, string + string")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nNo se detectaron errores (PROBLEMA: deberían haberse detectado)")
    
    def test_valid_arithmetic_expressions(self):
        """Test that valid arithmetic expressions are accepted"""
        code = '''
        function testValidArithmetic() {
            let num1: integer = 10;
            let num2: integer = 5;
            let text1: string = "Hello";
            let text2: string = "World";
            
            let sum: integer = num1 + num2;          // Valid: integer + integer
            let diff: integer = num1 - num2;         // Valid: integer - integer
            let product: integer = num1 * num2;      // Valid: integer * integer
            let quotient: integer = num1 / num2;     // Valid: integer / integer
            let remainder: integer = num1 % num2;    // Valid: integer % integer
            let greeting: string = text1 + " " + text2;  // Valid: string concatenation
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores inesperados: {analyzer.errors}")
        
        print("\n\nPrueba de validación de expresiones aritméticas válidas ------------------------------------------")
        print("Esta prueba verifica que las expresiones aritméticas válidas se acepten:")
        print("- integer + integer (suma)")
        print("- integer - integer (resta)")
        print("- integer * integer (multiplicación)")
        print("- integer / integer (división)")
        print("- integer % integer (módulo)")
        print("- string + string (concatenación)")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
            print("PROBLEMA: No deberían haber errores en expresiones válidas")
        else:
            print("\nAnálisis semántico completado sin errores")
            
        if analyzer.warnings:
            print("\n=== Advertencias encontradas ===")
            for warning in analyzer.warnings:
                print(warning)
    
    def test_division_by_zero_warning(self):
        """Test detection of potential division by zero"""
        code = '''
        function testDivisionByZero(): integer {
            let number: integer = 42;
            let zero: integer = 0;
            
            let result1: integer = number / 0;      // Warning: literal division by zero
            let result2: integer = number / zero;   // Potential warning if detectable
            
            return result1;
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de detección de división por cero ------------------------------------------")
        print("Esta prueba verifica la detección de posibles divisiones por cero:")
        print("- number / 0: división literal por cero (ADVERTENCIA)")
        print("- number / zero: división por variable cero (posible advertencia)")
        print("- Detección en tiempo de compilación cuando es posible")
        
        if analyzer.warnings:
            print("\n=== Advertencias encontradas ===")
            for i, warning in enumerate(analyzer.warnings, 1):
                print(f"{i}. {warning}")
        else:
            print("\nNo se detectaron advertencias de división por cero")
            
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for error in analyzer.errors:
                print(error)
        else:
            print("\nAnálisis semántico completado sin errores")

class TestEnhancedDuplicateDeclarations(unittest.TestCase):
    """Tests for enhanced duplicate declaration detection"""
    
    def setUp(self):
        """Configurar variables para las pruebas"""
        from main2 import analyze_code
        self.analyze_code = analyze_code
    
    def test_variable_constant_conflicts(self):
        """Test detection of conflicts between variables and constants"""
        code = '''
        function testConflicts(): void {
            let myVar: integer = 5;
            const myVar: integer = 10;    // Error: ya declarada como variable
            
            const myConst: string = "hello";
            let myConst: string = "world"; // Error: ya declarada como constante
        }
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        
        print("\n\nPrueba de conflictos entre variables y constantes ------------------------------------------")
        print("Esta prueba verifica la detección mejorada de declaraciones duplicadas:")
        print("- let myVar seguido de const myVar (CONFLICTO)")
        print("- const myConst seguido de let myConst (CONFLICTO)")
        print("- Detección específica del tipo de símbolo ya declarado")
        print("- Mensajes de error informativos sobre el tipo de conflicto")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nNo se detectaron errores (PROBLEMA: deberían haberse detectado)")
    
    def test_function_variable_conflicts(self):
        """Test detection of conflicts between functions and variables"""
        code = '''
        let calculate: integer = 42;
        
        function calculate(): integer {  // Error: ya declarada como variable
            return 10;
        }
        
        function process(): void {
        }
        
        let process: string = "text";    // Error: ya declarada como función
        '''
        
        analyzer = self.analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        
        print("\n\nPrueba de conflictos entre funciones y variables ------------------------------------------")
        print("Esta prueba verifica conflictos entre diferentes tipos de símbolos:")
        print("- let calculate seguido de function calculate (CONFLICTO)")
        print("- function process seguido de let process (CONFLICTO)")
        print("- Detección entre diferentes categorías de símbolos")
        print("- Identificación específica del tipo ya declarado")
        
        if analyzer.errors:
            print("\n=== Errores encontrados ===")
            for i, error in enumerate(analyzer.errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nNo se detectaron errores (PROBLEMA: deberían haberse detectado)")
    
    def test_scope_specific_duplicates(self):
        """Test that duplicates are detected per scope"""
        code = '''
        let globalVar: integer = 1;
        
        function testScopes(): void {
            let localVar: integer = 2;
            let localVar: string = "duplicate";  // Error: duplicate in same scope
            
            if (true) {
                let globalVar: integer = 3;      // OK: different scope
                let blockVar: integer = 4;
                const blockVar: integer = 5;     // Error: duplicate in block scope
            }
        }
        '''
        
        analyzer = self.analyze_code(code)
        
        print("\n\nPrueba de duplicados específicos por scope ------------------------------------------")
        print("Esta prueba verifica la detección de duplicados respetando scopes:")
        print("- localVar duplicada en mismo scope de función (ERROR)")
        print("- globalVar en scope de bloque (VÁLIDO - scope diferente)")
        print("- blockVar duplicada en mismo scope de bloque (ERROR)")
        print("- Respeto de jerarquía de scopes")
        
        # Should have errors for duplicates in same scope
        duplicate_errors = [error for error in analyzer.errors if "ya declarada" in error]
        if duplicate_errors:
            print("\n=== Errores de duplicados encontrados ===")
            for i, error in enumerate(duplicate_errors, 1):
                print(f"{i}. {error}")
        else:
            print("\nNo se detectaron errores de duplicados")
            
        if len(analyzer.errors) > len(duplicate_errors):
            print("\n=== Otros errores encontrados ===")
            other_errors = [error for error in analyzer.errors if "ya declarada" not in error]
            for error in other_errors:
                print(error)

class TestAssignmentAndTypeValidation(unittest.TestCase):
    """Tests for assignment and type validation rules"""
    
    def test_const_reassignment(self):
        """Test reassignment of constants"""
        code = '''
        const PI: integer = 314;
        PI = 315;  // Error: cannot reassign constant
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("No se puede reasignar la constante" in error for error in analyzer.errors))
    
    def test_undefined_variable_assignment(self):
        """Test assignment to undefined variable"""
        code = '''
        undefinedVar = 42;  // Error: variable not declared
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("no declarada" in error for error in analyzer.errors))
    
    def test_type_mismatch_assignment(self):
        """Test type mismatch in assignments"""
        code = '''
        let num: integer = 42;
        let text: string = "hello";
        num = text;  // Error: cannot assign string to integer
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("No se puede asignar" in error for error in analyzer.errors))
    
    def test_const_initialization_required(self):
        """Test that constants require initialization"""
        code = '''
        const VALUE: integer;  // Error: constant must be initialized
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("debe ser inicializada" in error for error in analyzer.errors))
    
    def test_type_inference_with_null(self):
        """Test type inference with null values"""
        code = '''
        let value = null;
        value = 42;  // Should work - type inferred from first non-null assignment
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
        
        # Verify variable type was updated
        global_scope = analyzer.symbol_table.all_scopes[0]
        self.assertIn('value', global_scope.symbols)
        self.assertEqual(global_scope.symbols['value'].type.name, 'integer')

class TestArithmeticSemantics(unittest.TestCase):
    """Tests for arithmetic operation semantic rules"""
    
    def test_string_concatenation(self):
        """Test string concatenation with + operator"""
        code = '''
        let first: string = "Hello";
        let second: string = "World";
        let greeting: string = first + " " + second;
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
    
    def test_invalid_arithmetic_types(self):
        """Test arithmetic operations with invalid types"""
        code = '''
        let text: string = "hello";
        let flag: boolean = true;
        let result1: integer = text + flag;  // Error: invalid operands
        let result2: integer = text * 2;     // Error: string * integer
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        # Should have errors for invalid arithmetic operations
        error_text = ' '.join(analyzer.errors)
        self.assertTrue("requiere operandos" in error_text)
    
    def test_mixed_string_integer_addition(self):
        """Test invalid mixed string/integer addition"""
        code = '''
        let text: string = "number: ";
        let num: integer = 42;
        let result: string = text + num;  // Error: cannot add string + integer
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("requiere operandos" in error for error in analyzer.errors))

class TestArraySemantics(unittest.TestCase):
    """Tests for array-related semantic rules"""
    
    def test_array_declaration_and_access(self):
        """Test array declarations and element access"""
        code = '''
        let numbers: integer[] = [1, 2, 3, 4, 5];
        let matrix: integer[][] = [[1, 2], [3, 4]];
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
        
        # Verify array types
        global_scope = analyzer.symbol_table.all_scopes[0]
        self.assertIn('numbers', global_scope.symbols)
        self.assertIn('matrix', global_scope.symbols)
    
    def test_array_element_type_consistency(self):
        """Test that array elements must be of consistent type"""
        code = '''
        let mixed: integer[] = [1, "hello", 3];  // Error: inconsistent element types
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("tipos inconsistentes" in error for error in analyzer.errors))

class TestErrorPropagation(unittest.TestCase):
    """Tests for error propagation and edge cases"""
    
    def test_unary_not_operator(self):
        """Test unary NOT operator with invalid types"""
        code_invalid = '''
        let num: integer = 5;
        let result: boolean = !num;  // Error: ! requires boolean operand
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code_invalid)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("requiere operando booleano" in error for error in analyzer.errors))
        
        # Test valid case
        code_valid = '''
        let flag: boolean = true;
        let result: boolean = !flag;
        '''
        
        analyzer = analyze_code(code_valid)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
    
    def test_null_comparisons(self):
        """Test null comparison rules"""
        # Valid null comparisons
        code_valid = '''
        let text: string = "hello";
        let result1: boolean = text == null;
        let result2: boolean = null == null;
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code_valid)
        self.assertEqual(len(analyzer.errors), 0, f"Errores: {analyzer.errors}")
        
        # Invalid null comparisons
        code_invalid = '''
        let num: integer = 5;
        let result: boolean = null == num;  // Error: cannot compare null with integer
        '''
        
        analyzer = analyze_code(code_invalid)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("No se puede comparar null" in error for error in analyzer.errors))
    
    def test_return_outside_function(self):
        """Test return statement outside function"""
        code = '''
        return 42;  // Error: return outside function
        '''
        
        from main2 import analyze_code
        analyzer = analyze_code(code)
        self.assertGreater(len(analyzer.errors), 0)
        self.assertTrue(any("return fuera de función" in error for error in analyzer.errors))

if __name__ == '__main__':
    unittest.main()
