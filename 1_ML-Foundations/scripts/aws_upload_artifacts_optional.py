"""Optional artifact upload helper.

This script is intentionally safe by default. It performs a dry run unless
`--execute` is provided. It is not used by the base lab and requires no AWS
account for normal execution.
"""

from __future__ import annotations

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def iter_artifacts() -> list[Path]:
    if not ARTIFACTS_DIR.exists():
        return []
    return [path for path in ARTIFACTS_DIR.rglob("*") if path.is_file()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optionally upload artifacts to S3.")
    parser.add_argument("--bucket", default="", help="Target S3 bucket name.")
    parser.add_argument("--prefix", default="aws-ml-foundations/lab-01", help="S3 prefix.")
    parser.add_argument("--execute", action="store_true", help="Actually upload files. Default is dry run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = iter_artifacts()
    if not artifacts:
        print("No artifacts found. Run the lab pipeline first.")
        return

    if not args.execute:
        print("Dry run only. No AWS calls will be made.")
        for artifact in artifacts:
            relative = artifact.relative_to(PROJECT_ROOT).as_posix()
            target = f"s3://{args.bucket or '<bucket>'}/{args.prefix}/{relative}"
            print(f"Would upload {relative} -> {target}")
        print("Pass --execute and --bucket only when you intentionally want AWS upload.")
        return

    if not args.bucket:
        raise SystemExit("--bucket is required when --execute is used.")

    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise SystemExit("boto3 is not installed. Install it only for optional AWS upload.") from exc

    s3 = boto3.client("s3")
    for artifact in artifacts:
        relative = artifact.relative_to(PROJECT_ROOT).as_posix()
        key = f"{args.prefix}/{relative}"
        s3.upload_file(str(artifact), args.bucket, key)
        print(f"Uploaded {relative} -> s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()

