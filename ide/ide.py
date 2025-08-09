import streamlit as st
from typing import Tuple

st.set_page_config(page_title="Mini IDE", layout="wide")

# ---------- Estado ----------
if "vista" not in st.session_state:
    st.session_state.vista = "Código"
if "locked" not in st.session_state:
    st.session_state.locked = False
if "code_input" not in st.session_state:
    st.session_state.code_input = ""
if "output_text" not in st.session_state:
    st.session_state.output_text = "Listo. Escribe dos números separados por coma y presiona Compilar."

# ---------- Estilo del área gris ----------
st.markdown("""
<style>
.gray-box { border: 4px solid #7a7a7a; border-radius: 6px; padding: 12px; min-height: 380px; }
</style>
""", unsafe_allow_html=True)

# ---------- Barra superior ----------
c1, csp, c3 = st.columns([3, 6, 3])

with c1:
    archivo = st.file_uploader("Cargar archivo (opcional)", type=None)

with c3:
    if st.button("Compilar", use_container_width=True):
        # Al compilar: leer, validar, ejecutar sumar() y bloquear edición
        try:
            # Parseo "a, b"
            raw = st.session_state.code_input.strip()
            if not raw:
                raise ValueError("El editor está vacío. Escribe: 12, 8")

            def parse_par(a: str) -> Tuple[float, float]:
                parts = [p.strip() for p in a.split(",")]
                if len(parts) != 2:
                    raise ValueError("Usa exactamente dos números separados por coma, ej.: 12, 8")
                x, y = float(parts[0]), float(parts[1])
                return x, y

            a, b = parse_par(raw)

            # Import dinámico del archivo externo
            from sumar import sumar  # asegurate que sumar.py esté junto a ide.py

            res = sumar(a, b)
            st.session_state.output_text = f"Resultado de sumar({a}, {b}) = {res}"
            st.session_state.locked = True
            st.session_state.vista = "Código"  # mostrar en el editor
        except Exception as e:
            st.session_state.output_text = f"Error al compilar/ejecutar: {e}"
            st.session_state.locked = False

# ---------- Selector de vista (sin marco azul) ----------
vista = st.segmented_control(
    "Vista",
    options=["Código", "Árbol Sintáctico"],
    default=st.session_state.vista
)
st.session_state.vista = vista

if st.session_state.vista == "Código":
    if st.session_state.locked:
        # Mostrar resultado, sin permitir editar
        st.text_area(
            label="Salida",
            value=st.session_state.output_text,
            height=320,
            label_visibility="collapsed",
            disabled=True,
            key="output_area_locked",
        )
        st.caption("La edición está bloqueada tras compilar.")
        if st.button("Editar de nuevo"):
            st.session_state.locked = False
            # Mantener el texto previo para que el usuario lo ajuste
    else:
        # Editor editable
        st.text_area(
            label="Editor",
            key="code_input",
            height=320,
            placeholder="Escribe dos números separados por coma, p. ej.: 12, 8",
        )
        # Mostrar mensajes abajo mientras se edita
        st.caption(st.session_state.output_text)

else:
    # Placeholder de la otra vista
    st.caption("Aquí iría la visualización del Árbol Sintáctico.")

st.markdown('</div>', unsafe_allow_html=True)
