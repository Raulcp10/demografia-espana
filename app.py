"""Dashboard de demografía de España — datos del INE."""

import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Demografía España", page_icon="👥", layout="wide")

# Reducir padding de las métricas
st.markdown("""
<style>
[data-testid="stMetric"] { padding: 8px 0; }
[data-testid="stMetricLabel"] > div { font-size: 0.8rem; }
[data-testid="stMetricValue"] > div { font-size: 1.3rem; }
[data-testid="stMetricDelta"] > div { font-size: 0.7rem; }
hr { margin: 6px 0 !important; }
</style>
""", unsafe_allow_html=True)

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"
YEAR = 2023  # Año de referencia (último con datos completos en todos los indicadores)

AGE_GROUPS = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
    "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+",
]


# --- Data fetching ---

@st.cache_data(ttl=7200, show_spinner="Descargando pirámide de población…")
def load_pyramid() -> pd.DataFrame:
    """National population pyramid from ECP table 56934.

    nult=2 returns 2024 and 2023; we pick the one matching YEAR.
    """
    url = f"{BASE_URL}/DATOS_TABLA/56934?nult=3"
    raw = requests.get(url, timeout=120).json()

    data = {}  # (age_group, sex) -> population

    for series in raw:
        nombre = series.get("Nombre", "")
        if "Total Nacional" not in nombre:
            continue

        parts = [p.strip() for p in nombre.split(".") if p.strip()]

        # Parse age
        age_num = None
        for part in parts:
            m = re.match(r"^(\d+)\s*años?$", part)
            if m:
                age_num = int(m.group(1))
                break
        if age_num is None:
            continue

        # Age group
        if age_num >= 100:
            group = "100+"
        else:
            bucket = (age_num // 5) * 5
            group = f"{bucket}-{bucket + 4}"

        # Sex
        sex = parts[2].strip() if len(parts) > 2 else ""
        if sex not in ("Hombres", "Mujeres"):
            continue

        # Find value for the target year (Jan 1 of YEAR+1 = end of YEAR)
        valor = None
        for dp in series.get("Data", []):
            if dp.get("Valor") is None:
                continue
            fecha = pd.Timestamp(dp["Fecha"], unit="ms")
            if fecha.year == YEAR or fecha.year == YEAR + 1:
                valor = dp["Valor"]
                break
        if valor is None:
            continue

        key = (group, sex)
        data[key] = data.get(key, 0) + valor

    rows = []
    for group in AGE_GROUPS:
        h = data.get((group, "Hombres"), 0)
        m = data.get((group, "Mujeres"), 0)
        rows.append({"grupo_edad": group, "hombres": h, "mujeres": m})

    return pd.DataFrame(rows)


@st.cache_data(ttl=7200, show_spinner="Descargando indicadores…")
def load_rates() -> tuple[dict, pd.DataFrame]:
    """Fetch national birth/death rates: current YEAR value + historical series."""
    current = {}
    series_data = {}
    for key, tid in [("natalidad", 1381), ("mortalidad", 1411)]:
        url = f"{BASE_URL}/DATOS_TABLA/{tid}?nult=20"
        raw = requests.get(url, timeout=60).json()
        for series in raw:
            if "total nacional" not in series["Nombre"].lower():
                continue
            rows = []
            for dp in series.get("Data", []):
                if dp.get("Valor") is None:
                    continue
                fecha = pd.Timestamp(dp["Fecha"], unit="ms")
                rows.append({"año": fecha.year, "valor": dp["Valor"]})
                if fecha.year == YEAR:
                    current[key] = dp["Valor"]
            series_data[key] = rows
            break

    # Build combined DataFrame
    all_rows = []
    for key, rows in series_data.items():
        for r in rows:
            all_rows.append({"año": r["año"], "indicador": key, "valor": r["valor"]})
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.drop_duplicates(["año", "indicador"]).sort_values("año")
    return current, df


@st.cache_data(ttl=7200, show_spinner="Descargando indicadores demográficos…")
def load_demographics() -> dict:
    """Fetch edad media, tasa de dependencia, tasa de fecundidad and % 65+ for YEAR."""
    result = {}
    tables = [
        ("edad_media", 3197, "Total"),
        ("dependencia", 1490, None),
        ("fecundidad", 1407, "Ambas nacionalidades"),
        ("pct_65", 48887, None),
    ]
    for key, tid, extra_match in tables:
        url = f"{BASE_URL}/DATOS_TABLA/{tid}?nult=3"
        raw = requests.get(url, timeout=60).json()
        for series in raw:
            nombre = series.get("Nombre", "")
            if "total nacional" not in nombre.lower():
                continue
            if extra_match and extra_match.lower() not in nombre.lower():
                continue
            for dp in series.get("Data", []):
                if dp.get("Valor") is None:
                    continue
                fecha = pd.Timestamp(dp["Fecha"], unit="ms")
                if fecha.year == YEAR:
                    result[key] = dp["Valor"]
                    break
            break
    return result


@st.cache_data(ttl=7200, show_spinner="Descargando series históricas…")
def load_historical() -> pd.DataFrame:
    """Fetch historical % 65+ (table 48887)."""
    url = f"{BASE_URL}/DATOS_TABLA/48887?nult=20"
    raw = requests.get(url, timeout=60).json()
    for series in raw:
        if "total nacional" not in series.get("Nombre", "").lower():
            continue
        rows = []
        for dp in series.get("Data", []):
            if dp.get("Valor") is None:
                continue
            fecha = pd.Timestamp(dp["Fecha"], unit="ms")
            rows.append({"año": fecha.year, "valor": dp["Valor"]})
        if rows:
            return pd.DataFrame(rows).sort_values("año").drop_duplicates("año")
        break
    return pd.DataFrame()



# --- Load data ---

pyramid = load_pyramid()
rates, hist_rates = load_rates()
demographics = load_demographics()
hist_65 = load_historical()

natalidad = rates.get("natalidad", 0)
mortalidad = rates.get("mortalidad", 0)
crecimiento = natalidad - mortalidad

total = pyramid["hombres"].sum() + pyramid["mujeres"].sum()
young = pyramid[pyramid["grupo_edad"].isin(["0-4", "5-9", "10-14"])]
old = pyramid[pyramid["grupo_edad"].isin([g for g in AGE_GROUPS if int(g.split("-")[0].replace("+", "")) >= 65])]
pop_young = young["hombres"].sum() + young["mujeres"].sum()
pop_old = old["hombres"].sum() + old["mujeres"].sum()

# --- UI ---

st.title("👥 Demografía de España")
st.caption(f"Fuente: INE · Año {YEAR}")

# --- Métricas superiores ---
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Población total", f"{total / 1e6:.2f} M",
          help="Personas residentes en España según la Estadística Continua de Población.")
