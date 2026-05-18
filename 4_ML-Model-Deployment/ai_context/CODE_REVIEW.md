# Code Review Checklist

Usar este checklist para revisar cambios del laboratorio 4.

## Alcance

- [ ] Se crearon archivos fuera de `4_ML-Model-Deployment/`?
- [ ] Se modificaron archivos fuera de `4_ML-Model-Deployment/`?
- [ ] Se respeto `doc/4_AWS_Model_Deployment.pdf` sin moverlo ni renombrarlo?

## Ejecucion AWS

- [ ] El laboratorio se ejecuta en AWS?
- [ ] Soporta `standalone_mode`?
- [ ] Soporta `integrated_mode`?
- [ ] Se reutiliza Model Registry o `model.tar.gz` si existe?
- [ ] Existe fallback standalone si no hay laboratorio 3?

## Patrones de inferencia

- [ ] Se usa Batch Transform para batch inference?
- [ ] Se usa Real-Time Endpoint para inferencia online?
- [ ] Se evita llamar "Batch Endpoint" al Batch Transform Job?
- [ ] La documentacion explica batch, real-time, async y serverless?

## Datos y Feature Store

- [ ] Se usa Offline Store o S3 para batch input?
- [ ] Se usa Online Store para real-time feature lookup cuando existe?
- [ ] En standalone, se crea Feature Store con Online Store y Offline Store si no existe?
- [ ] Batch Transform consume export S3 derivado del Offline Store?
- [ ] Real-time obtiene features con `GetRecord` desde Online Store?
- [ ] Se valida el contrato de features?
- [ ] La columna target queda excluida de inferencia?
- [ ] Se conserva el ID original en batch output?
- [ ] Se valida request/response?

## Observabilidad y operacion

- [ ] Se configura o documenta data capture?
- [ ] Se configura o documenta autoscaling?
- [ ] Se revisan logs y metricas en CloudWatch?
- [ ] Se prepara el camino para el laboratorio de monitoreo y data drift?

## Seguridad y costo

- [ ] Se documentan costos de endpoint persistente?
- [ ] Existe cleanup seguro?
- [ ] No se eliminan recursos externos por defecto?
- [ ] No hay credenciales reales?
- [ ] Los buckets no son publicos?
- [ ] Se usa minimo privilegio?
- [ ] Se cifra S3 o se documenta el mecanismo esperado?

## Calidad educativa

- [ ] La documentacion es clara para la audiencia objetivo?
- [ ] Los errores esperados tienen troubleshooting?
- [ ] Los comandos son reproducibles?
- [ ] Los nombres de recursos siguen la convencion del laboratorio?
- [ ] Los outputs son trazables?
