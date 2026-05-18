from pyspark import pipelines as dp
from pyspark.sql.types import StructType


@dp.materialized_view
def customer_orders_gold():
    return spark.createDataFrame([], StructType([]))
