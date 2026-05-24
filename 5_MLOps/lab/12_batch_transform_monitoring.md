# 12 - Batch Transform, Data Capture batch y monitoreo

## Objetivo

Ejecutar inferencia batch con SageMaker Batch Transform, capturar evidencia de inferencia en S3 y preparar un monitoring schedule para datos batch.

## Que vas a construir o validar

Vas a crear un SageMaker Model para batch a partir del ultimo modelo aprobado, ejecutar un Batch Transform Job con `BatchDataCaptureConfig`, validar outputs y capturas en S3, crear un schedule de Model Monitor usando `BatchTransformInput` y preparar un fallback custom si el schedule nativo falla.

## Input del paso

- Modelo `Approved` en Model Registry.
- `SAGEMAKER_EXECUTION_ROLE_ARN`.
- Dataset batch en `BATCH_TRANSFORM_INPUT_S3_URI` o, por defecto, `s3://<bucket>/mlops-lab/lab/data/raw/inference_normal.jsonl`.
- Baseline generado en el paso 10:
  - `statistics.json`.
  - `constraints.json`.
- Cuota disponible para Batch Transform.
- Imagen de Model Monitor resuelta por region o `MODEL_MONITOR_IMAGE_URI`.

## Output esperado del paso

- SageMaker Model batch creado o reutilizado:
  - `mlops-lab-lab-batch-model`.
- Batch Transform Job completado.
- Outputs batch en S3:
  - `batch-transform/output/`.
- Captura batch en S3:
  - `batch-transform/data-capture/`.
- Monitoring schedule batch:
  - `mlops-lab-batch-monitoring-schedule`.
- Fallback custom batch, si el schedule nativo no esta disponible:
  - EventBridge rule `mlops-custom-batch-data-quality-schedule`.
  - Lambda `mlops-custom-batch-data-quality-trigger`.
  - Processing Job custom `mlops-lab-custom-batch-data-quality-*`.
  - Metrica custom `MLOps/Lab / BatchDataQualityViolations`.
  - CloudWatch Alarm `mlops-custom-batch-data-quality-alarm`.
- Metadata local:
  - `batch_transform.json`.
  - `batch_transform_capture.json`.
  - `batch_monitoring_schedule.json`.
  - `custom_batch_data_quality_schedule.json`.
  - `custom_batch_data_quality_job.json`.
  - `batch_cloudwatch_alarm.json`.

## Conceptos claves

En SageMaker no existe un "batch endpoint" persistente equivalente al endpoint real-time. El patron correcto es **Batch Transform**: cada ejecucion crea un job efimero que lee datos desde S3, carga el modelo, genera predicciones y escribe resultados nuevamente en S3.

La diferencia operacional es importante:

- Real-time endpoint: recurso persistente, cobra mientras esta `InService`, recibe invocaciones online y usa Data Capture configurado en el Endpoint Config.
- Batch Transform: job efimero, cobra durante ejecucion, recibe archivos desde S3 y puede usar `BatchDataCaptureConfig` por job.

El flujo de Data Capture tambien cambia. En inferencia online, la captura esta asociada al endpoint vivo. En inferencia batch, la captura esta asociada al transform job y se escribe en `DestinationS3Uri` configurado en `DataCaptureConfig`. No debes buscar una pestana de Data Capture del endpoint para batch; debes validar el prefijo S3 de captura del job batch.

La captura batch se organiza como manifests bajo subdirectorios `input/` y `output/`. Esos manifests referencian los objetos S3 de entrada y salida del transform job, evitando duplicar archivos grandes. Si `GenerateInferenceId=true`, los outputs incluyen campos de trazabilidad como `SageMakerInferenceId` y `SageMakerInferenceTime`, utiles para unir predicciones con ground truth.

Flujo batch recomendado:

```text
S3 batch input
-> SageMaker Batch Transform Job
-> S3 batch predictions
-> BatchDataCaptureConfig
-> S3 batch captured data
-> BatchTransformInput en Model Monitor
-> Monitoring schedule
-> constraints_violations.json
-> CloudWatch metric/alarm nativa o fallback custom
-> EventBridge/Step Functions feedback loop
```

