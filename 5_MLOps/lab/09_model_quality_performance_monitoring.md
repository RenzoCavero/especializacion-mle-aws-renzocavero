# 09 - Model quality nativo y fallback custom

## Objetivo

Configurar el flujo nativo de SageMaker Model Quality Monitor para medir performance del modelo con predicciones capturadas, `InferenceId` y ground truth retrasado.

## Que vas a construir o validar

Vas a reutilizar el endpoint desplegado en los pasos 07/08, validar que Data Capture tenga `Input` y `Output`, invocar el endpoint con `InferenceId`, subir ground truth en el formato que SageMaker Model Monitor espera, crear un baseline de Model Quality, crear un `MonitoringSchedule` nativo de tipo `ModelQuality` y crear una alarma de CloudWatch sobre la metrica nativa `f1`. Si AWS no permite crear el schedule nativo, el laboratorio deja preparado un fallback custom con EventBridge -> Lambda -> SageMaker Processing Job.

## Input del paso

- Endpoint y modelo aprobados por los pasos 06 y 07.
- Datos generados por el paso 02:
  - `data/local_cache/inference_normal.jsonl`.
  - `data/local_cache/inference_normal_ground_truth.jsonl`.
- Data Capture habilitado con `Input` y `Output`.
- Variables principales:
  - `CAPTURE_ENDPOINT_OUTPUT=true`.
  - `MODEL_QUALITY_SCHEDULE_NAME`.
  - `MODEL_QUALITY_JOB_DEFINITION_NAME`.
  - `MODEL_QUALITY_PROBLEM_TYPE=BinaryClassification`.
  - `MODEL_QUALITY_INFERENCE_ATTRIBUTE=prediction`.
  - `MODEL_QUALITY_PROBABILITY_ATTRIBUTE=probability`.
  - `MODEL_QUALITY_PROBABILITY_THRESHOLD=0.5`.
  - `MODEL_QUALITY_MONITORING_CRON_EXPRESSION`.
  - `MODEL_QUALITY_ALARM_NAME`.
  - `CUSTOM_MODEL_QUALITY_CRON_EXPRESSION`.
  - `CUSTOM_MODEL_QUALITY_ALARM_NAME`.

## Output esperado del paso

- Endpoint existente validado con captura `Input` y `Output`.
- Capturas del endpoint en S3 bajo `data-capture/<endpoint>/`.
- Ground truth compatible con SageMaker bajo `model-quality/ground-truth/yyyy/mm/dd/hh/`.
- Baseline nativo bajo `model-quality/baseline/`.
- Evidencia auxiliar bajo `model-quality/predictions/` y `model-quality/ground-truth-debug/`.
- Monitoring schedule `mlops-model-quality-schedule`.
- Definicion de monitoring inline dentro del schedule. Si AWS rechaza esa ruta, el script prueba como fallback `mlops-model-quality-job-def`.
- Alarma `mlops-model-quality-alarm`.
- Fallback custom, solo si el schedule nativo queda `native_model_quality_schedule_unavailable`:
  - EventBridge schedule `mlops-custom-model-quality-schedule`.
  - Lambda trigger `mlops-custom-model-quality-trigger`.
  - Processing Job custom con codigo `processing/custom_model_quality.py`.
  - Alarma `mlops-custom-model-quality-alarm` sobre la metrica custom `MLOps/Lab / ModelQualityF1`.
- Metadata local:
  - `endpoint_deployment.json`.
  - `data_capture.json`.
  - `model_quality_endpoint_validation.json`.
  - `model_quality_capture.json`.
  - `model_quality_baseline.json`.
  - `model_quality_schedule.json`.
  - `custom_model_quality_schedule.json`.
  - `model_quality_alarm.json`.
  - `custom_model_quality_alarm.json`.

## Conceptos claves

Model Quality Monitor no puede calcular accuracy, F1 o AUC solo con features de entrada. Necesita unir:

```text
endpoint output capturado + InferenceId + ground truth posterior
```

Por eso este paso usa Data Capture con `Input` y `Output`. El endpoint devuelve una respuesta JSON simple:

```json
{"prediction": 1, "probability": 0.5479}
```

El script `src.capture_model_quality_data` envia cada solicitud con `InferenceId`. SageMaker Data Capture usa ese identificador como llave del evento capturado. Luego el script escribe ground truth en S3 con el mismo identificador:

