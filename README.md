# Compilador-CompiScript
Proyecto 1 de Construcción de Compiladores | Fase de Compilación: Análisis Semántico

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
python main2.py arhivo_especifico.cps  
```