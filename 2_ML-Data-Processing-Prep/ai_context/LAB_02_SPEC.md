# Especificacion Del Laboratorio 02

## Tema

Procesamiento y preparacion de datos AWS - Machine Learning

## Objetivo Del Laboratorio

Construir una solucion cloud-first en AWS para procesamiento y preparacion de datos para Machine Learning.

El laboratorio debe mostrar como pasar desde datos crudos hasta datasets listos para entrenamiento e inferencia usando servicios AWS reales y recursos provisionados de forma reproducible. La ejecucion objetivo debe ocurrir en AWS, con utilidades locales solo para preparacion, empaquetado, datos sinteticos o descarga de reportes.

## Caso Practico Principal

Pipeline de datos para deteccion de fraude o scoring de riesgo.

El caso debe representar fuentes transaccionales y de clientes, por ejemplo:

- Transacciones con monto, comercio, canal, pais, timestamp y resultado.
- Clientes con antiguedad, segmento, region, comportamiento historico y senales de riesgo.
- Etiquetas sinteticas de fraude o riesgo para entrenamiento supervisado.
- Registros recientes sin etiqueta para inferencia.

## Flujo Funcional

El flujo debe cubrir:

1. Definir el problema de negocio.
2. Identificar fuentes de datos transaccionales y de clientes.
3. Generar o cargar datasets sinteticos.
4. Subir datos crudos a Amazon S3.
5. Organizar el data lake en capas `raw`, `cleaned`, `curated`, `features` e `inference`.
6. Catalogar datos con AWS Glue Data Catalog.
7. Ejecutar profiling basico de datos.
8. Ejecutar validaciones de calidad.
9. Limpiar datos.
10. Transformar datos.
11. Crear features.
12. Generar dataset de entrenamiento.
13. Generar dataset de inferencia.
14. Reutilizar logica de features para evitar training-serving skew.
15. Guardar artefactos y reportes en S3.
16. Generar documentacion de lineage.
17. Generar dataset card.
18. Monitorear ejecucion con CloudWatch Logs.
19. Documentar equivalencia conceptual con AWS.
20. Ejecutar cleanup de recursos creados.

## Servicios AWS Esperados

- Amazon S3 para data lake y artefactos.
- AWS Glue Data Catalog para catalogacion.
- AWS Glue Job o SageMaker Processing Job para procesamiento.
- SageMaker Feature Store como componente opcional o preparado para extension.
- IAM Roles y Policies con minimo privilegio.
- CloudWatch Logs para logs operativos.
- AWS KMS opcional para cifrado.
- CloudFormation, AWS CDK o Terraform para infraestructura como codigo.

## Preferencia De Infraestructura

Opcion recomendada para estudiantes:

- AWS CloudFormation, por simplicidad operativa y alineacion nativa con AWS.

Opcion tambien valida:

- AWS CDK, si el laboratorio busca que estudiantes definan infraestructura con codigo Python o TypeScript.

Opcion alternativa:

- Terraform, si el repositorio de la especializacion decide mantener independencia multi-cloud.

La eleccion final debe quedar documentada en `ai_context/INFRASTRUCTURE_GUIDE.md` y en `infra/README.md`.

## Estructura Final Esperada

```text
2_ML-Data-Processing-Prep/
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- .env.example
|-- Makefile
|-- doc/
|-- lab/
|-- src/
|-- scripts/
|-- infra/
|-- data/
|   |-- sample/
|   `-- local_cache/
|-- artifacts/
|   `-- local_outputs/
`-- tests/
```

## Estructura AWS Esperada En S3

```text
s3://<bucket-name>/
|-- raw/
|-- cleaned/
|-- curated/
|-- features/
|-- inference/
|-- profiles/
|-- quality/
|-- lineage/
|-- reports/
`-- logs/
```

## Scripts Python Esperados

- `src/config.py`
- `src/generate_sample_data.py`
- `src/upload_raw_data.py`
- `src/data_profiling.py`
- `src/data_quality.py`
- `src/clean_data.py`
- `src/transform_data.py`
- `src/feature_engineering.py`
- `src/build_training_dataset.py`
- `src/build_inference_dataset.py`
- `src/lineage_report.py`
- `src/dataset_card.py`
- `src/aws_clients.py`

## Infraestructura Esperada

- `infra/README.md`
- `infra/cloudformation/template.yaml` o `infra/cdk/` o `infra/terraform/`
- `infra/parameters.example.json` o equivalente
- `scripts/deploy_infra.sh`
- `scripts/deploy_infra.ps1`
- `scripts/destroy_infra.sh`
- `scripts/destroy_infra.ps1`

## Scripts De Ejecucion Esperados

- `scripts/run_all_cloud.sh`
- `scripts/run_all_cloud.ps1`
- `scripts/upload_sample_data.sh`
- `scripts/upload_sample_data.ps1`
- `scripts/run_processing_job.sh`
- `scripts/run_processing_job.ps1`
- `scripts/download_reports.sh`
- `scripts/download_reports.ps1`

## Documentacion Esperada

- `README.md`
- `lab/README.md`
- `lab/00_contexto_negocio.md`
- `lab/01_aws_setup.md`
- `lab/02_data_lake_s3.md`
- `lab/03_glue_catalog.md`
- `lab/04_data_quality_profiling.md`
- `lab/05_processing_jobs.md`
- `lab/06_feature_engineering.md`
- `lab/07_training_serving_consistency.md`
- `lab/08_governance_lineage.md`
- `lab/09_cost_security_cleanup.md`

## Criterios De Aceptacion

- Se puede desplegar la infraestructura con un comando documentado.
- Se crea un bucket S3 o se usa uno existente configurado por parametro.
- Se crean roles IAM necesarios con minimo privilegio.
- Se suben datos sinteticos a S3 `raw/`.
- Se ejecuta un pipeline de procesamiento en AWS.
- Se generan datasets `cleaned`, `curated`, `features` e `inference` en S3.
- Se genera profiling.
- Se genera reporte de calidad.
- Se genera reporte de lineage.
- Se genera dataset card.
- Se guardan logs operativos en CloudWatch.
- Se puede descargar una copia local de reportes.
- Se puede destruir la infraestructura creada.
- No hay credenciales reales en el repositorio.
- No se crean archivos fuera de `2_ML-Data-Processing-Prep/`.
- La documentacion explica la relacion con AWS Glue, SageMaker Processing, SageMaker Data Wrangler, SageMaker Feature Store, Amazon S3, IAM, KMS, CloudWatch y lineage.
