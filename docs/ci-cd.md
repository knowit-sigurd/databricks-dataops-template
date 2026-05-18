# CI/CD

## Overview

All CI logic lives in `Makefile` targets. CI YAML files call `make` — no inline shell logic in YAML.

Two workflows are active:

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | PR against `main` | Lint → test → deploy PR environment → run job |
| `.github/workflows/cd.yml` | Push to `main` | Deploy prod → run job |

Azure DevOps pipeline definitions are planned for a future pass. See [Azure DevOps](#azure-devops) below.

---

## GitHub Actions

### Secrets

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Used by | Description |
|---|---|---|
| `DATABRICKS_HOST` | `ci.yml`, `cd.yml` | Workspace URL, e.g. `https://dbc-xxx.cloud.databricks.com` |
| `DATABRICKS_CLIENT_ID` | `ci.yml`, `cd.yml` | Service principal application (client) ID — OAuth M2M |
| `DATABRICKS_CLIENT_SECRET` | `ci.yml`, `cd.yml` | Service principal client secret — OAuth M2M |
| `DATABRICKS_SP_CLIENT_ID` | `cd.yml` | SP application UUID for `prod` `run_as` (may be the same SP) |

### CI workflow (`ci.yml`)

Runs on every PR against `main`.

**`lint-test` job:**
1. `actions/checkout@v4`
2. `git checkout -B ${{ github.head_ref }}` — fixes detached HEAD so `${bundle.git.branch}` is populated
3. `uv sync`
4. `make lint`
5. `make test`

**`deploy-pr` job** (runs after `lint-test`, skipped for Dependabot):
1. Destroy any previous deployment for this PR (`make destroy-pr`, `continue-on-error: true`)
2. Deploy: `make deploy-pr PR_NUMBER=<N>`
3. Run: `make run-pr PR_NUMBER=<N>`

The PR schema is `pr_<N>` — fully isolated from dev and from other open PRs. The bundle `root_path` includes `${bundle.git.branch}`, providing workspace-level isolation too.

`concurrency.cancel-in-progress: false` — Databricks deploys are stateful. If two pushes land quickly, the second deploy queues rather than interrupting the first.

> **Pass 1 stub.** The full PR deploy order (destroy → orphan cleanup → schema → volume → upload → bundle deploy → run → validate) is implemented in Pass 2. Currently: destroy → bundle deploy → run.

### CD workflow (`cd.yml`)

Runs on push to `main`. Skipped for docs-only changes (`docs/**`, `README.md`, `.github/PULL_REQUEST_TEMPLATE.md`).

1. `make deploy-prod` — passes `DATABRICKS_SP_CLIENT_ID` as `--var sp_client_id=...`
2. `make run-prod`

`concurrency.group: deploy-prod` with `cancel-in-progress: false` — prod deploys never interrupt each other.

### Dependabot

`.github/dependabot.yml` configures monthly updates for GitHub Actions and pip dependencies. All deploy jobs include `if: github.actor != 'dependabot[bot]'` — Dependabot PRs run lint and tests only, never deploy.

---

## Azure DevOps

> **Placeholder — planned for a future pass.**

All CI logic is in `Makefile` targets. When ADO pipelines are added, they will call `make` the same way GitHub Actions does. No pipeline logic will be duplicated.

When implemented, the ADO setup will require:

- A service connection to the Databricks workspace
- A variable group with `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_SP_CLIENT_ID`
- Pipeline YAML files in `ci/`

See `ci/README.md` for the current placeholder.

---

## Deploy order (PR target, Pass 2)

The full PR deploy sequence once Pass 2 is complete:

1. **Destroy** — `databricks bundle destroy --target pr` (removes stale pipeline/job definitions)
2. **Orphan cleanup** — remove schemas/volumes from closed PRs (Pass 2 script)
3. **Schema** — create `pr_<N>` schema in UC
4. **Volume** — create landing volume under the schema
5. **Upload** — upload fixture/seed data to the volume
6. **Bundle deploy** — `databricks bundle deploy --target pr --var target_schema=pr_<N>`
7. **Run** — `databricks bundle run data_product_operational_job`
8. **Validate** — check ops tables for pass/fail status
