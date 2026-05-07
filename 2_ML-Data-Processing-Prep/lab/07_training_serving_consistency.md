# 07 - Consistencia Entrenamiento/Inferencia

Training-serving skew ocurre cuando el modelo entrena con una definicion de features y luego recibe otra diferente en inferencia.

Este laboratorio evita ese problema con una unica logica compartida:

```text
src/feature_engineering.py
```

Tanto entrenamiento como inferencia pasan por `build_feature_frame`. Los tests locales validan que el contrato de columnas se mantenga.

Comandos:

```bash
make training-dataset
make inference-dataset
make test
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

## Por Que Importa

Training-serving skew puede producir modelos que se ven buenos en entrenamiento, pero fallan en produccion porque reciben columnas distintas o calculadas de otra forma.

Este laboratorio prepara la base para futuros temas:

- Entrenamiento en SageMaker.
- Batch inference.
- Real-time inference.
- MLOps con pipelines.
- Monitoreo de drift.
