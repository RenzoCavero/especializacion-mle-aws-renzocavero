# 01 - Configuracion AWS, IAM e infraestructura base

## Objetivo

Preparar la infraestructura base del laboratorio en AWS.

Este paso crea el bucket S3, el rol de ejecucion de SageMaker, permisos IAM acotados y un log group propio del laboratorio.

## Que vas a construir o validar

Vas a desplegar el stack CloudFormation `ml-training-opt-lab`. El stack crea:

| Recurso | Nombre o patron | Uso |
|---|---|---|
| Bucket S3 | generado por CloudFormation o definido en `S3_BUCKET_NAME` | Datos, codigo, modelos, metricas y reportes. |
| IAM Role | `SageMakerExecutionRole` dentro del stack | Rol usado por Processing Jobs, Training Jobs, HPO, Pipelines y Model Registry. |
| IAM Policy | `LabSageMakerExecutionPolicy` | Permisos sobre S3, SageMaker, Glue, Athena, CloudWatch Logs y ECR. |
| CloudWatch Log Group | `/<RESOURCE_PREFIX>/sagemaker-lab` | Log group propio con retencion limitada. |

Los jobs de SageMaker tambien escribiran logs en grupos administrados por AWS como `/aws/sagemaker/ProcessingJobs` y `/aws/sagemaker/TrainingJobs`.

## Conceptos clave

- AWS CloudFormation: servicio de infraestructura como codigo.
- IAM Role: identidad que SageMaker asume para acceder a S3, CloudWatch y otros servicios.
- Athena: servicio usado por el Processing Job para consultar el Offline Store registrado en Glue.
- `iam:PassRole`: permiso que permite entregar el rol de ejecucion a SageMaker.
- `.env`: archivo local editable con configuracion del estudiante.
- `.env.cloud`: archivo generado con outputs reales del stack. No debes commitearlo.

## Prerrequisitos

1. Ubicate en:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Copia el ejemplo de variables:

   ```bash
   cp .env.example .env
   ```

   En PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edita `.env` y confirma al menos:

   ```text
   AWS_PROFILE=mlops-2-data-prep-lab
   AWS_REGION=us-east-1
   RESOURCE_PREFIX=ml-training-opt-lab
   STACK_NAME=ml-training-opt-lab
   ```

4. Valida tu identidad AWS:

   ```bash
   aws sts get-caller-identity --profile <AWS_PROFILE> --region <AWS_REGION>
   ```

5. Si usas AWS SSO y el token expiro, inicia sesion:

   ```bash
   aws sso login --profile <AWS_PROFILE>
   ```

No escribas access keys dentro del repositorio. No commitees `.env` ni `.env.cloud`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-01-aws-setup
```

Comando individual equivalente:

```bash
make deploy-infra
```

Con Bash o Git Bash:

```bash
bash scripts/deploy_infra.sh
```

En Windows PowerShell:

```powershell
.\scripts\deploy_infra.ps1
```

Con Python:

```bash
python -m src.deploy_infra
```

`scripts/deploy_infra.sh` y `scripts/deploy_infra.ps1` cargan `.env`, ejecutan `aws cloudformation deploy` y luego ejecutan:

```bash
python -m src.fetch_stack_outputs
```

`make lab-01-aws-setup` ejecuta directamente `python -m src.deploy_infra`, que usa boto3 para crear o actualizar el stack.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/deploy_infra.sh` |
| Wrapper PowerShell | `scripts/deploy_infra.ps1` |
| Modulo Python recomendado para desplegar infra | `src/deploy_infra.py` |
| Modulo que escribe outputs locales | `src/fetch_stack_outputs.py` |
| Template CloudFormation enviado a AWS | `infra/cloudformation/template.yaml` |

## Scripts y parametros principales

| Necesidad | Archivo a modificar | Comentario |
|---|---|---|
| Cambiar permisos IAM del rol de SageMaker | `infra/cloudformation/template.yaml` | Agrega acciones bajo `SageMakerExecutionPolicy` solo si el laboratorio las requiere. |
| Cambiar bucket, region, prefijo o stack | `.env`, `.env.example`, `src/config.py` | `.env` controla la ejecucion local; `src/config.py` define defaults. |
| Cambiar como se despliega infraestructura | `src/deploy_infra.py` | Usa boto3/CloudFormation y escribe outputs al final. |
| Cambiar como se escribe `.env.cloud` | `src/fetch_stack_outputs.py` | Lee outputs del stack y genera variables locales. |
| Cambiar wrappers de terminal | `scripts/deploy_infra.sh`, `scripts/deploy_infra.ps1` | Utiles si necesitas adaptar Git Bash o PowerShell. |
| Ver relacion con otros pasos | `lab/14_workflow_and_scripts_reference.md` | Mapa completo del workflow. |

## Resultado esperado

Archivos locales generados:

```text
.env.cloud
artifacts/local_outputs/infra_outputs.json
```

`.env.cloud` debe incluir:

```text
S3_BUCKET_NAME=<S3_BUCKET>
SAGEMAKER_EXECUTION_ROLE_ARN=<SAGEMAKER_ROLE_ARN>
```

`artifacts/local_outputs/infra_outputs.json` debe incluir outputs como:

- `BucketName`.
- `SageMakerExecutionRoleArn`.
- `StackName`.
- `LabLogGroupName`.

La terminal debe finalizar con un mensaje similar a:

```text
Infrastructure ready. Bucket: <S3_BUCKET>
```

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a CloudFormation > Stacks.
3. Busca `ml-training-opt-lab`.
4. Verifica estado `CREATE_COMPLETE` o `UPDATE_COMPLETE`.
5. Abre la pestana `Outputs` y confirma el bucket y el rol de SageMaker.
6. Ve a Amazon S3 y abre el bucket creado.
7. En `Permissions`, confirma que el acceso publico esta bloqueado.
8. En `Properties`, confirma cifrado por defecto con SSE-S3.
9. Ve a IAM > Roles y busca el rol creado por el stack.
10. Abre `Trust relationships` y confirma que `sagemaker.amazonaws.com` puede asumir el rol.
11. En `Permissions`, confirma que la politica incluye acciones como `athena:StartQueryExecution`, `glue:GetTable`, `sagemaker:AddTags` y permisos de S3 sobre el bucket del laboratorio.
12. Ve a CloudWatch > Log groups y busca `/<RESOURCE_PREFIX>/sagemaker-lab`.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `Missing required AWS configuration` en pasos posteriores | No existe `.env.cloud` o no tiene bucket/rol. | Reejecuta `make lab-01-aws-setup`. |
| `AccessDenied` en CloudFormation o IAM | El profile no tiene permisos suficientes. | Valida permisos para CloudFormation, S3, IAM, SageMaker, CloudWatch Logs e `iam:PassRole`. |
| Bucket name ya existe | `S3_BUCKET_NAME` debe ser globalmente unico. | Deja `S3_BUCKET_NAME=` vacio o usa otro nombre. |
| Region incorrecta | `AWS_REGION` no coincide con la consola abierta. | Ajusta `.env` o cambia la region en la consola. |
| Token SSO expirado | Sesion AWS SSO vencida. | Ejecuta `aws sso login --profile <AWS_PROFILE>`. |

## Limpieza de recursos

No limpies todavia. Este stack es necesario para todos los pasos siguientes. La limpieza se realiza en el paso 12.
