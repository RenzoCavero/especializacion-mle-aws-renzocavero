# 07 - Consistencia Entrenamiento/Inferencia

Training-serving skew ocurre cuando el modelo entrena con una definicion de features y luego recibe otra diferente en inferencia.

Este laboratorio evita ese problema con una unica logica compartida:

```text
src/feature_engineering.py
```

Tanto entrenamiento como inferencia pasan por `build_feature_frame`. Los tests locales validan que el contrato de columnas se mantenga.

Comandos:

```bash
bash scripts/lab.sh step 07
make training-dataset
make inference-dataset
make test
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 step 07
.\scripts\run_processing_job.ps1 -Steps training-dataset,inference-dataset
```

## Contrato De Features

El contrato principal es:

- Entrenamiento puede incluir `is_fraud` porque es el target historico.
- Inferencia no debe incluir `is_fraud`.
- Las columnas predictoras deben mantener el mismo significado, nombre y tipo esperado.
- La logica de transformacion debe vivir en funciones compartidas, no duplicadas por separado para training e inference.

En el codigo, la reutilizacion ocurre en:

```text
src/feature_engineering.py
```

Funciones clave:

```text
build_training_features
build_inference_features
assert_feature_contract
```

## Como Validarlo

Ejecuta:

```bash
pytest -q
```

o:

```bash
make test
```

Luego ejecuta el pipeline cloud:

```bash
bash scripts/run_processing_job.sh all
python -m src.validate_outputs
```

Si el contrato se rompe, el pipeline debe fallar antes de publicar datasets finales inconsistentes.

## Rutas De Ejecucion

| Nivel | Ruta |
|---|---|
| Runner numerado | `scripts/lab.sh step 07` o `scripts/lab.ps1 step 07` |
| Script directo | `scripts/run_processing_job.sh training-dataset,inference-dataset` |
| Modulo que envia el Glue Job | `src.run_processing_job` |
| Logica compartida | `src.feature_engineering.build_feature_frame` |
| Validacion de contrato | `src.feature_engineering.assert_feature_contract` |
| Dataset entrenamiento | `src.build_training_dataset.build_training_dataset` |
| Dataset inferencia | `src.build_inference_dataset.build_inference_dataset` |

## Validacion En AWS Console

1. Abre Amazon S3.
2. Entra al bucket del laboratorio.
3. Revisa `features/training_dataset.csv`.
4. Revisa `inference/inference_dataset.csv`.
5. Confirma que ambos archivos existen y tienen tamano mayor a cero.
6. Si actualizaste el catalogo, abre AWS Glue > Data Catalog > Tables y revisa `features_training` y `features_inference`.
7. En Athena puedes comparar columnas entre ambas tablas. Las columnas predictoras deben coincidir; `features_training` incluye ademas `is_fraud` y `split`.

## Por Que Importa

Training-serving skew puede producir modelos que se ven buenos en entrenamiento, pero fallan en produccion porque reciben columnas distintas o calculadas de otra forma.

Este laboratorio prepara la base para futuros temas:

- Entrenamiento en SageMaker.
- Batch inference.
- Real-time inference.
- MLOps con pipelines.
- Monitoreo de drift.
