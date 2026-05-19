from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from data_product.domains.customers.rules import CUSTOMER_RULES
from data_product.domains.customers.transformations import (
    BRONZE_SCHEMA,
    build_rejected,
    transform_bronze_to_silver,
)


@dp.table
def customers_bronze():
    spark = SparkSession.getActiveSession()
    source_format = spark.conf.get("pipelines.source_format", "cloudFiles")
    source_path = spark.conf.get("pipelines.customers_source_path", None)
    if source_path is None:
        catalog = spark.conf.get("pipelines.catalog", "dataops_template")
        target = spark.conf.get("pipelines.target", "dev")
        source_path = f"/Volumes/{catalog}/{target}/customers_raw/"

    if source_format == "cloudFiles":
        reader = (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "csv")
            .option("header", "true")
            .schema(BRONZE_SCHEMA)
            .load(source_path)
        )
    else:
        reader = (
            spark.readStream.format("csv")
            .option("header", "true")
            .schema(BRONZE_SCHEMA)
            .load(source_path)
        )

    return reader.select(
        *[F.col(f.name) for f in BRONZE_SCHEMA],
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingested_at"),
    )


@dp.table
def customers_silver():
    spark = SparkSession.getActiveSession()
    quality_mode = spark.conf.get("pipelines.quality_mode", "drop")

    for rule in CUSTOMER_RULES:
        if rule.severity == "critical":
            dp.expect_or_fail(rule.name, rule.constraint)
        elif rule.severity == "business_invalid":
            if quality_mode == "fail":
                dp.expect_or_fail(rule.name, rule.constraint)
            else:
                dp.expect_or_drop(rule.name, rule.constraint)
        elif rule.severity == "warning":
            dp.expect(rule.name, rule.constraint)

    bronze = dp.read_stream("customers_bronze")
    return transform_bronze_to_silver(bronze)


@dp.table
def customers_rejected():
    bronze = dp.read_stream("customers_bronze")
    candidates = transform_bronze_to_silver(bronze)
    return build_rejected(candidates, CUSTOMER_RULES)
