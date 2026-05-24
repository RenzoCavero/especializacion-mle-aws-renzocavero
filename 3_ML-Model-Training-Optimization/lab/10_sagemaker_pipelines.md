# 10 - SageMaker Pipelines

## Objetivo

Crear una definicion de SageMaker Pipeline que automatiza ingesta de features, procesamiento, entrenamiento, evaluacion y registro condicional.

## Que vas a construir o validar

Vas a crear o actualizar:

```text
PIPELINE_NAME=ml-training-opt-lab-pipeline
```

El Pipeline incluye estos steps:

| Step | Funcion |
|---|---|
| `IngestCuratedFeatures` | Leer `curated/` e ingestar records en Feature Store. |
| `ProcessChurnFeatures` | Preparar train, validation, test y metadata. |
| `TrainChurnBaseline` | Entrenar un candidato baseline. |
| `EvaluateChurnModel` | Calcular metricas sobre test. |
| `CheckF1BeforeRegister` | Validar umbral minimo de F1. |
| `RegisterChurnModel` | Registrar el modelo si la condicion se cumple. |

Este Pipeline puede usarse para reentrenamiento. Cada vez que existan nuevos datos en `curated/` o nuevas filas en Feature Store, puedes ejecutar de nuevo el Pipeline para reconstruir el dataset, entrenar un nuevo candidato baseline, evaluarlo y registrarlo si supera el umbral de calidad.

El comando `python -m src.lab_runner step 10` solo crea o actualiza la definicion del Pipeline. Para ejecutar un reentrenamiento debes iniciar una ejecucion con `python -m src.run_pipeline` o `make run-pipeline`.

Importante: este Pipeline base no ejecuta HPO. Es util para reentrenamientos controlados con hiperparametros fijos. Para un flujo con busqueda de hiperparametros, este laboratorio incluye una variante opcional llamada:

```text
HPO_PIPELINE_NAME=ml-training-opt-lab-hpo-pipeline
```

La variante HPO agrega un `TuningStep` administrado por SageMaker Pipelines.

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
| `IngestCuratedFeatures` | `processing/feature_ingestion_entrypoint.py` y `src/feature_pipeline.py` | Paso 03, `src.submit_feature_ingestion_job` | Lee `curated/churn_features.csv`, aplica transformaciones compartidas y llama `PutRecord`. |
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

1. El Pipeline usa el mismo entrypoint de ingesta del paso 03, por lo que puede actualizar Feature Store desde `CuratedFeaturesS3Uri`.
2. El Pipeline usa el mismo entrypoint del paso 04, por lo que puede materializar datos desde el Offline Store via Athena cuando `FeatureSource=offline_store`.
3. El Pipeline no ejecuta HPO. Usa un baseline con:

   ```text
   C=1.0
   max-iter=250
   class-weight=balanced
   random-state=42
   ```

4. El Pipeline registra el modelo con `RegisterModel` si la condicion de F1 se cumple.
5. El paso 09 standalone agrega metadata adicional, contrato de features, `training_report.md` y `model_card.md`.
6. Si quieres que el Pipeline incluya HPO, comparacion de modelos o reportes custom, tendrias que agregar steps adicionales.

## Pipeline opcional con HPO

El repositorio tambien incluye una definicion opcional de Pipeline con Hyperparameter Tuning. Este Pipeline no reemplaza al baseline; lo complementa para mostrar un patron mas cercano a produccion.

Steps esperados:

| Step | Funcion |
|---|---|
| `IngestCuratedFeaturesForHPO` | Ingestar features curadas en Feature Store antes de construir el dataset. |
| `ProcessChurnFeaturesForHPO` | Leer el Offline Store via Athena y crear train, validation y test. |
| `TuneChurnModel` | Ejecutar un Tuning Job administrado por SageMaker con varios Training Jobs hijos. |
| `EvaluateBestHPOModel` | Evaluar el mejor artefacto producido por HPO sobre el split de test. |
| `CheckHPOF1BeforeRegister` | Aplicar un gate de F1 antes del registro. |
| `RegisterBestHPOModel-RegisterModel` | Registrar el mejor candidato de HPO si cumple el gate. |

