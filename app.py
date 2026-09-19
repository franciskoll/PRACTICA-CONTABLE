import streamlit as st
import pandas as pd
from datetime import datetime

# =========================================================================
# CONFIGURACIÓN INICIAL DE LA PÁGINA Y ESTADOS
# =========================================================================
st.set_page_config(page_title="Sistema Contable", layout="wide")

if "asientos" not in st.session_state:
    st.session_state.asientos = []

if "submayores" not in st.session_state:
    st.session_state.submayores = {
        "Clientes": [],
        "Proveedores": []
    }

if "plan_cuentas" not in st.session_state:
    st.session_state.plan_cuentas = [
        "Caja",
        "Banco",
        "Valores a Depositar",
        "Deudores por Ventas",
        "Proveedores",
        "Obligaciones a Pagar",
        "Ventas",
        "Costo de Ventas",
        "Gastos Generales",
        "Capital"
    ]

st.title("Sistema de Gestión Contable y Submayores")

# =========================================================================
# BARRA LATERAL: NAVEGACIÓN
# =========================================================================
opcion = st.sidebar.selectbox(
    "Selecciona un Módulo",
    ["1. Plan de Cuentas", "2. Carga de Asientos", "3. Libro Diario", "4. Submayores y Vencimientos", "5. Flujo de Caja Proyectado"]
)

# =========================================================================
# MÓDULO 1: PLAN DE CUENTAS
# =========================================================================
if opcion == "1. Plan de Cuentas":
    st.header("Plan de Cuentas")
    
    nueva_cuenta = st.text_input("Agregar Nueva Cuenta")
    if st.button("Guardar Cuenta"):
        if nueva_cuenta and nueva_cuenta not in st.session_state.plan_cuentas:
            st.session_state.plan_cuentas.append(nueva_cuenta)
            st.success(f"Cuenta '{nueva_cuenta}' agregada exitosamente.")
        elif nueva_cuenta in st.session_state.plan_cuentas:
            st.warning("La cuenta ya existe en el plan de cuentas.")

    st.subheader("Cuentas Registradas")
    st.dataframe(pd.DataFrame({"Cuentas": st.session_state.plan_cuentas}), use_container_width=True)

