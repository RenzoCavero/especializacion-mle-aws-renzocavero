# 10 - Athena Y Features Nativas De Glue

Este capitulo muestra como usar servicios nativos de AWS sobre los datasets generados por el laboratorio:

- Amazon Athena para consultar tablas del Glue Data Catalog.
- AWS Glue Crawler como ejemplo de inferencia automatica de esquema.
- AWS Glue Data Quality para evaluar reglas DQDL administradas por Glue.
- Glue Data Catalog Column Statistics para calcular estadisticas administradas por el catalogo.

Estos pasos son opcionales. No se ejecutan dentro de `make all-cloud` para controlar costo y tiempo de ejecucion.

Comando agrupado:

```bash
bash scripts/lab.sh step 10
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 step 10
```

## Prerrequisitos

Ejecuta primero el flujo base:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
```

Verifica outputs:

```bash
python -m src.validate_outputs
```

Los ejemplos asumen:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=us-east-1
GLUE_DATABASE_NAME=ml_data_prep_lab
RESOURCE_PREFIX=ml-data-prep-lab
```

## 1. Consultar Con Athena Desde La Consola AWS

Athena no copia los datos. Athena consulta archivos en S3 usando metadata del Glue Data Catalog.

### Paso 1: Abrir Athena

1. Entra a AWS Console.
2. Busca `Athena`.
3. Abre `Amazon Athena`.
4. Confirma que estas en la misma region del laboratorio, por ejemplo `us-east-1`.

### Paso 2: Configurar Query Result Location

Si Athena pide configurar una ubicacion para resultados:

1. En Athena, entra a `Settings`.
2. Selecciona `Manage`.
3. En `Location of query result`, usa:

```text
s3://<bucket-name>/athena-results/
```

4. Guarda la configuracion.

Reemplaza `<bucket-name>` por el bucket del stack. Puedes obtenerlo con:

```bash
aws cloudformation describe-stacks \
  --stack-name ml-data-prep-lab-stack \
  --profile mlops-2-data-prep-lab \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text
```

### Paso 3: Elegir Data Source Y Database

En el editor de Athena:

```text
Data source: AwsDataCatalog
Database: ml_data_prep_lab
```

Deberias ver tablas como:

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

### Paso 3.1: Confirmar La Ubicacion S3 De La Tabla

Para Athena, la ubicacion de una tabla externa debe apuntar a un prefijo S3 que contenga archivos, no al archivo CSV como si fuera una carpeta.

En este laboratorio `features_training` debe verse asi en Glue Data Catalog:

```text
Location: s3://<bucket>/features/training_dataset/
```

Y dentro de ese prefijo debe existir:

```text
s3://<bucket>/features/training_dataset/training_dataset.csv
```

El archivo original tambien existe:

```text
s3://<bucket>/features/training_dataset.csv
```

Ese archivo original se mantiene porque es sencillo para explicar el data lake y para descargarlo directamente. La copia bajo carpeta es la que hace que Athena lea filas de forma confiable desde Glue Data Catalog.

### Paso 4: Query Basica Sobre Splits

Ejecuta:

```sql
SELECT split, COUNT(*) AS rows
FROM features_training
GROUP BY split
ORDER BY split;
```

Uso:

- Verifica que el dataset de entrenamiento tenga particion logica `train`, `validation` y `test`.
- No usa particiones fisicas S3; es una columna del dataset.

Resultado esperado:

```text
split       rows
test        <n>
train       <n>
validation  <n>
```

Los numeros exactos pueden variar si cambias la semilla o el tamano de los datos sinteticos.

### Paso 5: Query Basica Sobre Target

Ejecuta:

```sql
SELECT is_fraud, COUNT(*) AS rows
FROM features_training
GROUP BY is_fraud
ORDER BY is_fraud;
```

Uso:

- Permite revisar el balance del target sintetico.
- En un proyecto real, esta consulta ayuda a detectar desbalance severo antes de entrenar.

### Paso 6: Query Basica Sobre Variables De Riesgo

Ejecuta:

```sql
SELECT
  high_risk_country,
  AVG(amount) AS avg_amount,
  COUNT(*) AS rows
FROM features_training
GROUP BY high_risk_country
ORDER BY high_risk_country;
```

Uso:

- Explora si los montos se comportan distinto para paises marcados como alto riesgo.
- Es una inspeccion rapida antes de entrenamiento.

### Paso 7: Query Sobre Datos Curated

