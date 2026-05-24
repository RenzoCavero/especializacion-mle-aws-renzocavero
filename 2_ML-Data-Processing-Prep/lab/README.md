# Guia del laboratorio

## Objetivo del laboratorio

Este laboratorio construye la etapa de preparacion de datos para Machine Learning en AWS. El flujo empieza con datos sinteticos de clientes y transacciones, los publica en un data lake en Amazon S3, registra metadata en AWS Glue Data Catalog y ejecuta transformaciones cloud con un AWS Glue Python Shell Job.

Al finalizar, tendras:

1. Datos raw en S3.
2. Tablas registradas en Glue Data Catalog.
3. Reportes de profiling y calidad.
4. Datos limpios y curados.
5. Features para entrenamiento e inferencia.
6. Dataset supervisado para entrenamiento.
7. Dataset de inferencia sin target.
8. Lineage y dataset card.
9. Extras opcionales con Athena, Glue Crawler, Glue Data Quality y Glue Column Statistics.

## Que se construira en AWS

| Servicio | Uso en el laboratorio |
|---|---|
| Amazon S3 | Data lake con zonas `raw/`, `cleaned/`, `curated/`, `features/`, `inference/`, `profiles/`, `quality/`, `lineage/`, `reports/`, `logs/` y `scripts/`. |
| AWS CloudFormation | Despliegue reproducible del bucket, Glue Database, Glue Job, Glue Crawler, IAM Role y CloudWatch Log Group. |
| AWS IAM | Rol de ejecucion para Glue con permisos acotados al laboratorio. |
| AWS Glue Data Catalog | Metadata de tablas externas consultables por Glue, Athena y futuros flujos ML. |
| AWS Glue Python Shell Job | Procesamiento cloud principal del laboratorio. |
| AWS Glue Crawler | Extra opcional para descubrir esquemas desde S3. |
| AWS Glue Data Quality | Extra opcional para evaluar reglas DQDL administradas. |
| Glue Column Statistics | Extra opcional para estadisticas administradas del catalogo. |
| Amazon Athena | Consulta SQL sobre tablas del Glue Data Catalog. |
| Amazon CloudWatch Logs | Logs operativos del Glue Job. |

No se crean endpoints, Training Jobs ni modelos en este laboratorio. Esos temas se retoman en los laboratorios posteriores.

## Prerrequisitos

1. Cuenta AWS con permisos para CloudFormation, S3, Glue, IAM, CloudWatch Logs e `iam:PassRole`.
2. AWS CLI v2 instalado.
3. Python 3.11+ o 3.12.
4. Entorno virtual activo.
5. Dependencias instaladas:

   ```bash
   python -m pip install -r requirements.txt
   ```

6. Profile AWS valido:

   ```bash
   aws sts get-caller-identity --profile <AWS_PROFILE> --region <AWS_REGION>
   ```

## Configuracion inicial

Ejecuta desde la carpeta del proyecto:

```bash
cd 2_ML-Data-Processing-Prep
```

Copia `.env.example`:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Revisa estas variables:

| Variable | Default del repo | Uso |
|---|---|---|
| `AWS_PROFILE` | `mlops-2-data-prep-lab` | Profile usado por boto3 y AWS CLI. |
| `AWS_REGION` | `us-east-1` | Region donde se crean recursos. |
| `PROJECT_NAME` | `ml-data-processing-prep` | Nombre logico del proyecto. |
| `RESOURCE_PREFIX` | `ml-data-prep-lab` | Prefijo de recursos AWS. |
| `STACK_NAME` | `ml-data-prep-lab-stack` | Stack CloudFormation. |
| `S3_BUCKET_NAME` | vacio | Si queda vacio, CloudFormation genera el bucket. |
| `GLUE_DATABASE_NAME` | `ml_data_prep_lab` | Base de datos Glue. |
| `GLUE_ROLE_ARN` | vacio | Rol Glue precreado, si la cuenta no permite crear IAM roles. |
| `EMPTY_S3_ON_DESTROY` | `true` | Permite vaciar el bucket antes de borrar el stack. |

No guardes access keys, secret keys ni session tokens en `.env`. No commitees `.env`.

## Formas de ejecucion

Ejecucion completa del flujo base, sin cleanup:

```bash
make lab
```

Equivalente sin Make:

```bash
bash scripts/lab.sh all
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 all
```

Listar pasos:

```bash
bash scripts/lab.sh list
python -m src.lab_runner list
```

