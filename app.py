import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
from sqlalchemy import create_engine, text
import os

# --------------------------
# CONFIG
# --------------------------
DB_FILE = "inventario.db"
ENGINE = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
st.set_page_config(page_title="Dashboard Inventario - CAASA TI", layout="wide")

# --------------------------
# DB INITIALIZATION
# --------------------------
def init_db():
    with ENGINE.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            producto TEXT UNIQUE,
            categoria TEXT,
            stock INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 1,
            proveedor TEXT,
            ultima_actualizacion TEXT
        )"""))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            producto TEXT,
            tipo TEXT,
            cantidad INTEGER,
            usuario TEXT,
            comentario TEXT
        )"""))

# Seed sample data if productos empty (optional)
def seed_sample_data():
    df = pd.read_sql("SELECT * FROM productos LIMIT 1", ENGINE)
    if df.empty:
        sample = pd.DataFrame([
            {"codigo":"A001","producto":"Codo PVC 1\"","categoria":"Plomería","stock":50,"stock_minimo":10,"proveedor":"Prov A","ultima_actualizacion":datetime.today().strftime("%Y-%m-%d")},
            {"codigo":"A002","producto":"Tornillo 1/4","categoria":"Fijación","stock":200,"stock_minimo":50,"proveedor":"Prov B","ultima_actualizacion":datetime.today().strftime("%Y-%m-%d")},
            {"codigo":"A003","producto":"Cable UTP 5m","categoria":"Redes","stock":30,"stock_minimo":5,"proveedor":"Prov C","ultima_actualizacion":datetime.today().strftime("%Y-%m-%d")},
        ])
        sample.to_sql("productos", ENGINE, if_exists="append", index=False)

# --------------------------
# UTIL: Leer tablas
# --------------------------
@st.cache_data(ttl=60)
def load_productos():
    return pd.read_sql("SELECT * FROM productos", ENGINE)

@st.cache_data(ttl=60)
def load_movimientos():
    return pd.read_sql("SELECT * FROM movimientos", ENGINE)

# --------------------------
# FUNCIONALIDAD: Registrar movimiento
# --------------------------
def registrar_movimiento(producto, tipo, cantidad, usuario="", comentario=""):
    fecha = datetime.now().strftime("%Y-%m-%d")
    with ENGINE.begin() as conn:
        # insertar movimiento
        conn.execute(text("INSERT INTO movimientos (fecha, producto, tipo, cantidad, usuario, comentario) VALUES (:f,:p,:t,:c,:u,:m)"),
                     {"f": fecha, "p": producto, "t": tipo, "c": int(cantidad), "u": usuario, "m": comentario})
        # actualizar stock
        prod = conn.execute(text("SELECT stock FROM productos WHERE producto = :p"), {"p": producto}).fetchone()
        if prod:
            stock_actual = prod[0]
            nuevo = stock_actual + cantidad if tipo == "Ingreso" else stock_actual - cantidad
            if nuevo < 0:
                raise ValueError("Resultado de stock negativo.")
            conn.execute(text("UPDATE productos SET stock = :s, ultima_actualizacion = :u WHERE producto = :p"),
                         {"s": int(nuevo), "u": fecha, "p": producto})
        else:
            # crear producto si no existe (se crea con categoría 'Sin categoría' y stock según ingreso)
            if tipo == "Ingreso":
                conn.execute(text("INSERT INTO productos (codigo, producto, categoria, stock, stock_minimo, proveedor, ultima_actualizacion) VALUES (:cod,:p,:cat,:s,:min,:prov,:u)"),
                             {"cod": "", "p": producto, "cat": "Sin categoría", "s": int(cantidad), "min": 1, "prov": "", "u": fecha})
            else:
                raise ValueError("Producto no existe; no se puede registrar salida.")

