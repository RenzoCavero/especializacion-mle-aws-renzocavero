# Runbook

Este runbook documenta comandos operativos para el laboratorio 4. Los comandos ejecutan recursos reales en AWS cuando las variables de entorno estan completas.

## Variables esperadas en .env

```bash
LAB_MODE=standalone
# Valores posibles: standalone, integrated

AWS_PROFILE=
AWS_REGION=
PROJECT_NAME=ml-model-deployment
ENVIRONMENT=lab
RESOURCE_PREFIX=ml-deploy-lab
S3_PREFIX=ml-deploy-lab/lab
S3_BUCKET_NAME=
SAGEMAKER_EXECUTION_ROLE_ARN=
KMS_KEY_ID=

MODEL_PACKAGE_GROUP_NAME=
MODEL_PACKAGE_ARN=
MODEL_ARTIFACT_S3_URI=

FEATURE_GROUP_NAME=
OFFLINE_STORE_S3_URI=
FEATURE_CONTRACT_S3_URI=

CREATE_STANDALONE_MODEL=true
CREATE_STANDALONE_FEATURE_GROUP=true

ENDPOINT_NAME=ml-deploy-realtime-endpoint
ENDPOINT_CONFIG_NAME=ml-deploy-realtime-config
MODEL_NAME=ml-deploy-model
INSTANCE_TYPE=ml.m5.large
INITIAL_INSTANCE_COUNT=1
BATCH_INSTANCE_TYPE=ml.m5.large
BATCH_INSTANCE_COUNT=1
BATCH_JOB_PREFIX=ml-deploy-batch
BATCH_SPLIT_TYPE=Line
BATCH_STRATEGY=SingleRecord
MAX_PAYLOAD_IN_MB=6
MAX_CONCURRENT_TRANSFORMS=1
ENABLE_DATA_CAPTURE=true
ENABLE_AUTOSCALING=true
AUTOSCALING_MIN_CAPACITY=1
AUTOSCALING_MAX_CAPACITY=2
AUTOSCALING_TARGET_INVOCATIONS_PER_INSTANCE=50
REALTIME_RECORD_ID=
WAIT_FOR_BATCH=true
WAIT_FOR_ENDPOINT=true
DELETE_LAB_S3=false

FRAUD_WRITE_LAST_SEEN_FEATURES=false
FRAUD_S3_PREFIX=ml-deploy-lab/lab/fraud
FRAUD_DECISION_TABLE_NAME=
FRAUD_EVENT_QUEUE_URL=
FRAUD_EVENT_QUEUE_NAME=
FRAUD_FEATURE_GROUP_PREFIX=ml-deploy-lab-fraud
FRAUD_MODEL_PACKAGE_GROUP_NAME=ml-deploy-lab-fraud-models
FRAUD_MODEL_PACKAGE_ARN=
FRAUD_MODEL_ARTIFACT_S3_URI=
FRAUD_MODEL_NAME=ml-deploy-lab-fraud-model
FRAUD_ENDPOINT_CONFIG_NAME=ml-deploy-lab-fraud-realtime-config
FRAUD_USE_SAGEMAKER_ENDPOINT=true
FRAUD_ENDPOINT_NAME=ml-deploy-lab-fraud-realtime-endpoint
FRAUD_INSTANCE_TYPE=ml.m5.large
FRAUD_INITIAL_INSTANCE_COUNT=1
FRAUD_ENABLE_DATA_CAPTURE=true
```

## Instalacion

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Comandos Make esperados

```bash
make help
make setup
make deploy-infra
make show-config
make validate-contracts
make resolve-model
make create-model
make create-feature-store
make prepare-batch-input
make run-batch
make collect-batch-output
make reconstruct-batch-results
make create-endpoint-config
make create-endpoint
make wait-endpoint
make invoke-endpoint
make validate-online-features
make configure-data-capture
make setup-autoscaling
make check-metrics
make deployment-report
make destroy-endpoint
make cleanup-feature-store
make destroy-all
make test
make all-cloud
```

`make deploy-infra` y `make lab-01-aws-setup` despliegan CloudFormation y generan `.env.cloud` con `S3_BUCKET_NAME`, `SAGEMAKER_EXECUTION_ROLE_ARN`, `FRAUD_S3_PREFIX`, `FRAUD_DECISION_TABLE_NAME`, `FRAUD_EVENT_QUEUE_URL` y `FRAUD_EVENT_QUEUE_NAME`, siguiendo el mismo patron del laboratorio 3.

## Comandos del caso de fraude con AWS

```bash
make fraud-deploy-infra
make fraud-generate-data-aws
make fraud-raw-to-cleaned-aws
make fraud-cleaned-to-curated-aws
make fraud-curated-to-offline-features-aws
make fraud-register-model-aws
make fraud-deploy-endpoint-aws
make fraud-online-score-aws
make fraud-async-update-aws
make fraud-batch-predict-aws
make fraud-build-retraining-dataset-aws
make fraud-cleanup-feature-store-aws
make fraud-cloud-all
```

`make fraud-cloud-all` usa S3, SageMaker Feature Store, SageMaker Model Registry, SageMaker Real-Time Endpoint, DynamoDB y SQS reales. El endpoint persistente se crea en `fraud-step 05` y genera costo mientras este activo. Ejecutar `python -m src.lab_runner fraud-cleanup` al terminar.