Ejecuta:

```sql
SELECT
  segment,
  COUNT(*) AS transactions,
  AVG(amount) AS avg_amount
FROM curated_customer_transactions
GROUP BY segment
ORDER BY transactions DESC;
```

Uso:

- Muestra como `curated/` conecta datos transaccionales con atributos de cliente.
- Es util cuando una feature aun no existe y quieres explorar datos integrados.

### Si Athena Muestra 0 Filas Pero `validate_outputs` Pasa

Este sintoma suele ocurrir cuando Glue tiene el esquema, pero Athena no encuentra objetos de datos bajo el `Location` de la tabla.

Acciones:

1. Desactiva temporalmente `Reuse query results` en Athena o pulsa `Run again`.
2. Confirma que estas en la misma region, database `ml_data_prep_lab` y data source `AwsDataCatalog`.
3. Ejecuta desde la raiz del laboratorio:

```bash
python -m src.register_catalog
python -m src.validate_outputs
```

`register_catalog` actualiza las ubicaciones Glue y sincroniza copias tipo carpeta para Athena, por ejemplo:

```text
features/training_dataset.csv
-> features/training_dataset/training_dataset.csv
```

4. Si `validate_outputs` indica que faltan objetos procesados, regenera el pipeline y registra de nuevo:

```bash
bash scripts/run_processing_job.sh all
python -m src.register_catalog
python -m src.validate_outputs
```

5. Prueba una consulta minima:

```sql
SELECT COUNT(*) AS rows
FROM features_training;
```

Si esta consulta devuelve filas y la consulta por `split` no, revisa que la columna `split` exista en el schema de `features_training`.

## 2. Usar Glue Crawler Como Ejemplo

El laboratorio registra tablas manualmente porque los esquemas estan definidos en codigo:

```text
src/schemas.py
src/glue_catalog.py
```

Esto es mas reproducible para estudiantes. Aun asi, se incluye un Glue Crawler opcional para mostrar inferencia automatica de esquema.

### Para Que Sirve En El Laboratorio

Glue Crawler responde una pregunta distinta a `src.register_catalog`:

```text
register_catalog -> Yo ya conozco el contrato de datos y registro tablas controladas.
Glue Crawler     -> AWS inspecciona archivos en S3 e infiere tablas y esquemas.
```

En proyectos reales, un crawler es util cuando:

- Llegan archivos nuevos a un data lake y necesitas descubrirlos.
- No controlas completamente el esquema de entrada.
- Quieres poblar el Glue Data Catalog sin escribir a mano cada tabla.
- Tienes particiones S3 y quieres que el catalogo las descubra.

En este laboratorio, el pipeline principal no depende del crawler porque el objetivo es mantener reproducibilidad. Para ML, normalmente quieres que los esquemas de entrenamiento e inferencia sean explicitos y estables.

### Recurso Creado Por Infraestructura

CloudFormation crea el crawler:

```text
ml-data-prep-lab-raw-crawler
```

El crawler usa el rol de Glue del laboratorio y apunta al prefijo:

```text
s3://<bucket>/crawler_demo/
```

No apunta directamente a `raw/` para evitar que un crawler altere o confunda las tablas principales del laboratorio. `crawler_demo/` es una copia controlada solo para demostracion.

### Que Hace El Crawler Demo

El script:

```bash
bash scripts/run_glue_crawler.sh
```

hace lo siguiente:

1. Copia archivos raw a una estructura mas amigable para crawler:

```text
s3://<bucket>/crawler_demo/customers/customers.csv
s3://<bucket>/crawler_demo/transactions/transactions.csv
s3://<bucket>/crawler_demo/inference_transactions/inference_transactions.csv
```

2. Ejecuta el crawler:

```text
ml-data-prep-lab-raw-crawler
```

3. El crawler crea tablas con prefijo:

```text
crawler_
```

4. Escribe un reporte:

```text
s3://<bucket>/reports/glue_crawler_report.json
```

### Flujo Interno Del Script

`bash scripts/run_glue_crawler.sh` ejecuta:

```bash
python -m src.run_glue_crawler
```

El modulo hace esta secuencia:

1. Lee la configuracion AWS desde `.env` o el profile activo.
2. Obtiene el bucket y la base Glue del stack.
3. Registra/actualiza las tablas principales para mantener el catalogo consistente.
4. Copia archivos raw hacia `crawler_demo/`:

```text
raw/customers.csv
-> crawler_demo/customers/customers.csv

raw/transactions.csv
-> crawler_demo/transactions/transactions.csv

raw/inference_transactions.csv
-> crawler_demo/inference_transactions/inference_transactions.csv
```

5. Ejecuta `StartCrawler`.
6. Espera hasta que el crawler vuelva a estado `READY`.
7. Lista tablas creadas con prefijo `crawler_`.
8. Guarda `reports/glue_crawler_report.json`.

### Por Que Copiamos A `crawler_demo/`

Un crawler agrupa archivos segun heuristicas de estructura de carpetas. Si varios CSV viven directamente bajo `raw/`, el crawler podria interpretarlos como una sola tabla o generar nombres menos claros.

Por eso usamos una carpeta por dataset:

```text
crawler_demo/customers/
crawler_demo/transactions/
crawler_demo/inference_transactions/
```

Asi el estudiante puede ver una tabla por fuente:

```text
crawler_customers
crawler_transactions
crawler_inference_transactions
```

### Ejecutar

```bash
bash scripts/run_glue_crawler.sh
```

O con Make:

```bash
make glue-crawler
```

### Revisar En AWS Console

1. Abre AWS Glue.
2. Ve a `Data Catalog`.
3. Entra a `Crawlers`.
4. Busca:

```text
ml-data-prep-lab-raw-crawler
```

5. Revisa `Last run`.
6. Ve a `Tables` y filtra por:

```text
crawler_
```

Tablas esperadas:

```text
crawler_customers
crawler_transactions
crawler_inference_transactions
```

### Revisar Con AWS CLI

```bash
aws glue get-crawler \
  --name ml-data-prep-lab-raw-crawler \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

```bash
aws glue get-tables \
  --database-name ml_data_prep_lab \
  --profile mlops-2-data-prep-lab \
  --region us-east-1 \
  --query "TableList[?starts_with(Name, 'crawler_')].[Name,StorageDescriptor.Location]" \
  --output table
