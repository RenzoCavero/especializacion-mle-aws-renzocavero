# 12 - Seguridad y limpieza

## Objetivo

Eliminar los recursos creados por el laboratorio y cerrar la ejecucion de forma segura.

## Que vas a construir o validar

Este paso no construye recursos nuevos. Ejecuta limpieza de:

| Recurso | Accion |
|---|---|
| SageMaker Pipeline | Eliminar `ml-training-opt-lab-pipeline` y, si existe, `ml-training-opt-lab-hpo-pipeline`. |
| Model Registry | Eliminar model packages y `churn-model-package-group`. |
| SageMaker Experiments | Eliminar Trials y Experiment. |
| Feature Store | Solicitar eliminacion de `churn-customer-features`. |
| Autopilot opcional | Detener AutoML Jobs activos si `STOP_ACTIVE_JOBS_ON_CLEANUP=true`. |
| Athena | Eliminar resultados porque estan dentro del bucket del laboratorio. |
| S3 | Vaciar el bucket del stack antes de eliminar CloudFormation. |
| CloudFormation | Eliminar stack `ml-training-opt-lab`. |

## Conceptos clave

- Cleanup: eliminacion controlada de recursos.
- Stack-owned bucket: bucket que CloudFormation reconoce como `LabBucket`.
- Guardrail: proteccion para no borrar recursos externos por accidente.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Descarga o revisa reportes antes de limpiar, si necesitas conservar evidencia:

   ```bash
   make download-reports
   ```

   O:

   ```bash
   python -m src.download_outputs
   ```

3. Confirma que estas en la cuenta y region correctas.

