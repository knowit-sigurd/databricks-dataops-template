# Databricks notebook source
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

spark = SparkSession.builder.getOrCreate()

catalog = dbutils.widgets.get("catalog")
target_schema = dbutils.widgets.get("target_schema")

ops_run_log = f"{catalog}.{target_schema}.ops_pipeline_run_log"
ops_contract_log = f"{catalog}.{target_schema}.ops_contract_check_log"

# gold_pipeline_id intentionally not passed — @dp.materialized_view expectations may not
# surface in event_log() the same way streaming table expectations do.
# TODO: verify on first prod run; update architecture.md once confirmed.

try:
    run_id = str(
        dbutils.notebook.entry_point.getDbutils().notebook().getContext().currentRunId().get()
    )
except Exception:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

RUN_LOG_SCHEMA = StructType([
    StructField("run_id", StringType()),
    StructField("pipeline_name", StringType()),
    StructField("check_name", StringType()),
    StructField("check_type", StringType()),
    StructField("status", StringType()),
    StructField("message", StringType()),
    StructField("checked_at", TimestampType()),
])

CONTRACT_LOG_SCHEMA = StructType([
    StructField("run_id", StringType()),
    StructField("table_name", StringType()),
    StructField("check_name", StringType()),
    StructField("status", StringType()),
    StructField("actual_value", StringType()),
    StructField("expected_value", StringType()),
    StructField("checked_at", TimestampType()),
])

for table, schema in [(ops_run_log, RUN_LOG_SCHEMA), (ops_contract_log, CONTRACT_LOG_SCHEMA)]:
    cols = ", ".join(f"{f.name} {f.dataType.simpleString().upper()}" for f in schema)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({cols}) USING DELTA")

run_rows = []
contract_rows = []
failures = []
checked_at = datetime.now(timezone.utc)
gold_table = f"{catalog}.{target_schema}.customer_order_summary"
PIPELINE_NAME = "gold_pipeline"

EXPECTED_COLUMNS = {
    "customer_id", "name_std", "email_std", "region",
    "order_count", "total_amount", "last_order_date",
}


def run_record(check_name, status, message):
    run_rows.append(
        (run_id, PIPELINE_NAME, check_name, "direct", status, message, checked_at)
    )
    if status == "FAIL":
        failures.append(f"[{PIPELINE_NAME}] {check_name}: {message}")


def contract_record(check_name, status, actual, expected):
    contract_rows.append(
        (run_id, gold_table, check_name, status, str(actual), str(expected), checked_at)
    )
    if status == "FAIL":
        failures.append(f"[contract] {check_name}: actual={actual} expected={expected}")


# --- Not-empty ---
gold_count = spark.read.table(gold_table).count()
if gold_count == 0:
    run_record("gold_not_empty", "FAIL", f"{gold_table} is empty")
    contract_record("gold_not_empty", "FAIL", 0, "> 0")
else:
    run_record("gold_not_empty", "PASS", f"{gold_count} rows")
    contract_record("gold_not_empty", "PASS", gold_count, "> 0")

# --- Required columns ---
gold_df = spark.read.table(gold_table)
actual_columns = set(gold_df.columns)
missing = EXPECTED_COLUMNS - actual_columns
if missing:
    run_record("required_columns", "FAIL", f"Missing columns: {sorted(missing)}")
    contract_record("required_columns", "FAIL", sorted(actual_columns), sorted(EXPECTED_COLUMNS))
else:
    run_record("required_columns", "PASS", "All expected columns present")
    contract_record("required_columns", "PASS", sorted(actual_columns), sorted(EXPECTED_COLUMNS))

# --- No null customer_id (critical rule) ---
null_customer_count = gold_df.filter("customer_id IS NULL").count()
if null_customer_count > 0:
    run_record("customer_id_not_null", "FAIL", f"{null_customer_count} rows with null customer_id")
    contract_record("customer_id_not_null", "FAIL", null_customer_count, 0)
else:
    run_record("customer_id_not_null", "PASS", "No null customer_id rows")
    contract_record("customer_id_not_null", "PASS", 0, 0)

# --- Non-negative order_count (business_invalid rule) ---
negative_count = gold_df.filter("order_count < 0").count()
if negative_count > 0:
    run_record("non_negative_order_count", "FAIL",
               f"{negative_count} rows with order_count < 0")
    contract_record("non_negative_order_count", "FAIL", negative_count, 0)
else:
    run_record("non_negative_order_count", "PASS", "All order_count values >= 0")
    contract_record("non_negative_order_count", "PASS", 0, 0)

# --- Write ops rows ---
(
    spark.createDataFrame(run_rows, schema=RUN_LOG_SCHEMA)
    .write.mode("append")
    .saveAsTable(ops_run_log)
)
(
    spark.createDataFrame(contract_rows, schema=CONTRACT_LOG_SCHEMA)
    .write.mode("append")
    .saveAsTable(ops_contract_log)
)

# --- Fail job run if any check failed ---
if failures:
    raise RuntimeError(
        f"validate_gold_contract: {len(failures)} check(s) failed.\n"
        + "\n".join(failures)
    )
