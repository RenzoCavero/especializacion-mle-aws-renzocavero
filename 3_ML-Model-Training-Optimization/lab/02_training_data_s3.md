# 02 - Datos de entrenamiento en Amazon S3

## Objetivo

Generar un dataset sintetico de churn y subirlo a Amazon S3 para que SageMaker pueda usarlo en Feature Store y Processing Jobs.

## Que vas a construir o validar

Vas a crear dos archivos locales y dos objetos S3.

| Tipo | Ruta | Uso |
|---|---|---|
| Local | `data/local_cache/churn_raw.csv` | Dataset completo sintetico. |
| Local | `data/sample/churn_sample.csv` | Muestra de 25 filas para inspeccion rapida. |
| S3 | `s3://<S3_BUCKET>/raw/churn_raw.csv` | Copia raw del dataset. |
| S3 | `s3://<S3_BUCKET>/processing/input/churn_features.csv` | Snapshot que usara SageMaker Processing. |

## Conceptos clave

- Dataset raw: datos originales generados antes de transformaciones de entrenamiento.
- Snapshot de features: copia estable que Processing usara como entrada.
- S3 prefix: ruta logica dentro del bucket, por ejemplo `raw/` o `processing/input/`.

## Prerrequisitos

1. Ejecuta los comandos desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Deben existir `.env` y `.env.cloud`.

3. `.env.cloud` debe contener `S3_BUCKET_NAME` y `SAGEMAKER_EXECUTION_ROLE_ARN`.

4. El profile AWS debe poder escribir en el bucket.

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
```

Internamente:

1. `src.generate_sample_data` genera 1200 filas por defecto con semilla `42`.
2. `src.upload_raw_data` sube el CSV a S3 en `raw/` y `processing/input/`.
3. `src.upload_raw_data` actualiza `artifacts/local_outputs/run_state.json`.

## Resultado esperado

La terminal debe mostrar:

- Cantidad de filas generadas.
- Ruta local de `churn_raw.csv`.
- Ruta local de `churn_sample.csv`.
- Tasa sintetica de churn.
- Upload a `s3://<S3_BUCKET>/raw/churn_raw.csv`.
- Upload a `s3://<S3_BUCKET>/processing/input/churn_features.csv`.

El dataset contiene columnas como:

- `customer_id`.
- `event_time`.
- `age_days`.
- `plan_type`.
- `country`.
- `device_type`.
- `sessions_last_7d`.
- `sessions_last_30d`.
- `avg_session_duration_last_30d`.
- `support_tickets_last_30d`.
- `payment_failures_last_90d`.
- `days_since_last_login`.
- `engagement_score`.
- `churn_label`.

## Validacion local

1. Abre `data/sample/churn_sample.csv`.
2. Confirma que tiene encabezados y filas.
3. Abre `artifacts/local_outputs/run_state.json`.
4. Verifica que aparezcan:

   ```text
   raw_data_s3_uri
   feature_snapshot_s3_uri
   ```

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon S3.
3. Entra al bucket indicado por `S3_BUCKET_NAME` en `.env.cloud`.
4. Abre el prefijo `raw/`.
5. Verifica que exista `churn_raw.csv` y que tenga tamano mayor a cero.
6. Abre el prefijo `processing/input/`.
7. Verifica que exista `churn_features.csv` y que tenga tamano mayor a cero.
8. Abre `Properties` de cada objeto y confirma cifrado.
9. Abre `Permissions` y confirma que el objeto no es publico.

## Validacion opcional por CLI

```bash
aws s3 ls s3://<S3_BUCKET>/raw/ --profile <AWS_PROFILE> --region <AWS_REGION>
aws s3 ls s3://<S3_BUCKET>/processing/input/ --profile <AWS_PROFILE> --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `Missing required AWS configuration: S3_BUCKET_NAME` | No corriste el paso 01 o `.env.cloud` no existe. | Ejecuta `make lab-01-aws-setup`. |
| `FileNotFoundError` en upload | No se genero `churn_raw.csv`. | Ejecuta `python -m src.generate_sample_data`. |
| `AccessDenied` al subir a S3 | El profile o rol no tiene permisos sobre el bucket. | Revisa permisos del stack y profile AWS. |
| No ves objetos en S3 | Estas en otra region o bucket. | Confirma `AWS_REGION` y `S3_BUCKET_NAME`. |
