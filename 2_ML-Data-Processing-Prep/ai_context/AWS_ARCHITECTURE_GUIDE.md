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
| Profiling de datos | SageMaker Processing / AWS Glue |
| Validaciones de calidad | AWS Glue Data Quality / scripts en SageMaker Processing |
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
9. Se revisan logs en CloudWatch.
10. Se ejecuta cleanup para eliminar recursos creados.

## Componentes

### Amazon S3

S3 es el data lake central. Debe contener zonas separadas para entradas, transformaciones, features, inferencia, logs y reportes. El bucket debe tener bloqueo de acceso publico y cifrado en reposo.

### AWS Glue Data Catalog

Glue Data Catalog debe registrar bases de datos y tablas asociadas a las capas del data lake. El catalogo permite que los datos sean descubribles por Glue, Athena, SageMaker y herramientas posteriores.

### Glue Job O SageMaker Processing

El procesamiento puede implementarse con Glue Jobs o SageMaker Processing Jobs:

- Glue Job es natural para ETL distribuido, Spark y catalogacion integrada.
- SageMaker Processing es natural para ejecutar codigo Python de preparacion ML con entradas y salidas S3.

Para estudiantes, se recomienda comenzar con SageMaker Processing si el pipeline usa pandas y datasets pequenos. Glue queda como catalogo obligatorio y como extension ETL.

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
- SageMaker Feature Store online para inferencia real-time, solo si se controla costo.
- CloudTrail y Lake Formation para auditoria y gobernanza avanzada.
