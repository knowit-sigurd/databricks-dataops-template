from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from data_product.domains.customers.transformations import BRONZE_SCHEMA


@dp.table
def customers_bronze():
    spark = SparkSession.getActiveSession()
    return (
        spark.readStream.format("rate").load()
        .where(F.lit(False))
        .select([F.lit(None).cast(f.dataType).alias(f.name) for f in BRONZE_SCHEMA])
    )
