# 09 - SageMaker Model Registry

## Objetivo

Registrar el modelo seleccionado en SageMaker Model Registry como una version gobernada y lista para aprobacion.

## Que vas a construir o validar

Vas a crear o reutilizar:

```text
MODEL_PACKAGE_GROUP_NAME=churn-model-package-group
```

Y registrar una version de modelo con estado:

```text
PendingManualApproval
```

Tambien vas a generar reportes y metadata de features.

## Conceptos clave

- Model Registry: componente de SageMaker para versionar modelos y controlar aprobaciones.
- Model Package Group: grupo que contiene versiones de un modelo.
- Model Package: version concreta del modelo con artefacto, imagen, metricas y metadata.
- Approval status: estado de aprobacion del modelo.
- Audit status: estado de gobernanza o model card visible en Studio para documentar riesgos, uso previsto, propietarios y contexto del modelo.

Estados comunes:

| Estado | Significado |
|---|---|
| `PendingManualApproval` | Registrado, pendiente de revision humana. |
| `Approved` | Aprobado para promocion o despliegue. |
| `Rejected` | No aprobado para uso posterior. |

En la vista de SageMaker Studio puedes ver dos estados relacionados, pero no son lo mismo:

| Campo en Studio | Que significa en este laboratorio |
|---|---|
| `Audit: Draft` | La informacion de gobernanza/model card aun esta en borrador. No significa que el modelo haya fallado. |
| `Deploy: Pending Approval` | El Model Package fue registrado con `ModelApprovalStatus=PendingManualApproval` y requiere aprobacion manual antes de promocionarlo. |
| `Train: Complete` | SageMaker encontro el artefacto entrenado del modelo. |
| `Evaluate: Complete` | El registro tiene metricas asociadas en `ModelMetrics`. |

El script `src.model_card` genera un archivo Markdown para documentacion:

```text
artifacts/local_outputs/model_card.md
s3://<S3_BUCKET>/reports/model_card.md
```

Ese archivo no aprueba automaticamente el audit/model card dentro de Studio. Por eso es normal ver `Audit: Draft` despues del paso 09.

## Modos de inferencia registrados

El modelo queda registrado con dos modos soportados porque `src.register_model` define:

```text
SupportedRealtimeInferenceInstanceTypes = ml.m5.large
SupportedTransformInstanceTypes = ml.m5.large
```

Por eso la consola puede mostrar instancias con estos modos:

| Modo | Para que sirve |
|---|---|
| `Realtime` | Endpoint persistente para predicciones sincronas de baja latencia. |
| `Batch transform` | Jobs batch sobre archivos en S3, sin endpoint persistente. |

`Near-real-time` no aparece como una fila separada en esta tabla. En SageMaker, ese patron suele implementarse con `Asynchronous Inference`: el cliente envia o referencia un payload en S3, SageMaker encola la solicitud, procesa con un endpoint asincrono y escribe el resultado en S3. Ese modo se configura al crear el endpoint o endpoint configuration con `AsyncInferenceConfig`; no se configura en este paso del laboratorio.

Mapa practico:

| Necesidad | Opcion de SageMaker |
|---|---|
| Respuesta sincronica de baja latencia | Real-Time Endpoint |
| Predicciones masivas offline | Batch Transform |
| Solicitudes en cola, payloads grandes o procesamiento mas largo con latencia cercana a tiempo real | Asynchronous Inference |
| Trafico intermitente sin administrar capacidad fija | Serverless Inference |

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 05, 06 y 07.

3. Confirma que `run_state.json` contiene:

   - `selected_model_artifact_s3_uri`.
   - `selected_metrics_s3_uri`.
   - `objective_metric_value`.

