# Scripts Bash Y Modulos Python Del Laboratorio

Los scripts `.sh` permiten ejecutar el laboratorio desde Git Bash, Linux o macOS. En Windows PowerShell usa los equivalentes `.ps1`.

Todos los scripts cambian automaticamente al directorio raiz del laboratorio:

```text
2_ML-Data-Processing-Prep/
```

Por eso se pueden ejecutar desde la raiz del proyecto con comandos como:

```bash
bash scripts/upload_sample_data.sh
```

## Respuesta Corta Sobre `upload_sample_data.sh`

Si ejecutas:

```bash
bash scripts/upload_sample_data.sh
```

se ejecutan estos modulos Python:

```bash
python -m src.generate_sample_data
python -m src.upload_raw_data
```

No ejecuta:

```bash
python -m src.register_catalog
```

`register_catalog` es un paso separado. Se ejecuta con:

```bash
python -m src.register_catalog
```

o con:

```bash
make catalog
```

Tambien se ejecuta dentro del flujo completo:

```bash
bash scripts/run_all_cloud.sh
```

Ademas, `bash scripts/run_processing_job.sh all` ejecuta el paso `catalog` dentro del Glue Job. Esa doble ejecucion es intencional e idempotente: sirve para que las tablas existan antes de correr el job y para que el pipeline cloud pueda actualizar metadata si cambia la estructura esperada.

## Tabla Unificada De Scripts Bash Y Modulos Python

Esta tabla conecta cada comando operativo con el modulo Python que ejecuta, el capitulo del laboratorio donde se explica, el recurso AWS principal y el output esperado.

| Paso operativo | Script Bash | Modulo Python | Capitulo relacionado | Recurso AWS principal | Output esperado |
|---|---|---|---|---|---|
| Desplegar infraestructura | `bash scripts/deploy_infra.sh` | `python -m src.deploy_infra` | `lab/01_aws_setup.md`, `lab/09_cost_security_cleanup.md`, `infra/README.md` | CloudFormation, S3, IAM, Glue, CloudWatch Logs | Stack `ml-data-prep-lab-stack`, bucket S3, Glue Database, Glue Job, rol IAM y log group |
| Generar datos sinteticos | Incluido en `bash scripts/upload_sample_data.sh` | `python -m src.generate_sample_data` | `lab/00_contexto_negocio.md`, `lab/04_data_quality_profiling.md` | Local filesystem | CSV en `data/sample/customers.csv`, `data/sample/transactions.csv`, `data/sample/inference_transactions.csv` |
| Subir datos raw y assets Glue | `bash scripts/upload_sample_data.sh` | `python -m src.upload_raw_data` | `lab/02_data_lake_s3.md`, `lab/05_processing_jobs.md` | Amazon S3 | Datos en `s3://<bucket>/raw/`, copias raw para Athena y assets en `s3://<bucket>/scripts/` |
| Registrar catalogo | Sin `.sh` dedicado; incluido en `run_all_cloud.sh` | `python -m src.register_catalog` | `lab/03_glue_catalog.md` | AWS Glue Data Catalog, S3 | Tablas `raw_*`, `cleaned_*`, `curated_*`, `features_*` registradas o actualizadas, con `Location` apuntando a prefijos S3 consultables por Athena |
| Ejecutar pipeline cloud | `bash scripts/run_processing_job.sh <steps>` | `python -m src.run_processing_job --steps <steps>` | `lab/03_glue_catalog.md`, `lab/04_data_quality_profiling.md`, `lab/05_processing_jobs.md`, `lab/06_feature_engineering.md`, `lab/07_training_serving_consistency.md`, `lab/08_governance_lineage.md` | AWS Glue Job, S3, Glue Data Catalog, CloudWatch Logs | Outputs en `profiles/`, `quality/`, `cleaned/`, `curated/`, `features/`, `inference/`, `lineage/`, `reports/`, `logs/` |
| Ejecutar Glue Crawler demo | `bash scripts/run_glue_crawler.sh` | `python -m src.run_glue_crawler` | `lab/03_glue_catalog.md`, `lab/10_athena_glue_native_features.md` | AWS Glue Crawler, S3, Glue Data Catalog | Datos copiados a `crawler_demo/`, tablas `crawler_*` y reporte `reports/glue_crawler_report.json` |
| Ejecutar Glue Data Quality | `bash scripts/run_glue_data_quality.sh` | `python -m src.run_glue_data_quality` | `lab/04_data_quality_profiling.md`, `lab/10_athena_glue_native_features.md` | AWS Glue Data Quality, Glue Data Catalog, S3 | Resultado administrado en `quality/aws_glue_data_quality/` y resumen `quality/glue_data_quality_result.json` |
| Calcular Column Statistics | `bash scripts/run_glue_column_statistics.sh` | `python -m src.run_glue_column_statistics` | `lab/03_glue_catalog.md`, `lab/10_athena_glue_native_features.md` | AWS Glue Data Catalog Column Statistics | Estadisticas en Glue Catalog y copia `profiles/glue_column_statistics_features_training.json` |
| Descargar reportes | `bash scripts/download_reports.sh` | `python -m src.download_reports` | `lab/04_data_quality_profiling.md`, `lab/08_governance_lineage.md` | Amazon S3 | Copia local en `artifacts/local_outputs/` |
| Validar outputs | Sin `.sh` dedicado; incluido en `run_all_cloud.sh` | `python -m src.validate_outputs` | `lab/05_processing_jobs.md`, `lab/09_cost_security_cleanup.md` | S3, Glue Data Catalog | Validacion de objetos S3 esperados, copias para Athena, tablas Glue y ubicaciones `Location` |
| Ejecutar laboratorio completo | `bash scripts/run_all_cloud.sh` | `src.deploy_infra`, `src.generate_sample_data`, `src.upload_raw_data`, `src.register_catalog`, `src.run_processing_job`, `src.download_reports`, `src.validate_outputs` | Todo `lab/*.md` | CloudFormation, S3, IAM, Glue, CloudWatch Logs | Laboratorio completo desplegado, ejecutado, descargado y validado |
| Destruir infraestructura | `bash scripts/destroy_infra.sh` | `python -m src.destroy_infra` | `lab/09_cost_security_cleanup.md` | CloudFormation, S3, IAM, Glue, CloudWatch Logs | Bucket vaciado y stack eliminado |

