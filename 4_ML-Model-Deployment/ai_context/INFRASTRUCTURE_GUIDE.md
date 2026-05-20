# Infrastructure Guide

Este documento define la infraestructura esperada para el laboratorio 4.

## Herramienta IaC recomendada

Usar CloudFormation o AWS CDK. Para un repositorio educativo, CloudFormation puede ser mas explicito; CDK puede ser una extension si se busca codigo tipado.

La estructura inicial reserva `infra/cloudformation/` para plantillas.

## Recursos minimos

- Bucket S3 o prefijos dentro de un bucket existente.
- SageMaker Execution Role.
- SageMaker Model.
- SageMaker Batch Transform Job.
- SageMaker Endpoint Configuration.
- SageMaker Real-Time Endpoint.
- Configuracion de data capture.
- Politicas para CloudWatch Logs y metricas.
- Application Auto Scaling si `ENABLE_AUTOSCALING=true`.
- KMS opcional para cifrado administrado.

## Parametros configurables

- `project_name`: `ml-model-deployment`
- `environment`: `lab`
- `resource_prefix`: `ml-deploy-lab`
- `batch_job_prefix`: `ml-deploy-batch`
- `endpoint_name`: `ml-deploy-realtime-endpoint`
- `endpoint_config_name`: `ml-deploy-realtime-config`
- `model_name`: `ml-deploy-model`
- `instance_type`
- `batch_instance_type`
- `batch_instance_count`
- `s3_bucket_name`
- `enable_data_capture`
- `enable_autoscaling`

## Tags

| Key | Value |
|---|---|
| Project | MLModelDeployment |
| Environment | Lab |
| Owner | LabUser |
| ManagedBy | IaC |
| CostCenter | Training |
| AutoDelete | true |

## Roles IAM

El SageMaker Execution Role debe tener permisos minimos para:

- Leer artefactos del modelo en S3.
- Leer batch input desde S3.
- Escribir batch output en S3.
- Escribir data capture en S3.
- Escribir logs en CloudWatch.
- Acceder a ECR si se usa imagen propia o imagen de framework.
- Consultar Model Registry si se usa `integrated_mode`.
- Consultar Feature Store si esta habilitado.

## Politicas minimas por capacidad

### S3 bucket

- `s3:GetObject`
- `s3:PutObject`
- `s3:ListBucket`
- `s3:DeleteObject` solo para prefijos creados por el laboratorio.

### Model Registry

- `sagemaker:DescribeModelPackage`
- `sagemaker:ListModelPackages`
- `sagemaker:DescribeModelPackageGroup`

### Batch Transform

- `sagemaker:CreateTransformJob`
- `sagemaker:DescribeTransformJob`
- `sagemaker:StopTransformJob`

### Real-Time Endpoint

- `sagemaker:CreateModel`
- `sagemaker:DescribeModel`
- `sagemaker:DeleteModel`
- `sagemaker:CreateEndpointConfig`
- `sagemaker:DescribeEndpointConfig`
- `sagemaker:DeleteEndpointConfig`
- `sagemaker:CreateEndpoint`
- `sagemaker:DescribeEndpoint`
- `sagemaker:UpdateEndpoint`
- `sagemaker:DeleteEndpoint`
- `sagemaker:InvokeEndpoint`

### Feature Store

- `sagemaker:CreateFeatureGroup`
- `sagemaker:DescribeFeatureGroup`
- `sagemaker:DeleteFeatureGroup`
- `sagemaker:PutRecord`
- `sagemaker:GetRecord`
- `sagemaker:BatchGetRecord`

### CloudWatch

- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`
- `cloudwatch:GetMetricData`
- `cloudwatch:ListMetrics`

### Application Auto Scaling

- `application-autoscaling:RegisterScalableTarget`
- `application-autoscaling:PutScalingPolicy`
- `application-autoscaling:DescribeScalableTargets`
- `application-autoscaling:DescribeScalingPolicies`
- `application-autoscaling:DeregisterScalableTarget`
- `application-autoscaling:DeleteScalingPolicy`

## KMS opcional

Si se usa KMS, el rol debe poder usar la key para cifrar y descifrar objetos S3 y volumenes asociados a SageMaker. Para el laboratorio, SSE-S3 puede ser suficiente si no se requiere una key administrada por el cliente.

## Cleanup obligatorio

- Eliminar endpoint.
- Eliminar endpoint config.
- Eliminar SageMaker Model creado por el laboratorio.
- Eliminar batch transform jobs solo si aplica.
- Eliminar objetos S3 creados por el laboratorio si corresponde.
- No eliminar Model Package externo.
- No eliminar Feature Group externo.
- No eliminar recursos de laboratorios anteriores por defecto.

## Convenciones de nombres

- `project_name`: `ml-model-deployment`
- `environment`: `lab`
- `resource_prefix`: `ml-deploy-lab`
- `batch_job_prefix`: `ml-deploy-batch`
- `endpoint_name`: `ml-deploy-realtime-endpoint`
- `endpoint_config_name`: `ml-deploy-realtime-config`
- `model_name`: `ml-deploy-model`
