# CI/CD

## Overview

All CI logic lives in `Makefile` targets. CI YAML files call `make` — no inline shell logic in YAML.

Two CI platforms are supported. GitHub Actions pipelines are live; Azure DevOps pipeline YAML is deferred until the PathfinderAnalytics workspace is available for end-to-end verification.

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | PR against `main` | Lint → test → deploy PR environment → run job |
| `.github/workflows/cd.yml` | Push to `main` | Deploy prod → run job |
| `ci/ci.yml` *(ADO, deferred)* | PR against `main` | Same as above via `make` |
| `ci/deploy.yml` *(ADO, deferred)* | Push to `main` | Same as above via `make` |

---

## GitHub Actions

### Secrets

Configure in **Settings → Secrets and variables → Actions**:

| Secret | Used by | Description |
|---|---|---|
| `DATABRICKS_HOST` | `ci.yml`, `cd.yml` | Workspace URL, e.g. `https://dbc-xxx.cloud.databricks.com` |
| `DATABRICKS_CLIENT_ID` | `ci.yml`, `cd.yml` | Service principal application (client) ID — OAuth M2M |
| `DATABRICKS_CLIENT_SECRET` | `ci.yml`, `cd.yml` | Service principal client secret — OAuth M2M |
| `DATABRICKS_SP_CLIENT_ID` | `cd.yml` | SP application UUID for `prod` `run_as` (may be the same SP) |

OIDC (GitHub's `id-token: write` + Databricks workload identity federation) is preferred over OAuth M2M for new setups — eliminates the long-lived client secret. OAuth M2M is the fallback if OIDC federation is not configured.

### PR number and branch name

| Value | Expression |
|---|---|
| PR number | `${{ github.event.number }}` |
| Branch name | `${{ github.head_ref \|\| github.ref_name }}` |

`git checkout -B ${{ github.head_ref || github.ref_name }}` is required after `actions/checkout` — the default checkout leaves a detached HEAD, which causes `${bundle.git.branch}` to be empty.

### Changed-file detection

```yaml
- run: |
    echo "SHOULD_DEPLOY=$(CI_PROVIDER=github PR_NUMBER=${{ github.event.number }} \
      GITHUB_REPOSITORY=${{ github.repository }} GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }} \
      uv run python scripts/changed_files.py)" >> $GITHUB_ENV
```

### CI workflow (`ci.yml`)

Runs on every PR against `main`.

**`lint-test` job:**
1. `actions/checkout@v4`
2. `git checkout -B ${{ github.head_ref }}` — fixes detached HEAD
3. `uv sync`
4. `make lint`
5. `make test`

**`deploy-pr` job** (runs after `lint-test`, skipped for Dependabot, skipped if docs-only):
1. Destroy previous deployment for this PR (`make destroy-pr`, `continue-on-error: true`)
2. Deploy: `make deploy-pr PR_NUMBER=<N>`
3. Run: `make run-pr PR_NUMBER=<N>`

The PR schema is `pr_<N>` — fully isolated from dev and from other open PRs. The bundle `root_path` includes `${bundle.git.branch}`, providing workspace-level isolation too.

`concurrency.cancel-in-progress: false` — Databricks deploys are stateful. If two pushes land quickly, the second deploy queues rather than interrupting the first.

### CD workflow (`cd.yml`)

Runs on push to `main`. Skipped for docs-only changes (`docs/**`, `README.md`, `.github/PULL_REQUEST_TEMPLATE.md`).

1. `make deploy-prod` — passes `DATABRICKS_SP_CLIENT_ID` as `--var sp_client_id=...`
2. `make run-prod`

`concurrency.group: deploy-prod` with `cancel-in-progress: false` — prod deploys never interrupt each other.

### Prod approval gate

GitHub does not have a native approval gate for Actions. Options:
- A required reviewer on the PR (merge = implicit approval)
- A GitHub Environment with required reviewers configured — the `cd.yml` job references the environment and pauses for approval before deploying

### Dependabot

`.github/dependabot.yml` configures monthly updates for GitHub Actions and pip dependencies. All deploy jobs include `if: github.actor != 'dependabot[bot]'` — Dependabot PRs run lint and tests only, never deploy.

---

## Azure DevOps

> **Pipeline YAML deferred.** `ci/*.yml` will be added once the ADO workspace is available for end-to-end verification. All CI logic is in `Makefile` targets — ADO pipelines will call `make` identically to GitHub Actions. See `ci/README.md`.

### Variable group

Create a variable group (e.g. `databricks-dataops`) in **Pipelines → Library** and link it to the pipeline. Mark secrets as secret.

| Variable | Used by | Description |
|---|---|---|
| `DATABRICKS_HOST` | CI, CD | Workspace URL |
| `DATABRICKS_CLIENT_ID` | CI, CD | Service principal application (client) ID |
| `DATABRICKS_CLIENT_SECRET` | CI, CD | Service principal client secret *(secret)* |
| `DATABRICKS_SP_CLIENT_ID` | CD | SP application UUID for `prod` `run_as` |

### Authentication

**Preferred — OIDC (workload identity federation):**  
Configure a federated credential on the Azure AD service principal trusting the ADO service connection issuer. The pipeline uses the service connection identity — no long-lived secret stored.

**Fallback — OAuth M2M:**  
Store `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` in the variable group. The Databricks CLI picks these up via environment variables.

Never use PAT tokens.

### PR number and branch name

| Value | ADO variable / expression |
|---|---|
| PR number | `$(System.PullRequest.PullRequestId)` |
| Branch name | `$(Build.SourceBranch)` stripped of `refs/heads/` |

Do not use `Build.SourceBranchName` — for branches containing a slash (e.g. `feature/my-feature`) it returns only the last segment (`my-feature`), which silently truncates `${bundle.git.branch}` in `workspace.root_path` and can cause root-path collisions between unrelated branches.

Use `Build.SourceBranch` with an explicit strip step:

```bash
BRANCH=$(echo "$(Build.SourceBranch)" | sed 's|refs/heads/||')
```

Unlike GitHub Actions, the ADO checkout is not detached, so no `git checkout -B` equivalent is required once the branch variable is set correctly.

### Changed-file detection

ADO injects the required env vars automatically. `SYSTEM_ACCESSTOKEN` must be explicitly mapped:

```yaml
- script: |
    SHOULD_DEPLOY=$(CI_PROVIDER=azure_devops uv run python scripts/changed_files.py)
    echo "##vso[task.setvariable variable=SHOULD_DEPLOY]$SHOULD_DEPLOY"
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### Prod approval gate

ADO uses an **Environment** resource with an Approval check — more explicit than GitHub's model.

1. Create an Environment named `prod` in **Pipelines → Environments**.
2. Add an Approvals check with the required approvers.
3. In `ci/deploy.yml`, the prod deployment job references `environment: prod` — the pipeline pauses at that job until approved.

---

## PR deploy order

Full sequence for every PR deploy (both GHA and ADO):

1. **Destroy** — remove stale pipeline/job definitions for this PR
2. **Orphan cleanup** — remove schemas/volumes from closed PRs
3. **Schema** — create `pr_<N>` schema in UC
4. **Volume** — create landing volume under the schema
5. **Upload** — upload fixture/seed data to the volume
6. **Bundle deploy** — `databricks bundle deploy --target pr --var target_schema=pr_<N>`
7. **Run** — `databricks bundle run data_product_operational_job`
8. **Validate** — check ops tables for pass/fail status
