# Reportes de datos INE — España en datos

Datos descargados del [Instituto Nacional de Estadística](https://www.ine.es/) (INE).

## Vivienda

| Indicador | Reporte | Datos |
|-----------|---------|-------|
| Índice de Precios de Vivienda (IPV) | [ipv.md](<ipv.md>) | [`ipv_ultimo.csv`](<../data/csv/ipv_ultimo.csv>) |
| Compraventas de viviendas | [compraventas.md](<compraventas.md>) | [`compraventas_ultimo.csv`](<../data/csv/compraventas_ultimo.csv>) |
| Hipotecas constituidas | [hipotecas.md](<hipotecas.md>) | [`hipotecas_ultimo.csv`](<../data/csv/hipotecas_ultimo.csv>) |
| Viviendas turísticas | [viviendas_turisticas.md](<viviendas_turisticas.md>) | [`viviendas_turisticas_ultimo.csv`](<../data/csv/viviendas_turisticas_ultimo.csv>) |
| Índice de Precios de Alquiler | [alquiler.md](<alquiler.md>) | [`alquiler_ultimo.csv`](<../data/csv/alquiler_ultimo.csv>) |
| Inmigración procedente del extranjero | [inmigracion.md](<inmigracion.md>) | [`inmigracion_ultimo.csv`](<../data/csv/inmigracion_ultimo.csv>) |

## Demografía

| Indicador | Reporte | Datos |
|-----------|---------|-------|
| Tasa bruta de natalidad | [natalidad.md](<natalidad.md>) | [`natalidad_ultimo.csv`](<../data/csv/natalidad_ultimo.csv>) |
| Tasa bruta de mortalidad | [mortalidad.md](<mortalidad.md>) | [`mortalidad_ultimo.csv`](<../data/csv/mortalidad_ultimo.csv>) |
| Crecimiento anual por 1.000 hab. | [crecimiento.md](<crecimiento.md>) | [`crecimiento_ultimo.csv`](<../data/csv/crecimiento_ultimo.csv>) |
| Saldo migratorio por 1.000 hab. | [saldo_migratorio.md](<saldo_migratorio.md>) | [`saldo_migratorio_ultimo.csv`](<../data/csv/saldo_migratorio_ultimo.csv>) |
| Porcentaje de población ≥65 años | [pct_65.md](<pct_65.md>) | [`pct_65_ultimo.csv`](<../data/csv/pct_65_ultimo.csv>) |
| Índice de envejecimiento | [envejecimiento.md](<envejecimiento.md>) | [`envejecimiento_ultimo.csv`](<../data/csv/envejecimiento_ultimo.csv>) |
| Tasa de dependencia | [dependencia.md](<dependencia.md>) | [`dependencia_ultimo.csv`](<../data/csv/dependencia_ultimo.csv>) |

## Inmigración

| Indicador | Reporte | Datos |
|-----------|---------|-------|
| Inmigración desde el extranjero | [inmigracion.md](<inmigracion.md>) | [`inmigracion_ultimo.csv`](<../data/csv/inmigracion_ultimo.csv>) |

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
