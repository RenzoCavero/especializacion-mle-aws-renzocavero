# 05 - Processing Jobs

El procesamiento cloud del laboratorio se ejecuta con un AWS Glue Python Shell Job.

Este documento explica:

- Que ejecuta el job.
- Como entran los datos.
- Que pasos componen el pipeline.
- Que transforma cada paso.
- Que outputs escribe en S3.
- Como leer ejemplos simples de entrada y salida.
- Como monitorear errores y logs.

## Rol Del Processing Job En El Laboratorio

El Glue Job representa la etapa cloud de preparacion de datos para Machine Learning.

Antes del job ya deben existir:

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
s3://<bucket>/scripts/glue_pipeline.py
s3://<bucket>/scripts/ml_data_prep_src.zip
```

El job toma datos crudos desde `raw/` y produce datasets preparados en:

```text
cleaned/
curated/
features/
inference/
profiles/
quality/
lineage/
reports/
logs/
```

Conceptualmente, este job cumple el rol que en un proyecto real podria resolverse con:

- AWS Glue ETL Job.
- SageMaker Processing Job.
- SageMaker Pipelines.
- Step Functions orquestando varios jobs.

En este laboratorio se usa Glue Python Shell por simplicidad, costo bajo y buena integracion con S3, Glue Data Catalog y CloudWatch Logs.

Los servicios Glue Crawler, Glue Data Quality y Glue Data Catalog Column Statistics se ejecutan como extras opcionales despues del pipeline principal. No forman parte del Glue Python Shell Job porque son capacidades administradas separadas y conviene que el estudiante vea su ejecucion, permisos, costo y outputs de forma explicita. Estan documentados en `lab/10_athena_glue_native_features.md`.

## Como Se Ejecuta

Comando recomendado:

```bash
bash scripts/run_processing_job.sh all
```

Ese script ejecuta localmente:

```bash
python -m src.run_processing_job --steps all
```

`src.run_processing_job` hace tres cosas:

1. Empaqueta y sube el codigo Python de `src/` a S3.
2. Inicia el Glue Job `ml-data-prep-lab-processing-job`.
3. Espera hasta que el job termine en `SUCCEEDED` o falle.

Dentro de AWS Glue se ejecuta:

```text
s3://<bucket>/scripts/glue_pipeline.py
```

`glue_pipeline.py` carga el paquete `src/` desde:

```text
s3://<bucket>/scripts/ml_data_prep_src.zip
```

y llama a:

```text
src.pipeline.run_pipeline
```

## Parametros Que Recibe El Job

El modulo `src.run_processing_job` pasa argumentos al Glue Job:

| Argumento | Ejemplo | Uso |
|---|---|---|
| `--bucket-name` | `ml-data-prep-lab-stack-labbucket-abc123` | Bucket S3 del data lake. |
| `--database-name` | `ml_data_prep_lab` | Base de datos de Glue Catalog. |
| `--resource-prefix` | `ml-data-prep-lab` | Prefijo para recursos y reportes. |
| `--pipeline-steps` | `all` | Pasos del pipeline a ejecutar/escribir. |
| `--run-id` | `20260507T141728Z` | Identificador de ejecucion. |

## Pasos Disponibles

El pipeline reconoce estos pasos:

```text
catalog
profile
quality
process
features
training-dataset
inference-dataset
lineage
dataset-card
```

`all` equivale a ejecutar todos:

```bash
bash scripts/run_processing_job.sh all
```

Tambien puedes ejecutar un paso:

```bash
bash scripts/run_processing_job.sh quality
```

o varios pasos:

```bash
bash scripts/run_processing_job.sh profile,quality,process
```

## Nota Importante Sobre Pasos Parciales

El pipeline siempre lee `raw/` y calcula en memoria las preparaciones necesarias:

```text
raw -> quality -> cleaned -> curated -> features -> training/inference datasets
```

Luego escribe solo los outputs solicitados por `--pipeline-steps`.

Ejemplo:

```bash
bash scripts/run_processing_job.sh quality
```

Aunque solo escriba:

```text
s3://<bucket>/quality/quality_report.json
```

el job igualmente valida estructura y prepara objetos internos para asegurar que la misma logica se mantenga entre pasos.

Si hay fallas `ERROR` en calidad, el pipeline se detiene antes de escribir datasets finales. Las fallas `WARN` se reportan, pero el laboratorio puede continuar porque la limpieza las corrige o las tolera.

Nota: en fallas estructurales muy tempranas, el job puede detenerse antes de publicar `quality_report.json`. En ese caso revisa CloudWatch Logs y el `ErrorMessage` del Glue Job.

## Vista General De Inputs Y Outputs

| Paso | Inputs principales | Transformacion | Outputs |
|---|---|---|---|
| `catalog` | Rutas S3 y esquemas esperados | Registra metadata; no cambia datos | Glue tables |
| `profile` | Raw y datasets preparados en memoria | Calcula estadisticas; no cambia datos | `profiles/profile.json` |
| `quality` | Raw datasets | Evalua reglas; no cambia datos | `quality/quality_report.json` |
| `process` | Raw customers, transactions, inference transactions | Limpieza + integracion + features temporales basicas | `cleaned/`, `curated/` |
| `features` | Curated training e inference | Agregaciones, ratios, flags, one-hot encoding | `features/training_features.csv`, `features/inference_features.csv` |
| `training-dataset` | Training features | Agrega split deterministico y ordena columnas | `features/training_dataset.csv` |
| `inference-dataset` | Inference features | Selecciona contrato sin target | `inference/inference_dataset.csv` |
| `lineage` | Configuracion del pipeline y rutas S3 | Genera trazabilidad; no cambia datasets | `lineage/lineage.json`, `lineage/lineage.md` |
| `dataset-card` | Profile, quality, counts y features | Genera documentacion del dataset | `reports/dataset_card.json`, `reports/dataset_card.md` |

## Paso 1: `catalog`

### Objetivo

Registrar tablas externas en AWS Glue Data Catalog para que las capas del data lake sean descubribles por Glue, Athena, SageMaker y futuros laboratorios.

### Inputs

No lee el contenido completo de los CSV para transformar datos. Usa archivos fuente si existen:

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
s3://<bucket>/cleaned/customers.csv
s3://<bucket>/cleaned/transactions.csv
s3://<bucket>/curated/customer_transactions.csv
s3://<bucket>/features/training_dataset.csv
s3://<bucket>/inference/inference_dataset.csv
```

