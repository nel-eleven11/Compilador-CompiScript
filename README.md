# Compilador-CompiScript
Proyecto de Construcción de Compiladores | Fases: Análisis Semántico + Generación de Código Intermedio + Generación de Código MIPS

## Dependencias necesarias
```bash
pip install antlr4-tools
```

```bash
pip install antlr4-python3-runtime
```

#### Estando en en la carpeta "proyecto"

```bash
antlr4 -Dlanguage=Python3 Compiscript.g4 -visitor -no-listener
```

### Correr el IDE

Desde la carpet ide:

```bash
streamlit run ide.py
```

### Correr pruebas

#### Corriendo todas las pruebas
Desde la carpeta proyecto

```bash
python -m tests.test_semantic
```

#### Corriendo un archivo especifico
Desde la carpeta proyecto

```bash
python main2.py archivo_especifico.cps
```

**Nota**: El archivo `.cps` puede estar en cualquier ubicación. Se recomienda colocar archivos de prueba en la carpeta `test_cps/`. El código MIPS generado se guardará automáticamente en `test_asm/`.

---

## Arquitectura del Proyecto

### Estructura de Carpetas

```
proyecto/
├── classes/                    # Clases principales del compilador
│   ├── types.py               # Definición de tipos del lenguaje
│   ├── symbols.py             # Definición de símbolos
│   ├── symbol_table.py        # Tabla de símbolos
│   ├── scope.py               # Manejo de scopes
│   ├── quadruple.py           # Definición de cuádruplos (TAC)
│   ├── code_generator.py      # Generador de código intermedio
│   ├── memory_manager.py      # Manejador de memoria
│   ├── activation_record_design.py  # Diseño de registros de activación
│   └── MIPS_generator/        # NUEVO: Generación de código MIPS
│       ├── mips_generator.py       # Generador principal TAC → MIPS
│       ├── register_allocator.py   # Asignación de registros (getReg)
│       ├── mips_stack_manager.py   # Manejo de stack para funciones
│       └── mips_runtime.py         # Funciones de runtime (print, etc.)
├── semantic_visitor.py        # Análisis semántico + generación TAC
├── main2.py                   # Punto de entrada principal
├── test_cps/                  # NUEVO: Archivos de prueba .cps
└── test_asm/                  # NUEVO: Código MIPS generado .asm
```

### Flujo de Compilación

```
Código Fuente (.cps)
       ↓
   [Lexer/Parser - ANTLR]
       ↓
   Árbol Sintáctico (AST)
       ↓
   [SemanticVisitor]
       ↓
   Análisis Semántico + Tabla de Símbolos
       ↓
   [CodeGenerator]
       ↓
   Código Intermedio (Cuádruplos TAC)
       ↓
   [MIPSGenerator] ← NUEVO
       ↓
   Código MIPS (.asm)
       ↓
   [Simulador MARS]
       ↓
   Ejecución
```

---

## Generación de Código MIPS

### Operaciones Implementadas

#### 1. Operaciones Aritméticas
- Suma (`+`) → `add`
- Resta (`-`) → `sub`
- Multiplicación (`*`) → `mul`
- División (`/`) → `div` + `mflo`
- Módulo (`%`) → `div` + `mfhi`

#### 2. Operaciones de Comparación
- Menor que (`<`) → `slt`
- Mayor que (`>`) → `slt` (invertido)
- Menor o igual (`<=`) → `slt` + `xori`
- Mayor o igual (`>=`) → `slt` + `xori`
- Igual (`==`) → `xor` + `sltiu`
- Diferente (`!=`) → `xor` + `sltu`

#### 3. Operaciones Lógicas
- AND lógico (`&&`) → `and` + normalización
- OR lógico (`||`) → `or` + normalización
- NOT lógico (`!`) → `sltiu`

#### 4. Operaciones Unarias
- Negación aritmética (`-x`) → `sub $zero`

#### 5. Control de Flujo
- Salto incondicional (`goto`) → `j`
- Salto condicional (`if`) → `bne`
- Salto condicional falso (`if_false`) → `beq`
- Etiquetas (`label`) → labels MIPS

