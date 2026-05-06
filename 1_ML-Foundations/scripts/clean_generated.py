"""Clean generated lab outputs without deleting source files or documentation."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GENERATED_DIRS = [
    PROJECT_ROOT / "data" / "raw",
    PROJECT_ROOT / "data" / "processed",
    PROJECT_ROOT / "artifacts" / "model",
    PROJECT_ROOT / "artifacts" / "metrics",
    PROJECT_ROOT / "artifacts" / "predictions",
    PROJECT_ROOT / "artifacts" / "governance",
    PROJECT_ROOT / ".pytest_cache",
    PROJECT_ROOT / "test_work",
]


def is_inside_project(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def discover_pycache_dirs() -> list[Path]:
    excluded_roots = [PROJECT_ROOT / ".venv", PROJECT_ROOT / "venv"]
    pycache_dirs = []
    for path in PROJECT_ROOT.rglob("__pycache__"):
        if not path.is_dir():
            continue
        if any(is_inside(path, excluded_root) for excluded_root in excluded_roots):
            continue
        pycache_dirs.append(path)
    return pycache_dirs


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def remove_dir(path: Path, dry_run: bool) -> None:
    if not is_inside_project(path):
        raise RuntimeError(f"Refusing to remove path outside project: {path}")
    if not path.exists():
        print(f"[clean] skip missing {path.relative_to(PROJECT_ROOT)}")
        return
    print(f"[clean] remove {path.relative_to(PROJECT_ROOT)}")
    if not dry_run:
        shutil.rmtree(path)


def clean_generated(dry_run: bool = False) -> None:
    targets = GENERATED_DIRS + discover_pycache_dirs()
    for path in targets:
        remove_dir(path, dry_run=dry_run)
    if dry_run:
        print("[clean] dry run completed; no files were deleted.")
    else:
        print("[clean] generated outputs removed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove generated data, artifacts and Python caches.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_generated(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
