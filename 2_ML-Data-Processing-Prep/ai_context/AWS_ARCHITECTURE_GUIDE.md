# Guia De Arquitectura AWS

## Arquitectura Conceptual

El laboratorio implementa una arquitectura cloud-first para preparar datos de Machine Learning en AWS. La arquitectura debe ser simple para estudiantes, pero suficientemente realista para conectar con proyectos productivos.

## Tabla De Equivalencias

| Componente del laboratorio | Servicio AWS |
|---|---|
| Data lake | Amazon S3 |
| `raw/` | S3 raw zone |
| `cleaned/` | S3 cleaned zone |
| `curated/` | S3 curated zone |
| `features/` | S3 features zone / SageMaker Feature Store offline store |
| `inference/` | S3 inference dataset |
| Catalogo de datos | AWS Glue Data Catalog |
| Descubrimiento automatico de esquemas | AWS Glue Crawler |
| Profiling de datos | SageMaker Processing / AWS Glue |
| Validaciones de calidad | AWS Glue Data Quality / scripts en SageMaker Processing |
| Estadisticas de columnas | AWS Glue Data Catalog Column Statistics |
| Consulta SQL exploratoria | Amazon Athena |
| Limpieza y transformacion | AWS Glue Job / SageMaker Processing |
| Feature engineering | SageMaker Processing / Feature Store |
| Reportes y artefactos | Amazon S3 |
| Logs | Amazon CloudWatch Logs |
| Roles y permisos | AWS IAM |
| Cifrado | AWS KMS / SSE-S3 |
| Auditoria futura | AWS CloudTrail |
| Orquestacion futura | SageMaker Pipelines / Step Functions / EventBridge |
| Infraestructura | CloudFormation / CDK / Terraform |

## Flujo Logico

1. Usuario ejecuta despliegue de infraestructura.
2. Se crea bucket S3, roles IAM, logs y recursos de procesamiento.
3. Se generan datos sinteticos localmente o en AWS.
4. Se suben datos a S3 `raw/`.
5. Se cataloga o registra metadata con Glue.
6. Se ejecuta procesamiento con Glue Job o SageMaker Processing.
7. Se escriben salidas en `cleaned/`, `curated/`, `features/` e `inference/`.
8. Se generan reportes en `profiles/`, `quality/`, `lineage/` y `reports/`.
9. Opcionalmente se ejecutan Glue Crawler, Glue Data Quality, Column Statistics y consultas Athena para conectar el pipeline con capacidades administradas de AWS.
10. Se revisan logs en CloudWatch.
11. Se ejecuta cleanup para eliminar recursos creados.

## Secuencia Pedagogica Recomendada

Para explicar el laboratorio a estudiantes, presentar primero esta secuencia conceptual:

```text
S3 raw data
-> Glue Crawler o registro explicito
-> Glue Data Catalog
-> Data Quality gate
-> Glue ETL Job
-> S3 cleaned / curated / features
-> Athena, SageMaker Training, Batch Inference o Feature Store
```

En la implementacion actual, el registro explicito de tablas es el camino principal y el crawler es demo opcional. La calidad aparece en dos niveles: reglas Python dentro del Glue Job antes de publicar datasets finales y Glue Data Quality administrado sobre `features_training` despues de crear features. En una version productiva, Glue Data Quality tambien puede ejecutarse sobre raw o cleaned antes de iniciar transformaciones costosas.

## Componentes

### Amazon S3

S3 es el data lake central. Debe contener zonas separadas para entradas, transformaciones, features, inferencia, logs y reportes. El bucket debe tener bloqueo de acceso publico y cifrado en reposo.

### AWS Glue Data Catalog

Glue Data Catalog debe registrar bases de datos y tablas asociadas a las capas del data lake. El catalogo permite que los datos sean descubribles por Glue, Athena, SageMaker y herramientas posteriores.

### AWS Glue Crawler

