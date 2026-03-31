"""Dashboard de demografía de España — Fuente: INE."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.maps.provinces import get_province_name, load_geojson
from src.sources.ine.demografia import (
    AGE_GROUPS,
    IDB_TABLES,
    YEAR,
    fetch_idb,
    fetch_idb_latest,
    load_demographics,
    load_historical_65,
    load_pyramid,
    load_rates,
)

CSV_DIR = Path("data/csv")

st.set_page_config(
    page_title="Demografía de España · INE",
    page_icon="👥",
    layout="wide",
)

st.markdown("""
<style>
[data-testid="stMetric"] { padding: 8px 0; }
[data-testid="stMetricLabel"] > div { font-size: 0.8rem; }
[data-testid="stMetricValue"] > div { font-size: 1.3rem; }
[data-testid="stMetricDelta"] > div { font-size: 0.7rem; }
hr { margin: 6px 0 !important; }
</style>
""", unsafe_allow_html=True)


# --- Data loading ---
@st.cache_data(show_spinner=False)
def _load_geojson():
    return load_geojson()


@st.cache_data(ttl=7200, show_spinner="Descargando pirámide de población…")
def _pyramid():
    return load_pyramid()


@st.cache_data(ttl=7200, show_spinner="Descargando indicadores…")
def _rates():
    return load_rates()


@st.cache_data(ttl=7200, show_spinner="Descargando indicadores demográficos…")
def _demographics():
    return load_demographics()


@st.cache_data(ttl=7200, show_spinner="Descargando series históricas…")
def _hist_65():
    return load_historical_65()


@st.cache_data(ttl=7200, show_spinner="Descargando mapa por provincias…")
def _demo_prov(key):
    return fetch_idb_latest(key)


@st.cache_data(show_spinner=False)
def _load_csv(key: str) -> pd.DataFrame:
    path = CSV_DIR / f"{key}_ultimo.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "cod_prov" in df.columns:
        df["cod_prov"] = df["cod_prov"].astype(str).str.zfill(2)
    return df


@st.cache_data(show_spinner=False)
def _load_csv_series(key: str) -> pd.DataFrame:
    path = CSV_DIR / f"{key}_serie.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "cod_prov" in df.columns:
        df["cod_prov"] = df["cod_prov"].astype(str).str.zfill(2)
    if "periodo" in df.columns:
        df["periodo"] = pd.to_datetime(df["periodo"])
        df["year"] = df["periodo"].dt.year
    return df


# --- Tabs ---
st.title("👥 Demografía de España")
st.caption(f"Fuente: INE · Año {YEAR}")

tab_nacional, tab_mapa, tab_informe = st.tabs(["Nacional", "Mapa por provincias", "Informe"])

geojson = _load_geojson()


# ============================================================
# TAB: Demografía nacional
# ============================================================
with tab_nacional:
    pyramid = _pyramid()
    rates, hist_rates = _rates()
    demographics = _demographics()
    hist_65 = _hist_65()

    natalidad = rates.get("natalidad", 0)
    mortalidad = rates.get("mortalidad", 0)

    total = pyramid["hombres"].sum() + pyramid["mujeres"].sum()
    young = pyramid[pyramid["grupo_edad"].isin(["0-4", "5-9", "10-14"])]
    old = pyramid[pyramid["grupo_edad"].isin(
        [g for g in AGE_GROUPS if int(g.split("-")[0].replace("+", "")) >= 65],
    )]
    pop_young = young["hombres"].sum() + young["mujeres"].sum()

    dep_val = demographics.get("dependencia", 0)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(
        "Población total", f"{total / 1e6:.2f} M",
        help="Personas residentes en España. El crecimiento poblacional depende casi exclusivamente de la inmigración, ya que el crecimiento natural (nacimientos - defunciones) es negativo desde 2015.",
    )
    m2.metric(
        "Porcentaje menores de 15", f"{pop_young / total * 100:.1f}%",
        help="Proporción de la población menor de 15 años. Indica la capacidad de renovación generacional. Por debajo del 15% se considera una población con bajo potencial de reemplazo.",
    )
    m3.metric(
        "Porcentaje mayores de 65", f"{demographics.get('pct_65', 0):.1f}%",
        help="Proporción de la población con 65 años o más. Es el indicador clave de envejecimiento. Por encima del 20% se habla de sociedad envejecida, lo que presiona el sistema de pensiones y la sanidad.",
    )
    m4.metric(
        "Edad media", f"{demographics.get('edad_media', 0):.1f} años",
        help="Edad promedio de toda la población. Refleja el equilibrio generacional. España tiene una de las edades medias más altas de Europa, señal de baja natalidad y alta esperanza de vida.",
    )
    m5.metric(
        "Tasa de dependencia", f"{dep_val:.1f}%",
        help=f"Personas en edad no laboral (menores de 16 y mayores de 65) por cada 100 en edad de trabajar (16-64). Valores de referencia: <50% = situación cómoda · 50-55% = media de la UE · 55-60% = presión notable · >60% = presión crítica. España ({dep_val:.0f}%) está en torno a la media europea.",
    )
    m6.metric(
        "Tasa de fecundidad", f"{demographics.get('fecundidad', 0):.2f}",
        help="Número medio de hijos por mujer. Se necesita un 2,1 para garantizar el reemplazo generacional. España lleva décadas por debajo, lo que conduce al envejecimiento progresivo de la población.",
    )

    col_pyramid, col_65 = st.columns(2, gap="large")

    with col_pyramid:
        fig_pyr = go.Figure()
        fig_pyr.add_trace(go.Bar(
            y=pyramid["grupo_edad"], x=-pyramid["hombres"],
            name="Hombres", orientation="h", marker_color="#4287f5",
            customdata=pyramid["hombres"],
            hovertemplate="%{y}: %{customdata:,.0f}<extra>Hombres</extra>",
        ))
        fig_pyr.add_trace(go.Bar(
            y=pyramid["grupo_edad"], x=pyramid["mujeres"],
            name="Mujeres", orientation="h", marker_color="#e84393",
            hovertemplate="%{y}: %{x:,.0f}<extra>Mujeres</extra>",
        ))
        max_val = max(pyramid["hombres"].max(), pyramid["mujeres"].max())
        tick_vals = [-max_val, -max_val / 2, 0, max_val / 2, max_val]
        tick_text = [f"{abs(v) / 1e6:.1f}M" for v in tick_vals]
        fig_pyr.update_layout(
            title={"text": "Pirámide de población", "font": {"size": 14}},
            barmode="overlay", bargap=0.05, height=300,
            xaxis={"tickvals": tick_vals, "ticktext": tick_text, "title": ""},
            yaxis={"categoryorder": "array", "categoryarray": AGE_GROUPS, "title": "", "tickfont": {"size": 9}},
            legend={"orientation": "h", "y": 1.06, "x": 0.5, "xanchor": "center"},
            margin={"r": 10, "t": 35, "l": 10, "b": 10},
        )
        st.plotly_chart(fig_pyr, use_container_width=True)

    with col_65:
        if not hist_65.empty:
            fig_65 = go.Figure(go.Scatter(
                x=hist_65["año"], y=hist_65["valor"],
                mode="lines+markers",
                marker={"color": "#e74c3c", "size": 5},
                line={"color": "#e74c3c", "width": 2},
                hovertemplate="Año %{x}: %{y:.2f}%<extra></extra>",
            ))
            fig_65.update_layout(
                title={"text": "Evolución % mayores de 65", "font": {"size": 14}},
                height=280, xaxis={"title": "", "dtick": 2}, yaxis={"title": "%"},
                margin={"r": 10, "t": 35, "l": 45, "b": 30},
            )
            st.plotly_chart(fig_65, use_container_width=True)

    if not hist_rates.empty:
        df_nat = hist_rates[hist_rates["indicador"] == "natalidad"].copy()
        df_mor = hist_rates[hist_rates["indicador"] == "mortalidad"].copy()
        df_merged = df_nat[["año", "valor"]].merge(
            df_mor[["año", "valor"]], on="año", suffixes=("_nat", "_mor"),
        )
        df_merged["crecimiento"] = df_merged["valor_nat"] - df_merged["valor_mor"]

        fig_rates = go.Figure()
        fig_rates.add_trace(go.Bar(
            x=df_merged["año"], y=df_merged["valor_nat"], name="Natalidad",
            marker_color="#27ae60",
            hovertemplate="Año %{x}: %{y:.2f} ‰<extra>Natalidad</extra>",
        ))
        fig_rates.add_trace(go.Bar(
            x=df_merged["año"], y=df_merged["valor_mor"], name="Mortalidad",
            marker_color="#e74c3c",
            hovertemplate="Año %{x}: %{y:.2f} ‰<extra>Mortalidad</extra>",
        ))
        fig_rates.add_trace(go.Scatter(
            x=df_merged["año"], y=df_merged["crecimiento"], name="Crecimiento natural",
            mode="lines+markers",
            marker={"color": "#2c3e50", "size": 5},
            line={"color": "#2c3e50", "width": 2},
            hovertemplate="Año %{x}: %{y:+.2f} ‰<extra>Crecimiento natural</extra>",
        ))
        fig_rates.add_hline(y=0, line_dash="solid", line_color="#e74c3c", line_width=1.5,
                            annotation_text="Crecimiento cero", annotation_position="bottom left",
                            annotation_font_color="#e74c3c", annotation_font_size=10)
        y_min = df_merged["crecimiento"].min() - 2
        fig_rates.update_layout(
            title={"text": "Natalidad, mortalidad y crecimiento natural", "font": {"size": 14}},
            barmode="group", height=400, xaxis={"title": "", "dtick": 2},
            yaxis={"title": "‰", "range": [y_min, 13], "zeroline": True, "zerolinewidth": 2, "zerolinecolor": "#e74c3c"},
            legend={"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
            margin={"r": 10, "t": 35, "l": 45, "b": 40},
        )
        st.plotly_chart(fig_rates, use_container_width=True)


# ============================================================
# TAB: Mapa demográfico por provincias
# ============================================================
with tab_mapa:
    indicador = st.selectbox(
        "Indicador",
        options=list(IDB_TABLES.keys()),
        format_func=lambda k: IDB_TABLES[k]["name"],
    )

    df_prov = _demo_prov(indicador)

    if not df_prov.empty:
        cod_to_name = {}
        for feat in geojson["features"]:
            cod_to_name[feat["properties"]["cod_prov"]] = feat["properties"]["name"]
        df_prov["nombre"] = df_prov["cod_prov"].map(cod_to_name)

        info = IDB_TABLES[indicador]
        fig_demo_map = px.choropleth_map(
            df_prov, geojson=geojson,
            locations="cod_prov", featureidkey="properties.cod_prov",
            color="valor", hover_name="nombre",
            hover_data={"valor": ":.2f", "cod_prov": False},
            color_continuous_scale="YlOrRd",
            labels={"valor": info["unit"] or "valor"},
            map_style="carto-positron",
            center={"lat": 40.0, "lon": -3.7}, zoom=4.5, opacity=0.8,
        )
        fig_demo_map.update_layout(
            height=600, margin={"r": 0, "t": 0, "l": 0, "b": 0},
            coloraxis_colorbar={"title": info["unit"]},
        )
        st.plotly_chart(fig_demo_map, use_container_width=True)

        # Ranking
        sorted_prov = df_prov.sort_values("valor", ascending=True)
        fig_rank = px.bar(
            sorted_prov, x="valor", y="nombre", orientation="h",
            labels={"valor": info["unit"] or "Valor", "nombre": ""},
            color="valor", color_continuous_scale="YlOrRd",
            height=max(400, len(sorted_prov) * 18),
        )
        fig_rank.update_traces(hovertemplate="%{y}: %{x:.2f}<extra></extra>")
        fig_rank.update_layout(
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
            showlegend=False, coloraxis_showscale=False, yaxis={"dtick": 1},
            xaxis={"tickformat": ".1f"},
        )
        st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.warning("No se pudieron cargar datos para este indicador.")


# ============================================================
# TAB: Informe demográfico
# ============================================================
with tab_informe:
    st.header("Demografía de España: radiografía de un país que envejece")
    st.caption("Datos del Instituto Nacional de Estadística (INE) · Último dato disponible: 2023")

    st.markdown("""
