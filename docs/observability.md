# Observability

The template ships a lightweight operational dashboard covering the two questions a data product team needs to answer on any given morning: _did the pipeline run?_ and _is the data good?_

## Data flow

```
DLT pipelines
    │  quality expectations → event_log()
    │
validate_silver_readiness    validate_gold_contract
    │  (runs as CI SP)            │  (runs as CI SP)
    ▼                             ▼
ops_pipeline_run_log         ops_contract_check_log
         │                        │
         └──────────┬─────────────┘
                    ▼
          finalize_ops_status
                    │
                    ▼
           ops_job_run_log
                    │
         SQL views (stable layer)
                    │
           AI/BI dashboard
```

`event_log()` requires pipeline ownership. The CI service principal owns all pipelines and can query it. Human operators cannot query prod event logs directly. The validate tasks bridge this: they run as the CI SP, pull from `event_log()`, and write to ops tables that operators are granted SELECT on.

## Ops tables

| Table | Written by | Purpose |
|---|---|---|
| `ops_pipeline_run_log` | `validate_silver_readiness`, `validate_gold_contract` | Per-pipeline quality check results |
| `ops_contract_check_log` | `validate_gold_contract` | Gold contract check results |
| `ops_job_run_log` | `finalize_ops_status` | One row per job run with overall status |

All three tables are target-scoped: `${catalog}.${target_schema}.<table>`.

### check_type values in ops_pipeline_run_log

- `direct` — authoritative checks computed directly (row counts, freshness, rejection ratio). These drive `overall_status`.
- `expectation` — enrichment from `event_log()` DLT expectations. Informational only; does not affect `overall_status`. May show WARN if `event_log()` is unavailable.

## overall_status logic

`finalize_ops_status` derives status from the Jobs API, independent of whether the validate tasks ran:

| Condition | Status |
|---|---|
| Any task (except `finalize_ops_status`) in FAILED / TIMEDOUT / CANCELED state | `FAILED` |
| All tasks succeeded, at least one `direct` check returned WARN this run | `WARNING` |
| All tasks succeeded, all `direct` checks passed | `SUCCESS` |
| Jobs API call failed (transient error) | `UNKNOWN` |

## Dashboard views

Views sit between raw ops tables and the dashboard. The dashboard only queries views, decoupling widget SQL from table schema changes.

| View | Source | Purpose |
|---|---|---|
| `ops_current_status_v` | `ops_job_run_log` | Latest run with `dashboard_status` (RED/YELLOW/GREEN/STALE/UNKNOWN) |
| `ops_run_history_v` | `ops_job_run_log` | All job runs |
| `ops_pipeline_run_history_v` | `ops_pipeline_run_log` | All pipeline check results |
| `ops_contract_check_history_v` | `ops_contract_check_log` | All contract check results |

Views are recreated on every `finalize_ops_status` run via `CREATE OR REPLACE VIEW`, keeping definitions current with schema changes.

### Staleness rule in ops_current_status_v

A `SUCCESS` run older than 48 hours becomes `STALE` (dashboard_status). Adjust the threshold in `finalize_ops_status.py` if the pipeline schedule differs.

## Dashboard deployment

The dashboard is a DABs-managed resource deployed to `dev` and `prod` targets only — not `pr`. Each target points at its own schema via `dataset_catalog` / `dataset_schema` overrides.

Dashboard file: `dashboards/data_product_operations.lvdash.json`
Resource config: `resources/ops_dashboard.yml`

Required variable: `dashboard_warehouse_id` — an existing SQL warehouse. Pass via `DATABRICKS_WAREHOUSE_ID` environment variable (GitHub secret for CI, `.env` for local).

```bash
# Deploy dev (also deploys dashboard)
make deploy-dev

# Deploy prod
make deploy-prod DATABRICKS_SP_CLIENT_ID=<uuid>
```

### Dashboard schedule

Configure a refresh schedule directly in the dashboard UI (Databricks built-in). No job task needed. Recommended: match the pipeline schedule.

## Access

Grant operators SELECT on the views and CAN_VIEW on the dashboard:

```sql
GRANT SELECT ON VIEW dataops_template.prod.ops_current_status_v TO `data-operators`;
GRANT SELECT ON VIEW dataops_template.prod.ops_run_history_v TO `data-operators`;
GRANT SELECT ON VIEW dataops_template.prod.ops_pipeline_run_history_v TO `data-operators`;
GRANT SELECT ON VIEW dataops_template.prod.ops_contract_check_history_v TO `data-operators`;
```

Dashboard CAN_VIEW is set in `ops_dashboard.yml` and applied on every deploy.

## Optional extensions

**Dependency checks** — Add a `check_dependencies` notebook task before `run_customers`/`run_orders` to verify upstream data has arrived. The right check is source-specific: expected arrival time, business date, partition, file count, source watermark, or upstream job dependency. A skeleton task is intentionally not shipped — a generic check would always pass on the sample data and give false confidence. Add it when you know the upstream contract.

**Quality trend page** — Add a third dashboard page charting expectation pass/fail rates over time once `event_log()` enrichment is working (requires the CI SP to own the pipelines in the target workspace).

**System tables** — `system.lakeflow.job_run_timeline` and `system.billing.usage` can be joined to ops tables to add cost-per-run visibility. Requires system table access to be enabled on the workspace.

**Notification destinations** — Wire `email_notifications` or `webhook_notifications` on the job resource (commented out in `data_product_operational_job.yml`) to alert on failure without polling the dashboard.