Notas:

- `upload_sample_data.sh` combina dos modulos: primero genera datos sinteticos y luego los sube a S3.
- `register_catalog` no tiene script Bash dedicado porque es un paso liviano y tambien se ejecuta dentro de `run_all_cloud.sh`.
- Las tablas Glue apuntan a prefijos S3 tipo carpeta. Por ejemplo, `features_training` usa `s3://<bucket>/features/training_dataset/`, que contiene una copia `training_dataset.csv`. Esto permite consultar la tabla desde Athena.
- `validate_outputs` no tiene script Bash dedicado porque normalmente se ejecuta al final del flujo completo.
- `run_processing_job.sh all` tambien ejecuta el paso `catalog` dentro de Glue, de forma idempotente.

## Secuencia Recomendada Con Scripts

Usa esta secuencia si quieres ver cada bloque del laboratorio por separado:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
bash scripts/download_reports.sh
python -m src.validate_outputs
```

Para clase, si quieres conectar el laboratorio con Glue Crawler, Glue Data Quality, Column Statistics y Athena, usa esta secuencia extendida:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_glue_crawler.sh
bash scripts/run_processing_job.sh all
bash scripts/run_glue_data_quality.sh
bash scripts/run_glue_column_statistics.sh
bash scripts/download_reports.sh
python -m src.validate_outputs
```

La razon del orden:

- El crawler necesita datos en `raw/`; por eso corre despues de `upload_sample_data.sh`.
- El Glue Job principal escribe `cleaned/`, `curated/`, `features/` e `inference/`.
- Glue Data Quality y Column Statistics del laboratorio apuntan a `features_training`; por eso corren despues de `run_processing_job.sh all`.
- `download_reports.sh` conviene ejecutarlo despues de los extras para traer tambien sus reportes.

