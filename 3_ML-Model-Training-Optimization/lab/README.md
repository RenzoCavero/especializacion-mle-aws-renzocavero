# Guia del laboratorio

## Objetivo del laboratorio

Este laboratorio guia la construccion de un flujo cloud de entrenamiento y optimizacion de modelos con AWS.

Al finalizar, habras ejecutado un ciclo completo para un caso de churn:

1. Generacion de datos sinteticos.
2. Carga de datos en Amazon S3 con zonas `raw/`, `cleaned/` y `curated/`.
3. Creacion de un Feature Group en SageMaker Feature Store.
4. Ingesta de features curadas hacia Feature Store con SageMaker Processing Jobs.
5. Preparacion de datasets con SageMaker Processing Jobs desde el Offline Store.
6. Entrenamiento baseline con SageMaker Training Jobs.
7. Evaluacion reproducible.
8. Optimizacion con SageMaker Automatic Model Tuning.
9. Tracking con SageMaker Experiments.
10. Registro del modelo en SageMaker Model Registry.
11. Creacion de una definicion de SageMaker Pipeline.
12. Revision de costos.
13. Limpieza de recursos.
14. Preparacion para laboratorios de inferencia batch y real-time.
15. Referencia de workflow, scripts y puntos de modificacion.

## Que se construira en AWS

| Servicio | Uso en el laboratorio |
|---|---|
| Amazon S3 | Datos raw, cleaned, curated, snapshots, datasets procesados, modelos, metricas y reportes. |
| AWS CloudFormation | Infraestructura base del laboratorio. |
| AWS IAM | Rol de ejecucion de SageMaker y permisos acotados. |
| Amazon CloudWatch | Logs de Processing Jobs y Training Jobs. |
| AWS Glue Data Catalog | Metadata del Offline Store de Feature Store. |
| Amazon Athena | Materializacion del Offline Store para construir datasets de training. |
| Amazon SageMaker Feature Store | Online Store y Offline Store para features. |
| SageMaker Processing Jobs | Ingesta batch de features, materializacion del Offline Store y evaluacion de modelos. |
| SageMaker Training Jobs | Entrenamiento baseline y trials de HPO. |
| SageMaker Automatic Model Tuning | Busqueda de hiperparametros. |
| SageMaker Autopilot | Demo AutoML opcional y pequena para ver candidatos, leaderboard y artefactos. |
| SageMaker Experiments | Tracking de jobs, trials y metadata. |
| SageMaker Model Registry | Versionado y aprobacion del modelo. |
| SageMaker Pipelines | Definicion automatizada process/train/evaluate/register y variante opcional con HPO. |

No se crean endpoints persistentes en este laboratorio.

## Prerrequisitos

1. Cuenta AWS con permisos para CloudFormation, S3, SageMaker, IAM, CloudWatch Logs, AWS Glue Data Catalog e `iam:PassRole`.
2. AWS CLI instalado y configurado.
3. Python 3.11+ o 3.12.
4. Entorno virtual activo.
5. Dependencias instaladas:

   ```bash
   python -m pip install -r requirements.txt
   ```

6. Profile AWS valido:

   ```bash
   aws sts get-caller-identity --profile <AWS_PROFILE> --region <AWS_REGION>
   ```

## Configuracion inicial

Ejecuta desde la carpeta del proyecto:

```bash
cd 3_ML-Model-Training-Optimization
```

Copia `.env.example`:

```bash
cp .env.example .env
```

En PowerShell:

```powershell
Copy-Item .env.example .env
```

Edita `.env` y revisa:

