# Plantillas De Prompts

Estas plantillas ayudan a pedir futuras tareas a Codex sin repetir todo el contexto.

## Nueva Feature Cloud

Antes de implementar, lee `AGENTS.md` y los archivos de `ai_context/`.

Quiero agregar la siguiente funcionalidad:

```text
[DESCRIBIR FEATURE]
```

Restricciones:

- Trabaja solo dentro de `2_ML-Data-Processing-Prep/`.
- Manten compatibilidad con `make all-cloud`.
- Actualiza tests si aplica.
- Actualiza documentacion si aplica.
- Usa AWS de forma controlada.
- No hardcodees credenciales.
- Manten minimo privilegio.
- Manten cleanup.
- Manten la separacion entre `raw`, `cleaned`, `curated`, `features` e `inference`.
- Manten la logica de features reutilizable entre entrenamiento e inferencia.

Entrega:

- Archivos modificados.
- Recursos AWS involucrados.
- Resumen tecnico.
- Como desplegar.
- Como probar.
- Como destruir recursos.
- Riesgos o supuestos.

## Correccion De Bug Cloud

Antes de implementar, lee `AGENTS.md`, `ai_context/RUNBOOK.md`, `ai_context/COST_AND_SECURITY.md` y `ai_context/CODE_REVIEW.md`.

Tengo este error:

```text
[PEGAR ERROR]
```

Corrige el problema respetando:

- No crear archivos fuera de `2_ML-Data-Processing-Prep/`.
- No romper `make all-cloud`.
- No eliminar documentacion ni artefactos necesarios.
- No dejar recursos huerfanos.
- Actualizar tests si aplica.

Entrega:

- Causa raiz.
- Archivos modificados.
- Recursos AWS impactados.
- Como validar la correccion.
- Como verificar que no quedaron recursos innecesarios.

## Refactor

Lee `AGENTS.md`, `ai_context/CODE_STYLE.md` y `ai_context/CODE_REVIEW.md`.

Quiero refactorizar:

```text
[DESCRIBIR MODULO, SCRIPT O PROBLEMA]
```

Objetivo:

```text
[DESCRIBIR RESULTADO ESPERADO]
```

Restricciones:

- Mantener comportamiento existente.
- No cambiar contratos S3 salvo que se documente.
- Mantener compatibilidad Windows/Linux cuando sea razonable.
- Actualizar tests y documentacion si aplica.

Entrega:

- Resumen del refactor.
- Archivos modificados.
- Riesgos reducidos.
- Validaciones ejecutadas.

## Agregar Test

Lee `AGENTS.md`, `ai_context/CODE_STYLE.md` y `ai_context/CODE_REVIEW.md`.

Agrega tests para:

```text
[DESCRIBIR FUNCIONALIDAD]
```

Los tests deben validar:

- Esquema esperado.
- Casos felices.
- Casos de error relevantes.
- Consistencia entrenamiento/inferencia si aplica.

Entrega:

- Tests agregados.
- Como ejecutarlos.
- Cobertura funcional.

## Mejorar Documentacion

Lee `AGENTS.md`, `ai_context/PROJECT_CONTEXT.md`, `ai_context/LAB_02_SPEC.md` y `ai_context/SOURCE_SUMMARY.md`.

Mejora la documentacion de:

```text
[DESCRIBIR SECCION]
```

Debe quedar:

- Clara para estudiantes.
- Alineada con AWS real.
- Con comandos reproducibles.
- Con advertencias de costo y seguridad cuando aplique.
- Sin crear archivos fuera del tema 2.

Entrega:

- Archivos modificados.
- Resumen de mejoras.
- Supuestos.

## Validar Alineacion Con AWS

Lee `AGENTS.md`, `ai_context/AWS_ARCHITECTURE_GUIDE.md`, `ai_context/INFRASTRUCTURE_GUIDE.md` y `ai_context/COST_AND_SECURITY.md`.

Revisa si la implementacion actual esta alineada con AWS real.

No modifiques archivos todavia.

Dime:

- Servicios AWS representados correctamente.
- Servicios o conceptos faltantes.
- Riesgos de seguridad.
- Riesgos de costo.
- Problemas de reproducibilidad.
- Recomendaciones priorizadas.

## Revisar Calidad Del Laboratorio Cloud

Lee `AGENTS.md` y `ai_context/CODE_REVIEW.md`.

Revisa el estado actual del laboratorio del tema 2.

No modifiques archivos todavia.

Dime:

- Que criterios ya se cumplen.
- Que criterios faltan.
- Que archivos deberian corregirse.
- Que riesgos ves en estructura, infraestructura, codigo, seguridad, costos, documentacion o ejecucion.
- Que priorizarias antes de entregar el laboratorio a estudiantes.

