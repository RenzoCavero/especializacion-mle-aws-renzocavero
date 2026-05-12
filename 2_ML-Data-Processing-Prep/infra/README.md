# Infraestructura Del Laboratorio

La infraestructura se define con AWS CloudFormation en:

```text
infra/cloudformation/template.yaml
```

## Recursos Creados

- Bucket S3 privado y cifrado para el data lake.
- Glue Data Catalog database.
- Glue Python Shell Job para procesamiento cloud.
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

## Seguridad

El bucket bloquea acceso publico y usa SSE-S3. El rol IAM de Glue solo puede leer `raw/` y `scripts/`, y escribir en las zonas de salida del laboratorio.

## Costos

Este laboratorio usa datasets pequenos y Glue Python Shell con `0.0625` DPU por defecto. Aun asi, S3, Glue y CloudWatch pueden generar costos. Ejecuta cleanup al terminar.

## Cleanup

```bash
make destroy-infra
```

El script vacia el bucket creado por el stack y luego elimina CloudFormation. No guardes datos importantes en el bucket del laboratorio.

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
