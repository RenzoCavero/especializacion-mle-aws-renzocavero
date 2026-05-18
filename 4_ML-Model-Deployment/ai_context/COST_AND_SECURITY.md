# Cost and Security Guide

## Reglas de costo

- Los endpoints real-time son persistentes y generan costo mientras estan activos.
- Usar instancias pequenas para laboratorio.
- Configurar `min_capacity` bajo.
- Limitar autoscaling con `max_capacity` razonable.
- Ejecutar cleanup al terminar.
- Batch Transform es efimero, pero genera costo durante ejecucion.
- Feature Store Online Store y Offline Store generan costos por almacenamiento, lecturas y escrituras.
- Evitar cargas grandes.
- Evitar multiples endpoints.
- No activar async/serverless opcional salvo que se pida.
- Documentar como verificar endpoints activos.
- Documentar como revisar recursos en SageMaker y CloudWatch.

## Recomendaciones de costo para el laboratorio

- Usar `ml.m5.large` solo si esta disponible y permitido por la cuenta.
- Permitir cambiar `INSTANCE_TYPE` y `BATCH_INSTANCE_TYPE`.
- Mantener `BATCH_INSTANCE_COUNT=1` por defecto.
- Evitar datasets grandes en `standalone_mode`.
- Crear un solo endpoint por ejecucion.
- Mostrar el nombre del endpoint activo al finalizar cualquier comando de creacion.
- Ejecutar `make destroy-endpoint` o `make destroy-all` al terminar.
- Ejecutar `make cleanup-feature-store` si el Feature Group fue creado por el laboratorio y ya no se necesita.

## Como verificar endpoints activos

La implementacion futura debe documentar comandos AWS CLI equivalentes a:

```bash
aws sagemaker list-endpoints --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws sagemaker describe-endpoint --endpoint-name "$ENDPOINT_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

## Como revisar recursos y costos indirectos

- Consola de SageMaker: endpoints, endpoint configs, models y transform jobs.
- Consola de S3: prefijos de input, output, artifacts y data capture.
- CloudWatch: logs, metricas y alarmas.
- AWS Cost Explorer o Billing para revisar gasto acumulado.

## Reglas de seguridad

- No hardcodear credenciales.
- Usar AWS profiles o roles IAM.
- Aplicar minimo privilegio.
- Bloquear S3 public access.
- Cifrar S3.
- No usar datos reales sensibles.
- Usar datos sinteticos o anonimizados.
- No exponer endpoints publicamente fuera del control de IAM.
- No exponer stack traces ni datos sensibles en responses.
- Registrar `request_id` y `model_version` para trazabilidad.
- No eliminar recursos externos sin confirmacion explicita.

## Datos y privacidad

`standalone_mode` debe usar datos sinteticos. `integrated_mode` debe asumir que los datos del laboratorio 3 son educativos, anonimizados o no sensibles. Si se usan datos propios, se debe revisar privacidad, retencion, cifrado y permisos antes de ejecutar inferencia.

## IAM minimo

Separar permisos por funcion:

- Lectura de artefactos.
- Escritura de outputs.
- Creacion de recursos SageMaker.
- Invocacion de endpoint.
- Consulta Feature Store.
- Observabilidad.
- Cleanup.

Evitar usar roles administrativos para el laboratorio si se puede crear un rol acotado.

## Cleanup seguro

La eliminacion debe limitarse a recursos creados por el laboratorio 4 y preferentemente identificados por tags o por un archivo de estado local. En `integrated_mode`, no borrar Model Package, Feature Group, Offline Store ni Online Store por defecto.
