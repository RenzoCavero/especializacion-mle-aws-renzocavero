from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"


def load_training_module():
    sys.path.insert(0, str(TRAINING_DIR))
    spec = importlib.util.spec_from_file_location("lab_training_train", TRAINING_DIR / "train.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_accepts_sagemaker_short_c_argument() -> None:
    module = load_training_module()
    args = module.parse_args(["-C", "0.5", "--max-iter", "300", "--class-weight", "balanced"])

    assert args.C == 0.5
    assert args.max_iter == 300
    assert args.class_weight == "balanced"


def test_parse_args_accepts_long_c_argument() -> None:
    module = load_training_module()
    args = module.parse_args(["--C", "2.0"])

    assert args.C == 2.0
