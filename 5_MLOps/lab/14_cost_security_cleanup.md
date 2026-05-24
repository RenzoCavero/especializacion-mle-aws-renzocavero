# 14 - Costos, seguridad y cleanup

## Objetivo

Revisar riesgos de costo y seguridad, y preparar planes seguros de rollback, baseline update y cleanup.

## Que vas a construir o validar

Vas a generar planes locales no destructivos para rollback y baseline update. El cleanup real de recursos AWS queda separado en `python -m src.lab_runner cleanup`. El reporte/readiness del paso 13 debe ejecutarse antes de este paso o antes de `cleanup`, porque cleanup puede borrar recursos cloud y artefactos S3.

## Input del paso

- Metadata del endpoint, monitoreo y feedback loop.
- Variables de guardrail:
  - `ENABLE_ROLLBACK_EXECUTION=false`.
  - `ENABLE_BASELINE_UPDATE=false`.
  - `ENABLE_AUTOMATIC_RETRAINING=false`.

## Output esperado del paso

- `artifacts/local_outputs/rollback_plan.json`.
- `artifacts/local_outputs/baseline_update_plan.json`.
- `artifacts/local_outputs/lab_step_14.json`.
- `artifacts/local_outputs/cleanup_all.json`, solo despues de ejecutar cleanup.
- `artifacts/local_outputs/cleanup_local_outputs_plan.json`, si revisas el plan de cleanup local.

## Conceptos claves

El recurso mas importante de costo persistente es el endpoint real-time. Mientras este `InService`, genera costo aunque no reciba trafico. Por eso el cleanup de endpoint es explicito y visible.

Processing Jobs, Training Jobs y Model Monitor jobs generan costo durante ejecucion. Los schedules de monitoreo pueden crear jobs periodicos; si quedan activos despues de la practica, seguiran ejecutandose.

CloudWatch Logs y S3 suelen parecer baratos, pero pueden acumular costo por volumen y retencion. Data Capture y el paso 09 de model quality pueden generar objetos si el endpoint recibe trafico frecuente.

Seguridad empieza con credenciales. El laboratorio no usa credenciales hardcodeadas. Los permisos deben venir de profiles, roles o mecanismos AWS administrados.

El principio de minimo privilegio requiere separar responsabilidades: SageMaker entrena y despliega, Lambda ejecuta acciones ligeras, Step Functions coordina y EventBridge enruta. Usar un rol administrador para todo simplifica una demo pero no representa un patron sano.

Cleanup seguro significa distinguir recursos propios de recursos externos. En `integrated_mode`, un endpoint o Model Package puede pertenecer a otro flujo. Por eso no se elimina por defecto.

Tambien hay que distinguir recursos cloud de evidencia local. `artifacts/local_outputs/` y `data/local_cache/` son archivos generados por el laboratorio para auditoria, troubleshooting y reporte final. `python -m src.lab_runner cleanup` conserva esos archivos locales por defecto, pero ahora si borra los artefactos S3 bajo el prefijo exacto del laboratorio.

Rollback y baseline update son acciones de cambio operativo. En este laboratorio quedan como planes seguros por defecto para evitar modificaciones destructivas o silenciosas.

El cleanup cloud borra recursos activos y registros terminales cuando AWS lo permite: endpoint, modelos, schedules, alarmas, EventBridge, SNS, Step Functions, Lambdas, pipeline de SageMaker, Model Package Group en modo standalone, Processing Jobs terminales, Training Jobs terminales, Transform Jobs terminales, log groups/streams del laboratorio y objetos S3 bajo `s3://<bucket>/<RESOURCE_PREFIX>/<ENVIRONMENT>/`.

Ese prefijo S3 incluye datos raw/procesados del lab, artefactos de modelo, codigo subido para jobs, data capture, ground truth, predicciones, reportes de monitoreo y outputs batch generados por los pasos del laboratorio.

Las metricas custom de CloudWatch no se borran directamente como recurso independiente. CloudWatch conserva datapoints por retencion y desaparecen de la consola cuando dejan de recibir datos. Lo que cleanup borra son alarmas, log groups/log streams y las fuentes que publicaban esas metricas.

