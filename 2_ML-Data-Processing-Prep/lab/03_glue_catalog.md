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
bash scripts/lab.sh step 03
make catalog
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 step 03
python -m src.register_catalog
```

## Que Hace `register_catalog`

El comando:

```bash
python -m src.register_catalog
```

registra o actualiza tablas externas en Glue Data Catalog apuntando a rutas S3.

No genera datos y no transforma archivos. Su responsabilidad principal es crear metadata: nombre de tabla, columnas, tipos, formato CSV y ubicacion S3.

Ademas, si ya existen archivos CSV de una etapa, sincroniza una copia compatible con Athena bajo un prefijo tipo carpeta. Esto evita que Athena encuentre el esquema en Glue, pero no lea filas porque la tabla apunta a un objeto individual.

Ejemplo conceptual:

```text
raw_transactions -> Location: s3://<bucket>/raw/transactions/
features_training -> Location: s3://<bucket>/features/training_dataset/
features_inference -> Location: s3://<bucket>/inference/inference_dataset/
```

Los archivos originales siguen existiendo para lectura directa y compatibilidad con el laboratorio:

```text
s3://<bucket>/raw/transactions.csv
s3://<bucket>/features/training_dataset.csv
s3://<bucket>/inference/inference_dataset.csv
```

Las tablas Glue apuntan a copias bajo prefijos consultables por Athena:

```text
s3://<bucket>/raw/transactions/transactions.csv
s3://<bucket>/features/training_dataset/training_dataset.csv
s3://<bucket>/inference/inference_dataset/inference_dataset.csv
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
- No genera datos sinteticos.
- No transforma datasets.
- Si los CSV ya existen, sincroniza copias bajo prefijos de tabla para Athena.

## Validar Tablas Glue

```bash
aws glue get-databases --profile <profile> --region <region>
aws glue get-tables --database-name ml_data_prep_lab --profile <profile> --region <region>
```

## Rutas De Ejecucion

| Nivel | Ruta |
|---|---|
| Runner numerado | `scripts/lab.sh step 03` o `scripts/lab.ps1 step 03` |
| Target Make | `make catalog` |
| Modulo Python | `src.register_catalog` |
| Definicion de tablas | `src.glue_catalog.TABLES` |
| Servicio AWS | AWS Glue Data Catalog |

Si no aparecen tablas, revisa:

- Que el stack CloudFormation haya creado la base Glue.
- Que `AWS_REGION` sea la misma region donde desplegaste.
- Que el usuario tenga permisos `glue:GetDatabase`, `glue:GetTable`, `glue:CreateTable` y `glue:UpdateTable`.

## Validacion En AWS Console

1. Abre AWS Glue.
2. Ve a Data Catalog > Databases.
3. Entra a `ml_data_prep_lab`.
4. Abre `Tables`.
5. Verifica que aparezcan tablas como `raw_customers`, `raw_transactions`, `features_training` y `features_inference`.
6. Abre una tabla y revisa `Schema` y `Location`.
7. Confirma que `Location` apunta al bucket del laboratorio, por ejemplo `s3://<bucket>/features/training_dataset/`.

## Extensiones Nativas Relacionadas

Despues de ejecutar el pipeline principal puedes probar:

- Athena para consultar tablas catalogadas con SQL.
- Glue Crawler para descubrir esquemas desde S3.
- Glue Data Catalog Column Statistics para calcular estadisticas administradas.

Guia paso a paso:

```text
lab/10_athena_glue_native_features.md
```
