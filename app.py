"""Mapas interactivos de España con datos de vivienda del INE."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ine import TABLES, get_latest_data, get_timeseries
from src.provinces import get_province_name, load_geojson

st.set_page_config(
    page_title="Mapas INE · Vivienda",
    page_icon="🏠",
    layout="wide",
)

# --- Constants ---
UNITS = {
    "ipv": "Índice (base 2015=100)",
    "compraventas": "Nº compraventas",
    "hipotecas": "Nº hipotecas",
    "viviendas_turisticas": "Nº viv. turísticas",
    "alquiler": "Índice (base 2015=100)",
    "inmigracion": "Nº inmigrantes",
}

COLOR_SCALES = {
    "ipv": "YlOrRd",
    "compraventas": "Blues",
    "hipotecas": "Purples",
    "viviendas_turisticas": "Oranges",
    "alquiler": "RdYlGn_r",
    "inmigracion": "Teal",
}

ALL_DATASETS = list(TABLES.keys()) + ["inmigracion"]
DATASET_NAMES = {k: TABLES[k]["name"] for k in TABLES}
DATASET_NAMES["inmigracion"] = "Inmigración desde el extranjero"

CSV_DIR = Path("data/csv")


# --- Data loading ---
@st.cache_data(ttl=3600, show_spinner="Descargando datos del INE…")
def _load_latest(table_key: str):
    if table_key == "inmigracion":
        return _load_csv_latest("inmigracion")
    return get_latest_data(table_key)


@st.cache_data(ttl=3600, show_spinner="Descargando serie temporal…")
def _load_timeseries(table_key: str, n: int):
    if table_key == "inmigracion":
        return _load_csv_series("inmigracion")
    return get_timeseries(table_key, nult=n)


@st.cache_data(show_spinner=False)
def _load_geojson():
    return load_geojson()


@st.cache_data(show_spinner=False)
def _load_csv_latest(key: str) -> pd.DataFrame:
    path = CSV_DIR / f"{key}_ultimo.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "periodo" in df.columns:
        df["periodo"] = pd.to_datetime(df["periodo"])
    return df


@st.cache_data(show_spinner=False)
def _load_csv_series(key: str) -> pd.DataFrame:
    path = CSV_DIR / f"{key}_serie.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "periodo" in df.columns:
        df["periodo"] = pd.to_datetime(df["periodo"])
    return df


@st.cache_data(show_spinner="Cargando todos los indicadores…")
def _load_all_latest() -> dict[str, pd.DataFrame]:
    """Load latest data for all datasets."""
    result = {}
    for key in ALL_DATASETS:
        df = _load_csv_latest(key)
        if df.empty and key in TABLES:
            df = get_latest_data(key)
        if not df.empty:
            if "provincia" not in df.columns:
                df["provincia"] = df["cod_prov"].map(get_province_name)
            result[key] = df
    return result


@st.cache_data(show_spinner="Cargando series temporales…")
def _load_all_timeseries() -> dict[str, pd.DataFrame]:
    """Load time series for all datasets from CSV."""
    result = {}
    for key in ALL_DATASETS:
        df = _load_csv_series(key)
        if not df.empty:
            if "provincia" not in df.columns:
                df["provincia"] = df["cod_prov"].map(get_province_name)
            result[key] = df
    return result


def _add_province_names(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty and "provincia" not in df.columns:
        df["provincia"] = df["cod_prov"].map(get_province_name)
    return df


# --- Tabs ---
st.title("🏠 Vivienda en España")
st.caption("Datos del Instituto Nacional de Estadística (INE)")

tab_map, tab_dashboard, tab_cross = st.tabs([
    "🗺️ Explorador de mapas",
    "📊 Dashboard comparativo",
    "🔀 Cruce de indicadores",
])

geojson = _load_geojson()


# ============================================================
# TAB 1: Explorador de mapas (existing functionality)
# ============================================================
with tab_map:
    col_controls, col_empty = st.columns([1, 3])
    with col_controls:
        dataset = st.selectbox(
            "Indicador",
            options=ALL_DATASETS,
            format_func=lambda k: DATASET_NAMES.get(k, k),
        )
        nult = st.slider(
            "Períodos históricos",
            min_value=1, max_value=40, value=12,
        )

    latest = _load_latest(dataset)
    if latest.empty:
        st.error("No se encontraron datos para este indicador.")
        st.stop()

    latest = _add_province_names(latest)
    unit_label = UNITS.get(dataset, "Valor")
    color_scale = COLOR_SCALES.get(dataset, "Viridis")

    # Choropleth
    st.subheader(f"{DATASET_NAMES.get(dataset, dataset)} por provincia")
    if "periodo" in latest.columns and latest["periodo"].notna().any():
        st.caption(f"Último dato: {latest['periodo'].max().strftime('%B %Y')}")

    fig = px.choropleth_map(
        latest, geojson=geojson,
        locations="cod_prov", featureidkey="properties.cod_prov",
        color="valor", hover_name="provincia",
        hover_data={"cod_prov": False, "valor": ":.1f"},
        color_continuous_scale=color_scale,
        labels={"valor": unit_label},
        map_style="carto-positron",
        center={"lat": 40.0, "lon": -3.5}, zoom=4.5, opacity=0.8,
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=550,
        coloraxis_colorbar={"title": unit_label, "thickness": 15},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Media", f"{latest['valor'].mean():,.1f}")
    c2.metric("Mediana", f"{latest['valor'].median():,.1f}")
    c3.metric("Máximo", f"{latest['valor'].max():,.1f}")
    c4.metric("Mínimo", f"{latest['valor'].min():,.1f}")

    # Ranking
    col_rank, col_ts = st.columns(2)
    with col_rank:
        st.subheader("Ranking")
        sorted_df = latest.sort_values("valor", ascending=True)
        fig_bar = px.bar(
            sorted_df, x="valor", y="provincia", orientation="h",
            labels={"valor": unit_label, "provincia": ""},
            color="valor", color_continuous_scale=color_scale,
            height=max(400, len(sorted_df) * 18),
        )
        fig_bar.update_layout(
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
            showlegend=False, coloraxis_showscale=False, yaxis={"dtick": 1},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Time series
    with col_ts:
        st.subheader("Evolución temporal")
        ts = _load_timeseries(dataset, nult)
        if ts.empty:
            st.info("No hay datos de serie temporal.")
        else:
            ts = _add_province_names(ts)
            all_provs = sorted(ts["provincia"].unique())
            selected = st.multiselect(
                "Provincias", options=all_provs, default=all_provs[:5],
                key="ts_select",
            )
            if selected:
                fig_ts = px.line(
                    ts[ts["provincia"].isin(selected)],
                    x="periodo", y="valor", color="provincia",
                    labels={"valor": unit_label, "periodo": "", "provincia": ""},
                )
                fig_ts.update_layout(
                    margin={"r": 10, "t": 10, "l": 10, "b": 10},
                    height=500, legend={"orientation": "h", "y": -0.1},
                )
                st.plotly_chart(fig_ts, use_container_width=True)

    with st.expander("📋 Ver datos"):
        display_df = latest[["provincia", "valor", "periodo"]].copy()
        display_df.columns = ["Provincia", unit_label, "Período"]
        display_df["Período"] = display_df["Período"].dt.strftime("%Y-%m")
        st.dataframe(display_df.sort_values(unit_label, ascending=False),
                      use_container_width=True, hide_index=True)


# ============================================================
# TAB 2: Dashboard comparativo
# ============================================================
with tab_dashboard:
    st.subheader("Comparar provincias en todos los indicadores")

    all_data = _load_all_latest()
    all_ts = _load_all_timeseries()

    # Get list of all provinces from any dataset
    all_province_names = set()
    for df in all_data.values():
        if "provincia" in df.columns:
            all_province_names.update(df["provincia"].unique())
    all_province_names = sorted(all_province_names)

    selected_provs = st.multiselect(
        "Seleccionar provincias a comparar",
        options=all_province_names,
        default=["Madrid", "Barcelona", "Sevilla"],
        key="dash_provs",
    )

    if not selected_provs:
        st.info("Selecciona al menos una provincia.")
        st.stop()

    # --- Radar chart ---
    st.subheader("Perfil comparado (valores normalizados)")

    radar_data = []
    for key, df in all_data.items():
        if df.empty:
            continue
        vmin, vmax = df["valor"].min(), df["valor"].max()
        rng = vmax - vmin if vmax != vmin else 1
        for prov in selected_provs:
            row = df[df["provincia"] == prov]
            if row.empty:
                continue
            val = row.iloc[0]["valor"]
            normalized = (val - vmin) / rng * 100
            radar_data.append({
                "provincia": prov,
                "indicador": DATASET_NAMES.get(key, key),
                "valor_norm": normalized,
                "valor_real": val,
            })

    if radar_data:
        radar_df = pd.DataFrame(radar_data)
        fig_radar = px.line_polar(
            radar_df, r="valor_norm", theta="indicador",
            color="provincia", line_close=True,
            hover_data={"valor_real": ":.1f", "valor_norm": False},
            labels={"valor_norm": "% del rango", "provincia": ""},
        )
        fig_radar.update_traces(fill="toself", opacity=0.3)
        fig_radar.update_layout(
            height=500,
            polar={"radialaxis": {"visible": True, "range": [0, 100]}},
            legend={"orientation": "h", "y": -0.05},
            margin={"t": 30, "b": 30},
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # --- Indicator cards ---
    st.subheader("Detalle por indicador")

    for key, df in all_data.items():
        if df.empty:
            continue
        name = DATASET_NAMES.get(key, key)
        unit = UNITS.get(key, "Valor")

        with st.expander(f"**{name}**", expanded=True):
            # Metrics row
            cols = st.columns(len(selected_provs))
            national_mean = df["valor"].mean()
            for i, prov in enumerate(selected_provs):
                row = df[df["provincia"] == prov]
                if row.empty:
                    cols[i].metric(prov, "Sin datos")
                    continue
                val = row.iloc[0]["valor"]
                delta = val - national_mean
                delta_pct = (delta / national_mean * 100) if national_mean else 0
                cols[i].metric(
                    prov,
                    f"{val:,.1f}",
                    delta=f"{delta_pct:+.1f}% vs media",
                )

            # Time series comparison
            ts_df = all_ts.get(key, pd.DataFrame())
            if not ts_df.empty:
                ts_filtered = ts_df[ts_df["provincia"].isin(selected_provs)]
                if not ts_filtered.empty:
                    fig_line = px.line(
                        ts_filtered, x="periodo", y="valor",
                        color="provincia",
                        labels={"valor": unit, "periodo": "", "provincia": ""},
                    )
                    fig_line.update_layout(
                        height=300,
                        margin={"r": 10, "t": 10, "l": 10, "b": 10},
                        legend={"orientation": "h", "y": -0.15},
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

    # --- Summary table ---
    st.subheader("Tabla resumen")
    summary_rows = []
    for key, df in all_data.items():
        if df.empty:
            continue
        row = {"Indicador": DATASET_NAMES.get(key, key)}
        for prov in selected_provs:
            prov_row = df[df["provincia"] == prov]
            row[prov] = f"{prov_row.iloc[0]['valor']:,.1f}" if not prov_row.empty else "—"
        row["Media nacional"] = f"{df['valor'].mean():,.1f}"
        summary_rows.append(row)

    if summary_rows:
        st.dataframe(
            pd.DataFrame(summary_rows).set_index("Indicador"),
            use_container_width=True,
        )


# ============================================================
# TAB 3: Cruce de indicadores
# ============================================================
with tab_cross:
    st.subheader("Correlación entre indicadores")

    all_data = _load_all_latest()
    available = [k for k in ALL_DATASETS if k in all_data and not all_data[k].empty]

    col_x, col_y = st.columns(2)
    with col_x:
        x_key = st.selectbox(
            "Eje X", options=available,
            format_func=lambda k: DATASET_NAMES.get(k, k),
            index=0, key="cross_x",
        )
    with col_y:
        y_key = st.selectbox(
            "Eje Y", options=available,
            format_func=lambda k: DATASET_NAMES.get(k, k),
            index=min(1, len(available) - 1), key="cross_y",
        )

    # Merge datasets on cod_prov
    df_x = all_data[x_key][["cod_prov", "valor"]].rename(columns={"valor": "x"})
    df_y = all_data[y_key][["cod_prov", "valor"]].rename(columns={"valor": "y"})
    merged = df_x.merge(df_y, on="cod_prov", how="inner")
    merged["provincia"] = merged["cod_prov"].map(get_province_name)

    if merged.empty:
        st.warning("No hay provincias en común entre estos dos indicadores.")
    else:
        x_label = DATASET_NAMES.get(x_key, x_key)
        y_label = DATASET_NAMES.get(y_key, y_key)

        # Scatter plot
        fig_scatter = px.scatter(
            merged, x="x", y="y",
            hover_name="provincia",
            labels={"x": x_label, "y": y_label},
            trendline="ols",
            color_discrete_sequence=["#3b82f6"],
        )
        fig_scatter.update_traces(marker={"size": 10, "opacity": 0.7})
        fig_scatter.update_layout(
            height=550,
            margin={"r": 20, "t": 30, "l": 20, "b": 20},
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Correlation stat
        corr = merged["x"].corr(merged["y"])
        corr_color = "🟢" if abs(corr) > 0.7 else "🟡" if abs(corr) > 0.4 else "🔴"
        st.metric(
            f"Correlación de Pearson",
            f"{corr:.3f}",
            delta=f"{'Fuerte' if abs(corr) > 0.7 else 'Moderada' if abs(corr) > 0.4 else 'Débil'}",
        )

        # Ratio map
        st.subheader(f"Ratio {x_label} / {y_label}")
        merged["ratio"] = merged["x"] / merged["y"].replace(0, float("nan"))

        fig_ratio = px.choropleth_map(
            merged, geojson=geojson,
            locations="cod_prov", featureidkey="properties.cod_prov",
            color="ratio", hover_name="provincia",
            hover_data={"cod_prov": False, "x": ":.1f", "y": ":.1f", "ratio": ":.2f"},
            color_continuous_scale="RdBu_r",
            labels={"ratio": "Ratio", "x": x_label, "y": y_label},
            map_style="carto-positron",
            center={"lat": 40.0, "lon": -3.5}, zoom=4.5, opacity=0.8,
        )
        fig_ratio.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=500,
            coloraxis_colorbar={"title": "Ratio", "thickness": 15},
        )
        st.plotly_chart(fig_ratio, use_container_width=True)

        # Table
        with st.expander("📋 Ver datos del cruce"):
            show_df = merged[["provincia", "x", "y", "ratio"]].copy()
            show_df.columns = ["Provincia", x_label, y_label, "Ratio"]
            st.dataframe(
                show_df.sort_values("Ratio", ascending=False),
                use_container_width=True, hide_index=True,
            )