España atraviesa una transformación demográfica profunda. La combinación de una natalidad
en mínimos históricos, una esperanza de vida entre las más altas del mundo y un envejecimiento
acelerado de la población configura un escenario que ya está impactando el mercado laboral,
el sistema de pensiones y la vertebración territorial.
""")

    st.divider()

    # --- Natalidad ---
    st.subheader("Natalidad: caída sostenida durante una década")

    nat_series = _load_csv_series("natalidad")
    nat_latest = _load_csv("natalidad")

    st.markdown("""
La tasa bruta de natalidad media en España ha caído un **27,6%** en diez años,
pasando de 8,67‰ en 2014 a 6,28‰ en 2023. Es un descenso sin precedentes
que no muestra signos de revertirse.
""")

    if not nat_series.empty:
        nat_yearly = nat_series.groupby("year")["valor"].mean().reset_index()
        fig_nat = go.Figure(go.Scatter(
            x=nat_yearly["year"], y=nat_yearly["valor"],
            mode="lines+markers+text",
            text=[f"{v:.1f}" for v in nat_yearly["valor"]],
            textposition="top center", textfont={"size": 9},
            marker={"color": "#27ae60", "size": 7},
            line={"color": "#27ae60", "width": 2},
            hovertemplate="%{x}: %{y:.2f}‰<extra></extra>",
        ))
        fig_nat.update_layout(
            title="Evolución de la tasa de natalidad (media nacional)",
            height=350, xaxis={"title": "", "dtick": 1}, yaxis={"title": "‰"},
            margin={"r": 10, "t": 40, "l": 45, "b": 30},
        )
        st.plotly_chart(fig_nat, use_container_width=True)

    if not nat_latest.empty:
        st.markdown("""