#### 6. Operaciones de Memoria
- Asignación directa (`=`) → `li` + `sw`
- Carga de variables (`@`) → `lw`
- Variables globales → sección `.data`
- Valores booleanos (`true`/`false`) → `1`/`0`

### Ejemplo de Uso

```bash
# 1. Crear un archivo de prueba
cat > test_cps/mi_programa.cps << 'EOF'
let a: integer = 10;
let b: integer = 5;
let c: integer = a + b;

if (a > b) {
    c = a * 2;
} else {
    c = b * 2;
}
EOF

# 2. Compilar a MIPS
python main2.py test_cps/mi_programa.cps

# 3. El archivo MIPS se genera en:
# test_asm/mi_programa.asm

# 4. Abrir en MARS y ejecutar
```

### Archivos de Prueba Disponibles

**Operaciones Básicas:**
- `test_cps/test_control_flow.cps` - Control de flujo (if/else)
- `test_cps/test_comparisons.cps` - Todas las comparaciones
- `test_cps/test_logical_unary.cps` - Operaciones lógicas, unarias y módulo
- `test_cps/test_complete_basic.cps` - TODAS las operaciones básicas combinadas

**Funciones (Etapa 2):**
- `test_cps/test_method_call.cps` - Llamada a método simple (2 parámetros)
- `test_cps/test_recursive_method.cps` - Factorial recursivo (prueba de recursividad)

**Nota**: Ver `ETAPA2_SUMMARY.md` para detalles completos de la implementación de funciones.

###  Componentes del Generador MIPS

#### MIPSGenerator (`mips_generator.py`)
- **Propósito**: Coordina la traducción de cuádruplos TAC a instrucciones MIPS
- **Métodos principales**:
  - `generate_mips_code()` - Genera el programa MIPS completo
  - `_translate_quadruple()` - Traduce un cuádruplo individual
  - `_translate_arithmetic_quad()` - Traduce operaciones aritméticas
  - `_translate_comparison_quad()` - Traduce comparaciones
  - `_translate_logical_quad()` - Traduce operaciones lógicas
  - `_translate_jump_quad()` - Traduce saltos y control de flujo
  - `_translate_unary_quad()` - Traduce operaciones unarias
  - `_translate_modulo_quad()` - Traduce operación módulo

#### RegisterAllocator (`register_allocator.py`)
- **Propósito**: Implementa el algoritmo `getReg()` para asignar registros MIPS
- **Registros disponibles**:
  - `$t0-$t9`: Registros temporales (10)
  - `$s0-$s7`: Registros guardados (8)
  - `$a0-$a3`: Registros de argumentos (4)
- **Características**:
  - Asignación inteligente de registros
  - Reutilización cuando es posible
  - Preparado para spilling al stack (futuro)

#### MIPSStackManager (`mips_stack_manager.py`)
- **Propósito**: Manejo del stack para llamadas a funciones
- **Funciones**:
  - `generate_function_prologue()` - Genera prólogo de función
  - `generate_function_epilogue()` - Genera epílogo de función
  - `generate_call_sequence()` - Genera secuencia de llamada
- **Estado**: Implementado pero aún no utilizado (funciones pendientes)

#### MIPSRuntime (`mips_runtime.py`)
- **Propósito**: Funciones de runtime para operaciones del sistema
- **Incluye**: Funciones para print_int, print_string, read_int, etc.
- **Estado**: Implementado pero aún no integrado

---

## Estado del Proyecto

### Completado

1. **Análisis Léxico y Sintáctico** (ANTLR)
2. **Análisis Semántico** (SemanticVisitor)
   - Verificación de tipos
   - Tabla de símbolos
   - Manejo de scopes
   - Detección de errores semánticos
3. **Generación de Código Intermedio** (CodeGenerator)
   - Cuádruplos TAC
   - Optimización básica de temporales
   - Manejo de memoria
4. **Generación de Código MIPS** (MIPSGenerator)
   - Todas las operaciones básicas
   - Control de flujo
   - Asignación de registros
   - Manejo de variables globales
