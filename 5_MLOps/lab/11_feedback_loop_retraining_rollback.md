# 11 - Feedback loop, retraining y rollback

## Objetivo

Crear el feedback loop gobernado que convierte alarmas en decisiones operativas controladas.

## Que vas a construir o validar

Vas a crear Lambdas, una state machine de Step Functions, un topic SNS con suscripcion email y una regla EventBridge que enruta alarmas hacia el flujo de decision y hacia email.

## Input del paso

- `LAMBDA_EXECUTION_ROLE_ARN`.
- `STEPFUNCTIONS_ROLE_ARN`.
- `EVENTBRIDGE_TO_SFN_ROLE_ARN`.
- `stepfunctions/feedback_loop.asl.json`.
- Handlers en `lambdas/`.
- Alarma de Data Quality creada en el paso 10. Puede ser `mlops-data-quality-alarm` o `mlops-custom-data-quality-alarm`, segun la ruta activa.
- Si ejecutas el paso 09, la misma regla tambien escucha `mlops-model-quality-alarm` y `mlops-custom-model-quality-alarm`.
- Si ejecutas el paso 12, la misma regla tambien puede escuchar `mlops-custom-batch-data-quality-alarm`.
- `ALARM_EMAIL`, por defecto `enriquemejiagamarra@gmail.com`.
- `ALARM_SNS_TOPIC_NAME`, por defecto `mlops-lab-alarm-notifications`.

## Output esperado del paso

- Lambda functions:
  - feedback handler.
  - retraining trigger.
  - rollback handler.
  - baseline update handler.
  - human review handler.
- Step Functions state machine `mlops-feedback-loop`.
- SNS topic `mlops-lab-alarm-notifications`.
- Suscripcion email pendiente de confirmacion o existente.
- EventBridge rule `mlops-lab-alarm-to-feedback-loop`.
- Ejecucion manual de prueba.
- Metadata local:
  - `feedback_loop.json`.
  - `alarm_notifications.json`.
  - `eventbridge_rule.json`.
  - `feedback_loop_execution.json`.

## Conceptos claves

El feedback loop es la frontera entre observabilidad y operacion. Model Monitor detecta drift/data quality, el paso 09 detecta degradacion de model quality, CloudWatch alerta, EventBridge enruta, Step Functions decide y Lambda ejecuta acciones ligeras.

SNS es el canal humano de notificacion. El laboratorio no envia email directamente desde Lambda; crea un topic SNS y EventBridge publica ahi los eventos de alarma. La primera vez, AWS envia un correo de confirmacion al destinatario. Hasta que esa suscripcion se confirme, SNS no entregara notificaciones.

El correo de confirmacion de SNS puede caer en Spam/Correo no deseado, especialmente en Gmail. Busca un mensaje con asunto parecido a `AWS Notification - Subscription Confirmation` enviado por `no-reply@sns.amazonaws.com`, abre el mensaje y usa el enlace `Confirm subscription`. Si `src.create_alarm_notifications` muestra un ARN de subscription en vez de `PendingConfirmation`, AWS ya considera la suscripcion confirmada.

Hay varias reglas EventBridge distintas que suelen verse durante el laboratorio:

| Regla | Donde aparece | Proposito |
|---|---|---|
| `mlops-custom-data-quality-schedule` | `EventBridge -> Scheduler -> Scheduled rules (legacy)` | Cron del paso 10. Invoca la Lambda `mlops-custom-data-quality-trigger` para iniciar un Processing Job custom de Data Quality si el schedule nativo no esta disponible. |
| `mlops-custom-model-quality-schedule` | `EventBridge -> Scheduler -> Scheduled rules (legacy)` | Cron del paso 09. Invoca la Lambda `mlops-custom-model-quality-trigger` para iniciar un Processing Job custom de Model Quality. |
| `mlops-lab-alarm-to-feedback-loop` | `EventBridge -> Buses -> Rules` | Regla de este paso. Escucha cambios de estado `ALARM` de CloudWatch y los enruta hacia SNS y Step Functions. |

Las reglas `mlops-custom-*-schedule` programan evaluaciones periodicas. La regla `mlops-lab-alarm-to-feedback-loop` reacciona a alarmas. No cumplen la misma funcion y pueden coexistir.

No hay dos reglas de alarma separadas por defecto. Hay **una sola regla EventBridge de alarmas** con dos targets opcionales:

```text
CloudWatch Alarm -> EventBridge rule -> SNS topic -> Email
CloudWatch Alarm -> EventBridge rule -> Step Functions -> Lambda decision/action handlers
```

