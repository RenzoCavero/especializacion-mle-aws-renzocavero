# 14 - Referencia de workflow y scripts

## Objetivo

Entender como se conectan todos los pasos del laboratorio, que scripts participa en cada etapa y donde cambiar parametros cuando quieras adaptar el flujo.

Usa esta guia como mapa tecnico. Los archivos `00` a `13` explican como ejecutar cada paso; este archivo explica como se relacionan entre si.

## Workflow resumido

```text
01 Infra AWS
  -> 02 Raw, cleaned y curated en S3
  -> 03 Feature Store Online/Offline
  -> 04 Dataset train/validation/test desde Offline Store
  -> 05 Baseline Training Job
  -> 06 Evaluacion baseline
  -> 07 HPO + evaluacion optimized + comparacion
  -> 08 Experiments report
  -> 09 Model Registry + reportes + model card
  -> 10 Pipeline baseline o Pipeline HPO
  -> 11 Revision de costos
  -> 13 Contrato para batch y real-time
  -> 12 Cleanup cuando termines
```

El flujo de datos principal es:

```text
data/local_cache/churn_raw.csv
  -> s3://<S3_BUCKET>/raw/churn_raw.csv
  -> s3://<S3_BUCKET>/cleaned/churn_cleaned.csv
  -> s3://<S3_BUCKET>/curated/churn_features.csv
  -> SageMaker Feature Store
  -> Offline Store en s3://<S3_BUCKET>/feature-store-offline/
  -> Athena materialization
  -> s3://<S3_BUCKET>/input/train/train.csv
  -> s3://<S3_BUCKET>/input/validation/validation.csv
  -> s3://<S3_BUCKET>/input/test/test.csv
  -> Training, HPO, Evaluation, Registry
```

## Mapa por paso

| Paso | Entrada principal | Script local | Modulos `src/` | Codigo remoto en SageMaker | Output principal |
|---|---|---|---|---|---|
| 00 | Documentacion | `scripts/lab.sh` | `src/lab_runner.py` | No aplica | Contexto del caso. |
| 01 | `.env`, CloudFormation template | `scripts/deploy_infra.sh`, `.ps1` | `src/deploy_infra.py`, `src/fetch_stack_outputs.py` | No aplica | `.env.cloud`, bucket S3, rol IAM. |
| 02 | Config AWS y semilla local | `scripts/upload_training_data.sh`, `.ps1` | `src/generate_sample_data.py`, `src/upload_raw_data.py`, `src/prepare_feature_sources.py` | No aplica | `raw/`, `cleaned/`, `curated/`, `lineage/` en S3. |
| 03 | `curated/churn_features.csv` | `scripts/create_feature_group.*`, `scripts/ingest_features.*` | `src/create_feature_group.py`, `src/submit_feature_ingestion_job.py`, `src/get_online_features.py`, `src/query_offline_store.py` | `processing/feature_ingestion_entrypoint.py` | Feature Group, Online Store, Offline Store. |
| 04 | Feature Store Offline Store | `scripts/run_processing_job.*` | `src/submit_processing_job.py` | `processing/processing_entrypoint.py`, `processing/utils.py` | `train.csv`, `validation.csv`, `test.csv`. |
| 05 | `input/train/`, `input/validation/` | `scripts/run_baseline_training.*` | `src/submit_training_job.py` | `training/train.py`, `training/utils.py` | Baseline `model.tar.gz`. |
| 06 | `input/test/`, baseline model | `scripts/lab.sh step 06` | `src/evaluate_model.py` | `processing/evaluation_entrypoint.py`, `processing/utils.py` | `evaluation/baseline/evaluation_metrics.json`. |
| 07 | Processed datasets | `scripts/run_hpo.*` | `src/submit_hpo_job.py`, `src/evaluate_model.py`, `src/compare_models.py`, `src/submit_autopilot_job.py` | `training/train.py`, `processing/evaluation_entrypoint.py` | HPO job, best model, comparison report. |
| 08 | `run_state.json`, SageMaker Experiments API | `scripts/lab.sh step 08` | `src/show_experiment_tracking.py`, `src/experiments.py` | No aplica | `experiment_tracking_report.json`. |
| 09 | Selected model artifact | `scripts/register_best_model.*`, `scripts/approve_model.*` | `src/register_model.py`, `src/export_feature_metadata.py`, `src/training_report.py`, `src/model_card.py`, `src/approve_model.py` | No aplica | Model Package, reports, feature contract. |
| 10 | Feature Store, processed datasets, code templates | `scripts/create_pipeline.*`, `scripts/run_pipeline.*`, `scripts/create_hpo_pipeline.*`, `scripts/run_hpo_pipeline.*` | `src/create_pipeline.py`, `src/run_pipeline.py`, `src/create_hpo_pipeline.py`, `src/run_hpo_pipeline.py` | Processing/training entrypoints reutilizados | Pipeline baseline o HPO Pipeline. |
| 11 | Recursos AWS existentes | `scripts/lab.sh step 11` | `src/cost_and_resource_check.py` | No aplica | `cost_and_resource_check.json`. |
| 12 | Recursos creados por el lab | `scripts/destroy_infra.*`, `scripts/clean_local_outputs.*` | `src/destroy_infra.py`, `src/cleanup_resources.py`, `src/clean_local_outputs.py` | No aplica | Recursos eliminados o outputs locales borrados. |
| 13 | Feature schema y registry metadata | `scripts/lab.sh step 13` | `src/export_feature_metadata.py` | No aplica | `feature_contract.json`. |

