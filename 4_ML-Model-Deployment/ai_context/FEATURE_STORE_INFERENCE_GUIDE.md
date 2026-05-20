# Feature Store Inference Guide

Este documento define como usar SageMaker Feature Store en inferencia batch y real-time dentro del laboratorio 4.

## Offline Store para batch inference

Feature Store Offline Store es una fuente natural para batch inference porque contiene historicos de features en S3. El laboratorio debe usarla en `integrated_mode` cuando `OFFLINE_STORE_S3_URI` este disponible y debe crearla en `standalone_mode` cuando no exista un Feature Group previo.

Buenas practicas:

- Leer solo columnas necesarias para inferencia y trazabilidad.
- Excluir `target_column`.
- Conservar `batch_identifier_column`.
- Generar batch input versionado en S3.
- Registrar fecha de extraccion, feature group y contrato usado.

## Online Store para real-time inference

Feature Store Online Store se usa para obtener features actualizadas de baja latencia antes de invocar el endpoint. El laboratorio debe consultar Online Store con `GetRecord` cuando `FEATURE_GROUP_NAME` y `realtime_lookup_key` esten disponibles.

Buenas practicas:

- Validar que el record existe.
- Validar tipos y columnas devueltas.
- Construir el payload solo con `inference_features`.
- No enviar target ni metadata innecesaria al endpoint.
- Registrar `request_id` y lookup key para trazabilidad.

## Diferencia entre features batch y online

Las features batch suelen venir de historicos consolidados y pueden cubrir grandes ventanas de datos. Las features online deben estar disponibles rapidamente, con valores actualizados y consistentes con las usadas en entrenamiento.

El laboratorio debe ensenar que batch y online pueden tener fuentes distintas, pero deben respetar el mismo contrato semantico para evitar training-serving skew.

## Record identifier y event time

- `record_identifier_name`: clave primaria del registro en Feature Store.
- `event_time_feature_name`: timestamp del evento o vigencia del registro.

Estos campos son necesarios para ordenar, versionar y auditar datos de features.

## Evitar training-serving skew

Para reducir skew:

- Usar el mismo feature contract para entrenamiento e inferencia.
- Validar nombres, orden y tipos de columnas.
- No incluir el target en inferencia.
- Versionar transformaciones de features.
- Registrar feature group, modelo y fecha de extraccion.
- Probar payloads batch y online contra el mismo validador.

## Validar contrato de features

El contrato debe declarar:

- Features usadas para entrenamiento.
- Features permitidas en inferencia.
- Target.
- Identificadores.
- Fuentes S3 y Feature Store.
- Modelo o Model Package asociado.

Validaciones minimas:

- Todas las `inference_features` existen.
- No hay columnas desconocidas si el modo estricto esta activo.
- `target_column` no se envia al endpoint.
- Tipos esperados coinciden.
- El orden de features coincide con el modelo si el contenedor lo requiere.

## Consulta Online Store con GetRecord

La implementacion futura debe usar el cliente `sagemaker-featurestore-runtime` de boto3:

```python
client.get_record(
    FeatureGroupName=feature_group_name,
    RecordIdentifierValueAsString=record_id,
)
```

Luego debe convertir la lista de features devuelta por AWS a un diccionario tipado y validado.

En el caso de fraude cloud, `fraud_lab.aws.feature_store.AwsFeatureStore` consulta varios Feature Groups:

- `user_profile_features` por `user_id`.
- `user_behavior_features` por `user_id`.
- `card_velocity_features` por `card_id`.
- `merchant_risk_features` por `merchant_id`.
- `device_features` por `device_id`.

El Fraud Scoring Service calcula en memoria las features de la transaccion actual y solo usa Online Store para features historicas o de entidad.

## Preparar batch input desde Offline Store

La implementacion futura debe:

1. Leer datos desde `OFFLINE_STORE_S3_URI` o una ruta derivada.
2. Seleccionar registros relevantes.
3. Remover target y columnas prohibidas.
4. Conservar ID original en un archivo de manifest o columna de trazabilidad.
5. Escribir input batch en S3.
6. Registrar el contrato usado.

En el caso de fraude cloud, `fraud-batch-predict-aws` lee `lake/curated/transactions_to_score.csv` desde S3 y usa `feature-store/offline-export/<feature_group>/features.csv` para hacer point-in-time joins. Ese export representa la preparacion que en produccion podria ejecutarse con Athena, Glue o SageMaker Processing sobre el Offline Store.

## Metadata esperada del laboratorio 3

- `feature_group_name`
- `record_identifier_name`
- `event_time_feature_name`
- `training_features`
- `inference_features`
- `target_column`
- `batch_identifier_column`
- `realtime_lookup_key`
- `offline_store_s3_uri`
- `model_package_group_name`
- `model_artifact_s3_uri`

## Si Feature Store no existe

En `standalone_mode`, si Feature Store no existe, el laboratorio debe crear un Feature Group con Online Store y Offline Store. Para mantener la ejecucion deterministica, tambien debe materializar un export batch-ready en S3 desde los mismos registros transformados que se cargan al Feature Group.

- Usar dataset sintetico.
- Crear feature contract minimo.
- Aplicar `src/feature_transformations.py` como transformacion comun.
- Cargar registros con `PutRecord` hacia Online Store y Offline Store.
- Usar el export Offline Store/S3 como fuente del Batch Transform Job.
- Usar `GetRecord` contra Online Store para real-time.
- No enviar target al endpoint.

## Contrato esperado

```yaml
feature_group_name: ""
record_identifier_name: "customer_id"
event_time_feature_name: "event_time"
training_features: []
inference_features: []
target_column: "target"
batch_identifier_column: "customer_id"
realtime_lookup_key: "customer_id"
offline_store_s3_uri: ""
model_package_group_name: ""
model_artifact_s3_uri: ""
```

## Reglas obligatorias

- La columna target no debe enviarse al endpoint.
- El payload real-time debe contener solo features de inferencia.
- El batch output debe conservar el identificador original.
- El endpoint debe devolver `score` y `decision`.
- Los resultados deben ser trazables.
