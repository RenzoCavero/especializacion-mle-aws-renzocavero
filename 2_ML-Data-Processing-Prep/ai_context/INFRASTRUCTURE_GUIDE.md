# Guia De Infraestructura

## Herramienta IaC Recomendada

La herramienta recomendada para este laboratorio es **AWS CloudFormation**.

Razon:

- Es nativa de AWS.
- No requiere instalar runtimes adicionales mas alla de AWS CLI.
- Es facil de destruir con un stack.
- Permite a estudiantes ver recursos AWS directamente.
- Mantiene el laboratorio alineado con servicios AWS administrados.

AWS CDK es una alternativa valida si se quiere ensenar infraestructura con codigo. Terraform es alternativa si la especializacion decide mantener una estrategia multi-cloud. Si se elige una alternativa, documentar la decision en `infra/README.md`.

## Decision De Implementacion Actual

La implementacion del laboratorio usa:

- CloudFormation como IaC.
- Amazon S3 como data lake.
- AWS Glue Data Catalog como catalogo.
- AWS Glue Python Shell Job como motor cloud de procesamiento.
- AWS Glue Crawler como demo opcional de descubrimiento de esquemas.
- AWS Glue Data Quality Ruleset como demo opcional de validacion administrada.
- AWS Glue Data Catalog Column Statistics como demo opcional de estadisticas administradas.
- Amazon Athena como demo opcional de consulta SQL sobre tablas catalogadas.
- CloudWatch Logs para operacion.
- IAM Role de Glue con minimo privilegio sobre recursos del laboratorio.

Se eligio Glue Python Shell porque mantiene el laboratorio cloud-first, evita endpoints persistentes, integra naturalmente S3 y Glue Catalog, y reduce costos con datasets pequenos.

## Recursos Minimos

Recursos base esperados:

- Bucket S3 del laboratorio.
- Estructura de prefixes en S3: `raw/`, `cleaned/`, `curated/`, `features/`, `inference/`, `profiles/`, `quality/`, `lineage/`, `reports/`, `logs/`.
- Glue Database.
- Rol IAM para procesamiento.
- Politicas IAM de minimo privilegio.
- Log group de CloudWatch.
- Glue Crawler opcional, ejecutado bajo demanda.
- Glue Data Quality Ruleset opcional, ejecutado bajo demanda.
- Glue Data Catalog Column Statistics opcional, ejecutado bajo demanda.
- Glue Job o SageMaker Processing Job.
- KMS key opcional.
- SageMaker Feature Store opcional o preparado para extension.

## Parametros Configurables

Parametros minimos:

- `project_name`: `ml-data-processing-prep`
- `environment`: `lab`
- `region`: configurable
- `bucket_name`: generado o pasado por parametro
- `resource_prefix`: `ml-data-prep-lab`
- `aws_profile`: definido fuera de IaC, usado por AWS CLI
- `enable_kms`: opcional
- `use_existing_bucket`: opcional
- `enable_feature_store`: opcional, por defecto `false`

## Convencion De Nombres

Convencion recomendada:

```text
project_name: ml-data-processing-prep
environment: lab
region: configurable
bucket_name: generado o pasado por parametro
resource_prefix: ml-data-prep-lab
```

Ejemplos:

- Stack: `ml-data-prep-lab-stack`
- Bucket: `ml-data-prep-lab-<account-id>-<region>`
- Glue Database: `ml_data_prep_lab`
- IAM Role: `ml-data-prep-lab-processing-role`
- CloudWatch Log Group: `/aws/ml-data-prep-lab/processing`
- Glue Crawler: `ml-data-prep-lab-raw-crawler`
- Glue Data Quality Ruleset: `ml-data-prep-lab-features-training-quality`

Los nombres deben evitar valores globalmente conflictivos cuando aplique, especialmente S3.

## Region AWS

La region debe ser configurable por variable de entorno o parametro:

```text
AWS_REGION=
```

