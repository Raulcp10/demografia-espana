"""Descarga datos del INE, genera gráficas PNG y reportes Markdown."""

import locale
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import requests

# Meses en español
locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")

MESES_ES = {
    "January": "enero", "February": "febrero", "March": "marzo",
    "April": "abril", "May": "mayo", "June": "junio",
    "July": "julio", "August": "agosto", "September": "septiembre",
    "October": "octubre", "November": "noviembre", "December": "diciembre",
}


def fecha_es(ts: pd.Timestamp) -> str:
    """Format a timestamp as 'mes año' in Spanish."""
    try:
        return ts.strftime("%B %Y").lower()
    except Exception:
        month = ts.strftime("%B")
        return f"{MESES_ES.get(month, month)} {ts.year}"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ine import TABLES, get_latest_data, get_timeseries
from src.provinces import (
    CCAA_TO_PROVINCES,
    INE_NAME_TO_COD_PROV,
    get_province_name,
    is_province,
    load_geojson,
)

DATA_DIR = Path("data/csv")
IMG_DIR = Path("reports/img")
REPORTS_DIR = Path("reports")

COLOR_SCALES = {
    "ipv": "YlOrRd",
    "compraventas": "Blues",
    "hipotecas": "Purples",
    "viviendas_turisticas": "Oranges",
    "alquiler": "RdYlGn_r",
    "inmigracion": "Teal",
}

UNITS = {
    "ipv": "Índice (base 2015=100)",
    "compraventas": "Nº de compraventas",
    "hipotecas": "Nº de hipotecas",
    "viviendas_turisticas": "Nº de viviendas turísticas",
    "alquiler": "Índice (base 2015=100)",
    "inmigracion": "Nº de inmigrantes",
}


# --- Immigration data ---


def fetch_immigration(nult: int = 5) -> pd.DataFrame:
    """Fetch immigration data by province from INE table 69691."""
    url = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/69691"
    resp = requests.get(url, params={"nult": nult}, timeout=120)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for series in raw:
        nombre = series.get("Nombre", "")
        n_lower = nombre.lower()
        # Filter: total ages, total nationality, total sex
        if "todas las edades" not in n_lower:
            continue
        if "dato base" not in n_lower:
            continue

        parts = [p.strip() for p in nombre.split(".") if p.strip()]
        if not parts:
            continue

        territory = parts[0]
        # Check if it's "Total" sex (not Hombres/Mujeres)
        if len(parts) > 3 and parts[3] != "Total":
            continue
        # Check nationality = Total (not Española/Extranjera)
        if len(parts) > 2 and parts[2] != "Total":
            continue

        # Resolve to province
        if not is_province(territory):
            continue
        cod = INE_NAME_TO_COD_PROV.get(territory)
        if not cod:
            continue

        for dp in series.get("Data", []):
            valor = dp.get("Valor")
            fecha = dp.get("Fecha")
            if valor is None or fecha is None:
                continue
            rows.append({
                "cod_prov": cod,
                "periodo": pd.Timestamp(fecha, unit="ms"),
                "valor": valor,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["cod_prov", "periodo"])
    return df


# --- Chart generation ---


def save_choropleth(df: pd.DataFrame, key: str, geojson: dict) -> str:
    """Generate and save a choropleth map as PNG."""
    fig = px.choropleth_map(
        df,
        geojson=geojson,
        locations="cod_prov",
        featureidkey="properties.cod_prov",
        color="valor",
        hover_name="provincia",
        color_continuous_scale=COLOR_SCALES.get(key, "Viridis"),
        labels={"valor": UNITS.get(key, "Valor")},
        map_style="carto-positron",
        center={"lat": 40.0, "lon": -3.5},
        zoom=4.5,
        opacity=0.8,
    )
    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=500,
        width=900,
        title=f"{TABLES.get(key, {}).get('name', key)} por provincia",
        coloraxis_colorbar={"title": UNITS.get(key, "Valor"), "thickness": 15},
    )
    path = IMG_DIR / f"{key}_mapa.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


