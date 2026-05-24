# Deployment Patterns Guide

Este documento compara los patrones de inferencia que el laboratorio debe explicar.

## Criterios de decision

| Criterio | Batch Transform | Real-Time Endpoint | Asynchronous Inference | Serverless Inference |
|---|---|---|---|---|
| Latencia | Minutos u horas | Milisegundos a segundos | Segundos a minutos | Milisegundos a segundos con cold start posible |
| Volumen | Alto o masivo | Bajo a alto continuo | Medio a alto | Bajo a variable |
| Tamano de payload | Archivos o lotes | Payload pequeno o medio | Payload grande | Payload pequeno o medio |
| Frecuencia | Programada o bajo demanda | Continua | Near real-time | Intermitente |
| Costo | Efimero por job | Persistente mientras el endpoint vive | Efimero o gestionado por cola | Pago por uso con limites |
| Operacion | Simple para lotes | Requiere capacidad, scaling y monitoreo | Requiere colas y outputs asincronos | Menor operacion |
| Escalabilidad | Por instancias de transform | Por variants y autoscaling | Por concurrencia asincrona | Gestionada con limites |
| Casos de uso | Scoring offline, reportes, forecasting | Fraude, recomendacion, aprobaciones | OCR, NLP pesado, documentos | Trafico irregular, demos, APIs con bajo uso |

## Batch Transform

Ideal para lotes masivos, reportes, churn scoring, forecasting y scoring offline. No requiere endpoint persistente, por lo que puede ser mas eficiente en costo cuando no se necesita respuesta inmediata.

Usar cuando:

- Hay muchos registros acumulados.
- La latencia no es critica.
- El consumidor espera un archivo de resultados.
- Se necesita reconstruir predicciones con IDs originales.

Evitar cuando:

- El usuario espera decision inmediata.
- Hay requests individuales interactivos.

## Real-Time Endpoint

Ideal para decisiones sincronas de baja latencia. Mantiene infraestructura activa para responder rapidamente.

Usar cuando:

- La aplicacion necesita respuesta inmediata.
- La latencia p95/p99 importa.
- Hay consumo continuo o predecible.
- Se requiere integracion directa con una aplicacion.

Precaucion: los endpoints persistentes generan costo mientras esten activos.

## Asynchronous Inference

Util para payloads grandes y procesamiento near real-time. El consumidor envia una solicitud y recupera el resultado despues.

Usar cuando:

- El payload individual es grande.
- El procesamiento puede tardar mas.
- El consumidor no necesita una respuesta sincrona.
- Hay necesidad de desacoplar request y resultado.

Casos frecuentes: OCR, imagenes, documentos, NLP pesado y procesos que pueden tardar varios minutos.

## Serverless Inference

Util para trafico intermitente con menor operacion. Reduce la necesidad de administrar capacidad persistente, pero puede introducir cold start y limites de payload/concurrencia.

Usar cuando:

- El trafico es variable o bajo.
- Hay tolerancia a cold start.
- Se quiere simplificar operacion.
- El payload y la latencia requerida estan dentro de los limites del servicio.

## Regla practica

Si el consumidor no espera respuesta inmediata, evitar un endpoint persistente y evaluar Batch Transform o Asynchronous Inference. Esto ayuda a optimizar TCO y reduce riesgos de dejar capacidad activa sin uso.
