# Resumen del laboratorio 3: ML Model Training & Optimization

## Objetivo general
Entrenar, evaluar, optimizar e registrar un modelo de churn/riesgo con Amazon SageMaker, construyendo un flujo cloud reproducible desde features curadas hasta un modelo registrado en Model Registry con pipelines MLOps.

## Servicios AWS principales usados
- Amazon S3: datos crudos, limpios, curados, snapshots, datasets procesados, modelos, métricas y reportes.
- AWS CloudFormation: infraestructura reproducible.
- SageMaker Feature Store: Online Store y Offline Store para features.
- Amazon Athena y AWS Glue Data Catalog: materialización del Offline Store para construir datasets.
- SageMaker Processing Jobs: ingesta batch de features, preparación de datasets y evaluación.
- SageMaker Training Jobs: entrenamiento baseline y trials de Hyperparameter Optimization (HPO).
- SageMaker Automatic Model Tuning: búsqueda optimizada de hiperparámetros.
- SageMaker Autopilot: demo AutoML opcional para ver candidatos y leaderboard.
- SageMaker Experiments: tracking de jobs, trials y metadata.
- SageMaker Model Registry: versionado y aprobación del modelo.
- SageMaker Pipelines: definición automatizada process/train/evaluate/register.
- CloudWatch Logs: operación de Processing y Training Jobs.
- IAM: rol de ejecución con permisos acotados.

**Nota**: no se crean endpoints persistentes en este laboratorio.

## Flujo de datos
1. Generar datos sintéticos locales en `data/sample/`.
2. Subir CSV a S3 en `raw/`, preparar en `cleaned/` y `curated/`.
3. Crear Feature Group en SageMaker Feature Store.
4. Ingestar features curadas al Feature Store mediante Processing Job.
5. Materializar Offline Store con Athena para construir train/validation/test.
6. Entrenar baseline con SageMaker Training Job.
7. Evaluar baseline con métricas reproducibles.
8. Ejecutar HPO (Hyperparameter Tuning) para optimizar.
9. Evaluar mejor modelo y comparar con baseline.
10. Registrar modelo en Model Registry.
11. Crear SageMaker Pipeline para automatizar flujo completo.
12. Exportar contrato de features para laboratorios futuros.

## Archivos y artefactos clave
- `src/generate_sample_data.py`: genera CSV sintéticos.
- `src/upload_raw_data.py`: sube datos a S3.
- `src/create_feature_group.py`: crea Feature Group.
- `src/submit_feature_ingestion_job.py`: lanza Processing Job para ingestar features.
- `src/submit_processing_job.py`: prepara datasets desde Offline Store.
- `src/submit_training_job.py`: entrena baseline.
- `src/submit_hpo_job.py`: ejecuta Hyperparameter Tuning.
- `src/evaluate_model.py`: evalúa modelo.
- `src/register_model.py`: registra modelo en Model Registry.
- `src/create_pipeline.py`: crea SageMaker Pipeline baseline.
- `src/create_hpo_pipeline.py`: crea SageMaker Pipeline con HPO.
- `processing/feature_ingestion_entrypoint.py`: código remoto para ingesta Feature Store.
- `processing/processing_entrypoint.py`: código remoto para preparación de datasets.
- `processing/evaluation_entrypoint.py`: código remoto para evaluación.
- `training/train.py`: código remoto para entrenamiento.

## Variables de configuración importantes
Copiar y editar el archivo de ambiente:

```bash
cp .env.example .env
```

