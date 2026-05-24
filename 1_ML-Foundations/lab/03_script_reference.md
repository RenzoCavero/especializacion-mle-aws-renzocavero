# Referencia Detallada De Scripts

Esta guia explica que hace cada script principal del laboratorio, que archivos consume y genera, y como cada paso influye en el proceso de Machine Learning.

## Vista General Del Flujo

| Orden | Comando | Fase ML | Equivalente AWS conceptual |
|---:|---|---|---|
| 1 | `python -m src.generate_dataset` | Datos crudos / definicion del caso | Amazon S3 raw zone / sistemas transaccionales |
| 2 | `python -m src.data_preparation` | ETL, calidad y feature engineering | AWS Glue / SageMaker Processing |
| 3 | `python -m src.train` | Entrenamiento y seleccion de umbral | SageMaker Training Jobs |
| 4 | `python -m src.evaluate` | Evaluacion con datos no vistos | SageMaker Experiments / Pipeline Evaluation Step |
| 5 | `python -m src.batch_inference` | Inferencia por lotes | SageMaker Batch Transform |
| 6 | `python -m src.monitor` | Monitoreo y feedback | SageMaker Model Monitor + CloudWatch |
| 7 | `python -m src.model_card` | Gobernanza y documentacion | SageMaker Model Cards / Model Registry |

## 1. `python -m src.generate_dataset`

### Que Hace

Genera un dataset sintetico de transacciones para el caso de deteccion de fraude. Simula variables que suelen influir en riesgo transaccional:

- Monto.
- Categoria de comercio.
- Pais.
- Canal.
- Dispositivo.
- Hora y dia.
- Edad del cliente.
- Velocidad transaccional.
- Promedio historico de monto.
- Tasa historica de contracargos.
- Distancia desde ubicacion habitual.
- Indicadores de transaccion extranjera y comercio de alto riesgo.

Tambien crea un archivo de batch scoring sin label, para simular transacciones futuras que necesitan prediccion.

### Entradas

No requiere archivos previos. Usa configuracion centralizada en `src/config.py`.

Parametros opcionales:

