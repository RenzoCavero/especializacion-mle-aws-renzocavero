# Infraestructura

Esta carpeta contiene infraestructura como codigo para el laboratorio 4.

## CloudFormation

La plantilla `cloudformation/template.yaml` crea o referencia los recursos minimos:

- Bucket S3 opcional con public access block y cifrado SSE-S3.
- SageMaker Execution Role.
- Politicas para S3, SageMaker Model, Endpoint, EndpointConfig, TransformJob, Model Registry, Feature Store CreateFeatureGroup/PutRecord/GetRecord/DeleteFeatureGroup, CloudWatch Logs y Application Auto Scaling.
- Permisos S3 de bucket requeridos por Feature Store Offline Store, incluidos `s3:GetBucketAcl` y `s3:GetBucketLocation`.
- Tabla DynamoDB `fraud-decisions` para decisiones operacionales del caso de fraude.
- Cola SQS `fraud-events` para eventos asincronos posteriores a la prediccion online.

El laboratorio tambien puede usar un bucket existente. En ese caso configura:

```bash
export CREATE_BUCKET=false
export S3_BUCKET_NAME=<bucket-existente>
```

## Deploy

Bash:

```bash
scripts/deploy_infra.sh
```

PowerShell:

```powershell
scripts/deploy_infra.ps1
```

Outputs importantes:

- `BucketName`
- `SageMakerExecutionRoleArn`
- `FraudS3Prefix`
- `FraudDecisionTableName`
- `FraudEventQueueUrl`
- `FraudEventQueueName`

Los scripts del laboratorio escriben esos valores en `.env.cloud` como `S3_BUCKET_NAME`, `SAGEMAKER_EXECUTION_ROLE_ARN`, `FRAUD_S3_PREFIX`, `FRAUD_DECISION_TABLE_NAME`, `FRAUD_EVENT_QUEUE_URL` y `FRAUD_EVENT_QUEUE_NAME`.

## Uso en el caso de fraude

El modo cloud del caso de fraude usa:

- S3 como Data Lake con capas `raw`, `cleaned`, `curated`, exports offline, batch outputs y logs de inferencia.
- SageMaker Feature Store para Online Store y Offline Store.
- SageMaker Model Registry para registrar el modelo simple de fraude como Model Package aprobado.
- DynamoDB para consultar decisiones por `transaction_id`.
- SQS como cola de eventos que activa el pipeline asincrono.

La creacion de Feature Groups se hace desde codigo con `make fraud-curated-to-offline-features-aws` porque depende del contrato de features del caso. La plantilla prepara el bucket, el rol y los recursos operacionales compartidos.

## Seguridad

La plantilla usa permisos amplios dentro de servicios educativos para simplificar el laboratorio, pero sigue dos reglas:

- El bucket creado queda privado y cifrado.
- El cleanup del codigo no elimina Model Package ni Feature Group externos por defecto. Los Feature Groups creados por el caso de fraude pueden eliminarse con `make fraud-cleanup-feature-store-aws`.
- DynamoDB, SQS y el bucket pertenecen al stack CloudFormation. Eliminarlos debe hacerse como decision explicita de infraestructura, no como efecto colateral del scoring.

Para produccion, acotar los ARNs S3, SageMaker y Feature Store a nombres/prefijos concretos.