| Variable | Default del repo | Uso |
|---|---|---|
| `AWS_PROFILE` | `mlops-2-data-prep-lab` | Profile usado por boto3 y AWS CLI. |
| `AWS_REGION` | `us-east-1` | Region donde se crean recursos. |
| `RESOURCE_PREFIX` | `ml-training-opt-lab` | Prefijo de jobs y recursos. |
| `STACK_NAME` | `ml-training-opt-lab` | Stack CloudFormation. |
| `S3_BUCKET_NAME` | vacio | Si queda vacio, CloudFormation genera el bucket. |
| `FEATURE_GROUP_NAME` | `churn-customer-features` | Feature Group. |
| `MODEL_PACKAGE_GROUP_NAME` | `churn-model-package-group` | Model Registry. |
| `PROCESSING_INSTANCE_TYPE` | `ml.t3.medium` | Instancia principal para Processing. |
| `TRAINING_INSTANCE_TYPE` | `ml.t3.medium` | Instancia principal para Training. |
| `HPO_MAX_JOBS` | `4` | Numero maximo de trials HPO. |
| `HPO_MAX_PARALLEL_JOBS` | `1` | Paralelismo de HPO. |
| `FEATURE_DATA_SOURCE` | `offline_store` | Fuente principal para construir train/validation/test. |
| `ALLOW_FEATURE_SNAPSHOT_FALLBACK` | `true` | Permite fallback al snapshot si Offline Store aun no tiene filas. |
| `PROCESSING_INGEST_FEATURE_STORE` | `true` | Incluye un step de pipeline que ingesta `curated/` hacia Feature Store. |
| `AUTOPILOT_MAX_CANDIDATES` | `2` | Candidatos maximos para el demo opcional de Autopilot. |
| `AUTOPILOT_MAX_RUNTIME_SECONDS` | `900` | Runtime maximo del demo opcional. |
| `AUTOPILOT_MODE` | `ENSEMBLING` | Modo liviano para crear un pequeno conjunto de candidatos. |
| `AUTOPILOT_ALGORITHMS` | `linear-learner,xgboost` | Algoritmos basicos para limitar el alcance del demo. |

El Pipeline baseline usa:

```text
PIPELINE_NAME=ml-training-opt-lab-pipeline
```

La variante opcional con HPO usa:

```text
HPO_PIPELINE_NAME=ml-training-opt-lab-hpo-pipeline
```

No guardes credenciales en `.env`. No commitees `.env` ni `.env.cloud`.

## Formas de ejecucion

Ejecucion completa sin cleanup:

```bash
make all-cloud
```

Sin Make:

```bash
python -m src.lab_runner all
bash scripts/lab.sh all
```

En Windows PowerShell:

```powershell
.\scripts\run_all_cloud.ps1
```

Listar pasos:

```bash
python -m src.lab_runner list
bash scripts/lab.sh list
```

Ejecutar un paso:

```bash
python -m src.lab_runner step 04
bash scripts/lab.sh step 04
```

Demo opcional minimo de Autopilot, despues del paso 04:

```bash
make autopilot
bash scripts/run_autopilot.sh
python -m src.submit_autopilot_job
```

No se incluye en `all` porque AutoML puede generar costo adicional.

Este demo usa pocos candidatos y algoritmos explicables para estudiantes. Su objetivo es ubicar los resultados en SageMaker, revisar el candidate leaderboard y entender que artefactos produce Autopilot, no reemplazar el flujo baseline/HPO del laboratorio.

Pipeline baseline de reentrenamiento:

```bash
make lab-10-pipeline
make run-pipeline
```

`make lab-10-pipeline` crea o actualiza la definicion. `make run-pipeline` inicia una ejecucion real de reentrenamiento.

Pipeline opcional con HPO:

```bash
make create-hpo-pipeline
make run-hpo-pipeline
```

`make create-hpo-pipeline` crea o actualiza la definicion. `make run-hpo-pipeline` inicia la ejecucion que lanza un Tuning Job administrado.

Comandos Python directos equivalentes:

```bash
python -m src.create_hpo_pipeline
python -m src.run_hpo_pipeline
```

Usa estos comandos si quieres evitar `make` y ejecutar directamente los modulos del laboratorio. El primer comando sube la definicion del Pipeline HPO a SageMaker Pipelines; el segundo inicia una ejecucion nueva de ese Pipeline.

En ambos casos, valida en Amazon SageMaker > Pipelines. Para la variante HPO, tambien revisa Amazon SageMaker AI > Hyperparameter tuning jobs.

Cleanup:

```bash
make lab-12-cleanup
bash scripts/lab.sh cleanup
.\scripts\destroy_infra.ps1
```

## Mapa de scripts y codigo enviado a SageMaker

En el laboratorio hay tres niveles de ejecucion:

1. Wrapper de terminal: script Bash, PowerShell o target Make que ejecuta el estudiante.
2. Modulo Python submitter: archivo en `src/` que llama APIs de AWS o SageMaker SDK.
3. Codigo remoto: archivo que SageMaker ejecuta dentro de un Processing Job o Training Job.

