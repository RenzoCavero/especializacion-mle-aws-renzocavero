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

- `deploy_infra.sh`: crea bucket S3, Glue Database, Glue Job, IAM Role y CloudWatch Log Group con CloudFormation.
- `upload_sample_data.sh`: ejecuta `src.generate_sample_data` y `src.upload_raw_data`; genera CSV sinteticos, sube datos a `raw/` y sube assets del Glue Job a `scripts/`.
- `python -m src.register_catalog`: registra o actualiza tablas externas en Glue Data Catalog. No genera datos, no sube CSV y no transforma datasets.
- `run_processing_job.sh all`: ejecuta el Glue Job para catalogo, profiling, calidad, limpieza, curacion, features, training dataset, inference dataset, lineage y dataset card. El paso `catalog` dentro del job es idempotente.
- `download_reports.sh`: descarga reportes desde S3 a `artifacts/local_outputs/`.
- `python -m src.validate_outputs`: valida objetos esperados en S3 y tablas esperadas en Glue Catalog.
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

Debe registrar metadata en Glue Data Catalog o ejecutar crawler si se implementa.

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

### Bucket Ya Existe

Sintoma: `BucketAlreadyExists`.

Accion: pasar un nombre unico o permitir que IaC genere uno con account id y region.

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
