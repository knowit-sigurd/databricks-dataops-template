# Pattern: Backfill and reprocessing

Reprocessing historical data in a Lakeflow Declarative Pipeline requires understanding how SDP incremental state works. The wrong approach resets more than intended; the right approach is targeted.

---

## When to backfill

| Situation | Action |
|---|---|
| Transformation bug fixed — bad rows already in silver | Backfill affected bronze files through pipeline |
| New column added to bronze schema | Deploy is sufficient — new column appears on next incremental run |
| New domain bootstrapped from existing files | Full initial load — checkpoint does not exist yet, Auto Loader processes all files |
| Gold logic changed — silver tables are correct | Full refresh gold pipeline only |
| Bronze schema rename or column removal | Checkpoint reset + full refresh required |

If only gold logic changed and silver is correct, do not reset bronze or silver. Scope the refresh to the lowest affected layer.

---

## How SDP incremental state works

Auto Loader tracks which files have been processed via a checkpoint stored in the pipeline's cloud storage location (under the pipeline's `storage` path in UC). The checkpoint is tied to the pipeline ID — not the table name or schema.

On every pipeline update, Auto Loader reads only files not yet in the checkpoint. Bronze tables are append-only by default. Silver and gold are rebuilt incrementally from new bronze rows.

A **full refresh** (`databricks pipelines start --full-refresh`) discards incremental state for the specified tables and reprocesses from the current source. It does not reset the Auto Loader checkpoint — files that were already processed are not re-ingested unless you also reset the checkpoint.

---

## Targeted backfill — one-time append flow

To reprocess a specific set of files without resetting the entire checkpoint, copy or move the files back into the landing volume and trigger an incremental pipeline run. Auto Loader will pick them up as new arrivals.

```bash
# Copy historical files back into the landing volume
databricks fs cp --recursive \
  dbfs:/archive/customers/2024-01/ \
  dbfs:/Volumes/dataops_template/prod/customers_raw/backfill-2024-01/

# Trigger an incremental run — Auto Loader picks up the new files
make run-prod
```

Downstream deduplication: if the reprocessed rows already exist in silver, handle duplicates explicitly in the silver transformation (e.g. `dropDuplicates(["customer_id", "updated_at"])`) before the backfill run. Remove the deduplication after.

---

## Checkpoint reset

A checkpoint reset is required when:
- The Auto Loader schema is incompatible with the new source format
- A column is renamed or removed in bronze
- You need to re-ingest all historical files from scratch

Reset via the Databricks CLI:

```bash
# Full refresh a specific table (reprocesses from current source, does not re-ingest files)
databricks pipelines start --pipeline-id <id> --full-refresh-selection customers_bronze

# Full refresh the entire pipeline (all tables, from current source)
databricks pipelines start --pipeline-id <id> --full-refresh
```

To re-ingest files from the Auto Loader source after a full refresh, you must also clear the checkpoint. This is done by deleting the pipeline and recreating it (the checkpoint lives under the pipeline storage path and is deleted with the pipeline), or by using Auto Loader's `cloudFiles.backfillInterval` option.

> Deleting and recreating the pipeline changes the pipeline ID. Any job references, `event_log()` queries, and ops table pipeline IDs must be updated.

---

## Downstream cascade

Reprocessing bronze affects silver and gold incrementally on the next run. If the reprocessed rows change silver content:

- **Silver** — SDP rebuilds silver from the new bronze rows. If silver logic is correct, no separate action needed.
- **Gold** — materialized views rebuild automatically from the updated silver tables. No separate action needed.
- **Ops tables** — `validate_silver_readiness` and `validate_gold_contract` append a new row per run. Historical ops rows are not affected.

If silver or gold tables contain bad rows from before the backfill, a full refresh of those tables removes and rebuilds them:

```bash
databricks pipelines start --pipeline-id <gold-pipeline-id> --full-refresh
```