Este Pipeline usa el servicio administrado de Hyperparameter Tuning de SageMaker. No es un bucle manual dentro de un script. SageMaker crea el Tuning Job, lanza los Training Jobs hijos, compara la metrica objetivo `validation:f1` y expone el mejor modelo al siguiente step.

Hiperparametros explorados:

| Hiperparametro | Tipo | Rango |
|---|---|---|
| `C` | Continuo logaritmico | `0.01` a `10.0` |
| `max-iter` | Entero | `150` a `450` |
| `class-weight` | Categorico | `balanced`, `none` |

Configuracion de costo controlado:

| Variable | Default | Uso |
|---|---|---|
| `HPO_MAX_JOBS` | `4` | Numero total de Training Jobs hijos. |
| `HPO_MAX_PARALLEL_JOBS` | `1` | Numero de jobs en paralelo. |

Buenas practicas que muestra esta variante:

1. El dataset se construye antes de HPO desde Feature Store Offline Store.
2. HPO entrena desde datasets finales en S3, no directamente desde Feature Store.
3. El mejor modelo de HPO se evalua en test antes de registrarse.
4. El registro queda en `PendingManualApproval`.
5. El despliegue queda fuera del pipeline de entrenamiento.

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

## Pipeline de entrenamiento vs pipeline de despliegue

El Pipeline de este laboratorio es un pipeline de entrenamiento y registro. Su responsabilidad termina cuando registra un candidato en Model Registry:

```text
Process -> Train -> Evaluate -> CheckQualityGate -> RegisterModel
```

Un pipeline de despliegue es otro workflow. Normalmente empieza despues de la aprobacion humana del Model Package:

```text
Model Package Approved
  -> EventBridge
  -> Deployment pipeline
  -> Staging deploy
  -> Smoke tests
  -> Production approval
  -> Production deploy
```

La separacion es saludable porque entrenamiento y despliegue tienen riesgos distintos:

| Pipeline | Pregunta que responde | Ejemplos de steps |
|---|---|---|
| Training pipeline | El modelo candidato es suficientemente bueno para registrarse? | Processing, Training, HPO, Evaluation, RegisterModel. |
| Deployment pipeline | El modelo aprobado puede servirse de forma segura? | CreateModel, deploy staging, smoke tests, approval, update production endpoint, rollback. |

El evento que conecta ambos mundos suele ser un cambio en Model Registry:

```text
ModelApprovalStatus = Approved
```

Amazon EventBridge puede capturar ese evento y disparar CodePipeline, Step Functions o una Lambda que inicie el workflow de despliegue.

Ejemplo de responsabilidades:

```text
EventBridge:
  detecta "SageMaker Model Package State Change" con status Approved

Step Functions o CodePipeline:
  ordena los pasos de despliegue

CodeBuild o Lambda:
  ejecuta scripts que llaman CreateModel, CreateEndpointConfig, UpdateEndpoint
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

2. Completa al menos los pasos 01, 02, 03 y 04.

3. Confirma que existe el Offline Store y la tabla Glue del Feature Group.

4. Confirma que existe la fuente curada que el pipeline puede volver a ingestar:

   ```text
   s3://<S3_BUCKET>/curated/churn_features.csv
   ```

5. Confirma que existe el snapshot de fallback:

   ```text
   s3://<S3_BUCKET>/processing/input/churn_features.csv
   ```

6. Confirma que el Model Package Group existe o que tienes permisos para crearlo cuando el pipeline registre.

7. Si ves errores de permisos con Athena, `PutRecord` o AddTags, actualiza infraestructura:

   ```bash
   bash scripts/lab.sh step 01
   ```

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

Tambien puedes usar los wrappers directos:

```bash
bash scripts/create_pipeline.sh
```

En Windows PowerShell:

```powershell
.\scripts\create_pipeline.ps1
```

Ejecucion opcional del pipeline:

```bash
make run-pipeline
```

O:

```bash
python -m src.run_pipeline
```

Con wrappers:

```bash
bash scripts/run_pipeline.sh
```

En Windows PowerShell:

```powershell
.\scripts\run_pipeline.ps1
```

Crear o actualizar el Pipeline opcional con HPO:

```bash
make create-hpo-pipeline
```

O:

```bash
python -m src.create_hpo_pipeline
```

Si prefieres ejecutar solo los modulos Python, usa esta secuencia desde la raiz del laboratorio:

```bash
python -m src.create_hpo_pipeline
python -m src.run_hpo_pipeline
```

El primer comando crea o actualiza la definicion `ml-training-opt-lab-hpo-pipeline`. El segundo comando inicia una ejecucion real, por lo que SageMaker crea los steps `IngestCuratedFeaturesForHPO`, `ProcessChurnFeaturesForHPO`, `TuneChurnModel`, `EvaluateBestHPOModel`, `CheckHPOF1BeforeRegister` y `RegisterBestHPOModel-RegisterModel`.

Con Bash o Git Bash:

```bash
bash scripts/create_hpo_pipeline.sh
```

En Windows PowerShell:

```powershell
.\scripts\create_hpo_pipeline.ps1
```

Ejecutar el Pipeline opcional con HPO:

```bash
make run-hpo-pipeline
```

O:

```bash
python -m src.run_hpo_pipeline
```

Con Bash o Git Bash:

```bash
bash scripts/run_hpo_pipeline.sh
```

En Windows PowerShell:

```powershell
.\scripts\run_hpo_pipeline.ps1
```

Advertencia: ejecutar el pipeline crea nuevos Processing Jobs, Training Jobs y posiblemente nuevos Model Packages. Eso genera costo adicional.
La variante HPO genera mas costo que el Pipeline baseline porque crea varios Training Jobs hijos.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general para crear pipeline baseline | `scripts/lab.sh step 10` |
| Wrapper directo para crear pipeline baseline | `scripts/create_pipeline.sh`, `scripts/create_pipeline.ps1` |
| Wrapper directo para ejecutar pipeline baseline | `scripts/run_pipeline.sh`, `scripts/run_pipeline.ps1` |
| Wrapper directo para crear pipeline HPO | `scripts/create_hpo_pipeline.sh`, `scripts/create_hpo_pipeline.ps1` |
| Wrapper directo para ejecutar pipeline HPO | `scripts/run_hpo_pipeline.sh`, `scripts/run_hpo_pipeline.ps1` |
| Modulo que crea o actualiza la definicion | `src/create_pipeline.py` |
| Modulo que inicia una ejecucion | `src/run_pipeline.py` |
| Modulo que crea o actualiza la definicion HPO | `src/create_hpo_pipeline.py` |
| Modulo que inicia una ejecucion HPO | `src/run_hpo_pipeline.py` |
| Codigo remoto de `IngestCuratedFeatures` | `processing/feature_ingestion_entrypoint.py` |
| Codigo compartido de feature engineering | `src/feature_pipeline.py`, montado dentro del Processing Job |
| Codigo remoto de `ProcessChurnFeatures` | `processing/processing_entrypoint.py` |
| Codigo remoto de `TrainChurnBaseline` | `training/train.py` |
| Codigo remoto de los Training Jobs hijos de HPO | `training/train.py` |
| Codigo remoto de `EvaluateChurnModel` | `processing/evaluation_entrypoint.py` |
| Registro condicional | `RegisterModel` de SageMaker SDK dentro de `src/create_pipeline.py` |
| Registro condicional HPO | `RegisterModel` de SageMaker SDK dentro de `src/create_hpo_pipeline.py` |

## Scripts y parametros principales

| Necesidad | Archivo |
|---|---|
| Cambiar steps del Pipeline baseline | `src/create_pipeline.py` |
| Cambiar parametros enviados al ejecutar Pipeline baseline | `src/run_pipeline.py` |
| Cambiar steps del Pipeline HPO | `src/create_hpo_pipeline.py` |
| Cambiar rangos de HPO del Pipeline | `src/create_hpo_pipeline.py` |
| Cambiar parametros enviados al ejecutar Pipeline HPO | `src/run_hpo_pipeline.py` |
| Cambiar umbral `MinF1ForRegistration` por defecto | `src/run_pipeline.py`, `src/run_hpo_pipeline.py` |
| Cambiar codigo remoto de ingesta | `processing/feature_ingestion_entrypoint.py`, `src/feature_pipeline.py` |
| Cambiar codigo remoto de processing | `processing/processing_entrypoint.py`, `processing/utils.py` |
| Cambiar codigo remoto de training | `training/train.py` |
| Cambiar codigo remoto de evaluacion | `processing/evaluation_entrypoint.py` |
| Ver workflow completo | `lab/14_workflow_and_scripts_reference.md` |

## Resultado esperado

Al crear la definicion:

- Se crea o actualiza `ml-training-opt-lab-pipeline`.
- No se ejecutan jobs inmediatamente.
- `artifacts/local_outputs/run_state.json` incluye `pipeline_name`.

Al crear la definicion HPO:

- Se crea o actualiza `ml-training-opt-lab-hpo-pipeline`.
- No se ejecutan jobs inmediatamente.
- `artifacts/local_outputs/run_state.json` incluye `hpo_pipeline_name`.

Al ejecutar el pipeline:

- `run_state.json` incluye `pipeline_execution_arn`.
- SageMaker crea jobs asociados a la ejecucion.
- Si F1 cumple el umbral `MinF1ForRegistration=0.50`, se ejecuta `RegisterChurnModel`.

Al ejecutar el Pipeline HPO:

- `run_state.json` incluye `hpo_pipeline_execution_arn`.
- SageMaker crea un Tuning Job desde el step `TuneChurnModel`.
- El Tuning Job crea varios Training Jobs hijos.
- El mejor artefacto de HPO se evalua en `EvaluateBestHPOModel`.
- Si F1 cumple el umbral, se ejecuta `RegisterBestHPOModel-RegisterModel`.

Parametros del Pipeline:

| Parametro | Default |
|---|---|
| `InputDataS3Uri` | `s3://<S3_BUCKET>/processing/input/churn_features.csv`, usado como fallback. |
| `CuratedFeaturesS3Uri` | `s3://<S3_BUCKET>/curated/churn_features.csv`, usado por `IngestCuratedFeatures`. |
| `FeatureSource` | `offline_store` |
| `AthenaOutputS3Uri` | `s3://<S3_BUCKET>/athena/query-results/` |
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
5. Revisa el grafo y confirma los steps esperados:
   - `IngestCuratedFeatures`.
   - `ProcessChurnFeatures`.
   - `TrainChurnBaseline`.
   - `EvaluateChurnModel`.
   - `CheckF1BeforeRegister`.
   - `RegisterChurnModel-RegisterModel`.
