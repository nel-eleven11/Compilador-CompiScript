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
        
    

if __name__ == '__main__':
    unittest.main()