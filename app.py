import streamlit as st
import pandas as pd
import json
import hashlib
import datetime
import io
from supabase import create_client, Client

# Importaciones para generación de PDF con ReportLab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Configuración de la página
st.set_page_config(page_title="App Educativa de Contabilidad", layout="wide")

# ==========================================
# 0. CONEXIÓN A SUPABASE
# ==========================================

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ==========================================
# 1. BASE DE DATOS Y PERSISTENCIA (SUPABASE)
# ==========================================

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    res = supabase.table("usuarios").select("username").eq("username", "admin").execute()
    if not res.data:
        supabase.table("usuarios").insert({
            "username": "admin",
            "password": hash_pass("admin123"),
            "nombre_alumno": "Profesor / Administrador",
            "curso": "Docente"
        }).execute()

def registrar_log(username, accion, detalle=""):
    try:
        fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        supabase.table("logs_actividad").insert({
            "username": username,
            "fecha_hora": fecha_actual,
            "accion": accion,
            "detalle": detalle
        }).execute()
    except Exception as e:
        print(f"Error registrando log: {e}")

def registrar_usuario(username, password, nombre_alumno, curso):
    try:
        supabase.table("usuarios").insert({
            "username": username,
            "password": hash_pass(password),
            "nombre_alumno": nombre_alumno,
            "curso": curso
        }).execute()
        
        plan_base = [
            "1.1.01 Caja", "1.1.02 Banco Nación c/c",
            "1.2.01 Deudores por Ventas (Clientes)", "1.2.02 Deudores Morosos", "1.2.03 Deudores Incobrables",
            "1.3.01 Mercaderías (Stock)", "1.4.01 Muebles y Útiles",
            "1.4.02 Depreciación Acumulada Muebles y Útiles", "2.1.01 Proveedores",
            "2.1.02 Obligaciones a Pagar", "3.1.01 Capital Social", "4.1.01 Ventas",
            "4.2.01 Sobrante de Caja", "5.1.01 Costo de Mercaderías Vendidas (CMV)",
            "5.1.02 Gastos Generales", "5.2.01 Faltante de Caja", "5.2.02 Depreciación Muebles y Útiles"
        ]
        
        datos_iniciales = {
            "alumno_nombre": nombre_alumno,
            "alumno_curso": curso,
            "plan_cuentas": plan_base,
            "padron_terceros": [],
            "padron_articulos": [],
            "libro_diario": [],
            "submayores": {"Clientes": [], "Proveedores": [], "Stock_Fisico": [], "Stock_Valorizado": {}}
        }
        
        supabase.table("estado_alumno").insert({
            "username": username,
            "datos_json": json.dumps(datos_iniciales)
        }).execute()

        registrar_log(username, "REGISTRO_CUENTA", f"Nuevo registro de usuario: {nombre_alumno}")
        return True
    except Exception as e:
        return False

def verificar_credenciales(username, password):
    res = supabase.table("usuarios").select("*").eq("username", username).eq("password", hash_pass(password)).execute()
    return len(res.data) > 0

def cargar_estado_db(username):
    res = supabase.table("estado_alumno").select("datos_json").eq("username", username).execute()
    if res.data and res.data[0].get("datos_json"):
        datos = json.loads(res.data[0]["datos_json"])
        for renglon in datos.get("libro_diario", []):
            if isinstance(renglon.get("Fecha"), str):
                renglon["Fecha"] = datetime.date.fromisoformat(renglon["Fecha"])
                
        for clave, movs in datos.get("submayores", {}).items():
            if isinstance(movs, list):
                for m in movs:
                    if isinstance(m.get("Fecha"), str):
                        m["Fecha"] = datetime.date.fromisoformat(m["Fecha"])
            elif isinstance(movs, dict):
                for art, registros in movs.items():
                    for r in registros:
                        if isinstance(r.get("Fecha"), str):
                            r["Fecha"] = datetime.date.fromisoformat(r["Fecha"])
        return datos
    return None

