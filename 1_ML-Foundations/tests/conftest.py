from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import shutil
import uuid

import pytest


@pytest.fixture
def project_tmp_path() -> Iterator[Path]:
    base_dir = Path(__file__).resolve().parents[1] / "test_work"
    base_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_dir / uuid.uuid4().hex
    run_dir.mkdir()
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
