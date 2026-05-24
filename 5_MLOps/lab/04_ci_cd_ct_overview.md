# 04 - CI/CD/CT overview

## Objetivo

Validar los controles de CI/CD/CT que sostienen el flujo MLOps antes de ejecutar el pipeline cloud completo.

## Que vas a construir o validar

Vas a generar un readiness check inicial. Este archivo permite ver que componentes ya tienen evidencia local y cuales siguen pendientes.

## Input del paso

- Metadata producida por pasos anteriores.
- Configuracion local.
- Contrato de pipeline si el paso 03 fue ejecutado.

## Output esperado del paso

- `artifacts/local_outputs/readiness_check.json`.
- `artifacts/local_outputs/readiness_check.md`.

## Conceptos claves

CI en Machine Learning no se limita a linting o unit tests. Debe validar codigo, dependencias, schemas de datos, contratos de features, serializacion de modelos y compatibilidad de inferencia. Un cambio de schema puede romper produccion aunque el codigo compile.

CD en MLOps no deberia desplegar cualquier artefacto recien entrenado. La promocion debe pasar por Model Registry y approval status. Esto desacopla entrenamiento de despliegue: el pipeline puede registrar candidatos, pero solo modelos aprobados llegan a endpoint.

CT significa Continuous Training, pero no debe confundirse con entrenamiento automatico sin control. CT es la capacidad de reentrenar cuando hay nueva evidencia: nuevos datos, ground truth, degradacion de metricas o drift confirmado. En este laboratorio, `ENABLE_AUTOMATIC_RETRAINING=false` evita que una alarma genere costos o cambios sin aprobacion explicita.

Los readiness checks son una forma liviana de gobernanza. No reemplazan auditoria empresarial, pero documentan si existen datos, pipeline, registry, aprobacion, endpoint, monitoreo, alarmas, feedback loop y cleanup.

Un pipeline MLOps confiable debe dejar evidencia en cada etapa. Sin evidencia, no hay base para rollback, baseline update o human review.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.readiness_check` | Metadata existente en `artifacts/local_outputs/`, `.env` | Ninguno | `artifacts/local_outputs/readiness_check.json`, `artifacts/local_outputs/readiness_check.md` | Ninguno | Consolidar que evidencia existe y que bloques siguen pendientes. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Local input | `artifacts/local_outputs/*.json` | Evidencia generada por pasos anteriores. |
| Local output | `artifacts/local_outputs/readiness_check.json` | Estado estructurado por bloque: datos, pipeline, registry, deployment, monitoring, etc. |
| Local output | `artifacts/local_outputs/readiness_check.md` | Resumen legible del readiness check. |

## Prerrequisitos

- Paso 03 recomendado.
- Python y dependencias instaladas.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 04
```

## Resultado esperado

Se genera un checklist con estados `ready`, `pending` o `documented`.

## Validacion local

```bash
type artifacts\local_outputs\readiness_check.md
```

## Validacion en consola AWS

No aplica directamente. Este paso valida evidencia local.

## Siguiente paso

Ejecutar `python -m src.lab_runner step 05` para crear y ejecutar SageMaker Pipelines.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.readiness_check` | Revisar evidencia local existente y clasificar cada dominio del laboratorio. | `run_readiness_check`, `read_metadata`. | `artifacts/local_outputs/*.json`. | stdout JSON con estados por dominio. |

El readiness inicial normalmente muestra muchos dominios en `pending`; eso es correcto antes de ejecutar build, deployment y monitoring. El valor didactico esta en entender que MLOps no se valida por un unico job exitoso, sino por evidencia acumulada.

Dominios revisados:

- Datos: `data_generation`, `data_upload`.
- Pipeline: `pipeline_definition`, `pipeline_execution`.
- Registry y approval.
- Deployment y smoke test.
- Monitoring, drift, model quality, alarmas y feedback loop.
- Seguridad, costos y documentacion.

Troubleshooting:

- Si esperabas `ready` y aparece `pending`, busca el metadata indicado en `artifacts/local_outputs/`.
- Si la metadata existe pero el estado no cambia, revisa que el nombre del archivo coincida con el esperado por `src/readiness_check.py`.
