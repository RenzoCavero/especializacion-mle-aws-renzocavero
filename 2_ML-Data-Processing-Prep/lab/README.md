# Guia Del Laboratorio

Este laboratorio ensena la etapa de datos del ciclo de vida ML en AWS: desde datos crudos hasta features y datasets listos para entrenamiento e inferencia.

El caso practico es un pipeline de datos para deteccion de fraude o scoring de riesgo. La ejecucion es cloud-first: los datos se almacenan en Amazon S3, la metadata se registra en AWS Glue Data Catalog y el procesamiento principal corre en AWS Glue Python Shell Job.

## Orden Sugerido De Lectura

| Orden | Documento | Que explica | Comandos relacionados |
|---|---|---|---|
| 1 | `00_contexto_negocio.md` | Problema de negocio, fuentes sinteticas y resultado esperado. | `python -m src.generate_sample_data` |
| 2 | `01_aws_setup.md` | Prerrequisitos, AWS profile o SSO, permisos IAM y variables `.env`. | `aws sts get-caller-identity`, `bash scripts/deploy_infra.sh` |
| 3 | `02_data_lake_s3.md` | Estructura del data lake en S3 y zonas `raw`, `cleaned`, `curated`, `features`, `inference`. | `bash scripts/upload_sample_data.sh` |
| 4 | `03_glue_catalog.md` | Registro de tablas en Glue Data Catalog. | `python -m src.register_catalog`, `make catalog` |
| 5 | `04_data_quality_profiling.md` | Profiling, reglas de calidad y outputs de validacion. | `bash scripts/run_processing_job.sh profile`, `bash scripts/run_processing_job.sh quality` |
| 6 | `05_processing_jobs.md` | Ejecucion cloud con AWS Glue Python Shell Job. | `bash scripts/run_processing_job.sh all` |
| 7 | `06_feature_engineering.md` | Construccion de features para entrenamiento e inferencia. | `bash scripts/run_processing_job.sh features` |
| 8 | `07_training_serving_consistency.md` | Reutilizacion de logica para evitar training-serving skew. | `bash scripts/run_processing_job.sh training-dataset`, `bash scripts/run_processing_job.sh inference-dataset` |
| 9 | `08_governance_lineage.md` | Lineage, dataset card y documentacion de artefactos. | `bash scripts/run_processing_job.sh lineage`, `bash scripts/run_processing_job.sh dataset-card` |
| 10 | `09_cost_security_cleanup.md` | Costos, seguridad, revision de recursos activos y cleanup. | `bash scripts/destroy_infra.sh` |
| 11 | `10_athena_glue_native_features.md` | Ejemplo de Athena en consola, Glue Crawler, Glue Data Quality y Glue Column Statistics. | `make aws-native-extras`, `bash scripts/run_glue_crawler.sh`, `bash scripts/run_glue_data_quality.sh`, `bash scripts/run_glue_column_statistics.sh` |

## Formas De Ejecutar El Laboratorio

Hay tres formas equivalentes de ejecutar el laboratorio:

| Forma | Uso recomendado |
|---|---|
| `make` | Opcion mas simple para Linux, macOS o Git Bash si `make` esta disponible. |
| `scripts/*.sh` | Opcion clara para ejecutar por bloques desde Bash o Git Bash. |
| `python -m src.<modulo>` | Opcion mas explicita para debug o aprendizaje paso a paso. |

La guia detallada de scripts esta en:

```text
scripts/README.md
```

## Ejecucion Completa

Con Make:

```bash
make all-cloud
```

Con scripts Bash:

```bash
bash scripts/run_all_cloud.sh
```

Ambos flujos ejecutan:

```bash
python -m src.deploy_infra
python -m src.generate_sample_data
python -m src.upload_raw_data
python -m src.register_catalog
python -m src.run_processing_job --steps all
python -m src.download_reports
python -m src.validate_outputs
```

## Ejecucion Paso A Paso

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
bash scripts/download_reports.sh
python -m src.validate_outputs
```

Cleanup:

```bash
bash scripts/destroy_infra.sh
```

## Secuencia Recomendada Para Clase

Para ensenar el laboratorio con el modelo mental de data lake en AWS, usa esta secuencia:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_glue_crawler.sh
bash scripts/run_processing_job.sh all
bash scripts/run_glue_data_quality.sh
bash scripts/run_glue_column_statistics.sh
bash scripts/download_reports.sh
python -m src.validate_outputs
```

