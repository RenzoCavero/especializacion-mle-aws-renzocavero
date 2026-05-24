# 02 - Data Lake En S3

Amazon S3 es el data lake del laboratorio.

Zonas:

- `raw/`: datos originales.
- `cleaned/`: datos corregidos.
- `curated/`: datos integrados y transformados.
- `features/`: features y dataset de entrenamiento.
- `inference/`: dataset para prediccion.
- `profiles/`: profiling.
- `quality/`: validaciones.
- `lineage/`: trazabilidad.
- `reports/`: dataset card.
- `logs/`: metadatos de ejecucion.

Comandos:

```bash
bash scripts/lab.sh step 02
make data
make upload-raw
aws s3 ls s3://<bucket-name>/raw/ --profile <profile> --region <region>
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 step 02
.\scripts\upload_sample_data.ps1
```

## Que Significa Cada Zona

| Zona | Proposito | Quien la escribe |
|---|---|---|
| `raw/` | Conserva los archivos originales, sin corregir. Es la fuente auditable del pipeline. | `src.upload_raw_data` |
| `cleaned/` | Guarda datos con nulos tratados, duplicados removidos y registros invalidos corregidos o filtrados. | Glue Job, paso `process` |
| `curated/` | Integra clientes y transacciones en tablas listas para analisis y features. | Glue Job, paso `process` |
| `features/` | Guarda variables numericas/categoricas listas para entrenamiento y el dataset supervisado final. | Glue Job, pasos `features` y `training-dataset` |
| `inference/` | Guarda dataset de scoring sin target. | Glue Job, paso `inference-dataset` |
| `profiles/` | Guarda resumen estadistico y estructura de datasets. | Glue Job, paso `profile` |
| `quality/` | Guarda resultado de reglas de calidad. | Glue Job, paso `quality` |
| `lineage/` | Guarda trazabilidad entre entradas, transformaciones y salidas. | Glue Job, paso `lineage` |
| `reports/` | Guarda dataset card en JSON y Markdown. | Glue Job, paso `dataset-card` |
| `logs/` | Guarda metadata funcional del pipeline, como `run_id` y pasos ejecutados. | Glue Job |

## Upload Raw Paso A Paso

Este comando:

```bash
bash scripts/upload_sample_data.sh
```

ejecuta:

```bash
python -m src.generate_sample_data
python -m src.upload_raw_data
```

Despues de ejecutarlo, deben existir:

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
s3://<bucket>/scripts/ml_data_prep_src.zip
s3://<bucket>/scripts/glue_pipeline.py
```

Nota: este script no ejecuta `python -m src.register_catalog`. La subida a `raw/` y el catalogo son etapas separadas.

## Rutas De Ejecucion

| Nivel | Ruta |
|---|---|
| Runner numerado | `scripts/lab.sh step 02` o `scripts/lab.ps1 step 02` |
| Script directo | `scripts/upload_sample_data.sh` o `scripts/upload_sample_data.ps1` |
| Modulos Python | `src.generate_sample_data`, `src.upload_raw_data`, `src.package_job_assets` |
| Codigo subido a Glue | `s3://<bucket>/scripts/glue_pipeline.py`, `s3://<bucket>/scripts/ml_data_prep_src.zip` |
| Datos locales | `data/sample/customers.csv`, `data/sample/transactions.csv`, `data/sample/inference_transactions.csv` |
| Datos S3 | `s3://<bucket>/raw/` |

## Validar La Capa Raw

```bash
aws s3 ls s3://<bucket-name>/raw/ --profile <profile> --region <region>
aws s3 ls s3://<bucket-name>/scripts/ --profile <profile> --region <region>
```

Si `raw/` no existe o esta vacio, revisa:

- Que la infraestructura este desplegada.
- Que `.env` tenga `AWS_PROFILE`, `AWS_REGION` y, si aplica, `S3_BUCKET_NAME`.
- Que tu profile tenga permisos `s3:PutObject`, `s3:GetObject` y `s3:ListBucket`.

## Validacion En AWS Console

1. Abre Amazon S3.
2. Entra al bucket generado por CloudFormation.
3. Revisa el prefijo `raw/`.
4. Confirma que existen `customers.csv`, `transactions.csv` e `inference_transactions.csv`.
5. Revisa el prefijo `scripts/`.
6. Confirma que existen `glue_pipeline.py` y `ml_data_prep_src.zip`.
7. Verifica que los archivos tengan tamano mayor a cero.