def guardar_estado_db(username):
    if username == "admin":
        return
        
    def serializar_fecha(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()

    datos_exportar = {
        "alumno_nombre": st.session_state.alumno_nombre,
        "alumno_curso": st.session_state.alumno_curso,
        "plan_cuentas": st.session_state.plan_cuentas,
        "padron_terceros": st.session_state.padron_terceros,
        "padron_articulos": st.session_state.padron_articulos,
        "libro_diario": st.session_state.libro_diario,
        "submayores": st.session_state.submayores
    }
    
    json_str = json.dumps(datos_exportar, default=serializar_fecha, indent=2)
    supabase.table("estado_alumno").update({"datos_json": json_str}).eq("username", username).execute()

def obtener_todos_usuarios():
    res = supabase.table("usuarios").select("username, nombre_alumno, curso").neq("username", "admin").execute()
    return [(u["username"], u["nombre_alumno"], u["curso"]) for u in res.data]

def obtener_datos_usuario(username):
    res = supabase.table("usuarios").select("username, nombre_alumno, curso").eq("username", username).execute()
    if res.data:
        u = res.data[0]
        return (u["username"], u["nombre_alumno"], u["curso"])
    return None

def admin_actualizar_usuario(old_username, nuevo_nombre, nuevo_curso):
    supabase.table("usuarios").update({
        "nombre_alumno": nuevo_nombre,
        "curso": nuevo_curso
    }).eq("username", old_username).execute()
    
    res = supabase.table("estado_alumno").select("datos_json").eq("username", old_username).execute()
    if res.data and res.data[0].get("datos_json"):
        datos = json.loads(res.data[0]["datos_json"])
        datos["alumno_nombre"] = nuevo_nombre
        datos["alumno_curso"] = nuevo_curso
        supabase.table("estado_alumno").update({"datos_json": json.dumps(datos)}).eq("username", old_username).execute()

    registrar_log("admin", "MODIFICACION_USUARIO", f"Actualizados datos de {old_username}")

def admin_reset_password(username, nueva_clave):
    supabase.table("usuarios").update({"password": hash_pass(nueva_clave)}).eq("username", username).execute()
    registrar_log("admin", "RESET_PASSWORD", f"Restablecida clave de {username}")

def eliminar_usuario(username):
    supabase.table("estado_alumno").delete().eq("username", username).execute()
    supabase.table("logs_actividad").delete().eq("username", username).execute()
    supabase.table("usuarios").delete().eq("username", username).execute()
    registrar_log("admin", "ELIMINAR_USUARIO", f"Usuario eliminado: {username}")

def admin_reiniciar_asientos_usuario(username):
    res = supabase.table("estado_alumno").select("datos_json").eq("username", username).execute()
    if res.data and res.data[0].get("datos_json"):
        datos = json.loads(res.data[0]["datos_json"])
        
        # Blanqueamos Libro Diario y Submayores manteniendo padrones y plan de cuentas
        datos["libro_diario"] = []
        datos["submayores"] = {
            "Clientes": [], 
            "Proveedores": [], 
            "Stock_Fisico": [], 
            "Stock_Valorizado": {}
        }
        
        json_str = json.dumps(datos)
        supabase.table("estado_alumno").update({"datos_json": json_str}).eq("username", username).execute()
        registrar_log("admin", "REINICIAR_ASIENTOS", f"Se reiniciaron los asientos del usuario: {username}")

def obtener_logs_auditoria():
    res = supabase.table("logs_actividad").select("id, username, fecha_hora, accion, detalle").order("id", desc=True).limit(200).execute()
    return res.data

# ==========================================
# 2. CONTROL DE ACCESO Y SESIÓN
# ==========================================

init_db()

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""

if "asiento_form_id" not in st.session_state:
    st.session_state["asiento_form_id"] = 0

if not st.session_state["autenticado"]:
    st.title("📚 Sistema Contable Educativo con Auditoría")
    st.write("Acceso al entorno de práctica contable.")
    
    tab_login, tab_registro, tab_recuperar = st.tabs(["Iniciar Sesión", "Registrarse", "Recuperar Contraseña"])
    
    with tab_login:
        user_input = st.text_input("Usuario (DNI / Legajo)", key="l_user")
        pass_input = st.text_input("Contraseña", type="password", key="l_pass")
        if st.button("Ingresar al Taller", type="primary"):
            user_clean = user_input.strip()
            if verificar_credenciales(user_clean, pass_input):
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = user_clean
                
                if user_clean != "admin":
                    estado = cargar_estado_db(user_clean)
                    if estado:
                        st.session_state.alumno_nombre = estado.get("alumno_nombre", "Alumno")
                        st.session_state.alumno_curso = estado.get("alumno_curso", "5° Año")
                        st.session_state.plan_cuentas = estado.get("plan_cuentas", [])
                        st.session_state.padron_terceros = estado.get("padron_terceros", [])
                        st.session_state.padron_articulos = estado.get("padron_articulos", [])
                        st.session_state.libro_diario = estado.get("libro_diario", [])
                        st.session_state.submayores = estado.get("submayores", {})
                else:
                    st.session_state.alumno_nombre = "Profesor / Administrador"
                    st.session_state.alumno_curso = "Docente Maestro"
                    st.session_state.plan_cuentas = []
                    st.session_state.padron_terceros = []
                    st.session_state.padron_articulos = []
                    st.session_state.libro_diario = []
                    st.session_state.submayores = {}

                registrar_log(user_clean, "INICIO_SESION", "Ingreso exitoso al sistema")
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
                
    with tab_registro:
        with st.form("form_registro_usuario", clear_on_submit=True):
            r_user = st.text_input("Crear Nombre de Usuario / DNI")
            r_pass = st.text_input("Crear Contraseña", type="password")
            r_nom = st.text_input("Nombre Completo del Alumno")
            r_curso = st.text_input("Curso / Domicilio / División", value="5° Año - Contabilidad")
            
            submit_registro = st.form_submit_button("Crear Cuenta", type="primary")

        if submit_registro:
            usuario_clean = r_user.strip()
            pass_clean = r_pass.strip()
            nom_clean = r_nom.strip()
            curso_clean = r_curso.strip()

            if usuario_clean.lower() == "admin":
                st.error("El nombre 'admin' está reservado.")
            elif usuario_clean and pass_clean and nom_clean:
                if registrar_usuario(usuario_clean, pass_clean, nom_clean, curso_clean):
                    st.success("¡Cuenta creada exitosamente! Ya puedes iniciar sesión en la otra pestaña.")
                else:
                    st.warning("El nombre de usuario o DNI ya se encuentra registrado.")
            else:
                st.error("Completa todos los campos obligatorios.")

    with tab_recuperar:
        st.subheader("🔑 Restablecer Contraseña")
        with st.form("form_recuperar_pass", clear_on_submit=True):
            rec_user = st.text_input("Usuario / DNI")
            rec_nombre = st.text_input("Nombre Completo (tal como te registraste)")
            rec_pass_nueva = st.text_input("Nueva Contraseña", type="password")
            
            submit_rec = st.form_submit_button("Cambiar Contraseña")

        if submit_rec:
            u_clean = rec_user.strip()
            n_clean = rec_nombre.strip()
            p_clean = rec_pass_nueva.strip()

            if u_clean and n_clean and p_clean:
                res = supabase.table("usuarios").select("*").eq("username", u_clean).ilike("nombre_alumno", n_clean).execute()
                if res.data:
                    supabase.table("usuarios").update({"password": hash_pass(p_clean)}).eq("username", u_clean).execute()
                    registrar_log(u_clean, "RECUPERACION_PASSWORD", "Restablecimiento de clave realizado")
                    st.success("¡Contraseña restablecida con éxito! Ya puedes iniciar sesión.")
                else:
                    st.error("Los datos ingresados no coinciden.")
            else:
                st.error("Completa todos los campos.")

    st.stop()

# ==========================================
# 3. ENTORNO DE TRABAJO CONTABLE
# ==========================================

usr_act = st.session_state["usuario"]

st.title("📚 Sistema Contable Educativo con Auditoría")
st.write("Herramienta pedagógica para registración manual, gestión de padrones, valuación de inventarios por PPP y Hoja de Trabajo (8 Columnas).")

st.sidebar.header("🎓 Datos del Estudiante")
st.sidebar.text_input("Usuario Activo", value=usr_act, disabled=True)

st.session_state.alumno_nombre = st.sidebar.text_input("Nombre del Alumno", value=st.session_state.alumno_nombre, disabled=(usr_act=="admin"))
st.session_state.alumno_curso = st.sidebar.text_input("Curso / Domicilio", value=st.session_state.alumno_curso, disabled=(usr_act=="admin"))

if usr_act != "admin":
    if st.sidebar.button("💾 Guardar Avance en Nube"):
        guardar_estado_db(usr_act)
        registrar_log(usr_act, "GUARDAR_AVANCE", "Avance guardado manualmente")
        st.sidebar.success("¡Avance guardado exitosamente!")

if st.sidebar.button("Cerrar Sesión"):
    if usr_act != "admin":
        guardar_estado_db(usr_act)
    registrar_log(usr_act, "CIERRE_SESION", "Sesión cerrada")
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""
    st.rerun()

st.sidebar.divider()

def obtener_encabezado_pdf(styles):
    style_header_label = ParagraphStyle('HLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#1E293B'))
    style_header_right = ParagraphStyle('HRight', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, alignment=2, textColor=colors.HexColor('#64748B'))
    fecha_emision = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    header_data = [
        [
            Paragraph(f"<b>Estudiante:</b> {st.session_state.alumno_nombre}", style_header_label),
            Paragraph(f"<b>Emisión:</b> {fecha_emision}", style_header_right)
        ],
        [
            Paragraph(f"<b>Curso/Domicilio:</b> {st.session_state.alumno_curso}", style_header_label),
            Paragraph("Sistema de Practicantes Contables", style_header_right)
        ]
    ]

    table_header = Table(header_data, colWidths=[350, 190])
    table_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))

    return [
        table_header,
        Spacer(1, 5),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=15)
    ]

def generar_pdf_libro_diario(asientos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, alignment=1, spaceAfter=12)
    style_normal = ParagraphStyle('NormStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9)
    style_right = ParagraphStyle('RightStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, alignment=2)
    style_th = ParagraphStyle('THStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1, textColor=colors.white)

    elements = []
    elements.extend(obtener_encabezado_pdf(styles))
    elements.append(Paragraph("LIBRO DIARIO GENERAL", style_title))
    elements.append(Spacer(1, 10))

    headers = [
        Paragraph("<b>Fecha / Detalle</b>", style_th),
        Paragraph("<b>Cuenta / Imputación</b>", style_th),
        Paragraph("<b>Debe ($)</b>", style_th),
        Paragraph("<b>Haber ($)</b>", style_th)
    ]
    data = [headers]

    for a in asientos:
        tipo_asiento_tag = f" [{a.get('Tipo_Asiento', 'Normal')}]" if a.get('Tipo_Asiento') == 'Ajuste de Auditoría' else ""
        data.append([
            Paragraph(f"<b>Asiento N° {a['Asiento']}</b>{tipo_asiento_tag}<br/>{a['Fecha']}", style_normal),
            Paragraph(f"<b>Operación:</b> {a['Operación']}", style_normal),
            "", ""
        ])
        for r in a['Renglones']:
            debe_str = f"${r['Monto']:,.2f}" if r['Tipo'] == "Debe" else ""
            haber_str = f"${r['Monto']:,.2f}" if r['Tipo'] == "Haber" else ""
            cuenta_fmt = f"<b>{r['Cuenta']}</b>" if r['Tipo'] == "Debe" else f"&nbsp;&nbsp;&nbsp;&nbsp;a <b>{r['Cuenta']}</b>"
            
            data.append([
                "",
                Paragraph(cuenta_fmt, style_normal),
                Paragraph(debe_str, style_right),
                Paragraph(haber_str, style_right)
            ])
            
        tercero_str = f" | Tercero: {a['Tercero']}" if a['Tercero'] != "N/A" else ""
        data.append([
            "",
            Paragraph(f"<i>Según: {a['Concepto']}{tercero_str}</i>", style_normal),
            "", ""
        ])

    table = Table(data, colWidths=[100, 270, 90, 90])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generar_pdf_tabla_generica(titulo, df, orientacion="portrait"):
    buffer = io.BytesIO()
    pagesize = landscape(letter) if orientacion == "landscape" else letter
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, alignment=1, spaceAfter=12)
    style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=7)
    style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1, textColor=colors.white)

    elements = []
    elements.extend(obtener_encabezado_pdf(styles))
    elements.append(Paragraph(f"<b>{titulo.upper()}</b>", style_title))
    elements.append(Spacer(1, 10))

    if isinstance(df.columns, pd.MultiIndex):
        headers = [Paragraph(f"<b>{col[1] if col[1] else col[0]}</b>", style_header) for col in df.columns]
    else:
        headers = [Paragraph(f"<b>{col}</b>", style_header) for col in df.columns]
    table_data = [headers]

    for _, row in df.iterrows():
        row_data = []
        for val in row:
            if isinstance(val, (float, int)):
                val_str = f"${val:,.2f}" if isinstance(val, float) else str(val)
            else:
                val_str = str(val) if pd.notnull(val) else ""
            row_data.append(Paragraph(val_str, style_cell))
        table_data.append(row_data)

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# OPCIONES DE NAVEGACIÓN DIVERSIFICADAS POR ROL
opciones_menu = [
    "1. Padrones y Plan de Cuentas",
    "2. Carga de Asientos (Libro Diario)",
    "3. Libro Mayor y Submayores",
    "4. Ficha de Stock PPP",
    "5. Sumas y Saldos",
    "6. Auditoría y Prebalance (8 Columnas)"
]

