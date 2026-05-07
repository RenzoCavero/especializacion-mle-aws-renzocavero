# Instrucciones Para Codex - Tema 2

Este archivo es la fuente principal de instrucciones para cualquier tarea futura dentro de `2_ML-Data-Processing-Prep/`.

## Alcance Del Proyecto

Este directorio contiene el laboratorio del tema 2 de la especializacion:

**Procesamiento y preparacion de datos AWS - Machine Learning**

El laboratorio debe construir una solucion cloud-first en AWS para convertir datos crudos en datasets listos para entrenamiento e inferencia de Machine Learning. El caso principal recomendado es un pipeline de datos para deteccion de fraude o scoring de riesgo.

El trabajo de Codex debe mantenerse exclusivamente dentro de:

```text
2_ML-Data-Processing-Prep/
```

## Regla Estricta De Alcance

Reglas obligatorias:

- No crear archivos fuera de `2_ML-Data-Processing-Prep/`.
- No modificar archivos fuera de `2_ML-Data-Processing-Prep/`.
- No mover ni renombrar archivos existentes en `doc/`.
- No eliminar documentos fuente ubicados en `doc/`.
- Separar claramente codigo, infraestructura, datos, artefactos, documentacion y pruebas.

## Orden De Lectura Obligatorio

Antes de implementar una nueva tarea, lee en este orden:

1. `AGENTS.md`
2. `ai_context/PROJECT_CONTEXT.md`
3. `ai_context/LAB_02_SPEC.md`
4. `ai_context/AWS_ARCHITECTURE_GUIDE.md`
5. `ai_context/INFRASTRUCTURE_GUIDE.md`
6. `ai_context/COST_AND_SECURITY.md`
7. `ai_context/CODE_STYLE.md`
8. `ai_context/RUNBOOK.md`
9. `ai_context/CODE_REVIEW.md`

Si la tarea requiere contexto teorico, lee tambien:

10. `ai_context/SOURCE_SUMMARY.md`
11. Los documentos disponibles en `doc/`

## Fuente Principal Del Tema

La fuente principal del contenido teorico esta en:

```text
2_ML-Data-Processing-Prep/doc/
```

El documento inicial inspeccionado es:

```text
doc/AWS_Data_Processing_and_preparation.pdf
```

Usa estos documentos como referencia conceptual primaria para explicar preparacion de datos, data lakes, profiling, calidad, limpieza, transformacion, feature engineering, consistencia entrenamiento/inferencia, gobernanza, seguridad y lineage.

## Objetivo Del Laboratorio

El laboratorio debe mostrar como pasar desde datos crudos hasta datasets listos para entrenamiento e inferencia usando AWS real. Debe cubrir:

- Generacion o carga de datos sinteticos.
- Carga de datos crudos en Amazon S3.
- Organizacion de un data lake en capas `raw/`, `cleaned/`, `curated/`, `features/` e `inference/`.
- Catalogacion con AWS Glue Data Catalog.
- Profiling basico de datos.
- Validaciones de calidad.
- Limpieza, transformacion y feature engineering.
- Generacion de dataset de entrenamiento.
- Generacion de dataset de inferencia.
- Reutilizacion de logica de features para evitar training-serving skew.
- Reportes de profiling, calidad, lineage y dataset card.
- Logs operativos en CloudWatch.
- Despliegue, ejecucion, validacion y cleanup reproducibles.

## Ejecucion En AWS

El laboratorio debe ejecutarse en AWS. Puede incluir utilidades locales para generar datasets sinteticos, empaquetar codigo o descargar reportes, pero el pipeline objetivo de procesamiento y preparacion debe correr en servicios AWS.

Recursos AWS esperados:

- Amazon S3 para data lake y artefactos.
- AWS Glue Data Catalog para catalogacion.
- AWS Glue Job o SageMaker Processing Job para procesamiento.
- SageMaker Feature Store como componente opcional o preparado para extension.
- IAM Roles y Policies con minimo privilegio.
- CloudWatch Logs para logs operativos.
- AWS KMS opcional o SSE-S3 para cifrado.
- CloudFormation, AWS CDK o Terraform para infraestructura como codigo.

