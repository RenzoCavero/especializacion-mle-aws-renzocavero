# AGENTS.md - Laboratorio 4: Despliegue de modelo AWS - Machine Learning

Este archivo es la fuente principal de instrucciones para Codex dentro del laboratorio 4. Toda tarea debe mantenerse dentro de `4_ML-Model-Deployment/`.

## Alcance del laboratorio

El laboratorio ensena despliegue de modelos ML en AWS con dos patrones obligatorios:

1. `SageMaker Batch Transform` para inferencia batch.
2. `SageMaker Real-Time Endpoint` para inferencia online de baja latencia.

Tambien debe explicar estos patrones, aunque por defecto no los implemente:

- Batch Transform.
- Real-Time Endpoint.
- Asynchronous Inference.
- Serverless Inference.

No uses el termino "SageMaker Batch Endpoint" como implementacion principal. Para batch inference en SageMaker el patron correcto es `SageMaker Batch Transform Job`.

## Regla estricta de alcance

- No crear archivos fuera de `4_ML-Model-Deployment/`.
- No modificar archivos fuera de `4_ML-Model-Deployment/`.
- No mover ni renombrar `doc/4_AWS_Model_Deployment.pdf`.
- Si una tarea parece requerir cambios fuera de este directorio, detenerse y pedir confirmacion explicita.

## Fuente principal

La fuente principal del tema es:

`doc/4_AWS_Model_Deployment.pdf`

El material del PDF se resume en `ai_context/SOURCE_SUMMARY.md`. Para tareas teoricas o de documentacion, revisar tambien el PDF.

## Orden obligatorio de lectura antes de implementar

Antes de implementar una tarea, lee en este orden:

1. `AGENTS.md`
2. `ai_context/PROJECT_CONTEXT.md`
3. `ai_context/LAB_04_SPEC.md`
4. `ai_context/AWS_ARCHITECTURE_GUIDE.md`
5. `ai_context/FEATURE_STORE_INFERENCE_GUIDE.md`
6. `ai_context/DEPLOYMENT_PATTERNS_GUIDE.md`
7. `ai_context/INFRASTRUCTURE_GUIDE.md`
8. `ai_context/COST_AND_SECURITY.md`
9. `ai_context/CODE_STYLE.md`
10. `ai_context/RUNBOOK.md`
11. `ai_context/CODE_REVIEW.md`

Si la tarea requiere contexto teorico, lee tambien:

12. `ai_context/SOURCE_SUMMARY.md`
13. `doc/4_AWS_Model_Deployment.pdf`

## Modos del laboratorio

### standalone_mode

Modo por defecto. Permite ejecutar el laboratorio 4 sin haber ejecutado el laboratorio 3.

En este modo, el laboratorio debe preparar recursos minimos de ejemplo:

- Dataset sintetico de inferencia.
- Modelo simple de ejemplo o artefacto `model.tar.gz` de ejemplo.
- Contrato de features minimo.
- Batch input en S3.
- SageMaker Model.
- SageMaker Batch Transform Job.
- SageMaker Real-Time Endpoint.
- Feature Store con Online Store y Offline Store; si no existe, el laboratorio debe crearlo.

Esta ruta debe estar documentada como una ruta educativa autonoma.

### integrated_mode

Modo integrado con el laboratorio 3. Usa recursos generados por el laboratorio anterior:

- Model Registry.
- Model Package.
- `model.tar.gz`.
- Feature Group.
- Online Store.
- Offline Store.
- Feature contract.
- SageMaker Execution Role.

Variables esperadas:

- `MODEL_PACKAGE_GROUP_NAME`
- `MODEL_PACKAGE_ARN`
- `MODEL_ARTIFACT_S3_URI`
- `FEATURE_GROUP_NAME`
- `OFFLINE_STORE_S3_URI`
- `FEATURE_CONTRACT_S3_URI`
- `SAGEMAKER_EXECUTION_ROLE_ARN`

Esta ruta debe estar documentada como la mas cercana a produccion.

## Servicios AWS principales

- Amazon SageMaker Model Registry.
- Amazon SageMaker Model.
- Amazon SageMaker Batch Transform.
- Amazon SageMaker Real-Time Endpoint.
- Amazon SageMaker Endpoint Configuration.
- Amazon SageMaker Feature Store.
- Amazon S3.
- Amazon CloudWatch.
- Application Auto Scaling.
- AWS IAM.
- AWS KMS opcional.
- EventBridge o Step Functions como orquestacion opcional.

