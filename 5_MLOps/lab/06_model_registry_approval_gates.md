# 06 - Model Registry y approval gates

## Objetivo

Registrar, revisar y aprobar un modelo candidato antes de permitir despliegue.

## Que vas a construir o validar

Vas a consultar el ultimo Model Package creado por el pipeline, registrar metadata local, aprobar el candidato y resolver el ultimo modelo aprobado.

## Input del paso

- Model Package Group `mlops-model-package-group`.
- Model Package creado por el paso 05.
- Metricas de evaluacion disponibles.
- Permisos `sagemaker:ListModelPackages`, `DescribeModelPackage`, `UpdateModelPackage`.

## Output esperado del paso

- Modelo con `ModelApprovalStatus=Approved`.
- Metricas de evaluacion reflejadas como metadata visible del Model Package:
  - `metric_accuracy`
  - `metric_f1`
  - `metric_auc`
  - `quality_gate_f1_threshold`
  - `quality_gate_auc_threshold`
  - `evaluation_s3_uri`
- Metadata local:
  - `model_registry.json`
  - `model_approval.json`
  - `approved_model.json`

## Conceptos claves

Model Registry es el control de versionado operativo para modelos. Un Model Package contiene artefactos de modelo, imagen de inferencia, metricas, metadata y estado de aprobacion.

El Model Package Group agrupa versiones de una familia de modelos. En este laboratorio se usa una familia unica para mantener simple el flujo, pero en produccion podrian existir grupos por caso de uso, segmento o producto.

`PendingManualApproval` indica que un modelo fue registrado pero no esta listo para despliegue. Este estado es sano: permite que el entrenamiento sea automatico sin que el despliegue sea automatico.

`Approved` habilita la ruta de deployment. El script de deploy resuelve el ultimo modelo aprobado y bloquea despliegues si no hay candidato aprobado. Esta separacion evita que un modelo con metricas insuficientes llegue a produccion.

`Rejected` conserva evidencia historica. Rechazar no borra el modelo; deja registro de que existio un candidato y no paso criterios. Esa trazabilidad es importante para auditoria y aprendizaje.

La aprobacion no deberia basarse solo en una metrica. En ambientes reales se revisan datos, fairness, seguridad, costos, latencia, explicabilidad, drift previo y riesgos de negocio.

Las metricas de performance del pipeline se guardan primero en S3 como `evaluation.json`. Ese archivo queda asociado al Model Package mediante `ModelMetrics.ModelQuality.Statistics.S3Uri`. Dependiendo de la version de SageMaker Studio y del formato exacto del JSON, la pestana Performance puede mostrar solo el enlace al artefacto o no renderizar una tabla con las metricas arbitrarias.

Por eso este paso hace una segunda accion de gobierno: lee `evaluation.json` desde S3 y copia `accuracy`, `f1` y `auc` a `CustomerMetadataProperties` del Model Package. Esa metadata no reemplaza el artefacto oficial de evaluacion; lo complementa para que la version del modelo sea auditable por consola, CLI, scripts de approval y reportes locales.

La validacion correcta del Registry tiene dos capas:

- Artefacto de evidencia: `ModelMetrics.ModelQuality.Statistics.S3Uri` apunta al JSON completo de evaluacion en S3.
- Metadata operativa: `metric_accuracy`, `metric_f1` y `metric_auc` quedan en el Model Package para inspeccion rapida y decisiones automatizadas.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.register_model_metadata` | `pipeline_execution_status.json` si existe | Model Package Group, ultimo Model Package, `evaluation.json` en S3 | `model_registry.json` | `CustomerMetadataProperties` actualizadas en el Model Package | Leer metricas y dejarlas visibles para gobierno. |
| 2 | `src.approve_model` | `.env` y metadata del registry | Model Package mas reciente pendiente | `model_approval.json` | `ModelApprovalStatus=Approved` | Aprobar manualmente el candidato del laboratorio. |
| 3 | `src.resolve_approved_model` | `.env` | Model Package Group | `approved_model.json` | Ninguno | Resolver el ultimo modelo aprobado para despliegue. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Model Package Group | `mlops-model-package-group` | Paso 05 o infraestructura del laboratorio | Pasos 06, 07 y 16. |
| Model Package | `arn:aws:sagemaker:<region>:<account>:model-package/mlops-model-package-group/<version>` | `RegisterModel` del pipeline | Approval, deploy y batch transform. |
| Evaluacion | `s3://<bucket>/mlops-lab/lab/artifacts/evaluation/evaluation.json` | Paso 05 | `src.register_model_metadata` y auditoria. |
| Metadata de registry | `artifacts/local_outputs/model_registry.json` | `src.register_model_metadata` | Paso 14 y revision local. |
| Decision de approval | `artifacts/local_outputs/model_approval.json` | `src.approve_model` | Paso 14 y auditoria. |
| Modelo aprobado resuelto | `artifacts/local_outputs/approved_model.json` | `src.resolve_approved_model` | `src.deploy_model`, `src.run_batch_transform` y reporte final. |