4. Confirma que `STACK_NAME=ml-training-opt-lab`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-12-cleanup
```

Comando individual equivalente:

```bash
make destroy-infra
```

Con Bash o Git Bash:

```bash
bash scripts/destroy_infra.sh
```

En Windows PowerShell:

```powershell
.\scripts\destroy_infra.ps1
```

Con Python:

```bash
python -m src.destroy_infra
```

Internamente:

1. `src.destroy_infra` llama a `src.cleanup_resources`.
2. Elimina recursos SageMaker segun flags de `.env`.
3. Identifica el bucket `LabBucket` del stack.
4. Vacia el bucket del stack si coincide con `S3_BUCKET_NAME`.
5. Solicita eliminacion del stack CloudFormation.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper Bash para cleanup cloud | `scripts/destroy_infra.sh` |
| Wrapper PowerShell para cleanup cloud | `scripts/destroy_infra.ps1` |
| Modulo principal de cleanup cloud | `src/destroy_infra.py` |
| Modulo que elimina recursos SageMaker auxiliares | `src/cleanup_resources.py` |
| Wrapper Bash para cleanup local | `scripts/clean_local_outputs.sh` |
| Wrapper PowerShell para cleanup local | `scripts/clean_local_outputs.ps1` |
| Modulo de cleanup local | `src/clean_local_outputs.py` |

## Scripts y parametros principales

| Necesidad | Archivo |
|---|---|
| Cambiar orden de limpieza cloud | `src/destroy_infra.py` |
| Cambiar que recursos SageMaker se eliminan | `src/cleanup_resources.py` |
| Cambiar que archivos locales se borran | `src/clean_local_outputs.py` |
| Cambiar flags de cleanup | `.env`, `.env.example`, `src/config.py` |
| Cambiar wrappers Bash/PowerShell | `scripts/destroy_infra.sh`, `scripts/destroy_infra.ps1`, `scripts/clean_local_outputs.sh`, `scripts/clean_local_outputs.ps1` |
| Ver workflow completo | `lab/14_workflow_and_scripts_reference.md` |

## Limpieza de outputs locales

La limpieza de AWS elimina recursos cloud. Si tambien quieres borrar artefactos locales generados por el laboratorio, usa el script local-only:

```bash
make clean-local-outputs
```

Con Bash o Git Bash:

```bash
bash scripts/clean_local_outputs.sh
```

En Windows PowerShell:

```powershell
.\scripts\clean_local_outputs.ps1
```

Con Python:

```bash
python -m src.clean_local_outputs
```

Para revisar que borraria sin eliminar archivos:

```bash
python -m src.clean_local_outputs --dry-run
```

Este script elimina solo archivos locales generados por el lab:

| Ruta | Que elimina |
|---|---|
| `artifacts/local_outputs/` | Reportes, metricas, estado local, descargas y metadata generada. |
| `data/local_cache/` | Dataset raw local y archivos procesados locales. |
| `data/sample/*.csv` | Muestra CSV generada. |
| `.env.cloud` | Outputs locales de CloudFormation. |

No elimina `.env`, `.env.example`, codigo fuente ni recursos AWS. Si borras `.env.cloud` y quieres seguir ejecutando pasos cloud, vuelve a ejecutar `python -m src.deploy_infra` o `python -m src.fetch_stack_outputs` para regenerarlo.

## Resultado esperado

La terminal debe mostrar mensajes de eliminacion como:

- `Deleted Pipeline`.
- `Deleted Model Package`.
- `Deleted Model Package Group`.
- `Deleted Trial`.
- `Deleted Experiment`.
- `Requested deletion of Feature Group`.
- `Emptying stack-owned S3 bucket`.
- `CloudFormation stack deleted`.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a CloudFormation > Stacks.
3. Busca `ml-training-opt-lab`.
4. Confirma que desaparecio o aparece como `DELETE_COMPLETE` en historial.
5. Ve a Amazon S3 y confirma que el bucket del laboratorio ya no existe.
6. Ve a Amazon SageMaker > Feature Store y confirma que `churn-customer-features` no aparece.
7. Ve a Amazon SageMaker > Pipelines y confirma que `ml-training-opt-lab-pipeline` y `ml-training-opt-lab-hpo-pipeline` no aparecen.
8. Ve a Amazon SageMaker > Inference > Model Registry y confirma que `churn-model-package-group` no aparece.
9. Ve a Amazon SageMaker > Experiments and trials y confirma que `ml-training-opt-lab-experiment` no aparece.
10. Si ejecutaste Autopilot, ve a SageMaker Autopilot o AutoML y confirma que no haya jobs activos con prefijo del laboratorio.
11. Ve a Amazon SageMaker > Inference > Endpoints y confirma que no hay endpoints con prefijo del laboratorio.
12. Ve a IAM > Roles y confirma que el rol creado por el stack ya no aparece.
13. Revisa CloudWatch Logs si necesitas validar retencion o eliminar logs manuales.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| Stack queda en `DELETE_FAILED` | Bucket no vacio o recurso en uso. | Abre CloudFormation > Events, revisa el recurso fallido y reejecuta cleanup. |
| Feature Group tarda en desaparecer | Eliminacion asincrona. | Espera unos minutos y vuelve a validar. |
| AutoML Job sigue corriendo | Se ejecuto el demo opcional de Autopilot y no termino. | Activa `STOP_ACTIVE_JOBS_ON_CLEANUP=true` antes de cleanup o detenlo desde SageMaker. |
| `AccessDenied` al limpiar | Profile sin permisos de delete. | Revisa permisos para SageMaker, S3, CloudFormation e IAM. |
| Hay objetos S3 restantes | Bucket externo o mismatch con `S3_BUCKET_NAME`. | Verifica que el bucket pertenece al stack antes de borrar manualmente. |

## Buenas practicas de seguridad

1. No hardcodees credenciales.
2. No commitees `.env` ni `.env.cloud`.
3. No uses datos personales reales en este laboratorio.
4. No borres buckets externos sin verificar propiedad.
5. Revisa la region antes de limpiar.

## Limpieza manual, si aplica

Si queda un recurso no eliminado:

1. Confirma que el nombre tiene prefijo `ml-training-opt-lab`.
2. Revisa si pertenece al stack o fue creado manualmente.
3. Eliminalo desde consola solo si estas seguro de que pertenece al laboratorio.
4. Vuelve a ejecutar `python -m src.destroy_infra` para completar CloudFormation.
