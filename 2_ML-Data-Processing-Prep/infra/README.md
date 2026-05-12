# Infraestructura Del Laboratorio

La infraestructura se define con AWS CloudFormation en:

```text
infra/cloudformation/template.yaml
```

## Recursos Creados

- Bucket S3 privado y cifrado para el data lake.
- Glue Data Catalog database.
- Glue Python Shell Job para procesamiento cloud.
- Glue Crawler opcional para demostrar descubrimiento automatico de esquemas.
- IAM Role para Glue con permisos acotados al bucket, catalogo y logs del laboratorio.
- CloudWatch Log Group con retencion corta.

## Despliegue

Desde la raiz de `2_ML-Data-Processing-Prep/`:

```bash
make deploy-infra
```

O directamente:

```bash
python -m src.deploy_infra
```

## Parametros

Los parametros se leen desde `.env`:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=
PROJECT_NAME=ml-data-processing-prep
ENVIRONMENT=lab
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
GLUE_DATABASE_NAME=ml_data_prep_lab
GLUE_ROLE_ARN=
GLUE_CRAWLER_NAME=
GLUE_DATA_QUALITY_RULESET_NAME=
GLUE_DATA_QUALITY_WORKERS=2
```

Si `S3_BUCKET_NAME` queda vacio, CloudFormation genera el nombre del bucket.

Si `GLUE_ROLE_ARN` queda vacio, CloudFormation intenta crear el rol IAM del Glue Job. Esto requiere permisos IAM como `iam:GetRole`, `iam:CreateRole`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:DeleteRole` e `iam:PassRole`.

Si la cuenta no permite crear roles IAM, pide al administrador un Glue execution role precreado y coloca el ARN en `GLUE_ROLE_ARN`.

## Procesamiento

El job `ml-data-prep-lab-processing-job` ejecuta:

- Profiling.
- Calidad.
- Limpieza.
- Curacion.
- Feature engineering.
- Training dataset.
- Inference dataset.
- Lineage.
- Dataset card.

El codigo del job se sube a `s3://<bucket>/scripts/` antes de iniciar la ejecucion.

## Extras Glue Nativos

El template tambien crea el crawler opcional para aprendizaje:

- Crawler `ml-data-prep-lab-raw-crawler`.

No se ejecutan automaticamente durante `make all-cloud`. Para usarlos:

```bash
make glue-crawler
make glue-data-quality
make column-stats
```

El crawler lee `s3://<bucket>/crawler_demo/` porque el script copia ahi una version separada de los CSV raw. Esto permite que Glue cree tablas separadas como `crawler_customers` y evita mezclar el demo de descubrimiento con las tablas contractuales del pipeline.

Glue Data Quality evalua reglas sobre la tabla `features_training`, despues de que el pipeline genere `features/training_dataset.csv`. El ruleset `ml-data-prep-lab-features-training-quality` se crea o actualiza bajo demanda con `make glue-data-quality`, no durante el despliegue de CloudFormation. Esto evita fallos transitorios de CloudFormation con `AWS::Glue::DataQualityRuleset` y mantiene el deploy base estable.

El rol de Glue creado por el template incluye `s3:GetObject` sobre `arn:aws:s3:::aws-glue-ml-data-quality-assets-<region>/*`, requerido por AWS Glue Data Quality para descargar sus librerias administradas. Si usas `GLUE_ROLE_ARN` con un rol precreado, el administrador debe agregar ese permiso al rol.

El rol tambien incluye permisos sobre `arn:aws:glue:<region>:<account-id>:dataQualityRuleset/*` para que la evaluacion pueda consultar el ruleset, publicar resultados y leer el estado del run. Si usas un rol precreado, agrega `glue:GetDataQualityRuleset`, `glue:GetDataQualityRulesetEvaluationRun`, `glue:GetDataQualityResult` y `glue:PublishDataQuality`.

Glue Data Catalog Column Statistics se calcula bajo demanda con `make column-stats` y queda visible en Glue Catalog; ademas se guarda una copia JSON en `profiles/`.

Column Statistics valida la ubicacion S3 de la tabla antes de iniciar. El rol creado por el template incluye `s3:ListBucket` y `s3:GetBucketLocation` sin condicion de prefijo sobre el bucket del laboratorio, mas `s3:GetObject` sobre los objetos permitidos. Esto es necesario porque la validacion de AWS Glue puede no enviar el mismo `s3:prefix` que usan otros pasos. Si usas un rol precreado, agrega permisos equivalentes sobre el bucket del laboratorio.

## Seguridad

El bucket bloquea acceso publico y usa SSE-S3. El rol IAM de Glue solo puede leer `raw/` y `scripts/`, y escribir en las zonas de salida del laboratorio.

## Costos

Este laboratorio usa datasets pequenos y Glue Python Shell con `0.0625` DPU por defecto. Aun asi, S3, Glue, Glue Crawlers, Glue Data Quality, Glue Column Statistics y CloudWatch pueden generar costos. Ejecuta cleanup al terminar.

## Cleanup

```bash
make destroy-infra
```

El script vacia el bucket creado por el stack y luego elimina CloudFormation. No guardes datos importantes en el bucket del laboratorio.

Si ejecutaste `make glue-data-quality`, el cleanup intenta eliminar tambien el ruleset `ml-data-prep-lab-features-training-quality` antes de borrar el stack.

Si el stack queda en `DELETE_FAILED` porque tu profile no puede ejecutar `iam:DeleteRolePolicy`, usa:

```bash
python -m src.destroy_infra --retain-glue-role
```

Esto elimina el stack reteniendo `GlueProcessingRole`. El rol queda huerfano y debe revisarlo o eliminarlo un administrador.

## Nota Para AWS SSO

Si el caller es un rol asumido de IAM Identity Center, por ejemplo:

```text
AWSReservedSSO_MLOpsLab2Permission_<id>
```

los permisos IAM faltantes deben agregarse al Permission Set `MLOpsLab2Permission` o al rol que usa el deployer. Agregar la politica al rol `ml-data-prep-lab-glue-processing-role` no ayuda, porque ese es el recurso administrado por CloudFormation.

Despues de actualizar permisos SSO:

```bash
aws sso logout
aws sso login --profile mlops-2-data-prep-lab
```

Luego reintenta deploy o cleanup.
