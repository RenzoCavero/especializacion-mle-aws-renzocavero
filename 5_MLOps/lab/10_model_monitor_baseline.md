# 10 - Data Quality monitoring

## Objetivo

Crear el flujo completo de Data Quality Monitoring en un solo paso: baseline,
monitoring schedule nativo o fallback custom, simulacion de drift, revision de
violations y alarma de CloudWatch.

## Que vas a construir o validar

Vas a crear un baseline de SageMaker Model Monitor para los datos de entrada,
programar la evaluacion periodica contra Data Capture, preparar un fallback con
EventBridge + Lambda + Processing Job si el schedule nativo falla, publicar la
metrica custom `DataQualityViolations` y crear la alarma activa de Data Quality.
El nombre activo depende de la ruta:

- `mlops-data-quality-alarm`: ruta nativa de Data Quality.
- `mlops-custom-data-quality-alarm`: fallback custom cuando el schedule nativo no
  esta disponible.

Este paso reemplaza la separacion anterior:

- Antiguo paso 10: baseline de Model Monitor.
- Antiguo paso 11: monitoring schedule, drift y violations.
- Antiguo paso 12: CloudWatch alarm.

## Input del paso

- Endpoint `mlops-lab-endpoint` desplegado y con Data Capture activo.
- Datos generados por el paso 02.
- Dataset baseline en S3 o datos locales en `data/local_cache/`.
- `SAGEMAKER_EXECUTION_ROLE_ARN`.
- Roles de Lambda/EventBridge si se requiere el fallback custom.
- Variables de `.env`: `MONITORING_CRON_EXPRESSION`, `CUSTOM_DATA_QUALITY_CRON_EXPRESSION`, `VIOLATIONS_METRIC_NAME`, `ALARM_NAME`, `CUSTOM_DATA_QUALITY_ALARM_NAME` y `ALARM_THRESHOLD`.

## Output esperado del paso

- `statistics.json` en S3.
- `constraints.json` en S3.
- Metadata local `baseline.json`.
- Monitoring schedule nativo `mlops-monitoring-schedule`, si SageMaker lo crea.
- Fallback custom, si el schedule nativo no esta disponible:
  - EventBridge rule `mlops-custom-data-quality-schedule`.
  - Lambda `mlops-custom-data-quality-trigger`.
  - Codigo custom en `s3://.../monitoring/custom/code/`.
- Trafico drift enviado al endpoint.
- Metadata local `monitoring_results.json`.
- Reporte local `monitoring_report.md`.
- Metrica custom `MLOps/Lab / DataQualityViolations`.
- CloudWatch Alarm `mlops-data-quality-alarm` o `mlops-custom-data-quality-alarm`.

## Conceptos claves

Data Quality Monitoring responde una pregunta distinta a Model Quality:

- Data Quality revisa si las features de entrada se parecen al baseline.
- Model Quality revisa si las predicciones siguen siendo buenas contra labels.

Un baseline es una fotografia estadistica del comportamiento esperado de las
features. No dice si el modelo es bueno; dice como se ven los datos cuando el
sistema esta en una condicion aceptada.

`statistics.json` contiene distribuciones, conteos, tipos inferidos, nulos y
resumenes por columna. `constraints.json` contiene el contrato que se evaluara
despues: tipos esperados, completitud, dominios categoricos y configuracion de
comparacion.

Ambos archivos los genera un SageMaker Processing Job con la imagen prebuilt:

```text
156813124566.dkr.ecr.us-east-1.amazonaws.com/sagemaker-model-monitor-analyzer
```

Esa imagen es el analyzer oficial de SageMaker Model Monitor. El laboratorio usa
boto3 low-level porque las APIs de alto nivel cambiaron entre versiones del
SageMaker Python SDK.

`baseline_monitor.csv` si es necesario para crear el baseline. El script lo
prepara con el mismo schema que recibe el endpoint: `record_id` y features, sin
`churned`. Una vez generados `statistics.json` y `constraints.json`, el schedule
nativo ya no lee el CSV en cada ejecucion, pero conviene conservarlo para
auditoria y regeneracion.

El schedule de Data Quality lee capturas de input del endpoint. En este
laboratorio Data Capture incluye `Input` y `Output` porque el paso 09 tambien
usa Model Quality, pero Data Quality compara las features de entrada contra el
baseline.