```bash
python -m src.generate_dataset --rows 5000 --batch-rows 250 --seed 42
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `data/raw/fraud_transactions.csv` | Dataset crudo con features y label `is_fraud`. |
| `data/raw/batch_scoring_input.csv` | Muestra sin label para batch inference. |
| `data/raw/dataset_metadata.json` | Metadatos de generacion, filas, tasa de fraude y seed. |

### Variables Generadas En El Dataset

Estas columnas aparecen en `data/raw/fraud_transactions.csv`. El archivo `data/raw/batch_scoring_input.csv` contiene las mismas variables excepto `is_fraud`, porque simula datos futuros sin etiqueta conocida.

| Variable | Tipo | Descripcion breve | Ejemplos posibles |
|---|---|---|---|
| `transaction_id` | Identificador | ID unico de la transaccion. Permite trazabilidad entre datos crudos, batch inference y predicciones. | `txn_0000001`, `txn_0002781` |
| `customer_id` | Identificador | ID sintetico del cliente asociado a la transaccion. No representa una persona real. | `cus_12345`, `cus_98765` |
| `event_timestamp` | Fecha/hora | Momento sintetico de la transaccion dentro de una ventana simulada desde enero de 2026. | `2026-01-15 10:30:00`, `2026-02-01 02:14:00` |
| `amount` | Numerica | Monto de la transaccion. Se genera con una distribucion sesgada para simular muchos pagos pequenos y pocos pagos altos. | `12.50`, `87.32`, `450.00`, `1250.75` |
| `merchant_category` | Categorica | Categoria del comercio. Algunas categorias se tratan como mas riesgosas en la generacion del label. | `grocery`, `electronics`, `travel`, `digital_goods`, `money_transfer`, `luxury` |
| `country` | Categorica | Pais asociado a la transaccion. `PE` es el pais base; otros paises pueden activar `is_foreign_transaction`. | `PE`, `CO`, `CL`, `MX`, `US`, `BR` |
| `channel` | Categorica | Canal de captura de la transaccion. Algunos canales digitales pueden tener mas riesgo simulado. | `pos`, `web`, `mobile`, `api` |
| `device_type` | Categorica | Tipo de dispositivo o contexto desde donde ocurre la transaccion. | `card_present`, `ios`, `android`, `desktop`, `unknown` |
| `hour` | Numerica entera | Hora del dia entre 0 y 23. Se usa luego para crear `is_night`. | `0`, `2`, `10`, `17`, `23` |
| `day_of_week` | Numerica entera | Dia de la semana en formato pandas: lunes `0`, domingo `6`. | `0`, `2`, `5`, `6` |
| `customer_age_days` | Numerica entera | Antiguedad sintetica del cliente en dias. Clientes muy nuevos pueden ser utiles para analisis de riesgo. | `10`, `120`, `365`, `2400` |
| `transactions_last_24h` | Numerica entera | Cantidad de transacciones recientes del cliente. Simula velocidad transaccional. | `0`, `2`, `5`, `12` |
| `avg_amount_30d` | Numerica | Promedio sintetico del monto del cliente en los ultimos 30 dias. Sirve como referencia historica. | `25.40`, `80.00`, `215.75` |
| `chargeback_rate_90d` | Numerica | Tasa historica sintetica de contracargos del cliente en 90 dias. Va de 0 a 1. | `0.0000`, `0.0250`, `0.0800`, `0.2100` |
| `distance_from_home_km` | Numerica | Distancia sintetica respecto a una ubicacion habitual del cliente. Valores altos pueden indicar anomalia. | `0.50`, `15.00`, `180.00`, `650.00` |
| `is_foreign_transaction` | Binaria | Indica si la transaccion ocurre fuera del pais base `PE`. | `0`, `1` |
| `is_high_risk_merchant` | Binaria | Indica si la categoria pertenece a un grupo de mayor riesgo simulado: `digital_goods`, `money_transfer` o `luxury`. | `0`, `1` |
| `is_fraud` | Target binario | Etiqueta sintetica que indica si la transaccion es fraudulenta. Es la variable objetivo del problema ML. | `0`, `1` |

Ejemplo simplificado de una fila:

```text
transaction_id=txn_0002781
customer_id=cus_37986
event_timestamp=2026-01-31 17:29:00
amount=87.32
merchant_category=digital_goods
country=US
channel=mobile
device_type=android
hour=17
day_of_week=5
customer_age_days=120
transactions_last_24h=8
avg_amount_30d=75.00
chargeback_rate_90d=0.0800
distance_from_home_km=180.00
is_foreign_transaction=1
is_high_risk_merchant=1
is_fraud=1
```

### Como Se Construye El Riesgo Sintetico

`generate_dataset` no asigna fraude al azar puro. Primero calcula una probabilidad de fraude a partir de senales de riesgo, por ejemplo:

- comercio de alto riesgo;
- transaccion extranjera;
- horario nocturno;
- muchas transacciones en 24 horas;
- monto muy superior al promedio historico;
- distancia alta desde ubicacion habitual;
- historial de contracargos;
- canal y dispositivo.

Luego usa esa probabilidad para crear `is_fraud`. Esto permite que el modelo tenga patrones aprendibles, no solo ruido.

### Como Influye En El Proceso ML

Este paso define la distribucion inicial de datos y el problema supervisado. Si el dataset esta mal disenado, el resto del pipeline puede producir metricas poco utiles. En el material fuente, esto conecta con la idea de pasar de objetivo de negocio a problema ML: reducir fraude se traduce en una clasificacion binaria / scoring de riesgo.

### Equivalente AWS

Representa datos producidos por sistemas transaccionales y almacenados en una zona cruda de Amazon S3. En un proyecto real, estos datos podrian venir de aplicaciones, logs, bases transaccionales, Kinesis, RDS, DynamoDB o un data lake.

## 2. `python -m src.data_preparation`

### Que Hace

Convierte datos crudos en datasets entrenables. Ejecuta validaciones, transformaciones y separacion train/test.

Transformaciones principales:

- Valida columnas obligatorias.
- Convierte campos numericos.
- Normaliza categorias a minusculas.
- Crea `amount_log`.
- Crea `amount_to_avg_ratio`.
- Crea `is_night`.
- Crea `velocity_amount_score`.
- Genera split estratificado para conservar proporcion de fraude.
- Separa un archivo de batch input procesado sin label.
- Crea perfil de datos y schema de features.

### Transformaciones Con Ejemplos Cortos

| Transformacion | Que busca | Ejemplo corto |
|---|---|---|
| Validacion de columnas obligatorias | Evitar que el pipeline entrene con datos incompletos o incompatibles. | Si falta `amount`, el script falla antes de crear `train.csv`. |
| Conversion numerica | Asegurar que campos como monto, hora o distancia puedan usarse en calculos. | `"450.0"` como texto pasa a `450.0` numerico. |
| Limpieza de `amount` | Evitar montos negativos en datos preparados. | `amount=-10.0` se ajustaria a `0.0`. |
| Limpieza de `avg_amount_30d` | Evitar division por cero al comparar monto actual contra promedio historico. | `avg_amount_30d=0` se ajusta a un minimo de `1.0`. |
| Normalizacion de categorias | Reducir duplicados por diferencias de mayusculas/minusculas. | `Digital_Goods` pasa a `digital_goods`. |
| `amount_log` | Reducir el impacto de montos extremadamente altos y suavizar distribuciones sesgadas. | Si `amount=100`, entonces `amount_log=log(101)=4.615`. |
| `amount_to_avg_ratio` | Medir que tan grande es el monto frente al comportamiento historico del cliente. | Si `amount=150` y `avg_amount_30d=50`, entonces `amount_to_avg_ratio=3.0`. |
| `is_night` | Capturar comportamiento potencialmente anomalo por horario. | Si `hour=2`, entonces `is_night=1`; si `hour=14`, entonces `is_night=0`. |
| `velocity_amount_score` | Combinar velocidad reciente y monto relativo para capturar bursts de gasto. | Si `transactions_last_24h=8` y `amount_to_avg_ratio=3`, entonces `log(9)*3=6.59`. |
| Casting de `is_fraud` | Asegurar que el target sea binario entero. | `"1"` o `1.0` pasa a `1`. |
| Split estratificado | Mantener una proporcion similar de fraude en train y test. | Si el dataset tiene cerca de 9% fraude, train y test quedan con una tasa parecida. |
| Preparacion de batch input | Simular datos futuros sin etiqueta, listos para scoring. | `batch_input.csv` conserva features e IDs, pero no incluye `is_fraud`. |
| Perfil de datos | Guardar estadisticas para trazabilidad y monitoreo. | `data_profile.json` registra medias, minimos, maximos y categorias principales. |
| Schema de features | Documentar que columnas son IDs, numericas, categoricas y target. | `feature_schema.json` separa `NUMERIC_FEATURES`, `CATEGORICAL_FEATURES` y `is_fraud`. |

### Variables Derivadas Que Se Agregan

Estas variables no nacen directamente en `generate_dataset`; se crean durante `data_preparation` y se usan en entrenamiento, evaluacion, batch inference y API.

| Variable derivada | Formula o regla | Ejemplo |
|---|---|---|
| `amount_log` | `log1p(amount)` | `amount=100` produce `4.615`. |
| `amount_to_avg_ratio` | `amount / avg_amount_30d` | `150 / 50 = 3.0`. |
| `is_night` | `1` si `hour <= 5` o `hour >= 23`; si no, `0`. | `hour=23` produce `1`; `hour=12` produce `0`. |
| `velocity_amount_score` | `log1p(transactions_last_24h) * amount_to_avg_ratio` | `transactions_last_24h=8` y ratio `3.0` produce `6.59`. |

### Por Que Estas Transformaciones Importan

Estas transformaciones convierten datos operativos en senales ML:

- `amount_log` ayuda a que montos extremos no dominen el entrenamiento.
- `amount_to_avg_ratio` compara la transaccion contra el patron del propio cliente.
- `is_night` captura horarios de mayor riesgo operativo.
- `velocity_amount_score` aproxima un patron de anomalia: muchas transacciones recientes y monto alto.
- El split estratificado hace que la evaluacion sea mas justa en un problema desbalanceado.

### Entradas

| Archivo | Descripcion |
|---|---|
| `data/raw/fraud_transactions.csv` | Dataset crudo con label. |
| `data/raw/batch_scoring_input.csv` | Dataset crudo para scoring futuro. |

Comando:

```bash
python -m src.data_preparation
```

Parametros opcionales:

```bash
python -m src.data_preparation --seed 42
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `data/processed/train.csv` | Datos preparados para entrenamiento. |
| `data/processed/test.csv` | Holdout para evaluacion. |
| `data/processed/batch_input.csv` | Datos preparados para batch inference. |
| `data/processed/data_profile.json` | Perfil de datos, distribuciones y tasas de fraude. |
| `data/processed/feature_schema.json` | Columnas ID, features numericas, categoricas y target. |

