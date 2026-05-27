# databricks-dataops-template summary

## Purpose
Databricks DataOps starter template for one production-style data product.

## What it demonstrates
- Databricks Asset Bundles
- Lakeflow pipelines
- dev / pr / prod targets
- Unity Catalog Volumes
- CI/CD
- ops tables
- observability dashboard
- runbook patterns
- local PySpark tests

## What it deliberately excludes
- full platform landing zone
- full governance accelerator
- commercial/provider playbook
- customer-specific scope
- generic Managed Services model

## Important files
...

## Current known gaps
- dashboard portability
- status vocabulary alignment
- configurable operator group
- configurable alerts
- Azure DevOps implementation
- FinOps pack
- generic contract validation


# databricks-dataops-template summary

## Purpose

This repository is a Databricks DataOps starter template for one production-style data product. It is intended as a client-facing technical accelerator, not a learning artifact.

## Core principles

- Databricks-specific, not platform-agnostic.
- Uses Databricks Asset Bundles for deployment.
- Uses Lakeflow pipelines for ingestion/transformation.
- Uses Unity Catalog and UC Volumes.
- Uses Git, PRs, CI/CD, and local PySpark tests.
- Keeps business logic in importable Python modules under `src/`.
- Keeps pipeline files thin.
- Supports dev, PR, and prod targets.
- Uses prod `run_as` service principal.
- Includes operational jobs, validation tasks, ops tables, and dashboard.
- Should stay clean, reusable, and customer-forkable.

## What the template demonstrates

- dev / pr / prod target isolation
- Databricks bundle deployment
- source-domain pipeline separation
- bronze / silver / gold pattern
- data quality rule severities
- rejected-row pattern
- operational job orchestration
- ops tables
- dashboard-facing SQL views
- basic runbook commands
- GitHub Actions CI/CD
- Azure DevOps portability documentation
- local development in VS Code
- local PySpark tests

## What the template deliberately excludes

- full platform landing zone
- full governance accelerator
- row filters, masks, ABAC, and enterprise governance
- full commercial provider playbook
- customer-specific SOW or contract material
- generic Managed Services operating model
- CDC and API ingestion as built-in core patterns
- enterprise observability across all workspaces
- full FinOps product

## Important files

### Repository orientation
- README.md
- docs/architecture.md
- docs/setup.md
- docs/platform-prerequisites.md
- docs/ci-cd.md
- docs/runbook.md
- docs/observability.md

### Pattern docs
- docs/patterns/cdc.md
- docs/patterns/backfill.md
- docs/patterns/schema-migration.md

### Bundle and resources
- databricks.yml
- resources/data_product_operational_job.yml
- resources/customers_pipeline.yml
- resources/orders_pipeline.yml
- resources/gold_pipeline.yml
- resources/ops_dashboard.yml
- resources/volumes.yml

### Operational notebooks
- src/data_product/pipelines/validate_silver_readiness.py
- src/data_product/pipelines/validate_gold_contract.py
- src/data_product/pipelines/finalize_ops_status.py

### CI/CD
- .github/workflows/ci.yml
- .github/workflows/cd.yml
- ci/README.md
- scripts/changed_files.py
- Makefile

## Current known gaps

### P0 gaps
- Make operator group configurable instead of hardcoded `data-operators`.
- Align status vocabulary across `finalize_ops_status.py`, docs, and dashboard.
- Audit dashboard for hardcoded catalog/schema references.
- Add configurable failure notifications.
- Create verified Azure DevOps CI/CD path or skeleton.

### P1 gaps
- Make freshness, rejection thresholds, and staleness configurable.
- Add generic YAML-driven data contract validation.
- Refactor ops logic into testable modules.
- Add FinOps tagging standard.
- Add optional FinOps SQL pack.
- Add PR cleanup automation.
- Add release/change documentation.
- Add OIDC-first CI/CD documentation.

### P2 gaps
- Optional CDC accelerator.
- Optional API ingestion accelerator.
- Enterprise observability using Databricks system tables.
- Data product scale-out method.

## Provider relationship

This repository should remain the technical foundation.

Provider operating model, commercial packaging, service definitions, RACI, incident model, customer workshop material, SOW wording, monthly service reports, security review packs, and migration playbooks should live in a separate private repository:

`databricks-dataops-provider-playbook`.

Customer-specific implementation should live in customer-specific repositories.