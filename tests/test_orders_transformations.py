from datetime import datetime
from decimal import Decimal

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, StringType, StructField, StructType, TimestampType

from data_product.domains.orders.rules import ORDER_RULES
from data_product.domains.orders.transformations import build_rejected, transform_bronze_to_silver

BRONZE_WITH_META = StructType([
    StructField("order_id", StringType(), nullable=True),
    StructField("customer_id", StringType(), nullable=True),
    StructField("amount", DecimalType(10, 2), nullable=True),
    StructField("order_date", TimestampType(), nullable=True),
    StructField("status", StringType(), nullable=True),
    StructField("_source_file", StringType(), nullable=True),
    StructField("_ingested_at", TimestampType(), nullable=True),
])

_NOW = datetime(2026, 5, 19, 12, 0, 0)
_DATE = datetime(2026, 5, 1, 10, 0, 0)


def _bronze(spark: SparkSession, rows: list[tuple]) -> object:
    return spark.createDataFrame(rows, schema=BRONZE_WITH_META)


# --- standardisation ---

def test_status_is_uppercased_and_trimmed(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("12.50"), _DATE, "  pending  ", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["status_std"] == "PENDING"


def test_amount_and_order_date_pass_through_unchanged(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("99.99"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    row = silver.collect()[0]
    assert row["amount"] == Decimal("99.99")
    assert row["order_date"] == _DATE


# --- severity matrix: critical ---

def test_critical_order_id_not_null_detects_violation(spark: SparkSession):
    bronze = _bronze(spark, [(None, "c1", Decimal("10.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rule = next(r for r in ORDER_RULES if r.name == "order_id_not_null")
    violations = silver.filter(F.expr(f"NOT ({rule.constraint})"))
    assert violations.count() == 1


def test_critical_customer_id_not_null_detects_violation(spark: SparkSession):
    bronze = _bronze(spark, [("o1", None, Decimal("10.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rule = next(r for r in ORDER_RULES if r.name == "customer_id_not_null")
    violations = silver.filter(F.expr(f"NOT ({rule.constraint})"))
    assert violations.count() == 1


# --- severity matrix: business_invalid ---

def test_negative_amount_appears_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("-1.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.count() == 1


def test_zero_amount_appears_in_rejected(spark: SparkSession):
    # amount > 0 is strict — zero is invalid
    bronze = _bronze(spark, [("o1", "c1", Decimal("0.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.count() == 1


def test_positive_amount_not_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("10.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.count() == 0


def test_rejected_reason_is_positive_amount(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("-5.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.collect()[0]["rejection_reason"] == "positive_amount"


def test_rejected_severity_is_business_invalid(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("-5.00"), _DATE, "paid", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.collect()[0]["rejection_severity"] == "business_invalid"


# --- severity matrix: warning ---

def test_null_status_passes_through_to_silver(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("10.00"), _DATE, None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.count() == 1
    assert silver.collect()[0]["status_std"] is None


def test_null_status_not_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("10.00"), _DATE, None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, ORDER_RULES)
    assert rejected.count() == 0


def test_warning_rule_detects_null_status(spark: SparkSession):
    bronze = _bronze(spark, [("o1", "c1", Decimal("10.00"), _DATE, None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rule = next(r for r in ORDER_RULES if r.severity == "warning")
    violations = silver.filter(F.expr(f"NOT ({rule.constraint})"))
    assert violations.count() == 1
