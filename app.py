import streamlit as st
import pandas as pd
import json
import datetime
import io

# Importaciones para generación de PDF con ReportLab
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Configuración de la página
st.set_page_config(page_title="App Educativa de Contabilidad", layout="wide")

st.title("📚 Sistema Contable Educativo con Auditoría")
st.write("Herramienta pedagógica para registración manual, gestión de padrones, valuación de inventarios por PPP y Hoja de Trabajo (8 Columnas).")

# ==========================================
# INICIALIZACIÓN DE ESTADOS (SESSION STATE)
# ==========================================

def inicializar_estados():
    if "alumno_nombre" not in st.session_state:
        st.session_state.alumno_nombre = "Alumno Demo"
    if "alumno_curso" not in st.session_state:
        st.session_state.alumno_curso = "5° Año - Contabilidad"

    if "plan_cuentas" not in st.session_state:
        st.session_state.plan_cuentas = [
            "1.1.01 Caja",
            "1.1.02 Banco Nación c/c",
            "1.2.01 Deudores por Ventas (Clientes)",
            "1.2.02 Deudores Morosos",
            "1.2.03 Deudores Incobrables",
            "1.3.01 Mercaderías (Stock)",
            "1.4.01 Muebles y Útiles",
            "1.4.02 Depreciación Acumulada Muebles y Útiles",
            "2.1.01 Proveedores",
            "2.1.02 Obligaciones a Pagar",
            "3.1.01 Capital Social",
            "4.1.01 Ventas",
            "4.2.01 Sobrante de Caja",
            "5.1.01 Costo de Mercaderías Vendidas (CMV)",
            "5.1.02 Gastos Generales",
            "5.2.01 Faltante de Caja",
            "5.2.02 Depreciación Muebles y Útiles"
        ]

    if "padron_terceros" not in st.session_state:
        st.session_state.padron_terceros = []

    if "padron_articulos" not in st.session_state:
        st.session_state.padron_articulos = []

    if "libro_diario" not in st.session_state:
        st.session_state.libro_diario = []

    if "submayores" not in st.session_state:
        st.session_state.submayores = {
            "Clientes": [],
            "Proveedores": [],
            "Stock_Fisico": [],
            "Stock_Valorizado": {}
        }
    
    if "asiento_key" not in st.session_state:
        st.session_state.asiento_key = 0

inicializar_estados()

# ==========================================
# SIDEBAR: DATOS DEL ALUMNO Y GUARDADO
# ==========================================
st.sidebar.header("🎓 Datos del Estudiante")

st.session_state.alumno_nombre = st.sidebar.text_input(
    "Nombre del Alumno", 
    value=st.session_state.alumno_nombre,
    help="Modificable en etapa de prueba."
)

st.session_state.alumno_curso = st.sidebar.text_input(
    "Curso / División / Materia", 
    value=st.session_state.alumno_curso
)

st.sidebar.divider()

st.sidebar.header("💾 Guardar / Cargar Trabajo")

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

nombre_archivo_backup = f"practica_{st.session_state.alumno_nombre.strip().replace(' ', '_')}.json"

st.sidebar.download_button(
    label="📥 Guardar Avance (Descargar .json)",
    data=json_str,
    file_name=nombre_archivo_backup,
    mime="application/json",
    help="Descargá este archivo para guardar lo que registraste."
)

archivo_cargado = st.sidebar.file_uploader("📤 Cargar Avance previo (.json)", type=["json"])

