from __future__ import annotations

import argparse

from .aws_clients import client_error_code, clients
from .config import load_config, utc_now, write_json


def configure_autoscaling() -> dict[str, object]:
    config = load_config(require_aws=True)
    if not config.enable_autoscaling:
        metadata = {"enabled": False, "reason": "ENABLE_AUTOSCALING=false", "updated_at": utc_now()}
        write_json(config.metadata_path("autoscaling.json"), metadata)
        print("Autoscaling deshabilitado por configuracion.")
        return metadata

    aas = clients(config).application_autoscaling
    resource_id = f"endpoint/{config.endpoint_name}/variant/AllTraffic"
    policy_name = f"{config.endpoint_name}-invocations-policy"[:128]
    aas.register_scalable_target(
        ServiceNamespace="sagemaker",
        ResourceId=resource_id,
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
        MinCapacity=config.autoscaling_min_capacity,
        MaxCapacity=config.autoscaling_max_capacity,
    )
    response = aas.put_scaling_policy(
        PolicyName=policy_name,
        ServiceNamespace="sagemaker",
        ResourceId=resource_id,
        ScalableDimension="sagemaker:variant:DesiredInstanceCount",
        PolicyType="TargetTrackingScaling",
        TargetTrackingScalingPolicyConfiguration={
            "TargetValue": config.autoscaling_target_invocations_per_instance,
            "PredefinedMetricSpecification": {
                "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
            },
            "ScaleInCooldown": 300,
            "ScaleOutCooldown": 120,
        },
    )
    metadata = {
        "enabled": True,
        "resource_id": resource_id,
        "policy_name": policy_name,
        "policy_arn": response.get("PolicyARN"),
        "min_capacity": config.autoscaling_min_capacity,
        "max_capacity": config.autoscaling_max_capacity,
        "target_invocations_per_instance": config.autoscaling_target_invocations_per_instance,
        "updated_at": utc_now(),
    }
    write_json(config.metadata_path("autoscaling.json"), metadata)
    print(f"Autoscaling configurado para {resource_id}")
    return metadata


def main() -> None:
    argparse.ArgumentParser(description="Configurar Application Auto Scaling.").parse_args()
    try:
        configure_autoscaling()
    except Exception as exc:
        if client_error_code(exc) in {"AccessDenied", "AccessDeniedException"}:
            raise SystemExit("Permisos insuficientes para configurar autoscaling.") from exc
        raise


if __name__ == "__main__":
    main()
