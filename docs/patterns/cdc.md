# Pattern: Change Data Capture (CDC)

## Not in MVP

CDC via `create_auto_cdc_flow()` is out of scope for this data product. The source systems deliver full snapshots or append-only event streams — there are no deletes or out-of-order updates to handle.

## When CDC is needed

Use `create_auto_cdc_flow()` when the source delivers:
- Row-level deletes
- Updates to existing rows (not inserts)
- Out-of-order records that must be applied in sequence order

Use `create_auto_cdc_from_snapshot_flow()` when the source delivers periodic full snapshots and deletes are implied by absence — the row was present last snapshot, absent this one.

If the source is append-only and never retracts or amends rows, CDC adds complexity with no benefit.

---

## Recommended path: create_auto_cdc_flow()

`create_auto_cdc_flow()` is the SDP/DLT primitive for event-stream CDC. It targets a silver table and maintains it as a Type 1 SCD (last write wins) or Type 2 SCD (full history).

> `apply_changes()` is the deprecated predecessor — same signature, still functional, but Databricks recommends migrating to the new name.

Minimal shape:

```python
from pyspark import pipelines as dp

dp.create_auto_cdc_flow(
    target="customers_silver",
    source="customers_bronze",
    keys=["customer_id"],
    sequence_by="updated_at",
    stored_as_scd_type=1,
)
```

Key decisions:

1. **`sequence_by` column** — must be a monotonically increasing timestamp or version number present in the source. Auto Loader ingest order (`_metadata.file_path`) is not sufficient — use a source-side sequence column.

2. **Quality expectations on bronze, not silver** — with `create_auto_cdc_flow()`, the silver table is managed by the CDC engine. `@dp.expect_or_*` decorators belong on the bronze source table, not on the CDC target.

3. **Rejected rows** — `create_auto_cdc_flow()` does not support a rejected table directly. Implement a pre-filter step that routes invalid rows to `customers_rejected` before they reach the CDC target. See [When to split bronze and silver](#when-to-split-bronze-and-silver).

4. **`run_as` and event_log** — the CDC pipeline still requires SP ownership in prod for `event_log()` access. No change to the ownership model.

5. **SCD Type 2** — set `stored_as_scd_type=2` and add `__START_AT` / `__END_AT` to your gold query. The current gold pipeline reads the latest silver row — it must be updated to filter on active records (`__END_AT IS NULL`).

---

## Recommended path: create_auto_cdc_from_snapshot_flow()

Use this when the source delivers full periodic snapshots (e.g. a nightly full extract) rather than a change log. Deletes are inferred: if a key was in snapshot N and absent in snapshot N+1, it is treated as deleted.

> `apply_changes_from_snapshot()` is the deprecated predecessor — same signature, still functional, but Databricks recommends migrating to the new name.

```python
import pyspark.sql.functions as F
from pyspark import pipelines as dp

dp.create_auto_cdc_from_snapshot_flow(
    target="customers_silver",
    source=lambda: spark.read.table("customers_bronze"),
    keys=["customer_id"],
    stored_as_scd_type=1,
    track_history_column_list=None,  # track all columns
)
```

Key differences from `create_auto_cdc_flow()`:

- No `sequence_by` — ordering is determined by snapshot arrival order, not a column value
- The source is a batch relation (a lambda returning a DataFrame), not a streaming table
- Deletions are implicit — no delete event record is needed in the source

---

## Anti-pattern: custom MERGE

Do not implement CDC with a manual `MERGE INTO` statement inside a `@dp.table` function. Reasons:

- **No ordering guarantee** — DLT may process micro-batches in any order. A MERGE without a reliable sequence column will silently apply updates out of order.
- **No restartability** — DLT's incremental processing model assumes idempotent operations. A MERGE that reads from a mutable target table breaks this assumption; a restart may produce different results.
- **No delete support** — MERGE can handle updates but delete semantics require tracking tombstone records manually, which is error-prone.
- **No SCD Type 2** — implementing history tracking on top of MERGE requires significant custom logic that `create_auto_cdc_flow()` provides out of the box.

`create_auto_cdc_flow()` exists specifically to replace this pattern. Use it.

---

## Schema change handling

`create_auto_cdc_flow()` respects the `schema_evolution_mode` setting on the pipeline resource.

| Mode | Behaviour |
|---|---|
| `none` (default) | New columns in source are ignored. Target schema is fixed. |
| `addNewColumns` | New columns in source are automatically added to the target. Existing columns are never dropped or renamed. |

**Recommended approach:** start with `none` and add new columns explicitly via a schema migration. `addNewColumns` is convenient but can silently propagate upstream schema drift into your silver table, which downstream gold queries may not expect.

When a source adds a new column:
1. Add it to the bronze `StructType` schema definition
2. Add it to the silver transform in `transformations.py`
3. Update gold if the column is needed downstream
4. Deploy — the silver table schema evolves on the next pipeline run

Never rely on schema inference in bronze (`StructType` is required by convention in this template). Explicit schemas make upstream drift visible at deploy time, not at runtime.

---

## When to split bronze and silver

With `create_auto_cdc_flow()`, the silver table is owned by the CDC engine — you cannot attach a `@dp.table` function to it. This changes the bronze→silver relationship.

Split bronze into two steps when adding CDC:

```
Auto Loader → customers_bronze_raw    (@dp.table, streaming, explicit schema)
                    │
                    ├──→ customers_rejected  (invalid rows filtered out)
                    │
                    ▼
             customers_bronze          (@dp.table, quality-filtered, ready for CDC)
                    │
                    ▼
             dp.create_auto_cdc_flow(target="customers_silver", source="customers_bronze", ...)
```

The intermediate `customers_bronze` step is where quality expectations (`@dp.expect_or_drop`, `@dp.expect_or_fail`) live. `create_auto_cdc_flow()` consumes from this clean source.

Split is necessary when:
- You need a rejected table alongside CDC (rejected rows must be diverted before the CDC target)
- Quality rules must run before the CDC merge (always true in this template)

Split is not necessary when:
- The source is already clean and no rejection logic is required (rare in practice)

---

## Impact on this template

If CDC is added to an existing domain (e.g. `customers`):

- Replace the `customers_silver` `@dp.table` function with `dp.create_auto_cdc_flow()`
- Add a pre-CDC `customers_bronze` quality step as a separate `@dp.table`
- Update `transformations.py`: the silver transform function is removed; the bronze quality filter becomes the main transformation
- Update tests: test the bronze quality filter, not a silver transform function (there is none)
- Update gold: if SCD Type 2, filter on `__END_AT IS NULL` for active records
- The job DAG and validate tasks are unaffected

---

## References

- [Databricks: AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)
- [Databricks: `create_auto_cdc_flow()` Python reference](https://docs.databricks.com/aws/en/ldp/python-ref#create_auto_cdc_flow)
- [Databricks: SCD Type 2 with Lakeflow Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/cdc#scd-type-2)