# =========================================================================
# MÓDULO 2: CARGA DE ASIENTOS
# =========================================================================
elif opcion == "2. Carga de Asientos":
    st.header("Carga de Asientos Contables")

    with st.form("form_asiento", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.date_input("Fecha de la Operación", datetime.today())
            concepto = st.text_input("Concepto / Leyenda")
        with col2:
            tipo_operacion = st.selectbox("Tipo de Operación", ["Venta", "Compra", "Cobro", "Pago", "Otro"])
            tercero_operacion = st.text_input("Nombre de Tercero (Cliente/Proveedor)", value="N/A")
        with col3:
            estado_vencimiento = st.selectbox("Condición de Pago", ["Contado", "Pendiente"])
            fecha_vencimiento = st.date_input("Fecha de Vencimiento", datetime.today()) if estado_vencimiento == "Pendiente" else None

        st.subheader("Imputaciones Contables")
        
        # Generación dinamica de filas Debe y Haber
        col_debe, col_haber = st.columns(2)
        
        filas_debe = []
        filas_haber = []

        with col_debe:
            st.markdown("**Cuentas del DEBE (Cargos)**")
            cant_debe = st.number_input("Renglones en Debe", min_value=1, max_value=5, value=2)
            for i in range(int(cant_debe)):
                c1, c2 = st.columns([2, 1])
                cta = c1.selectbox(f"Cuenta Debe #{i+1}", st.session_state.plan_cuentas, key=f"d_cta_{i}")
                monto = c2.number_input(f"Monto Debe #{i+1}", min_value=0.0, step=100.0, key=f"d_monto_{i}")
                if monto > 0:
                    filas_debe.append({"Cuenta": cta, "Monto": monto})

        with col_haber:
            st.markdown("**Cuentas del HABER (Abonos)**")
            cant_haber = st.number_input("Renglones en Haber", min_value=1, max_value=5, value=2)
            for i in range(int(cant_haber)):
                c1, c2 = st.columns([2, 1])
                cta = c1.selectbox(f"Cuenta Haber #{i+1}", st.session_state.plan_cuentas, key=f"h_cta_{i}")
                monto = c2.number_input(f"Monto Haber #{i+1}", min_value=0.0, step=100.0, key=f"h_monto_{i}")
                if monto > 0:
                    filas_haber.append({"Cuenta": cta, "Monto": monto})

        guardar = st.form_submit_button("Registrar Asiento")

    if guardar:
        total_debe = sum(r["Monto"] for r in filas_debe)
        total_haber = sum(r["Monto"] for r in filas_haber)

        if total_debe == 0 or total_haber == 0:
            st.error("Error: Debes ingresar montos mayores a cero en al menos un renglón del Debe y Haber.")
        elif round(total_debe, 2) != round(total_haber, 2):
            st.error(f"Error de Balanceo: El Debe (${total_debe:,.2f}) no coincide con el Haber (${total_haber:,.2f}).")
        else:
            # Guardar en Libro Diario
            num_asiento = len(st.session_state.asientos) + 1
            st.session_state.asientos.append({
                "Nro": num_asiento,
                "Fecha": fecha,
                "Concepto": concepto,
                "Debe": filas_debe,
                "Haber": filas_haber,
                "Total": total_debe
            })

            # =========================================================================
            # ACTUALIZACIÓN DE SUBMAYORES CON VENCIMIENTO (LÓGICA CORREGIDA)
            # =========================================================================
            if tercero_operacion not in ["N/A", "Sin especificar", ""]:
                
                # Identificación de los montos específicos asignados a la deuda/crédito
                monto_credito_cliente = sum(r["Monto"] for r in filas_debe if "deudores" in r["Cuenta"].lower())
                monto_cobro_efectivo = sum(r["Monto"] for r in filas_haber if any(c in r["Cuenta"].lower() for c in ["caja", "banco", "valores"]))
                
                monto_deuda_proveedor = sum(r["Monto"] for r in filas_haber if any(c in r["Cuenta"].lower() for c in ["proveedores", "obligaciones"]))
                monto_pago_efectivo = sum(r["Monto"] for r in filas_debe if any(c in r["Cuenta"].lower() for c in ["caja", "banco", "valores"]))

                # Operaciones de Clientes
                if tipo_operacion == "Venta":
                    if estado_vencimiento == "Pendiente":
                        monto_pendiente = monto_credito_cliente if monto_credito_cliente > 0 else total_debe
                        
                        st.session_state.submayores["Clientes"].append({
                            "Fecha": fecha, 
                            "Fecha_Vencimiento": fecha_vencimiento if fecha_vencimiento else fecha,
                            "Cliente": tercero_operacion, 
                            "Concepto": f"Venta a Crédito - {concepto}",
                            "Debe (Venta/Cargo)": monto_pendiente,
                            "Haber (Cobro/Pago)": 0.0,
                            "Estado": "Pendiente"
                        })
                        
                        if monto_cobro_efectivo > 0:
                            st.session_state.submayores["Clientes"].append({
                                "Fecha": fecha, 
                                "Fecha_Vencimiento": fecha,
                                "Cliente": tercero_operacion, 
                                "Concepto": f"Anticipo/Cobro Contado - {concepto}",
                                "Debe (Venta/Cargo)": monto_cobro_efectivo,
                                "Haber (Cobro/Pago)": monto_cobro_efectivo,
                                "Estado": "Cobrado"
                            })
                    else:
                        st.session_state.submayores["Clientes"].append({
                            "Fecha": fecha, 
                            "Fecha_Vencimiento": fecha,
                            "Cliente": tercero_operacion, 
                            "Concepto": f"Venta Contado - {concepto}",
                            "Debe (Venta/Cargo)": total_debe,
                            "Haber (Cobro/Pago)": total_debe,
                            "Estado": "Cobrado"
                        })

                elif tipo_operacion == "Cobro":
                    st.session_state.submayores["Clientes"].append({
                        "Fecha": fecha, 
                        "Fecha_Vencimiento": fecha,
                        "Cliente": tercero_operacion, 
                        "Concepto": f"Cobro - {concepto}",
                        "Debe (Venta/Cargo)": 0.0,
                        "Haber (Cobro/Pago)": total_debe,
                        "Estado": "Cobrado"
                    })

                # Operaciones de Proveedores
                elif tipo_operacion == "Compra":
                    if estado_vencimiento == "Pendiente":
                        monto_pendiente = monto_deuda_proveedor if monto_deuda_proveedor > 0 else total_debe
                        
                        st.session_state.submayores["Proveedores"].append({
                            "Fecha": fecha, 
                            "Fecha_Vencimiento": fecha_vencimiento if fecha_vencimiento else fecha,
                            "Proveedor": tercero_operacion, 
                            "Concepto": f"Compra a Crédito - {concepto}",
                            "Debe (Pago)": 0.0,
                            "Haber (Compra/Deuda)": monto_pendiente,
                            "Estado": "Pendiente"
                        })
                        
                        if monto_pago_efectivo > 0:
                            st.session_state.submayores["Proveedores"].append({
                                "Fecha": fecha, 
                                "Fecha_Vencimiento": fecha,
                                "Proveedor": tercero_operacion, 
                                "Concepto": f"Pago Parcial Contado - {concepto}",
                                "Debe (Pago)": monto_pago_efectivo,
                                "Haber (Compra/Deuda)": monto_pago_efectivo,
                                "Estado": "Pagado"
                            })
                    else:
                        st.session_state.submayores["Proveedores"].append({
                            "Fecha": fecha, 
                            "Fecha_Vencimiento": fecha,
                            "Proveedor": tercero_operacion, 
                            "Concepto": f"Compra Contado - {concepto}",
                            "Debe (Pago)": total_debe,
                            "Haber (Compra/Deuda)": total_debe,
                            "Estado": "Pagado"
                        })

                elif tipo_operacion == "Pago":
                    st.session_state.submayores["Proveedores"].append({
                        "Fecha": fecha, 
                        "Fecha_Vencimiento": fecha,
                        "Proveedor": tercero_operacion, 
                        "Concepto": f"Pago - {concepto}",
                        "Debe (Pago)": total_debe,
                        "Haber (Compra/Deuda)": 0.0,
                        "Estado": "Pagado"
                    })

            st.success(f"Asiento #{num_asiento} registrado con éxito.")

# =========================================================================
# MÓDULO 3: LIBRO DIARIO
# =========================================================================
elif opcion == "3. Libro Diario":
    st.header("Libro Diario General")
    
    if not st.session_state.asientos:
        st.info("No se han registrado asientos contables.")
    else:
        for a in st.session_state.asientos:
            with st.expander(f"Asiento N° {a['Nro']} | Fecha: {a['Fecha']} | Concepto: {a['Concepto']}"):
                df_debe = pd.DataFrame(a["Debe"])
                df_haber = pd.DataFrame(a["Haber"])
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**DEBE**")
                    st.table(df_debe)
                with c2:
                    st.write("**HABER**")
                    st.table(df_haber)
                st.write(f"**Total Balanceado:** ${a['Total']:,.2f}")

# =========================================================================
# MÓDULO 4: SUBMAYORES Y VENCIMIENTOS
# =========================================================================
elif opcion == "4. Submayores y Vencimientos":
    st.header("Gestión de Submayores y Control de Vencimientos")
    
    sub_tab1, sub_tab2 = st.tabs(["Cuentas por Cobrar (Clientes)", "Cuentas por Pagar (Proveedores)"])
    
    with sub_tab1:
        st.subheader("Submayor de Clientes")
        if st.session_state.submayores["Clientes"]:
            df_cli = pd.DataFrame(st.session_state.submayores["Clientes"])
            st.dataframe(df_cli, use_container_width=True)
        else:
            st.info("No hay datos cargados en el submayor de clientes.")
            
    with sub_tab2:
        st.subheader("Submayor de Proveedores")
        if st.session_state.submayores["Proveedores"]:
            df_prov = pd.DataFrame(st.session_state.submayores["Proveedores"])
            st.dataframe(df_prov, use_container_width=True)
        else:
            st.info("No hay datos cargados en el submayor de proveedores.")

# =========================================================================
# MÓDULO 5: FLUJO DE CAJA PROYECTADO
# =========================================================================
elif opcion == "5. Flujo de Caja Proyectado":
    st.header("Proyección de Flujo de Caja por Vencimientos")

    cli_pendientes = [x for x in st.session_state.submayores["Clientes"] if x.get("Estado") == "Pendiente"]
    prov_pendientes = [x for x in st.session_state.submayores["Proveedores"] if x.get("Estado") == "Pendiente"]

    if not cli_pendientes and not prov_pendientes:
        st.info("No existen operaciones pendientes para calcular la proyección.")
    else:
        flujo = []
        for c in cli_pendientes:
            flujo.append({
                "Fecha_Vencimiento": c["Fecha_Vencimiento"],
                "Tipo": "Ingreso (Cobro Pendiente)",
                "Tercero": c["Cliente"],
                "Monto": c["Debe (Venta/Cargo)"]
            })
        for p in prov_pendientes:
            flujo.append({
                "Fecha_Vencimiento": p["Fecha_Vencimiento"],
                "Tipo": "Egreso (Pago Pendiente)",
                "Tercero": p["Proveedor"],
                "Monto": -p["Haber (Compra/Deuda)"]
            })

        df_flujo = pd.DataFrame(flujo)
        df_flujo = df_flujo.sort_values(by="Fecha_Vencimiento")
        
        st.dataframe(df_flujo, use_container_width=True)
        
        balance_proyectado = df_flujo["Monto"].sum()
        if balance_proyectado >= 0:
            st.metric("Balance Proyectado", f"${balance_proyectado:,.2f}")
        else:
            st.metric("Balance Proyectado", f"${balance_proyectado:,.2f}", delta_color="inverse")