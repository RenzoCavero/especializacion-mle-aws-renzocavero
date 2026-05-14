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

El artefacto queda en:

```text
s3://<S3_BUCKET>/output/baseline/<training-job>/output/model.tar.gz
```

## Conceptos clave

- Training Job: ejecucion gestionada de entrenamiento en SageMaker.
- Script Mode: forma de ejecutar un script propio dentro de una imagen administrada.
- Model artifact: paquete `model.tar.gz` que contiene el modelo entrenado.
- Metric definitions: expresiones que SageMaker usa para extraer metricas desde logs.

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
8. Revisa `Output` y copia la ruta S3 del model artifact.
9. Revisa `Metrics` para ver las metricas capturadas.
10. Abre CloudWatch Logs desde el detalle del job.
11. Busca `Reporting training SUCCESS`.
12. Ve a S3 y confirma que existe `model.tar.gz`.

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
