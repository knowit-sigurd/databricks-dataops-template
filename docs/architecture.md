# Architecture

## Data flow

```
UC Volume (/Volumes/dataops_template/<schema>/landing/)
    │
    ├── customers/  ──→  customers_pipeline  ──→  customers_bronze
    │                                         ──→  customers_silver
    │                                         ──→  customers_rejected
    │
    └── orders/  ────→  orders_pipeline  ────→  orders_bronze
                                              ──→  orders_silver
                                              ──→  orders_rejected
                                                        │
                                                (published UC tables)
                                                        │
                                                        ▼
                                          gold_pipeline
                                              ──→  customer_orders_gold  (materialized view)
```

Each source domain has its own SDP pipeline. Gold reads from the published silver UC tables — it does not run in the same pipeline as bronze/silver, and it has no dependency on the internal pipeline state of the source pipelines.

## Operational job DAG

```
run_customers ─┐
               ├──→  validate_silver_readiness  ──→  run_gold  ──→  validate_gold_contract
run_orders    ─┘
```

`run_customers` and `run_orders` are triggered in parallel. The validation tasks query `event_log()` and write results to ops tables. See [runbook](runbook.md) for the `event_log()` ownership constraint.

## Quality severity matrix

Three severity levels control how the pipeline responds to bad rows:

| Severity | DLT expectation (dev / PR) | DLT expectation (prod) | Behaviour |
|---|---|---|---|
| `critical` | `expect_or_fail` | `expect_or_fail` | Pipeline halts. Row violates a structural invariant — no recovery possible. |
| `business_invalid` | `expect_or_drop` | `expect_or_fail` | Dev/PR: row written to `_rejected` table. Prod: pipeline halts. |
| `warning` | `expect` | `expect` | Row passes, metric recorded. No operational impact. |

The `quality_mode` bundle variable (`drop` in dev/PR, `fail` in prod) controls how `business_invalid` rules are applied. `critical` and `warning` are fixed regardless of target.

Rules are defined in `src/data_product/domains/{domain}/rules.py` and applied in the pipeline wrapper. Tests must cover all three severities per domain.


## Source package layout

```
src/data_product/
  domains/
    customers/
      transformations.py   # bronze → silver transform (pure PySpark)
      rules.py             # CUSTOMER_RULES list
    orders/
      transformations.py
      rules.py
    gold/
      transformations.py   # silver → gold join logic
      rules.py
  pipelines/
    customers_pipeline.py  # @dp.table wrappers — no logic
    orders_pipeline.py
    gold_pipeline.py       # @dp.materialized_view wrappers
    validate_silver_readiness.py  # notebook task
    validate_gold_contract.py     # notebook task
```

Pipeline files import from domains but contain no business logic. Tests import only from `domains/` — never from `pipelines/`.

## Bundle targets

| Target | Schema | `quality_mode` | `run_as` | `root_path` |
|---|---|---|---|---|
| `dev` | `dev` | `drop` | caller | `~/.../dev/<branch>` |
| `pr` | `pr_<N>` | `drop` | caller | `~/.../pr/<branch>` |
| `prod` | `prod` | `fail` | SP (app UUID) | `/Shared/.../<branch>` |

Per-PR root path isolation is enforced by including `${bundle.git.branch}` in the workspace `root_path`.

A separate platform bundle (`platform/databricks.yml`) optionally manages dev and prod schemas with `lifecycle.prevent_destroy: true` — for teams where a platform function owns persistent infrastructure separately from the data product bundle.

## Key design decisions

**Three pipelines, not one.** Source domains are isolated. A schema change in orders does not require redeploying customers. Gold reads published UC tables — it is not coupled to silver pipeline internals.

**`src/` package pattern.** All business logic is in plain Python, importable without a DLT runtime. This makes real local Spark tests practical. Pipeline files are wrappers only.

**Serverless compute.** No `node_type_id`, no instance pools. All pipelines and job tasks use Databricks serverless. This removes cluster management from the operational surface.

**UC Volumes for all paths.** No `s3://` or `abfss://` in any pipeline code. Storage is accessed only through `/Volumes/{catalog}/{schema}/...`. Cloud credential management is delegated entirely to the Unity Catalog external location.

**`run_as` in prod only.** The SP identity is set once at the prod target level. It cannot be removed from a pipeline once set — never configure it in dev or pr.

**Ops tables are target-scoped.** `{catalog}.{target_schema}.ops_pipeline_run_log` and `ops_contract_check_log` live in the same schema as the pipeline outputs. A shared `ops` schema is Phase 4.

## Out of scope (MVP)

| Feature | Reason |
|---|---|
| Column masks / row filters | Governance layer — Phase 3 |
| Multi-workspace staging | Not required for this data product |
| Shared ops schema | Phase 4 |
| CDC (`apply_changes()`) | See [patterns/cdc.md](patterns/cdc.md) |
| Push-based alerting | Operational tooling — Phase 3 |
| Schema registry | Not required for file-based ingestion |
| Third domain | Only if it demonstrates a new pattern |
