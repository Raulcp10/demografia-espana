"""Datos demográficos del INE: pirámide, tasas, indicadores IDB."""

from __future__ import annotations

import re

import pandas as pd

from src.maps.provinces import INE_NAME_TO_COD_PROV, get_province_name, is_province
from src.sources.ine.client import BASE_URL, fetch_table

import requests

YEAR = 2023

AGE_GROUPS = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
    "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+",
]

IDB_TABLES = {
    "natalidad": {"id": 1470, "name": "Tasa bruta de natalidad", "unit": "‰"},
    "mortalidad": {"id": 1482, "name": "Tasa bruta de mortalidad", "unit": "‰"},
    "crecimiento": {"id": 5226, "name": "Crecimiento anual por 1.000 hab.", "unit": "‰"},
    "saldo_migratorio": {"id": 61771, "name": "Saldo migratorio por 1.000 hab.", "unit": "‰"},
    "pct_65": {"id": 48887, "name": "Porcentaje de población ≥65 años", "unit": "%"},
    "envejecimiento": {"id": 1489, "name": "Índice de envejecimiento", "unit": ""},
    "dependencia": {"id": 1490, "name": "Tasa de dependencia", "unit": "%"},
}

_MULTI_CCAA = {
    "Andalucía", "Aragón", "Castilla y León", "Castilla - La Mancha",
    "Cataluña", "Comunitat Valenciana", "Extremadura", "Galicia",
    "País Vasco", "Canarias", "Total Nacional",
}


# --- Pirámide de población ---

def load_pyramid() -> pd.DataFrame:
    """Pirámide de población nacional (tabla ECP 56934)."""
    url = f"{BASE_URL}/DATOS_TABLA/56934?nult=3"
    raw = requests.get(url, timeout=120).json()

    data = {}
    for series in raw:
        nombre = series.get("Nombre", "")
        if "Total Nacional" not in nombre:
            continue

        parts = [p.strip() for p in nombre.split(".") if p.strip()]

        age_num = None
        for part in parts:
            m = re.match(r"^(\d+)\s*años?$", part)
            if m:
                age_num = int(m.group(1))
                break
        if age_num is None:
            continue

        if age_num >= 100:
            group = "100+"
        else:
            bucket = (age_num // 5) * 5
            group = f"{bucket}-{bucket + 4}"

        sex = parts[2].strip() if len(parts) > 2 else ""
        if sex not in ("Hombres", "Mujeres"):
            continue

        valor = None
        for dp in series.get("Data", []):
            if dp.get("Valor") is None:
                continue
            fecha = pd.Timestamp(dp["Fecha"], unit="ms")
            if fecha.year in (YEAR, YEAR + 1):
                valor = dp["Valor"]
                break
        if valor is None:
            continue

        key = (group, sex)
        data[key] = data.get(key, 0) + valor

    rows = []
    for group in AGE_GROUPS:
        h = data.get((group, "Hombres"), 0)
        m_val = data.get((group, "Mujeres"), 0)
        rows.append({"grupo_edad": group, "hombres": h, "mujeres": m_val})

    return pd.DataFrame(rows)


# --- Tasas nacionales ---

def load_rates() -> tuple[dict, pd.DataFrame]:
    """Tasas de natalidad y mortalidad: valor actual + serie histórica."""
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

    all_rows = []
    for key, rows in series_data.items():
        for r in rows:
            all_rows.append({"año": r["año"], "indicador": key, "valor": r["valor"]})
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.drop_duplicates(["año", "indicador"]).sort_values("año")
    return current, df


def load_demographics() -> dict:
    """Edad media, dependencia, fecundidad y % 65+."""
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


def load_historical_65() -> pd.DataFrame:
    """Serie histórica de % de mayores de 65."""
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


# --- Indicadores IDB por provincia ---

def _parse_territory(nombre: str, table_key: str) -> str | None:
    """Extrae nombre de territorio de una serie IDB."""
    parts = [p.strip() for p in nombre.split(".") if p.strip()]
    if table_key in ("natalidad", "mortalidad"):
        return parts[1] if len(parts) > 1 else None
    if table_key in ("crecimiento", "saldo_migratorio"):
        return parts[0] if parts else None
    if table_key == "pct_65":
        if "proporción" in nombre.lower():
            return None
        for part in parts:
            if part in INE_NAME_TO_COD_PROV:
                return part
        return parts[1] if len(parts) > 1 and parts[0].startswith("Indicadores") else parts[0]
    if table_key in ("envejecimiento", "dependencia"):
        return parts[1] if len(parts) > 1 else None
    return None


def fetch_idb(table_key: str, nult: int = 10) -> pd.DataFrame:
    """Indicador IDB por provincia con serie temporal.

    Columnas: cod_prov, periodo, valor, provincia
    """
    info = IDB_TABLES[table_key]
    raw = fetch_table(info["id"], nult=nult)

    rows = []
    for series in raw:
        nombre = series.get("Nombre", "")
        territory = _parse_territory(nombre, table_key)
        if territory is None or not is_province(territory):
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
        df["provincia"] = df["cod_prov"].map(get_province_name)
    return df


def fetch_idb_latest(table_key: str) -> pd.DataFrame:
    """Último dato IDB por provincia."""
    df = fetch_idb(table_key, nult=1)
    if df.empty:
        return df
    return df.sort_values("periodo").groupby("cod_prov").last().reset_index()