Variables clave en `.env`:
- `AWS_PROFILE`: perfil AWS.
- `AWS_REGION`: región AWS.
- `S3_BUCKET_NAME`: bucket S3 (si se deja vacío, CloudFormation lo genera).
- `RESOURCE_PREFIX`: prefijo para jobs y recursos.
- `FEATURE_GROUP_NAME`: nombre del Feature Group.
- `MODEL_PACKAGE_GROUP_NAME`: nombre del grupo de modelos en Model Registry.
- `PROCESSING_INSTANCE_TYPE`: tipo de instancia para Processing (default: `ml.t3.medium`).
- `TRAINING_INSTANCE_TYPE`: tipo de instancia para Training (default: `ml.t3.medium`).
- `HPO_MAX_JOBS`: número máximo de trials HPO (default: `4`).
- `HPO_MAX_PARALLEL_JOBS`: paralelismo HPO (default: `1`).
- `FEATURE_DATA_SOURCE`: fuente de features (`offline_store` o snapshot fallback).
- `ALLOW_FEATURE_SNAPSHOT_FALLBACK`: si se permite fallback a snapshot.
- `PROCESSING_INGEST_FEATURE_STORE`: si ingesta features al Feature Store en pipeline.

## Dependencias e instalación
Crear y activar un entorno virtual, luego instalar requisitos:

Linux/Mac:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Comandos principales del laboratorio

### Ejecución completa
- Con Make:
  ```bash
  make all-cloud
  ```
- Sin Make (Python):
  ```bash
  python -m src.lab_runner all
  ```
- Sin Make (Bash):
  ```bash
  bash scripts/lab.sh all
  ```
- Sin Make (PowerShell):
  ```powershell
  .\scripts\run_all_cloud.ps1
  ```

### Ejecución por pasos
- Listar pasos:
  ```bash
  make list
  python -m src.lab_runner list
  bash scripts/lab.sh list
  ```
- Ejecutar un paso específico:
  ```bash
  make lab-04-processing
  python -m src.lab_runner step 04
  bash scripts/lab.sh step 04
  ```

### Pasos individuales con Make
```bash
make lab-00-context
make lab-01-aws-setup
make lab-02-training-data
make lab-03-feature-store
make lab-04-processing
make lab-05-training
make lab-06-evaluation
make lab-07-hpo
make lab-08-experiments
make lab-09-model-registry
make lab-10-pipeline
make lab-11-cost
make lab-12-cleanup
make lab-13-next-labs
```

### Demo opcional de Autopilot
```bash
make autopilot
bash scripts/run_autopilot.sh
```

### Pipeline baseline
```bash
make lab-10-pipeline      # crea o actualiza la definición
make run-pipeline         # inicia ejecución
```

### Pipeline con HPO
```bash
make create-hpo-pipeline  # crea o actualiza definición
make run-hpo-pipeline     # inicia ejecución
```

### Feature Store - Validación
```bash
make validate-online-store
make query-offline-store
```

### Cleanup y destrucción
```bash
make destroy-infra
bash scripts/destroy_infra.sh
# o con PowerShell:
.\scripts\destroy_infra.ps1
```

## Pasos del laboratorio y su propósito

| Paso | Archivo | Propósito | Comando |
|---|---|---|---|
| 00 | `00_contexto_negocio.md` | Entender caso de churn/riesgo. | `bash scripts/lab.sh step 00` |
| 01 | `01_aws_setup.md` | Crear infraestructura base con CloudFormation. | `bash scripts/lab.sh step 01` |
| 02 | `02_training_data_s3.md` | Generar y subir datos raw a S3. | `bash scripts/lab.sh step 02` |
| 03 | `03_feature_store_design.md` | Crear e ingestar Feature Group. | `bash scripts/lab.sh step 03` |
| 04 | `04_sagemaker_processing_jobs.md` | Preparar datasets desde Offline Store. | `bash scripts/lab.sh step 04` |
| 05 | `05_sagemaker_training_jobs.md` | Entrenar modelo baseline. | `bash scripts/lab.sh step 05` |
| 06 | `06_metrics_evaluation.md` | Evaluar baseline. | `bash scripts/lab.sh step 06` |
| 07 | `07_hyperparameter_tuning.md` | Ejecutar HPO y comparar modelos. | `bash scripts/lab.sh step 07` |
| 08 | `08_experiments_tracking.md` | Revisar tracking con SageMaker Experiments. | `bash scripts/lab.sh step 08` |
| 09 | `09_model_registry.md` | Registrar modelo en Model Registry. | `bash scripts/lab.sh step 09` |
| 10 | `10_sagemaker_pipelines.md` | Crear SageMaker Pipeline. | `bash scripts/lab.sh step 10` |
| 11 | `11_cost_optimization.md` | Revisar costos y recursos activos. | `bash scripts/lab.sh step 11` |
| 12 | `12_security_cleanup.md` | Eliminar recursos. | `bash scripts/lab.sh cleanup` |
| 13 | `13_next_labs_batch_and_realtime.md` | Preparar para laboratorios de inferencia. | `bash scripts/lab.sh step 13` |
| 14 | `14_workflow_and_scripts_reference.md` | Referencia técnica del workflow. | Lectura. |