y los esquemas definidos en:

```text
src/glue_catalog.py
src/schemas.py
```

### Que Hace

- Crea o actualiza tablas Glue.
- Define columnas y tipos.
- Define formato CSV.
- Asocia cada tabla con un prefijo S3 consultable por Athena.
- Si el archivo fuente existe, sincroniza una copia 1:1 bajo el prefijo de tabla.
- Puede registrar metadata antes de que algunos outputs existan fisicamente, por ejemplo `cleaned/` o `features/`.

Es una operacion idempotente:

- Si la tabla no existe, la crea.
- Si existe, la actualiza.

### Outputs

Metadata en Glue Data Catalog:

```text
raw_customers
raw_transactions
raw_inference_transactions
cleaned_customers
cleaned_transactions
curated_customer_transactions
features_training
features_inference
```

### Ejemplo Conceptual

Entrada conceptual:

```text
s3://<bucket>/raw/transactions.csv
```

Tabla resultante:

```text
Database: ml_data_prep_lab
Table: raw_transactions
Location: s3://<bucket>/raw/transactions/
Columns: transaction_id, customer_id, event_time, amount, merchant_category, channel, country, device_type, is_fraud
```

Objeto que Athena lee dentro de ese `Location`:

```text
s3://<bucket>/raw/transactions/transactions.csv
```

El mismo patron aplica a `features_training`:

```text
Archivo simple: s3://<bucket>/features/training_dataset.csv
Location Glue:  s3://<bucket>/features/training_dataset/
Objeto Athena:  s3://<bucket>/features/training_dataset/training_dataset.csv
```

Validar:

```bash
aws glue get-tables --database-name ml_data_prep_lab --profile <profile> --region <region>
```

## Paso 2: `profile`

### Objetivo

Describir la salud y estructura de los datasets.

Profiling no corrige datos y no decide si el pipeline debe parar. Sirve para entender:

- Volumen.
- Columnas.
- Nulos.
- Duplicados.
- Tipos.
- Distribuciones numericas.
- Valores categoricos frecuentes.

### Inputs