if archivo_cargado is not None:
    try:
        datos_recuperados = json.load(archivo_cargado)
        
        for renglon in datos_recuperados.get("libro_diario", []):
            if isinstance(renglon.get("Fecha"), str):
                renglon["Fecha"] = datetime.date.fromisoformat(renglon["Fecha"])
                
        for clave, movs in datos_recuperados.get("submayores", {}).items():
            if isinstance(movs, list):
                for m in movs:
                    if isinstance(m.get("Fecha"), str):
                        m["Fecha"] = datetime.date.fromisoformat(m["Fecha"])
            elif isinstance(movs, dict):
                for art, registros in movs.items():
                    for r in registros:
                        if isinstance(r.get("Fecha"), str):
                            r["Fecha"] = datetime.date.fromisoformat(r["Fecha"])

        st.session_state.alumno_nombre = datos_recuperados.get("alumno_nombre", st.session_state.alumno_nombre)
        st.session_state.alumno_curso = datos_recuperados.get("alumno_curso", st.session_state.alumno_curso)
        st.session_state.plan_cuentas = datos_recuperados.get("plan_cuentas", st.session_state.plan_cuentas)
        st.session_state.padron_terceros = datos_recuperados.get("padron_terceros", [])
        
        articulos_recuperados = datos_recuperados.get("padron_articulos", st.session_state.padron_articulos)
        st.session_state.padron_articulos = articulos_recuperados if articulos_recuperados else []
        
        st.session_state.libro_diario = datos_recuperados.get("libro_diario", [])
        st.session_state.submayores = datos_recuperados.get("submayores", st.session_state.submayores)
        
        st.sidebar.success("¡Avance cargado con éxito!")
    except Exception as e:
        st.sidebar.error("Error al leer el archivo JSON.")

st.sidebar.divider()

# ==========================================
# FUNCIONES AUXILIARES PARA GENERACIÓN DE PDF
# ==========================================

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
            Paragraph(f"<b>Curso/Materia:</b> {st.session_state.alumno_curso}", style_header_label),
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

# ==========================================
# MENÚ NAVEGACIÓN
# ==========================================
menu = st.sidebar.radio(
    "Navegación",
    [
        "1. Padrones y Plan de Cuentas",
        "2. Carga de Asientos (Libro Diario)",
        "3. Libro Mayor y Submayores",
        "4. Ficha de Stock PPP",
        "5. Sumas y Saldos",
        "6. Auditoría y Prebalance (8 Columnas)"
    ]
)

# ==========================================
# MÓDULO 1: PADRONES Y PLAN DE CUENTAS
# ==========================================
if menu == "1. Padrones y Plan de Cuentas":
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
                    st.success(f"{tipo_tercero} '{nombre}' registrado correctamente.")
                    st.rerun()

        st.subheader("📋 Padrón Registrado (Modificable)")
        if st.session_state.padron_terceros:
            df_padron = pd.DataFrame(st.session_state.padron_terceros)
            edited_padron = st.data_editor(
                df_padron,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_padron_terceros"
            )
            if st.button("💾 Guardar Cambios en Padrón"):
                st.session_state.padron_terceros = edited_padron.to_dict('records')
                st.success("Padrón de clientes y proveedores actualizado correctamente.")
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
                        st.success(f"Artículo '{nom_art}' registrado en el inventario.")
                        st.rerun()

        st.subheader("📋 Catálogo de Artículos Registrados (Modificable)")
        if st.session_state.padron_articulos:
            df_articulos = pd.DataFrame(st.session_state.padron_articulos)
            edited_articulos = st.data_editor(
                df_articulos,
                num_rows="dynamic",
                use_container_width=True,
                key="editor_padron_articulos"
            )
            if st.button("💾 Guardar Cambios en Artículos"):
                st.session_state.padron_articulos = edited_articulos.to_dict('records')
                st.success("Padrón de artículos actualizado correctamente.")
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
                        st.success(f"Cuenta '{nueva_cuenta_str}' agregada.")
                        st.rerun()

        st.subheader("📋 Plan de Cuentas Actual (Modificable)")
        df_plan = pd.DataFrame({"Cuentas Disponibles": st.session_state.plan_cuentas})
        edited_plan = st.data_editor(
            df_plan,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_plan_cuentas"
        )
        if st.button("💾 Guardar Cambios en Plan de Cuentas"):
            nuevas_cuentas = [c for c in edited_plan["Cuentas Disponibles"].tolist() if c and str(c).strip()]
            nuevas_cuentas.sort()
            st.session_state.plan_cuentas = nuevas_cuentas
            st.success("Plan de cuentas actualizado correctamente.")
            st.rerun()

