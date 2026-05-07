# 04 - Data Quality Y Profiling

El profiling mide la salud del dataset antes de entrenar:

- Conteo de filas y columnas.
- Nulos.
- Duplicados.
- Tipos de datos.
- Resumen numerico.
- Valores categoricos frecuentes.

Las reglas de calidad revisan:

- Columnas requeridas.
- Duplicados.
- Montos invalidos.
- Referencias a clientes existentes.
- Separacion correcta del target en inferencia.

Comandos:

```bash
make profile
make quality
```

Outputs:

```text
s3://<bucket>/profiles/profile.json
s3://<bucket>/quality/quality_report.json
```

## Diferencia Entre Profiling Y Calidad

Profiling describe el dataset. Responde preguntas como:

- Cuantas filas y columnas tiene cada archivo.
- Que columnas tienen nulos.
- Que tipos de datos aparecen.
- Cuales son los valores frecuentes.
- Como se distribuyen las variables numericas.

Calidad evalua reglas. Responde preguntas como:

- El dataset puede continuar hacia features.
- Faltan columnas obligatorias.
- Hay montos invalidos.
- Hay transacciones duplicadas.
- Hay transacciones con clientes inexistentes.
- El dataset de inferencia excluye correctamente el target.

## Ejecutar En AWS

Para una ejecucion completa y eficiente:

```bash
bash scripts/run_processing_job.sh all
```

Para ejecutar solo estos pasos, sabiendo que cada comando lanza un Glue Job:

```bash
bash scripts/run_processing_job.sh profile
bash scripts/run_processing_job.sh quality
```

Para ejecutar ambos en un solo Glue Job:

```bash
bash scripts/run_processing_job.sh profile,quality
```

## Como Leer Los Reportes

Despues de descargar reportes:

```bash
bash scripts/download_reports.sh
```

revisa:

```text
artifacts/local_outputs/profiles/profile.json
artifacts/local_outputs/quality/quality_report.json
```

Si la calidad falla con reglas criticas, el pipeline debe detenerse antes de producir datasets finales. Esto simula una practica real de ML: no entrenar modelos con datasets que incumplen reglas basicas.

## Como Leer `profile.json`

Archivo local:

```text
artifacts/local_outputs/profiles/profile.json
```

Este archivo describe el estado de cada dataset observado por el pipeline. No decide si el pipeline debe parar; sirve para inspeccionar volumen, estructura, nulos, duplicados, tipos de datos y distribuciones.

Estructura principal:

```text
generated_at
datasets
  customers
  transactions
  inference_transactions
  cleaned_customers
  cleaned_transactions
  features_training
  features_inference
```

Cada dataset contiene:

| Campo | Como leerlo |
|---|---|
| `row_count` | Numero de filas del dataset. |
| `column_count` | Numero de columnas. |
| `columns` | Lista de columnas disponibles. |
| `nulls` | Conteo de valores nulos por columna. |
| `dtypes` | Tipo detectado por pandas para cada columna. |
| `duplicate_rows` | Numero de filas completamente duplicadas. |
| `duplicate_keys` | Duplicados en columnas clave, como `transaction_id` o `customer_id`. |
| `numeric_summary` | Minimo, maximo, promedio, mediana, desviacion y p95 para columnas numericas. |
| `categorical_top_values` | Valores categoricos mas frecuentes por columna. |

### Ejemplo 1: Ver Datasets Disponibles

PowerShell:

```powershell
$profile = Get-Content artifacts/local_outputs/profiles/profile.json -Raw | ConvertFrom-Json
$profile.datasets.PSObject.Properties.Name
```

Python:

```bash
python -c "import json; p=json.load(open('artifacts/local_outputs/profiles/profile.json')); print(list(p['datasets']))"
```

Resultado esperado conceptual:

```text
customers
transactions
inference_transactions
cleaned_customers
cleaned_transactions
features_training
features_inference
```

### Ejemplo 2: Revisar Filas, Columnas Y Nulos De Transacciones Raw

PowerShell:

```powershell
$tx = $profile.datasets.transactions
$tx.row_count
$tx.column_count
$tx.nulls
```

Python:

```bash
python -c "import json; p=json.load(open('artifacts/local_outputs/profiles/profile.json')); tx=p['datasets']['transactions']; print(tx['row_count'], tx['column_count']); print(tx['nulls'])"
```

Interpretacion:

- `row_count` indica cuantas transacciones raw llegaron al data lake.
- `nulls.amount > 0` indica montos faltantes.
- `nulls.country > 0` indica transacciones sin pais.
- Estos problemas son esperados en los datos sinteticos raw y deben corregirse en la capa `cleaned/`.

### Ejemplo 3: Detectar Duplicados En La Clave

PowerShell:

```powershell
$profile.datasets.transactions.duplicate_keys
$profile.datasets.transactions.duplicate_rows
```

Python:

```bash
python -c "import json; p=json.load(open('artifacts/local_outputs/profiles/profile.json')); tx=p['datasets']['transactions']; print(tx['duplicate_keys']); print(tx['duplicate_rows'])"
```

Interpretacion:

- `duplicate_keys.transaction_id > 0` significa que hay IDs de transaccion repetidos.
- `duplicate_rows > 0` significa que hay filas exactamente duplicadas.
- En datos raw esto puede ser una alerta. En `cleaned_transactions` deberia ser `0`.

### Ejemplo 4: Leer Distribucion Numerica De `amount`

PowerShell:

```powershell
$profile.datasets.transactions.numeric_summary.amount
```

Python:

```bash
python -c "import json; p=json.load(open('artifacts/local_outputs/profiles/profile.json')); print(p['datasets']['transactions']['numeric_summary']['amount'])"
```

Interpretacion:

- `min <= 0` sugiere montos invalidos.
- `max` muy alto frente a `median` puede indicar outliers.
- `p95` muestra un valor alto pero menos extremo que `max`, util para entender cola de distribucion.

Ejemplo conceptual:

```text
min: -25.0
median: 64.62
p95: 283.87
max: 10468.36
```

Lectura:

- Hay al menos un monto invalido negativo.
- La mayoria de transacciones esta muy por debajo del maximo.
- El maximo podria ser un caso de alto riesgo, outlier o dato a revisar.

### Ejemplo 5: Comparar Raw Vs Cleaned

PowerShell:

```powershell
$profile.datasets.transactions.nulls.amount
$profile.datasets.cleaned_transactions.nulls.amount
$profile.datasets.transactions.duplicate_rows
$profile.datasets.cleaned_transactions.duplicate_rows
```

Python:

```bash
python -c "import json; p=json.load(open('artifacts/local_outputs/profiles/profile.json')); print('raw_null_amount=', p['datasets']['transactions']['nulls']['amount']); print('cleaned_null_amount=', p['datasets']['cleaned_transactions']['nulls']['amount']); print('raw_duplicates=', p['datasets']['transactions']['duplicate_rows']); print('cleaned_duplicates=', p['datasets']['cleaned_transactions']['duplicate_rows'])"
```

Interpretacion:

- Si `transactions` tiene nulos o duplicados y `cleaned_transactions` queda en `0`, la limpieza funciono.
- Si los problemas siguen en `cleaned_transactions`, hay que revisar `src/clean_data.py`.

## Como Leer `quality_report.json`

Archivo local:

```text
artifacts/local_outputs/quality/quality_report.json
```

Este archivo evalua reglas de calidad. A diferencia del profiling, aqui si hay una decision operativa: si una regla `ERROR` falla, el pipeline no deberia continuar.

Estructura principal:

```text
generated_at
summary
rules
notes
```

Campos importantes de `summary`:

| Campo | Como leerlo |
|---|---|
| `total_rules` | Numero total de reglas ejecutadas. |
| `passed` | Reglas que pasaron. |
| `failed` | Reglas que fallaron. |
| `error_failures` | Fallas criticas. Debe ser `0` para continuar. |
| `warning_failures` | Fallas no criticas, esperadas en datos sinteticos raw. |
| `pipeline_can_continue` | `true` si no hay fallas `ERROR`. |