```json
{
  "groundTruthData": {"data": "1", "encoding": "CSV"},
  "eventMetadata": {"eventId": "<InferenceId>"},
  "eventVersion": "0"
}
```

El schedule nativo usa:

- `EndpointInput` para leer capturas del endpoint.
- `ground_truth_input` en el environment del monitoring job para leer labels retrasados.
- `BaselineConfig` para leer `model-quality/baseline/statistics.json` y `model-quality/baseline/constraints.json`.
- `InferenceAttribute=$.prediction`.
- `ProbabilityAttribute=$.probability`.
- `MonitoringType=ModelQuality`.

Como el endpoint devuelve tanto una clase discreta (`prediction`) como una probabilidad (`probability`), el schedule no envia `ProbabilityThresholdAttribute`. Ese threshold se usa cuando el output trae solo probabilidad y SageMaker debe convertirla a clase; aqui la clase ya viene en el JSON.

El laboratorio usa boto3 low-level porque SageMaker Python SDK v3 ya no expone `sagemaker.model_monitor.ModelQualityMonitor`. Para acercarse al flujo de los notebooks oficiales de SDK v2, el script crea primero el schedule con un `MonitoringJobDefinition` inline. Si SageMaker devuelve `InternalFailure`, prueba un nombre fallback y luego la ruta explicita `CreateModelQualityJobDefinition`.

El baseline oficial de Model Quality debe producir secciones como `binary_classification_metrics` y `binary_classification_constraints`. Si la imagen analyzer devuelve un baseline tipo Data Quality (`features`, `monitoring_config`, `version`), el laboratorio calcula las metricas localmente desde `prediction`, `probability` y `label`, y sobrescribe `statistics.json` y `constraints.json` con el schema de Model Quality esperado por SageMaker.

El Processing Job del baseline fuerza `analysis_type=MODEL_QUALITY` para que el contenedor analyzer trate el dataset como performance de modelo y no como drift de features. Si aun asi el contenedor devuelve artefactos de Data Quality, el lab conserva el resultado del job como evidencia y publica los artefactos Model Quality sintetizados.

`model-quality/baseline/baseline.csv` si es necesario para crear el baseline de Model Quality. Es el dataset etiquetado que contiene, por fila, la prediccion del modelo, la probabilidad y el label real. Sin ese dataset no se pueden calcular F1, accuracy, precision, recall o AUC. Despues de generar `statistics.json` y `constraints.json`, el schedule usa esos JSON como referencia; no recalcula el baseline desde `baseline.csv` en cada ejecucion. Aun asi, el CSV se conserva para auditoria y para regenerar los artefactos si cambian los criterios.

En produccion, el baseline de Model Quality no tiene que salir necesariamente del training job. Lo importante es que sea un conjunto representativo con:

```text
prediccion del modelo + probabilidad del modelo + label real
```

Ese conjunto puede venir de un holdout/test set evaluado durante training, de una validacion offline posterior o de una ventana inicial de produccion ya etiquetada. En este laboratorio se simula con el endpoint real: se envian 50 registros normales, se guardan sus predicciones y se unen con labels sinteticos conocidos para construir `baseline.csv`.

## Ejemplo de artefactos Model Quality

El `baseline.csv` de Model Quality tiene un schema distinto al baseline de Data Quality. Aqui no se comparan features; se comparan metricas de performance.

Ejemplo reducido de `model-quality/baseline/baseline.csv`:

```csv
probability,prediction,label
0.82,1,1
0.31,0,0
0.62,1,0
0.18,0,0
```

El Processing Job con la imagen prebuilt `sagemaker-model-monitor-analyzer` lee ese CSV y genera `statistics.json` y `constraints.json`. Para Model Quality, `statistics.json` contiene metricas baseline, no distribuciones de features.

Ejemplo reducido de `model-quality/baseline/statistics.json`:

```json
{
  "version": 0.0,
  "binary_classification_metrics": {
    "confusion_matrix": {
      "0": {
        "0": 28,
        "1": 3
      },
      "1": {
        "0": 4,
        "1": 15
      }
    },
    "accuracy": {
      "value": 0.86,
      "standard_deviation": "NaN"
    },
    "precision": {
      "value": 0.83,
      "standard_deviation": "NaN"
    },
    "recall": {
      "value": 0.79,
      "standard_deviation": "NaN"
    },
    "f1": {
      "value": 0.81,
      "standard_deviation": "NaN"
    },
    "auc": {
      "value": 0.91,
      "standard_deviation": "NaN"
    }
  }
}
```