if usr_act == "admin":
    opciones_menu.insert(0, "👨‍🏫 Gestión de Alumnos")

menu = st.sidebar.radio("Navegación", opciones_menu)

# MÓDULO EXCLUSIVO PARA ADMINISTRADOR / PROFESOR
if menu == "👨‍🏫 Gestión de Alumnos":
    st.header("👨‍🏫 Panel de Control Docente y Administración de Usuarios")
    
    tab_alum, tab_logs = st.tabs(["👥 Lista de Alumnos", "📋 Registro de Auditoría / Logs de Uso"])

    with tab_alum:
        usuarios_list = obtener_todos_usuarios()
        if usuarios_list:
            df_u = pd.DataFrame(usuarios_list, columns=["Usuario / DNI", "Nombre Completo del Alumno", "Curso / Domicilio"])
            st.dataframe(df_u, use_container_width=True)
            
            st.divider()
            col_adm1, col_adm2, col_adm3, col_adm4 = st.columns(4)
            
            with col_adm1:
                st.markdown("##### ✏️ Editar Datos")
                user_edit = st.selectbox("Seleccionar Usuario", [u[0] for u in usuarios_list], key="sel_edit_adm")
                u_datos = obtener_datos_usuario(user_edit)
                if u_datos:
                    with st.form("form_edit_user"):
                        nuevo_nombre = st.text_input("Nombre Completo", value=u_datos[1])
                        nuevo_curso = st.text_input("Curso / Domicilio", value=u_datos[2])
                        if st.form_submit_button("Guardar Cambios", type="primary"):
                            if nuevo_nombre.strip() and nuevo_curso.strip():
                                admin_actualizar_usuario(user_edit, nuevo_nombre.strip(), nuevo_curso.strip())
                                st.success(f"Datos del usuario '{user_edit}' actualizados.")
                                st.rerun()
                            else:
                                st.error("Los campos no pueden estar vacíos.")
            
            with col_adm2:
                st.markdown("##### 🔑 Cambiar Clave")
                user_reset = st.selectbox("Seleccionar Alumno", [u[0] for u in usuarios_list], key="sel_reset_adm")
                pass_nueva = st.text_input("Nueva Contraseña", type="password", key="pass_reset_adm")
                if st.button("Actualizar Contraseña", type="primary"):
                    if pass_nueva.strip():
                        admin_reset_password(user_reset, pass_nueva.strip())
                        st.success(f"Contraseña de '{user_reset}' actualizada.")
                    else:
                        st.error("Ingresa una contraseña válida.")

            with col_adm3:
                st.markdown("##### 🔄 Reiniciar Asientos")
                user_res_ast = st.selectbox("Seleccionar Alumno", [u[0] for u in usuarios_list], key="sel_res_ast_adm")
                if st.button("Blanquear Asientos", type="secondary"):
                    admin_reiniciar_asientos_usuario(user_res_ast)
                    st.success(f"Asientos de '{user_res_ast}' reiniciados.")
                    st.rerun()

            with col_adm4:
                st.markdown("##### 🗑️ Eliminar Usuario")
                user_del = st.selectbox("Seleccionar Alumno a Eliminar", [u[0] for u in usuarios_list], key="sel_del_adm")
                if st.button("Eliminar Cuenta Definitivamente"):
                    eliminar_usuario(user_del)
                    st.warning(f"Usuario '{user_del}' eliminado.")
                    st.rerun()
        else:
            st.info("Aún no hay alumnos registrados en la base de datos.")

    with tab_logs:
        st.subheader("📋 Historial Reciente de Actividades y Registros")
        logs = obtener_logs_auditoria()
        if logs:
            df_logs = pd.DataFrame(logs)
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("No hay registros de actividad almacenados.")

