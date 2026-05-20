# Fraud 03 - SageMaker Feature Store Online y Offline

## Objetivo

Crear y cargar Feature Groups de fraude en SageMaker Feature Store con Online Store y Offline Store.

Este paso convierte datos business-ready del Data Lake en datos ML-ready organizados por entidad, tiempo y contrato de features.

## Que vas a construir o validar

Este paso crea o reutiliza Feature Groups para:

- `user_profile_features`
- `user_behavior_features`
- `card_velocity_features`
- `merchant_risk_features`
- `device_features`
- `last_transaction_features`

Cada Feature Group tiene:

- Record identifier: llave de entidad, por ejemplo `user_id`, `card_id`, `merchant_id` o `device_id`.
- `event_time`: timestamp que indica desde cuando ese registro de features es valido.
- Online Store habilitado para lookup de baja latencia.
- Offline Store en S3 para historico.
- Export CSV controlado para batch prediction y retraining.

## Input del paso

Requiere:

```bash
S3_BUCKET_NAME=<bucket>
SAGEMAKER_EXECUTION_ROLE_ARN=<role>
FRAUD_S3_PREFIX=ml-deploy-lab/lab/fraud
FRAUD_FEATURE_GROUP_PREFIX=ml-deploy-lab-fraud
```

Registros base de ejemplo:

```json
{
  "user_id": "U123",
  "event_time": "2026-05-17T14:00:00Z",
  "user_txn_count_1h": 4,
  "user_avg_amount_30d": 87.5,
  "user_max_amount_30d": 520.0
}
```

## Output esperado del paso

Feature Groups fisicos con nombres como:

```text
ml-deploy-lab-fraud-user-profile-features
ml-deploy-lab-fraud-user-behavior-features
ml-deploy-lab-fraud-card-velocity-features
ml-deploy-lab-fraud-merchant-risk-features
ml-deploy-lab-fraud-device-features
ml-deploy-lab-fraud-last-transaction-features
```

Exports S3:

```text
s3://<bucket>/<prefix>/feature-store/offline-export/user_behavior_features/features.csv
s3://<bucket>/<prefix>/feature-store/offline-export/card_velocity_features/features.csv
```

## Ejemplos de Feature Groups

| Feature Group | Entidad | Ejemplo de feature | Definicion | Uso en el laboratorio |
| --- | --- | --- | --- | --- |
| `user_profile_features` | `user_id` | `account_age_days` | Dias desde la creacion de la cuenta del usuario. Es una feature estatica o de cambio lento. | Se usa como senal de madurez de la cuenta. Cuentas muy nuevas pueden aportar mas riesgo que cuentas antiguas. |
| `user_behavior_features` | `user_id` | `user_avg_amount_30d` | Promedio del monto transaccional del usuario durante los ultimos 30 dias. | Permite comparar la transaccion actual contra el comportamiento normal del usuario. Alimenta razonamientos como `high_amount_vs_user_avg`. |
| `card_velocity_features` | `card_id` | `card_txn_count_5m` | Numero de transacciones recientes de la tarjeta en una ventana de 5 minutos. | Representa velocidad. Muchas transacciones en poco tiempo elevan el riesgo de fraude o abuso automatizado. |
| `merchant_risk_features` | `merchant_id` | `merchant_risk_score` | Score normalizado de riesgo del comercio, calculado desde fraude historico, chargebacks, categoria y perfil del merchant. | Eleva el score cuando la transaccion ocurre en un comercio riesgoso. Puede generar reason code `risky_merchant`. |
| `device_features` | `device_id` | `device_trust_score` | Score de confianza del dispositivo. Valores bajos indican dispositivo nuevo, compartido, sospechoso o con baja reputacion. | Reduce o aumenta riesgo segun la confiabilidad del dispositivo. Puede activar `new_or_risky_device`. |
| `last_transaction_features` | `user_id` | `last_transaction_country` | Ultimo pais observado para una transaccion del usuario. | Se actualiza de forma asincrona para futuras predicciones. No se guarda para leerlo inmediatamente en la misma transaccion. |

## Conceptos claves

Online Store guarda el ultimo valor disponible por entidad. Es la fuente para inferencia online porque permite `GetRecord` de baja latencia. En este caso, una transaccion con `user_id=U123`, `card_id=C789`, `merchant_id=M999` y `device_id=D123` consulta features de usuario, tarjeta, comercio y dispositivo antes de invocar el modelo.

Offline Store guarda historico por `event_time`. Es la fuente correcta para batch prediction y retraining porque permite reconstruir que features existian al momento de una transaccion pasada. Esta propiedad es clave para evitar data leakage.

Un Feature Group no representa una tabla transaccional completa. Representa un conjunto de features con una entidad y una semantica comun. Por eso el usuario aparece en dos grupos distintos: `user_profile_features` para atributos lentos y `user_behavior_features` para agregaciones dinamicas.

La columna `event_time` no es decorativa. Para online indica la frescura del registro disponible. Para offline permite point-in-time joins: si una transaccion ocurrio a las 14:20, se debe usar el snapshot de features con `event_time <= 14:20`, no un valor calculado a las 15:00.

El laboratorio tambien escribe un `offline-export` en S3. SageMaker Batch Transform consume archivos S3; no consulta Online Store registro por registro. En produccion, ese export puede venir de Athena, Glue, SageMaker Processing o consultas sobre la tabla del Offline Store.

`last_transaction_features` muestra un patron valido de escritura directa a Online Store: guardar datos que seran utiles para futuras predicciones. No representa el patron incorrecto de guardar una current feature solo para leerla inmediatamente.

## Como se usa en los siguientes pasos

- Paso 05: el Fraud Scoring Service consulta Online Store para armar el vector online.
- Paso 06: el pipeline asincrono actualiza algunos Feature Groups para futuras transacciones.
- Paso 07: batch prediction usa exports de Offline Store y no hace lookups online fila por fila.
- Paso 08: retraining usa Offline Store con point-in-time joins y labels tardios.

## Prerrequisitos

- Haber ejecutado `fraud-step 01`.
- Haber ejecutado `fraud-step 02` para tener Data Lake y artifacts.
- Permisos para `sagemaker:CreateFeatureGroup`, `sagemaker:PutRecord`, `sagemaker:GetRecord` y S3.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 03
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.pipelines.curated_to_offline_features_aws
```

## Resultado esperado

Feature Store queda cargado con registros historicos y ultimos valores por entidad. Los exports offline quedan disponibles para los pasos batch y retraining.

## Validacion local

El comando imprime un JSON con `physical_feature_groups`, `record_counts`, `offline_exports_prefix` y artifacts.

## Validacion en consola AWS

Revisa en SageMaker Feature Store:

- Estado `Created`.
- Online Store habilitado.
- Offline Store apuntando a S3.
- Record identifier correcto para cada grupo.
- `event_time` como Event time feature.

Revisa en S3:

```text
<FRAUD_S3_PREFIX>/feature-store/offline-export/
<FRAUD_S3_PREFIX>/feature-store/offline-store/
```

Si `CreateFeatureGroup` falla con `s3:GetBucketAcl`, actualiza la infraestructura con:

```bash
python -m src.lab_runner fraud-step 01
```

Luego ejecuta otra vez:

```bash
python -m src.lab_runner fraud-step 03
```

El paso intenta eliminar y recrear Feature Groups que hayan quedado en `CreateFailed`.
