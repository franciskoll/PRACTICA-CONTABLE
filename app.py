import sqlite3
import hashlib
import streamlit as st

# ==========================================
# 1. GESTIÓN DE BASE DE DATOS Y SEGURIDAD
# ==========================================

DB_NAME = "sistema_alumnos.db"

def init_db():
    """Crea la estructura de tablas si no existe."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de credenciales (Username es clave única/primaria)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    # Tabla de avances (Vinculada al usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avances (
            username TEXT PRIMARY KEY,
            modulo_actual INTEGER DEFAULT 1,
            calificacion REAL DEFAULT 0.0,
            respuestas_guardadas TEXT DEFAULT '',
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')
    conn.commit()
    conn.close()

def hash_pass(password: str) -> str:
    """Encripta la contraseña para no guardarla en texto plano."""
    return hashlib.sha256(password.encode()).hexdigest()

def registrar_usuario(username, password):
    """Registra usuario y crea su registro de avance inicial."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios VALUES (?, ?)", (username, hash_pass(password)))
        cursor.execute("INSERT INTO avances (username, modulo_actual, calificacion, respuestas_guardadas) VALUES (?, 1, 0.0, '')", (username,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # El nombre de usuario ya está registrado
    finally:
        conn.close()

def verificar_credenciales(username, password):
    """Valida si el usuario y contraseña coinciden."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, hash_pass(password)))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def obtener_avance(username):
    """Carga el estado del alumno."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT modulo_actual, calificacion, respuestas_guardadas FROM avances WHERE username = ?", (username,))
    datos = cursor.fetchone()
    conn.close()
    return datos if datos else (1, 0.0, "")

def guardar_avance(username, modulo, calificacion, respuestas=""):
    """Actualiza y persiste los datos del alumno."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE avances 
        SET modulo_actual = ?, calificacion = ?, respuestas_guardadas = ?
        WHERE username = ?
    ''', (modulo, calificacion, respuestas, username))
    conn.commit()
    conn.close()


# ==========================================
# 2. CONTROL DE SESIÓN Y FLUJO
# ==========================================

init_db()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""

# --- PANTALLA 1: LOGIN / REGISTRO ---
if not st.session_state["autenticado"]:
    st.title("Plataforma Educativa - Acceso")
    
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab_login:
        user_input = st.text_input("Nombre de Usuario", key="login_user")
        pass_input = st.text_input("Contraseña", type="password", key="login_pass")
        
        if st.button("Ingresar", type="primary"):
            if verificar_credenciales(user_input, pass_input):
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = user_input
                st.success("Acceso correcto.")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
                
    with tab_registro:
        nuevo_user = st.text_input("Elige un Nombre de Usuario (Inmutable)", key="reg_user")
        nueva_pass = st.text_input("Crea tu Contraseña", type="password", key="reg_pass")
        
        if st.button("Crear Cuenta"):
            if nuevo_user.strip() and nueva_pass.strip():
                if registrar_usuario(nuevo_user.strip(), nueva_pass):
                    st.success("Cuenta registrada con éxito. Ahora puedes iniciar sesión.")
                else:
                    st.warning("Ese nombre de usuario ya existe. Elige otro.")
            else:
                st.error("Por favor completa todos los campos.")

# --- PANTALLA 2: ENTORNO DEL ALUMNO ---
else:
    usuario_activo = st.session_state["usuario"]
    modulo, calificacion, respuestas = obtener_avance(usuario_activo)
    
    # Barra lateral: Identificación estática y deshabilitada
    st.sidebar.title("Perfil del Alumno")
    st.sidebar.text_input("Usuario Activo:", value=usuario_activo, disabled=True)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = ""
        st.rerun()

    # Panel principal
    st.title(f"Bienvenido/a, {usuario_activo}")
    
    # Métricas de estado
    c1, c2 = st.columns(2)
    c1.metric("Módulo Actual", f"Módulo {modulo}")
    c2.metric("Calificación Promedio", f"{calificacion:.2f}")
    
    st.divider()
    
    # Simulación de actividades
    st.subheader(f"Contenido del Módulo {modulo}")
    
    respuesta_actividad = st.text_area("Desarrollo de la tarea:", value=respuestas)
    nuevo_puntaje = st.slider("Calificación sugerida/obtenida:", 0.0, 10.0, value=float(calificacion))
    
    if st.button("Guardar Avance del Trabajo"):
        guardar_avance(usuario_activo, modulo, nuevo_puntaje, respuesta_actividad)
        st.success("Progreso guardado en la base de datos.")
        st.rerun()
        
    if st.button("Avanzar al Siguiente Módulo"):
        guardar_avance(usuario_activo, modulo + 1, nuevo_puntaje, respuesta_actividad)
        st.success("¡Has avanzado de módulo!")
        st.rerun()