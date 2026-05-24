PYTHON ?= python
UVICORN ?= uvicorn

.PHONY: help data prepare train evaluate batch monitor model-card all api test clean

help:
	@echo "Targets:"
	@echo "  make data        Generate synthetic raw data"
	@echo "  make prepare     Prepare features and train/test split"
	@echo "  make train       Train local fraud model"
	@echo "  make evaluate    Evaluate model"
	@echo "  make batch       Run batch inference"
	@echo "  make monitor     Run monitoring simulation"
	@echo "  make model-card  Generate governance model card"
	@echo "  make all         Run full pipeline"
	@echo "  make api         Start FastAPI app"
	@echo "  make test        Run pytest"
	@echo "  make clean       Remove generated data/artifacts/caches"

data:
	$(PYTHON) -m src.generate_dataset

prepare:
	$(PYTHON) -m src.data_preparation

train:
	$(PYTHON) -m src.train

evaluate:
	$(PYTHON) -m src.evaluate

batch:
	$(PYTHON) -m src.batch_inference

monitor:
	$(PYTHON) -m src.monitor

model-card:
	$(PYTHON) -m src.model_card

all: data prepare train evaluate batch monitor model-card

api:
	$(UVICORN) src.api.main:app --reload

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) scripts/clean_generated.py
