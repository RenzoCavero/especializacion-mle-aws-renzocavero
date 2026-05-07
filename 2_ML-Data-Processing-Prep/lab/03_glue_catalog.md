# 03 - Glue Data Catalog

Glue Data Catalog registra metadatos de las capas del data lake. Esto permite que los datasets sean descubribles por Glue, Athena, SageMaker y futuros pipelines.

El stack crea la base:

```text
ml_data_prep_lab
```

El laboratorio registra tablas como:

- `raw_customers`
- `raw_transactions`
- `raw_inference_transactions`
- `cleaned_customers`
- `cleaned_transactions`
- `curated_customer_transactions`
- `features_training`
- `features_inference`

Comando:

```bash
make catalog
```

## Que Hace `register_catalog`

El comando:

```bash
python -m src.register_catalog
```

registra o actualiza tablas externas en Glue Data Catalog apuntando a rutas S3.

No sube datos y no transforma archivos. Solo crea metadata: nombre de tabla, columnas, tipos, formato CSV y ubicacion S3.

Ejemplo conceptual:

```text
raw_transactions -> s3://<bucket>/raw/transactions.csv
features_training -> s3://<bucket>/features/training_dataset.csv
features_inference -> s3://<bucket>/inference/inference_dataset.csv
```

La operacion es idempotente:

- Si la tabla no existe, se crea.
- Si la tabla existe, se actualiza.

Esto permite ejecutar `make catalog` varias veces durante desarrollo.

## Diferencia Entre Upload Y Catalogo

`bash scripts/upload_sample_data.sh`:

- Genera CSV sinteticos.
- Sube datos a `s3://<bucket>/raw/`.
- Sube assets del Glue Job a `s3://<bucket>/scripts/`.
- No registra tablas Glue.

`python -m src.register_catalog`:

- Registra tablas Glue.
- No genera datos.
- No sube CSV.
- No ejecuta transformaciones.

## Validar Tablas Glue

```bash
aws glue get-databases --profile <profile> --region <region>
aws glue get-tables --database-name ml_data_prep_lab --profile <profile> --region <region>
```

Si no aparecen tablas, revisa:

- Que el stack CloudFormation haya creado la base Glue.
- Que `AWS_REGION` sea la misma region donde desplegaste.
- Que el usuario tenga permisos `glue:GetDatabase`, `glue:GetTable`, `glue:CreateTable` y `glue:UpdateTable`.