6. Abre `Parameters` y confirma los valores default.
7. Si ejecutaste el pipeline, abre `Executions`.
8. Selecciona la ejecucion mas reciente.
9. Revisa cada step y su estado.
10. Si un step falla, abre el detalle del step.
11. Navega al Processing Job o Training Job asociado.
12. Abre CloudWatch Logs desde el job fallido.

Para validar el Pipeline HPO:

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Pipelines.
3. Busca `ml-training-opt-lab-hpo-pipeline`.
4. Abre el Pipeline y revisa el grafo.
5. Confirma que aparece `TuneChurnModel`.
6. Ejecuta el Pipeline o abre la ejecucion mas reciente.
7. Cuando llegue al step `TuneChurnModel`, abre el detalle del step.
8. Ve a Amazon SageMaker > Hyperparameter tuning jobs.
9. Busca el Tuning Job creado por el Pipeline.
10. Abre `Best training job` para identificar el mejor hijo.
11. En `Training jobs`, confirma que existen jobs hijos con sufijos como `001`, `002`, `003`.
12. Regresa al Pipeline y confirma que `EvaluateBestHPOModel` finaliza en `Completed`.
13. Si el gate pasa, revisa Amazon SageMaker > Model Registry > `churn-model-package-group`.

El step `EvaluateBestHPOModel` toma el artefacto del mejor Training Job desde:

```text
s3://<S3_BUCKET>/output/pipeline-hpo/<BEST_TRAINING_JOB_NAME>/output/model.tar.gz
```

Ese path debe coincidir con el `output_path` configurado para los Training Jobs hijos de HPO.

## Outputs esperados si ejecutas el pipeline