# --------------------------
# FUNCIONALIDAD: Exportar a Excel (en memoria)
# --------------------------
def export_to_excel(df_dict: dict, filename="reporte_inventario.xlsx"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        writer.save()
    processed_data = output.getvalue()
    return processed_data

# --------------------------
# INICIALIZAR DB y seed
# --------------------------
init_db()
seed_sample_data()

# --------------------------
# UI: SIDEBAR (Registrar movimientos y gestión)
# --------------------------
st.sidebar.header("Registrar movimiento")
productos_df = load_productos()
productos = list(productos_df["producto"].sort_values())

with st.sidebar.form("form_mov"):
    tipo = st.selectbox("Tipo", ["Ingreso", "Salida"])
    producto_sel = st.selectbox("Producto", options=productos) if productos else st.text_input("Producto (nuevo)")
    cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
    usuario = st.text_input("Usuario (opcional)")
    comentario = st.text_input("Comentario (opcional)")
    submitted = st.form_submit_button("Registrar")

if submitted:
    try:
        registrar_movimiento(producto_sel, tipo, int(cantidad), usuario, comentario)
        st.sidebar.success(f"{tipo} registrado: {cantidad} x {producto_sel}")
        # limpiar caches para recargar datos
        load_productos.clear()
        load_movimientos.clear()
        productos_df = load_productos()
        productos = list(productos_df["producto"].sort_values())
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("---")
st.sidebar.header("Administración")
if st.sidebar.button("Recargar datos"):
    load_productos.clear()
    load_movimientos.clear()
    st.experimental_rerun()

# --------------------------
# MAIN DASHBOARD
# --------------------------
st.title("📦 Dashboard Inventario - CAASA TI")
st.markdown("Panel profesional con histórico, alertas y exportación a Excel.")

# cargar datos actuales
productos_df = load_productos()
movimientos_df = load_movimientos()

# filtros globales
st.sidebar.header("Filtros del tablero")
fecha_min_default = pd.to_datetime(movimientos_df["fecha"]).min() if not movimientos_df.empty else pd.to_datetime("2020-01-01")
fecha_max_default = pd.to_datetime(movimientos_df["fecha"]).max() if not movimientos_df.empty else pd.to_datetime(datetime.now().date())
rango_fechas = st.sidebar.date_input("Rango de fechas (movimientos)", [fecha_min_default.date(), fecha_max_default.date()])
categoria_fil = st.sidebar.multiselect("Filtrar por categoría", options=sorted(productos_df["categoria"].dropna().unique()), default=sorted(productos_df["categoria"].dropna().unique()))
producto_fil = st.sidebar.multiselect("Filtrar por producto", options=sorted(productos_df["producto"].unique()), default=sorted(productos_df["producto"].unique()))

# Aplicar filtros a productos y movimientos
prod_display = productos_df.copy()
if categoria_fil:
    prod_display = prod_display[prod_display["categoria"].isin(categoria_fil)]
if producto_fil:
    prod_display = prod_display[prod_display["producto"].isin(producto_fil)]

# Métricas resumen
total_productos = len(prod_display)
total_unidades = int(prod_display["stock"].sum()) if not prod_display.empty else 0
bajo_stock = prod_display[prod_display["stock"] <= prod_display["stock_minimo"]]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total productos", total_productos)
col2.metric("Unidades totales", total_unidades)
col3.metric("Productos en bajo stock", len(bajo_stock))
col4.metric("Movimientos registrados", len(movimientos_df))

st.markdown("----")

# Layout: tabla y gráficos
left, right = st.columns((2,3))

with left:
    st.subheader("Inventario actual")
    st.dataframe(prod_display.reset_index(drop=True), use_container_width=True)
    st.markdown("**Productos con bajo stock**")
    if not bajo_stock.empty:
        st.dataframe(bajo_stock[["producto","categoria","stock","stock_minimo","proveedor"]].reset_index(drop=True), use_container_width=True)
    else:
        st.success("Niveles de stock OK ✅")

with right:
    st.subheader("Visualizaciones")
    # Stock por categoría
    if "categoria" in prod_display.columns and not prod_display.empty:
        fig_cat = px.bar(prod_display.groupby("categoria", as_index=False)["stock"].sum(), x="categoria", y="stock", title="Stock total por categoría")
        st.plotly_chart(fig_cat, use_container_width=True)

    # Top productos por stock
    top_n = st.slider("Top N productos (por stock)", 5, 20, 10)
    top_stock = prod_display.sort_values("stock", ascending=False).head(top_n)
    if not top_stock.empty:
        fig_top = px.bar(top_stock, x="producto", y="stock", title=f"Top {top_n} productos por stock")
        st.plotly_chart(fig_top, use_container_width=True)

st.markdown("----")

# --------------------------
# HISTÓRICO: Gráficos de movimientos
# --------------------------
st.subheader("📈 Histórico de movimientos")
if movimientos_df.empty:
    st.info("Aún no hay movimientos registrados.")
else:
    movs = movimientos_df.copy()
    movs["fecha"] = pd.to_datetime(movs["fecha"])
    # filtrar por rango y productos
    start_date, end_date = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
    mask = (movs["fecha"] >= start_date) & (movs["fecha"] <= end_date)
    if producto_fil:
        mask = mask & movs["producto"].isin(producto_fil)
    movs_filtered = movs.loc[mask]

    # selector de agregación: diario o mensual
    agg_period = st.selectbox("Periodo de agregación", ["Diario", "Semanal", "Mensual"])
    if agg_period == "Diario":
        movs_group = movs_filtered.groupby([movs_filtered["fecha"].dt.date, "tipo"])["cantidad"].sum().reset_index()
        movs_group.rename(columns={"fecha":"Fecha"}, inplace=True)
    elif agg_period == "Semanal":
        movs_filtered["week"] = movs_filtered["fecha"].dt.to_period("W").apply(lambda r: r.start_time)
        movs_group = movs_filtered.groupby(["week","tipo"])["cantidad"].sum().reset_index().rename(columns={"week":"Fecha"})
    else:
        movs_filtered["month"] = movs_filtered["fecha"].dt.to_period("M").apply(lambda r: r.start_time)
        movs_group = movs_filtered.groupby(["month","tipo"])["cantidad"].sum().reset_index().rename(columns={"month":"Fecha"})

    # gráfico de barras agrupadas por tipo
    if not movs_group.empty:
        fig_hist = px.bar(movs_group, x="Fecha", y="cantidad", color="tipo", barmode="group",
                          title=f"Evolución de movimientos ({agg_period})")
        st.plotly_chart(fig_hist, use_container_width=True)

    # gráfico de líneas acumuladas
    movs_pivot = movs_filtered.groupby(["fecha","tipo"])["cantidad"].sum().reset_index()
    movs_pivot = movs_pivot.pivot(index="fecha", columns="tipo", values="cantidad").fillna(0)
    movs_pivot["Net"] = movs_pivot.get("Ingreso", 0) - movs_pivot.get("Salida", 0)
    if not movs_pivot.empty:
        fig_line = px.line(movs_pivot.reset_index(), x="fecha", y=["Ingreso","Salida","Net"], title="Series de movimiento diario")
        st.plotly_chart(fig_line, use_container_width=True)

    # tabla resumida de movimientos
    st.markdown("**Tabla de movimientos (filtrada)**")
    st.dataframe(movs_filtered.sort_values("fecha", ascending=False).reset_index(drop=True), use_container_width=True)

st.markdown("----")

# --------------------------
# EXPORTACIÓN
# --------------------------
st.subheader("📤 Exportar datos")
if st.button("Generar y descargar Excel (Productos + Movimientos)"):
    df_prod = pd.read_sql("SELECT * FROM productos", ENGINE)
    df_mov = pd.read_sql("SELECT * FROM movimientos", ENGINE)
    excel_bytes = export_to_excel({"Productos": df_prod, "Movimientos": df_mov})
    st.success("Archivo preparado!")
    st.download_button(label="Descargar reporte_inventario.xlsx", data=excel_bytes, file_name="reporte_inventario.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --------------------------
# FOOTER / AYUDA RÁPIDA
# --------------------------
st.markdown("---")
st.markdown("Ayuda rápida: registra movimientos desde la barra lateral. Usa filtros para analizar periodos. Exporta para respaldo o informes.")
