# CLAUDE.md — databricks-dataops-template

## What this repo is

An opinionated Databricks DataOps starter template for one production-style data product. Client-facing starting point — not a learning artifact. Clean, no milestone history, no lab-specific config.

Successor to `databricks-dataops-lakeflow-reference` (reference/learning repo). Proven patterns carried forward; milestone ceremony and learning log left behind.

Current build: **Pass 2** (Pass 1 complete and validated on Databricks dev + prod 2026-05-18).

## Locked-in architecture decisions

Do not propose alternatives to these.

**Three separate SDP pipeline resources + one Lakeflow Job:**
- `customers_pipeline` — bronze (Auto Loader) + silver + rejected
- `orders_pipeline` — bronze (Auto Loader) + silver + rejected
- `gold_pipeline` — `@dp.materialized_view`, reads published silver UC tables via `spark.read.table()`
- `data_product_operational_job` — DAG: `[run_customers, run_orders] → validate_silver_readiness → run_gold → validate_gold_contract`

**`src/` package pattern** — business logic in pure PySpark under `domains/{domain}/transformations.py` and `domains/{domain}/rules.py`. Pipeline files are thin DLT wrappers only. Tests never import from pipeline files. This enables real local Spark testing in devcontainer.

**Serverless compute everywhere.** No `node_type_id`, no `aws_attributes`, no instance pools.

**UC Volumes for all data paths.** No `s3://` or `abfss://` in pipeline code. All paths via `/Volumes/{catalog}/{schema}/...`.

**`from pyspark import pipelines as dp`** — the canonical import alias. Never `import dlt` (legacy). Never `import pyspark.pipelines as dlt` (non-standard). Confirmed working on runtime dlt:17.3.10.

**Pipeline library type is `file:`, not `notebook:`** — `.py` source files in pipeline resources use `libraries: - file: path: ...`. `notebook:` expects an `.ipynb` or Databricks notebook format and will reject plain Python files.

**`environment.dependencies: - --editable ${workspace.file_path}`** on every pipeline resource — makes the `data_product` package importable in the DLT runtime. DABs uploads the source tree to `${workspace.file_path}` on deploy; the editable install reads the package from there. No wheel build required. Requires `[build-system]` (hatchling) in `pyproject.toml` and `[tool.hatch.build.targets.wheel] packages = ["src/data_product"]`.

**`@dp.table` stubs use a rate stream filtered to zero rows** — `createDataFrame()` returns a batch relation which DLT rejects for streaming tables. Pattern:
```python
spark.readStream.format("rate").load()
    .where(F.lit(False))
    .select([F.lit(None).cast(f.dataType).alias(f.name) for f in SCHEMA])
```

**`@dp.materialized_view` stubs use `createDataFrame([], schema)`** — materialized views are batch; `createDataFrame` is correct and does not hang.

**`SparkSession.getActiveSession()`** instead of the `spark` global — the global is injected by the DLT runtime but is not available in the local `spark-pipelines` runner.

**`pipelines.catalog` and `pipelines.target` are DLT built-in conf keys** — set from the pipeline spec's `catalog:` and `target:` fields before any user function runs. Use these to derive source paths and cross-pipeline table references in `@dp.table` and `@dp.materialized_view` functions. Custom `configuration:` block keys (e.g. `pipelines.target_schema`) are NOT available during the DLT analysis/planning phase — only during execution, after the DAG is already resolved. `spark.catalog.currentCatalog()` is blocked by the Py4J security whitelist. `spark.sql("SELECT current_catalog()")` returns `hive_metastore` during analysis. Use `spark.conf.get("pipelines.catalog")` and `spark.conf.get("pipelines.target")` instead. Local-dev overrides via `spark.conf.get("pipelines.customers_source_path", None)` still work because the `spark-pipelines` runner injects those keys normally.

**Validate scripts are notebook tasks with relative paths** — `validate_silver_readiness.py` and `validate_gold_contract.py` must have `# Databricks notebook source` as their first line, and the job resource must reference them with a relative path (e.g. `../src/data_product/pipelines/validate_silver_readiness.py`) without `source: WORKSPACE`. Relative paths cause DABs to import via the Workspace Notebook Import API. Absolute `${workspace.root_path}/files/...` paths point to files stored via the Workspace Files API — a different storage mechanism, not accessible to `notebook_task`.

