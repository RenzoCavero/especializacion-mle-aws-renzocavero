# Lab 04 Spec - Despliegue de modelo AWS - Machine Learning

## Tema

Despliegue de modelo AWS - Machine Learning.

## Objetivo

Implementar en AWS dos patrones de inferencia con Amazon SageMaker:

1. SageMaker Batch Transform.
2. SageMaker Real-Time Endpoint.

El laboratorio tambien debe explicar Batch Transform, Real-Time Endpoint, Asynchronous Inference y Serverless Inference.

## Audiencia

Audiencia con conocimientos basicos o intermedios de cloud computing, data science y machine learning que necesita entender como pasar de un modelo entrenado a un servicio de inferencia operativo en AWS.

## Servicios AWS usados

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

## Modos de ejecucion

### standalone_mode

Modo por defecto. No depende del laboratorio 3. Debe preparar un dataset sintetico, un artefacto de modelo minimo, un contrato de features minimo, Feature Store con Online Store y Offline Store, input batch en S3, SageMaker Model, Batch Transform Job y Real-Time Endpoint.

### integrated_mode

Modo integrado con el laboratorio 3. Reutiliza Model Registry, Model Package, `model.tar.gz`, Feature Group, Online Store, Offline Store, feature contract y SageMaker Execution Role. Es la ruta mas cercana a produccion.

Variables esperadas:

- `MODEL_PACKAGE_GROUP_NAME`
- `MODEL_PACKAGE_ARN`
- `MODEL_ARTIFACT_S3_URI`
- `FEATURE_GROUP_NAME`
- `OFFLINE_STORE_S3_URI`
- `FEATURE_CONTRACT_S3_URI`
- `SAGEMAKER_EXECUTION_ROLE_ARN`

## Flujo del laboratorio

1. Revisar patron de inferencia adecuado.
2. Validar variables de entorno y permisos.
3. Detectar `LAB_MODE`.
4. En `integrated_mode`, obtener modelo desde Model Registry o `MODEL_ARTIFACT_S3_URI`.
5. En `standalone_mode`, preparar modelo de ejemplo o artefacto `model.tar.gz` minimo.
6. Crear SageMaker Model.
7. Crear o reutilizar Feature Store con Online Store y Offline Store.
8. Preparar input batch desde Offline Store/export S3.
9. Ejecutar SageMaker Batch Transform.
10. Guardar output batch en S3.
11. Reconstruir resultados con `transaction_id` o `customer_id`.
12. Crear Endpoint Configuration.
13. Crear Real-Time Endpoint.
14. Validar estado `InService`.
15. Consultar Feature Store Online Store con `GetRecord`.
16. Invocar endpoint.
17. Validar response contract.
18. Configurar data capture para futuras tareas de monitoreo.
19. Configurar autoscaling basico.
20. Revisar metricas y logs en CloudWatch.
21. Generar reporte de despliegue.
22. Ejecutar cleanup completo.

## Flujo batch

El flujo batch parte desde S3 o Feature Store Offline Store. Debe preparar un archivo de inferencia sin target, conservar un identificador original, ejecutar SageMaker Batch Transform, guardar outputs en S3 y reconstruir resultados con el ID de negocio.

## Flujo real-time

El flujo real-time recibe un request, valida el contrato, consulta Feature Store Online Store, construye el payload de inferencia, invoca el Real-Time Endpoint y devuelve una respuesta con `score`, `decision`, `model_version` y `request_id`.

## Recursos AWS esperados

- Bucket S3 o prefijos S3 para inputs, outputs, artefactos y reportes.
- SageMaker Model.
- SageMaker Batch Transform Job.
- SageMaker Endpoint Configuration.
- SageMaker Real-Time Endpoint.
- Configuracion de data capture.
- Registro de autoscaling, si esta habilitado.
- Logs y metricas en CloudWatch.

## Variables de entorno

- `LAB_MODE`
- `AWS_PROFILE`
- `AWS_REGION`
- `PROJECT_NAME`
- `ENVIRONMENT`
- `RESOURCE_PREFIX`
- `S3_BUCKET_NAME`
- `SAGEMAKER_EXECUTION_ROLE_ARN`
- `MODEL_PACKAGE_GROUP_NAME`
- `MODEL_PACKAGE_ARN`
- `MODEL_ARTIFACT_S3_URI`
- `FEATURE_GROUP_NAME`
- `OFFLINE_STORE_S3_URI`
- `FEATURE_CONTRACT_S3_URI`
- `CREATE_STANDALONE_MODEL`
- `CREATE_STANDALONE_FEATURE_GROUP`
- `ENDPOINT_NAME`
- `INSTANCE_TYPE`
- `BATCH_INSTANCE_TYPE`
- `BATCH_INSTANCE_COUNT`
- `ENABLE_DATA_CAPTURE`
- `ENABLE_AUTOSCALING`

## Outputs esperados

- Batch input en S3.
- Batch output en S3.
- Archivo local o reporte con reconstruccion de predicciones.
- Endpoint real-time `InService`.
- Resultado de invocacion online.
- Reporte de despliegue.
- Metadata de data capture.
- Evidencia de logs y metricas en CloudWatch.
- Registro de recursos creados para cleanup.

## Criterios de aceptacion

- Se puede ejecutar en `standalone_mode` sin depender del laboratorio 3.
- Se puede ejecutar en `integrated_mode` reutilizando recursos del laboratorio 3.
- Se puede crear o resolver SageMaker Model.
- Se puede ejecutar Batch Transform.
- Se generan predicciones batch en S3.
- Se reconstruyen predicciones con IDs originales.
- Se puede crear un Real-Time Endpoint.
- Se puede invocar el endpoint.
- El endpoint usa payload validado.
- Se consulta Feature Store Online Store cuando esta disponible.
- Se documenta Offline Store como fuente para batch.
- Se configura o documenta data capture.
- Se configura o documenta autoscaling.
- Se revisan metricas de CloudWatch.
- Se genera reporte de despliegue.
- Existe cleanup de endpoint, endpoint config, model y recursos creados.
- No se hardcodean credenciales.
- No se crean archivos fuera de `4_ML-Model-Deployment/`.
- La documentacion explica batch, real-time, async y serverless, aunque solo batch y real-time sean obligatorios.

## Reglas de cleanup

- Eliminar endpoint creado por el laboratorio.
- Eliminar endpoint config creado por el laboratorio.
- Eliminar SageMaker Model creado por el laboratorio.
- Eliminar objetos S3 creados por el laboratorio si corresponde.
- No eliminar Model Package externo.
- No eliminar Feature Group externo.
- No eliminar recursos de laboratorios anteriores por defecto.

## Relacion con futuros laboratorios

El laboratorio 4 debe dejar una base automatizable para el laboratorio 5 y debe capturar evidencia suficiente para el laboratorio 6: data capture, metricas, logs, outputs batch, request/response contract y metadata de modelo.
