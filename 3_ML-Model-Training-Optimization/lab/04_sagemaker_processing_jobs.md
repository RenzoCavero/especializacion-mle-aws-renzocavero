# 04 - SageMaker Processing Jobs

## Objetivo

Ejecutar la preparacion de datos en SageMaker Processing para producir datasets reproducibles de entrenamiento, validacion y test.

## Que vas a construir o validar

Vas a crear un Processing Job con nombre similar a:

```text
ml-training-opt-lab-processing-<timestamp>-<instance>
```

El job lee el snapshot de features y genera:

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

En este laboratorio, el Processing Job actual prepara datasets de entrenamiento:

```text
feature snapshot -> one-hot encoding -> train/validation/test CSVs
```

Ese feature snapshot viene de:

```text
s3://<S3_BUCKET>/processing/input/churn_features.csv
```

Por lo tanto, este Processing Job no consulta directamente el Offline Store. El Offline Store si queda escrito en S3 por Feature Store, pero en esta version del laboratorio se usa como evidencia de historico y como base conceptual para laboratorios futuros.

En un diseno productivo, este mismo tipo de Processing Job podria consultar el Offline Store:

```text
Feature Store Offline Store in S3
    |
    v
AWS Glue Data Catalog or Athena query
    |
    v
SageMaker Processing Job
    |
    v
Feature transformations and point-in-time dataset build
    |
    v
train/validation/test datasets in S3
    |
    v
Training Job or HPO
```

Ese enfoque es util cuando necesitas reconstruir datasets historicos, evitar leakage temporal y entrenar con datos particionados por `event_time`. La salida final para entrenamiento seguiria siendo S3; SageMaker Training Jobs y HPO consumen canales de entrada en S3, no consultas directas a Feature Store.

No es todavia un actualizador streaming de Feature Store. En una arquitectura productiva, separa:

1. Logica compartida de feature engineering.
2. Logica exclusiva de entrenamiento, como split train/test y manejo del label.
3. Logica de actualizacion online, que transforma eventos recientes y llama `PutRecord`.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 01, 02 y 03.

3. Confirma que existe:

   ```text
   s3://<S3_BUCKET>/processing/input/churn_features.csv
   ```

4. Confirma que `PROCESSING_INSTANCE_TYPE` y `PROCESSING_INSTANCE_TYPE_FALLBACKS` estan definidos en `.env`.

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
5. Monta `s3://<S3_BUCKET>/processing/input/churn_features.csv` en `/opt/ml/processing/input`.
6. Ejecuta `processing/processing_entrypoint.py`.
7. Descarga `preprocessing_metadata.json` a `artifacts/local_outputs/`.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/run_processing_job.sh` |
| Wrapper PowerShell | `scripts/run_processing_job.ps1` |
| Modulo que envia el job a SageMaker | `src/submit_processing_job.py` |
| Codigo remoto ejecutado en el Processing Job | `processing/processing_entrypoint.py` |
| Librerias auxiliares montadas en el contenedor | `processing/` |

## Resultado esperado

La terminal debe mostrar un mensaje similar a:

```text
Prepared train=720 validation=240 test=240
Processing Job submitted: <job-name> on <instance-type>
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
5. Abre `artifacts/local_outputs/run_state.json` y confirma `processing_job_name`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Processing > Processing jobs.
3. Busca el job `ml-training-opt-lab-processing-*`.
4. Verifica que el estado sea `Completed`.
5. Abre el detalle del job.
6. Revisa `Processing inputs`:
   - `processing-source`.
   - `feature-snapshot`.
7. Revisa `Processing outputs`:
   - `train`.
   - `validation`.
   - `test`.
   - `metadata`.
8. Abre el enlace de CloudWatch Logs.
9. Busca el mensaje `Prepared train=... validation=... test=...`.
10. Ve a Amazon S3 y confirma los cuatro outputs esperados.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `ResourceLimitExceeded` | La cuenta no tiene cuota para el tipo de instancia. | El script prueba fallbacks. Si todos fallan, cambia `PROCESSING_INSTANCE_TYPE_FALLBACKS` o solicita cuota. |
| `No CSV input found` | No existe el snapshot de features en S3. | Reejecuta pasos 02 y 03. |
| Error de ruta `C:\... url scheme c` | El SDK interpreto una ruta Windows absoluta como URI. | Usa los scripts del repo; el codigo usa rutas relativas POSIX con `sdk_local_path`. |
| El job falla pero se creo | Error dentro del contenedor. | Abre CloudWatch Logs del Processing Job y revisa el traceback. |

## Limpieza de recursos

El Processing Job es efimero y no queda ejecutandose al terminar. Los outputs en S3 y logs en CloudWatch permanecen hasta cleanup o retencion configurada.
