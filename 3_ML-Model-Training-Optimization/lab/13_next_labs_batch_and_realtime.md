# 13 - Preparacion para batch inference y real-time inference

## Objetivo

Entender que componentes deja preparados este laboratorio para los siguientes laboratorios de inferencia batch y real-time.

Este laboratorio se enfoca en entrenamiento, optimizacion, tracking, registro y automatizacion. Los siguientes laboratorios se enfocaran en servir el modelo para consumo.

## Que vas a construir o validar

Este paso actualiza el contrato de features:

```text
artifacts/local_outputs/feature_contract.json
s3://<S3_BUCKET>/model_registry_metadata/feature_contract.json
```

El contrato conecta:

- Feature Group.
- Online Store.
- Offline Store.
- Features de entrenamiento.
- Features de inferencia.
- Target.
- Modelo seleccionado.
- Model Package Group.
- Metrica objetivo.

## Conceptos clave

| Concepto | Significado |
|---|---|
| Entrenar un modelo | Ajustar parametros del modelo usando datos historicos. |
| Evaluar un modelo | Medir desempeno con datos no vistos. |
| Registrar un modelo | Versionar el modelo en Model Registry con metadata y estado de aprobacion. |
| Desplegar un modelo | Crear infraestructura para servir predicciones. |
| Batch inference | Generar predicciones para muchos registros de una vez. |
| Real-time inference | Responder predicciones de baja latencia por request. |
| Near-real-time inference | Procesar solicitudes en cola con resultado posterior, usualmente mediante inferencia asincrona. |
| Offline Store | Fuente historica util para batch. |
| Online Store | Fuente de baja latencia util para endpoints. |

## Regla practica: datos actuales vs historicos

SageMaker Feature Store separa dos patrones de uso:

| Necesidad | Store recomendado | Explicacion |
|---|---|---|
| Obtener las features actuales de un cliente para responder una prediccion | Online Store | `GetRecord(customer_id)` devuelve el record actual disponible para ese identificador. |
| Reconstruir que features tenia un cliente en un momento anterior | Offline Store | El historial queda en S3 particionado por fecha y puede consultarse con Glue/Athena o procesos batch. |

Si ingestas una nueva version para `CUST-000001` con un timestamp mas reciente, el Online Store queda listo para consultas de inferencia casi de inmediato. El Offline Store tambien recibira ese registro, pero lo escribe en S3 de forma asincrona, por lo que puede tardar algunos minutos en verse en el prefijo `feature-store-offline/`.

Por eso:

- Real-time inference consulta Online Store para obtener el estado actual del cliente.
- Batch inference y entrenamiento usan Offline Store o datasets procesados derivados para trabajar con historia y volumen.
- Si necesitas comparar multiples timestamps de un mismo `customer_id`, no uses `GetRecord`; consulta Offline Store.

## Arquitectura para mantener Feature Store actualizado

El mismo Feature Group puede recibir datos desde pipelines batch y desde pipelines streaming.

### Actualizacion batch o micro-batch

Usa SageMaker Processing Jobs cuando los datos llegan en archivos o lotes periodicos:

```text
Raw data in S3
    |
    v
SageMaker Processing Job
    |
    v
Feature transformations
    |
    v
PutRecord to SageMaker Feature Store
    |
    +--> Online Store: features actuales para inferencia
    +--> Offline Store: historial en S3
```

Este patron sirve para:

- Cargas historicas iniciales.
- Backfills.
- Recalculo diario u horario de features.
- Preparacion auditable de datos de entrenamiento.
- Batch inference.

### Actualizacion streaming

Usa servicios de streaming cuando los eventos deben actualizar el Online Store con baja latencia:

```text
Application or product events
    |
    v
Amazon Kinesis Data Streams or Amazon MSK
    |
    v
Stream processor
    |-- AWS Lambda for simple/stateless transforms
    |-- Managed Service for Apache Flink for windowed/stateful transforms
    |
    v
Shared feature transformation code
    |
    v
PutRecord to SageMaker Feature Store
    |
    +--> Online Store: latest record by customer_id
    +--> Offline Store: historical records in S3
```

