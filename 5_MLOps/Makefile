.RECIPEPREFIX := >

PYTHON ?= python

.PHONY: setup deploy-infra list lab-list step lab-step lab all all-cloud cleanup cleanup-local data check-compute check-processing-compute check-training-compute check-training-inventory check-endpoint-compute check-batch-transform-compute check-batch-transform-inventory build-pipeline run-build-pipeline check-pipeline approve-model reject-model deploy-model smoke-test enable-data-capture check-data-capture model-quality create-baseline create-monitoring-schedule run-batch-transform check-batch-transform-capture create-batch-monitoring-schedule create-custom-batch-data-quality-schedule run-custom-batch-data-quality create-batch-alarm simulate-batch-data-quality-alarm capture-model-quality check-model-quality create-model-quality-alarm create-custom-model-quality-schedule create-custom-model-quality-alarm run-custom-model-quality simulate-model-quality-alarm create-alarm-notifications simulate-traffic simulate-drift check-monitoring create-alarm create-feedback-loop trigger-feedback-loop mlops-report readiness-check destroy-endpoint destroy-monitoring destroy-feedback-loop destroy-local-plan destroy-local destroy-all test step-00 step-01 step-02 step-03 step-04 step-05 step-06 step-07 step-08 step-09 step-10 step-11 step-12 step-13 step-14

setup:
> $(PYTHON) -m pip install -r requirements.txt

deploy-infra:
> bash scripts/deploy_infra.sh

list lab-list:
> $(PYTHON) -m src.lab_runner list

step lab-step:
> $(PYTHON) -m src.lab_runner step $(STEP)

lab all:
> $(PYTHON) -m src.lab_runner all

all-cloud:
> $(PYTHON) -m src.lab_runner all

cleanup:
> $(PYTHON) -m src.lab_runner cleanup

cleanup-local:
> $(PYTHON) -m src.lab_runner cleanup-local

data:
> $(PYTHON) -m src.generate_sample_data --upload

check-compute:
> $(PYTHON) -m src.compute

check-processing-compute:
> $(PYTHON) -m src.compute --workload processing

check-training-compute:
> $(PYTHON) -m src.compute --workload training

check-training-inventory:
> $(PYTHON) -m src.compute --workload training --inventory --limit 0

check-endpoint-compute:
> $(PYTHON) -m src.compute --workload endpoint

check-batch-transform-compute:
> $(PYTHON) -m src.compute --workload batch-transform

check-batch-transform-inventory:
> $(PYTHON) -m src.compute --workload batch-transform --inventory --limit 0

build-pipeline:
> $(PYTHON) -m src.create_or_update_pipeline

run-build-pipeline:
> $(PYTHON) -m src.run_build_pipeline --wait

check-pipeline:
> $(PYTHON) -m src.check_pipeline_execution

approve-model:
> $(PYTHON) -m src.register_model_metadata
> $(PYTHON) -m src.approve_model

reject-model:
> $(PYTHON) -m src.reject_model

deploy-model:
> $(PYTHON) -m src.deploy_model

smoke-test:
> $(PYTHON) -m src.smoke_test_endpoint

enable-data-capture:
> $(PYTHON) -m src.configure_data_capture

check-data-capture:
> $(PYTHON) -m src.check_data_capture --wait

model-quality:
> $(PYTHON) -m src.lab_runner step 09

create-baseline:
> $(PYTHON) -m src.generate_baseline

create-monitoring-schedule:
> $(PYTHON) -m src.create_monitoring_schedule

run-batch-transform:
> $(PYTHON) -m src.run_batch_transform --wait

check-batch-transform-capture:
> $(PYTHON) -m src.check_batch_transform_capture --wait

create-batch-monitoring-schedule:
> $(PYTHON) -m src.create_batch_monitoring_schedule

create-custom-batch-data-quality-schedule:
> $(PYTHON) -m src.create_custom_batch_data_quality_schedule --force

run-custom-batch-data-quality:
> $(PYTHON) -m src.start_custom_batch_data_quality_job --wait

create-batch-alarm:
> $(PYTHON) -m src.create_batch_cloudwatch_alarm

simulate-batch-data-quality-alarm:
> $(PYTHON) -m src.simulate_batch_data_quality_alarm --wait

capture-model-quality:
> $(PYTHON) -m src.capture_model_quality_data

check-model-quality:
> $(PYTHON) -m src.check_model_quality

create-model-quality-baseline:
> $(PYTHON) -m src.generate_model_quality_baseline --wait

create-model-quality-schedule:
> $(PYTHON) -m src.create_model_quality_schedule

create-model-quality-alarm:
> $(PYTHON) -m src.create_model_quality_alarm

create-custom-model-quality-schedule:
> $(PYTHON) -m src.create_custom_model_quality_schedule --force

create-custom-model-quality-alarm:
> $(PYTHON) -m src.create_custom_model_quality_alarm

run-custom-model-quality:
> $(PYTHON) -m src.start_custom_model_quality_job --wait

simulate-model-quality-alarm:
> $(PYTHON) -m src.simulate_model_quality_alarm --wait

create-alarm-notifications:
> $(PYTHON) -m src.create_alarm_notifications

simulate-traffic:
> $(PYTHON) -m src.simulate_traffic

simulate-drift:
> $(PYTHON) -m src.simulate_drift

check-monitoring:
> $(PYTHON) -m src.check_monitoring_results

create-alarm:
> $(PYTHON) -m src.create_cloudwatch_alarm

create-feedback-loop:
> $(PYTHON) -m src.create_feedback_loop
> $(PYTHON) -m src.create_alarm_notifications
> $(PYTHON) -m src.create_eventbridge_rule

trigger-feedback-loop:
> $(PYTHON) -m src.trigger_feedback_loop

mlops-report:
> $(PYTHON) -m src.mlops_report

readiness-check:
> $(PYTHON) -m src.readiness_check

destroy-endpoint:
> $(PYTHON) -m src.cleanup_endpoint

destroy-monitoring:
> $(PYTHON) -m src.cleanup_monitoring

destroy-feedback-loop:
> $(PYTHON) -m src.cleanup_feedback_loop

destroy-local-plan:
> $(PYTHON) -m src.cleanup_local_outputs

destroy-local:
> $(PYTHON) -m src.cleanup_local_outputs --execute

destroy-all:
> $(PYTHON) -m src.cleanup_all

test:
> $(PYTHON) -m pytest tests

step-00:
> $(PYTHON) -m src.lab_runner step 00

step-01:
> $(PYTHON) -m src.lab_runner step 01

step-02:
> $(PYTHON) -m src.lab_runner step 02

step-03:
> $(PYTHON) -m src.lab_runner step 03

step-04:
> $(PYTHON) -m src.lab_runner step 04

step-05:
> $(PYTHON) -m src.lab_runner step 05

step-06:
> $(PYTHON) -m src.lab_runner step 06

step-07:
> $(PYTHON) -m src.lab_runner step 07

step-08:
> $(PYTHON) -m src.lab_runner step 08

step-09:
> $(PYTHON) -m src.lab_runner step 09

step-10:
> $(PYTHON) -m src.lab_runner step 10

step-11:
> $(PYTHON) -m src.lab_runner step 11

step-12:
> $(PYTHON) -m src.lab_runner step 12

step-13:
> $(PYTHON) -m src.lab_runner step 13

step-14:
> $(PYTHON) -m src.lab_runner step 14
