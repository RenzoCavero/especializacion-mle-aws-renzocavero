# Procesamiento Y Preparacion De Datos AWS - Machine Learning

Laboratorio cloud-first del tema 2 de la especializacion ML en AWS.

El objetivo es construir un pipeline reproducible en AWS que lleve datos crudos sinteticos de fraude o scoring de riesgo hasta datasets listos para entrenamiento e inferencia.

## Arquitectura

Servicios usados:

- Amazon S3 como data lake.
- AWS Glue Data Catalog para metadatos.
- AWS Glue Python Shell Job para profiling, calidad, limpieza, transformacion y features.
- AWS Glue Crawler como ejemplo opcional de descubrimiento de esquemas.
- AWS Glue Data Quality como ejemplo opcional de reglas administradas.
- AWS Glue Data Catalog Column Statistics como ejemplo opcional de estadisticas administradas.
- Amazon Athena como ejemplo opcional de consulta SQL sobre tablas catalogadas.
- IAM Role con minimo privilegio.
- CloudWatch Logs para operacion.
- CloudFormation como infraestructura reproducible.

## Flujo

```text
data/sample/*.csv
  -> s3://<bucket>/raw/
  -> Glue Data Catalog
  -> Glue Job
  -> cleaned/
  -> curated/
  -> features/
  -> inference/
  -> profiles/ quality/ lineage/ reports/ logs/
```

## Prerrequisitos

- Cuenta AWS.
- AWS CLI configurado con un profile o rol.
- Python 3.11+ o 3.12 local.
- Permisos para CloudFormation, S3, IAM, Glue y CloudWatch.

### Como Obtener Los Prerrequisitos

1. Instala AWS CLI v2 desde la documentacion oficial:

   ```text
   https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html
   ```

   Valida:

   ```bash
   aws --version
   ```

2. Configura un profile AWS. Recomendado: IAM Identity Center / SSO.

   Pide al administrador AWS:

   ```text
   SSO start URL
   SSO region
   AWS account ID
   Permission set o rol asignado
   Region del laboratorio
   ```

   Configura e inicia sesion:

   ```bash
   aws configure sso --profile mlops-2-data-prep-lab
   aws sso login --profile mlops-2-data-prep-lab
   aws sts get-caller-identity --profile mlops-2-data-prep-lab
   ```

   Alternativa con rol IAM: configura un profile con `role_arn` y `source_profile` en `~/.aws/config`. La CLI asumira el rol y administrara credenciales temporales.

3. Instala Python 3.11+ o 3.12 desde:

   ```text
   https://www.python.org/downloads/
   ```

   Valida:

   ```bash
   python --version
   ```

4. Solicita permisos AWS para desplegar el laboratorio.

   El usuario, el Permission Set `MLOpsLab2Permission` o el rol que ejecuta `make all-cloud` necesita crear y destruir recursos de:

   ```text
   CloudFormation
   S3
   IAM
   Glue
   CloudWatch Logs
   ```

   Validaciones rapidas:

   ```bash
   aws cloudformation list-stacks --profile mlops-2-data-prep-lab --region us-east-1
   aws s3 ls --profile mlops-2-data-prep-lab --region us-east-1
   aws glue get-databases --profile mlops-2-data-prep-lab --region us-east-1
   aws logs describe-log-groups --profile mlops-2-data-prep-lab --region us-east-1
   ```

   Si aparece `AccessDenied`, falta permiso. Revisa el detalle completo en `lab/01_aws_setup.md`.

## Configuracion

```bash
cp .env.example .env
```

Edita `.env`:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
GLUE_DATABASE_NAME=ml_data_prep_lab
GLUE_CRAWLER_NAME=
GLUE_DATA_QUALITY_RULESET_NAME=
GLUE_DATA_QUALITY_WORKERS=2
GLUE_ROLE_ARN=
```

No coloques access keys ni tokens en el repositorio.

Si tu cuenta no permite crear roles IAM, pide al administrador un Glue execution role precreado y coloca su ARN en `GLUE_ROLE_ARN`. Aun con rol precreado, tu profile necesita permiso `iam:PassRole` sobre ese rol para crear el Glue Job.

## Instalacion

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

## Ejecucion Completa

```bash
make all-cloud
```

El comando:

1. Despliega CloudFormation.
2. Genera datos sinteticos.
3. Sube datos crudos a S3.
4. Registra tablas en Glue Catalog.
5. Ejecuta el Glue Job con todos los pasos.
6. Descarga reportes.
7. Valida outputs esperados.

## Ejecucion Sin Make

Bash:

```bash
bash scripts/run_all_cloud.sh
```

Esto ejecuta en secuencia: deploy de infraestructura, generacion de datos, upload a S3, registro Glue Catalog, Glue Job completo, descarga de reportes y validacion. La guia detallada de cada script esta en `scripts/README.md`.

PowerShell:

```powershell
scripts/run_all_cloud.ps1
```

Secuencia manual equivalente en Bash:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
bash scripts/download_reports.sh
python -m src.validate_outputs
```

