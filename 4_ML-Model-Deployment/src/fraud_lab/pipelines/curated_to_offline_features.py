from __future__ import annotations

import argparse

from fraud_lab.feature_store.seed_feature_store import seed_feature_store


def curated_to_offline_features() -> dict[str, int]:
    counts = seed_feature_store()
    print("Curated -> Feature Store completado.")
    print("Se escribio Offline Store historico y Online Store con ultimo valor por entidad.")
    return counts


def main() -> None:
    argparse.ArgumentParser(description="Build local offline feature groups from curated data.").parse_args()
    curated_to_offline_features()


if __name__ == "__main__":
    main()

