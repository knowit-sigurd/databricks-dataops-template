from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql.types import DecimalType, StringType, StructField, StructType, TimestampType


@dp.materialized_view
def orders_gold():
    spark = SparkSession.getActiveSession()
    return spark.createDataFrame(
        [],
        StructType([
            StructField("customer_id", StringType(), nullable=True),
            StructField("name", StringType(), nullable=True),
            StructField("email", StringType(), nullable=True),
            StructField("order_id", StringType(), nullable=True),
            StructField("amount", DecimalType(10, 2), nullable=True),
            StructField("order_date", TimestampType(), nullable=True),
        ]),
    )