## Scripts y parametros principales

La tabla siguiente resume los puntos de modificacion mas comunes. Si un cambio afecta un flujo standalone y un Pipeline, actualiza ambos archivos indicados.

| Necesidad | Archivo principal | Tambien revisar | Comentario |
|---|---|---|---|
| Cambiar region, bucket, prefijos, instancias o flags del lab | `.env`, `.env.example`, `src/config.py` | `infra/cloudformation/template.yaml` si afecta permisos | `src/config.py` centraliza defaults y rutas S3. |
| Cambiar columnas del Feature Group | `src/feature_schema.py` | `src/feature_pipeline.py`, `processing/utils.py`, `training/inference.py` | Mantener schema, transformacion e inferencia alineados. |
| Cambiar logica raw -> cleaned -> curated | `src/feature_pipeline.py` | `src/prepare_feature_sources.py`, `processing/feature_ingestion_entrypoint.py` | Esta logica se reutiliza antes de Feature Store y en ingesta. |
| Cambiar generacion dummy | `src/generate_sample_data.py` | `src/feature_schema.py` | Mantener columnas esperadas por schema. |
| Cambiar query Athena del Offline Store | `processing/processing_entrypoint.py` | `processing/utils.py` | `_offline_store_query` define columnas y seleccion del ultimo record por `customer_id`. |
| Cambiar one-hot encoding o features del modelo | `processing/utils.py` | `training/train.py`, `processing/evaluation_entrypoint.py`, `training/inference.py` | `prepare_model_frame` define columnas finales usadas por training/evaluation. |
| Cambiar split train/validation/test | `processing/processing_entrypoint.py` | `src/submit_processing_job.py`, `src/create_pipeline.py`, `src/create_hpo_pipeline.py` | Los defaults estan en argumentos del entrypoint. |
| Cambiar algoritmo del baseline | `training/train.py` | `src/submit_training_job.py`, `training/requirements.txt` | El estimator SageMaker ejecuta `training/train.py`. |
| Cambiar hiperparametros fijos del baseline | `src/submit_training_job.py` | `src/create_pipeline.py` | Mantener standalone y pipeline baseline consistentes. |
| Cambiar metricas capturadas por Training Job | `src/submit_training_job.py` | `training/train.py` | `METRIC_DEFINITIONS` debe coincidir con los `print()` del script remoto. |
| Cambiar rangos de HPO standalone | `src/submit_hpo_job.py` | `.env` para `HPO_MAX_JOBS` y `HPO_MAX_PARALLEL_JOBS` | Define `ContinuousParameter`, `IntegerParameter` y `CategoricalParameter`. |
| Cambiar rangos de HPO Pipeline | `src/create_hpo_pipeline.py` | `.env` para limites HPO | El `TuningStep` usa los rangos definidos en este archivo. |
| Cambiar metrica objetivo de HPO | `src/submit_hpo_job.py`, `src/create_hpo_pipeline.py` | `training/train.py`, `METRIC_DEFINITIONS` | La metrica debe imprimirse en logs y existir en metric definitions. |
| Cambiar criterio de seleccion baseline vs optimized | `src/compare_models.py` | `src/evaluate_model.py` | Actualmente compara F1. |
| Cambiar umbral de registro del Pipeline | `src/run_pipeline.py`, `src/run_hpo_pipeline.py` | `src/create_pipeline.py`, `src/create_hpo_pipeline.py` | Parametro `MinF1ForRegistration`. |
| Cambiar contenido del Model Package | `src/register_model.py` | `training/inference.py` | Define imagen, model data, inference source y modos realtime/batch. |
| Cambiar reportes o model card | `src/training_report.py`, `src/model_card.py` | `src/export_feature_metadata.py` | Solo afecta documentacion/metadata, no training. |
| Cambiar aprobacion deployable | `src/approve_model.py` | `src/register_model.py` | Aprueba Model Package y puede crear `SageMaker Model`. |
| Cambiar validaciones finales | `src/validate_lab.py`, `src/cost_and_resource_check.py` | `lab/README.md` | Usado al final del flujo educativo. |
| Cambiar limpieza | `src/cleanup_resources.py`, `src/destroy_infra.py`, `src/clean_local_outputs.py` | `.env` flags de cleanup | Revisa antes de borrar recursos compartidos. |