```

### Consultar Tabla Crawler En Athena

Despues de que el crawler termine, puedes ejecutar:

```sql
SELECT COUNT(*) AS rows
FROM crawler_transactions;
```

Y comparar con la tabla manual:

```sql
SELECT COUNT(*) AS rows
FROM raw_transactions;
```

Si ambos conteos son similares, el crawler pudo leer la misma fuente conceptual. Si los tipos son diferentes, usa esa comparacion para recordar que la inferencia automatica no siempre produce el contrato ideal para ML.

### Comparar Manual Vs Crawler

Manual:

```text
raw_transactions
```

Crawler:

```text
crawler_transactions
```

La version manual es preferida para el pipeline porque:

- El esquema es deterministico.
- Los tipos se controlan en codigo.
- Evita cambios inesperados por inferencia.

La version crawler sirve para aprender como Glue descubre datos en S3.

### Como Interpretarlo

Secuencia recomendada:

1. Mostrar `raw/` en S3.
2. Explicar que Glue Data Catalog guarda metadata, no copia datos.
3. Ejecutar `python -m src.register_catalog` y mostrar tablas manuales.
4. Ejecutar `bash scripts/run_glue_crawler.sh`.
5. Comparar `raw_transactions` vs `crawler_transactions`.
6. Elegir la tabla segun el objetivo: discovery con crawler o contrato controlado con tablas definidas en codigo.

Respuesta esperada:

- Para aprendizaje y exploracion, crawler es comodo.
- Para entrenamiento/inferencia, contrato explicito es mas seguro.
- En produccion pueden coexistir: crawler para discovery, tablas controladas para pipelines criticos.

### Errores Comunes Del Crawler

| Sintoma | Causa probable | Accion |
|---|---|---|
| No aparecen tablas `crawler_*` | El crawler no termino o fallo | Revisar `Last crawl` en Glue Console |
| `AccessDenied` leyendo S3 | El rol Glue no puede leer `raw/` o `crawler_demo/` | Actualizar permisos del rol o redeploy |
| Tabla con nombre inesperado | El crawler infirio otra raiz de tabla | Revisar estructura bajo `crawler_demo/` |
| Tipos diferentes a los manuales | Inferencia automatica distinta al contrato | Usar tabla manual para pipeline critico |
| Crawler tarda mas de lo esperado | Muchos archivos o prefijo amplio | Limitar el prefijo y usar datasets pequenos |

### Buenas Practicas

- Limitar crawlers a prefijos concretos.
- Evitar crawlear buckets completos en un laboratorio.
- Separar datos de demo (`crawler_demo/`) de tablas principales.
- Revisar cambios de schema antes de usarlos en ML.
- Ejecutarlos bajo demanda o con schedule controlado.
- Documentar costos y destruir recursos al terminar.

## 3. Usar AWS Glue Data Quality

El pipeline base ya genera calidad con Python:

```text
s3://<bucket>/quality/quality_report.json
```

La extension Glue Data Quality ejecuta reglas DQDL administradas por Glue contra la tabla:

```text
features_training
```

### Para Que Sirve En El Laboratorio

Glue Data Quality permite expresar reglas declarativas sobre una tabla del Data Catalog. En vez de escribir toda la validacion a mano, defines un ruleset con DQDL y AWS ejecuta una evaluacion administrada.

En este laboratorio hay dos niveles de calidad:

```text
quality_report.json       -> calidad controlada por codigo Python dentro del pipeline.
Glue Data Quality ruleset -> calidad administrada por AWS sobre features_training.
```

No se reemplazan. Se complementan:

- Python quality es transparente, versionable y facil de probar.
- Glue Data Quality conecta con capacidades nativas de AWS, consola, ejecuciones administradas y DQDL.

### Cuando Ejecutarlo

Ejecutalo despues de crear el dataset de entrenamiento:

```bash
bash scripts/run_processing_job.sh all
bash scripts/run_glue_data_quality.sh
```

No lo ejecutes antes de `run_processing_job.sh all`, porque la tabla `features_training` necesita datos bajo:

```text
s3://<bucket>/features/training_dataset/
```

### Flujo Interno Del Script

`bash scripts/run_glue_data_quality.sh` ejecuta:

```bash
python -m src.run_glue_data_quality
```

El modulo hace esta secuencia:

1. Verifica que exista `features/training_dataset.csv`.
2. Sincroniza la copia consultable por Glue/Athena:

```text
features/training_dataset.csv
-> features/training_dataset/training_dataset.csv
```

3. Registra o actualiza tablas Glue.
4. Crea o actualiza el ruleset `ml-data-prep-lab-features-training-quality`.
5. Ejecuta `StartDataQualityRulesetEvaluationRun` contra `features_training`.
6. Espera el estado final.
7. Descarga resultados con `GetDataQualityResult`.
8. Escribe un resumen en `quality/glue_data_quality_result.json`.

### Reglas Implementadas

Ruleset:

```text
Rules = [
  IsComplete "transaction_id",
  IsComplete "customer_id",
  IsComplete "amount",
  IsComplete "is_fraud",
  ColumnValues "amount" > 0,
  ColumnValues "is_fraud" in [0, 1],
  ColumnValues "split" in ["train", "validation", "test"]
]
```

Estas reglas validan que:

- IDs principales no sean nulos.
- `amount` no sea nulo y sea positivo.
- `is_fraud` sea binario.
- `split` tenga valores esperados.

### Como Leer Las Reglas

| Regla | Interpretacion | Riesgo Que Detecta |
|---|---|---|
| `IsComplete "transaction_id"` | No permite nulos en identificador de transaccion. | Filas imposibles de trazar. |
| `IsComplete "customer_id"` | No permite nulos en identificador de cliente. | Joins o features por cliente rotas. |
| `IsComplete "amount"` | No permite nulos en monto. | Features numericas incompletas. |
| `IsComplete "is_fraud"` | No permite nulos en target. | Entrenamiento supervisado invalido. |
| `ColumnValues "amount" > 0` | El monto debe ser positivo. | Datos raw no limpiados o errores de negocio. |
| `ColumnValues "is_fraud" in [0, 1]` | Target binario esperado. | Etiquetas fuera de contrato. |
| `ColumnValues "split" in [...]` | Split controlado. | Dataset de training mal construido. |

### Que Pasa Si Falla Una Regla

El script falla con `RuntimeError` si AWS Glue Data Quality devuelve `FAILED`, `STOPPED` o `TIMEOUT`.

En un proyecto real, esta falla se podria usar como quality gate:

```text
Si calidad falla -> no publicar features / no entrenar modelo.
Si calidad pasa  -> continuar a entrenamiento o inferencia batch.
```

En este laboratorio, el resultado se revisa manualmente para aprendizaje.

### Ejecutar

```bash
bash scripts/run_glue_data_quality.sh
```

O con Make:

```bash
make glue-data-quality
```

El script crea o actualiza bajo demanda el ruleset:

```text
ml-data-prep-lab-features-training-quality
```

El ruleset no se crea en CloudFormation porque en algunos entornos `AWS::Glue::DataQualityRuleset` puede fallar con `Internal Failure` durante el deploy. Ejecutarlo por script deja el despliegue base estable y mantiene Glue Data Quality como demo explicito.

### Outputs

Glue Data Quality guarda resultados administrados bajo:

```text
s3://<bucket>/quality/aws_glue_data_quality/
```

El laboratorio tambien guarda un resumen descargable:

```text
s3://<bucket>/quality/glue_data_quality_result.json
```

Para traerlo local:

```bash
bash scripts/download_reports.sh
```

Luego revisa:

```text
artifacts/local_outputs/quality/glue_data_quality_result.json
```

### Como Leer `glue_data_quality_result.json`

Campos utiles:

```text
ruleset_name        -> nombre del ruleset evaluado.
database            -> Glue database.
table               -> tabla evaluada.
run_id              -> identificador de ejecucion Glue Data Quality.
run.Status          -> estado global de la evaluacion.
results             -> resultados por regla.
results_s3_prefix   -> ubicacion S3 de resultados administrados.
```

Ejemplo de lectura esperada:

```json
{
  "ruleset_name": "ml-data-prep-lab-features-training-quality",
  "table": "features_training",
  "run": {
    "Status": "SUCCEEDED"
  }
}
```

Si necesitas buscar una regla fallida, abre el arreglo `results` y revisa los outcomes por regla. La estructura exacta puede variar segun la respuesta de AWS, pero el punto pedagogico es el mismo: cada regla DQDL debe poder trazarse a una condicion de calidad.

### Revisar En AWS Console

1. Abre AWS Glue.
2. Ve a `Data Catalog`.
3. Entra a `Data quality`.
4. Busca el ruleset:

```text
ml-data-prep-lab-features-training-quality
```

5. Revisa el resultado de la evaluacion.

Tambien puedes revisar desde la tabla:

1. AWS Glue.
2. `Data Catalog`.
3. `Tables`.
4. Abre `features_training`.
5. Busca opciones o tabs relacionadas con `Data quality`.

La consola cambia con el tiempo, asi que si no ves el panel exacto, usa el buscador interno de Glue para `Data quality`.

### Revisar Con AWS CLI

Listar rulesets:

```bash
aws glue list-data-quality-rulesets \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Ver ruleset:

```bash
aws glue get-data-quality-ruleset \
  --name ml-data-prep-lab-features-training-quality \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Ver el resumen descargable del laboratorio:

```bash
aws s3 cp \
  s3://<bucket>/quality/glue_data_quality_result.json \
  artifacts/local_outputs/quality/glue_data_quality_result.json \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

### Nota De Costo

Glue Data Quality ejecuta recursos administrados de Glue. Usalo como demo puntual y evita correrlo repetidamente sin necesidad.

### Como Agregar Una Nueva Regla

Edita `FEATURES_TRAINING_RULESET` en:

```text
src/run_glue_data_quality.py
```

Ejemplo conceptual:

```text
ColumnValues "age" between 18 and 100
```

Luego ejecuta:

```bash
bash scripts/run_glue_data_quality.sh
```

El script actualiza el ruleset si ya existe. No necesitas borrar el ruleset manualmente.

### Buenas Practicas

- Ejecutar reglas sobre tablas ya catalogadas y con datos existentes.
- Mantener reglas pequenas y explicables para estudiantes.
- Separar reglas criticas (`ERROR`) de reglas exploratorias en proyectos reales.
- Guardar resultados en S3 para auditoria.
- Usar Data Quality como gate antes de entrenar o publicar features.
- No ejecutar repetidamente sin necesidad porque genera costo.

### Error `aws-glue-ml-data-quality-assets`

Si la ejecucion falla con un mensaje como:

```text
LAUNCH ERROR | Error downloading from S3 for bucket: aws-glue-ml-data-quality-assets-us-east-1
Access Denied
```

el rol usado por Glue Data Quality no puede descargar las librerias administradas de AWS Glue Data Quality. El rol necesita:

```json
{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::aws-glue-ml-data-quality-assets-<region>/*"
}
```

Si usas el rol creado por este laboratorio, actualiza el stack:

```bash
bash scripts/deploy_infra.sh
```

Luego reintenta:

```bash
bash scripts/run_glue_data_quality.sh
```

Referencia oficial: https://docs.aws.amazon.com/glue/latest/dg/data-quality-trouble.html

### Error `same resourceName but a different internalId already exists`

Si ves:

```text
InvalidInputException: A resource with the same resourceName but a different internalId already exists
```

el ruleset se creo en un intento anterior, pero la evaluacion fallo despues. El script actual es idempotente: si el ruleset ya existe, lo actualiza y continua.

Reintenta:

```bash
bash scripts/run_glue_data_quality.sh
```

### Error `glue:GetDataQualityRulesetEvaluationRun`

Si ves:

```text
not authorized to perform: glue:GetDataQualityRulesetEvaluationRun
```

el rol de ejecucion de Glue Data Quality necesita permisos Glue Data Quality sobre el ruleset:

```json
{
  "Effect": "Allow",
  "Action": [
    "glue:GetDataQualityRuleset",
    "glue:GetDataQualityRulesetEvaluationRun",
    "glue:GetDataQualityResult",
    "glue:PublishDataQuality"
  ],
  "Resource": "arn:aws:glue:<region>:<account-id>:dataQualityRuleset/*"
}
```

Si usas el rol creado por este laboratorio, actualiza el stack:

```bash
bash scripts/deploy_infra.sh
```

Luego reintenta:

```bash
bash scripts/run_glue_data_quality.sh
```

## 4. Usar Glue Data Catalog Column Statistics

Column Statistics calcula estadisticas administradas por Glue Data Catalog para columnas de una tabla.

### Para Que Sirve En El Laboratorio

Column Statistics ayuda a responder:

```text
Que sabe el Glue Data Catalog sobre las columnas de esta tabla?
```

AWS Glue calcula estadisticas como minimos, maximos, nulos, valores distintos, longitudes promedio o conteos booleanos segun el tipo de dato. Estas estadisticas quedan asociadas a la tabla en el Data Catalog y pueden ayudar a servicios analiticos como Athena a planificar consultas.

No es lo mismo que `profiles/profile.json`:

```text
profile.json       -> profiling ML didactico creado por nuestro pipeline.
Column Statistics -> metadata administrada por Glue Catalog.
```

En este laboratorio se ejecuta contra:

```text
features_training
```

Columnas:

```text
amount
amount_log
customer_txn_count
amount_to_customer_avg
is_fraud
split
```

### Por Que Solo Se Calculan 6 Columnas

La tabla `features_training` tiene mas columnas que las seis listadas. El script calcula solo columnas clave para controlar costo, tiempo y claridad pedagogica.

Columnas elegidas:

- `amount`: monto base de negocio.
- `amount_log`: transformacion numerica usada como feature.
- `customer_txn_count`: agregacion por cliente.
- `amount_to_customer_avg`: ratio de comportamiento.
- `is_fraud`: target supervisado.
- `split`: particion logica del dataset.

Si quieres calcular estadisticas para mas columnas, edita `COLUMN_NAMES` en:

```text
src/run_glue_column_statistics.py
```

Si usas la API directamente y no pasas `ColumnNameList`, Glue puede intentar calcular estadisticas para todas las columnas. Para este laboratorio se prefiere una lista corta y explicable.

### Cuando Ejecutarlo

Ejecutalo despues del pipeline principal y despues de registrar catalogo:

```bash
bash scripts/run_processing_job.sh all
python -m src.register_catalog
bash scripts/run_glue_column_statistics.sh
```

El script tambien ejecuta `register_all_tables`, pero correr `python -m src.register_catalog` antes ayuda a que el estado sea visible para estudiantes.

### Flujo Interno Del Script

`bash scripts/run_glue_column_statistics.sh` ejecuta:

```bash
python -m src.run_glue_column_statistics
```

El modulo hace esta secuencia:

1. Verifica que exista `features/training_dataset.csv`.
2. Sincroniza la copia bajo el prefijo de tabla.
3. Registra o actualiza tablas Glue.
4. Llama `StartColumnStatisticsTaskRun` para `features_training`.
5. Pasa el rol Glue del laboratorio.
6. Pide muestra `SampleSize=100.0`.
7. Espera estado `SUCCEEDED`.
8. Consulta `GetColumnStatisticsForTable`.
9. Escribe una copia en `profiles/glue_column_statistics_features_training.json`.

