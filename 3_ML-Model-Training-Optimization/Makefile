PYTHON ?= python

.PHONY: help install deploy-infra data upload-raw create-feature-group ingest-features validate-online-store query-offline-store processing train-baseline evaluate-baseline hpo evaluate-best compare-models register-model export-feature-metadata training-report model-card create-pipeline run-pipeline download-reports validate cost-check show-experiments clean-local-outputs lab lab-00-context lab-01-aws-setup lab-02-training-data lab-03-feature-store lab-04-processing lab-05-training lab-06-evaluation lab-07-hpo lab-08-experiments lab-09-model-registry lab-10-pipeline lab-11-cost lab-12-cleanup lab-13-next-labs all-cloud destroy-infra test

help:
	@echo "AWS ML Lab 03 targets:"
	@echo "  make all-cloud      Deploy infra and run the full cloud training flow"
	@echo "  make lab            Same as all-cloud, without cleanup"
	@echo "  make lab-03-feature-store  Run a specific teaching step"
	@echo "  make destroy-infra  Cleanup SageMaker resources and delete CloudFormation stack"
	@echo "  make clean-local-outputs  Delete local generated artifacts only"
	@echo "  make validate       Validate Feature Store, S3, jobs, registry and no endpoints"

install:
	$(PYTHON) -m pip install -r requirements.txt

deploy-infra:
	bash scripts/deploy_infra.sh

data:
	$(PYTHON) -m src.generate_sample_data

upload-raw:
	$(PYTHON) -m src.upload_raw_data

create-feature-group:
	$(PYTHON) -m src.create_feature_group

ingest-features:
	$(PYTHON) -m src.ingest_features

validate-online-store:
	$(PYTHON) -m src.get_online_features

query-offline-store:
	$(PYTHON) -m src.query_offline_store

processing:
	$(PYTHON) -m src.submit_processing_job

train-baseline:
	$(PYTHON) -m src.submit_training_job

evaluate-baseline:
	$(PYTHON) -m src.evaluate_model --model-name baseline

hpo:
	$(PYTHON) -m src.submit_hpo_job

evaluate-best:
	$(PYTHON) -m src.evaluate_model --model-name optimized

compare-models: evaluate-best
	$(PYTHON) -m src.compare_models

register-model:
	$(PYTHON) -m src.register_model

export-feature-metadata:
	$(PYTHON) -m src.export_feature_metadata

training-report:
	$(PYTHON) -m src.training_report

model-card:
	$(PYTHON) -m src.model_card

create-pipeline:
	$(PYTHON) -m src.create_pipeline

run-pipeline:
	$(PYTHON) -m src.run_pipeline

download-reports:
	$(PYTHON) -m src.download_outputs

validate:
	$(PYTHON) -m src.validate_lab

cost-check:
	$(PYTHON) -m src.cost_and_resource_check

show-experiments:
	$(PYTHON) -m src.show_experiment_tracking

clean-local-outputs:
	$(PYTHON) -m src.clean_local_outputs

test:
	$(PYTHON) -m pytest tests

lab-00-context:
	@echo "Read lab/00_contexto_negocio.md and doc/3_AWS_Model_Training_Optimization.pdf before running cloud resources."

lab-01-aws-setup: deploy-infra

lab-02-training-data: data upload-raw

lab-03-feature-store: create-feature-group ingest-features validate-online-store query-offline-store

lab-04-processing: processing

lab-05-training: train-baseline

lab-06-evaluation: evaluate-baseline

lab-07-hpo: hpo compare-models

lab-08-experiments: show-experiments

lab-09-model-registry: register-model export-feature-metadata training-report model-card

lab-10-pipeline: create-pipeline

lab-11-cost: cost-check

lab-12-cleanup: destroy-infra

lab-13-next-labs: export-feature-metadata
	@echo "Feature contract refreshed for batch and real-time inference labs."

lab: lab-00-context lab-01-aws-setup lab-02-training-data lab-03-feature-store lab-04-processing lab-05-training lab-06-evaluation lab-07-hpo lab-08-experiments lab-09-model-registry lab-10-pipeline lab-11-cost lab-13-next-labs download-reports validate
	@echo "Teaching lab completed. Run make lab-12-cleanup when students finish reviewing resources."

all-cloud: lab
	@echo "Cloud lab completed. Review costs, reports, Model Registry and run make destroy-infra when finished."

destroy-infra:
	bash scripts/destroy_infra.sh