`constraints.json` contiene los umbrales que se evaluaran en ejecuciones futuras. En este laboratorio los umbrales se derivan del baseline y de los minimos configurados en `.env`, por ejemplo `MODEL_QUALITY_F1_THRESHOLD` y `MODEL_QUALITY_AUC_THRESHOLD`.

Ejemplo reducido de `model-quality/baseline/constraints.json`:

```json
{
  "version": 0.0,
  "binary_classification_constraints": {
    "accuracy": {
      "threshold": 0.774,
      "comparison_operator": "LessThanThreshold"
    },
    "f1": {
      "threshold": 0.729,
      "comparison_operator": "LessThanThreshold"
    },
    "auc": {
      "threshold": 0.819,
      "comparison_operator": "LessThanThreshold"
    },
    "false_positive_rate": {
      "threshold": 0.197,
      "comparison_operator": "GreaterThanThreshold"
    }
  }
}
```

La lectura practica es: si en una ejecucion futura el F1 cae por debajo del threshold, o si una tasa de error sube por encima del threshold, Model Quality Monitor puede producir violations y publicar metricas para CloudWatch.

## Fallback custom sin MonitoringSchedule nativo

Si `CreateMonitoringSchedule` o `CreateModelQualityJobDefinition` falla con `InternalFailure`, el lab no se queda bloqueado. `src.create_custom_model_quality_schedule --if-native-unavailable` crea esta ruta:

```text
EventBridge cron
-> Lambda mlops-custom-model-quality-trigger
-> SageMaker Processing Job custom
-> processing/custom_model_quality.py
-> CloudWatch custom metrics MLOps/Lab
-> CloudWatch Alarm mlops-custom-model-quality-alarm
-> EventBridge alarm rule en paso 11
-> SNS email y Step Functions
```

El Processing Job custom no usa el `MonitoringSchedule` nativo. Lee los JSONL auxiliares que genera `src.capture_model_quality_data`:

- `s3://.../model-quality/predictions/.../predictions.jsonl`.
- `s3://.../model-quality/ground-truth-debug/.../ground_truth_debug.jsonl`.

Luego une por `inference_id`, calcula `accuracy`, `f1` y `auc`, escribe un reporte bajo `s3://.../model-quality/custom/reports/` y publica metricas custom en CloudWatch:

```text
Namespace: MLOps/Lab
Metric: ModelQualityF1
Dimension: EndpointName=<endpoint>
```

La ejecucion manual usa:

```bash
python -m src.start_custom_model_quality_job --wait
```

La ejecucion programada usa el cron:

```env
CUSTOM_MODEL_QUALITY_CRON_EXPRESSION=cron(0 * ? * * *)
```

`CUSTOM_MODEL_QUALITY_CRON_EXPRESSION` debe ser un cron de EventBridge. Para una ejecucion inmediata no uses `NOW` en el fallback custom; usa `python -m src.start_custom_model_quality_job --wait`.

Este fallback es util para laboratorios o cuentas donde el plano de control de SageMaker rechaza el schedule nativo, pero se sigue queriendo evidencia cloud, metricas, alarmas y feedback loop.

## Que revisar en EventBridge y Lambda

Cuando el fallback custom se crea correctamente, en la consola de EventBridge puedes verlo en:

```text
Amazon EventBridge -> Scheduler -> Scheduled rules (legacy)
```

Esto es esperado. El laboratorio usa `events.put_rule(...)` con `ScheduleExpression`, por eso AWS lo muestra como una regla programada legacy. No necesitas migrarla al nuevo EventBridge Scheduler para este laboratorio. La regla correcta es:

```text
mlops-custom-model-quality-schedule
```

Debe estar en estado `Enabled`, sobre el event bus `default`, con tipo `Scheduled Standard` y target hacia:

```text
Lambda: mlops-custom-model-quality-trigger
```

La Lambda no calcula metricas. Su responsabilidad es pequena: recibir el evento del cron y crear un SageMaker Processing Job custom. El flujo real es:

```text
EventBridge scheduled rule
-> Lambda mlops-custom-model-quality-trigger
-> SageMaker CreateProcessingJob
-> processing/custom_model_quality.py dentro del container
-> S3 report
-> CloudWatch custom metrics
-> CloudWatch alarm
```

El archivo que ves en Lambda como `lambda_function.py` corresponde a `lambdas/custom_model_quality_trigger.py` empaquetado por `src.create_custom_model_quality_schedule`. El handler genera un nombre unico de job, lee variables de entorno y ejecuta:

```python
sagemaker.create_processing_job(...)
```

La parte clave es el entrypoint:

```python
"ContainerEntrypoint": [
  "python3",
  "/opt/ml/processing/code/custom_model_quality.py"
]
```

Ese script se descarga desde:

```text
s3://.../model-quality/custom/code/custom_model_quality.py
```

y corre dentro del Processing Job. Alli se leen las predicciones y ground truth debug:

```text
s3://.../model-quality/predictions/
s3://.../model-quality/ground-truth-debug/
```

Luego se unen por `inference_id`, se calculan `accuracy`, `f1` y `auc`, se escribe `model_quality_report.json` en S3 y se publican metricas:

```text
Namespace: MLOps/Lab
Metric: ModelQualityF1
Dimension: EndpointName=mlops-lab-endpoint
```

Si ejecutas manualmente:

```bash
python -m src.start_custom_model_quality_job --wait
```

no esperes logs nuevos en Lambda, porque este comando evita EventBridge y Lambda. Crea el Processing Job directamente desde tu terminal para validar rapido el evaluator custom.

## Simulacion de alarma custom

Para probar CloudWatch sin esperar una degradacion real, usa:

```bash
python -m src.simulate_model_quality_alarm --wait
```

Este comando hace tres cosas:

1. Valida que el endpoint este listo para Model Quality.
2. Invoca el endpoint con trafico normal, pero escribe labels opuestos a la prediccion del modelo (`label_mode=opposite-prediction`).
3. Ejecuta manualmente el Processing Job custom y espera a que termine.

El resultado esperado es:

| Servicio | Evidencia esperada |
|---|---|
| SageMaker Processing Jobs | Job con nombre `mlops-lab-custom-model-quality-...` en estado `Completed`. |
| S3 | Reporte bajo `s3://.../model-quality/custom/reports/`. |
| CloudWatch Metrics | Metrica `MLOps/Lab / ModelQualityF1` con dimension `EndpointName=mlops-lab-endpoint`. |
| CloudWatch Alarm | `mlops-custom-model-quality-alarm` cambia a `ALARM` si `ModelQualityF1 < MODEL_QUALITY_F1_THRESHOLD`. |
| Lambda | No necesariamente cambia, porque esta ejecucion manual no pasa por Lambda. |
| EventBridge schedule | Sigue `Enabled` y ejecutara la Lambda en el siguiente horario del cron. |

La simulacion usa los S3 URI exactos de la corrida adversa que acaba de generar, por ejemplo:

```text
s3://.../model-quality/predictions/<run_id>/predictions.jsonl
s3://.../model-quality/ground-truth-debug/<run_id>/ground_truth_debug.jsonl
```

Esto evita que el evaluator mezcle la corrida adversa con capturas normales anteriores dentro de la ventana `CUSTOM_MODEL_QUALITY_WINDOW_HOURS`. Si se evaluara todo el prefijo de las ultimas 24 horas, un volumen alto de labels normales podria mantener el F1 por encima del umbral y la alarma quedaria en `OK` aunque la ultima corrida haya sido adversa.

Para una evaluacion manual general sobre la ventana configurada, usa:

```bash
python -m src.start_custom_model_quality_job --wait
```

Para una evaluacion manual acotada a un archivo especifico, puedes pasar rutas explicitas:

```bash
python -m src.start_custom_model_quality_job --wait \
  --predictions-s3-uri s3://.../model-quality/predictions/<run_id>/predictions.jsonl \
  --ground-truth-debug-s3-uri s3://.../model-quality/ground-truth-debug/<run_id>/ground_truth_debug.jsonl
```

El email por SNS no se configura en este paso. Para recibir notificaciones por correo cuando el alarm pase a `ALARM`, ejecuta el paso 11 y confirma la suscripcion SNS:

```bash
python -m src.lab_runner step 11
```

Sin esa confirmacion, CloudWatch puede entrar en `ALARM`, pero SNS no entregara correo.

