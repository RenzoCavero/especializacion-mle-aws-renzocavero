# Fraud 01 - Infraestructura AWS: S3, IAM, DynamoDB y SQS

## Objetivo

Crear la infraestructura base que permite ejecutar el caso de fraude sobre AWS sin hardcodear credenciales ni recursos.

## Que vas a construir o validar

Este paso despliega o actualiza un stack CloudFormation con:

- Bucket S3 privado para Data Lake, logs, exports offline, batch outputs y retraining.
- IAM role para ejecucion de SageMaker y acceso a S3/Feature Store.
- Tabla DynamoDB para decisiones operacionales.
- Cola SQS para eventos asincronos despues del scoring online.
- Archivo `.env.cloud` con outputs reutilizables por los siguientes pasos.

## Input del paso

Variables esperadas en `.env`:

```bash
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
RESOURCE_PREFIX=ml-deploy-lab
STACK_NAME=ml-deploy-lab
S3_BUCKET_NAME=
CREATE_BUCKET=
```

Si `S3_BUCKET_NAME` esta vacio, CloudFormation crea un bucket del laboratorio. Si ya tienes bucket, define `CREATE_BUCKET=false` y `S3_BUCKET_NAME=<bucket>`.

## Output esperado del paso

Archivo `.env.cloud` con valores como:

```bash
S3_BUCKET_NAME=ml-deploy-lab-<account>-us-east-1
SAGEMAKER_EXECUTION_ROLE_ARN=arn:aws:iam::<account>:role/ml-deploy-lab-sagemaker-execution-role-us-east-1
FRAUD_S3_PREFIX=ml-deploy-lab/lab/fraud
FRAUD_DECISION_TABLE_NAME=ml-deploy-lab-fraud-decisions-us-east-1
FRAUD_EVENT_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/<account>/ml-deploy-lab-fraud-events-us-east-1
FRAUD_EVENT_QUEUE_NAME=ml-deploy-lab-fraud-events-us-east-1
```

## Conceptos claves

CloudFormation es el control plane de infraestructura. En lugar de crear recursos manualmente en consola, el laboratorio define recursos versionables y reproducibles. Esto tambien evita copiar ARNs manualmente: los outputs del stack se escriben en `.env.cloud`.

S3 cumple dos roles. Primero, actua como Data Lake con capas `raw`, `cleaned` y `curated`. Segundo, actua como storage operacional para logs de inferencia, exports del Offline Store y datasets model-ready para batch y retraining.

DynamoDB no reemplaza el Data Lake. Su funcion es consulta operacional de baja latencia por `transaction_id`, por ejemplo para que una aplicacion vea rapidamente si una transaccion fue `approve`, `manual_review` o `reject`.

SQS representa la frontera asincrona. La prediccion online no debe esperar a que se recalculen ventanas historicas ni a que se completen escrituras analiticas. En su lugar, emite un evento que otro proceso consume despues.

El IAM role debe aplicar minimo privilegio razonable para el laboratorio: acceso al bucket/prefijos del lab, Feature Store, DynamoDB, SQS y SageMaker. En produccion, se restringen ARNs y acciones por entorno.

## Prerrequisitos

- AWS CLI configurado o credenciales disponibles por rol.
- Permisos para CloudFormation, IAM, S3, DynamoDB, SQS y SageMaker.
- `.env` creado desde `.env.example`.
- Dependencias instaladas.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 01
```

Comando directo equivalente:

```bash
python -m src.deploy_infra
python -m src.config --check-aws
```

## Resultado esperado

El stack queda en `CREATE_COMPLETE` o `UPDATE_COMPLETE`. El archivo `.env.cloud` queda actualizado y los siguientes pasos pueden leer automaticamente bucket, rol, tabla y cola.

## Validacion local

Revisa:

```bash
type .env.cloud
python -m src.config --check-aws
```

En Git Bash:

```bash
cat .env.cloud
python -m src.config --check-aws
```

## Validacion en consola AWS

Revisa:

- CloudFormation: stack `ml-deploy-lab`.
- S3: bucket privado creado o bucket existente referenciado.
- IAM: role de SageMaker creado por el stack.
- DynamoDB: tabla `*-fraud-decisions-*`.
- SQS: cola `*-fraud-events-*`.

