# databricks-dataops-template

Opinionated Databricks DataOps starter template for one production-style data product. Client-facing — not a learning artifact.

## Documentation

| Doc | Purpose |
|---|---|
| [Architecture](docs/architecture.md) | Pipeline design, quality model, key decisions |
| [Platform prerequisites](docs/platform-prerequisites.md) | What must exist in the workspace before first deploy |
| [Setup](docs/setup.md) | Onboarding a data engineering team member |
| [CI/CD](docs/ci-cd.md) | GitHub Actions and Azure DevOps pipeline reference |
| [Runbook](docs/runbook.md) | Day-to-day operational commands |
| [Patterns: CDC](docs/patterns/cdc.md) | Why CDC is out of scope and what to do when it isn't |

## What this is

Three SDP pipeline resources feeding a Lakeflow orchestration job, deployed via Databricks Asset Bundles to three isolated targets (`dev`, `pr`, `prod`). Business logic lives in pure PySpark under `src/` and is unit-tested locally — pipeline files are thin wrappers.

**Current build: Pass 2 — Working vertical slice.** Full domain logic, pipelines, validate scripts, and CI/CD verified end-to-end on GitHub Actions + Databricks.

## Quick start

```bash
# 1. Open in devcontainer (see docs/setup.md)
# 2. Configure Databricks CLI
# 3. Deploy and run:
make test        # unit tests against local Spark
make deploy-dev  # deploy bundle to dev target
make run-dev     # run data_product_operational_job in dev
```

## Repo layout

```
databricks.yml                    bundle definition, variables, targets
Makefile                          all CI logic lives here
resources/                        pipeline and job resource YAML
src/data_product/
  domains/{customers,orders,gold}/
    transformations.py            pure PySpark business logic
    rules.py                      quality rule definitions
  pipelines/                      thin DLT wrappers + notebook tasks
mutators/tags.py                  DAB Python mutator — stamps git_sha
tests/                            unit tests (never import pipeline files)
.github/workflows/                GitHub Actions CI/CD
ci/                               Azure DevOps — planned for a future pass
docs/                             this documentation
```

## Requirements

- Databricks workspace with Unity Catalog — see [platform prerequisites](docs/platform-prerequisites.md)
- Databricks CLI configured (`~/.databrickscfg`) — see [setup](docs/setup.md)
- GitHub secrets `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_SP_CLIENT_ID` — see [CI/CD](docs/ci-cd.md)
