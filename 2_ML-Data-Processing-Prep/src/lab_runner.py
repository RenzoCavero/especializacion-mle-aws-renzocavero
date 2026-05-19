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


CORE_STEPS: tuple[LabStep, ...] = (
    LabStep(
        "00",
        "context",
        "Contexto de negocio y objetivo del data lake ML",
        (("message", "Lee lab/00_contexto_negocio.md antes de crear recursos cloud."),),
    ),
    LabStep("01", "aws-setup", "Configuracion AWS e infraestructura base", (("src.deploy_infra",),)),
    LabStep("02", "data-lake-s3", "Datos sinteticos y capa raw en Amazon S3", (("src.generate_sample_data",), ("src.upload_raw_data",))),
    LabStep("03", "glue-catalog", "Registro de tablas en AWS Glue Data Catalog", (("src.register_catalog",),)),
    LabStep("04", "quality-profiling", "Profiling y reglas de calidad", (("src.run_processing_job", "--steps", "profile,quality"),)),
    LabStep("05", "processing-jobs", "AWS Glue Python Shell Job y transformacion principal", (("src.run_processing_job", "--steps", "process"),)),
    LabStep("06", "feature-engineering", "Construccion de features", (("src.run_processing_job", "--steps", "features"),)),
    LabStep(
        "07",
        "training-serving-consistency",
        "Datasets de entrenamiento e inferencia con contrato consistente",
        (("src.run_processing_job", "--steps", "training-dataset,inference-dataset"),),
    ),
    LabStep(
        "08",
        "governance-lineage",
        "Lineage, dataset card y reportes",
        (("src.run_processing_job", "--steps", "lineage,dataset-card"), ("src.download_reports",)),
    ),
)

OPTIONAL_STEP = LabStep(
    "10",
    "athena-glue-native-features",
    "Athena, Glue Crawler, Glue Data Quality y Column Statistics",
    (("src.run_glue_crawler",), ("src.run_glue_data_quality",), ("src.run_glue_column_statistics",), ("src.download_reports",)),
)

CLEANUP_STEP = LabStep("09", "cost-security-cleanup", "Costos, seguridad y limpieza", (("src.destroy_infra",),))


def run_module(command: Command) -> None:
    if command[0] == "message":
        print(command[1])
        return
    subprocess.run([sys.executable, "-m", *command], cwd=PROJECT_ROOT, check=True)


def find_step(identifier: str) -> LabStep:
    normalized = identifier.strip().lower()
    steps = (*CORE_STEPS, CLEANUP_STEP, OPTIONAL_STEP)
    for step in steps:
        if normalized in {step.number, step.slug, step.key, f"lab-{step.key}"}:
            return step
    valid = ", ".join(step.key for step in steps)
    raise SystemExit(f"Unknown step '{identifier}'. Valid steps: {valid}")


def run_step(step: LabStep) -> None:
    print(f"\n=== Lab {step.key}: {step.title} ===")
    for command in step.commands:
        if command[0] != "message":
            print(f"$ python -m {' '.join(command)}")
        run_module(command)


def list_steps() -> None:
    for step in CORE_STEPS:
        print(f"{step.key}: {step.title}")
    print(f"{CLEANUP_STEP.key}: {CLEANUP_STEP.title}")
    print(f"{OPTIONAL_STEP.key}: {OPTIONAL_STEP.title} (opcional)")


def run_all() -> None:
    run_step(CORE_STEPS[0])
    run_step(CORE_STEPS[1])
    run_step(CORE_STEPS[2])
    run_step(CORE_STEPS[3])
    print("\n=== Lab 04-08: Pipeline cloud completo en un solo Glue Job ===")
    run_module(("src.run_processing_job", "--steps", "all"))
    run_module(("src.download_reports",))
    run_module(("src.validate_outputs",))
    print("\nLaboratorio base completado. La limpieza esta separada: python -m src.lab_runner cleanup")
    print("Extras opcionales: python -m src.lab_runner step 10")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Lab 02 data preparation steps without Make.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available lab steps.")
    subparsers.add_parser("all", help="Run the base lab without cleanup.")
    step_parser = subparsers.add_parser("step", help="Run one lab step by number or name.")
    step_parser.add_argument("identifier", help="Example: 04, quality-profiling, 04-quality-profiling")
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
