# 04 - SageMaker Processing Jobs

## Objetivo

Ejecutar la materializacion de datos en SageMaker Processing para producir datasets reproducibles de entrenamiento, validacion y test desde el Offline Store.

En este laboratorio ya usaste un Processing Job en el paso 03 para ingestar `curated/` hacia Feature Store. En este paso usas otro Processing Job con un proposito distinto: leer el historial del Offline Store y construir los archivos finales que consumen Training Jobs y HPO.

## Que vas a construir o validar

Vas a crear un Processing Job con nombre similar a:

```text
ml-training-opt-lab-processing-<timestamp>-<instance>
```

El job materializa features desde el Offline Store de SageMaker Feature Store y genera:

| Salida | Ruta S3 |
|---|---|
| Train | `s3://<S3_BUCKET>/input/train/train.csv` |
| Validation | `s3://<S3_BUCKET>/input/validation/validation.csv` |
| Test | `s3://<S3_BUCKET>/input/test/test.csv` |
| Metadata | `s3://<S3_BUCKET>/processing/output/metadata/preprocessing_metadata.json` |

## Conceptos clave

- Processing Job: job gestionado de SageMaker para preparar datos o ejecutar procesamiento batch.
- Canal de entrada: ruta S3 o codigo que SageMaker monta dentro del contenedor.
- Output de procesamiento: directorio del contenedor que SageMaker copia a S3.
- One-hot encoding: conversion de variables categoricas a columnas numericas.
- Athena materialization: consulta SQL que lee el Offline Store registrado en AWS Glue Data Catalog y escribe el resultado como CSV temporal en S3.

Materializar con Athena significa convertir una consulta logica sobre una tabla en un archivo fisico de resultado. En este laboratorio, el Processing Job no lee directamente todos los Parquet del Offline Store. Primero ejecuta una query en Athena, Athena deja el resultado en:

```text
s3://<S3_BUCKET>/athena/query-results/
```

Luego el Processing Job descarga ese resultado como:

```text
/opt/ml/processing/input/offline_store_features.csv
```

Desde ese CSV temporal se aplican las transformaciones de entrenamiento.

## Glue Data Catalog y tablas del Offline Store

El laboratorio no crea manualmente la base de datos de Glue. La crea SageMaker Feature Store cuando el Feature Group se configura con Offline Store y con creacion de tabla Glue habilitada.

En `src/create_feature_group.py`, el Feature Group se crea con:

```python
"OfflineStoreConfig": {
    "S3StorageConfig": ...,
    "DisableGlueTableCreation": False,
}
```

Ese parametro le indica a SageMaker Feature Store:

1. Escribe los registros historicos del Offline Store en S3.
2. Registra una tabla en AWS Glue Data Catalog.
3. Usa la base de datos `sagemaker_featurestore`.

La base `sagemaker_featurestore` es compartida por la cuenta y region. Por eso puedes ver muchas tablas:

- Tablas `churn_customer_features_*`: creaciones o recreaciones del Feature Group de este laboratorio.
- Tablas de otros laboratorios o proyectos: Feature Groups creados por otros flujos, por ejemplo `ml_deploy_lab_*`.

Cada tabla suele incluir un sufijo porque AWS necesita nombres unicos cuando se recrea un Feature Group. Para saber que tabla usa el Feature Group activo, ejecuta:

```bash
aws sagemaker describe-feature-group \
  --feature-group-name churn-customer-features \
  --region <AWS_REGION> \
  --query "OfflineStoreConfig.DataCatalogConfig"
```

El resultado incluye `Database`, `TableName` y `Catalog`.

## Dos usos de Processing Jobs en este laboratorio

| Paso | Job | Entrada principal | Salida principal | Proposito |
|---|---|---|---|---|
| 03 | `ml-training-opt-lab-feature-ingestion-*` | `s3://<S3_BUCKET>/curated/churn_features.csv` | Feature Store Online/Offline Store | Actualizar el Feature Group desde datos curados. |
| 04 | `ml-training-opt-lab-processing-*` | Feature Store Offline Store via Athena | `train.csv`, `validation.csv`, `test.csv` | Crear datasets versionables para entrenamiento. |

