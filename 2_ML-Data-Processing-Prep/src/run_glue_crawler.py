"""Run the optional Glue crawler demo for raw data."""

from __future__ import annotations

import time
from typing import Any, Dict

from src.aws_clients import client, get_bucket_name, get_glue_crawler_name, get_glue_database_name
from src.config import get_settings
from src.data_utils import utc_now_iso
from src.glue_catalog import register_all_tables, sync_catalog_data
from src.s3_io import write_json_to_s3


RAW_TO_CRAWLER_DEMO = {
    "raw/customers.csv": "crawler_demo/customers/customers.csv",
    "raw/transactions.csv": "crawler_demo/transactions/transactions.csv",
    "raw/inference_transactions.csv": "crawler_demo/inference_transactions/inference_transactions.csv",
}


def _copy_raw_files_for_crawler(s3_client: Any, bucket_name: str) -> list[str]:
    copied = []
    for source_key, target_key in RAW_TO_CRAWLER_DEMO.items():
        s3_client.head_object(Bucket=bucket_name, Key=source_key)
        s3_client.copy_object(
            Bucket=bucket_name,
            CopySource={"Bucket": bucket_name, "Key": source_key},
            Key=target_key,
        )
        copied.append(target_key)
    return copied


def _wait_for_crawler(glue_client: Any, crawler_name: str, poll_seconds: int) -> Dict[str, object]:
    while True:
        crawler = glue_client.get_crawler(Name=crawler_name)["Crawler"]
        state = crawler["State"]
        print(f"Glue crawler state: {state}")
        if state == "READY":
            last_crawl = crawler.get("LastCrawl", {})
            status = last_crawl.get("Status", "UNKNOWN")
            if status == "FAILED":
                raise RuntimeError(f"Glue crawler failed: {last_crawl.get('ErrorMessage', '')}")
            return crawler
        time.sleep(poll_seconds)


def run_crawler(wait: bool = True, poll_seconds: int = 15) -> Dict[str, object]:
    settings = get_settings()
    bucket = get_bucket_name(settings)
    database = get_glue_database_name(settings)
    crawler_name = get_glue_crawler_name(settings)
    s3 = client("s3", settings)
    glue = client("glue", settings)

    sync_catalog_data(s3, bucket)
    register_all_tables(glue, database, bucket)
    copied_keys = _copy_raw_files_for_crawler(s3, bucket)
    print(f"Copied raw CSV files into s3://{bucket}/crawler_demo/ for crawler-friendly layout.")

    try:
        glue.start_crawler(Name=crawler_name)
        print(f"Started Glue crawler {crawler_name}")
    except glue.exceptions.CrawlerRunningException:
        print(f"Glue crawler {crawler_name} is already running.")

    crawler = _wait_for_crawler(glue, crawler_name, poll_seconds) if wait else glue.get_crawler(Name=crawler_name)["Crawler"]
    tables = glue.get_tables(DatabaseName=database)["TableList"]
    crawler_tables = sorted(table["Name"] for table in tables if table["Name"].startswith("crawler_"))
    report: Dict[str, object] = {
        "generated_at": utc_now_iso(),
        "crawler_name": crawler_name,
        "database": database,
        "bucket": bucket,
        "copied_demo_keys": copied_keys,
        "crawler_state": crawler.get("State"),
        "last_crawl": crawler.get("LastCrawl", {}),
        "created_or_updated_tables": crawler_tables,
        "note": "Crawler demo uses crawler_demo/ subfolders so each raw CSV is inferred as a separate table.",
    }
    write_json_to_s3(s3, report, bucket, "reports/glue_crawler_report.json")
    print(f"Crawler report written to s3://{bucket}/reports/glue_crawler_report.json")
    print(f"Crawler tables: {', '.join(crawler_tables) if crawler_tables else '(none found yet)'}")
    return report


def main() -> None:
    run_crawler()


if __name__ == "__main__":
    main()
