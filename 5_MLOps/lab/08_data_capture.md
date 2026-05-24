# 08 - Data Capture

## Objetivo

Validar que el endpoint captura trafico de inferencia y generar solicitudes normales para alimentar monitoreo.

## Que vas a construir o validar

Vas a revisar la configuracion de Data Capture del endpoint y enviar trafico normal desde `inference_normal.jsonl`.

## Input del paso

- Endpoint `InService`.
- `ENABLE_DATA_CAPTURE=true`.
- Archivo `data/local_cache/inference_normal.jsonl`.
- Permisos para invocar endpoint.

## Output esperado del paso

- Metadata local:
  - `data_capture.json`
  - `traffic_normal.json`
  - `data_capture_check.json`
- Capturas en S3 bajo `data-capture/<endpoint>/`.

## Conceptos claves

Data Capture guarda payloads del endpoint. Esta evidencia permite analizar que datos reales esta recibiendo el modelo, que predicciones genera y como cambia el trafico con el tiempo.

La captura no reemplaza logging aplicativo. Es una fuente especializada para monitoreo de modelos, particularmente util para Model Monitor. Puede capturar input, output o ambos.

Para este laboratorio, la captura por defecto es `Input` y `Output`. La razon es que el paso 09 usa el flujo nativo de SageMaker Model Quality Monitor, y ese flujo necesita ver la prediccion capturada por el endpoint. Data Quality Monitor sigue usando principalmente las features de entrada para comparar contra el baseline.

El flag que controla esto es:

```env
CAPTURE_ENDPOINT_OUTPUT=true
```

Solo cambia a `false` si quieres aislar un flujo puramente de Data Quality y drift de features. Si `Output` esta activo, la respuesta del endpoint debe permanecer en un formato JSON compatible; por eso el endpoint del laboratorio responde como objeto JSON con `prediction` y `probability`.

Capturar output no reemplaza ground truth. Para performance, el paso 09 invoca el endpoint con `InferenceId` y sube labels retrasados a S3. SageMaker Model Quality Monitor une `endpointOutput` con ground truth usando ese identificador.

El porcentaje de captura controla costo y volumen. En el laboratorio se usa 100% para que sea facil ver evidencia; en produccion se ajusta segun volumen, sensibilidad y costo.

Data Capture escribe en S3 de forma asincrona. Puede haber demora entre invocar el endpoint y ver archivos en el bucket.

La consola de SageMaker puede variar segun si estas usando SageMaker Studio nuevo, Studio Classic o la consola antigua. En algunas vistas no existe una pestana separada llamada `Data Capture`; la configuracion aparece dentro de `Settings`, `Details` o en el Endpoint Config asociado. La fuente autoritativa no es el nombre de la pestana, sino:

- `DescribeEndpoint`: `DataCaptureConfig.CaptureStatus=Started`.
- `DescribeEndpointConfig`: `DataCaptureConfig.EnableCapture=true`.
- S3: archivos `.jsonl` escritos bajo el prefijo de captura.

El paso 08 valida esas tres cosas. Primero describe el endpoint y endpoint config, luego envia trafico, y finalmente espera archivos de captura en S3.

El trafico normal se usa como contraste contra trafico con drift. Si no hay trafico, Model Monitor no tiene datos recientes que comparar.

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.configure_data_capture` | `.env` | Endpoint y Endpoint Config | `data_capture.json` | Ninguno | Validar que Data Capture esta habilitado y documentar modo de captura. |
| 2 | `src.simulate_traffic` | `data/local_cache/inference_normal.jsonl` | Endpoint `mlops-lab-endpoint` | `traffic_normal.json` | Invocaciones al endpoint; capturas asincronas en S3 | Generar trafico normal para evidencia y monitoreo. |
| 3 | `src.check_data_capture --wait` | `.env` | Endpoint, Endpoint Config y prefijo S3 de captura | `data_capture_check.json` | Ninguno | Esperar y confirmar objetos `.jsonl` de Data Capture. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Trafico normal local | `data/local_cache/inference_normal.jsonl` | Paso 02 | `src.simulate_traffic`. |
| Endpoint | `mlops-lab-endpoint` | Paso 07 | Scripts del paso 08. |
| Configuracion de captura | Endpoint Config asociado | Paso 07 | `src.configure_data_capture` y `src.check_data_capture`. |
| Capturas online | `s3://<bucket>/mlops-lab/lab/data-capture/mlops-lab-endpoint/<endpoint>/AllTraffic/yyyy/mm/dd/hh/*.jsonl` | Data Capture de SageMaker | Paso 09 para model quality y paso 10 para data quality. |
| Evidencia local | `artifacts/local_outputs/data_capture.json` | `src.configure_data_capture` | Paso 14 y troubleshooting. |
| Trafico enviado | `artifacts/local_outputs/traffic_normal.json` | `src.simulate_traffic` | Paso 14 y troubleshooting. |
| Check de captura | `artifacts/local_outputs/data_capture_check.json` | `src.check_data_capture` | Paso 14 y troubleshooting. |

