# 01 - AWS Setup

Configura AWS CLI con un profile o rol IAM. No guardes access keys en el repositorio.

## 1. Obtener Una Cuenta AWS

Necesitas una cuenta AWS de laboratorio, sandbox, AWS Academy, Learner Lab o una cuenta corporativa.

Si trabajas en una organizacion, pide al administrador una de estas opciones:

- Acceso por AWS IAM Identity Center / SSO.
- Un IAM Role que puedas asumir.
- Un usuario temporal de laboratorio con permisos acotados.

Evita usar el usuario root. No uses access keys permanentes salvo que el instructor o administrador lo indique explicitamente para un entorno controlado.

## 2. Instalar AWS CLI

Instala AWS CLI v2 desde la documentacion oficial:

```text
https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html
```

Valida:

```bash
aws --version
```

Debes ver una version `aws-cli/2.x`.

## 3. Configurar Un Profile Con IAM Identity Center / SSO

Esta es la opcion recomendada para estudiantes porque evita credenciales permanentes.

Pide al administrador AWS:

```text
SSO start URL
SSO region
AWS account ID
Permission set o rol asignado
Region del laboratorio, por ejemplo us-east-1
```

Configura el profile:

```bash
aws configure sso --profile mlops-2-data-prep-lab
```

Inicia sesion:

```bash
aws sso login --profile mlops-2-data-prep-lab
```

Valida identidad:

```bash
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

Si funciona, copia el profile y region a `.env`:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
RESOURCE_PREFIX=ml-data-prep-lab
S3_BUCKET_NAME=
```

## 4. Alternativa: Configurar Un Profile Que Asume Un Rol

Si el administrador te entrega un IAM Role, pide:

```text
Role ARN
Nombre del source profile
Region del laboratorio
Permiso sts:AssumeRole desde el source profile
Trust policy del rol que permita asumirlo
```

Ejemplo conceptual en `~/.aws/config`:

```text
[profile base-profile]
region = us-east-1

[profile mlops-2-data-prep-lab]
role_arn = arn:aws:iam::<account-id>:role/<role-name>
source_profile = base-profile
region = us-east-1
```

Valida:

```bash
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

La AWS CLI pedira o reutilizara credenciales temporales segun el mecanismo configurado. No copies tokens temporales al repositorio.

## 5. Instalar Python 3.11+ O 3.12

Valida si ya existe:

```bash
python --version
```

En Windows tambien puedes revisar:

```powershell
py -0p
```

Si no tienes Python 3.11+ o 3.12, instala desde:

```text
https://www.python.org/downloads/
```

En Windows marca `Add python.exe to PATH` durante la instalacion.

Luego, desde la raiz del laboratorio:

```bash
python -m venv .venv
```

Linux/Mac:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 6. Obtener Permisos Para Desplegar El Laboratorio

Los permisos no se instalan localmente. Los asigna un administrador en AWS mediante IAM Identity Center, el Permission Set `MLOpsLab2Permission`, una politica IAM o un IAM Role.

El usuario, profile o rol que ejecuta `make all-cloud` necesita permisos para:

- CloudFormation create/update/delete stack.
- Crear bucket S3.
- Crear rol IAM y policy del laboratorio.
- Crear Glue database y Glue job.
- Crear CloudWatch log group.

Este laboratorio despliega CloudFormation con:

```text
CAPABILITY_NAMED_IAM
```

Eso significa que CloudFormation puede crear un rol IAM con nombre para el Glue Job. Si el deploy falla en IAM, pide al administrador permisos para crear roles/policies del laboratorio o solicita que el rol sea precreado.

## 7. Checklist De Permisos

Valida servicios basicos:

```bash
aws cloudformation list-stacks --profile mlops-2-data-prep-lab --region us-east-1
aws s3 ls --profile mlops-2-data-prep-lab --region us-east-1
aws glue get-databases --profile mlops-2-data-prep-lab --region us-east-1
aws logs describe-log-groups --profile mlops-2-data-prep-lab --region us-east-1
```

Validar identidad:

```bash
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

Si cualquiera devuelve `AccessDenied`, comparte el error con el administrador AWS.

## 8. Permisos Minimos Conceptuales

Para un entorno educativo aislado, el administrador puede asignar el Permission Set `MLOpsLab2Permission`. Para una cuenta compartida, pedir permisos acotados a recursos con prefijo:

```text
ml-data-prep-lab
```

Servicios requeridos:

