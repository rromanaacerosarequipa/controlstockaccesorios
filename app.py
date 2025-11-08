import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Stock", layout="wide")

# --- Cargar datos ---
@st.cache_data
def load_data():
    return pd.read_csv("data/stock.csv")

def save_data(df):
    df.to_csv("data/stock.csv", index=False)

df = load_data()

# --- Sidebar ---
st.sidebar.title("📦 Control de Stock")
menu = st.sidebar.radio("Seleccione una opción:", ["Ver Stock", "Registrar Ingreso", "Registrar Salida", "Reposiciones"])

# --- Ver Stock ---
if menu == "Ver Stock":
    st.title("📊 Stock Actual de Materiales")
    st.dataframe(df, use_container_width=True)
    st.bar_chart(df.set_index("Material")["Stock"])

# --- Ingreso ---
elif menu == "Registrar Ingreso":
    st.title("📥 Registrar Ingreso de Material")
    material = st.selectbox("Seleccione material:", df["Material"])
    cantidad = st.number_input("Cantidad ingresada:", min_value=1, step=1)
    if st.button("Guardar Ingreso"):
        df.loc[df["Material"] == material, "Stock"] += cantidad
        save_data(df)
        st.success(f"✅ Se agregó {cantidad} unidades de {material} al stock.")

# --- Salida ---
elif menu == "Registrar Salida":
    st.title("📤 Registrar Salida de Material")
    material = st.selectbox("Seleccione material:", df["Material"])
    cantidad = st.number_input("Cantidad salida:", min_value=1, step=1)
    stock_actual = df.loc[df["Material"] == material, "Stock"].values[0]
    if st.button("Guardar Salida"):
        if cantidad <= stock_actual:
            df.loc[df["Material"] == material, "Stock"] -= cantidad
            save_data(df)
            st.success(f"✅ Se retiraron {cantidad} unidades de {material}.")
        else:
            st.error("❌ No hay suficiente stock disponible.")

# --- Reposiciones ---
elif menu == "Reposiciones":
    st.title("🔁 Reposición Automática / Manual")
    minimo = st.number_input("Nivel mínimo de stock (alerta):", min_value=1, value=5)
    bajos = df[df["Stock"] <= minimo]
    if bajos.empty:
        st.info("✅ Todos los materiales están por encima del mínimo.")
    else:
        st.warning("⚠️ Materiales con stock bajo:")
        st.dataframe(bajos)