Para inferencia real-time:

```text
Prediction request with customer_id
    |
    v
GetRecord from Online Store
    |
    v
Build model payload
    |
    v
SageMaker Real-Time Endpoint
```

## Shared feature transformation code

`Shared feature transformation code` significa tener una sola implementacion reutilizable de la logica que convierte datos crudos en features del modelo.

Ejemplo: si un evento crudo contiene datos como sesiones, tickets de soporte y fallas de pago, el modelo probablemente no consume el evento tal cual. Consume features como:

```text
days_since_last_login
engagement_score
support_tickets_last_30d
payment_failures_last_90d
```

La logica que calcula esas columnas debe vivir en un modulo compartido, por ejemplo:

```text
feature_engineering/
  schema.py
  transforms.py
  validation.py
```

Ese mismo modulo deberia ser usado por:

- SageMaker Processing Jobs.
- Jobs batch.
- AWS Lambda.
- Aplicaciones de Flink.
- Scripts de batch inference.
- Pruebas unitarias de features.

Ejemplo conceptual:

```python
def compute_engagement_score(row):
    return (
        0.45 * min(row["sessions_last_30d"] / 25, 1)
        + 0.25 * min(row["avg_session_duration_last_30d"] / 40, 1)
        + 0.20 * (1 - min(row["days_since_last_login"], 60) / 60)
        + 0.10 * int(row["plan_type"] != "free")
    )
```

El objetivo es evitar training-serving skew: que el modelo sea entrenado con una formula y luego servido con otra distinta.

En este laboratorio, los archivos mas cercanos a esa idea son:

```text
src/feature_schema.py
processing/utils.py
```

Para produccion, conviene extraer la logica de features a un paquete compartido y versionado. La regla practica es simple: una feature debe tener una sola definicion fuente, aunque se ejecute en batch o streaming.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa al menos los pasos 03, 05, 06 y 09 si quieres un contrato completo con Feature Store, modelo y Registry.

