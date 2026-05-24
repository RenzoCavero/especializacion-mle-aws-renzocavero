# 13 - MLOps readiness checklist

## Objetivo

Generar el reporte final y evaluar readiness MLOps del laboratorio.

## Que vas a construir o validar

Vas a consolidar la evidencia local de datos, pipeline, registry, approval, deployment, monitoring, drift, model quality, alarmas, feedback loop, seguridad, costos y cleanup.

## Input del paso

- Metadata generada en `artifacts/local_outputs/`.
- Configuracion efectiva del laboratorio.
- Resultados de pasos previos.

## Output esperado del paso

- `artifacts/local_outputs/mlops_report.md`.
- `artifacts/local_outputs/readiness_check.json`.
- `artifacts/local_outputs/readiness_check.md`.

## Conceptos claves

MLOps readiness mide si el sistema tiene controles suficientes para operar modelos con confianza. No significa perfeccion empresarial; significa que existen evidencias minimas para reproducir, aprobar, desplegar, monitorear y responder.

El primer bloque es datos. Debe existir un dataset de entrenamiento o una fuente integrada clara. Sin trazabilidad de datos, las metricas del modelo pierden contexto.

El segundo bloque es pipeline. Un build reproducible permite regenerar artefactos, comparar ejecuciones y auditar cambios. Ejecutar notebooks manualmente no entrega la misma trazabilidad.

El tercer bloque es gobierno del modelo: registry, approval status, metadata y criterios. Un modelo sin estado de aprobacion no deberia desplegarse.

El cuarto bloque es operacion: endpoint, smoke test, data capture, baseline, monitoring schedule, violations y model quality. Esto demuestra que el modelo no solo fue creado, sino observado con senales de datos y performance.

El quinto bloque es respuesta: alarmas, EventBridge, Step Functions y Lambdas. La deteccion sin accion gobernada deja el sistema incompleto.

El sexto bloque es seguridad y costo: roles, S3 privado, cleanup, guardrails de retraining, proteccion de recursos externos y advertencia de endpoints activos.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.mlops_report` | Metadata en `artifacts/local_outputs/` | Ninguno directo | `mlops_report.md` | Ninguno | Consolidar evidencia narrativa del laboratorio. |
| 2 | `src.readiness_check` | Metadata en `artifacts/local_outputs/`, `.env` | Ninguno directo | `readiness_check.json`, `readiness_check.md` | Ninguno | Evaluar estado por dominios MLOps. |

## Evidencias que revisa

| Dominio | Metadata local esperada | Que demuestra |
|---|---|---|
| Datos | `data_generation.json`, `data_upload.json` | Existe fuente de datos trazable. |
| Pipeline | `pipeline_upsert.json`, `pipeline_execution_status.json` | El build es reproducible y auditable. |
| Registry y approval | `model_registry.json`, `model_approval.json`, `approved_model.json` | Hay versionado y gobierno del modelo. |
| Deployment | `endpoint_deployment.json`, `smoke_test.json` | El modelo aprobado puede servir inferencia. |
| Data capture | `data_capture.json`, `data_capture_check.json` | Existe evidencia de trafico capturado. |
| Data quality | `baseline.json`, `monitoring_schedule.json`, `monitoring_results.json` | Hay baseline, schedule y revision de drift. |
| Model quality | `model_quality_capture.json`, `model_quality_baseline.json`, `model_quality_schedule.json`, `custom_model_quality_schedule.json`, `model_quality_alarm.json`, `custom_model_quality_alarm.json` | Hay performance monitoring con ground truth y fallback custom. |
| Alarmas y feedback | `cloudwatch_alarm.json`, `alarm_notifications.json`, `eventbridge_rule.json`, `feedback_loop.json`, `feedback_loop_execution.json` | Hay ruta de deteccion a decision y email. |
| Batch Transform opcional | `batch_transform.json`, `batch_transform_capture.json`, `batch_monitoring_schedule.json`, `custom_batch_data_quality_schedule.json`, `custom_batch_data_quality_job.json`, `batch_cloudwatch_alarm.json` | Hay evidencia de inferencia batch, captura batch y fallback custom si el schedule nativo falla. |
| Costo y seguridad | `rollback_plan.json`, `baseline_update_plan.json`, `cleanup_all.json` si se ejecuto cleanup | Hay guardrails y cierre operativo. |

## Paths principales

| Tipo | Path | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Reporte final | `artifacts/local_outputs/mlops_report.md` | `src.mlops_report` | Entrega final del laboratorio. |
| Checklist JSON | `artifacts/local_outputs/readiness_check.json` | `src.readiness_check` | Automatizacion y auditoria. |
| Checklist Markdown | `artifacts/local_outputs/readiness_check.md` | `src.readiness_check` | Revision humana. |

## Prerrequisitos

- Ejecutar los pasos que se quieran evaluar.
- Para reporte completo, ejecutar 00-12 antes de este paso. El paso 14 y `cleanup` quedan despues porque pueden destruir recursos y artefactos.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 13
```

Comandos individuales:

```bash
python -m src.mlops_report
python -m src.readiness_check
```

## Resultado esperado

Reporte Markdown y checklist JSON disponibles localmente.

## Validacion local

```bash
type artifacts\local_outputs\mlops_report.md
type artifacts\local_outputs\readiness_check.md
```

## Validacion en consola AWS

Contrastar el reporte con:

- SageMaker Pipelines.
- Model Registry.
- SageMaker Endpoint.
- S3 Data Capture, Monitoring outputs y Model Quality outputs.
- CloudWatch Alarms.
- EventBridge Rules.
- SNS Topics/subscriptions.
- Step Functions executions.
- Lambda Logs.

## Criterio de cierre

El laboratorio queda completo cuando existe evidencia de build, aprobacion, despliegue, monitoreo, alerta, feedback loop y cleanup seguro.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.mlops_report` | Consolidar evidencias locales en reporte Markdown. | `generate_report`. | Lista de metadata en `artifacts/local_outputs/`. | `mlops_report.md`. |
| `src.readiness_check` | Evaluar dominios esperados y estados. | `run_readiness_check`. | Metadata local por dominio. | stdout JSON; puede complementarse con reporte local. |

Archivos que mas pesan en el cierre:

- `pipeline_execution_status.json`
- `model_registry.json`, `model_approval.json`, `approved_model.json`
- `endpoint_deployment.json`, `smoke_test.json`
- `data_capture_check.json`
- `baseline.json`, `monitoring_schedule.json`, `monitoring_results.json`
- `model_quality_baseline.json`, `model_quality_schedule.json`, `custom_model_quality_schedule.json`
- `cloudwatch_alarm.json`, `eventbridge_rule.json`, `feedback_loop.json`, `alarm_notifications.json`
- `batch_transform.json`, `batch_monitoring_schedule.json`, `batch_cloudwatch_alarm.json` si ejecutaste el paso 12

Si un dominio queda `pending`, no maquilles el reporte: vuelve al paso que produce esa evidencia o deja una observacion explicita. En una revision profesional, la trazabilidad incompleta es una senal de riesgo operacional.