- `cloudformation:*` sobre el stack del laboratorio.
- `s3:*` solo sobre el bucket del laboratorio.
- `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:PutRolePolicy`, `iam:PassRole` para el rol de Glue del laboratorio.
- `glue:*` para database, tables y job del laboratorio.
- `logs:*` para log groups/streams del laboratorio.

En produccion, reemplaza comodines por acciones y ARNs exactos.

## 9. Configurar `.env`

Desde la raiz del laboratorio:

```bash
cp .env.example .env
```

Ejemplo:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
PROJECT_NAME=ml-data-processing-prep
ENVIRONMENT=lab
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
GLUE_DATABASE_NAME=ml_data_prep_lab
GLUE_ROLE_ARN=
STACK_NAME=ml-data-prep-lab-stack
EMPTY_S3_ON_DESTROY=true
```

No incluyas:

- Access keys.
- Secret keys.
- Session tokens.
- Passwords.
- Archivos de credenciales.

## 10. Validacion Final Antes Del Deploy

```bash
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
python --version
python -m pytest -q
```

Luego ejecuta:

```bash
make all-cloud
```

Al terminar:

```bash
make destroy-infra
```

## 11. Cuentas Restringidas Sin Permisos IAM

Si el deploy falla con:

```text
not authorized to perform: iam:GetRole
not authorized to perform: iam:DeleteRolePolicy
```

el profile puede usar servicios como S3, Glue o CloudFormation, pero no puede administrar roles IAM. Revisa que el Permission Set `MLOpsLab2Permission` incluya las acciones IAM necesarias para el laboratorio.

Opcion A: pedir permisos temporales para crear y eliminar el rol del laboratorio:

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

Opcion B: pedir un Glue execution role precreado.

El rol precreado debe tener:

- Trust policy para `glue.amazonaws.com`.
- Permisos para leer `raw/` y `scripts/` en el bucket del laboratorio.
- Permisos para escribir `cleaned/`, `curated/`, `features/`, `inference/`, `profiles/`, `quality/`, `lineage/`, `reports/` y `logs/`.
- Permisos de Glue Data Catalog para la database del laboratorio.
- Permisos de CloudWatch Logs para los log groups del laboratorio.

Tu profile tambien necesita:

```text
iam:PassRole
```

sobre ese rol precreado.

Luego configura `.env`:

```text
GLUE_ROLE_ARN=arn:aws:iam::<account-id>:role/<glue-role-name>
```

Si un stack quedo atascado en `DELETE_FAILED` por no poder borrar el rol IAM:

```bash
python -m src.destroy_infra --retain-glue-role
```

Esto elimina el resto del stack y deja el rol IAM retenido para que el administrador lo revise o elimine.

## 12. Refrescar Login Cuando Cambian Permisos SSO

Si estas usando AWS IAM Identity Center / SSO, los permisos se aplican al Permission Set `MLOpsLab2Permission`, que genera el rol asumido, por ejemplo:

```text
arn:aws:sts::<account-id>:assumed-role/AWSReservedSSO_MLOpsLab2Permission_<id>/<user>
```

La politica con permisos como `iam:DeleteRolePolicy` debe agregarse al Permission Set `MLOpsLab2Permission` o al rol SSO correspondiente, no al rol `ml-data-prep-lab-glue-processing-role`.

Incorrecto:

```text
Agregar permisos al rol ml-data-prep-lab-glue-processing-role
```

Correcto:

```text
Agregar permisos al Permission Set MLOpsLab2Permission o identity que usa tu AWS_PROFILE
```

Despues de que el administrador cambie permisos, cierra y vuelve a abrir sesion:

```bash
aws sso logout
aws sso login --profile mlops-2-data-prep-lab
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

Luego reintenta:

```bash
python -m src.destroy_infra
```

Si el stack sigue en `DELETE_FAILED`, elimina el stack reteniendo el rol:

```bash
python -m src.destroy_infra --retain-glue-role
```

Ese comando deja el rol IAM huerfano; un administrador debe revisarlo o eliminarlo.

## 13. Siguiente Paso Despues Del Setup

Cuando `aws sts get-caller-identity` funciona y `.env` esta configurado, continua con:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
```

Para entender que hace cada script antes de ejecutarlo, lee:

```text
scripts/README.md
```

Para entender las capas S3 creadas por el flujo, sigue con:

```text
lab/02_data_lake_s3.md
lab/03_glue_catalog.md
lab/05_processing_jobs.md
```
