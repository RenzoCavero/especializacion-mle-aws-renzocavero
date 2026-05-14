from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.config import PROJECT_ROOT, get_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run processing entrypoint locally for debugging only.")
    parser.add_argument("--input", default=None)
    args = parser.parse_args()
    config = get_config()
    input_path = Path(args.input) if args.input else config.raw_data_local_path
    output_root = PROJECT_ROOT / "data" / "local_cache" / "processed"
    output_root.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(PROJECT_ROOT / "processing" / "processing_entrypoint.py"),
        "--input-data",
        str(input_path),
        "--train-output",
        str(output_root / "train"),
        "--validation-output",
        str(output_root / "validation"),
        "--test-output",
        str(output_root / "test"),
        "--metadata-output",
        str(output_root / "metadata"),
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
