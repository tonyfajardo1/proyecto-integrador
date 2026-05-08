# Esquema estrella propuesto (Avance 2)

Este esquema aterriza el modelo OLAP para analitica y Data Mining, alineado a Medallion (Gold) y a buenas practicas aplicables de PSet2.

## 1) Dimensiones

### `dim_date`
- `date_key` (PK, entero tipo YYYYMMDD)
- `fecha`
- `anio`
- `mes_num`
- `mes_nombre`
- `semana_ano`
- `dia_semana_num`
- `dia_semana_nombre`
- `es_inicio_mes`
- `es_fin_mes`

### `dim_producto`
- `producto_key` (PK)
- `codigo_producto`
- `codigo_alterno`
- `producto`
- `categoria`
- `subcategoria`
- `unidad_medida`
- `activo`

### `dim_agencia`
- `agencia_key` (PK)
- `centro_costo`
- `agencia_nombre`
- `ciudad`
- `region`
- `tipo_agencia`
- `activo`

### `dim_cliente`
- `cliente_key` (PK)
- `idcliente`
- `cliente_nombre`
- `segmento`

### `dim_modelo`
- `modelo_key` (PK)
- `nombre_modelo`
- `version_modelo`
- `fecha_entrenamiento`
- `parametros_json`

## 2) Tablas de hechos

### `fct_ventas`
- `date_key` (FK)
- `producto_key` (FK)
- `agencia_key` (FK)
- `cliente_key` (FK)
- `cant_venta`
- `total_venta`
- `cant_devolucion`
- `total_devolucion`
- `cant_neto`
- `total_neto`
- `costo_venta`
- `rentabilidad`

### `fct_produccion`
- `date_key` (FK)
- `producto_key` (FK)
- `cliente_key` (FK)
- `qty_planificada`
- `qty_despachada`
- `desviacion_absoluta`
- `desviacion_porcentual`
- `tasa_cumplimiento`
- `clasificacion_cumplimiento`

### `fct_pred_devolucion`
- `date_key` (FK)
- `producto_key` (FK)
- `agencia_key` (FK)
- `modelo_key` (FK)
- `probabilidad_devolucion`
- `prediccion_clase`
- `nivel_riesgo`
- `actual_clase` (si existe etiqueta real)

### `fct_anomalias_agencia`
- `date_key` (FK)
- `agencia_key` (FK)
- `modelo_key` (FK)
- `anomaly_score`
- `es_anomalia`
- `tipo_anomalia`
- `severidad`

## 3) Como conecta con tu Medallion actual

- **Silver** sigue siendo capa de integracion/limpieza.
- **Gold** se reorganiza en estrella para consumo analitico.
- Los outputs actuales (`kpis_ventas`, `kpis_produccion`, `predicciones_devolucion`, `anomalias_agencias`) pueden mapearse a `fct_*`.

## 4) Mejores practicas PSet2 aplicables aqui

1. **Idempotencia por periodo**
   - Evitar `replace` global.
   - Cargar por particion (`anio`, `mes`) con `delete+insert` o `merge`.

2. **Quality gates antes de cargar hechos**
   - `not_null` en PK/FK.
   - `accepted_values` en estados.
   - `unique` en claves naturales de dimensiones.

3. **Cobertura de datos por fuente/periodo**
   - Tabla `logs.coverage`: `source`, `periodo`, `status`, `row_count`, `error`.

4. **Observabilidad**
   - `logs.pipeline_ejecuciones` con tiempos y conteos.
   - `logs.calidad_datos` con resultados por regla.

5. **Reproducibilidad de modelos**
   - Registrar `modelo_key`, version, parametros y dataset usado.
