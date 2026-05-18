from pyspark import pipelines as dp
from pyspark.sql.types import StructType

from data_product.domains.orders.transformations import BRONZE_SCHEMA


@dp.table
def orders_bronze():
    return spark.createDataFrame([], BRONZE_SCHEMA)


@dp.table
def orders_silver():
    return spark.createDataFrame([], StructType([]))


@dp.table
def orders_rejected():
    return spark.createDataFrame([], StructType([]))
