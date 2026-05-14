from __future__ import annotations

from pathlib import Path

import pandas as pd


TARGET_COLUMN = "churn_label"


def find_channel_csv(channel_dir: str | Path) -> Path:
    path = Path(channel_dir)
    candidates = sorted(path.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV files found in channel {path}")
    return candidates[0]


def load_supervised_dataset(channel_dir: str | Path):
    csv_path = find_channel_csv(channel_dir)
    df = pd.read_csv(csv_path)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Dataset {csv_path} does not contain {TARGET_COLUMN}")
    X = df.drop(columns=[TARGET_COLUMN])
    y = df[TARGET_COLUMN].astype(int)
    return X, y