## Flujo detallado del paso 14

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.rollback_model` | `approved_model.json`, metadata de endpoint si existe | Model Registry y endpoint si se ejecutara rollback real | `rollback_plan.json` | Ninguno por defecto | Documentar procedimiento seguro de rollback sin cambiar trafico. |
| 2 | `src.update_baseline` | `baseline.json`, `monitoring_results.json` si existe | Baseline actual en S3 | `baseline_update_plan.json` | Ninguno por defecto | Documentar evidencias requeridas antes de reemplazar baseline. |
| 3 | `record` del runner | Ninguno | Ninguno | `lab_step_14.json` | Ninguno | Dejar claro que cleanup real es comando separado. |

## Flujo detallado de cleanup

| Comando | Que elimina | Que conserva | Evidencia local |
|---|---|---|---|
| `python -m src.lab_runner cleanup` | Endpoint, Endpoint Config, SageMaker Models, pipeline, Model Package Group standalone, jobs terminales, monitoring schedules, job definitions, alarmas, EventBridge rules, SNS topic, Step Functions, Lambdas, logs del lab y objetos S3 del prefijo del laboratorio | `artifacts/local_outputs/`, `data/local_cache/`, `.env`, codigo y docs | `cleanup_all.json`, `cleanup_sagemaker_resources.json`, `cleanup_s3_artifacts.json` |
| `python -m src.cleanup_all --retain-s3-outputs` | Igual que cleanup cloud, pero conserva objetos S3 | S3 outputs, evidencia local, `.env`, codigo y docs | `cleanup_all.json` |
| `python -m src.cleanup_local_outputs` | Nada; solo plan | Todo | `cleanup_local_outputs_plan.json` |
| `python -m src.lab_runner cleanup-local` | `artifacts/local_outputs/` y `data/local_cache/` | `.env`, `.env.cloud`, codigo, docs y S3 outputs | El propio output del comando antes de borrar evidencia |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Plan de rollback | `artifacts/local_outputs/rollback_plan.json` | `src.rollback_model` | Revision humana y reporte del paso 13 si se regenera. |
| Plan de baseline update | `artifacts/local_outputs/baseline_update_plan.json` | `src.update_baseline` | Revision humana y reporte del paso 13 si se regenera. |
| Resultado de cleanup cloud | `artifacts/local_outputs/cleanup_all.json` | `src.cleanup_all` | Auditoria de cierre. |
| Cleanup SageMaker | `artifacts/local_outputs/cleanup_sagemaker_resources.json` | `src.cleanup_sagemaker_resources` | Evidencia de pipeline, registry, jobs y logs eliminados. |
| Cleanup S3 | `artifacts/local_outputs/cleanup_s3_artifacts.json` | `src.cleanup_s3_artifacts` | Evidencia de objetos S3 eliminados bajo el prefijo del lab. |
| Plan de cleanup local | `artifacts/local_outputs/cleanup_local_outputs_plan.json` | `src.cleanup_local_outputs` | Decision antes de borrar evidencia local. |
| Evidencia local borrable | `artifacts/local_outputs/`, `data/local_cache/` | Todo el laboratorio | `cleanup-local` si ya no necesitas evidencia. |
| Outputs S3 del lab | `s3://<bucket>/mlops-lab/lab/...` | Pasos cloud | `cleanup` los borra por defecto; usa `--retain-s3-outputs` si quieres conservarlos. |

## Prerrequisitos

- Pasos anteriores ejecutados segun el alcance que quieras limpiar.

## Pasos de ejecucion

Secuencia recomendada al terminar la practica:

```bash
python -m src.lab_runner step 13
python -m src.lab_runner step 14
python -m src.lab_runner cleanup
python -m src.lab_runner cleanup-local
```

Generar planes no destructivos:

```bash
python -m src.lab_runner step 14
```

Ejecutar cleanup explicito:

```bash
python -m src.lab_runner cleanup
```

Revisar plan de archivos locales generados que se podrian borrar:

```bash
python -m src.cleanup_local_outputs
```

Eliminar archivos locales generados por el laboratorio:

```bash
python -m src.cleanup_local_outputs --execute
```

Comando equivalente desde el runner:

```bash
python -m src.lab_runner cleanup-local
```

Comandos especificos:

```bash
make destroy-endpoint
make destroy-monitoring
make destroy-feedback-loop
make destroy-local-plan
make destroy-local
make destroy-all
```

## Resultado esperado

El paso 14 no elimina recursos. Solo documenta planes y guardrails. El comando `cleanup` elimina endpoint, schedules de monitoreo, alarmas de drift/model quality, feedback loop, SageMaker Pipeline, Model Package Group standalone, jobs terminales y artefactos S3 creados bajo el prefijo del laboratorio.

Si despues de `cleanup` todavia ves archivos en `artifacts/local_outputs/` o `data/local_cache/`, es esperado: son evidencia local. Para borrarlos, usa `python -m src.cleanup_local_outputs --execute` o `make destroy-local`. Si quieres conservar S3 para auditoria, usa `python -m src.cleanup_all --retain-s3-outputs`.

## Validacion local

```bash
type artifacts\local_outputs\rollback_plan.json
type artifacts\local_outputs\baseline_update_plan.json
```

Despues de cleanup:

