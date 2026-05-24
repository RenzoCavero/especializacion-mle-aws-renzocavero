# Fraud 06 - Async update con SQS, S3 y Feature Store

## Objetivo

Procesar eventos posteriores a la prediccion online para actualizar el Data Lake y publicar features que serviran a predicciones futuras.

Este paso demuestra por que la arquitectura online no debe cargar con todo el trabajo analitico. La respuesta al cliente ocurre en el paso 05; el mantenimiento del estado historico ocurre despues, desacoplado por SQS.

## Que vas a construir o validar

Este paso valida:

- Lectura de mensajes desde SQS.
- Escritura asincrona en S3 raw, cleaned y curated.
- Actualizacion de Feature Store Online Store.
- Actualizacion de Offline Store/export S3.
- Eliminacion segura del mensaje procesado.

## Input del paso

Mensaje SQS producido por `fraud-step 05`:

```json
{
  "event_type": "fraud_prediction_completed",
  "raw_event": {},
  "cleaned_event": {},
  "prediction_event": {},
  "trace_uris": {}
}
```

El mensaje representa que la prediccion online ya termino. Incluye la transaccion original, la version limpia, la decision y las rutas de trazabilidad en S3.

## Output esperado del paso

Resumen:

```json
{
  "processed_events": 1
}
```

Objetos S3:

```text
lake/raw/async-transactions/
lake/cleaned/async-transactions/
lake/curated/async-transactions/
events/async_update_summary.json
```

Feature Groups actualizados:

- `user_behavior_features`
- `card_velocity_features`
- `last_transaction_features`

## Flujo de la cola SQS

El flujo completo es:

```text
fraud-step 05
  -> predice online
  -> guarda trazas en S3
  -> guarda decision en DynamoDB
  -> envia mensaje a SQS

fraud-step 06
  -> lee mensaje desde SQS
  -> procesa evento
  -> escribe raw/cleaned/curated asincrono en S3
  -> actualiza Feature Store Online y Offline
  -> elimina mensaje de SQS solo si termino correctamente
```

SQS cumple cuatro funciones arquitectonicas:

| Funcion | Que significa en el laboratorio |
| --- | --- |
| Desacoplamiento | El endpoint online no espera a que se recalculen features ni a que se escriban todas las capas analiticas. |
| Buffer | Si el pipeline asincrono esta detenido, los eventos quedan pendientes en la cola. |
| Reintento | Si el procesamiento falla antes de borrar el mensaje, SQS puede volver a exponerlo despues del visibility timeout. |
| Control operacional | Permite observar mensajes disponibles, mensajes en vuelo y atrasos del procesamiento. |

SQS no reemplaza al Data Lake. La cola transporta eventos pendientes de procesamiento; S3 conserva la historia auditable.

## Conceptos claves

La prediccion online debe ser rapida. No conviene que el cliente espere recargas de Feature Store, recalculo de ventanas o escrituras analiticas completas. Por eso el paso 05 emite un evento y el paso 06 lo procesa despues.

El pipeline asincrono actualiza features para futuras predicciones. Por ejemplo, despues de puntuar `T001`, puede incrementar `user_txn_count_1h`, `card_txn_count_5m` y registrar `last_transaction_country`. Esa actualizacion no afecta la prediccion de `T001`, pero si puede afectar una transaccion `T002` que llegue despues.

El orden temporal importa. Si `T001` llega a las 14:20, el score de `T001` usa las features disponibles antes o hasta ese momento. Luego, a las 14:20:05, el pipeline actualiza Feature Store. Si `T002` llega a las 14:21, ya puede ver esas features actualizadas.

No todas las features deben actualizarse en este proceso simple. Features de ventana compleja como `device_users_count_7d`, `countries_count_24h` o agregaciones multi-entidad normalmente se calculan con streaming, batch incremental o jobs especializados. El laboratorio usa agregaciones simples para mostrar el patron sin esconder la arquitectura.

El borrado del mensaje debe ocurrir al final. Si se elimina de SQS antes de escribir S3 o Feature Store, un fallo podria perder el evento. Por eso el flujo correcto es procesar, persistir y luego borrar.

La idempotencia es una preocupacion real. En produccion, el mismo `transaction_id` y `request_id` deberian permitir detectar duplicados si SQS reentrega un mensaje. El laboratorio conserva esos identificadores en trazas y decisiones para mostrar ese principio.

Una DLQ no esta implementada por defecto en el flujo didactico, pero en produccion se agregaria una dead-letter queue para mensajes que fallan repetidamente.

## Ejemplo temporal

```text
14:20:00 - T001 llega al Fraud Scoring Service.
14:20:00 - Se calculan current features en memoria.
14:20:00 - Se consultan historical/entity features desde Online Store.
14:20:01 - Se devuelve decision al cliente.
14:20:01 - Se envia evento a SQS.
14:20:05 - Async update procesa el mensaje.
14:20:05 - Se actualizan Data Lake y Feature Store.
14:21:00 - T002 llega y puede ver features actualizadas por T001.
```

## Prerrequisitos

- Haber ejecutado `fraud-step 05`.
- Cola SQS con mensaje pendiente.
- Feature Groups creados y cargados.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 06
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.pipelines.async_update_online_features_aws
```

## Resultado esperado

El mensaje SQS se procesa y se elimina. Online Store queda actualizado con nuevas features simples para usuario/tarjeta y `last_transaction_features`. El export offline en S3 queda actualizado para batch/retraining.

## Validacion local

El stdout debe mostrar `processed_events` mayor o igual a 1 si habia mensajes pendientes.

Si muestra `0`, normalmente significa que:

- No se ejecuto `fraud-step 05`.
- El mensaje ya fue procesado.
- La cola configurada en `.env.cloud` no corresponde al stack actual.

## Validacion en consola AWS

Revisa:

- SQS: la cola queda sin mensajes visibles despues del procesamiento.
- S3: existe `events/async_update_summary.json`.
- S3: existen objetos bajo `lake/raw/async-transactions/`, `lake/cleaned/async-transactions/` y `lake/curated/async-transactions/`.
- SageMaker Feature Store: `user_behavior_features`, `card_velocity_features` o `last_transaction_features` tienen registros recientes con `event_time` de la transaccion.

Para corroborar SQS en consola:

1. Abre Amazon SQS.
2. Busca la cola `FRAUD_EVENT_QUEUE_NAME`.
3. Antes del paso 06, revisa `Messages available`.
4. Ejecuta el paso 06.
5. Refresca la cola y confirma que `Messages available` vuelve a 0 si el mensaje fue procesado.
