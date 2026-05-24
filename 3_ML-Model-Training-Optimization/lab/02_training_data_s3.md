# 02 - Datos de entrenamiento en Amazon S3

## Objetivo

Generar un dataset sintetico de churn y organizarlo en zonas de datos en Amazon S3. Este paso prepara la base para una arquitectura mas cercana a produccion:

```text
local dummy data -> raw/ -> cleaned/ -> curated/
```

La zona `curated/` sera la entrada del Processing Job que actualiza SageMaker Feature Store en el paso 03.

## Que vas a construir o validar

| Tipo | Ruta | Uso |
|---|---|---|
| Local | `data/local_cache/churn_raw.csv` | Dataset sintetico completo. |
| Local | `data/sample/churn_sample.csv` | Muestra de 25 filas para inspeccion rapida. |
| Local | `data/local_cache/churn_cleaned.csv` | Dataset validado y tipado. |
| Local | `data/local_cache/churn_features_curated.csv` | Features curadas listas para Feature Store. |
| Local | `artifacts/local_outputs/feature_lineage.json` | Metadata de linaje raw-cleaned-curated-feature-store. |
| S3 | `s3://<S3_BUCKET>/raw/churn_raw.csv` | Copia raw del dataset. |
| S3 | `s3://<S3_BUCKET>/cleaned/churn_cleaned.csv` | Datos limpios. |
| S3 | `s3://<S3_BUCKET>/curated/churn_features.csv` | Features curadas que se ingieren a Feature Store. |
| S3 | `s3://<S3_BUCKET>/processing/input/churn_features.csv` | Snapshot de fallback para Processing. |
| S3 | `s3://<S3_BUCKET>/lineage/feature_lineage.json` | Linaje de fuentes y transformaciones. |

## Conceptos clave

- Raw: datos originales, sin transformaciones de negocio.
- Cleaned: datos validados, con tipos consistentes y registros duplicados removidos.
- Curated: datos listos para consumo por ML, con transformaciones de feature engineering aplicadas.
- Feature lineage: metadata que explica de donde salieron las features y que transformaciones se aplicaron.
- Snapshot de fallback: copia curada que el paso 04 puede usar si el Offline Store aun no escribio filas.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa el paso 01 para crear el bucket y el rol de SageMaker.
3. Confirma que existen `.env` y `.env.cloud`.
4. `.env.cloud` debe contener `S3_BUCKET_NAME` y `SAGEMAKER_EXECUTION_ROLE_ARN`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-02-training-data
```

Con Bash o Git Bash:

```bash
bash scripts/upload_training_data.sh
```

En Windows PowerShell:

```powershell
.\scripts\upload_training_data.ps1
```

Con Python, paso a paso:

```bash
python -m src.generate_sample_data
python -m src.upload_raw_data
python -m src.prepare_feature_sources
```

Internamente:

1. `src.generate_sample_data` genera 1200 filas sinteticas con semilla `42`.
2. `src.upload_raw_data` sube `churn_raw.csv` a `s3://<S3_BUCKET>/raw/`.
3. `src.prepare_feature_sources` lee el raw local, crea `cleaned/` y `curated/`, sube ambos a S3 y escribe `feature_lineage.json`.

Para controlar costo y tiempo de clase, la conversion `raw -> cleaned -> curated` se ejecuta localmente y escribe los resultados en S3. En una plataforma productiva, esa conversion normalmente seria otro job de datos, por ejemplo AWS Glue, EMR, Spark, dbt, Step Functions o un SageMaker Processing Job dedicado.

## Scripts usados

| Accion | Script local | Modulo Python |
|---|---|---|
| Generar dataset | `scripts/upload_training_data.sh` / `.ps1` | `src/generate_sample_data.py` |
| Subir raw a S3 | `scripts/upload_training_data.sh` / `.ps1` | `src/upload_raw_data.py` |
| Crear cleaned/curated | `scripts/upload_training_data.sh` / `.ps1` | `src/prepare_feature_sources.py` |
| Transformaciones compartidas | No aplica | `src/feature_pipeline.py` |

## Parametros y logica que puedes cambiar

| Necesidad | Archivo |
|---|---|
| Cambiar distribucion o cantidad de datos dummy | `src/generate_sample_data.py` |
| Cambiar columnas esperadas o tipos de features | `src/feature_schema.py` |
| Cambiar reglas `raw -> cleaned -> curated` | `src/feature_pipeline.py` |
| Cambiar rutas S3 como `raw/`, `cleaned/`, `curated/` | `src/config.py` |
| Cambiar wrapper de carga | `scripts/upload_training_data.sh`, `scripts/upload_training_data.ps1` |
| Ver inputs/outputs de todo el lab | `lab/14_workflow_and_scripts_reference.md` |

## Resultado esperado

La terminal debe mostrar:

- Cantidad de filas generadas.
- Ruta local de `churn_raw.csv`.
- Upload a `s3://<S3_BUCKET>/raw/churn_raw.csv`.
- Upload a `s3://<S3_BUCKET>/cleaned/churn_cleaned.csv`.
- Upload a `s3://<S3_BUCKET>/curated/churn_features.csv`.
- Upload a `s3://<S3_BUCKET>/processing/input/churn_features.csv`.
- Escritura de `feature_lineage.json` local y remoto.

## Validacion local

1. Abre `data/sample/churn_sample.csv`.
2. Abre `data/local_cache/churn_cleaned.csv`.
3. Abre `data/local_cache/churn_features_curated.csv`.
4. Abre `artifacts/local_outputs/feature_lineage.json`.
5. Confirma que `run_state.json` contenga:

   ```text
   raw_data_s3_uri
   cleaned_data_s3_uri
   curated_features_s3_uri
   feature_snapshot_s3_uri
   feature_lineage_s3_uri
   ```

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon S3.
3. Entra al bucket indicado por `S3_BUCKET_NAME`.
4. Revisa el prefijo `raw/` y confirma `churn_raw.csv`.
5. Revisa el prefijo `cleaned/` y confirma `churn_cleaned.csv`.
6. Revisa el prefijo `curated/` y confirma `churn_features.csv`.
7. Revisa el prefijo `lineage/` y confirma `feature_lineage.json`.
8. Revisa el prefijo `processing/input/` y confirma `churn_features.csv`.
9. Verifica que los objetos tengan tamano mayor a cero y no sean publicos.

## Validacion opcional por CLI

```bash
aws s3 ls s3://<S3_BUCKET>/raw/ --profile <AWS_PROFILE> --region <AWS_REGION>
aws s3 ls s3://<S3_BUCKET>/cleaned/ --profile <AWS_PROFILE> --region <AWS_REGION>
aws s3 ls s3://<S3_BUCKET>/curated/ --profile <AWS_PROFILE> --region <AWS_REGION>
aws s3 ls s3://<S3_BUCKET>/lineage/ --profile <AWS_PROFILE> --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `Missing required AWS configuration: S3_BUCKET_NAME` | No corriste el paso 01 o `.env.cloud` no existe. | Ejecuta `make lab-01-aws-setup`. |
| `FileNotFoundError` en upload | No se genero `churn_raw.csv`. | Ejecuta `python -m src.generate_sample_data`. |
| `AccessDenied` al subir a S3 | El profile no tiene permisos sobre el bucket. | Revisa el profile AWS y el stack CloudFormation. |
| No ves objetos en S3 | Estas en otra region o bucket. | Confirma `AWS_REGION` y `S3_BUCKET_NAME`. |
| `ValueError` por columnas faltantes | El CSV raw fue modificado manualmente. | Regenera el dataset con `python -m src.generate_sample_data`. |
