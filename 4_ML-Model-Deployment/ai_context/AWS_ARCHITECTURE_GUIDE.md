# AWS Architecture Guide - Laboratorio 4

## Mapa de componentes

| Componente | Servicio AWS |
|---|---|
| Modelo registrado | SageMaker Model Registry |
| Artefacto model.tar.gz | Amazon S3 |
| Modelo desplegable | SageMaker Model |
| Batch input | Amazon S3 / Feature Store Offline Store |
| Batch inference | SageMaker Batch Transform |
| Batch output | Amazon S3 |
| Features online | SageMaker Feature Store Online Store |
| Endpoint real-time | SageMaker Real-Time Endpoint |
| Endpoint config | SageMaker Endpoint Configuration |
| Production variant | SageMaker Production Variant |
| Data capture | SageMaker Endpoint Data Capture |
| Logs y metricas | Amazon CloudWatch |
| Autoscaling | Application Auto Scaling |
| IAM | SageMaker Execution Role |
| Cifrado | SSE-S3 / AWS KMS |
| Orquestacion batch opcional | EventBridge / Step Functions |
| Monitoreo futuro | SageMaker Model Monitor |
| Data Lake fraude | Amazon S3 |
| Decisiones operacionales fraude | Amazon DynamoDB |
| Eventos asincronos fraude | Amazon SQS |

## Arquitectura batch

1. Offline Store o dataset en S3.
2. Preparacion del input batch.
3. SageMaker Batch Transform Job.
4. Output en S3.
5. Reconstruccion con ID original.
6. Reporte de resultados.
7. Logs y metricas en CloudWatch.

El batch input debe excluir el target y conservar un identificador como `transaction_id` o `customer_id`. El batch output debe poder unirse con los registros originales para analisis posterior.

## Arquitectura real-time

1. Cliente o script invocador.
2. Validacion de request.
3. Lookup de features en Online Store.
4. Construccion de payload.
5. Invocacion de Real-Time Endpoint.
6. Respuesta con `score`, `decision`, `model_version` y `request_id`.
7. Logs, metricas, data capture y autoscaling.

El endpoint debe estar protegido por IAM y no debe exponer datos sensibles en respuestas o logs.

## Arquitectura cloud del caso de fraude

1. API o script de scoring recibe una transaccion cruda.
2. Fraud Scoring Service valida y limpia la transaccion.
3. Las current transaction features se calculan en memoria.
4. SageMaker Feature Store Online Store devuelve historical/entity features con `GetRecord`.
5. Un modelo simple de fraude se registra como Model Package aprobado en SageMaker Model Registry.
6. El servicio ensambla el vector final usando `feature_order.json`.
7. El Model Package se convierte en SageMaker Model deployable, Endpoint Configuration y Real-Time Endpoint.
8. S3 guarda raw event, cleaned event, feature vector y prediction event.
9. DynamoDB guarda la decision operacional por `transaction_id`.
10. SQS recibe un evento asincrono para actualizar Data Lake, Online Store y Offline Store para predicciones futuras.
11. Batch prediction y retraining leen Feature Store Offline Store/export S3 con point-in-time joins.

Este flujo demuestra que Online Store no debe usarse como paso intermedio para guardar y leer inmediatamente features de la misma transaccion. La transaccion actual se transforma en memoria; el Online Store aporta historia reusable.

## Flujo standalone

1. Generar dataset sintetico.
2. Crear artefacto `model.tar.gz` de ejemplo.
3. Crear Feature Group con Online Store y Offline Store.
4. Aplicar transformacion comun y cargar registros en Feature Store.
5. Subir artefactos a S3.
6. Crear SageMaker Model.
7. Ejecutar Batch Transform desde export Offline Store/S3.
8. Crear Real-Time Endpoint.
9. Invocar endpoint con payload construido desde Online Store.
10. Generar reportes.
11. Destruir recursos.

Este flujo existe para que el laboratorio pueda ejecutarse sin depender del laboratorio 3.

## Flujo integrado

1. Resolver Model Package o `model.tar.gz` desde laboratorio 3.
2. Leer Feature Contract si existe.
3. Usar Offline Store o dataset derivado para batch.
4. Usar Online Store para request real-time.
5. Desplegar modelo.
6. Ejecutar batch y real-time.
7. Preparar data capture para monitoreo.
8. Destruir solo recursos creados por laboratorio 4.

Este flujo representa una aproximacion mas cercana a produccion porque reutiliza artefactos registrados, contratos y Feature Store.

## Fronteras de responsabilidad

- El laboratorio 4 crea recursos de despliegue.
- El laboratorio 4 no entrena modelos productivos.
- El laboratorio 4 no borra recursos externos por defecto.
- El laboratorio 4 prepara evidencia para MLOps y monitoreo.

## Trazabilidad minima

Cada ejecucion debe registrar:

- `LAB_MODE`.
- `model_name`.
- `model_version` o `model_package_arn`.
- `model_artifact_s3_uri`.
- `batch_job_name`.
- `batch_input_s3_uri`.
- `batch_output_s3_uri`.
- `endpoint_name`.
- `endpoint_config_name`.
- `request_id`.
- Fecha y region AWS.
