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
bash scripts/lab.sh step 08
make lineage
make dataset-card
make download-reports
```

En Windows PowerShell:

```powershell
.\scripts\lab.ps1 step 08
.\scripts\download_reports.ps1
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

## Rutas De Ejecucion

| Nivel | Ruta |
|---|---|
| Runner numerado | `scripts/lab.sh step 08` o `scripts/lab.ps1 step 08` |
| Script directo | `scripts/run_processing_job.sh lineage,dataset-card` |
| Descarga local | `scripts/download_reports.sh` o `scripts/download_reports.ps1` |
| Modulo que envia el Glue Job | `src.run_processing_job` |
| Logica lineage | `src.lineage_report` |
| Logica dataset card | `src.dataset_card` |
| Descarga de reportes | `src.download_reports` |

## Validacion En AWS Console

1. Abre Amazon S3.
2. Entra al bucket del laboratorio.
3. Revisa `lineage/lineage.json` y `lineage/lineage.md`.
4. Revisa `reports/dataset_card.json` y `reports/dataset_card.md`.
5. Abre AWS Glue > ETL jobs > `ml-data-prep-lab-processing-job`.
6. Confirma que el run que genero estos reportes esta en `Succeeded`.
7. Abre CloudWatch Logs si necesitas verificar mensajes `Wrote lineage reports` y `Wrote dataset card`.
