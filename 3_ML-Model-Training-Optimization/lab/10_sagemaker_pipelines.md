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

## Diseno realista con HPO y seleccion de modelo

En un caso real, el Data Scientist suele empezar con un baseline para tener una referencia clara. Despues ejecuta HPO para buscar mejores hiperparametros. El resultado de HPO no deberia desplegarse automaticamente sin evaluacion y gobierno.

Flujo recomendado:

```text
BuildTrainingDataset
  -> TrainBaseline
  -> TuneModel
  -> ExtractBestHPOModel
  -> EvaluateBaseline
  -> EvaluateCandidate
  -> CompareModels
  -> CheckQualityGate
  -> RegisterModel
```

### Que hace `TuneModel`

`TuneModel` es el step de Hyperparameter Tuning. Lanza varios Training Jobs hijos con distintas combinaciones de hiperparametros y optimiza una metrica objetivo, por ejemplo:

```text
objective metric = validation:f1
```

Ejemplo conceptual:

```text
TuneModel
  -> trial 001: C=0.1, max_iter=200, validation:f1=0.71
  -> trial 002: C=1.0, max_iter=300, validation:f1=0.76
  -> trial 003: C=5.0, max_iter=250, validation:f1=0.74
```

El objetivo de `TuneModel` es responder:

```text
Que hiperparametros generan el mejor desempeno en validacion?
```

### Que hace `ExtractBestHPOModel`

`ExtractBestHPOModel` identifica el mejor Training Job hijo creado por HPO y extrae la informacion necesaria para el resto del pipeline:

```text
best_training_job_name
best_model_artifact_s3_uri
best_hyperparameters
best_objective_metric_value
```

Ejemplo:

```text
HPO job: churn-hpo-001

Child jobs:
  churn-hpo-001-001 -> validation:f1 = 0.71
  churn-hpo-001-002 -> validation:f1 = 0.76
  churn-hpo-001-003 -> validation:f1 = 0.74

ExtractBestHPOModel:
  best_training_job = churn-hpo-001-002
  best_model_artifact = s3://.../churn-hpo-001-002/output/model.tar.gz
  best_hyperparameters = {...}
```

Despues de HPO tienes dos opciones validas:

| Opcion | Flujo | Cuando usarla |
|---|---|---|
| Registrar el mejor artefacto de HPO | Evaluar `best_model_artifact_s3_uri` en test, comparar contra baseline/champion y registrar si pasa los gates. | Flujo simple y comun para primeras versiones MLOps. |
| Reentrenar un modelo final | Usar `best_hyperparameters` en un Training Job final con el dataset final, evaluar y registrar ese artefacto. | Flujo mas riguroso cuando quieres entrenar con mas datos o separar busqueda de hiperparametros del modelo final. |

La opcion mas conservadora en produccion suele ser:

```text
HPO encuentra hiperparametros
  -> Training Job final usa esos hiperparametros
  -> Evaluacion en test no visto
  -> Comparacion contra baseline o champion
  -> Registro en Model Registry
  -> Aprobacion
  -> Despliegue
```

Evita desplegar directamente desde HPO. Usa gates como:

```text
candidate_f1 >= baseline_f1 + minimum_delta
candidate_recall >= required_recall
candidate_roc_auc >= threshold
data_quality_checks = passed
manual_approval = required
```

## Donde entra Feature Store en un pipeline real

Feature Store entra antes del entrenamiento y tambien antes de la inferencia.

Para entrenamiento:

```text
Raw events or curated data
  -> Feature engineering
  -> Feature Store Offline Store
  -> BuildTrainingDataset
  -> train/validation/test datasets in S3
  -> Training or HPO
```

Para inferencia real-time:

```text
Request with customer_id
  -> GetRecord from Online Store
  -> Build model payload
  -> Invoke endpoint
```

HPO no lee directamente Feature Store. HPO entrena con datasets finales en S3. El Offline Store es la fuente historica que un step de Processing puede consultar para construir esos datasets.

## Combinar datos curados de S3 con Feature Store

En proyectos reales es normal que el dataset de entrenamiento combine varias fuentes:

```text
Curated S3 customer table
  customer_id, segment, acquisition_channel

Feature Store Offline Store
  customer_id, event_time, engagement_score, payment_failures_last_90d

Curated S3 labels table
  customer_id, churn_label, label_date
```

El step `BuildTrainingDataset`, normalmente implementado como Processing Step, puede:

1. Leer tablas curadas desde S3.
2. Leer features historicas desde Offline Store usando S3, AWS Glue Data Catalog o Amazon Athena.
3. Unir las fuentes por `customer_id` y ventanas de tiempo.
4. Aplicar reglas de point-in-time correctness.
5. Validar schema, nulos, rangos y duplicados.
6. Aplicar transformaciones compartidas de feature engineering.
7. Separar train/validation/test.
8. Escribir los datasets finales en S3.

Flujo:

```text
Curated S3 data
    |
    +--> BuildTrainingDataset Processing Step
    |
Feature Store Offline Store
    |
    v
Join + validation + point-in-time filtering + split
    |
    v
s3://.../datasets/churn/train/train.csv
s3://.../datasets/churn/validation/validation.csv
s3://.../datasets/churn/test/test.csv
```

Luego Training Jobs y HPO leen solo esos outputs finales de S3.

La separacion limpia es:

```text
Feature Store / curated S3 = fuentes
Processing Step = constructor del dataset
S3 train/validation/test = inputs de entrenamiento
Training/HPO = modelado
Model Registry = gobierno del modelo
```

Nota importante: si usas features con timestamps, el join debe ser point-in-time correct. Para cada `label_date`, usa solamente features disponibles antes de esa fecha. Esto evita data leakage, es decir, entrenar con informacion que no habria estado disponible al momento real de predecir.

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

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general para crear pipeline | `scripts/lab.sh step 10` |
| Modulo que crea o actualiza la definicion | `src/create_pipeline.py` |
| Modulo que inicia una ejecucion | `src/run_pipeline.py` |
| Codigo remoto de `ProcessChurnFeatures` | `processing/processing_entrypoint.py` |
| Codigo remoto de `TrainChurnBaseline` | `training/train.py` |
| Codigo remoto de `EvaluateChurnModel` | `processing/evaluation_entrypoint.py` |
| Registro condicional | `RegisterModel` de SageMaker SDK dentro de `src/create_pipeline.py` |

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