## Prerrequisitos

- Paso 07 completado.
- Datos de inferencia generados en paso 02.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 08
```

Comandos individuales:

```bash
python -m src.configure_data_capture
python -m src.simulate_traffic
python -m src.check_data_capture --wait
```

## Resultado esperado

El endpoint recibe solicitudes normales y la configuracion de captura queda documentada.

## Validacion local

```bash
type artifacts\local_outputs\traffic_normal.json
type artifacts\local_outputs\data_capture_check.json
```

`data_capture_check.json` debe mostrar:

```json
{
  "endpoint_capture_status": "Started",
  "enabled": true,
  "capture_modes": ["Input", "Output"],
  "status": "capture_files_found",
  "s3_listing": {
    "object_count": 1
  }
}
```

## Validacion en consola AWS

- SageMaker > Endpoints > `mlops-lab-endpoint`.
- Revisar `Settings` o `Details` del endpoint y confirmar Data Capture habilitado.
- Revisar el Endpoint Config asociado y confirmar `EnableCapture=true`.
- S3 > bucket del laboratorio > prefijo `mlops-lab/lab/data-capture/`.
- CloudWatch Logs del endpoint si hay errores.

Si no ves una pestana llamada `Data Capture`, usa la validacion por S3. En Studio nuevo puede no aparecer como pestana independiente.

Validacion por CLI:

```bash
aws sagemaker describe-endpoint \
  --endpoint-name mlops-lab-endpoint \
  --query "DataCaptureConfig" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>

aws s3 ls s3://<bucket>/mlops-lab/lab/data-capture/ --recursive --profile <AWS_PROFILE>
```

## Troubleshooting: encoding mismatch en Model Monitor

Si un monitoring execution falla con:

```text
Encoding mismatch: Encoding is JSON for endpointInput, but Encoding is BASE64 for endpointOutput
```

significa que el endpoint o su contrato de respuesta no esta alineado con lo que Model Monitor espera leer. Para este laboratorio, primero valida el endpoint existente:

```bash
python -m src.validate_model_quality_endpoint
```

Si el endpoint viene de una version antigua del laboratorio o quedo con un Endpoint Config incompatible, recrealo explicitamente con la version actual del `output_fn`, que devuelve JSON simple:

```bash
python -m src.deploy_model --wait --force-recreate
```

Despues ejecuta de nuevo los pasos 08 y 09 para generar capturas frescas. Si quieres desactivar el flujo nativo de Model Quality y quedarte solo con Data Quality de inputs, puedes definir `CAPTURE_ENDPOINT_OUTPUT=false` y recrear el endpoint, pero el paso 09 nativo ya no aplicara.

## Consideracion de privacidad

En escenarios reales, capturar payloads puede incluir informacion sensible. Usar cifrado, acceso restringido y politicas de retencion.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.configure_data_capture` | Describir configuracion de captura activa en el endpoint. | `describe_data_capture`. | Endpoint y EndpointConfig. | `data_capture.json`. |
| `src.simulate_traffic` | Enviar trafico normal al endpoint. | `_load_records`, `send_traffic`. | `data/local_cache/inference_normal.jsonl`. | `traffic_normal.json`, capturas asincronas en S3. |
| `src.check_data_capture --wait` | Verificar que S3 recibio archivos `.jsonl`. | `list_capture_objects`, `check_data_capture`. | Endpoint config y prefijo S3. | `data_capture_check.json`. |

Inputs y outputs importantes:

- Entrada local: `data/local_cache/inference_normal.jsonl`.
- Recurso AWS: `ENDPOINT_NAME`.
- Salida S3: `s3://<bucket>/<prefix>/data-capture/<endpoint>/<endpoint>/AllTraffic/yyyy/mm/dd/hh/*.jsonl`.
- Evidencia local: `artifacts/local_outputs/data_capture.json`, `traffic_normal.json`, `data_capture_check.json`.

Parametros modificables:

- `ENABLE_DATA_CAPTURE`: activa o desactiva captura al desplegar endpoint.
- `CAPTURE_ENDPOINT_OUTPUT`: agrega output capture si es `true`.
- `DATA_CAPTURE_S3_URI`: permite usar un destino S3 externo en modo integrado.

Troubleshooting:

- Data Capture escribe con retraso; usa `--wait`.
- Si solo aparecen capturas antiguas, revisa `latest_modified` en `data_capture_check.json`.
- Si el endpoint no tiene Output capture y necesitas Model Quality, recrea con `CAPTURE_ENDPOINT_OUTPUT=true`.