Para probar el email de Model Quality de punta a punta, ejecuta primero el paso 11 y confirma la suscripcion SNS. Luego revisa que `mlops-custom-model-quality-alarm` este en `OK`; EventBridge solo envia correo cuando la alarma cambia hacia `ALARM`:

```bash
aws cloudwatch describe-alarms \
  --alarm-names mlops-custom-model-quality-alarm \
  --query "MetricAlarms[0].StateValue" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

Si esta en `ALARM`, espera entre 5 y 10 minutos despues del ultimo datapoint malo para que vuelva a `OK` con `TreatMissingData=notBreaching`. Cuando este en `OK`, ejecuta:

```bash
python -m src.simulate_model_quality_alarm --wait
```

La alarma usa metricas nativas de SageMaker Model Monitor en el namespace:

```text
aws/sagemaker/Endpoints/model-metrics
```

con dimensiones:

```text
Endpoint=<endpoint>
MonitoringSchedule=<model-quality-schedule>
```

El feedback loop del paso 11 interpreta la severidad de Model Quality como
degradacion relativa de F1 contra `MODEL_QUALITY_F1_THRESHOLD`. Con el umbral
default `0.70`, un F1 de `0.50` representa una caida de `28.57%` y se clasifica
como `high`; un F1 de `0.30` representa `57.14%` y se clasifica como
`critical`. La tabla usada por `lambdas/feedback_handler/lambda_function.py` es:

| Degradacion de F1 | Severidad |
|---:|---|
| 0% | `none` |
| Mayor a 0% y menor a 10% | `low` |
| 10% a menor de 25% | `medium` |
| 25% a menor de 50% | `high` |
| 50% o mas | `critical` |

Este paso ya no recrea el endpoint por defecto. El endpoint se crea en el paso 07 y se valida en el paso 08. El paso 09 solo ejecuta `src.validate_model_quality_endpoint` para confirmar que el endpoint existente esta `InService`, que Data Capture esta activo y que captura `Input` y `Output`. Si esa validacion falla, corrige el endpoint con:

```bash
python -m src.deploy_model --wait
```

Usa `--force-recreate` solo si necesitas reemplazar un endpoint/configuracion antigua que no puede actualizarse limpiamente:

```bash
python -m src.deploy_model --wait --force-recreate
```

Data Capture no cambia el tipo de respuesta del endpoint. La respuesta JSON `{"prediction": ..., "probability": ...}` viene de `training/inference.py`, empaquetado y configurado en el SageMaker Model por `src.deploy_model`.

`InferenceId` tampoco es configuracion del endpoint. Se envia en cada llamada `InvokeEndpoint` desde `src.capture_model_quality_data` para que SageMaker pueda unir la prediccion capturada con el ground truth posterior.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.configure_data_capture` | `.env`, `.env.cloud` | `DescribeEndpoint`, `DescribeEndpointConfig` | `artifacts/local_outputs/data_capture.json` | Ninguno | Documentar la configuracion Data Capture existente. |
| 2 | `src.validate_model_quality_endpoint` | `.env`, `.env.cloud` | Endpoint y EndpointConfig actuales | `artifacts/local_outputs/model_quality_endpoint_validation.json` | Ninguno | Fallar temprano si el endpoint no captura `Input` y `Output`. |
| 3 | `src.capture_model_quality_data --traffic-type normal --limit 50` | `data/local_cache/inference_normal.jsonl`, `data/local_cache/inference_normal_ground_truth.jsonl` | `InvokeEndpoint` con `InferenceId` | `artifacts/local_outputs/model_quality_predictions.jsonl`, `artifacts/local_outputs/model_quality_ground_truth.jsonl`, `artifacts/local_outputs/model_quality_capture.json` | Data Capture bajo `s3://.../data-capture/<endpoint>/...`, debug bajo `s3://.../model-quality/predictions/...`, ground truth bajo `s3://.../model-quality/ground-truth/yyyy/mm/dd/hh/ground_truth_<run_id>.jsonl` | Generar predicciones capturadas y labels retrasados con la misma llave. |
| 4 | `src.generate_model_quality_baseline --wait` | `artifacts/local_outputs/model_quality_predictions.jsonl`, `artifacts/local_outputs/model_quality_ground_truth.jsonl` | Analyzer image y S3 baseline prefix | `artifacts/local_outputs/model_quality_baseline.json` | `s3://.../model-quality/baseline/baseline.csv`, `statistics.json`, `constraints.json` | Crear baseline de performance con `prediction`, `probability`, `label`. |
| 5 | `src.create_model_quality_schedule` | `artifacts/local_outputs/model_quality_baseline.json`, `artifacts/local_outputs/model_quality_capture.json` | Endpoint capture, ground truth prefix, baseline artifacts | `artifacts/local_outputs/model_quality_schedule.json` | `MonitoringSchedule` o evidencia `native_model_quality_schedule_unavailable` | Crear schedule nativo que ejecutaria jobs periodicos de Model Quality. |
| 6 | `src.create_custom_model_quality_schedule --if-native-unavailable` | `model_quality_schedule.json`, `processing/custom_model_quality.py`, `lambdas/custom_model_quality_trigger.py` | Lambda role, SageMaker execution role, EventBridge | `custom_model_quality_schedule.json` | EventBridge cron, Lambda trigger, codigo custom en S3 | Crear fallback si el schedule nativo no existe. |
| 7 | `src.create_model_quality_alarm` | `.env`, schedule metadata | CloudWatch | `artifacts/local_outputs/model_quality_alarm.json` | `mlops-model-quality-alarm` | Alertar si la metrica nativa `f1` baja del umbral. |
| 8 | `src.create_custom_model_quality_alarm` | `.env` | CloudWatch | `artifacts/local_outputs/custom_model_quality_alarm.json` | `mlops-custom-model-quality-alarm` | Alertar si la metrica custom `ModelQualityF1` baja del umbral. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Local input | `data/local_cache/inference_normal.jsonl` | Features usadas para invocar el endpoint en el baseline de Model Quality. |
| Local input | `data/local_cache/inference_normal_ground_truth.jsonl` | Labels sinteticos conocidos para esos registros. |
| Local output | `artifacts/local_outputs/model_quality_predictions.jsonl` | Predicciones devueltas por el endpoint, con `inference_id`. |
| Local output | `artifacts/local_outputs/model_quality_ground_truth.jsonl` | Labels locales unidos a cada `inference_id`. |
| S3 output | `s3://.../model-quality/ground-truth/yyyy/mm/dd/hh/` | Ground truth en formato SageMaker JSONL para el schedule. |
| S3 output | `s3://.../model-quality/baseline/baseline.csv` | Dataset `prediction,probability,label` usado por el Processing Job de baseline. |
| S3 output | `s3://.../model-quality/baseline/statistics.json` | Metricas baseline: accuracy, precision, recall, F1, AUC, matriz de confusion. |
| S3 output | `s3://.../model-quality/baseline/constraints.json` | Umbrales baseline que futuras ejecuciones comparan. |
| S3 output | `s3://.../model-quality/reports/` | Reportes de executions futuras del MonitoringSchedule. |
| S3 output | `s3://.../model-quality/custom/code/` | Codigo `custom_model_quality.py` usado por el Processing Job fallback. |
| S3 output | `s3://.../model-quality/custom/reports/` | Reportes JSON del Processing Job custom. |