## Como Trabajar Con Los Extras Nativos De Glue

Los tres scripts siguientes no reemplazan el pipeline principal. Sirven para mostrar capacidades administradas de AWS Glue sobre datos ya generados.

| Script | Cuando ejecutarlo | Que valida o descubre | Donde verlo en AWS | Output del laboratorio |
|---|---|---|---|---|
| `bash scripts/run_glue_crawler.sh` | Despues de `upload_sample_data.sh` | Descubre esquemas desde copias raw en `crawler_demo/` | AWS Glue > Data Catalog > Crawlers y Tables | `reports/glue_crawler_report.json` |
| `bash scripts/run_glue_data_quality.sh` | Despues de `run_processing_job.sh all` | Evalua reglas DQDL sobre `features_training` | AWS Glue > Data quality | `quality/glue_data_quality_result.json` |
| `bash scripts/run_glue_column_statistics.sh` | Despues de `run_processing_job.sh all` y catalogo actualizado | Calcula estadisticas administradas para columnas clave | AWS Glue > Tables > `features_training` > Column statistics | `profiles/glue_column_statistics_features_training.json` |

### Glue Crawler En La Practica

Usalo para ensenar descubrimiento automatico:

```bash
bash scripts/run_glue_crawler.sh
```

El script copia:

```text
raw/customers.csv -> crawler_demo/customers/customers.csv
raw/transactions.csv -> crawler_demo/transactions/transactions.csv
raw/inference_transactions.csv -> crawler_demo/inference_transactions/inference_transactions.csv
```

Luego ejecuta el crawler `ml-data-prep-lab-raw-crawler`. El resultado esperado son tablas:

```text
crawler_customers
crawler_transactions
crawler_inference_transactions
```

Usalo para comparar `crawler_transactions` contra `raw_transactions`. La tabla `raw_transactions` es manual y deterministica; `crawler_transactions` es inferida por AWS.

### Glue Data Quality En La Practica

Usalo para ensenar reglas administradas:

```bash
bash scripts/run_glue_data_quality.sh
```

El script:

1. Verifica que exista `features/training_dataset.csv`.
2. Actualiza tablas Glue.
3. Crea o actualiza el ruleset `ml-data-prep-lab-features-training-quality`.
4. Ejecuta la evaluacion administrada.
5. Guarda un resumen descargable.

Reglas principales:

```text
transaction_id completo
customer_id completo
amount completo y mayor que 0
is_fraud completo y en [0, 1]
split en train, validation o test
```

Si falla, revisa `quality/glue_data_quality_result.json` y el panel `Data quality` de AWS Glue.

### Glue Column Statistics En La Practica

Usalo para ensenar estadisticas administradas del catalogo:

```bash
bash scripts/run_glue_column_statistics.sh
```

El script calcula estadisticas para seis columnas:

```text
amount
amount_log
customer_txn_count
amount_to_customer_avg
is_fraud
split
```

Si en la consola ves `Column statistics (6)` aunque el schema tenga mas columnas, es esperado. El laboratorio limita las columnas para reducir costo, tiempo y ruido didactico. Para ampliar la lista, edita `COLUMN_NAMES` en:

```text
src/run_glue_column_statistics.py
```

### Comandos CLI Utiles

Crawler:

```bash
aws glue get-crawler \
  --name ml-data-prep-lab-raw-crawler \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Data Quality rulesets:

```bash
aws glue list-data-quality-rulesets \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Column Statistics:

```bash
aws glue get-column-statistics-for-table \
  --database-name ml_data_prep_lab \
  --table-name features_training \
  --column-names amount amount_log customer_txn_count amount_to_customer_avg is_fraud split \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Mas detalle en:

```text
lab/10_athena_glue_native_features.md
```

Al terminar:

```bash
bash scripts/destroy_infra.sh
```

La misma secuencia completa esta empaquetada en:

```bash
bash scripts/run_all_cloud.sh
```

Ese script ejecuta internamente:

```bash
python -m src.deploy_infra
python -m src.generate_sample_data
python -m src.upload_raw_data
python -m src.register_catalog
python -m src.run_processing_job --steps all
python -m src.download_reports
python -m src.validate_outputs
```

## Definicion De Cada Modulo Python

### `python -m src.deploy_infra`

Despliega o actualiza la infraestructura declarada en CloudFormation.

Hace lo siguiente:

- Lee variables desde `.env`.
- Crea o actualiza el stack `ml-data-prep-lab-stack`.
- Crea el bucket S3 del data lake si `S3_BUCKET_NAME` esta vacio.
- Usa un bucket existente si `S3_BUCKET_NAME` tiene valor.
- Crea la base de datos de Glue Catalog.
- Crea el Glue Job del laboratorio.
- Crea o usa el rol IAM del Glue Job segun `GLUE_ROLE_ARN`.
- Crea el log group de CloudWatch.

Relacionado con:

- `lab/01_aws_setup.md`
- `lab/09_cost_security_cleanup.md`
- `infra/README.md`

### `python -m src.generate_sample_data`

Genera datos sinteticos locales para el caso de fraude o scoring de riesgo.

Produce:

```text
data/sample/customers.csv
data/sample/transactions.csv
data/sample/inference_transactions.csv
```

El dataset incluye algunos problemas intencionales para que el laboratorio pueda mostrar profiling, calidad y limpieza:

- Valores nulos.
- Monto negativo.
- Duplicados.
- Referencias a clientes inexistentes.
- Diferencia entre dataset historico con `is_fraud` y dataset de inferencia sin target.

Relacionado con:

- `lab/00_contexto_negocio.md`
- `lab/04_data_quality_profiling.md`

### `python -m src.upload_raw_data`

Sube los datos crudos a S3 y prepara los assets que necesitara Glue.

Hace lo siguiente:

- Verifica que existan los CSV en `data/sample/`.
- Si faltan, genera datos sinteticos automaticamente.
- Crea objetos marcador para las zonas del data lake.
- Sube:

```text
data/sample/customers.csv -> s3://<bucket>/raw/customers.csv
data/sample/transactions.csv -> s3://<bucket>/raw/transactions.csv
data/sample/inference_transactions.csv -> s3://<bucket>/raw/inference_transactions.csv
```

- Crea copias bajo prefijos tipo carpeta para que las tablas raw puedan consultarse con Athena:

```text
s3://<bucket>/raw/customers/customers.csv
s3://<bucket>/raw/transactions/transactions.csv
s3://<bucket>/raw/inference_transactions/inference_transactions.csv
```

- Empaqueta el codigo de `src/` en `data/local_cache/ml_data_prep_src.zip`.
- Sube assets del Glue Job a:

```text
s3://<bucket>/scripts/ml_data_prep_src.zip
s3://<bucket>/scripts/glue_pipeline.py
```

No registra tablas Glue. Para eso usa `src.register_catalog`.

Relacionado con:

- `lab/02_data_lake_s3.md`
- `lab/05_processing_jobs.md`

### `python -m src.register_catalog`

Registra o actualiza tablas externas en AWS Glue Data Catalog.

Hace lo siguiente:

- Lee el bucket y la base Glue desde el stack o `.env`.
- Registra tablas CSV apuntando a rutas S3.
- Sincroniza copias de archivos existentes bajo prefijos consultables por Athena.
- Usa operaciones tipo upsert: crea la tabla si no existe o la actualiza si ya existe.

Tablas principales:

```text
raw_customers
raw_transactions
raw_inference_transactions
cleaned_customers
cleaned_transactions
curated_customer_transactions
features_training
features_inference
```

No genera datos sinteticos, no transforma datasets y no ejecuta Glue Job. Las copias que crea son copias 1:1 de archivos ya existentes para que Glue/Athena trabajen con `Location` tipo prefijo.

Ejemplo:

```text
Archivo simple del laboratorio:
s3://<bucket>/features/training_dataset.csv

Prefijo de tabla para Glue/Athena:
s3://<bucket>/features/training_dataset/training_dataset.csv