Nota: `bash scripts/upload_sample_data.sh` genera datos sinteticos, sube archivos a `s3://<bucket>/raw/` y crea copias raw bajo prefijos compatibles con Athena. El registro en Glue Catalog se ejecuta con `python -m src.register_catalog`, `make catalog` o dentro de `bash scripts/run_all_cloud.sh`. La definicion detallada de cada script y modulo esta en `scripts/README.md`.

Las tablas Glue del laboratorio apuntan a prefijos S3 tipo carpeta. Por ejemplo, `features_training` usa `s3://<bucket>/features/training_dataset/`, que contiene `training_dataset.csv`. El archivo simple `s3://<bucket>/features/training_dataset.csv` tambien se mantiene para descarga directa y compatibilidad didactica.

Cleanup:

```bash
bash scripts/destroy_infra.sh
```

## Targets Principales

```bash
make deploy-infra
make data
make upload-raw
make catalog
make profile
make quality
make process
make features
make training-dataset
make inference-dataset
make lineage
make dataset-card
make download-reports
make validate
make destroy-infra
```

Para evitar multiples ejecuciones de Glue y reducir costo, usa `make all-cloud` durante el flujo normal.

## Extras AWS Nativos Opcionales

Despues del pipeline principal puedes ejecutar ejemplos administrados adicionales:

```bash
make aws-native-extras
```

Esto ejecuta Glue Crawler, Glue Data Quality y Glue Data Catalog Column Statistics sobre datos ya generados por el laboratorio. Tambien queda documentado un ejemplo paso a paso para consultar las tablas desde la consola de Athena.

Guia detallada:

```text
lab/10_athena_glue_native_features.md
```

Ese capitulo explica como trabajar en detalle con:

- Glue Crawler: discovery automatico de esquemas sobre `crawler_demo/`.
- Glue Data Quality: reglas DQDL administradas sobre `features_training`.
- Glue Column Statistics: estadisticas administradas para columnas clave del catalogo.

Comandos individuales:

```bash
make glue-crawler
make glue-data-quality
make column-stats
```

Estos comandos son opcionales y pueden generar costo adicional por ejecuciones de Glue y almacenamiento de resultados en S3.

## Outputs En S3

```text
s3://<bucket-name>/raw/
s3://<bucket-name>/cleaned/
s3://<bucket-name>/curated/
s3://<bucket-name>/features/
s3://<bucket-name>/inference/
s3://<bucket-name>/profiles/profile.json
s3://<bucket-name>/quality/quality_report.json
s3://<bucket-name>/lineage/lineage.json
s3://<bucket-name>/reports/dataset_card.md
s3://<bucket-name>/logs/pipeline_run.json
```

Listar outputs:

```bash
aws s3 ls s3://<bucket-name>/ --recursive --profile <profile> --region <region>
```

## Logs CloudWatch

El stack crea:

```text
/aws/ml-data-prep-lab/processing
```

AWS Glue tambien puede publicar logs administrados bajo:

```text
/aws-glue/python-jobs/output
/aws-glue/python-jobs/error
```

Buscar ejecuciones:

```bash
aws glue get-job-runs --job-name ml-data-prep-lab-processing-job --profile <profile> --region <region>
aws logs describe-log-groups --log-group-name-prefix /aws --profile <profile> --region <region>
```

## Cleanup

```bash
make destroy-infra
```

El script vacia el bucket del laboratorio y elimina el stack. Ejecutalo al terminar para evitar costos.

## Troubleshooting CloudFormation

Si `deploy_infra.sh` falla con `DELETE_FAILED`, `CREATE_FAILED` o `ROLLBACK_COMPLETE`, revisa primero los eventos del stack:

```bash
aws cloudformation describe-stack-events \
  --stack-name ml-data-prep-lab-stack \
  --profile mlops-2-data-prep-lab \
  --region us-east-1 \
  --query "StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
  --output table
```

La columna `ResourceStatusReason` muestra la causa real, por ejemplo permisos insuficientes, nombre de recurso duplicado, bucket existente o fallo creando IAM.

Luego limpia el stack fallido:

```bash
python -m src.destroy_infra
```

Y vuelve a desplegar:

```bash
bash scripts/deploy_infra.sh
```

Si el cleanup falla por permisos, pide al administrador permisos para eliminar recursos del laboratorio en CloudFormation, S3, IAM, Glue y CloudWatch Logs.

