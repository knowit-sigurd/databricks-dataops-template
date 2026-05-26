# Databricks notebook source
import json as _json
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import RunResultState
from pyspark.sql import SparkSession
from pyspark.sql.types import LongType, StringType, StructField, StructType, TimestampType

spark = SparkSession.builder.getOrCreate()

catalog = dbutils.widgets.get("catalog")
target_schema = dbutils.widgets.get("target_schema")
bundle_target = dbutils.widgets.get("bundle_target")
# {{parent_run_id}} and {{job.id}} are Databricks dynamic value references resolved at runtime
job_run_id_param = dbutils.widgets.get("job_run_id")
job_id_param = dbutils.widgets.get("job_id")

ops_job_log = f"{catalog}.{target_schema}.ops_job_run_log"
recorded_at = datetime.now(timezone.utc)

overall_status = "UNKNOWN"
failed_task_key = None
failure_message = None
started_at = None
completed_at = recorded_at
duration_seconds = None
job_run_id_str = job_run_id_param
job_run_url = None
git_sha = "unknown"

try:
    w = WorkspaceClient()

    job_run_id = int(job_run_id_param)
    job_run = w.jobs.get_run(run_id=job_run_id)
    job_run_id_str = str(job_run_id)

    if job_run.start_time:
        started_at = datetime.fromtimestamp(job_run.start_time / 1000, tz=timezone.utc)
    if started_at:
        duration_seconds = int((recorded_at - started_at).total_seconds())

    job_run_url = f"{w.config.host}/jobs/{job_id_param}/runs/{job_run_id}"

    # git_sha stamped onto the job by the DAB mutator
    job_details = w.jobs.get(job_id=int(job_id_param))
    git_sha = (job_details.settings.tags or {}).get("git_sha", "unknown")

    # Derive overall_status from task outcomes — independent of validate notebook results
    FAILED_STATES = {RunResultState.FAILED, RunResultState.TIMEDOUT, RunResultState.CANCELED}
    failed_tasks = []
    for task in (job_run.tasks or []):
        if task.task_key == "finalize_ops_status":
            continue
        state = task.state
        if state and state.result_state in FAILED_STATES:
            msg = (state.state_message or "")[:500]
            failed_tasks.append((task.task_key, msg))

    if failed_tasks:
        overall_status = "FAILED"
        failed_task_key = failed_tasks[0][0]
        failure_message = failed_tasks[0][1] or None
    else:
        overall_status = "SUCCESS"

    # Upgrade SUCCESS → WARNING if any quality checks returned WARN this run
    if overall_status == "SUCCESS" and started_at:
        warn_table = f"{catalog}.{target_schema}.ops_pipeline_run_log"
        try:
            started_str = started_at.strftime("%Y-%m-%d %H:%M:%S")
            warn_count = spark.sql(f"""
                SELECT COUNT(*) AS cnt
                FROM {warn_table}
                WHERE status = 'WARN'
                AND check_type = 'direct'
                AND checked_at >= '{started_str}'
            """).collect()[0]["cnt"]
            if warn_count > 0:
                overall_status = "WARNING"
        except Exception:
            pass  # table may not exist on first run

except Exception as e:
    print(f"WARNING: could not retrieve job run details from Jobs API: {e}")

# --- Create ops_job_run_log if not exists ---
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {ops_job_log} (
        job_run_id      STRING,
        recorded_at     TIMESTAMP,
        catalog_name    STRING,
        schema_name     STRING,
        bundle_target   STRING,
        git_sha         STRING,
        overall_status  STRING,
        failed_task_key STRING,
        failure_message STRING,
        started_at      TIMESTAMP,
        completed_at    TIMESTAMP,
        duration_seconds BIGINT,
        job_run_url     STRING
    ) USING DELTA
""")

OPS_JOB_LOG_SCHEMA = StructType([
    StructField("job_run_id", StringType()),
    StructField("recorded_at", TimestampType()),
    StructField("catalog_name", StringType()),
    StructField("schema_name", StringType()),
    StructField("bundle_target", StringType()),
    StructField("git_sha", StringType()),
    StructField("overall_status", StringType()),
    StructField("failed_task_key", StringType()),
    StructField("failure_message", StringType()),
    StructField("started_at", TimestampType()),
    StructField("completed_at", TimestampType()),
    StructField("duration_seconds", LongType()),
    StructField("job_run_url", StringType()),
])

(
    spark.createDataFrame(
        [(
            job_run_id_str, recorded_at, catalog, target_schema, bundle_target,
            git_sha, overall_status, failed_task_key, failure_message,
            started_at, completed_at, duration_seconds, job_run_url,
        )],
        schema=OPS_JOB_LOG_SCHEMA,
    )
    .write.mode("append")
    .saveAsTable(ops_job_log)
)

# --- Create / refresh dashboard-facing SQL views ---
# Views are (re)created on every run so their definitions stay current with schema changes.

_views = {
    f"{catalog}.{target_schema}.ops_current_status_v": f"""
        SELECT
            job_run_id, recorded_at, catalog_name, schema_name, bundle_target,
            git_sha, overall_status, failed_task_key, failure_message,
            started_at, completed_at, duration_seconds, job_run_url,
            CASE
                WHEN overall_status = 'FAILED'  THEN 'FAILED'
                WHEN overall_status = 'WARNING' THEN 'WARNING'
                WHEN overall_status = 'SUCCESS'
                     AND (unix_timestamp(current_timestamp())
                          - unix_timestamp(completed_at)) / 3600 > 48
                                                THEN 'STALE'
                WHEN overall_status = 'SUCCESS' THEN 'HEALTHY'
                ELSE 'UNKNOWN'
            END AS dashboard_status,
            current_timestamp() AS view_refreshed_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (ORDER BY recorded_at DESC) AS _rn
            FROM {catalog}.{target_schema}.ops_job_run_log
        )
        WHERE _rn = 1
    """,
    f"{catalog}.{target_schema}.ops_run_history_v": f"""
        SELECT
            job_run_id, recorded_at, catalog_name, schema_name, bundle_target,
            git_sha, overall_status, failed_task_key, failure_message,
            started_at, completed_at, duration_seconds, job_run_url
        FROM {catalog}.{target_schema}.ops_job_run_log
    """,
    f"{catalog}.{target_schema}.ops_pipeline_run_history_v": f"""
        SELECT run_id, pipeline_name, check_name, check_type, status, message, checked_at
        FROM {catalog}.{target_schema}.ops_pipeline_run_log
    """,
    f"{catalog}.{target_schema}.ops_contract_check_history_v": f"""
        SELECT run_id, table_name, check_name, status, actual_value, expected_value, checked_at
        FROM {catalog}.{target_schema}.ops_contract_check_log
    """,
}

for view_fqn, view_sql in _views.items():
    spark.sql(f"CREATE OR REPLACE VIEW {view_fqn} AS {view_sql}")

# --- Print summary ---
print("finalize_ops_status")
print("=" * 40)
print(f"job_run_id:      {job_run_id_str}")
print(f"overall_status:  {overall_status}")
if failed_task_key:
    print(f"failed_task:     {failed_task_key}")
    print(f"failure_message: {failure_message}")
print(f"duration:        {duration_seconds}s" if duration_seconds else "duration:        unknown")
print(f"views refreshed: {list(_views.keys())}")

dbutils.notebook.exit(_json.dumps({
    "status": overall_status,
    "job_run_id": job_run_id_str,
    "failed_task_key": failed_task_key,
}))
