"""Train a simple churn classifier for the standalone MLOps lab."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


LABEL_COLUMN = "churned"


def train(train_data: Path, model_dir: Path, n_estimators: int = 120) -> Path:
    frame = pd.read_csv(train_data)
    y = frame[LABEL_COLUMN]
    x = frame.drop(columns=[LABEL_COLUMN])
    categorical = list(x.select_dtypes(include=["object", "category"]).columns)
    numeric = [col for col in x.columns if col not in categorical and col != "record_id"]
    passthrough = ["record_id"] if "record_id" in x.columns else []

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("drop_ids", "drop", passthrough),
        ],
        remainder="drop",
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=max(500, n_estimators * 5),
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(x, y)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "model.joblib"
    joblib.dump(model, model_path)
    return model_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-data", default="/opt/ml/input/data/train/train.csv")
    parser.add_argument("--model-dir", default="/opt/ml/model")
    parser.add_argument("--n-estimators", type=int, default=120)
    args = parser.parse_args()
    path = train(Path(args.train_data), Path(args.model_dir), n_estimators=args.n_estimators)
    print(f"Saved model to {path}")


if __name__ == "__main__":
    main()
