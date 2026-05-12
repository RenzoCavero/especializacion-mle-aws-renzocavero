# Costos Y Seguridad

## Reglas De Costos

El laboratorio debe ser de bajo costo y facil de destruir.

Reglas obligatorias:

- Usar datasets pequenos.
- Usar recursos minimos para laboratorio.
- Evitar jobs largos.
- Evitar endpoints persistentes.
- Evitar recursos 24/7.
- Evitar SageMaker Feature Store online salvo que se indique explicitamente.
- Preferir jobs efimeros.
- Incluir cleanup.
- Documentar como verificar recursos activos.
- Documentar como revisar costos aproximados.

## Diseno Para Bajo Costo

Preferencias:

- Procesamiento batch bajo demanda.
- Archivos pequenos en S3.
- Retencion corta de logs.
- Sin endpoints de inferencia en este tema.
- Sin notebooks obligatorios permanentes.
- Sin clusters persistentes.
- Feature Store deshabilitado por defecto.
- KMS opcional.

## Recursos A Vigilar

Recursos que pueden generar costos:

- Buckets S3 con datos y artefactos.
- Glue Jobs.
- Glue Crawlers.
- Glue Data Quality evaluations.
- Glue Data Catalog Column Statistics tasks.
- Athena queries por datos escaneados.
- SageMaker Processing Jobs.
- SageMaker Feature Store.
- CloudWatch Logs.
- KMS customer managed keys.

## Verificacion De Recursos Activos

Comandos orientativos:

```bash
aws cloudformation describe-stacks --stack-name ml-data-prep-lab-stack --profile <profile> --region <region>
aws s3 ls s3://<bucket-name>/ --recursive --profile <profile> --region <region>
aws glue get-databases --profile <profile> --region <region>
aws glue list-crawlers --profile <profile> --region <region>
aws glue list-data-quality-rulesets --profile <profile> --region <region>
aws logs describe-log-groups --log-group-name-prefix /aws/ml-data-prep-lab --profile <profile> --region <region>
```

Si se usa SageMaker:

```bash
aws sagemaker list-processing-jobs --name-contains ml-data-prep-lab --profile <profile> --region <region>
aws sagemaker list-feature-groups --name-contains ml-data-prep-lab --profile <profile> --region <region>
```

## Revision De Costos Aproximados

Recomendaciones:

- Revisar AWS Billing and Cost Management.
- Filtrar por tags `Project=MLDataProcessingPrep` y `CostCenter=Training` si estan disponibles.
- Revisar servicios S3, Glue, SageMaker, CloudWatch y KMS.
- En Athena, configurar `s3://<bucket>/athena-results/` y evitar consultas `SELECT *` innecesarias sobre datasets grandes.
- Ejecutar Glue Crawler, Glue Data Quality y Column Statistics solo cuando se necesite el demo.
- Destruir recursos al finalizar cada sesion de laboratorio.

## Reglas De Seguridad

Reglas obligatorias:

- No usar credenciales hardcodeadas.
- Usar AWS profiles o roles IAM.
- Aplicar minimo privilegio.
- Cifrar datos en S3.
- No usar datos reales sensibles.
- No subir PII real.
- Usar datos sinteticos.
- No exponer buckets publicamente.
- Bloquear acceso publico en S3.
- Documentar permisos requeridos.
- Documentar riesgos.

## Credenciales

Prohibido incluir:

- `AWS_ACCESS_KEY_ID` real.
- `AWS_SECRET_ACCESS_KEY` real.
- `AWS_SESSION_TOKEN` real.
- Tokens personales.
- Credenciales en notebooks, scripts, README, logs o archivos `.env`.

Permitido:

- `.env.example` con variables vacias.
- Uso de `AWS_PROFILE`.
- Uso de roles IAM.
- Uso de credenciales ya configuradas en AWS CLI fuera del repositorio.

## S3 Seguro

Configuracion esperada:

- Public Access Block habilitado.
- Bucket policy sin acceso publico.
- Cifrado por defecto.
- Prefixes separados por capa.
- Escritura limitada a roles del laboratorio.

## IAM Minimo Privilegio

Los permisos deben estar acotados a:

- Recursos del laboratorio.
- Prefixes del bucket del laboratorio.
- Glue database/tablas del laboratorio.
- Log groups del laboratorio.
- KMS key del laboratorio si aplica.

Evitar wildcards globales en recursos cuando existan ARNs especificos.

## Datos

El laboratorio debe usar datos sinteticos. Si se usa un dataset publico, documentar licencia, origen y sanitizacion. No usar PII real ni datos regulados.

## Riesgos A Documentar

- Costos por no ejecutar cleanup.
- Buckets no vaciados por datos remanentes.
- Permisos IAM demasiado amplios.
- Region incorrecta.
- Profile AWS equivocado.
- Feature Store online habilitado accidentalmente.
- Logs con informacion sensible.
- Diferencias entre features de entrenamiento e inferencia.