No hardcodear region en scripts si puede leerse desde `.env`, AWS CLI o parametros.

## Tags Obligatorios

Todo recurso que soporte tags debe incluir:

| Tag | Valor |
|---|---|
| Project | MLDataProcessingPrep |
| Environment | Lab |
| Owner | Student |
| ManagedBy | IaC |
| CostCenter | Training |
| AutoDelete | true |

## IAM

### Roles

Rol minimo esperado:

- Rol de procesamiento para Glue Job o SageMaker Processing Job.

Opcionales:

- Rol de Glue Crawler.
- Rol separado para Feature Store si se habilita.

### Politicas Minimas

Las politicas deben limitarse a:

- Lectura en `s3://<bucket>/raw/*`.
- Lectura y escritura controlada en `s3://<bucket>/crawler_demo/*` para el demo de Glue Crawler.
- Escritura controlada en `s3://<bucket>/athena-results/*` para resultados de Athena.
- Escritura controlada en `s3://<bucket>/quality/aws_glue_data_quality/*` para resultados de Glue Data Quality.
- Escritura en `s3://<bucket>/cleaned/*`, `curated/*`, `features/*`, `inference/*`, `profiles/*`, `quality/*`, `lineage/*`, `reports/*` y `logs/*`.
- Acceso minimo a Glue Data Catalog requerido para crear o leer tablas.
- Acceso minimo a Glue Data Quality y Column Statistics cuando se ejecuten los extras opcionales.
- Escritura de logs en CloudWatch para el log group del laboratorio.
- Uso de KMS solo sobre la key del laboratorio si KMS esta habilitado.

Evitar permisos amplios como `s3:*` sobre todos los recursos, `iam:*`, `glue:*` global o `sagemaker:*` global salvo que sea estrictamente necesario y temporal para estudiantes administradores durante deploy.

## Bucket S3

Configuracion esperada:

- Bloqueo de acceso publico habilitado.
- Cifrado en reposo con SSE-S3 por defecto o KMS opcional.
- Versioning opcional. Para control de costos, puede quedar deshabilitado en laboratorios pequenos.
- Lifecycle opcional para expirar outputs temporales.
- Nombres y prefixes documentados.

Si se usa un bucket existente, el stack no debe destruirlo por defecto sin confirmacion explicita.

## CloudWatch Logs

Crear o documentar log group:

```text
/aws/ml-data-prep-lab/processing
```

Configurar retencion corta para controlar costos, por ejemplo 7 o 14 dias.

## Glue Database

Glue Database recomendado:

```text
ml_data_prep_lab
```

Debe registrar tablas para capas relevantes, por ejemplo:

- `raw_transactions`
- `raw_customers`
- `cleaned_transactions`
- `curated_customer_transactions`
- `features_training`
- `features_inference`

## Glue Crawler Opcional

El crawler puede descubrir esquemas en S3, pero no debe ser obligatorio si aumenta complejidad. Si se usa:

- Limitarlo a prefixes del laboratorio.
- Ejecutarlo bajo demanda.
- Documentar costo y cleanup.

La implementacion actual crea un crawler opcional que lee `crawler_demo/customers/`, `crawler_demo/transactions/` y `crawler_demo/inference_transactions/`. El script `src.run_glue_crawler` copia los CSV desde `raw/` a esos prefixes para que el crawler genere una tabla por fuente.

## Glue Data Quality Opcional

Glue Data Quality puede complementar las validaciones Python del pipeline con reglas administradas DQDL. Debe ejecutarse bajo demanda sobre tablas ya generadas, por ejemplo `features_training`.

La implementacion actual crea o actualiza un ruleset basico bajo demanda con `src.run_glue_data_quality`, en vez de crearlo durante CloudFormation. Esta decision evita fallos transitorios de `AWS::Glue::DataQualityRuleset` durante el deploy y mantiene Glue Data Quality como demo explicito despues del pipeline principal. El resultado administrado queda en `quality/aws_glue_data_quality/` y una copia resumida queda en `quality/glue_data_quality_result.json`.

