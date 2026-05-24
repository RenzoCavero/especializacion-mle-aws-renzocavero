# Fraud 04 - Modelo simple en SageMaker Model Registry

## Objetivo

Crear un modelo simple de fraude, empaquetarlo como artefacto SageMaker, subirlo a S3 y registrarlo en SageMaker Model Registry como un Model Package aprobado.

Este paso no despliega el endpoint todavia. Su responsabilidad es gobierno y versionado del modelo.

## Que vas a construir o validar

Este paso construye:

- Modelo scikit-learn simple para fraude.
- Artefacto `model.tar.gz` con `model.joblib`, metadata y codigo de inferencia SageMaker.
- Artefacto `source_dir.tar.gz` con el directorio de codigo que usara el contenedor.
- Model Package Group en SageMaker Model Registry.
- Model Package con `ModelApprovalStatus=Approved`.
- Metadata local en `artifacts/local_outputs/fraud_model_registry.json`.

## Input del paso

Variables principales:

```bash
S3_BUCKET_NAME=<bucket>
FRAUD_S3_PREFIX=ml-deploy-lab/lab/fraud
FRAUD_MODEL_PACKAGE_GROUP_NAME=ml-deploy-lab-fraud-models
AWS_REGION=us-east-1
```

El modelo se entrena con datos sinteticos deterministas generados desde el contrato de features de fraude.

## Output esperado del paso

S3:

```text
s3://<bucket>/<prefix>/model-registry/artifacts/<timestamp>/model.tar.gz
s3://<bucket>/<prefix>/model-registry/source-dir/<timestamp>/source_dir.tar.gz
```

SageMaker Model Registry:

```text
Model Package Group: ml-deploy-lab-fraud-models
Model Package: arn:aws:sagemaker:<region>:<account>:model-package/...
Approval: Approved
```

Metadata local:

```text
artifacts/local_outputs/fraud_model_registry.json
```

## Archivos que definen el modelo

El modelo queda definido por tres capas de informacion:

| Capa | Donde queda | Que contiene | Para que sirve |
| --- | --- | --- | --- |
| Artefacto del modelo | `model-registry/artifacts/<timestamp>/model.tar.gz` | Pesos/modelo serializado, metadata y codigo de serving. | Es el `ModelDataUrl` del Model Package y la base para endpoint y batch. |
| Source directory | `model-registry/source-dir/<timestamp>/source_dir.tar.gz` | Directorio de codigo que el contenedor instala/usa como `SAGEMAKER_SUBMIT_DIRECTORY`. | Hace explicito el entry point que SageMaker debe importar al desplegar. |
| Model Package | SageMaker Model Registry | URI del artefacto, imagen de inferencia, content types, approval status y metadata. | Gobierna que version esta aprobada para despliegue. |

Contenido conceptual de `model.tar.gz`:

| Archivo dentro del tar | Proposito |
| --- | --- |
| `model.joblib` | Pipeline scikit-learn entrenado. Es el objeto que se carga para predecir. |
| `model_metadata.json` | Version del modelo, version de features, `feature_order` y tipo de modelo. |
| `fraud_entry.py` | Entry point principal para el contenedor SageMaker. |
| `model_fn.py` | Funcion que carga `model.joblib` desde `/opt/ml/model`. |
| `input_fn.py` | Funcion que interpreta payload JSON o CSV enviado al endpoint o Batch Transform. |
| `predict_fn.py` | Funcion que ejecuta inferencia y calcula score/decision. |
| `output_fn.py` | Funcion que serializa la respuesta como JSON. |
| `requirements.txt` | Dependencias necesarias dentro del contenedor. |
| `setup.py` | Permite instalar el paquete de inferencia dentro del contenedor. |
| `code/`, `fraud_entry/`, `inference/` | Copias organizadas del codigo para compatibilidad con el contenedor Scikit-learn de SageMaker. |

El Model Package registra principalmente:

- `Image`: imagen del contenedor Scikit-learn para la region.
- `ModelDataUrl`: S3 URI de `model.tar.gz`.
- `SupportedContentTypes`: `application/json` y `text/csv`.
- `SupportedResponseMIMETypes`: `application/json`.
- `ModelApprovalStatus`: `Approved`.
- Metadata de negocio: caso de uso, version de modelo, version de features y laboratorio.

El `source_dir_s3_uri` queda guardado en la metadata local y se usa en el despliegue del paso 05 para configurar `SAGEMAKER_SUBMIT_DIRECTORY`. En una implementacion productiva tambien podria registrarse como metadata adicional de linaje o asociarse a un pipeline de training.

## Conceptos claves

SageMaker Model Registry no es un endpoint. Es un catalogo gobernado de versiones de modelo. Permite registrar artefactos, imagen de inferencia, estado de aprobacion, metadata y linaje. Desplegar un modelo requiere un paso posterior: crear un SageMaker Model desde el Model Package y luego un Endpoint o Batch Transform Job.

El artefacto del modelo debe incluir tanto el objeto entrenado como el codigo necesario para cargarlo y servirlo. Si el `.joblib` existe pero falta `input_fn` o el entry point, el endpoint puede crearse pero fallar al arrancar el contenedor.

El `feature_order.json` del paso 02 y la metadata del modelo deben estar alineados. El modelo no recibe nombres de columnas de forma libre; recibe un vector con orden estable. Este punto evita training-serving skew.

El approval status separa registro de despliegue. Un modelo puede estar registrado pero no aprobado. En este laboratorio se usa `Approved` para que el siguiente paso pueda desplegarlo por defecto.

La imagen de inferencia no es el modelo. La imagen define el runtime; el artefacto S3 define el contenido del modelo; el Model Package une ambos en una version gobernada.

## Prerrequisitos

- Haber ejecutado `fraud-step 01`.
- Dependencias instaladas: `scikit-learn`, `joblib`, `boto3`, `sagemaker`.
- Permisos para `sagemaker:CreateModelPackageGroup`, `sagemaker:CreateModelPackage` y S3 upload.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 04
```

Comando directo equivalente:

```bash
python -m fraud_lab.aws.model_registry
```

## Resultado esperado

El comando imprime:

- `model_package_group_name`
- `model_package_arn`
- `model_artifact_s3_uri`
- `source_dir_s3_uri`
- `image_uri`
- `approval_status`

Tambien sugiere variables que puedes copiar a `.env` si quieres fijar esa version:

```bash
FRAUD_MODEL_PACKAGE_GROUP_NAME=...
FRAUD_MODEL_PACKAGE_ARN=...
FRAUD_MODEL_ARTIFACT_S3_URI=...
```

## Validacion local

Revisa:

```bash
type artifacts\local_outputs\fraud_model_registry.json
```

En Git Bash:

```bash
cat artifacts/local_outputs/fraud_model_registry.json
```

El JSON debe mostrar `model_artifact_s3_uri`, `source_dir_s3_uri`, `model_package_arn`, `image_uri` y `artifact_packaging_version`.

## Validacion en consola AWS

En SageMaker Studio o consola SageMaker:

- Ir a Model Registry.
- Buscar el Model Package Group `ml-deploy-lab-fraud-models`.
- Confirmar que existe una version con estado `Approved`.
- Abrir la version y revisar que el contenedor apunta al S3 URI bajo `model-registry/artifacts/`.
- En S3, revisar tambien el prefijo `model-registry/source-dir/`.

Model Registry no muestra necesariamente cada archivo interno del tarball. Para auditar contenido interno, descarga `model.tar.gz` desde S3 o revisa la copia local generada en `data/local_cache/fraud_model.tar.gz`.