Para monitoreo batch, Model Monitor no consume trafico desde un endpoint. Consume los datos capturados en S3 mediante `BatchTransformInput.DataCapturedDestinationS3Uri`. Ese input apunta al prefijo donde Batch Transform escribio la captura.

Si `CreateMonitoringSchedule` falla con `InternalFailure`, el fallback custom usa un enfoque distinto: no intenta simular un endpoint ni leer trafico online. Evalua el JSONL batch de entrada (`BATCH_TRANSFORM_INPUT_S3_URI`) contra `baseline_monitor.csv`, escribe reportes custom en S3 y publica la metrica `BatchDataQualityViolations`. Esta ruta es util para mantener el laboratorio y la operacion batch auditables aunque el plano de control de SageMaker no cree el schedule nativo.

Arquitectura fallback batch:

```text
EventBridge cron
-> Lambda mlops-custom-batch-data-quality-trigger
-> SageMaker Processing Job custom
-> processing/custom_data_quality.py
-> S3 batch-transform/custom-monitoring/reports/
-> CloudWatch metric MLOps/Lab / BatchDataQualityViolations
-> CloudWatch Alarm mlops-custom-batch-data-quality-alarm
-> EventBridge alarm rule en paso 11
-> SNS email y Step Functions feedback loop
```

La diferencia frente al fallback online es la fuente de datos:

| Ruta | Fuente evaluada |
|---|---|
| Online Data Quality fallback | Capturas del endpoint o JSONL explicito de inferencia online. |
| Batch Data Quality fallback | JSONL batch de entrada en S3. |

Esto es intencional. La captura batch puede contener manifests `input/` y `output/`; el fallback custom del lab evalua el archivo batch original porque es el contrato de features que alimenta el Transform Job.

El baseline puede ser el mismo que se usa para online si las features y el contrato de datos son equivalentes. Si el flujo batch recibe otro esquema, otra granularidad o una poblacion distinta, se debe crear un baseline separado para batch. Reutilizar un baseline incompatible produce falsas alarmas o drift silencioso.

Buenas practicas para batch:

- Versionar input batch, output batch y capture batch por fecha, modelo y ejecucion.
- Usar modelos aprobados del Registry; no transformar con artefactos sueltos sin approval.
- Separar output de predicciones y data capture.
- Activar `GenerateInferenceId=true` para trazabilidad.
- Guardar `TransformJobName`, input S3, output S3 y capture S3 como evidencia.
- No mezclar capturas online y batch en el mismo prefijo.
- Crear schedules conservadores; batch suele monitorearse despues de cargas periodicas, no cada minuto.
- Usar cleanup para schedules y modelos batch creados por el laboratorio.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.compute --workload batch-transform` | `.env` | Service Quotas de SageMaker | `compute_selection_batch_transform.json` | Ninguno | Elegir instancia valida para Transform Jobs. |
| 2 | `src.run_batch_transform --wait` | `approved_model.json`, `training/inference.py` | Modelo aprobado, dataset batch en S3, role de SageMaker | `batch_transform.json` | SageMaker Model batch, Transform Job, predicciones en `batch-transform/output/`, captura en `batch-transform/data-capture/` | Ejecutar inferencia batch gobernada. |
| 3 | `src.check_batch_transform_capture --wait` | `batch_transform.json` | S3 output y S3 capture del Transform Job | `batch_transform_capture.json` | Ninguno | Confirmar que existen predicciones y capturas batch. |
| 4 | `src.create_batch_monitoring_schedule` | `baseline.json`, `batch_transform_capture.json` | `statistics.json`, `constraints.json`, capture batch S3, role de SageMaker | `batch_monitoring_schedule.json` | Monitoring Schedule `mlops-lab-batch-monitoring-schedule` | Crear monitoreo Data Quality para batch. |
| 5 | `src.create_custom_batch_data_quality_schedule --if-native-unavailable` | `batch_monitoring_schedule.json`, `processing/custom_data_quality.py` | Lambda role, EventBridge, SageMaker role | `custom_batch_data_quality_schedule.json` | EventBridge cron, Lambda, codigo custom en S3 | Crear fallback cloud si el schedule nativo falla. |
| 6 | `src.start_custom_batch_data_quality_job --if-native-unavailable --wait` | `batch_monitoring_schedule.json` | Batch input S3 y baseline S3 | `custom_batch_data_quality_job.json` | Processing Job custom y reportes en S3 | Publicar evidencia y metrica custom inicial. |
| 7 | `src.create_batch_cloudwatch_alarm` | Metadata del schedule batch | CloudWatch Metrics | `batch_cloudwatch_alarm.json` | Alarm `mlops-custom-batch-data-quality-alarm` | Conectar fallback batch y pruebas manuales con EventBridge/SNS/Step Functions. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Input batch | `BATCH_TRANSFORM_INPUT_S3_URI` o `s3://<bucket>/mlops-lab/lab/data/raw/inference_normal.jsonl` | Paso 02 o configuracion externa | Transform Job. |
| Modelo batch | `mlops-lab-lab-batch-model` | `src.run_batch_transform` | Transform Job. |
| Output batch | `s3://<bucket>/mlops-lab/lab/batch-transform/output/` | Transform Job | Revision y downstream batch. |
| Captura batch | `s3://<bucket>/mlops-lab/lab/batch-transform/data-capture/` | BatchDataCaptureConfig | Batch Monitoring Schedule. |
| Baseline Data Quality | `s3://<bucket>/mlops-lab/lab/monitoring/baseline/statistics.json` y `constraints.json` | Paso 10 | Batch Monitoring Schedule. |
| Metadata transform | `artifacts/local_outputs/batch_transform.json` | `src.run_batch_transform` | Check de captura, cleanup y readiness. |
| Metadata capture | `artifacts/local_outputs/batch_transform_capture.json` | `src.check_batch_transform_capture` | Schedule batch y reporte final. |
| Metadata schedule | `artifacts/local_outputs/batch_monitoring_schedule.json` | `src.create_batch_monitoring_schedule` | Cleanup y troubleshooting. |
| Metadata fallback schedule | `artifacts/local_outputs/custom_batch_data_quality_schedule.json` | `src.create_custom_batch_data_quality_schedule` | Cleanup, readiness y auditoria. |
| Metadata fallback job | `artifacts/local_outputs/custom_batch_data_quality_job.json` | `src.start_custom_batch_data_quality_job` | CloudWatch y auditoria. |
| Metadata alarma batch | `artifacts/local_outputs/batch_cloudwatch_alarm.json` | `src.create_batch_cloudwatch_alarm` | EventBridge y reporte final. |

## Prerrequisitos

- Pasos 02, 06 y 10 completados.
- El modelo aprobado debe tener `ModelDataUrl` e imagen de inferencia.
- Cuota de SageMaker Batch Transform para alguna instancia candidata.
- Si no hay cuota batch, revisar:

```bash
python -m src.compute --workload batch-transform --inventory --limit 0
```

## Pasos de ejecucion

```bash
python -m src.lab_runner step 12
```

Comandos individuales:

```bash
python -m src.compute --workload batch-transform
python -m src.run_batch_transform --wait
python -m src.check_batch_transform_capture --wait
python -m src.create_batch_monitoring_schedule
python -m src.create_custom_batch_data_quality_schedule --if-native-unavailable
python -m src.start_custom_batch_data_quality_job --if-native-unavailable --wait
python -m src.create_batch_cloudwatch_alarm
```

Equivalentes Make:

```bash
make check-batch-transform-compute
make run-batch-transform
make check-batch-transform-capture
make create-batch-monitoring-schedule
make create-custom-batch-data-quality-schedule
make run-custom-batch-data-quality
make create-batch-alarm
```