## Scripts compartidos importantes

| Archivo | Uso |
|---|---|
| `src/config.py` | Carga `.env` y `.env.cloud`, define rutas S3, nombres de recursos y defaults. |
| `src/aws_clients.py` | Crea sesiones boto3, SageMaker Session y PipelineSession. |
| `src/state.py` | Lee y escribe `artifacts/local_outputs/run_state.json`. |
| `src/feature_schema.py` | Contrato de features, tipos y columnas esperadas. |
| `src/feature_pipeline.py` | Transformaciones compartidas para cleaned/curated e ingesta a Feature Store. |
| `src/experiments.py` | Helpers para SageMaker Experiments. |
| `src/instance_types.py` | Fallbacks de tipos de instancia cuando hay cuotas/capacidad limitada. |
| `src/logging_utils.py` | Logging consistente. |
| `processing/utils.py` | Preprocesamiento del modelo, one-hot encoding, carga de modelo y metricas. |
| `training/utils.py` | Carga de datasets supervisados para `training/train.py`. |

## Revision de scripts en `src/`

Los scripts se agrupan asi:

| Categoria | Archivos |
|---|---|
| Flujo principal ejecutado por pasos del lab | `deploy_infra.py`, `generate_sample_data.py`, `upload_raw_data.py`, `prepare_feature_sources.py`, `create_feature_group.py`, `submit_feature_ingestion_job.py`, `get_online_features.py`, `query_offline_store.py`, `submit_processing_job.py`, `submit_training_job.py`, `evaluate_model.py`, `submit_hpo_job.py`, `compare_models.py`, `show_experiment_tracking.py`, `register_model.py`, `export_feature_metadata.py`, `training_report.py`, `model_card.py`, `create_pipeline.py`, `run_pipeline.py`, `cost_and_resource_check.py`, `destroy_infra.py`, `download_outputs.py`, `validate_lab.py`. |
| Flujo opcional | `submit_autopilot_job.py`, `approve_model.py`, `create_hpo_pipeline.py`, `run_hpo_pipeline.py`, `clean_local_outputs.py`. |
| Helpers necesarios | `aws_clients.py`, `config.py`, `experiments.py`, `feature_pipeline.py`, `feature_schema.py`, `fetch_stack_outputs.py`, `instance_types.py`, `logging_utils.py`, `metrics.py`, `state.py`, `cleanup_resources.py`. |
| Compatibilidad o debug local | `ingest_features.py`, `prepare_train_validation_test.py`. |

