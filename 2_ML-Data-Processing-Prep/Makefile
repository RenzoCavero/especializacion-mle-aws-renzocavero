PYTHON ?= python

.PHONY: help deploy-infra data upload-raw catalog profile quality process features training-dataset inference-dataset lineage dataset-card glue-crawler glue-data-quality column-stats aws-native-extras download-reports validate clean-local-outputs lab lab-00-context lab-01-aws-setup lab-02-data-lake-s3 lab-03-glue-catalog lab-04-quality-profiling lab-05-processing-jobs lab-06-feature-engineering lab-07-training-serving-consistency lab-08-governance-lineage lab-09-cost-security-cleanup lab-10-athena-glue-native-features destroy-infra all-cloud test

help:
	@echo "AWS ML data preparation lab"
	@echo "Targets: deploy-infra data upload-raw catalog profile quality process features training-dataset inference-dataset lineage dataset-card glue-crawler glue-data-quality column-stats aws-native-extras download-reports validate clean-local-outputs lab destroy-infra all-cloud test"
	@echo "Numbered steps: make lab-02-data-lake-s3, make lab-05-processing-jobs, make lab-10-athena-glue-native-features"

deploy-infra:
	$(PYTHON) -m src.deploy_infra

data:
	$(PYTHON) -m src.generate_sample_data

upload-raw:
	$(PYTHON) -m src.upload_raw_data

catalog:
	$(PYTHON) -m src.register_catalog

profile:
	$(PYTHON) -m src.run_processing_job --steps profile

quality:
	$(PYTHON) -m src.run_processing_job --steps quality

process:
	$(PYTHON) -m src.run_processing_job --steps process

features:
	$(PYTHON) -m src.run_processing_job --steps features

training-dataset:
	$(PYTHON) -m src.run_processing_job --steps training-dataset

inference-dataset:
	$(PYTHON) -m src.run_processing_job --steps inference-dataset

lineage:
	$(PYTHON) -m src.run_processing_job --steps lineage

dataset-card:
	$(PYTHON) -m src.run_processing_job --steps dataset-card

glue-crawler:
	$(PYTHON) -m src.run_glue_crawler

glue-data-quality:
	$(PYTHON) -m src.run_glue_data_quality

column-stats:
	$(PYTHON) -m src.run_glue_column_statistics

aws-native-extras:
	$(PYTHON) -m src.run_glue_crawler
	$(PYTHON) -m src.run_glue_data_quality
	$(PYTHON) -m src.run_glue_column_statistics

download-reports:
	$(PYTHON) -m src.download_reports

validate:
	$(PYTHON) -m src.validate_outputs

clean-local-outputs:
	$(PYTHON) -m src.clean_local_outputs

destroy-infra:
	$(PYTHON) -m src.destroy_infra

lab-00-context:
	@echo "Read lab/00_contexto_negocio.md before running cloud resources."

lab-01-aws-setup: deploy-infra

lab-02-data-lake-s3: data upload-raw

lab-03-glue-catalog: catalog

lab-04-quality-profiling:
	$(PYTHON) -m src.run_processing_job --steps profile,quality

lab-05-processing-jobs:
	$(PYTHON) -m src.run_processing_job --steps process

lab-06-feature-engineering:
	$(PYTHON) -m src.run_processing_job --steps features

lab-07-training-serving-consistency:
	$(PYTHON) -m src.run_processing_job --steps training-dataset,inference-dataset

lab-08-governance-lineage:
	$(PYTHON) -m src.run_processing_job --steps lineage,dataset-card
	$(PYTHON) -m src.download_reports

lab-09-cost-security-cleanup: destroy-infra

lab-10-athena-glue-native-features: aws-native-extras download-reports

lab:
	$(PYTHON) -m src.lab_runner all

all-cloud:
	$(PYTHON) -m src.deploy_infra
	$(PYTHON) -m src.generate_sample_data
	$(PYTHON) -m src.upload_raw_data
	$(PYTHON) -m src.register_catalog
	$(PYTHON) -m src.run_processing_job --steps all
	$(PYTHON) -m src.download_reports
	$(PYTHON) -m src.validate_outputs

test:
	pytest -q
