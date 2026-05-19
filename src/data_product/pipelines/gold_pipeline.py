from pyspark import pipelines as dp
from pyspark.sql import SparkSession

from data_product.domains.gold.transformations import build_customer_orders


@dp.materialized_view
def customer_order_summary():
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("pipelines.catalog", "dataops_template")
    target_schema = spark.conf.get("pipelines.target_schema", "dev")

    customers_silver = spark.read.table(f"{catalog}.{target_schema}.customers_silver")
    orders_silver = spark.read.table(f"{catalog}.{target_schema}.orders_silver")

    return build_customer_orders(customers_silver, orders_silver)
