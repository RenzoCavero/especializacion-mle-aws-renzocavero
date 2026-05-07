# 09 - Costos, Seguridad Y Cleanup

Buenas practicas aplicadas:

- Datos sinteticos, sin PII real.
- Bucket S3 privado.
- Cifrado SSE-S3.
- IAM minimo privilegio para Glue.
- Glue Python Shell efimero.
- Sin endpoints persistentes.
- CloudWatch Logs con retencion corta.

Revisar recursos:

```bash
aws cloudformation describe-stacks --stack-name ml-data-prep-lab-stack --profile <profile> --region <region>
aws glue get-job-runs --job-name ml-data-prep-lab-processing-job --profile <profile> --region <region>
aws s3 ls s3://<bucket-name>/ --recursive --profile <profile> --region <region>
```

Cleanup obligatorio:

```bash
make destroy-infra
```

Riesgo principal: dejar el bucket, Glue Job o logs activos despues del laboratorio. Ejecuta cleanup al finalizar.

## Recursos Que Pueden Generar Costo

| Recurso | Por que puede costar | Control aplicado |
|---|---|---|
| S3 | Almacenamiento y requests. | Datasets pequenos y cleanup del bucket. |
| Glue Job | Tiempo de ejecucion del job. | Uso de Glue Python Shell y preferencia por `steps all`. |
| Glue Data Catalog | Metadata y requests. | Pocas tablas, nombres acotados al laboratorio. |
| CloudWatch Logs | Ingestion y almacenamiento de logs. | Retencion corta definida por infraestructura. |
| KMS, si se habilita | Requests de cifrado. | Por defecto se usa SSE-S3 para simplicidad. |

## Comando De Cleanup Con Scripts

Con Bash:

```bash
bash scripts/destroy_infra.sh
```

Con Python directo:

```bash
python -m src.destroy_infra
```

Si CloudFormation queda en `DELETE_FAILED` por permisos insuficientes para borrar el rol IAM del Glue Job:

```bash
python -m src.destroy_infra --retain-glue-role
```

Ese comando elimina el resto de recursos y retiene `GlueProcessingRole` para revision por un administrador.

## Checklist Al Final Del Laboratorio

Ejecuta:

```bash
aws cloudformation describe-stacks --stack-name ml-data-prep-lab-stack --profile <profile> --region <region>
```

Si el stack ya no existe, revisa recursos remanentes por prefijo:

```bash
aws s3 ls --profile <profile> --region <region>
aws glue get-databases --profile <profile> --region <region>
aws logs describe-log-groups --log-group-name-prefix /aws/ml-data-prep-lab --profile <profile> --region <region>
```

Si usaste `--retain-glue-role`, pide al administrador eliminar o revisar:

```text
ml-data-prep-lab-glue-processing-role
```
