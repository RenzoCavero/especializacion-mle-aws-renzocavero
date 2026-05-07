# Checklist De Code Review

Usar este checklist antes de cerrar cualquier tarea del laboratorio.

## Alcance

- Se crearon archivos fuera de `2_ML-Data-Processing-Prep/`?
- Se modificaron archivos fuera de `2_ML-Data-Processing-Prep/`?
- Se movieron o renombraron archivos dentro de `doc/`?
- La estructura mantiene separacion entre codigo, infraestructura, datos, artefactos, documentacion y pruebas?

## AWS Y Cloud-First

- El laboratorio realmente se ejecuta en AWS?
- La infraestructura es reproducible?
- Existe comando de deploy?
- Existe comando de cleanup?
- Se usa Amazon S3 como data lake?
- Se usa AWS Glue Data Catalog o queda claramente implementado?
- Se usa Glue Job o SageMaker Processing Job para procesamiento cloud?
- Se guardan logs operativos en CloudWatch?
- La solucion evita recursos persistentes innecesarios?

## Costos

- Se documentan costos?
- Se usan datasets pequenos?
- Se evitan endpoints persistentes?
- Feature Store online esta deshabilitado salvo solicitud explicita?
- CloudWatch Logs tiene retencion razonable?
- Existe una forma clara de destruir los recursos creados?
- Se documenta como revisar recursos activos?

## Seguridad

- Se documentan permisos IAM?
- No hay credenciales reales?
- No hay access keys, secret keys ni tokens?
- Los buckets S3 no son publicos?
- Se bloquea acceso publico en S3?
- Se usa minimo privilegio?
- Se cifran datos en S3?
- Se evita usar PII real?
- Se usan datos sinteticos?

## Pipeline De Datos

- Se generan datos sinteticos?
- Se suben datos a S3 `raw/`?
- Se generan datos en `cleaned/`, `curated/`, `features/` e `inference/`?
- Se genera profiling?
- Se genera reporte de calidad?
- Se genera lineage?
- Se genera dataset card?
- Se puede descargar una copia local de reportes?
- Los outputs quedan en S3 y no solo localmente?

## Features Y Consistencia

- La logica de features se reutiliza para entrenamiento e inferencia?
- Se evita training-serving skew?
- Hay contrato de esquema para features?
- Se documentan features generadas?
- Se separa columna objetivo de dataset de inferencia?

## Documentacion

- Se documenta la relacion con AWS?
- Se explica Glue, SageMaker Processing, Data Wrangler, Feature Store, S3, IAM, KMS, CloudWatch y lineage?
- La documentacion es clara para estudiantes?
- Los comandos funcionan desde la raiz de `2_ML-Data-Processing-Prep/`?
- Hay alternativas Windows y Linux cuando corresponde?

## Tests Y Validacion

- Hay tests basicos?
- Los tests cubren generacion de datos, calidad, transformaciones y features?
- Se probo el flujo local auxiliar si existe?
- Se probo deploy o al menos validacion sintactica de IaC?
- Se documento cualquier prueba no ejecutada?

## Extension Futura

- La solucion es extensible a futuros laboratorios?
- Los datasets pueden alimentar entrenamiento?
- La capa `inference/` puede alimentar batch inference?
- La logica de features puede evolucionar a real-time inference?
- Los reportes pueden servir como baseline de monitoreo?
- Lineage y dataset card preparan gobernanza y MLOps?

## Cierre

Antes de responder al usuario, confirmar:

- Archivos modificados.
- Recursos AWS involucrados.
- Comandos de deploy, ejecucion, validacion y cleanup.
- Validaciones ejecutadas.
- Riesgos o pendientes.