Lee y/o usa en memoria:

```text
raw/customers.csv
raw/transactions.csv
raw/inference_transactions.csv
cleaned_customers
cleaned_transactions
features_training
features_inference
```

### Que Hace

Para cada dataset calcula:

```text
row_count
column_count
columns
nulls
dtypes
duplicate_rows
duplicate_keys
numeric_summary
categorical_top_values
```

### Output

```text
s3://<bucket>/profiles/profile.json
```

Si luego ejecutas:

```bash
bash scripts/download_reports.sh
```

lo tendras localmente en:

```text
artifacts/local_outputs/profiles/profile.json
```

### Ejemplo De Lectura

Entrada raw simplificada:

```csv
transaction_id,customer_id,amount,country
T000001,C00010,120.50,PE
T000002,C00011,,US
T000003,C00012,-25.00,BR
T000001,C00010,120.50,PE
```

Salida conceptual en `profile.json`:

```json
{
  "row_count": 4,
  "nulls": {
    "amount": 1
  },
  "duplicate_keys": {
    "transaction_id": 1
  },
  "duplicate_rows": 1,
  "numeric_summary": {
    "amount": {
      "min": -25.0,
      "median": 120.5,
      "max": 120.5
    }
  }
}
```

Interpretacion:

- Hay un monto faltante.
- Hay una transaccion duplicada por `transaction_id`.
- Hay un monto negativo.
- Estos hallazgos deben contrastarse con `quality_report.json` y luego con la capa `cleaned/`.

## Paso 3: `quality`

### Objetivo

Evaluar reglas de calidad sobre los datos raw.

Quality no transforma datos. Produce un reporte de decision:

- `ERROR`: falla critica; el pipeline no debe continuar.
- `WARN`: problema esperado o corregible; el pipeline puede continuar si no hay `ERROR`.

### Inputs

```text
raw/customers.csv
raw/transactions.csv
raw/inference_transactions.csv
```

### Reglas

| Regla | Severidad | Que valida |
|---|---|---|
| `customers_has_expected_columns` | `ERROR` | `customers.csv` tiene columnas obligatorias. |
| `transactions_has_expected_columns` | `ERROR` | `transactions.csv` tiene columnas obligatorias. |
| `inference_transactions_has_expected_columns` | `ERROR` | `inference_transactions.csv` tiene columnas obligatorias. |
| `transaction_ids_are_unique` | `WARN` | IDs historicos no duplicados. |
| `inference_transaction_ids_are_unique` | `ERROR` | IDs de inferencia no duplicados. |
| `transaction_amounts_are_positive` | `WARN` | Montos historicos positivos. |
| `transaction_amounts_not_missing` | `WARN` | Montos historicos no nulos. |
| `transactions_have_customer_id` | `ERROR` | Transacciones tienen `customer_id`. |
| `transactions_reference_known_customers` | `WARN` | Transacciones referencian clientes conocidos. |
| `inference_dataset_has_no_target` | `ERROR` | Inferencia no incluye `is_fraud`. |

### Output

```text
s3://<bucket>/quality/quality_report.json
```

Localmente, despues de descargar:

```text
artifacts/local_outputs/quality/quality_report.json
```

### Ejemplo De Entrada Y Salida

Entrada raw simplificada:

```csv
transaction_id,customer_id,amount,is_fraud
T000001,C00010,120.50,0
T000002,C99999,50.00,1
T000003,C00012,-25.00,0
T000004,C00013,,0
```

Salida conceptual:

```json
{
  "summary": {
    "error_failures": 0,
    "warning_failures": 3,
    "pipeline_can_continue": true
  },
  "rules": [
    {
      "name": "transaction_amounts_are_positive",
      "status": "FAIL",
      "severity": "WARN",
      "details": {
        "invalid_amounts": 1
      }
    },
    {
      "name": "transaction_amounts_not_missing",
      "status": "FAIL",
      "severity": "WARN",
      "details": {
        "missing_amounts": 1
      }
    },
    {
      "name": "transactions_reference_known_customers",
      "status": "FAIL",
      "severity": "WARN",
      "details": {
        "unknown_customer_references": 1
      }
    }
  ]
}
```

Interpretacion:

