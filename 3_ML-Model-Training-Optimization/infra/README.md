# Infraestructura

Este laboratorio usa AWS CloudFormation como herramienta IaC predeterminada.

El stack crea:

- Un bucket S3 privado y cifrado para datos, artefactos, metricas y reportes.
- Un rol de ejecucion de SageMaker usado por Processing Jobs, Training Jobs, HPO y Pipelines.
- Un log group propio del laboratorio en CloudWatch con retencion limitada. Los jobs de SageMaker tambien escriben en log groups administrados por AWS bajo `/aws/sagemaker/*`.

Feature Store, jobs, Experiments, Model Registry y Pipelines se crean desde scripts Python porque dependen del schema de features y de outputs generados durante la ejecucion del laboratorio.

## Despliegue

Con Bash:

```bash
bash scripts/deploy_infra.sh
```

Con Python:

```bash
python -m src.deploy_infra
```

## Destruccion

Con Bash:

```bash
DELETE_S3_OBJECTS_ON_CLEANUP=true bash scripts/destroy_infra.sh
```

Con Python:

```bash
DELETE_S3_OBJECTS_ON_CLEANUP=true python -m src.destroy_infra
```

El profile AWS usado para desplegar tambien debe tener permisos para crear jobs de SageMaker y para pasar el SageMaker Execution Role generado.
