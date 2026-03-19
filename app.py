"""Dashboard de demografía de España — Fuente: INE."""

from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.maps.provinces import load_geojson
from src.sources.ine.demografia import (
    AGE_GROUPS,
    IDB_TABLES,
    YEAR,
    fetch_idb_latest,
    load_demographics,
    load_historical_65,
    load_pyramid,
    load_rates,
)

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

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Población total", f"{total / 1e6:.2f} M")
    m2.metric("% menores de 15", f"{pop_young / total * 100:.1f}%")
    m3.metric("% mayores de 65", f"{demographics.get('pct_65', 0):.1f}%")
    m4.metric("Edad media", f"{demographics.get('edad_media', 0):.1f} años")
    m5.metric("Tasa de dependencia", f"{demographics.get('dependencia', 0):.1f}%")
    m6.metric("Tasa de fecundidad", f"{demographics.get('fecundidad', 0):.2f}")

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
            barmode="overlay", bargap=0.05, height=280,
            xaxis={"tickvals": tick_vals, "ticktext": tick_text, "title": ""},
            yaxis={"categoryorder": "array", "categoryarray": AGE_GROUPS, "title": "", "tickfont": {"size": 9}},
            legend={"orientation": "h", "y": 1.06, "x": 0.5, "xanchor": "center"},
            margin={"r": 10, "t": 25, "l": 10, "b": 10},
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
        fig_rates.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        fig_rates.update_layout(
            title={"text": "Natalidad, mortalidad y crecimiento natural", "font": {"size": 14}},
            barmode="group", height=300, xaxis={"title": "", "dtick": 2}, yaxis={"title": "‰"},
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
        fig_rank.update_layout(
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
            showlegend=False, coloraxis_showscale=False, yaxis={"dtick": 1},
        )
        st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.warning("No se pudieron cargar datos para este indicador.")


# ============================================================
# TAB: Informe demográfico
# ============================================================
with tab_informe:
    informe_path = Path("reports/informe_demografico.md")
    if informe_path.exists():
        st.markdown(informe_path.read_text())
    else:
        st.info("No se encontró el informe. Comprueba que existe `reports/informe_demografico.md`.")
