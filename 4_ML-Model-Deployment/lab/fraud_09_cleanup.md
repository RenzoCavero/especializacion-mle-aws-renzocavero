# Fraud 09 - Cleanup endpoint y Feature Store

## Objetivo

Eliminar de forma explicita el Real-Time Endpoint, Endpoint Configuration, SageMaker Model y Feature Groups creados por el caso de fraude sin borrar recursos externos ni datos de otros laboratorios.

## Que vas a construir o validar

Este paso valida:

- Eliminacion del endpoint `FRAUD_ENDPOINT_NAME`.
- Eliminacion de `FRAUD_ENDPOINT_CONFIG_NAME`.
- Eliminacion de `FRAUD_MODEL_NAME`.
- Identificacion de Feature Groups creados con `FRAUD_FEATURE_GROUP_PREFIX`.
- Eliminacion de Feature Groups del caso de fraude.
- Conservacion de Model Registry, DynamoDB, SQS y bucket.
- Conservacion de recursos externos por defecto.

## Input del paso

Variables:

```bash
FRAUD_FEATURE_GROUP_PREFIX=ml-deploy-lab-fraud
FRAUD_MODEL_NAME=ml-deploy-lab-fraud-model
FRAUD_ENDPOINT_CONFIG_NAME=ml-deploy-lab-fraud-realtime-config
FRAUD_ENDPOINT_NAME=ml-deploy-lab-fraud-realtime-endpoint
AWS_REGION=us-east-1
```

## Output esperado del paso

Resumen:

```json
{
  "deleted": ["ml-deploy-lab-fraud-user-profile-features"],
  "skipped": []
}
```

## Conceptos claves

Cleanup debe ser explicito porque los recursos cloud generan costo y porque borrar recursos equivocados puede romper otros flujos. Este paso borra solo recursos deployables y Feature Groups creados por la ruta fraud.

El Real-Time Endpoint es el recurso mas importante de limpiar porque genera costo mientras esta activo. El SageMaker Model y Endpoint Configuration no mantienen capacidad, pero se eliminan para evitar confusion en la consola.

El bucket S3, DynamoDB, SQS y Model Registry se conservan. El Model Registry representa gobierno y versionado del modelo; borrarlo deberia ser una decision separada.

No se borran Model Packages, Feature Groups externos ni recursos del laboratorio 3. La regla general es: el laboratorio solo elimina recursos que creo y que puede identificar por prefijo controlado.

SageMaker Feature Store puede tardar en borrar Feature Groups. Si un grupo queda en estado `Deleting`, espera unos minutos antes de recrearlo.

SageMaker no siempre permite borrar un endpoint mientras esta en `Creating`, `Updating` o `SystemUpdating`. El cleanup espera a que termine la operacion en progreso y luego elimina el endpoint. Si ves mensajes de espera, es normal: evita dejar capacidad activa y costo acumulandose.

## Prerrequisitos

- Haber ejecutado `fraud-step 03`.
- Permiso `sagemaker:DeleteFeatureGroup`.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-cleanup
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.pipelines.cleanup_feature_store_aws
```

## Resultado esperado

El endpoint, endpoint config, SageMaker Model y Feature Groups del caso de fraude se eliminan o se reportan como inexistentes. DynamoDB, SQS, S3 y Model Registry se conservan.

## Cleanup total opcional

El cleanup numerado conserva recursos de gobierno e infraestructura. Si quieres borrar tambien los recursos restantes del caso de fraude, usa el comando de teardown total con flags explicitos:

```bash
python -m fraud_lab.aws.pipelines.full_cleanup_aws --all
```

Este comando solicita:

- Borrar endpoint, endpoint config, SageMaker Model y Feature Groups si todavia existen.
- Borrar Model Packages y Model Package Group de fraude.
- Borrar objetos bajo los prefijos S3 del laboratorio.
- Borrar el stack CloudFormation, lo que elimina DynamoDB, SQS, IAM role y bucket si el stack lo creo y el bucket queda vacio.
- Borrar archivos locales generados en `data/`, `artifacts/local_outputs/`, `.env.cloud`, `__pycache__/` y `.pytest_cache/`.

Si el bucket fue creado exclusivamente para este laboratorio y CloudFormation falla porque quedan objetos, puedes vaciar completamente el bucket antes de borrar el stack:

```bash
python -m fraud_lab.aws.pipelines.full_cleanup_aws --all --empty-stack-bucket
```

Usa `--empty-stack-bucket` solo si el bucket pertenece a este laboratorio. Si el bucket es compartido, este flag puede borrar datos que no pertenecen al caso de fraude.

`--all` no activa `--empty-stack-bucket` para evitar borrar accidentalmente buckets compartidos. Tambien puedes ejecutar por partes:

```bash
python -m fraud_lab.aws.pipelines.full_cleanup_aws --delete-model-registry
python -m fraud_lab.aws.pipelines.full_cleanup_aws --delete-s3
python -m fraud_lab.aws.pipelines.full_cleanup_aws --delete-stack
python -m fraud_lab.aws.pipelines.full_cleanup_aws --delete-local
```

En Windows, algunos caches locales como `.pytest_cache/` o `__pycache__/` pueden quedar bloqueados temporalmente por la terminal, pytest o el editor. El cleanup local no debe fallar por eso: los paths bloqueados se reportan en `skipped` y se pueden borrar luego cerrando el proceso que los tenga abiertos o reejecutando:

```bash
python -m fraud_lab.aws.pipelines.full_cleanup_aws --delete-local
```

El flag `--delete-local` puede ejecutarse solo, incluso si `.env.cloud` ya fue eliminado en un intento anterior.

## Validacion local

El stdout muestra listas `deleted` y `skipped`.

## Validacion en consola AWS

Revisa:

- SageMaker Feature Store: Feature Groups en estado `Deleting` o ya ausentes.
- SageMaker Endpoints: endpoint de fraude ausente.
- SageMaker Models: modelo deployable de fraude ausente.
- SageMaker Model Registry: Model Package Group de fraude sigue existiendo.
- DynamoDB: tabla de decisiones sigue existiendo.
- SQS: cola de eventos sigue existiendo.
- S3: datos del Data Lake siguen disponibles.
