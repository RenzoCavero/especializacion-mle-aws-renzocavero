from src.config import FeatureContract
from src.prepare_batch_input import build_batch_payload, generate_synthetic_dataframe


def test_batch_payload_excludes_target_and_preserves_identifier():
    contract = FeatureContract.standalone()
    df = generate_synthetic_dataframe(rows=5, contract=contract)
    payload, manifest = build_batch_payload(df, contract)

    assert contract.target_column not in payload.columns
    assert contract.batch_identifier_column in manifest.columns
    assert len(payload) == len(manifest) == 5
    assert list(payload.columns) == contract.inference_features


def test_batch_output_can_be_joined_by_row_order():
    contract = FeatureContract.standalone()
    df = generate_synthetic_dataframe(rows=3, contract=contract)
    _, manifest = build_batch_payload(df, contract)

    predictions = [0.1, 0.7, 0.9]
    manifest["score"] = predictions

    assert manifest.loc[0, contract.batch_identifier_column] == "CUST-0001"
    assert manifest.loc[2, "score"] == 0.9
