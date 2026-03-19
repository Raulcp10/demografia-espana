"""Cliente genérico para la API JSON del INE (servicios.ine.es)."""

import pandas as pd
import requests

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"


def fetch_table(table_id: int, nult: int = 5) -> list[dict]:
    """Descarga datos crudos de una tabla del INE."""
    url = f"{BASE_URL}/DATOS_TABLA/{table_id}"
    resp = requests.get(url, params={"nult": nult}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        raise ValueError(f"Error de la API del INE: {data}")
    return data


def parse_timestamp(ts: int | None) -> pd.Timestamp | None:
    """Convierte timestamp en milisegundos del INE a pandas Timestamp."""
    if ts is None:
        return None
    return pd.Timestamp(ts, unit="ms")
