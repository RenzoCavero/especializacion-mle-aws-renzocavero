# 11 - Optimizacion de costos y revision de recursos

## Objetivo

Revisar recursos activos y entender donde se generan costos en el laboratorio.

## Que vas a construir o validar

Vas a generar un reporte local:

```text
artifacts/local_outputs/cost_and_resource_check.json
```

El reporte consulta:

| Recurso | Que valida |
|---|---|
| Processing Jobs | Jobs `InProgress` con prefijo del laboratorio. |
| Training Jobs | Jobs `InProgress` con prefijo del laboratorio. |
| HPO Jobs | Tuning Jobs `InProgress` con prefijo del laboratorio. |
| Autopilot Jobs | AutoML Jobs `InProgress` si ejecutaste el demo opcional. |
| Endpoints | Que no existan endpoints persistentes del laboratorio. |
| S3 | Muestra de reportes, metricas y metadata. |
| Guardrails | Tipos de instancia, HPO max jobs y Online Store. |

## Conceptos clave

- Costo de compute: instancias usadas por Processing, Training y HPO.
- Costo de almacenamiento: S3, Offline Store y CloudWatch Logs.
- Costo de consulta: Athena cobra por datos escaneados al materializar Offline Store.
- Feature Store Online Store: puede generar costo mientras exista.
- Autopilot: puede lanzar candidatos y jobs internos, por eso se mantiene opcional.
- Endpoint persistente: recurso que seguiria cobrando si queda activo; este laboratorio no crea endpoints.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Haber ejecutado los pasos cloud que quieras revisar.

3. Tener `.env.cloud` con bucket y rol.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-11-cost
```

Con Python:

```bash
python -m src.cost_and_resource_check
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 11
```

No hay wrapper `.ps1` especifico para este paso. En Windows usa el comando Python.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general | `scripts/lab.sh step 11` |
| Modulo que consulta recursos y costos operativos | `src/cost_and_resource_check.py` |
| Archivo local generado | `artifacts/local_outputs/cost_and_resource_check.json` |

## Resultado esperado

Archivo local:

```text
artifacts/local_outputs/cost_and_resource_check.json
```

El reporte debe mostrar:

- `no_persistent_endpoints_expected: true`.
- Listas vacias o controladas para jobs activos.
- Prefijos S3 con reportes, metricas y metadata.

## Validacion local

1. Abre `cost_and_resource_check.json`.
2. Revisa `active_processing_jobs`.
3. Revisa `active_training_jobs`.
4. Revisa `active_hpo_jobs`.
5. Revisa `active_autopilot_jobs`.
6. Revisa `endpoints_with_lab_prefix`.
7. Confirma que no hay endpoints inesperados.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker > Processing > Processing jobs.
3. Filtra por `ml-training-opt-lab` y confirma que no haya jobs `InProgress` inesperados.
4. Ve a Amazon SageMaker > Training > Training jobs.
5. Filtra por `ml-training-opt-lab` y confirma que no haya jobs activos inesperados.
6. Ve a Amazon SageMaker > Training > Hyperparameter tuning jobs.
7. Confirma que no haya Tuning Jobs activos inesperados.
8. Si ejecutaste Autopilot, ve a SageMaker Autopilot o AutoML y confirma que no haya jobs activos.
9. Ve a Amazon SageMaker > Inference > Endpoints.
10. Confirma que no existan endpoints con prefijo `ml-training-opt-lab`.
11. Ve a Amazon SageMaker > Feature Store y revisa si `churn-customer-features` sigue creado.
12. Ve a Amazon Athena y revisa que no haya consultas corriendo.
13. Ve a Amazon S3 y revisa el tamano aproximado de los prefijos generados.
14. Ve a CloudWatch > Log groups y revisa logs bajo `/aws/sagemaker/`.
15. Si tienes Cost Explorer habilitado, ve a Billing and Cost Management > Cost Explorer y filtra por SageMaker, S3, Athena y region.

## Fuentes principales de costo

| Fuente | Como reducirla |
|---|---|
| Processing Jobs | Usar instancias pequenas y terminar jobs fallidos. |
| Training Jobs | Mantener dataset pequeno y usar fallbacks de instancia. |
| HPO | Reducir `HPO_MAX_JOBS` y `HPO_MAX_PARALLEL_JOBS`. |
| Athena | Consultar solo columnas necesarias y mantener datasets pequenos. |
| Autopilot opcional | Reducir `AUTOPILOT_MAX_CANDIDATES`, no usar `--wait` si solo quieres lanzar y revisar luego, detener jobs que no necesites. |
| Feature Store Online Store | Eliminar Feature Group al finalizar. |
| S3 | Limpiar bucket del laboratorio. |
| CloudWatch Logs | Configurar retencion y limpiar si aplica. |
| Pipeline executions | Evitar `make run-pipeline` si solo necesitas la definicion. |

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| Aparecen jobs `InProgress` | Ejecucion reciente o job colgado. | Espera o detenlo desde consola si corresponde. |
| Aparece un endpoint | Recurso creado manualmente fuera del flujo. | Detenlo/eliminalo si pertenece al laboratorio. |
| Cost Explorer no muestra datos | Cost Explorer no esta habilitado o hay retraso. | Usa la consola de SageMaker y S3 para validar recursos activos. |
| `ResourceLimitExceeded` en pasos anteriores | Cuota regional de SageMaker. | Ajusta tipos de instancia o solicita aumento de cuota. |

## Limpieza de recursos

Despues de revisar resultados, ejecuta el paso 12 para eliminar recursos. No dejes Feature Store, bucket S3 o recursos de SageMaker creados si ya terminaste el laboratorio.
