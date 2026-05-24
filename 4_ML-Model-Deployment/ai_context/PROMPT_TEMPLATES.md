# Prompt Templates

Plantillas reutilizables para futuras consultas a Codex dentro de `4_ML-Model-Deployment/`.

## Nueva feature cloud

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Lee AGENTS.md y ai_context/*.md segun el orden indicado. Implementa la feature cloud: <descripcion>. Debe soportar standalone_mode e integrated_mode, no hardcodear credenciales, documentar costos y agregar cleanup seguro si crea recursos AWS.
```

## Correccion de bug batch

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Revisa el flujo SageMaker Batch Transform. Corrige el bug: <descripcion>. Conserva el uso de Batch Transform, valida input/output, mantiene IDs originales y agrega o ajusta tests.
```

## Correccion de bug endpoint

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Revisa el flujo SageMaker Real-Time Endpoint. Corrige el bug: <descripcion>. Valida request/response, CloudWatch logs, data capture y cleanup del endpoint.
```

## Mejorar autoscaling

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora la configuracion de Application Auto Scaling para el Real-Time Endpoint. Mantener min_capacity bajo, max_capacity controlado, metricas documentadas y cleanup del scalable target/policies.
```

## Mejorar data capture

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora data capture del endpoint para preparar el laboratorio 6. Registrar S3 output, porcentaje de captura, content types, request_id, model_version y documentar como verificar los archivos capturados.
```

## Mejorar Feature Store lookup

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora el lookup de Feature Store Online Store con GetRecord. Validar feature contract, record identifier, event time, ausencia de target, tipos esperados y creacion standalone de Feature Store cuando no exista.
```

## Mejorar standalone_mode

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora standalone_mode para que el laboratorio pueda ejecutarse sin laboratorio 3. Crear dataset sintetico, artefacto model.tar.gz minimo, contrato de features minimo, input batch en S3 y payload online sintetico.
```

## Mejorar integrated_mode

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora integrated_mode para reutilizar Model Registry, Model Package, model.tar.gz, Feature Group, Offline Store, Online Store, feature contract y SageMaker Execution Role del laboratorio 3. No borrar recursos externos por defecto.
```

## Mejorar documentacion

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Mejora la documentacion para la audiencia objetivo. Explica que Batch Transform no es un Batch Endpoint, compara batch, real-time, async y serverless, y mantiene comandos y cleanup claros.
```

## Revisar costos

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Revisa costos del laboratorio. Identifica endpoints persistentes, instancias, autoscaling, batch jobs, S3 y CloudWatch. Propone cambios para reducir gasto y asegurar cleanup.
```

## Revisar seguridad

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Revisa seguridad. Verifica que no haya credenciales, que se usen AWS profiles o roles IAM, minimo privilegio, S3 no publico, cifrado y respuestas sin datos sensibles.
```

## Preparar monitoreo futuro

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Prepara el camino para el laboratorio 6 de monitoreo y drift. Asegura data capture, CloudWatch metrics, logs, request_id, model_version, batch outputs trazables y documentacion de Model Monitor.
```

## Revisar cleanup

```text
Trabaja solo dentro de 4_ML-Model-Deployment/. Revisa cleanup. Debe eliminar endpoint, endpoint config, SageMaker Model y objetos S3 creados por el laboratorio si corresponde. No eliminar Model Package, Feature Group ni recursos externos por defecto.
```