## Prerrequisitos

- Pasos 02, 05, 06 y 07 completados.
- Permisos para:
  - `sagemaker-runtime:InvokeEndpoint`.
  - `sagemaker:CreateModelQualityJobDefinition`.
  - `sagemaker:CreateMonitoringSchedule`.
  - `sagemaker:DescribeEndpoint`.
  - `sagemaker:CreateEndpointConfig`.
  - `sagemaker:CreateProcessingJob`.
  - `s3:PutObject`.
  - `cloudwatch:PutMetricAlarm`.
  - `lambda:CreateFunction` y `events:PutRule` si se crea el fallback custom.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 09
```

Make equivalente:

```bash
make model-quality
```

Comandos individuales:

```bash
python -m src.configure_data_capture
python -m src.validate_model_quality_endpoint
python -m src.capture_model_quality_data --traffic-type normal --limit 50
python -m src.generate_model_quality_baseline --wait
python -m src.create_model_quality_schedule
python -m src.create_custom_model_quality_schedule --if-native-unavailable
python -m src.create_model_quality_alarm
python -m src.create_custom_model_quality_alarm
```

## Resultado esperado

El paso debe imprimir:

- `capture_modes` con `Input` y `Output`.
- `inference_id_used=true`.
- URI de ground truth en `model-quality/ground-truth/yyyy/mm/dd/hh/ground_truth_<run_id>.jsonl`.
- `constraints.json` de model quality bajo `model-quality/baseline/`.
- `status=created` o `status=existing` para `model_quality_schedule`.
- `schedule_route=inline_monitoring_job_definition` en el caso normal.
- Si el schedule nativo falla, `custom_model_quality_schedule.json` con `status=created`.
- Alarmas creadas en CloudWatch.

El primer execution real del schedule nativo puede tardar hasta el siguiente periodo horario definido por `MODEL_QUALITY_MONITORING_CRON_EXPRESSION`. Si usas `NOW` en el schedule nativo, espera algunos minutos para que Data Capture haya escrito los archivos antes de revisar resultados. El fallback custom usa `CUSTOM_MODEL_QUALITY_CRON_EXPRESSION` como cron de EventBridge y su ejecucion inmediata se hace con `python -m src.start_custom_model_quality_job --wait`.

## Validacion local

```bash
type artifacts\local_outputs\data_capture.json
type artifacts\local_outputs\model_quality_endpoint_validation.json
type artifacts\local_outputs\model_quality_capture.json
type artifacts\local_outputs\model_quality_baseline.json
type artifacts\local_outputs\model_quality_schedule.json
type artifacts\local_outputs\custom_model_quality_schedule.json
type artifacts\local_outputs\model_quality_alarm.json
type artifacts\local_outputs\custom_model_quality_alarm.json
```

Campos importantes:

```json
{
  "capture_modes": ["Input", "Output"],
  "inference_id_used": true,
  "monitoring_type": "ModelQuality",
  "schedule_route": "inline_monitoring_job_definition",
  "ground_truth_s3_uri": "s3://.../model-quality/ground-truth/2026/05/23/21/ground_truth_20260523214807.jsonl",
  "model_quality_constraints_s3_uri": "s3://.../model-quality/baseline/constraints.json",
  "inference_attribute": "prediction",
  "probability_attribute": "probability"
}
```

## Validacion en consola AWS

- SageMaker > Model dashboard > modelo `mlops-lab-endpoint-model`.
- En la seccion `Monitor schedule`, buscar `mlops-model-quality-schedule`.
- SageMaker > Processing jobs, revisar executions generados por el schedule.
- S3 > bucket del laboratorio:
  - `mlops-lab/lab/data-capture/`.
  - `mlops-lab/lab/model-quality/ground-truth/`.
  - `mlops-lab/lab/model-quality/reports/`.
- CloudWatch > Metrics > `aws/sagemaker/Endpoints/model-metrics`.
- CloudWatch > Metrics > `MLOps/Lab`.
- CloudWatch > Alarms > `mlops-model-quality-alarm`.
- CloudWatch > Alarms > `mlops-custom-model-quality-alarm`.

Validacion por CLI:

```bash
aws sagemaker describe-monitoring-schedule \
  --monitoring-schedule-name mlops-model-quality-schedule \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws sagemaker list-monitoring-executions \
  --monitoring-schedule-name mlops-model-quality-schedule \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws cloudwatch list-metrics \
  --namespace aws/sagemaker/Endpoints/model-metrics \
  --metric-name f1 \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws cloudwatch list-metrics \
  --namespace MLOps/Lab \
  --metric-name ModelQualityF1 \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

