from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.config import get_config
from src.feature_schema import RAW_FEATURE_COLUMNS, validate_records_columns
from src.logging_utils import configure_logging


LOGGER = logging.getLogger(__name__)


def generate_churn_dataset(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    plan_types = np.array(["free", "basic", "pro", "enterprise"])
    countries = np.array(["PE", "CO", "MX", "CL", "US"])
    device_types = np.array(["mobile", "desktop", "tablet"])

    plan = rng.choice(plan_types, rows, p=[0.28, 0.38, 0.26, 0.08])
    country = rng.choice(countries, rows, p=[0.28, 0.22, 0.22, 0.18, 0.10])
    device = rng.choice(device_types, rows, p=[0.62, 0.30, 0.08])

    age_days = rng.integers(15, 1600, rows)
    sessions_30d = rng.poisson(12, rows).clip(0, 80)
    sessions_7d = np.minimum(rng.poisson(np.maximum(sessions_30d / 4, 0.2)), sessions_30d)
    avg_session_duration = rng.gamma(shape=2.2, scale=8.0, size=rows).clip(1, 120)
    support_tickets = rng.poisson(0.5, rows).clip(0, 8)
    payment_failures = rng.poisson(0.25, rows).clip(0, 6)
    days_since_last_login = rng.integers(0, 80, rows)

    engagement_score = (
        0.45 * np.tanh(sessions_30d / 25)
        + 0.25 * np.tanh(avg_session_duration / 40)
        + 0.20 * (1 - np.minimum(days_since_last_login, 60) / 60)
        + 0.10 * (plan != "free").astype(float)
    ).clip(0, 1)

    risk = (
        -2.1
        + 0.055 * days_since_last_login
        + 0.45 * support_tickets
        + 0.65 * payment_failures
        - 1.8 * engagement_score
        - 0.035 * sessions_7d
        + 0.45 * (plan == "free").astype(float)
        + 0.20 * (device == "mobile").astype(float)
    )
    churn_probability = 1 / (1 + np.exp(-risk))
    churn_label = rng.binomial(1, churn_probability)

    event_times = [
        (now - timedelta(minutes=int(offset))).isoformat()
        for offset in rng.integers(1, 60 * 24 * 14, rows)
    ]

    df = pd.DataFrame(
        {
            "customer_id": [f"CUST-{idx:06d}" for idx in range(1, rows + 1)],
            "event_time": event_times,
            "age_days": age_days.astype(int),
            "plan_type": plan,
            "country": country,
            "device_type": device,
            "sessions_last_7d": sessions_7d.astype(int),
            "sessions_last_30d": sessions_30d.astype(int),
            "avg_session_duration_last_30d": avg_session_duration.round(3),
            "support_tickets_last_30d": support_tickets.astype(int),
            "payment_failures_last_90d": payment_failures.astype(int),
            "days_since_last_login": days_since_last_login.astype(int),
            "engagement_score": engagement_score.round(4),
            "churn_label": churn_label.astype(int),
        }
    )
    validate_records_columns(list(df.columns))
    return df.loc[:, list(RAW_FEATURE_COLUMNS)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a small synthetic churn dataset.")
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    configure_logging()
    config = get_config()
    config.raw_data_local_path.parent.mkdir(parents=True, exist_ok=True)
    config.sample_data_local_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate_churn_dataset(rows=args.rows, seed=args.seed)
    df.to_csv(config.raw_data_local_path, index=False)
    df.head(25).to_csv(config.sample_data_local_path, index=False)

    churn_rate = float(df["churn_label"].mean())
    LOGGER.info("Generated %s rows at %s", len(df), config.raw_data_local_path)
    LOGGER.info("Sample saved at %s", config.sample_data_local_path)
    LOGGER.info("Synthetic churn rate: %.3f", churn_rate)


if __name__ == "__main__":
    main()