Las provincias con mayor natalidad son **Melilla**, **Almería** y **Ceuta**, todas con
poblaciones jóvenes y mayor proporción de inmigración. En el extremo opuesto,
**Ourense**, **Zamora** y **León** registran tasas propias de sociedades en declive.
""")
        top5 = nat_latest.nlargest(5, "valor")
        bot5 = nat_latest.nsmallest(5, "valor")
        combined = pd.concat([top5, bot5]).sort_values("valor")
        combined["color"] = combined["valor"].apply(lambda v: "Top 5" if v >= top5["valor"].min() else "Bottom 5")
        fig_nat_bar = px.bar(
            combined, x="valor", y="provincia", orientation="h",
            color="color", color_discrete_map={"Top 5": "#27ae60", "Bottom 5": "#e74c3c"},
            labels={"valor": "‰", "provincia": "", "color": ""},
            height=350,
        )
        fig_nat_bar.update_traces(hovertemplate="%{y}: %{x:.2f}‰<extra></extra>")
        fig_nat_bar.update_layout(
            title="Top 5 y bottom 5 provincias por natalidad",
            margin={"r": 10, "t": 40, "l": 10, "b": 10},
            legend={"orientation": "h", "y": -0.1},
            xaxis={"tickformat": ".1f"},
        )
        st.plotly_chart(fig_nat_bar, use_container_width=True)

    st.divider()

    # --- Mortalidad ---
    st.subheader("Mortalidad: estable, con el pico de la pandemia")

    mor_series = _load_csv_series("mortalidad")

    st.markdown("""
