# 05 - SageMaker Pipelines build

## Objetivo

Crear y ejecutar el model build pipeline en SageMaker.

## Que vas a construir o validar

Vas a crear un pipeline con pasos de procesamiento, entrenamiento, evaluacion, quality gate y registro de modelo. Este es el nucleo del flujo MLOps.

## Input del paso

- Datos en S3 generados por el paso 02.
- `SAGEMAKER_EXECUTION_ROLE_ARN`.
- `S3_BUCKET_NAME`.
- Candidatos de compute opcionales:
  - `PROCESSING_INSTANCE_TYPE_CANDIDATES`
  - `TRAINING_INSTANCE_TYPE_CANDIDATES`
  - `INSTANCE_TYPE_CANDIDATES`
  - `BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES`
- Codigo en:
  - `processing/preprocess.py`
  - `training/train.py`
  - `processing/evaluate.py`
  - `pipelines/build/pipeline_definition.py`

## Output esperado del paso

- SageMaker Pipeline `mlops-build-pipeline`.
- Metadata local de seleccion de compute:
  - `compute_selection_processing.json`
  - `compute_selection_training.json`
  - `compute_selection_endpoint.json`
  - `pipeline_compute_selection.json`
- Processing Job de preparacion.
- Training Job de entrenamiento.
- Processing Job de evaluacion.
- Quality gate con F1 y AUC.
- Model Package en Model Registry si el gate pasa.
- Metadata local:
  - `pipeline_upsert.json`
  - `pipeline_execution.json`
  - `pipeline_execution_status.json`

## Conceptos claves

SageMaker Pipelines permite expresar el ciclo de entrenamiento como un DAG reproducible. En lugar de ejecutar scripts manuales, cada paso declara entradas, salidas y dependencias. Esto mejora trazabilidad y repetibilidad.

`ProcessingStep` prepara datos. En este laboratorio divide dataset en train/test y genera baseline data. En produccion, este paso tambien podria validar schemas, nulos, rangos, duplicados y contratos de features.

`TrainingStep` entrena el modelo. El algoritmo es simple a proposito: el foco es la industrializacion, no la optimizacion del modelo. El artefacto final queda en S3 para registro y despliegue.

En `standalone_mode`, el dataset sintetico tiene una senal deliberadamente aprendible y el modelo usa una regresion logistica balanceada. Esto mantiene el laboratorio estable: el candidato por defecto debe superar el quality gate sin convertir el ejercicio en ajuste manual de hiperparametros.

`EvaluationStep` calcula metricas. F1 y AUC son utiles para clasificacion binaria porque capturan balance entre precision/recall y separabilidad. El pipeline escribe `evaluation.json`, que luego alimenta el quality gate.

`ConditionStep` implementa el quality gate. Si las metricas superan umbrales, el modelo puede registrarse. Si no, el pipeline evita promocionar un candidato debil.

`RegisterModel` crea un Model Package con estado inicial `PendingManualApproval`. Esta decision separa entrenamiento automatico de despliegue gobernado.

La definicion del pipeline se genera con `boto3` y el JSON nativo de SageMaker Pipelines. Esto evita depender de imports especificos del SageMaker Python SDK clasico, como `sagemaker.inputs` o `sagemaker.workflow`, que cambiaron en el SDK v3. El laboratorio sigue usando SageMaker Pipelines real en AWS; simplemente construye la definicion de manera compatible con entornos modernos.

Las cuotas de SageMaker son especificas por tipo de instancia y por workload. Tener cuota para endpoint no implica tener cuota para processing job, training job o transform job. Por eso el laboratorio usa `AUTO_SELECT_COMPUTE=true` por defecto y consulta Service Quotas antes de crear el pipeline. Si `ml.m5.large for processing job usage` tiene cuota 0, el selector prueba candidatos validos para processing como `ml.t3.medium`, `ml.t3.large`, `ml.m6i.large`, `ml.m5.xlarge`, `ml.m5.large`, `ml.c6i.xlarge` y `ml.c5.xlarge`.

Training requiere mas cuidado: algunas instancias aparecen en el enum de la API, pero SageMaker puede devolver luego `training-job/<instance-type> is not available in this region`. Por eso el selector no usa automaticamente candidatos con cuota `unknown` para training; exige una cuota positiva visible o falla antes de ejecutar el pipeline. Esto evita esperar varios minutos para descubrir que la cuenta no tiene capacidad de entrenamiento.

Hay una excepcion controlada: si Service Quotas reporta 0 pero la misma cuenta y region tienen Training Jobs recientes en estado `Completed`, el selector puede usar ese historial como evidencia best-effort. Esto permite continuar en sandboxes donde Service Quotas no refleja la capacidad real, pero mantiene la advertencia de que una ejecucion futura podria volver a fallar si AWS ya retiro esa cuota.