Cada elemento de `rules` contiene:

| Campo | Como leerlo |
|---|---|
| `name` | Nombre de la regla. |
| `status` | `PASS` o `FAIL`. |
| `severity` | `ERROR` o `WARN`. |
| `details` | Conteos o evidencia de la regla. |

### Ejemplo 1: Leer Resumen De Calidad

PowerShell:

```powershell
$quality = Get-Content artifacts/local_outputs/quality/quality_report.json -Raw | ConvertFrom-Json
$quality.summary
```

Python:

```bash
python -c "import json; q=json.load(open('artifacts/local_outputs/quality/quality_report.json')); print(q['summary'])"
```

Ejemplo conceptual:

```text
total_rules: 10
passed: 6
failed: 4
error_failures: 0
warning_failures: 4
pipeline_can_continue: true
```

Interpretacion:

- Hay reglas fallidas, pero son `WARN`.
- No hay fallas `ERROR`.
- El pipeline puede continuar porque `pipeline_can_continue` es `true`.

### Ejemplo 2: Listar Solo Reglas Fallidas

PowerShell:

```powershell
$quality.rules | Where-Object { $_.status -eq "FAIL" } | Select-Object name,severity,details
```

Python:

```bash
python -c "import json; q=json.load(open('artifacts/local_outputs/quality/quality_report.json')); [print(r['name'], r['severity'], r['details']) for r in q['rules'] if r['status']=='FAIL']"
```

Ejemplo conceptual:

```text
transaction_ids_are_unique WARN {'duplicate_transaction_ids': 1}
transaction_amounts_are_positive WARN {'invalid_amounts': 1}
transaction_amounts_not_missing WARN {'missing_amounts': 1}
transactions_reference_known_customers WARN {'unknown_customer_references': 1}
```

Interpretacion:

- Hay una transaccion duplicada.
- Hay un monto invalido.
- Hay un monto faltante.
- Hay una referencia a cliente inexistente.
- Como son `WARN`, el laboratorio permite continuar y espera que la capa `cleaned/` corrija estos problemas.

### Ejemplo 3: Revisar Si El Pipeline Puede Continuar

PowerShell:

```powershell
$quality.summary.pipeline_can_continue
```

Python:

```bash
python -c "import json; q=json.load(open('artifacts/local_outputs/quality/quality_report.json')); print(q['summary']['pipeline_can_continue'])"
```

Interpretacion:

- `true`: no hay fallas criticas. El pipeline puede construir `cleaned/`, `curated/`, `features/` e `inference/`.
- `false`: hay al menos una falla `ERROR`. Se debe revisar `rules` antes de continuar.

### Ejemplo 4: Distinguir `WARN` De `ERROR`

`WARN` significa que el dato tiene problemas, pero el pipeline puede corregirlos o tolerarlos para fines del laboratorio. Ejemplos:

- Duplicados raw.
- Montos faltantes.
- Montos invalidos.
- Clientes desconocidos.

`ERROR` significa que el dataset no es estructuralmente seguro para continuar. Ejemplos:

- Falta una columna obligatoria.
- El dataset de inferencia trae `is_fraud`.
- Faltan IDs de cliente en transacciones.
- Hay IDs duplicados en inferencia.

Regla practica:

```text
Si error_failures > 0, detener y corregir.
Si warning_failures > 0 pero error_failures = 0, revisar y confirmar que cleaned/ corrige.
```

## Lectura Recomendada Para El Estudiante

1. Abrir primero `quality_report.json` y revisar `summary.pipeline_can_continue`.
2. Si es `false`, revisar reglas `ERROR` fallidas.
3. Si es `true`, revisar reglas `WARN` para entender que problemas raw fueron detectados.
4. Abrir `profile.json` y comparar `transactions` contra `cleaned_transactions`.
5. Confirmar que `features_training` y `features_inference` no tienen nulos inesperados.
6. Confirmar que `features_training` tiene `is_fraud`, pero `features_inference` no.