# MÓDULO 1: PADRONES Y PLAN DE CUENTAS
elif menu == "1. Padrones y Plan de Cuentas":
    st.header("⚙️ Configuración Inicial: Padrones, Inventario y Cuentas")
    
    tab_padron, tab_articulos, tab_cuentas = st.tabs([
        "👥 Padrón de Clientes / Proveedores", 
        "📦 Inventario (Artículos)", 
        "📑 Plan de Cuentas"
    ])

    with tab_padron:
        st.subheader("Alta de Cliente o Proveedor")
        with st.form("form_tercero", clear_on_submit=True):
            col_t1, col_t2 = st.columns(2)
            tipo_tercero = col_t1.selectbox("Tipo de Entidad", ["Cliente", "Proveedor"])
            nombre = col_t2.text_input("Razón Social / Nombre", placeholder="Ej: Distribuidora Tucumán S.R.L.")

            col_t3, col_t4, col_t5 = st.columns(3)
            cuit = col_t3.text_input("CUIT / DNI", placeholder="20-30405060-7")
            domicilio = col_t4.text_input("Domicilio Comercial", placeholder="Ej: Av. San Martín 450")
            condicion_pago = col_t5.selectbox("Condición Habitual", [
                "Contado / Efectivo",
                "Cuenta Corriente 30 días",
                "Cuenta Corriente 60 días",
                "Transferencia Bancaria"
            ])

            if st.form_submit_button("Guardar en Padrón"):
                if not nombre or not cuit:
                    st.error("El nombre y el CUIT son obligatorios.")
                else:
                    st.session_state.padron_terceros.append({
                        "Tipo": tipo_tercero,
                        "Nombre": nombre,
                        "CUIT": cuit,
                        "Domicilio": domicilio,
                        "Condicion": condicion_pago
                    })
                    guardar_estado_db(usr_act)
                    registrar_log(usr_act, "ALTA_PADRON", f"Alta de {tipo_tercero}: {nombre}")
                    st.success(f"{tipo_tercero} '{nombre}' registrado correctamente.")

        st.subheader("📋 Padrón Registrado")
        if st.session_state.padron_terceros:
            st.dataframe(pd.DataFrame(st.session_state.padron_terceros), use_container_width=True)
            
            st.divider()
            col_ep1, col_ep2 = st.columns(2)
            
            with col_ep1:
                st.markdown("##### ✏️ Editar Entidad del Padrón")
                nombres_padr = [t["Nombre"] for t in st.session_state.padron_terceros]
                sel_edit_ter = st.selectbox("Seleccionar Entidad a Editar", nombres_padr, key="sel_edit_padr")
                idx_ter = nombres_padr.index(sel_edit_ter)
                ent_act = st.session_state.padron_terceros[idx_ter]
                
                with st.form("form_edit_tercero"):
                    e_tipo = st.selectbox("Tipo", ["Cliente", "Proveedor"], index=0 if ent_act["Tipo"] == "Cliente" else 1)
                    e_nom = st.text_input("Nombre / Razón Social", value=ent_act["Nombre"])
                    e_cuit = st.text_input("CUIT / DNI", value=ent_act["CUIT"])
                    e_dom = st.text_input("Domicilio", value=ent_act["Domicilio"])
                    e_cond = st.text_input("Condición Habitual", value=ent_act["Condicion"])
                    
                    if st.form_submit_button("Guardar Cambios en Padrón"):
                        st.session_state.padron_terceros[idx_ter] = {
                            "Tipo": e_tipo, "Nombre": e_nom, "CUIT": e_cuit,
                            "Domicilio": e_dom, "Condicion": e_cond
                        }
                        guardar_estado_db(usr_act)
                        registrar_log(usr_act, "EDITAR_PADRON", f"Edición de entidad: {e_nom}")
                        st.success("Entidad actualizada correctamente.")
                        st.rerun()

            with col_ep2:
                st.markdown("##### 🗑️ Eliminar Entidad del Padrón")
                sel_del_ter = st.selectbox("Seleccionar Entidad a Eliminar", nombres_padr, key="sel_del_padr")
                if st.button("Eliminar del Padrón"):
                    idx_d = nombres_padr.index(sel_del_ter)
                    st.session_state.padron_terceros.pop(idx_d)
                    guardar_estado_db(usr_act)
                    registrar_log(usr_act, "ELIMINAR_PADRON", f"Eliminación de entidad: {sel_del_ter}")
                    st.warning(f"Entidad '{sel_del_ter}' eliminada.")
                    st.rerun()
        else:
            st.info("Aún no hay clientes o proveedores registrados.")

    with tab_articulos:
        st.subheader("Alta de Artículo de Inventario")
        with st.form("form_articulo", clear_on_submit=True):
            col_a1, col_a2, col_a3 = st.columns([1, 2, 1])
            cod_art = col_a1.text_input("Código de Artículo", placeholder="Ej: ART-001")
            nom_art = col_a2.text_input("Descripción / Nombre del Artículo", placeholder="Ej: Resma A4 75g")
            um_art = col_a3.selectbox("Unidad de Medida", ["Unidades", "Kilos", "Litros", "Metros", "Cajas", "Packs"])

            if st.form_submit_button("Guardar Artículo"):
                if not nom_art:
                    st.error("El nombre del artículo es obligatorio.")
                else:
                    nombres_existentes = [a["Nombre"] for a in st.session_state.padron_articulos]
                    if nom_art in nombres_existentes:
                        st.warning(f"El artículo '{nom_art}' ya se encuentra registrado.")
                    else:
                        st.session_state.padron_articulos.append({
                            "Código": cod_art if cod_art else "S/C",
                            "Nombre": nom_art,
                            "Unidad": um_art
                        })
                        guardar_estado_db(usr_act)
                        registrar_log(usr_act, "ALTA_ARTICULO", f"Nuevo artículo: {nom_art}")
                        st.success(f"Artículo '{nom_art}' registrado en el inventario.")

        st.subheader("📋 Catálogo de Artículos Registrados")
        if st.session_state.padron_articulos:
            st.dataframe(pd.DataFrame(st.session_state.padron_articulos), use_container_width=True)
            
            st.divider()
            col_ea1, col_ea2 = st.columns(2)
            
            with col_ea1:
                st.markdown("##### ✏️ Editar Artículo")
                nombres_arts = [a["Nombre"] for a in st.session_state.padron_articulos]
                sel_edit_art = st.selectbox("Seleccionar Artículo a Editar", nombres_arts, key="sel_edit_art")
                idx_art = nombres_arts.index(sel_edit_art)
                art_act = st.session_state.padron_articulos[idx_art]
                
                with st.form("form_edit_art"):
                    ea_cod = st.text_input("Código", value=art_act["Código"])
                    ea_nom = st.text_input("Descripción / Nombre", value=art_act["Nombre"])
                    ea_um = st.text_input("Unidad de Medida", value=art_act["Unidad"])
                    
                    if st.form_submit_button("Guardar Cambios en Artículo"):
                        st.session_state.padron_articulos[idx_art] = {
                            "Código": ea_cod, "Nombre": ea_nom, "Unidad": ea_um
                        }
                        guardar_estado_db(usr_act)
                        registrar_log(usr_act, "EDITAR_ARTICULO", f"Edición de artículo: {ea_nom}")
                        st.success("Artículo actualizado correctamente.")
                        st.rerun()

            with col_ea2:
                st.markdown("##### 🗑️ Eliminar Artículo")
                sel_del_art = st.selectbox("Seleccionar Artículo a Eliminar", nombres_arts, key="sel_del_art")
                if st.button("Eliminar del Inventario"):
                    idx_da = nombres_arts.index(sel_del_art)
                    st.session_state.padron_articulos.pop(idx_da)
                    guardar_estado_db(usr_act)
                    registrar_log(usr_act, "ELIMINAR_ARTICULO", f"Eliminación de artículo: {sel_del_art}")
                    st.warning(f"Artículo '{sel_del_art}' eliminado.")
                    st.rerun()
        else:
            st.info("Aún no hay artículos registrados en el inventario.")

    with tab_cuentas:
        st.subheader("Agregar Nueva Cuenta Contable")
        with st.form("form_nueva_cuenta", clear_on_submit=True):
            col_c1, col_c2 = st.columns([1, 3])
            codigo = col_c1.text_input("Código de Cuenta", placeholder="Ej: 1.1.03")
            nombre_cuenta = col_c2.text_input("Nombre de la Cuenta", placeholder="Ej: Valores a Depositar")

            if st.form_submit_button("Agregar Cuenta al Plan"):
                if not codigo or not nombre_cuenta:
                    st.error("El código y nombre son obligatorios.")
                else:
                    nueva_cuenta_str = f"{codigo} {nombre_cuenta}"
                    if nueva_cuenta_str not in st.session_state.plan_cuentas:
                        st.session_state.plan_cuentas.append(nueva_cuenta_str)
                        st.session_state.plan_cuentas.sort()
                        guardar_estado_db(usr_act)
                        registrar_log(usr_act, "ALTA_CUENTA", f"Nueva cuenta: {nueva_cuenta_str}")
                        st.success(f"Cuenta '{nueva_cuenta_str}' agregada.")

        st.dataframe(pd.DataFrame({"Cuentas Disponibles": st.session_state.plan_cuentas}), use_container_width=True)

        st.divider()
        col_ec1, col_ec2 = st.columns(2)
        
        with col_ec1:
            st.markdown("##### ✏️ Editar Nombre o Código de Cuenta")
            sel_edit_cta = st.selectbox("Seleccionar Cuenta a Editar", st.session_state.plan_cuentas, key="sel_edit_cta")
            idx_cta = st.session_state.plan_cuentas.index(sel_edit_cta)
            
            with st.form("form_edit_cuenta"):
                nueva_cta_val = st.text_input("Nombre / Código Modificado", value=sel_edit_cta)
                if st.form_submit_button("Guardar Cambios en Cuenta"):
                    if nueva_cta_val.strip():
                        st.session_state.plan_cuentas[idx_cta] = nueva_cta_val.strip()
                        st.session_state.plan_cuentas.sort()
                        guardar_estado_db(usr_act)
                        registrar_log(usr_act, "EDITAR_CUENTA", f"Cuenta modificada: {nueva_cta_val.strip()}")
                        st.success("Plan de cuentas actualizado.")
                        st.rerun()

        with col_ec2:
            st.markdown("##### 🗑️ Eliminar Cuenta del Plan")
            sel_del_cta = st.selectbox("Seleccionar Cuenta a Eliminar", st.session_state.plan_cuentas, key="sel_del_cta")
            if st.button("Eliminar Cuenta"):
                st.session_state.plan_cuentas.remove(sel_del_cta)
                guardar_estado_db(usr_act)
                registrar_log(usr_act, "ELIMINAR_CUENTA", f"Cuenta eliminada: {sel_del_cta}")
                st.warning(f"Cuenta '{sel_del_cta}' eliminada.")
                st.rerun()

