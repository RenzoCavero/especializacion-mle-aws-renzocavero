# Fraud 05 - Deploy Real-Time Endpoint y online scoring

## Objetivo

Crear un SageMaker Model deployable desde el modelo registrado, desplegar un SageMaker Real-Time Endpoint y ejecutar una prediccion online de fraude usando Online Store y persistencia operacional en AWS.

## Que vas a construir o validar

Este paso valida:

- Limpieza y validacion del request.
- Feature engineering de la transaccion actual.
- Lookup de historical/entity features con SageMaker Feature Store Online Store.
- Ensamblaje del vector final con `feature_order.json`.
- SageMaker Model visible como modelo deployable.
- Endpoint Configuration con Production Variant y data capture.
- SageMaker Real-Time Endpoint real.
- Prediccion invocando SageMaker Runtime.
- Persistencia de trazas en S3.
- Decision operacional en DynamoDB.
- Evento asincrono en SQS.

## Input del paso

Transaccion default:

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

Variables relevantes:

```bash
FRAUD_MODEL_NAME=ml-deploy-lab-fraud-model
FRAUD_ENDPOINT_CONFIG_NAME=ml-deploy-lab-fraud-realtime-config
FRAUD_USE_SAGEMAKER_ENDPOINT=true
FRAUD_ENDPOINT_NAME=ml-deploy-lab-fraud-realtime-endpoint
FRAUD_INSTANCE_TYPE=ml.m5.large
FRAUD_INITIAL_INSTANCE_COUNT=1
FRAUD_ENABLE_DATA_CAPTURE=true
FRAUD_DECISION_TABLE_NAME=<tabla>
FRAUD_EVENT_QUEUE_URL=<cola>
```

## Output esperado del paso

Respuesta tipo:

```json
{
  "transaction_id": "T001",
  "request_id": "REQ-...",
  "fraud_score": 0.87,
  "decision": "manual_review",
  "reason_codes": ["high_amount_vs_user_avg", "risky_merchant"],
  "model_version": "fraud_model_v1",
  "feature_version": "fraud_features_v1",
  "latency_ms": 142
}
```

Trazas en S3:

```text
operational/inference-logs/raw-events/
operational/inference-logs/cleaned-events/
operational/inference-logs/feature-vectors/
operational/inference-logs/predictions/
```

Metadata local:

```text
artifacts/local_outputs/fraud_sagemaker_model.json
artifacts/local_outputs/fraud_endpoint_config.json
artifacts/local_outputs/fraud_realtime_endpoint.json
```

## Conceptos claves

El Fraud Scoring Service es responsable de transformar el request en un payload model-ready. En esta arquitectura no se usa SageMaker Inference Pipeline; el endpoint recibe el vector final y solo predice.

Current transaction features se calculan en memoria porque dependen del evento actual y no requieren historia: `amount_normalized`, `hour_of_day`, `day_of_week`, `is_weekend`, one-hot de categoria, encoding de canal e indicador cross-border.

Historical/entity features se leen desde Online Store. Ejemplos: `user_avg_amount_30d`, `card_txn_count_5m`, `merchant_risk_score`, `device_trust_score`. Estas features representan conocimiento acumulado antes de que la transaccion actual llegue.

El paso anterior registra un modelo simple en Model Registry. Este paso lo convierte en un SageMaker Model deployable, crea una Endpoint Configuration y despliega un Real-Time Endpoint. Por eso en SageMaker Studio deberias ver el modelo en una zona de modelos deployables o como recurso SageMaker Model, ademas del Model Package registrado.

Registrar un modelo no lo despliega. Model Registry es gobierno/versionado. SageMaker Model es el recurso deployable. Endpoint Configuration define instancia, variantes y data capture. Real-Time Endpoint mantiene capacidad activa para inferencia de baja latencia.

Este endpoint genera costo mientras este activo. El cleanup de la ruta fraud borra endpoint, endpoint config y SageMaker Model, pero conserva Model Registry, S3, DynamoDB y SQS.

DynamoDB guarda la decision para consulta operacional. S3 guarda trazas para auditoria y replay. SQS publica un evento para que procesos posteriores actualicen lake y features sin bloquear la respuesta online.

Las trazas bajo `operational/inference-logs/` se generan automaticamente dentro del scoring service cada vez que se ejecuta este paso. No necesitas correr un script manual adicional. Son diferentes de CloudWatch Logs y de SageMaker Data Capture: son evidencia de negocio para reproducir una decision.