| Paso | Wrapper principal | Modulo Python que envia o consulta AWS | Servicio o accion | Codigo remoto ejecutado por SageMaker |
|---|---|---|---|---|
| 00 | `scripts/lab.sh step 00` | `src.lab_runner` | Solo imprime guia de contexto. | No aplica. |
| 01 | `scripts/deploy_infra.sh`, `scripts/deploy_infra.ps1` | `src.deploy_infra` | Crea/actualiza CloudFormation, S3, IAM y CloudWatch. | No aplica. |
| 02 | `scripts/upload_training_data.sh`, `scripts/upload_training_data.ps1` | `src.generate_sample_data`, `src.upload_raw_data`, `src.prepare_feature_sources` | Genera CSV local, sube raw y crea zonas `cleaned/`, `curated/` y `lineage/` en S3. | No aplica. |
| 03 | `scripts/create_feature_group.sh`, `scripts/ingest_features.sh` | `src.create_feature_group`, `src.submit_feature_ingestion_job`, `src.get_online_features`, `src.query_offline_store` | Crea Feature Group, envia un Processing Job de ingesta, valida Online Store y Offline Store. | `processing/feature_ingestion_entrypoint.py` con `src/feature_pipeline.py`. |
| 04 | `scripts/run_processing_job.sh`, `scripts/run_processing_job.ps1` | `src.submit_processing_job` | Envia un SageMaker Processing Job que materializa Offline Store via Athena y genera datasets. | `processing/processing_entrypoint.py` con soporte de `processing/`. |
| 05 | `scripts/run_baseline_training.sh`, `scripts/run_baseline_training.ps1` | `src.submit_training_job` | Envia un SageMaker Training Job. | `training/train.py` con `training/requirements.txt`. |
| 06 | `scripts/lab.sh step 06` o `python -m src.evaluate_model --model-name baseline` | `src.evaluate_model` | Envia un Processing Job de evaluacion. | `processing/evaluation_entrypoint.py` con soporte de `processing/`. |
| 07 | `scripts/run_hpo.sh`, `scripts/run_hpo.ps1` | `src.submit_hpo_job`, `src.evaluate_model`, `src.compare_models` | Crea un SageMaker Hyperparameter Tuning Job, evalua el mejor modelo y compara metricas. | HPO ejecuta `training/train.py`; la evaluacion ejecuta `processing/evaluation_entrypoint.py`. |
| 08 | `scripts/lab.sh step 08` | `src.show_experiment_tracking` | Consulta SageMaker Experiments y genera reporte local. | No aplica. |
| 09 | `scripts/register_best_model.sh`, `scripts/register_best_model.ps1` | `src.compare_models`, `src.register_model`, `src.export_feature_metadata`, `src.training_report`, `src.model_card` | Registra un Model Package, sube metadata y reportes a S3. | No ejecuta job; empaqueta `training/inference.py` como codigo de inferencia futuro. |
| Opcional | `scripts/approve_model.sh`, `scripts/approve_model.ps1` | `src.approve_model` | Aprueba el Model Package y crea un `SageMaker Model` deployable. | No crea endpoint ni compute; deja metadata lista para deploy. |
| 10 | `scripts/lab.sh step 10`, `scripts/create_pipeline.sh`, `scripts/create_pipeline.ps1`; ejecucion con `scripts/run_pipeline.sh`, `scripts/run_pipeline.ps1` | `src.create_pipeline`, `src.run_pipeline` | Crea/actualiza SageMaker Pipeline baseline y opcionalmente inicia ejecucion. | Pipeline usa `processing/feature_ingestion_entrypoint.py`, `processing/processing_entrypoint.py`, `training/train.py`, `processing/evaluation_entrypoint.py` y `RegisterModel`. |
| Opcional | `scripts/create_hpo_pipeline.sh`, `scripts/create_hpo_pipeline.ps1`; ejecucion con `scripts/run_hpo_pipeline.sh`, `scripts/run_hpo_pipeline.ps1` | `src.create_hpo_pipeline`, `src.run_hpo_pipeline` | Crea/ejecuta un Pipeline con `TuningStep` administrado por SageMaker. | HPO ejecuta `training/train.py`, evalua el mejor artefacto con `processing/evaluation_entrypoint.py` y registra si pasa el gate. |
| 11 | `scripts/lab.sh step 11` | `src.cost_and_resource_check` | Consulta recursos activos y escribe reporte de costos/recursos. | No aplica. |
| 12 | `scripts/destroy_infra.sh`, `scripts/destroy_infra.ps1` | `src.destroy_infra`, `src.cleanup_resources` | Elimina recursos SageMaker y CloudFormation. | No aplica. |
| 13 | `scripts/lab.sh step 13` | `src.export_feature_metadata` | Exporta contrato de features local y a S3. | No aplica. |
| Opcional | `scripts/run_autopilot.sh`, `scripts/run_autopilot.ps1` | `src.submit_autopilot_job` | Crea un AutoML Job V2 minimo con `linear-learner` y `xgboost`. | Autopilot gestiona sus propios jobs internos. |