La separacion es intencional. Primero se publica la feature en Feature Store. Luego se materializa el Offline Store para training. Esto evita que el Training Job dependa de una lectura directa a Feature Store y permite reproducir datasets historicos.

## Uso batch vs streaming

Un SageMaker Processing Job se puede reutilizar para mantener Feature Store actualizado cuando el patron es batch o micro-batch. Por ejemplo:

1. Llegan archivos nuevos a S3 cada hora o cada dia.
2. Un scheduler o event trigger lanza un Processing Job.
3. El job lee los datos nuevos.
4. Aplica transformaciones de features.
5. Ingiere records en SageMaker Feature Store con `PutRecord`.
6. Feature Store actualiza Online Store y escribe historico en Offline Store.

Arquitectura batch o micro-batch:

```text
Raw data in S3
    |
    v
SageMaker Processing Job
    |
    v
Feature transformations
    |
    v
PutRecord to SageMaker Feature Store
    |
    +--> Online Store
    +--> Offline Store
```

Para streaming real de baja latencia, un Processing Job no suele ser la mejor opcion porque es un job efimero: arranca infraestructura, descarga inputs, ejecuta codigo y termina. Para eventos continuos conviene usar un componente event-driven o always-on, por ejemplo:

```text
Application events
    |
    v
Amazon Kinesis Data Streams or Amazon MSK
    |
    v
Stream processor
    |-- AWS Lambda for simple/stateless transforms
    |-- Managed Service for Apache Flink for windowed/stateful transforms
    |
    v
PutRecord to SageMaker Feature Store
    |
    +--> Online Store
    +--> Offline Store
```

En este paso, el Processing Job prepara datasets de entrenamiento:

```text
Feature Store Offline Store -> Athena -> one-hot encoding -> train/validation/test CSVs
```

Esto significa:

1. Feature Store Offline Store conserva el historial de features en S3.
2. AWS Glue Data Catalog expone ese historial como tabla.
3. Amazon Athena ejecuta SQL sobre esa tabla.
4. El Processing Job descarga el resultado materializado de Athena.
5. El Processing Job transforma categorias a columnas numericas.
6. El Processing Job separa `train.csv`, `validation.csv` y `test.csv`.

El codigo mantiene un snapshot CSV como respaldo para cuentas de estudiante donde el Offline Store tarde en estar disponible:

```text
s3://<S3_BUCKET>/processing/input/churn_features.csv
```

La fuente principal se controla con estas variables:

| Variable | Uso |
|---|---|
| `FEATURE_DATA_SOURCE=offline_store` | Usa Offline Store como fuente principal del dataset. |
| `ALLOW_FEATURE_SNAPSHOT_FALLBACK=true` | Permite usar el snapshot CSV si Athena/Offline Store aun no devuelve filas. |
| `OFFLINE_STORE_MAX_WAIT_SECONDS=900` | Tiempo maximo de espera para que el Offline Store este consultable. |
| `OFFLINE_STORE_POLL_SECONDS=60` | Intervalo entre reintentos. |

Este enfoque es util cuando necesitas reconstruir datasets historicos, evitar leakage temporal y entrenar con datos particionados por `event_time`. La salida final para entrenamiento sigue siendo S3; SageMaker Training Jobs y HPO consumen canales de entrada en S3, no consultas directas a Feature Store.

El actualizador batch de Feature Store ya esta representado por el paso 03. Para streaming real, un Processing Job sigue sin ser la mejor opcion porque arranca infraestructura por ejecucion. En una arquitectura productiva, separa:

1. Logica compartida de feature engineering.
2. Logica exclusiva de entrenamiento, como split train/test y manejo del label.
3. Logica de actualizacion online, que transforma eventos recientes y llama `PutRecord`.

## Consulta Athena usada por el Processing Job

