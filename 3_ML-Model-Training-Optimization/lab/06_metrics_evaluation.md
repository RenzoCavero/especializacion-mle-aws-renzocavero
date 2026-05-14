# 06 - Metricas y evaluacion reproducible

## Objetivo

Evaluar el modelo baseline con el dataset de test y guardar metricas reproducibles.

## Que vas a construir o validar

Vas a crear un Processing Job de evaluacion con nombre similar a:

```text
ml-training-opt-lab-eval-baseline-<timestamp>-<instance>
```

El job usa:

| Entrada | Fuente |
|---|---|
| Modelo | `baseline_model_artifact_s3_uri` en `run_state.json` |
| Test data | `s3://<S3_BUCKET>/input/test/test.csv` |

Y genera:

| Salida | Ruta |
|---|---|
| Metricas JSON en S3 | `s3://<S3_BUCKET>/evaluation/baseline/evaluation_metrics.json` |
| Reporte Markdown en S3 | `s3://<S3_BUCKET>/reports/baseline/baseline_evaluation_report.md` |
| Copia local | `artifacts/local_outputs/evaluation/baseline/evaluation_metrics.json` |

## Conceptos clave

- Test set: datos no usados durante entrenamiento ni validacion.
- F1: balance entre precision y recall.
- ROC AUC: capacidad de separar clases usando scores.
- Matriz de confusion: conteo de aciertos y errores por clase.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa el paso 05.

3. Confirma que `run_state.json` contiene `baseline_model_artifact_s3_uri`.

4. Confirma que existe:

   ```text
   s3://<S3_BUCKET>/input/test/test.csv
   ```

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-06-evaluation
```

Con Python:

```bash
python -m src.evaluate_model --model-name baseline
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 06
```

No hay wrapper `.ps1` especifico para este paso. En Windows usa el comando Python.

Internamente:

1. `src.evaluate_model` crea un `SKLearnProcessor`.
2. Monta el modelo baseline y `test.csv`.
3. Ejecuta `processing/evaluation_entrypoint.py`.
4. Extrae `model.tar.gz`.
5. Calcula metricas.
6. Escribe JSON y Markdown.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general | `scripts/lab.sh step 06` |
| Modulo que envia el Processing Job de evaluacion | `src/evaluate_model.py` |
| Codigo remoto ejecutado en el Processing Job | `processing/evaluation_entrypoint.py` |
| Librerias auxiliares montadas en el contenedor | `processing/` |
| Artefacto de modelo evaluado | `s3://<S3_BUCKET>/output/baseline/<training-job>/output/model.tar.gz` |

## Resultado esperado

La terminal debe mostrar:

```text
evaluation:f1=...
evaluation:recall=...
evaluation:precision=...
evaluation:roc_auc=...
```

El JSON local debe incluir:

- `model_name`.
- `metrics`.
- `classification_metrics`.
- `test_rows`.
- `feature_columns`.

## Validacion local

1. Abre `artifacts/local_outputs/evaluation/baseline/evaluation_metrics.json`.
2. Revisa `metrics.f1`, `metrics.recall`, `metrics.precision`, `metrics.roc_auc` y `metrics.accuracy`.
3. Revisa `metrics.confusion_matrix`.
4. Abre `artifacts/local_outputs/run_state.json` y confirma `baseline_metrics_s3_uri`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Processing > Processing jobs.
3. Busca `ml-training-opt-lab-eval-baseline-*`.
4. Verifica estado `Completed`.
5. Abre el detalle del job.
6. Revisa inputs: `test-data`, `model-artifact` y `processing-source`.
7. Revisa outputs: `evaluation` y `reports`.
8. Abre CloudWatch Logs.
9. Busca las lineas `evaluation:f1`, `evaluation:recall`, `evaluation:precision` y `evaluation:roc_auc`.
10. Ve a Amazon S3 > bucket del laboratorio > `evaluation/baseline/`.
11. Verifica `evaluation_metrics.json`.
12. Ve a `reports/baseline/` y verifica `baseline_evaluation_report.md`.

## Por que no aparece en `Jobs > Model evaluation`

El paso 06 no usa la funcionalidad administrada de `Model evaluation` de SageMaker Studio.

Este laboratorio evalua el modelo ejecutando:

```bash
python -m src.evaluate_model --model-name baseline
```

Ese modulo crea un `SKLearnProcessor` y lanza un SageMaker Processing Job. Dentro del contenedor se ejecuta `processing/evaluation_entrypoint.py`, se descarga el artefacto `model.tar.gz`, se lee `test.csv` y se calculan metricas como F1, recall, precision, accuracy y ROC AUC.

Por eso, el resultado esperado no aparece en `SageMaker Studio > Jobs > Model evaluation`. La validacion correcta para este paso es:

| Resultado | Donde verlo |
|---|---|
| Job de evaluacion | Amazon SageMaker > Processing > Processing jobs |
| Logs de metricas | CloudWatch Logs del Processing Job |
| JSON de metricas | S3 > `evaluation/baseline/evaluation_metrics.json` |
| Reporte Markdown | S3 > `reports/baseline/baseline_evaluation_report.md` |
| Copia local | `artifacts/local_outputs/evaluation/baseline/evaluation_metrics.json` |

Usa `Jobs > Model evaluation` cuando crees una evaluacion administrada desde Studio o desde la API especifica de evaluacion de modelos. En este laboratorio la evaluacion es reproducible por codigo y queda versionada como artefactos en S3.

## Interpretacion rapida

| Metrica | Como leerla |
|---|---|
| F1 | Metrica principal para comparar candidatos. |
| Recall | Alto recall reduce clientes en riesgo no detectados. |
| Precision | Alta precision reduce acciones de retencion innecesarias. |
| ROC AUC | Evalua separacion general entre clases. |
| Accuracy | Secundaria; puede ser enganosa con clases desbalanceadas. |

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `No model artifact found for baseline` | No se ejecuto training o `run_state.json` esta incompleto. | Reejecuta paso 05. |
| `No CSV file found under /opt/ml/processing/test` | No existe `test.csv`. | Reejecuta paso 04. |
| Falla al extraer `model.tar.gz` | Artefacto ausente o corrupto. | Revisa el Training Job y la ruta S3 del modelo. |
| Job falla sin detalle claro | Error dentro del contenedor. | Abre CloudWatch Logs del Processing Job. |
| `Jobs > Model evaluation` aparece vacio | El paso 06 no crea una evaluacion administrada de Studio; crea un Processing Job con codigo propio. | Valida en `Processing > Processing jobs`, CloudWatch Logs y S3 bajo `evaluation/baseline/`. |