El target SNS se configura cuando existe `alarm_notifications.json`; el target Step Functions se configura cuando existe `feedback_loop.json` y `EVENTBRIDGE_TO_SFN_ROLE_ARN` esta definido. Los cron de `mlops-custom-data-quality-schedule` y `mlops-custom-model-quality-schedule` son reglas distintas porque no reaccionan a alarmas: disparan jobs periodicos.

Step Functions usa un estado `Choice` para seleccionar una sola accion. Esto evita bucles infinitos y hace visible el camino tomado. El flujo implementado tiene ramas para retraining, rollback, baseline update, human review y no action.

Lambda debe mantenerse ligera. No entrena modelos pesados directamente. Puede diagnosticar, leer metadata, iniciar un pipeline, registrar evidencia o preparar una accion.

Retraining esta deshabilitado por defecto con `ENABLE_AUTOMATIC_RETRAINING=false`. Si una violation severa ocurre, el flujo recomienda revision en lugar de iniciar costos automaticamente. Para activar retraining real, el flag debe cambiar de forma explicita.

Rollback tambien es seguro por defecto. Cambiar trafico de un endpoint puede impactar consumidores. Por eso el handler registra plan y evidencia, pero no altera trafico sin controles adicionales.

Baseline update es una decision delicada. Actualizar baseline puede ser correcto si el negocio cambio; tambien puede ocultar un bug. El flujo lo trata como accion controlada y auditable.

Alarmas escuchadas por EventBridge:

| Tipo | Alarma | Metrica |
|---|---|---|
| Data Quality nativo | `mlops-data-quality-alarm` | `MLOps/Lab / DataQualityViolations` en este lab. En produccion podria apuntar a metricas nativas de Model Monitor. |
| Data Quality custom | `mlops-custom-data-quality-alarm` | `MLOps/Lab / DataQualityViolations`. |
| Batch Data Quality custom | `mlops-custom-batch-data-quality-alarm` | `MLOps/Lab / BatchDataQualityViolations`. |
| Model Quality nativo | `mlops-model-quality-alarm` | `aws/sagemaker/Endpoints/model-metrics / f1`. |
| Model Quality custom | `mlops-custom-model-quality-alarm` | `MLOps/Lab / ModelQualityF1`. |

`lambdas/feedback_handler/lambda_function.py` deriva severidad desde el evento de CloudWatch:

| Caso | Regla de severidad |
|---|---|
| Data Quality | Usa el ultimo datapoint de `DataQualityViolations`: `0=none`, `1=low`, `2-4=medium`, `5-9=high`, `10+=critical`. |
| Model Quality | Usa degradacion relativa de F1 contra `MODEL_QUALITY_F1_THRESHOLD`: `<10%=low`, `10-24.99%=medium`, `25-49.99%=high`, `>=50%=critical`. |

Ejemplo: con threshold F1 `0.70`, un F1 de `0.50` representa una degradacion de `28.57%`, por lo que se clasifica como `high`. Un F1 de `0.30` representa `57.14%`, por lo que se clasifica como `critical`.

### Nota conceptual: severidad en produccion

La regla del laboratorio es correcta como punto de partida didactico: Data
Quality se interpreta por conteo de violations y Model Quality por degradacion
relativa de F1. Es facil de probar, facil de explicar y suficiente para conectar
CloudWatch, EventBridge, SNS y Step Functions.

En produccion, la severidad no deberia depender de una sola metrica aislada.
Una definicion mas robusta combina al menos estos factores:

| Factor | Data Quality | Model Quality |
|---|---|---|
| Magnitud | Numero de violations, features afectadas y distancia contra el baseline. | Caida relativa y absoluta de F1, accuracy, AUC, precision o recall. |
| Duracion | Cuantos periodos consecutivos muestran drift. | Cuantos periodos consecutivos muestran degradacion. |
| Volumen | Porcentaje de requests o registros afectados. | Numero de predicciones evaluadas y confianza estadistica. |
| Criticidad de feature o segmento | Drift en una feature critica pesa mas que drift en una feature auxiliar. | Degradacion en un segmento critico pesa mas que degradacion global pequena. |
| Impacto de negocio | Riesgo operacional, fraude, perdida, SLA o experiencia de cliente. | Error costoso, falso positivo/falso negativo sensible o incumplimiento regulatorio. |
| Confianza | Calidad del ground truth, retraso de labels y cantidad minima de muestras. | Labels confirmados, ventana representativa y ausencia de sesgos de muestreo. |

Una practica mas madura es definir niveles como `low`, `medium`, `high` y
`critical` con una matriz de impacto y confianza. Por ejemplo:

| Severidad | Ejemplo de criterio Data Quality | Ejemplo de criterio Model Quality | Accion esperada |
|---|---|---|---|
| `low` | Una violation aislada, bajo volumen, feature no critica. | F1 cae menos de 10% y hay pocas muestras afectadas. | Revisar evidencia sin interrumpir operacion. |
| `medium` | Varias violations o cambio persistente por 2-3 periodos. | F1 cae 10-25% o afecta un segmento importante. | Crear investigacion y evaluar baseline update o ajuste de datos. |
| `high` | Drift en features criticas, alto volumen o persistencia clara. | F1 cae 25-50%, precision/recall criticos se deterioran o aumenta el costo de error. | Escalar a Data Scientist/on-call; evaluar retraining o mitigacion. |
| `critical` | Drift masivo, schema roto, nulos severos o riesgo operacional inmediato. | F1 cae 50% o mas, modelo inutil para un segmento critico o impacto regulatorio. | Incidente; considerar rollback, bloqueo, retraining urgente o decision manual obligatoria. |

Tambien conviene usar configuracion de CloudWatch que reduzca ruido: periodos de
evaluacion, `DatapointsToAlarm` y tratamiento de missing data deben reflejar la
latencia real de las metricas y labels. Para Model Quality, no conviene alarmar
con pocas etiquetas; usa un minimo de registros antes de clasificar severidad.

Decision esperada en produccion por rama:

| Rama | Como se activa en el lab | Decision esperada en produccion |
|---|---|---|
| `HumanReview` | Severidad `low`, o `high/critical` cuando `ENABLE_AUTOMATIC_RETRAINING=false`. | Crear ticket o notificar a Data Scientist/on-call con evidencia, links a S3, metrica, endpoint y ventana afectada. Puede usar SNS, Slack, Jira u OpsCenter. |
| `BaselineUpdate` | Severidad `medium`. | Abrir un cambio gobernado para actualizar baseline solo si negocio confirma que la distribucion nueva es valida. |
| `Retraining` | Severidad `high/critical` y `ENABLE_AUTOMATIC_RETRAINING=true`. | Iniciar pipeline de retraining con presupuesto, aprobacion y quality gates. El lab solo lo activa con opt-in explicito. |
| `Rollback` | Entrada manual con `recommended_action=rollback` o una regla de diagnostico extendida. | Cambiar trafico a un modelo aprobado anterior despues de smoke tests y validacion de consumidores. En el lab es placeholder seguro. |
| `NoAction` | `violations_count=0` o alarma sin degradacion. | Registrar evidencia y cerrar sin cambios. |

## Flujo detallado del paso

| Orden | Script | Input local | Input S3/AWS | Output local | Output S3/AWS | Proposito |
|---:|---|---|---|---|---|---|
| 1 | `src.create_feedback_loop` | `stepfunctions/feedback_loop.asl.json`, handlers en `lambdas/`, `.env` | Roles de Lambda y Step Functions | `feedback_loop.json` | Lambdas y State Machine `mlops-feedback-loop` | Crear la capa de decision gobernada. |
| 2 | `src.create_alarm_notifications` | `.env` | SNS, account id y nombre de la regla EventBridge | `alarm_notifications.json` | SNS topic y suscripcion email | Preparar el canal de email para eventos de alarma. |
| 3 | `src.create_eventbridge_rule` | `feedback_loop.json`, `alarm_notifications.json`, `.env` | CloudWatch Alarms, SNS topic y role EventBridge -> Step Functions | `eventbridge_rule.json` | Rule `mlops-lab-alarm-to-feedback-loop` con targets a Step Functions y SNS | Enrutar alarmas a decision y email. |
| 4 | `src.trigger_feedback_loop` | Metadata local disponible | State Machine | `feedback_loop_execution.json` | Execution manual de prueba | Probar el flujo sin esperar una alarma real. |

## Paths principales

