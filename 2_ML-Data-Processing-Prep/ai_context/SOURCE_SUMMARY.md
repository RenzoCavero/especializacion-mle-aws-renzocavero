# Resumen De Fuentes Del Tema 2

## Documentos Inspeccionados

Fuente principal disponible:

```text
doc/AWS_Data_Processing_and_preparation.pdf
```

El PDF corresponde a una presentacion sobre preparacion de datos en AWS para Machine Learning. El contenido extraido se resume aqui de forma estructurada; no se copia texto largo del documento.

## Conceptos Principales

### Por Que La Preparacion De Datos Importa

La calidad del dato define el limite real del modelo. Un modelo sofisticado no compensa datos incompletos, duplicados, sesgados, mal representados o inconsistentes.

La preparacion de datos reduce ruido, errores y reprocesos. Tambien mejora la estabilidad en produccion porque disminuye diferencias entre lo que el modelo vio durante entrenamiento y lo que recibira durante inferencia.

### De Datos Crudos A Datos Listos Para ML

El material presenta una evolucion por etapas:

- Datos crudos: logs, eventos, archivos, tablas transaccionales o fuentes heterogeneas.
- Datos limpios: registros con nulos, duplicados, errores y rangos invalidos tratados.
- Datos curados: esquemas validados, joins aplicados, reglas de negocio incorporadas y formatos consistentes.
- Features: variables numericas o categoricas preparadas para aprendizaje.
- Datasets de entrenamiento e inferencia: matrices reproducibles para entrenamiento, validacion, prueba o prediccion.

### Fundamento De Data Lake En AWS

Un data lake permite almacenar datos de distintas fuentes y niveles de procesamiento manteniendo separacion por zonas. En AWS, Amazon S3 es el componente central para este patron por costo, durabilidad, integracion con Glue, Athena, SageMaker y herramientas de seguridad.

### Capas Raw, Cleaned, Curated Y Features

El material destaca la separacion por capas:

- `raw/`: datos originales, sin modificar, usados como fuente auditable.
- `cleaned/`: datos con errores basicos corregidos.
- `curated/`: datos integrados, con reglas de negocio y esquema validado.
- `features/`: senales listas para entrenamiento o inferencia.
- `inference/`: datasets recientes o sin etiqueta para prediccion.

### Calidad De Datos Y Profiling

Antes de limpiar o transformar, se debe medir la salud del dataset. El profiling debe identificar:

- Nulos.
- Duplicados.
- Tipos de datos.
- Cardinalidad.
- Distribuciones.
- Outliers.
- Valores fuera de rango.
- Columnas con bajo valor predictivo.
- Posibles fugas de informacion.

### Limpieza Y Transformacion

La preparacion incluye normalizacion, imputacion, deduplicacion, filtrado, conversion de tipos, codificacion de categoricas, agregaciones y enriquecimiento con contexto. La meta es convertir datos inconsistentes en senales estables y utiles.

### SageMaker Data Wrangler

Data Wrangler aparece como herramienta para exploracion visual, profiling rapido, transformaciones preconstruidas y exportacion de flujos hacia pipelines. Es util para prototipado rapido y validacion visual, aunque el laboratorio debe preservar reproducibilidad mediante scripts e infraestructura.

### SageMaker Processing

SageMaker Processing permite ejecutar jobs efimeros y reproducibles para profiling, validacion, limpieza, transformacion, feature engineering y generacion de datasets. Encaja bien cuando se quiere ejecutar codigo Python controlado con entradas y salidas en S3.

### AWS Glue Para ETL Y Catalogacion

AWS Glue se asocia a descubrir, catalogar, transformar y dejar datasets trazables para analitica y ML. Glue Data Catalog debe registrar metadatos de tablas y ubicaciones S3. Glue Jobs o Crawlers pueden usarse para ETL y descubrimiento de esquema cuando el laboratorio lo requiera.

### SageMaker Ground Truth Para Etiquetado

Ground Truth se relaciona con convertir datos sin etiquetas en datasets supervisados, validados y listos para entrenamiento. Para este laboratorio se recomienda usar etiquetas sinteticas, pero documentar como Ground Truth podria incorporarse si existiera etiquetado humano o semiautomatico.

### Feature Engineering

Feature engineering crea senales predictivas a partir de datos operacionales. En un caso de fraude o riesgo puede incluir agregaciones por cliente, conteos de transacciones, frecuencia reciente, desviacion contra comportamiento historico, ratios, codificacion de canal o comercio, y variables temporales.

### SageMaker Feature Store

Feature Store permite compartir features entre entrenamiento e inferencia. En este laboratorio puede ser opcional, pero la estructura debe dejar preparada la capa `features/` como equivalente de offline store y documentar como evolucionaria hacia Feature Store.

### Consistencia Entrenamiento/Inferencia

La logica de features debe reutilizarse para entrenamiento e inferencia. Si se calculan features de forma distinta en produccion, el modelo predice sobre datos que no representan lo aprendido.

### Training-Serving Skew

Training-serving skew es la diferencia entre las features usadas durante entrenamiento y las usadas durante inferencia. El laboratorio debe evitarlo con funciones compartidas, tests de esquema y documentacion clara del contrato de features.

### Gobernanza, Seguridad Y Lineage

La preparacion de datos debe controlar acceso, proteger datos y rastrear decisiones desde la fuente hasta el modelo. Esto incluye IAM, cifrado, logs, catalogo, lineage y dataset cards.

### Caso De Uso

El material sugiere llevar eventos crudos hacia features, modelo, inferencia y accion operativa. Para este laboratorio se recomienda deteccion de fraude o scoring de riesgo, aunque tambien podria adaptarse a forecasting o mantenimiento predictivo.

## Como Se Traduce Este Material Al Laboratorio En AWS

- Data lake en AWS -> Amazon S3 con carpetas `raw`, `cleaned`, `curated`, `features` e `inference`.
- Datos crudos -> archivos sinteticos cargados en `s3://<bucket>/raw/`.
- Datos limpios -> outputs de limpieza en `s3://<bucket>/cleaned/`.
- Datos curados -> datasets integrados y con reglas de negocio en `s3://<bucket>/curated/`.
- Features -> archivos versionables en `s3://<bucket>/features/` y posible extension a SageMaker Feature Store offline store.
- Dataset de inferencia -> registros sin etiqueta en `s3://<bucket>/inference/`.
- AWS Glue -> Data Catalog para tablas y, opcionalmente, Crawlers o Jobs ETL.
- SageMaker Processing -> jobs reproducibles para profiling, calidad, limpieza, transformacion y feature engineering.
- SageMaker Data Wrangler -> referencia conceptual para exploracion visual y prototipado, documentada sin hacerla dependencia obligatoria.
- SageMaker Ground Truth -> extension conceptual para etiquetado supervisado si se reemplazan etiquetas sinteticas.
- Data quality -> reportes en S3 bajo `quality/`.
- Profiling -> reportes en S3 bajo `profiles/`.
- Lineage -> reportes en S3 bajo `lineage/`.
- Dataset card -> reporte Markdown o JSON en S3 bajo `reports/`.
- Seguridad -> IAM de minimo privilegio, bloqueo de acceso publico en S3 y cifrado.
- Operacion -> logs en CloudWatch y comandos de deploy, ejecucion, validacion y cleanup.
