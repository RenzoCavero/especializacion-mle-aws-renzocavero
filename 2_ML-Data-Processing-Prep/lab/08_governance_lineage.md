# 08 - Gobernanza Y Lineage

El laboratorio genera trazabilidad desde fuentes crudas hasta datasets finales.

Outputs:

```text
s3://<bucket>/lineage/lineage.json
s3://<bucket>/lineage/lineage.md
s3://<bucket>/reports/dataset_card.json
s3://<bucket>/reports/dataset_card.md
```

La dataset card documenta:

- Uso previsto.
- Fuentes.
- Outputs.
- Features.
- Target.
- Limitaciones.
- Seguridad.
- Calidad.

Comandos:

```bash
make lineage
make dataset-card
make download-reports
```

## Que Documenta El Lineage

El lineage conecta:

- Archivos raw de entrada.
- Procesos de limpieza y transformacion.
- Construccion de features.
- Datasets finales de entrenamiento e inferencia.
- Reportes de calidad y profiling.

Esto ayuda a responder preguntas operativas:

- De donde salio este dataset.
- Que transformaciones se aplicaron.
- Que outputs dependen de cada fuente.
- Que capa debe revisarse si una regla de calidad falla.

## Que Documenta La Dataset Card

La dataset card resume el dataset para usuarios tecnicos y no tecnicos:

- Caso de uso.
- Fuentes usadas.
- Target.
- Features principales.
- Tamanos de entrenamiento e inferencia.
- Calidad observada.
- Limitaciones conocidas.
- Consideraciones de seguridad y PII.
- Recomendaciones para futuros laboratorios.

## Ejecutar Y Descargar

Para generar lineage y dataset card dentro de AWS Glue:

```bash
bash scripts/run_processing_job.sh lineage,dataset-card
```

Para descargar los reportes:

```bash
bash scripts/download_reports.sh
```

Revisa localmente:

```text
artifacts/local_outputs/lineage/lineage.md
artifacts/local_outputs/reports/dataset_card.md
```

En AWS, los mismos archivos quedan en:

```text
s3://<bucket>/lineage/
s3://<bucket>/reports/
```
