.PHONY: run validate docker-build docker-run clean help

PYTHON ?= python

help:
	@echo "LPDG Gateway Prediction Service"
	@echo "Targets:"
	@echo "  make run          - Run prediction pipeline locally"
	@echo "  make validate     - Validate generated predictions.csv"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run pipeline inside Docker container"

run:
	$(PYTHON) run.py --data data --out predictions.csv

validate:
	$(PYTHON) validate_submission.py predictions.csv

docker-build:
	docker compose build

docker-run:
	docker compose up --abort-on-container-exit

clean:
	rm -rf __pycache__ src/__pycache__ .pytest_cache