## Infraestructura

La infraestructura debe ser reproducible mediante IaC. La opcion recomendada para estudiantes es CloudFormation por simplicidad y alineacion nativa con AWS. AWS CDK tambien es aceptable si el curso prioriza desarrollo programatico. Terraform es alternativa si se decide mantener independencia multi-cloud.

Cada implementacion debe documentar:

- Herramienta IaC elegida.
- Region configurable.
- Nombre de bucket generado o pasado por parametro.
- Roles IAM y politicas minimas.
- Tags obligatorios.
- Comandos de deploy y destroy.
- Recursos que pueden generar costo.
- Estrategia de cleanup.

## Seguridad

Reglas obligatorias:

- Usar AWS CLI y/o boto3 solo con perfiles o roles IAM.
- Nunca hardcodear access keys, secret keys, session tokens ni credenciales temporales.
- No subir PII real ni datos sensibles reales.
- Usar datos sinteticos para el laboratorio.
- Bloquear acceso publico en S3.
- Aplicar principio de minimo privilegio.
- Cifrar datos en S3 con SSE-S3 o KMS cuando aplique.
- Documentar permisos requeridos.
- Mantener `.env.example` sin secretos reales.

## Control De Costos

Reglas obligatorias:

- Usar datasets pequenos.
- Usar recursos minimos para laboratorio.
- Preferir jobs efimeros.
- Evitar endpoints persistentes.
- Evitar recursos 24/7.
- Evitar SageMaker Feature Store online salvo que se indique explicitamente.
- Incluir advertencias de costo en README, runbook e infraestructura.
- Incluir comandos para revisar recursos activos.
- Incluir una forma clara de destruir recursos creados.

## Limpieza De Recursos

Todo laboratorio debe tener cleanup documentado. Como minimo:

- `make destroy-infra`
- `scripts/destroy_infra.sh`
- `scripts/destroy_infra.ps1`

Si se crean buckets con datos, la estrategia debe indicar si el stack puede vaciar el bucket automaticamente o si se requiere limpieza previa. No dejar roles, jobs, logs, buckets, crawlers o recursos de Feature Store huerfanos.

## Comandos Esperados

Comandos objetivo con Make:

```bash
make deploy-infra
make data
make upload-raw
make catalog
make profile
make quality
make process
make features
make training-dataset
make inference-dataset
make lineage
make dataset-card
make download-reports
make validate
make destroy-infra
make all-cloud
```

Scripts equivalentes esperados:

```bash
bash scripts/deploy_infra.sh
bash scripts/run_all_cloud.sh
bash scripts/destroy_infra.sh
```

```powershell
scripts/deploy_infra.ps1
scripts/run_all_cloud.ps1
scripts/destroy_infra.ps1
```

## Reglas De Calidad

- Mantener compatibilidad Windows/Linux cuando sea razonable.
- Usar Python 3.11+ o 3.12.
- Centralizar configuracion en `src/config.py`.
- Centralizar clientes AWS en `src/aws_clients.py`.
- Usar `pathlib.Path` para rutas locales.
- Usar boto3 para interaccion AWS cuando aplique.
- Usar pandas para datasets pequenos.
- Incluir manejo basico de errores y logs.
- Agregar tests con pytest para logica local y validaciones.
- Evitar notebooks como dependencia obligatoria.
- No versionar archivos pesados generados.
- Guardar cache local en `data/local_cache/`.
- Guardar outputs locales descargados en `artifacts/local_outputs/`.
- Guardar outputs reales del laboratorio en S3.

## Formato De Respuesta Al Terminar Una Tarea

Al finalizar una tarea, responder en espanol con:

- Resumen tecnico breve.
- Archivos creados o modificados.
- Recursos AWS involucrados.
- Comandos para desplegar, ejecutar, validar y destruir, cuando aplique.
- Pruebas o validaciones ejecutadas.
- Riesgos, supuestos o pendientes relevantes.

Si no se pudo ejecutar algo, indicarlo explicitamente y explicar la razon.
