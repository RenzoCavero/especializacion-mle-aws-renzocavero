# Lab 01 Overview

## Objetivo

Construir una solucion local end-to-end de Machine Learning para deteccion de fraude. El laboratorio traduce conceptos de AWS Machine Learning Foundations a scripts reproducibles.

## Historia Del Caso

Una transaccion llega al sistema y debe recibir un score de riesgo. El negocio necesita reducir fraude, pero tambien evitar friccion innecesaria para clientes legitimos.

## Pasos

1. `make data`: genera transacciones sinteticas.
2. `make prepare`: transforma datos crudos en features.
3. `make train`: entrena un modelo local.
4. `make evaluate`: valida generalizacion en holdout.
5. `make batch`: ejecuta scoring por lote.
6. `make monitor`: simula drift y senales operativas.
7. `make model-card`: genera gobernanza del modelo.
8. `make api`: expone `/health` y `/predict`.

## Resultado Esperado

Al final tendras:

- Datos crudos y procesados.
- Un modelo serializado.
- Metricas de evaluacion.
- Predicciones batch.
- Reporte de monitoreo.
- Model card.
- API local de inferencia.