## Simular una alarma de Model Quality

Para probar CloudWatch, EventBridge y SNS sin esperar una degradacion real, usa ground truth artificialmente adverso. Este comando invoca el endpoint, pero escribe labels opuestos a la prediccion del modelo. Eso fuerza un F1 bajo y debe disparar `mlops-custom-model-quality-alarm` cuando el Processing Job custom publique la metrica.

```bash
python -m src.simulate_model_quality_alarm --wait
```

Comandos equivalentes:

```bash
python -m src.capture_model_quality_data --traffic-type normal --limit 50 --label-mode opposite-prediction
python -m src.start_custom_model_quality_job --wait
```

Usa este modo solo para pruebas de alarma. No lo uses para crear el baseline normal.

## Troubleshooting

Si `CreateMonitoringSchedule` o `CreateModelQualityJobDefinition` devuelve `InternalFailure`, revisa CloudTrail para esos eventos. El script guarda `service_error` en `model_quality_schedule.json` y deja el estado como `native_model_quality_schedule_unavailable`.

Si el baseline falla con:

```text
Probability threshold is not supported for DATA_QUALITY
```

el analyzer interpreto el Processing Job como baseline de Data Quality. El baseline de este laboratorio no envia `probability_threshold_attribute` al Processing Job; ese threshold se conserva solo para el schedule nativo de Model Quality. Despues de actualizar el codigo, no necesitas recrear endpoint: ejecuta de nuevo `python -m src.generate_model_quality_baseline --wait` y luego continua con `python -m src.create_model_quality_schedule`.