Location de la tabla features_training:
s3://<bucket>/features/training_dataset/
```

Relacionado con:

- `lab/03_glue_catalog.md`

### `python -m src.run_processing_job --steps all`

Lanza y monitorea el AWS Glue Python Shell Job.

Hace lo siguiente:

- Sube nuevamente los assets del Glue Job a `s3://<bucket>/scripts/`.
- Inicia el job `ml-data-prep-lab-processing-job`.
- Pasa argumentos como bucket, database, prefijo, pasos y `run_id`.
- Espera hasta que el job termine.
- Falla si Glue termina en estado `FAILED`, `STOPPED`, `TIMEOUT`, `ERROR` o `EXPIRED`.

Dentro de AWS Glue se ejecuta `src.glue_pipeline`, que llama a `src.pipeline`.

Relacionado con:

- `lab/03_glue_catalog.md`
- `lab/04_data_quality_profiling.md`
- `lab/05_processing_jobs.md`
- `lab/06_feature_engineering.md`
- `lab/07_training_serving_consistency.md`
- `lab/08_governance_lineage.md`

### `python -m src.run_glue_crawler`

Ejecuta un ejemplo de AWS Glue Crawler sobre una copia controlada de los datos raw.

Hace lo siguiente:

- Verifica que existan datos en `s3://<bucket>/raw/`.
- Copia los CSV raw a prefixes separados para que el crawler cree una tabla por fuente:

```text
s3://<bucket>/crawler_demo/customers/customers.csv
s3://<bucket>/crawler_demo/transactions/transactions.csv
s3://<bucket>/crawler_demo/inference_transactions/inference_transactions.csv
```

- Inicia el crawler `ml-data-prep-lab-raw-crawler`.
- Espera a que termine.
- Lista las tablas creadas con prefijo `crawler_`.
- Guarda un resumen en:

```text
s3://<bucket>/reports/glue_crawler_report.json
```

Este paso muestra descubrimiento automatico de esquemas. El pipeline principal usa tablas definidas por codigo porque ya conoce el contrato de datos y asi es mas reproducible.

Relacionado con:

- `lab/03_glue_catalog.md`
- `lab/10_athena_glue_native_features.md`

### `python -m src.run_glue_data_quality`

Ejecuta reglas basicas de AWS Glue Data Quality sobre la tabla `features_training`.

Prerequisito: el pipeline principal debe haber generado:

```text
s3://<bucket>/features/training_dataset.csv
```

Hace lo siguiente:

- Registra o actualiza las tablas del Glue Data Catalog.
- Crea o actualiza el ruleset `ml-data-prep-lab-features-training-quality`.
- Ejecuta una evaluacion administrada de Glue Data Quality sobre `features_training`.
- Espera el resultado.
- Guarda un resumen del run y de las reglas en:

```text
s3://<bucket>/quality/glue_data_quality_result.json
```

Las salidas administradas de Glue quedan bajo:

```text
s3://<bucket>/quality/aws_glue_data_quality/
```

Relacionado con:

- `lab/04_data_quality_profiling.md`
- `lab/10_athena_glue_native_features.md`

### `python -m src.run_glue_column_statistics`

Calcula estadisticas administradas de columnas en AWS Glue Data Catalog para `features_training`.

Prerequisito: el pipeline principal debe haber generado y registrado:

```text
s3://<bucket>/features/training_dataset.csv
```

Hace lo siguiente:

- Registra o actualiza las tablas del Glue Data Catalog.
- Inicia una tarea `StartColumnStatisticsTaskRun`.
- Calcula estadisticas para columnas numericas y categoricas clave.
- Consulta el resultado desde Glue Catalog.
- Guarda una copia para lectura del estudiante en:

```text
s3://<bucket>/profiles/glue_column_statistics_features_training.json
```

Estas estadisticas ayudan al optimizador de consultas y complementan, pero no reemplazan, el profiling ML del pipeline.

Relacionado con:

- `lab/03_glue_catalog.md`
- `lab/10_athena_glue_native_features.md`

### `python -m src.download_reports`

Descarga reportes desde S3 a una carpeta local para revision del estudiante.

Descarga prefijos:

```text
profiles/
quality/
lineage/
reports/
logs/
```