SageMaker Model Monitor puede devolver `InternalFailure` al crear
`CreateMonitoringSchedule` o `CreateDataQualityJobDefinition`. Cuando eso pasa,
el laboratorio no bloquea el aprendizaje: crea una ruta fallback cloud:

```text
EventBridge cron
-> Lambda mlops-custom-data-quality-trigger
-> SageMaker Processing Job custom
-> processing/custom_data_quality.py
-> S3 constraints_violations.json y data_quality_report.json
-> CloudWatch metric MLOps/Lab / DataQualityViolations
-> CloudWatch Alarm mlops-custom-data-quality-alarm
```

La alarma no envia email por si sola. El paso 11 crea SNS, EventBridge y Step
Functions para enrutar eventos de alarma.

## Que contienen statistics.json y constraints.json

Ejemplo reducido de `statistics.json`:

```json
{
  "version": 0.0,
  "dataset": {
    "item_count": 500
  },
  "features": [
    {
      "name": "age",
      "inferred_type": "Fractional",
      "numerical_statistics": {
        "common": {
          "num_present": 500,
          "num_missing": 0
        },
        "mean": 39.8,
        "std_dev": 11.2,
        "min": 18.0,
        "max": 78.0
      }
    }
  ]
}
```

Ejemplo reducido de `constraints.json`:

```json
{
  "version": 0.0,
  "features": [
    {
      "name": "age",
      "inferred_type": "Fractional",
      "completeness": 1.0,
      "num_constraints": {
        "is_non_negative": true
      }
    }
  ],
  "monitoring_config": {
    "evaluate_constraints": "Enabled",
    "emit_metrics": "Enabled"
  }
}
```

Los archivos reales pueden incluir mas histogramas, dominios y configuraciones
internas del analyzer.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.generate_baseline --wait` | `.env`, `data/local_cache/` | Dataset baseline, role SageMaker, Service Quotas | `baseline.json` | Processing Job `mlops-lab-baseline-*`, `statistics.json`, `constraints.json` | Crear baseline Data Quality con analyzer oficial. |
| 2 | `src.create_monitoring_schedule` | `baseline.json`, `.env` | Endpoint, Data Capture, `statistics.json`, `constraints.json` | `monitoring_schedule.json` | Monitoring Schedule nativo o metadata de fallo | Crear schedule nativo de Data Quality. |
| 3 | `src.create_custom_data_quality_schedule --if-native-unavailable` | `monitoring_schedule.json`, `processing/custom_data_quality.py`, Lambda trigger | Lambda role, EventBridge, SageMaker role | `custom_data_quality_schedule.json` | EventBridge cron, Lambda, codigo custom en S3 | Crear fallback cloud si el schedule nativo no existe. |
| 4 | `src.simulate_drift` | `data/local_cache/inference_drift.jsonl` | Endpoint | `traffic_drift.json` | Invocaciones y capturas asincronas en S3 | Generar datos actuales con drift. |
| 5 | `src.check_monitoring_results` | `monitoring_schedule.json`, baseline metadata | Reports nativos o capturas fallback | `monitoring_results.json`, `monitoring_report.md` | `constraints_violations.json`, metrica `DataQualityViolations` | Resumir violations y publicar metrica custom. |
| 6 | `src.create_cloudwatch_alarm` | `.env`, evidencia de monitoring | CloudWatch Metrics | `cloudwatch_alarm.json` | `mlops-data-quality-alarm` o `mlops-custom-data-quality-alarm` | Crear alarma accionable de Data Quality. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Dataset baseline | `s3://<bucket>/mlops-lab/lab/data/raw/baseline_monitor.csv` | `src.generate_baseline` | Processing Job baseline y fallback custom. |
| Statistics | `s3://<bucket>/mlops-lab/lab/monitoring/baseline/statistics.json` | Analyzer oficial | Monitoring Schedule. |
| Constraints | `s3://<bucket>/mlops-lab/lab/monitoring/baseline/constraints.json` | Analyzer oficial | Monitoring Schedule. |
| Capturas online | `s3://<bucket>/mlops-lab/lab/data-capture/mlops-lab-endpoint/.../*.jsonl` | Endpoint Data Capture | Schedule nativo o fallback. |
| Reports custom | `s3://<bucket>/mlops-lab/lab/monitoring/custom/reports/` | Processing Job custom | Auditoria y troubleshooting. |
| Baseline metadata | `artifacts/local_outputs/baseline.json` | `src.generate_baseline` | Monitoreo y reporte final. |
| Schedule metadata | `artifacts/local_outputs/monitoring_schedule.json` | `src.create_monitoring_schedule` | Cleanup, fallback y resultados. |
| Results metadata | `artifacts/local_outputs/monitoring_results.json` | `src.check_monitoring_results` | Alarma y reporte final. |
| Alarm metadata | `artifacts/local_outputs/cloudwatch_alarm.json` | `src.create_cloudwatch_alarm` | Feedback loop y reporte final. |

