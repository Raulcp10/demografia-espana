"""Cliente para la API JSON del INE (servicios.ine.es)."""

import pandas as pd
import requests

from .provinces import (
    CCAA_NAMES,
    CCAA_TO_PROVINCES,
    INE_NAME_TO_COD_PROV,
    is_province,
)

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"

# Tablas conocidas
TABLES = {
    "ipv": {
        "id": 25171,
        "name": "Índice de Precios de Vivienda (IPV)",
        "level": "ccaa",
        "description": "Índice trimestral de precios de vivienda por CCAA",
    },
    "compraventas": {
        "id": 6146,
        "name": "Compraventas de viviendas",
        "level": "provincia",
        "description": "Transmisiones de viviendas por provincia (mensual)",
    },
    "hipotecas": {
        "id": 76317,
        "name": "Hipotecas constituidas",
        "level": "provincia",
        "description": "Hipotecas constituidas por provincia (mensual, base nueva)",
    },
    "viviendas_turisticas": {
        "id": 39364,
        "name": "Viviendas turísticas",
        "level": "provincia",
        "description": "Viviendas turísticas por provincia",
    },
    "alquiler": {
        "id": 59058,
        "name": "Índice de Precios de Alquiler",
        "level": "provincia",
        "description": "Índice de precios de alquiler por provincia (trimestral)",
    },
}


def fetch_table(table_id: int, nult: int = 5) -> list[dict]:
    """Fetch raw data from an INE table."""
    url = f"{BASE_URL}/DATOS_TABLA/{table_id}?nult={nult}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _parse_timestamp(ts: int | None) -> pd.Timestamp | None:
    """Convert INE millisecond timestamp to pandas Timestamp."""
    if ts is None:
        return None
    return pd.Timestamp(ts, unit="ms")


def _extract_territory(nombre: str, table_key: str) -> str | None:
    """Extract territory name from INE series name."""
    parts = [p.strip() for p in nombre.split(".") if p.strip()]
    if table_key == "ipv":
        # Format: "CCAA. Tipo. Métrica."
        return parts[0] if parts else None
    if table_key == "compraventas":
        # Format: "Número. Territorio. Tipo finca."
        return parts[1] if len(parts) > 1 else None
    if table_key == "hipotecas":
        # Format: "Tipo. Métrica. Territorio. Base. Periodicidad."
        return parts[2] if len(parts) > 2 else None
    if table_key == "alquiler":
        # Format: "Territorio. Tipo. Métrica."
        return parts[0] if parts else None
    if table_key == "viviendas_turisticas":
        for part in parts:
            if part in INE_NAME_TO_COD_PROV or part in CCAA_NAMES:
                return part
    return parts[1] if len(parts) > 1 else None


def _filter_series(nombre: str, table_key: str) -> bool:
    """Filter to keep only the relevant series for each table."""
    n = nombre.lower()
    if table_key == "ipv":
        return "general" in n and "índice" in n and "variación" not in n
    if table_key == "compraventas":
        return "viviendas" in n and "número" in n
    if table_key == "hipotecas":
        return "viviendas" in n and "número de hipotecas" in n and "base nueva" in n
    if table_key == "viviendas_turisticas":
        return "viviendas turísticas" in n and "plazas por" not in n and "plazas" not in n.replace("viviendas turísticas, plazas", "")
    if table_key == "alquiler":
        return "total" in n and "índice" in n and "variación" not in n
    return True


def fetch_province_data(table_key: str, nult: int = 5) -> pd.DataFrame:
    """Fetch and parse INE data into a province-level DataFrame.

    Returns DataFrame with columns: cod_prov, periodo, valor
    """
    table_info = TABLES[table_key]
    raw = fetch_table(table_info["id"], nult=nult)

    rows = []
    for series in raw:
        nombre = series.get("Nombre", "")
        if not _filter_series(nombre, table_key):
            continue

        territory = _extract_territory(nombre, table_key)
        if territory is None:
            continue

        # Resolve to province codes
        if table_info["level"] == "ccaa":
            # Map CCAA data to all its provinces
            if territory in CCAA_TO_PROVINCES:
                prov_codes = CCAA_TO_PROVINCES[territory]
            elif territory in INE_NAME_TO_COD_PROV:
                prov_codes = [INE_NAME_TO_COD_PROV[territory]]
            else:
                continue
        else:
            if not is_province(territory):
                continue
            cod = INE_NAME_TO_COD_PROV.get(territory)
            if cod is None:
                continue
            prov_codes = [cod]

        for data_point in series.get("Data", []):
            valor = data_point.get("Valor")
            if valor is None:
                continue
            periodo = _parse_timestamp(data_point.get("Fecha"))
            for cod in prov_codes:
                rows.append({
                    "cod_prov": cod,
                    "periodo": periodo,
                    "valor": valor,
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values(["cod_prov", "periodo"])
    return df


def get_latest_data(table_key: str) -> pd.DataFrame:
    """Get the most recent data point per province."""
    df = fetch_province_data(table_key, nult=1)
    if df.empty:
        return df
    # Keep last value per province
    return df.sort_values("periodo").groupby("cod_prov").last().reset_index()


def get_timeseries(table_key: str, nult: int = 20) -> pd.DataFrame:
    """Get time series data for all provinces."""
    return fetch_province_data(table_key, nult=nult)
