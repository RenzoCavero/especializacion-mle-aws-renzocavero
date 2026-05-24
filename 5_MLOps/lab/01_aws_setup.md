# 01 - AWS setup

## Objetivo

Validar que la configuracion local puede autenticarse contra AWS y crear o actualizar la infraestructura base necesaria para los siguientes pasos.

## Que vas a construir o validar

Vas a validar `.env`, region, profile y acceso a AWS. Si bucket o roles todavia no existen, este mismo paso crea o actualiza la infraestructura base con CloudFormation y escribe los outputs en `.env.cloud`.

## Input del paso

- `.env` con valores minimos:
  - `AWS_REGION`, con `us-east-1` como default si queda vacio.
  - `AWS_PROFILE`, opcional si usas credenciales del entorno, SSO activo o un rol.
  - `S3_BUCKET_NAME`, opcional antes de desplegar infraestructura.
  - Roles IAM, opcionales antes de desplegar infraestructura.
- Credenciales disponibles por AWS profile, variables de entorno, SSO o rol.
- Stack CloudFormation opcional previo. Si no existe, el paso lo crea.

## Output esperado del paso

- Impresion de configuracion no sensible.
- Validacion de sesion boto3.
- Identidad AWS confirmada via STS.
- Stack CloudFormation `mlops-lab-stack` creado o actualizado.
- `.env.cloud` con:
  - `S3_BUCKET_NAME`
  - `SAGEMAKER_EXECUTION_ROLE_ARN`
  - `LAMBDA_EXECUTION_ROLE_ARN`
  - `STEPFUNCTIONS_ROLE_ARN`
  - `EVENTBRIDGE_TO_SFN_ROLE_ARN`
- Validacion final mostrando bucket y roles listos.

## Conceptos claves

La configuracion AWS es el primer control de seguridad del laboratorio. No se usan credenciales hardcodeadas; boto3 resuelve credenciales mediante el mecanismo configurado localmente: profile, SSO, variables de entorno, metadata de instancia o rol.

`AWS_REGION` es obligatoria porque SageMaker, CloudWatch, EventBridge, Step Functions y Lambda son servicios regionales. Un endpoint creado en una region no existe en otra. Mantener todos los recursos del laboratorio en la misma region evita errores de ARN, permisos y busqueda de artefactos.

`S3_BUCKET_NAME` y `SAGEMAKER_EXECUTION_ROLE_ARN` no tienen que estar completos antes de ejecutar este paso. Si faltan, al inicio aparecen como `PENDING`; luego `src.deploy_infra` crea o actualiza la base cloud y escribe `.env.cloud`. Los pasos posteriores cargan automaticamente esos valores.

`SAGEMAKER_EXECUTION_ROLE_ARN` permite a SageMaker leer datos en S3, escribir artefactos, ejecutar jobs y crear modelos. Esta relacion usa `iam:PassRole`: la identidad que lanza el pipeline debe estar autorizada a pasar ese rol a SageMaker. Muchos errores de MLOps en AWS no son de codigo, sino de PassRole o de permisos S3 mal delimitados.

Los roles de Lambda, Step Functions y EventBridge separan responsabilidades. Lambda ejecuta acciones ligeras, Step Functions coordina decisiones y EventBridge enruta eventos. Separar roles evita usar permisos amplios para todo.

CloudFormation deja una base reproducible. En este laboratorio, la infraestructura base crea roles y bucket opcional; los recursos MLOps dinamicos se crean paso a paso para que cada componente sea visible. El comando principal de infraestructura es `python -m src.deploy_infra`; `make deploy-infra`, `scripts/deploy_infra.sh` y `scripts/deploy_infra.ps1` son formas convenientes de llamar esa misma ruta.