### Que Significa `top_values` En `data_profile.json`

`top_values` muestra los valores mas frecuentes de cada variable categorica dentro del dataset de entrenamiento.

Se calcula contando valores con `value_counts()` y tomando los primeros 10. Por ejemplo:

```json
"merchant_category": {
  "unique": 8,
  "top_values": {
    "grocery": 860,
    "restaurants": 525,
    "digital_goods": 490
  }
}
```

Esto significa que, en `train.csv`, `grocery` aparecio 860 veces, `restaurants` 525 veces y `digital_goods` 490 veces. Sirve para entender distribuciones categoricas antes de entrenar y como referencia para monitorear cambios futuros.

### Como Influye En El Proceso ML

Este paso controla la calidad de las senales que aprendera el modelo. Antes de entrenar hay que convertir datos crudos en datasets confiables, representativos y listos para aprendizaje. Aqui se materializa esa idea: sin validacion, feature engineering y split correcto, el entrenamiento podria aprender ruido, perder trazabilidad o evaluar con datos contaminados.

### Equivalente AWS

Equivale a AWS Glue o SageMaker Processing:

- Glue: catalogo, ETL, joins, limpieza y preparacion.
- SageMaker Processing: jobs reproducibles para transformar datos antes de entrenar.

## 3. `python -m src.train`

