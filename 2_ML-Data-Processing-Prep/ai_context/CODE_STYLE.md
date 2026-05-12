# Estilo De Codigo

## Versiones

- Usar Python 3.11+ o 3.12.
- Mantener dependencias minimas.
- Evitar notebooks como dependencia obligatoria del laboratorio.

## Organizacion

Separar claramente:

- Generacion de datos.
- Upload a S3.
- Profiling.
- Calidad.
- Limpieza.
- Transformacion.
- Feature engineering.
- Dataset de entrenamiento.
- Dataset de inferencia.
- Lineage.
- Dataset card.
- Clientes AWS.
- Configuracion.

Scripts esperados:

- `src/config.py`
- `src/aws_clients.py`
- `src/generate_sample_data.py`
- `src/upload_raw_data.py`
- `src/data_profiling.py`
- `src/data_quality.py`
- `src/clean_data.py`
- `src/transform_data.py`
- `src/feature_engineering.py`
- `src/build_training_dataset.py`
- `src/build_inference_dataset.py`
- `src/lineage_report.py`
- `src/dataset_card.py`

## Configuracion

Centralizar configuracion en `src/config.py`.

Variables esperadas:

```text
AWS_PROFILE=mlops-2-data-prep-lab
AWS_REGION=
PROJECT_NAME=ml-data-processing-prep
ENVIRONMENT=lab
S3_BUCKET_NAME=
RESOURCE_PREFIX=ml-data-prep-lab
```

Reglas:

- No usar rutas absolutas.
- No hardcodear bucket, region ni profile en funciones internas.
- No hardcodear credenciales.
- Leer parametros desde variables de entorno, argumentos CLI o archivos de configuracion sin secretos.

## Rutas

Usar `pathlib.Path` para rutas locales.

Convenciones:

- Datos sinteticos versionables pequenos: `data/sample/`.
- Cache local: `data/local_cache/`.
- Artefactos descargados: `artifacts/local_outputs/`.
- Outputs reales del laboratorio: S3.

## AWS

Usar boto3 cuando aplique.

Buenas practicas:

- Centralizar sesiones y clientes en `src/aws_clients.py`.
- Soportar `AWS_PROFILE` y `AWS_REGION`.
- No depender de credenciales en codigo.
- Manejar errores comunes de AWS con mensajes claros.
- Loguear recursos y prefixes usados sin imprimir secretos.

## Python

Estilo esperado:

- Codigo modular.
- Funciones pequenas y reutilizables.
- Type hints cuando aplique.
- Manejo basico de errores.
- Logs simples o logging estructurado.
- Nombres descriptivos.
- Evitar dependencias innecesarias.
- Evitar side effects al importar modulos.
- Usar `if __name__ == "__main__":` en scripts ejecutables.

## Datos

Para datasets pequenos:

- Usar pandas.
- Preferir CSV o Parquet segun dependencia disponible.
- Validar esquemas minimos.
- Mantener campos y tipos consistentes entre entrenamiento e inferencia.

El pipeline debe preservar la separacion:

- `raw`: datos originales.
- `cleaned`: datos corregidos.
- `curated`: datos integrados.
- `features`: senales reutilizables.
- `inference`: datos listos para prediccion.

## Feature Engineering

La logica de features debe ser compartida por entrenamiento e inferencia. Evitar duplicar transformaciones en scripts separados si eso puede causar training-serving skew.

Recomendaciones:

- Crear funciones puras para transformaciones.
- Mantener contrato de columnas esperado.
- Agregar tests de esquema.
- Documentar features en dataset card.

## Tests

Usar pytest.

Tests minimos:

- Generacion de datos sinteticos produce columnas esperadas.
- Validaciones de calidad detectan nulos, duplicados o rangos invalidos.
- Transformaciones producen esquema esperado.
- Feature engineering se reutiliza para entrenamiento e inferencia.
- Dataset card y lineage pueden generarse con datos de prueba.

## Compatibilidad

Mantener compatibilidad Windows/Linux cuando sea razonable:

- Scripts `.sh` para Bash.
- Scripts `.ps1` para PowerShell.
- Makefile como conveniencia, no como unica opcion en Windows.
- Evitar comandos exclusivos de un sistema sin alternativa documentada.

## Versionado

No versionar:

- Datasets grandes generados.
- Caches locales.
- Artefactos descargados.
- `.env` con valores reales.
- Logs grandes.

Versionar:

- `.env.example`.
- Scripts.
- Infraestructura.
- Tests.
- Documentacion.
- Datos sinteticos pequenos si son utiles para pruebas.
