from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from data_product.domains.customers.rules import Rule

BRONZE_SCHEMA = StructType([
    StructField("customer_id", StringType(), nullable=True),
    StructField("name", StringType(), nullable=True),
    StructField("email", StringType(), nullable=True),
    StructField("country_code", StringType(), nullable=True),
    StructField("phone", StringType(), nullable=True),
])

REGION_MAP: dict[str, str] = {
    "NO": "Europe",
    "SE": "Europe",
    "DK": "Europe",
    "DE": "Europe",
    "GB": "Europe",
    "US": "North America",
    "CA": "North America",
}


def transform_bronze_to_silver(bronze: DataFrame) -> DataFrame:
    mapping_expr = F.create_map(*[F.lit(x) for kv in REGION_MAP.items() for x in kv])
    return bronze.select(
        F.col("customer_id"),
        F.initcap(F.trim(F.col("name"))).alias("name_std"),
        F.lower(F.trim(F.col("email"))).alias("email_std"),
        F.col("country_code"),
        F.coalesce(mapping_expr[F.col("country_code")], F.lit("Unknown")).alias("region"),
        F.col("phone"),
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
