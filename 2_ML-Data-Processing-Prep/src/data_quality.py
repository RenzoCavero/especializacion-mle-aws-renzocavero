"""Data quality checks for the lab pipeline."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.data_utils import json_safe, require_columns, utc_now_iso
from src.schemas import CUSTOMER_COLUMNS, INFERENCE_TRANSACTION_COLUMNS, TRANSACTION_COLUMNS


def _rule(name: str, passed: bool, severity: str, details: Dict[str, object]) -> Dict[str, object]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "severity": severity,
        "details": details,
    }


def validate_raw_data(
    customers: pd.DataFrame,
    transactions: pd.DataFrame,
    inference_transactions: pd.DataFrame,
) -> Dict[str, object]:
    rules: List[Dict[str, object]] = []

    for dataset_name, df, columns in [
        ("customers", customers, CUSTOMER_COLUMNS),
        ("transactions", transactions, TRANSACTION_COLUMNS),
        ("inference_transactions", inference_transactions, INFERENCE_TRANSACTION_COLUMNS),
    ]:
        missing = [column for column in columns if column not in df.columns]
        rules.append(
            _rule(
                f"{dataset_name}_has_expected_columns",
                not missing,
                "ERROR",
                {"missing_columns": missing},
            )
        )

    require_columns(customers, CUSTOMER_COLUMNS, "customers")
    require_columns(transactions, TRANSACTION_COLUMNS, "transactions")
    require_columns(inference_transactions, INFERENCE_TRANSACTION_COLUMNS, "inference_transactions")

    duplicate_transactions = int(transactions["transaction_id"].duplicated().sum())
    duplicate_inference = int(inference_transactions["transaction_id"].duplicated().sum())
    invalid_amounts = int((pd.to_numeric(transactions["amount"], errors="coerce") <= 0).fillna(False).sum())
    missing_amounts = int(transactions["amount"].isna().sum())
    missing_customers = int(transactions["customer_id"].isna().sum())
    unknown_customers = int((~transactions["customer_id"].isin(customers["customer_id"])).sum())
    inference_has_target = "is_fraud" in inference_transactions.columns

    rules.extend(
        [
            _rule(
                "transaction_ids_are_unique",
                duplicate_transactions == 0,
                "WARN",
                {"duplicate_transaction_ids": duplicate_transactions},
            ),
            _rule(
                "inference_transaction_ids_are_unique",
                duplicate_inference == 0,
                "ERROR",
                {"duplicate_inference_transaction_ids": duplicate_inference},
            ),
            _rule(
                "transaction_amounts_are_positive",
                invalid_amounts == 0,
                "WARN",
                {"invalid_amounts": invalid_amounts},
            ),
            _rule(
                "transaction_amounts_not_missing",
                missing_amounts == 0,
                "WARN",
                {"missing_amounts": missing_amounts},
            ),
            _rule(
                "transactions_have_customer_id",
                missing_customers == 0,
                "ERROR",
                {"missing_customer_ids": missing_customers},
            ),
            _rule(
                "transactions_reference_known_customers",
                unknown_customers == 0,
                "WARN",
                {"unknown_customer_references": unknown_customers},
            ),
            _rule(
                "inference_dataset_has_no_target",
                not inference_has_target,
                "ERROR",
                {"has_is_fraud_column": inference_has_target},
            ),
        ]
    )

    error_failures = [rule for rule in rules if rule["status"] == "FAIL" and rule["severity"] == "ERROR"]
    warn_failures = [rule for rule in rules if rule["status"] == "FAIL" and rule["severity"] == "WARN"]
    report = {
        "generated_at": utc_now_iso(),
        "summary": {
            "total_rules": len(rules),
            "passed": len([rule for rule in rules if rule["status"] == "PASS"]),
            "failed": len([rule for rule in rules if rule["status"] == "FAIL"]),
            "error_failures": len(error_failures),
            "warning_failures": len(warn_failures),
            "pipeline_can_continue": len(error_failures) == 0,
        },
        "rules": rules,
        "notes": [
            "WARN failures are expected in the synthetic raw data and are corrected in cleaned outputs.",
            "ERROR failures should stop the lab because downstream datasets would be structurally unsafe.",
        ],
    }
    return json_safe(report)

