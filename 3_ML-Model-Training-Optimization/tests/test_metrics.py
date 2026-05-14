from src.metrics import binary_classification_metrics, confusion_counts


def test_confusion_counts() -> None:
    counts = confusion_counts([1, 1, 0, 0], [1, 0, 1, 0])
    assert counts == {
        "true_positive": 1,
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
    }


def test_binary_metrics_zero_division_safe() -> None:
    metrics = binary_classification_metrics([0, 0, 0], [0, 0, 0])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert metrics["accuracy"] == 1.0
