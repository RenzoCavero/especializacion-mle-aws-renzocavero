"""Resolve SageMaker compute candidates with Service Quotas when available."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .aws_clients import create_session
from .config import LabConfig, load_config, write_metadata


WORKLOAD_QUOTA_USAGE = {
    "processing": "processing job usage",
    "training": "training job usage",
    "endpoint": "endpoint usage",
    "batch_transform": "transform job usage",
}
WORKLOAD_INSTANCE_SHAPES = {
    "processing": "ProcessingInstanceType",
    "training": "TrainingInstanceType",
    "endpoint": "ProductionVariantInstanceType",
    "batch_transform": "TransformInstanceType",
}
FALLBACK_ALLOWED_INSTANCE_TYPES = {
    "processing": {
        "ml.t3.medium",
        "ml.t3.large",
        "ml.m5.large",
        "ml.m5.xlarge",
        "ml.m6i.large",
        "ml.c6i.xlarge",
        "ml.c5.xlarge",
    },
    "training": {
        "ml.m5.large",
        "ml.m5.xlarge",
        "ml.m6i.large",
        "ml.c6i.xlarge",
        "ml.c5.xlarge",
    },
    "endpoint": {
        "ml.c6i.large",
        "ml.m6i.large",
        "ml.m5.large",
        "ml.m5.xlarge",
        "ml.c5.large",
        "ml.c5.xlarge",
    },
    "batch_transform": {
        "ml.c6i.large",
        "ml.m6i.large",
        "ml.m5.large",
        "ml.m5.xlarge",
        "ml.c6i.xlarge",
        "ml.c5.xlarge",
    },
}
WORKLOAD_ALIASES = {
    "batch": "batch_transform",
    "batch-transform": "batch_transform",
    "batch_transform": "batch_transform",
    "transform": "batch_transform",
}
REQUIRE_POSITIVE_QUOTA_WORKLOADS = {"processing", "training"}


def candidate_env_var(workload: str) -> str:
    workload = normalize_workload(workload)
    return {
        "processing": "PROCESSING_INSTANCE_TYPE_CANDIDATES",
        "training": "TRAINING_INSTANCE_TYPE_CANDIDATES",
        "endpoint": "INSTANCE_TYPE_CANDIDATES",
        "batch_transform": "BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES",
    }.get(workload, "*_INSTANCE_TYPE_CANDIDATES")


def normalize_workload(workload: str) -> str:
    return WORKLOAD_ALIASES.get(workload, workload)


@dataclass(frozen=True)
class ComputeSelection:
    workload: str
    selected_instance_type: str
    candidates: list[str]
    quota_value: float | None
    source: str
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload": self.workload,
            "selected_instance_type": self.selected_instance_type,
            "candidates": self.candidates,
            "quota_value": self.quota_value,
            "source": self.source,
            "notes": self.notes,
        }


def _quota_matches(quota_name: str, workload: str, instance_type: str) -> bool:
    normalized = quota_name.lower()
    usage = WORKLOAD_QUOTA_USAGE[workload]
    return instance_type.lower() in normalized and usage in normalized


def _instance_sort_key(instance_type: str) -> tuple[int, str]:
    # Keep smaller CPU families first for lab cost control, then leave the AWS name as a stable tie breaker.
    family_order = [
        "ml.t3.",
        "ml.m5.",
        "ml.m6i.",
        "ml.m7i.",
        "ml.c5.",
        "ml.c6i.",
        "ml.c7i.",
        "ml.r5.",
        "ml.r7i.",
        "ml.g4dn.",
        "ml.g5.",
        "ml.g6.",
        "ml.g6e.",
        "ml.g7e.",
        "ml.p2.",
        "ml.p3.",
        "ml.p5.",
    ]
    for index, prefix in enumerate(family_order):
        if instance_type.startswith(prefix):
            return index, instance_type
    return len(family_order), instance_type


def _list_sagemaker_quotas(session: Any) -> list[dict[str, Any]]:
    client = session.client("service-quotas")
    quotas: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_service_quotas")
    for page in paginator.paginate(ServiceCode="sagemaker"):
        quotas.extend(page.get("Quotas", []))
    return quotas


def _quota_value(quotas: list[dict[str, Any]], workload: str, instance_type: str) -> float | None:
    for quota in quotas:
        name = quota.get("QuotaName", "")
        if _quota_matches(name, workload, instance_type):
            value = quota.get("Value")
            return float(value) if value is not None else None
    return None


def allowed_instance_types(session: Any | None, workload: str) -> set[str]:
    workload = normalize_workload(workload)
    try:
        if session is None:
            return FALLBACK_ALLOWED_INSTANCE_TYPES[workload]
        sagemaker = session.client("sagemaker")
        shape = sagemaker.meta.service_model.shape_for(WORKLOAD_INSTANCE_SHAPES[workload])
        return set(shape.enum)
    except Exception:
        return FALLBACK_ALLOWED_INSTANCE_TYPES[workload]


def _filter_valid_candidates(candidates: list[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for instance_type in candidates:
        if instance_type in allowed:
            if instance_type not in valid:
                valid.append(instance_type)
        else:
            invalid.append(instance_type)
    return valid, invalid


def _positive_outside_candidates(
    *,
    quotas: list[dict[str, Any]],
    workload: str,
    allowed: set[str],
    configured_candidates: list[str],
) -> list[tuple[str, float]]:
    configured = set(configured_candidates)
    matches: list[tuple[str, float]] = []
    for instance_type in sorted(allowed - configured, key=_instance_sort_key):
        value = _quota_value(quotas, workload, instance_type)
        if value is not None and value > 0:
            matches.append((instance_type, value))
    return matches


def _recent_successful_training_instances(
    session: Any,
    allowed: set[str],
    *,
    max_jobs: int = 50,
    lookback_days: int = 14,
) -> list[dict[str, Any]]:
    """Find recent completed Training Jobs as a second source of evidence.

    Some AWS lab/sandbox accounts report zero or incomplete Service Quotas even
    when recent jobs have completed. This does not guarantee future capacity,
    but it is useful evidence for a teaching lab when Service Quotas is too
    pessimistic.
    """
    client = session.client("sagemaker")
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    response = client.list_training_jobs(
        StatusEquals="Completed",
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=max_jobs,
    )
    evidence: list[dict[str, Any]] = []
    for summary in response.get("TrainingJobSummaries", []):
        job_name = summary.get("TrainingJobName")
        if not job_name:
            continue
        creation_time = summary.get("CreationTime")
        if creation_time and getattr(creation_time, "tzinfo", None) is None:
            creation_time = creation_time.replace(tzinfo=timezone.utc)
        if creation_time and creation_time < cutoff:
            continue
        description = client.describe_training_job(TrainingJobName=job_name)
        instance_type = description.get("ResourceConfig", {}).get("InstanceType")
        if instance_type in allowed:
            evidence.append(
                {
                    "training_job_name": job_name,
                    "instance_type": instance_type,
                    "creation_time": creation_time or description.get("CreationTime"),
                    "training_job_status": description.get("TrainingJobStatus"),
                }
            )
    return evidence


def _select_from_recent_training_evidence(
    *,
    evidence: list[dict[str, Any]],
    valid_candidates: list[str],
) -> dict[str, Any] | None:
    if not evidence:
        return None
    for candidate in valid_candidates:
        for item in evidence:
            if item.get("instance_type") == candidate:
                return item
    return evidence[0]


def select_instance_type(
    config: LabConfig,
    *,
    workload: str,
    preferred: str,
    candidates: list[str],
    session: Any | None = None,
) -> ComputeSelection:
    workload = normalize_workload(workload)
    if workload not in WORKLOAD_QUOTA_USAGE:
        raise ValueError(f"Unsupported SageMaker workload: {workload}")
    if not candidates:
        candidates = [preferred]
    allowed = allowed_instance_types(session, workload)
    valid_candidates, invalid_candidates = _filter_valid_candidates(candidates, allowed)
    if not valid_candidates:
        valid_candidates = [preferred] if preferred else candidates

    if not config.auto_select_compute:
        return ComputeSelection(
            workload=workload,
            selected_instance_type=preferred,
            candidates=valid_candidates,
            quota_value=None,
            source="AUTO_SELECT_COMPUTE=false",
            notes=[
                "Compute auto-selection disabled; using configured instance type.",
                *([f"Invalid candidates ignored for {workload}: {', '.join(invalid_candidates)}"] if invalid_candidates else []),
            ],
        )

    notes: list[str] = []
    if invalid_candidates:
        notes.append(f"Invalid candidates ignored for {workload}: {', '.join(invalid_candidates)}")
    try:
        session = session or create_session(config)
        quotas = _list_sagemaker_quotas(session)
    except Exception as exc:
        selected = valid_candidates[0]
        return ComputeSelection(
            workload=workload,
            selected_instance_type=selected,
            candidates=valid_candidates,
            quota_value=None,
            source="fallback-no-service-quotas",
            notes=[
                *notes,
                "Could not read Service Quotas; using the first configured candidate.",
                f"Service Quotas error: {exc}",
            ],
        )

    inspected: list[str] = []
    unknown_quota_candidates: list[str] = []
    for instance_type in valid_candidates:
        value = _quota_value(quotas, workload, instance_type)
        inspected.append(f"{instance_type}={value if value is not None else 'unknown'}")
        if value is None:
            unknown_quota_candidates.append(instance_type)
            continue
        if value is not None and value > 0:
            return ComputeSelection(
                workload=workload,
                selected_instance_type=instance_type,
                candidates=valid_candidates,
                quota_value=value,
                source="service-quotas",
                notes=[*notes, f"Inspected quotas: {', '.join(inspected)}"],
            )

    outside_positive = _positive_outside_candidates(
        quotas=quotas,
        workload=workload,
        allowed=allowed,
        configured_candidates=valid_candidates,
    )
    if outside_positive:
        selected, value = outside_positive[0]
        notes.append(f"No configured candidate had positive quota. Inspected quotas: {', '.join(inspected)}")
        notes.append(f"Selected {selected} because it has positive quota outside {candidate_env_var(workload)}.")
        notes.append(f"Add {selected} to {candidate_env_var(workload)} if you want this selection to be explicit.")
        return ComputeSelection(
            workload=workload,
            selected_instance_type=selected,
            candidates=[*valid_candidates, selected],
            quota_value=value,
            source="service-quotas-outside-candidates",
            notes=notes,
        )

    if workload == "training":
        try:
            evidence = _recent_successful_training_instances(session, allowed)
        except Exception as exc:
            evidence = []
            notes.append(f"Could not inspect recent completed Training Jobs: {exc}")
        recent_match = _select_from_recent_training_evidence(evidence=evidence, valid_candidates=valid_candidates)
        if recent_match:
            selected = str(recent_match["instance_type"])
            job_name = recent_match.get("training_job_name", "")
            creation_time = recent_match.get("creation_time", "")
            notes.append(
                "Service Quotas did not show positive training quota, but a recent completed "
                f"Training Job used {selected}: {job_name} at {creation_time}."
            )
            notes.append(
                "Using recent job evidence as a best-effort fallback. If SageMaker rejects the job, "
                "request a quota increase for training job usage."
            )
            return ComputeSelection(
                workload=workload,
                selected_instance_type=selected,
                candidates=valid_candidates if selected in valid_candidates else [*valid_candidates, selected],
                quota_value=None,
                source="recent-successful-training-job",
                notes=notes,
            )

    if unknown_quota_candidates:
        if workload in REQUIRE_POSITIVE_QUOTA_WORKLOADS:
            notes.append(
                f"Unknown quota candidates were not selected automatically for {workload}; "
                "required pipeline jobs need a positive quota to avoid late SageMaker failures."
            )
        else:
            selected = unknown_quota_candidates[0]
            notes.append(f"No known positive quota found. Trying valid candidate with unknown quota: {selected}")
            notes.append(f"Inspected quotas: {', '.join(inspected)}")
            return ComputeSelection(
                workload=workload,
                selected_instance_type=selected,
                candidates=valid_candidates,
                quota_value=None,
                source="fallback-unknown-quota",
                notes=notes,
            )

    if unknown_quota_candidates and workload in REQUIRE_POSITIVE_QUOTA_WORKLOADS:
        notes.append(f"Unknown candidates found but not used: {', '.join(unknown_quota_candidates)}")
        notes.append(f"To inspect every SageMaker-supported type for this workload, run: python -m src.compute --workload {workload.replace('_', '-')} --inventory --limit 0")
        notes.append(f"Request a SageMaker quota increase for {WORKLOAD_QUOTA_USAGE[workload]} or update {candidate_env_var(workload)} with a type that has positive quota.")
        return ComputeSelection(
            workload=workload,
            selected_instance_type=valid_candidates[0],
            candidates=valid_candidates,
            quota_value=0.0,
            source="fallback-no-positive-quota",
            notes=notes,
        )

    notes.append(f"No candidate with quota > 0 found. Inspected quotas: {', '.join(inspected)}")
    notes.append("No available quota was found for this workload. Request a quota increase or adjust *_INSTANCE_TYPE_CANDIDATES.")
    notes.append(f"To inspect every SageMaker-supported type for this workload, run: python -m src.compute --workload {workload.replace('_', '-')} --inventory --limit 0")
    return ComputeSelection(
        workload=workload,
        selected_instance_type=valid_candidates[0],
        candidates=valid_candidates,
        quota_value=0.0,
        source="fallback-no-positive-quota",
        notes=notes,
    )


def _configured_candidates_for_workload(config: LabConfig, workload: str) -> tuple[str, list[str]]:
    workload = normalize_workload(workload)
    mapping = {
        "processing": (config.processing_instance_type, config.processing_instance_type_candidates_list),
        "training": (config.training_instance_type, config.training_instance_type_candidates_list),
        "endpoint": (config.instance_type, config.endpoint_instance_type_candidates),
        "batch_transform": (config.instance_type, config.batch_transform_instance_type_candidates_list),
    }
    if workload not in mapping:
        raise ValueError(f"Unsupported SageMaker workload: {workload}")
    return mapping[workload]


def _limit_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return items
    return items[:limit]


def build_quota_inventory(
    config: LabConfig,
    *,
    workload: str,
    session: Any | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Inspect all API-supported instance types for one SageMaker workload."""
    workload = normalize_workload(workload)
    if workload not in WORKLOAD_QUOTA_USAGE:
        raise ValueError(f"Unsupported SageMaker workload: {workload}")

    session = session or create_session(config)
    _, configured_candidates = _configured_candidates_for_workload(config, workload)
    allowed = sorted(allowed_instance_types(session, workload), key=_instance_sort_key)
    quota_error = ""
    try:
        quotas = _list_sagemaker_quotas(session)
    except Exception as exc:
        quotas = []
        quota_error = str(exc)

    configured_set = set(configured_candidates)
    records = [
        {
            "instance_type": instance_type,
            "quota_value": _quota_value(quotas, workload, instance_type),
            "configured_candidate": instance_type in configured_set,
        }
        for instance_type in allowed
    ]
    positive = [record for record in records if (record["quota_value"] or 0) > 0]
    zero = [record for record in records if record["quota_value"] == 0]
    unknown = [record for record in records if record["quota_value"] is None]
    positive_configured = [record for record in positive if record["configured_candidate"]]
    positive_outside_configured = [record for record in positive if not record["configured_candidate"]]
    recent_training_evidence: list[dict[str, Any]] = []
    if workload == "training":
        try:
            recent_training_evidence = _recent_successful_training_instances(session, set(allowed))
        except Exception as exc:
            quota_error = quota_error or f"Could not inspect recent completed Training Jobs: {exc}"

    if positive_configured:
        recommendation = (
            f"Use configured candidate {positive_configured[0]['instance_type']} "
            f"for {workload}; it has quota {positive_configured[0]['quota_value']}."
        )
    elif positive_outside_configured:
        suggested = positive_outside_configured[0]["instance_type"]
        env_var = "BATCH_TRANSFORM_INSTANCE_TYPE_CANDIDATES" if workload == "batch_transform" else "*_INSTANCE_TYPE_CANDIDATES"
        recommendation = f"Add {suggested} to {env_var}; it has positive quota outside the configured candidates."
    elif recent_training_evidence:
        suggested = recent_training_evidence[0]["instance_type"]
        recommendation = (
            f"Service Quotas shows no positive training quota, but recent completed jobs used {suggested}. "
            "You can retry with that instance type as best effort; if it fails, request a training quota increase."
        )
    elif unknown:
        recommendation = (
            "No positive quota was found. Some valid instance types are unknown in Service Quotas; "
            "AWS may still return the authoritative validation when the job is created."
        )
    else:
        recommendation = "No supported instance type shows positive quota. Request a SageMaker quota increase for this workload."

    return {
        "workload": workload,
        "quota_usage_name_fragment": WORKLOAD_QUOTA_USAGE[workload],
        "configured_candidates": configured_candidates,
        "supported_instance_type_count": len(allowed),
        "positive_quota_count": len(positive),
        "zero_quota_count": len(zero),
        "unknown_quota_count": len(unknown),
        "positive_quota_instance_types": _limit_items(positive, limit),
        "positive_quota_outside_configured_candidates": _limit_items(positive_outside_configured, limit),
        "recent_successful_training_jobs": _limit_items(recent_training_evidence, limit) if workload == "training" else [],
        "zero_quota_instance_types": _limit_items(zero, limit),
        "unknown_quota_instance_types": _limit_items(unknown, limit),
        "limit": limit,
        "quota_error": quota_error,
        "recommendation": recommendation,
        "note": "Use --limit 0 to print every item in each inventory section.",
    }


