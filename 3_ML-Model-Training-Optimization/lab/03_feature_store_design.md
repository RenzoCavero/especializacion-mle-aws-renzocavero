# 03 - Diseno de SageMaker Feature Store

## Objetivo

Crear e ingestar un Feature Group en SageMaker Feature Store para reutilizar features en entrenamiento, batch inference y real-time inference.

## Que vas a construir o validar

Vas a crear el Feature Group configurado en `.env`:

```text
FEATURE_GROUP_NAME=churn-customer-features
```

El Feature Group tendra:

| Componente | Valor |
|---|---|
| Record identifier | `customer_id` |
| Event time feature | `event_time` |
| Online Store | habilitado por `ENABLE_ONLINE_STORE=true` |
| Offline Store | `s3://<S3_BUCKET>/feature-store-offline/` |
| Glue table | creada en AWS Glue Data Catalog si Offline Store esta habilitado |

## Conceptos clave

- SageMaker Feature Store: repositorio gestionado para almacenar, consultar y compartir features.
- Feature Group: definicion del schema de features y su almacenamiento.
- Online Store: almacenamiento de baja latencia para inferencia en tiempo real.
- Offline Store: almacenamiento historico en S3 para entrenamiento, analitica y batch inference.
- AWS Glue Data Catalog: catalogo donde Feature Store puede registrar metadata tabular del Offline Store.

## Como se comportan Online Store y Offline Store

Cuando el laboratorio ejecuta `src.ingest_features`, cada fila del CSV se envia a SageMaker Feature Store con `PutRecord`.

Si el Feature Group tiene Online Store y Offline Store habilitados, SageMaker maneja dos destinos:

| Store | Escritura | Lectura principal | Uso tipico |
|---|---|---|---|
| Online Store | Casi inmediata para el `RecordIdentifier` | `GetRecord` por `customer_id` | Inferencia en tiempo real. |
| Offline Store | Asincrona; puede tardar minutos en aparecer en S3 | Consulta historica en S3, Glue o Athena | Entrenamiento, batch inference, auditoria y analitica. |

En este laboratorio:

```text
RecordIdentifier = customer_id
EventTimeFeature = event_time
```

Si ingestas una nueva version de features para `CUST-000001` con un `event_time` mas reciente:

1. Online Store queda actualizado para consultas de baja latencia por `customer_id`.
2. Offline Store guarda el registro historico en S3, pero la escritura puede aparecer despues de unos minutos.
3. `GetRecord` sobre Online Store devuelve el estado actual del record para ese `customer_id`; no devuelve todo el historial.
4. Para revisar versiones anteriores por timestamp, usa Offline Store en S3, normalmente consultado con Glue/Athena o leyendo los objetos historicos.

Esto permite usar Online Store para servir predicciones actuales y Offline Store para reconstruir datasets historicos.

## Uso real del Offline Store en este laboratorio

El Offline Store se crea y se valida en este paso, pero los siguientes pasos del laboratorio no lo consultan directamente.

Durante la ingesta, `src.ingest_features` tambien sube un snapshot CSV a:

```text
s3://<S3_BUCKET>/processing/input/churn_features.csv
```

Ese snapshot es el input directo del Processing Job del paso 04. Luego HPO entrena con los datasets que el Processing Job genera en:

```text
s3://<S3_BUCKET>/input/train/train.csv
s3://<S3_BUCKET>/input/validation/validation.csv
```

Flujo real del laboratorio:

```text
data/local_cache/churn_raw.csv
    |
    v
PutRecord to Feature Store
    |
    +--> Online Store
    +--> Offline Store in S3
    |
    v
Snapshot CSV: processing/input/churn_features.csv
    |
    v
Processing Job
    |
    v
train/validation/test CSVs in S3
    |
    v
Training Job and HPO
```

En una arquitectura mas cercana a produccion, el Processing Job podria leer desde el Offline Store usando S3, AWS Glue Data Catalog o Amazon Athena. Ese job construiria el dataset de entrenamiento a partir del historial versionado, aplicaria transformaciones, splits y validaciones, y escribiria los datasets finales en S3.

Incluso en ese diseno, HPO no entrenaria directamente desde Feature Store. HPO seguiria recibiendo canales de entrenamiento y validacion en S3, por ejemplo:

```text
Offline Store -> Processing/Athena query -> train.csv + validation.csv -> HPO
```

La diferencia es que la fuente historica seria el Offline Store en lugar del snapshot CSV que usa este laboratorio para simplificar la ejecucion.

## Prerrequisitos

1. Ejecuta desde:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Completa los pasos 01 y 02.

3. Confirma que existe:

   ```text
   data/local_cache/churn_raw.csv
   ```

4. Confirma que `.env.cloud` incluye bucket y rol de SageMaker.

5. El rol de SageMaker debe tener `s3:GetBucketAcl`, permisos de escritura en S3 y permisos Glue sobre `sagemaker_featurestore`.