Si el baseline imprime:

```json
"has_binary_classification_constraints": false
```

quiere decir que el analyzer genero un baseline de Data Quality. La version actual del laboratorio lo corrige automaticamente y debe dejar:

```json
"synthesized_model_quality_artifacts": true,
"has_binary_classification_constraints": true
```

Si el schedule no produce metricas, valida:

- El endpoint tiene `Input` y `Output` en `DataCaptureConfig.CaptureOptions`.
- Las invocaciones fueron enviadas con `InferenceId`.
- El ground truth tiene `eventMetadata.eventId` igual al `InferenceId`.
- La respuesta del endpoint es JSON compatible con los atributos `prediction` y `probability`.
- Data Capture ya escribio objetos recientes en S3.

## Siguiente paso

Ejecuta `python -m src.lab_runner step 10` para crear el baseline de Data Quality. Ese baseline sigue siendo util para drift de features; el paso 09 cubre performance del modelo con labels.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.validate_model_quality_endpoint` | Validar contrato del endpoint para Model Quality. | `validate_model_quality_endpoint`. | Endpoint/EndpointConfig. | `model_quality_endpoint_validation.json`. |
| `src.capture_model_quality_data` | Invocar endpoint con `InferenceId` y escribir predicciones/ground truth. | `_parse_prediction`, `_resolve_label`, `capture_model_quality_data`. | `inference_normal.jsonl`, ground truth local. | `model_quality_capture.json`, JSONL local, S3 predictions y ground truth. |
| `src.generate_model_quality_baseline` | Crear baseline MQ con Processing Job y sintetizar artifacts si SageMaker genera schema DQ. | `_prepare_baseline_dataset`, `_build_model_quality_artifacts`, `_validate_or_synthesize_artifacts`. | `model_quality_capture.json`, `baseline.csv`. | `model_quality_baseline.json`, `statistics.json`, `constraints.json`. |
| `src.create_model_quality_schedule` | Crear MonitoringSchedule nativo de tipo `ModelQuality`. | `_inline_schedule_request`, `_model_quality_job_definition_request`, `_create_with_retries`. | Baseline MQ, endpoint, ground truth prefix. | `model_quality_schedule.json`, schedule nativo o status unavailable. |
| `src.create_custom_model_quality_schedule` | Fallback EventBridge -> Lambda -> Processing Job. | `_validate_eventbridge_schedule_expression`, `_upsert_lambda`. | `model_quality_schedule.json`, processor custom. | `custom_model_quality_schedule.json`, Lambda y EventBridge rule. |
| `src.create_model_quality_alarm` / `src.create_custom_model_quality_alarm` | Crear alarmas nativa y custom sobre F1. | `create_model_quality_alarm`, `create_custom_model_quality_alarm`. | Metadata de schedules. | `model_quality_alarm.json`, `custom_model_quality_alarm.json`. |

Para probar una alarma sin esperar degradacion real, usa `src.simulate_model_quality_alarm`. Ese script llama internamente a `capture_model_quality_data(label_mode="opposite-prediction")` y luego ejecuta el Processing Job custom.

Parametros modificables:

- `MODEL_QUALITY_F1_THRESHOLD`, `MODEL_QUALITY_AUC_THRESHOLD`, `MODEL_QUALITY_MIN_RECORDS`.
- `MODEL_QUALITY_START_TIME_OFFSET`, `MODEL_QUALITY_END_TIME_OFFSET`: ventana que lee el schedule nativo.
- `CUSTOM_MODEL_QUALITY_WINDOW_HOURS`: ventana que lee el fallback custom.
- `CUSTOM_MODEL_QUALITY_CRON_EXPRESSION`: cron de EventBridge para el fallback; no acepta `NOW`.
