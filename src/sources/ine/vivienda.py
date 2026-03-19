"""Datos de vivienda del INE: IPV, compraventas, hipotecas, alquiler, turísticas."""

import pandas as pd

from src.maps.provinces import (
    CCAA_NAMES,
    CCAA_TO_PROVINCES,
    INE_NAME_TO_COD_PROV,
    is_province,
)
from src.sources.ine.client import fetch_table, parse_timestamp

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


def _extract_territory(nombre: str, table_key: str) -> str | None:
    """Extrae el nombre de territorio de una serie del INE."""
    parts = [p.strip() for p in nombre.split(".") if p.strip()]
    if table_key == "ipv":
        return parts[0] if parts else None
    if table_key == "compraventas":
        return parts[1] if len(parts) > 1 else None
    if table_key == "hipotecas":
        return parts[2] if len(parts) > 2 else None
    if table_key == "alquiler":
        return parts[0] if parts else None
    if table_key == "viviendas_turisticas":
        for part in parts:
            if part in INE_NAME_TO_COD_PROV or part in CCAA_NAMES:
                return part
    return parts[1] if len(parts) > 1 else None


def _filter_series(nombre: str, table_key: str) -> bool:
    """Filtra para quedarse solo con las series relevantes."""
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
    """Descarga datos del INE y devuelve un DataFrame a nivel provincia.

    Columnas: cod_prov, periodo, valor
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

        if table_info["level"] == "ccaa":
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
            periodo = parse_timestamp(data_point.get("Fecha"))
            for cod in prov_codes:
                rows.append({
                    "cod_prov": cod,
                    "periodo": periodo,
                    "valor": valor,
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["cod_prov", "periodo"])


def get_latest_data(table_key: str) -> pd.DataFrame:
    """Último dato por provincia."""
    df = fetch_province_data(table_key, nult=1)
    if df.empty:
        return df
    return df.sort_values("periodo").groupby("cod_prov").last().reset_index()


def get_timeseries(table_key: str, nult: int = 20) -> pd.DataFrame:
    """Serie temporal por provincia."""
    return fetch_province_data(table_key, nult=nult)