La tasa de mortalidad se mantiene en torno al 10‰, con un pico notable en 2019-2020
por la pandemia de COVID-19 (que llegó a 11,93‰ de media). El mapa de mortalidad
es casi el inverso del de natalidad: las provincias más envejecidas del interior registran
las tasas más altas.
""")

    if not mor_series.empty and not nat_series.empty:
        nat_y = nat_series.groupby("year")["valor"].mean().reset_index().rename(columns={"valor": "natalidad"})
        mor_y = mor_series.groupby("year")["valor"].mean().reset_index().rename(columns={"valor": "mortalidad"})
        merged = nat_y.merge(mor_y, on="year")
        merged["crecimiento_natural"] = merged["natalidad"] - merged["mortalidad"]

        fig_gap = go.Figure()
        fig_gap.add_trace(go.Scatter(
            x=merged["year"], y=merged["natalidad"], name="Natalidad",
            fill=None, mode="lines", line={"color": "#27ae60", "width": 2},
        ))
        fig_gap.add_trace(go.Scatter(
            x=merged["year"], y=merged["mortalidad"], name="Mortalidad",
            fill="tonexty", mode="lines", line={"color": "#e74c3c", "width": 2},
            fillcolor="rgba(231, 76, 60, 0.15)",
        ))
        fig_gap.update_layout(
            title="Brecha natalidad–mortalidad (media nacional)",
            height=350, xaxis={"title": "", "dtick": 1}, yaxis={"title": "‰"},
            legend={"orientation": "h", "y": -0.1},
            margin={"r": 10, "t": 40, "l": 45, "b": 30},
        )
        st.plotly_chart(fig_gap, use_container_width=True)

        st.markdown(f"""