El codigo remoto que ejecuta la consulta esta en `processing/processing_entrypoint.py`, funcion `_offline_store_query`.

La consulta que usa el laboratorio es:

```sql
WITH ranked_features AS (
    SELECT
        "customer_id",
        "event_time",
        "age_days",
        "sessions_last_7d",
        "sessions_last_30d",
        "avg_session_duration_last_30d",
        "support_tickets_last_30d",
        "payment_failures_last_90d",
        "days_since_last_login",
        "engagement_score",
        "plan_type",
        "country",
        "device_type",
        "churn_label",
        row_number() OVER (
            PARTITION BY "customer_id"
            ORDER BY "event_time" DESC
        ) AS row_num
    FROM "<DATABASE>"."<TABLE_NAME>"
    WHERE "customer_id" IS NOT NULL
      AND "event_time" IS NOT NULL
)
SELECT
    "customer_id",
    "event_time",
    "age_days",
    "sessions_last_7d",
    "sessions_last_30d",
    "avg_session_duration_last_30d",
    "support_tickets_last_30d",
    "payment_failures_last_90d",
    "days_since_last_login",
    "engagement_score",
    "plan_type",
    "country",
    "device_type",
    "churn_label"
FROM ranked_features
WHERE row_num = 1
```

`<DATABASE>` y `<TABLE_NAME>` no se escriben a mano. El Processing Job los obtiene llamando:

```text
DescribeFeatureGroup -> OfflineStoreConfig.DataCatalogConfig
```

El job envia la query a Athena con:

```python
athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={"Database": database},
    ResultConfiguration={"OutputLocation": athena_output_s3_uri},
)
```

`athena_output_s3_uri` viene de la configuracion del laboratorio y apunta al prefijo `athena/query-results/` del bucket.

### Que filas selecciona y por que

La parte importante es:

```sql
row_number() OVER (
    PARTITION BY "customer_id"
    ORDER BY "event_time" DESC
) AS row_num
```

Esta ventana asigna `row_num = 1` al registro mas reciente de cada `customer_id`. Luego el filtro:

```sql
WHERE row_num = 1
```

deja una sola fila por cliente.

El laboratorio usa esa regla porque entrena un modelo simple de churn con un snapshot actual por cliente:

```text
1 cliente -> 1 fila de entrenamiento
```

En produccion, si tienes labels por fecha, lo correcto suele ser una consulta point-in-time:

```text
tomar las features disponibles antes de label_date
```

La sample query de SageMaker Studio en `Feature Store > Sample queries > Time travel` sigue esa idea. Normalmente incluye condiciones como:

```sql
WHERE "event_time" <= TIMESTAMP '<timestamp>'
```

y ordena tambien por metadatos internos como `Api_Invocation_Time` y `write_time`.

La query del laboratorio es mas simple:

- No usa un timestamp de corte.
- No consulta todos los metadatos internos del Offline Store.
- Toma el ultimo registro por `customer_id`.
- Es suficiente para explicar materializacion, transformacion y split de entrenamiento.

Si quieres hacer entrenamiento point-in-time real, adapta la query para usar `label_date` o un timestamp de corte.

## Por que usar Athena en lugar de leer archivos S3 directamente

Si, tecnicamente puedes leer los archivos fisicos que Feature Store escribe en S3 bajo:

```text
s3://<S3_BUCKET>/feature-store-offline/
```

Pero para el laboratorio y para produccion suele ser mejor consultar la tabla de Glue con Athena, Spark o un motor que entienda catalogo y particiones.

Leer directamente los objetos de S3 puede ser fragil porque:

- El Offline Store escribe archivos particionados por fecha/hora.
- Puede haber multiples archivos para el mismo Feature Group.
- Puede haber varias versiones de un mismo `customer_id`.
- Puedes leer una tabla antigua si el Feature Group fue recreado.
- Debes resolver manualmente schema, particiones y deduplicacion temporal.

Athena aporta ventajas:

| Beneficio | Explicacion |
|---|---|
| Usa el Glue Data Catalog | Lee la tabla correcta registrada por Feature Store. |
| Entiende particiones | Evita recorrer manualmente carpetas `year=`, `month=`, `day=`, `hour=`. |
| Permite SQL | Puedes filtrar, deduplicar, hacer ventanas, joins y time travel. |
| Facilita reproducibilidad | La query queda documentada y puede versionarse. |
| Escala mejor que leer archivos sueltos | Athena ejecuta la lectura de forma distribuida sobre S3. |

La idea no es que S3 sea incorrecto. S3 es el almacenamiento fisico. Athena es la capa de consulta que hace que ese almacenamiento sea usable como tabla historica.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 01, 02 y 03.

3. Confirma que existe el Feature Group y que el Offline Store esta habilitado:

   ```bash
   aws sagemaker describe-feature-group \
     --feature-group-name churn-customer-features \
     --region <AWS_REGION>
   ```

4. Confirma que el snapshot de respaldo existe. Este archivo se genera desde `curated/` en el paso 02:

   ```text
   s3://<S3_BUCKET>/processing/input/churn_features.csv
   ```

5. Confirma que `PROCESSING_INSTANCE_TYPE` y `PROCESSING_INSTANCE_TYPE_FALLBACKS` estan definidos en `.env`.

6. Si actualizaste el repositorio despues de crear el stack, reejecuta el paso 01 para aplicar permisos de Athena:

   ```bash
   bash scripts/lab.sh step 01
   ```

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-04-processing
```

Con Bash o Git Bash:

```bash
bash scripts/run_processing_job.sh
```

En Windows PowerShell:

```powershell
.\scripts\run_processing_job.ps1
```

Con Python:

```bash
python -m src.submit_processing_job
```

Internamente:

1. `src.submit_processing_job` crea un `SKLearnProcessor`.
2. Usa la imagen administrada `sklearn` version `1.2-1`.
3. Sube `processing/processing_entrypoint.py` como codigo del job.
4. Monta `processing/` en `/opt/ml/processing/lib`.
5. Monta `s3://<S3_BUCKET>/processing/input/churn_features.csv` como fallback en `/opt/ml/processing/input`. Ese snapshot viene de `curated/churn_features.csv`.
6. Ejecuta `processing/processing_entrypoint.py`.
7. El entrypoint consulta el Feature Group, obtiene la tabla Glue del Offline Store y lanza una consulta Athena.
8. La consulta Athena selecciona el registro mas reciente por `customer_id` ordenando por `event_time`.
9. El job transforma el dataset, separa train/validation/test y escribe outputs en S3.
10. Descarga `preprocessing_metadata.json` a `artifacts/local_outputs/`.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/run_processing_job.sh` |
| Wrapper PowerShell | `scripts/run_processing_job.ps1` |
| Modulo que envia el job a SageMaker | `src/submit_processing_job.py` |
| Codigo remoto ejecutado en el Processing Job | `processing/processing_entrypoint.py` |
| Librerias auxiliares montadas en el contenedor | `processing/` |
| Fuente principal de features | SageMaker Feature Store Offline Store via AWS Glue Data Catalog y Amazon Athena |
| Snapshot de respaldo | `s3://<S3_BUCKET>/processing/input/churn_features.csv` |

## Scripts y parametros principales

| Necesidad | Archivo |
|---|---|
| Cambiar como se envia el Processing Job | `src/submit_processing_job.py` |
| Cambiar la query Athena contra Offline Store | `processing/processing_entrypoint.py` |
| Cambiar columnas usadas para entrenar | `processing/utils.py` |
| Cambiar one-hot encoding | `processing/utils.py`, funcion `prepare_model_frame` |
| Cambiar split train/validation/test | `processing/processing_entrypoint.py` |
| Cambiar instancia o fallbacks de Processing | `.env`, `.env.example`, `src/config.py` |
| Cambiar rutas S3 de outputs `input/train`, `input/validation`, `input/test` | `src/config.py` |
| Ver workflow completo | `lab/14_workflow_and_scripts_reference.md` |

