"""Run the MLOps lab by numbered steps or as a full flow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import load_config, write_metadata


ROOT_DIR = Path(__file__).resolve().parents[1]
Command = tuple[str, ...]


def resolve_python_executable() -> str:
    """Prefer the lab-local virtualenv for child commands when it exists."""
    candidates = [
        ROOT_DIR / ".venv" / "Scripts" / "python.exe",
        ROOT_DIR / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


@dataclass(frozen=True)
class LabStep:
    number: str
    slug: str
    title: str
    doc_path: str
    commands: tuple[Command, ...]
    include_in_all: bool = True

    @property
    def key(self) -> str:
        return f"{self.number}-{self.slug}"


LAB_STEPS: tuple[LabStep, ...] = (
    LabStep(
        "00",
        "contexto-negocio",
        "Contexto de negocio y alcance MLOps",
        "lab/00_contexto_negocio.md",
        (
            ("message", "Documentacion: lab/00_contexto_negocio.md"),
            ("record", "Contexto revisado. Se genera evidencia local del inicio del laboratorio."),
        ),
    ),
    LabStep(
        "01",
        "aws-setup",
        "Validacion de configuracion AWS",
        "lab/01_aws_setup.md",
        (
            ("message", "Documentacion: lab/01_aws_setup.md"),
            ("src.config",),
            ("src.aws_clients",),
            ("src.deploy_infra",),
            ("src.aws_clients",),
        ),
    ),
    LabStep(
        "02",
        "standalone-vs-integrated",
        "Seleccion de modo y preparacion de datos",
        "lab/02_standalone_vs_integrated_mode.md",
        (
            ("message", "Documentacion: lab/02_standalone_vs_integrated_mode.md"),
            ("src.generate_sample_data", "--upload"),
        ),
    ),
    LabStep(
        "03",
        "devops-vs-mlops",
        "Contrato local de MLOps frente a DevOps",
        "lab/03_devops_vs_mlops.md",
        (
            ("message", "Documentacion: lab/03_devops_vs_mlops.md"),
            ("src.create_or_update_pipeline", "--contract-only"),
            ("record", "Contrato local de pipeline creado sin ejecutar recursos cloud."),
        ),
    ),
    LabStep(
        "04",
        "ci-cd-ct",
        "Validaciones CI/CD/CT y guardrails",
        "lab/04_ci_cd_ct_overview.md",
        (
            ("message", "Documentacion: lab/04_ci_cd_ct_overview.md"),
            ("src.readiness_check",),
        ),
    ),
    LabStep(
        "05",
        "sagemaker-pipelines-build",
        "SageMaker build pipeline",
        "lab/05_sagemaker_pipelines_build.md",
        (
            ("message", "Documentacion: lab/05_sagemaker_pipelines_build.md"),
            ("src.compute", "--workload", "processing"),
            ("src.compute", "--workload", "training"),
            ("src.compute", "--workload", "endpoint"),
            ("src.create_or_update_pipeline",),
            ("src.run_build_pipeline", "--wait"),
            ("src.check_pipeline_execution",),
        ),
    ),
    LabStep(
        "06",
        "model-registry-approval",
        "Model Registry y approval gate",
        "lab/06_model_registry_approval_gates.md",
        (
            ("message", "Documentacion: lab/06_model_registry_approval_gates.md"),
            ("src.register_model_metadata",),
            ("src.approve_model",),
            ("src.resolve_approved_model",),
        ),
    ),
    LabStep(
        "07",
        "deployment-pipeline",
        "Deployment controlado del modelo aprobado",
        "lab/07_deployment_pipeline.md",
        (
            ("message", "Documentacion: lab/07_deployment_pipeline.md"),
            ("src.deploy_model", "--wait"),
            ("src.smoke_test_endpoint",),
        ),
    ),
    LabStep(
        "08",
        "data-capture",
        "Data Capture y trafico normal",
        "lab/08_data_capture.md",
        (
            ("message", "Documentacion: lab/08_data_capture.md"),
            ("src.configure_data_capture",),
            ("src.simulate_traffic",),
            ("src.check_data_capture", "--wait", "--timeout-seconds", "300", "--poll-seconds", "30"),
        ),
    ),
    LabStep(
        "09",
        "model-quality-performance",
        "Model quality nativo y fallback custom",
        "lab/09_model_quality_performance_monitoring.md",
        (
            ("message", "Documentacion: lab/09_model_quality_performance_monitoring.md"),
            ("src.configure_data_capture",),
            ("src.validate_model_quality_endpoint",),
            ("src.capture_model_quality_data", "--traffic-type", "normal", "--limit", "50"),
            ("src.generate_model_quality_baseline", "--wait"),
            ("src.create_model_quality_schedule",),
            ("src.create_custom_model_quality_schedule", "--if-native-unavailable"),
            ("src.create_model_quality_alarm",),
            ("src.create_custom_model_quality_alarm",),
        ),
    ),
    LabStep(
        "10",
        "model-monitor-baseline",
        "Data Quality baseline, monitoring y alarma",
        "lab/10_model_monitor_baseline.md",
        (
            ("message", "Documentacion: lab/10_model_monitor_baseline.md"),
            ("src.generate_baseline", "--wait"),
            ("src.create_monitoring_schedule",),
            ("src.create_custom_data_quality_schedule", "--if-native-unavailable"),
            ("src.simulate_drift",),
            ("src.check_monitoring_results",),
            ("src.create_cloudwatch_alarm",),
        ),
    ),
    LabStep(
        "11",
        "feedback-loop",
        "Feedback loop con Step Functions y Lambda",
        "lab/11_feedback_loop_retraining_rollback.md",
        (
            ("message", "Documentacion: lab/11_feedback_loop_retraining_rollback.md"),
            ("src.create_feedback_loop",),
            ("src.create_alarm_notifications",),
            ("src.create_eventbridge_rule",),
            ("src.trigger_feedback_loop",),
        ),
    ),
    LabStep(
        "12",
        "batch-transform-monitoring",
        "Batch Transform, Data Capture batch y monitoreo",
        "lab/12_batch_transform_monitoring.md",
        (
            ("message", "Documentacion: lab/12_batch_transform_monitoring.md"),
            ("src.compute", "--workload", "batch-transform"),
            ("src.run_batch_transform", "--wait"),
            ("src.check_batch_transform_capture", "--wait", "--timeout-seconds", "300", "--poll-seconds", "30"),
            ("src.create_batch_monitoring_schedule",),
            ("src.create_custom_batch_data_quality_schedule", "--if-native-unavailable"),
            ("src.start_custom_batch_data_quality_job", "--if-native-unavailable", "--wait"),
            ("src.create_batch_cloudwatch_alarm",),
        ),
        include_in_all=False,
    ),
    LabStep(
        "13",
        "mlops-readiness",
        "MLOps readiness y reporte final",
        "lab/13_mlops_readiness_checklist.md",
        (
            ("message", "Documentacion: lab/13_mlops_readiness_checklist.md"),
            ("src.mlops_report",),
            ("src.readiness_check",),
        ),
    ),
    LabStep(
        "14",
        "cost-security-cleanup",
        "Costos, seguridad y plan de cleanup",
        "lab/14_cost_security_cleanup.md",
        (
            ("message", "Documentacion: lab/14_cost_security_cleanup.md"),
            ("src.rollback_model",),
            ("src.update_baseline",),
            ("record", "Cleanup documentado. La destruccion real se ejecuta solo con python -m src.lab_runner cleanup."),
        ),
    ),
)

CLEANUP_STEP = LabStep(
    "cleanup",
    "destroy-resources",
    "Cleanup explicito de recursos cloud y artefactos S3",
    "lab/14_cost_security_cleanup.md",
    (
        ("message", "Cleanup explicito. Elimina recursos cloud, pipeline, jobs terminales y artefactos S3 del prefijo del laboratorio."),
        ("src.cleanup_all",),
    ),
    include_in_all=False,
)

LOCAL_CLEANUP_STEP = LabStep(
    "cleanup-local",
    "destroy-local-files",
    "Cleanup explicito de archivos locales generados",
    "lab/14_cost_security_cleanup.md",
    (
        (
            "message",
            "Cleanup local explicito. Elimina artifacts/local_outputs y data/local_cache; conserva .env, .env.cloud, codigo, docs y S3 outputs.",
        ),
        ("src.cleanup_local_outputs", "--execute"),
    ),
    include_in_all=False,
)


def record_step(step: LabStep, note: str) -> None:
    config = load_config(validate=False)
    payload = {
        "step": step.number,
        "slug": step.slug,
        "title": step.title,
        "doc_path": step.doc_path,
        "note": note,
    }
    write_metadata(config, f"lab_step_{step.number}", payload)
    print(note, flush=True)


def run_command(step: LabStep, command: Command) -> None:
    if command[0] == "message":
        print(command[1], flush=True)
        return
    if command[0] == "record":
        record_step(step, command[1])
        return

    python_executable = resolve_python_executable()
    print(f"$ {python_executable} -m {' '.join(command)}", flush=True)
    try:
        subprocess.run([python_executable, "-m", *command], cwd=ROOT_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        joined = " ".join(command)
        raise SystemExit(
            f"El comando del paso fallo: python -m {joined}\n"
            "Revisa el error anterior. Si era un comando cloud, valida .env, permisos IAM, roles, bucket y region AWS."
        ) from exc


def find_step(identifier: str) -> LabStep:
    normalized = identifier.strip().lower()
    normalized = normalized.removeprefix("step-").removeprefix("mlops-")
    if normalized in {"cleanup", "destroy", "destroy-resources"}:
        return CLEANUP_STEP
    if normalized in {"cleanup-local", "local-cleanup", "destroy-local-files"}:
        return LOCAL_CLEANUP_STEP

    for step in LAB_STEPS:
        aliases = {
            step.number,
            step.slug,
            step.key,
            f"step-{step.number}",
            f"mlops-{step.number}",
            f"mlops-{step.key}",
        }
        if normalized in aliases or identifier.strip().lower() in aliases:
            return step

    valid = ", ".join(step.key for step in LAB_STEPS)
    raise SystemExit(f"Unknown step '{identifier}'. Valid steps: {valid}, cleanup, cleanup-local")


def run_step(step: LabStep) -> None:
    print(f"\n=== Lab 05 {step.key}: {step.title} ===", flush=True)
    print(f"Doc: {step.doc_path}", flush=True)
    for command in step.commands:
        run_command(step, command)


def list_steps() -> None:
    print("Ruta MLOps AWS:")
    for step in LAB_STEPS:
        print(f"{step.key}: {step.title} -> {step.doc_path}")
    print(f"{CLEANUP_STEP.number}: {CLEANUP_STEP.title} -> {CLEANUP_STEP.doc_path}")
    print(f"{LOCAL_CLEANUP_STEP.number}: {LOCAL_CLEANUP_STEP.title} -> {LOCAL_CLEANUP_STEP.doc_path}")


def run_all() -> None:
    for step in LAB_STEPS:
        if step.include_in_all:
            run_step(step)
    print("\nRuta MLOps completada. El cleanup es explicito: python -m src.lab_runner cleanup", flush=True)


def run_cleanup() -> None:
    run_step(CLEANUP_STEP)


def run_local_cleanup() -> None:
    run_step(LOCAL_CLEANUP_STEP)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Lab 05 MLOps steps individually or as a full flow.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List numbered lab steps.")
    subparsers.add_parser("all", help="Run the full lab without cleanup.")
    subparsers.add_parser("cleanup", help="Run explicit cleanup without deleting external resources by default.")
    subparsers.add_parser("cleanup-local", help="Delete generated local lab files after explicit confirmation by command.")
    step_parser = subparsers.add_parser("step", help="Run one lab step by number or slug.")
    step_parser.add_argument("identifier", help="Example: 00, 05, sagemaker-pipelines-build")
    args = parser.parse_args()

    if args.command == "list":
        list_steps()
    elif args.command == "all":
        run_all()
    elif args.command == "cleanup":
        run_cleanup()
    elif args.command == "cleanup-local":
        run_local_cleanup()
    elif args.command == "step":
        run_step(find_step(args.identifier))


if __name__ == "__main__":
    main()