5. **Funciones y Llamadas** (Etapa 2) **COMPLETADO**
   - Traducción completa de cuádruplos `enter`, `leave`, `push`, `call`, `pop`, `return`
   - Implementación de stack frames con FP (frame pointer)
   - Manejo de argumentos vía stack
   - Manejo de valores de retorno en `$v0`
   - Soporte completo para recursividad
   - FP-relative addressing para parámetros y locales
   - Limpieza automática de stack después de llamadas

### Optimizaciones Implementadas

1. **Optimización de Cargas de Variables**
   - **Antes**: Generaba cuádruplos `@` (load) para cada acceso a variable
   - **Ahora**: Pasa direcciones de memoria directamente a operaciones
   - **Reducción**: 33-41% menos cuádruplos en código típico

   **Ejemplo**:
   ```
   ANTES (6 cuádruplos):
   0: (=, 10, None, 0x1000)      # a = 10
   1: (=, 5, None, 0x1004)       # b = 5
   2: (@, 0x1000, None, t0)      # Load a
   3: (@, 0x1004, None, t1)      # Load b
   4: (+, t0, t1, t2)            # t2 = t0 + t1
   5: (=, t2, None, 0x1008)      # c = t2

   AHORA (4 cuádruplos):
   0: (=, 10, None, 0x1000)      # a = 10
   1: (=, 5, None, 0x1004)       # b = 5
   2: (+, 0x1000, 0x1004, t0)    # Operación directa con direcciones
   3: (=, t0, None, 0x1008)      # c = t0
   ```

   **Impacto medido**:
   - `test_simple_opt.cps`: 6 → 4 cuádruplos (33% reducción)
   - `test_complete_basic.cps`: 58 → 34 cuádruplos (41% reducción)

---

## Debugging y Verificación

### Ver Código Intermedio Generado

Cuando ejecutas `python main2.py archivo.cps`, se muestra:

1. **Tabla de Símbolos**: Variables y sus tipos
2. **Cuádruplos TAC**: Código intermedio generado
3. **Mapa de Memoria**: Direcciones asignadas
4. **Código MIPS**: Traducción final a assembler

### Verificar Código MIPS en MARS

1. Instalar [MARS MIPS Simulator](http://courses.missouristate.edu/kenvollmar/mars/)
2. Abrir el archivo `.asm` generado en `test_asm/`
3. Ensamblar (F3)
4. Ejecutar paso a paso (F7) o completo (F5)
5. Verificar valores en **Data Segment**

### Valores Esperados en Memoria

Para `test_complete_basic.cps`:
- `var_a` = 15
- `var_b` = 4
- `var_sum` = 19
- `var_diff` = 11
- `var_prod` = 60
- `var_quot` = 3
- `var_mod` = 3
- `var_neg` = -4 (0xFFFFFFFC)
- `var_is_greater` = 1 (true)
- `var_is_equal` = 0 (false)
- `var_result` = 15
- `var_complex` = 35

---

## Notas Técnicas

### Convenciones MIPS Utilizadas

- **Registros temporales** (`$t0-$t9`): Para cálculos intermedios
- **Registros guardados** (`$s0-$s7`): Para valores que deben persistir
- **Registros de argumentos** (`$a0-$a3`): Para parámetros de funciones
- **Registros de retorno** (`$v0-$v1`): Para valores de retorno
- **Stack Pointer** (`$sp`): Apunta al tope del stack
- **Frame Pointer** (`$fp`): Apunta al frame actual
- **Return Address** (`$ra`): Dirección de retorno

### Manejo de Booleanos

Los valores booleanos se representan como:
- `true` → `1`
- `false` → `0`

Cualquier valor `!= 0` se considera verdadero en condicionales.

### Bugs Conocidos y Soluciones

**Bug**: El código intermedio a veces usa `true`/`false` como nombres de temporales.

**Solución**: El generador MIPS normaliza automáticamente estos valores:
- `_is_temporary()` NO trata `true`/`false` como temporales
- `_normalize_value()` convierte `true` → `1`, `false` → `0`
- `_load_value_to_reg()` aplica normalización automáticamente
