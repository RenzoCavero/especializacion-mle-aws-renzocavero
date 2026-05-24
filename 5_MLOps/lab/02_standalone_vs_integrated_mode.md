# 02 - standalone_mode vs integrated_mode

## Objetivo

Seleccionar el modo de ejecucion y preparar los datos de entrada del laboratorio.

## Que vas a construir o validar

Vas a generar un dataset sintetico de churn para `standalone_mode` y subirlo a S3. En `integrated_mode`, se valida que el laboratorio puede convivir con recursos existentes sin eliminarlos por defecto.

## Input del paso

- `LAB_MODE=standalone` o `LAB_MODE=integrated`.
- `S3_BUCKET_NAME`.
- Permisos S3 de lectura/escritura en el prefijo del laboratorio.
- Para `integrated_mode`, variables opcionales como `MODEL_PACKAGE_ARN`, `ENDPOINT_NAME` o `DATA_CAPTURE_S3_URI`.

## Output esperado del paso

- `data/local_cache/churn_train.csv`.
- `data/local_cache/baseline.csv`.
- `data/local_cache/inference_normal.jsonl`.
- `data/local_cache/inference_drift.jsonl`.
- Objetos en S3 bajo `s3://<bucket>/mlops-lab/lab/data/raw/`.
- Metadata local `artifacts/local_outputs/data_generation.json`.

## Conceptos claves

`standalone_mode` es la ruta autocontenida. Produce datos sinteticos, entrena un modelo simple y crea todos los recursos necesarios para demostrar MLOps sin depender de laboratorios previos. Esto evita que el exito del laboratorio dependa de un endpoint o artefacto externo.

`integrated_mode` representa una ruta mas cercana a produccion: reutilizar un modelo ya registrado, un endpoint existente o un feature contract previo. La diferencia clave es la propiedad del recurso. Si el recurso fue creado fuera del laboratorio, el cleanup no debe eliminarlo por defecto.

El dataset sintetico no busca maximizar performance predictiva. Su funcion es habilitar un flujo MLOps completo con variables numericas, categoricas, label, registros normales y registros con drift. Esta separacion permite entrenar, crear baseline y luego simular cambios de distribucion.

Los archivos de inferencia no incluyen label operativo. En produccion, el endpoint recibe features y devuelve predicciones. El label se usa en entrenamiento o en evaluaciones posteriores con ground truth.

Mantener IDs (`record_id`) permite trazabilidad. En MLOps, no basta con saber que hubo drift; tambien se necesita rastrear que registros, rango temporal o lote causaron la senal.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---|---|---|---|---|---|---|
| 1 | `src.generate_sample_data --upload` | `.env`, parametros default de datos sinteticos | S3 bucket configurado | `data/local_cache/*.csv`, `data/local_cache/*.jsonl`, `artifacts/local_outputs/data_generation.json` | `s3://<bucket>/mlops-lab/lab/data/raw/*` | Generar datasets de entrenamiento, baseline, trafico normal y trafico con drift. |

## Paths principales

| Tipo | Path | Contenido |
|---|---|---|
| Local output | `data/local_cache/churn_train.csv` | Dataset con features y label para entrenamiento. |
| Local output | `data/local_cache/baseline.csv` | Dataset de referencia para baseline de Data Quality. |
| Local output | `data/local_cache/inference_normal.jsonl` | Registros sin label para trafico normal del endpoint. |
| Local output | `data/local_cache/inference_drift.jsonl` | Registros sin label con cambios de distribucion. |
| Local output | `data/local_cache/inference_normal_ground_truth.jsonl` | Labels sinteticos usados luego por Model Quality. |
| Local metadata | `artifacts/local_outputs/data_generation.json` | Conteos, rutas locales y URIs S3 generadas. |
| S3 output | `s3://<bucket>/mlops-lab/lab/data/raw/` | Copia cloud de los datasets del laboratorio. |

## Prerrequisitos

- Paso 01 completado.
- Bucket S3 accesible.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 02
```

Comando equivalente:

```bash
make step-02
```

## Resultado esperado

Datos locales generados y subidos a S3. El comando imprime rutas locales y URIs S3.

## Validacion local

```bash
python -m src.generate_sample_data
```

Revisar:

```bash
dir data\local_cache
```

## Validacion en consola AWS

En S3, revisar el prefijo:

```text
s3://<bucket>/mlops-lab/lab/data/raw/
```

Debe contener archivos CSV y JSONL generados por el paso.

## Nota de seguridad

Los datos son sinteticos. No uses datos reales sensibles para esta demo.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.generate_sample_data --upload` | Generar dataset sintetico de churn y trafico normal/drift. | `_make_frame`, `generate`, `write_jsonl`, `upload_generated_data`. | `.env`, defaults de `LabConfig`. | `data/local_cache/*`, `artifacts/local_outputs/data_generation.json`, objetos en `s3://.../data/raw/`. |

Archivos locales esperados:

- `data/local_cache/baseline.csv`
- `data/local_cache/inference_normal.jsonl`
- `data/local_cache/inference_drift.jsonl`
- `data/local_cache/inference_normal_ground_truth.jsonl`
- `data/local_cache/inference_drift_ground_truth.jsonl`

Parametros modificables:

- `CREATE_STANDALONE_DATASET=false`: omite generacion standalone si trabajas en modo integrado.
- `LAB_MODE=integrated`: permite reutilizar recursos externos, pero exige configurar referencias como `MODEL_PACKAGE_ARN` o `FEATURE_CONTRACT_S3_URI` en pasos posteriores.
- `RESOURCE_PREFIX` y `ENVIRONMENT`: cambian el prefijo S3 donde se suben los datos.

Troubleshooting:

- Si el paso 05 no encuentra datos en S3, vuelve a ejecutar `python -m src.generate_sample_data --upload`.
- Si `data/local_cache/` tiene archivos antiguos, usa `python -m src.lab_runner cleanup-local` al finalizar una corrida anterior y genera datos nuevamente.
- Si S3 devuelve `AccessDenied`, revisa el bucket, region y permisos `s3:PutObject`.