Destino local:

```text
artifacts/local_outputs/
```

Relacionado con:

- `lab/04_data_quality_profiling.md`
- `lab/08_governance_lineage.md`

### `python -m src.validate_outputs`

Valida que el laboratorio produjo los objetos y tablas esperados.

Revisa:

- Objetos esperados en S3.
- Copias S3 bajo prefijos consultables por Athena.
- Tablas esperadas en Glue Data Catalog.
- Que el `Location` de cada tabla Glue apunte al prefijo correcto.

Si falta algo, falla con una lista de objetos o tablas ausentes.

Relacionado con:

- Todos los capitulos del laboratorio, especialmente `lab/09_cost_security_cleanup.md`.

### `python -m src.destroy_infra`

Elimina la infraestructura del laboratorio.

Hace lo siguiente:

- Busca el bucket del stack.
- Vacia el bucket si `EMPTY_S3_ON_DESTROY=true`.
- Elimina el stack CloudFormation.
- Imprime eventos recientes si CloudFormation falla.

Si el stack queda bloqueado porque tu usuario no puede borrar el rol IAM del Glue Job:

```bash
python -m src.destroy_infra --retain-glue-role
```

Ese modo elimina el resto del stack y deja el rol para que un administrador lo revise o lo borre.

Relacionado con:

- `lab/01_aws_setup.md`
- `lab/09_cost_security_cleanup.md`

## Pasos Disponibles En `run_processing_job.sh`

Por defecto corre todos los pasos:

```bash
bash scripts/run_processing_job.sh
```

Equivale a:

```bash
bash scripts/run_processing_job.sh all
```

Pasos individuales:

```bash
bash scripts/run_processing_job.sh catalog
bash scripts/run_processing_job.sh profile
bash scripts/run_processing_job.sh quality
bash scripts/run_processing_job.sh process
bash scripts/run_processing_job.sh features
bash scripts/run_processing_job.sh training-dataset
bash scripts/run_processing_job.sh inference-dataset
bash scripts/run_processing_job.sh lineage
bash scripts/run_processing_job.sh dataset-card
```

Tambien puedes pasar varios pasos separados por coma:

```bash
bash scripts/run_processing_job.sh profile,quality,process
```

Para reducir costos durante una ejecucion normal, usa `all`, porque lanza un solo Glue Job en vez de varios jobs separados:

```bash
bash scripts/run_processing_job.sh all
```

## Que Produce Cada Paso Del Pipeline Cloud

| Paso | Que hace | Output S3 |
|---|---|---|
| `catalog` | Registra tablas en Glue Data Catalog. | Metadata en Glue, sin archivo nuevo obligatorio |
| `profile` | Calcula conteos, nulos, duplicados, tipos y resumen estadistico. | `profiles/profile.json` |
| `quality` | Evalua reglas de calidad sobre datos raw. | `quality/quality_report.json` |
| `process` | Limpia datos, corrige valores, elimina duplicados e integra clientes con transacciones. | `cleaned/`, `curated/` |
| `features` | Crea features compartidas para entrenamiento e inferencia. | `features/training_features.csv`, `features/inference_features.csv` |
| `training-dataset` | Genera dataset supervisado con target `is_fraud` y split. | `features/training_dataset.csv` |
| `inference-dataset` | Genera dataset para prediccion sin target. | `inference/inference_dataset.csv` |
| `lineage` | Documenta trazabilidad de fuentes, transformaciones y salidas. | `lineage/lineage.json`, `lineage/lineage.md` |
| `dataset-card` | Documenta uso, columnas, calidad, riesgos y limitaciones del dataset. | `reports/dataset_card.json`, `reports/dataset_card.md` |

Cada ejecucion del pipeline escribe ademas:

```text
s3://<bucket>/logs/pipeline_run.json
```

## Antes De Ejecutar