Al finalizar la clase:

```bash
bash scripts/destroy_infra.sh
```

Lectura conceptual de la secuencia:

| Momento | Comando | Concepto AWS |
|---|---|---|
| 1 | `deploy_infra.sh` | Crea infraestructura reproducible con CloudFormation. |
| 2 | `upload_sample_data.sh` | Publica datos crudos en Amazon S3 `raw/`. |
| 3 | `register_catalog` | Registra tablas conocidas en Glue Data Catalog. |
| 4 | `run_glue_crawler.sh` | Muestra descubrimiento automatico de esquemas con Glue Crawler. |
| 5 | `run_processing_job.sh all` | Ejecuta profiling, calidad Python, limpieza, curacion, features, lineage y dataset card en Glue. |
| 6 | `run_glue_data_quality.sh` | Ejecuta reglas administradas de Glue Data Quality sobre `features_training`. |
| 7 | `run_glue_column_statistics.sh` | Calcula estadisticas administradas de columnas en Glue Catalog. |
| 8 | `download_reports.sh` | Descarga reportes generados en S3. |
| 9 | `validate_outputs` | Verifica objetos S3 y tablas Glue esperadas. |

Nota importante: en una arquitectura productiva, Glue Data Quality puede ejecutarse antes de transformar datos raw y tambien despues de publicar datasets curados o features. En este laboratorio hay dos capas de calidad: reglas Python dentro del Glue Job antes de escribir datasets finales y Glue Data Quality como demo administrado sobre `features_training`.

## Nota Importante Sobre `upload_sample_data.sh`

Este comando:

```bash
bash scripts/upload_sample_data.sh
```

solo ejecuta:

```bash
python -m src.generate_sample_data
python -m src.upload_raw_data
```

No ejecuta `python -m src.register_catalog`.

La razon es que `upload_sample_data.sh` representa la etapa de data lake raw: crear archivos sinteticos y subirlos a `s3://<bucket>/raw/`. El catalogo es una etapa diferente del laboratorio y se ejecuta con:

```bash
python -m src.register_catalog
```

o:

```bash
make catalog
```

Tambien se ejecuta automaticamente dentro de `bash scripts/run_all_cloud.sh`.

## Outputs Esperados

Al finalizar `make all-cloud` o `bash scripts/run_all_cloud.sh`, deben existir:

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
s3://<bucket>/profiles/profile.json
s3://<bucket>/quality/quality_report.json
s3://<bucket>/cleaned/customers.csv
s3://<bucket>/cleaned/transactions.csv
s3://<bucket>/curated/customer_transactions.csv
s3://<bucket>/features/training_features.csv
s3://<bucket>/features/inference_features.csv
s3://<bucket>/features/training_dataset.csv
s3://<bucket>/inference/inference_dataset.csv
s3://<bucket>/lineage/lineage.json
s3://<bucket>/lineage/lineage.md
s3://<bucket>/reports/dataset_card.json
s3://<bucket>/reports/dataset_card.md
s3://<bucket>/logs/pipeline_run.json
```

Tambien debe existir metadata en Glue Data Catalog para las tablas definidas en `lab/03_glue_catalog.md`.

## Extras AWS Nativos Opcionales

Despues de ejecutar el pipeline principal puedes activar ejemplos administrados de AWS:

```bash
make aws-native-extras
```

Ese target ejecuta:

```bash
python -m src.run_glue_crawler
python -m src.run_glue_data_quality
python -m src.run_glue_column_statistics
```

Estos extras muestran como consultar tablas con Athena, como descubrir esquemas con Glue Crawler, como ejecutar reglas basicas con Glue Data Quality y como calcular estadisticas de columnas en Glue Data Catalog. No forman parte de `make all-cloud` para mantener bajo el costo y que el estudiante decida cuando ejecutar recursos adicionales.

La guia paso a paso esta en:

```text
lab/10_athena_glue_native_features.md
```

## Regla De Costo

Para una ejecucion normal usa:

```bash
bash scripts/run_processing_job.sh all
```

Esto lanza un solo Glue Job. Ejecutar `profile`, `quality`, `process`, `features` y otros pasos por separado es util para aprendizaje o debug, pero puede generar mas ejecuciones Glue y mas costo.

Al terminar:

```bash
make destroy-infra
```