## Preparar Extension Hacia AWS Real

Lee `AGENTS.md`, `ai_context/LAB_02_SPEC.md`, `ai_context/AWS_ARCHITECTURE_GUIDE.md` e `ai_context/INFRASTRUCTURE_GUIDE.md`.

Quiero convertir la implementacion actual en una ejecucion cloud real en AWS.

Alcance:

```text
[DESCRIBIR ALCANCE: CloudFormation, SageMaker Processing, Glue, etc.]
```

Restricciones:

- Infraestructura reproducible.
- Deploy y destroy documentados.
- No credenciales hardcodeadas.
- Minimo privilegio.
- Control de costos.
- Datasets pequenos.

Entrega:

- Archivos modificados.
- Recursos AWS creados.
- Comandos de ejecucion.
- Cleanup.
- Riesgos.

## Agregar Una Nueva Validacion De Calidad

Lee `AGENTS.md`, `ai_context/CODE_STYLE.md`, `ai_context/LAB_02_SPEC.md` y `ai_context/CODE_REVIEW.md`.

Agrega la siguiente validacion de calidad:

```text
[DESCRIBIR REGLA: nulos, rango, duplicados, cardinalidad, drift de esquema, etc.]
```

Debe:

- Ejecutarse dentro del pipeline cloud.
- Generar reporte en `quality/`.
- Fallar o advertir segun severidad documentada.
- Tener test unitario cuando aplique.

Entrega:

- Regla implementada.
- Reporte esperado.
- Tests.
- Como ejecutar.

## Agregar Una Nueva Feature Al Pipeline

Lee `AGENTS.md`, `ai_context/CODE_STYLE.md` y `ai_context/SOURCE_SUMMARY.md`.

Agrega esta feature:

```text
[DESCRIBIR FEATURE]
```

Debe:

- Reutilizar logica entre entrenamiento e inferencia.
- Actualizar dataset card.
- Actualizar lineage.
- Actualizar tests.
- Mantener esquema documentado.

Entrega:

- Archivos modificados.
- Justificacion de la feature.
- Como se evita training-serving skew.
- Como validar.

## Revisar Consistencia Entrenamiento/Inferencia

Lee `AGENTS.md`, `ai_context/SOURCE_SUMMARY.md`, `ai_context/CODE_STYLE.md` y `ai_context/CODE_REVIEW.md`.

Revisa si la logica de features se reutiliza correctamente entre entrenamiento e inferencia.

No modifiques archivos todavia.

Dime:

- Donde se calcula cada feature.
- Riesgos de training-serving skew.
- Diferencias de esquema.
- Tests faltantes.
- Cambios recomendados.

## Mejorar Lineage O Dataset Card

Lee `AGENTS.md`, `ai_context/LAB_02_SPEC.md` y `ai_context/SOURCE_SUMMARY.md`.

Mejora:

```text
[LINEAGE, DATASET CARD O AMBOS]
```

Debe incluir:

- Fuentes.
- Transformaciones.
- Capas S3.
- Reglas de calidad.
- Features.
- Limitaciones.
- Uso previsto.
- Riesgos.

Entrega:

- Archivos modificados.
- Ejemplo de salida.
- Como generar el reporte.

## Mejorar Seguridad IAM

Lee `AGENTS.md`, `ai_context/INFRASTRUCTURE_GUIDE.md` y `ai_context/COST_AND_SECURITY.md`.

Revisa y mejora las politicas IAM.

Objetivo:

```text
[DESCRIBIR OBJETIVO]
```

Restricciones:

- Minimo privilegio.
- Recursos acotados al laboratorio.
- No romper deploy ni ejecucion.
- Documentar permisos requeridos.

Entrega:

- Cambios IAM.
- Riesgos mitigados.
- Como validar permisos.

## Mejorar Control De Costos

Lee `AGENTS.md`, `ai_context/COST_AND_SECURITY.md` y `ai_context/INFRASTRUCTURE_GUIDE.md`.

Mejora el control de costos del laboratorio.

Considera:

- Retencion de logs.
- Lifecycle en S3.
- Recursos efimeros.
- Feature Store offline/online.
- Tamanos de datasets.
- Cleanup.

Entrega:

- Cambios realizados.
- Costos mitigados.
- Como verificar recursos activos.

## Revisar Cleanup

Lee `AGENTS.md`, `ai_context/RUNBOOK.md`, `ai_context/INFRASTRUCTURE_GUIDE.md` y `ai_context/COST_AND_SECURITY.md`.

Revisa si el cleanup elimina todos los recursos creados.

No modifiques archivos todavia.

Dime:

- Recursos creados por el laboratorio.
- Recursos destruidos por el cleanup.
- Posibles recursos huerfanos.
- Riesgos de costo.
- Cambios recomendados.