## Relacion con laboratorio 3

En `integrated_mode`, el laboratorio 4 consume artefactos del laboratorio 3: Model Registry, Model Package, `model.tar.gz`, Feature Group, Online Store, Offline Store, feature contract y rol de ejecucion de SageMaker. No debe eliminar esos recursos por defecto.

## Relacion con laboratorio 5 de MLOps

El laboratorio 4 debe dejar comandos, configuracion y convenciones que puedan automatizarse luego con CI/CD/CT en el laboratorio 5. Evitar pasos manuales irreproducibles.

## Relacion con laboratorio 6 de monitoreo y drift

El laboratorio 4 debe preparar data capture, logs, metricas, trazabilidad, `request_id`, `model_version` y outputs batch para que el laboratorio 6 pueda trabajar monitoreo, evaluacion y data drift.

## Reglas de seguridad

- No hardcodear credenciales.
- Usar AWS profiles o roles IAM.
- Aplicar minimo privilegio.
- No usar datos reales sensibles.
- Usar datos sinteticos o anonimizados.
- Bloquear acceso publico a S3.
- Cifrar S3 con SSE-S3 o KMS cuando aplique.
- No exponer endpoints publicamente fuera del control de IAM.
- No exponer stack traces ni datos sensibles en responses.
- Registrar `request_id` y `model_version` para trazabilidad.

## Reglas de costo

- Los endpoints real-time son persistentes y generan costo mientras estan activos.
- Usar instancias pequenas para laboratorio, por ejemplo `ml.m5.large` o una alternativa disponible y de bajo costo.
- Configurar `min_capacity` bajo y limites de autoscaling.
- Evitar cargas grandes.
- Evitar crear multiples endpoints.
- No activar async/serverless salvo que se pida explicitamente.
- Documentar costos antes de crear recursos persistentes.
- Incluir advertencias visibles de cleanup.

## Reglas de cleanup

- Incluir cleanup seguro para endpoint, endpoint config, SageMaker Model y objetos S3 creados por el laboratorio cuando corresponda.
- No eliminar Model Package externo por defecto.
- No eliminar Feature Group externo por defecto.
- No eliminar recursos de laboratorios anteriores por defecto.
- No dejar endpoints activos sin advertencia.

## Comandos esperados

Los comandos se documentan en `ai_context/RUNBOOK.md` y se expondran desde `Makefile`:

- `make setup`
- `make deploy-infra`
- `make resolve-model`
- `make create-model`
- `make prepare-batch-input`
- `make run-batch`
- `make collect-batch-output`
- `make reconstruct-batch-results`
- `make create-endpoint-config`
- `make create-endpoint`
- `make wait-endpoint`
- `make invoke-endpoint`
- `make validate-online-features`
- `make setup-autoscaling`
- `make check-metrics`
- `make deployment-report`
- `make destroy-endpoint`
- `make destroy-all`
- `make test`
- `make all-cloud`

## Formato esperado de respuesta al terminar una tarea

Al finalizar una tarea, responder con:

- Resumen breve de cambios.
- Archivos creados o modificados.
- Validaciones ejecutadas.
- Riesgos o pendientes.
- Siguiente prompt recomendado, si aplica.

## Reglas obligatorias

- No crear archivos fuera de `4_ML-Model-Deployment/`.
- No modificar archivos fuera de `4_ML-Model-Deployment/`.
- No mover ni renombrar `doc/4_AWS_Model_Deployment.pdf`.
- El laboratorio debe ejecutarse en AWS.
- El laboratorio debe soportar `standalone_mode` e `integrated_mode`.
- Batch inference debe implementarse con SageMaker Batch Transform.
- Real-time inference debe implementarse con SageMaker Real-Time Endpoint.
- No hardcodear credenciales.
- Usar AWS profiles o roles IAM.
- Aplicar minimo privilegio.
- Documentar costos.
- Incluir cleanup seguro.
- No eliminar recursos externos por defecto.
- No dejar endpoints activos sin advertencia.
- Preparar data capture para el laboratorio de monitoreo.
