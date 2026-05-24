"""Preprocess churn data for SageMaker Processing."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


LABEL_COLUMN = "churned"


def preprocess(input_data: Path, train_output: Path, test_output: Path, baseline_output: Path) -> None:
    frame = pd.read_csv(input_data)
    if LABEL_COLUMN not in frame.columns:
        raise ValueError(f"Input data must include label column '{LABEL_COLUMN}'.")

    train, test = train_test_split(frame, test_size=0.25, random_state=42, stratify=frame[LABEL_COLUMN])

    train_output.parent.mkdir(parents=True, exist_ok=True)
    test_output.parent.mkdir(parents=True, exist_ok=True)
    baseline_output.parent.mkdir(parents=True, exist_ok=True)

    train.to_csv(train_output, index=False)
    test.to_csv(test_output, index=False)
    frame.drop(columns=[LABEL_COLUMN]).sample(min(300, len(frame)), random_state=42).to_csv(baseline_output, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", default="/opt/ml/processing/input/churn_train.csv")
    parser.add_argument("--train-output", default="/opt/ml/processing/train/train.csv")
    parser.add_argument("--test-output", default="/opt/ml/processing/test/test.csv")
    parser.add_argument("--baseline-output", default="/opt/ml/processing/baseline/baseline.csv")
    args = parser.parse_args()
    preprocess(Path(args.input_data), Path(args.train_output), Path(args.test_output), Path(args.baseline_output))


if __name__ == "__main__":
    main()

