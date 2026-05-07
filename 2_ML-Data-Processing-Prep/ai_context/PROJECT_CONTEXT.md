# Contexto Del Proyecto

Este repositorio forma parte de una especializacion educativa y practica sobre Machine Learning en AWS. El objetivo general es que profesionales con conocimientos basicos o intermedios de cloud computing, data engineering y machine learning aprendan a construir soluciones ML con criterios cercanos a produccion: arquitectura clara, reproducibilidad, seguridad, control de costos, calidad de datos, gobernanza y continuidad operativa.

## Temario De La Especializacion

1. AWS Machine Learning Foundations
2. Procesamiento y preparacion de datos AWS - Machine Learning
3. Entrenamiento y optimizacion de modelos AWS - Machine Learning
4. Batch Inference in AWS - Machine Learning
5. Real-Time Inference in AWS - Machine Learning
6. MLOps y automatizacion CI/CD/CT en AWS - Machine Learning
7. Monitoreo y evaluacion Data Drift - AWS ML

## Estado Actual

Por ahora se construye solo el laboratorio del tema 2:

```text
2_ML-Data-Processing-Prep/
```

Aunque el alcance inmediato es preparacion de datos, el diseno debe dejar bases limpias para los laboratorios posteriores. Los datasets, features, reportes y convenciones generados aqui deben poder reutilizarse en entrenamiento, inferencia batch, inferencia real-time, MLOps y monitoreo.

## Audiencia

La audiencia esperada son profesionales que ya conocen conceptos basicos o intermedios de:

- Cloud computing.
- Data engineering.
- Python.
- Machine Learning aplicado.
- Servicios AWS a nivel introductorio.

El laboratorio debe ser tecnico y didactico a la vez. No debe quedarse en teoria, pero tampoco debe ocultar decisiones importantes de arquitectura, seguridad, costos o gobernanza.

## Estilo Esperado

El proyecto debe tener un estilo:

- Tecnico.
- Didactico.
- Aplicable a proyectos reales.
- Orientado a arquitectura.
- Orientado a produccion.
- Con buenas practicas de calidad de datos.
- Con consistencia entre entrenamiento e inferencia.
- Con seguridad e IAM de minimo privilegio.
- Con control de costos.
- Con gobernanza, lineage y documentacion.

## Relacion Con El Tema 1

El tema 1 introduce el ciclo de vida de Machine Learning en AWS: definicion del problema, datos, entrenamiento, despliegue, inferencia, automatizacion, monitoreo y mejora continua.

El tema 2 profundiza en la etapa de datos. Su foco es convertir datos crudos, ruidosos o inconsistentes en datasets confiables para entrenamiento e inferencia. Esto incluye data lake, calidad, profiling, limpieza, transformacion, feature engineering, catalogacion, seguridad y trazabilidad.

La relacion practica es:

- Tema 1 da el mapa del ciclo de vida ML.
- Tema 2 implementa la base de datos y features para ese ciclo.
- Temas 3 a 7 consumiran o extenderan los outputs del tema 2.

## Continuidad Hacia Futuros Laboratorios

El laboratorio del tema 2 debe preparar la continuidad de esta forma:

- Entrenamiento y optimizacion: generar datasets de entrenamiento versionables y reportes de calidad para justificar el entrenamiento.
- Batch inference: generar datasets de inferencia bajo `inference/` con el mismo esquema de features.
- Real-time inference: separar la logica de feature engineering para poder convertirla luego en transformaciones online o precomputadas.
- MLOps: documentar parametros, artefactos, lineage y comandos reproducibles que puedan integrarse con pipelines.
- Monitoreo y data drift: guardar perfiles, estadisticas y dataset cards que puedan servir como baseline de monitoreo.

## Principio Rector

El laboratorio debe ensenar que un modelo ML no empieza en el algoritmo. Empieza en datos confiables, trazables, seguros, reproducibles y preparados con la misma logica que se usara en produccion.