Para forzar una alarma batch con datos drifted:

```bash
python -m src.simulate_batch_data_quality_alarm --wait
```

Ese comando no lanza otro Batch Transform Job. Toma `inference_drift.jsonl`,
lo evalua como input batch adverso contra el baseline y publica
`MLOps/Lab / BatchDataQualityViolations`. Debe usarse para probar
CloudWatch/EventBridge/SNS/Step Functions.

## Resultado esperado

El Batch Transform Job queda `Completed`, S3 contiene predicciones batch y captura batch, y se crea un monitoring schedule batch que podra procesar capturas con Model Monitor. Si AWS devuelve `InternalFailure` al crear el schedule nativo, el resultado aceptable es `status=native_batch_schedule_unavailable` junto con el fallback custom creado.

## Validacion local

```bash
type artifacts\local_outputs\batch_transform.json
type artifacts\local_outputs\batch_transform_capture.json
type artifacts\local_outputs\batch_monitoring_schedule.json
type artifacts\local_outputs\custom_batch_data_quality_schedule.json
type artifacts\local_outputs\custom_batch_data_quality_job.json
type artifacts\local_outputs\batch_cloudwatch_alarm.json
```

En `batch_transform_capture.json` deberias ver:

```json
{
  "status": "batch_output_and_capture_found",
  "output_listing": {
    "object_count": 1
  },
  "capture_listing": {
    "object_count": 1
  }
}
```

## Validacion en consola AWS

- SageMaker > Inference > Batch transform jobs.
- Abrir el job con prefijo `mlops-lab-batch-`.
- Confirmar `Completed`.
- Revisar `DataCaptureConfig` del job.
- S3:
  - `mlops-lab/lab/batch-transform/output/`.
  - `mlops-lab/lab/batch-transform/data-capture/`.
- SageMaker > Model Monitor > Monitoring schedules.
- Confirmar `mlops-lab-batch-monitoring-schedule`.
- Si el schedule nativo fallo:
  - EventBridge > Scheduled rules > `mlops-custom-batch-data-quality-schedule`.
  - Lambda > `mlops-custom-batch-data-quality-trigger`.
  - SageMaker > Processing Jobs > `mlops-lab-custom-batch-data-quality-*`.
  - CloudWatch > Metrics > `MLOps/Lab / BatchDataQualityViolations`.
  - CloudWatch > Alarms > `mlops-custom-batch-data-quality-alarm`.

Validacion por CLI:

```bash
aws sagemaker describe-transform-job \
  --transform-job-name <TRANSFORM_JOB_NAME> \
  --query "{Status:TransformJobStatus, Input:TransformInput, Output:TransformOutput, Capture:DataCaptureConfig}" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws s3 ls s3://<bucket>/mlops-lab/lab/batch-transform/ --recursive --profile <AWS_PROFILE>
```

## Relacion con CloudWatch y feedback loop

El feedback loop no cambia conceptualmente. Cambia la fuente de evidencia:

- Online: Endpoint Data Capture -> Model Monitor -> violations.
- Batch: BatchDataCaptureConfig -> BatchTransformInput -> Model Monitor -> violations.

Luego se mantiene el mismo patron:

```text
violations -> custom metric -> CloudWatch Alarm -> EventBridge -> Step Functions -> decision
```

La decision puede ser retraining, rollback, baseline update, revision humana o no action. En batch, rollback suele significar reejecutar el lote con una version anterior aprobada y conservar evidencia del job fallido.

`src.create_batch_cloudwatch_alarm` crea la alarma custom batch aunque el schedule nativo exista. Esto permite dos usos: fallback operativo cuando `CreateMonitoringSchedule` falla, y prueba manual con `python -m src.simulate_batch_data_quality_alarm --wait`. Si no hay metrica publicada todavia, la alarma puede quedar en `OK` o `INSUFFICIENT_DATA` hasta que el Processing Job custom publique `BatchDataQualityViolations`.

