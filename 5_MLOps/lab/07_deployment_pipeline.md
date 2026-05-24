# 07 - Deployment pipeline

## Objetivo

Desplegar un modelo aprobado a un endpoint real-time minimo y validar inferencia.

## Que vas a construir o validar

Vas a crear un SageMaker Model, Endpoint Config y Endpoint. Luego se ejecuta un smoke test contra el endpoint.

## Input del paso

- Modelo aprobado en Model Registry.
- `SAGEMAKER_EXECUTION_ROLE_ARN`.
- `ENDPOINT_NAME`.
- `INSTANCE_TYPE`.
- Si usas `MODEL_ARTIFACT_S3_URI` sin Model Package, tambien `MODEL_IMAGE_URI`.
- Codigo de inferencia empaquetado por el paso en `s3://.../artifacts/source/inference.tar.gz`.

## Output esperado del paso

- SageMaker Model creado.
- SageMaker Model con variables de entorno de inferencia:
  - `SAGEMAKER_PROGRAM=inference.py`
  - `SAGEMAKER_SUBMIT_DIRECTORY=s3://.../inference.tar.gz`
- Endpoint Config creado.
- Endpoint en estado `InService`.
- Data Capture configurado si `ENABLE_DATA_CAPTURE=true`.
- Metadata local:
  - `endpoint_deployment.json`
  - `smoke_test.json`

## Conceptos claves

El deployment pipeline convierte un modelo aprobado en un servicio de inferencia. No debe partir de cualquier artefacto en S3, sino de una version aprobada o de un artefacto externo explicitamente configurado.

SageMaker separa tres conceptos: Model, Endpoint Config y Endpoint. `Model` define contenedor y artefacto. `Endpoint Config` define variantes, instancia y data capture. `Endpoint` es el recurso vivo que recibe trafico.

En contenedores preconstruidos de SageMaker scikit-learn, el artefacto `model.tar.gz` no basta por si solo para servir inferencia cuando se usa codigo custom. El contenedor necesita saber que modulo importar para `model_fn`, `input_fn`, `predict_fn` y `output_fn`. Ese contrato se define con `SAGEMAKER_PROGRAM` y `SAGEMAKER_SUBMIT_DIRECTORY`. Si esas variables faltan, el health check `/ping` falla porque el contenedor no puede importar el modulo de serving.

Este paso empaqueta `training/inference.py`, lo sube a S3 y crea el SageMaker Model con `Image`, `ModelDataUrl` y `Environment`. El Model Package sigue siendo la fuente gobernada de aprobacion, pero el modelo desplegado queda con el entrypoint explicito que el contenedor necesita para arrancar.

### Variables de entorno de inferencia

`SAGEMAKER_SUBMIT_DIRECTORY` es la ubicacion S3 de un `.tar.gz` con el codigo de inferencia custom. En este laboratorio, `src.deploy_model` empaqueta `training/inference.py` dentro de `inference.tar.gz` y lo sube a:

```text
s3://.../mlops-lab/lab/artifacts/source/inference.tar.gz
```

`SAGEMAKER_PROGRAM` es el archivo Python dentro de ese paquete que el contenedor debe importar. En este laboratorio es:

```text
SAGEMAKER_PROGRAM=inference.py
```

Durante el arranque del endpoint, SageMaker hace conceptualmente este flujo:

1. Inicia el contenedor preconstruido de scikit-learn.
2. Descarga el artefacto del modelo desde `ModelDataUrl`, es decir `model.tar.gz`.
3. Descarga y extrae el codigo desde `SAGEMAKER_SUBMIT_DIRECTORY`.
4. Importa el modulo indicado por `SAGEMAKER_PROGRAM`.
5. Usa las funciones del modulo:
   - `model_fn()` carga el modelo entrenado desde `/opt/ml/model`.
   - `input_fn()` convierte el request JSON/CSV en un `DataFrame`.
   - `predict_fn()` ejecuta la prediccion.
   - `output_fn()` serializa la respuesta como JSON o CSV.

Por eso estas variables viven en el **SageMaker Model**, no directamente en el Endpoint. El Endpoint apunta a un Endpoint Config, y el Endpoint Config apunta al Model.

Para verlo por CLI:

```bash
aws sagemaker describe-model \
  --model-name mlops-lab-endpoint-model \
  --query "PrimaryContainer.{Image:Image,ModelDataUrl:ModelDataUrl,Environment:Environment}" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

En consola:

```text
SageMaker AI > Deployments & inference > Models > mlops-lab-endpoint-model
```

Busca la seccion de `Primary container`, `Container details` o `Environment variables`. Ahi debes ver `SAGEMAKER_PROGRAM`, `SAGEMAKER_SUBMIT_DIRECTORY`, `SAGEMAKER_CONTAINER_LOG_LEVEL` y `SAGEMAKER_REGION`.

Si una ejecucion anterior dejo un endpoint en estado `Failed`, el paso reemplaza los recursos administrados por el laboratorio antes de recrearlos. Esto evita quedarse atrapado con un Endpoint Config o Model creado sin las variables de inferencia.

El endpoint real-time genera costo mientras esta activo. Esta es una diferencia importante frente a jobs batch o processing, que cobran durante ejecucion. Por eso el cleanup de endpoint es explicito y visible.

El smoke test no demuestra calidad del modelo. Solo valida que el endpoint responde con el contrato esperado. La calidad se gobierna con metricas de evaluacion y monitoreo posterior.

El deployment no reemplaza approval. El script busca un modelo `Approved`; si no existe, falla. Este patron evita despliegues accidentales de modelos pendientes o rechazados.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.deploy_model --wait` | `approved_model.json`, `training/inference.py`, `.env` | Model Package aprobado, modelo `model.tar.gz`, role de SageMaker | `endpoint_deployment.json` | SageMaker Model, Endpoint Config, Endpoint `InService`, `artifacts/source/inference.tar.gz` | Convertir el modelo aprobado en servicio real-time. |
| 2 | `src.smoke_test_endpoint` | Registro de prueba construido por el script | Endpoint `mlops-lab-endpoint` | `smoke_test.json` | Invocacion en SageMaker Runtime | Verificar contrato de respuesta `prediction` y `probability`. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Modelo aprobado | `artifacts/local_outputs/approved_model.json` | Paso 06 | `src.deploy_model`. |
| Codigo de inferencia | `training/inference.py` | Repositorio | `src.deploy_model` lo empaqueta. |
| Paquete de inferencia | `s3://<bucket>/mlops-lab/lab/artifacts/source/inference.tar.gz` | `src.deploy_model` | SageMaker Model mediante `SAGEMAKER_SUBMIT_DIRECTORY`. |
| Artefacto de modelo | `s3://<bucket>/mlops-lab/lab/artifacts/models/.../model.tar.gz` | Paso 05 | SageMaker Model. |
| Endpoint | `mlops-lab-endpoint` | `src.deploy_model` | Pasos 08, 09, 10, 11 y smoke tests. |
| Captura online | `s3://<bucket>/mlops-lab/lab/data-capture/mlops-lab-endpoint` | Endpoint Config si `ENABLE_DATA_CAPTURE=true` | Pasos 08, 09 y 11. |
| Evidencia local | `endpoint_deployment.json`, `smoke_test.json` | Scripts del paso 07 | Pasos 15 y troubleshooting. |

## Prerrequisitos

- Paso 06 completado.
- Permisos para crear modelo, endpoint config y endpoint.
- Quota disponible para el tipo de instancia.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 07
```

Comandos individuales:

```bash
python -m src.deploy_model --wait
python -m src.smoke_test_endpoint
```

## Resultado esperado

Endpoint `mlops-lab-endpoint` en `InService` y respuesta JSON con `prediction` y `probability`.

## Validacion local

```bash
type artifacts\local_outputs\smoke_test.json
```

## Validacion en consola AWS

- SageMaker > Endpoints > `mlops-lab-endpoint`.
- Revisar estado `InService`.
- Revisar Endpoint Config y Data Capture.
- En CloudWatch Logs, confirmar que `/ping` no retorna `500`.

Si ves `AttributeError: 'NoneType' object has no attribute 'startswith'` durante `/ping`, el modelo fue creado sin `SAGEMAKER_PROGRAM`. Vuelve a ejecutar este paso; la version actual reemplaza recursos fallidos del laboratorio y crea el modelo con el entrypoint de inferencia.

## Advertencia de costo

Ejecuta cleanup cuando termines:

```bash
python -m src.lab_runner cleanup
```

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.deploy_model --wait` | Crear/reutilizar SageMaker Model, EndpointConfig y Endpoint. | `deploy`, `_upload_inference_source`, `_build_capture_config`, `_replace_for_endpoint_config_change`. | `approved_model.json`, `training/inference.py`, `.env`. | `endpoint_deployment.json`, `inference.tar.gz` en S3, endpoint real. |
| `src.smoke_test_endpoint` | Invocar endpoint con payload de prueba. | `smoke_test`. | Endpoint `ENDPOINT_NAME`. | `smoke_test.json`. |
| `src.resolve_approved_model` | Se llama desde deploy si necesita resolver artefacto aprobado. | `resolve_approved_model`. | Model Registry. | `approved_model.json`. |

Configuraciones importantes:

- `ENDPOINT_NAME`, `INSTANCE_TYPE`, `INSTANCE_TYPE_CANDIDATES`.
- `CAPTURE_ENDPOINT_OUTPUT=true`: hace que Data Capture incluya input y output, necesario para Model Quality.
- `ENABLE_DATA_CAPTURE=true`: activa `DataCaptureConfig`.
- `CREATE_ENDPOINT=false`: permite saltar el despliegue en escenarios integrados.

Artefactos clave:

- `s3://.../artifacts/source/inference.tar.gz`: paquete con `training/inference.py`.
- `s3://.../data-capture/<endpoint>/`: destino de capturas.
- `artifacts/local_outputs/endpoint_deployment.json`: fuente local para saber si el endpoint quedo `InService`.

Troubleshooting:

- Si el endpoint queda `Failed`, revisa CloudWatch Logs del endpoint y vuelve a ejecutar este paso; el script reemplaza recursos fallidos creados por el lab.
- Si SageMaker bloquea la eliminacion por schedules asociados, el script intenta borrar schedules del lab antes de recrear.
- Si quieres forzar recreacion por cambios de captura o inferencia, usa `python -m src.deploy_model --wait --force-recreate`.