3. Confirma que `.env.cloud` contiene `S3_BUCKET_NAME`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-13-next-labs
```

Con Python:

```bash
python -m src.export_feature_metadata
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 13
```

No hay wrapper `.ps1` especifico para este paso. En Windows usa el comando Python.

Internamente, `src.export_feature_metadata` lee `.env`, `.env.cloud` y `run_state.json`, construye el contrato con `src.feature_schema.build_feature_contract` y lo guarda localmente y en S3.

## Resultado esperado

Local:

```text
artifacts/local_outputs/feature_contract.json
artifacts/local_outputs/run_state.json
```

S3:

```text
s3://<S3_BUCKET>/model_registry_metadata/feature_contract.json
```

El contrato debe incluir:

- `feature_group_name`.
- `online_store_enabled`.
- `offline_store_s3_uri`.
- `record_identifier_name`.
- `event_time_feature_name`.
- `features`.
- `target_column`.
- `inference_features`.
- `training_features`.
- `batch_inference_source`.
- `realtime_lookup_key`.
- `model_package_group_name`.
- `model_package_arn`.
- `model_artifact_s3_uri`.
- `objective_metric_name`.
- `objective_metric_value`.

## Validacion local

1. Abre `artifacts/local_outputs/feature_contract.json`.
2. Confirma que `target_column` sea `churn_label`.
3. Confirma que `inference_features` no incluya `churn_label`.
4. Confirma que `realtime_lookup_key` sea `customer_id`.
5. Confirma que `model_artifact_s3_uri` apunte al modelo seleccionado.
6. Confirma que `model_approval_status` sea `PendingManualApproval`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon S3.
3. Entra al bucket del laboratorio.
4. Abre `model_registry_metadata/`.
5. Verifica `feature_contract.json`.
6. Ve a Amazon SageMaker > Feature Store > Feature groups.
7. Abre `churn-customer-features` si aun no ejecutaste cleanup.
8. Confirma Online Store y Offline Store.
9. Ve a Amazon SageMaker > Inference > Model Registry.
10. Abre `churn-model-package-group`.
11. Confirma que existe una version registrada del modelo.

## Como se conecta con batch inference

En un laboratorio de batch inference, el flujo esperado sera:

1. Leer datos desde Offline Store o desde un dataset procesado derivado.
2. Excluir `churn_label`.
3. Ordenar columnas segun `inference_features` o segun el bundle del modelo.
4. Usar el artefacto registrado o seleccionado.
5. Ejecutar SageMaker Batch Transform o el mecanismo batch definido por el curso.
6. Guardar predicciones en S3.

Componentes ya preparados:

- Modelo entrenado y evaluado.
- Artefacto `model.tar.gz`.
- Model Package en Registry.
- Contrato de features.
- Offline Store historico.

Componentes que faltara construir:

- Job o pipeline de batch inference.
- Dataset batch sin target.
- Ubicacion S3 de predicciones.
- Validacion de outputs batch.

## Como se conecta con real-time inference

En un laboratorio de real-time inference, el flujo esperado sera:

1. Recibir un `customer_id`.
2. Consultar Online Store con ese `customer_id`.
3. Construir el payload usando `inference_features`.
4. Excluir `churn_label`.
5. Crear o usar un SageMaker Real-Time Endpoint.
6. Invocar el endpoint y recibir una prediccion.

Componentes ya preparados:

- Feature Group con Online Store.
- `realtime_lookup_key=customer_id`.
- Features de inferencia documentadas.
- Codigo de inferencia empaquetado en `inference_source.tar.gz`.
- Modelo registrado en Model Registry.

Componentes que faltara construir:

- Modelo aprobado para despliegue.
- SageMaker Model/Endpoint Configuration/Endpoint.
- Logica de consulta Online Store + payload.
- Monitoreo del endpoint.
- Estrategia de costos para endpoints persistentes.

## Como se conecta con near-real-time inference

Near-real-time no es un tercer modo visible en la tabla de instancias del Model Registry. En SageMaker normalmente se implementa con Asynchronous Inference.

Usa este patron cuando:

- La respuesta no tiene que ser inmediata en la misma conexion HTTP.
- El payload puede ser grande.
- La inferencia o el preprocesamiento puede tardar mas que una llamada sincrona normal.
- Quieres que las solicitudes se encolen y que el resultado se escriba en S3.

Flujo esperado:

```text
Client or application
    |
    v
Input payload in S3
    |
    v
InvokeEndpointAsync
    |
    v
SageMaker async endpoint queue
    |
    v
Model container
    |
    v
Prediction output in S3
    |
    v
Optional SNS notification
```

Componentes ya preparados:

- Modelo registrado en Model Registry.
- Artefacto `model.tar.gz`.
- Codigo de inferencia empaquetado.
- Contrato de features para construir payloads consistentes.

Componentes que faltara construir:

- Aprobacion del Model Package.
- Endpoint configuration con `AsyncInferenceConfig`.
- Endpoint asincrono.
- Bucket/prefijos S3 para inputs y outputs asincronos.
- Notificaciones opcionales con Amazon SNS.
- Logica para consultar el estado y leer el resultado desde S3.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `model_artifact_s3_uri` aparece vacio | No se ejecuto training, HPO o comparacion. | Ejecuta pasos 05, 06 y 07. |
| `model_package_arn` aparece vacio | No se ejecuto Model Registry. | Ejecuta paso 09. |
| Online Store no disponible | Feature Group no existe o fue eliminado. | Reejecuta paso 03 si aun necesitas validar. |
| Contrato no aparece en S3 | Falta `S3_BUCKET_NAME` o permisos. | Revisa `.env.cloud` y permisos S3. |

## Antes de terminar

Si vas a continuar con inferencia batch o real-time, conserva:

- `feature_contract.json`.
- Model Package en Registry.
- Artefacto del modelo.
- Feature Group.
- Bucket S3 con metadata.

Si ya no continuaras, ejecuta cleanup en el paso 12 para evitar costos.
