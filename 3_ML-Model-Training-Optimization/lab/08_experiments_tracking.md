# 08 - Tracking con SageMaker Experiments

## Objetivo

Revisar la trazabilidad de los jobs del laboratorio con SageMaker Experiments.

## Que vas a construir o validar

El laboratorio crea o reutiliza el Experiment:

```text
ml-training-opt-lab-experiment
```

Y Trials como:

| Trial | Que agrupa |
|---|---|
| `ml-training-opt-lab-data-processing` | Processing Job de preparacion. |
| `ml-training-opt-lab-baseline-trial` | Training Job baseline. |
| `ml-training-opt-lab-baseline-evaluation` | Evaluacion baseline. |
| `ml-training-opt-lab-hpo-trial` | HPO. |
| `ml-training-opt-lab-optimized-evaluation` | Evaluacion optimized. |

## Conceptos clave

- Experiment: contenedor logico para ejecuciones relacionadas.
- Trial: agrupacion de una ejecucion o familia de ejecuciones.
- Trial Component o Run: metadata asociada a jobs, parametros, metricas y artefactos.
- Lineage: evidencia que conecta datos, codigo, entrenamiento, metricas y modelo.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa al menos los pasos 04, 05, 06 y 07.

3. Confirma que `run_state.json` contiene nombres de jobs.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-08-experiments
```

Con Python:

```bash
python -m src.show_experiment_tracking
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 08
```

No hay wrapper `.ps1` especifico para este paso. En Windows usa el comando Python.

Internamente, `src.show_experiment_tracking` consulta SageMaker y escribe un resumen local.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general | `scripts/lab.sh step 08` |
| Modulo que consulta Experiments | `src/show_experiment_tracking.py` |
| Helper que crea Experiment y Trials durante pasos previos | `src/experiments.py` |
| Archivo local generado | `artifacts/local_outputs/experiment_tracking_report.json` |

## Resultado esperado

Archivo local:

```text
artifacts/local_outputs/experiment_tracking_report.json
```

El reporte debe incluir:

- `experiment_name`.
- `tracked_jobs_from_state`.
- Lista de `trials`.

## Validacion local

1. Abre `artifacts/local_outputs/experiment_tracking_report.json`.
2. Confirma que `experiment_name` sea `ml-training-opt-lab-experiment`.
3. Revisa que aparezcan los jobs ejecutados.
4. Confirma que los Trials coincidan con los pasos realizados.

## Validacion en la consola AWS

La ruta puede variar segun la consola disponible.

Opcion 1:

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Experiments and trials.
3. Busca `ml-training-opt-lab-experiment`.
4. Abre el Experiment.
5. Revisa los Trials creados.
6. Abre cada Trial y revisa los componentes asociados.

Opcion 2, si usas SageMaker Studio:

1. Abre Amazon SageMaker Studio.
2. Ve a Experiments.
3. Busca `ml-training-opt-lab-experiment`.
4. Compara runs, parametros y metricas.

## Validacion opcional por CLI

```bash
aws sagemaker list-experiments --profile <AWS_PROFILE> --region <AWS_REGION>
aws sagemaker list-trials --experiment-name ml-training-opt-lab-experiment --profile <AWS_PROFILE> --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| Experiment no aparece | No se ejecutaron jobs que crean experiment config. | Ejecuta pasos 04 a 07. |
| Reporte local muestra warning | El usuario no tiene permisos o el Experiment no existe. | Revisa permisos SageMaker y region. |
| Trials aparecen pero sin todos los jobs | Ejecutaste solo parte del laboratorio. | Completa los pasos anteriores o revisa `run_state.json`. |

## Conexion con Model Registry

Antes de registrar un modelo, debes poder explicar que job lo produjo, con que datos se entreno y que metricas obtuvo. Experiments aporta esa trazabilidad.
