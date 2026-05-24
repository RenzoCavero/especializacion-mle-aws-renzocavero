"""Generate lightweight local baseline statistics and constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def generate_baseline(input_data: Path, output_dir: Path) -> dict[str, object]:
    frame = pd.read_csv(input_data)
    numeric = frame.select_dtypes(include=["number"])
    categorical = frame.select_dtypes(exclude=["number"])

    statistics = {
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "numeric": {
            col: {
                "mean": float(numeric[col].mean()),
                "std": float(numeric[col].std() or 0.0),
                "min": float(numeric[col].min()),
                "max": float(numeric[col].max()),
            }
            for col in numeric.columns
        },
        "categorical": {
            col: categorical[col].value_counts(dropna=False).to_dict()
            for col in categorical.columns
        },
    }
    constraints = {
        "numeric_ranges": {
            col: {
                "min": float(numeric[col].min()),
                "max": float(numeric[col].max()),
            }
            for col in numeric.columns
        },
        "allowed_values": {
            col: sorted(str(value) for value in categorical[col].dropna().unique())
            for col in categorical.columns
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "statistics.json").write_text(json.dumps(statistics, indent=2) + "\n", encoding="utf-8")
    (output_dir / "constraints.json").write_text(json.dumps(constraints, indent=2) + "\n", encoding="utf-8")
    return {"statistics": statistics, "constraints": constraints}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", default="/opt/ml/processing/baseline/baseline.csv")
    parser.add_argument("--output-dir", default="/opt/ml/processing/output")
    args = parser.parse_args()
    generate_baseline(Path(args.input_data), Path(args.output_dir))


if __name__ == "__main__":
    main()

