"""Datos de inmigración desde el extranjero del INE (tabla 69691)."""

import pandas as pd
import requests

from src.maps.provinces import INE_NAME_TO_COD_PROV, is_province


def fetch_immigration(nult: int = 5) -> pd.DataFrame:
    """Descarga datos de inmigración por provincia.

    Columnas: cod_prov, periodo, valor
    """
    url = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/69691"
    resp = requests.get(url, params={"nult": nult}, timeout=120)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for series in raw:
        nombre = series.get("Nombre", "")
        n_lower = nombre.lower()
        if "todas las edades" not in n_lower:
            continue
        if "dato base" not in n_lower:
            continue

        parts = [p.strip() for p in nombre.split(".") if p.strip()]
        if not parts:
            continue

        territory = parts[0]
        if len(parts) > 3 and parts[3] != "Total":
            continue
        if len(parts) > 2 and parts[2] != "Total":
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
    return df
