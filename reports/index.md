# Reportes demográficos — INE

Datos descargados del [Instituto Nacional de Estadística](https://www.ine.es/) (INE).

| Indicador | Reporte | Datos |
|-----------|---------|-------|
| Tasa bruta de natalidad | [natalidad.md](<natalidad.md>) | [`natalidad_ultimo.csv`](<../data/csv/natalidad_ultimo.csv>) |
| Tasa bruta de mortalidad | [mortalidad.md](<mortalidad.md>) | [`mortalidad_ultimo.csv`](<../data/csv/mortalidad_ultimo.csv>) |
| Crecimiento anual por 1.000 hab. | [crecimiento.md](<crecimiento.md>) | [`crecimiento_ultimo.csv`](<../data/csv/crecimiento_ultimo.csv>) |
| Saldo migratorio por 1.000 hab. | [saldo_migratorio.md](<saldo_migratorio.md>) | [`saldo_migratorio_ultimo.csv`](<../data/csv/saldo_migratorio_ultimo.csv>) |
| Porcentaje de población ≥65 años | [pct_65.md](<pct_65.md>) | [`pct_65_ultimo.csv`](<../data/csv/pct_65_ultimo.csv>) |
| Índice de envejecimiento | [envejecimiento.md](<envejecimiento.md>) | [`envejecimiento_ultimo.csv`](<../data/csv/envejecimiento_ultimo.csv>) |
| Tasa de dependencia | [dependencia.md](<dependencia.md>) | [`dependencia_ultimo.csv`](<../data/csv/dependencia_ultimo.csv>) |

## Cómo se generaron

```bash
uv run python scripts/generate_reports.py
```
