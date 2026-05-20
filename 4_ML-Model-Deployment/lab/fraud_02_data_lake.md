# Fraud 02 - Data Lake en S3: raw, cleaned y curated

## Objetivo

Construir las capas principales del Data Lake de fraude en Amazon S3 y demostrar la diferencia entre datos crudos, datos limpios, datos curados, labels y artefactos de contrato de features.

Este paso prepara la base de datos historica y de scoring que luego alimenta Feature Store, batch prediction y retraining.

## Que vas a construir o validar

Este paso escribe en S3:

- `lake/raw/`: eventos tal como llegan desde sistemas transaccionales o archivos de entrada.
- `lake/cleaned/`: eventos validados, canonizados y con tipos consistentes.
- `lake/curated/`: tablas de negocio listas para analitica y feature engineering.
- `lake/curated/fraud_labels.csv`: labels tardios para retraining.
- `artifacts/preprocessing/`: contrato de features y orden esperado del modelo.

El paso ejecuta tres fases:

1. Generacion sintetica: crea datos base y ejemplos de outputs esperados.
2. Raw -> cleaned: toma raw como fuente y produce eventos canonizados.
3. Cleaned -> curated: agrega contexto de negocio y produce tablas CSV.

## Input del paso

Datos sinteticos generados por el laboratorio:

```json
{
  "transaction_id": "T001",
  "amount": "500",
  "currency": "pen",
  "location": "Lima|PE",
  "timestamp": "17/05/2026 14:20",
  "category": "Electronics"
}
```

Configuracion requerida desde `.env.cloud`:

```bash
S3_BUCKET_NAME=<bucket>
FRAUD_S3_PREFIX=ml-deploy-lab/lab/fraud
```

## Output esperado del paso

El comando imprime URIs como estas. Cada archivo cumple un rol diferente dentro de la arquitectura:

| Nombre impreso | S3 URI | Contenido | Uso posterior |
| --- | --- | --- | --- |
| `historical_raw` | `lake/raw/historical_transactions.jsonl` | Transacciones historicas exactamente como llegaron: strings, timestamp regional, location compacta, monto como texto. | Fuente de auditoria, replay y reconstruccion de pipelines. |
| `batch_raw` | `lake/raw/transactions_to_score_raw.jsonl` | Transacciones futuras o pendientes de scoring batch en formato crudo. | Entrada conceptual para preparar batch prediction sin consultar servicios online registro por registro. |
| `online_sample` | `lake/raw/online_transaction.json` | Una transaccion individual tipo API request. | Ejemplo que se usa para explicar el camino online del paso 05. |
| `historical_cleaned` | `lake/cleaned/historical_transactions.jsonl` | Historico normalizado: `amount` numerico, `currency` uppercase, `timestamp` ISO, `city` y `country` separados. | Base deterministica para curated y Feature Store. |
| `batch_cleaned` | `lake/cleaned/transactions_to_score.jsonl` | Lote de scoring ya canonizado y sin target. | Base limpia para construir `transactions_to_score.csv`. |
| `historical_curated` | `lake/curated/historical_transactions.csv` | Tabla de negocio: transaccion + usuario + tarjeta + merchant + device + monto en PEN + estado. | Fuente para generar features historicas y dataset de retraining. |
| `batch_curated` | `lake/curated/transactions_to_score.csv` | Transacciones business-ready que deben puntuarse en batch. | Entrada del paso 07 junto con Offline Store. |
| `labels` | `lake/curated/fraud_labels.csv` | Labels que llegan despues de la transaccion: chargeback, revision manual o disputa. | Target supervisado del paso 08. |
| `feature_contract` | `artifacts/preprocessing/feature_contract.yaml` | Definicion de features actuales, features de Online Store, tipos, defaults y version. | Contrato usado por online, batch, retraining y Model Registry. |
| `feature_order` | `artifacts/preprocessing/feature_order.json` | Orden exacto del vector que espera el modelo. | Evita training-serving skew. |

## Conceptos claves

Raw Layer conserva el evento exactamente como llego. No intenta corregir formatos ni inferir reglas de negocio. Si `amount` llega como `"500"`, `currency` como `"pen"` y `timestamp` como `"17/05/2026 14:20"`, raw conserva esa forma. Esta capa sirve para auditoria, replay, debugging y reprocesamiento cuando cambian las reglas de limpieza.

Cleaned Layer aplica validacion y canonicalizacion. `amount` pasa a tipo numerico, `currency` se normaliza a uppercase, `timestamp` se convierte a ISO 8601, `location` se separa en `city` y `country`, `category` y `channel` se normalizan. Esta capa reduce ambiguedad para que los pasos siguientes no tengan que interpretar formatos regionales o strings inconsistentes.

Curated Layer agrega contexto de negocio. Una transaccion limpia se enriquece con atributos como segmento de cliente, edad de cuenta, tipo de merchant, pais normalizado, estado operacional o monto convertido. Curated es business-ready: es util para analitica, reportes y feature engineering, pero no necesariamente es model-ready.

Feature Store nace despues de curated. Las features model-ready pueden derivarse de curated, pero se publican con otro contrato: entidad, `event_time`, tipos, defaults, version y orden esperado. Esta separacion evita que una tabla analitica sea usada accidentalmente como input del modelo sin validacion.

Labels no pertenecen al camino online. En fraude, el label puede llegar horas o dias despues por chargeback, revision manual o reclamo. Por eso `fraud_labels.csv` se guarda en curated para retraining, no para la prediccion actual.

El Data Lake usa S3 como almacenamiento durable, barato y desacoplado. S3 no impone por si mismo un contrato de esquema; el contrato lo define el pipeline y los artefactos `feature_contract.yaml` y `feature_order.json`.

## Flujo arquitectonico de este paso

```text
Synthetic source data
  -> S3 raw
  -> cleaning/canonicalization
  -> S3 cleaned
  -> business enrichment
  -> S3 curated
  -> feature contract artifacts
```

El resultado no crea Feature Groups todavia. Solo deja los datos organizados para que el paso 03 publique features en SageMaker Feature Store.

## Prerrequisitos

- Haber ejecutado `fraud-step 01`.
- `.env.cloud` con bucket y prefijo de fraude.
- Permisos `s3:PutObject` y `s3:GetObject`.

## Pasos de ejecucion

Ejecutar:

```bash
python -m src.lab_runner fraud-step 02
```

Comandos directos equivalentes:

```bash
python -m fraud_lab.aws.pipelines.generate_synthetic_data_aws
python -m fraud_lab.aws.pipelines.raw_to_cleaned_aws
python -m fraud_lab.aws.pipelines.cleaned_to_curated_aws
```

## Resultado esperado

S3 contiene datos crudos, limpios y curados. Tambien quedan disponibles `feature_contract.yaml` y `feature_order.json`, que se usaran para ensamblar el vector de features de online, batch y retraining.

## Validacion local

El comando imprime las URIs generadas. Tambien puedes validar que la configuracion cargue:

```bash
python -m src.config --check-aws
```

## Validacion en consola AWS

En S3, navega al bucket y prefijo:

```text
<FRAUD_S3_PREFIX>/lake/raw/
<FRAUD_S3_PREFIX>/lake/cleaned/
<FRAUD_S3_PREFIX>/lake/curated/
<FRAUD_S3_PREFIX>/artifacts/preprocessing/
```

Abre un archivo raw y uno cleaned para comparar normalizacion de `amount`, `currency`, `location` y `timestamp`. Abre un curated CSV para confirmar que ya contiene contexto de negocio y no solo el payload original.