```text
s3://<S3_BUCKET>/processing/pipeline/metadata/
s3://<S3_BUCKET>/feature-store/pipeline-ingestion/metadata/
s3://<S3_BUCKET>/output/pipeline/
s3://<S3_BUCKET>/evaluation/pipeline/
s3://<S3_BUCKET>/reports/pipeline/
s3://<S3_BUCKET>/feature-store/hpo-pipeline-ingestion/metadata/
s3://<S3_BUCKET>/processing/hpo-pipeline/metadata/
s3://<S3_BUCKET>/output/pipeline-hpo/
s3://<S3_BUCKET>/evaluation/pipeline-hpo/
s3://<S3_BUCKET>/reports/pipeline-hpo/
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| Se crea un Processing Job al crear pipeline | Se uso `SageMaker Session` normal en lugar de `PipelineSession`. | El codigo actual usa `pipeline_session`; verifica que estas ejecutando `src.create_pipeline` actualizado. |
| Error `ParameterString is not JSON serializable` | Version anterior intentaba serializar parametros en una llamada no compatible. | Usa la version actual del codigo; valida que `create_pipeline.py` usa `PipelineSession`. |
| `not authorized to perform: sagemaker:AddTags` en `CreateProcessingJob` | El rol de ejecucion de SageMaker no tiene permiso para etiquetar jobs creados por el Pipeline. SageMaker Pipelines agrega tags automaticamente a los jobs de cada step. | Actualiza la infraestructura con `python -m src.deploy_infra` o `bash scripts/lab.sh step 01` para aplicar la politica IAM que incluye `sagemaker:AddTags`; luego ejecuta de nuevo `python -m src.run_pipeline`. |
| `not authorized to perform: sagemaker:PutRecord` en `IngestCuratedFeatures` | El pipeline intenta actualizar Feature Store desde un Processing Step y el rol no tiene permiso. | Reejecuta paso 01 para aplicar la politica IAM actualizada. |
| `not authorized to perform: athena:StartQueryExecution` | El Pipeline usa el Offline Store via Athena y el rol no fue actualizado. | Ejecuta `bash scripts/lab.sh step 01` para actualizar el rol con permisos de Athena. |
| `ProcessChurnFeatures` espera o cae a fallback | Offline Store escribe asincronicamente o la tabla Glue aun no tiene filas. | Espera unos minutos. Si `ALLOW_FEATURE_SNAPSHOT_FALLBACK=true`, revisa metadata para confirmar si uso fallback. |
| Pipeline falla en step de training | Datos procesados ausentes o permisos insuficientes. | Abre el step, luego el Training Job y CloudWatch Logs. |
| No se registra el modelo | F1 no supera `MinF1ForRegistration`. | Revisa `EvaluateChurnModel` y el Condition Step. |
| `TuneChurnModel` falla con `not authorized to perform: sagemaker:ListTrainingJobsForHyperParameterTuningJob` | El Tuning Job puede haber terminado, pero SageMaker Pipelines necesita listar los Training Jobs hijos para identificar el mejor artefacto y continuar. | Ejecuta `python -m src.deploy_infra` o `bash scripts/lab.sh step 01` para actualizar el rol con `sagemaker:ListTrainingJobsForHyperParameterTuningJob`. Luego usa `Retry` en la ejecucion fallida o lanza una nueva ejecucion con `python -m src.run_hpo_pipeline`. |
| `EvaluateBestHPOModel` falla con `No S3 objects found under .../output/pipeline-hpo/best-model/.../model.tar.gz` | La definicion del Pipeline apuntaba a un prefijo que no coincide con el `output_path` real de los Training Jobs hijos. | Actualiza el codigo, ejecuta `python -m src.create_hpo_pipeline` para subir la nueva definicion y lanza una nueva ejecucion con `python -m src.run_hpo_pipeline`. |
| El Pipeline HPO falla en `TuneChurnModel` por cuota o capacidad | Cuota de Training insuficiente, capacidad no disponible o algun child Training Job fallo. | Revisa Hyperparameter tuning jobs y CloudWatch Logs. Si es cuota, reduce `HPO_MAX_JOBS` o usa una instancia disponible. |
| El Pipeline HPO tarda mas que el baseline | HPO ejecuta varios Training Jobs hijos. | Es esperado. Para laboratorio, usa `HPO_MAX_JOBS=2` o `4` y `HPO_MAX_PARALLEL_JOBS=1`. |

## Limpieza de recursos

Crear un Pipeline no ejecuta compute. Ejecutarlo si crea jobs. El Pipeline baseline, el Pipeline HPO y las versiones registradas se eliminan en el paso 12.
