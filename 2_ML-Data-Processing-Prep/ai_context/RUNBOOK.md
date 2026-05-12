# Runbook

Este runbook documenta el flujo esperado para desplegar, ejecutar, validar y destruir el laboratorio cloud del tema 2.

## Prerrequisitos

- Cuenta AWS.
- AWS CLI instalado.
- AWS CLI configurado con un profile.
- Permisos para crear recursos del laboratorio.
- Python 3.11+ o 3.12.
- Make opcional.
- Git Bash, Linux/Mac o PowerShell.

## Como Obtener Prerrequisitos

### AWS CLI

Instalar AWS CLI v2 desde:

```text
https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html
```

Validar:

```bash
aws --version
```

### Profile AWS Recomendado Con SSO

Pedir al administrador:

```text
SSO start URL
SSO region
AWS account ID
Permission set o rol asignado
Region del laboratorio
```

Configurar:

```bash
aws configure sso --profile mlops-2-data-prep-lab
aws sso login --profile mlops-2-data-prep-lab
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

### Profile Con Rol IAM

Si se usa rol, pedir `role_arn`, `source_profile`, permiso `sts:AssumeRole` y trust policy correcta.

Ejemplo en `~/.aws/config`:

```text
[profile mlops-2-data-prep-lab]
role_arn = arn:aws:iam::<account-id>:role/<role-name>
source_profile = base-profile
region = us-east-1
```

### Python Local

Instalar Python 3.11+ o 3.12 desde:

```text
https://www.python.org/downloads/
```

Validar:

```bash
python --version
```

### Permisos AWS

El profile o rol usado por `make all-cloud` debe poder crear y destruir recursos de:

```text
CloudFormation
S3
IAM
Glue
CloudWatch Logs
```

CloudFormation usa `CAPABILITY_NAMED_IAM`, por lo que el deployer necesita permisos IAM para crear el rol del Glue Job o un rol preexistente provisto por el administrador.

Validar permisos basicos:

```bash
aws cloudformation list-stacks --profile mlops-2-data-prep-lab --region us-east-1
aws s3 ls --profile mlops-2-data-prep-lab --region us-east-1
aws glue get-databases --profile mlops-2-data-prep-lab --region us-east-1
aws logs describe-log-groups --profile mlops-2-data-prep-lab --region us-east-1
```

## Configuracion

Crear archivo local de variables:

```bash
cp .env.example .env
```

Variables esperadas:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=
PROJECT_NAME=ml-data-processing-prep
ENVIRONMENT=lab
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
GLUE_ROLE_ARN=
GLUE_CRAWLER_NAME=
GLUE_DATA_QUALITY_RULESET_NAME=
GLUE_DATA_QUALITY_WORKERS=2
```

No guardar credenciales reales en `.env`.

## Instalacion Linux/Mac

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Instalacion Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Validar AWS CLI

```bash
aws sts get-caller-identity --profile <profile> --region <region>
aws configure list --profile <profile>
```

## Flujo Cloud Esperado

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

Comando completo:

```bash
make all-cloud
```

Extras AWS nativos opcionales, despues de `make all-cloud`:

```bash
make glue-crawler
make glue-data-quality
make column-stats
make aws-native-extras
```

Estos extras no se ejecutan dentro de `make all-cloud` para evitar costos adicionales no esperados. Se documentan en `lab/10_athena_glue_native_features.md`.

## Cleanup

```bash
make destroy-infra
```

Cleanup debe ejecutarse al terminar el laboratorio para evitar costos.

## Scripts Equivalentes Sin Make

Bash:

```bash
bash scripts/deploy_infra.sh
bash scripts/run_all_cloud.sh
bash scripts/destroy_infra.sh
```

La documentacion detallada de cada script Bash vive en `scripts/README.md`.