Cuando el paso 11 ya existe, `src.create_eventbridge_rule` escucha tambien `mlops-custom-batch-data-quality-alarm`. Por tanto, una transicion `OK -> ALARM` puede enviar email via SNS y ejecutar `mlops-feedback-loop`. El `feedback_handler` interpreta esta alarma como Data Quality porque la metrica contiene violations.

## Costos y cleanup

Batch Transform cobra mientras el job se ejecuta. El schedule batch crea Processing Jobs periodicos y tambien genera costo.

Cleanup:

```bash
make destroy-monitoring
make destroy-endpoint
```

`destroy-monitoring` elimina schedules online y batch. `destroy-endpoint` elimina el modelo online y el modelo batch creados por el laboratorio. Los outputs S3 se conservan por defecto.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.compute --workload batch-transform` | Seleccionar instancia valida para Transform Job. | `select_instance_type`, `build_quota_inventory`. | Service Quotas. | `compute_selection_batch_transform.json`. |
| `src.run_batch_transform --wait` | Crear modelo batch y lanzar Transform Job. | `ensure_batch_model`, `run_batch_transform`. | `approved_model.json`, input S3 batch. | `batch_transform.json`, outputs en S3. |
| `src.check_batch_transform_capture --wait` | Confirmar captura batch en S3. | `check_batch_capture`. | Prefijo batch capture. | `batch_transform_capture.json`. |
| `src.create_batch_monitoring_schedule` | Crear schedule de monitoreo para batch. | `_create_monitoring_schedule_with_retries`, `create_batch_schedule`. | Batch capture, baseline. | `batch_monitoring_schedule.json`. |
| `src.create_custom_batch_data_quality_schedule` | Crear fallback EventBridge -> Lambda -> Processing Job. | `_upsert_lambda`, `create_custom_batch_data_quality_schedule`. | Batch input, baseline, roles. | `custom_batch_data_quality_schedule.json`. |
| `src.start_custom_batch_data_quality_job` | Ejecutar fallback batch manualmente. | `start_custom_batch_data_quality_job`. | Batch input JSONL, baseline. | `custom_batch_data_quality_job.json`, reportes S3, metrica custom. |
| `src.create_batch_cloudwatch_alarm` | Crear alarma del fallback batch. | `create_batch_alarm`. | Metadata de batch schedule/fallback. | `batch_cloudwatch_alarm.json`, `mlops-custom-batch-data-quality-alarm`. |
| `src.simulate_batch_data_quality_alarm` | Probar alarma batch con input drifted. | `simulate_batch_data_quality_alarm`. | `inference_drift.jsonl`. | `batch_data_quality_alarm_simulation.json`, metrica custom. |

Configuraciones:

- `BATCH_TRANSFORM_INPUT_S3_URI`, `BATCH_TRANSFORM_OUTPUT_S3_URI`, `BATCH_DATA_CAPTURE_S3_URI`, `BATCH_MONITORING_S3_URI`.
- `BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES`.
- `BATCH_MONITORING_SCHEDULE_NAME`.
- `CUSTOM_BATCH_DATA_QUALITY_CRON_EXPRESSION`.
- `CUSTOM_BATCH_DATA_QUALITY_ALARM_NAME`.
- `BATCH_VIOLATIONS_METRIC_NAME`.

Troubleshooting:

- `ml.t3.medium` no es valido para Batch Transform; usa candidatos como `ml.c6i.large`, `ml.m6i.large`, `ml.m5.xlarge` o `ml.m5.large`.
- Si no hay cuota, revisa `compute_inventory_batch_transform.json` y ajusta candidatos o region.
- Batch Transform no es endpoint persistente; si no ves endpoint nuevo, es correcto.
- Si `batch_monitoring_schedule.json` muestra `native_batch_schedule_unavailable`, valida el fallback custom y usa `python -m src.simulate_batch_data_quality_alarm --wait` para probar la ruta de alerta.
- Si no llega email batch, confirma que el paso 11 se ejecuto despues de crear la alarma batch o reejecuta `python -m src.create_eventbridge_rule`.

