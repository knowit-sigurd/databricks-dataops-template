from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from data_product.domains.customers.rules import CUSTOMER_RULES
from data_product.domains.customers.transformations import (
    build_rejected,
    transform_bronze_to_silver,
)

BRONZE_WITH_META = StructType([
    StructField("customer_id", StringType(), nullable=True),
    StructField("name", StringType(), nullable=True),
    StructField("email", StringType(), nullable=True),
    StructField("country_code", StringType(), nullable=True),
    StructField("phone", StringType(), nullable=True),
    StructField("_source_file", StringType(), nullable=True),
    StructField("_ingested_at", TimestampType(), nullable=True),
])

_NOW = datetime(2026, 5, 19, 12, 0, 0)


def _bronze(spark: SparkSession, rows: list[tuple]) -> object:
    return spark.createDataFrame(rows, schema=BRONZE_WITH_META)


# --- standardisation ---

def test_name_is_title_cased_and_trimmed(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "  john doe  ", "j@x.com", "NO", "111", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["name_std"] == "John Doe"


def test_email_is_lowercased_and_trimmed(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "Jane", "  JANE@EXAMPLE.COM  ", "SE", "222", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["email_std"] == "jane@example.com"


# --- region enrichment ---

def test_known_country_code_maps_to_region(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "A", "a@b.com", "NO", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["region"] == "Europe"


def test_us_maps_to_north_america(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "B", "b@c.com", "US", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["region"] == "North America"


def test_unknown_country_code_falls_back_to_unknown(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "C", "c@d.com", "ZZ", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    assert silver.collect()[0]["region"] == "Unknown"


# --- severity matrix: critical ---

def test_critical_rule_constraint_fails_on_null_customer_id(spark: SparkSession):
    bronze = _bronze(spark, [(None, "D", "d@e.com", "DE", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    critical_rule = next(r for r in CUSTOMER_RULES if r.severity == "critical")
    # DLT enforces expect_or_fail at runtime; here we verify the constraint fires as a filter
    violations = silver.filter(F.expr(f"NOT ({critical_rule.constraint})"))
    assert violations.count() == 1


# --- severity matrix: business_invalid ---

def test_invalid_email_appears_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [
        ("c1", "Good", "good@example.com", "NO", "1", "f", _NOW),
        ("c2", "Bad", "not-an-email", "SE", "2", "f", _NOW),
    ])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, CUSTOMER_RULES)
    assert rejected.count() == 1
    assert rejected.collect()[0]["customer_id"] == "c2"


def test_valid_email_not_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "Good", "good@example.com", "NO", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, CUSTOMER_RULES)
    assert rejected.count() == 0


def test_rejected_reason_is_rule_name(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "Bad", "not-an-email", "NO", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, CUSTOMER_RULES)
    assert rejected.collect()[0]["rejection_reason"] == "valid_email_format"


def test_rejected_severity_is_business_invalid(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "Bad", "not-an-email", "NO", "1", "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, CUSTOMER_RULES)
    assert rejected.collect()[0]["rejection_severity"] == "business_invalid"


# --- severity matrix: warning ---

def test_null_phone_passes_through_to_silver(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "E", "e@f.com", "GB", None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    # Row must survive — warning never drops
    assert silver.count() == 1
    assert silver.collect()[0]["phone"] is None


def test_null_phone_not_in_rejected(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "E", "e@f.com", "GB", None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    rejected = build_rejected(silver, CUSTOMER_RULES)
    assert rejected.count() == 0


def test_warning_rule_constraint_detects_null_phone(spark: SparkSession):
    bronze = _bronze(spark, [("c1", "E", "e@f.com", "GB", None, "f", _NOW)])
    silver = transform_bronze_to_silver(bronze)
    warning_rule = next(r for r in CUSTOMER_RULES if r.severity == "warning")
    violations = silver.filter(F.expr(f"NOT ({warning_rule.constraint})"))
    assert violations.count() == 1
