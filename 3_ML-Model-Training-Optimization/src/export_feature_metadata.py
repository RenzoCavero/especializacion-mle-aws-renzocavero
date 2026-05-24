from __future__ import annotations

import json
import logging

from src.aws_clients import put_json_s3
from src.config import get_config, s3_join
from src.feature_schema import build_feature_contract
from src.logging_utils import configure_logging
from src.state import load_state, update_state


LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    config = get_config()
    config.require_aws_fields()
    state = load_state()
    contract = build_feature_contract(
        feature_group_name=config.feature_group_name,
        online_store_enabled=config.enable_online_store,
        offline_store_s3_uri=config.offline_store_s3_uri,
        model_package_group_name=config.model_package_group_name,
        model_artifact_s3_uri=state.get("selected_model_artifact_s3_uri")
        or state.get("best_model_artifact_s3_uri")
        or state.get("baseline_model_artifact_s3_uri"),
        dataset_s3_uri=state.get("train_s3_uri") or config.train_s3_uri,
        objective_metric_name=state.get("objective_metric_name", "f1"),
        objective_metric_value=state.get("objective_metric_value"),
        preprocessing_metadata_s3_uri=state.get("preprocessing_metadata_s3_uri"),
        model_package_arn=state.get("model_package_arn"),
        raw_data_s3_uri=state.get("raw_data_s3_uri") or config.raw_data_s3_uri,
        cleaned_data_s3_uri=state.get("cleaned_data_s3_uri") or config.cleaned_data_s3_uri,
        curated_features_s3_uri=state.get("curated_features_s3_uri") or config.curated_features_s3_uri,
        feature_lineage_s3_uri=state.get("feature_lineage_s3_uri") or config.feature_lineage_s3_uri,
    )
    local_path = config.local_outputs_dir / "feature_contract.json"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")
    s3_uri = s3_join(config.s3_bucket_name, "model_registry_metadata", "feature_contract.json")
    put_json_s3(config, contract, s3_uri)
    update_state(feature_contract_local_path=str(local_path), feature_contract_s3_uri=s3_uri)
    LOGGER.info("Feature contract written to %s and %s", local_path, s3_uri)


if __name__ == "__main__":
    main()