| Tipo | Path o recurso | Quien lo crea | Quien lo consume |
|---|---|---|---|
| Definicion ASL | `stepfunctions/feedback_loop.asl.json` | Repositorio | `src.create_feedback_loop`. |
| Lambda handlers | `lambdas/*.py` | Repositorio | `src.create_feedback_loop`. |
| State machine | `arn:aws:states:<region>:<account>:stateMachine:mlops-feedback-loop` | `src.create_feedback_loop` | EventBridge y ejecuciones manuales. |
| SNS topic | `mlops-lab-alarm-notifications` | `src.create_alarm_notifications` | EventBridge rule. |
| Suscripcion email | `enriquemejiagamarra@gmail.com` o `ALARM_EMAIL` | `src.create_alarm_notifications` | SNS entrega emails despues de confirmacion. |
| EventBridge rule | `mlops-lab-alarm-to-feedback-loop` | `src.create_eventbridge_rule` | CloudWatch alarm state changes. |
| Metadata feedback | `artifacts/local_outputs/feedback_loop.json` | `src.create_feedback_loop` | Cleanup y readiness. |
| Metadata SNS | `artifacts/local_outputs/alarm_notifications.json` | `src.create_alarm_notifications` | EventBridge y auditoria. |
| Metadata EventBridge | `artifacts/local_outputs/eventbridge_rule.json` | `src.create_eventbridge_rule` | Cleanup y readiness. |
| Ejecucion de prueba | `artifacts/local_outputs/feedback_loop_execution.json` | `src.trigger_feedback_loop` | Paso 14 y auditoria. |

## Prerrequisitos

- Paso 10 completado.
- Paso 09 recomendado si quieres que la misma regla tambien escuche `mlops-model-quality-alarm` y `mlops-custom-model-quality-alarm`.
- Roles de Lambda, Step Functions y EventBridge disponibles.
- Confirmar el correo de SNS cuando AWS envie el email de suscripcion.

## Pasos de ejecucion

```bash
python -m src.lab_runner step 11
```

Comandos individuales:

```bash
python -m src.create_feedback_loop
python -m src.create_alarm_notifications
python -m src.create_eventbridge_rule
python -m src.trigger_feedback_loop
```

## Resultado esperado

La ejecucion manual de Step Functions inicia y queda registrada. El topic SNS queda creado y el email queda en estado pendiente hasta que el destinatario confirme la suscripcion.

Si antes ejecutaste:

```bash
python -m src.simulate_model_quality_alarm --wait
```

el alarm `mlops-custom-model-quality-alarm` deberia pasar a `ALARM` despues de que CloudWatch reciba la metrica `MLOps/Lab / ModelQualityF1`. Con este paso ya creado y la suscripcion SNS confirmada, el cambio de estado del alarm debe producir:

- Evento en EventBridge con `detail-type=CloudWatch Alarm State Change`.
- Publicacion al topic SNS `mlops-lab-alarm-notifications`.
- Email al valor de `ALARM_EMAIL`.
- Ejecucion de Step Functions si `EVENTBRIDGE_TO_SFN_ROLE_ARN` esta configurado.

## Prueba de email y alarmas

Primero confirma la suscripcion SNS. Luego prueba el topic directamente:

```bash
aws sns publish \
  --topic-arn arn:aws:sns:<AWS_REGION>:<ACCOUNT_ID>:mlops-lab-alarm-notifications \
  --subject "MLOps lab SNS test after confirmation" \
  --message "SNS is confirmed and working." \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

Si ese correo llega, SNS esta funcionando. Si no llega, revisa Spam, confirma la suscripcion y valida el topic en SNS.

Despues prueba el flujo completo con alarmas reales. EventBridge solo envia el evento cuando una alarma cambia de estado hacia `ALARM`. Si una alarma ya esta en `ALARM`, repetir la simulacion puede no mandar otro correo hasta que la alarma vuelva a `OK` y luego entre otra vez en `ALARM`.

Para revisar estados:

```bash
aws cloudwatch describe-alarms \
  --alarm-names mlops-data-quality-alarm mlops-custom-data-quality-alarm mlops-custom-batch-data-quality-alarm mlops-custom-model-quality-alarm \
  --query "MetricAlarms[].{Name:AlarmName,State:StateValue,Reason:StateReason}" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

Probar Data Quality:

```bash
python -m src.simulate_data_quality_alarm --wait
```

Ese comando publica `MLOps/Lab / DataQualityViolations` y debe mover la alarma activa de Data Quality a `ALARM` si el conteo es mayor o igual a `ALARM_THRESHOLD`. Si el fallback custom esta activo, revisa `mlops-custom-data-quality-alarm`; si el schedule nativo fue creado, revisa `mlops-data-quality-alarm`.

Probar Model Quality:

```bash
python -m src.simulate_model_quality_alarm --wait
```

Ese comando publica `MLOps/Lab / ModelQualityF1` bajo el umbral y debe mover `mlops-custom-model-quality-alarm` de `OK` a `ALARM`. Si `mlops-custom-model-quality-alarm` ya esta en `ALARM`, espera a que vuelva a `OK` antes de repetir. Con la configuracion por defecto (`Period=300`, `EvaluationPeriods=1`, `TreatMissingData=notBreaching`), espera entre 5 y 10 minutos despues del ultimo datapoint malo y valida el estado:

```bash
aws cloudwatch describe-alarms \
  --alarm-names mlops-custom-model-quality-alarm \
  --query "MetricAlarms[0].StateValue" \
  --profile <AWS_PROFILE> \
  --region <AWS_REGION>
```

Cuando el resultado sea `"OK"`, vuelve a ejecutar:

```bash
python -m src.simulate_model_quality_alarm --wait
```

## Validacion local

```bash
type artifacts\local_outputs\feedback_loop.json
type artifacts\local_outputs\alarm_notifications.json
type artifacts\local_outputs\eventbridge_rule.json
type artifacts\local_outputs\feedback_loop_execution.json
```

## Validacion en consola AWS

- Lambda > functions con prefijo `mlops-lab`.
- Step Functions > `mlops-feedback-loop`.
- EventBridge > rules > `mlops-lab-alarm-to-feedback-loop`.
- SNS > Topics > `mlops-lab-alarm-notifications`.
- Email inbox de `ALARM_EMAIL` para confirmar la suscripcion.
- Step Functions > execution history.

## Guardrail principal

No hay transicion recursiva en la state machine. Cada ejecucion termina despues de una decision.

## Ficha tecnica del paso

| Script | Responsabilidad | Funciones clave | Lee | Escribe |
|---|---|---|---|---|
| `src.create_feedback_loop` | Empaquetar Lambdas y crear/actualizar Step Functions. | `_zip_lambda`, `_upsert_lambda`, `_render_asl`, `create_feedback_loop`. | `lambdas/*/lambda_function.py`, `stepfunctions/feedback_loop.asl.json`, roles. | `feedback_loop.json`, zips en `artifacts/local_outputs/`, Lambdas y state machine. |
| `src.create_alarm_notifications` | Crear topic SNS y suscripcion email. | `_topic_policy`, `_subscription_exists`, `create_alarm_notifications`. | `ALARM_EMAIL`, cuenta AWS. | `alarm_notifications.json`, SNS topic/subscription. |
| `src.create_eventbridge_rule` | Enrutar alarmas CloudWatch a Step Functions y SNS. | `create_rule`. | `feedback_loop.json`, `alarm_notifications.json`. | `eventbridge_rule.json`, EventBridge rule. |
| `src.trigger_feedback_loop` | Ejecutar state machine manualmente para prueba. | `trigger`. | `feedback_loop.json`. | `feedback_loop_execution.json`. |

Handlers Lambda:

- `lambdas/feedback_handler/lambda_function.py`: decide accion segun violations/severity y flag de retraining.
- `lambdas/retraining_trigger/lambda_function.py`: inicia pipeline si `ENABLE_AUTOMATIC_RETRAINING=true`.
- `lambdas/rollback_handler/lambda_function.py`: placeholder seguro para rollback.
- `lambdas/baseline_update_handler/lambda_function.py`: placeholder seguro para actualizar baseline.
- `lambdas/human_review_handler/lambda_function.py`: ruta de revision humana.

Parametros modificables:

- `ENABLE_AUTOMATIC_RETRAINING`: cambia decision automatica del feedback handler.
- `ALARM_EMAIL`: destino de SNS; requiere confirmacion del correo.
- `ALARM_NAME`: alarma Data Quality nativa, por defecto `mlops-data-quality-alarm`.
- `CUSTOM_DATA_QUALITY_ALARM_NAME`: alarma Data Quality custom, por defecto `mlops-custom-data-quality-alarm`.
- `CUSTOM_BATCH_DATA_QUALITY_ALARM_NAME`: alarma Batch Data Quality custom, por defecto `mlops-custom-batch-data-quality-alarm`.
- `MODEL_QUALITY_ALARM_NAME`: alarma Model Quality nativa.
- `CUSTOM_MODEL_QUALITY_ALARM_NAME`: alarma Model Quality custom.
- `STATE_MACHINE_NAME`, `LAMBDA_EXECUTION_ROLE_ARN`, `STEPFUNCTIONS_ROLE_ARN`, `EVENTBRIDGE_TO_SFN_ROLE_ARN`.

Troubleshooting:

- Si EventBridge no tiene target Step Functions, revisa `EVENTBRIDGE_TO_SFN_ROLE_ARN`.
- Si no llega correo, confirma la suscripcion SNS en el inbox.
- Si `trigger_feedback_loop` falla, revisa `feedback_loop.json` y que la state machine exista.

