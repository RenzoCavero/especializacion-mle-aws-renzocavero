from types import SimpleNamespace

from src.submit_autopilot_job import build_tabular_config


def test_build_tabular_config_limits_algorithms_for_minimal_demo() -> None:
    config = SimpleNamespace(
        autopilot_mode="ENSEMBLING",
        autopilot_max_candidates=2,
        autopilot_max_runtime_seconds=900,
        autopilot_algorithms=("linear-learner", "xgboost"),
    )

    tabular_config = build_tabular_config(config)

    assert tabular_config["CompletionCriteria"]["MaxCandidates"] == 2
    assert tabular_config["CompletionCriteria"]["MaxAutoMLJobRuntimeInSeconds"] == 900
    assert tabular_config["CandidateGenerationConfig"]["AlgorithmsConfig"] == [
        {"AutoMLAlgorithms": ["linear-learner", "xgboost"]}
    ]


def test_build_tabular_config_skips_algorithms_for_auto_mode() -> None:
    config = SimpleNamespace(
        autopilot_mode="AUTO",
        autopilot_max_candidates=2,
        autopilot_max_runtime_seconds=900,
        autopilot_algorithms=("linear-learner", "xgboost"),
    )

    tabular_config = build_tabular_config(config)

    assert "CandidateGenerationConfig" not in tabular_config
