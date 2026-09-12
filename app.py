import sqlite3
import hashlib
import pandas as pd
import streamlit as st

# ==========================================
# 1. BASE DE DATOS Y PERSISTENCIA
# ==========================================

DB_NAME = "practica_contable_v2.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    # Plan de Cuentas (por usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plan_cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            codigo TEXT,
            nombre_cuenta TEXT,
            tipo TEXT,
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')

    # Clientes (por usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            razon_social TEXT,
            cuit TEXT,
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')

    # Proveedores (por usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            razon_social TEXT,
            cuit TEXT,
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')

    # Libro Diario / Asientos (por usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            fecha TEXT,
            cuenta_debe TEXT,
            monto_debe REAL,
            cuenta_haber TEXT,
            monto_haber REAL,
            entidad_asociada TEXT,
            leyenda TEXT,
            FOREIGN KEY (username) REFERENCES usuarios (username)
        )
    ''')

    conn.commit()
    conn.close()

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def cargar_cuentas_base(username):
    """Carga un plan de cuentas básico inicial para el alumno recién registrado."""
    cuentas_iniciales = [
        ("1.1.1.01", "Caja", "Activo"),
        ("1.1.1.02", "Banco Nación C/C", "Activo"),
        ("1.1.2.01", "Deudores por Ventas", "Activo"),
        ("1.1.3.01", "Mercaderías", "Activo"),
        ("2.1.1.01", "Proveedores", "Pasivo"),
        ("2.1.2.01", "Obligaciones a Pagar", "Pasivo"),
        ("3.1.1.01", "Capital Social", "Patrimonio Neto"),
        ("4.1.1.01", "Ventas de Mercaderías", "Ingresos"),
        ("5.1.1.01", "Costo de Mercaderías Vendidas", "Gastos"),
    ]
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for cod, nom, tipo in cuentas_iniciales:
        cursor.execute("INSERT INTO plan_cuentas (username, codigo, nombre_cuenta, tipo) VALUES (?, ?, ?, ?)", (username, cod, nom, tipo))
    conn.commit()
    conn.close()

def registrar_usuario(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios VALUES (?, ?)", (username, hash_pass(password)))
        conn.commit()
        conn.close()
        cargar_cuentas_base(username)
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def verificar_credenciales(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, hash_pass(password)))
    user = cursor.fetchone()
    conn.close()
    return user is not None

# Funciones de lectura
def obtener_datos(tabla, username):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(f"SELECT * FROM {tabla} WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

# ==========================================
# 2. INTERFAZ DE USUARIO Y SESIÓN
# ==========================================

init_db()

st.set_page_config(page_title="Sistema de Gestión y Práctica Contable", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""

# --- PANTALLA DE ACCESO ---
if not st.session_state["autenticado"]:
    st.title("Sistema de Gestión y Práctica Contable")
    
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab_login:
        user_input = st.text_input("Usuario (Legajo / Nombre)", key="login_u")
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
                    st.success("Cuenta creada exitosamente. Ya puedes ingresar.")
                else:
                    st.warning("Ese usuario ya existe.")
            else:
                st.error("Completa todos los campos.")

# --- ENTORNO DE TRABAJO CONTABLE ---
else:
    usr = st.session_state["usuario"]

    # Barra lateral
    st.sidebar.title("Perfil de Usuario")
    st.sidebar.text_input("Alumno Conectado:", value=usr, disabled=True)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = ""
        st.rerun()

    st.title("Taller de Práctica Contable")
    
    # Navegación por Pestañas de Gestión
    tab_diario, tab_cuentas, tab_terceros = st.tabs([
        "📖 Libro Diario y Asientos", 
        "📊 Plan de Cuentas", 
        "👥 Clientes y Proveedores"
    ])

    # ----------------------------------------------------
    # PESTAÑA 1: LIBRO DIARIO Y REGISTRO DE ASIENTOS
    # ----------------------------------------------------
    with tab_diario:
        df_cuentas = obtener_datos("plan_cuentas", usr)
        df_cli = obtener_datos("clientes", usr)
        df_prov = obtener_datos("proveedores", usr)

        lista_cuentas = df_cuentas["codigo"] + " - " + df_cuentas["nombre_cuenta"] if not df_cuentas.empty else ["Sin Cuentas"]
        lista_terceros = ["Ninguno"] + list(df_cli["razon_social"]) + list(df_prov["razon_social"])

        st.subheader("Registrar Nuevo Asiento Contable")
        
        col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
        with col_f1:
            fecha = st.date_input("Fecha de la Operación")
        with col_f2:
            leyenda = st.text_input("Documento Respaldatorio / Leyenda", value="s/Factura A")
        with col_f3:
            tercero = st.selectbox("Cliente / Proveedor Asociado", options=lista_terceros)

        c_debe, c_haber = st.columns(2)

        with c_debe:
            st.markdown("#### Debe (Débito)")
            cuenta_debe = st.selectbox("Seleccionar Cuenta a Debitar", options=lista_cuentas, key="sb_debe")
            monto_debe = st.number_input("Monto Debe ($)", min_value=0.0, value=0.0, step=100.0)

        with c_haber:
            st.markdown("#### Haber (Crédito)")
            cuenta_haber = st.selectbox("Seleccionar Cuenta a Acreditar", options=lista_cuentas, key="sb_haber")
            monto_haber = st.number_input("Monto Haber ($)", min_value=0.0, value=0.0, step=100.0)

        if st.button("Guardar Asiento en Libro Diario", type="primary"):
            if monto_debe <= 0 or monto_haber <= 0:
                st.error("Los importes deben ser mayores a cero.")
            elif cuenta_debe == cuenta_haber:
                st.warning("La cuenta del Debe y del Haber no pueden ser iguales.")
            else:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO asientos (username, fecha, cuenta_debe, monto_debe, cuenta_haber, monto_haber, entidad_asociada, leyenda)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (usr, str(fecha), cuenta_debe, monto_debe, cuenta_haber, monto_haber, tercero, leyenda))
                conn.commit()
                conn.close()
                st.success("Asiento asentado y persistido correctamente.")
                st.rerun()

        st.divider()
        st.subheader("Libro Diario General")
        df_asientos = obtener_datos("asientos", usr)
        
        if not df_asientos.empty:
            st.dataframe(df_asientos[["fecha", "cuenta_debe", "monto_debe", "cuenta_haber", "monto_haber", "entidad_asociada", "leyenda"]], use_container_width=True)
        else:
            st.info("No hay asientos registrados para este usuario.")

    # ----------------------------------------------------
    # PESTAÑA 2: PLAN DE CUENTAS
    # ----------------------------------------------------
    with tab_cuentas:
        st.subheader("Plan de Cuentas del Alumno")
        
        with st.expander("Alta de Nueva Cuenta Contable"):
            c1, c2, c3 = st.columns(3)
            cod_c = c1.text_input("Código (ej: 1.1.1.03)")
            nom_c = c2.text_input("Nombre de Cuenta (ej: Banco Galicia)")
            tipo_c = c3.selectbox("Tipo de Cuenta", ["Activo", "Pasivo", "Patrimonio Neto", "Ingresos", "Gastos"])
            
            if st.button("Agregar Cuenta"):
                if cod_c.strip() and nom_c.strip():
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO plan_cuentas (username, codigo, nombre_cuenta, tipo) VALUES (?, ?, ?, ?)", (usr, cod_c, nom_c, tipo_c))
                    conn.commit()
                    conn.close()
                    st.success("Cuenta agregada.")
                    st.rerun()

        df_c = obtener_datos("plan_cuentas", usr)
        st.dataframe(df_c[["codigo", "nombre_cuenta", "tipo"]], use_container_width=True)

    # ----------------------------------------------------
    # PESTAÑA 3: CLIENTES Y PROVEEDORES
    # ----------------------------------------------------
    with tab_terceros:
        st.subheader("Gestión de Entidades Comerciales")
        col_cli, col_prov = st.columns(2)

        with col_cli:
            st.markdown("### Clientes")
            with st.form("form_cliente"):
                rs_cli = st.text_input("Razón Social / Nombre")
                cuit_cli = st.text_input("CUIT / DNI")
                if st.form_submit_button("Guardar Cliente"):
                    if rs_cli.strip():
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO clientes (username, razon_social, cuit) VALUES (?, ?, ?)", (usr, rs_cli, cuit_cli))
                        conn.commit()
                        conn.close()
                        st.success("Cliente guardado.")
                        st.rerun()
            
            st.dataframe(obtener_datos("clientes", usr)[["razon_social", "cuit"]], use_container_width=True)

        with col_prov:
            st.markdown("### Proveedores")
            with st.form("form_proveedor"):
                rs_pr = st.text_input("Razón Social / Nombre")
                cuit_pr = st.text_input("CUIT / DNI")
                if st.form_submit_button("Guardar Proveedor"):
                    if rs_pr.strip():
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO proveedores (username, razon_social, cuit) VALUES (?, ?, ?)", (usr, rs_pr, cuit_pr))
                        conn.commit()
                        conn.close()
                        st.success("Proveedor guardado.")
                        st.rerun()
                        
            st.dataframe(obtener_datos("proveedores", usr)[["razon_social", "cuit"]], use_container_width=True)