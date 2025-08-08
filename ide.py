import streamlit as st

st.set_page_config(page_title="Mini IDE", layout="wide")

# --------- Estado ----------
if "vista" not in st.session_state:
    st.session_state.vista = "Código"
if "mensaje" not in st.session_state:
    st.session_state.mensaje = "Listo. Presiona un botón para ver el mensaje aquí."

# --------- Estilos (colores/bordes como el boceto) ----------
st.markdown("""
<style>
.box-gris {
    border: 6px solid #7a7a7a; border-radius: 6px; padding: 12px; min-height: 420px;
}
.box-azul   { border: 6px solid #0033ff; border-radius: 6px; padding: 8px; }
.box-rojo   { border: 6px solid #ff2b2b; border-radius: 6px; padding: 8px; }
.box-verde  { border: 6px solid #00ff66; border-radius: 6px; padding: 8px; }
label div[data-testid="stMarkdownContainer"] { margin-bottom: 0; }
</style>
""", unsafe_allow_html=True)

# --------- Fila superior: rojo (cargar) + verde (compilar) ----------
c1, csp, c3 = st.columns([3, 6, 3])

with c1:
    st.markdown('<div class="box-rojo">', unsafe_allow_html=True)
    archivo = st.file_uploader("Cargar archivo", type=None, label_visibility="collapsed")
    if archivo is not None:
        st.session_state.mensaje = f"Se presionó: Cargar archivo — {archivo.name}"
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="box-verde">', unsafe_allow_html=True)
    if st.button("Compilar", use_container_width=True):
        st.session_state.mensaje = "Se presionó: Compilar"
    st.markdown('</div>', unsafe_allow_html=True)

# --------- Fila azul: selector de vista ----------
st.markdown('<div class="box-azul">', unsafe_allow_html=True)
try:
    # Streamlit 1.31+: segmented control (horizontal)
    vista = st.segmented_control("Vista", options=["Código", "Árbol Sintáctico"], default=st.session_state.vista)
except Exception:
    # Fallback si la versión no tiene segmented_control
    vista = st.radio("Vista", ["Código", "Árbol Sintáctico"], horizontal=True, index=0 if st.session_state.vista=="Código" else 1)

if vista != st.session_state.vista:
    st.session_state.vista = vista
    st.session_state.mensaje = f"Se presionó: {vista}"
st.markdown('</div>', unsafe_allow_html=True)

# --------- Área gris (visor) ----------
st.markdown('<div class="box-gris">', unsafe_allow_html=True)
st.write(st.session_state.mensaje)

# (Opcional) muestra algo distinto por vista, solo para futura integración
if st.session_state.vista == "Código":
    st.caption("Aquí iría el editor de texto.")
else:
    st.caption("Aquí iría la visualización del Árbol Sintáctico.")

st.markdown('</div>', unsafe_allow_html=True)
