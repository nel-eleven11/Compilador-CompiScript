# README - Compilador CompisCript

## Descripción General
Este proyecto es un compilador para el lenguaje CompisCript, una variante de TypeScript, implementado en Python utilizando ANTLR4. El compilador sigue la arquitectura tradicional de análisis léxico, sintáctico y semántico, con un enfoque en el análisis semántico mediante el patrón Visitor.

## Estructura del Proyecto y Componentes Principales

### 1. Sistema de Tipos (`classes/types.py`)
- Define los tipos primitivos (`integer`, `boolean`, `string`, `void`, `null`)
- Se tiene tambien un error type, que sirve para propagar errores en operaciones recursivas como en las operaciones aritméticas
- Implementa arrays
- Proporciona reglas de compatibilidad de tipos (`can_assign_to`)

### 2. Símbolos (`classes/symbols.py`)
- Clases base para representar variables, funciones y clases
- Almacena información semántica de cada entidad
- Es el componente princippal de la tabla de símbolos

### 3. Tabla de Símbolos (`classes/symbol_table.py`)
- Los símbolos son varias cosas. Variables, nombres de funciones, ...
- Nuestra tabla de símbolos esta diseñada para ser una lista de diccionarios practicamente. Esto es porque cada entrada de la tabla de símbolos es un ámbito/scope y tiene los metodos necesarios para agregar y buscar símbolos. También tiene la lógica para entrar y salir de un ambiente para tener las variables en el escpo correcto.
- Búsqueda jerárquica de símbolos

### 4. Ámbitos y Tabla de Símbolos (`classes/scope.py`)
- Implementa scopes anidados (global, función, clase, bloque)
- La idea es poder controlar y verificar la creacion de variables, variables duplicadas, entre otros aspectos relacionada al scope/ambito
- Trabaja de la mano con symbol_table


### 5. Visitor Semántico (`semantic_visitor.py`)
- Implementa las reglas semánticas del lenguaje, por eso el archvio es tan grande
- Valida tipos, declaraciones, uso correcto de variables/funciones y demás
- Usamos visitor para poder recorrer el árbol sintáctico y revisar el input procesado


## Convenciones
* Manejo de errores: Todos los errores se registran en self.errors en el visitor, es una lista de errores que se muestran luego de que termina el analisis semantico. Si se encuentra el error semantico no debe de parar el visitor, debe seguir hasta terminar y agregar el error a la lista de errores del visitor.
* Tipos: Usar siempre los tipos definidos en types.py (ej. INT_TYPE, BOOL_TYPE)
* Jerarquía de scopes: Respetar los niveles de scope (global > función/clase > bloque)

## Pruebas
* Hay archivos .cps con casos de prueba, el archivo principal de prueba es program.cps
* Ejecutar con main2.py para verificar detección de errores
* Los errores semánticos se muestran con formato: Línea X: Mensaje de error

## Carpet test_files
Dentro de este se tienen varios archivos de prueba para poder testear los casos que deben ser validos al momento de realizar el análisis semántico. Dichos archivos se pueden correr desde el IDE o bien corriendo el siguiente comando desde la carpeto "proyecto":

```bash
python -m tests.test_semantic
```