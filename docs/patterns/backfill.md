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

A **full refresh** (`databricks pipelines start --full-refresh`) on a streaming table truncates the table, removes the Auto Loader checkpoint, and restarts ingestion from the beginning of the source. All files in the landing volume are re-ingested. Use full refresh only when you need to reprocess everything from scratch — not for targeted backfills.

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
# Full refresh a specific table — truncates the table and resets its checkpoint
databricks pipelines start --pipeline-id <id> --full-refresh-selection customers_bronze

# Full refresh the entire pipeline — truncates all tables and resets all checkpoints
databricks pipelines start --pipeline-id <id> --full-refresh
```

After a full refresh, the next pipeline run re-ingests all files from the landing volume from the beginning. This is the correct behaviour — the checkpoint was removed as part of the full refresh.

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