Tambien se puede ejecutar con el mismo runner numerado:

```bash
python -m src.lab_runner fraud-list
python -m src.lab_runner fraud-step 00
python -m src.lab_runner fraud-step 01
python -m src.lab_runner fraud-step 02
python -m src.lab_runner fraud-step 03
python -m src.lab_runner fraud-step 04
python -m src.lab_runner fraud-step 05
python -m src.lab_runner fraud-step 06
python -m src.lab_runner fraud-step 07
python -m src.lab_runner fraud-step 08
python -m src.lab_runner fraud-cleanup
```

`python -m src.lab_runner step 00` pertenece a la ruta principal de SageMaker deployment. Para fraude, usar `fraud-step 00` o `step fraud-00`.

## Comandos por pasos

```bash
make lab-list
make lab-00-context
make lab-01-aws-setup
make lab-02-modes
make lab-03-model-artifact
make lab-04-batch-design
make lab-05-batch-traceability
make lab-06-run-batch
make lab-07-endpoint-design
make lab-08-request-response
make lab-09-feature-store-online
make lab-10-autoscaling
make lab-11-observability
make lab-12-cleanup
make lab-13-next-monitoring
```

Equivalentes sin Make:

```bash
python -m src.lab_runner list
python -m src.lab_runner all
python -m src.lab_runner step 06
python -m src.lab_runner cleanup
scripts/lab.sh 06
scripts/lab.ps1 06
```

## Flujo sugerido standalone

1. `make setup`
2. `make deploy-infra`
3. `make resolve-model`
4. `make create-model`
5. `make create-feature-store`
6. `make prepare-batch-input`
7. `make run-batch`
8. `make collect-batch-output`
9. `make reconstruct-batch-results`
10. `make create-endpoint-config`
11. `make create-endpoint`
12. `make wait-endpoint`
13. `make invoke-endpoint`
14. `make setup-autoscaling`
15. `make check-metrics`
16. `make deployment-report`
17. `make destroy-all`

## Flujo sugerido integrated

1. Completar variables del laboratorio 3.
2. `make resolve-model`
3. `make create-model`
4. `make prepare-batch-input`
5. `make run-batch`
6. `make reconstruct-batch-results`
7. `make create-endpoint-config`
8. `make create-endpoint`
9. `make wait-endpoint`
10. `make validate-online-features`
11. `make invoke-endpoint`
12. `make check-metrics`
13. `make deployment-report`
14. `make destroy-endpoint` o `make destroy-all`

## Troubleshooting

### AWS profile no existe

Verificar `AWS_PROFILE` y ejecutar `aws configure list-profiles`. Si se usa rol temporal, confirmar que las credenciales no expiraron.

### Permisos insuficientes

Revisar el error `AccessDenied` y comparar con `ai_context/INFRASTRUCTURE_GUIDE.md`. Validar permisos de SageMaker, S3, CloudWatch, Feature Store y Application Auto Scaling.

### Model Registry vacio

En `integrated_mode`, confirmar `MODEL_PACKAGE_GROUP_NAME` y que exista al menos un Model Package aprobado o usable. Si no existe, usar `MODEL_ARTIFACT_S3_URI` o cambiar a `standalone`.

### MODEL_ARTIFACT_S3_URI no definido

En `integrated_mode`, definir `MODEL_ARTIFACT_S3_URI` o `MODEL_PACKAGE_ARN`. En `standalone`, habilitar `CREATE_STANDALONE_MODEL=true`.

### Feature Group no existe

Confirmar `FEATURE_GROUP_NAME` y region. En `standalone_mode`, ejecutar `make create-feature-store` para crear Online Store y Offline Store desde cero.

### Online Store no devuelve registros

Validar `record_identifier_name`, `realtime_lookup_key`, valor consultado y estado del Feature Group. Confirmar que Online Store este habilitado. En standalone, ejecutar `make create-feature-store` o `python -m src.create_feature_store` para cargar registros sinteticos antes de invocar el endpoint.

### Batch Transform falla

Revisar CloudWatch Logs, formato de input, `ContentType`, `SplitType`, `BatchStrategy`, permisos S3 y compatibilidad del contenedor.

### Endpoint tarda en crear

Revisar `describe-endpoint`, eventos de SageMaker, disponibilidad de instancia y permisos para imagen/artefacto. Algunos endpoints tardan varios minutos.

### Endpoint falla con ContainerError

Revisar logs del contenedor en CloudWatch, handler de inferencia, dependencias del modelo, `model.tar.gz`, formato del payload y variables de entorno.

### Invocacion devuelve 4xx/5xx

Validar request contract, content type, endpoint name, permisos `InvokeEndpoint` y logs de contenedor.

### No aparecen logs en CloudWatch

Confirmar permisos del execution role, log group correcto y que el contenedor haya emitido logs. Revisar region.

### Autoscaling no se registra

Validar permisos de Application Auto Scaling, resource ID del variant y que el endpoint este `InService`.

### Cleanup incompleto

Ejecutar describe/list en SageMaker. Eliminar en orden: endpoint, endpoint config, model. Revisar objetos S3 creados por el laboratorio.

### Costos inesperados por endpoint activo

Listar endpoints activos y borrar los que pertenezcan al laboratorio. Confirmar tambien CloudWatch logs, S3 data capture y transform jobs recientes.