## Salidas esperadas en S3

Después de ejecutar el flujo completo deben existir estos prefijos y archivos:

```text
s3://<bucket>/raw/                         # datos sintéticos crudos
s3://<bucket>/cleaned/                     # datos limpios
s3://<bucket>/curated/                     # features curadas
s3://<bucket>/lineage/                     # metadata de lineaje
s3://<bucket>/processing/input/            # snapshot de fallback
s3://<bucket>/feature-store-offline/       # Offline Store de Feature Store
s3://<bucket>/input/train/                 # datasets procesados
s3://<bucket>/input/validation/
s3://<bucket>/input/test/
s3://<bucket>/output/baseline/             # artefactos baseline
s3://<bucket>/output/hpo/                  # artefactos HPO
s3://<bucket>/output/best_model/           # mejor modelo
s3://<bucket>/evaluation/                  # métricas de evaluación
s3://<bucket>/metrics/                     # comparativas
s3://<bucket>/reports/                     # reportes finales
s3://<bucket>/model_registry_metadata/     # metadata del modelo registrado
s3://<bucket>/automl/output/               # artefactos Autopilot (opcional)
```

## Artefactos locales importantes

Los outputs locales se escriben en `artifacts/local_outputs/`:

```text
infra_outputs.json                         # outputs de infraestructura
run_state.json                             # estado de jobs y ejecuciones
feature_lineage.json                       # linaje de features
feature_ingestion_metadata.json            # metadata de ingesta
online_store_get_record.json              # validación Online Store
offline_store_validation.txt               # validación Offline Store
preprocessing_metadata.json                # metadata de preparación
evaluation/baseline/evaluation_metrics.json
evaluation/optimized/evaluation_metrics.json
model_comparison.json                      # comparación baseline vs optimizado
experiment_tracking_report.json            # reporte de experiments
feature_contract.json                      # contrato de features
training_report.md                         # reporte de entrenamiento
model_card.md                              # tarjeta del modelo
cost_and_resource_check.json              # reporte de costos
validation_report.json                     # validación general
```

## Validación rápida

1. Verificar stack CloudFormation.
2. Confirmar bucket S3 y prefijos principales.
3. Confirmar Feature Group en SageMaker Feature Store.
4. Revisar SageMaker Processing Jobs y Training Jobs.
5. Confirmar Model Registry con modelo registrado.
6. Revisar SageMaker Pipelines si se creó.
7. Revisar CloudWatch Logs para jobs.
8. Revisar SageMaker Experiments para tracking.

## Recomendaciones útiles

- Usa `make all-cloud` para evitar ejecutar múltiples jobs por separado.
- HPO puede generar costo significativo; limita `HPO_MAX_JOBS` durante pruebas.
- Autopilot es opcional; usa solo para demostración, no reemplaza el flujo baseline/HPO.
- Valida el Offline Store en Athena si necesitas diagnosticar issues con datasets.
- El `feature_contract.json` es esencial para los laboratorios 4 y 5 de inferencia.
- Destruye la infraestructura al terminar para evitar costos continuos.
- Si Offline Store no tiene filas aún, el lab utiliza fallback a snapshot en `processing/input/`.
- Model Registry mantiene el modelo en estado `PendingManualApproval` hasta que se apruebe.
