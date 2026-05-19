from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import boto3
import pandas as pd

sys.path.insert(0, "/opt/ml/processing/code")

from src.feature_pipeline import curate_feature_frame, feature_lineage_document, row_to_feature_record
from src.state import save_state


def find_input_file(input_path: Path) -> Path:
    if input_path.is_file():
        return input_path
    candidates = sorted(input_path.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV input found under {input_path}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest curated churn features into SageMaker Feature Store.")
    parser.add_argument("--input-data", default="/opt/ml/processing/curated")
    parser.add_argument("--feature-group-name", required=True)
    parser.add_argument("--aws-region", default="us-east-1")
    parser.add_argument("--source-raw-s3-uri", required=True)
    parser.add_argument("--source-cleaned-s3-uri", required=True)
    parser.add_argument("--source-curated-s3-uri", required=True)
    parser.add_argument("--metadata-output", default="/opt/ml/processing/output/metadata")
    parser.add_argument("--sleep-every", type=int, default=250)
    args = parser.parse_args()

    input_file = find_input_file(Path(args.input_data))
    raw_curated = pd.read_csv(input_file)
    curated, transformations = curate_feature_frame(raw_curated)

    runtime = boto3.client("sagemaker-featurestore-runtime", region_name=args.aws_region)
    for index, row in curated.iterrows():
        runtime.put_record(
            FeatureGroupName=args.feature_group_name,
            Record=row_to_feature_record(row),
        )
        if args.sleep_every and (index + 1) % args.sleep_every == 0:
            print(f"Ingested {index + 1} curated feature records")
            time.sleep(0.2)

    metadata_dir = Path(args.metadata_output)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    lineage = feature_lineage_document(
        raw_s3_uri=args.source_raw_s3_uri,
        cleaned_s3_uri=args.source_cleaned_s3_uri,
        curated_s3_uri=args.source_curated_s3_uri,
        feature_group_name=args.feature_group_name,
        transformations=transformations,
        row_counts={"curated_input": int(len(raw_curated)), "ingested": int(len(curated))},
        producer="processing/feature_ingestion_entrypoint.py",
    )
    save_state(lineage, metadata_dir / "feature_ingestion_lineage.json")
    save_state(
        {
            "feature_group_name": args.feature_group_name,
            "source_curated_s3_uri": args.source_curated_s3_uri,
            "ingested_records": int(len(curated)),
            "metadata_file": "feature_ingestion_lineage.json",
        },
        metadata_dir / "feature_ingestion_metadata.json",
    )
    print(f"Ingested {len(curated)} curated feature records into {args.feature_group_name}")


if __name__ == "__main__":
    main()