La brecha entre mortalidad y natalidad se ha ido ampliando. En 2023, la mortalidad media
superó a la natalidad en **{abs(merged.iloc[-1]['crecimiento_natural']):.1f} puntos por mil**.
Sin la inmigración, España estaría perdiendo población de forma acelerada.
""")

    st.divider()

    # --- Envejecimiento ---
    st.subheader("Envejecimiento: la España vaciada no es solo rural")

    pct65_series = _load_csv_series("pct_65")
    pct65_latest = _load_csv("pct_65")

    if not pct65_series.empty:
        pct65_yearly = pct65_series.groupby("year")["valor"].mean().reset_index()
        fig_65r = go.Figure(go.Bar(
            x=pct65_yearly["year"], y=pct65_yearly["valor"],
            marker_color=["#e74c3c" if v >= 22 else "#f39c12" if v >= 20 else "#3498db" for v in pct65_yearly["valor"]],
            text=[f"{v:.1f}%" for v in pct65_yearly["valor"]],
            textposition="outside", textfont={"size": 9},
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ))
        fig_65r.update_layout(
            title="Evolución del % de población ≥65 años",
            height=350, xaxis={"title": "", "dtick": 1}, yaxis={"title": "%", "range": [18, 24]},
            margin={"r": 10, "t": 40, "l": 45, "b": 30},
        )
        st.plotly_chart(fig_65r, use_container_width=True)

    st.markdown("""
En una década, España ha pasado de tener una de cada cinco personas mayor de 65
a casi **una de cada cuatro**. Pero la media nacional oculta contrastes brutales.
""")

    if not pct65_latest.empty:
        fig_map_65 = px.choropleth_map(
            pct65_latest, geojson=geojson,
            locations="cod_prov", featureidkey="properties.cod_prov",
            color="valor", hover_name="provincia",
            hover_data={"valor": ":.1f", "cod_prov": False},
            color_continuous_scale="OrRd",
            labels={"valor": "% ≥65"},
            map_style="carto-positron",
            center={"lat": 40.0, "lon": -3.7}, zoom=4.5, opacity=0.8,
        )
        fig_map_65.update_layout(
            height=500, margin={"r": 0, "t": 0, "l": 0, "b": 0},
            coloraxis_colorbar={"title": "%"},
        )
        st.plotly_chart(fig_map_65, use_container_width=True)

        col_old, col_young = st.columns(2)
        top3 = pct65_latest.nlargest(3, "valor")
        bot3 = pct65_latest.nsmallest(3, "valor")
        with col_old:
            st.markdown("**Más envejecidas**")
            for _, row in top3.iterrows():
                st.metric(row["provincia"], f"{row['valor']:.1f}%")
        with col_young:
            st.markdown("**Más jóvenes**")
            for _, row in bot3.iterrows():
                st.metric(row["provincia"], f"{row['valor']:.1f}%")

    st.divider()

    # --- Crecimiento ---
    st.subheader("Crecimiento: inmigración como motor")

    crec_latest = _load_csv("crecimiento")

    st.markdown("""
