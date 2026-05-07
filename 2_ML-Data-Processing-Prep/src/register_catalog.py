"""Register Glue Data Catalog tables for the lab."""

from __future__ import annotations

from src.aws_clients import client, get_bucket_name, get_glue_database_name
from src.config import get_settings
from src.glue_catalog import register_all_tables


def register_catalog() -> None:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    glue = client("glue", settings)
    registered = register_all_tables(glue, database, bucket)
    print(f"Registered Glue tables in database {database}: {', '.join(registered)}")


def main() -> None:
    register_catalog()


if __name__ == "__main__":
    main()

