# Lab 03 - AWS Model Training and Optimization

Laboratorio cloud-first para entrenar, evaluar, optimizar y registrar un modelo de churn con Amazon SageMaker.

## Arquitectura

El flujo usa:

- Amazon S3 para datos, codigo, metricas, reportes y artefactos.
- SageMaker Feature Store con Online Store y Offline Store.
- SageMaker Processing Jobs para preparacion y evaluacion reproducibles.
- SageMaker Training Jobs para baseline training.
- SageMaker Automatic Model Tuning para HPO.
- SageMaker Experiments para tracking.
- SageMaker Model Registry para registrar el mejor modelo.
- SageMaker Pipelines como base process/train/evaluate/register.
- IAM y CloudWatch Logs.

No se crean endpoints persistentes en este laboratorio.

## Prerrequisitos

- Cuenta AWS.
- AWS CLI configurado con un profile.
- Python 3.11+ o 3.12.
- Permisos para CloudFormation, S3, SageMaker, IAM PassRole y CloudWatch Logs.

## Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

PowerShell:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Edita `.env` con `AWS_PROFILE` y `AWS_REGION`.

## Ejecutar todo el laboratorio

```bash
make all-cloud
```

Sin `make`, puedes usar Python:

```bash
python -m src.lab_runner all
```

O Bash:

```bash
bash scripts/lab.sh all
```

En Windows sin `make`, tambien puedes usar:

```powershell
scripts\run_all_cloud.ps1
```

`make all-cloud` despliega infraestructura, genera datos sinteticos, crea Feature Store, ingiere features, prepara datasets con Processing Job, entrena baseline, ejecuta HPO, evalua, compara, registra el modelo, exporta contrato de features, genera reportes y valida recursos.

## Ejecutar por pasos para clase

Usa estos comandos para ensenar el laboratorio en paralelo con el PDF:

```bash
make lab-00-context
make lab-01-aws-setup
make lab-02-training-data
make lab-03-feature-store
make lab-04-processing
make lab-05-training
make lab-06-evaluation
make lab-07-hpo
make lab-08-experiments
make lab-09-model-registry
make lab-10-pipeline
make lab-11-cost
make lab-13-next-labs
```

Equivalentes con Python:

```bash
python -m src.lab_runner list
python -m src.lab_runner step 00
python -m src.lab_runner step 01
python -m src.lab_runner step 02
python -m src.lab_runner step 03
python -m src.lab_runner step 04
python -m src.lab_runner step 05
python -m src.lab_runner step 06
python -m src.lab_runner step 07
python -m src.lab_runner step 08
python -m src.lab_runner step 09
python -m src.lab_runner step 10
python -m src.lab_runner step 11
python -m src.lab_runner step 13
```

Equivalentes con Bash:

```bash
bash scripts/lab.sh list
bash scripts/lab.sh 00
bash scripts/lab.sh 01
bash scripts/lab.sh 02
bash scripts/lab.sh 03
bash scripts/lab.sh 04
bash scripts/lab.sh 05
bash scripts/lab.sh 06
bash scripts/lab.sh 07
bash scripts/lab.sh 08
bash scripts/lab.sh 09
bash scripts/lab.sh 10
bash scripts/lab.sh 11
bash scripts/lab.sh 13
```

El cleanup queda separado:

```bash
DELETE_S3_OBJECTS_ON_CLEANUP=true make lab-12-cleanup
DELETE_S3_OBJECTS_ON_CLEANUP=true python -m src.lab_runner cleanup
DELETE_S3_OBJECTS_ON_CLEANUP=true bash scripts/lab.sh cleanup
```

Cada paso tiene una guia en `lab/` con teoria, servicio AWS, comando, outputs y preguntas para estudiantes.

## Validar Feature Store

```bash
make validate-online-store
make query-offline-store
```

Tambien puedes usar AWS CLI:

```bash
aws sagemaker describe-feature-group --feature-group-name churn-customer-features --profile <profile> --region <region>
```

La salida local de `GetRecord` queda en:

```text
artifacts/local_outputs/online_store_get_record.json
```

## Validar Processing Job

```bash
make processing
```

Revisa el job en SageMaker Processing Jobs y los outputs en:

```text
s3://<bucket>/input/train/train.csv
s3://<bucket>/input/validation/validation.csv
s3://<bucket>/input/test/test.csv
s3://<bucket>/processing/output/metadata/preprocessing_metadata.json
```

## Revisar outputs en S3

```bash
aws s3 ls s3://<bucket-name>/ --recursive --profile <profile> --region <region>
```

Prefijos importantes:

- `raw/`
- `feature-store-offline/`
- `input/train/`
- `input/validation/`
- `input/test/`
- `output/baseline/`
- `output/hpo/`
- `output/best_model/`
- `evaluation/`
- `metrics/`
- `reports/`
- `model_registry_metadata/`

## Revisar logs en CloudWatch

Busca log groups de SageMaker en CloudWatch Logs:

- `/aws/sagemaker/ProcessingJobs`
- `/aws/sagemaker/TrainingJobs`

Los HPO trials aparecen como Training Jobs individuales.

## Revisar Experiments y Model Registry

Experiments:

```bash
aws sagemaker list-experiments --profile <profile> --region <region>
```

Model Registry:

```bash
aws sagemaker list-model-packages \
  --model-package-group-name churn-model-package-group \
  --profile <profile> \
  --region <region>
```

El modelo queda en estado `PendingManualApproval`.

## Contrato para futuros laboratorios

El contrato de features se guarda en:

```text
artifacts/local_outputs/feature_contract.json
s3://<bucket-name>/model_registry_metadata/feature_contract.json
```

El tema 4 debe usar el Offline Store o datasets derivados para Batch Transform. El tema 5 debe consultar el Online Store por `customer_id` antes de invocar un endpoint real-time.

## Cleanup

Para destruir recursos:

```bash
DELETE_S3_OBJECTS_ON_CLEANUP=true make destroy-infra
```

PowerShell:

```powershell
$env:DELETE_S3_OBJECTS_ON_CLEANUP="true"
scripts\destroy_infra.ps1
```

El cleanup elimina Feature Group, Pipeline, Model Registry, Experiments y objetos S3 si `DELETE_S3_OBJECTS_ON_CLEANUP=true`.

## Riesgos de costo

- Feature Store Online Store puede generar costo.
- Offline Store persiste datos en S3.
- Processing, Training y HPO usan instancias SageMaker.
- HPO ejecuta multiples Training Jobs.
- CloudWatch Logs y S3 acumulan almacenamiento.

Usa datasets pequenos, HPO limitado y cleanup al terminar.