Batch Transform es la forma nativa de SageMaker para inferencia batch. No crea un endpoint persistente; crea un Transform Job que lee datos desde S3, ejecuta inferencia y escribe resultados en S3. Por eso el selector incluye el workload `batch_transform` y permite revisar sus cuotas por separado con `python -m src.compute --workload batch-transform`.

No todos los tipos sirven para todos los workloads. Por ejemplo, `ml.c6i.large` puede ser valido para endpoint, pero no para Processing Job; en jobs el equivalente de la familia c6i empieza en `ml.c6i.xlarge`. El selector filtra candidatos contra el enum real de SageMaker antes de crear la definicion del pipeline.

El selector no reduce costos por si solo; elige capacidad disponible. Para controlar costos se mantiene `InstanceCount=1`, datasets pequenos y cleanup explicito. Si quieres forzar una instancia concreta, usa `AUTO_SELECT_COMPUTE=false`.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.compute --workload processing` | `.env` | Service Quotas de SageMaker | `compute_selection_processing.json` | Ninguno | Elegir instancia valida para Processing Jobs. |
| 2 | `src.compute --workload training` | `.env` | Service Quotas de SageMaker | `compute_selection_training.json` | Ninguno | Elegir instancia valida para Training Jobs. |
| 3 | `src.compute --workload endpoint` | `.env` | Service Quotas de SageMaker | `compute_selection_endpoint.json` | Ninguno | Elegir instancia valida para despliegue real-time. |
| 4 | `src.create_or_update_pipeline` | `processing/preprocess.py`, `processing/evaluate.py`, `training/train.py`, `pipelines/build/pipeline_definition.py` | Dataset raw en S3 y role de SageMaker | `pipeline_contract.json`, `sagemaker_pipeline_definition.json`, `pipeline_upsert.json`, `pipeline_compute_selection.json` | Pipeline `mlops-build-pipeline`, codigo subido a `artifacts/code/`, source package en `artifacts/source/` | Construir o actualizar la definicion del pipeline. |
| 5 | `src.run_build_pipeline --wait` | Metadata del pipeline | SageMaker Pipeline | `pipeline_execution.json` | Processing Job, Training Job, Evaluation Job y Model Package si pasa el gate | Ejecutar el DAG completo y esperar resultado. |
| 6 | `src.check_pipeline_execution` | `pipeline_execution.json` | Execution y steps en SageMaker | `pipeline_execution_status.json` | Ninguno | Resumir estado, jobs creados y recomendaciones. |

## Paths principales

| Tipo | Path | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Datos raw | `s3://<bucket>/mlops-lab/lab/data/raw/` | Paso 02, `src.generate_sample_data --upload` | `ProcessData` del pipeline. |
| Datos procesados | `s3://<bucket>/mlops-lab/lab/data/processed/` | `processing/preprocess.py` dentro del Processing Job | `TrainingStep` y evaluacion. |
| Codigo de procesamiento | `s3://<bucket>/mlops-lab/lab/artifacts/code/preprocess.py` y `evaluate.py` | `src.create_or_update_pipeline` | Processing Jobs del pipeline. |
| Codigo de entrenamiento | `s3://<bucket>/mlops-lab/lab/artifacts/source/training.tar.gz` | `src.create_or_update_pipeline` | Training Job y Model Package. |
| Modelo entrenado | `s3://<bucket>/mlops-lab/lab/artifacts/models/.../model.tar.gz` | Training Job | Model Registry y despliegue. |
| Evaluacion | `s3://<bucket>/mlops-lab/lab/artifacts/evaluation/evaluation.json` | `processing/evaluate.py` | Quality gate y paso 06. |
| Evidencia local | `artifacts/local_outputs/pipeline_*.json` | Scripts del paso 05 | Pasos 06, 15 y troubleshooting. |

## Prerrequisitos

