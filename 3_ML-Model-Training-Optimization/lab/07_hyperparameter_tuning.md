# 07 - SageMaker Automatic Model Tuning

## Objetivo

Ejecutar Hyperparameter Tuning para buscar una configuracion mejor que el baseline y comparar ambos candidatos con evidencia.

## Que vas a construir o validar

Vas a crear un Tuning Job con nombre similar a:

```text
ml-train-hpo-<timestamp>-<instance>
```

El Tuning Job ejecuta varios Training Jobs y maximiza:

```text
validation:f1
```

Hiperparametros optimizados:

| Hiperparametro | Rango |
|---|---|
| `C` | `0.01` a `10.0`, escala logaritmica |
| `max-iter` | `150` a `450` |
| `class-weight` | `balanced` o `none` |

## Conceptos clave

- Tuning Job: orquestador de multiples entrenamientos con hiperparametros distintos.
- Trial: Training Job individual dentro de HPO.
- Objective metric: metrica usada para elegir el mejor trial.
- Best training job: trial con mejor valor de la metrica objetivo.

## De donde lee datos HPO

HPO no lee directamente SageMaker Feature Store ni el Offline Store.

En este laboratorio, el Tuning Job usa los mismos canales de S3 que un Training Job normal:

```text
s3://<S3_BUCKET>/input/train/train.csv
s3://<S3_BUCKET>/input/validation/validation.csv
```

Esos archivos fueron creados por el Processing Job del paso 04 a partir del snapshot:

```text
s3://<S3_BUCKET>/processing/input/churn_features.csv
```

El Offline Store queda disponible bajo:

```text
s3://<S3_BUCKET>/feature-store-offline/
```

pero no es la fuente directa usada por HPO en este laboratorio.

En una arquitectura mas productiva, podrias cambiar el flujo para que Processing lea desde el Offline Store usando S3, AWS Glue Data Catalog o Amazon Athena. Processing construiria el dataset historico, aplicaria transformaciones y escribiria `train.csv` y `validation.csv` en S3. Despues HPO seguiria entrenando desde esos archivos de S3:

```text
Offline Store -> Processing/Athena -> train.csv + validation.csv -> HPO
```

Esta separacion es importante: Feature Store conserva la historia y el schema; Processing construye datasets reproducibles; HPO ejecuta multiples Training Jobs sobre datasets ya preparados.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 04, 05 y 06.

3. Confirma que `.env` define:

   ```text
   HPO_MAX_JOBS=4
   HPO_MAX_PARALLEL_JOBS=1
   ```

4. Confirma que existen `train.csv` y `validation.csv` en S3.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-07-hpo
```

Con Bash o Git Bash:

```bash
bash scripts/run_hpo.sh
python -m src.compare_models
```

En Windows PowerShell:

```powershell
.\scripts\run_hpo.ps1
python -m src.compare_models
```

Con Python:

```bash
python -m src.submit_hpo_job
python -m src.evaluate_model --model-name optimized
python -m src.compare_models
```

Importante: `scripts/run_hpo.sh` y `scripts/run_hpo.ps1` ejecutan HPO y evaluacion del modelo optimizado, pero no ejecutan `src.compare_models`. Si usas esos wrappers, ejecuta `python -m src.compare_models` despues.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/run_hpo.sh` |
| Wrapper PowerShell | `scripts/run_hpo.ps1` |
| Modulo que crea el Tuning Job | `src/submit_hpo_job.py` |
| Servicio SageMaker usado | SageMaker Automatic Model Tuning con `HyperparameterTuner` |
| Codigo remoto ejecutado por cada trial de HPO | `training/train.py` |
| Modulo que evalua el modelo optimizado | `src/evaluate_model.py` |
| Codigo remoto usado para evaluacion | `processing/evaluation_entrypoint.py` |
| Modulo local que compara baseline vs optimized | `src/compare_models.py` |

## Resultado esperado

S3:

```text
s3://<S3_BUCKET>/output/hpo/
s3://<S3_BUCKET>/output/best_model/model.tar.gz
s3://<S3_BUCKET>/evaluation/optimized/evaluation_metrics.json
s3://<S3_BUCKET>/metrics/model_comparison.json
s3://<S3_BUCKET>/reports/model_comparison.md
```

Local:

```text
artifacts/local_outputs/evaluation/optimized/evaluation_metrics.json
artifacts/local_outputs/model_comparison.json
artifacts/local_outputs/model_comparison.md
artifacts/local_outputs/run_state.json
```

`run_state.json` debe incluir:

- `hpo_job_name`.
- `best_training_job_name`.
- `hpo_best_objective_metric`.
- `best_model_artifact_s3_uri`.
- `selected_model_name`.

## Validacion local

1. Abre `artifacts/local_outputs/model_comparison.json`.
2. Compara `baseline` y `optimized`.
3. Confirma `selected_model`.
4. Verifica que la regla sea seleccionar el mayor F1.

Es valido que el baseline gane en test aunque HPO haya encontrado un mejor modelo en validacion.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker AI > Hyperparameter tuning jobs.
3. Busca el tuning job padre, por ejemplo `ml-train-hpo-0514151220-m5-large`.
4. Verifica estado `Completed`.
5. Abre el Tuning Job.
6. En `Hyperparameter tuning job summary`, revisa:
   - `Status`.
   - `Approx. total training duration`.
   - `Creation time`.
7. Abre la pestana `Best training job`.
8. Confirma:
   - Nombre del best training job.
   - Estado `Completed`.
   - `Objective metric` = `validation:f1`.
   - Valor de la metrica objetivo.
9. Revisa `Best training job hyperparameters` para ver los valores ganadores, por ejemplo:
   - `C`.
   - `class-weight`.
   - `max-iter`.
10. Abre la pestana `Training jobs`.
11. Confirma que aparecen los trials creados por HPO, con nombres similares a:

   ```text
   ml-train-hpo-<timestamp>-m5-large-001-...
   ml-train-hpo-<timestamp>-m5-large-002-...
   ml-train-hpo-<timestamp>-m5-large-003-...
   ml-train-hpo-<timestamp>-m5-large-004-...
   ```

12. Si estas en SageMaker Studio > Jobs > Training, veras principalmente esos Training Jobs hijos. Eso es normal: son los trials que creo el Tuning Job.
13. Para ver el job padre, vuelve a Amazon SageMaker AI > Hyperparameter tuning jobs.
14. Ve a Amazon SageMaker > Processing > Processing jobs.
15. Busca `ml-training-opt-lab-eval-optimized-*`.
16. Verifica estado `Completed`.
17. Ve a S3 > `output/best_model/` y confirma `model.tar.gz`.
18. Ve a S3 > `metrics/` y confirma `model_comparison.json`.

## Advertencia de costos

HPO ejecuta multiples Training Jobs. Cada trial consume instancia de SageMaker. Mantener `HPO_MAX_JOBS` bajo es intencional para controlar costo en cuentas de estudiantes.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `ResourceLimitExceeded` | Sin cuota para la instancia de training. | Ajusta `TRAINING_INSTANCE_TYPE_FALLBACKS` o solicita cuota. |
| HPO tarda mas que training baseline | Ejecuta varios jobs. | Espera a que termine o baja `HPO_MAX_JOBS`. |
| `Baseline metrics missing` al comparar | No se ejecuto paso 06. | Ejecuta `python -m src.evaluate_model --model-name baseline`. |
| `Optimized metrics missing` | No se evaluo el mejor modelo. | Ejecuta `python -m src.evaluate_model --model-name optimized`. |
| Solo ves Training Jobs en SageMaker Studio | Studio muestra los trials hijos. | Abre Amazon SageMaker AI > Hyperparameter tuning jobs para ver el tuning job padre. |

## Limpieza de recursos

Los Training Jobs terminados no quedan activos, pero sus artefactos y logs permanecen. Revisa costos y limpia en el paso 12.
