import sqlite3
import hashlib
import streamlit as st

# ==========================================
# 1. BASE DE DATOS Y PERSISTENCIA
# ==========================================

DB_NAME = "practica_contable.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    # Guardamos el avance del caso práctico en formato texto (por ejemplo, en JSON o CSV simulado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avances (
            username TEXT PRIMARY KEY,
            libro_diario TEXT DEFAULT '',
            estado_ejercicio INTEGER DEFAULT 1,
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')
    conn.commit()
    conn.close()

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def registrar_usuario(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios VALUES (?, ?)", (username, hash_pass(password)))
        cursor.execute("INSERT INTO avances (username, libro_diario, estado_ejercicio) VALUES (?, '', 1)", (username,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verificar_credenciales(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, hash_pass(password)))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def cargar_datos_alumno(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT libro_diario, estado_ejercicio FROM avances WHERE username = ?", (username,))
    datos = cursor.fetchone()
    conn.close()
    return datos if datos else ("", 1)

def guardar_datos_alumno(username, libro_diario, estado_ejercicio):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE avances 
        SET libro_diario = ?, estado_ejercicio = ?
        WHERE username = ?
    ''', (libro_diario, estado_ejercicio, username))
    conn.commit()
    conn.close()

# ==========================================
# 2. CONTROL DE SESIÓN
# ==========================================

init_db()

st.set_page_config(page_title="Práctica Contable", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""

# --- PANTALLA DE ACCESO ---
if not st.session_state["autenticado"]:
    st.title("Sistemas de Información Contable - Acceso")
    
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab_login:
        user_input = st.text_input("Usuario (Legajo o Nombre)", key="login_u")
        pass_input = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Ingresar", type="primary"):
            if verificar_credenciales(user_input, pass_input):
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = user_input
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
                
    with tab_registro:
        nuevo_user = st.text_input("Crear Nombre de Usuario (Inmutable)", key="reg_u")
        nueva_pass = st.text_input("Crear Contraseña", type="password", key="reg_p")
        if st.button("Registrarme"):
            if nuevo_user.strip() and nueva_pass.strip():
                if registrar_usuario(nuevo_user.strip(), nueva_pass):
                    st.success("Cuenta creada. Ya puedes iniciar sesión.")
                else:
                    st.warning("Ese usuario ya existe. Elige otro.")
            else:
                st.error("Completa todos los campos.")

# --- PANTALLA DE TRABAJO: PRÁCTICA CONTABLE ---
else:
    usuario_activo = st.session_state["usuario"]
    libro_guardado, ejercicio_actual = cargar_datos_alumno(usuario_activo)

    # Panel Lateral de Usuario
    st.sidebar.title("Perfil de Usuario")
    st.sidebar.text_input("Alumno Conectado:", value=usuario_activo, disabled=True)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = ""
        st.rerun()

    st.title("Taller de Práctica Contable")
    st.subheader(f"Registro de Libro Diario y Asientos - Alumno: {usuario_activo}")
    st.divider()

    # ENUNCIADO DEL CASO PRÁCTICO
    with st.expander("Ver Enunciado de las Operaciones", expanded=True):
        st.markdown("""
        **Operaciones a registrar en el Libro Diario:**
        1. **Inicio de Actividades:** Apertura de la empresa con $100.000 en efectivo y $50.000 en banco.
        2. **Compra de Mercaderías:** Se compran $20.000 en mercaderías pagando el 50% en efectivo y el resto en cuenta corriente.
        3. **Venta de Mercaderías:** Se venden mercaderías por $30.000 cobrando con cheque común. (Costo de venta: $12.000).
        """)

    # INTERFAZ DE REGISTRO CONTABLE Y REGISTRO DE ASIENTOS
    col_asiento, col_diario = st.columns([1, 1])

    with col_asiento:
        st.markdown("### Registrar Asiento")
        fecha = st.date_input("Fecha")
        cuenta_debe = st.text_input("Cuenta a Debitar (Debe)")
        importe_debe = st.number_input("Monto Debe ($)", min_value=0.0, value=0.0)
        
        cuenta_haber = st.text_input("Cuenta a Acreditar (Haber)")
        importe_haber = st.number_input("Monto Haber ($)", min_value=0.0, value=0.0)
        
        leyenda = st.text_input("Leyenda / Documento Respaldatorio", value="s/Factura")

        if st.button("Agregar Asiento al Registro"):
            nuevo_registro = f"{fecha} | {cuenta_debe} ($ {importe_debe}) a {cuenta_haber} ($ {importe_haber}) - {leyenda}\n"
            libro_actualizado = libro_guardado + nuevo_registro
            guardar_datos_alumno(usuario_activo, libro_actualizado, ejercicio_actual)
            st.success("Asiento registrado y guardado.")
            st.rerun()

    with col_diario:
        st.markdown("### Libro Diario Registrado")
        # Mostramos lo que el alumno tiene guardado en la base de datos
        asientos_texto = st.text_area("Registros acumulados:", value=libro_guardado, height=300)
        
        if st.button("Guardar Cambios Manuales"):
            guardar_datos_alumno(usuario_activo, asientos_texto, ejercicio_actual)
            st.success("Libro Diario actualizado.")
            st.rerun()

        if st.button("Limpiar Mi Libro Diario", type="secondary"):
            guardar_datos_alumno(usuario_activo, "", ejercicio_actual)
            st.warning("Se ha reiniciado tu registro.")
            st.rerun()