- Pasos 01 y 02 completados.
- Roles IAM con permisos para SageMaker, S3, logs, `iam:PassRole` y tagging de recursos SageMaker (`sagemaker:AddTags`, `sagemaker:ListTags`, `sagemaker:DeleteTags`).
- Dependencias instaladas.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 05
```

Comandos equivalentes:

```bash
python -m src.compute
python -m src.compute --workload training
python -m src.compute --workload training --inventory --limit 0
python -m src.compute --workload batch-transform
python -m src.compute --workload batch-transform --inventory --limit 0
make build-pipeline
make run-build-pipeline
make check-pipeline
```

## Resultado esperado

La ejecucion del pipeline termina en `Succeeded` y registra un candidato si cumple los umbrales.

## Validacion local

Revisar:

```text
artifacts/local_outputs/pipeline_execution_status.json
artifacts/local_outputs/compute_selection_processing.json
artifacts/local_outputs/compute_selection_training.json
artifacts/local_outputs/compute_selection_endpoint.json
artifacts/local_outputs/pipeline_compute_selection.json
artifacts/local_outputs/compute_selection_batch_transform.json
artifacts/local_outputs/compute_inventory_batch_transform.json
```

## Validacion en consola AWS

- SageMaker > Pipelines > `mlops-build-pipeline`.
- Revisar execution graph.
- Abrir Processing Jobs y Training Job.
- Revisar artefactos en S3 bajo `artifacts/` y `data/processed/`.

## Errores frecuentes

- `AccessDenied` por `iam:PassRole`.
- `AccessDenied` por `sagemaker:AddTags`: actualiza la infraestructura con `python -m src.deploy_infra` o `make deploy-infra` para agregar permisos de tagging al role `mlops-lab-lab-sagemaker-exec`.
- Bucket o prefijo S3 incorrecto.
- Instancia no disponible en la region.
- Quality gate no pasa por metricas bajas: revisa `evaluation.json`. En `standalone_mode`, vuelve a ejecutar `python -m src.lab_runner step 02` para regenerar/subir el dataset actualizado y luego `python -m src.lab_runner step 05`.
- `SAGEMAKER_RESOURCE_LIMIT` o cuota 0 para `processing job usage`: ejecuta `python -m src.compute --workload processing --inventory --limit 0`. Ajusta `PROCESSING_INSTANCE_TYPE_CANDIDATES` con instancias que tengan cuota en tu cuenta.
- `training-job/ml.t3.medium is not available in this region`: ejecuta `python -m src.compute --workload training --inventory --limit 0`. Si `positive_quota_count` es 0, solicita aumento de cuota para `training job usage`; si hay una instancia positiva, agregala a `TRAINING_INSTANCE_TYPE_CANDIDATES`.
- Cuota 0 para `transform job usage`: ejecuta `python -m src.compute --workload batch-transform --inventory --limit 0`. Si no aparece ninguna instancia con cuota positiva, solicita aumento de cuota para Batch Transform o usa otra region/profile. Si aparece una instancia positiva fuera de los candidatos, agregala a `BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES`.
- Error `No module named 'sagemaker.inputs'`: la ruta actual ya no depende de ese import. Actualiza el codigo del laboratorio y vuelve a ejecutar `python -m src.lab_runner step 05`.

## Ficha tecnica del paso

| Componente | Ruta | Responsabilidad | Entradas | Salidas |
|---|---|---|---|---|
| Selector de compute | `src/compute.py` | Consultar Service Quotas y elegir instancia por workload. | `.env`, boto3 Service Quotas/SageMaker. | `compute_selection_*.json`. |
| Pipeline builder | `src/create_or_update_pipeline.py` | Crear Model Package Group y upsert del pipeline. | `.env`, datos S3, codigo de processing/training. | `pipeline_upsert.json`, definicion JSON, assets en S3. |
| Definicion pipeline | `pipelines/build/pipeline_definition.py` | Construir DAG nativo de SageMaker Pipelines. | `LabConfig`, compute seleccionado. | `sagemaker_pipeline_definition.json`, `pipeline_contract.json`. |
| Preprocess | `processing/preprocess.py` | Separar train/test/baseline. | Raw data en S3. | Train/test/baseline en `data/processed/`. |
| Training | `training/train.py` | Entrenar modelo sklearn. | `train.csv`. | `model.tar.gz`. |
| Evaluation | `processing/evaluate.py` | Calcular accuracy, F1, AUC. | Modelo y `test.csv`. | `evaluation.json`. |
| Execution checker | `src/check_pipeline_execution.py` | Leer steps y diagnosticar fallos. | Execution ARN. | `pipeline_execution_status.json`. |

Funciones o clases relevantes:

- `select_instance_type` y `build_quota_inventory` en `src/compute.py`.
- `ensure_model_package_group` en `src/create_or_update_pipeline.py`.
- `upsert_pipeline` y `save_pipeline_contract` en `pipelines/build/pipeline_definition.py`.
- `train` en `training/train.py`.
- `evaluate` en `processing/evaluate.py`.

Para modificar comportamiento:

- Cambia preprocessing en `processing/preprocess.py`.
- Cambia algoritmo o hiperparametros en `training/train.py`.
- Cambia metricas/umbrales en `processing/evaluate.py`, `F1_THRESHOLD` y `AUC_THRESHOLD`.
- Cambia estructura del DAG en `pipelines/build/pipeline_definition.py`.

Validacion profunda:

```bash
type artifacts\local_outputs\sagemaker_pipeline_definition.json
type artifacts\local_outputs\pipeline_execution_status.json
aws sagemaker list-pipeline-execution-steps --pipeline-execution-arn <arn> --region <AWS_REGION>
```
