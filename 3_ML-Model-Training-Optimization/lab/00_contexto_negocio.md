# 00 - Contexto de negocio y formulacion ML

## Objetivo

Entender el problema que vas a resolver antes de crear recursos en AWS.

El laboratorio trabaja con un caso de prevencion de churn. El objetivo es estimar que clientes tienen mayor probabilidad de abandonar el servicio para priorizar acciones de retencion.

## Que vas a construir o validar

En los siguientes pasos vas a construir un flujo completo de entrenamiento:

1. Generar datos sinteticos de clientes.
2. Crear un contrato de features en SageMaker Feature Store.
3. Preparar datasets con SageMaker Processing.
4. Entrenar un baseline con SageMaker Training.
5. Evaluar metricas.
6. Optimizar hiperparametros con SageMaker Automatic Model Tuning.
7. Registrar el modelo seleccionado en SageMaker Model Registry.
8. Crear una definicion de SageMaker Pipeline.

Este primer paso no crea recursos. Sirve para dejar clara la decision de negocio que el modelo debe apoyar.

## Conceptos clave

| Concepto | Significado en este laboratorio |
|---|---|
| Churn | Abandono del cliente. |
| Clasificacion binaria | Tarea ML con dos clases: churn o no churn. |
| Target | Columna que el modelo aprende a predecir: `churn_label`. |
| Clase positiva | Cliente con riesgo de churn. |
| F1 score | Metrica principal para balancear precision y recall. |
| Recall | Capacidad de detectar clientes que realmente abandonarian. |
| Precision | Proporcion de alertas de churn que realmente corresponden a clientes en riesgo. |

## Prerrequisitos

1. Ubicate en la carpeta del laboratorio:

   ```bash
   cd 3_ML-Model-Training-Optimization
   ```

2. Revisa que el entorno virtual este activo y que las dependencias hayan sido instaladas:

   ```bash
   python -m pip install -r requirements.txt
   ```

## Pasos de ejecucion

Ejecuta:

```bash
make lab-00-context
```

Sin Make:

```bash
python -m src.lab_runner step 00
```

Con Bash o Git Bash:

```bash
bash scripts/lab.sh step 00
```

No hay wrapper PowerShell especifico para este paso. En Windows puedes usar el comando Python anterior.

Rutas importantes:

| Tipo | Ruta |
|---|---|
| Wrapper general | `scripts/lab.sh step 00` |
| Modulo que imprime el paso | `src/lab_runner.py` |
| Archivo de lectura del paso | `lab/00_contexto_negocio.md` |

## Resultado esperado

La terminal imprime el encabezado del paso. No se crean recursos AWS, archivos locales ni objetos S3.

Antes de avanzar, confirma que puedes responder:

1. Que decision de negocio apoya el modelo.
2. Que columna es el target.
3. Que significa un falso negativo.
4. Que significa un falso positivo.
5. Por que F1 es mas util que accuracy como criterio principal en este caso.

## Validacion en la consola AWS

Este paso no crea recursos en AWS. Aun asi, antes de ejecutar los pasos cloud:

1. Abre la consola AWS.
2. Confirma que estas en la cuenta correcta.
3. Confirma que la region corresponde a `AWS_REGION` en `.env`; por defecto, `us-east-1`.

## Problemas comunes y como resolverlos

| Problema | Causa probable | Solucion |
|---|---|---|
| `make` no existe en Windows | No tienes Make instalado. | Usa `python -m src.lab_runner step 00` o Git Bash con `bash scripts/lab.sh step 00`. |
| No sabes desde donde ejecutar el comando | Estas fuera de la carpeta del proyecto. | Ejecuta los comandos desde `3_ML-Model-Training-Optimization/`. |
| El paso menciona recursos cloud que aun no existen | Este paso es solo conceptual. | Los recursos AWS empiezan en el paso 01. |