## Prerrequisitos

- Pasos 02, 07 y 08 completados.
- Endpoint en estado `InService`.
- Data Capture activo y escribiendo `.jsonl` en S3.
- Roles creados por el paso 01.
- Credenciales AWS SSO vigentes.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 10
```

Comandos individuales equivalentes:

```bash
python -m src.generate_baseline --wait
python -m src.create_monitoring_schedule
python -m src.create_custom_data_quality_schedule --if-native-unavailable
python -m src.simulate_drift
python -m src.check_monitoring_results
python -m src.create_cloudwatch_alarm
```

Probar manualmente el fallback custom y la alarma sin esperar al cron:

```bash
python -m src.simulate_data_quality_alarm --wait
```

Para probar tambien email y feedback loop, ejecuta primero el paso 11 y luego
corre la simulacion. Asi EventBridge y SNS ya existen cuando CloudWatch cambia
el estado de la alarma.

Para Data Quality, el flujo de prueba completo es:

```bash
python -m src.lab_runner step 11
# confirmar el correo SNS en el inbox o Spam
python -m src.simulate_data_quality_alarm --wait
```

La alarma activa debe cambiar de `OK` a `ALARM` cuando `DataQualityViolations >= ALARM_THRESHOLD`. En la ruta custom, esa alarma es `mlops-custom-data-quality-alarm`; en la ruta nativa, `mlops-data-quality-alarm`. Si la alarma ya estaba en `ALARM`, CloudWatch no genera un nuevo evento de transicion y EventBridge/SNS pueden no enviar otro email hasta que vuelva a `OK`.

## Resultado esperado

El baseline queda disponible en S3, el schedule nativo queda creado o se deja un
fallback custom listo, se publica `DataQualityViolations` y se crea la alarma
activa de Data Quality. Si `monitoring_schedule.json` tiene
`status=native_schedule_unavailable`, espera ver `mlops-custom-data-quality-alarm`.
Si el schedule nativo existe, espera ver `mlops-data-quality-alarm`.

Severidad sugerida para Data Quality:

| Violations | Severidad | Lectura operacional |
|---:|---|---|
| 0 | `none` | No hay accion. |
| 1 | `low` | Revisar evidencia; puede ser ruido o cambio menor. |
| 2-4 | `medium` | Evaluar baseline update o investigacion de datos. |
| 5-9 | `high` | Revision humana prioritaria; posible drift real. |
| 10+ | `critical` | Incidente de calidad de datos; escalar antes de automatizar cambios. |

Si el schedule nativo falla con `InternalFailure`, el resultado correcto puede
ser `status=native_schedule_unavailable` en `monitoring_schedule.json` junto con
`custom_data_quality_schedule.json` creado.

## Validacion local

```bash
type artifacts\local_outputs\baseline.json
type artifacts\local_outputs\monitoring_schedule.json
type artifacts\local_outputs\monitoring_results.json
type artifacts\local_outputs\cloudwatch_alarm.json
type artifacts\local_outputs\monitoring_report.md
```

## Validacion en consola AWS

- SageMaker > Processing Jobs: jobs `mlops-lab-baseline-*` y, si aplica, `mlops-lab-custom-data-quality-*`.
- SageMaker > Model Monitor > Monitoring schedules: `mlops-monitoring-schedule`, si el nativo fue creado.
- S3 > `monitoring/baseline/statistics.json`.
- S3 > `monitoring/baseline/constraints.json`.
- CloudWatch > Metrics > Custom namespaces > `MLOps/Lab` > `DataQualityViolations`.
- CloudWatch > Alarms > `mlops-data-quality-alarm` o `mlops-custom-data-quality-alarm`.
- EventBridge > Scheduled rules > `mlops-custom-data-quality-schedule`, si el fallback fue creado.
- Lambda > `mlops-custom-data-quality-trigger`, si el fallback fue creado.

Validacion por CLI:

```bash
aws cloudwatch list-metrics \
  --namespace MLOps/Lab \
  --metric-name DataQualityViolations \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws cloudwatch describe-alarms \
  --alarm-names mlops-data-quality-alarm mlops-custom-data-quality-alarm \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