### Que Hace

Entrena un modelo local de regresion logistica ponderada implementada con NumPy. El entrenamiento pondera clases para manejar desbalance, ya que en fraude los casos positivos suelen ser pocos.

Acciones principales:

- Carga `data/processed/train.csv`.
- Ajusta un preprocessor local:
  - estadisticas para features numericas;
  - one-hot encoding para features categoricas.
- Entrena pesos y bias del modelo.
- Calcula probabilidades sobre train.
- Selecciona un threshold buscando favorecer recall/F1.
- Guarda el modelo, preprocessor, threshold y metadatos.

### Donde Se Asigna El Threshold Del Modelo

El threshold, por ejemplo `0.47`, se calcula automaticamente durante `python -m src.train`. No esta escrito como constante fija.

El entrenamiento llama a `choose_threshold(...)`, que prueba candidatos entre `0.10` y `0.90`. La seleccion busca buen `F1` y, cuando es posible, respeta un piso de recall. Esto tiene sentido en fraude porque perder fraudes reales suele ser mas costoso que revisar algunos casos legitimos.

El threshold elegido se guarda en:

- `artifacts/model/model.joblib`
- `artifacts/model/model_metadata.json`
- `artifacts/metrics/training_metrics.json`

Luego `evaluate`, `batch_inference` y la API usan ese threshold guardado junto al modelo.

### Entradas

| Archivo | Descripcion |
|---|---|
| `data/processed/train.csv` | Dataset preparado con label. |

Comando:

```bash
python -m src.train
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `artifacts/model/model.joblib` | Bundle serializado con modelo, preprocessor y threshold. |
| `artifacts/model/model_metadata.json` | Tipo de modelo, version, features y filas de entrenamiento. |
| `artifacts/metrics/training_metrics.json` | Metricas en train y threshold seleccionado. |

### Como Influye En El Proceso ML

Este paso convierte datos preparados en una funcion predictiva. Corresponde a entrenar y generar un modelo candidato. Tambien introduce una decision importante: el umbral. En fraude, no basta con producir probabilidad; hay que decidir desde que valor revisar o bloquear. Ese threshold afecta precision, recall, falsos positivos y falsos negativos.

### Equivalente AWS

Equivale a SageMaker Training Jobs:

- Entrenamiento reproducible.
- Artefacto de modelo.
- Metadatos de entrenamiento.
- Preparacion para registro/aprobacion.

En AWS, el artefacto podria almacenarse en S3 y registrarse en SageMaker Model Registry.

## 4. `python -m src.evaluate`

### Que Hace

Evalua el modelo usando el conjunto holdout `data/processed/test.csv`, que no fue usado durante entrenamiento.

Calcula:

- Accuracy.
- Precision.
- Recall.
- Specificity.
- F1-score.
- ROC AUC.
- PR AUC.
- Matriz de confusion.

Tambien genera un reporte Markdown de evaluacion.

### Entradas

| Archivo | Descripcion |
|---|---|
| `data/processed/test.csv` | Holdout con label. |
| `artifacts/model/model.joblib` | Modelo entrenado. |

Comando:

```bash
python -m src.evaluate
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `artifacts/metrics/evaluation_metrics.json` | Metricas estructuradas. |
| `artifacts/metrics/evaluation_report.md` | Reporte legible de evaluacion. |

### Como Influye En El Proceso ML

Este paso responde si el modelo generaliza. Entrenar no es solo ajustar parametros: hay que validar sesgo/varianza, underfitting, overfitting y desempeno con datos no vistos. Para fraude, PR AUC, recall, precision y F1 son mas informativas que accuracy porque las clases estan desbalanceadas.

### Equivalente AWS

Equivale a un Evaluation Step en SageMaker Pipelines o seguimiento con SageMaker Experiments. En un flujo productivo, estas metricas podrian decidir si el modelo se registra, se rechaza o requiere reentrenamiento.

## 5. `python -m src.batch_inference`

### Que Hace

Ejecuta inferencia por lotes sobre `data/processed/batch_input.csv`. Usa el modelo entrenado para calcular probabilidad de fraude por transaccion y asigna una decision.

Decisiones:

- `approve`: probabilidad menor al threshold de revision.
- `review`: probabilidad desde el threshold de revision hasta el umbral de bloqueo.
- `block`: probabilidad mayor o igual al umbral operativo alto.

El script preserva `transaction_id`, `customer_id` y `event_timestamp` para trazabilidad.

### Donde Se Definen `approve`, `review` Y `block`

La regla operativa usa dos limites:

- `review_threshold`: sale del modelo entrenado; en una ejecucion puede ser `0.47`.
- `block_threshold`: se define en `src/config.py` como `DECISION_BLOCK_THRESHOLD = 0.75`.

La logica queda asi:

| Condicion | Decision |
|---|---|
| `fraud_probability < review_threshold` | `approve` |
| `review_threshold <= fraud_probability < block_threshold` | `review` |
| `fraud_probability >= block_threshold` | `block` |

Ejemplo con `review_threshold=0.47` y `block_threshold=0.75`:

| Probabilidad | Decision |
|---:|---|
| `0.21` | `approve` |
| `0.58` | `review` |
| `0.82` | `block` |

### Entradas

| Archivo | Descripcion |
|---|---|
| `data/processed/batch_input.csv` | Datos preparados para scoring. |
| `artifacts/model/model.joblib` | Modelo entrenado. |

Comando:

```bash
python -m src.batch_inference
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `artifacts/predictions/batch_predictions.csv` | Predicciones por transaccion. |
| `artifacts/predictions/batch_summary.json` | Resumen de decisiones, umbrales y probabilidad promedio. |

### Como Influye En El Proceso ML

Este paso convierte el modelo en accion operativa diferida. En lugar de exponer un endpoint 24/7, procesa un lote completo. Esto es util cuando la prediccion puede ejecutarse por horarios, reportes o cargas masivas. Al comparar batch, real-time y async inference; batch optimiza costo cuando no se necesita respuesta inmediata.

### Equivalente AWS

Equivale a SageMaker Batch Transform. En AWS, el input estaria en S3, el job procesaria el lote y escribiria resultados nuevamente en S3.

## 6. `python -m src.monitor`

### Que Hace

Simula monitoreo local comparando una linea base de entrenamiento con datos actuales de scoring.

Senales monitoreadas:

- Drift numerico con PSI y cambio de media normalizado.
- Drift categorico con delta maximo de distribucion.
- Probabilidad promedio de fraude.
- Tasa de transacciones en `review` o `block`.
- Alertas operativas simples.

### Entradas

| Archivo | Descripcion |
|---|---|
| `data/processed/train.csv` | Baseline de entrenamiento. |
| `data/processed/batch_input.csv` | Datos actuales para comparar. |
| `artifacts/predictions/batch_predictions.csv` | Predicciones recientes. |

Comando:

```bash
python -m src.monitor
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `artifacts/metrics/monitoring_report.json` | Reporte estructurado de drift y alertas. |
| `artifacts/metrics/monitoring_report.md` | Reporte legible de monitoreo. |
| `artifacts/metrics/drift_charts/*.svg` | Graficos visuales de drift y alertas. |