Ejecutar un paso:

```bash
bash scripts/lab.sh step 04
python -m src.lab_runner step 04
```

Cleanup:

```bash
bash scripts/lab.sh cleanup
make lab-09-cost-security-cleanup
```

## Mapa de scripts y codigo enviado a AWS Glue

El laboratorio tiene tres niveles de ejecucion:

1. Wrapper de terminal: Bash, PowerShell o Make.
2. Modulo Python local: envia llamadas a AWS o prepara archivos.
3. Codigo remoto: script que AWS Glue ejecuta dentro del Glue Job.

| Paso | Documento | Wrapper recomendado | Modulo Python local | Servicio o accion | Codigo remoto |
|---|---|---|---|---|---|
| 00 | `00_contexto_negocio.md` | `bash scripts/lab.sh step 00` | `src.lab_runner` | Solo lectura guiada. | No aplica. |
| 01 | `01_aws_setup.md` | `bash scripts/lab.sh step 01`, `bash scripts/deploy_infra.sh` | `src.deploy_infra` | CloudFormation crea S3, Glue, IAM y CloudWatch. | No aplica. |
| 02 | `02_data_lake_s3.md` | `bash scripts/lab.sh step 02`, `bash scripts/upload_sample_data.sh` | `src.generate_sample_data`, `src.upload_raw_data`, `src.package_job_assets` | Genera CSV locales, sube `raw/` y assets Glue a S3. | No aplica. |
| 03 | `03_glue_catalog.md` | `bash scripts/lab.sh step 03`, `make catalog` | `src.register_catalog`, `src.glue_catalog` | Crea/actualiza tablas Glue externas. | No aplica. |
| 04 | `04_data_quality_profiling.md` | `bash scripts/lab.sh step 04` | `src.run_processing_job --steps profile,quality` | Inicia un Glue Job para profiling y calidad. | `s3://<S3_BUCKET>/scripts/glue_pipeline.py` + `scripts/ml_data_prep_src.zip`. |
| 05 | `05_processing_jobs.md` | `bash scripts/lab.sh step 05`, `bash scripts/run_processing_job.sh process` | `src.run_processing_job --steps process` | Inicia un Glue Job para limpiar y curar datos. | `src.pipeline.run_pipeline` dentro de AWS Glue. |
| 06 | `06_feature_engineering.md` | `bash scripts/lab.sh step 06`, `bash scripts/run_processing_job.sh features` | `src.run_processing_job --steps features` | Genera features training/inference. | `src.feature_engineering` dentro del Glue Job. |
| 07 | `07_training_serving_consistency.md` | `bash scripts/lab.sh step 07` | `src.run_processing_job --steps training-dataset,inference-dataset` | Genera datasets finales y valida contrato. | `src.build_training_dataset`, `src.build_inference_dataset`, `src.feature_engineering`. |
| 08 | `08_governance_lineage.md` | `bash scripts/lab.sh step 08` | `src.run_processing_job --steps lineage,dataset-card`, `src.download_reports` | Genera y descarga reportes. | `src.lineage_report`, `src.dataset_card`. |
| 09 | `09_cost_security_cleanup.md` | `bash scripts/lab.sh cleanup`, `bash scripts/destroy_infra.sh` | `src.destroy_infra` | Vacia bucket y elimina stack. | No aplica. |
| 10 | `10_athena_glue_native_features.md` | `bash scripts/lab.sh step 10`, `make aws-native-extras` | `src.run_glue_crawler`, `src.run_glue_data_quality`, `src.run_glue_column_statistics` | Ejecuta extras administrados de Glue. | Servicios administrados de AWS Glue. |

El comando `bash scripts/lab.sh all` usa una ruta eficiente: despliega infraestructura, sube datos, registra catalogo y ejecuta `src.run_processing_job --steps all` una sola vez para reducir ejecuciones Glue.

## Secuencia recomendada