### Ejecutar

```bash
bash scripts/run_glue_column_statistics.sh
```

O con Make:

```bash
make column-stats
```

### Output

El resultado se guarda como reporte del laboratorio:

```text
s3://<bucket>/profiles/glue_column_statistics_features_training.json
```

Para descargarlo:

```bash
bash scripts/download_reports.sh
```

Luego revisa:

```text
artifacts/local_outputs/profiles/glue_column_statistics_features_training.json
```

### Como Leer El Reporte Local

Campos utiles:

```text
database      -> Glue database.
table         -> tabla analizada.
column_names  -> columnas solicitadas.
task_run      -> estado de la tarea administrada.
statistics    -> estadisticas devueltas por Glue.
```

Ejemplo conceptual:

```json
{
  "table": "features_training",
  "column_names": ["amount", "amount_log", "customer_txn_count", "amount_to_customer_avg", "is_fraud", "split"],
  "task_run": {
    "Status": "SUCCEEDED"
  }
}
```

En la consola puedes ver algo como:

```text
Column statistics (6)
```

Eso es esperado en este laboratorio: hay 31 columnas en el schema, pero solo pedimos estadisticas para 6 columnas.

### Revisar En AWS Console

1. Abre AWS Glue.
2. Ve a `Data Catalog`.
3. Entra a `Tables`.
4. Abre:

```text
features_training
```

5. Busca la seccion `Column statistics`.

### Revisar Con AWS CLI

Ver estadisticas guardadas en Glue:

```bash
aws glue get-column-statistics-for-table \
  --database-name ml_data_prep_lab \
  --table-name features_training \
  --column-names amount amount_log customer_txn_count amount_to_customer_avg is_fraud split \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

Ver task runs recientes:

```bash
aws glue get-column-statistics-task-runs \
  --database-name ml_data_prep_lab \
  --table-name features_training \
  --profile mlops-2-data-prep-lab \
  --region us-east-1