Si cambias de cuenta AWS, `.env.cloud` puede contener outputs viejos. El paso 01 detecta ARNs de otra cuenta y refresca los outputs para la cuenta activa.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.config` | `.env`, `.env.cloud` si existe | Ninguno | Impresion de configuracion efectiva | Ninguno | Mostrar valores no sensibles y detectar pendientes. |
| 2 | `src.aws_clients` | `.env`, `.env.cloud` | STS, S3/IAM/SageMaker segun config | Impresion de readiness | Ninguno | Validar credenciales, region, bucket y roles. |
| 3 | `src.deploy_infra` | `infra/cloudformation/template.yaml`, `.env` | CloudFormation, IAM, S3 | `.env.cloud` | Stack `mlops-lab-stack`, bucket y roles base | Crear o actualizar infraestructura base. |
| 4 | `src.aws_clients` | `.env`, `.env.cloud` actualizado | STS y recursos base | Impresion final de readiness | Ninguno | Confirmar que los pasos cloud pueden continuar. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Local input | `.env` | Configuracion editable por el estudiante. |
| Local output | `.env.cloud` | Outputs generados por CloudFormation: bucket y roles. |
| Infra | `infra/cloudformation/template.yaml` | Definicion de roles IAM y bucket opcional. |
| AWS output | CloudFormation `mlops-lab-stack` | Stack que agrupa la base cloud del laboratorio. |
| AWS output | S3 bucket del lab | Almacenamiento de datos, modelos, captura y monitoreo. |

## Prerrequisitos

- AWS CLI configurado.
- `pip install -r requirements.txt`.
- `.env` creado a partir de `.env.example`.

## Pasos de ejecucion

Ejecuta solamente el paso numerado:

```bash
python -m src.lab_runner step 01
```

Internamente ejecuta:

```bash
python -m src.config
python -m src.aws_clients
python -m src.deploy_infra
python -m src.aws_clients
```

## Resultado esperado

El comando muestra la configuracion efectiva y un bloque similar a:

```text
AWS setup readiness
===================
AWS_ACCOUNT_ID: ...
AWS_REGION: us-east-1
```

Al inicio puede verse:

```text
S3_BUCKET_NAME: PENDING - run make deploy-infra or set S3_BUCKET_NAME
```

Al final del mismo paso debe verse un bucket y roles ya resueltos. Tambien puedes evitar CloudFormation si ya tienes un bucket y roles existentes. En ese caso define manualmente en `.env`:

```env
S3_BUCKET_NAME=tu-bucket-privado
SAGEMAKER_EXECUTION_ROLE_ARN=arn:aws:iam::<account-id>:role/<sagemaker-role>
LAMBDA_EXECUTION_ROLE_ARN=arn:aws:iam::<account-id>:role/<lambda-role>
STEPFUNCTIONS_ROLE_ARN=arn:aws:iam::<account-id>:role/<stepfunctions-role>
EVENTBRIDGE_TO_SFN_ROLE_ARN=arn:aws:iam::<account-id>:role/<eventbridge-role>
```

## Validacion local

```bash
python -m src.config
```

## Validacion en consola AWS

- CloudFormation: stack `mlops-lab-stack` o el nombre definido.
- IAM: roles `mlops-lab-lab-sagemaker-exec`, `mlops-lab-lab-lambda`, `mlops-lab-lab-sfn`.
- S3: bucket creado o bucket existente configurado.

## Errores frecuentes

- Profile inexistente.
- Region vacia.
- Bucket pendiente despues del paso 01: revisa permisos CloudFormation/IAM/S3 y que `.env.cloud` no este bloqueado.
- `iam:PassRole` insuficiente.
- Roles creados pero no copiados a `.env`.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.config` | Cargar `.env` y `.env.cloud`, construir rutas y defaults. | `load_config`, `LabConfig`, `validate_for_cloud`. | `.env`, `.env.cloud`. | stdout con configuracion resuelta. |
| `src.aws_clients` | Validar sesion boto3 y credenciales. | `create_session`, `create_clients`, `main --strict`. | `AWS_PROFILE`, `AWS_REGION`. | stdout de readiness. |
| `src.deploy_infra` | Crear o actualizar stack CloudFormation. | `deploy_infra`, `stack_parameters`, `write_env_cloud`. | `infra/cloudformation/template.yaml`, `.env`. | `.env.cloud`, stack outputs, metadata de infraestructura. |

Configuraciones que mas cambian el comportamiento:

- `CREATE_BUCKET`: vacio/`true` crea bucket; `false` usa `S3_BUCKET_NAME`.
- `STACK_NAME`, `RESOURCE_PREFIX`, `ENVIRONMENT`: cambian nombres fisicos.
- `AWS_PROFILE`, `AWS_REGION`: definen cuenta y region.
- `S3_BUCKET_NAME`: obligatorio si no quieres que CloudFormation cree bucket.

Validacion profunda:

```bash
python -m src.deploy_infra
python -m src.config
python -m src.aws_clients --strict
type .env.cloud
```

Si `src.aws_clients --strict` falla despues de desplegar infraestructura, el problema esta en credenciales/profile/region, no en SageMaker. Si `.env.cloud` no contiene roles, revisa los outputs del stack en CloudFormation.
