PYTHON ?= python

.PHONY: help deploy-infra data upload-raw catalog profile quality process features training-dataset inference-dataset lineage dataset-card download-reports validate destroy-infra all-cloud test

help:
	@echo "AWS ML data preparation lab"
	@echo "Targets: deploy-infra data upload-raw catalog profile quality process features training-dataset inference-dataset lineage dataset-card download-reports validate destroy-infra all-cloud test"

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

download-reports:
	$(PYTHON) -m src.download_reports

validate:
	$(PYTHON) -m src.validate_outputs

destroy-infra:
	$(PYTHON) -m src.destroy_infra

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

