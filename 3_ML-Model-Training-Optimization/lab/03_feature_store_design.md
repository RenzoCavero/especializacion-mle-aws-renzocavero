# 03 - Diseno de SageMaker Feature Store

## Objetivo

Crear un Feature Group en SageMaker Feature Store e ingestar features curadas usando un SageMaker Processing Job. Este patron separa la preparacion de datos del almacenamiento de features:

```text
raw/ -> cleaned/ -> curated/ -> Processing Job -> Feature Store
```

## Que vas a construir o validar

Vas a crear el Feature Group configurado en `.env`:

```text
FEATURE_GROUP_NAME=churn-customer-features
```

El Feature Group tendra:

| Componente | Valor |
|---|---|
| Record identifier | `customer_id` |
| Event time feature | `event_time` |
| Online Store | habilitado por `ENABLE_ONLINE_STORE=true` |
| Offline Store | `s3://<S3_BUCKET>/feature-store-offline/` |
| Glue table | creada en AWS Glue Data Catalog si Offline Store esta habilitado |
| Fuente curada | `s3://<S3_BUCKET>/curated/churn_features.csv` |
| Linaje documentado | `s3://<S3_BUCKET>/lineage/feature_lineage.json` y tags del Feature Group |

## Conceptos clave

- SageMaker Feature Store: repositorio gestionado para almacenar, consultar y compartir features.
- Feature Group: definicion del schema, identificador, timestamp y stores de una familia de features.
- Online Store: almacenamiento de baja latencia para consultar el ultimo estado por `customer_id`.
- Offline Store: almacenamiento historico en S3 para entrenamiento, auditoria, batch inference y analitica.
- `PutRecord`: API que ingesta un registro de features en un Feature Group.
- Feature lineage: informacion que conecta fuentes, transformaciones y destino de las features.

## Como se comportan Online Store y Offline Store

El Processing Job de este paso lee `curated/churn_features.csv`, aplica la logica compartida de feature engineering y envia cada fila a Feature Store con `PutRecord`.

Si el Feature Group tiene Online Store y Offline Store habilitados, SageMaker maneja dos destinos:

| Store | Escritura | Lectura principal | Uso tipico |
|---|---|---|---|
| Online Store | Casi inmediata para el `RecordIdentifier` | `GetRecord` por `customer_id` | Inferencia en tiempo real. |
| Offline Store | Asincrona; puede tardar minutos en aparecer en S3 | S3, Glue o Athena | Entrenamiento, batch inference, auditoria y analitica. |

Si ingestas una nueva version de features para `CUST-000001` con un `event_time` mas reciente:

1. Online Store queda actualizado para consultas por `customer_id`.
2. Offline Store guarda el registro historico en S3 despues de una escritura asincrona.
3. `GetRecord` devuelve el ultimo estado disponible para ese `customer_id`; no devuelve todo el historial.
4. Para revisar versiones anteriores por timestamp, consulta Offline Store con S3, Glue o Athena.

## Flujo real de este paso

```text
s3://<S3_BUCKET>/curated/churn_features.csv
    |
    v
src.submit_feature_ingestion_job
    |
    v
processing/feature_ingestion_entrypoint.py
    |
    v
PutRecord to SageMaker Feature Store
    |
    +--> Online Store
    +--> Offline Store in S3
```

Este flujo es mas parecido a produccion que ingestar directamente desde la laptop. El rol de SageMaker ejecuta el job, lee S3, transforma los datos e ingesta features.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 01 y 02.
3. Confirma que existe:

   ```text
   s3://<S3_BUCKET>/curated/churn_features.csv
   ```

