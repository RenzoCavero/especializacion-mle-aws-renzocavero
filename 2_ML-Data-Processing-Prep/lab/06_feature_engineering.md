# 06 - Feature Engineering

Las features convierten datos operacionales en senales para ML.

Ejemplos:

- `amount_log`
- `customer_txn_count`
- `customer_avg_amount`
- `amount_to_customer_avg`
- `high_risk_country`
- Indicadores por canal, segmento y categoria de comercio.

Comando:

```bash
make features
```

Outputs:

```text
s3://<bucket>/features/training_features.csv
s3://<bucket>/features/inference_features.csv
```

El dataset final de entrenamiento se genera en:

```text
s3://<bucket>/features/training_dataset.csv
```

## Que Datos Usa Feature Engineering

Las features se construyen desde la capa `curated/`, no directamente desde `raw/`.

Esto permite que la logica de features reciba datos ya:

- Limpios.
- Integrados entre clientes y transacciones.
- Con fechas normalizadas.
- Sin duplicados criticos.
- Con nulos tratados.

## Salidas De Features

El paso:

```bash
bash scripts/run_processing_job.sh features
```

genera:

```text
s3://<bucket>/features/training_features.csv
s3://<bucket>/features/inference_features.csv
```

El paso:

```bash
bash scripts/run_processing_job.sh training-dataset
```

genera:

```text
s3://<bucket>/features/training_dataset.csv
```

El paso:

```bash
bash scripts/run_processing_job.sh inference-dataset
```

genera:

```text
s3://<bucket>/inference/inference_dataset.csv
```

## Relacion Con SageMaker Feature Store

En este laboratorio, las features se guardan en S3 para mantener costos bajos y simplicidad. Conceptualmente, la capa `features/` cumple el rol de un offline feature store.

En un laboratorio futuro se puede extender hacia SageMaker Feature Store:

- `features/training_features.csv` podria poblar el offline store.
- `features/inference_features.csv` podria convertirse en datos de scoring batch.
- La misma definicion de columnas debe mantenerse para evitar training-serving skew.