Secuencia manual recomendada:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
bash scripts/download_reports.sh
python -m src.validate_outputs
```

Que ocurre en cada paso:

- `deploy_infra.sh`: crea bucket S3, Glue Database, Glue Job, Glue Crawler, IAM Role y CloudWatch Log Group con CloudFormation.
- `upload_sample_data.sh`: ejecuta `src.generate_sample_data` y `src.upload_raw_data`; genera CSV sinteticos, sube datos a `raw/` y sube assets del Glue Job a `scripts/`.
- `python -m src.register_catalog`: registra o actualiza tablas externas en Glue Data Catalog. No genera datos ni transforma datasets; si los CSV ya existen, sincroniza copias bajo prefijos S3 consultables por Athena.
- `run_processing_job.sh all`: ejecuta el Glue Job para catalogo, profiling, calidad, limpieza, curacion, features, training dataset, inference dataset, lineage y dataset card. El paso `catalog` dentro del job es idempotente.
- `run_glue_crawler.sh`: ejecuta el Glue Crawler opcional sobre `crawler_demo/` y registra tablas `crawler_*` como ejemplo de descubrimiento automatico.
- `run_glue_data_quality.sh`: ejecuta Glue Data Quality sobre la tabla `features_training` y guarda resultados en `quality/`.
- `run_glue_column_statistics.sh`: calcula Glue Data Catalog Column Statistics para columnas clave de `features_training` y guarda una copia en `profiles/`.
- `download_reports.sh`: descarga reportes desde S3 a `artifacts/local_outputs/`.
- `python -m src.validate_outputs`: valida objetos esperados en S3, copias para Athena, tablas esperadas en Glue Catalog y ubicaciones `Location`.
- `destroy_infra.sh`: vacia el bucket del laboratorio y elimina el stack.

PowerShell:

```powershell
scripts/deploy_infra.ps1
scripts/run_all_cloud.ps1
scripts/destroy_infra.ps1
```

## Operaciones Esperadas

### Deploy

Debe crear o configurar:

- Bucket S3.
- Glue Database.
- IAM Role de procesamiento.
- CloudWatch Log Group.
- Recursos opcionales como Glue Crawler, Glue Job, SageMaker Processing config o KMS.

### Data

Debe generar datasets sinteticos pequenos para fraude o scoring de riesgo.

### Upload Raw

Debe subir datos a:

```text
s3://<bucket-name>/raw/
```

### Catalog

Debe registrar metadata en Glue Data Catalog. El laboratorio usa registro explicito por codigo para las tablas principales y ofrece Glue Crawler como demo opcional para descubrir esquemas desde S3.

### Profile

Debe generar reportes en:

```text
s3://<bucket-name>/profiles/
```

### Quality

Debe generar reportes en:

```text
s3://<bucket-name>/quality/
```

El pipeline principal genera `quality/quality_report.json` con reglas Python reproducibles. El extra opcional de Glue Data Quality genera resultados administrados en `quality/aws_glue_data_quality/` y un resumen en `quality/glue_data_quality_result.json`.

Modo de trabajo con Glue Data Quality:

- Ejecutarlo despues de `run_processing_job.sh all`.
- Validar que exista la tabla `features_training`.
- Usarlo para ensenar reglas DQDL administradas.
- Revisar el ruleset `ml-data-prep-lab-features-training-quality`.
- Revisar `quality/glue_data_quality_result.json` despues de descargar reportes.
- Tratarlo como complemento del reporte Python; en proyectos reales puede funcionar como quality gate antes de publicar features o entrenar modelos.

### Glue Crawler Opcional

Debe copiar datos raw a:

```text
s3://<bucket-name>/crawler_demo/
```

y crear tablas `crawler_*` en Glue Data Catalog. Se ejecuta con:

```bash
make glue-crawler
```

Modo de trabajo con Glue Crawler:

- Ejecutarlo despues de `upload_sample_data.sh`.
- Usarlo para demostrar descubrimiento automatico de esquemas.
- Revisar el crawler `ml-data-prep-lab-raw-crawler` en AWS Glue Console.
- Revisar tablas `crawler_*` en Glue Data Catalog.
- Comparar tablas `crawler_*` contra tablas manuales `raw_*`.
- Recordar que el crawler no es dependencia del pipeline principal; el pipeline usa tablas manuales porque conoce el contrato de datos y necesita reproducibilidad.

### Athena Opcional

Debe consultar tablas registradas en Glue Data Catalog desde la consola de Athena. La salida de Athena debe configurarse en:

```text
s3://<bucket-name>/athena-results/
```

El paso a paso esta en `lab/10_athena_glue_native_features.md`.

Las tablas Glue del laboratorio deben apuntar a prefijos S3 tipo carpeta. Por ejemplo:

```text
features_training Location: s3://<bucket-name>/features/training_dataset/
Objeto leido por Athena: s3://<bucket-name>/features/training_dataset/training_dataset.csv
```

El archivo simple `s3://<bucket-name>/features/training_dataset.csv` tambien existe para descarga directa y compatibilidad con los pasos del pipeline.

### Column Statistics Opcional

Debe calcular estadisticas administradas para `features_training` con Glue Data Catalog Column Statistics:

```bash
make column-stats
```

La copia del resultado para lectura del estudiante queda en:

```text
s3://<bucket-name>/profiles/glue_column_statistics_features_training.json
```