El crecimiento poblacional medio por provincia es positivo, pero el **crecimiento natural**
(nacimientos menos defunciones) es negativo en la mayoría de provincias.
Lo que sostiene el crecimiento es la **inmigración**.
""")

    if not crec_latest.empty:
        crec_sorted = crec_latest.sort_values("valor")
        crec_sorted["color"] = crec_sorted["valor"].apply(lambda v: "Crece" if v > 0 else "Decrece")
        fig_crec = px.bar(
            crec_sorted, x="valor", y="provincia", orientation="h",
            color="color", color_discrete_map={"Crece": "#3498db", "Decrece": "#e74c3c"},
            labels={"valor": "‰", "provincia": "", "color": ""},
            height=max(400, len(crec_sorted) * 16),
        )
        fig_crec.update_traces(hovertemplate="%{y}: %{x:.2f}‰<extra></extra>")
        fig_crec.update_layout(
            title="Crecimiento poblacional por provincia (‰)",
            margin={"r": 10, "t": 40, "l": 10, "b": 10},
            showlegend=True, legend={"orientation": "h", "y": -0.05},
            yaxis={"dtick": 1}, xaxis={"tickformat": ".1f"},
        )
        fig_crec.add_vline(x=0, line_dash="dot", line_color="gray")
        st.plotly_chart(fig_crec, use_container_width=True)

    st.divider()

    # --- Dependencia ---
    st.subheader("Dependencia: presión sobre la población activa")

    dep_latest = _load_csv("dependencia")

    st.markdown("""
La tasa de dependencia mide cuántas personas en edad no laboral (<16 y ≥65)
dependen de cada 100 en edad de trabajar. Una tasa alta implica mayor presión
fiscal y sobre los servicios públicos.
""")

    if not dep_latest.empty:
        dep_sorted = dep_latest.sort_values("valor", ascending=True)
        fig_dep = px.bar(
            dep_sorted, x="valor", y="provincia", orientation="h",
            color="valor", color_continuous_scale="BuPu",
            labels={"valor": "%", "provincia": ""},
            height=max(400, len(dep_sorted) * 16),
        )
        fig_dep.update_traces(hovertemplate="%{y}: %{x:.2f}%<extra></extra>")
        fig_dep.update_layout(
            title="Tasa de dependencia por provincia (%)",
            margin={"r": 10, "t": 40, "l": 10, "b": 10},
            coloraxis_showscale=False, yaxis={"dtick": 1},
            xaxis={"tickformat": ".1f"},
        )
        st.plotly_chart(fig_dep, use_container_width=True)

    st.divider()

    # --- Conclusión ---
    st.subheader("Conclusión")
    st.markdown("""
Los datos del INE dibujan un país con **dos velocidades demográficas**. Las provincias
del interior y noroeste se vacían y envejecen a un ritmo acelerado, mientras que el litoral
mediterráneo y las grandes áreas metropolitanas crecen gracias a la inmigración.

El reto demográfico de España no es un problema futuro: **ya está aquí**. La natalidad no va
a remontar a corto plazo, el envejecimiento se va a acelerar con la jubilación de los
*baby boomers* (nacidos entre 1958 y 1975), y la inmigración — el único factor que
compensa — depende de políticas y contextos internacionales cambiantes.

---
*Datos: Instituto Nacional de Estadística (INE). Procesados con Python.*
""")
