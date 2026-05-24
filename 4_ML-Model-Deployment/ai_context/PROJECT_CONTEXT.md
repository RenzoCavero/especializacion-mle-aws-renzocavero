# Project Context - Especializacion Machine Learning en AWS

Este repositorio contiene una especializacion educativa sobre Machine Learning en AWS. La secuencia completa esta organizada en seis temas:

1. AWS Machine Learning Foundations.
2. Procesamiento y preparacion de datos AWS - Machine Learning.
3. Entrenamiento y optimizacion de modelos AWS - Machine Learning.
4. Despliegue de modelo AWS - Machine Learning.
5. MLOps y automatizacion CI/CD/CT en AWS - Machine Learning.
6. Monitoreo y evaluacion Data Drift - AWS ML.

## Rol del tema 4

El tema 4 se enfoca exclusivamente en desplegar modelos ML en AWS. Su objetivo es llevar un artefacto entrenado hacia patrones de inferencia productivos usando Amazon SageMaker.

El laboratorio implementa dos patrones principales:

1. SageMaker Batch Transform para batch inference.
2. SageMaker Real-Time Endpoint para inferencia online de baja latencia.

Tambien explica Asynchronous Inference y Serverless Inference como alternativas de arquitectura, aunque no son obligatorias por defecto.

## Relacion con el tema 3

En `integrated_mode`, el tema 4 consume artefactos del tema 3:

- Model Registry.
- Model Package.
- `model.tar.gz`.
- Feature Group.
- Online Store.
- Offline Store.
- Feature contract.
- SageMaker Execution Role.

El laboratorio 4 no debe asumir que esos recursos siempre existen. Debe resolverlos cuando esten disponibles y fallar con mensajes claros cuando falte metadata critica.

## Ejecucion independiente

En `standalone_mode`, el tema 4 puede ejecutarse sin haber corrido el tema 3. Para ello debe preparar recursos minimos de ejemplo:

- Dataset sintetico de inferencia.
- Modelo simple o artefacto `model.tar.gz` de ejemplo.
- Contrato de features minimo.
- Batch input en S3.
- SageMaker Model.
- SageMaker Batch Transform Job.
- SageMaker Real-Time Endpoint.
- Feature Store con Online Store y Offline Store cuando no exista uno previo.

Esta ruta es la ruta educativa autonoma.

## Salida hacia temas futuros

El tema 4 debe preparar el camino para:

- Tema 5: automatizacion CI/CD/CT, despliegues repetibles, validaciones y comandos reproducibles.
- Tema 6: monitoreo, evaluacion, data drift, data capture, CloudWatch, trazabilidad y Model Monitor.

Por eso, todo despliegue debe producir metadata util: `request_id`, `model_version`, artefactos usados, S3 input/output, endpoint name, batch job name y reporte de despliegue.

## Principios de diseno

- Cloud-first: el laboratorio debe ejecutarse en AWS.
- Reproducible: comandos y variables deben estar documentados.
- Seguro: sin credenciales hardcodeadas, minimo privilegio y datos sinteticos o anonimizados.
- Controlado en costos: endpoints persistentes deben tener advertencias y cleanup.
- Educativo: la documentacion debe ser clara para una audiencia con conocimientos basicos o intermedios de cloud computing, data science y machine learning.
- Trazable: cada prediccion batch y online debe poder relacionarse con el input, el modelo y el flujo que la genero.