def save_ranking(df: pd.DataFrame, key: str) -> str:
    """Generate and save a horizontal bar chart as PNG."""
    sorted_df = df.sort_values("valor", ascending=True)
    fig = px.bar(
        sorted_df,
        x="valor",
        y="provincia",
        orientation="h",
        labels={"valor": UNITS.get(key, "Valor"), "provincia": ""},
        color="valor",
        color_continuous_scale=COLOR_SCALES.get(key, "Viridis"),
        height=max(400, len(sorted_df) * 20),
        width=800,
    )
    fig.update_layout(
        margin={"r": 10, "t": 40, "l": 10, "b": 10},
        title=f"Ranking: {TABLES.get(key, {}).get('name', key)}",
        showlegend=False,
        coloraxis_showscale=False,
        yaxis={"dtick": 1},
    )
    path = IMG_DIR / f"{key}_ranking.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


def save_timeseries(ts: pd.DataFrame, key: str, top_n: int = 10) -> str:
    """Generate time series chart for top N provinces."""
    if ts.empty:
        return ""
    # Get top N provinces by latest value
    last = ts.sort_values("periodo").groupby("cod_prov").last().reset_index()
    top_provs = last.nlargest(top_n, "valor")["cod_prov"].tolist()
    filtered = ts[ts["cod_prov"].isin(top_provs)]

    fig = px.line(
        filtered,
        x="periodo",
        y="valor",
        color="provincia",
        labels={"valor": UNITS.get(key, "Valor"), "periodo": "Período", "provincia": "Provincia"},
        width=900,
        height=450,
    )
    fig.update_layout(
        margin={"r": 10, "t": 40, "l": 10, "b": 10},
        title=f"Evolución: {TABLES.get(key, {}).get('name', key)} (top {top_n})",
        legend={"orientation": "h", "y": -0.2},
    )
    path = IMG_DIR / f"{key}_serie.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


# --- Report generation ---


def generate_report(key: str, latest: pd.DataFrame, ts: pd.DataFrame, geojson: dict) -> str:
    """Generate a Markdown report for a dataset."""
    table_info = TABLES.get(key, {"name": key, "description": ""})
    unit = UNITS.get(key, "Valor")

    # Generate charts
    print(f"  Generando mapa...")
    map_file = save_choropleth(latest, key, geojson)
    print(f"  Generando ranking...")
    rank_file = save_ranking(latest, key)
    serie_file = ""
    if not ts.empty:
        print(f"  Generando serie temporal...")
        serie_file = save_timeseries(ts, key)

    # Stats
    mean = latest["valor"].mean()
    median = latest["valor"].median()
    top5 = latest.nlargest(5, "valor")[["provincia", "valor"]]
    bottom5 = latest.nsmallest(5, "valor")[["provincia", "valor"]]

    periodo = ""
    if "periodo" in latest.columns and latest["periodo"].notna().any():
        periodo = fecha_es(latest["periodo"].max())

    # Write report
    md = f"""# {table_info['name']}

> {table_info.get('description', '')}
> Último dato: {periodo}

## Mapa por provincia

![Mapa](<img/{map_file}>)

## Estadísticas resumen

| Métrica | Valor |
|---------|-------|
| Media | {mean:,.1f} |
| Mediana | {median:,.1f} |
| Máximo | {latest['valor'].max():,.1f} |
| Mínimo | {latest['valor'].min():,.1f} |
| Provincias | {len(latest)} |

## Top 5 provincias

| Provincia | {unit} |
|-----------|--------|
"""
    for _, row in top5.iterrows():
        md += f"| {row['provincia']} | {row['valor']:,.1f} |\n"

    md += f"""
## Bottom 5 provincias

| Provincia | {unit} |
|-----------|--------|
"""
    for _, row in bottom5.iterrows():
        md += f"| {row['provincia']} | {row['valor']:,.1f} |\n"

    md += f"""
## Ranking completo

![Ranking](<img/{rank_file}>)
"""

    if serie_file:
        md += f"""
## Evolución temporal (top 10 provincias)

![Serie temporal](<img/{serie_file}>)
"""

    md += f"""
## Datos

Los datos completos están disponibles en:
- `data/csv/{key}_ultimo.csv` — último dato por provincia
- `data/csv/{key}_serie.csv` — serie temporal completa
"""
    return md


