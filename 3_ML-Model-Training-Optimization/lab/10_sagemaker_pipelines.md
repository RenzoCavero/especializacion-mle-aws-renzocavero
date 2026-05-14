# 10 - SageMaker Pipelines

## Objetivo

Crear una definicion de SageMaker Pipeline que automatiza procesamiento, entrenamiento, evaluacion y registro condicional.

## Que vas a construir o validar

Vas a crear o actualizar:

```text
PIPELINE_NAME=ml-training-opt-lab-pipeline
```

El Pipeline incluye estos steps:

| Step | Funcion |
|---|---|
| `ProcessChurnFeatures` | Preparar train, validation, test y metadata. |
| `TrainChurnBaseline` | Entrenar un candidato baseline. |
| `EvaluateChurnModel` | Calcular metricas sobre test. |
| `CheckF1BeforeRegister` | Validar umbral minimo de F1. |
| `RegisterChurnModel` | Registrar el modelo si la condicion se cumple. |

## Conceptos clave

- Pipeline: flujo declarativo de MLOps en SageMaker.
- PipelineSession: sesion que construye definiciones sin ejecutar jobs inmediatamente.
- ProcessingStep: paso de procesamiento.
- TrainingStep: paso de entrenamiento.
- ConditionStep: gate automatico basado en una metrica.
- RegisterModel: paso que registra un candidato en Model Registry.

## Relacion con los pasos anteriores

El Pipeline reutiliza el mismo codigo central de procesamiento, entrenamiento y evaluacion que ya ejecutaste en los pasos anteriores. La diferencia principal es la orquestacion: antes ejecutabas modulos Python o scripts Bash uno por uno; ahora SageMaker Pipelines crea un grafo declarativo y ejecuta cada step en orden.

| Step del Pipeline | Codigo reutilizado | Equivalente anterior | Comentario |
|---|---|---|---|
| `ProcessChurnFeatures` | `processing/processing_entrypoint.py` | Paso 04, `src.submit_processing_job` | Usa la misma logica de transformacion y split train/validation/test. |
| `TrainChurnBaseline` | `training/train.py` | Paso 05, `src.submit_training_job` | Entrena el baseline con hiperparametros fijos. |
| `EvaluateChurnModel` | `processing/evaluation_entrypoint.py` | Paso 06, `src.evaluate_model` | Calcula metricas sobre test usando el modelo generado por el step de training. |
| `CheckF1BeforeRegister` | Definicion nativa de SageMaker Pipelines | No existe como script standalone | Evalua si F1 cumple `MinF1ForRegistration`. |
| `RegisterChurnModel-RegisterModel` | `RegisterModel` de SageMaker SDK | Similar al paso 09, `src.register_model` | Registra el modelo, pero no genera todo el paquete de reportes custom del paso 09. |

Resumen practico:

```text
Mismo codigo central.
Distinta orquestacion.
El Pipeline agrega dependencias, parametros y registro condicional.
```

Hay diferencias importantes:

1. El Pipeline no ejecuta HPO. Usa un baseline con:

   ```text
   C=1.0
   max-iter=250
   class-weight=balanced
   random-state=42
   ```

2. El Pipeline registra el modelo con `RegisterModel` si la condicion de F1 se cumple.
3. El paso 09 standalone agrega metadata adicional, contrato de features, `training_report.md` y `model_card.md`.
4. Si quieres que el Pipeline incluya HPO, comparacion de modelos o reportes custom, tendrias que agregar steps adicionales.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa al menos los pasos 01, 02 y 04.

3. Confirma que existe:

   ```text
   s3://<S3_BUCKET>/processing/input/churn_features.csv
   ```

4. Confirma que el Model Package Group existe o que tienes permisos para crearlo cuando el pipeline registre.

## Pasos de ejecucion

Crear o actualizar la definicion:

```bash
make lab-10-pipeline
```

Con Python:

```bash
python -m src.create_pipeline
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 10
```

No hay wrapper `.ps1` especifico para crear el pipeline. En Windows usa el comando Python.

Ejecucion opcional del pipeline:

```bash
make run-pipeline
```

O:

```bash
python -m src.run_pipeline
```

Advertencia: ejecutar el pipeline crea nuevos Processing Jobs, Training Jobs y posiblemente nuevos Model Packages. Eso genera costo adicional.

## Resultado esperado

Al crear la definicion:

- Se crea o actualiza `ml-training-opt-lab-pipeline`.
- No se ejecutan jobs inmediatamente.
- `artifacts/local_outputs/run_state.json` incluye `pipeline_name`.

Al ejecutar el pipeline:

- `run_state.json` incluye `pipeline_execution_arn`.
- SageMaker crea jobs asociados a la ejecucion.
- Si F1 cumple el umbral `MinF1ForRegistration=0.50`, se ejecuta `RegisterChurnModel`.

Parametros del Pipeline:

| Parametro | Default |
|---|---|
| `InputDataS3Uri` | `s3://<S3_BUCKET>/processing/input/churn_features.csv` |
| `ModelApprovalStatus` | `PendingManualApproval` |
| `MinF1ForRegistration` | `0.50` |

## Validacion local

1. Abre `artifacts/local_outputs/run_state.json`.
2. Confirma `pipeline_name`.
3. Si ejecutaste el pipeline, confirma `pipeline_execution_arn`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Pipelines.
3. Busca `ml-training-opt-lab-pipeline`.
4. Abre el Pipeline.
5. Revisa el grafo y confirma los steps esperados.
6. Abre `Parameters` y confirma los valores default.
7. Si ejecutaste el pipeline, abre `Executions`.
8. Selecciona la ejecucion mas reciente.
9. Revisa cada step y su estado.
10. Si un step falla, abre el detalle del step.
11. Navega al Processing Job o Training Job asociado.
12. Abre CloudWatch Logs desde el job fallido.

## Outputs esperados si ejecutas el pipeline

```text
s3://<S3_BUCKET>/processing/pipeline/metadata/
s3://<S3_BUCKET>/output/pipeline/
s3://<S3_BUCKET>/evaluation/pipeline/
s3://<S3_BUCKET>/reports/pipeline/
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| Se crea un Processing Job al crear pipeline | Se uso `SageMaker Session` normal en lugar de `PipelineSession`. | El codigo actual usa `pipeline_session`; verifica que estas ejecutando `src.create_pipeline` actualizado. |
| Error `ParameterString is not JSON serializable` | Version anterior intentaba serializar parametros en una llamada no compatible. | Usa la version actual del codigo; valida que `create_pipeline.py` usa `PipelineSession`. |
| `not authorized to perform: sagemaker:AddTags` en `CreateProcessingJob` | El rol de ejecucion de SageMaker no tiene permiso para etiquetar jobs creados por el Pipeline. SageMaker Pipelines agrega tags automaticamente a los jobs de cada step. | Actualiza la infraestructura con `python -m src.deploy_infra` o `bash scripts/lab.sh step 01` para aplicar la politica IAM que incluye `sagemaker:AddTags`; luego ejecuta de nuevo `python -m src.run_pipeline`. |
| Pipeline falla en step de training | Datos procesados ausentes o permisos insuficientes. | Abre el step, luego el Training Job y CloudWatch Logs. |
| No se registra el modelo | F1 no supera `MinF1ForRegistration`. | Revisa `EvaluateChurnModel` y el Condition Step. |

## Limpieza de recursos

Crear el Pipeline no ejecuta compute. Ejecutarlo si crea jobs. El Pipeline y versiones registradas se eliminan en el paso 12.
