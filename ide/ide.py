# ide/ide.py
import io
import json
import sys
import subprocess
from pathlib import Path
from contextlib import redirect_stdout
import importlib
from importlib.util import spec_from_file_location, module_from_spec


import streamlit as st

st.set_page_config(page_title="IDE CompiScript", layout="wide")

# --- Rutas ---
IDE_DIR = Path(__file__).resolve().parent
PROY_DIR = IDE_DIR.parent / "proyecto"
AST_PATH = PROY_DIR / "ast.json"
LOG_PATH = PROY_DIR / "log.txt"
GRAMMAR = PROY_DIR / "Compiscript.g4"

def _load_cps_main():
    """
    Intenta cargar el front-end del compilador.
    1) Primero como módulo 'main' en PROY_DIR (vía PYTHONPATH).
    2) Si falla, carga por ruta explícita proyecto/main.py
    3) Siempre permite recarga si ya estaba importado.
    """
    # Asegurar PROY_DIR en sys.path
    if str(PROY_DIR) not in sys.path:
        sys.path.insert(0, str(PROY_DIR))

    # 1) Import convencional (y recarga si ya estaba)
    try:
        if 'main' in sys.modules:
            return importlib.reload(sys.modules['main'])
        return importlib.import_module('main')  # proyecto/main.py
    except Exception:
        pass

    # 2) Carga por ruta explícita (fallback)
    for fname in ("main.py"):
        fpath = PROY_DIR / fname
        if fpath.exists():
            try:
                spec = spec_from_file_location("cps_main", str(fpath))
                mod = module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                return mod
            except Exception:
                continue
    return None

# Carga inicial 
cps_main = _load_cps_main()


# ---------- Estado ----------
if "vista" not in st.session_state:
    st.session_state.vista = "Código"
if "locked" not in st.session_state:
    st.session_state.locked = False
if "code_input" not in st.session_state:
    st.session_state.code_input = ""
if "output_text" not in st.session_state:
    st.session_state.output_text = "Carga un .cps o escribe código y presiona Compilar."
if "upload_name" not in st.session_state:
    st.session_state.upload_name = None
if "last_compile_ok" not in st.session_state:
    st.session_state.last_compile_ok = False
if "last_errors" not in st.session_state:
    st.session_state.last_errors = []
if "symbols" not in st.session_state:
    st.session_state.symbols = []
if "editor_widget" not in st.session_state:
    st.session_state.editor_widget = st.session_state.code_input
if "quadruples" not in st.session_state:
    st.session_state.quadruples = []

# ---------- Utilidades ----------
def ensure_grammar_generated() -> str:
    """
    Si faltan archivos generados por ANTLR4, los genera.
    Devuelve una cadena con el log de ese paso (vacía si no hizo nada).
    """
    needed = [
        PROY_DIR / "CompiscriptLexer.py",
        PROY_DIR / "CompiscriptParser.py",
        PROY_DIR / "CompiscriptVisitor.py",
        PROY_DIR / "semantic_visitor.py",
    ]
    if all(p.exists() for p in needed):
        return ""

    if not GRAMMAR.exists():
        raise FileNotFoundError(f"No se encontró la gramática: {GRAMMAR}")

    # Verificar antlr4
    try:
        subprocess.run(["antlr4", "-version"], capture_output=True, text=True, check=True)
    except Exception:
        raise RuntimeError("No se encontró el comando 'antlr4'. Instálalo o agrega al PATH.")

    cmd = ["antlr4", "-Dlanguage=Python3", "Compiscript.g4", "-visitor", "-no-listener"]
    proc = subprocess.run(cmd, cwd=str(PROY_DIR), capture_output=True, text=True, check=True)
    return f"=== ANTLR4 ===\n{proc.stdout}\n{proc.stderr}"

def _sync_editor_to_state():
# Copia lo que tenga el widget al valor canónico
    st.session_state.code_input = st.session_state.editor_widget