### Que Es PSI

PSI significa `Population Stability Index`. Mide cuanto cambio la distribucion de una variable numerica entre:

- baseline: `data/processed/train.csv`;
- current: `data/processed/batch_input.csv`.

La idea es dividir la distribucion en buckets y comparar la proporcion de filas en cada bucket.

Interpretacion practica:

| PSI | Lectura |
|---:|---|
| Cerca de `0.00` | Distribuciones muy parecidas. |
| `>= 0.10` | Cambio a observar. |
| `>= 0.25` | Posible drift relevante. |

En este laboratorio, una variable numerica queda en `alert` si `psi >= 0.25`.

### Que Es `Mean shift std`

`Mean shift std` mide cuanto se movio la media actual respecto a la media baseline, expresado en desviaciones estandar del baseline.

Formula:

```text
abs(current_mean - baseline_mean) / baseline_std
```

Ejemplo:

```text
baseline_mean = 100
current_mean = 130
baseline_std = 20
mean_shift_std = abs(130 - 100) / 20 = 1.5
```

En este laboratorio, una variable numerica queda en `alert` si `mean_shift_std >= 1.5`.

### Que Significa `Operational Signals`

`Operational Signals` son senales agregadas de operacion del lote monitoreado. No son solo drift estadistico; ayudan a entender el comportamiento del modelo en uso.

Incluyen:

- filas del baseline;
- filas actuales;
- probabilidad promedio de fraude;
- tasa de transacciones en `review` o `block`;
- alertas activadas.

Estas senales ayudan a decidir si se debe investigar, ajustar thresholds, reentrenar o revisar datos.

### Que Es `Max distribution delta`

`Max distribution delta` aplica a variables categoricas. Mide la mayor diferencia de proporcion entre baseline y current para las categorias de una feature.

Ejemplo:

```text
baseline channel:
pos=0.46, mobile=0.26

current channel:
pos=0.35, mobile=0.38
```

Deltas:

```text
pos: abs(0.35 - 0.46) = 0.11
mobile: abs(0.38 - 0.26) = 0.12
```

Entonces:

```text
max_distribution_delta = 0.12
```

En este laboratorio, una variable categorica queda en `alert` si `max_distribution_delta >= 0.20`.

### Graficos Visuales De Drift

`python -m src.monitor` genera graficos SVG en:

```text
artifacts/metrics/drift_charts/
```

Los graficos generados son:

| Grafico | Archivo | Para que sirve |
|---|---|---|
| Histogramas baseline vs current | `numeric_<feature>.svg` | Ver cambios de distribucion en variables numericas. |
| Barras categoricas baseline vs current | `categorical_<feature>.svg` | Comparar proporciones de categorias. |
| Ranking PSI | `psi_by_feature.svg` | Identificar rapidamente las variables numericas con mayor drift. |
| Heatmap de alertas | `alert_heatmap.svg` | Ver intensidad relativa de PSI, mean shift, categorical delta y senales operativas. |

Los graficos son SVG generados con Python estandar; no requieren `matplotlib`.

### Como Se Calcula El Monitoring Summary

`Average fraud probability in batch scoring` es el promedio de `fraud_probability` en `artifacts/predictions/batch_predictions.csv`.

Formula:

```text
average_fraud_probability = mean(fraud_probability)
```

`Review/block rate` es la proporcion de predicciones cuya decision es `review` o `block`.

Formula:

```text
review_or_block_rate = count(decision in ["review", "block"]) / total_rows
```

Ejemplo con:

```json
"decision_counts": {
  "approve": 144,
  "review": 92,
  "block": 14
}
```

Entonces:

```text
review_or_block_rate = (92 + 14) / 250 = 0.424
```

Por eso aparece una alerta si supera el limite configurado:

```text
High review/block rate: 0.424
```

En el codigo actual, esa alerta se dispara si:

```text
review_or_block_rate >= 0.40
```

### Como Influye En El Proceso ML

Este paso representa el feedback loop del ciclo ML. ML no termina en el despliegue: hay que observar drift, degradacion, errores y senales operativas antes de que impacten al negocio. Si el monitoreo detecta cambios fuertes, una accion razonable puede ser investigar datos, ajustar umbrales, reentrenar o probar otra version.

### Equivalente AWS

Equivale a SageMaker Model Monitor + CloudWatch:

- Model Monitor para drift y calidad.
- CloudWatch para metricas y alarmas.
- EventBridge/SNS para notificaciones o acciones correctivas.

## 7. `python -m src.model_card`

### Que Hace

Genera documentacion de gobernanza del modelo. Consolida informacion de:

- Metadatos de entrenamiento.
- Perfil de datos.
- Metricas de evaluacion.
- Reporte de monitoreo.
- Limitaciones y uso previsto.
- Mapeo local a AWS.

### Entradas

| Archivo | Descripcion |
|---|---|
| `artifacts/model/model_metadata.json` | Version, tipo de modelo y features. |
| `artifacts/metrics/evaluation_metrics.json` | Metricas holdout. |
| `data/processed/data_profile.json` | Perfil del dataset. |
| `artifacts/metrics/monitoring_report.json` | Monitoreo y alertas. |

Comando:

```bash
python -m src.model_card
```

### Salidas

| Archivo | Descripcion |
|---|---|
| `artifacts/governance/model_card.md` | Model card legible. |
| `artifacts/governance/governance_summary.json` | Estado de aprobacion local y metadatos. |

### Como Influye En El Proceso ML

Este paso da trazabilidad y accountability. Un modelo productivo no solo debe predecir bien: debe ser seguro, trazable, explicable y aprobable. La model card documenta proposito, datos, metricas, limitaciones, riesgos y usos permitidos o no permitidos. Esto evita que el modelo quede como una "caja negra" sin contexto operativo.

### Equivalente AWS

Equivale a SageMaker Model Cards y documentacion asociada al Model Registry. En un proceso real, este artefacto apoyaria aprobaciones, auditoria, revision de riesgos y promocion controlada a produccion.

## Dependencias Entre Scripts

```text
generate_dataset
    -> data_preparation
        -> train
            -> evaluate
            -> batch_inference
                -> monitor
                    -> model_card
```

`evaluate` y `batch_inference` dependen del modelo entrenado, pero sirven a propositos diferentes: evaluacion mide calidad con labels; batch inference produce predicciones para registros sin label.

`model_card` debe ejecutarse al final porque resume resultados de entrenamiento, evaluacion y monitoreo.

## Como Leer Los Resultados

- Si `recall` es bajo, el modelo deja escapar demasiados fraudes.
- Si `precision` es baja, muchas transacciones legitimas van a revision o bloqueo.
- Si `PR AUC` mejora, el modelo separa mejor la clase positiva en un contexto desbalanceado.
- Si monitoreo reporta drift, las distribuciones actuales ya no se parecen a las de entrenamiento.
- Si sube mucho la tasa `review/block`, puede haber drift, threshold mal calibrado o cambios reales en el negocio.

## Relacion Con La Arquitectura ML

El flujo completo implementa localmente la arquitectura de referencia del material:

| Concepto del PDF | Implementacion local |
|---|---|
| Datos e ingesta | `src.generate_dataset`, `data/raw/` |
| Procesamiento y calidad | `src.data_preparation`, `data/processed/` |
| Entrenamiento y automatizacion | `src.train`, `artifacts/model/` |
| Evaluacion y seleccion | `src.evaluate`, `artifacts/metrics/` |
| Inferencia | `src.batch_inference` y FastAPI `/predict` |
| Monitoreo y accion | `src.monitor`, reportes y alertas |
| Gobernanza | `src.model_card`, `artifacts/governance/` |