Modo de trabajo con Column Statistics:

- Ejecutarlo despues de `run_processing_job.sh all` y catalogo actualizado.
- Usarlo para mostrar estadisticas administradas del Glue Data Catalog.
- Revisar la seccion `Column statistics` de la tabla `features_training`.
- Explicar que el laboratorio calcula solo columnas clave para reducir costo y ruido.
- Revisar `profiles/glue_column_statistics_features_training.json` despues de descargar reportes.
- Usarlo como complemento de `profiles/profile.json`, no como reemplazo de profiling ML ni reglas de calidad.

### Process

Debe generar datos limpios y curados:

```text
s3://<bucket-name>/cleaned/
s3://<bucket-name>/curated/
```

### Features

Debe generar features en:

```text
s3://<bucket-name>/features/
```

### Training Dataset

Debe generar dataset supervisado para entrenamiento.

### Inference Dataset

Debe generar dataset sin etiqueta o con columnas objetivo excluidas para inferencia.

### Lineage

Debe generar reporte de lineage en:

```text
s3://<bucket-name>/lineage/
```

### Dataset Card

Debe generar dataset card en:

```text
s3://<bucket-name>/reports/
```

### Download Reports

Debe descargar reportes a:

```text
artifacts/local_outputs/
```

## Troubleshooting

### AWS CLI No Configurado

Sintoma: `Unable to locate credentials`.

Accion:

```bash
aws configure sso --profile <profile>
# o configurar el mecanismo autorizado por la organizacion
```

### Profile No Existe

Sintoma: `The config profile could not be found`.

Accion:

```bash
aws configure list-profiles
```

Actualizar `AWS_PROFILE`.

### Region No Configurada

Sintoma: errores de region faltante.

Accion: definir `AWS_REGION` en `.env` o pasar `--region`.

### Permisos Insuficientes

Sintoma: `AccessDenied`.

Accion: revisar permisos para CloudFormation, S3, IAM, Glue, SageMaker y CloudWatch. Usar minimo privilegio, pero asegurar permisos de deploy para crear recursos del laboratorio.

### Stack En DELETE_FAILED, CREATE_FAILED O ROLLBACK_COMPLETE

Sintoma: `Waiter StackCreateComplete failed` o stack en estado terminal fallido.

Accion 1: revisar eventos para encontrar la causa real:

```bash
aws cloudformation describe-stack-events \
  --stack-name ml-data-prep-lab-stack \
  --profile mlops-2-data-prep-lab \
  --region us-east-1 \
  --query "StackEvents[0:10].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
  --output table
```

Accion 2: limpiar el stack fallido:

```bash
python -m src.destroy_infra
```

Accion 3: corregir la causa indicada en `ResourceStatusReason` y reintentar:

```bash
bash scripts/deploy_infra.sh
```

Desde la version actual del deploy, los stacks nuevos usan `OnFailure=DO_NOTHING` para preservar eventos de diagnostico. El cleanup sigue siendo explicito con `destroy_infra`.

### Glue Data Quality Ruleset Falla Durante Deploy

Sintoma en eventos de CloudFormation:

```text
GlueFeaturesTrainingQualityRuleset AWS::Glue::DataQualityRuleset CREATE_FAILED Internal Failure
```

Accion:

- Actualizar el template a la version donde Glue Data Quality se crea bajo demanda con `make glue-data-quality`.
- Eliminar el stack fallido:

```bash
python -m src.destroy_infra
```

- Reintentar deploy:

```bash
bash scripts/deploy_infra.sh
```

El ruleset `ml-data-prep-lab-features-training-quality` se crea despues, cuando ejecutes:

```bash
make glue-data-quality
```

### Bucket Ya Existe

Sintoma: `BucketAlreadyExists`.

Accion: pasar un nombre unico o permitir que IaC genere uno con account id y region.

### Cleanup Falla Con `NoSuchBucket`

Sintoma:

```text
NoSuchBucket: The specified bucket does not exist
```

Causa probable:

- CloudFormation conserva una referencia fisica a un bucket de un intento fallido.
- El bucket fue eliminado o nunca termino de crearse.

Accion:

- Usar la version actual de `src.destroy_infra`, que ignora `NoSuchBucket` durante el vaciado y continua con `delete_stack`.
- Reintentar:

```bash
python -m src.destroy_infra
```

- Si despues aparece un fallo IAM al borrar el rol Glue, usar:

```bash
python -m src.destroy_infra --retain-glue-role
```

### Error De Acceso A S3

Sintoma: `AccessDenied` al subir o leer.