## Errores frecuentes

- `TokenRetrievalError`: la sesion SSO expiro. Ejecuta `aws sso login --profile <AWS_PROFILE>`.
- `No usable value for version`: `constraints.json` es antiguo o incompatible. Vuelve a ejecutar este paso para regenerar baseline con el analyzer oficial.
- `InternalFailure` en `CreateMonitoringSchedule`: error de plano de control de SageMaker. El fallback custom debe quedar creado si los roles estan correctos.
- No aparece ninguna alarma de Data Quality: valida que este paso haya llegado a `src.create_cloudwatch_alarm`.
- La alarma queda en `OK` aunque hubo drift: revisa el periodo de evaluacion de CloudWatch y que exista un datapoint reciente de `DataQualityViolations`.
- No llega email: el email se configura en el paso 11; confirma la suscripcion SNS antes de esperar entrega.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.generate_baseline` | Preparar baseline y lanzar analyzer oficial. | `_prepare_model_monitor_baseline`, `_validate_model_monitor_baseline_artifacts`, `generate_baseline`. | Datos raw, `.env`. | `baseline.json`, `statistics.json`, `constraints.json`. |
| `src.create_monitoring_schedule` | Crear schedule Data Quality nativo. | `_monitoring_definition`, `_inline_schedule_request`, `_create_monitoring_schedule_with_retries`. | Baseline, endpoint, cron. | `monitoring_schedule.json`, schedule o job definition. |
| `src.create_custom_data_quality_schedule` | Crear fallback EventBridge -> Lambda -> Processing Job. | `_validate_eventbridge_schedule_expression`, `_upsert_lambda`, `create_custom_data_quality_schedule`. | Processor custom, roles, metadata nativa. | `custom_data_quality_schedule.json`, Lambda, EventBridge rule. |
| `processing/custom_data_quality.py` | Comparar baseline contra datos actuales y publicar metrica. | `_build_violations`, `_publish_metric`. | Baseline CSV, capturas o JSONL explicito. | `constraints_violations.json`, `data_quality_report.json`, metrica custom. |
| `src.simulate_drift` | Enviar trafico drifted al endpoint. | `send_drift`. | `inference_drift.jsonl`. | `traffic_drift.json`, capturas S3. |
| `src.check_monitoring_results` | Leer reports o generar evidencia fallback. | `_fallback_monitoring_if_needed`, `_build_fallback_violations`, `check_results`. | Reports/capturas/baseline. | `monitoring_results.json`, `monitoring_report.md`, `DataQualityViolations`. |
| `src.create_cloudwatch_alarm` | Crear alarma de Data Quality. | `create_alarm`, `_active_data_quality_alarm_name`. | `.env`, metadata del schedule. | `cloudwatch_alarm.json`, alarma activa de Data Quality. |

Parametros modificables:

- `MONITORING_CRON_EXPRESSION`: frecuencia nativa de Model Monitor.
- `CUSTOM_DATA_QUALITY_CRON_EXPRESSION`: frecuencia del fallback EventBridge.
- `CUSTOM_DATA_QUALITY_WINDOW_HOURS`: ventana para leer capturas recientes.
- `VIOLATIONS_METRIC_NAME`: nombre de la metrica custom.
- `ALARM_NAME`: nombre de la alarma Data Quality nativa, por defecto `mlops-data-quality-alarm`.
- `CUSTOM_DATA_QUALITY_ALARM_NAME`: nombre de la alarma fallback, por defecto `mlops-custom-data-quality-alarm`.
- `ALARM_THRESHOLD`: umbral de violations para alarmar.
- `ALARM_PERIOD_SECONDS`, `ALARM_EVALUATION_PERIODS`, `ALARM_DATAPOINTS_TO_ALARM`.

Validacion profunda:

```bash
aws s3 cp s3://<bucket>/mlops-lab/lab/monitoring/baseline/statistics.json -
aws s3 cp s3://<bucket>/mlops-lab/lab/monitoring/baseline/constraints.json -
aws cloudwatch list-metrics --namespace MLOps/Lab --metric-name DataQualityViolations --region <AWS_REGION>
```
