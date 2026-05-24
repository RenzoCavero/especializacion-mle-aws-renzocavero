# 00 - Contexto de negocio

## Objetivo

Definir el problema operativo que resuelve MLOps: convertir un modelo entrenado en un sistema gobernado, observable, trazable y recuperable.

## Que vas a construir o validar

Vas a validar el alcance del laboratorio y generar una primera evidencia local de ejecucion. Este paso no crea recursos AWS; deja claro que el objetivo no es solo desplegar un endpoint, sino operar el ciclo completo del modelo.

## Input del paso

- Repositorio con `5_MLOps/` inicializado.
- Archivo `.env` opcional.
- Documentacion de contexto en `ai_context/`.

## Output esperado del paso

- Metadata local en `artifacts/local_outputs/lab_step_00.json`.
- Comprension del flujo: build, registry, approval, deployment, monitoring, alarmas, feedback loop y cleanup.

## Conceptos claves

MLOps agrega una capa operativa alrededor de Machine Learning. En software tradicional, desplegar una version puede ser suficiente para empezar a medir latencia, errores y disponibilidad. En Machine Learning, un endpoint puede estar tecnicamente sano y aun asi producir decisiones de baja calidad si la distribucion de datos cambia, si el concepto de negocio cambia o si el modelo fue entrenado con evidencia incompleta.

El laboratorio usa el modelo como una entidad gobernada. Eso significa que cada version debe tener origen, metricas, artefactos, estado de aprobacion y una ruta controlada hacia despliegue. El Model Registry no es solo un catalogo; es el limite entre experimentacion y operacion.

La observabilidad tambien se expande. No basta con CloudWatch para CPU o errores HTTP. El flujo necesita data capture, baseline, constraints, statistics y violations para comparar trafico real contra comportamiento esperado. Esa evidencia alimenta alarmas y decisiones.

El feedback loop cierra el ciclo. Una alarma no debe disparar automaticamente una accion costosa o riesgosa. Primero se diagnostica, luego se decide: retraining, rollback, baseline update, human review o no action. Esta separacion reduce loops infinitos, costos inesperados y cambios no auditados.

La independencia del laboratorio 4 se garantiza con `standalone_mode`: datos sinteticos, modelo simple, pipeline y endpoint propios. `integrated_mode` existe para reutilizar recursos previos, pero no es obligatorio.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.lab_runner` | Documento `lab/00_contexto_negocio.md`, repo local | Ninguno | `artifacts/local_outputs/lab_step_00.json` | Ninguno | Registrar que el alcance del laboratorio fue revisado. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Documento | `lab/00_contexto_negocio.md` | Contexto, alcance y criterios del flujo MLOps. |
| Local output | `artifacts/local_outputs/lab_step_00.json` | Evidencia minima de ejecucion del paso. |

## Prerrequisitos

- Estar ubicado en la raiz de `5_MLOps/` o ejecutar comandos desde el root del laboratorio.
- Python disponible.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 00
```

Tambien puedes usar:

```bash
make step-00
```

## Resultado esperado

El comando imprime la ruta de documentacion y registra evidencia local del paso.

## Validacion local

```bash
type artifacts\local_outputs\lab_step_00.json
```

En Linux/macOS:

```bash
cat artifacts/local_outputs/lab_step_00.json
```

## Validacion en consola AWS

No aplica. Este paso no crea recursos AWS.

## Siguiente paso

Continuar con `python -m src.lab_runner step 01` para validar configuracion AWS.

## Ficha tecnica del paso

| Elemento | Detalle |
|---|---|
| Modulo ejecutado | No ejecuta un modulo cloud; `src.lab_runner` registra evidencia local. |
| Funcion relevante | `record_step(step, note)` en `src/lab_runner.py`. |
| Inputs | Lectura conceptual del caso de negocio y estructura del laboratorio. |
| Outputs locales | `artifacts/local_outputs/lab_step_00.json`. |
| Outputs AWS | Ninguno. |
| Dependencias posteriores | Todos los pasos usan este contexto para interpretar el flujo build -> deploy -> monitor -> feedback. |

Para modificar el alcance del laboratorio, actualiza primero este documento y despues alinea `src/lab_runner.py`, `.env.example` y los pasos afectados. Este paso debe seguir sin crear recursos: su objetivo es fijar el contrato conceptual antes de incurrir costos.
