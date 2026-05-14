from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, "/opt/ml/processing/lib")

from utils import ensure_dir, prepare_model_frame, write_json


def find_input_file(input_path: Path) -> Path:
    if input_path.is_file():
        return input_path
    candidates = sorted(input_path.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV input found under {input_path}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare train/validation/test datasets from churn features.")
    parser.add_argument("--input-data", default="/opt/ml/processing/input")
    parser.add_argument("--train-output", default="/opt/ml/processing/output/train")
    parser.add_argument("--validation-output", default="/opt/ml/processing/output/validation")
    parser.add_argument("--test-output", default="/opt/ml/processing/output/test")
    parser.add_argument("--metadata-output", default="/opt/ml/processing/output/metadata")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--validation-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    input_file = find_input_file(Path(args.input_data))
    df = pd.read_csv(input_file)
    model_df, metadata = prepare_model_frame(df)

    train_validation, test = train_test_split(
        model_df,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=model_df["churn_label"],
    )
    relative_validation_size = args.validation_size / (1.0 - args.test_size)
    train, validation = train_test_split(
        train_validation,
        test_size=relative_validation_size,
        random_state=args.seed,
        stratify=train_validation["churn_label"],
    )

    train_dir = ensure_dir(args.train_output)
    validation_dir = ensure_dir(args.validation_output)
    test_dir = ensure_dir(args.test_output)
    metadata_dir = ensure_dir(args.metadata_output)

    train.to_csv(train_dir / "train.csv", index=False)
    validation.to_csv(validation_dir / "validation.csv", index=False)
    test.to_csv(test_dir / "test.csv", index=False)

    metadata.update(
        {
            "input_rows": int(len(df)),
            "train_rows": int(len(train)),
            "validation_rows": int(len(validation)),
            "test_rows": int(len(test)),
            "source": "SageMaker Feature Store export snapshot / Offline Store-compatible feature dataset",
        }
    )
    write_json(metadata, metadata_dir / "preprocessing_metadata.json")
    print(f"Prepared train={len(train)} validation={len(validation)} test={len(test)}")


if __name__ == "__main__":
    main()
