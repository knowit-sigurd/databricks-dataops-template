.PHONY: lint test deploy-dev deploy-pr destroy-pr deploy-prod run-dev run-pr run-prod

lint:
	uv run ruff check src/ tests/

test:
	uv run pytest tests/

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
	databricks bundle run --target prod data_product_operational_job
