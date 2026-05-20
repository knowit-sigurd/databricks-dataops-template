# Setup

Onboarding a data engineering team member onto this repo.

## Prerequisites

Before starting:
- Docker Desktop installed and running
- VS Code with the Dev Containers extension
- Access to the Databricks workspace
- A Databricks PAT or OAuth credential in `~/.databrickscfg`

Platform-level prerequisites (workspace, catalog, UC Volumes) are in [platform-prerequisites.md](platform-prerequisites.md).

## 1. Clone and open the devcontainer

```bash
git clone <repo-url>
cd databricks-dataops-template
code .
# VS Code: "Reopen in Container"
```

The devcontainer installs:
- Python 3.12 with PySpark 4.1.1 (via uv)
- Spark 4.1.1 binaries (for local tests)
- Databricks CLI
- GitHub CLI (`gh`)

On first open, `uv sync` runs automatically. The `.venv` is activated in every new terminal.

## 2. Verify Databricks CLI

```bash
databricks auth describe
```

Expected: your workspace URL and username. If it fails, check `~/.databrickscfg`:

```ini
[DEFAULT]
host       = https://<workspace>.cloud.databricks.com   # or azuredatabricks.net
client_id  = <service-principal-client-id>
client_secret = <service-principal-client-secret>
```

The devcontainer mounts `~/.databrickscfg` from the host — configure it on the host, not inside the container. Adjust the profile name to match your `DATABRICKS_CONFIG_PROFILE` env var, or use `[DEFAULT]`.

## 3. Run the tests

```bash
make test
```

This runs pytest against local Spark (`local[1]`). No Databricks connection required. Expected: all tests pass.

## 4. Deploy to dev

```bash
make deploy-dev
```

This runs `databricks bundle deploy --target dev`. The bundle is deployed to `~/databricks-dataops-template/dev/<branch>` in the workspace.

Verify in the Databricks UI: Workflows → the three pipelines and the operational job should appear under your dev schema.

## 5. Run the operational job

```bash
make run-dev
```

## Makefile reference

| Target | What it does |
|---|---|
| `make lint` | `ruff check src/ tests/` |
| `make test` | `pytest tests/` |
| `make deploy-dev` | Bundle deploy to `dev` target |
| `make deploy-pr PR_NUMBER=<N>` | Bundle deploy to `pr` target, schema `pr_<N>` |
| `make destroy-pr PR_NUMBER=<N>` | Destroy `pr` target deployment |
| `make deploy-prod` | Bundle deploy to `prod` target (requires `DATABRICKS_SP_CLIENT_ID`) |
| `make run-dev` | Run `data_product_operational_job` in `dev` |
| `make run-pr PR_NUMBER=<N>` | Run job in `pr` target |
| `make run-prod` | Run job in `prod` |

## Without the devcontainer

If you prefer a local Python environment:

```bash
pip install uv
uv sync
source .venv/bin/activate
```

You need Java 11+ on your PATH for local Spark tests to run. The devcontainer handles this automatically.

---

## Forking this template

When adapting this template for a client data product, work through this checklist in order. The sample product uses `customers` and `orders` as domains and `dataops_template` as the catalog — replace these with the actual names throughout.

### 1. Bundle identity

- [ ] `databricks.yml` — rename `bundle.name` (used in workspace `root_path` and resource name prefixes)
- [ ] `databricks.yml` — update `workspace.root_path` paths to use the new bundle name
- [ ] `databricks.yml` — update `presets.tags.project` to match the new bundle name
- [ ] `platform/databricks.yml` — rename `bundle.name` if using the platform bundle

### 2. Catalog and schemas

- [ ] `databricks.yml` — update the `catalog` variable default from `dataops_template` to the client catalog name
- [ ] Verify `dev`, `pr_<N>`, and `prod` schema names are acceptable — or adjust `target_schema` defaults per target
- [ ] Update the external location in UC to cover the new catalog/schema paths (see [platform-prerequisites.md](platform-prerequisites.md))

### 3. Domains

For each domain being replaced or added:

- [ ] Create `src/data_product/domains/<domain>/transformations.py` and `rules.py`
- [ ] Create `src/data_product/pipelines/<domain>_pipeline.py`
- [ ] Add `resources/<domain>_pipeline.yml` — update pipeline name, source path, library path
- [ ] Add `resources/volumes.yml` entry for the domain's landing volume
- [ ] Wire `run_<domain>` task into `resources/data_product_operational_job.yml`
- [ ] Add Makefile upload targets: `upload-sample-data-dev`, `upload-sample-data-pr` for the new volume
- [ ] Add `data/sample/<domain>/` fixture files for local and PR testing
- [ ] Add tests under `tests/domains/<domain>/`
- [ ] Remove the sample `customers` and `orders` domains once replaced

### 4. CI/CD and access

- [ ] GitHub secrets (or ADO variable group) — set `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_SP_CLIENT_ID` for the client workspace
- [ ] Replace `data-operators` group name in all resource YAMLs (`customers_pipeline.yml`, `orders_pipeline.yml`, `gold_pipeline.yml`, `data_product_operational_job.yml`) with the client's actual Databricks account group
- [ ] Create or verify the prod run-as SP owns prod pipelines and job (required for `event_log()` access)
- [ ] Grant `SELECT` on ops tables to the operators group

### 5. Docs

- [ ] `README.md` — update the "What this is" description for the actual data product
- [ ] `docs/architecture.md` — update the data flow diagram with real domain and table names
- [ ] `docs/runbook.md` — update SQL examples with the actual catalog and schema names