m2.metric("% menores de 15", f"{pop_young / total * 100:.1f}%",
          help="Proporción de la población con menos de 15 años.")
m3.metric("% mayores de 65", f"{demographics.get('pct_65', 0):.1f}%",
          help="Proporción de la población con 65 años o más. Fuente: IDB del INE.")
m4.metric("Edad media", f"{demographics.get('edad_media', 0):.1f} años",
          help="Edad media de la población residente.")
m5.metric("Tasa de dependencia", f"{demographics.get('dependencia', 0):.1f}%",
          help="Ratio entre población dependiente (<16 y ≥65) y población en edad de trabajar (16-64).")
m6.metric("Tasa de fecundidad", f"{demographics.get('fecundidad', 0):.2f}",
          help="Número medio de hijos por mujer (indicador sintético de fecundidad).")

# --- Pirámide + Evolución % 65+ ---
col_pyramid, col_65 = st.columns(2, gap="large")

with col_pyramid:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=pyramid["grupo_edad"],
        x=-pyramid["hombres"],
        name="Hombres",
        orientation="h",
        marker_color="#4287f5",
        customdata=pyramid["hombres"],
        hovertemplate="%{y}: %{customdata:,.0f}<extra>Hombres</extra>",
    ))
    fig.add_trace(go.Bar(
        y=pyramid["grupo_edad"],
        x=pyramid["mujeres"],
        name="Mujeres",
        orientation="h",
        marker_color="#e84393",
        hovertemplate="%{y}: %{x:,.0f}<extra>Mujeres</extra>",
    ))

    max_val = max(pyramid["hombres"].max(), pyramid["mujeres"].max())
    tick_vals = [-max_val, -max_val / 2, 0, max_val / 2, max_val]
    tick_text = [f"{abs(v) / 1e6:.1f}M" for v in tick_vals]

    fig.update_layout(
        barmode="overlay",
        bargap=0.05,
        height=280,
        xaxis={"tickvals": tick_vals, "ticktext": tick_text, "title": ""},
        yaxis={"categoryorder": "array", "categoryarray": AGE_GROUPS, "title": "", "tickfont": {"size": 9}},
        legend={"orientation": "h", "y": 1.06, "x": 0.5, "xanchor": "center"},
        margin={"r": 10, "t": 25, "l": 10, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

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
            title={"text": "Evolución porcentaje de mayores de 65", "font": {"size": 14}},
            height=280,
            xaxis={"title": "", "dtick": 2},
            yaxis={"title": "%"},
            margin={"r": 10, "t": 35, "l": 45, "b": 30},
        )
        st.plotly_chart(fig_65, use_container_width=True)

# --- Natalidad, mortalidad y crecimiento natural ---
if not hist_rates.empty:
    df_nat = hist_rates[hist_rates["indicador"] == "natalidad"].copy()
    df_mor = hist_rates[hist_rates["indicador"] == "mortalidad"].copy()
    # Merge para calcular crecimiento natural por año
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
        barmode="group",
        height=300,
        xaxis={"title": "", "dtick": 2},
        yaxis={"title": "‰"},
        legend={"orientation": "h", "y": -0.15, "x": 0.5, "xanchor": "center"},
        margin={"r": 10, "t": 35, "l": 45, "b": 40},
    )
    st.plotly_chart(fig_rates, use_container_width=True)
