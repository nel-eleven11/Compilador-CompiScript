# ide/ide.py
import io
import json
import sys
import subprocess
from pathlib import Path
from contextlib import redirect_stdout

import streamlit as st

st.set_page_config(page_title="Mini IDE", layout="wide")

# --- Rutas (según la estructura de carpetas) ---
IDE_DIR = Path(__file__).resolve().parent
PROY_DIR = IDE_DIR.parent / "proyecto"
AST_PATH = PROY_DIR / "ast.json"
LOG_PATH = PROY_DIR / "log.txt"
GRAMMAR = PROY_DIR / "Compiscript.g4"

# Asegurar que 'proyecto' esté en el PYTHONPATH para importar main.py
if str(PROY_DIR) not in sys.path:
    sys.path.insert(0, str(PROY_DIR))

# Import tardío 
try:
    import main as cps_main  # proyecto/main.py
except Exception:
    cps_main = None

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
    ]
    if all(p.exists() for p in needed):
        return ""

    if not GRAMMAR.exists():
        raise FileNotFoundError(f"No se encontró la gramática: {GRAMMAR}")

    # Verificar antlr4
    try:
        subprocess.run(["antlr4", "-version"], capture_output=True, text=True, check=True)
    except Exception:
        raise RuntimeError(
            "No se encontró el comando 'antlr4'. Instálalo o agrega al PATH."
        )

    cmd = ["antlr4", "-Dlanguage=Python3", "Compiscript.g4", "-visitor", "-no-listener"]
    proc = subprocess.run(
        cmd,
        cwd=str(PROY_DIR),
        capture_output=True,
        text=True,
        check=True,
    )
    return f"=== ANTLR4 ===\n{proc.stdout}\n{proc.stderr}"

# -------- Compilar --------
def compile_current_code() -> None:
    """
    Compila el código del editor con el pipeline de proyecto/main.py.
    - Asegura gramática generada
    - Ejecuta run_from_text
    - Guarda stdout en log.txt
    - Bloquea edición
    """
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
        # 1) generar gramática si hace falta
        antlr_log = ensure_grammar_generated()
        # 2) ejecutar compilación capturando prints
        with redirect_stdout(buffer):
            cps_main.run_from_text(src, ast_path=str(AST_PATH))
        out = (antlr_log + "\n" + buffer.getvalue()).strip()
        LOG_PATH.write_text(out, encoding="utf-8")

        st.session_state.output_text = (
            "Compilación finalizada. Revisa 'Árbol Sintáctico' y 'Output Messages'."
        )
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

    # etiqueta rica para reglas
    pos = ""
    if all(k in node for k in ("start_line", "end_line")):
        pos = f"  [L{node['start_line']}..L{node['end_line']}]"
    with st.expander(f"{label}{pos}", expanded=False):
        for child in node.get("children", []):
            render_ast_node(child)


# ---------- Barra superior ----------
c1, csp, c3 = st.columns([4, 4, 4])

with c1:
    # Solo .cps
    archivo = st.file_uploader("Cargar archivo .cps", type=["cps"])
    if archivo is not None:
        name = archivo.name
        if not name.lower().endswith(".cps"):
            st.error("Solo se aceptan archivos con extensión .cps")
        else:
            try:
                text = archivo.getvalue().decode("utf-8")
            except Exception:
                text = archivo.getvalue().decode("latin-1", errors="ignore")
            st.session_state.code_input = text
            st.session_state.upload_name = name
            st.session_state.output_text = f"Archivo cargado: {name}"
            st.session_state.locked = False  # permite editar el código cargado

with c3:
    if st.button("Compilar", use_container_width=True):
        compile_current_code()

# ---------- Selector de vista ----------
vista = st.segmented_control(
    "Vista",
    options=["Código", "Árbol Sintáctico", "Acciones", "Output Messages"],
    default=st.session_state.vista,
)
st.session_state.vista = vista


if vista == "Código":
    filename_hint = f" ({st.session_state.upload_name})" if st.session_state.upload_name else ""
    if st.session_state.locked:
        st.text_area(
            label=f"Editor{filename_hint}",
            value=st.session_state.code_input,
            height=380,
            disabled=True,
            label_visibility="collapsed",
            key="editor_locked",
        )
        st.caption("La edición está bloqueada tras compilar.")
        if st.button("Editar de nuevo"):
            st.session_state.locked = False
    else:
        st.text_area(
            label=f"Editor{filename_hint}",
            key="code_input",
            height=380,
            placeholder="Escribe tu código Compiscript aquí…",
            label_visibility="collapsed",
        )
    st.caption(st.session_state.output_text)

elif vista == "Árbol Sintáctico":
    if AST_PATH.exists():
        try:
            data = json.loads(AST_PATH.read_text(encoding="utf-8"))
            st.markdown("**Árbol sintáctico** (expande los nodos):")
            # raíz visible como expander principal
            render_ast_node(data)
        except Exception as e:
            st.error(f"No se pudo leer ast.json: {e}")
    else:
        st.info("Aún no hay ast.json. Compila primero.")

elif vista == "Acciones":
    st.subheader("Acciones")
    st.caption("Próximamente: ejecutar pruebas, formatear código, limpiar artefactos, etc.")
    st.write("- (placeholder)")

elif vista == "Output Messages":
    if LOG_PATH.exists():
        # lectura como texto plano, sin permitir edición
        content = LOG_PATH.read_text(encoding="utf-8")
        st.text_area("Mensajes del compilador", value=content, height=380, disabled=True)
    else:
        st.info("Aún no hay log.txt. Compila para ver los mensajes.")

st.markdown("</div>", unsafe_allow_html=True)
