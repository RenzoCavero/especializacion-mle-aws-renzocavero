# Source Summary - doc/4_AWS_Model_Deployment.pdf

Resumen estructurado del PDF `doc/4_AWS_Model_Deployment.pdf`, sin copiar texto largo. El material extraido localmente identifica el titulo "Model Deployment en AWS: Batch y Real-Time Inference" y enfoca arquitectura, estrategia y operacion de modelos ML en Amazon SageMaker.

## Promesa del tema

El tema conecta artefactos entrenados con patrones de inferencia operativos en AWS. La promesa educativa es poder elegir, disenar y operar despliegues en SageMaker considerando latencia, throughput, volumen, payload, costo, criticidad y trazabilidad.

## Que significa desplegar un modelo ML

Desplegar un modelo no es solo subir un archivo. Implica convertir un artefacto entrenado en un recurso invocable, con contrato de entrada y salida, infraestructura, permisos, logs, metricas, escalabilidad, versionado, seguridad y cleanup.

## Patrones de inferencia

- Batch Transform: procesa lotes masivos sin endpoint persistente.
- Real-Time Endpoint: responde solicitudes sincronas de baja latencia.
- Asynchronous Inference: procesa payloads grandes o trabajos near real-time donde el consumidor puede esperar.
- Serverless Inference: atiende trafico intermitente reduciendo operacion, con tolerancia a cold start.

## Batch vs real-time

Batch es adecuado cuando el consumidor no necesita una respuesta inmediata y se busca optimizar costo total y throughput. Real-time es adecuado para decisiones sincronas como fraude, recomendaciones, aprobaciones en linea o aplicaciones interactivas.

## Matriz de decision

Criterios principales:

- Latencia esperada.
- Volumen total.
- Tamano del payload.
- Frecuencia de invocacion.
- Costo operativo.
- Criticidad del resultado.
- Complejidad de operacion.
- Necesidad de escalabilidad.

Regla de desempate: si el consumidor no espera una respuesta inmediata, evitar un endpoint persistente y evaluar Batch o Async para optimizar TCO.

## SageMaker Batch Transform

Batch Transform busca maximizar throughput total. Procesa grandes volumenes en el menor tiempo posible, distribuyendo registros en instancias de transformacion.

Parametros relevantes:

- `SplitType`: divide registros por linea o RecordIO.
- `BatchStrategy`: `MultiRecord` para eficiencia o `SingleRecord` para depuracion.
- `MaxPayloadInMB`: tamano maximo enviado al contenedor.
- `InstanceCount` e `InstanceType`: capacidad total del cluster.

Metricas a observar:

- Duracion del job.
- Registros por segundo.
- Errores.
- Costo por prediccion.

## Arquitectura batch con Feature Store

La arquitectura batch usa Feature Store Offline Store o archivos en S3 como fuente. El input debe excluir la columna target, conservar un identificador de negocio y guardar predicciones en S3. Luego se reconstruyen resultados con `transaction_id`, `customer_id` u otro ID original.

## Diseno de input/output batch

El input batch debe ser estable, versionado y trazable. Debe conservar metadata suficiente para unir predicciones con registros originales, pero enviar al modelo solo las features esperadas. El output batch debe guardarse en S3 junto con metadata del job, modelo, fecha y modo de ejecucion.

## SageMaker Real-Time Endpoint

Real-Time Endpoint protege latencias p95 y p99 para solicitudes sincronas. El desafio principal es manejar picos de trafico, concurrencia variable y capacidad insuficiente. La solucion esperada incluye auto scaling basado en metricas operativas.

Metricas relevantes:

- `InvocationsPerInstance`.
- CPU, memoria o GPU utilization.
- Latencia p95 y p99.
- 4xx y 5xx.
- Invocaciones.
- Concurrencia.
- Cooldown de escalamiento.
- Pre-warming o warm pools cuando aplique.

## Arquitectura real-time

El cliente envia un request, el sistema valida contrato, consulta Online Store si existe, arma el payload, invoca el endpoint y devuelve una respuesta con score, decision, version de modelo y request_id. CloudWatch y data capture deben registrar evidencia para monitoreo posterior.

## Request/response contract

El request debe contener solo features de inferencia y claves necesarias para lookup. La columna target nunca debe enviarse al endpoint. La respuesta debe ser explicita y trazable:

- `score`
- `decision`
- `model_version`
- `request_id`

## Validacion y resiliencia

El laboratorio debe validar schema, tipos, columnas esperadas, columnas prohibidas y valores nulos criticos. Debe manejar errores de AWS, fallas de endpoint, timeouts, respuestas 4xx/5xx y errores de contenedor con mensajes comprensibles.

## Escalabilidad, latencia y throughput

Batch escala por numero y tipo de instancias de transformacion y por parametros de particionado. Real-time escala por production variants y Application Auto Scaling. El objetivo batch es throughput total; el objetivo real-time es proteger latencia y disponibilidad.

## Observabilidad y preparacion para Model Monitor

CloudWatch debe usarse para logs y metricas. Data capture debe quedar preparado para alimentar tareas posteriores de monitoreo y data drift. El laboratorio debe registrar inputs, outputs, modelo usado, version, endpoint, batch job y request IDs.

## Seguridad, IAM, cifrado, trazabilidad y cleanup

El material enfatiza operacion segura: IAM de minimo privilegio, S3 cifrado, buckets no publicos, no credenciales en codigo, versionado, trazabilidad, cleanup y despliegues seguros con enfoque MLOps.

## Como se traduce este material al laboratorio

- Batch Transform -> `src/run_batch_transform.py`.
- S3 input/output -> data lake de inferencia batch.
- Feature Store Offline Store -> fuente batch.
- Feature Store Online Store -> lookup de features para real-time.
- Real-Time Endpoint -> `src/create_realtime_endpoint.py`.
- Request/response contract -> `src/validate_request_response.py`.
- Autoscaling -> `src/configure_autoscaling.py`.
- CloudWatch -> `src/check_cloudwatch_metrics.py`.
- Cleanup -> `src/cleanup_all.py`.
