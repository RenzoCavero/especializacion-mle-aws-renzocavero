# Code Style

## Version de Python

- Usar Python 3.11+ o 3.12.
- Mantener compatibilidad razonable con Windows y Linux.

## Organizacion esperada

La implementacion futura debe separar responsabilidades:

- `src/config.py`: configuracion centralizada.
- `src/aws_clients.py`: clientes AWS centralizados.
- Batch: preparacion de input, ejecucion de transform job, recoleccion y reconstruccion.
- Real-time: endpoint config, endpoint, wait, invocacion y validacion.
- Feature Store: lookup online y lectura offline.
- Autoscaling: registro de scalable target y policies.
- Reportes: generacion de reporte de despliegue.
- Cleanup: eliminacion segura de recursos creados.

## Estilo de codigo

- Codigo modular.
- Type hints cuando aplique.
- Funciones pequenas y testeables.
- Sin rutas absolutas.
- Sin credenciales reales.
- Logging claro con contexto util.
- Manejo explicito de errores.
- Mensajes comprensibles para la audiencia objetivo.
- Scripts ejecutables desde la raiz de `4_ML-Model-Deployment/`.
- Tests con pytest.

## Dependencias AWS

- Usar boto3 para llamadas AWS de bajo nivel.
- Usar SageMaker SDK cuando simplifique SageMaker Model, Transform Job o Endpoint.
- Centralizar sesiones y clientes para respetar `AWS_PROFILE` y `AWS_REGION`.

## Configuracion

Toda configuracion debe venir de:

- Variables de entorno.
- `.env` cargado con `python-dotenv`.
- Parametros CLI si se agregan.

No hardcodear nombres de cuenta, ARNs, buckets, perfiles, regiones ni credenciales.

## Logging

Cada script debe registrar:

- Modo (`LAB_MODE`).
- Region.
- Recurso creado o consultado.
- S3 URI de input/output cuando aplique.
- Nombre de endpoint o batch job.
- Mensajes de cleanup.

Evitar imprimir payloads completos si pueden contener datos sensibles.

## Manejo de errores

Errores esperados deben tener mensajes accionables:

- AWS profile no existe.
- Permisos insuficientes.
- Variable requerida faltante.
- Model Package no encontrado.
- Feature Group no encontrado.
- Endpoint fallo con `ContainerError`.
- Batch Transform fallo.

## Tests

Los tests deben cubrir:

- Validacion de configuracion.
- Deteccion de `LAB_MODE`.
- Validacion de feature contract.
- Construccion de payload batch y online.
- Reconstruccion de outputs batch.
- Seleccion segura de recursos para cleanup.

Evitar tests que creen recursos AWS por defecto. Usar mocks para unit tests y marcar pruebas cloud como integracion cuando existan.

## Compatibilidad

- Evitar comandos shell especificos si se puede usar Python portable.
- Documentar alternativas PowerShell y bash en el runbook.
- Usar `pathlib` en codigo Python.
- Usar rutas relativas a la raiz del laboratorio.
