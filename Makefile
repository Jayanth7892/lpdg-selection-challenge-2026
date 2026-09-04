.PHONY: run validate charts bootstrap live-session docker-build docker-run clean help

PYTHON ?= python

help:
	@echo "LPDG Gateway Prediction Service (Track D: Data Science)"
	@echo "Targets:"
	@echo "  make run          - Run prediction pipeline and write predictions.csv"
	@echo "  make validate     - Validate generated predictions.csv"
	@echo "  make charts       - Generate visual plots in reports/charts/"
	@echo "  make bootstrap    - Run 1,000-sample bootstrap uncertainty simulation"
	@echo "  make live-session - Run threshold adjustment sensitivity demo"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run pipeline inside Docker container"

run:
	$(PYTHON) run.py --data data --out predictions.csv

validate:
	$(PYTHON) validate_submission.py predictions.csv

charts:
	$(PYTHON) -m src.data_science.generate_charts

bootstrap:
	$(PYTHON) -m src.data_science.bootstrap --iterations 1000

live-session:
	$(PYTHON) -m src.data_science.cost_model --threshold 0.65 --step 0.10

docker-build:
	docker compose build

docker-run:
	docker compose up --abort-on-container-exit

clean:
	rm -rf __pycache__ src/__pycache__ src/data_science/__pycache__ .pytest_cache