## Pasos de ejecucion

Comando recomendado:

```bash
make lab-03-feature-store
```

Con Bash o Git Bash, por partes:

```bash
bash scripts/create_feature_group.sh
bash scripts/ingest_features.sh
python -m src.get_online_features
python -m src.query_offline_store
```

En Windows PowerShell, por partes:

```powershell
.\scripts\create_feature_group.ps1
.\scripts\ingest_features.ps1
python -m src.get_online_features
python -m src.query_offline_store
```

Con Python:

```bash
python -m src.create_feature_group
python -m src.ingest_features
python -m src.get_online_features
python -m src.query_offline_store
```

Internamente:

1. `src.create_feature_group` crea o reutiliza el Feature Group.
2. `src.ingest_features` envia registros con `PutRecord`.
3. `src.get_online_features` valida un `GetRecord` desde Online Store.
4. `src.query_offline_store` lista objetos visibles en S3 bajo Offline Store.

## Resultado esperado

Archivos locales:

```text
artifacts/local_outputs/online_store_get_record.json
artifacts/local_outputs/offline_store_validation.txt
artifacts/local_outputs/run_state.json
```

S3:

```text
s3://<S3_BUCKET>/feature-store-offline/
s3://<S3_BUCKET>/processing/input/churn_features.csv
```

El Offline Store escribe de forma asincrona. Puede tardar varios minutos en mostrar objetos en S3.

## Validacion local

1. Abre `artifacts/local_outputs/online_store_get_record.json`.
2. Confirma que incluye `customer_id`, `record` y `future_realtime_payload_without_target`.
3. Abre `artifacts/local_outputs/offline_store_validation.txt`.
4. Confirma que lista objetos en `feature-store-offline/` o que indica que la materializacion aun no es visible.

## Validacion en la consola AWS

1. Abre AWS Console.
2. Ve a Amazon SageMaker AI > Dashboard.
3. En `All active resources`, revisa `Data prep`.
4. Confirma que `Total feature groups` muestre al menos `1 Created`.

Ese contador confirma que el Feature Group existe, pero puede no abrir el detalle completo desde el dashboard. Para ver el catalogo detallado:

1. En Amazon SageMaker AI, crea o abre un SageMaker Domain.
2. Si la consola muestra `Preparing SageMaker domain`, espera a que termine la preparacion.
3. Crea o selecciona un user profile.
4. Entra a SageMaker Studio.
5. Dentro de Studio, ve a `More` > `Feature Store`.
6. Abre la pestana `Feature Group Catalog`.
7. Selecciona `My account`.
8. Busca `churn-customer-features`.
9. Verifica que el estado sea `Created`.
10. Abre el Feature Group y revisa `Feature definitions`.
11. Confirma que existen columnas como `customer_id`, `event_time`, `plan_type`, `engagement_score` y `churn_label`.
12. Confirma `Record identifier` = `customer_id`.
13. Confirma que el tipo de store sea `both`, es decir, Online Store y Offline Store.

La creacion del SageMaker Domain es necesaria solo para usar la interfaz detallada de Studio. El Feature Group ya fue creado por el script aunque aun no hayas entrado a Studio.

Para validar Offline Store:

1. Ve a Amazon S3 > bucket del laboratorio.
2. Abre el prefijo `feature-store-offline/`.
3. Confirma que aparecen objetos o particiones generadas por Feature Store.

Si tienes acceso a AWS Glue:

1. Ve a AWS Glue Data Catalog > Databases.
2. Busca la base `sagemaker_featurestore`.
3. Revisa si existe una tabla asociada al Feature Group.

## Validacion opcional por CLI

```bash
aws sagemaker describe-feature-group \
  --feature-group-name churn-customer-features \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `AccessDenied` con `s3:GetBucketAcl` | El rol de SageMaker no tiene permiso para validar el bucket. | Reejecuta el paso 01 para actualizar la politica IAM. |
| Feature Group queda en `CreateFailed` | Permisos S3, Glue o rol incorrectos. | Revisa eventos del error en SageMaker y permisos del rol. |
| Online Store no devuelve record | La ingesta no termino o el cliente no existe. | Reejecuta `python -m src.ingest_features` y luego `python -m src.get_online_features`. |
| Offline Store no muestra objetos | Escritura asincrona de Feature Store. | Espera unos minutos y reejecuta `python -m src.query_offline_store`. |
| Solo ves `Total feature groups` en el dashboard, pero no el detalle | La vista detallada de Feature Store esta dentro de SageMaker Studio. | Crea o abre un SageMaker Domain, entra a Studio y navega a `More` > `Feature Store`. |

## Conexion con laboratorios futuros

El Online Store se usara para construir payloads de inferencia en tiempo real. El Offline Store o datasets derivados se usaran para inferencia batch.
