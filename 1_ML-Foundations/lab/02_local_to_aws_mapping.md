# Local To AWS Mapping

Este laboratorio no crea recursos AWS. Cada componente local representa un patron arquitectonico equivalente.

| Paso local | Archivo o carpeta | Equivalente AWS conceptual |
|---|---|---|
| Datos crudos | `data/raw/` | Amazon S3 raw zone |
| Datos procesados | `data/processed/` | Amazon S3 processed/curated zone |
| Preparacion | `src/data_preparation.py` | AWS Glue / SageMaker Processing |
| Entrenamiento | `src/train.py` | SageMaker Training Jobs |
| Evaluacion | `src/evaluate.py` | SageMaker Experiments / Evaluation Step |
| Artefacto modelo | `artifacts/model/model.joblib` | SageMaker model artifact |
| Batch inference | `src/batch_inference.py` | SageMaker Batch Transform |
| Real-time inference | `src/api/main.py` | SageMaker Real-Time Endpoint |
| Monitoreo | `src/monitor.py` | SageMaker Model Monitor + CloudWatch |
| Model card | `artifacts/governance/model_card.md` | SageMaker Model Cards |

## Principio Local-First

El flujo debe ser entendible y ejecutable sin nube. Una vez validada la separacion de responsabilidades, cada paso puede migrarse gradualmente a servicios gestionados.