4. Confirma que `.env` define:

   ```text
   MODEL_PACKAGE_GROUP_NAME=churn-model-package-group
   FEATURE_GROUP_NAME=churn-customer-features
   ```

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-09-model-registry
```

Con Bash o Git Bash:

```bash
bash scripts/register_best_model.sh
python -m src.training_report
python -m src.model_card
```

En Windows PowerShell:

```powershell
.\scripts\register_best_model.ps1
python -m src.training_report
python -m src.model_card
```

Con Python:

```bash
python -m src.register_model
python -m src.export_feature_metadata
python -m src.training_report
python -m src.model_card
```

Importante: `scripts/register_best_model.sh` y `.ps1` ejecutan comparacion, registro y exportacion de metadata, pero no generan `training_report.md` ni `model_card.md`. Si usas esos wrappers, ejecuta los dos comandos Python adicionales.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash | `scripts/register_best_model.sh` |
| Wrapper PowerShell | `scripts/register_best_model.ps1` |
| Modulo que registra el Model Package | `src/register_model.py` |
| Modulo que exporta contrato de features | `src/export_feature_metadata.py` |
| Modulo que genera reporte de training | `src/training_report.py` |
| Modulo que genera model card local | `src/model_card.py` |
| Codigo de inferencia empaquetado para despliegues futuros | `training/inference.py` |
| Archivo que se sube a S3 como source de inferencia | `artifacts/local_outputs/inference_source.tar.gz` |

## Resultado esperado

S3:

```text
s3://<S3_BUCKET>/code/inference_source.tar.gz
s3://<S3_BUCKET>/model_registry_metadata/feature_contract.json
s3://<S3_BUCKET>/reports/training_report.md
s3://<S3_BUCKET>/reports/model_card.md
```

Local:

```text
artifacts/local_outputs/inference_source.tar.gz
artifacts/local_outputs/feature_contract.json
artifacts/local_outputs/training_report.md
artifacts/local_outputs/model_card.md
artifacts/local_outputs/run_state.json
```

`run_state.json` debe incluir:

- `model_package_arn`.
- `model_package_group_name`.
- `model_approval_status`.
- `inference_source_s3_uri`.
- `feature_contract_s3_uri`.

## Validacion local

1. Abre `artifacts/local_outputs/feature_contract.json`.
2. Confirma `feature_group_name`, `training_features`, `inference_features` y `model_artifact_s3_uri`.
3. Abre `training_report.md`.
4. Confirma jobs, modelo seleccionado y metricas.
5. Abre `model_card.md`.
6. Confirma uso previsto, limitaciones y estado de aprobacion.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Inference > Model Registry.
3. Abre `churn-model-package-group`.
4. Abre la version creada.
5. Verifica `Approval status` = `PendingManualApproval`.
6. Si Studio muestra `Audit: Draft`, interpreta que la documentacion de gobernanza aun esta en borrador.
7. Revisa `Model data` y confirma que apunta al `model.tar.gz` seleccionado.
8. Revisa la imagen de inferencia de scikit-learn.
9. Revisa `Model metrics` y confirma que apunta al JSON de metricas.
10. Revisa `Customer metadata properties`, si la consola las muestra.
11. En la seccion de instancias soportadas, confirma que aparezcan `Realtime` y `Batch transform` para `ml.m5.large`.
12. Ve a S3 > `model_registry_metadata/` y confirma `feature_contract.json`.
13. Ve a S3 > `reports/` y confirma `training_report.md` y `model_card.md`.

## Evaluacion visible en Studio

El paso 09 registra `ModelMetrics` apuntando al JSON de metricas generado por los Processing Jobs de evaluacion. En la version del modelo deberias ver `Evaluate: Complete` si Studio puede leer esas metricas.

Si quieres agregar collaterals de evaluacion manualmente desde la UI:

1. Abre SageMaker Studio.
2. Ve a `Models` o `Registry`.
3. Abre `Churn Model Package Group`.
4. Entra a la version registrada.
5. Abre la pestana `Evaluate`.
6. Selecciona `Add` > `S3`, si la opcion esta disponible.
7. Usa una de estas rutas:

   ```text
   s3://<S3_BUCKET>/evaluation/baseline/
   s3://<S3_BUCKET>/evaluation/optimized/
   ```

Esto no es lo mismo que `Jobs > Model evaluation`. Esa seccion de Studio muestra evaluaciones administradas creadas por el servicio o por el wizard de Studio. Para este modelo tabular de `scikit-learn`, la evaluacion del lab queda trazada como Processing Job, metricas en S3 y ModelMetrics en Model Registry.

## Validacion opcional por CLI

```bash
aws sagemaker list-model-packages \
  --model-package-group-name churn-model-package-group \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `No selected model artifact found` | No se ejecuto `compare_models`. | Ejecuta `python -m src.compare_models`. |
| `No model metrics S3 URI found` | No se evaluo el modelo. | Ejecuta paso 06 y paso 07. |
| `Tags are not supported in Model Package versions` | Version anterior del codigo agregaba tags al package. | Usa la version actual de `src.register_model.py`; no modifiques docs para agregar tags a versiones. |
| Model Package Group no aparece | Region incorrecta o fallo de permisos. | Verifica `AWS_REGION` y permisos SageMaker. |
| Studio muestra `Audit: Draft` | El model card/gobernanza no fue aprobado desde la UI. | Es esperado en el laboratorio. Revisa `reports/model_card.md` y actualiza el audit manualmente si el ejercicio lo requiere. |
| No aparece `Near-real-time` como modo | SageMaker lo implementa normalmente con Asynchronous Inference, no como fila separada de esta tabla. | Documentalo como opcion futura y configuralo en el endpoint con `AsyncInferenceConfig` cuando construyas inferencia asincrona. |

## Conexion con despliegues futuros

Registrar el modelo no crea un endpoint. El Model Package deja el modelo listo para que un flujo posterior lo apruebe y lo use en Batch Transform, Real-Time Endpoint o un endpoint asincrono si el caso requiere near-real-time.