def main():
    print("=" * 60)
    print("Generando reportes de datos INE")
    print("=" * 60)

    geojson = load_geojson()

    # --- Vivienda datasets ---
    for key in TABLES:
        print(f"\n--- {TABLES[key]['name']} ---")
        print("  Descargando datos...")
        latest = get_latest_data(key)
        ts = get_timeseries(key, nult=20)

        if latest.empty:
            print(f"  Sin datos para {key}, saltando.")
            continue

        latest["provincia"] = latest["cod_prov"].map(get_province_name)
        if not ts.empty:
            ts["provincia"] = ts["cod_prov"].map(get_province_name)

        # Save CSVs
        latest.to_csv(DATA_DIR / f"{key}_ultimo.csv", index=False)
        if not ts.empty:
            ts.to_csv(DATA_DIR / f"{key}_serie.csv", index=False)

        # Generate report
        md = generate_report(key, latest, ts, geojson)
        report_path = REPORTS_DIR / f"{key}.md"
        report_path.write_text(md)
        print(f"  Reporte: {report_path}")

    # --- Immigration ---
    print(f"\n--- Inmigración procedente del extranjero ---")
    print("  Descargando datos...")
    imm_ts = fetch_immigration(nult=5)
    if not imm_ts.empty:
        imm_ts["provincia"] = imm_ts["cod_prov"].map(get_province_name)
        imm_latest = imm_ts.sort_values("periodo").groupby("cod_prov").last().reset_index()

        # Save CSVs
        imm_latest.to_csv(DATA_DIR / "inmigracion_ultimo.csv", index=False)
        imm_ts.to_csv(DATA_DIR / "inmigracion_serie.csv", index=False)

        # Add to TABLES temporarily for report generation
        TABLES["inmigracion"] = {
            "name": "Inmigración procedente del extranjero",
            "description": "Flujo de inmigración desde el extranjero por provincia (anual)",
        }
        md = generate_report("inmigracion", imm_latest, imm_ts, geojson)
        report_path = REPORTS_DIR / "inmigracion.md"
        report_path.write_text(md)
        print(f"  Reporte: {report_path}")
    else:
        print("  Sin datos de inmigración.")

    # --- Index report ---
    print("\n--- Generando índice ---")
    index_md = """# Reportes de datos INE — Vivienda e Inmigración

Datos descargados del [Instituto Nacional de Estadística](https://www.ine.es/) (INE).

## Vivienda

| Indicador | Reporte | Datos |
|-----------|---------|-------|
"""
    for key, info in TABLES.items():
        csv_path = f"../data/csv/{key}_ultimo.csv"
        index_md += f"| {info['name']} | [{key}.md](<{key}.md>) | [`{key}_ultimo.csv`](<{csv_path}>) |\n"

    index_md += """
## Cómo se generaron

```bash
uv run python3 scripts/generate_reports.py
```

Cada reporte incluye:
1. **Mapa coroplético** de España por provincia
2. **Estadísticas resumen** (media, mediana, máx, mín)
3. **Top 5 y bottom 5** provincias
4. **Ranking completo** en gráfica de barras
5. **Evolución temporal** de las 10 provincias con mayor valor
6. **Datos en CSV** para análisis propio
"""
    (REPORTS_DIR / "index.md").write_text(index_md)
    print(f"  Índice: reports/index.md")

    print("\n" + "=" * 60)
    print("Completado. Reportes en reports/, datos en data/csv/")
    print("=" * 60)


if __name__ == "__main__":
    main()