## Resultado esperado

La terminal debe mostrar un mensaje similar a:

```text
Materialized 1200 latest feature records from Feature Store Offline Store using Athena table ...
Prepared train=720 validation=240 test=240
Processing Job submitted: <job-name> on <instance-type>
```

Si el Offline Store aun no esta consultable y `ALLOW_FEATURE_SNAPSHOT_FALLBACK=true`, puedes ver:

```text
Falling back to feature snapshot CSV because Offline Store materialization failed.
Prepared train=720 validation=240 test=240
```

Archivos locales:

```text
artifacts/local_outputs/preprocessing_metadata.json
artifacts/local_outputs/run_state.json
```

S3:

```text
s3://<S3_BUCKET>/input/train/train.csv
s3://<S3_BUCKET>/input/validation/validation.csv
s3://<S3_BUCKET>/input/test/test.csv
s3://<S3_BUCKET>/processing/output/metadata/preprocessing_metadata.json
```

## Validacion local

1. Abre `artifacts/local_outputs/preprocessing_metadata.json`.
2. Verifica `train_rows`, `validation_rows` y `test_rows`.
3. Revisa `encoded_feature_columns`.
4. Confirma que `target_column` es `churn_label`.
5. Confirma `source`. El valor esperado principal es `feature_store_offline_store`.
6. Abre `artifacts/local_outputs/run_state.json` y confirma `processing_job_name`, `feature_data_source` y `athena_query_results_s3_uri`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Processing > Processing jobs.
3. Busca el job `ml-training-opt-lab-processing-*`.
4. Verifica que el estado sea `Completed`.
5. Abre el detalle del job.
6. Revisa `Processing inputs`:
   - `processing-source`.
   - `feature-snapshot`, usado como fallback.
7. Revisa `Processing outputs`:
   - `train`.
   - `validation`.
   - `test`.
   - `metadata`.
8. Abre el enlace de CloudWatch Logs.
9. Busca el mensaje `Prepared train=... validation=... test=...`.
10. Ve a Amazon S3 y confirma los cuatro outputs esperados.
11. Ve a S3 > `<S3_BUCKET>` > `athena/query-results/` y confirma que Athena dejo archivos de resultado.
12. Ve a AWS Glue Data Catalog > Databases > `sagemaker_featurestore` y valida que existe una tabla asociada al Feature Group.
13. Si quieres ver la consulta manualmente, abre Amazon Athena, selecciona la base `sagemaker_featurestore` y revisa la tabla del Offline Store.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `ResourceLimitExceeded` | La cuenta no tiene cuota para el tipo de instancia. | El script prueba fallbacks. Si todos fallan, cambia `PROCESSING_INSTANCE_TYPE_FALLBACKS` o solicita cuota. |
| `AccessDenied` con `athena:StartQueryExecution` | El rol de SageMaker no tiene permisos de Athena. | Reejecuta paso 01 para actualizar CloudFormation y aplicar la politica nueva. |
| `Offline Store query returned 0 rows` | Feature Store escribe Offline Store de forma asincrona. | Espera unos minutos; el job reintenta hasta `OFFLINE_STORE_MAX_WAIT_SECONDS`. |
| `No CSV input found` | No existe el snapshot de respaldo en S3 y el fallback esta habilitado. | Reejecuta pasos 02 y 03. |
| Error de ruta `C:\... url scheme c` | El SDK interpreto una ruta Windows absoluta como URI. | Usa los scripts del repo; el codigo usa rutas relativas POSIX con `sdk_local_path`. |
| El job falla pero se creo | Error dentro del contenedor. | Abre CloudWatch Logs del Processing Job y revisa el traceback. |

## Limpieza de recursos

El Processing Job es efimero y no queda ejecutandose al terminar. Los outputs en S3 y logs en CloudWatch permanecen hasta cleanup o retencion configurada.