def resolve_lab_compute(config: LabConfig | None = None, session: Any | None = None) -> dict[str, Any]:
    config = config or load_config(validate=False)
    selected = {
        "processing": select_instance_type(
            config,
            workload="processing",
            preferred=config.processing_instance_type,
            candidates=config.processing_instance_type_candidates_list,
            session=session,
        ).to_dict(),
        "training": select_instance_type(
            config,
            workload="training",
            preferred=config.training_instance_type,
            candidates=config.training_instance_type_candidates_list,
            session=session,
        ).to_dict(),
        "endpoint": select_instance_type(
            config,
            workload="endpoint",
            preferred=config.instance_type,
            candidates=config.endpoint_instance_type_candidates,
            session=session,
        ).to_dict(),
        "batch_transform": select_instance_type(
            config,
            workload="batch_transform",
            preferred=config.instance_type,
            candidates=config.batch_transform_instance_type_candidates_list,
            session=session,
        ).to_dict(),
    }
    write_metadata(config, "compute_selection", selected)
    return selected


def resolve_pipeline_compute(config: LabConfig | None = None, session: Any | None = None) -> dict[str, Any]:
    """Resolve only compute needed by the build pipeline."""
    config = config or load_config(validate=False)
    selected = {
        "processing": select_instance_type(
            config,
            workload="processing",
            preferred=config.processing_instance_type,
            candidates=config.processing_instance_type_candidates_list,
            session=session,
        ).to_dict(),
        "training": select_instance_type(
            config,
            workload="training",
            preferred=config.training_instance_type,
            candidates=config.training_instance_type_candidates_list,
            session=session,
        ).to_dict(),
        "endpoint": select_instance_type(
            config,
            workload="endpoint",
            preferred=config.instance_type,
            candidates=config.endpoint_instance_type_candidates,
            session=session,
        ).to_dict(),
    }
    write_metadata(config, "pipeline_compute_selection", selected)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve SageMaker compute candidates using Service Quotas.")
    parser.add_argument(
        "--workload",
        choices=["processing", "training", "endpoint", "batch_transform", "batch-transform", "batch", "transform", "all"],
        default="all",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="List all SageMaker-supported instance types for the workload with Service Quotas values.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum items per inventory section. Use 0 for no limit.",
    )
    args = parser.parse_args()
    workload = normalize_workload(args.workload)
    config = load_config(validate=False)
    session = create_session(config)
    if args.inventory:
        if workload == "all":
            payload = {
                key: build_quota_inventory(config, workload=key, session=session, limit=args.limit)
                for key in WORKLOAD_QUOTA_USAGE
            }
            write_metadata(config, "compute_inventory", payload)
        else:
            payload = build_quota_inventory(config, workload=workload, session=session, limit=args.limit)
            write_metadata(config, f"compute_inventory_{workload}", payload)
    elif workload == "all":
        payload = resolve_lab_compute(config, session)
    else:
        preferred, candidates = _configured_candidates_for_workload(config, workload)
        payload = select_instance_type(
            config,
            workload=workload,
            preferred=preferred,
            candidates=candidates,
            session=session,
        ).to_dict()
        write_metadata(config, f"compute_selection_{workload}", payload)
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
