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
bash scripts/lab.sh cleanup
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
bash scripts/lab.sh cleanup
bash scripts/destroy_infra.sh
```

Con Windows PowerShell:

```powershell
.\scripts\lab.ps1 cleanup
.\scripts\destroy_infra.ps1
```

Con Python directo:

```bash
python -m src.destroy_infra
```

## Limpieza Solo De Archivos Locales

Si quieres borrar outputs locales sin tocar AWS:

```bash
python -m src.clean_local_outputs --dry-run
python -m src.clean_local_outputs
```

Con Bash:

```bash
bash scripts/clean_local_outputs.sh --dry-run
bash scripts/clean_local_outputs.sh
```

Con PowerShell:

```powershell
.\scripts\clean_local_outputs.ps1 -DryRun
.\scripts\clean_local_outputs.ps1
```

Esto limpia:

- `data/sample/*.csv`
- `data/local_cache/`
- `artifacts/local_outputs/`

No elimina `.env`, no borra codigo fuente y no toca recursos AWS.

Si CloudFormation queda en `DELETE_FAILED` por permisos insuficientes para borrar el rol IAM del Glue Job:

```bash
python -m src.destroy_infra --retain-glue-role
```

Ese comando elimina el resto de recursos y retiene `GlueProcessingRole` para revision por un administrador.

Si el cleanup muestra `NoSuchBucket`, significa que el stack aun referencia un bucket que ya no existe o que no termino de crearse. La version actual de `src.destroy_infra` ignora ese caso durante el vaciado y continua con la eliminacion del stack:

```bash
python -m src.destroy_infra
```

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

## Validacion En AWS Console

Despues del cleanup:

1. Abre CloudFormation > Stacks.
2. Confirma que `ml-data-prep-lab-stack` ya no exista o este en eliminacion completada.
3. Abre Amazon S3 y confirma que el bucket del laboratorio ya no existe.
4. Abre AWS Glue > Databases y confirma que `ml_data_prep_lab` fue eliminado.
5. Abre AWS Glue > ETL jobs y confirma que `ml-data-prep-lab-processing-job` ya no existe.
6. Abre CloudWatch > Log groups y revisa que no queden log groups con prefijo `/aws/ml-data-prep-lab`.
7. Si ejecutaste `--retain-glue-role`, abre IAM > Roles y revisa el rol retenido con un administrador antes de eliminarlo manualmente.
