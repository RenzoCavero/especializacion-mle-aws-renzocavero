# AWS Architecture Notes

Estas notas explican como migrar conceptualmente el laboratorio local hacia AWS. No son pasos obligatorios y no crean recursos.

## Arquitectura Conceptual

1. Amazon S3 almacena datos crudos, procesados y artefactos.
2. AWS Glue o SageMaker Processing prepara datasets y features.
3. SageMaker Training Jobs entrena el modelo con datos desde S3.
4. SageMaker Experiments registra parametros, metricas y artefactos.
5. SageMaker Model Registry versiona y aprueba modelos.
6. SageMaker Batch Transform ejecuta scoring por lotes.
7. SageMaker Real-Time Endpoint sirve predicciones online.
8. CloudWatch y SageMaker Model Monitor observan drift, latencia, errores y calidad.
9. EventBridge/SNS activan alertas y acciones correctivas.
10. SageMaker Model Cards documenta uso, metricas, riesgos y aprobacion.

## Seguridad

- Usar IAM de minimo privilegio.
- Cifrar datos en S3 con KMS.
- Usar TLS para trafico en transito.
- Mantener endpoints en VPC cuando aplique.
- Auditar acciones con CloudTrail.
- No poner secrets en codigo ni repositorio.

## Costos

- El laboratorio base evita costos porque corre localmente.
- En AWS real, preferir Batch Transform para cargas diferidas.
- Usar endpoints real-time solo cuando la latencia del negocio lo justifique.
- Apagar o escalar a cero recursos no usados.

## Extension Recomendada

Migrar por fases:

1. Subir artefactos a S3 de forma controlada.
2. Ejecutar preparacion como SageMaker Processing.
3. Ejecutar entrenamiento como SageMaker Training Job.
4. Registrar modelo y metricas.
5. Separar batch y real-time inference.
6. Agregar monitoreo y alarmas.

