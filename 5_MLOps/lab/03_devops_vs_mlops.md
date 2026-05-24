# 03 - DevOps vs MLOps

## Objetivo

Construir el contrato local que diferencia un flujo DevOps tradicional de un flujo MLOps con datos, metricas, aprobacion y monitoreo.

## Que vas a construir o validar

Vas a generar el contrato local del build pipeline sin crear recursos cloud. Este contrato permite validar que el flujo contiene los pasos MLOps esperados antes de ejecutarlo en SageMaker.

## Input del paso

- Configuracion local cargable desde `.env`.
- `S3_BUCKET_NAME` para construir URIs.
- Codigo de pipeline en `pipelines/build/`.

## Output esperado del paso

- `artifacts/local_outputs/pipeline_contract.json`.
- `artifacts/local_outputs/pipeline_definition.json`.
- Metadata del paso en `artifacts/local_outputs/lab_step_03.json`.

## Conceptos claves

DevOps tradicional controla cambios de software: codigo, infraestructura, binarios, configuracion, pruebas y despliegue. MLOps hereda todo eso, pero agrega objetos que cambian el riesgo operativo: datos, features, labels, modelos, metricas y evidencia de entrenamiento.

La diferencia mas importante es que el artefacto desplegado no es solo codigo. Un modelo depende de la distribucion de entrenamiento, del procesamiento de features, del algoritmo, de hiperparametros y de umbrales de aprobacion. Dos modelos pueden usar el mismo codigo y tener comportamientos distintos si cambian los datos.

Por eso el pipeline debe ser declarativo y auditable. El contrato `process -> train -> evaluate -> quality_gate -> register` expresa que el modelo no llega a registry sin pasar por preparacion, entrenamiento, evaluacion y validacion de metricas.

El quality gate es una barrera de promocion. En DevOps, una build puede pasar tests unitarios. En MLOps, ademas se requieren metricas como F1 o AUC, validacion de esquema y evidencia del dataset.

El monitoreo tambien cambia. Una aplicacion puede estar disponible y aun asi un modelo puede degradarse por data drift o concept drift. Esa es la razon de conectar deployment con data capture y Model Monitor.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.create_or_update_pipeline --contract-only` | `.env`, `pipelines/build/`, codigo de `processing/` y `training/` | Ninguno | `artifacts/local_outputs/pipeline_contract.json`, `artifacts/local_outputs/pipeline_definition.json` | Ninguno | Generar contrato local sin crear pipeline cloud. |
| 2 | `src.lab_runner` record | Resultado del comando anterior | Ninguno | `artifacts/local_outputs/lab_step_03.json` | Ninguno | Dejar evidencia de revision conceptual. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Local input | `pipelines/build/` | Definicion del pipeline SageMaker. |
| Local input | `processing/preprocess.py` | Script de preparacion de datos usado por el pipeline. |
| Local input | `processing/evaluate.py` | Script de evaluacion y quality gate. |
| Local input | `training/train.py`, `training/inference.py` | Codigo de entrenamiento e inferencia. |
| Local output | `artifacts/local_outputs/pipeline_contract.json` | Contrato MLOps local: process, train, evaluate, gate, register. |
| Local output | `artifacts/local_outputs/pipeline_definition.json` | Definicion local simplificada para inspeccion. |

## Prerrequisitos

- Paso 02 completado o `.env` con bucket configurado.
- No se requieren permisos AWS para el modo `--contract-only`.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 03
```

## Resultado esperado

El contrato local muestra los pasos:

```text
process, train, evaluate, quality_gate, register
```

## Validacion local

```bash
python -m src.create_or_update_pipeline --contract-only
```

Abrir:

```text
artifacts/local_outputs/pipeline_contract.json
```

## Validacion en consola AWS

No aplica. Este paso es local y previo a la creacion real del pipeline.

## Siguiente paso

Ejecutar `python -m src.lab_runner step 04` para revisar CI/CD/CT y readiness inicial.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.create_or_update_pipeline --contract-only` | Crear contrato local del pipeline sin tocar AWS. | `save_pipeline_contract` en `pipelines/build/pipeline_definition.py`, `write_metadata`. | `.env`, `src/config.py`, scripts de `processing/` y `training/`. | `artifacts/local_outputs/pipeline_contract.json`, `pipeline_upsert.json`. |

Este contrato documenta que steps existiran en el pipeline cloud: procesamiento, entrenamiento, evaluacion, condition gate y registro. Es una buena practica MLOps: antes de crear recursos, se puede revisar el contrato y detectar cambios de interfaz.

Parametros modificables:

- `PIPELINE_NAME`: nombre logico del pipeline.
- `F1_THRESHOLD`, `AUC_THRESHOLD`: umbrales del quality gate.
- Candidatos de compute: definen instancias que se usaran cuando el pipeline se cree en el paso 05.

Troubleshooting:

- Si el contrato no se escribe, revisa permisos locales sobre `artifacts/local_outputs/`.
- Si el contrato no refleja un cambio de script, confirma que editaste `pipelines/build/pipeline_definition.py` y no solo un documento.
