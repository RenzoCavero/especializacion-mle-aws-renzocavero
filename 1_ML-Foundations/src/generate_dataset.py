"""Generate a synthetic fraud dataset for the local AWS ML Foundations lab."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.config import (
    DEFAULT_BATCH_ROWS,
    DEFAULT_DATASET_ROWS,
    RAW_BATCH_INPUT_PATH,
    RAW_TRANSACTIONS_PATH,
    RANDOM_SEED,
    TARGET_COLUMN,
    ensure_directories,
    project_relative,
)
from src.modeling import save_json, utc_now_iso


MERCHANT_CATEGORIES = [
    "grocery",
    "electronics",
    "travel",
    "digital_goods",
    "fuel",
    "restaurants",
    "money_transfer",
    "luxury",
]
COUNTRIES = ["PE", "CO", "CL", "MX", "US", "BR"]
CHANNELS = ["pos", "web", "mobile", "api"]
DEVICE_TYPES = ["card_present", "ios", "android", "desktop", "unknown"]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -35, 35)))


def generate_transactions(n_rows: int, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    customer_ids = rng.integers(10000, 99999, size=n_rows)
    base_date = np.datetime64("2026-01-01T00:00:00")
    timestamps = base_date + rng.integers(0, 60 * 24 * 60, size=n_rows).astype("timedelta64[m]")

    merchant_category = rng.choice(
        MERCHANT_CATEGORIES,
        size=n_rows,
        p=[0.23, 0.13, 0.11, 0.13, 0.10, 0.14, 0.08, 0.08],
    )
    country = rng.choice(COUNTRIES, size=n_rows, p=[0.55, 0.09, 0.09, 0.08, 0.12, 0.07])
    channel = rng.choice(CHANNELS, size=n_rows, p=[0.46, 0.22, 0.26, 0.06])
    device_type = rng.choice(DEVICE_TYPES, size=n_rows, p=[0.44, 0.18, 0.20, 0.14, 0.04])

    customer_age_days = rng.integers(10, 2500, size=n_rows)
    avg_amount_30d = rng.lognormal(mean=3.25, sigma=0.55, size=n_rows)
    amount_multiplier = rng.lognormal(mean=0.15, sigma=0.75, size=n_rows)
    amount = np.round(avg_amount_30d * amount_multiplier, 2)
    amount = np.clip(amount, 1.0, 2500.0)

    hour = pd.to_datetime(timestamps.astype(str)).hour.to_numpy()
    day_of_week = pd.to_datetime(timestamps.astype(str)).dayofweek.to_numpy()
    transactions_last_24h = rng.poisson(lam=1.8, size=n_rows)
    burst_mask = rng.random(n_rows) < 0.08
    transactions_last_24h[burst_mask] += rng.integers(4, 15, size=burst_mask.sum())

    chargeback_rate_90d = rng.beta(1.2, 18.0, size=n_rows)
    distance_from_home_km = np.round(rng.exponential(scale=25.0, size=n_rows), 2)
    distance_from_home_km = np.clip(distance_from_home_km, 0.0, 800.0)
    is_foreign_transaction = (country != "PE").astype(int)
    is_high_risk_merchant = np.isin(merchant_category, ["digital_goods", "money_transfer", "luxury"]).astype(int)

    amount_to_avg_ratio = amount / np.maximum(avg_amount_30d, 1.0)
    is_night = ((hour <= 5) | (hour >= 23)).astype(int)
    country_risk = np.select(
        [country == "US", country == "BR", country == "MX", country == "CO"],
        [0.35, 0.32, 0.25, 0.20],
        default=0.0,
    )
    channel_risk = np.select(
        [channel == "api", channel == "web", channel == "mobile"],
        [0.55, 0.25, 0.18],
        default=0.0,
    )
    device_risk = np.select(
        [device_type == "unknown", device_type == "desktop", device_type == "android"],
        [0.65, 0.18, 0.10],
        default=0.0,
    )

    linear_risk = (
        -4.35
        + 0.85 * is_high_risk_merchant
        + 0.58 * is_foreign_transaction
        + 0.42 * is_night
        + 0.30 * np.log1p(transactions_last_24h)
        + 0.55 * (amount_to_avg_ratio > 2.6).astype(float)
        + 0.78 * (distance_from_home_km > 120).astype(float)
        + 5.0 * chargeback_rate_90d
        + country_risk
        + channel_risk
        + device_risk
        + rng.normal(0.0, 0.65, size=n_rows)
    )
    fraud_probability = _sigmoid(linear_risk)
    is_fraud = rng.binomial(1, fraud_probability)

    df = pd.DataFrame(
        {
            "transaction_id": [f"txn_{idx:07d}" for idx in range(1, n_rows + 1)],
            "customer_id": [f"cus_{value}" for value in customer_ids],
            "event_timestamp": pd.to_datetime(timestamps.astype(str)).astype(str),
            "amount": amount,
            "merchant_category": merchant_category,
            "country": country,
            "channel": channel,
            "device_type": device_type,
            "hour": hour,
            "day_of_week": day_of_week,
            "customer_age_days": customer_age_days,
            "transactions_last_24h": transactions_last_24h,
            "avg_amount_30d": np.round(avg_amount_30d, 2),
            "chargeback_rate_90d": np.round(chargeback_rate_90d, 4),
            "distance_from_home_km": distance_from_home_km,
            "is_foreign_transaction": is_foreign_transaction,
            "is_high_risk_merchant": is_high_risk_merchant,
            TARGET_COLUMN: is_fraud.astype(int),
        }
    )
    return df


def generate_dataset(
    output_path=RAW_TRANSACTIONS_PATH,
    batch_output_path=RAW_BATCH_INPUT_PATH,
    n_rows: int = DEFAULT_DATASET_ROWS,
    batch_rows: int = DEFAULT_BATCH_ROWS,
    seed: int = RANDOM_SEED,
) -> dict[str, object]:
    ensure_directories()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    batch_output_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate_transactions(n_rows=n_rows, seed=seed)
    df.to_csv(output_path, index=False)

    # Batch input simulates a future scoring file. Keep labels out of that file.
    batch_df = df.sample(n=min(batch_rows, len(df)), random_state=seed + 7).drop(columns=[TARGET_COLUMN])
    batch_df.to_csv(batch_output_path, index=False)

    metadata = {
        "created_at": utc_now_iso(),
        "rows": int(len(df)),
        "batch_rows": int(len(batch_df)),
        "fraud_rate": float(df[TARGET_COLUMN].mean()),
        "output_path": project_relative(output_path),
        "batch_output_path": project_relative(batch_output_path),
        "seed": int(seed),
        "note": "Synthetic data only; no real customer or transaction data.",
    }
    save_json(output_path.parent / "dataset_metadata.json", metadata)
    print(f"[data] generated {output_path} rows={len(df)} fraud_rate={metadata['fraud_rate']:.4f}")
    print(f"[data] generated {batch_output_path} rows={len(batch_df)}")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud transactions.")
    parser.add_argument("--rows", type=int, default=DEFAULT_DATASET_ROWS)
    parser.add_argument("--batch-rows", type=int, default=DEFAULT_BATCH_ROWS)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_dataset(n_rows=args.rows, batch_rows=args.batch_rows, seed=args.seed)


if __name__ == "__main__":
    main()