Los wrappers `scripts/lab.sh all` y `scripts/run_all_cloud.sh` ejecutan varios pasos en secuencia. El archivo `Makefile` expone los mismos pasos como targets `make lab-04-processing`, `make lab-05-training`, `make lab-07-hpo`, etc.

Para entender inputs, outputs, dependencias entre pasos y que archivo editar cuando quieras cambiar parametros, revisa tambien `lab/14_workflow_and_scripts_reference.md`.

## Secuencia recomendada

| Archivo | Proposito | Comando relacionado | Resultado esperado | Validacion en AWS Console |
|---|---|---|---|---|
| `00_contexto_negocio.md` | Formular el problema de churn. | `make lab-00-context` | Sin recursos cloud. | Confirmar cuenta y region antes de avanzar. |
| `01_aws_setup.md` | Crear infraestructura base. | `make lab-01-aws-setup` | Stack, bucket, rol y `.env.cloud`. | CloudFormation, S3, IAM, CloudWatch. |
| `02_training_data_s3.md` | Generar y preparar datos. | `make lab-02-training-data` | CSV local, `raw/`, `cleaned/`, `curated/`, snapshot y linaje. | S3 > `raw/`, `cleaned/`, `curated/`, `lineage/`, `processing/input/`. |
| `03_feature_store_design.md` | Crear e ingestar Feature Group. | `make lab-03-feature-store` | Processing Job de ingesta, Online Store validado y Offline Store en S3. | SageMaker Feature Store, Processing jobs, S3, Glue. |
| `04_sagemaker_processing_jobs.md` | Preparar train/validation/test desde Offline Store. | `make lab-04-processing` | Processing Job, consulta Athena y datasets procesados. | SageMaker Processing jobs, Athena, Glue, S3, CloudWatch. |
| `05_sagemaker_training_jobs.md` | Entrenar baseline. | `make lab-05-training` | Training Job y `model.tar.gz`. | SageMaker Training jobs, S3, CloudWatch. |
| `06_metrics_evaluation.md` | Evaluar baseline. | `make lab-06-evaluation` | Metricas JSON y reporte Markdown. | SageMaker Processing jobs, S3, CloudWatch. |
| `07_hyperparameter_tuning.md` | Ejecutar HPO y comparar modelos. | `make lab-07-hpo` | Tuning Job, best model y comparacion. | SageMaker HPO, Training jobs, S3. |
| `08_experiments_tracking.md` | Revisar trazabilidad. | `make lab-08-experiments` | `experiment_tracking_report.json`. | SageMaker Experiments and trials. |
| `09_model_registry.md` | Registrar modelo y metadata. | `make lab-09-model-registry` | Model Package, contrato y reportes. | Model Registry, S3. |
| `10_sagemaker_pipelines.md` | Crear pipeline MLOps baseline y variante opcional con HPO. | `make lab-10-pipeline`, `make create-hpo-pipeline` | Pipeline creado o actualizado. | SageMaker Pipelines, HPO. |
| `11_cost_optimization.md` | Revisar costos y recursos activos. | `make lab-11-cost` | `cost_and_resource_check.json`. | SageMaker, S3, CloudWatch, Cost Explorer. |
| `12_security_cleanup.md` | Eliminar recursos. | `make lab-12-cleanup` | Stack y recursos eliminados. | CloudFormation, S3, SageMaker, IAM. |
| `13_next_labs_batch_and_realtime.md` | Preparar inferencia futura. | `make lab-13-next-labs` | `feature_contract.json`. | S3, Feature Store, Model Registry. |
| `14_workflow_and_scripts_reference.md` | Entender workflow, scripts reutilizados y puntos de cambio. | No ejecuta comandos. | Mapa tecnico del laboratorio. | No aplica. |

