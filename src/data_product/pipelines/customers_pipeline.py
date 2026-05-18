from pyspark import pipelines as dp
from pyspark.sql.types import StructType

from data_product.domains.customers.transformations import BRONZE_SCHEMA


@dp.table
def customers_bronze():
    return spark.createDataFrame([], BRONZE_SCHEMA)


@dp.table
def customers_silver():
    return spark.createDataFrame([], StructType([]))


@dp.table
def customers_rejected():
    return spark.createDataFrame([], StructType([]))