**`bundle run` re-validates the full bundle config** — variables used in `run_as` (e.g. `sp_client_id`) must be passed to both `bundle deploy` and `bundle run`. The Makefile prod run target must include `--var sp_client_id=$(DATABRICKS_SP_CLIENT_ID)`.

**`${var.catalog}` everywhere.** Default `dataops_template`. No hardcoded catalog name.

**Three targets:** `dev`, `pr`, `prod`. PR schema: `pr_${PR_NUMBER}`. Per-PR `root_path` isolation is non-negotiable.

**CI/CD dual target from day one:** `.github/workflows/` (GitHub Actions) + `ci/` (Azure DevOps). Pass 1 and 2: `ci/` is a README placeholder only — no non-working ADO YAML.

**Makefile-first.** All CI logic lives in Makefile targets. CI YAML files call `make`. No inline shell logic in CI YAML.

**`run_as` in prod target only.** Uses SP application UUID (`${var.sp_client_id}`), not display name. Never set in dev or pr — it cannot be removed once set on a pipeline.

**Ops tables are target-scoped (MVP).** `${catalog}.${target_schema}.ops_pipeline_run_log` and `ops_contract_check_log`. Not a shared `ops` schema — that is Phase 4.

## Code conventions

- Explicit `StructType` for all bronze schemas — no schema inference
- `DecimalType(10, 2)` for all monetary amounts
- `_metadata.file_path` for source file tracking (`input_file_name()` is blocked in Unity Catalog)
- `_ingested_at` (`current_timestamp()`) on all bronze tables
- Gold join is LEFT on `customer_id` — inner join silently drops customers with no orders
- `quality_mode` conf variable: `drop` (dev/PR) → `expect_or_drop`; `fail` (prod) → `expect_or_fail` for `business_invalid` rules
- `critical` rules always use `expect_or_fail` regardless of `quality_mode`
- `warning` rules always use `expect` regardless of `quality_mode`
- `presets.tags` in `databricks.yml` — not per-resource `tags:` blocks
- DAB Python mutators for stable deploy-time tags only (not `deployed_at` by default — creates noisy diffs on every deploy)
- `python.mutators` at top level (not `bundle.mutators`), format `module:object_name` (e.g. `mutators.tags:tag_pipeline`)

## Local dev workflow

`make pipeline-run PIPELINE=<name>` runs a pipeline locally in the devcontainer using `spark-pipelines`. Specs live in `local-dev/<name>.yml`. The package is made available via `PYTHONPATH=$(pwd)/src` — no editable install needed locally.

**Verify locally before committing.** For any pipeline or job change, run `make pipeline-run`, `make lint`, and `make test` and confirm they pass before writing a commit. Do not rely on Databricks CI as the feedback loop — each round-trip is slow. The exception is Databricks-specific behaviour (UC permissions, notebook Import API vs Files API) that cannot be caught locally.

## Test conventions

- `conftest.py` at repo root, session-scoped `SparkSession`, `local[1]`
- Tests cover transformation logic only — never pipeline entrypoints
- Never mock the SparkSession — run real local Spark against fixture DataFrames
- Test the full severity matrix per domain: critical fails, business_invalid drops, warning passes
- Do not test `@dp.table`, `@dp.expect_or_fail` decorators — they require DLT runtime

## CI/CD conventions

- `cancel-in-progress: false` on deploy jobs — Databricks deploys are stateful; new pushes queue, never interrupt
- `git checkout -B ${{ github.head_ref || github.ref_name }}` after `actions/checkout` — detached HEAD produces empty `${bundle.git.branch}`
- Docs-only deploy skip covers: `docs/**`, `README.md`, `.github/PULL_REQUEST_TEMPLATE.md` only
- `github.actor != 'dependabot[bot]'` condition on all deploy jobs — add from day one
- PR deploy order: destroy → orphan cleanup → schema → volume → upload → bundle deploy → run → validate

## What is out of scope (MVP)

Column masks, row filters, multi-workspace staging, shared ops schema, CDC (`apply_changes()`), push-based alerting, schema registry, third domain (unless it demonstrates a new pattern). Do not propose these for MVP work.

## event_log() access rule

`event_log('<pipeline_id>')` requires pipeline **ownership**, not just `CAN_VIEW`. The PERMISSION_DENIED error message is misleading (mentions cluster type — irrelevant). CI service principal owns prod pipelines. Human users cannot query prod event log directly. The bridge: `validate_silver_readiness` and `validate_gold_contract` tasks run as the CI SP, pull from `event_log()`, and write to ops tables that human users can be granted SELECT on.
