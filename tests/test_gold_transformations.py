from datetime import datetime
from decimal import Decimal

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DecimalType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from data_product.domains.gold.transformations import build_customer_orders

CUSTOMERS_SILVER_SCHEMA = StructType([
    StructField("customer_id", StringType(), nullable=True),
    StructField("name_std", StringType(), nullable=True),
    StructField("email_std", StringType(), nullable=True),
    StructField("country_code", StringType(), nullable=True),
    StructField("region", StringType(), nullable=True),
    StructField("phone", StringType(), nullable=True),
    StructField("_source_file", StringType(), nullable=True),
    StructField("_ingested_at", TimestampType(), nullable=True),
])

ORDERS_SILVER_SCHEMA = StructType([
    StructField("order_id", StringType(), nullable=True),
    StructField("customer_id", StringType(), nullable=True),
    StructField("amount", DecimalType(10, 2), nullable=True),
    StructField("order_date", TimestampType(), nullable=True),
    StructField("status_std", StringType(), nullable=True),
    StructField("_source_file", StringType(), nullable=True),
    StructField("_ingested_at", TimestampType(), nullable=True),
])

_NOW = datetime(2026, 5, 19, 12, 0, 0)
_D1 = datetime(2026, 1, 1, 0, 0, 0)
_D2 = datetime(2026, 2, 1, 0, 0, 0)
_D3 = datetime(2026, 3, 1, 0, 0, 0)


def test_customer_with_no_orders_appears_in_gold(spark: SparkSession):
    customers = spark.createDataFrame(
        [
            ("c1", "Alice Smith", "alice@example.com", "NO", "Europe", "111", "f", _NOW),
            ("c2", "Bob Jones", "bob@example.com", "US", "North America", "222", "f", _NOW),
        ],
        schema=CUSTOMERS_SILVER_SCHEMA,
    )
    # c2 has no orders
    orders = spark.createDataFrame(
        [("o1", "c1", Decimal("50.00"), _D1, "PAID", "f", _NOW)],
        schema=ORDERS_SILVER_SCHEMA,
    )
    gold = build_customer_orders(customers, orders)
    rows = {r["customer_id"]: r for r in gold.collect()}

    assert "c2" in rows, "Customer with no orders must appear (LEFT join)"
    assert rows["c2"]["order_count"] == 0
    assert rows["c2"]["total_amount"] is None
    assert rows["c2"]["last_order_date"] is None


def test_order_count_aggregated_correctly(spark: SparkSession):
    customers = spark.createDataFrame(
        [("c1", "Alice Smith", "alice@example.com", "NO", "Europe", "111", "f", _NOW)],
        schema=CUSTOMERS_SILVER_SCHEMA,
    )
    orders = spark.createDataFrame(
        [
            ("o1", "c1", Decimal("10.00"), _D1, "PAID", "f", _NOW),
            ("o2", "c1", Decimal("20.00"), _D2, "PAID", "f", _NOW),
            ("o3", "c1", Decimal("30.00"), _D3, "PAID", "f", _NOW),
        ],
        schema=ORDERS_SILVER_SCHEMA,
    )
    gold = build_customer_orders(customers, orders)
    row = gold.collect()[0]
    assert row["order_count"] == 3


def test_total_amount_is_sum_of_orders(spark: SparkSession):
    customers = spark.createDataFrame(
        [("c1", "Alice Smith", "alice@example.com", "NO", "Europe", "111", "f", _NOW)],
        schema=CUSTOMERS_SILVER_SCHEMA,
    )
    orders = spark.createDataFrame(
        [
            ("o1", "c1", Decimal("10.00"), _D1, "PAID", "f", _NOW),
            ("o2", "c1", Decimal("20.00"), _D2, "PAID", "f", _NOW),
            ("o3", "c1", Decimal("30.00"), _D3, "PAID", "f", _NOW),
        ],
        schema=ORDERS_SILVER_SCHEMA,
    )
    gold = build_customer_orders(customers, orders)
    row = gold.collect()[0]
    assert row["total_amount"] == Decimal("60.00")


def test_last_order_date_is_max(spark: SparkSession):
    customers = spark.createDataFrame(
        [("c1", "Alice Smith", "alice@example.com", "NO", "Europe", "111", "f", _NOW)],
        schema=CUSTOMERS_SILVER_SCHEMA,
    )
    orders = spark.createDataFrame(
        [
            ("o1", "c1", Decimal("10.00"), _D1, "PAID", "f", _NOW),
            ("o2", "c1", Decimal("20.00"), _D3, "PAID", "f", _NOW),
        ],
        schema=ORDERS_SILVER_SCHEMA,
    )
    gold = build_customer_orders(customers, orders)
    row = gold.collect()[0]
    assert row["last_order_date"] == _D3


def test_gold_output_columns(spark: SparkSession):
    customers = spark.createDataFrame(
        [("c1", "Alice Smith", "alice@example.com", "NO", "Europe", "111", "f", _NOW)],
        schema=CUSTOMERS_SILVER_SCHEMA,
    )
    orders = spark.createDataFrame([], schema=ORDERS_SILVER_SCHEMA)
    gold = build_customer_orders(customers, orders)
    assert set(gold.columns) == {
        "customer_id", "name_std", "email_std", "region",
        "order_count", "total_amount", "last_order_date",
    }
