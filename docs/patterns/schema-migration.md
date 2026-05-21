# Pattern: Schema migration

Lakeflow Declarative Pipelines manage table schemas automatically, but changes to source schemas, transformation outputs, or gold contracts require deliberate handling. The wrong approach causes pipeline failures or silent data loss.

---

## Adding a column to bronze

**No full refresh required.**

1. Add the column to the `StructType` in `src/data_product/domains/<domain>/transformations.py`.
2. Set `schema_evolution_mode: addNewColumns` on the pipeline resource if not already set, or handle the new column explicitly in the transformation.
3. Deploy and run — the column appears in the bronze table on the next incremental update.

Auto Loader infers the schema from the `StructType` you provide. New columns in source files that are not in the schema are ignored by default. Add them to the schema to capture them.

> Prefer explicit schema changes over `addNewColumns`. Automatic propagation can silently introduce upstream drift into silver and gold.

---

## Adding a column to silver

**No full refresh required in most cases.**

1. Add the column to the silver transformation in `transformations.py`.
2. Deploy and run — SDP adds the column to the silver table on the next incremental update. Existing rows get `NULL` for the new column unless you backfill.

If existing silver rows must be populated with the new column value, a full refresh is required:

```bash
databricks pipelines start --pipeline-id <customers-pipeline-id> \
  --full-refresh-selection customers_silver
```

---

## Adding a column to gold

**No full refresh required — materialized views rebuild automatically.**

Gold uses `@dp.materialized_view`. Databricks refreshes it as part of the pipeline update — attempting incremental refresh when the query supports it, or full recompute otherwise. Add the column to the gold transformation and deploy — no manual refresh needed for additive column changes.

Notify downstream consumers before deploying. Gold is a published contract — adding a column is additive and non-breaking, but consumers may need to update their queries.

---

## Renaming a column

**Breaking change — requires a deprecation window.**

There is no safe in-place column rename in Delta tables. The pattern:

1. **Add** the new column name to the transformation alongside the old one. Deploy.
2. **Notify** all consumers of the old column name. Give them a migration window.
3. **Remove** the old column from the transformation after consumers have migrated. Deploy.
4. **Drop** the old column from the physical table if needed:

```sql
ALTER TABLE dataops_template.prod.customers_silver DROP COLUMN old_column_name;
```

For gold: the same pattern applies. Both column names are present in the materialized view during the migration window.

---

## Removing a column

**Breaking change — requires a deprecation window.**

Same pattern as renaming: keep the column in the transformation, notify consumers, remove after migration, then drop from the physical table.

Do not drop a column from a pipeline transformation and deploy immediately — existing consumers querying the table will fail with a column-not-found error.

---

## Changing a gold contract column type

**Breaking change — Delta does not support implicit type changes.**

Delta allows widening type changes (e.g. `INT` → `BIGINT`) but not narrowing or incompatible changes. For an incompatible type change:

1. Rename the old column (follow the rename pattern above).
2. Add the new column with the correct type.
3. Migrate consumers.
4. Drop the old column.

Alternatively, recreate the gold table with a full refresh after changing the type in the transformation — this rebuilds the table from silver with the new schema, but drops all existing data:

```bash
databricks pipelines start --pipeline-id <gold-pipeline-id> --full-refresh
```

---

## When full refresh is required vs deploy only

| Change | Action |
|---|---|
| Add column to bronze `StructType` | Deploy only |
| Add column to silver transformation | Deploy only (existing rows get NULL) |
| Add column to gold transformation | Deploy only (materialized view rebuilds) |
| Rename column anywhere | Deprecation window + deploy + drop |
| Remove column anywhere | Deprecation window + deploy + drop |
| Incompatible type change | Full refresh or deprecation window |
| Bronze schema incompatible with Auto Loader checkpoint | Checkpoint reset (see [backfill](backfill.md)) |
| Fix transformation bug affecting existing silver rows | Full refresh of silver (and gold if affected) |
