from __future__ import annotations

import argparse
from dataclasses import dataclass
import subprocess
import sys

from src.config import PROJECT_ROOT


Command = tuple[str, ...]


@dataclass(frozen=True)
class LabStep:
    number: str
    slug: str
    title: str
    commands: tuple[Command, ...]

    @property
    def key(self) -> str:
        return f"{self.number}-{self.slug}"


STEPS: tuple[LabStep, ...] = (
    LabStep("00", "context", "Contexto de negocio y formulacion ML", (("message", "Lee lab/00_contexto_negocio.md antes de crear recursos."),)),
    LabStep("01", "aws-setup", "Configuracion AWS, IAM e infraestructura base", (("src.deploy_infra",),)),
    LabStep("02", "training-data", "Datos de entrenamiento en Amazon S3", (("src.generate_sample_data",), ("src.upload_raw_data",))),
    LabStep(
        "03",
        "feature-store",
        "SageMaker Feature Store",
        (("src.create_feature_group",), ("src.ingest_features",), ("src.get_online_features",), ("src.query_offline_store",)),
    ),
    LabStep("04", "processing", "SageMaker Processing Jobs", (("src.submit_processing_job",),)),
    LabStep("05", "training", "SageMaker Training Jobs", (("src.submit_training_job",),)),
    LabStep("06", "evaluation", "Metricas y evaluacion reproducible", (("src.evaluate_model", "--model-name", "baseline"),)),
    LabStep(
        "07",
        "hpo",
        "Automatic Model Tuning",
        (("src.submit_hpo_job",), ("src.evaluate_model", "--model-name", "optimized"), ("src.compare_models",)),
    ),
    LabStep("08", "experiments", "SageMaker Experiments", (("src.show_experiment_tracking",),)),
    LabStep(
        "09",
        "model-registry",
        "SageMaker Model Registry",
        (("src.register_model",), ("src.export_feature_metadata",), ("src.training_report",), ("src.model_card",)),
    ),
    LabStep("10", "pipeline", "SageMaker Pipelines", (("src.create_pipeline",),)),
    LabStep("11", "cost", "Revision de costos y recursos", (("src.cost_and_resource_check",),)),
    LabStep("13", "next-labs", "Contrato de features para futuros laboratorios", (("src.export_feature_metadata",),)),
)

CLEANUP_STEP = LabStep("12", "cleanup", "Seguridad y limpieza", (("src.destroy_infra",),))


def run_module(command: Command) -> None:
    if command[0] == "message":
        print(command[1])
        return
    subprocess.run([sys.executable, "-m", *command], cwd=PROJECT_ROOT, check=True)


def find_step(identifier: str) -> LabStep:
    normalized = identifier.strip().lower()
    for step in (*STEPS, CLEANUP_STEP):
        if normalized in {step.number, step.slug, step.key, f"lab-{step.key}"}:
            return step
    valid = ", ".join(step.key for step in (*STEPS, CLEANUP_STEP))
    raise SystemExit(f"Unknown step '{identifier}'. Valid steps: {valid}")


def run_step(step: LabStep) -> None:
    print(f"\n=== Lab {step.key}: {step.title} ===")
    for command in step.commands:
        if command[0] != "message":
            print(f"$ python -m {' '.join(command)}")
        run_module(command)


def list_steps() -> None:
    for step in STEPS:
        print(f"{step.key}: {step.title}")
    print(f"{CLEANUP_STEP.key}: {CLEANUP_STEP.title}")


def run_all() -> None:
    for step in STEPS:
        run_step(step)
    run_module(("src.download_outputs",))
    run_module(("src.validate_lab",))
    print("\nLaboratorio completado. La limpieza esta separada: python -m src.lab_runner cleanup")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Lab 03 without Make.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available lab steps.")
    subparsers.add_parser("all", help="Run the full lab without cleanup.")
    step_parser = subparsers.add_parser("step", help="Run one lab step by number or name.")
    step_parser.add_argument("identifier", help="Example: 03, feature-store, 03-feature-store")
    subparsers.add_parser("cleanup", help="Run cleanup and delete the CloudFormation stack.")
    args = parser.parse_args()

    if args.command == "list":
        list_steps()
    elif args.command == "all":
        run_all()
    elif args.command == "step":
        run_step(find_step(args.identifier))
    elif args.command == "cleanup":
        run_step(CLEANUP_STEP)


if __name__ == "__main__":
    main()
