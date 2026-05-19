# 00 - Contexto De Negocio

El caso practico es deteccion de fraude o scoring de riesgo transaccional.

El negocio necesita transformar eventos crudos de clientes y transacciones en senales confiables para entrenar un modelo y luego ejecutar inferencia batch. El laboratorio usa datos sinteticos para evitar PII real.

## Objetivo

Entender el problema de negocio antes de crear recursos AWS. En este laboratorio prepararas datos para que un modelo pueda aprender patrones de riesgo a partir de transacciones historicas y luego aplicar el mismo contrato de features a transacciones nuevas.

## Fuentes del laboratorio

- `customers.csv`: datos sinteticos de clientes.
- `transactions.csv`: transacciones historicas con etiqueta `is_fraud`.
- `inference_transactions.csv`: transacciones recientes sin etiqueta.

## Resultado esperado

- Dataset supervisado en `features/training_dataset.csv`.
- Dataset de inferencia en `inference/inference_dataset.csv`.
- Reportes de calidad, profiling, lineage y dataset card.

## Por Que Este Caso Sirve Para ML En AWS

Fraude y riesgo son casos utiles para practicar preparacion de datos porque combinan:

- Datos de clientes relativamente estables.
- Eventos transaccionales con alto volumen.
- Variables categoricas como canal, segmento, pais y comercio.
- Variables numericas como monto, edad, antiguedad y score inicial.
- Un target historico (`is_fraud`) que existe para entrenamiento, pero no para inferencia real.

El flujo reproduce una situacion comun en proyectos ML: los datos llegan crudos, incompletos o inconsistentes, y deben convertirse en datasets confiables antes de entrenar o puntuar un modelo.

## Como Se Generan Los Datos

El comando:

```bash
python -m src.generate_sample_data
```

crea tres archivos locales en:

```text
data/sample/
```

El generador tambien introduce algunos problemas controlados:

- Nulos en atributos de cliente o transaccion.
- Una transaccion con monto negativo.
- Una transaccion duplicada.
- Una transaccion que referencia un cliente inexistente.
- Un dataset de inferencia sin columna `is_fraud`.

Estos problemas permiten practicar profiling, reglas de calidad, limpieza y separacion correcta entre entrenamiento e inferencia.

## Relacion Con Los Scripts

Desde la raiz del proyecto puedes revisar este paso con:

```bash
bash scripts/lab.sh step 00
```

Para generar y subir estos datos al data lake:

```bash
bash scripts/upload_sample_data.sh
```

Ese script ejecuta:

```bash
python -m src.generate_sample_data
python -m src.upload_raw_data
```

El registro en Glue Catalog se hace despues, con:

```bash
python -m src.register_catalog
```

La explicacion detallada vive en `scripts/README.md`.

## Validacion esperada

Este paso no crea recursos AWS. Antes de continuar confirma que entiendes:

1. `transactions.csv` tiene el target historico `is_fraud`.
2. `inference_transactions.csv` no tiene target.
3. El pipeline debe producir columnas compatibles para entrenamiento e inferencia.
4. La capa `features/` sera el contrato que conectara este laboratorio con los laboratorios de entrenamiento.
