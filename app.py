# Archivo: app.py
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
movs_group = movs_filtered.groupby([movs_filtered["fecha"].dt.date, "tipo"]) ["cantidad"].sum().reset_index()
movs_group.rename(columns={"fecha":"Fecha"}, inplace=True)
elif agg_period == "Semanal":
movs_filtered["week"] = movs_filtered["fecha"].dt.to_p