```bash
type artifacts\local_outputs\cleanup_all.json
type artifacts\local_outputs\cleanup_sagemaker_resources.json
type artifacts\local_outputs\cleanup_s3_artifacts.json
type artifacts\local_outputs\cleanup_local_outputs_plan.json
```

Antes de borrar evidencia local, revisar alcance:

```bash
type artifacts\local_outputs\cleanup_local_outputs_plan.json
```

## Validacion en consola AWS

Revisar que no queden activos si se ejecuto cleanup:

- SageMaker Endpoints.
- SageMaker Pipelines `mlops-build-pipeline`.
- SageMaker Processing Jobs, Training Jobs y Transform Jobs terminales del laboratorio.
- SageMaker Model Package Group en modo standalone.
- SageMaker Monitoring schedules.
- CloudWatch Alarms `mlops-data-quality-alarm`, `mlops-custom-data-quality-alarm`, `mlops-custom-batch-data-quality-alarm`, `mlops-model-quality-alarm` y `mlops-custom-model-quality-alarm`.
- EventBridge Rules.
- SNS Topic `mlops-lab-alarm-notifications`.
- Step Functions State machines.
- Lambda Functions.

## Advertencia

S3 outputs del prefijo exacto del laboratorio se borran por defecto durante `cleanup`. El script valida que el prefijo sea exactamente `RESOURCE_PREFIX/ENVIRONMENT` para evitar borrados amplios. No borra el bucket completo.

Los jobs que esten `InProgress` o `Stopping` no se pueden borrar inmediatamente. El cleanup intenta detenerlos y registra `stop_requested`; ejecuta cleanup otra vez cuando queden `Stopped`.

El cleanup local elimina solamente `artifacts/local_outputs/` y `data/local_cache/`. Conserva `.env`, `.env.cloud`, codigo fuente y documentacion.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.rollback_model` | Documentar plan de rollback seguro; no ejecuta sin opt-in. | `rollback_plan`. | `.env`, registry. | `rollback_plan.json`. |
| `src.update_baseline` | Documentar plan de baseline update; no reemplaza sin opt-in. | `baseline_update_plan`. | `.env`, baseline actual. | `baseline_update_plan.json`. |
| `src.cleanup_all` | Orquestar cleanup cloud. | `cleanup_all`. | Metadata de endpoint, monitoring y feedback. | `cleanup_all.json`. |
| `src.cleanup_endpoint` | Borrar endpoint, config y modelos del lab. | `cleanup_endpoint`. | `endpoint_deployment.json`. | `cleanup_endpoint.json`. |
| `src.cleanup_monitoring` | Borrar schedules, alarms, Lambda fallback y SNS topic. | `cleanup_monitoring`. | `monitoring_schedule.json`, `batch_monitoring_schedule.json`, `model_quality_schedule.json`, `alarm_notifications.json`. | `cleanup_monitoring.json`. |
| `src.cleanup_feedback_loop` | Borrar EventBridge rule, Step Functions y Lambdas. | `cleanup_feedback_loop`. | `feedback_loop.json`, `eventbridge_rule.json`. | `cleanup_feedback_loop.json`. |
| `src.cleanup_sagemaker_resources` | Borrar pipeline, Model Package Group standalone, jobs terminales y logs SageMaker del lab. | `cleanup_sagemaker_resources`. | Metadata local y listados SageMaker. | `cleanup_sagemaker_resources.json`. |
| `src.cleanup_s3_artifacts` | Borrar objetos/versiones S3 bajo el prefijo exacto del laboratorio. | `cleanup_s3_artifacts`. | `S3_BUCKET_NAME`, `RESOURCE_PREFIX`, `ENVIRONMENT`. | `cleanup_s3_artifacts.json`. |
| `src.cleanup_local_outputs` | Planificar o borrar evidencia local generada. | `_clean_directory_contents`, `cleanup_local_outputs`. | `artifacts/local_outputs/`, `data/local_cache/`. | `cleanup_local_outputs_plan.json` o borrado local. |

Opt-in requeridos:

- Rollback real: `--execute` y `ENABLE_ROLLBACK_EXECUTION=true`.
- Baseline update real: `--execute` y `ENABLE_BASELINE_UPDATE=true`.
- Borrado local: `python -m src.lab_runner cleanup-local`.

Troubleshooting:

- `ResourceNotFound` durante cleanup no es fallo critico; indica que el recurso ya no existe.
- Si un job no se borra, revisa su estado. AWS permite borrar Processing/Training/Transform Jobs solo cuando estan en estado terminal.
- Si CloudFormation no puede borrar el bucket, revisa si quedaron objetos fuera del prefijo `RESOURCE_PREFIX/ENVIRONMENT` o versiones que el rol no pudo borrar.




