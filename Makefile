.PHONY: help lint test pipeline-run should-deploy deploy-dev deploy-pr destroy-pr deploy-prod run-dev run-pr run-prod upload-sample-data-dev upload-sample-data-pr upload-sample-data-prod create-schema-pr create-schema-prod dashboard-export

-include .env
export

PIPELINE_PYTHON := $(shell pwd)/.venv/bin/python3
PIPELINE_RUNNER := $(shell pwd)/.venv/bin/spark-pipelines

help:
	@echo "Usage: make <target> [VARIABLE=value ...]"
	@echo ""
	@echo "Development"
	@echo "  lint                          Run ruff linter"
	@echo "  test                          Run pytest against local Spark"
	@echo "  pipeline-run PIPELINE=<name>  Run a pipeline locally via spark-pipelines"
	@echo "  should-deploy                 Print true/false based on changed files (requires CI_PROVIDER)"
	@echo "  dashboard-export DASHBOARD_ID=<id>  Export published dashboard back to repo JSON"
	@echo ""
	@echo "Dev target  (requires DATABRICKS_WAREHOUSE_ID=<id>)"
	@echo "  deploy-dev                    Bundle deploy to dev target"
	@echo "  run-dev                       Run operational job in dev"
	@echo "  upload-sample-data-dev        Upload sample fixtures to dev UC Volume"
	@echo ""
	@echo "PR target  (requires PR_NUMBER=<n>)"
	@echo "  create-schema-pr              Create pr_<N> schema in UC"
	@echo "  deploy-pr                     Bundle deploy to pr target"
	@echo "  run-pr                        Run operational job in pr target"
	@echo "  upload-sample-data-pr         Upload sample fixtures to pr UC Volume"
	@echo "  destroy-pr                    Destroy pr bundle, volumes, and schema"
	@echo ""
	@echo "Prod target  (requires DATABRICKS_SP_CLIENT_ID=<uuid> DATABRICKS_WAREHOUSE_ID=<id>)"
	@echo "  create-schema-prod            Create prod schema in UC"
	@echo "  deploy-prod                   Bundle deploy to prod target"
	@echo "  run-prod                      Run operational job in prod"
	@echo ""
	@echo "Platform bundle  (run from platform/ directory)"
	@echo "  See platform/README.md"

lint:
	uv run ruff check src/ tests/

test:
	uv run pytest tests/

pipeline-run:
ifndef PIPELINE
	$(error PIPELINE is required. Usage: make pipeline-run PIPELINE=<name>)
endif
	PYSPARK_DRIVER_PYTHON=$(PIPELINE_PYTHON) PYSPARK_PYTHON=$(PIPELINE_PYTHON) PYTHONPATH=$(shell pwd)/src \
		$(PIPELINE_RUNNER) run --spec local-dev/$(PIPELINE).yml

should-deploy:
	@uv run python scripts/changed_files.py

dashboard-export:
ifndef DASHBOARD_ID
	$(error DASHBOARD_ID is required. Find it in the dashboard URL, or: databricks lakeview list | jq -r '.[] | [.dashboard_id, .display_name] | @tsv')
endif
	databricks lakeview get $(DASHBOARD_ID) \
		| jq -r '.serialized_dashboard' \
		> dashboards/data_product_operations.lvdash.json
	@echo "Exported → dashboards/data_product_operations.lvdash.json"

create-schema-pr:
ifndef PR_NUMBER
	$(error PR_NUMBER is required. Usage: make create-schema-pr PR_NUMBER=42)
endif
	databricks schemas create pr_$(PR_NUMBER) $(CATALOG) || true

create-schema-prod:
	databricks schemas create prod $(CATALOG) || true

upload-sample-data-dev:
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/dev/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/dev/orders_raw/ --overwrite

upload-sample-data-pr:
ifndef PR_NUMBER
	$(error PR_NUMBER is required. Usage: make upload-sample-data-pr PR_NUMBER=42)
endif
	$(MAKE) create-schema-pr
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/pr_$(PR_NUMBER)/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/pr_$(PR_NUMBER)/orders_raw/ --overwrite

upload-sample-data-prod:
	databricks fs cp --recursive data/sample/customers/ dbfs:/Volumes/$(CATALOG)/prod/customers_raw/ --overwrite
	databricks fs cp --recursive data/sample/orders/ dbfs:/Volumes/$(CATALOG)/prod/orders_raw/ --overwrite

deploy-dev:
ifndef DATABRICKS_WAREHOUSE_ID
	$(error DATABRICKS_WAREHOUSE_ID is required. Usage: make deploy-dev DATABRICKS_WAREHOUSE_ID=<id>)
endif
	databricks bundle deploy --target dev --var dashboard_warehouse_id=$(DATABRICKS_WAREHOUSE_ID) --force

deploy-pr:
ifndef PR_NUMBER
	$(error PR_NUMBER is required. Usage: make deploy-pr PR_NUMBER=42)
endif
	databricks bundle deploy --target pr --var target_schema=pr_$(PR_NUMBER)

destroy-pr:
ifndef PR_NUMBER
	$(error PR_NUMBER is required. Usage: make destroy-pr PR_NUMBER=42)
endif
	databricks bundle destroy --target pr --var target_schema=pr_$(PR_NUMBER) --auto-approve
	databricks volumes delete $(CATALOG).pr_$(PR_NUMBER).customers_raw || true
	databricks volumes delete $(CATALOG).pr_$(PR_NUMBER).orders_raw || true
	databricks schemas delete $(CATALOG).pr_$(PR_NUMBER) --force || true

deploy-prod:
ifndef DATABRICKS_SP_CLIENT_ID
	$(error DATABRICKS_SP_CLIENT_ID is required. Usage: make deploy-prod DATABRICKS_SP_CLIENT_ID=<uuid>)
endif
ifndef DATABRICKS_WAREHOUSE_ID
	$(error DATABRICKS_WAREHOUSE_ID is required. Usage: make deploy-prod DATABRICKS_SP_CLIENT_ID=<uuid> DATABRICKS_WAREHOUSE_ID=<id>)
endif
	databricks bundle deploy --target prod --var sp_client_id=$(DATABRICKS_SP_CLIENT_ID) --var dashboard_warehouse_id=$(DATABRICKS_WAREHOUSE_ID) --force

run-dev:
	databricks bundle run --target dev data_product_operational_job

run-pr:
ifndef PR_NUMBER
	$(error PR_NUMBER is required. Usage: make run-pr PR_NUMBER=42)
endif
	databricks bundle run --target pr --var target_schema=pr_$(PR_NUMBER) data_product_operational_job

run-prod:
ifndef DATABRICKS_SP_CLIENT_ID
	$(error DATABRICKS_SP_CLIENT_ID is required. Usage: make run-prod DATABRICKS_SP_CLIENT_ID=<uuid>)
endif
ifndef DATABRICKS_WAREHOUSE_ID
	$(error DATABRICKS_WAREHOUSE_ID is required. Usage: make run-prod DATABRICKS_SP_CLIENT_ID=<uuid> DATABRICKS_WAREHOUSE_ID=<id>)
endif
	databricks bundle run --target prod --var sp_client_id=$(DATABRICKS_SP_CLIENT_ID) --var dashboard_warehouse_id=$(DATABRICKS_WAREHOUSE_ID) data_product_operational_job