| Archivo | Proposito | Comando relacionado | Resultado esperado | Donde validarlo en AWS Console |
|---|---|---|---|---|
| `00_contexto_negocio.md` | Entender el caso de fraude/riesgo y los datasets. | `bash scripts/lab.sh step 00` | Sin recursos AWS. | No aplica. |
| `01_aws_setup.md` | Crear infraestructura base. | `bash scripts/lab.sh step 01` | Stack, bucket, Glue Database, Glue Job, Crawler, rol IAM y log group. | CloudFormation > Stacks; S3 > Buckets; AWS Glue > Databases/Jobs; IAM > Roles; CloudWatch > Log groups. |
| `02_data_lake_s3.md` | Generar y subir datos raw. | `bash scripts/lab.sh step 02` | CSV locales y objetos en `raw/` y `scripts/`. | S3 > `<S3_BUCKET>` > `raw/` y `scripts/`. |
| `03_glue_catalog.md` | Registrar tablas externas. | `bash scripts/lab.sh step 03` | Tablas Glue actualizadas. | AWS Glue > Data Catalog > Databases > `ml_data_prep_lab` > Tables. |
| `04_data_quality_profiling.md` | Crear reportes de profiling y calidad. | `bash scripts/lab.sh step 04` | `profiles/profile.json` y `quality/quality_report.json`. | AWS Glue > ETL jobs > Runs; CloudWatch Logs; S3 > `profiles/`, `quality/`. |
| `05_processing_jobs.md` | Limpiar y curar datos. | `bash scripts/lab.sh step 05` | `cleaned/` y `curated/`. | S3 > `cleaned/`, `curated/`; Glue Job run logs. |
| `06_feature_engineering.md` | Crear features. | `bash scripts/lab.sh step 06` | `features/training_features.csv` y `features/inference_features.csv`. | S3 > `features/`. |
| `07_training_serving_consistency.md` | Crear datasets finales con contrato consistente. | `bash scripts/lab.sh step 07` | `features/training_dataset.csv` e `inference/inference_dataset.csv`. | S3 > `features/`, `inference/`; Athena si el catalogo esta actualizado. |
| `08_governance_lineage.md` | Generar lineage y dataset card. | `bash scripts/lab.sh step 08` | Reportes en S3 y `artifacts/local_outputs/`. | S3 > `lineage/`, `reports/`; archivos locales descargados. |
| `09_cost_security_cleanup.md` | Revisar costos y eliminar recursos. | `bash scripts/lab.sh cleanup` | Stack eliminado o recursos retenidos segun permisos. | CloudFormation, S3, Glue, CloudWatch Logs, IAM. |
| `10_athena_glue_native_features.md` | Ejecutar extras nativos. | `bash scripts/lab.sh step 10` | Crawler demo, Glue Data Quality y Column Statistics. | Athena; AWS Glue > Crawlers, Data quality, Tables > Column statistics. |

## Outputs esperados en S3

Despues de `bash scripts/lab.sh all` o `make lab`, valida estos objetos:

```text
s3://<S3_BUCKET>/raw/customers.csv
s3://<S3_BUCKET>/raw/transactions.csv
s3://<S3_BUCKET>/raw/inference_transactions.csv
s3://<S3_BUCKET>/scripts/glue_pipeline.py
s3://<S3_BUCKET>/scripts/ml_data_prep_src.zip
s3://<S3_BUCKET>/profiles/profile.json
s3://<S3_BUCKET>/quality/quality_report.json
s3://<S3_BUCKET>/cleaned/customers.csv
s3://<S3_BUCKET>/cleaned/transactions.csv
s3://<S3_BUCKET>/curated/customer_transactions.csv
s3://<S3_BUCKET>/features/training_features.csv
s3://<S3_BUCKET>/features/inference_features.csv
s3://<S3_BUCKET>/features/training_dataset.csv
s3://<S3_BUCKET>/inference/inference_dataset.csv
s3://<S3_BUCKET>/lineage/lineage.json
s3://<S3_BUCKET>/lineage/lineage.md
s3://<S3_BUCKET>/reports/dataset_card.json
s3://<S3_BUCKET>/reports/dataset_card.md
s3://<S3_BUCKET>/logs/pipeline_run.json
```

## Artefactos locales importantes

| Ruta local | Generado por | Uso |
|---|---|---|
| `data/sample/customers.csv` | `src.generate_sample_data` | Datos sinteticos locales. |
| `data/sample/transactions.csv` | `src.generate_sample_data` | Historico con target `is_fraud`. |
| `data/sample/inference_transactions.csv` | `src.generate_sample_data` | Datos recientes sin target. |
| `data/local_cache/ml_data_prep_src.zip` | `src.package_job_assets` | Paquete que se sube a Glue. |
| `artifacts/local_outputs/profiles/profile.json` | `src.download_reports` | Profiling descargado desde S3. |
| `artifacts/local_outputs/quality/quality_report.json` | `src.download_reports` | Calidad descargada desde S3. |
| `artifacts/local_outputs/lineage/lineage.md` | `src.download_reports` | Trazabilidad legible. |
| `artifacts/local_outputs/reports/dataset_card.md` | `src.download_reports` | Resumen del dataset. |

