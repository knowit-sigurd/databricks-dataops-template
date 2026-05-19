.PHONY: lint test pipeline-run should-deploy deploy-dev deploy-pr destroy-pr deploy-prod run-dev run-pr run-prod upload-sample-data-dev upload-sample-data-pr upload-sample-data-prod

PIPELINE_PYTHON := $(shell pwd)/.venv/bin/python3
PIPELINE_RUNNER := $(shell pwd)/.venv/bin/spark-pipelines

lint:
	uv run ruff check src/ tests/

test:
	uv run pytest tests/

pipeline-run:
	PYSPARK_DRIVER_PYTHON=$(PIPELINE_PYTHON) PYSPARK_PYTHON=$(PIPELINE_PYTHON) PYTHONPATH=$(shell pwd)/src \
		$(PIPELINE_RUNNER) run --spec local-dev/$(PIPELINE).yml

should-deploy:
	uv run python scripts/changed_files.py

upload-sample-data-dev:
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/dev/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/dev/orders_raw/ --overwrite

upload-sample-data-pr:
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/pr_$(PR_NUMBER)/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/pr_$(PR_NUMBER)/orders_raw/ --overwrite

upload-sample-data-prod:
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/prod/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/prod/orders_raw/ --overwrite

deploy-dev:
	databricks bundle deploy --target dev

deploy-pr:
	databricks bundle deploy --target pr --var target_schema=pr_$(PR_NUMBER)

destroy-pr:
	databricks bundle destroy --target pr --var target_schema=pr_$(PR_NUMBER) --auto-approve

deploy-prod:
	databricks bundle deploy --target prod --var sp_client_id=$(DATABRICKS_SP_CLIENT_ID)

run-dev:
	databricks bundle run --target dev data_product_operational_job

run-pr:
	databricks bundle run --target pr --var target_schema=pr_$(PR_NUMBER) data_product_operational_job

run-prod:
	databricks bundle run --target prod --var sp_client_id=$(DATABRICKS_SP_CLIENT_ID) data_product_operational_job