# -------- Compilar --------
def compile_current_code() -> None:
    global cps_main
    cps_main = _load_cps_main()

    if cps_main is None:
        st.session_state.output_text = "Error: no pude importar proyecto/main.py"
        st.session_state.locked = False
        st.session_state.last_compile_ok = False
        return

    src = st.session_state.code_input.strip()
    if not src:
        st.session_state.output_text = "El editor está vacío."
        st.session_state.locked = False
        st.session_state.last_compile_ok = False
        return

    buffer = io.StringIO()
    try:
        # Generar gramática si hace falta
        antlr_log = ensure_grammar_generated()
        with redirect_stdout(buffer):
            result = cps_main.run_from_text(src, ast_path=str(AST_PATH))

        # Guardar log (tokens, tabla, etc. — SIN errores)
        out = (antlr_log + "\n" + buffer.getvalue()).strip()
        LOG_PATH.write_text(out, encoding="utf-8")

        # Guardar datos estructurados en sesión
        st.session_state.last_errors = result.get("errors", [])
        st.session_state.symbols = result.get("symbols", [])
        st.session_state.quadruples = result.get("quadruples", [])

        st.session_state.output_text = "Compilación finalizada. Revisa Árbol, Errores, Tabla de Símbolos, Mensajes y Código Intermedio."
        st.session_state.locked = True
        st.session_state.last_compile_ok = True

    except subprocess.CalledProcessError as e:
        msg = f"Error al ejecutar ANTLR4:\n{e.stderr or e.stdout or e}"
        LOG_PATH.write_text((buffer.getvalue() + "\n" + msg).strip(), encoding="utf-8")
        st.session_state.output_text = msg
        st.session_state.locked = False
        st.session_state.last_compile_ok = False

    except Exception as e:
        msg = f"Error durante la compilación: {e}"
        LOG_PATH.write_text((buffer.getvalue() + "\n" + msg).strip(), encoding="utf-8")
        st.session_state.output_text = msg
        st.session_state.locked = False
        st.session_state.last_compile_ok = False

# ------- Árbol Sintáctico ---------
def render_ast_node(node: dict):
    """
    Expander recursivo: padre -> hijos.
    """
    label = node.get("type", "<?>")
    # Si es token, mostramos detalles y regresamos
    if label == "TOKEN":
        info = f"{node.get('name')} → '{node.get('text')}'  (L{node.get('line')}:C{node.get('column')})"
        st.markdown(f"- **{info}**")
        return
    pos = ""
    if all(k in node for k in ("start_line", "end_line")):
        pos = f"  [L{node['start_line']}..L{node['end_line']}]"
    with st.expander(f"{label}{pos}", expanded=False):
        for child in node.get("children", []):
            render_ast_node(child)

# ---------- Barra superior ----------
def _on_upload():
    f = st.session_state.get("uploader")
    if f is None:
        return
    name = f.name
    try:
        text = f.getvalue().decode("utf-8")
    except Exception:
        text = f.getvalue().decode("latin-1", errors="ignore")

    # Actualiza SIEMPRE ambos: el canónico y el del widget
    st.session_state.code_input = text
    st.session_state.editor_widget = text

    st.session_state.upload_name = name
    st.session_state.output_text = f"Archivo cargado: {name}"
    st.session_state.locked = False

c1, csp, c3 = st.columns([4, 4, 4])
with c1:
    archivo = st.file_uploader("Cargar archivo .cps", type=["cps"], key="uploader", on_change=_on_upload)

with c3:
    if st.button("Compilar", use_container_width=True):
        compile_current_code()

# ---------- Selector de vista ----------
try:
    vista = st.segmented_control(
        "Vista",
        options=["Código", "Árbol Sintáctico", "Errores", "Tabla de Símbolos", "Mensajes", "Código Intermedio"],
        default=st.session_state.vista,
    )
except Exception:
    vista = st.radio(
        "Vista",
        ["Código", "Árbol Sintáctico", "Errores", "Tabla de Símbolos", "Mensajes", "Código Intermedio"],
        index=["Código", "Árbol Sintáctico", "Errores", "Tabla de Símbolos", "Mensajes", "Código Intermedio"].index(st.session_state.vista),
        horizontal=True,
    )
st.session_state.vista = vista

