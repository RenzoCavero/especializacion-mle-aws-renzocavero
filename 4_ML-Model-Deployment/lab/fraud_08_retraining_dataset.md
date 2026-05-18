# Fraud 08 - Retraining dataset

## Objetivo

Construir un dataset supervisado de retraining usando transacciones historicas, labels tardios y features point-in-time desde Offline Store/export S3.

## Que vas a construir o validar

Este paso valida:

- Lectura de transacciones historicas curadas.
- Lectura de labels de fraude.
- Point-in-time joins con features historicas.
- Union de labels posteriores a la transaccion.
- Escritura de dataset supervisado en S3.

## Input del paso

Transacciones historicas:

```csv
transaction_id,event_time,user_id,card_id,merchant_id,device_id,amount
T001,2026-05-17T14:20:00Z,U123,C789,M999,D123,500.0
```

Labels:

```csv
transaction_id,label,label_source,label_event_time
T001,1,chargeback,2026-05-20T10:00:00Z
```

## Output esperado del paso

Dataset:

```text
s3://<bucket>/<prefix>/retraining/training_dataset.csv
```

## Conceptos claves

En fraude, el label suele llegar despues de la transaccion. Puede venir de chargeback, disputa del cliente, revision manual o investigacion posterior. Por eso el dataset de entrenamiento une features disponibles al momento de la transaccion con labels observados dias despues.

El punto critico es evitar data leakage. Si una transaccion ocurrio a las 14:20, no se pueden usar features calculadas a las 15:00. El modelo entrenaria con informacion que no existia en produccion y luego fallaria al desplegarse.

Offline Store permite reconstruir el estado historico de features. El point-in-time join selecciona la version mas reciente antes o igual al timestamp de la transaccion.

El dataset de retraining debe respetar el mismo `feature_order.json` usado por online y batch. Esto mantiene consistencia entre entrenamiento, batch inference y real-time inference.

## Prerrequisitos

- Haber ejecutado `fraud-step 02`.
- Haber ejecutado `fraud-step 03`.
- Labels disponibles en `lake/curated/fraud_labels.csv`.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 08
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.pipelines.build_retraining_dataset_aws
```

## Resultado esperado

Se genera `training_dataset.csv` con `transaction_id`, `event_time`, todas las features del contrato y columnas de label.

## Validacion local

El stdout imprime la URI de `training_dataset`.

## Validacion en consola AWS

En S3 revisa:

```text
<FRAUD_S3_PREFIX>/retraining/training_dataset.csv
```

Confirma que contiene:

- `label`
- `label_source`
- `label_event_time`
- features del contrato
- `transaction_id`

