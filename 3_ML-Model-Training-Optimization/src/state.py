from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from src.config import STATE_FILE


def load_state(path: Path = STATE_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any], path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def update_state(**kwargs: Any) -> dict[str, Any]:
    state = load_state()
    state.update({key: value for key, value in kwargs.items() if value is not None})
    save_state(state)
    return state
