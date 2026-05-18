from pyspark.sql import DataFrame
from pyspark.sql.types import DecimalType, StringType, StructField, StructType, TimestampType

BRONZE_SCHEMA = StructType([
    StructField("order_id", StringType(), nullable=False),
    StructField("customer_id", StringType(), nullable=False),
    StructField("amount", DecimalType(10, 2), nullable=True),
    StructField("order_date", TimestampType(), nullable=True),
])


def transform_bronze_to_silver(bronze: DataFrame) -> DataFrame:
    raise NotImplementedError
