# Pattern: Change Data Capture (CDC)

## Not in MVP

CDC via `apply_changes()` is out of scope for this data product. The source systems deliver full snapshots or append-only event streams — there are no deletes or out-of-order updates to handle.

## When CDC is needed

Use `apply_changes()` when the source delivers:
- Row-level deletes
- Updates to existing rows (not inserts)
- Out-of-order records that must be applied in sequence order

If the source is append-only and never retracts or amends rows, CDC adds complexity with no benefit.

## Recommended path when adding CDC

`apply_changes()` is the SDP/DLT primitive for CDC. It targets a silver table and maintains it as a Type 1 SCD (or Type 2 with `STORED_AS_SCD_TYPE_2`).

Minimal shape:

```python
from pyspark import pipelines as dp

dp.apply_changes(
    target="customers_silver",
    source="customers_bronze",
    keys=["customer_id"],
    sequence_by="updated_at",
    stored_as_scd_type=1,
)
```

Key decisions when adopting CDC in this template:

1. **`SEQUENCE_BY` column** — must be a monotonically increasing timestamp or version number present in the source. Auto Loader ingest order (`_metadata.file_path`) is not sufficient — use a source-side sequence column.

2. **`expect_or_drop` on bronze, not silver** — with `apply_changes()`, the silver table is managed by the CDC engine. Quality expectations belong on the bronze source table, not on the CDC target.

3. **Rejected rows** — `apply_changes()` does not support a rejected table directly. Implement a pre-filter step that routes invalid rows to `customers_rejected` before they reach the CDC target.

4. **`run_as` and event_log** — the CDC pipeline still requires SP ownership in prod for `event_log()` access. No change to the ownership model.

5. **Schema evolution** — `apply_changes()` respects `schema_evolution_mode`. Be explicit about whether new columns from the source are automatically propagated.

## Impact on this template

If CDC is added to an existing domain:
- Replace the `customers_silver` `@dp.table` function with `dp.apply_changes()`
- Add a pre-CDC bronze quality step as a separate `@dp.table`
- Update tests: transformation logic tests change shape (test the pre-CDC bronze step, not a silver transform function)
- The job DAG and validate tasks are unaffected