Para borrar solo artefactos locales, sin tocar AWS:

```bash
python -m src.clean_local_outputs --dry-run
python -m src.clean_local_outputs
```

En Bash:

```bash
bash scripts/clean_local_outputs.sh --dry-run
```

En PowerShell:

```powershell
.\scripts\clean_local_outputs.ps1 -DryRun
```

## Validacion general en AWS Console

1. Abre AWS Console y confirma la region, por ejemplo `us-east-1`.
2. Ve a CloudFormation > Stacks y busca `ml-data-prep-lab-stack`.
3. Abre Amazon S3 > Buckets y entra al bucket generado por el stack.
4. Revisa los prefijos `raw/`, `scripts/`, `profiles/`, `quality/`, `cleaned/`, `curated/`, `features/`, `inference/`, `lineage/`, `reports/` y `logs/`.
5. Ve a AWS Glue > Data Catalog > Databases > `ml_data_prep_lab` y confirma las tablas.
6. Ve a AWS Glue > ETL jobs y abre `ml-data-prep-lab-processing-job`.
7. Entra a `Runs` y verifica que el ultimo run este en `Succeeded`.
8. Abre CloudWatch Logs desde el Glue Job si necesitas revisar errores.
9. Para extras, revisa AWS Glue > Crawlers, AWS Glue > Data quality y AWS Glue > Tables > `features_training` > Column statistics.
10. Para Athena, selecciona el database `ml_data_prep_lab` y ejecuta consultas sobre `features_training`.

## Advertencia de costos

Este laboratorio crea recursos reales. Los costos principales pueden venir de:

- Almacenamiento y requests de S3.
- Ejecuciones de AWS Glue Python Shell Job.
- Glue Crawler opcional.
- Glue Data Quality opcional.
- Glue Column Statistics opcional.
- CloudWatch Logs.

Para reducir costo, usa `bash scripts/lab.sh all` o `bash scripts/run_processing_job.sh all` cuando quieras una ejecucion completa, porque ejecuta un solo Glue Job para todos los pasos del pipeline. Ejecutar cada paso por separado es util para debug, pero lanza mas runs de Glue.

## Troubleshooting general

| Sintoma | Causa probable | Accion |
|---|---|---|
| `AccessDenied` en CloudFormation o IAM | El profile no puede crear o pasar roles. | Revisa `iam:PassRole`, `iam:CreateRole`, `iam:PutRolePolicy` o usa `GLUE_ROLE_ARN` precreado. |
| `BucketName output not found` | No se ejecuto el deploy o el stack fallo. | Ejecuta `bash scripts/lab.sh step 01` y revisa CloudFormation events. |
| `NoSuchKey` en `raw/` | No subiste datos. | Ejecuta `bash scripts/lab.sh step 02`. |
| Glue Job falla rapido | Assets no subidos o codigo no disponible. | Revisa S3 > `scripts/` y vuelve a ejecutar `bash scripts/run_processing_job.sh all`. |
| `No module named 'src'` en Glue | El zip `ml_data_prep_src.zip` no esta actualizado. | Ejecuta de nuevo `bash scripts/run_processing_job.sh all`; el script reempaqueta antes de lanzar el job. |
| Athena ve tablas pero 0 filas | La tabla apunta a prefijo sin copia compatible. | Ejecuta `python -m src.register_catalog` despues de generar outputs. |
| No ves datos en la consola | Region incorrecta. | Confirma `AWS_REGION` y el selector de region de la consola. |
| Cleanup queda en `DELETE_FAILED` | Falta permiso para borrar rol IAM. | Ejecuta `python -m src.destroy_infra --retain-glue-role` y pide revision del rol retenido. |

## Relacion con el siguiente laboratorio

Este laboratorio deja datasets listos para entrenamiento:

- `features/training_dataset.csv` para entrenar modelos.
- `inference/inference_dataset.csv` para simular scoring batch.
- Glue Catalog para consultar datasets con Athena.
- Lineage y dataset card para gobernanza.

El siguiente laboratorio usa estos conceptos para pasar de datos preparados a entrenamiento, optimizacion, registro de modelos y pipelines MLOps.