- Hay problemas en raw.
- Son advertencias.
- El pipeline puede continuar porque `pipeline_can_continue` es `true`.
- La limpieza deberia imputar, filtrar o corregir esos casos.

## Paso 4: `process`

### Objetivo

Construir las capas `cleaned/` y `curated/`.

Este es el primer paso que transforma datos y escribe datasets preparados.

### Inputs

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
```

### Outputs

```text
s3://<bucket>/cleaned/customers.csv
s3://<bucket>/cleaned/transactions.csv
s3://<bucket>/cleaned/inference_transactions.csv
s3://<bucket>/curated/customer_transactions.csv
s3://<bucket>/curated/inference_customer_transactions.csv
```

### Transformaciones De Limpieza

En `src.clean_data`:

Customers:

- Elimina duplicados por `customer_id`.
- Rellena `region` faltante con `unknown`.
- Rellena `segment` faltante con `retail`.
- Rellena `income_band` faltante con `medium`.
- Convierte `age` a numerico.
- Imputa edad faltante con la mediana.
- Limita `age` entre 18 y 90.
- Convierte `risk_score_seed` a numerico.
- Imputa `risk_score_seed` faltante con `0.5`.
- Limita `risk_score_seed` entre 0 y 1.
- Normaliza `signup_date`.

Transactions e inference transactions:

- Elimina duplicados por `transaction_id`.
- Convierte `amount` a numerico.
- Imputa `amount` faltante con la mediana de montos positivos.
- Elimina registros con `amount <= 0`.
- Elimina transacciones con `customer_id` desconocido.
- Rellena `country` faltante con `UNKNOWN`.
- Rellena `merchant_category`, `channel` y `device_type` faltantes con `unknown`.
- Convierte `event_time` a fecha UTC.
- Elimina registros con `event_time` invalido.
- Conserva `is_fraud` solo para historico de entrenamiento.

### Transformaciones De Curacion

En `src.transform_data`:

- Une transacciones con clientes por `customer_id`.
- Agrega atributos de cliente a cada transaccion.
- Calcula antiguedad del cliente:

```text
customer_tenure_days = event_date - signup_date
```

- Extrae hora del evento:

```text
event_hour
```

- Extrae dia de semana:

```text
event_dayofweek
```

- Crea indicador de fin de semana:

```text
is_weekend
```

- Crea indicador nocturno:

```text
is_night
```

- Crea transformacion logaritmica del monto:

```text
amount_log = log1p(amount)
```

### Ejemplo De Limpieza

Entrada raw:

```csv
transaction_id,customer_id,event_time,amount,country,is_fraud
T000001,C00010,2026-01-10T10:00:00+00:00,100.00,PE,0
T000002,C00010,2026-01-11T11:00:00+00:00,,US,1
T000003,C00011,2026-01-12T12:00:00+00:00,-25.00,BR,0
T000004,C99999,2026-01-13T13:00:00+00:00,75.00,CO,0
T000001,C00010,2026-01-10T10:00:00+00:00,100.00,PE,0
```

Salida cleaned conceptual:

```csv
transaction_id,customer_id,event_time,amount,country,is_fraud
T000001,C00010,2026-01-10T10:00:00+0000,100.00,PE,0
T000002,C00010,2026-01-11T11:00:00+0000,100.00,US,1
```

Que paso:

- `T000001` duplicado se conserva solo una vez.
- `T000002` recibe imputacion de `amount` con la mediana positiva.
- `T000003` se elimina por monto negativo.
- `T000004` se elimina porque `C99999` no existe en clientes.

### Ejemplo De Curacion

Entrada cleaned transaction:

```csv
transaction_id,customer_id,event_time,amount,channel,country,is_fraud
T000001,C00010,2026-01-10T10:00:00+0000,100.00,online,PE,0
```

Entrada cleaned customer:

```csv
customer_id,signup_date,segment,region,age,income_band,risk_score_seed
C00010,2025-01-10,retail,lima,35,medium,0.30
```

Salida curated conceptual:

```csv
transaction_id,customer_id,amount,channel,country,segment,age,risk_score_seed,customer_tenure_days,event_hour,event_dayofweek,is_weekend,is_night,amount_log,is_fraud
T000001,C00010,100.00,online,PE,retail,35,0.30,365,10,5,1,0,4.615,0
```

Que cambio:

- La transaccion ahora trae atributos del cliente.
- Se agregan features temporales basicas.
- Se agrega `amount_log`.
- Se mantiene `is_fraud` solo para entrenamiento historico.

## Paso 5: `features`

### Objetivo

Crear variables listas para ML con una logica compartida para entrenamiento e inferencia.

Este paso es clave para evitar training-serving skew.

### Inputs

En memoria desde curated:

```text
curated_training
curated_inference
```

Si el paso `process` ya se escribio, conceptualmente corresponden a:

```text
s3://<bucket>/curated/customer_transactions.csv
s3://<bucket>/curated/inference_customer_transactions.csv
```

### Outputs

```text
s3://<bucket>/features/training_features.csv
s3://<bucket>/features/inference_features.csv
```

### Transformaciones

En `src.feature_engineering`:

Agregaciones por cliente:

```text
customer_txn_count
customer_avg_amount
customer_max_amount
```

Ratios:

```text
amount_to_customer_avg = amount / customer_avg_amount
```

Flags:

```text
high_risk_country = 1 si country esta en US o BR
```

One-hot encoding de categoricas:

```text
channel_atm
channel_card_present
channel_mobile
channel_online
channel_wire
segment_premium
segment_retail
segment_smb
merchant_electronics
merchant_fuel
merchant_grocery
merchant_travel
merchant_utilities
```

Tambien conserva features numericas ya creadas:

```text
amount
amount_log
age
risk_score_seed
customer_tenure_days
event_hour
event_dayofweek
is_weekend
is_night
```

### Ejemplo

Entrada curated simplificada:

```csv
transaction_id,customer_id,amount,amount_log,channel,country,segment,merchant_category,is_fraud
T000001,C00010,100.00,4.615,online,PE,retail,grocery,0
T000002,C00010,200.00,5.303,wire,BR,retail,travel,1
```

Salida features conceptual:

```csv
transaction_id,customer_id,amount,amount_log,customer_txn_count,customer_avg_amount,customer_max_amount,amount_to_customer_avg,high_risk_country,channel_online,channel_wire,segment_retail,merchant_grocery,merchant_travel,is_fraud
T000001,C00010,100.00,4.615,2,150.00,200.00,0.667,0,1,0,1,1,0,0
T000002,C00010,200.00,5.303,2,150.00,200.00,1.333,1,0,1,1,0,1,1
```

Que cambio:

- El cliente `C00010` tiene 2 transacciones.
- Su promedio historico es 150.
- La primera transaccion esta por debajo del promedio.
- La segunda esta sobre el promedio y viene de pais de alto riesgo.
- Las categorias se convierten en columnas numericas binarias.

## Paso 6: `training-dataset`

### Objetivo

Construir el dataset supervisado final para futuros laboratorios de entrenamiento.

### Input

```text
training_features
```

Conceptualmente:

```text
s3://<bucket>/features/training_features.csv
```

### Output

```text
s3://<bucket>/features/training_dataset.csv
```

### Transformacion

En `src.build_training_dataset`:

- Copia las features de entrenamiento.
- Agrega la columna `split`.
- El split se calcula de forma deterministica usando `transaction_id`.

Regla aproximada:

```text
70% train
15% validation
15% test
```

La division es estable: la misma transaccion cae siempre en el mismo split.

### Ejemplo

Entrada:

```csv
transaction_id,customer_id,amount,amount_log,is_fraud
T000001,C00010,100.00,4.615,0
T000002,C00010,200.00,5.303,1
```

Salida conceptual:

```csv
transaction_id,customer_id,amount,amount_log,is_fraud,split
T000001,C00010,100.00,4.615,0,train
T000002,C00010,200.00,5.303,1,validation
```

Que cambio:

- Se conserva `is_fraud` porque entrenamiento necesita target.
- Se agrega `split` para separar entrenamiento, validacion y test.

## Paso 7: `inference-dataset`

### Objetivo

Construir un dataset listo para inferencia batch.

### Input

```text
inference_features
```

Conceptualmente:

```text
s3://<bucket>/features/inference_features.csv
```

### Output

```text
s3://<bucket>/inference/inference_dataset.csv
```

### Transformacion

En `src.build_inference_dataset`:

- Selecciona las mismas columnas predictoras usadas en entrenamiento.
- Excluye `is_fraud`.
- Excluye `split`.
- Mantiene `transaction_id` y `customer_id` para trazabilidad.

### Ejemplo

Entrada inference features:

```csv
transaction_id,customer_id,amount,amount_log,customer_txn_count,high_risk_country,channel_online
I000001,C00010,80.00,4.394,1,0,1
```

Salida inference dataset:

```csv
transaction_id,customer_id,amount,amount_log,customer_txn_count,high_risk_country,channel_online
I000001,C00010,80.00,4.394,1,0,1
```

Que cambio:

- El dataset queda alineado al contrato de features.
- No aparece `is_fraud`, porque en inferencia real no conocemos la respuesta.
- No aparece `split`, porque no aplica a scoring.

## Consistencia Entrenamiento/Inferencia

El pipeline valida el contrato con:

```text
src.feature_engineering.assert_feature_contract
```

La idea:

```text
training_dataset - columnas no predictivas y target = inference_dataset
```

En otras palabras:

- Training tiene `is_fraud`.
- Training tiene `split`.
- Inference no tiene `is_fraud`.
- Inference no tiene `split`.
- Las columnas predictoras deben coincidir.

Esto reduce riesgo de training-serving skew.

## Paso 8: `lineage`

### Objetivo

Documentar trazabilidad del pipeline.

Lineage no transforma datasets. Genera documentacion tecnica sobre:

- Fuentes.
- Capas S3.
- Servicios AWS usados.
- Relacion entre etapas.
- Consistencia de features.

### Inputs

```text
bucket_name
glue_database
resource_prefix
```

Conceptualmente tambien referencia:

```text
raw/
profiles/
quality/
cleaned/
curated/
features/
inference/
```

### Outputs

```text
s3://<bucket>/lineage/lineage.json
s3://<bucket>/lineage/lineage.md
```

### Ejemplo Conceptual

```json
{
  "stage": "features",
  "inputs": ["s3://<bucket>/curated/"],
  "outputs": ["s3://<bucket>/features/", "s3://<bucket>/inference/"],
  "aws_services": ["AWS Glue Job", "Amazon S3"]
}
```

Interpretacion:

- La etapa de features depende de curated.
- Produce datasets para training e inference.
- Corre en Glue y escribe en S3.

## Paso 9: `dataset-card`

### Objetivo

Generar documentacion del dataset preparado para ML.

La dataset card responde:

- Que dataset es.
- Para que se puede usar.
- Para que no se debe usar.
- Que outputs S3 existen.
- Cuantas filas tienen entrenamiento e inferencia.
- Que features contiene.
- Cual es el target.
- Que limitaciones tiene.
- Que consideraciones de seguridad aplican.

### Inputs

```text
profile
quality
training_dataset row count
inference_dataset row count
feature columns
bucket_name
```

### Outputs

```text
s3://<bucket>/reports/dataset_card.json
s3://<bucket>/reports/dataset_card.md
```

### Ejemplo Conceptual

```json
{
  "dataset_name": "fraud_risk_prepared_features",
  "target": "is_fraud",
  "row_counts": {
    "training_dataset": 598,
    "inference_dataset": 120
  },
  "limitations": [
    "Synthetic data does not represent real fraud prevalence."
  ]
}
```

Interpretacion:

- El dataset esta preparado para un problema de clasificacion binaria.
- El target es `is_fraud`.
- Los datos son sinteticos, por lo que no deben interpretarse como distribucion real de fraude.

## Log De Ejecucion En S3

Cada ejecucion escribe:

```text
s3://<bucket>/logs/pipeline_run.json
```

Contiene:

```text
run_id
started_at
finished_at
steps
bucket
database
registered_tables
```

Ejemplo conceptual:

```json
{
  "run_id": "20260507T141728Z",
  "steps": ["catalog", "profile", "quality", "process", "features", "training-dataset", "inference-dataset", "lineage", "dataset-card"],
  "bucket": "ml-data-prep-lab-stack-labbucket-example",
  "database": "ml_data_prep_lab"
}
```

## Orden Recomendado Para Estudiantes

Para entender el pipeline sin gastar demasiado:

1. Ejecutar todo una vez:

   ```bash
   bash scripts/run_processing_job.sh all
   ```

2. Descargar reportes:

   ```bash
   bash scripts/download_reports.sh
   ```

3. Leer:

   ```text
   artifacts/local_outputs/quality/quality_report.json
   artifacts/local_outputs/profiles/profile.json
   artifacts/local_outputs/lineage/lineage.md
   artifacts/local_outputs/reports/dataset_card.md
   ```

4. Comparar en S3:

   ```text
   raw/
   cleaned/
   curated/
   features/
   inference/
   ```

## Comandos Para Revisar Outputs En S3

Listar todo:

```bash
aws s3 ls s3://<bucket>/ --recursive --profile <profile> --region <region>
```

Ver outputs de proceso:

```bash
aws s3 ls s3://<bucket>/cleaned/ --profile <profile> --region <region>
aws s3 ls s3://<bucket>/curated/ --profile <profile> --region <region>
aws s3 ls s3://<bucket>/features/ --profile <profile> --region <region>
aws s3 ls s3://<bucket>/inference/ --profile <profile> --region <region>
```

Descargar un archivo puntual:

```bash
aws s3 cp s3://<bucket>/features/training_dataset.csv artifacts/local_outputs/training_dataset.csv --profile <profile> --region <region>
```

## Logs Operativos

El estado del Glue Job se revisa con:

```bash
aws glue get-job-runs --job-name ml-data-prep-lab-processing-job --profile <profile> --region <region>
```

Logs en CloudWatch:

```bash
aws logs describe-log-groups --log-group-name-prefix /aws --profile <profile> --region <region>
```

Dependiendo de la configuracion de Glue, los mensajes pueden aparecer en:

```text
/aws-glue/python-jobs/output
/aws-glue/python-jobs/error
/aws/ml-data-prep-lab/processing
```

Si el job falla, revisa:

- Estado del job en Glue.
- `ErrorMessage` del job run.
- Log streams de CloudWatch.
- Permisos del rol Glue para S3, Glue Catalog y CloudWatch Logs.
- Existencia de `raw/` y `scripts/` en el bucket.

## Por Que Usar `all`

Para una corrida normal:

```bash
bash scripts/run_processing_job.sh all
```

Ventajas:

- Lanza un solo Glue Job.
- Reduce costo frente a ejecutar cada paso por separado.
- Produce todos los artefactos consistentes en la misma ejecucion.
- Usa el mismo `run_id` para el pipeline.

Usa pasos individuales solo para debug o aprendizaje:

```bash
bash scripts/run_processing_job.sh quality
bash scripts/run_processing_job.sh features
```

## Diseno Productivo: Un Job O Varios Jobs

En este laboratorio se usa un solo Glue Python Shell Job con pasos modulares. Es una decision didactica y de costo:

- Menos recursos que explicar y destruir.
- Menos ejecuciones Glue para estudiantes.
- Un solo `run_id` para producir todos los artefactos.
- Codigo Python separado por responsabilidad, aunque corra en un mismo job.

En produccion, separar el ETL en varios jobs puede ser una buena practica cuando cada etapa tiene contrato, escala o ciclo de vida propio. Una division comun seria:

```text
raw -> cleaned
cleaned -> curated
curated -> features
```

### Cuando Conviene Separar

Separar en tres jobs suele tener sentido si:

- Cada capa tiene una salida reutilizable por equipos distintos.
- Raw-to-cleaned necesita reglas de calidad, deduplicacion o normalizacion independientes.
- Cleaned-to-curated hace joins pesados, enriquecimiento o cambia de granularidad.
- Curated-to-features pertenece al dominio ML y debe evolucionar con entrenamiento, inferencia o Feature Store.
- Cada etapa requiere diferente capacidad, timeout, dependencias o permisos IAM.
- Quieres reintentar solo una etapa sin recalcular todo.
- Quieres orquestar dependencias como grafo con AWS Glue Workflows, Glue Triggers, Step Functions o SageMaker Pipelines.

### Cuando No Conviene Separar Todavia

No conviene dividir por dividir si:

- El dataset es pequeno.
- Todas las etapas usan la misma capacidad y el mismo equipo las mantiene.
- El costo de arranque de multiples jobs domina el tiempo real de procesamiento.
- La orquestacion agrega mas complejidad que valor para el objetivo pedagogico.
- Aun estas prototipando el contrato de datos.

### Patron Recomendado Para Produccion

Una arquitectura mas productiva podria verse asi:

| Etapa | Servicio | Input | Output | Gate recomendado |
|---|---|---|---|---|
| Catalogacion raw | Glue Crawler o tablas explicitas | `raw/` | Glue tables raw | Schema esperado |
| Calidad raw | Glue Data Quality o reglas en job | Tablas raw | Reporte DQ | Bloquear si hay errores criticos |
| Raw to cleaned | Glue ETL Job | `raw/` | `cleaned/` en Parquet | Datos corregidos y deduplicados |
| Cleaned to curated | Glue ETL Job | `cleaned/` | `curated/` en Parquet | Joins, tipos y reglas de negocio |
| Curated to features | Glue Job, SageMaker Processing o Feature Store ingest | `curated/` | `features/` / Feature Store offline | Contrato training/inference |
| Consumo | Athena, SageMaker Training, Batch Inference | `curated/`, `features/`, `inference/` | Modelos o predicciones | Validacion y lineage |

Buenas practicas para esa version:

- Escribir capas procesadas en formato columnar como Parquet u ORC para reducir escaneo y mejorar rendimiento.
- Mantener jobs idempotentes: reejecutar una etapa no debe duplicar outputs.
- Usar particiones por fecha, fuente o batch cuando el volumen lo justifique.
- Aplicar calidad antes de publicar cada capa importante.
- Usar IAM de minimo privilegio por etapa si los equipos o permisos difieren.
- Emitir logs y metricas por etapa en CloudWatch.
- Orquestar dependencias con Glue Workflows o Step Functions si hay varios jobs.
- Para cargas incrementales, evaluar Glue Job Bookmarks y particiones.

Decision del laboratorio: no implementar tres Glue Jobs todavia. El codigo ya esta modularizado por etapas y el parametro `--pipeline-steps` permite ensenar los limites logicos sin multiplicar infraestructura ni costo. Una extension futura puede convertir estos pasos en jobs separados y orquestarlos como DAG.

Referencias AWS utiles para esta decision:

- AWS Glue Data Catalog y Crawlers: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
- AWS Glue Data Quality: https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html
- AWS Glue Workflows: https://docs.aws.amazon.com/glue/latest/dg/workflows_overview.html
- AWS Glue Triggers: https://docs.aws.amazon.com/glue/latest/dg/about-triggers.html
- AWS Prescriptive Guidance para ETL serverless con Glue: https://docs.aws.amazon.com/prescriptive-guidance/latest/serverless-etl-aws-glue/best-practices.html

## Troubleshooting

### Error `No module named 'src'`

Si ves:

```text
Glue job failed with state=FAILED: ModuleNotFoundError: No module named 'src'
```

significa que Glue inicio `glue_pipeline.py`, pero no encontro el paquete del proyecto dentro del entorno Python del job.

El laboratorio incluye una proteccion en `src/glue_pipeline.py`: si `src` no esta disponible, descarga automaticamente:

```text
s3://<bucket>/scripts/ml_data_prep_src.zip
```

lo agrega a `sys.path` y continua la ejecucion.

Para aplicar esa correccion no hace falta recrear CloudFormation. Vuelve a ejecutar:

```bash
bash scripts/run_processing_job.sh all
```

Ese comando sube de nuevo `glue_pipeline.py` y `ml_data_prep_src.zip` antes de lanzar el Glue Job.

### Error Por Falta De Datos Raw

Sintoma:

```text
NoSuchKey: raw/customers.csv
```

Accion:

```bash
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
```

### Error Por Permisos S3

Sintoma:

```text
AccessDenied
```

Accion:

- Revisar que el Glue execution role pueda leer `raw/` y `scripts/`.
- Revisar que pueda escribir `cleaned/`, `curated/`, `features/`, `inference/`, `profiles/`, `quality/`, `lineage/`, `reports/` y `logs/`.

### Error Por Calidad Critica

Sintoma:

```text
Data quality ERROR rules failed. See quality report for details.
```

Accion:

- Revisar `quality_report.json` si fue escrito.
- Si el archivo no existe, revisar CloudWatch Logs y el `ErrorMessage` del Glue Job.
- Buscar reglas con `severity=ERROR` y `status=FAIL`.
- Corregir datos raw o esquemas antes de reintentar.