## Glue Data Catalog Column Statistics Opcional

Column Statistics debe usarse como complemento de catalogacion y performance de consultas. No reemplaza el profiling ML del laboratorio.

La implementacion actual calcula estadisticas para columnas clave de `features_training` con `src.run_glue_column_statistics` y guarda una copia en `profiles/glue_column_statistics_features_training.json`.

## Glue Job O SageMaker Processing Job

La implementacion debe elegir una ruta principal:

- SageMaker Processing Job para scripts Python/pandas y datasets pequenos.
- Glue Job para ETL Spark o integracion Glue mas fuerte.

La ruta recomendada inicial de esta implementacion es AWS Glue Python Shell Job con codigo Python modular y salidas en S3, manteniendo Glue Data Catalog como catalogo. SageMaker Processing sigue siendo una alternativa valida para futuros laboratorios donde se quiera acercar el procesamiento a SageMaker training, Feature Store o Pipelines.

## Un Job Modular Vs Varios Jobs

La decision actual es usar un solo Glue Job modular para reducir costo, simplificar el despliegue y facilitar la ensenanza. Los limites logicos se expresan con pasos como `process`, `features`, `training-dataset` e `inference-dataset`.

Para una version productiva, es valido separar el procesamiento en jobs por capa:

```text
raw -> cleaned
cleaned -> curated
curated -> features
```

Usar varios jobs cuando las etapas tengan contratos independientes, escalas distintas, owners diferentes, permisos separados, reintentos aislados o gates de calidad entre capas. Evitar dividir de forma prematura si el volumen es pequeno o si la orquestacion agrega complejidad sin beneficio claro.

Si se implementan varios jobs en el futuro, documentar:

- Orquestador elegido: Glue Workflows, Glue Triggers, Step Functions o SageMaker Pipelines.
- Inputs y outputs S3 de cada job.
- Formato de salida recomendado, preferentemente Parquet u ORC para capas procesadas.
- Reglas de calidad por frontera de capa.
- Estrategia de reintentos, idempotencia y cleanup.
- Lineage por etapa y relacion con futuros laboratorios de entrenamiento e inferencia.

## SageMaker Feature Store Opcional

Feature Store debe permanecer deshabilitado por defecto para controlar costos. La capa `features/` en S3 debe estar disenada para evolucionar a offline store.

Si se habilita Feature Store:

- Usar offline store.
- Evitar online store salvo solicitud explicita.
- Documentar costos.
- Incluir cleanup del feature group.

## Estrategia De Cleanup

Cleanup obligatorio:

- `make destroy-infra`
- `scripts/destroy_infra.sh`
- `scripts/destroy_infra.ps1`

El cleanup debe:

- Eliminar stack IaC.
- Eliminar o vaciar recursos creados si el stack no puede hacerlo solo.
- Confirmar eliminacion de Glue resources, CloudWatch log groups, roles y jobs.
- Documentar comportamiento cuando se use bucket existente.

## Recursos Que Pueden Generar Costo

Pueden generar costos segun uso, volumen y tiempo:

- S3 por almacenamiento, requests y transferencia.
- Glue Jobs por tiempo de ejecucion y capacidad.
- Glue Crawlers por ejecucion.
- Glue Data Quality por evaluacion.
- Glue Data Catalog Column Statistics por ejecucion.
- Athena por datos escaneados.
- SageMaker Processing Jobs por instancia y duracion.
- SageMaker Feature Store por almacenamiento offline y online si se habilita.
- CloudWatch Logs por ingesta y retencion.
- KMS por requests y keys administradas por cliente.

## Cleanup Obligatorio

Todo laboratorio debe tener comando de destruccion y limpieza documentado. No entregar una implementacion que pueda crear recursos sin una forma clara de eliminarlos.
