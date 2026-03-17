"""Descarga y parseo de datos demográficos del INE."""

import re

import pandas as pd
import requests

from src.provinces import (
    CCAA_TO_PROVINCES,
    INE_NAME_TO_COD_PROV,
    get_province_name,
    is_province,
)

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"

# --- IDB tables (all province level) ---
IDB_TABLES = {
    "natalidad": {"id": 1470, "name": "Tasa bruta de natalidad", "unit": "‰"},
    "mortalidad": {"id": 1482, "name": "Tasa bruta de mortalidad", "unit": "‰"},
    "crecimiento": {"id": 5226, "name": "Crecimiento anual por 1.000 hab.", "unit": "‰"},
    "saldo_migratorio": {"id": 61771, "name": "Saldo migratorio por 1.000 hab.", "unit": "‰"},
    "pct_65": {"id": 48887, "name": "Porcentaje de población ≥65 años", "unit": "%"},
    "envejecimiento": {"id": 1489, "name": "Índice de envejecimiento", "unit": ""},
}


def _fetch(table_id: int, nult: int = 5) -> list[dict]:
    url = f"{BASE_URL}/DATOS_TABLA/{table_id}"
    resp = requests.get(url, params={"nult": nult}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        raise ValueError(f"INE API error: {data}")
    return data


def _parse_territory_idb(nombre: str, table_key: str) -> str | None:
    """Extract territory name from IDB series."""
    parts = [p.strip() for p in nombre.split(".") if p.strip()]
    if table_key in ("natalidad", "mortalidad"):
        # "Fecundidad. Territorio." or "Mortalidad. Territorio."
        return parts[1] if len(parts) > 1 else None
    if table_key in ("crecimiento", "saldo_migratorio"):
        # "Territorio. Indicadores... Crecimiento..."
        return parts[0] if parts else None
    if table_key == "pct_65":
        # Two formats:
        # "Indicadores... Territorio." (first series = %≥65)
        # "Territorio. Indicadores... Proporción... 70 y más..."
        if "proporción" in nombre.lower():
            return None  # Skip sub-age breakdowns
        for part in parts:
            if part in INE_NAME_TO_COD_PROV:
                return part
        return parts[1] if len(parts) > 1 and parts[0].startswith("Indicadores") else parts[0]
    if table_key == "envejecimiento":
        # "Indicadores... Territorio."
        return parts[1] if len(parts) > 1 else None
    return None


def fetch_idb(table_key: str, nult: int = 10) -> pd.DataFrame:
    """Fetch an IDB indicator by province."""
    info = IDB_TABLES[table_key]
    raw = _fetch(info["id"], nult=nult)

    rows = []
    for series in raw:
        nombre = series.get("Nombre", "")
        territory = _parse_territory_idb(nombre, table_key)
        if territory is None:
            continue
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
        df["provincia"] = df["cod_prov"].map(get_province_name)
    return df


def fetch_idb_latest(table_key: str) -> pd.DataFrame:
    """Get latest IDB data per province."""
    df = fetch_idb(table_key, nult=1)
    if df.empty:
        return df
    return df.sort_values("periodo").groupby("cod_prov").last().reset_index()


# --- Population by nationality (CCAA level, table 59587) ---


def fetch_nationality() -> pd.DataFrame:
    """Fetch population by nationality (española/extranjera) at CCAA level.

    Returns DataFrame with: ccaa, total, española, extranjera, pct_extranjera
    """
    raw = _fetch(59587, nult=1)

    data = {}  # ccaa -> {total, española, extranjera}
    for series in raw:
        nombre = series.get("Nombre", "")
        n_lower = nombre.lower()
        if "todas las edades" not in n_lower or "total" not in nombre.split(".")[2].strip():
            continue  # Only "Total" sex

        parts = [p.strip() for p in nombre.split(".") if p.strip()]
        territory = parts[0]

        # Determine nationality type
        nationality = parts[2].strip() if len(parts) > 2 else ""

        valor = None
        for dp in series.get("Data", []):
            if dp.get("Valor") is not None:
                valor = dp["Valor"]
                break
        if valor is None:
            continue

        if territory not in data:
            data[territory] = {}

        if nationality == "Total":
            data[territory]["total"] = valor
        elif nationality == "Española":
            data[territory]["española"] = valor
        elif nationality == "Extranjera":
            data[territory]["extranjera"] = valor

    # Build province-level data by mapping CCAA → provinces
    rows = []
    for ccaa_name, vals in data.items():
        total = vals.get("total", 0)
        extranjera = vals.get("extranjera", 0)
        if total == 0:
            continue
        pct = (extranjera / total) * 100

        # Map to provinces
        if ccaa_name in CCAA_TO_PROVINCES:
            prov_codes = CCAA_TO_PROVINCES[ccaa_name]
        elif ccaa_name in INE_NAME_TO_COD_PROV and is_province(ccaa_name):
            prov_codes = [INE_NAME_TO_COD_PROV[ccaa_name]]
        else:
            continue

        for cod in prov_codes:
            rows.append({
                "cod_prov": cod,
                "total": total / len(prov_codes),  # Approximate split
                "extranjera": extranjera / len(prov_codes),
                "pct_extranjera": pct,  # Same % for all provinces in CCAA
                "provincia": get_province_name(cod),
            })

    return pd.DataFrame(rows)


# --- Population pyramid (CCAA level, table 56940) ---

AGE_GROUPS = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
    "65-69", "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+",
]


def _age_to_group(age: int) -> str:
    if age >= 100:
        return "100+"
    bucket = (age // 5) * 5
    return f"{bucket}-{bucket + 4}"


def fetch_pyramid(nult: int = 1) -> pd.DataFrame:
    """Fetch population pyramid data (national + CCAA level).

    Returns DataFrame with: territory, grupo_edad, hombres, mujeres
    """
    raw = _fetch(56940, nult=nult)

    data = {}  # (territory, age_group, sex) -> sum

    for series in raw:
        nombre = series.get("Nombre", "")
        parts = [p.strip() for p in nombre.split(".") if p.strip()]

        # Parse age
        age_str = None
        for part in parts:
            match = re.match(r"^(\d+)\s*años?$", part)
            if match:
                age_str = match.group(1)
                break
        if age_str is None:
            continue
        age = int(age_str)
        group = _age_to_group(age)

        # Parse sex and territory
        if "Total Nacional" in nombre:
            territory = "Total Nacional"
            sex = parts[2].strip() if len(parts) > 2 else ""
        else:
            sex = parts[0].strip()
            territory = parts[2].strip() if len(parts) > 2 else ""

        if sex not in ("Hombres", "Mujeres"):
            continue

        valor = None
        for dp in series.get("Data", []):
            if dp.get("Valor") is not None:
                valor = dp["Valor"]
                break
        if valor is None:
            continue

        key = (territory, group, sex)
        data[key] = data.get(key, 0) + valor

    # Build DataFrame
    rows = []
    territories = set(k[0] for k in data)
    for territory in territories:
        for group in AGE_GROUPS:
            h = data.get((territory, group, "Hombres"), 0)
            m = data.get((territory, group, "Mujeres"), 0)
            if h > 0 or m > 0:
                rows.append({
                    "territorio": territory,
                    "grupo_edad": group,
                    "hombres": -h,  # Negative for pyramid display
                    "mujeres": m,
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Sort by age group
        df["_sort"] = df["grupo_edad"].apply(lambda x: AGE_GROUPS.index(x) if x in AGE_GROUPS else 99)
        df = df.sort_values(["territorio", "_sort"]).drop(columns="_sort")
    return df
