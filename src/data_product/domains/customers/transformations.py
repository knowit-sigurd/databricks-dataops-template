from pyspark.sql import DataFrame
from pyspark.sql.types import StringType, StructField, StructType

BRONZE_SCHEMA = StructType([
    StructField("customer_id", StringType(), nullable=False),
    StructField("name", StringType(), nullable=True),
    StructField("email", StringType(), nullable=True),
])


def transform_bronze_to_silver(bronze: DataFrame) -> DataFrame:
    raise NotImplementedError
