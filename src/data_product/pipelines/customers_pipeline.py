from pyspark import pipelines as dp

from data_product.domains.customers.transformations import BRONZE_SCHEMA


@dp.table
def customers_bronze():
    return spark.createDataFrame([], BRONZE_SCHEMA)