## Artefactos locales importantes

Los outputs locales se escriben en:

```text
artifacts/local_outputs/
```

Archivos clave:

| Archivo | Generado por |
|---|---|
| `infra_outputs.json` | Paso 01. |
| `run_state.json` | Varios pasos; mantiene nombres de jobs y rutas. |
| `feature_lineage.json` | Paso 02. |
| `feature_ingestion_metadata.json` | Paso 03. |
| `feature_ingestion_lineage.json` | Paso 03. |
| `online_store_get_record.json` | Paso 03. |
| `offline_store_validation.txt` | Paso 03. |
| `preprocessing_metadata.json` | Paso 04. |
| `evaluation/baseline/evaluation_metrics.json` | Paso 06. |
| `evaluation/optimized/evaluation_metrics.json` | Paso 07. |
| `model_comparison.json` | Paso 07. |
| `experiment_tracking_report.json` | Paso 08. |
| `feature_contract.json` | Pasos 09 y 13. |
| `training_report.md` | Paso 09. |
| `model_card.md` | Paso 09. |
| `approved_model.json` | Comando opcional `python -m src.approve_model`. |
| `cost_and_resource_check.json` | Paso 11. |
| `validation_report.json` | `python -m src.validate_lab`. |

## Prefijos S3 importantes

| Prefijo | Contenido |
|---|---|
| `raw/` | Dataset raw sintetico. |
| `cleaned/` | Dataset limpio y validado. |
| `curated/` | Features curadas para Feature Store. |
| `lineage/` | Metadata de linaje raw-cleaned-curated-feature-store. |
| `processing/input/` | Snapshot curado de fallback para Processing. |
| `feature-store/ingestion/metadata/` | Metadata del Processing Job que ingesta Feature Store. |
| `feature-store/pipeline-ingestion/metadata/` | Metadata equivalente cuando la ingesta corre dentro de SageMaker Pipelines. |
| `feature-store/hpo-pipeline-ingestion/metadata/` | Metadata equivalente cuando la ingesta corre dentro del Pipeline con HPO. |
| `feature-store-offline/` | Offline Store de Feature Store. |
| `athena/query-results/` | Resultados temporales de consultas Athena usadas para materializar Offline Store. |
| `input/train/` | Dataset de entrenamiento. |
| `input/validation/` | Dataset de validacion. |
| `input/test/` | Dataset de test. |
| `output/baseline/` | Artefactos del baseline. |
| `output/hpo/` | Artefactos de trials HPO. |
| `output/best_model/` | Mejor modelo copiado por HPO. |
| `evaluation/` | Metricas de evaluacion. |
| `metrics/` | Comparacion de modelos. |
| `reports/` | Reportes Markdown. |
| `model_registry_metadata/` | Contrato de features. |
| `code/` | Codigo subido para SageMaker. |
| `automl/output/` | Artefactos del demo opcional de Autopilot. |

Aunque puedas abrir `feature-store-offline/` directamente en S3, el laboratorio no construye el dataset leyendo archivos sueltos. El paso 04 consulta la tabla registrada por SageMaker Feature Store en AWS Glue Data Catalog usando Athena, selecciona el registro mas reciente por `customer_id` y escribe el resultado temporal en `athena/query-results/`. Luego el Processing Job aplica one-hot encoding y genera los CSVs finales de entrenamiento.

## Validacion general en AWS Console

Durante el laboratorio vas a revisar:

1. CloudFormation > Stacks.
2. Amazon S3 > bucket del laboratorio.
3. IAM > Roles.
4. CloudWatch > Log groups.
5. Amazon SageMaker AI > Dashboard para ver el contador de Feature Groups.
6. SageMaker Studio > `More` > `Feature Store` para ver el Feature Group Catalog detallado. Si aun no tienes Studio disponible, crea o abre un SageMaker Domain y entra con un user profile.
7. Amazon SageMaker > Processing > Processing jobs.
8. Amazon SageMaker > Training > Training jobs.
9. Amazon SageMaker AI > Hyperparameter tuning jobs para ver el Tuning Job padre; SageMaker Studio > Jobs > Training muestra los Training Jobs hijos o trials.
10. Amazon SageMaker > Experiments and trials.
11. Amazon SageMaker > Inference > Model Registry.
12. Amazon SageMaker > Pipelines.
13. Amazon Athena > Query editor, para validar consultas al Offline Store cuando sea necesario.
14. SageMaker Autopilot o AutoML, si ejecutaste el demo opcional.
15. Billing and Cost Management > Cost Explorer, si esta habilitado.

Si necesitas que el modelo aparezca en `Models > Deployable models`, ejecuta despues del paso 09:

```bash
python -m src.approve_model
```

Este comando aprueba el Model Package y crea un recurso `SageMaker Model`. No crea endpoint; el costo de compute empieza solo si despues despliegas un endpoint o ejecutas Batch Transform.

## Como interpretar Jobs en SageMaker Studio

SageMaker Studio muestra varias categorias bajo `Jobs`. No todas se usan en este laboratorio. Cada categoria responde a un tipo distinto de workload.

| Seccion en Studio | Cuando usarla | Ejemplo practico |
|---|---|---|
| `Training` | Cuando ejecutas un SageMaker Training Job desde SDK, pipeline, HPO o scripts. | Entrenar `training/train.py` con datos en S3 y generar `model.tar.gz`. |
| `Notebook jobs` | Cuando quieres ejecutar un notebook sin interaccion, una vez o con schedule. | Generar un reporte semanal desde un notebook de analisis. |
| `JumpStart training` | Cuando entrenas o fine-tuneas un modelo preconstruido desde SageMaker JumpStart. | Ajustar un modelo de vision, NLP o foundation model usando la UI de JumpStart. |
| `Inference optimization` | Cuando ya tienes un modelo y quieres optimizarlo antes de servirlo. | Probar cuantizacion, compilacion, recomendaciones de instancia o menor latencia/costo. |
| `Model evaluation` | Cuando usas la funcionalidad administrada de evaluacion de modelos desde Studio o su API. | Evaluar calidad de un modelo con una evaluacion administrada por SageMaker. |
| `Performance evaluation` | Cuando necesitas medir rendimiento de inferencia. | Medir latencia, throughput, p95/p99 y comportamiento de un endpoint bajo carga. |

En este laboratorio:

1. `Jobs > Training` muestra el Training Job baseline y los Training Jobs hijos creados por HPO.
2. `Amazon SageMaker AI > Hyperparameter tuning jobs` muestra el Tuning Job padre.
3. La evaluacion del paso 06 y del modelo optimizado se ejecuta como SageMaker Processing Job, no como `Jobs > Model evaluation`.
4. `Notebook jobs`, `JumpStart training`, `Inference optimization`, `Model evaluation` y `Performance evaluation` son utiles para otros flujos, pero no son el mecanismo principal usado por los scripts de este laboratorio.

## Advertencia de costos

Este laboratorio crea recursos reales en AWS. Los costos principales vienen de:

- Processing Jobs.
- Training Jobs.
- HPO, porque ejecuta multiples Training Jobs.
- Pipeline HPO opcional, porque ejecuta un Tuning Job y sus Training Jobs hijos.
- Athena, por las consultas al Offline Store.
- Autopilot opcional, porque puede crear varios candidatos y jobs internos.
- S3.
- CloudWatch Logs.
- SageMaker Feature Store Online Store.
- Ejecuciones opcionales de SageMaker Pipelines.

El laboratorio no crea endpoints persistentes. Si ves un endpoint con prefijo `ml-training-opt-lab`, revisalo porque probablemente fue creado manualmente.

## Troubleshooting general