# ==========================================
# MÓDULO 2: LIBRO DIARIO
# ==========================================
elif menu == "2. Carga de Asientos (Libro Diario)":
    st.header("📝 Registración de Asientos Contables")

    lista_clientes = [t["Nombre"] for t in st.session_state.padron_terceros if t.get("Tipo") == "Cliente"]
    lista_proveedores = [t["Nombre"] for t in st.session_state.padron_terceros if t.get("Tipo") == "Proveedor"]
    lista_articulos = [a["Nombre"] for a in st.session_state.padron_articulos]

    st.subheader("📄 Datos del Comprobante y Operación")
    col_op1, col_op2, col_op3, col_op4 = st.columns([1.5, 2, 2, 2.5])
    fecha = col_op1.date_input("Fecha de operación")
    tipo_asiento = col_op2.selectbox("Naturaleza del Asiento", ["Normal (Operativo)", "Ajuste de Auditoría"])
    tipo_operacion = col_op3.selectbox("Tipo de Operación", ["Compra", "Venta", "Cobro", "Pago", "Ajuste Contable", "Otra Operación"])
    concepto = col_op4.text_input("Comprobante / Detalle", placeholder="Ej: Factura A N° 0001-00000123 / Faltante de Caja")

    tercero_operacion = "N/A"
    if tipo_operacion in ["Venta", "Cobro"]:
        if lista_clientes:
            tercero_operacion = st.selectbox("Seleccionar Cliente", ["Sin especificar"] + lista_clientes, key=f"sel_cli_{tipo_operacion}")
        else:
            st.warning("⚠️ No hay Clientes registrados en el Padrón (Módulo 1).")
            tercero_operacion = "Sin especificar"
    elif tipo_operacion in ["Compra", "Pago"]:
        if lista_proveedores:
            tercero_operacion = st.selectbox("Seleccionar Proveedor", ["Sin especificar"] + lista_proveedores, key=f"sel_prov_{tipo_operacion}")
        else:
            st.warning("⚠️ No hay Proveedores registrados en el Padrón (Módulo 1).")
            tercero_operacion = "Sin especificar"

    st.divider()
    st.subheader("📥 Imputaciones Contables Multi-Cuenta")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("##### 1️⃣ Renglones al DEBE")
        df_debe_init = pd.DataFrame([{"Cuenta": st.session_state.plan_cuentas[0], "Monto": 0.0}])
        edited_debe = st.data_editor(
            df_debe_init,
            num_rows="dynamic",
            column_config={
                "Cuenta": st.column_config.SelectboxColumn("Cuenta Contable", options=st.session_state.plan_cuentas, required=True),
                "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0, step=100.0, format="$%.2f", required=True)
            },
            key=f"editor_debe_{st.session_state.asiento_key}",
            use_container_width=True
        )

    with col_m2:
        st.markdown("##### 2️⃣ Renglones al HABER")
        df_haber_init = pd.DataFrame([{"Cuenta": st.session_state.plan_cuentas[0], "Monto": 0.0}])
        edited_haber = st.data_editor(
            df_haber_init,
            num_rows="dynamic",
            column_config={
                "Cuenta": st.column_config.SelectboxColumn("Cuenta Contable", options=st.session_state.plan_cuentas, required=True),
                "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0, step=100.0, format="$%.2f", required=True)
            },
            key=f"editor_haber_{st.session_state.asiento_key}",
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

    with st.form("form_confirmacion_asiento"):
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

                # Actualización de Submayores
                if tercero_operacion not in ["N/A", "Sin especificar"]:
                    for r in renglones_asiento:
                        if tipo_operacion in ["Venta", "Cobro"] and "Clientes" in r["Cuenta"]:
                            st.session_state.submayores["Clientes"].append({
                                "Fecha": fecha, "Cliente": tercero_operacion, "Concepto": concepto,
                                "Debe (Deuda)": r["Monto"] if r["Tipo"] == "Debe" else 0.0,
                                "Haber (Pago)": r["Monto"] if r["Tipo"] == "Haber" else 0.0
                            })
                        elif tipo_operacion in ["Compra", "Pago"] and "Proveedores" in r["Cuenta"]:
                            st.session_state.submayores["Proveedores"].append({
                                "Fecha": fecha, "Proveedor": tercero_operacion, "Concepto": concepto,
                                "Debe (Pago)": r["Monto"] if r["Tipo"] == "Debe" else 0.0,
                                "Haber (Deuda)": r["Monto"] if r["Tipo"] == "Haber" else 0.0
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

                st.session_state.asiento_key += 1
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

# ==========================================
# MÓDULO 3: LIBRO MAYOR Y SUBMAYORES
# ==========================================
elif menu == "3. Libro Mayor y Submayores":
    st.header("📊 Libro Mayor General y Submayores Auxiliares")

    tab_mayor, tab_sub_c, tab_sub_p, tab_sub_stk = st.tabs([
        "Libro Mayor General", "Submayor Clientes", "Submayor Proveedores", "Stock Físico (Unidades)"
    ])

    with tab_mayor:
        cuenta_sel = st.selectbox("Seleccionar Cuenta", st.session_state.plan_cuentas)
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
                
                df_cuenta_tot = df_cuenta.copy()
                df_cuenta_tot["Fecha"] = df_cuenta_tot["Fecha"].astype(str)
                fila_tot = {col: "" for col in df_cuenta_tot.columns}
                fila_tot["Concepto"] = "TOTALES"
                fila_tot["Debe"] = t_debe
                fila_tot["Haber"] = t_haber
                df_cuenta_tot = pd.concat([df_cuenta_tot, pd.DataFrame([fila_tot])], ignore_index=True)

                pdf_mayor = generar_pdf_tabla_generica(f"LIBRO MAYOR: {cuenta_sel}", df_cuenta_tot)
                st.download_button("📄 Exportar Mayor (PDF)", pdf_mayor, f"Mayor_{cuenta_sel}.pdf", "application/pdf")
                
                st.dataframe(
                    df_cuenta_tot.style.format({
                        "Debe": "${:,.2f}",
                        "Haber": "${:,.2f}"
                    }),
                    use_container_width=True
                )

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Debe", f"${t_debe:,.2f}")
                c2.metric("Total Haber", f"${t_haber:,.2f}")
                c3.metric("Saldo", f"${t_debe - t_haber:,.2f}")
            else:
                st.info("Sin movimientos en esta cuenta.")

    with tab_sub_c:
        lista_c = list(set([m["Cliente"] for m in st.session_state.submayores["Clientes"]]))
        if lista_c:
            cliente_sel = st.selectbox("Seleccionar Cliente a Visualizar", lista_c)
            movs_cli = [m for m in st.session_state.submayores["Clientes"] if m["Cliente"] == cliente_sel]
            
            df_c = pd.DataFrame(movs_cli)
            df_c["Saldo Acumulado"] = (df_c["Debe (Deuda)"] - df_c["Haber (Pago)"]).cumsum()

            tot_d = df_c["Debe (Deuda)"].sum()
            tot_h = df_c["Haber (Pago)"].sum()
            saldo_f = df_c["Saldo Acumulado"].iloc[-1]

            df_c_tot = df_c.copy()
            df_c_tot["Fecha"] = df_c_tot["Fecha"].astype(str)
            fila_tot = {col: "" for col in df_c_tot.columns}
            fila_tot["Concepto"] = "TOTALES"
            fila_tot["Debe (Deuda)"] = tot_d
            fila_tot["Haber (Pago)"] = tot_h
            fila_tot["Saldo Acumulado"] = saldo_f
            df_c_tot = pd.concat([df_c_tot, pd.DataFrame([fila_tot])], ignore_index=True)

            pdf_sub_c = generar_pdf_tabla_generica(f"SUBMAYOR DE CLIENTE: {cliente_sel}", df_c_tot)
            st.download_button("📄 Exportar Submayor Cliente (PDF)", pdf_sub_c, f"Submayor_Cliente_{cliente_sel}.pdf", "application/pdf")

            st.dataframe(
                df_c_tot.style.format({
                    "Debe (Deuda)": "${:,.2f}",
                    "Haber (Pago)": "${:,.2f}",
                    "Saldo Acumulado": "${:,.2f}"
                }),
                use_container_width=True
            )
            st.metric("Saldo Pendiente del Cliente", f"${saldo_f:,.2f}")
        else:
            st.info("Sin registros en submayor de clientes.")

    with tab_sub_p:
        lista_p = list(set([m["Proveedor"] for m in st.session_state.submayores["Proveedores"]]))
        if lista_p:
            prov_sel = st.selectbox("Seleccionar Proveedor a Visualizar", lista_p)
            movs_prov = [m for m in st.session_state.submayores["Proveedores"] if m["Proveedor"] == prov_sel]
            
            df_p = pd.DataFrame(movs_prov)
            df_p["Saldo Acumulado"] = (df_p["Haber (Deuda)"] - df_p["Debe (Pago)"]).cumsum()

            tot_d = df_p["Debe (Pago)"].sum()
            tot_h = df_p["Haber (Deuda)"].sum()
            saldo_f = df_p["Saldo Acumulado"].iloc[-1]

            df_p_tot = df_p.copy()
            df_p_tot["Fecha"] = df_p_tot["Fecha"].astype(str)
            fila_tot = {col: "" for col in df_p_tot.columns}
            fila_tot["Concepto"] = "TOTALES"
            fila_tot["Debe (Pago)"] = tot_d
            fila_tot["Haber (Deuda)"] = tot_h
            fila_tot["Saldo Acumulado"] = saldo_f
            df_p_tot = pd.concat([df_p_tot, pd.DataFrame([fila_tot])], ignore_index=True)

            pdf_sub_p = generar_pdf_tabla_generica(f"SUBMAYOR DE PROVEEDOR: {prov_sel}", df_p_tot)
            st.download_button("📄 Exportar Submayor Proveedor (PDF)", pdf_sub_p, f"Submayor_Proveedor_{prov_sel}.pdf", "application/pdf")

            st.dataframe(
                df_p_tot.style.format({
                    "Debe (Pago)": "${:,.2f}",
                    "Haber (Deuda)": "${:,.2f}",
                    "Saldo Acumulado": "${:,.2f}"
                }),
                use_container_width=True
            )
            st.metric("Saldo Deuda con Proveedor", f"${saldo_f:,.2f}")
        else:
            st.info("Sin registros en submayor de proveedores.")

    with tab_sub_stk:
        if st.session_state.submayores["Stock_Fisico"]:
            df_sf = pd.DataFrame(st.session_state.submayores["Stock_Fisico"])
            tot_e = df_sf["Entrada"].sum()
            tot_s = df_sf["Salida"].sum()
            stk_f = df_sf["Stock Final"].iloc[-1]

            df_sf_tot = df_sf.copy()
            df_sf_tot["Fecha"] = df_sf_tot["Fecha"].astype(str)
            fila_tot = {col: "" for col in df_sf_tot.columns}
            fila_tot["Movimiento"] = "TOTALES"
            fila_tot["Entrada"] = tot_e
            fila_tot["Salida"] = tot_s
            fila_tot["Stock Final"] = stk_f
            df_sf_tot = pd.concat([df_sf_tot, pd.DataFrame([fila_tot])], ignore_index=True)

            pdf_sub_stk = generar_pdf_tabla_generica("SUBMAYOR DE STOCK FISICO", df_sf_tot)
            st.download_button("📄 Exportar Stock Físico (PDF)", pdf_sub_stk, "Stock_Fisico.pdf", "application/pdf")
            st.dataframe(df_sf_tot, use_container_width=True)
        else:
            st.info("Sin registros de movimientos físicos de stock.")

# ==========================================
# MÓDULO 4: FICHA DE STOCK VALORIZADA (PPP)
# ==========================================
elif menu == "4. Ficha de Stock PPP":
    st.header("📈 Ficha de Stock Valorizada - Método PPP")

    fichas = st.session_state.submayores["Stock_Valorizado"]

    if fichas:
        art_sel = st.selectbox("Seleccionar Artículo", list(fichas.keys()))
        df_art = pd.DataFrame(fichas[art_sel])

        if not df_art.empty:
            tot_e_cant = df_art["E. Cant"].sum()
            tot_e_monto = df_art["E. Total"].sum()
            tot_s_cant = df_art["S. Cant"].sum()
            tot_s_monto = df_art["S. Total"].sum()
            
            ult_reg = df_art.iloc[-1]
            tot_saldo_cant = ult_reg["Saldo Cantidad"]
            tot_saldo_ppp = ult_reg["Saldo PPP"]
            tot_saldo_monto = ult_reg["Saldo Total"]

            df_art_tot = df_art.copy()
            df_art_tot["Fecha"] = df_art_tot["Fecha"].astype(str)
            fila_tot = {col: "" for col in df_art_tot.columns}
            fila_tot["Concepto"] = "TOTALES"
            fila_tot["E. Cant"] = tot_e_cant
            fila_tot["E. Total"] = tot_e_monto
            fila_tot["S. Cant"] = tot_s_cant
            fila_tot["S. Total"] = tot_s_monto
            fila_tot["Saldo Cantidad"] = tot_saldo_cant
            fila_tot["Saldo PPP"] = tot_saldo_ppp
            fila_tot["Saldo Total"] = tot_saldo_monto
            df_art_tot = pd.concat([df_art_tot, pd.DataFrame([fila_tot])], ignore_index=True)

            df_display = df_art_tot.copy()
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

            pdf_ficha = generar_pdf_tabla_generica(f"FICHA DE STOCK PPP: {art_sel}", df_art_tot, orientacion="landscape")
            col_f2.download_button("📄 Exportar Ficha (PDF)", pdf_ficha, f"Ficha_PPP_{art_sel}.pdf", "application/pdf")

            st.dataframe(
                df_display.style.format({
                    ("ENTRADAS", "Cant."): lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("ENTRADAS", "P. Unitario"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("ENTRADAS", "Total"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("SALIDAS", "Cant."): lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("SALIDAS", "P. Unitario"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("SALIDAS", "Total"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("EXISTENCIAS", "Cant."): lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("EXISTENCIAS", "$ PPP"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v),
                    ("EXISTENCIAS", "Total Valorizado"): lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and v != "" else str(v)
                }),
                use_container_width=True
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Stock Actual", f"{int(tot_saldo_cant)} u.")
            m2.metric("Precio Promedio Ponderado ($PPP)", f"${tot_saldo_ppp:,.2f}")
            m3.metric("Valor Total del Inventario", f"${tot_saldo_monto:,.2f}")
    else:
        st.info("No hay artículos registrados con valuación de stock PPP.")

# ==========================================
# MÓDULO 5: BALANCE DE SUMAS Y SALDOS
# ==========================================
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

            df_resumen_tot = df_resumen.copy()
            fila_tot = {
                "Cuenta": "TOTALES",
                "Sumas Debe": tot_s_debe,
                "Sumas Haber": tot_s_haber,
                "Saldo Deudor": tot_sal_deu,
                "Saldo Acreedor": tot_sal_acr
            }
            df_resumen_tot = pd.concat([df_resumen_tot, pd.DataFrame([fila_tot])], ignore_index=True)

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

# ==========================================
# MÓDULO 6: AUDITORÍA Y HOJA DE TRABAJO (8 COLUMNAS)
# ==========================================
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

            df_8col_tot = df_8col.copy()
            fila_tot = {
                "Cuenta": "TOTALES",
                "1. Suma Debe": tot_s_debe,
                "2. Suma Haber": tot_s_haber,
                "3. Saldo Deudor": tot_sal_deu,
                "4. Saldo Acreedor": tot_sal_acr,
                "5. Ajuste Debe": tot_aj_debe,
                "6. Ajuste Haber": tot_aj_haber,
                "7. Saldo Ajustado Deudor": tot_aj_sal_deu,
                "8. Saldo Ajustado Acreedor": tot_aj_sal_acr
            }
            df_8col_tot = pd.concat([df_8col_tot, pd.DataFrame([fila_tot])], ignore_index=True)

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
            mc4.metric("Saldos Ajustados", f"${tot_aj_sal_deu:,.2f}", delta=f"Dif: ${tot_aj_sal_deu - tot_aj_sal_acr:,.2f}")

        else:
            st.info("No hay movimientos contables registrados para generar la Hoja de Trabajo.")
    else:
        st.info("Sin asientos registrados en el Libro Diario.")