# Runbook

Day-to-day operational reference.

## Deploy commands

```bash
# Dev
make deploy-dev
make run-dev

# PR environment (replace 42 with your PR number)
make deploy-pr PR_NUMBER=42
make run-pr PR_NUMBER=42
make destroy-pr PR_NUMBER=42

# Prod (requires DATABRICKS_SP_CLIENT_ID in env)
make deploy-prod
make run-prod
```

All targets call the Databricks CLI. Authentication comes from `~/.databrickscfg` or the `DATABRICKS_HOST` / `DATABRICKS_TOKEN` env vars.

## Check what's deployed

```bash
databricks bundle summary --target dev
databricks bundle summary --target pr --var target_schema=pr_42
databricks bundle summary --target prod
```

## Destroy a PR environment

PR environments are destroyed automatically when a PR is merged or closed (CI `destroy-pr` step). To destroy manually:

```bash
make destroy-pr PR_NUMBER=42
```

This calls `databricks bundle destroy` with `--auto-approve`. It removes the pipeline and job definitions from the workspace but does not drop the UC schema or tables.

> **Pass 2:** Schema and table cleanup will be handled by the orphan cleanup script.

## Monitoring pipeline runs

Pipeline run history is visible in the Databricks UI under **Delta Live Tables**. Filter by catalog `dataops_template` and schema `dev` / `pr_<N>` / `prod`.

Ops tables (written by the validate tasks) are queryable once Pass 2 is complete:

```sql
SELECT * FROM dataops_template.prod.ops_pipeline_run_log ORDER BY run_id DESC LIMIT 20;
SELECT * FROM dataops_template.prod.ops_contract_check_log ORDER BY checked_at DESC LIMIT 20;
```

> **Pass 2 stub.** These tables do not exist yet. The validate task scripts are stubs.

## event_log() access

`event_log('<pipeline_id>')` requires **pipeline ownership**, not just `CAN_VIEW`. The error message mentions cluster type — that is misleading and irrelevant.

- In **dev/PR**: the person who deployed owns the pipeline. You can query `event_log()` directly if you deployed.
- In **prod**: the CI service principal owns all prod pipelines. Human users cannot query `event_log()` directly.

The bridge for prod: `validate_silver_readiness` and `validate_gold_contract` run as the CI SP (via `run_as` at the prod target level). They pull from `event_log()` and write results to the ops tables. Grant humans `SELECT` on the ops tables — not on `event_log()`.

## Re-running a failed job

```bash
# Re-run the entire operational job from the beginning
make run-prod

# To re-run a single task, use the Databricks UI or CLI:
databricks jobs run-now --job-id <job-id> --only run_gold
```

## Prod rollback

There is no automated rollback. To redeploy a previous version:

```bash
git checkout <previous-sha>
make deploy-prod
make run-prod
```

The previous pipeline and job definitions are redeployed. Existing tables are not affected by the redeploy — only the pipeline logic changes.

## Adding a new domain

Not in scope for MVP. A third domain is only added if it demonstrates a new pattern not covered by customers or orders.

If adding one:
1. Create `src/data_product/domains/<domain>/transformations.py` and `rules.py`
2. Create `src/data_product/pipelines/<domain>_pipeline.py`
3. Add `resources/<domain>_pipeline.yml`
4. Wire `run_<domain>` into the job DAG in `resources/data_product_operational_job.yml`
5. Add tests under `tests/domains/<domain>/`
