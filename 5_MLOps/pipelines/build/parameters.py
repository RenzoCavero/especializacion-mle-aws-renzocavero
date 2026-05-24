"""Build pipeline parameter defaults."""

PIPELINE_STEPS = ["process", "train", "evaluate", "quality_gate", "register"]
DEFAULT_F1_THRESHOLD = 0.70
DEFAULT_AUC_THRESHOLD = 0.70
FRAMEWORK_VERSION = "1.2-1"
PYTHON_VERSION = "py3"


def default_parameters() -> dict[str, object]:
    return {
        "PipelineSteps": PIPELINE_STEPS,
        "F1Threshold": DEFAULT_F1_THRESHOLD,
        "AUCThreshold": DEFAULT_AUC_THRESHOLD,
        "FrameworkVersion": FRAMEWORK_VERSION,
        "PythonVersion": PYTHON_VERSION,
    }