## Prerrequisitos

- Haber ejecutado `fraud-step 01`.
- Haber ejecutado `fraud-step 03` para tener Online Store cargado.
- Haber ejecutado `fraud-step 04` para registrar el modelo en Model Registry.
- Tabla DynamoDB y cola SQS disponibles desde `.env.cloud`.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 05
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.deploy_endpoint
python -m fraud_lab.aws.pipelines.online_predict_aws
```

## Resultado esperado

Se crea o reutiliza el endpoint real-time. Se imprime una prediccion JSON. Se crea un item en DynamoDB y un mensaje en SQS. S3 recibe los logs de raw event, cleaned event, feature vector y prediction event.

## Validacion local

El stdout debe incluir metadata del endpoint y luego `fraud_score`, `decision`, `trace_uris` y `async_message_id`.

## Validacion en consola AWS

Revisa:

- DynamoDB: item con `transaction_id=T001`.
- SQS: un mensaje disponible antes de ejecutar `fraud-step 06`.
- S3: logs bajo `operational/inference-logs/`.
- SageMaker Models: modelo `FRAUD_MODEL_NAME` como recurso deployable.
- SageMaker Endpoints: endpoint `FRAUD_ENDPOINT_NAME` en estado `InService`.
- SageMaker Feature Store: registros consultables para `U123`, `C789`, `M999`, `D123`.

### Probar el endpoint desde SageMaker Studio Playground

En SageMaker Studio puedes abrir:

```text
Deployments -> Endpoints -> ML Deploy Lab Fraud Realtime Endpoint -> Playground
```

Selecciona:

```text
Testing option: Test the sample request
Content type: application/json
```

El Playground invoca directamente el SageMaker Real-Time Endpoint. Por eso no debes enviar la transaccion cruda del sistema transaccional. En esta pantalla no se ejecuta el Fraud Scoring Service, no se consulta Online Store y no se arma el vector de features. Para esta prueba debes enviar un payload model-ready, es decir, el vector final que normalmente construiria el servicio de scoring despues de limpiar la transaccion, consultar Feature Store y ordenar las features con `feature_order.json`.

Payload recomendado:

```json
{
  "features": {
    "amount_normalized": 500.0,
    "currency_normalized_amount": 500.0,
    "hour_of_day": 14,
    "day_of_week": 6,
    "is_weekend": 1,
    "category_electronics": 1,
    "category_travel": 0,
    "category_grocery": 0,
    "channel_mobile": 1,
    "channel_web": 0,
    "is_cross_border": 0,
    "account_age_days": 730,
    "customer_segment_premium": 1,
    "user_txn_count_1h": 4,
    "user_avg_amount_30d": 87.5,
    "card_txn_count_5m": 3,
    "card_declined_count_1h": 2,
    "merchant_fraud_rate_30d": 0.032,
    "merchant_risk_score": 0.71,
    "device_users_count_7d": 8,
    "device_trust_score": 0.35
  }
}
```

Respuesta esperada:

```json
[
  {
    "fraud_score": 0.87,
    "score": 0.87,
    "predicted_label": 1,
    "decision": "reject",
    "reason_codes": [
      "high_amount_vs_user_avg",
      "risky_merchant",
      "new_or_risky_device",
      "recent_card_declines"
    ],
    "model_version": "fraud_model_v1",
    "feature_version": "fraud_features_v1"
  }
]
```

El valor exacto de `fraud_score` puede variar ligeramente porque el modelo es entrenado durante el laboratorio, pero el formato debe conservarse: score numerico, label, decision, reason codes y versiones de modelo/features.

Si la invocacion funciona, CloudWatch Logs debe mostrar una linea parecida a:

```text
POST /invocations HTTP/1.1" 200
```

Esta prueba valida solo el endpoint. Para validar la arquitectura online completa usa `python -m src.lab_runner fraud-step 05`, porque ese paso ejecuta el Fraud Scoring Service, consulta Online Store, persiste logs en S3, guarda la decision en DynamoDB y emite el evento SQS.

Para ver las trazas en S3:

```bash
aws s3 ls "s3://$S3_BUCKET_NAME/$FRAUD_S3_PREFIX/operational/inference-logs/" --recursive --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

Para verificar SQS antes de `fraud-step 06`:

```bash
aws sqs get-queue-attributes --queue-url "$FRAUD_EVENT_QUEUE_URL" --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible --profile "$AWS_PROFILE" --region "$AWS_REGION"
```
