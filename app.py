# app.py
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from io import BytesIO
import plotly.express as px

# -------------------------
# Configuración de la app
# -------------------------
st.set_page_config(page_title="stockacesorios - Control de Inventarios", layout="wide")
st.title("📦 stockacesorios — Control de Inventarios")
st.markdown("Registro de ingresos, salidas, monitoreo y reportes. Exporta a Excel con un clic.")

# -------------------------
# Conexión a SQLite
# -------------------------
DB_NAME = "inventario.db"
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

# Crear tablas si no existen: productos y movimientos
c.execute("""
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT,
    producto TEXT UNIQUE,
    categoria TEXT,
    stock INTEGER DEFAULT 0,
    stock_minimo INTEGER DEFAULT 1,
    proveedor TEXT,
    ultima_actualizacion TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT,
    producto TEXT,
    tipo TEXT,
    cantidad INTEGER,
    usuario TEXT,
    comentario TEXT
)
""")
conn.commit()

# Seed opcional (solo si tabla productos está vacía)
prod_count = c.execute("SELECT COUNT(1) FROM productos").fetchone()[0]
if prod_count == 0:
    sample = [
        ("A001", "Codo PVC 1\"", "Plomería", 50, 10, "Prov A", datetime.today().strftime("%Y-%m-%d")),
        ("A002", "Tornillo 1/4", "Fijación", 200, 50, "Prov B", datetime.today().strftime("%Y-%m-%d")),
        ("A003", "Cable UTP 5m", "Redes", 30, 5, "Prov C", datetime.today().strftime("%Y-%m-%d")),
    ]
    c.executemany("INSERT OR IGNORE INTO productos (codigo, producto, categoria, stock, stock_minimo, proveedor, ultima_actualizacion) VALUES (?, ?, ?, ?, ?, ?, ?)", sample)
    conn.commit()

