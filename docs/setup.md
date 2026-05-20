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