| Sintoma | Causa probable | Accion |
|---|---|---|
| `AccessDenied` | Permisos insuficientes del profile o rol. | Revisa IAM, `iam:PassRole` y politicas del stack. |
| `ResourceLimitExceeded` | Cuota regional de SageMaker en cero o baja. | Ajusta fallbacks de instancia o solicita cuota. |
| `.env.cloud` no existe | No se ejecuto infraestructura. | Ejecuta paso 01. |
| No ves recursos en consola | Region incorrecta. | Confirma `AWS_REGION` y selector de region en consola. |
| Ves `Total feature groups`, pero no el detalle del Feature Group | La vista detallada esta dentro de SageMaker Studio y requiere un Domain/user profile. | Crea o abre un SageMaker Domain, entra a Studio y ve a `More` > `Feature Store`. |
| Job fallo | Error de script o datos. | Abre CloudWatch Logs desde el job. |
| S3 no tiene outputs esperados | Paso anterior no termino o fallo. | Revisa `run_state.json` y logs del paso anterior. |
| HPO consume tiempo/costo | Varios Training Jobs. | Baja `HPO_MAX_JOBS` para pruebas. |
| `Jobs > Model evaluation` esta vacio despues del paso 06 | El laboratorio evalua con un SageMaker Processing Job, no con la evaluacion administrada de Studio. | Ve a Amazon SageMaker > Processing > Processing jobs, busca `ml-training-opt-lab-eval-baseline-*` y revisa S3 en `evaluation/baseline/`. |
| Pipeline HPO falla en `TuneChurnModel` con `ListTrainingJobsForHyperParameterTuningJob` | El rol de ejecucion puede crear el Tuning Job, pero no puede listar sus Training Jobs hijos para seleccionar el mejor modelo. | Ejecuta `python -m src.deploy_infra` o `bash scripts/lab.sh step 01` para actualizar IAM. Luego usa `Retry` o `python -m src.run_hpo_pipeline`. |

## Limpieza de recursos

Cuando termines de revisar resultados:

```bash
make lab-12-cleanup
```

O:

```bash
bash scripts/lab.sh cleanup
```

En PowerShell:

```powershell
.\scripts\destroy_infra.ps1
```

No ejecutes cleanup antes de revisar S3, CloudWatch, Experiments, Model Registry, Pipelines y Feature Store. Cleanup elimina recursos necesarios para validacion visual.

Para borrar solo artefactos locales generados por el laboratorio, sin tocar AWS:

```bash
make clean-local-outputs
```

Vista previa sin borrar:

```bash
python -m src.clean_local_outputs --dry-run
```

Esto elimina contenido generado en `artifacts/local_outputs/`, `data/local_cache/`, `data/sample/*.csv` y `.env.cloud`. Conserva `.env`, codigo fuente y recursos cloud.

## Relacion con inferencia batch y real-time

Este laboratorio no despliega el modelo. Deja listos los componentes que usaran los siguientes laboratorios:

| Futuro laboratorio | Componentes preparados aqui |
|---|---|
| SageMaker Batch Inference / Batch Transform | Modelo registrado, Offline Store, contrato de features, datasets en S3. |
| SageMaker Real-Time Endpoint | Modelo registrado, Online Store, codigo de inferencia y `customer_id` como lookup key. |
| SageMaker Asynchronous Inference / near-real-time | Modelo registrado, codigo de inferencia, contrato de features y base para endpoint asincrono con inputs/outputs en S3. |
| Pipeline de despliegue | Model Registry, metricas, estado de aprobacion y contrato de features. |

El archivo `13_next_labs_batch_and_realtime.md` explica como reutilizar estos componentes.

Para mantener Feature Store actualizado en produccion, usa Processing Jobs para batch o micro-batch y usa Kinesis/MSK con Lambda o Managed Service for Apache Flink para streaming de baja latencia. En ambos casos, reutiliza la misma logica de transformacion de features para evitar diferencias entre entrenamiento e inferencia.

El one-hot encoding de `plan_type`, `country` y `device_type` ocurre en el Processing Job del paso 04. En los laboratorios de inferencia deberas decidir si esa transformacion queda dentro del artefacto del modelo, dentro de `inference.py`, en un SageMaker Inference Pipeline o en una capa previa que prepare el payload antes de llamar al endpoint.

En produccion, la aprobacion humana del Model Package se usa como evento de gobierno. Amazon EventBridge puede detectar `SageMaker Model Package State Change` cuando `ModelApprovalStatus=Approved` y disparar un workflow de despliegue con CodePipeline, Step Functions o SageMaker Pipelines. Ese workflow crea el `SageMaker Model`, despliega staging, ejecuta pruebas y recien despues promueve a produccion o lanza Batch Transform.