# -------------------------
# Utilidades
# -------------------------
def load_df(table_name: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

def export_excel_bytes(sheets: dict) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        writer.save()
    return output.getvalue()

# -------------------------
# Sidebar: registrar movimiento
# -------------------------
st.sidebar.header("➕ Registrar movimiento")
productos_df = load_df("productos")
productos_list = sorted(productos_df["producto"].tolist()) if not productos_df.empty else []

with st.sidebar.form(key="form_reg"):
    new_or_exist = st.radio("Producto", ("Existente", "Nuevo"))
    if new_or_exist == "Existente":
        producto = st.selectbox("Selecciona producto", options=productos_list)
        categoria = None
        proveedor = None
    else:
        producto = st.text_input("Nombre producto (nuevo)")
        categoria = st.text_input("Categoría")
        proveedor = st.text_input("Proveedor")
    tipo = st.selectbox("Tipo", ["Ingreso", "Salida"])
    cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
    usuario = st.text_input("Usuario (opcional)")
    comentario = st.text_input("Comentario (opcional)")
    submitted = st.form_submit_button("Registrar movimiento")

if submitted:
    fecha_now = datetime.now().strftime("%Y-%m-%d")
    # si producto nuevo y tipo salida -> error
    if not producto:
        st.sidebar.error("Ingresa el nombre del producto.")
    else:
        # insertar movimiento
        c.execute("INSERT INTO movimientos (fecha, producto, tipo, cantidad, usuario, comentario) VALUES (?, ?, ?, ?, ?, ?)",
                  (fecha_now, producto, tipo, int(cantidad), usuario or "", comentario or ""))
        # actualizar o crear producto
        prod_row = c.execute("SELECT stock FROM productos WHERE producto = ?", (producto,)).fetchone()
        if prod_row:
            stock_actual = prod_row[0]
            nuevo_stock = stock_actual + int(cantidad) if tipo == "Ingreso" else stock_actual - int(cantidad)
            if nuevo_stock < 0:
                st.sidebar.error("No hay suficiente stock para esa salida.")
                # revertir movimiento insertado
                conn.rollback()
            else:
                c.execute("UPDATE productos SET stock = ?, ultima_actualizacion = ? WHERE producto = ?", (nuevo_stock, fecha_now, producto))
                conn.commit()
                st.sidebar.success(f"{tipo} registrado: {cantidad} x {producto}")
        else:
            if tipo == "Ingreso":
                # crear producto nuevo con stock = cantidad
                c.execute("INSERT INTO productos (codigo, producto, categoria, stock, stock_minimo, proveedor, ultima_actualizacion) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          ("", producto, categoria or "Sin categoría", int(cantidad), 1, proveedor or "", fecha_now))
                conn.commit()
                st.sidebar.success(f"Producto nuevo creado y {tipo} registrado: {cantidad} x {producto}")
            else:
                st.sidebar.error("Producto no existe. No se puede registrar salida.")

    # recargar cache / dataframes
    productos_df = load_df("productos")

# -------------------------
# Main dashboard
# -------------------------
st.markdown("----")
productos_df = load_df("productos")
movimientos_df = load_df("movimientos")

# Métricas principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Productos registrados", int(productos_df.shape[0]))
col2.metric("Unidades totales", int(productos_df["stock"].sum()) if not productos_df.empty else 0)
low_stock_count = productos_df[productos_df["stock"] <= productos_df["stock_minimo"]].shape[0] if not productos_df.empty else 0
col3.metric("Productos en bajo stock", int(low_stock_count))
col4.metric("Movimientos totales", int(movimientos_df.shape[0]))

st.markdown("----")

# Filtros
st.sidebar.header("Filtros del tablero")
# Fechas para filtro
if not movimientos_df.empty:
    movimientos_df["fecha_dt"] = pd.to_datetime(movimientos_df["fecha"])
    min_date = movimientos_df["fecha_dt"].min().date()
    max_date = movimientos_df["fecha_dt"].max().date()
else:
    min_date = datetime.today().date()
    max_date = datetime.today().date()

rango = st.sidebar.date_input("Rango de fechas (movimientos)", [min_date, max_date])
categoria_sel = st.sidebar.multiselect("Filtrar por categoría", options=sorted(productos_df["categoria"].dropna().unique()) if not productos_df.empty else [])
producto_sel = st.sidebar.multiselect("Filtrar por producto", options=sorted(productos_df["producto"].unique()) if not productos_df.empty else [])

# Aplicar filtros
prod_display = productos_df.copy()
if categoria_sel:
    prod_display = prod_display[prod_display["categoria"].isin(categoria_sel)]
if producto_sel:
    prod_display = prod_display[prod_display["producto"].isin(producto_sel)]

left, right = st.columns((2,3))

with left:
    st.subheader("Inventario actual")
    st.dataframe(prod_display.reset_index(drop=True), use_container_width=True)

    st.markdown("**Productos con bajo stock**")
    low = prod_display[prod_display["stock"] <= prod_display["stock_minimo"]]
    if not low.empty:
        st.dataframe(low[["producto","categoria","stock","stock_minimo","proveedor"]].reset_index(drop=True), use_container_width=True)
    else:
        st.success("Niveles de stock adecuados ✅")

with right:
    st.subheader("Visualizaciones rápidas")
    # Stock por categoría
    if not prod_display.empty and "categoria" in prod_display.columns:
        fig_cat = px.bar(prod_display.groupby("categoria", as_index=False)["stock"].sum(), x="categoria", y="stock", title="Stock total por categoría")
        st.plotly_chart(fig_cat, use_container_width=True)

    # Top N productos por stock
    top_n = st.slider("Top N (por stock)", min_value=3, max_value=20, value=8)
    top_df = prod_display.sort_values("stock", ascending=False).head(top_n)
    if not top_df.empty:
        fig_top = px.bar(top_df, x="producto", y="stock", title=f"Top {top_n} productos por stock")
        st.plotly_chart(fig_top, use_container_width=True)

st.markdown("----")

# -------------------------
# Histórico de movimientos con gráficos
# -------------------------
st.subheader("📈 Histórico de movimientos")

if movimientos_df.empty:
    st.info("Aún no hay movimientos registrados.")
else:
    movs = movimientos_df.copy()
    movs["fecha_dt"] = pd.to_datetime(movs["fecha"])
    start_date = pd.to_datetime(rango[0])
    end_date = pd.to_datetime(rango[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    mask = (movs["fecha_dt"] >= start_date) & (movs["fecha_dt"] <= end_date)
    if producto_sel:
        mask = mask & movs["producto"].isin(producto_sel)
    movs_filtered = movs.loc[mask]

    agg = st.selectbox("Periodo de agregación", ["Diario", "Semanal", "Mensual"])
    if agg == "Diario":
        movs_group = movs_filtered.groupby([movs_filtered["fecha_dt"].dt.date, "tipo"])["cantidad"].sum().reset_index().rename(columns={"fecha_dt":"Fecha"})
    elif agg == "Semanal":
        movs_filtered["week"] = movs_filtered["fecha_dt"].dt.to_period("W").apply(lambda r: r.start_time)
        movs_group = movs_filtered.groupby(["week","tipo"])["cantidad"].sum().reset_index().rename(columns={"week":"Fecha"})
    else:
        movs_filtered["month"] = movs_filtered["fecha_dt"].dt.to_period("M").apply(lambda r: r.start_time)
        movs_group = movs_filtered.groupby(["month","tipo"])["cantidad"].sum().reset_index().rename(columns={"month":"Fecha"})

    if not movs_group.empty:
        fig_hist = px.bar(movs_group, x="Fecha", y="cantidad", color="tipo", barmode="group", title=f"Evolución de movimientos ({agg})")
        st.plotly_chart(fig_hist, use_container_width=True)

    # Series acumuladas / net
    pivot = movs_filtered.groupby([movs_filtered["fecha_dt"].dt.date, "tipo"])["cantidad"].sum().reset_index()
    pivot = pivot.pivot(index="fecha_dt", columns="tipo", values="cantidad").fillna(0)
    pivot["Net"] = pivot.get("Ingreso", 0) - pivot.get("Salida", 0)
    if not pivot.empty:
        pivot_fig = px.line(pivot.reset_index().rename(columns={"fecha_dt":"Fecha"}), x="Fecha", y=[c for c in pivot.columns if c in ["Ingreso","Salida","Net"]], title="Series diarias (Ingreso / Salida / Net)")
        st.plotly_chart(pivot_fig, use_container_width=True)

    st.markdown("**Movimientos (filtrados)**")
    st.dataframe(movs_filtered.sort_values("fecha_dt", ascending=False).reset_index(drop=True), use_container_width=True)

st.markdown("----")

# -------------------------
# Exportar (Excel)
# -------------------------
st.subheader("📤 Exportar datos")
if st.button("Generar archivo Excel (Productos + Movimientos)"):
    df_prod = load_df("productos")
    df_mov = load_df("movimientos")
    excel_bytes = export_excel_bytes({"Productos": df_prod, "Movimientos": df_mov})
    st.success("Archivo listo ✔️")
    st.download_button("⬇️ Descargar reporte_inventario.xlsx", data=excel_bytes,
                       file_name="reporte_inventario.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.caption("Hecho con ❤️ — stockacesorios. Si quieres que agregue usuarios, alertas por correo o migración a PostgreSQL, te lo configuro.")
