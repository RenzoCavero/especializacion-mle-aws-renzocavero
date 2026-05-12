"""Generate synthetic fraud-risk datasets for the lab."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

import pandas as pd

from src.config import SAMPLE_DATA_DIR, ensure_local_directories
from src.schemas import CUSTOMER_COLUMNS, INFERENCE_TRANSACTION_COLUMNS, TRANSACTION_COLUMNS


SEGMENTS = ["retail", "smb", "premium"]
REGIONS = ["lima", "arequipa", "cusco", "trujillo"]
INCOME_BANDS = ["low", "medium", "high"]
MERCHANTS = ["grocery", "fuel", "electronics", "travel", "utilities"]
CHANNELS = ["card_present", "online", "mobile", "atm", "wire"]
COUNTRIES = ["PE", "CO", "CL", "US", "BR"]
HIGH_RISK_COUNTRIES = {"US", "BR"}
DEVICES = ["ios", "android", "web", "pos", "atm"]


def _customer_id(index: int) -> str:
    return f"C{index:05d}"


def _transaction_id(prefix: str, index: int) -> str:
    return f"{prefix}{index:06d}"


def _fraud_label(amount: float, channel: str, country: str, risk_score: float, hour: int) -> int:
    score = 0.0
    score += 0.35 if amount > 420 else 0.0
    score += 0.25 if channel in {"online", "wire"} else 0.0
    score += 0.20 if country in HIGH_RISK_COUNTRIES else 0.0
    score += 0.25 if risk_score > 0.72 else 0.0
    score += 0.15 if hour < 5 else 0.0
    score += random.random() * 0.30
    return int(score > 0.58)


def build_synthetic_data(
    customers_count: int = 80,
    transactions_count: int = 600,
    inference_count: int = 120,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    random.seed(seed)
    base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    customers = []
    for i in range(1, customers_count + 1):
        signup = base_date - timedelta(days=random.randint(30, 1500))
        risk = round(random.uniform(0.05, 0.95), 4)
        customers.append(
            {
                "customer_id": _customer_id(i),
                "signup_date": signup.date().isoformat(),
                "segment": random.choice(SEGMENTS),
                "region": random.choice(REGIONS),
                "age": random.randint(18, 75),
                "income_band": random.choice(INCOME_BANDS),
                "risk_score_seed": risk,
            }
        )

    customers_df = pd.DataFrame(customers, columns=CUSTOMER_COLUMNS)
    if len(customers_df) > 5:
        customers_df.loc[3, "region"] = None

    customer_lookup = customers_df.set_index("customer_id")["risk_score_seed"].to_dict()

    transactions = []
    for i in range(1, transactions_count + 1):
        customer_id = _customer_id(random.randint(1, customers_count))
        event_time = base_date + timedelta(days=random.randint(0, 89), hours=random.randint(0, 23))
        amount = round(max(1.0, random.lognormvariate(4.2, 0.75)), 2)
        if random.random() < 0.04:
            amount = round(amount * random.uniform(5, 12), 2)
        channel = random.choice(CHANNELS)
        country = random.choice(COUNTRIES)
        risk = float(customer_lookup[customer_id])
        transactions.append(
            {
                "transaction_id": _transaction_id("T", i),
                "customer_id": customer_id,
                "event_time": event_time.isoformat(),
                "amount": amount,
                "merchant_category": random.choice(MERCHANTS),
                "channel": channel,
                "country": country,
                "device_type": random.choice(DEVICES),
                "is_fraud": _fraud_label(amount, channel, country, risk, event_time.hour),
            }
        )

    transactions_df = pd.DataFrame(transactions, columns=TRANSACTION_COLUMNS)
    if len(transactions_df) > 12:
        transactions_df.loc[1, "amount"] = None
        transactions_df.loc[2, "amount"] = -25.0
        transactions_df.loc[4, "customer_id"] = "C99999"
        transactions_df.loc[6, "country"] = None
        transactions_df = pd.concat([transactions_df, transactions_df.iloc[[0]]], ignore_index=True)

    inference_rows = []
    for i in range(1, inference_count + 1):
        customer_id = _customer_id(random.randint(1, customers_count))
        event_time = base_date + timedelta(days=100 + random.randint(0, 14), hours=random.randint(0, 23))
        amount = round(max(1.0, random.lognormvariate(4.0, 0.8)), 2)
        inference_rows.append(
            {
                "transaction_id": _transaction_id("I", i),
                "customer_id": customer_id,
                "event_time": event_time.isoformat(),
                "amount": amount,
                "merchant_category": random.choice(MERCHANTS),
                "channel": random.choice(CHANNELS),
                "country": random.choice(COUNTRIES),
                "device_type": random.choice(DEVICES),
            }
        )

    inference_df = pd.DataFrame(inference_rows, columns=INFERENCE_TRANSACTION_COLUMNS)
    if len(inference_df) > 8:
        inference_df.loc[5, "amount"] = None
        inference_df.loc[7, "country"] = None

    return customers_df, transactions_df, inference_df


def write_sample_data(output_dir: Path = SAMPLE_DATA_DIR, seed: int = 42) -> None:
    ensure_local_directories()
    output_dir.mkdir(parents=True, exist_ok=True)
    customers, transactions, inference = build_synthetic_data(seed=seed)
    customers.to_csv(output_dir / "customers.csv", index=False)
    transactions.to_csv(output_dir / "transactions.csv", index=False)
    inference.to_csv(output_dir / "inference_transactions.csv", index=False)
    print(f"Synthetic data written to {output_dir}")
    print(f"customers={len(customers)} transactions={len(transactions)} inference={len(inference)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud-risk sample data.")
    parser.add_argument("--output-dir", type=Path, default=SAMPLE_DATA_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    write_sample_data(args.output_dir, args.seed)


if __name__ == "__main__":
    main()
