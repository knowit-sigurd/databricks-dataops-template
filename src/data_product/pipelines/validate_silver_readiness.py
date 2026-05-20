# Databricks notebook source
import json as _json
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

spark = SparkSession.builder.getOrCreate()

catalog = dbutils.widgets.get("catalog")
target_schema = dbutils.widgets.get("target_schema")
customers_pipeline_id = dbutils.widgets.get("customers_pipeline_id")
orders_pipeline_id = dbutils.widgets.get("orders_pipeline_id")

ops_table = f"{catalog}.{target_schema}.ops_pipeline_run_log"

try:
    run_id = str(
        dbutils.notebook.entry_point.getDbutils().notebook().getContext().currentRunId().get()
    )
except Exception:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {ops_table} (
        run_id STRING,
        pipeline_name STRING,
        check_name STRING,
        check_type STRING,
        status STRING,
        message STRING,
        checked_at TIMESTAMP
    ) USING DELTA
""")

OPS_SCHEMA = StructType([
    StructField("run_id", StringType()),
    StructField("pipeline_name", StringType()),
    StructField("check_name", StringType()),
    StructField("check_type", StringType()),
    StructField("status", StringType()),
    StructField("message", StringType()),
    StructField("checked_at", TimestampType()),
])

ops_rows = []
failures = []
checked_at = datetime.now(timezone.utc)


def record(pipeline_name, check_name, check_type, status, message):
    ops_rows.append((run_id, pipeline_name, check_name, check_type, status, message, checked_at))
    if status == "FAIL":
        failures.append(f"[{pipeline_name}] {check_name}: {message}")


# --- Direct checks (authoritative — drives pass/fail) ---

FRESHNESS_HOURS = 24
REJECTION_THRESHOLD = 0.30

for domain, pipeline_name in [("customers", "customers_pipeline"), ("orders", "orders_pipeline")]:
    silver = f"{catalog}.{target_schema}.{domain}_silver"
    bronze = f"{catalog}.{target_schema}.{domain}_bronze"
    rejected = f"{catalog}.{target_schema}.{domain}_rejected"

    silver_count = spark.read.table(silver).count()
    if silver_count == 0:
        record(pipeline_name, "silver_not_empty", "direct", "FAIL", f"{silver} is empty")
    else:
        record(pipeline_name, "silver_not_empty", "direct", "PASS", f"{silver_count} rows")

    age_row = spark.sql(f"""
        SELECT (unix_timestamp(now()) - unix_timestamp(max(_ingested_at))) / 3600 AS age_hours
        FROM {silver}
    """).collect()[0]
    age_hours = age_row["age_hours"]
    if age_hours is None:
        record(pipeline_name, "silver_freshness", "direct", "FAIL", "_ingested_at is null")
    elif age_hours > FRESHNESS_HOURS:
        record(pipeline_name, "silver_freshness", "direct", "FAIL",
               f"Most recent _ingested_at is {age_hours:.1f}h ago (threshold: {FRESHNESS_HOURS}h)")
    else:
        record(pipeline_name, "silver_freshness", "direct", "PASS",
               f"Most recent _ingested_at is {age_hours:.1f}h ago")

    bronze_count = spark.read.table(bronze).count()
    rejected_count = spark.read.table(rejected).count()
    if bronze_count > 0:
        ratio = rejected_count / bronze_count
        status = "FAIL" if ratio > REJECTION_THRESHOLD else "PASS"
        record(
            pipeline_name, "rejection_ratio", "direct", status,
            f"{rejected_count}/{bronze_count} rows rejected"
            f" ({ratio:.1%}, threshold: {REJECTION_THRESHOLD:.0%})",
        )
    else:
        record(pipeline_name, "rejection_ratio", "direct", "WARN",
               "bronze table is empty — skipping ratio check")


# --- event_log() enrichment (informational — failure here does not block gold) ---

for pipeline_name, pipeline_id in [
    ("customers_pipeline", customers_pipeline_id),
    ("orders_pipeline", orders_pipeline_id),
]:
    try:
        event_df = spark.sql(f"SELECT * FROM event_log('{pipeline_id}')")

        latest = (
            event_df
            .filter("event_type = 'create_update'")
            .orderBy(F.col("timestamp").desc())
            .select(F.col("details.create_update.update_id"))
            .limit(1)
            .collect()
        )
        if not latest or latest[0][0] is None:
            record(pipeline_name, "event_log_enrichment", "expectation", "WARN",
                   "No update found in event_log — pipeline may not have run yet")
            continue

        update_id = latest[0][0]

        expectations = (
            event_df
            .filter(f"origin.update_id = '{update_id}' AND event_type = 'flow_progress'")
            .filter("details.flow_progress.data_quality IS NOT NULL")
            .select(
                F.col("origin.flow_name").alias("flow_name"),
                F.explode("details.flow_progress.data_quality.expectations").alias("exp"),
            )
            .select(
                "flow_name",
                F.col("exp.name").alias("expectation_name"),
                F.col("exp.passed_records").alias("passed_records"),
                F.col("exp.failed_records").alias("failed_records"),
            )
            .groupBy("flow_name", "expectation_name")
            .agg(
                F.sum("passed_records").alias("total_passed"),
                F.sum("failed_records").alias("total_failed"),
            )
            .collect()
        )

        for row in expectations:
            status = "PASS" if row["total_failed"] == 0 else "WARN"
            msg = (
                f"flow={row['flow_name']} "
                f"passed={row['total_passed']} failed={row['total_failed']}"
            )
            record(pipeline_name, row["expectation_name"], "expectation", status, msg)

    except Exception as e:
        record(pipeline_name, "event_log_enrichment", "expectation", "WARN",
               f"event_log() unavailable (pipeline ownership required): {e}")


# --- Print results to notebook output ---

print("validate_silver_readiness")
print("=" * 40)
for row in ops_rows:
    _, pipeline_name, check_name, _, status, message, _ = row
    print(f"[{pipeline_name}] {check_name:<35} {status:<5} {message}")

passed = sum(1 for r in ops_rows if r[4] == "PASS")
warned = sum(1 for r in ops_rows if r[4] == "WARN")
failed = sum(1 for r in ops_rows if r[4] == "FAIL")
overall = "FAIL" if failed else "PASS"
print(f"\nOverall: {overall} ({passed} passed, {failed} failed, {warned} warned)")

# --- Write ops rows ---

(
    spark.createDataFrame(ops_rows, schema=OPS_SCHEMA)
    .write.mode("append")
    .saveAsTable(ops_table)
)

# --- Block gold if any direct check failed ---

if failures:
    raise RuntimeError(
        f"validate_silver_readiness: {len(failures)} check(s) failed — gold pipeline blocked.\n"
        + "\n".join(failures)
    )

dbutils.notebook.exit(_json.dumps({
    "status": overall, "passed": passed, "failed": failed, "warned": warned,
}))