4. Confirma que `.env.cloud` incluye bucket y rol de SageMaker.
5. El rol de SageMaker debe tener permisos para S3, CloudWatch, SageMaker Processing y `sagemaker:PutRecord`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-03-feature-store
```

Con Bash o Git Bash, por partes:

```bash
bash scripts/create_feature_group.sh
bash scripts/ingest_features.sh
python -m src.get_online_features
python -m src.query_offline_store
```

En Windows PowerShell, por partes:

```powershell
.\scripts\create_feature_group.ps1
.\scripts\ingest_features.ps1
python -m src.get_online_features
python -m src.query_offline_store
```

Con Python:

```bash
python -m src.create_feature_group
python -m src.submit_feature_ingestion_job
python -m src.get_online_features
python -m src.query_offline_store
```

Internamente:

1. `src.create_feature_group` crea o reutiliza el Feature Group.
2. `src.submit_feature_ingestion_job` envia un SageMaker Processing Job.
3. El job remoto ejecuta `processing/feature_ingestion_entrypoint.py`.
4. El job monta `src/` dentro del contenedor para reutilizar `src/feature_pipeline.py`.
5. El job lee `s3://<S3_BUCKET>/curated/churn_features.csv`.
6. El job llama `PutRecord` por cada fila curada.
7. `src.get_online_features` valida un `GetRecord` desde Online Store.
8. `src.query_offline_store` lista objetos visibles en S3 bajo Offline Store.

## Scripts usados

| Accion | Script local | Modulo que envia o valida | Codigo ejecutado en AWS |
|---|---|---|---|
| Crear Feature Group | `scripts/create_feature_group.sh` / `.ps1` | `src/create_feature_group.py` | API SageMaker `CreateFeatureGroup` |
| Ingestar features | `scripts/ingest_features.sh` / `.ps1` | `src/submit_feature_ingestion_job.py` | `processing/feature_ingestion_entrypoint.py` |
| Transformaciones compartidas | No aplica | `src/feature_pipeline.py` | `src/feature_pipeline.py` montado en el job |
| Validar Online Store | No aplica | `src/get_online_features.py` | API Feature Store Runtime `GetRecord` |
| Validar Offline Store | No aplica | `src/query_offline_store.py` | S3 list bajo `feature-store-offline/` |

## Parametros y logica que puedes cambiar

| Necesidad | Archivo |
|---|---|
| Cambiar schema del Feature Group | `src/feature_schema.py` |
| Cambiar nombre del Feature Group u Online/Offline Store | `.env`, `.env.example`, `src/config.py` |
| Cambiar tags, descripcion o configuracion de creacion | `src/create_feature_group.py` |
| Cambiar como se ingesta desde `curated/` | `src/submit_feature_ingestion_job.py`, `processing/feature_ingestion_entrypoint.py` |
| Cambiar transformaciones antes de `PutRecord` | `src/feature_pipeline.py` |
| Cambiar validacion Online Store | `src/get_online_features.py` |
| Cambiar validacion Offline Store | `src/query_offline_store.py` |
| Ver workflow completo | `lab/14_workflow_and_scripts_reference.md` |

## Resultado esperado

Archivos locales:

```text
artifacts/local_outputs/feature_ingestion_metadata.json
artifacts/local_outputs/feature_ingestion_lineage.json
artifacts/local_outputs/online_store_get_record.json
artifacts/local_outputs/offline_store_validation.txt
artifacts/local_outputs/run_state.json
```

S3:

```text
s3://<S3_BUCKET>/feature-store/ingestion/metadata/feature_ingestion_metadata.json
s3://<S3_BUCKET>/feature-store/ingestion/metadata/feature_ingestion_lineage.json
s3://<S3_BUCKET>/feature-store-offline/
```

La terminal debe mostrar mensajes como:

```text
Ingested 1200 curated feature records into churn-customer-features
Validated Online Store GetRecord for CUST-000001
Offline Store has written objects to S3.
```

## Validacion local

1. Abre `artifacts/local_outputs/feature_ingestion_metadata.json`.
2. Confirma `ingested_records`.
3. Abre `artifacts/local_outputs/feature_ingestion_lineage.json`.
4. Confirma las fuentes `raw`, `cleaned` y `curated`.
5. Abre `artifacts/local_outputs/online_store_get_record.json`.
6. Confirma que incluye `customer_id`, `record` y `future_realtime_payload_without_target`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker AI > Dashboard.
3. En `All active resources`, revisa `Data prep`.
4. Confirma que `Total feature groups` muestre al menos `1 Created`.

Para ver el detalle completo:

1. En Amazon SageMaker AI, crea o abre un SageMaker Domain.
2. Crea o selecciona un user profile.
3. Entra a SageMaker Studio.
4. Ve a `More` > `Feature Store`.
5. Abre `Feature Group Catalog`.
6. Selecciona `My account`.
7. Busca `churn-customer-features`.
8. Verifica `Status = Created` y `Store type = both`.
9. Abre el Feature Group.
10. Revisa `Features` y confirma columnas como `customer_id`, `event_time`, `plan_type`, `engagement_score` y `churn_label`.
11. Revisa `Tags` y valida tags como `SourceRawS3Uri`, `SourceCleanedS3Uri`, `SourceCuratedS3Uri` y `FeatureLineageS3Uri`.
12. Abre `Sample queries` y selecciona `Time travel` para ver un ejemplo de consulta SQL sobre el Offline Store.

La sample query de Studio sirve como referencia para consultas historicas. El Processing Job del paso 04 usa la misma idea general: consulta la tabla Glue del Offline Store con Athena, ordena por `event_time` y toma la version mas reciente por `customer_id`. La query exacta del laboratorio esta documentada en `04_sagemaker_processing_jobs.md`.

Para validar el Processing Job de ingesta:

1. Ve a Amazon SageMaker AI > Processing jobs.
2. Busca `ml-training-opt-lab-feature-ingestion-*`.
3. Verifica `Status = Completed`.
4. Abre el job y revisa `Processing inputs`: `src-source` y `curated-features`.
5. Abre CloudWatch Logs y busca `Ingested 1200 curated feature records`.

Para validar Offline Store:

1. Ve a Amazon S3 > `<S3_BUCKET>`.
2. Abre `feature-store-offline/`.
3. Entra a las particiones `data/year=.../month=.../day=.../hour=...`.
4. Confirma que existan archivos `.parquet`.

## Lineage y Pipeline Executions en Feature Store

La pestana `Lineage` de Feature Store puede mostrar el Feature Group y entidades relacionadas que SageMaker conoce. El laboratorio deja el linaje documentado en:

```text
s3://<S3_BUCKET>/lineage/feature_lineage.json
s3://<S3_BUCKET>/feature-store/ingestion/metadata/feature_ingestion_lineage.json
```

Tambien agrega tags al Feature Group con las rutas de origen. Esto hace que el estudiante pueda validar de forma visual que las features vienen de `raw/`, `cleaned/` y `curated/`.

La pestana `Pipeline Executions` aparece vacia si no hay ejecuciones de SageMaker Pipelines asociadas visualmente al Feature Group. El paso 10 agrega un step de pipeline llamado `IngestCuratedFeatures`, pero la consola puede no mostrarlo dentro de esa pestana si Studio no asocia automaticamente esa ejecucion con el Feature Group. En ese caso, valida el pipeline desde `Pipelines` y el Feature Group desde `Feature Store`.

## Validacion opcional por CLI

```bash
aws sagemaker describe-feature-group \
  --feature-group-name churn-customer-features \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

```bash
aws s3 ls s3://<S3_BUCKET>/feature-store-offline/ \
  --recursive \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `AccessDenied` con `sagemaker:PutRecord` | El rol de SageMaker no puede escribir en Feature Store. | Reejecuta paso 01 para actualizar IAM. |
| Feature Group queda en `CreateFailed` | Permisos S3, Glue o rol incorrectos. | Revisa el detalle del Feature Group en SageMaker. |
| Processing Job de ingesta falla | Error de schema o permisos. | Abre CloudWatch Logs del job `feature-ingestion`. |
| Online Store no devuelve record | La ingesta no termino o el cliente no existe. | Reejecuta `python -m src.submit_feature_ingestion_job` y luego `python -m src.get_online_features`. |
| Offline Store no muestra objetos | Escritura asincrona de Feature Store. | Espera unos minutos y reejecuta `python -m src.query_offline_store`. |
| Solo ves el contador del dashboard | La vista detallada esta dentro de SageMaker Studio. | Crea o abre un SageMaker Domain y entra a `More` > `Feature Store`. |

## Conexion con pasos siguientes

El paso 04 no vuelve a construir las features desde `curated/`. Lee el Offline Store via AWS Glue Data Catalog y Amazon Athena para crear datasets de entrenamiento. Ese patron mantiene buenas practicas:

```text
curated/ -> Feature Store -> Offline Store -> Athena -> train/validation/test S3
```

Training Jobs y HPO consumen S3. No consultan Feature Store directamente.
