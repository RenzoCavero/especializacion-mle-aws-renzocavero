"""Shared schemas for the AWS ML data preparation lab."""

CUSTOMER_COLUMNS = [
    "customer_id",
    "signup_date",
    "segment",
    "region",
    "age",
    "income_band",
    "risk_score_seed",
]

TRANSACTION_COLUMNS = [
    "transaction_id",
    "customer_id",
    "event_time",
    "amount",
    "merchant_category",
    "channel",
    "country",
    "device_type",
    "is_fraud",
]

INFERENCE_TRANSACTION_COLUMNS = [
    "transaction_id",
    "customer_id",
    "event_time",
    "amount",
    "merchant_category",
    "channel",
    "country",
    "device_type",
]

CURATED_COLUMNS = [
    "transaction_id",
    "customer_id",
    "event_time",
    "amount",
    "merchant_category",
    "channel",
    "country",
    "device_type",
    "signup_date",
    "segment",
    "region",
    "age",
    "income_band",
    "risk_score_seed",
    "customer_tenure_days",
    "event_hour",
    "event_dayofweek",
    "is_weekend",
    "is_night",
    "amount_log",
]

TARGET_COLUMN = "is_fraud"

FEATURE_COLUMNS = [
    "amount",
    "amount_log",
    "age",
    "risk_score_seed",
    "customer_tenure_days",
    "event_hour",
    "event_dayofweek",
    "is_weekend",
    "is_night",
    "customer_txn_count",
    "customer_avg_amount",
    "customer_max_amount",
    "amount_to_customer_avg",
    "high_risk_country",
    "channel_atm",
    "channel_card_present",
    "channel_mobile",
    "channel_online",
    "channel_wire",
    "segment_premium",
    "segment_retail",
    "segment_smb",
    "merchant_electronics",
    "merchant_fuel",
    "merchant_grocery",
    "merchant_travel",
    "merchant_utilities",
]

TRAINING_COLUMNS = ["transaction_id", "customer_id"] + FEATURE_COLUMNS + [TARGET_COLUMN, "split"]
INFERENCE_COLUMNS = ["transaction_id", "customer_id"] + FEATURE_COLUMNS

S3_ZONES = [
    "raw",
    "cleaned",
    "curated",
    "features",
    "inference",
    "profiles",
    "quality",
    "lineage",
    "reports",
    "logs",
    "scripts",
]

