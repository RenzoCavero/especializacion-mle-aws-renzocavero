import pandas as pd

from src.config import TARGET_COLUMN
from src.generate_dataset import generate_dataset


def test_generate_dataset_creates_expected_files(project_tmp_path) -> None:
    raw_path = project_tmp_path / "raw" / "transactions.csv"
    batch_path = project_tmp_path / "raw" / "batch.csv"

    metadata = generate_dataset(
        output_path=raw_path,
        batch_output_path=batch_path,
        n_rows=600,
        batch_rows=50,
        seed=123,
    )

    df = pd.read_csv(raw_path)
    batch_df = pd.read_csv(batch_path)

    assert raw_path.exists()
    assert batch_path.exists()
    assert len(df) == 600
    assert len(batch_df) == 50
    assert TARGET_COLUMN in df.columns
    assert TARGET_COLUMN not in batch_df.columns
    assert 0.01 < metadata["fraud_rate"] < 0.50
