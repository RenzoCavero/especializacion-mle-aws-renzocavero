# 05 - SageMaker Training Jobs

## Objetivo

Entrenar un modelo baseline de churn con SageMaker Training Jobs y guardar el artefacto `model.tar.gz` en S3.

## Que vas a construir o validar

Vas a crear un Training Job con nombre similar a:

```text
ml-training-opt-lab-baseline-<timestamp>-<instance>
```

El job entrena un modelo `sklearn.linear_model.LogisticRegression` usando:

| Entrada | Ruta S3 |
|---|---|
| Train | `s3://<S3_BUCKET>/input/train/train.csv` |
| Validation | `s3://<S3_BUCKET>/input/validation/validation.csv` |

Estos archivos no se escriben manualmente. Los crea el Processing Job del paso 04 a partir del Offline Store de SageMaker Feature Store:

```text
Feature Store Offline Store
  -> Athena materialization
  -> Processing Job
  -> s3://<S3_BUCKET>/input/train/train.csv
  -> s3://<S3_BUCKET>/input/validation/validation.csv
```

Esto es la forma indirecta y recomendada de usar Feature Store para training: el Training Job recibe datasets versionables en S3, mientras el Offline Store conserva la historia de features.

El artefacto queda en:

```text
s3://<S3_BUCKET>/output/baseline/<training-job>/output/model.tar.gz
```

## Conceptos clave

- Training Job: ejecucion gestionada de entrenamiento en SageMaker.
- Script Mode: forma de ejecutar un script propio dentro de una imagen administrada.
- Model artifact: paquete `model.tar.gz` que contiene el modelo entrenado.
- Metric definitions: expresiones que SageMaker usa para extraer metricas desde logs.
- Offline Store indirecto: patron donde Feature Store alimenta un dataset historico mediante Processing/Athena, y el Training Job consume el resultado en S3.

## Donde queda el preprocesamiento del modelo

En este laboratorio, el one-hot encoding ocurre antes del Training Job, dentro del Processing Job del paso 04:

```text
Feature Store Offline Store
  -> Athena
  -> Processing Job
  -> one-hot encoding
  -> train.csv / validation.csv / test.csv
  -> Training Job
```

El Training Job recibe columnas ya numericas. Luego `training/train.py` entrena un `sklearn.pipeline.Pipeline` que contiene:

```text
StandardScaler -> LogisticRegression
```

El artefacto `model.joblib` guarda:

- El pipeline `StandardScaler + LogisticRegression`.
- La lista `feature_columns` que el modelo espera.
- Metricas de validacion.

Importante: el one-hot encoder no queda guardado como objeto dentro del modelo actual. Queda aplicado en los CSVs generados por Processing. Por eso, si en inferencia envias datos crudos con columnas como `plan_type`, `country` y `device_type`, necesitas aplicar la misma transformacion antes de invocar el modelo.

Opciones comunes para produccion:

| Opcion | Como funciona | Cuando usarla |
|---|---|---|
| Preprocesamiento dentro del artefacto del modelo | Entrenar un `sklearn Pipeline` con `ColumnTransformer`/`OneHotEncoder` y guardar todo en `model.joblib`. | Recomendado cuando quieres que el endpoint reciba datos crudos y el modelo se encargue de transformar. |
| Preprocesamiento en `inference.py` | El script de inferencia recibe JSON/CSV crudo, aplica one-hot encoding y ordena columnas antes de llamar al modelo. | Util cuando el preprocesamiento es simple y quieres mantener una sola imagen de inferencia. |
| SageMaker Inference Pipeline | Un contenedor transforma datos y otro contenedor ejecuta el modelo. | Util cuando el preprocesamiento es pesado o se comparte entre varios modelos. |
| Preprocesamiento upstream | Batch job, streaming job o aplicacion cliente envia al endpoint columnas ya codificadas. | Util en batch inference o cuando ya tienes una capa de feature serving controlada. |

Para este laboratorio educativo, la opcion elegida mantiene visible el flujo de datos:

```text
Processing = preparar dataset
Training = entrenar modelo
Inference futura = reutilizar contrato de features y aplicar la misma transformacion
```

En un sistema productivo, la opcion mas robusta suele ser guardar el encoder junto con el modelo o incluir la transformacion en el codigo de inferencia. Asi reduces el riesgo de training-serving skew, es decir, diferencias entre como transformas datos al entrenar y como los transformas al predecir.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa el paso 04.

3. Confirma que existen:

   ```text
   s3://<S3_BUCKET>/input/train/train.csv
   s3://<S3_BUCKET>/input/validation/validation.csv
   ```

