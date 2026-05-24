from __future__ import annotations

from pathlib import Path

from src.lab_runner import LAB_STEPS, find_step, resolve_python_executable


REQUIRED_SECTIONS = [
    "## Objetivo",
    "## Que vas a construir o validar",
    "## Input del paso",
    "## Output esperado del paso",
    "## Conceptos claves",
    "## Prerrequisitos",
    "## Pasos de ejecucion",
    "## Resultado esperado",
    "## Validacion local",
    "## Validacion en consola AWS",
]


def test_lab_runner_has_steps_00_to_14():
    assert [step.number for step in LAB_STEPS] == [f"{idx:02d}" for idx in range(15)]
    assert find_step("00").doc_path == "lab/00_contexto_negocio.md"
    assert find_step("step-09").doc_path == "lab/09_model_quality_performance_monitoring.md"
    assert find_step("step-10").doc_path == "lab/10_model_monitor_baseline.md"
    assert find_step("step-11").doc_path == "lab/11_feedback_loop_retraining_rollback.md"
    assert find_step("step-12").doc_path == "lab/12_batch_transform_monitoring.md"
    assert find_step("step-13").doc_path == "lab/13_mlops_readiness_checklist.md"
    assert find_step("step-14").doc_path == "lab/14_cost_security_cleanup.md"
    assert find_step("cleanup").slug == "destroy-resources"
    assert find_step("cleanup-local").slug == "destroy-local-files"
    assert find_step("destroy-local-files").commands[-1] == ("src.cleanup_local_outputs", "--execute")


def test_step_01_deploys_infrastructure_before_later_cloud_steps():
    step_01 = find_step("01")
    assert ("src.deploy_infra",) in step_01.commands
    assert step_01.commands[-1] == ("src.aws_clients",)


def test_step_09_reuses_existing_endpoint_instead_of_force_recreating():
    step_09 = find_step("09")
    assert ("src.deploy_model", "--wait", "--force-recreate") not in step_09.commands
    assert ("src.configure_data_capture",) in step_09.commands
    assert ("src.validate_model_quality_endpoint",) in step_09.commands
    assert step_09.commands.index(("src.validate_model_quality_endpoint",)) < step_09.commands.index(
        ("src.capture_model_quality_data", "--traffic-type", "normal", "--limit", "50")
    )
    assert ("src.create_custom_model_quality_schedule", "--if-native-unavailable") in step_09.commands
    assert ("src.create_custom_model_quality_alarm",) in step_09.commands


def test_step_10_runs_complete_data_quality_flow():
    step_10 = find_step("10")
    assert ("src.generate_baseline", "--wait") in step_10.commands
    assert ("src.create_monitoring_schedule",) in step_10.commands
    assert ("src.create_custom_data_quality_schedule", "--if-native-unavailable") in step_10.commands
    assert ("src.create_cloudwatch_alarm",) in step_10.commands
    assert step_10.commands.index(("src.create_monitoring_schedule",)) < step_10.commands.index(
        ("src.create_custom_data_quality_schedule", "--if-native-unavailable")
    )
    assert step_10.commands.index(("src.check_monitoring_results",)) < step_10.commands.index(
        ("src.create_cloudwatch_alarm",)
    )


def test_step_11_creates_alarm_notifications_before_eventbridge_rule():
    step_11 = find_step("11")
    assert ("src.create_alarm_notifications",) in step_11.commands
    assert step_11.commands.index(("src.create_alarm_notifications",)) < step_11.commands.index(
        ("src.create_eventbridge_rule",)
    )


def test_step_12_creates_batch_monitoring_fallback_before_alarm():
    step_12 = find_step("12")
    assert ("src.create_batch_monitoring_schedule",) in step_12.commands
    assert ("src.create_custom_batch_data_quality_schedule", "--if-native-unavailable") in step_12.commands
    assert ("src.start_custom_batch_data_quality_job", "--if-native-unavailable", "--wait") in step_12.commands
    assert ("src.create_batch_cloudwatch_alarm",) in step_12.commands
    assert step_12.commands.index(("src.create_batch_monitoring_schedule",)) < step_12.commands.index(
        ("src.create_custom_batch_data_quality_schedule", "--if-native-unavailable")
    )
    assert step_12.commands.index(
        ("src.start_custom_batch_data_quality_job", "--if-native-unavailable", "--wait")
    ) < step_12.commands.index(("src.create_batch_cloudwatch_alarm",))


def test_lab_runner_resolves_a_python_executable():
    assert resolve_python_executable()


def test_each_lab_step_has_documentation_and_required_sections():
    for step in LAB_STEPS:
        path = Path(step.doc_path)
        assert path.exists(), step.doc_path
        content = path.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            assert section in content, f"{step.doc_path} missing {section}"
        assert f"python -m src.lab_runner step {step.number}" in content
