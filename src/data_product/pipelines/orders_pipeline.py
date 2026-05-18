from pyspark import pipelines as dp

from data_product.domains.orders.transformations import BRONZE_SCHEMA


@dp.table
def orders_bronze():
    return spark.createDataFrame([], BRONZE_SCHEMA)