Los dos archivos de compatibilidad/debug no son parte del flujo recomendado actual:

| Archivo | Estado | Recomendacion |
|---|---|---|
| `src/ingest_features.py` | Ingesta directa desde la laptop con `PutRecord`. Fue reemplazado en el flujo principal por `src/submit_feature_ingestion_job.py`. | Mantener solo si quieres comparar ingesta local vs Processing Job. No lo uses como camino principal de clase. |
| `src/prepare_train_validation_test.py` | Ejecuta `processing/processing_entrypoint.py` localmente para debugging. | Mantener como herramienta de debug. No se usa en `Makefile`, `lab_runner` ni scripts cloud. |

No se eliminaron scripts en esta revision. La recomendacion es conservarlos mientras el laboratorio siga usando ejemplos de debugging y compatibilidad; si quieres un repositorio mas estricto para estudiantes, esos dos archivos pueden moverse a una carpeta `dev_tools/` o documentarse como no soportados.

## Relacion entre standalone y pipeline

El laboratorio tiene dos formas de ejecutar la misma logica:

| Ejecucion standalone | Pipeline equivalente | Codigo remoto compartido |
|---|---|---|
| Paso 03 `src.submit_feature_ingestion_job` | `IngestCuratedFeatures` / `IngestCuratedFeaturesForHPO` | `processing/feature_ingestion_entrypoint.py`, `src/feature_pipeline.py` |
| Paso 04 `src.submit_processing_job` | `ProcessChurnFeatures` / `ProcessChurnFeaturesForHPO` | `processing/processing_entrypoint.py`, `processing/utils.py` |
| Paso 05 `src.submit_training_job` | `TrainChurnBaseline` | `training/train.py` |
| Paso 07 `src.submit_hpo_job` | `TuneChurnModel` | `training/train.py` |
| Paso 06/07 `src.evaluate_model` | `EvaluateChurnModel` / `EvaluateBestHPOModel` | `processing/evaluation_entrypoint.py`, `processing/utils.py` |
| Paso 09 `src.register_model` | `RegisterChurnModel` / `RegisterBestHPOModel` | SageMaker SDK `RegisterModel` |

Cuando modifiques un script remoto compartido, el cambio impacta tanto el flujo standalone como el Pipeline. Por ejemplo:

1. Si cambias `training/train.py`, cambian baseline, HPO standalone y HPO Pipeline.
2. Si cambias `processing/utils.py`, cambian Processing Job standalone, evaluacion y Pipelines.
3. Si cambias `src/feature_pipeline.py`, cambian la preparacion curated local y la ingesta de Feature Store.

## Regla practica para modificar el laboratorio

1. Cambia primero el script fuente de la logica, no el wrapper.
2. Si el cambio afecta recursos AWS, revisa `infra/cloudformation/template.yaml`.
3. Si el cambio afecta rutas, nombres o defaults, revisa `src/config.py`.
4. Si el cambio afecta un job standalone y un Pipeline, actualiza ambos submitters.
5. Ejecuta pruebas locales antes de volver a crear recursos:

   ```bash
   python -m pytest tests
   ```

6. Si cambias una definicion de Pipeline, vuelve a subirla:

   ```bash
   python -m src.create_pipeline
   python -m src.create_hpo_pipeline
   ```