Configura `.env`:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
PROJECT_NAME=ml-data-processing-prep
ENVIRONMENT=lab
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
GLUE_DATABASE_NAME=ml_data_prep_lab
GLUE_CRAWLER_NAME=
GLUE_DATA_QUALITY_RULESET_NAME=
GLUE_DATA_QUALITY_WORKERS=2
GLUE_ROLE_ARN=
```

Activa el entorno Python:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Valida AWS:

```bash
aws sts get-caller-identity --profile mlops-2-data-prep-lab --region us-east-1
```

## Despues De Ejecutar

Revisar outputs en S3:

```bash
aws s3 ls s3://<bucket-name>/ --recursive --profile mlops-2-data-prep-lab --region us-east-1
```

Revisar ejecuciones Glue:

```bash
aws glue get-job-runs --job-name ml-data-prep-lab-processing-job --profile mlops-2-data-prep-lab --region us-east-1
```

Revisar logs CloudWatch:

```bash
aws logs describe-log-groups --log-group-name-prefix /aws --profile mlops-2-data-prep-lab --region us-east-1
```

Destruir recursos:

```bash
bash scripts/destroy_infra.sh
```

## Troubleshooting De Scripts

### Glue Falla Con `No module named 'src'`

Sintoma:

```text
Glue job failed with state=FAILED: ModuleNotFoundError: No module named 'src'
```

El Glue Job encontro `glue_pipeline.py`, pero no tenia disponible el paquete completo `src/`.

El laboratorio empaqueta `src/` en:

```text
s3://<bucket>/scripts/ml_data_prep_src.zip
```

y `glue_pipeline.py` puede descargar ese zip a `/tmp` si Glue no lo carga automaticamente con `--extra-py-files`.

Para reintentar:

```bash
bash scripts/run_processing_job.sh all
```

No necesitas ejecutar `bash scripts/deploy_infra.sh` otra vez para este caso, porque `run_processing_job.sh` ya sube los assets actualizados antes de lanzar el job.

## Equivalencia Con Make

| Make | Bash equivalente |
|---|---|
| `make deploy-infra` | `bash scripts/deploy_infra.sh` |
| `make data` | `python -m src.generate_sample_data` |
| `make upload-raw` | `python -m src.upload_raw_data` o `bash scripts/upload_sample_data.sh` si tambien quieres regenerar datos antes |
| `make catalog` | `python -m src.register_catalog` |
| `make glue-crawler` | `bash scripts/run_glue_crawler.sh` |
| `make glue-data-quality` | `bash scripts/run_glue_data_quality.sh` |
| `make column-stats` | `bash scripts/run_glue_column_statistics.sh` |
| `make aws-native-extras` | `bash scripts/run_glue_crawler.sh`, `bash scripts/run_glue_data_quality.sh`, `bash scripts/run_glue_column_statistics.sh` |
| `make profile` | `bash scripts/run_processing_job.sh profile` |
| `make quality` | `bash scripts/run_processing_job.sh quality` |
| `make process` | `bash scripts/run_processing_job.sh process` |
| `make features` | `bash scripts/run_processing_job.sh features` |
| `make training-dataset` | `bash scripts/run_processing_job.sh training-dataset` |
| `make inference-dataset` | `bash scripts/run_processing_job.sh inference-dataset` |
| `make lineage` | `bash scripts/run_processing_job.sh lineage` |
| `make dataset-card` | `bash scripts/run_processing_job.sh dataset-card` |
| `make download-reports` | `bash scripts/download_reports.sh` |
| `make validate` | `python -m src.validate_outputs` |
| `make destroy-infra` | `bash scripts/destroy_infra.sh` |
| `make all-cloud` | `bash scripts/run_all_cloud.sh` |

## Lectura Recomendada

Antes de ejecutar por primera vez:

1. `lab/00_contexto_negocio.md`
2. `lab/01_aws_setup.md`
3. `lab/02_data_lake_s3.md`
4. `lab/03_glue_catalog.md`
5. `lab/05_processing_jobs.md`
6. `lab/09_cost_security_cleanup.md`

Para entender los reportes:

1. `lab/04_data_quality_profiling.md`
2. `lab/06_feature_engineering.md`
3. `lab/07_training_serving_consistency.md`
4. `lab/08_governance_lineage.md`
5. `lab/10_athena_glue_native_features.md`
