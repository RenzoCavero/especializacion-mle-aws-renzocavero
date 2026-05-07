"""Lineage report generation."""

from __future__ import annotations

from typing import Dict, List

from src.data_utils import utc_now_iso


def build_lineage(bucket_name: str, glue_database: str, resource_prefix: str) -> Dict[str, object]:
    stages: List[Dict[str, object]] = [
        {
            "stage": "raw",
            "inputs": ["data/sample/customers.csv", "data/sample/transactions.csv", "data/sample/inference_transactions.csv"],
            "outputs": [f"s3://{bucket_name}/raw/"],
            "aws_services": ["Amazon S3"],
        },
        {
            "stage": "catalog",
            "inputs": [f"s3://{bucket_name}/raw/"],
            "outputs": [f"AWS Glue Data Catalog database {glue_database}"],
            "aws_services": ["AWS Glue Data Catalog"],
        },
        {
            "stage": "profile_quality",
            "inputs": [f"s3://{bucket_name}/raw/"],
            "outputs": [f"s3://{bucket_name}/profiles/", f"s3://{bucket_name}/quality/"],
            "aws_services": ["AWS Glue Job", "Amazon S3", "CloudWatch Logs"],
        },
        {
            "stage": "clean_curate",
            "inputs": [f"s3://{bucket_name}/raw/"],
            "outputs": [f"s3://{bucket_name}/cleaned/", f"s3://{bucket_name}/curated/"],
            "aws_services": ["AWS Glue Job", "Amazon S3"],
        },
        {
            "stage": "features",
            "inputs": [f"s3://{bucket_name}/curated/"],
            "outputs": [f"s3://{bucket_name}/features/", f"s3://{bucket_name}/inference/"],
            "aws_services": ["AWS Glue Job", "Amazon S3"],
        },
        {
            "stage": "governance",
            "inputs": [f"s3://{bucket_name}/profiles/", f"s3://{bucket_name}/quality/", f"s3://{bucket_name}/features/"],
            "outputs": [f"s3://{bucket_name}/lineage/", f"s3://{bucket_name}/reports/"],
            "aws_services": ["Amazon S3", "AWS Glue Data Catalog"],
        },
    ]
    return {
        "generated_at": utc_now_iso(),
        "project": resource_prefix,
        "business_case": "fraud_detection_or_risk_scoring",
        "feature_consistency": "Training and inference datasets use src.feature_engineering.build_feature_frame.",
        "stages": stages,
    }


def lineage_to_markdown(lineage: Dict[str, object]) -> str:
    lines = [
        "# Lineage Report",
        "",
        f"Generated at: `{lineage['generated_at']}`",
        "",
        f"Project: `{lineage['project']}`",
        "",
        "## Stages",
        "",
    ]
    for stage in lineage["stages"]:  # type: ignore[index]
        lines.extend(
            [
                f"### {stage['stage']}",
                "",
                f"- Inputs: {', '.join(stage['inputs'])}",
                f"- Outputs: {', '.join(stage['outputs'])}",
                f"- AWS services: {', '.join(stage['aws_services'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## Training-Serving Consistency",
            "",
            str(lineage["feature_consistency"]),
            "",
        ]
    )
    return "\n".join(lines)