```

### Diferencia Entre Profile Del Lab Y Column Statistics

`profiles/profile.json`:

- Lo genera el Glue Job del laboratorio.
- Incluye nulos, duplicados, dtypes, p95, top categoricos y comparaciones entre datasets.
- Es didactico y controlado por codigo.

Glue Column Statistics:

- Lo calcula AWS Glue Data Catalog.
- Sirve para estadisticas administradas por el catalogo.
- Puede ayudar a motores de consulta y tareas de catalogacion.
- No reemplaza completamente un reporte de profiling de ML.

### Como Interpretarlo

Usa esta comparacion:

| Pregunta | Mejor herramienta |
|---|---|
| Cuantos nulos, duplicados y top categorias tiene el dataset para ML? | `profiles/profile.json` |
| Que estadisticas conoce Glue Catalog para optimizar o describir columnas? | Column Statistics |
| Puedo usarlo como quality gate? | No directamente; usa Glue Data Quality |
| Puedo verlo en consola AWS? | Si, en la tabla Glue |

### Buenas Practicas

- Calcular estadisticas solo para columnas utiles.
- Recalcular despues de cambios importantes en datos.
- Usarlo como complemento de Athena y catalogacion, no como reemplazo de validaciones ML.
- Evitar calcular todas las columnas en datasets grandes sin necesidad.
- Asegurar que el rol tenga permisos sobre S3 y Glue Catalog.

### Error `Unable to Validate access to underlying S3 path`

Si ves:

```text
Unable to Validate access to underlying S3 path
```

el rol usado para Column Statistics no puede validar la ubicacion S3 de la tabla. AWS Glue Column Statistics asume el rol que se pasa en `StartColumnStatisticsTaskRun`, y ese rol debe poder listar el bucket y leer los objetos de la tabla.

Para el rol del laboratorio, actualiza el stack:

```bash
bash scripts/deploy_infra.sh
```

Luego reintenta:

```bash
bash scripts/run_glue_column_statistics.sh
```

Si usas `GLUE_ROLE_ARN` con un rol precreado, pide al administrador agregar:

```json
{
  "Effect": "Allow",
  "Action": [
    "s3:ListBucket",
    "s3:GetBucketLocation"
  ],
  "Resource": "arn:aws:s3:::<bucket-name>"
}
```

y:

```json
{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::<bucket-name>/*"
}
```

Referencia oficial: https://docs.aws.amazon.com/glue/latest/dg/column-stats-prereqs.html

## 5. Ejecutar Todos Los Extras Nativos

Despues de `make all-cloud`, puedes ejecutar:

```bash
make aws-native-extras
```

Equivale a:

```bash
python -m src.run_glue_crawler
python -m src.run_glue_data_quality
python -m src.run_glue_column_statistics
```

Luego descarga reportes:

```bash
bash scripts/download_reports.sh
```

Archivos locales esperados:

```text
artifacts/local_outputs/reports/glue_crawler_report.json
artifacts/local_outputs/quality/glue_data_quality_result.json
artifacts/local_outputs/profiles/glue_column_statistics_features_training.json
```

## 5.1 Secuencia Recomendada Para Recorrer Estos Tres Servicios

Usa esta historia:

```text
1. Ya tengo datos procesados en S3 y tablas principales en Glue.
2. Glue Crawler muestra discovery automatico sobre raw demo.
3. Glue Data Quality muestra reglas administradas sobre features_training.
4. Column Statistics muestra metadata estadistica administrada por Glue Catalog.
5. Athena permite consumir las tablas con SQL.
```

Comandos:

```bash
bash scripts/deploy_infra.sh
bash scripts/upload_sample_data.sh
python -m src.register_catalog
bash scripts/run_processing_job.sh all
python -m src.validate_outputs
bash scripts/run_glue_crawler.sh
bash scripts/run_glue_data_quality.sh
bash scripts/run_glue_column_statistics.sh
bash scripts/download_reports.sh
```

Orden pedagogico sugerido en consola:

1. S3: mostrar `raw/`, `features/`, `crawler_demo/`, `quality/`, `profiles/`.
2. Glue Tables: mostrar tablas manuales y `crawler_*`.
3. Glue Crawler: mostrar ultimo run.
4. Glue Data Quality: mostrar ruleset y evaluacion.
5. Glue Table `features_training`: mostrar schema y column statistics.
6. Athena: ejecutar queries de conteo y splits.

Resumen para estudiantes:

| Servicio | Rol en el laboratorio | Output visible |
|---|---|---|
| Glue Crawler | Descubre datasets y esquemas desde S3. | Tablas `crawler_*` y `glue_crawler_report.json`. |
| Glue Data Quality | Evalua reglas administradas DQDL. | Ruleset, evaluation run y `glue_data_quality_result.json`. |
| Column Statistics | Calcula estadisticas administradas por columna. | Seccion `Column statistics` y `glue_column_statistics_features_training.json`. |

## 6. Permisos Requeridos

Ademas de los permisos base del laboratorio, estos extras pueden requerir:

```text
glue:StartCrawler
glue:GetCrawler
glue:GetTables
glue:CreateDataQualityRuleset
glue:UpdateDataQualityRuleset
glue:GetDataQualityRuleset
glue:StartDataQualityRulesetEvaluationRun
glue:GetDataQualityRulesetEvaluationRun
glue:GetDataQualityResult
glue:PublishDataQuality
s3:GetObject sobre arn:aws:s3:::aws-glue-ml-data-quality-assets-<region>/*
glue:StartColumnStatisticsTaskRun
glue:GetColumnStatisticsTaskRuns
glue:GetColumnStatisticsForTable
iam:PassRole
athena:StartQueryExecution
athena:GetQueryExecution
athena:GetQueryResults
```

Si usas AWS IAM Identity Center, pide que se agreguen al Permission Set:

```text
MLOpsLab2Permission
```

## 7. Cleanup

El crawler creado por CloudFormation y el ruleset creado por `make glue-data-quality` se eliminan con:

```bash
bash scripts/destroy_infra.sh
```

Los objetos S3 bajo estos prefijos tambien se eliminan cuando el bucket del laboratorio se vacia:

```text
crawler_demo/
athena-results/
quality/aws_glue_data_quality/
```

## 8. Referencias Oficiales AWS

- Glue Data Catalog y crawlers: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
- Usar crawlers para poblar el Data Catalog: https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html
- Prerrequisitos de crawlers: https://docs.aws.amazon.com/glue/latest/dg/crawler-prereqs.html
- Glue Data Quality: https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html
- DQDL reference: https://docs.aws.amazon.com/glue/latest/dg/dqdl.html
- Column Statistics: https://docs.aws.amazon.com/glue/latest/dg/column-statistics.html
- Column Statistics API: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-crawler-column-statistics.html