Accion: revisar bucket policy, public access block, permisos del rol y region.

### Error Creando Rol IAM

Sintoma: CloudFormation falla en IAM.

Accion: confirmar permisos `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PutRolePolicy` o usar rol preexistente si el ambiente no permite crear IAM.

Si el error menciona `iam:GetRole` o `iam:DeleteRolePolicy`, el profile no puede administrar roles IAM. Opciones:

- Pedir permisos temporales: `iam:GetRole`, `iam:CreateRole`, `iam:TagRole`, `iam:PutRolePolicy`, `iam:GetRolePolicy`, `iam:DeleteRolePolicy`, `iam:DeleteRole`, `iam:PassRole`.
- Usar un rol precreado por el administrador y configurar `GLUE_ROLE_ARN`.

El rol precreado debe confiar en `glue.amazonaws.com` y tener permisos S3, Glue Data Catalog y CloudWatch Logs para el laboratorio. El usuario que crea el Glue Job necesita `iam:PassRole` sobre ese rol.

Si el stack quedo en `DELETE_FAILED` por no poder borrar el rol:

```bash
python -m src.destroy_infra --retain-glue-role
```

Esto retiene `GlueProcessingRole` y permite eliminar el resto del stack. El rol queda huerfano para revision o eliminacion por un administrador.

### Cambios De Permisos En AWS SSO

Si el usuario ejecuta con IAM Identity Center / SSO, el caller suele verse asi:

```text
arn:aws:sts::<account-id>:assumed-role/AWSReservedSSO_MLOpsLab2Permission_<id>/<user>
```

Los permisos faltantes deben agregarse al Permission Set `MLOpsLab2Permission` o al rol SSO del deployer. No agregarlos al rol `ml-data-prep-lab-glue-processing-role`, porque ese rol es el recurso que CloudFormation intenta administrar.

Despues de actualizar `MLOpsLab2Permission`:

```bash
aws sso logout
aws sso login --profile mlops-2-data-prep-lab
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

Luego reintentar:

```bash
python -m src.destroy_infra
```

### Glue Job Falla

Accion:

- Revisar CloudWatch Logs.
- Verificar permisos S3 y Glue.
- Verificar que los paths S3 existan.
- Revisar dependencias y formato de entrada.

#### Error `ModuleNotFoundError: No module named 'src'`

Sintoma:

```text
RuntimeError: Glue job failed with state=FAILED: ModuleNotFoundError: No module named 'src'
```

Causa probable:

- El script principal `glue_pipeline.py` se ejecuto en Glue, pero el paquete del proyecto `src/` no quedo disponible en `sys.path`.
- Esto puede pasar si Glue no carga `--extra-py-files` antes del primer import del script.

Solucion aplicada en el laboratorio:

- `src/glue_pipeline.py` intenta importar `src.pipeline`.
- Si no encuentra `src`, descarga `s3://<bucket>/scripts/ml_data_prep_src.zip` a `/tmp/ml_data_prep_src.zip`.
- Agrega ese zip a `sys.path`.
- Luego importa `src.pipeline` y ejecuta el pipeline.

Para reintentar no necesitas redeploy de infraestructura. Ejecuta:

```bash
bash scripts/run_processing_job.sh all
```

Ese comando vuelve a subir:

```text
s3://<bucket>/scripts/glue_pipeline.py
s3://<bucket>/scripts/ml_data_prep_src.zip
```

y arranca un nuevo Glue Job.

### Glue Crawler Falla

Accion:

- Confirmar que existe `s3://<bucket>/raw/`.
- Ejecutar primero `bash scripts/upload_sample_data.sh`.
- Confirmar que el rol Glue puede leer y escribir `crawler_demo/`.
- Revisar el crawler `ml-data-prep-lab-raw-crawler` en AWS Glue Console.

### Glue Data Quality Falla

Accion:

- Confirmar que ya existe `s3://<bucket>/features/training_dataset.csv`.
- Ejecutar primero `bash scripts/run_processing_job.sh all`.
- Confirmar permisos del deployer para `glue:StartDataQualityRulesetEvaluationRun` y `iam:PassRole`.
- Revisar el ruleset `ml-data-prep-lab-features-training-quality` en AWS Glue Console.

Si el error contiene:

```text
LAUNCH ERROR | Error downloading from S3 for bucket: aws-glue-ml-data-quality-assets-<region>
Access Denied
```

el rol de ejecucion de Glue Data Quality necesita leer los assets administrados de AWS Glue Data Quality:

```json
{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::aws-glue-ml-data-quality-assets-<region>/*"
}
```

Si el rol lo administra este stack, actualizar la policy con:

```bash
bash scripts/deploy_infra.sh
```

Luego reintentar:

```bash
bash scripts/run_glue_data_quality.sh
```

Si se usa `GLUE_ROLE_ARN` con un rol precreado, pedir al administrador que agregue ese permiso al rol precreado.

Si el error contiene:

```text
not authorized to perform: glue:GetDataQualityRulesetEvaluationRun
```

el rol de ejecucion de Glue Data Quality necesita permisos Glue Data Quality sobre el ruleset:

```json
{
  "Effect": "Allow",
  "Action": [
    "glue:GetDataQualityRuleset",
    "glue:GetDataQualityRulesetEvaluationRun",
    "glue:GetDataQualityResult",
    "glue:PublishDataQuality"
  ],
  "Resource": "arn:aws:glue:<region>:<account-id>:dataQualityRuleset/*"
}
```

Si el rol lo administra este stack, actualizar:

```bash
bash scripts/deploy_infra.sh
```

Luego reintentar:

```bash
bash scripts/run_glue_data_quality.sh
```

Si el error contiene:

```text
InvalidInputException: A resource with the same resourceName but a different internalId already exists
```

significa que el ruleset se creo en un intento anterior, pero la evaluacion fallo despues. La version actual de `src.run_glue_data_quality` detecta ese ruleset y lo actualiza en vez de crearlo de nuevo. Reintentar:

```bash
bash scripts/run_glue_data_quality.sh
```

### Glue Column Statistics Falla

Accion:

- Confirmar que la tabla `features_training` existe en Glue Data Catalog.
- Ejecutar `python -m src.register_catalog`.
- Confirmar permisos `glue:StartColumnStatisticsTaskRun`, `glue:GetColumnStatisticsTaskRuns` y `iam:PassRole`.
- Revisar la seccion `Column statistics` de la tabla en Glue Console.

Si el error contiene:

```text
Unable to Validate access to underlying S3 path
```

el rol usado en `StartColumnStatisticsTaskRun` no puede validar la ubicacion S3 de la tabla. El rol necesita `s3:ListBucket` y `s3:GetBucketLocation` sobre el bucket del laboratorio, y `s3:GetObject` sobre los objetos de datos.

Si el rol lo administra este stack, actualizar:

```bash
bash scripts/deploy_infra.sh
```

Luego reintentar:

```bash
bash scripts/run_glue_column_statistics.sh
```

Si se usa `GLUE_ROLE_ARN` con un rol precreado, pedir al administrador que agregue esos permisos S3 al rol.

### Athena Devuelve 0 Filas Aunque `validate_outputs` Pasaba

Sintoma:

```sql
SELECT split, COUNT(*) AS rows
FROM features_training
GROUP BY split
ORDER BY split;
```

termina correctamente, pero muestra `Results (0)`.

Causas probables:

- La tabla Glue existe, pero su `Location` apunta a un objeto CSV individual en vez de a un prefijo S3.
- Las copias bajo prefijos de tabla aun no se sincronizaron.
- Athena esta reutilizando un resultado anterior.
- Se esta usando otra region, database o workgroup.

Accion:

```bash
python -m src.register_catalog
python -m src.validate_outputs
```

Si faltan outputs procesados:

```bash
bash scripts/run_processing_job.sh all
python -m src.register_catalog
python -m src.validate_outputs
```

Luego en Athena desactivar temporalmente `Reuse query results` o pulsar `Run again`.

### SageMaker Processing Job Falla

Accion:

- Revisar CloudWatch Logs del job.
- Confirmar imagen o framework usado.
- Verificar rol de ejecucion.
- Verificar inputs y outputs S3.
- Confirmar que no se exceden limites o cuotas.

### No Aparecen Logs En CloudWatch

Accion:

- Confirmar region.
- Confirmar log group.
- Confirmar permisos `logs:CreateLogStream` y `logs:PutLogEvents`.
- Esperar unos minutos por latencia de publicacion.

### Costos Inesperados

Accion:

- Ejecutar `make destroy-infra`.
- Revisar S3, Glue, SageMaker, CloudWatch y KMS.
- Revisar Billing por tags del laboratorio.

### Cleanup Incompleto

Accion:

- Revisar eventos del stack.
- Vaciar bucket solo si fue creado para el laboratorio.
- Eliminar feature groups opcionales.
- Revisar log groups retenidos.

### Problemas Con Makefile En Windows

Accion:

- Usar scripts PowerShell equivalentes.
- Usar Git Bash para scripts `.sh`.
- Verificar que el entorno virtual este activado.
