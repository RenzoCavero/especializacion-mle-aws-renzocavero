# Guia del laboratorio

## Objetivo del laboratorio

Este laboratorio guia la construccion de un flujo cloud de entrenamiento y optimizacion de modelos con AWS.

Al finalizar, habras ejecutado un ciclo completo para un caso de churn:

1. Generacion de datos sinteticos.
2. Carga de datos en Amazon S3.
3. Creacion de un Feature Group en SageMaker Feature Store.
4. Preparacion de datasets con SageMaker Processing Jobs.
5. Entrenamiento baseline con SageMaker Training Jobs.
6. Evaluacion reproducible.
7. Optimizacion con SageMaker Automatic Model Tuning.
8. Tracking con SageMaker Experiments.
9. Registro del modelo en SageMaker Model Registry.
10. Creacion de una definicion de SageMaker Pipeline.
11. Revision de costos.
12. Limpieza de recursos.
13. Preparacion para laboratorios de inferencia batch y real-time.

## Que se construira en AWS

| Servicio | Uso en el laboratorio |
|---|---|
| Amazon S3 | Datos raw, snapshots, datasets procesados, modelos, metricas y reportes. |
| AWS CloudFormation | Infraestructura base del laboratorio. |
| AWS IAM | Rol de ejecucion de SageMaker y permisos acotados. |
| Amazon CloudWatch | Logs de Processing Jobs y Training Jobs. |
| AWS Glue Data Catalog | Metadata del Offline Store de Feature Store. |
| Amazon SageMaker Feature Store | Online Store y Offline Store para features. |
| SageMaker Processing Jobs | Preparacion de datos y evaluacion de modelos. |
| SageMaker Training Jobs | Entrenamiento baseline y trials de HPO. |
| SageMaker Automatic Model Tuning | Busqueda de hiperparametros. |
| SageMaker Experiments | Tracking de jobs, trials y metadata. |
| SageMaker Model Registry | Versionado y aprobacion del modelo. |
| SageMaker Pipelines | Definicion automatizada process/train/evaluate/register. |

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

Cleanup:

```bash
make lab-12-cleanup
bash scripts/lab.sh cleanup
.\scripts\destroy_infra.ps1
```

## Secuencia recomendada

| Archivo | Proposito | Comando relacionado | Resultado esperado | Validacion en AWS Console |
|---|---|---|---|---|
| `00_contexto_negocio.md` | Formular el problema de churn. | `make lab-00-context` | Sin recursos cloud. | Confirmar cuenta y region antes de avanzar. |
| `01_aws_setup.md` | Crear infraestructura base. | `make lab-01-aws-setup` | Stack, bucket, rol y `.env.cloud`. | CloudFormation, S3, IAM, CloudWatch. |
| `02_training_data_s3.md` | Generar y subir datos. | `make lab-02-training-data` | CSV local y objetos en S3. | S3 > `raw/` y `processing/input/`. |
| `03_feature_store_design.md` | Crear e ingestar Feature Group. | `make lab-03-feature-store` | Online Store validado y Offline Store en S3. | SageMaker Feature Store, S3, Glue. |
| `04_sagemaker_processing_jobs.md` | Preparar train/validation/test. | `make lab-04-processing` | Processing Job y datasets procesados. | SageMaker Processing jobs, S3, CloudWatch. |
| `05_sagemaker_training_jobs.md` | Entrenar baseline. | `make lab-05-training` | Training Job y `model.tar.gz`. | SageMaker Training jobs, S3, CloudWatch. |
| `06_metrics_evaluation.md` | Evaluar baseline. | `make lab-06-evaluation` | Metricas JSON y reporte Markdown. | SageMaker Processing jobs, S3, CloudWatch. |
| `07_hyperparameter_tuning.md` | Ejecutar HPO y comparar modelos. | `make lab-07-hpo` | Tuning Job, best model y comparacion. | SageMaker HPO, Training jobs, S3. |
| `08_experiments_tracking.md` | Revisar trazabilidad. | `make lab-08-experiments` | `experiment_tracking_report.json`. | SageMaker Experiments and trials. |
| `09_model_registry.md` | Registrar modelo y metadata. | `make lab-09-model-registry` | Model Package, contrato y reportes. | Model Registry, S3. |
| `10_sagemaker_pipelines.md` | Crear pipeline MLOps. | `make lab-10-pipeline` | Pipeline creado o actualizado. | SageMaker Pipelines. |
| `11_cost_optimization.md` | Revisar costos y recursos activos. | `make lab-11-cost` | `cost_and_resource_check.json`. | SageMaker, S3, CloudWatch, Cost Explorer. |
| `12_security_cleanup.md` | Eliminar recursos. | `make lab-12-cleanup` | Stack y recursos eliminados. | CloudFormation, S3, SageMaker, IAM. |
| `13_next_labs_batch_and_realtime.md` | Preparar inferencia futura. | `make lab-13-next-labs` | `feature_contract.json`. | S3, Feature Store, Model Registry. |

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
| `cost_and_resource_check.json` | Paso 11. |
| `validation_report.json` | `python -m src.validate_lab`. |

## Prefijos S3 importantes

| Prefijo | Contenido |
|---|---|
| `raw/` | Dataset raw sintetico. |
| `processing/input/` | Snapshot de features. |
| `feature-store-offline/` | Offline Store de Feature Store. |
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
13. Billing and Cost Management > Cost Explorer, si esta habilitado.

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
