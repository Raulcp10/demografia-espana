"""Descarga datos demográficos del INE, genera gráficas PNG y reportes Markdown."""

import locale
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")

MESES_ES = {
    "January": "enero", "February": "febrero", "March": "marzo",
    "April": "abril", "May": "mayo", "June": "junio",
    "July": "julio", "August": "agosto", "September": "septiembre",
    "October": "octubre", "November": "noviembre", "December": "diciembre",
}


def fecha_es(ts: pd.Timestamp) -> str:
    try:
        return ts.strftime("%B %Y").lower()
    except Exception:
        month = ts.strftime("%B")
        return f"{MESES_ES.get(month, month)} {ts.year}"


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.maps.provinces import load_geojson
from src.sources.ine.demografia import IDB_TABLES, fetch_idb, fetch_idb_latest

DATA_DIR = Path("data/csv")
IMG_DIR = Path("reports/img")
REPORTS_DIR = Path("reports")

COLOR_SCALES = {
    "natalidad": "Greens",
    "mortalidad": "Reds",
    "crecimiento": "RdYlGn",
    "saldo_migratorio": "PiYG",
    "pct_65": "OrRd",
    "envejecimiento": "YlOrBr",
    "dependencia": "BuPu",
}


def save_choropleth(df: pd.DataFrame, key: str, geojson: dict) -> str:
    info = IDB_TABLES[key]
    fig = px.choropleth_map(
        df, geojson=geojson,
        locations="cod_prov", featureidkey="properties.cod_prov",
        color="valor", hover_name="provincia",
        color_continuous_scale=COLOR_SCALES.get(key, "YlOrRd"),
        labels={"valor": info["unit"] or "Valor"},
        map_style="carto-positron",
        center={"lat": 40.0, "lon": -3.5}, zoom=4.5, opacity=0.8,
    )
    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=500, width=900,
        title=f"{info['name']} por provincia",
        coloraxis_colorbar={"title": info["unit"], "thickness": 15},
    )
    path = IMG_DIR / f"{key}_mapa.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


def save_ranking(df: pd.DataFrame, key: str) -> str:
    info = IDB_TABLES[key]
    sorted_df = df.sort_values("valor", ascending=True)
    fig = px.bar(
        sorted_df, x="valor", y="provincia", orientation="h",
        labels={"valor": info["unit"] or "Valor", "provincia": ""},
        color="valor", color_continuous_scale=COLOR_SCALES.get(key, "YlOrRd"),
        height=max(400, len(sorted_df) * 20), width=800,
    )
    fig.update_layout(
        margin={"r": 10, "t": 40, "l": 10, "b": 10},
        title=f"Ranking: {info['name']}",
        showlegend=False, coloraxis_showscale=False, yaxis={"dtick": 1},
    )
    path = IMG_DIR / f"{key}_ranking.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


def save_timeseries(ts: pd.DataFrame, key: str, top_n: int = 10) -> str:
    if ts.empty:
        return ""
    info = IDB_TABLES[key]
    last = ts.sort_values("periodo").groupby("cod_prov").last().reset_index()
    top_provs = last.nlargest(top_n, "valor")["cod_prov"].tolist()
    filtered = ts[ts["cod_prov"].isin(top_provs)]

    fig = px.line(
        filtered, x="periodo", y="valor", color="provincia",
        labels={"valor": info["unit"] or "Valor", "periodo": "Período", "provincia": "Provincia"},
        width=900, height=450,
    )
    fig.update_layout(
        margin={"r": 10, "t": 40, "l": 10, "b": 10},
        title=f"Evolución: {info['name']} (top {top_n})",
        legend={"orientation": "h", "y": -0.2},
    )
    path = IMG_DIR / f"{key}_serie.png"
    pio.write_image(fig, str(path), scale=2)
    return path.name


def generate_report(key: str, latest: pd.DataFrame, ts: pd.DataFrame, geojson: dict) -> str:
    info = IDB_TABLES[key]
    unit = info["unit"] or "Valor"

    print(f"  Generando mapa...")
    map_file = save_choropleth(latest, key, geojson)
    print(f"  Generando ranking...")
    rank_file = save_ranking(latest, key)
    serie_file = ""
    if not ts.empty:
        print(f"  Generando serie temporal...")
        serie_file = save_timeseries(ts, key)

    mean = latest["valor"].mean()
    median = latest["valor"].median()
    top5 = latest.nlargest(5, "valor")[["provincia", "valor"]]
    bottom5 = latest.nsmallest(5, "valor")[["provincia", "valor"]]

    periodo = ""
    if "periodo" in latest.columns and latest["periodo"].notna().any():
        periodo = fecha_es(latest["periodo"].max())

    md = f"""# {info['name']}

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
    print("Generando reportes demográficos — INE")
    print("=" * 60)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    geojson = load_geojson()

    for key in IDB_TABLES:
        info = IDB_TABLES[key]
        print(f"\n--- {info['name']} ---")
        print("  Descargando datos...")
        latest = fetch_idb_latest(key)
        ts = fetch_idb(key, nult=10)

        if latest.empty:
            print(f"  Sin datos para {key}, saltando.")
            continue

        latest.to_csv(DATA_DIR / f"{key}_ultimo.csv", index=False)
        if not ts.empty:
            ts.to_csv(DATA_DIR / f"{key}_serie.csv", index=False)

        md = generate_report(key, latest, ts, geojson)
        report_path = REPORTS_DIR / f"{key}.md"
        report_path.write_text(md)
        print(f"  Reporte: {report_path}")

    # Índice
    print("\n--- Generando índice ---")
    index_md = """# Reportes demográficos — INE

Datos descargados del [Instituto Nacional de Estadística](https://www.ine.es/) (INE).

| Indicador | Reporte | Datos |
|-----------|---------|-------|
"""
    for key, info in IDB_TABLES.items():
        csv_path = f"../data/csv/{key}_ultimo.csv"
        index_md += f"| {info['name']} | [{key}.md](<{key}.md>) | [`{key}_ultimo.csv`](<{csv_path}>) |\n"

    index_md += """
## Cómo se generaron

```bash
uv run python scripts/generate_reports.py
```
"""
    (REPORTS_DIR / "index.md").write_text(index_md)
    print(f"  Índice: reports/index.md")

    print("\n" + "=" * 60)
    print("Completado.")
    print("=" * 60)


if __name__ == "__main__":
    main()
