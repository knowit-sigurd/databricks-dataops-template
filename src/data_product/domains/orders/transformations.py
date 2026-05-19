from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, StringType, StructField, StructType, TimestampType

from data_product.domains.orders.rules import Rule

BRONZE_SCHEMA = StructType([
    StructField("order_id", StringType(), nullable=True),
    StructField("customer_id", StringType(), nullable=True),
    StructField("amount", DecimalType(10, 2), nullable=True),
    StructField("order_date", TimestampType(), nullable=True),
    StructField("status", StringType(), nullable=True),
])


def transform_bronze_to_silver(bronze: DataFrame) -> DataFrame:
    return bronze.select(
        F.col("order_id"),
        F.col("customer_id"),
        F.col("amount"),
        F.col("order_date"),
        F.upper(F.trim(F.col("status"))).alias("status_std"),
        F.col("_source_file"),
        F.col("_ingested_at"),
    )


def build_rejected(silver_candidates: DataFrame, rules: list[Rule]) -> DataFrame:
    """Return rows from silver_candidates that fail any business_invalid rule.

    silver_candidates is the result of transform_bronze_to_silver applied to bronze.
    rejection_reason is a comma-separated list of failing rule names.
    """
    bi_rules = [r for r in rules if r.severity == "business_invalid"]

    if not bi_rules:
        return silver_candidates.limit(0).withColumn(
            "rejection_reason", F.lit(None).cast("string")
        ).withColumn("rejection_severity", F.lit(None).cast("string"))

    df = silver_candidates
    for rule in bi_rules:
        df = df.withColumn(
            f"_fail_{rule.name}",
            F.when(F.expr(f"NOT ({rule.constraint})"), F.lit(rule.name)).otherwise(F.lit(None)),
        )

    fail_cols = [f"_fail_{r.name}" for r in bi_rules]

    df = df.filter(F.coalesce(*[F.col(c) for c in fail_cols]).isNotNull())
    df = df.withColumn("rejection_reason", F.concat_ws(", ", *[F.col(c) for c in fail_cols]))
    df = df.withColumn("rejection_severity", F.lit("business_invalid"))

    return df.drop(*fail_cols)
