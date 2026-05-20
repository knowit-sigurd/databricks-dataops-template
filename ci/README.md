# Azure DevOps CI/CD

Pipeline YAML for Azure DevOps is deferred until an ADO workspace is available for end-to-end verification. No unverified YAML will be added.

## What goes here

When ADO pipelines are added, this directory will contain:

| File | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR against `main` | Lint → test → deploy PR environment → run job |
| `deploy.yml` | Push to `main` | Deploy prod → run job (with approval gate) |
| `cleanup-pr.yml` | PR closed | Destroy PR environment, orphan cleanup |
| `cleanup-stale.yml` | Scheduled | Remove schemas/volumes from abandoned PRs |

All pipelines call `make` targets — no CI logic lives in the YAML itself.

## Setup

See [docs/ci-cd.md — Azure DevOps](../docs/ci-cd.md#azure-devops) for the full setup guide: variable groups, OIDC vs OAuth M2M authentication, PR number and branch name resolution, changed-file detection, and the prod approval gate.

See [docs/platform-prerequisites.md — Azure](../docs/platform-prerequisites.md#azure) for storage and external location setup.
