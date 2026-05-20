# Fraud 00 - Arquitectura de inferencia para fraude

## Objetivo

Entender la arquitectura completa de inferencia para deteccion de fraude con tarjetas de credito y como se mapea cada componente del laboratorio a un servicio AWS real.

Este paso no crea recursos. Define el mapa mental del laboratorio: que ocurre en el camino online, que ocurre de forma asincrona, que se usa para batch prediction y que se conserva para retraining.

## Que vas a construir o validar

Vas a validar la separacion entre:

- Transaccion actual recibida por una API.
- Current transaction features calculadas en memoria.
- Historical/entity features leidas desde SageMaker Feature Store Online Store.
- Data Lake en S3 con capas raw, cleaned y curated.
- Offline Store para batch prediction y retraining.
- SageMaker Model Registry para gobierno del modelo.
- SageMaker Real-Time Endpoint para inferencia online.
- SageMaker Batch Transform Job para inferencia batch cuando exista cuota disponible.
- DynamoDB como tabla operacional de decisiones.
- SQS como mecanismo asincrono para actualizar datos y features futuras.

## Input del paso

No crea recursos. El input conceptual es una transaccion como:

```json
{
  "transaction_id": "T001",
  "user_id": "U123",
  "card_id": "C789",
  "merchant_id": "M999",
  "device_id": "D123",
  "amount": "500",
  "currency": "pen",
  "category": "Electronics",
  "channel": "Mobile",
  "location": "Lima|PE",
  "timestamp": "17/05/2026 14:20"
}
```

## Output esperado del paso

Comprender el flujo online principal:

```text
API / Fraud Scoring Service
  -> validar request
  -> limpiar y canonizar la transaccion
  -> calcular current transaction features en memoria
  -> consultar Online Store para features historicas/de entidad
  -> ensamblar feature vector segun feature_order.json
  -> invocar SageMaker Real-Time Endpoint
  -> guardar decision operacional en DynamoDB
  -> guardar trazas en S3
  -> emitir evento a SQS para procesamiento asincrono
```

## Flujo arquitectonico del laboratorio

| Paso | Capa arquitectonica | Servicio AWS principal | Que valida |
| --- | --- | --- | --- |
| 00 | Arquitectura | N/A | Define los limites entre Data Lake, Feature Store, Model Registry, endpoint, batch y eventos. |
| 01 | Infraestructura base | CloudFormation, S3, IAM, DynamoDB, SQS | Crea bucket, rol de SageMaker, tabla de decisiones y cola de eventos. |
| 02 | Data Lake | S3 | Genera raw, cleaned, curated, labels y artefactos de contrato de features. |
| 03 | Feature Store | SageMaker Feature Store | Crea Feature Groups con Online Store y Offline Store. |
| 04 | Gobierno del modelo | SageMaker Model Registry | Empaqueta modelo + codigo de inferencia y registra un Model Package aprobado. |
| 05 | Inferencia online | SageMaker Real-Time Endpoint, Feature Store Runtime, DynamoDB, SQS, S3 | Consulta Online Store, invoca endpoint, persiste trazas y emite evento. |
| 06 | Actualizacion asincrona | SQS, S3, Feature Store | Procesa eventos posteriores al scoring y actualiza features futuras. |
| 07 | Inferencia batch | S3, Offline Store export, SageMaker Batch Transform Job | Usa Offline Store y point-in-time joins para scoring batch. |
| 08 | Retraining dataset | S3, Offline Store export | Une transacciones historicas, features historicas y labels tardios. |
| 09 | Cleanup | SageMaker, Feature Store | Elimina endpoint/model/Feature Groups del caso de fraude. |

## Conceptos claves

La transaccion actual trae proto-features: `amount`, `currency`, `timestamp`, `location`, `category`, `channel` y llaves de entidad como `user_id`, `card_id`, `merchant_id` y `device_id`. Algunas features se pueden calcular inmediatamente desde ese payload: `amount_normalized`, `hour_of_day`, `is_weekend`, `category_electronics`, `channel_mobile` o `is_cross_border`.

Las features historicas no deberian recalcularse en el camino online. En una arquitectura real, agregaciones como `user_txn_count_1h`, `card_txn_count_5m`, `merchant_risk_score` o `device_trust_score` ya deben existir en Online Store. El servicio de scoring solo las busca con una llave de entidad y ensambla el vector final.

El Online Store no debe usarse como paso temporal para guardar y leer la misma transaccion. Si el servicio calcula `hour_of_day=14`, lo usa directamente en memoria. Guardarlo en Online Store para leerlo inmediatamente agregaria latencia, dependencia operacional y riesgo de fallo sin aportar valor a la prediccion actual.

El Data Lake y Feature Store no son lo mismo. El Data Lake conserva eventos y tablas de negocio en S3. Feature Store publica datos ML-ready, versionados por `event_time` y organizados por Feature Group. Curated es business-ready; Feature Store es model-ready.

El Model Registry tampoco es un endpoint. El Registry gobierna versiones aprobadas del modelo. Desplegar requiere crear un SageMaker Model deployable y luego usarlo en un Real-Time Endpoint o en un Batch Transform Job.

SQS separa el tiempo de respuesta online del mantenimiento de datos. La prediccion debe responder rapido; la actualizacion del Data Lake y de features para futuras transacciones puede ocurrir segundos despues.

## Prerrequisitos

- Haber instalado dependencias con `pip install -r requirements.txt`.
- Revisar `.env.example`.
- Tener un AWS profile o credenciales del entorno configuradas.

## Pasos de ejecucion

Listar la ruta fraud:

```bash
python -m src.lab_runner list
```

Ejecutar este paso:

```bash
python -m src.lab_runner step 00
```

## Resultado esperado

Este paso imprime una referencia a la documentacion y no crea recursos. Despues de leerlo, deberias poder explicar por que online scoring usa Online Store para historia y por que batch/retraining usan Offline Store.

## Validacion local

Ejecuta:

```bash
python -m src.lab_runner list
```

Debes ver los pasos `00` a `09` de la ruta fraud.

## Validacion en consola AWS

No aplica para este paso. Todavia no se crea infraestructura.
