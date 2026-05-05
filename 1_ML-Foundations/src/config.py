"""Central configuration for the local AWS ML Foundations lab."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DOCS_DIR = PROJECT_ROOT / "doc"
LAB_DIR = PROJECT_ROOT / "lab"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "model"
METRICS_DIR = ARTIFACTS_DIR / "metrics"
PREDICTIONS_DIR = ARTIFACTS_DIR / "predictions"
GOVERNANCE_DIR = ARTIFACTS_DIR / "governance"

RAW_TRANSACTIONS_PATH = RAW_DATA_DIR / "fraud_transactions.csv"
RAW_BATCH_INPUT_PATH = RAW_DATA_DIR / "batch_scoring_input.csv"
TRAIN_DATA_PATH = PROCESSED_DATA_DIR / "train.csv"
TEST_DATA_PATH = PROCESSED_DATA_DIR / "test.csv"
BATCH_INPUT_PATH = PROCESSED_DATA_DIR / "batch_input.csv"
DATA_PROFILE_PATH = PROCESSED_DATA_DIR / "data_profile.json"
FEATURE_SCHEMA_PATH = PROCESSED_DATA_DIR / "feature_schema.json"

MODEL_PATH = MODEL_DIR / "model.joblib"
MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.json"
TRAINING_METRICS_PATH = METRICS_DIR / "training_metrics.json"
EVALUATION_METRICS_PATH = METRICS_DIR / "evaluation_metrics.json"
EVALUATION_REPORT_PATH = METRICS_DIR / "evaluation_report.md"
BATCH_PREDICTIONS_PATH = PREDICTIONS_DIR / "batch_predictions.csv"
BATCH_SUMMARY_PATH = PREDICTIONS_DIR / "batch_summary.json"
MONITORING_REPORT_PATH = METRICS_DIR / "monitoring_report.json"
MONITORING_MARKDOWN_PATH = METRICS_DIR / "monitoring_report.md"
MONITORING_CHARTS_DIR = METRICS_DIR / "drift_charts"
MODEL_CARD_PATH = GOVERNANCE_DIR / "model_card.md"

MODEL_VERSION = "fraud-risk-local-v1"
RANDOM_SEED = 42
DEFAULT_DATASET_ROWS = 5000
DEFAULT_BATCH_ROWS = 250
TEST_SIZE = 0.25

TARGET_COLUMN = "is_fraud"
ID_COLUMNS = ["transaction_id", "customer_id", "event_timestamp"]

RAW_FEATURE_COLUMNS = [
    "amount",
    "merchant_category",
    "country",
    "channel",
    "device_type",
    "hour",
    "day_of_week",
    "customer_age_days",
    "transactions_last_24h",
    "avg_amount_30d",
    "chargeback_rate_90d",
    "distance_from_home_km",
    "is_foreign_transaction",
    "is_high_risk_merchant",
]

NUMERIC_FEATURES = [
    "amount",
    "hour",
    "day_of_week",
    "customer_age_days",
    "transactions_last_24h",
    "avg_amount_30d",
    "chargeback_rate_90d",
    "distance_from_home_km",
    "is_foreign_transaction",
    "is_high_risk_merchant",
    "amount_log",
    "amount_to_avg_ratio",
    "is_night",
    "velocity_amount_score",
]

CATEGORICAL_FEATURES = [
    "merchant_category",
    "country",
    "channel",
    "device_type",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
REQUIRED_RAW_COLUMNS = ID_COLUMNS + RAW_FEATURE_COLUMNS
REQUIRED_TRAINING_COLUMNS = REQUIRED_RAW_COLUMNS + [TARGET_COLUMN]

DECISION_REVIEW_THRESHOLD = 0.35
DECISION_BLOCK_THRESHOLD = 0.75


def ensure_directories() -> None:
    """Create the directory layout used by the lab."""

    for path in [
        LAB_DIR,
        RAW_DATA_DIR,
        PROCESSED_DATA_DIR,
        MODEL_DIR,
        METRICS_DIR,
        PREDICTIONS_DIR,
        GOVERNANCE_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def require_file(path: Path, hint: str) -> None:
    """Raise a helpful error when an expected file is missing."""

    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}. {hint}")


def project_relative(path: Path) -> str:
    """Return a stable path string relative to the project root when possible."""

    path = Path(path)
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