4. Confirma que `TRAINING_INSTANCE_TYPE` y `TRAINING_INSTANCE_TYPE_FALLBACKS` estan definidos en `.env`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-05-training
```

Con Bash o Git Bash:

```bash
bash scripts/run_baseline_training.sh
```

En Windows PowerShell:

```powershell
.\scripts\run_baseline_training.ps1
```

Con Python:

```bash
python -m src.submit_training_job
```

Internamente:

1. `src.submit_training_job` crea un estimator `SKLearn`.
2. Usa imagen administrada `sklearn` version `1.2-1`.
3. Usa `training/train.py` como entry point.
4. Sube el directorio `training/` a S3 bajo `code/`.
5. Usa canales `train` y `validation`.
6. Registra metricas `validation:accuracy`, `validation:precision`, `validation:recall`, `validation:f1` y `validation:roc_auc`.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/run_baseline_training.sh` |
| Wrapper PowerShell | `scripts/run_baseline_training.ps1` |
| Modulo que envia el Training Job a SageMaker | `src/submit_training_job.py` |
| Codigo remoto ejecutado en el Training Job | `training/train.py` |
| Directorio subido como source dir | `training/` |
| Dependencias del contenedor de training | `training/requirements.txt` |

Hiperparametros baseline:

| Hiperparametro | Valor |
|---|---|
| `C` | `1.0` |
| `max-iter` | `250` |
| `class-weight` | `balanced` |
| `random-state` | `42` |

## Scripts y parametros principales

| Necesidad | Archivo |
|---|---|
| Cambiar como se envia el Training Job | `src/submit_training_job.py` |
| Cambiar hiperparametros baseline standalone | `src/submit_training_job.py`, funcion `build_estimator` |
| Cambiar hiperparametros baseline dentro del Pipeline | `src/create_pipeline.py` |
| Cambiar algoritmo o pipeline scikit-learn | `training/train.py` |
| Cambiar dependencias del contenedor de training | `training/requirements.txt` |
| Cambiar carga de `train.csv` y `validation.csv` | `training/utils.py` |
| Cambiar metricas capturadas por SageMaker | `src/submit_training_job.py`, constante `METRIC_DEFINITIONS`, y los `print()` en `training/train.py` |
| Cambiar instancia o fallbacks de Training | `.env`, `.env.example`, `src/config.py` |
| Ver workflow completo | `lab/14_workflow_and_scripts_reference.md` |

## Resultado esperado

La terminal debe mostrar metricas como:

```text
validation:accuracy=...
validation:precision=...
validation:recall=...
validation:f1=...
validation:roc_auc=...
```

Archivos y estado local:

```text
artifacts/local_outputs/run_state.json
```

El estado debe incluir:

- `baseline_training_job_name`.
- `baseline_model_artifact_s3_uri`.
- `baseline_training_instance_type`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Training > Training jobs.
3. Busca `ml-training-opt-lab-baseline-*`.
4. Verifica que el estado sea `Completed`.
5. Abre el detalle del job.
6. Revisa `Hyperparameters` y confirma `C`, `max-iter`, `class-weight` y `random-state`.
7. Revisa `Input data configuration` y confirma canales `train` y `validation`.
8. Abre las rutas de entrada y confirma que apuntan a:
   - `s3://<S3_BUCKET>/input/train/train.csv`.
   - `s3://<S3_BUCKET>/input/validation/validation.csv`.
9. Revisa `Output` y copia la ruta S3 del model artifact.
10. Revisa `Metrics` para ver las metricas capturadas.
11. Abre CloudWatch Logs desde el detalle del job.
12. Busca `Reporting training SUCCESS`.
13. Ve a S3 y confirma que existe `model.tar.gz`.

## Diferencia con otras opciones de `Jobs`

En SageMaker Studio puedes ver varias pestanas bajo `Jobs`. Para este paso usa `Training`, porque el script envia un SageMaker Training Job desde codigo.

| Pestana | Cuando usarla | Relacion con este laboratorio |
|---|---|---|
| `Training` | Entrenamiento reproducible con scripts, contenedores, datos en S3, metricas y artefactos. | Se usa en el paso 05 y en los trials de HPO del paso 07. |
| `Notebook jobs` | Ejecucion no interactiva o programada de notebooks. | No se usa aqui; seria util para reportes periodicos o analisis exploratorio automatizado. |
| `JumpStart training` | Fine-tuning o entrenamiento de modelos preconstruidos de SageMaker JumpStart. | No se usa aqui; este laboratorio entrena un modelo propio con `training/train.py`. |

Si ves varios jobs `ml-train-hpo-...` en `Jobs > Training`, son Training Jobs hijos creados por el Tuning Job del paso 07. El Tuning Job padre se valida en `Amazon SageMaker AI > Hyperparameter tuning jobs`.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `ResourceLimitExceeded` | Sin cuota para la instancia solicitada. | El script prueba fallbacks. Ajusta `TRAINING_INSTANCE_TYPE_FALLBACKS` o solicita cuota. |
| `No CSV files found in channel` | No existen datasets procesados. | Reejecuta el paso 04. |
| Error binario de pandas/numpy | Se instalaron dependencias incompatibles dentro del contenedor. | Manten `training/requirements.txt` vacio como esta en el repo. |
| `AccessDenied` leyendo S3 | Rol de SageMaker sin permisos al bucket. | Revisa el rol creado en el paso 01. |

## Limpieza de recursos

La instancia de entrenamiento se libera al terminar. El artefacto en S3 y los logs en CloudWatch permanecen para evaluacion, registro y auditoria.