## Troubleshooting Glue Job

### Error `ModuleNotFoundError: No module named 'src'`

Si `bash scripts/run_processing_job.sh all` falla con:

```text
Glue job failed with state=FAILED: ModuleNotFoundError: No module named 'src'
```

el Glue Job encontro `glue_pipeline.py`, pero no cargo el paquete del proyecto `src/` antes del primer import.

El laboratorio incluye una proteccion en `src/glue_pipeline.py`: si `src` no esta disponible, descarga `s3://<bucket>/scripts/ml_data_prep_src.zip` a `/tmp`, lo agrega a `sys.path` y continua.

Para aplicar la correccion, no necesitas recrear CloudFormation. Solo reintenta:

```bash
bash scripts/run_processing_job.sh all
```

Ese comando vuelve a subir `glue_pipeline.py` y `ml_data_prep_src.zip` antes de lanzar el job.

## Troubleshooting Athena

### Query Devuelve 0 Filas Aunque `validate_outputs` Pasa

Si Athena muestra el esquema de `features_training`, pero esta consulta devuelve 0 filas:

```sql
SELECT split, COUNT(*) AS rows
FROM features_training
GROUP BY split
ORDER BY split;
```

ejecuta:

```bash
python -m src.register_catalog
python -m src.validate_outputs
```

Luego vuelve a correr la query con `Run again` y, si aplica, desactiva temporalmente `Reuse query results`.

Si `validate_outputs` reporta objetos faltantes, regenera el pipeline:

```bash
bash scripts/run_processing_job.sh all
python -m src.register_catalog
python -m src.validate_outputs
```

La guia completa esta en `lab/10_athena_glue_native_features.md`.

## Troubleshooting IAM

### Error IAM: `iam:GetRole` O `iam:DeleteRolePolicy`

Si ves un error como:

```text
not authorized to perform: iam:GetRole
not authorized to perform: iam:DeleteRolePolicy
```

tu profile no tiene permisos para que CloudFormation cree o elimine el rol IAM del Glue Job. En este laboratorio, revisa el Permission Set `MLOpsLab2Permission`, porque muchos entornos bloquean acciones IAM.

Tienes dos opciones:

1. Pedir al administrador permisos temporales para desplegar y destruir el rol del laboratorio:

   ```text
   iam:GetRole
   iam:CreateRole
   iam:TagRole
   iam:PutRolePolicy
   iam:GetRolePolicy
   iam:DeleteRolePolicy
   iam:DeleteRole
   iam:PassRole
   ```

2. Pedir al administrador un Glue execution role precreado, con trust policy para `glue.amazonaws.com`, permisos S3/Glue/Logs del laboratorio, y permiso `iam:PassRole` para tu profile. Luego configura:

   ```text
   GLUE_ROLE_ARN=arn:aws:iam::<account-id>:role/<glue-role-name>
   ```

Para limpiar un stack atascado en `DELETE_FAILED` por falta de `iam:DeleteRolePolicy`, puedes retener el rol IAM y eliminar el resto del stack:

```bash
python -m src.destroy_infra --retain-glue-role
```

Esto deja el rol `ml-data-prep-lab-glue-processing-role` como recurso huerfano. Pide al administrador que lo revise o elimine despues.

### Importante Para AWS SSO / IAM Identity Center

Si usas un profile SSO y ves un caller como:

```text
arn:aws:sts::<account-id>:assumed-role/AWSReservedSSO_MLOpsLab2Permission_<id>/<user>
```

los permisos faltantes deben agregarse al Permission Set `MLOpsLab2Permission` o al rol que genera `AWSReservedSSO_MLOpsLab2Permission_<id>`. No sirve agregarlos al rol `ml-data-prep-lab-glue-processing-role`, porque ese rol es el recurso que CloudFormation intenta crear o eliminar.

Despues de que el administrador actualice `MLOpsLab2Permission`, refresca la sesion local:

```bash
aws sso logout
aws sso login --profile mlops-2-data-prep-lab
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

Luego reintenta:

```bash
python -m src.destroy_infra
```

Si sigue fallando por `iam:DeleteRolePolicy`, usa:

```bash
python -m src.destroy_infra --retain-glue-role
```

## Seguridad Y Costo

- Usa datos sinteticos.
- No usa endpoints persistentes.
- Glue Python Shell usa `0.0625` DPU por defecto.
- S3 bloquea acceso publico y usa SSE-S3.
- IAM se limita al bucket, Glue database y logs del laboratorio.
- CloudWatch Logs tiene retencion corta.

## Tests Locales

```bash
make test
```

Los tests validan generacion de datos, calidad, limpieza, features y consistencia entrenamiento/inferencia sin tocar AWS.
