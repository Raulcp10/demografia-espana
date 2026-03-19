"""Mapeo de provincias y CCAA entre INE y GeoJSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GEOJSON_PATH = Path(__file__).parent.parent.parent / "data" / "provincias.geojson"

# INE name → cod_prov (2-digit string)
INE_NAME_TO_COD_PROV: dict[str, str] = {
    "Almería": "04",
    "Cádiz": "11",
    "Córdoba": "14",
    "Granada": "18",
    "Huelva": "21",
    "Jaén": "23",
    "Málaga": "29",
    "Sevilla": "41",
    "Huesca": "22",
    "Teruel": "44",
    "Zaragoza": "50",
    "Asturias, Principado de": "33",
    "Asturias": "33",
    "Balears, Illes": "07",
    "Palmas, Las": "35",
    "Santa Cruz de Tenerife": "38",
    "Cantabria": "39",
    "Ávila": "05",
    "Burgos": "09",
    "León": "24",
    "Palencia": "34",
    "Salamanca": "37",
    "Segovia": "40",
    "Soria": "42",
    "Valladolid": "47",
    "Zamora": "49",
    "Albacete": "02",
    "Ciudad Real": "13",
    "Cuenca": "16",
    "Guadalajara": "19",
    "Toledo": "45",
    "Barcelona": "08",
    "Girona": "17",
    "Lleida": "25",
    "Tarragona": "43",
    "Alicante/Alacant": "03",
    "Castellón/Castelló": "12",
    "Valencia/València": "46",
    "Badajoz": "06",
    "Cáceres": "10",
    "Coruña, A": "15",
    "Lugo": "27",
    "Ourense": "32",
    "Pontevedra": "36",
    "Madrid, Comunidad de": "28",
    "Madrid": "28",
    "Murcia, Región de": "30",
    "Murcia": "30",
    "Navarra, Comunidad Foral de": "31",
    "Navarra": "31",
    "Araba/Álava": "01",
    "Álava": "01",
    "Bizkaia": "48",
    "Vizcaya": "48",
    "Gipuzkoa": "20",
    "Guipúzcoa": "20",
    "Rioja, La": "26",
    "Rioja (La)": "26",
    "Ceuta": "51",
    "Melilla": "52",
    # Variantes con paréntesis que usa el INE en tablas IDB
    "Balears (Illes)": "07",
    "Coruña (A)": "15",
    "Palmas (Las)": "35",
}

CCAA_TO_PROVINCES: dict[str, list[str]] = {
    "Andalucía": ["04", "11", "14", "18", "21", "23", "29", "41"],
    "Aragón": ["22", "44", "50"],
    "Asturias, Principado de": ["33"],
    "Balears, Illes": ["07"],
    "Canarias": ["35", "38"],
    "Cantabria": ["39"],
    "Castilla y León": ["05", "09", "24", "34", "37", "40", "42", "47", "49"],
    "Castilla - La Mancha": ["02", "13", "16", "19", "45"],
    "Cataluña": ["08", "17", "25", "43"],
    "Comunitat Valenciana": ["03", "12", "46"],
    "Extremadura": ["06", "10"],
    "Galicia": ["15", "27", "32", "36"],
    "Madrid, Comunidad de": ["28"],
    "Murcia, Región de": ["30"],
    "Navarra, Comunidad Foral de": ["31"],
    "País Vasco": ["01", "48", "20"],
    "Rioja, La": ["26"],
    "Ceuta": ["51"],
    "Melilla": ["52"],
}

_MULTI_PROVINCE_CCAA: set[str] = {
    name for name, provs in CCAA_TO_PROVINCES.items() if len(provs) > 1
}

CCAA_NAMES: set[str] = set(CCAA_TO_PROVINCES.keys()) | {"Total Nacional"}

SKIP_TERRITORIES: set[str] = _MULTI_PROVINCE_CCAA | {"Total Nacional"}


def is_province(name: str) -> bool:
    """True si el nombre mapea a una única provincia."""
    if name in SKIP_TERRITORIES:
        return False
    return name in INE_NAME_TO_COD_PROV


@lru_cache
def load_geojson() -> dict:
    """Carga el GeoJSON de provincias."""
    return json.loads(GEOJSON_PATH.read_text())


def get_province_name(cod_prov: str) -> str:
    """Nombre de provincia a partir de su código."""
    geojson = load_geojson()
    for feat in geojson["features"]:
        if feat["properties"]["cod_prov"] == cod_prov:
            return feat["properties"]["name"]
    return cod_prov