El crawler es una extension opcional para demostrar descubrimiento automatico de esquemas. El pipeline principal usa tablas definidas por codigo porque conoce el contrato de datos; el crawler se ejecuta bajo demanda sobre `crawler_demo/` para que el estudiante compare ambos enfoques.

### Glue Data Quality

Glue Data Quality complementa las validaciones Python del pipeline con reglas DQDL administradas por AWS. En este laboratorio se usa como demo opcional sobre `features_training`, despues de generar el dataset de entrenamiento.

### Glue Data Catalog Column Statistics

Column Statistics permite guardar estadisticas administradas en el catalogo para columnas seleccionadas. Sirve para exploracion y optimizacion de consultas, pero no reemplaza el profiling ML escrito en `profiles/profile.json`.

### Amazon Athena

Athena permite consultar las tablas del Glue Data Catalog con SQL desde la consola AWS. El laboratorio documenta consultas basicas sobre `features_training` y `curated_customer_transactions`, usando `s3://<bucket>/athena-results/` como ubicacion de resultados.

### Glue Job O SageMaker Processing

El procesamiento puede implementarse con Glue Jobs o SageMaker Processing Jobs:

- Glue Job es natural para ETL distribuido, Spark y catalogacion integrada.
- SageMaker Processing es natural para ejecutar codigo Python de preparacion ML con entradas y salidas S3.

La implementacion actual usa AWS Glue Python Shell Job para mantener el procesamiento dentro de AWS con costo bajo y sin endpoints persistentes. SageMaker Processing sigue siendo una alternativa valida para laboratorios futuros enfocados en SageMaker.

### Orquestacion Y Multiples Jobs

El laboratorio usa un job modular. Una version productiva puede separar `raw -> cleaned`, `cleaned -> curated` y `curated -> features`, y orquestar esos jobs con Glue Workflows, Glue Triggers, Step Functions o SageMaker Pipelines.

Separar jobs es recomendable cuando existen contratos independientes, volumen alto, permisos distintos, reintentos por etapa, diferentes SLAs o gates de calidad entre capas. Mantener un solo job es preferible para laboratorios pequenos, prototipos o pipelines donde la orquestacion extra no aporta valor todavia.

### CloudWatch Logs

Los jobs deben emitir logs a CloudWatch para trazabilidad operativa. El laboratorio debe documentar como encontrar logs y diagnosticar fallas.

### IAM

Los roles deben seguir minimo privilegio. El rol de procesamiento solo debe acceder al bucket/prefix del laboratorio, logs requeridos y catalogo Glue necesario.

### KMS O SSE-S3

El cifrado debe estar activo. SSE-S3 puede ser suficiente para simplicidad. KMS es opcional si se desea mostrar control de llaves.

### Feature Store

SageMaker Feature Store puede ser opcional para controlar costos. La capa `features/` debe estar disenada como equivalente conceptual del offline store y permitir una extension futura.

## Principios

- Cloud-first: la preparacion principal se ejecuta en AWS.
- Infraestructura reproducible: deploy y destroy via IaC.
- Minimo privilegio: IAM acotado a recursos del laboratorio.
- Separacion por capas de datos: raw, cleaned, curated, features, inference.
- Cifrado en reposo y en transito cuando aplique.
- Logging operativo en CloudWatch.
- Cleanup obligatorio.
- Control de costos por datasets pequenos y jobs efimeros.
- Preparacion para entrenamiento, inferencia, MLOps y monitoreo.

## Extensiones Futuras

- SageMaker Pipelines para orquestar etapas.
- Step Functions para workflows mas generales.
- EventBridge para disparar procesamiento al llegar datos.
- Athena para consultas de validacion.
- Glue Data Quality para reglas declarativas.
- Glue Data Catalog Column Statistics para optimizar consultas catalogadas.
- SageMaker Feature Store online para inferencia real-time, solo si se controla costo.
- CloudTrail y Lake Formation para auditoria y gobernanza avanzada.
