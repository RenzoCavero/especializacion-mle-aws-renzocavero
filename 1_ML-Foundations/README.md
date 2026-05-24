# AWS Machine Learning Foundations

Laboratorio practico end-to-end del tema 1: **AWS Machine Learning Foundations**.

El objetivo es construir una mini solucion local de Machine Learning para deteccion de fraude / scoring de riesgo. 

## Caso De Negocio

Una empresa necesita reducir fraude transaccional sin bloquear demasiadas operaciones legitimas. El objetivo ML es estimar la probabilidad de fraude por transaccion y convertirla en una decision operativa:

- `approve`: riesgo bajo.
- `review`: riesgo medio, requiere revision.
- `block`: riesgo alto.

## Flujo Del Laboratorio

1. Generar dataset sintetico.
2. Preparar datos y features.
3. Entrenar un modelo local.
4. Evaluar con metricas adecuadas para fraude.
5. Ejecutar batch inference.
6. Exponer real-time inference local con FastAPI.
7. Simular monitoreo.
8. Generar model card y documentacion de gobernanza.

## Instalacion

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Windows Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

En Git Bash sobre Windows, el entorno virtual usa `Scripts/activate`, no `bin/activate`. Ejecuta estos comandos desde la raiz del laboratorio, por ejemplo:

```bash
cd ~/Documents/UTEC/AWS-MLE/1_ML-foundations
```

Si tu terminal muestra la carpeta como `1_ML-Foundations`, tambien funcionara en Windows porque el sistema de archivos normalmente no distingue mayusculas/minusculas.

## Ejecucion Completa

Con `make`:

```bash
make all
```

Sin `make`, ejecutar desde la raiz de `1_ML-foundations/`:

```bash
python -m src.generate_dataset
python -m src.data_preparation
python -m src.train
python -m src.evaluate
python -m src.batch_inference
python -m src.monitor
python -m src.model_card
```

Tambien puedes usar:

```bash
bash scripts/run_all.sh
```

En Windows PowerShell:

```powershell
.\scripts\run_all.ps1
```

En Windows Git Bash:

```bash
bash scripts/run_all.sh
```

## Volver Al Estado Inicial

Para dejar el laboratorio como antes de ejecutar el pipeline, elimina solo outputs generados: datasets, datos procesados, modelo, metricas, predicciones, model card y caches de Python. Esto no borra el codigo, la documentacion ni `doc/AWS_Machine_Learning_Foundations.pdf`.

Con `make`:

```bash
make clean
```

Linux/macOS:

```bash
bash scripts/clean_generated.sh
```

Windows Git Bash:

```bash
bash scripts/clean_generated.sh
```

Windows PowerShell:

```powershell
.\scripts\clean_generated.ps1
```

Vista previa sin borrar:

```bash
python scripts/clean_generated.py --dry-run
```

Si tambien quieres eliminar el entorno virtual, desactivalo primero y borralo manualmente:

Linux/macOS o Git Bash:

```bash
deactivate
rm -rf .venv
```

Windows PowerShell:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
```

### Limpiar Temporales De Pytest Bloqueados

Si despues de ejecutar tests aparecen carpetas como `.pytest_tmp`, `test_tmp` o `pytest-cache-files-*`, puedes eliminarlas desde la raiz de `1_ML-foundations/`.

PowerShell:

```powershell
Remove-Item -Recurse -Force .pytest_tmp, test_tmp -ErrorAction SilentlyContinue
Get-ChildItem -Force -Directory -Filter "pytest-cache-files-*" |
  Remove-Item -Recurse -Force
```

Git Bash:

```bash
rm -rf .pytest_tmp test_tmp pytest-cache-files-*
```

Si Windows responde `Access denied`, abre PowerShell como Administrador, entra a la raiz del laboratorio y recupera permisos antes de borrar:

```powershell
takeown /F .pytest_tmp /R /D Y
takeown /F test_tmp /R /D Y
Get-ChildItem -Force -Directory -Filter "pytest-cache-files-*" |
  ForEach-Object { takeown /F $_.FullName /R /D Y }

icacls .pytest_tmp /grant "$($env:USERNAME):(OI)(CI)F" /T
icacls test_tmp /grant "$($env:USERNAME):(OI)(CI)F" /T
Get-ChildItem -Force -Directory -Filter "pytest-cache-files-*" |
  ForEach-Object { icacls $_.FullName /grant "$($env:USERNAME):(OI)(CI)F" /T }

Remove-Item -Recurse -Force .pytest_tmp, test_tmp -ErrorAction SilentlyContinue
Get-ChildItem -Force -Directory -Filter "pytest-cache-files-*" |
  Remove-Item -Recurse -Force
```

## API Local

Levantar API:

```bash
make api
```

o:

```bash
uvicorn src.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Prediccion:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cus_12345","amount":450.0,"merchant_category":"digital_goods","country":"US","channel":"mobile","device_type":"android","hour":2,"day_of_week":5,"customer_age_days":120,"transactions_last_24h":8,"avg_amount_30d":75.0,"chargeback_rate_90d":0.08,"distance_from_home_km":180.0,"is_foreign_transaction":1,"is_high_risk_merchant":1}'
```

## Salidas Generadas

| Salida local | Descripcion | Equivalente AWS conceptual |
|---|---|---|
| `data/raw/fraud_transactions.csv` | Dataset sintetico crudo | Amazon S3 raw zone |
| `data/processed/train.csv` | Dataset de entrenamiento | Amazon S3 curated zone |
| `data/processed/test.csv` | Dataset de evaluacion | Amazon S3 curated zone |
| `artifacts/model/model.joblib` | Artefacto serializado del modelo | SageMaker model artifact |
| `artifacts/metrics/evaluation_metrics.json` | Metricas holdout | SageMaker Evaluation Step |
| `artifacts/predictions/batch_predictions.csv` | Predicciones batch | SageMaker Batch Transform |
| `artifacts/metrics/monitoring_report.json` | Simulacion de monitoreo | SageMaker Model Monitor + CloudWatch |
| `artifacts/metrics/drift_charts/*.svg` | Graficos de drift y alertas | SageMaker Model Monitor dashboards / CloudWatch dashboards |
| `artifacts/governance/model_card.md` | Documentacion de gobernanza | SageMaker Model Cards |

## Monitoreo Visual

El paso `python -m src.monitor` compara el baseline de entrenamiento contra el lote actual y genera graficos SVG en:

```text
artifacts/metrics/drift_charts/
```

Incluye histogramas baseline vs current para variables numericas, barras comparativas para categoricas, ranking PSI por feature y un heatmap simple de alertas. Puedes abrir los `.svg` directamente en el navegador.

## Metricas

Fraude suele ser un problema desbalanceado. Por eso el laboratorio reporta:

- Precision.
- Recall.
- F1-score.
- ROC AUC.
- PR AUC.
- Matriz de confusion.

Accuracy se reporta, pero no debe ser la metrica principal.

## Seguridad Y Costos

- No se usan credenciales reales.
- No se crean recursos AWS.
- No se ejecutan servicios AWS por defecto.
- `scripts/aws_upload_artifacts_optional.py` es opcional y requiere `--execute` explicitamente.

## Material Fuente

La fuente teorica principal esta en:

```text
doc/AWS_Machine_Learning_Foundations.pdf
```


## Documentacion Del Pipeline

Para entender en detalle que hace cada script, que archivos consume y genera, y como cada paso influye en el ciclo de vida ML, revisa:

```text
lab/03_script_reference.md
```
