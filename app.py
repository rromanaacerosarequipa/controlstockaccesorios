import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.express as px

# ==============================
# Configuración de la app
# ==============================
st.set_page_config(page_title="Control de Stock de Accesorios", layout="wide")
st.title("📦 Control de Stock de Accesorios")

# ==============================
# Conexión a la base de datos SQLite
# ==============================
conn = sqlite3.connect("stock_accesorios.db", check_same_thread=False)
c = conn.cursor()

# Crear tabla si no existe
c.execute('''CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                producto TEXT,
                categoria TEXT,
                tipo_movimiento TEXT,
                cantidad INTEGER
            )''')
conn.commit()

# ==============================
# Sección: Registro de movimientos
# ==============================
st.sidebar.header("➕ Registrar Movimiento")

producto = st.sidebar.text_input("Nombre del producto:")
categoria = st.sidebar.text_input("Categoría:")
tipo_movimiento = st.sidebar.selectbox("Tipo de movimiento:", ["Ingreso", "Salida", "Reposición"])
cantidad = st.sidebar.number_input("Cantidad:", min_value=1, step=1)
fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if st.sidebar.button("Registrar"):
    if producto and categoria:
        c.execute("INSERT INTO stock (fecha, producto, categoria, tipo_movimiento, cantidad) VALUES (?, ?, ?, ?, ?)",
                  (fecha, producto, categoria, tipo_movimiento, cantidad))
        conn.commit()
        st.sidebar.success("✅ Movimiento registrado correctamente.")
    else:
        st.sidebar.error("⚠️ Debes completar todos los campos.")

# ==============================
# Sección: Visualización de datos
# ==============================
st.subheader("📋 Historial de Movimientos")

df = pd.read_sql("SELECT * FROM stock", conn)

if not df.empty:
    categoria_fil = st.multiselect("Filtrar por categoría:", options=df["categoria"].unique())

    prod_display = df.copy()
    if categoria_fil:
        prod_display = prod_display[prod_display["categoria"].isin(categoria_fil)]

    st.dataframe(prod_display, use_container_width=True)

    # ==============================
    # Gráfico histórico
    # ==============================
    st.subheader("📈 Gráfico Histórico de Movimientos")

    df_grouped = df.groupby(["fecha", "tipo_movimiento"])["cantidad"].sum().reset_index()
    fig = px.line(df_grouped, x="fecha", y="cantidad", color="tipo_movimiento",
                  title="Tendencia de movimientos en el tiempo")
    st.plotly_chart(fig, use_container_width=True)

    # ==============================
    # Exportar a Excel
    # ==============================
    st.subheader("📤 Exportar datos")
    output = df.to_excel("export_stock.xlsx", index=False)
    with open("export_stock.xlsx", "rb") as f:
        st.download_button("⬇️ Descargar Excel", f, file_name="stock_accesorios.xlsx")
else:
    st.info("No hay datos registrados aún.")

conn.close()
