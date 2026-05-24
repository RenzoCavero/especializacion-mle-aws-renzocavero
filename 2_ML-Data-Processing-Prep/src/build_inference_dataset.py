"""Build inference dataset with the same feature contract as training."""

from __future__ import annotations

import pandas as pd

from src.schemas import INFERENCE_COLUMNS


def build_inference_dataset(inference_features: pd.DataFrame) -> pd.DataFrame:
    return inference_features[INFERENCE_COLUMNS].reset_index(drop=True)

