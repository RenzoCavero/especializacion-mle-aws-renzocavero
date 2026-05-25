# Resumen del laboratorio 2: ML Data Processing & Prep

## Objetivo general
Construir un pipeline reproducible en AWS para preparar datos de fraude/riesgo desde archivos CSV sintéticos hasta datasets listos para entrenamiento e inferencia.

## Servicios AWS principales usados
- Amazon S3: data lake con zonas `raw/`, `cleaned/`, `curated/`, `features/`, `inference/`, `profiles/`, `quality/`, `lineage/`, `reports/`, `logs/`.
- AWS Glue Data Catalog: metadatos y tablas externas.
- AWS Glue Python Shell Job: procesamiento de profiling, calidad, limpieza, transformación y feature engineering.
- AWS Glue Crawler: opcional para descubrimiento de esquema.
- AWS Glue Data Quality: opcional para reglas de calidad administradas.
- Glue Column Statistics: opcional para estadísticas de columnas del catálogo.
- Amazon Athena: opcional para consultar tablas catalogadas.
- CloudWatch Logs: logs del Glue Job.
- CloudFormation: despliegue reproducible de recursos.

## Flujo de datos
1. Generar datos sintéticos locales en `data/sample/`.
2. Subir CSV a S3 en el prefijo `raw/`.
3. Registrar tablas externas en Glue Data Catalog.
4. Ejecutar Glue Job para profiling y calidad.
5. Procesar datos para limpiar, curar y generar features.
6. Generar datasets finales de entrenamiento e inferencia.
7. Descargar reportes de lineage y dataset card.

## Archivos y artefactos clave
- `data/sample/customers.csv`
- `data/sample/transactions.csv`
- `data/sample/inference_transactions.csv`
- `src/generate_sample_data.py`
- `src/upload_raw_data.py`
- `src/register_catalog.py`
- `src/run_processing_job.py`
- `src/feature_engineering.py`
- `src/build_training_dataset.py`
- `src/build_inference_dataset.py`
- `src/lineage_report.py`
- `src/dataset_card.py`

## Variables de configuración importantes
Copiar y editar el archivo de ambiente:

```bash
cp .env.example .env
```

Variables clave en `.env`:
- `AWS_PROFILE`: perfil AWS.
- `AWS_REGION`: región AWS.
- `S3_BUCKET_NAME`: bucket S3 destino (si se deja vacío, CloudFormation lo genera).
- `RESOURCE_PREFIX`: prefijo para recursos.
- `GLUE_DATABASE_NAME`: base de datos Glue.
- `GLUE_ROLE_ARN`: ARN de rol Glue precreado si no se pueden crear IAM roles.
- `EMPTY_S3_ON_DESTROY`: si se vacía el bucket al destruir infraestructura.

## Dependencias e instalación
Crear y activar un entorno virtual, luego instalar requisitos:

Linux/Mac:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Comandos principales del laboratorio

### Ejecución completa
- Con Make:
  ```bash
  make lab
  ```
- Sin Make (Bash):
  ```bash
  bash scripts/lab.sh all
  ```
- Sin Make (PowerShell):
  ```powershell
  .\scripts\lab.ps1 all
  ```

### Ejecución por pasos
- Listar pasos:
  ```bash
  bash scripts/lab.sh list
  python -m src.lab_runner list
  ```
- Ejecutar un paso específico:
  ```bash
  bash scripts/lab.sh step 04
  python -m src.lab_runner step 04
  ```

### Secuencia manual equivalente
```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
bash scripts/download_reports.sh
python -m src.validate_outputs
```

### Cleanup y destrucción
- Destruir infraestructura:
  ```bash
  bash scripts/destroy_infra.sh
  ```
- Limpiar artefactos locales:
  ```bash
  bash scripts/clean_local_outputs.sh --dry-run
  bash scripts/clean_local_outputs.sh
  ```

## Pasos del laboratorio y su propósito
- `01_aws_setup.md`: desplegar infraestructura base con CloudFormation.
- `02_data_lake_s3.md`: generar y subir datos raw a S3.
- `03_glue_catalog.md`: registrar tablas Glue.
- `04_data_quality_profiling.md`: generar profiling y reportes de calidad.
- `05_processing_jobs.md`: limpiar y curar datos.
- `06_feature_engineering.md`: crear features.
- `07_training_serving_consistency.md`: construir datasets de entrenamiento e inferencia.
- `08_governance_lineage.md`: generar lineage y dataset card.
- `09_cost_security_cleanup.md`: revisar costos y destruir recursos.
- `10_athena_glue_native_features.md`: ejecutar extras nativos de Glue.

## Salidas esperadas en S3
Después de ejecutar el flujo completo deben existir estos prefijos y archivos:

```text
s3://<bucket>/raw/customers.csv
s3://<bucket>/raw/transactions.csv
s3://<bucket>/raw/inference_transactions.csv
s3://<bucket>/scripts/glue_pipeline.py
s3://<bucket>/scripts/ml_data_prep_src.zip
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

## Validación rápida
1. Verificar stack CloudFormation `ml-data-prep-lab-stack`.
2. Confirmar bucket S3 y los prefijos principales (`raw/`, `cleaned/`, `features/`, `inference/`, `profiles/`, `quality/`).
3. Confirmar base de datos Glue `ml_data_prep_lab` y tablas registradas.
4. Revisar estado de ejecución del Glue Job y CloudWatch Logs.
5. Para extras, revisar Glue Crawler, Data Quality y Column Statistics.

## Recomendaciones útiles
- Usa `make lab` o `bash scripts/lab.sh all` para evitar ejecutar múltiples jobs Glue por separado.
- Si no puedes crear roles IAM, usa un `GLUE_ROLE_ARN` preexistente y `iam:PassRole`.
- No guardes claves sensibles en `.env` ni en el repositorio.
- Destruye la infraestructura al terminar para evitar costos.