# MÓDULO 2: LIBRO DIARIO
elif menu == "2. Carga de Asientos (Libro Diario)":
    st.header("📝 Registración de Asientos Contables")

    form_suffix = str(st.session_state["asiento_form_id"])

    lista_clientes = [t["Nombre"] for t in st.session_state.padron_terceros if t.get("Tipo") == "Cliente"]
    lista_proveedores = [t["Nombre"] for t in st.session_state.padron_terceros if t.get("Tipo") == "Proveedor"]
    lista_articulos = [a["Nombre"] for a in st.session_state.padron_articulos]

    st.subheader("📄 Datos del Comprobante y Operación")
    col_op1, col_op2, col_op3, col_op4 = st.columns([1.5, 2, 2, 2.5])
    fecha = col_op1.date_input("Fecha de operación", key=f"f_fecha_{form_suffix}")
    tipo_asiento = col_op2.selectbox("Naturaleza del Asiento", ["Normal (Operativo)", "Ajuste de Auditoría"], key=f"f_tipo_as_{form_suffix}")
    tipo_operacion = col_op3.selectbox("Tipo de Operación", ["Compra", "Venta", "Cobro", "Pago", "Ajuste Contable", "Otra Operación"], key=f"f_tipo_op_{form_suffix}")
    concepto = col_op4.text_input("Comprobante / Detalle", placeholder="Ej: Factura A N° 0001-00000123 / Faltante de Caja", key=f"f_concepto_{form_suffix}")

    tercero_operacion = "N/A"
    if tipo_operacion in ["Venta", "Cobro"]:
        if lista_clientes:
            tercero_operacion = st.selectbox("Seleccionar Cliente", ["Sin especificar"] + lista_clientes, key=f"sel_cli_{tipo_operacion}_{form_suffix}")
        else:
            st.warning("⚠️ No hay Clientes registrados en el Padrón (Módulo 1).")
            tercero_operacion = "Sin especificar"
    elif tipo_operacion in ["Compra", "Pago"]:
        if lista_proveedores:
            tercero_operacion = st.selectbox("Seleccionar Proveedor", ["Sin especificar"] + lista_proveedores, key=f"sel_prov_{tipo_operacion}_{form_suffix}")
        else:
            st.warning("⚠️ No hay Proveedores registrados en el Padrón (Módulo 1).")
            tercero_operacion = "Sin especificar"

    st.divider()
    st.subheader("📥 Imputaciones Contables Multi-Cuenta")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("##### 1️⃣ Renglones al DEBE")
        df_debe_init = pd.DataFrame([{"Cuenta": st.session_state.plan_cuentas[0] if st.session_state.plan_cuentas else "1.1.01 Caja", "Monto": 0.0}])
        edited_debe = st.data_editor(
            df_debe_init,
            num_rows="dynamic",
            column_config={
                "Cuenta": st.column_config.SelectboxColumn("Cuenta Contable", options=st.session_state.plan_cuentas, required=True),
                "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0, step=100.0, format="$%.2f", required=True)
            },
            key=f"editor_debe_{form_suffix}",
            use_container_width=True
        )

    with col_m2:
        st.markdown("##### 2️⃣ Renglones al HABER")
        df_haber_init = pd.DataFrame([{"Cuenta": st.session_state.plan_cuentas[0] if st.session_state.plan_cuentas else "1.1.01 Caja", "Monto": 0.0}])
        edited_haber = st.data_editor(
            df_haber_init,
            num_rows="dynamic",
            column_config={
                "Cuenta": st.column_config.SelectboxColumn("Cuenta Contable", options=st.session_state.plan_cuentas, required=True),
                "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0, step=100.0, format="$%.2f", required=True)
            },
            key=f"editor_haber_{form_suffix}",
            use_container_width=True
        )

    total_debe = edited_debe["Monto"].sum()
    total_haber = edited_haber["Monto"].sum()

    col_tot1, col_tot2, col_tot3 = st.columns(3)
    col_tot1.metric("Total DEBE", f"${total_debe:,.2f}")
    col_tot2.metric("Total HABER", f"${total_haber:,.2f}")
    diferencia = total_debe - total_haber
    col_tot3.metric("Diferencia Partida Doble", f"${diferencia:,.2f}", delta_color="inverse")

    st.divider()

    with st.form(f"form_confirmacion_asiento_{form_suffix}"):
        st.subheader("📦 Control de Inventario (Opcional)")
        col_st1, col_st2, col_st3, col_st4 = st.columns(4)
        mov_stock = col_st1.selectbox("Movimiento de Stock", ["Ninguno", "Entrada (Compra)", "Salida (Venta)"])
        
        if lista_articulos:
            art_stock = col_st2.selectbox("Seleccionar Artículo", lista_articulos)
        else:
            col_st2.warning("Sin artículos en inventario (Cargar en Módulo 1)")
            art_stock = None

        cant_stock = col_st3.number_input("Cantidad", min_value=0, step=1)
        pu_stock = col_st4.number_input("Precio Unitario Compra ($)", min_value=0.0, step=10.0, help="Solo para Entradas por Compra")

        submitted = st.form_submit_button("Registrar Asiento Contable")

        if submitted:
            filas_debe = edited_debe[edited_debe["Monto"] > 0].to_dict('records')
            filas_haber = edited_haber[edited_haber["Monto"] > 0].to_dict('records')

            if not filas_debe or not filas_haber:
                st.error("Error: Debe ingresar al menos un movimiento con monto positivo en el Debe y en el Haber.")
            elif abs(total_debe - total_haber) > 0.001:
                st.error(f"Error de Partida Doble: El Total Debe (${total_debe:,.2f}) no coincide con el Total Haber (${total_haber:,.2f}).")
            elif mov_stock != "Ninguno" and not art_stock:
                st.error("Error: Debe seleccionar un artículo del inventario para registrar el movimiento de stock.")
            else:
                num_asiento = len(st.session_state.libro_diario) + 1
                renglones_asiento = []

                for r in filas_debe:
                    renglones_asiento.append({"Tipo": "Debe", "Cuenta": r["Cuenta"], "Monto": float(r["Monto"])})
                for r in filas_haber:
                    renglones_asiento.append({"Tipo": "Haber", "Cuenta": r["Cuenta"], "Monto": float(r["Monto"])})

                asiento_obj = {
                    "Asiento": num_asiento,
                    "Fecha": fecha,
                    "Tipo_Asiento": tipo_asiento,
                    "Operación": tipo_operacion,
                    "Concepto": concepto,
                    "Tercero": tercero_operacion,
                    "Renglones": renglones_asiento
                }
                
                st.session_state.libro_diario.append(asiento_obj)

                # =========================================================================
                # ACTUALIZACIÓN DE SUBMAYORES (VENTA/COMPRA Y PAGO/COBRO EN EFECTIVO)
                # =========================================================================
                if tercero_operacion not in ["N/A", "Sin especificar"]:
                    if tipo_operacion == "Venta":
                        # 1. Cargo de la Venta (Debe)
                        st.session_state.submayores["Clientes"].append({
                            "Fecha": fecha, 
                            "Cliente": tercero_operacion, 
                            "Concepto": f"Venta - {concepto}",
                            "Debe (Venta/Cargo)": total_debe,
                            "Haber (Cobro/Pago)": 0.0
                        })
                        # 2. Descargo del Cobro en efectivo (Haber)
                        st.session_state.submayores["Clientes"].append({
                            "Fecha": fecha, 
                            "Cliente": tercero_operacion, 
                            "Concepto": f"Cobro en Efectivo/Contado - {concepto}",
                            "Debe (Venta/Cargo)": 0.0,
                            "Haber (Cobro/Pago)": total_debe
                        })
                    elif tipo_operacion == "Cobro":
                        st.session_state.submayores["Clientes"].append({
                            "Fecha": fecha, 
                            "Cliente": tercero_operacion, 
                            "Concepto": f"Cobro - {concepto}",
                            "Debe (Venta/Cargo)": 0.0,
                            "Haber (Cobro/Pago)": total_debe
                        })
                    elif tipo_operacion == "Compra":
                        # 1. Registro de la Compra / Deuda (Haber)
                        st.session_state.submayores["Proveedores"].append({
                            "Fecha": fecha, 
                            "Proveedor": tercero_operacion, 
                            "Concepto": f"Compra - {concepto}",
                            "Debe (Pago)": 0.0,
                            "Haber (Compra/Deuda)": total_debe
                        })
                        # 2. Registro del Pago en efectivo (Debe)
                        st.session_state.submayores["Proveedores"].append({
                            "Fecha": fecha, 
                            "Proveedor": tercero_operacion, 
                            "Concepto": f"Pago en Efectivo/Contado - {concepto}",
                            "Debe (Pago)": total_debe,
                            "Haber (Compra/Deuda)": 0.0
                        })
                    elif tipo_operacion == "Pago":
                        st.session_state.submayores["Proveedores"].append({
                            "Fecha": fecha, 
                            "Proveedor": tercero_operacion, 
                            "Concepto": f"Pago - {concepto}",
                            "Debe (Pago)": total_debe,
                            "Haber (Compra/Deuda)": 0.0
                        })

                # Manejo de Stock PPP
                if mov_stock != "Ninguno" and art_stock and cant_stock > 0:
                    historial_sf = [m for m in st.session_state.submayores["Stock_Fisico"] if m["Artículo"] == art_stock]
                    stock_f_prev = historial_sf[-1]["Stock Final"] if historial_sf else 0
                    
                    e_sf = cant_stock if mov_stock == "Entrada (Compra)" else 0
                    s_sf = cant_stock if mov_stock == "Salida (Venta)" else 0
                    stock_f_nuevo = stock_f_prev + e_sf - s_sf

                    st.session_state.submayores["Stock_Fisico"].append({
                        "Fecha": fecha, "Artículo": art_stock, "Movimiento": mov_stock,
                        "Entrada": e_sf, "Salida": s_sf, "Stock Final": stock_f_nuevo
                    })

                    fichas = st.session_state.submayores["Stock_Valorizado"]
                    if art_stock not in fichas:
                        fichas[art_stock] = []

                    historial_art = fichas[art_stock]
                    cant_saldo_prev = historial_art[-1]["Saldo Cantidad"] if historial_art else 0
                    monto_saldo_prev = historial_art[-1]["Saldo Total"] if historial_art else 0.0
                    ppp_prev = historial_art[-1]["Saldo PPP"] if historial_art else 0.0

                    if mov_stock == "Entrada (Compra)":
                        e_cant, e_pu = cant_stock, pu_stock
                        e_total = e_cant * e_pu
                        s_cant, s_pu, s_total = 0, 0.0, 0.0

                        cant_saldo_n = cant_saldo_prev + e_cant
                        monto_saldo_n = monto_saldo_prev + e_total
                        ppp_n = monto_saldo_n / cant_saldo_n if cant_saldo_n > 0 else 0.0
                    else:
                        e_cant, e_pu, e_total = 0, 0.0, 0.0
                        s_cant = cant_stock
                        s_pu = ppp_prev
                        s_total = s_cant * s_pu

                        cant_saldo_n = max(0, cant_saldo_prev - s_cant)
                        monto_saldo_n = max(0.0, monto_saldo_prev - s_total)
                        ppp_n = ppp_prev if cant_saldo_n > 0 else 0.0

                    historial_art.append({
                        "Fecha": fecha, "Concepto": concepto,
                        "E. Cant": e_cant, "E. PU": e_pu, "E. Total": e_total,
                        "S. Cant": s_cant, "S. PU": s_pu, "S. Total": s_total,
                        "Saldo Cantidad": cant_saldo_n, "Saldo PPP": ppp_n, "Saldo Total": monto_saldo_n
                    })

                guardar_estado_db(usr_act)
                registrar_log(usr_act, "NUEVO_ASIENTO", f"Asiento N° {num_asiento} registrado por total ${total_debe:,.2f}")
                st.session_state["asiento_form_id"] += 1
                st.success(f"Asiento N° {num_asiento} registrado con éxito.")
                st.rerun()

    col_tit, col_btn = st.columns([3, 1])
    col_tit.subheader("📖 Libro Diario General")
    
    if st.session_state.libro_diario:
        pdf_diario = generar_pdf_libro_diario(st.session_state.libro_diario)
        col_btn.download_button(
            label="📄 Exportar Libro Diario (PDF)",
            data=pdf_diario,
            file_name=f"Libro_Diario_{st.session_state.alumno_nombre.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

        for asito in st.session_state.libro_diario:
            with st.container():
                badge_ajuste = " 🛠️ *(Ajuste de Auditoría)*" if asito.get("Tipo_Asiento") == "Ajuste de Auditoría" else ""
                st.markdown(f"**------------------- Asiento N° {asito['Asiento']} ({asito['Fecha']}){badge_ajuste} -------------------**")
                
                for renglon in asito["Renglones"]:
                    if renglon["Tipo"] == "Debe":
                        col_c, col_d, col_h = st.columns([5, 2, 2])
                        col_c.write(f"**{renglon['Cuenta']}**")
                        col_d.write(f"${renglon['Monto']:,.2f}")
                        col_h.write("")

                for renglon in asito["Renglones"]:
                    if renglon["Tipo"] == "Haber":
                        col_c, col_d, col_h = st.columns([5, 2, 2])
                        col_c.write(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a **{renglon['Cuenta']}**", unsafe_allow_html=True)
                        col_d.write("")
                        col_h.write(f"${renglon['Monto']:,.2f}")

                tercero_str = f" | Tercero: {asito['Tercero']}" if asito['Tercero'] != "N/A" else ""
                st.caption(f"*Según: {asito['Concepto']}{tercero_str}*")
                st.divider()
    else:
        st.info("Sin asientos registrados.")

# MÓDULO 3: LIBRO MAYOR Y SUBMAYORES
elif menu == "3. Libro Mayor y Submayores":
    st.header("📊 Libro Mayor General y Submayores Auxiliares")

    tab_mayor, tab_sub_c, tab_sub_p, tab_sub_stk = st.tabs([
        "Libro Mayor General", "Submayor Clientes", "Submayor Proveedores", "Stock Físico (Unidades)"
    ])

    with tab_mayor:
        cuenta_sel = st.selectbox("Seleccionar Cuenta", st.session_state.plan_cuentas if st.session_state.plan_cuentas else ["1.1.01 Caja"])
        if st.session_state.libro_diario:
            renglones_flat = []
            for a in st.session_state.libro_diario:
                for r in a["Renglones"]:
                    if r["Cuenta"] == cuenta_sel:
                        renglones_flat.append({
                            "Asiento": a["Asiento"],
                            "Fecha": a["Fecha"],
                            "Tipo": a.get("Tipo_Asiento", "Normal (Operativo)"),
                            "Operación": a["Operación"],
                            "Concepto": a["Concepto"],
                            "Tercero": a["Tercero"],
                            "Debe": r["Monto"] if r["Tipo"] == "Debe" else 0.0,
                            "Haber": r["Monto"] if r["Tipo"] == "Haber" else 0.0
                        })

            if renglones_flat:
                df_cuenta = pd.DataFrame(renglones_flat)
                t_debe = df_cuenta["Debe"].sum()
                t_haber = df_cuenta["Haber"].sum()
                
                pdf_mayor = generar_pdf_tabla_generica(f"LIBRO MAYOR: {cuenta_sel}", df_cuenta)
                st.download_button("📄 Exportar Mayor (PDF)", pdf_mayor, f"Mayor_{cuenta_sel}.pdf", "application/pdf")
                
                st.dataframe(df_cuenta, use_container_width=True)

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Debe", f"${t_debe:,.2f}")
                c2.metric("Total Haber", f"${t_haber:,.2f}")
                c3.metric("Saldo Final", f"${t_debe - t_haber:,.2f}")
            else:
                st.info("Sin movimientos en esta cuenta.")

    with tab_sub_c:
        lista_c = list(set([m["Cliente"] for m in st.session_state.submayores.get("Clientes", [])]))
        if lista_c:
            cliente_sel = st.selectbox("Seleccionar Cliente a Visualizar", lista_c)
            movs_cli = [m for m in st.session_state.submayores["Clientes"] if m["Cliente"] == cliente_sel]
            
            df_c = pd.DataFrame(movs_cli)
            
            col_d_c = "Debe (Venta/Cargo)" if "Debe (Venta/Cargo)" in df_c.columns else "Debe (Deuda)"
            col_h_c = "Haber (Cobro/Pago)" if "Haber (Cobro/Pago)" in df_c.columns else "Haber (Pago)"

            df_c["Saldo Acumulado"] = (df_c[col_d_c].fillna(0) - df_c[col_h_c].fillna(0)).cumsum()

            tot_c_debe = df_c[col_d_c].sum()
            tot_c_haber = df_c[col_h_c].sum()
            saldo_c_final = df_c["Saldo Acumulado"].iloc[-1]

            pdf_sub_c = generar_pdf_tabla_generica(f"SUBMAYOR DE CLIENTE: {cliente_sel}", df_c)
            st.download_button("📄 Exportar Submayor Cliente (PDF)", pdf_sub_c, f"Submayor_Cliente_{cliente_sel}.pdf", "application/pdf")

            st.dataframe(df_c, use_container_width=True)

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Total Ventas / Cargos", f"${tot_c_debe:,.2f}")
            mc2.metric("Total Cobros / Pagos Recibidos", f"${tot_c_haber:,.2f}")
            mc3.metric("Saldo Pendiente del Cliente", f"${saldo_c_final:,.2f}")
        else:
            st.info("Sin registros en submayor de clientes.")

    with tab_sub_p:
        lista_p = list(set([m["Proveedor"] for m in st.session_state.submayores.get("Proveedores", [])]))
        if lista_p:
            prov_sel = st.selectbox("Seleccionar Proveedor a Visualizar", lista_p)
            movs_prov = [m for m in st.session_state.submayores["Proveedores"] if m["Proveedor"] == prov_sel]
            
            df_p = pd.DataFrame(movs_prov)

            col_d_p = "Debe (Pago)" if "Debe (Pago)" in df_p.columns else "Debe (Pago)"
            col_h_p = "Haber (Compra/Deuda)" if "Haber (Compra/Deuda)" in df_p.columns else "Haber (Deuda)"

            df_p["Saldo Acumulado"] = (df_p[col_h_p].fillna(0) - df_p[col_d_p].fillna(0)).cumsum()

            tot_p_debe = df_p[col_d_p].sum()
            tot_p_haber = df_p[col_h_p].sum()
            saldo_p_final = df_p["Saldo Acumulado"].iloc[-1]

            pdf_sub_p = generar_pdf_tabla_generica(f"SUBMAYOR DE PROVEEDOR: {prov_sel}", df_p)
            st.download_button("📄 Exportar Submayor Proveedor (PDF)", pdf_sub_p, f"Submayor_Proveedor_{prov_sel}.pdf", "application/pdf")

            st.dataframe(df_p, use_container_width=True)

            mp1, mp2, mp3 = st.columns(3)
            mp1.metric("Total Pagos Emitidos", f"${tot_p_debe:,.2f}")
            mp2.metric("Total Compras Realizadas", f"${tot_p_haber:,.2f}")
            mp3.metric("Saldo Deuda con Proveedor", f"${saldo_p_final:,.2f}")
        else:
            st.info("Sin registros en submayor de proveedores.")

    with tab_sub_stk:
        if st.session_state.submayores.get("Stock_Fisico"):
            df_sf = pd.DataFrame(st.session_state.submayores["Stock_Fisico"])
            
            tot_e_sf = df_sf["Entrada"].sum()
            tot_s_sf = df_sf["Salida"].sum()
            
            pdf_sub_stk = generar_pdf_tabla_generica("SUBMAYOR DE STOCK FISICO", df_sf)
            st.download_button("📄 Exportar Stock Físico (PDF)", pdf_sub_stk, "Stock_Fisico.pdf", "application/pdf")
            
            st.dataframe(df_sf, use_container_width=True)
            
            ms1, ms2, ms3 = st.columns(3)
            ms1.metric("Total Unidades Entrada", f"{tot_e_sf:,} u.")
            ms2.metric("Total Unidades Salida", f"{tot_s_sf:,} u.")
            ms3.metric("Existencia Física Final", f"{df_sf['Stock Final'].iloc[-1]:,} u.")
        else:
            st.info("Sin registros de movimientos físicos de stock.")

# MÓDULO 4: FICHA DE STOCK VALORIZADA (PPP)
elif menu == "4. Ficha de Stock PPP":
    st.header("📈 Ficha de Stock Valorizada - Método PPP")

    fichas = st.session_state.submayores.get("Stock_Valorizado", {})

    if fichas:
        art_sel = st.selectbox("Seleccionar Artículo", list(fichas.keys()))
        df_art = pd.DataFrame(fichas[art_sel])

        if not df_art.empty:
            df_display = df_art.copy()
            
            columnas_multinivel = pd.MultiIndex.from_tuples([
                ("Datos Operación", "Fecha"),
                ("Datos Operación", "Concepto"),
                ("ENTRADAS", "Cant."),
                ("ENTRADAS", "P. Unitario"),
                ("ENTRADAS", "Total"),
                ("SALIDAS", "Cant."),
                ("SALIDAS", "P. Unitario"),
                ("SALIDAS", "Total"),
                ("EXISTENCIAS", "Cant."),
                ("EXISTENCIAS", "$ PPP"),
                ("EXISTENCIAS", "Total Valorizado")
            ])
            
            df_display.columns = columnas_multinivel

            col_f1, col_f2 = st.columns([3, 1])
            col_f1.subheader(f"Ficha de Valuación: {art_sel}")

            pdf_ficha = generar_pdf_tabla_generica(f"FICHA DE STOCK PPP: {art_sel}", df_art, orientacion="landscape")
            col_f2.download_button("📄 Exportar Ficha (PDF)", pdf_ficha, f"Ficha_PPP_{art_sel}.pdf", "application/pdf")

            st.dataframe(
                df_display.style.format({
                    ("ENTRADAS", "Cant."): "{:,.0f}",
                    ("ENTRADAS", "P. Unitario"): "${:,.2f}",
                    ("ENTRADAS", "Total"): "${:,.2f}",
                    ("SALIDAS", "Cant."): "{:,.0f}",
                    ("SALIDAS", "P. Unitario"): "${:,.2f}",
                    ("SALIDAS", "Total"): "${:,.2f}",
                    ("EXISTENCIAS", "Cant."): "{:,.0f}",
                    ("EXISTENCIAS", "$ PPP"): "${:,.2f}",
                    ("EXISTENCIAS", "Total Valorizado"): "${:,.2f}"
                }),
                use_container_width=True
            )

            tot_e_cant = df_art["E. Cant"].sum()
            tot_e_monto = df_art["E. Total"].sum()
            tot_s_cant = df_art["S. Cant"].sum()
            tot_s_monto = df_art["S. Total"].sum()
            ultimo_reg = df_art.iloc[-1]

            st.divider()
            st.markdown("##### 📊 Resumen General de Totales del Artículo")
            
            fcol1, fcol2, fcol3, fcol4 = st.columns(4)
            fcol1.metric("Total Unidades Compradas", f"{tot_e_cant:,} u.")
            fcol2.metric("Total Inversión Compras", f"${tot_e_monto:,.2f}")
            fcol3.metric("Total Unidades Vendidas", f"{tot_s_cant:,} u.")
            fcol4.metric("Costo Total Mercadería Vendida (CMV)", f"${tot_s_monto:,.2f}")

            m1, m2, m3 = st.columns(3)
            m1.metric("Stock Actual Disponible", f"{int(ultimo_reg['Saldo Cantidad'])} u.")
            m2.metric("Precio Promedio Ponderado ($PPP)", f"${ultimo_reg['Saldo PPP']:,.2f}")
            m3.metric("Valor Total Inventario Final", f"${ultimo_reg['Saldo Total']:,.2f}")
    else:
        st.info("No hay artículos registrados con valuación de stock PPP.")

# MÓDULO 5: BALANCE DE SUMAS Y SALDOS
elif menu == "5. Sumas y Saldos":
    st.header("⚖️ Balance de Comprobación de Sumas y Saldos (Pre-Ajustes)")

    if st.session_state.libro_diario:
        resumen = []

        for cuenta in st.session_state.plan_cuentas:
            debe = 0.0
            haber = 0.0
            for a in st.session_state.libro_diario:
                if a.get("Tipo_Asiento", "Normal (Operativo)") != "Ajuste de Auditoría":
                    for r in a["Renglones"]:
                        if r["Cuenta"] == cuenta:
                            if r["Tipo"] == "Debe":
                                debe += r["Monto"]
                            else:
                                haber += r["Monto"]

            if debe > 0 or haber > 0:
                resumen.append({
                    "Cuenta": cuenta,
                    "Sumas Debe": debe,
                    "Sumas Haber": haber,
                    "Saldo Deudor": debe - haber if debe > haber else 0.0,
                    "Saldo Acreedor": haber - debe if haber > debe else 0.0
                })

        if resumen:
            df_resumen = pd.DataFrame(resumen)

            tot_s_debe = df_resumen["Sumas Debe"].sum()
            tot_s_haber = df_resumen["Sumas Haber"].sum()
            tot_sal_deu = df_resumen["Saldo Deudor"].sum()
            tot_sal_acr = df_resumen["Saldo Acreedor"].sum()

            df_resumen_tot = pd.concat([
                df_resumen,
                pd.DataFrame([{
                    "Cuenta": "TOTALES GENERALES",
                    "Sumas Debe": tot_s_debe,
                    "Sumas Haber": tot_s_haber,
                    "Saldo Deudor": tot_sal_deu,
                    "Saldo Acreedor": tot_sal_acr
                }])
            ], ignore_index=True)

            col_b1, col_b2 = st.columns([3, 1])
            col_b1.subheader("Balance General de Comprobación")

            pdf_balance = generar_pdf_tabla_generica("BALANCE DE COMPROBACION DE SUMAS Y SALDOS", df_resumen_tot)
            col_b2.download_button("📄 Exportar Balance (PDF)", pdf_balance, "Balance_Sumas_y_Saldos.pdf", "application/pdf")

            st.dataframe(
                df_resumen_tot.style.format({
                    "Sumas Debe": "${:,.2f}",
                    "Sumas Haber": "${:,.2f}",
                    "Saldo Deudor": "${:,.2f}",
                    "Saldo Acreedor": "${:,.2f}"
                }),
                use_container_width=True
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Debe", f"${tot_s_debe:,.2f}")
            c2.metric("Total Haber", f"${tot_s_haber:,.2f}")
            c3.metric("Total Deudor", f"${tot_sal_deu:,.2f}")
            c4.metric("Total Acreedor", f"${tot_sal_acr:,.2f}")
        else:
            st.info("Sin registros en operaciones ordinarias.")
    else:
        st.info("Sin asientos registrados en el Libro Diario.")

# MÓDULO 6: AUDITORÍA Y HOJA DE TRABAJO (8 COLUMNAS)
elif menu == "6. Auditoría y Prebalance (8 Columnas)":
    st.header("🔍 Módulo de Auditoría: Hoja de Trabajo / Balance de 8 Columnas")
    st.write("Visualización sistemática del proceso de ajuste contable y determinación de Saldos Ajustados.")

    if st.session_state.libro_diario:
        filas_prebalance = []

        for cuenta in st.session_state.plan_cuentas:
            s_debe = 0.0
            s_haber = 0.0
            a_debe = 0.0
            a_haber = 0.0

            for asiento in st.session_state.libro_diario:
                es_ajuste = asiento.get("Tipo_Asiento") == "Ajuste de Auditoría"
                for renglon in asiento["Renglones"]:
                    if renglon["Cuenta"] == cuenta:
                        if not es_ajuste:
                            if renglon["Tipo"] == "Debe":
                                s_debe += renglon["Monto"]
                            else:
                                s_haber += renglon["Monto"]
                        else:
                            if renglon["Tipo"] == "Debe":
                                a_debe += renglon["Monto"]
                            else:
                                a_haber += renglon["Monto"]

            if (s_debe + s_haber + a_debe + a_haber) > 0:
                saldo_orig = s_debe - s_haber
                sal_or_deudor = saldo_orig if saldo_orig > 0 else 0.0
                sal_or_acreedor = abs(saldo_orig) if saldo_orig < 0 else 0.0

                saldo_final = (s_debe + a_debe) - (s_haber + a_haber)
                sal_aj_deudor = saldo_final if saldo_final > 0 else 0.0
                sal_aj_acreedor = abs(saldo_final) if saldo_final < 0 else 0.0

                filas_prebalance.append({
                    "Cuenta": cuenta,
                    "1. Suma Debe": s_debe,
                    "2. Suma Haber": s_haber,
                    "3. Saldo Deudor": sal_or_deudor,
                    "4. Saldo Acreedor": sal_or_acreedor,
                    "5. Ajuste Debe": a_debe,
                    "6. Ajuste Haber": a_haber,
                    "7. Saldo Ajustado Deudor": sal_aj_deudor,
                    "8. Saldo Ajustado Acreedor": sal_aj_acreedor
                })

        if filas_prebalance:
            df_8col = pd.DataFrame(filas_prebalance)

            tot_s_debe = df_8col["1. Suma Debe"].sum()
            tot_s_haber = df_8col["2. Suma Haber"].sum()
            tot_sal_deu = df_8col["3. Saldo Deudor"].sum()
            tot_sal_acr = df_8col["4. Saldo Acreedor"].sum()
            tot_aj_debe = df_8col["5. Ajuste Debe"].sum()
            tot_aj_haber = df_8col["6. Ajuste Haber"].sum()
            tot_aj_sal_deu = df_8col["7. Saldo Ajustado Deudor"].sum()
            tot_aj_sal_acr = df_8col["8. Saldo Ajustado Acreedor"].sum()

            df_8col_tot = pd.concat([
                df_8col,
                pd.DataFrame([{
                    "Cuenta": "TOTALES GENERALES",
                    "1. Suma Debe": tot_s_debe,
                    "2. Suma Haber": tot_s_haber,
                    "3. Saldo Deudor": tot_sal_deu,
                    "4. Saldo Acreedor": tot_sal_acr,
                    "5. Ajuste Debe": tot_aj_debe,
                    "6. Ajuste Haber": tot_aj_haber,
                    "7. Saldo Ajustado Deudor": tot_aj_sal_deu,
                    "8. Saldo Ajustado Acreedor": tot_aj_sal_acr
                }])
            ], ignore_index=True)

            col_a1, col_a2 = st.columns([3, 1])
            col_a1.subheader("📋 Prebalance de 8 Columnas")

            pdf_8col = generar_pdf_tabla_generica("PREBALANCE DE AUDITORIA - 8 COLUMNAS", df_8col_tot, orientacion="landscape")
            col_a2.download_button("📄 Exportar Hoja 8 Col. (PDF)", pdf_8col, "Hoja_Trabajo_8_Columnas.pdf", "application/pdf")

            st.dataframe(
                df_8col_tot.style.format({
                    "1. Suma Debe": "${:,.2f}",
                    "2. Suma Haber": "${:,.2f}",
                    "3. Saldo Deudor": "${:,.2f}",
                    "4. Saldo Acreedor": "${:,.2f}",
                    "5. Ajuste Debe": "${:,.2f}",
                    "6. Ajuste Haber": "${:,.2f}",
                    "7. Saldo Ajustado Deudor": "${:,.2f}",
                    "8. Saldo Ajustado Acreedor": "${:,.2f}"
                }),
                use_container_width=True
            )

            st.divider()
            st.subheader("📊 Totales y Verificación de Cuadres")

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Sumas Originales", f"${tot_s_debe:,.2f}", delta=f"Dif: ${tot_s_debe - tot_s_haber:,.2f}")
            mc2.metric("Saldos Sin Ajuste", f"${tot_sal_deu:,.2f}", delta=f"Dif: ${tot_sal_deu - tot_sal_acr:,.2f}")
            mc3.metric("Total Ajustes", f"${tot_aj_debe:,.2f}", delta=f"Dif: ${tot_aj_debe - tot_aj_haber:,.2f}")
            mc4.metric("Saldos Ajustados", f"${tot_aj_sal_deu:,.2f}", delta=f"Dif: ${tot_aj_sal_acr:,.2f}")

        else:
            st.info("No hay movimientos contables registrados para generar la Hoja de Trabajo.")
    else:
        st.info("Sin asientos registrados en el Libro Diario.")