## Prerrequisitos

- Paso 05 completado.
- Model Package Group existente.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 06
```

Comandos individuales:

```bash
python -m src.register_model_metadata
python -m src.approve_model
python -m src.resolve_approved_model
```

## Resultado esperado

El modelo queda aprobado y listo para despliegue controlado.

## Validacion local

```bash
type artifacts\local_outputs\approved_model.json
type artifacts\local_outputs\model_registry.json
```

En `model_registry.json` deberias ver:

```json
{
  "metrics": {
    "accuracy": 0.0,
    "f1": 0.0,
    "auc": 0.0
  },
  "visible_metrics_update": {
    "status": "updated",
    "customer_metadata": {
      "metric_f1": "...",
      "metric_auc": "...",
      "evaluation_s3_uri": "s3://..."
    }
  }
}
```

## Validacion en consola AWS

- SageMaker > Model Registry.
- Abrir `mlops-model-package-group`.
- Confirmar que la version mas reciente tiene estado `Approved`.
- En la version del modelo, revisar:
  - `ModelMetrics` o el enlace del artefacto de evaluacion en S3.
  - `Customer metadata` / `Details` para `metric_accuracy`, `metric_f1` y `metric_auc`.

Si la pestana Performance no muestra una tabla de metricas, no significa que el pipeline no haya evaluado el modelo. Verifica el `evaluation_s3_uri` y la metadata del Model Package.

Validacion por CLI:

```bash
aws sagemaker describe-model-package ^
  --model-package-name <MODEL_PACKAGE_ARN> ^
  --query "{Approval:ModelApprovalStatus, Metrics:CustomerMetadataProperties, Evaluation:ModelMetrics.ModelQuality.Statistics.S3Uri}" ^
  --profile <AWS_PROFILE> ^
  --region <AWS_REGION>
```

## Rechazo manual

Para rechazar:

```bash
python -m src.reject_model --reason "Metricas insuficientes para despliegue"
```

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.register_model_metadata` | Localizar el Model Package mas reciente y espejar metricas visibles. | `latest_model_package`, `extract_evaluation_metrics`, `metadata_from_metrics`. | `pipeline_execution_status.json`, `evaluation.json` en S3. | `model_registry.json`, metadata en Model Package. |
| `src.approve_model` | Cambiar estado a `Approved` con guardrails basicos. | `_candidate_arn`, `_has_basic_metrics`, `approve`. | `model_registry.json`, Model Package. | `model_approval.json`, estado del Model Package. |
| `src.resolve_approved_model` | Resolver artefacto e imagen del ultimo modelo aprobado. | `resolve_approved_model`. | Model Registry. | `approved_model.json`. |
| `src.reject_model` | Ruta opcional para rechazo manual. | `reject`. | ARN explicito o metadata local. | `model_rejection.json`, estado `Rejected`. |

Parametros modificables:

- `MODEL_PACKAGE_GROUP_NAME`: grupo donde se buscan versiones.
- `F1_THRESHOLD`, `AUC_THRESHOLD`: no aprueban por si solos, pero quedan como contexto del gate.
- `--override` en `src.approve_model`: permite aprobar aunque falte metadata basica; usar solo con justificacion.

Validacion profunda:

```bash
type artifacts\local_outputs\model_registry.json
type artifacts\local_outputs\model_approval.json
type artifacts\local_outputs\approved_model.json
```

Si `resolve_approved_model` no encuentra modelo aprobado, confirma que el paso 05 registro una version y que `src.approve_model` actualizo el estado correcto.