# ---------- Vistas ----------
if vista == "Código":
    filename_hint = f" ({st.session_state.upload_name})" if st.session_state.upload_name else ""
    st.text_area(
        label=f"Editor{filename_hint}",
        key="editor_widget",                              
        value=st.session_state.code_input,              
        height=380,
        placeholder="Escribe tu código Compiscript aquí…",
        label_visibility="collapsed",
        disabled=st.session_state.locked,
        on_change=_sync_editor_to_state,                
    )
    if st.session_state.locked:
        if st.button("Editar de nuevo"):
            st.session_state.locked = False
    st.caption(st.session_state.output_text)

elif vista == "Árbol Sintáctico":
    if AST_PATH.exists():
        try:
            data = json.loads(AST_PATH.read_text(encoding="utf-8"))
            st.markdown("**Árbol sintáctico** (expande los nodos):")
            render_ast_node(data)
        except Exception as e:
            st.error(f"No se pudo leer ast.json: {e}")
    else:
        st.info("Aún no hay ast.json. Compila primero.")

elif vista == "Tabla de Símbolos":
    symdata = st.session_state.symbols or []
    if not symdata:
        st.info("Aún no hay tabla de símbolos. Compila primero.")
    else:
        st.subheader("Tabla de Símbolos")
        for scope in symdata:
            header = f"Ámbito {scope['scope_id']} ({scope['scope_type']})"
            if scope.get("parent_id") is not None:
                header += f" — padre: {scope['parent_id']}"
            with st.expander(header, expanded=False):
                syms = scope.get("symbols", [])
                if not syms:
                    st.caption("— vacío —")
                else:
                    for s in syms:
                        cat = s.get("category")
                        if cat == "variable":
                            flags = " const" if s.get("is_const") else ""
                            inf = " (inferred)" if s.get("is_type_inferred") else ""
                            st.write(f"**Var** {s['name']}{flags}{inf}: `{s.get('type')}`")
                        elif cat == "function":
                            params = ", ".join([f"{p.get('type')} {p.get('name')}" for p in s.get("parameters", [])])
                            st.write(f"**Func** {s['name']}({params}) -> `{s.get('return_type')}`")
                        elif cat == "class":
                            parent = s.get("parent")
                            st.write(f"**Class** {s['name']}" + (f" : {parent}" if parent else ""))
                            if s.get("attributes"):
                                st.markdown("_Atributos_")
                                for a in s["attributes"]:
                                    flags = " const" if a.get("is_const") else ""
                                    st.write(f"- {a['name']}{flags}: `{a.get('type')}`")
                            if s.get("methods"):
                                st.markdown("_Métodos_")
                                for m in s["methods"]:
                                    params = ", ".join([f"{p.get('type')} {p.get('name')}" for p in m.get("parameters", [])])
                                    st.write(f"- {m['name']}({params}) -> `{m.get('return_type')}`")

elif vista == "Mensajes":
    if LOG_PATH.exists():
        content = LOG_PATH.read_text(encoding="utf-8")
        st.text_area("Mensajes del compilador", value=content, height=380, disabled=True)
    else:
        st.info("Aún no hay log.txt. Compila para ver los mensajes.")

elif vista == "Errores":
    errs = st.session_state.last_errors or []
    st.subheader("Errores del analizador")
    if not errs:
        st.success("Sin errores semánticos.")
    else:
        # Soporta listas de strings o de dicts
        for i, e in enumerate(errs, start=1):
            if isinstance(e, dict):
                # intenta mostrar información común si existe
                line = e.get("line")
                col = e.get("column")
                msg = e.get("message") or e.get("msg") or str(e)
                where = f" (L{line}:C{col})" if line is not None else ""
                st.error(f"{i}. {msg}{where}")
            else:
                st.error(f"{i}. {e}")

elif vista == "Código Intermedio":
    st.subheader("Código Intermedio")
    quads = st.session_state.get("quadruples", [])
    if not quads:
        st.info("Aún no hay código intermedio. Compila primero.")
    else:
        # Mostrar los cuadruplos
        lines = [
            f"{i}: ({q.get('op')}, {q.get('arg1')}, {q.get('arg2')}, {q.get('result')})"
            for i, q in enumerate(quads)
        ]
        st.text_area("Código intermedio generado", value="\n".join(lines), height=380, disabled=True)
    st.caption("El mapa de memoria aparece en la vista 'Mensajes' junto con el resto del log.")

